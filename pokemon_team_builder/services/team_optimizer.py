"""Team Optimizer — optimizador greedy por-mon de la feature "Valorar equipo".

Implementa la adición (3) del ADR ``docs/adr-team-optimizer.md`` (§5). Es una
capa de ORQUESTACIÓN pura, igual que ``team_rater``: se sienta POR ENCIMA de
``team_rater`` (diff de sugerencias), ``team_generator`` (build coherente por
especie), ``viability_rater`` (nota del equipo) y ``replica_exporter``
(serialización), e importa de ellos — nunca al revés (sin ciclo).

NO introduce conocimiento competitivo nuevo. Sólo combina, por cada mon NO
fijado, ``recommend_member_build`` (qué build daría el builder a esa MISMA
especie), ``score_team`` (cuánto vale el equipo) y ``to_pokepaste``.

Invariantes duros (ADR §7), garantizados por construcción:
  - los miembros FIJADOS nunca cambian;
  - la ESPECIE (y ``mega_form``) nunca cambia — el build se recomputa sobre el
    mismo ``PokemonData`` y el ``model_copy`` conserva ``pokemon``/``mega_form``;
  - ``score_after >= score_before`` (criterio de aceptación: mejora ESTRICTA);
  - ``Σ(deltas) == delta_total`` (atribución marginal secuencial);
  - determinismo total (orden ascendente de índice; arquetipo fijado al inicio);
  - ``all-locked`` → no-op.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pokemon_team_builder.domain.models import TeamVariant
from pokemon_team_builder.services import team_rater
from pokemon_team_builder.services.replica_exporter import to_pokepaste
from pokemon_team_builder.services.team_generator import recommend_member_build
from pokemon_team_builder.services.team_rater import (
    LOW_CONFIDENCE_CUTOFF,
    Suggestion,
    _diff_to_suggestions,
    _set_coherence,
    detect_archetype,
)
from pokemon_team_builder.services.viability_rater import score_team

# Tolerancia de ruido de float para el criterio de mejora ESTRICTA (ADR §5.3.e).
EPSILON: float = 1e-9


@dataclass(frozen=True)
class AcceptedChange:
    """Un cambio aceptado por el greedy sobre un mon NO fijado (ADR §5.1)."""

    member_index: int
    member_name: str
    delta: float                    # mejora marginal atribuida a ESTE cambio (≥ 0)
    suggestions: list[Suggestion]   # diff build-usuario → build óptimo (reuso)


@dataclass(frozen=True)
class OptimizationResult:
    """Resultado completo del optimizador (ADR §5.1).

    Da AMBAS vistas: (a) resumen score_before→after + pokepaste_after;
    (b) lista ``changes`` rankeada desc por delta (orden de presentación).
    """

    score_before: float
    score_after: float
    delta_total: float              # score_after - score_before (≥ 0)
    detected_archetype: str
    archetype_confidence: float
    changes: list[AcceptedChange]
    pokepaste_after: str
    locked_indices: list[int]       # echo de los fijados (para la UI)
    import_warnings: list[str] = field(default_factory=list)


def optimize_team(
    variant: TeamVariant,
    locked_indices: list[int],
    import_warnings: list[str] | None = None,
) -> OptimizationResult:
    """Optimiza un equipo: greedy por-mon, UNA pasada, orden ascendente (§5.3).

    Por cada mon NO fijado (en orden de índice): recomputa el build coherente
    de la MISMA especie (``recommend_member_build``), construye un equipo
    candidato reemplazando sólo item/nature/EVs/moves/ability (nunca especie ni
    mega), lo puntúa, y acepta el cambio SÓLO si mejora ESTRICTAMENTE la nota
    global del equipo-en-progreso. Los fijados no se tocan jamás.

    El arquetipo de puntuación se fija UNA vez sobre el equipo original (ADR
    ADR-OPT-2): así ``score_before`` y ``score_after`` son comparables.
    """
    warnings = list(import_warnings) if import_warnings else []
    locked_set = set(locked_indices)

    # ── 0. Arquetipo y baseline (misma escala que el rater) ──────────────────
    detected, confidence = detect_archetype(variant)
    scoring_archetype = (
        "balance" if confidence < LOW_CONFIDENCE_CUTOFF else detected
    )
    team_sheet = variant.team_sheet

    score_before, _ = score_team(
        variant, archetype=scoring_archetype, team_sheet=team_sheet
    )

    # ── 1. Conjunto candidato — orden ascendente de índice (determinista) ────
    candidates = [i for i in range(len(variant.members)) if i not in locked_set]

    current_variant = variant
    current_score = score_before
    changes: list[AcceptedChange] = []

    # ── 2. Greedy por candidato (una sola pasada) ────────────────────────────
    for i in candidates:
        current_member = current_variant.members[i]

        # a. Build coherente ideal de la MISMA especie (imposible cambiar de
        #    especie: recomputa sobre current_member.pokemon).
        build = recommend_member_build(
            current_member.pokemon,
            list(current_member.role),
            archetype=scoring_archetype,
            team_sheet=team_sheet,
        )

        # b. Miembro candidato: sólo item/nature/EVs/moves/ability/role
        #    reemplazados; MISMO pokemon y mega_form (no se toca especie/mega).
        candidate_member = current_member.model_copy(update={
            "item": build.item,
            "nature": build.nature,
            "sp_distribution": build.sp_distribution,
            "moves": list(build.moves),
            "ability": build.ability,
            "role": list(build.roles),
        })

        # c. Equipo candidato (patrón inmutable de team_editor).
        new_members = list(current_variant.members)
        new_members[i] = candidate_member
        candidate_variant = current_variant.model_copy(
            update={"members": new_members}
        )

        # d. Nota del candidato (misma escala).
        cand_score, _ = score_team(
            candidate_variant, archetype=scoring_archetype, team_sheet=team_sheet
        )

        # e. Criterio de aceptación: mejora ESTRICTA.
        if cand_score > current_score + EPSILON:
            delta = cand_score - current_score
            # Diff build-usuario → sugerencias, reusando la maquinaria del
            # rater con el build YA calculado (sin recomputar). Las razones de
            # coherencia se calculan sobre el miembro ORIGINAL (lo que el
            # usuario tiene), que es lo que el diff describe.
            coherence_reasons = _set_coherence(current_member, current_variant)[1]
            suggestions = _diff_to_suggestions(
                current_member, build, coherence_reasons, scoring_archetype
            )
            changes.append(AcceptedChange(
                member_index=i,
                member_name=current_member.pokemon.name,
                delta=delta,
                suggestions=suggestions,
            ))
            current_variant = candidate_variant
            current_score = cand_score
        # Si no mejora: descartar (el mon conserva su build original).

    # ── 3. Ranking de presentación (desc por delta, desempate por índice) ────
    changes.sort(key=lambda c: (-c.delta, c.member_index))

    # ── 4. Salida ────────────────────────────────────────────────────────────
    score_after = current_score
    return OptimizationResult(
        score_before=score_before,
        score_after=score_after,
        delta_total=score_after - score_before,
        detected_archetype=detected,
        archetype_confidence=confidence,
        changes=changes,
        pokepaste_after=to_pokepaste(current_variant),
        locked_indices=sorted(locked_set),
        import_warnings=warnings,
    )
