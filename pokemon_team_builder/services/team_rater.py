"""Team Rater — valora un equipo PokePaste introducido por el usuario.

Implementa la feature "valorar equipo" descrita en ``docs/adr-team-rater.md``.
El roster es FIJO: nunca se propone cambiar/quitar un Pokémon; sólo se sugieren
ajustes de item / moveset / naturaleza / EVs.

Capa de ORQUESTACIÓN pura (ADR §2.2): se sienta POR ENCIMA de ``viability_rater``,
``synergy_engine``, ``pokemon_evaluator``, ``replica_exporter`` y ``team_generator``
e importa de ellos — nunca al revés (sin riesgo de import circular).

La única lógica genuinamente nueva es:
  (a) auto-detección de arquetipo (``detect_archetype``)  — B0
  (b) coherencia del set concreto (``_set_coherence``)     — B2
  (c) diff build-usuario vs recomendación builder           — B4

Todos los umbrales/pesos marcados ``# [UNCERTAIN] calibrate`` son puntos de
partida del ADR (§3.2, §4.2), calibrados con fixtures deterministas — NUNCA con
datos de meta inventados (memoria: nunca fabricar datos competitivos).
"""

from __future__ import annotations

from dataclasses import dataclass

from pokemon_team_builder.config import MAX_SP_TOTAL
from pokemon_team_builder.domain.models import TeamMember, TeamVariant
from pokemon_team_builder.services import replica_exporter
from pokemon_team_builder.services.pokemon_evaluator import evaluate_pokemon_quality
from pokemon_team_builder.services.synergy_engine import (
    analyze_coverage,
    assess_presence,
    derive_team_tags,
)
from pokemon_team_builder.services.team_generator import _derive_nature
from pokemon_team_builder.services.viability_rater import (
    _count_passive_liabilities,
    _count_speed_control,
    generate_explanation,
    score_team,
    variant_requires_speed_control,
)
from pokemon_team_builder.data.move_types import MOVE_TYPE as _MOVE_TYPE

# Reusa la tabla nature → (boosted, hindered) y el normalizador del preset
# builder (single source of truth; no duplicamos conocimiento de naturalezas).
from pokemon_team_builder.services.sp_preset_builder import _normalise_nature

# ── Arquetipos (NUNCA renombrar — son claves de archetype_weights.json) ──────
# El orden de _ARCHETYPE_ORDER refleja la prioridad de §3.2 (primera coincidencia
# gana); los 7 labels son fijos (ADR §1, principio 1).
ARCHETYPES: tuple[str, ...] = (
    "hyper_offense",
    "hard_trick_room",
    "bulky_offense",
    "weather_based",
    "stall",
    "balance",
    "perish_trap",
)

# ── Umbrales del clasificador (§3.2) ─────────────────────────────────────────
# [UNCERTAIN] calibrate — puntos de partida estructurales del ADR, NO datos de
# meta. Verificados contra el corpus de fixtures de test_team_rater.py.
_TR_SLOW_SPE: int = 60          # "miembro lento" para Trick Room (regla slow_trio)
_TR_MIN_SLOW: int = 2           # ≥2 lentos para que TR sea la estrategia
_HO_MIN_THREATS: int = 4        # ≥4 offensive_threat → hyper_offense
_STALL_MIN_DEFENSIVE: int = 3   # ≥3 defensive_pivot/walls → stall
_STALL_MAX_THREATS: int = 1     # y ≤1 offensive_threat
_BULKY_MIN_THREATS: int = 2     # 2–3 threats + ≥1 pivot → bulky_offense
_BULKY_MAX_THREATS: int = 3

# Umbral de baja confianza: por debajo, el equipo se valora como 'balance'
# (neutral) y se marca aviso de estrategia ambigua. Decisión de producto
# (resuelve §12 [DECISION NEEDED] a favor de balance+aviso).
LOW_CONFIDENCE_CUTOFF: float = 0.4

# Aviso emitido cuando la confianza < LOW_CONFIDENCE_CUTOFF.
AMBIGUOUS_STRATEGY_WARNING: str = (
    "Estrategia ambigua: el equipo no encaja claramente en ningún arquetipo "
    "(confianza baja); se valora como 'balance' (neutral)."
)


def _tag_counts(per_member_tags: list[list[str]]) -> dict[str, int]:
    """Cuenta cuántos miembros aportan cada tag (no instancias totales)."""
    counts: dict[str, int] = {}
    for tags in per_member_tags:
        for tag in set(tags):  # un miembro cuenta una vez por tag
            counts[tag] = counts.get(tag, 0) + 1
    return counts


def _confidence(consistent_members: int, total: int) -> float:
    """Fracción de miembros cuyos tags son consistentes con el arquetipo elegido.

    ADR §3.2: confidence = miembros_consistentes / total, clamp [0,1].
    """
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, consistent_members / total))


def detect_archetype(variant: TeamVariant) -> tuple[str, float]:
    """Clasifica un ``TeamVariant`` en uno de los 7 arquetipos (ADR §3.2).

    Devuelve ``(archetype, confidence)`` con ``confidence ∈ [0,1]``.

    Reglas ordenadas, primera coincidencia gana (los arquetipos VGC no son
    mutuamente excluyentes; elegimos el dominante). Todas las señales se REUSAN
    de servicios existentes — ninguna lógica de juego nueva:

      1. hard_trick_room — ≥1 trick_room_setter Y ≥2 miembros con spe ≤ 60.
      2. weather_based    — ≥1 weather_setter Y ≥1 weather_abuser (en miembro distinto).
      3. perish_trap      — perish-song en cualquier moveset.
      4. hyper_offense    — ≥4 offensive_threat Y _count_speed_control ≥ 1.
      5. stall            — ≥3 defensive_pivot Y ≤1 offensive_threat.
      6. bulky_offense    — 2–3 offensive_threat Y ≥1 defensive_pivot.
      7. balance          — fallback (pesos por defecto 1.0).

    La confianza es la fracción de miembros consistentes con el arquetipo
    elegido. El consumidor (``rate_team``) decide qué hacer con confianza baja
    (< LOW_CONFIDENCE_CUTOFF): valorar como 'balance' + aviso.
    """
    members = variant.members
    total = len(members)
    per_member_tags = derive_team_tags(variant)
    counts = _tag_counts(per_member_tags)

    threats = counts.get("offensive_threat", 0)
    tr_setters = counts.get("trick_room_setter", 0)
    weather_setters = counts.get("weather_setter", 0)
    weather_abusers = counts.get("weather_abuser", 0)
    defensive_pivots = counts.get("defensive_pivot", 0)
    speed_control = _count_speed_control(members)

    slow_members = sum(1 for m in members if m.pokemon.base_stats.spe <= _TR_SLOW_SPE)
    has_perish = any(
        "perish-song" in {mv.strip().lower() for mv in m.moves} for m in members
    )

    # 1. hard_trick_room — setter de TR + masa de lentos que lo abusen.
    if tr_setters >= 1 and slow_members >= _TR_MIN_SLOW:
        # Consistentes: setters de TR + abusers (lentos ofensivos marcados
        # trick_room_abuser por derive_team_tags) + el resto de lentos.
        abusers = counts.get("trick_room_abuser", 0)
        consistent = max(slow_members, tr_setters + abusers)
        return "hard_trick_room", _confidence(consistent, total)

    # 2. weather_based — setter Y abuser (en miembro distinto: el abuser se marca
    #    sólo si hay un setter del clima correcto en OTRO miembro, vía
    #    derive_team_tags → garantizado distinto).
    if weather_setters >= 1 and weather_abusers >= 1:
        consistent = weather_setters + weather_abusers
        return "weather_based", _confidence(consistent, total)

    # 3. perish_trap — perish nunca es incidental en M-A.
    if has_perish:
        # Consistencia: miembros con perish + control de velocidad (el trap
        # necesita atrapar y agotar turnos). Conservador: cuenta los portadores
        # de perish como el núcleo.
        perish_carriers = sum(
            1
            for m in members
            if "perish-song" in {mv.strip().lower() for mv in m.moves}
        )
        consistent = perish_carriers + min(int(speed_control), total - perish_carriers)
        return "perish_trap", _confidence(consistent, total)

    # 4. hyper_offense — masa de amenazas + al menos un control de velocidad.
    if threats >= _HO_MIN_THREATS and speed_control >= 1.0:
        return "hyper_offense", _confidence(threats, total)

    # 5. stall — muros/pivotes dominan y casi sin amenazas.
    if defensive_pivots >= _STALL_MIN_DEFENSIVE and threats <= _STALL_MAX_THREATS:
        return "stall", _confidence(defensive_pivots, total)

    # 6. bulky_offense — mezcla de amenazas y al menos un pivote defensivo.
    if _BULKY_MIN_THREATS <= threats <= _BULKY_MAX_THREATS and defensive_pivots >= 1:
        consistent = threats + defensive_pivots
        return "bulky_offense", _confidence(consistent, total)

    # 7. balance — fallback. La confianza refleja cuán "ofensivamente sano" es
    #    el equipo (fracción de amenazas): un equipo de puras amenazas que no
    #    llega al umbral HO sigue siendo coherentemente ofensivo → confianza
    #    media-alta; un equipo sin identidad → confianza baja → aviso ambiguo.
    return "balance", _confidence(threats, total)


# ── B2: coherencia del set concreto (ADR §4.1) ───────────────────────────────
# Magnitudes verbatim del ADR §4.1. [UNCERTAIN] calibrate — invierten las
# invariantes que el builder YA aplica al GENERAR; aquí las aplicamos como
# checklist al set parseado del usuario. Sin conocimiento de juego nuevo:
# reusamos _MOVE_CATEGORY / _offensive_category / _derive_nature / MOVE_TYPE /
# _normalise_nature.
_PEN_DEAD_MOVE: float = 0.15
_PEN_DEAD_MOVE_CAP: float = 0.30
_PEN_NATURE_MISMATCH: float = 0.10
_PEN_EV_WASTE: float = 0.10
_PEN_SP_NOT_MAXED: float = 0.05
_PEN_NO_STAB: float = 0.10

# Tolerance for the PokePaste EV→SP round-trip artifact (Tecle Brief #1):
# the parser converts EVs to SP via floor division by 8 (pokepaste_parser
# `val // 8`), so a fully-invested competitive spread (508 EVs, e.g. 252/252/4)
# lands at ~62 SP, never the 66 cap — a maxed standard Showdown spread CANNOT
# reach 66. Treating sp_total within this tolerance of the cap as "maxed"
# stops the rater firing a spurious "SP sin maximizar" penalty + EV suggestion
# on every member of every real paste. A genuinely under-invested set
# (total below MAX_SP_TOTAL - tolerance) still flags. Fix lives at the
# consumer, not the parser, to keep the /import contract stable.
_SP_MAXED_TOLERANCE: int = 6
_SP_MAXED_FLOOR: int = MAX_SP_TOTAL - _SP_MAXED_TOLERANCE  # 60

# Naturaleza-stat → categoría ofensiva que esa naturaleza favorece.
_BOOSTED_TO_CATEGORY: dict[str, str] = {"atk": "physical", "spa": "special"}


def _invested_offensive_category(member: TeamMember) -> str | None:
    """Categoría ofensiva COMPROMETIDA del build del usuario, o None.

    Requerimos compromiso ofensivo CLARO para evitar marcar como "muerta" una
    move de cobertura legítima de la categoría opuesta (un atacante físico
    suele llevar una de cobertura especial, y a la inversa — esto es normal,
    NO el bug Abomasnow). Reglas:

      - Naturaleza OFENSIVA (boostea atk → physical / spa → special):
          · si los EVs concuerdan o son neutros → esa categoría (compromiso).
          · si los EVs contradicen (nat física + EVs especiales) → None
            (build contradictorio; lo capturan nature/EV-waste, no move-muerto).
      - Naturaleza NEUTRA o DEFENSIVA (boostea def/spd/hp, o sin boost): NO hay
        compromiso ofensivo de categoría → None. Un mon defensivo con EVs en
        una stat de ataque NO está "comprometido" a esa categoría al punto de
        que la cobertura opuesta sea muerta (caso Forretress Impish + bug-buzz).

    El caso Abomasnow (Adamant = nat física + EVs atk) → "physical", de modo
    que Ice Beam (especial) se marca correctamente como move muerto.
    """
    boosted, _ = _normalise_nature(member.nature)
    nature_cat = _BOOSTED_TO_CATEGORY.get(boosted) if boosted else None
    if nature_cat is None:
        # Naturaleza neutra/defensiva → sin compromiso ofensivo de categoría.
        return None

    sp = member.sp_distribution
    if sp.atk > sp.spa:
        ev_cat: str | None = "physical"
    elif sp.spa > sp.atk:
        ev_cat = "special"
    else:
        ev_cat = None  # EVs neutros → la naturaleza manda.

    if ev_cat is not None and ev_cat != nature_cat:
        return None  # contradicción nature↔EV; no marcamos move muerto aquí.
    return nature_cat


def _damaging_moves(moves: list[str]) -> list[str]:
    """Moves con categoría de daño conocida (physical/special)."""
    out: list[str] = []
    for mv in moves:
        cat = replica_exporter._MOVE_CATEGORY.get(mv.strip().lower())
        if cat in ("physical", "special"):
            out.append(mv.strip().lower())
    return out


def _set_coherence(member: TeamMember, variant: TeamVariant) -> tuple[float, list[str]]:
    """Coherencia del set concreto del usuario en [0,1] + razones (ADR §4.1).

    Empieza en 1.0 y resta penalizaciones deterministas. ``variant`` se acepta
    por la firma del ADR (B2) aunque las señales actuales son por-miembro;
    permite futuras penalizaciones con contexto de equipo sin romper la firma.

    Checklist (cada detección reusa primitivas existentes):
      - Move muerto: move atacante cuya categoría contradice la inversión
        nature/EV del build (−0.15 c/u, cap −0.30).
      - Naturaleza ↔ moveset: nature del usuario ≠ _derive_nature de los moves
        (−0.10).
      - EV desperdiciado: SP en una stat ofensiva que el moveset no usa
        (atk SP en set all-special, o al revés) (−0.10).
      - SP no maximizado: total SP < MAX_SP_TOTAL (66) (−0.05).
      - Sin STAB: cero moves de daño del propio tipo del mon (−0.10).
    """
    reasons: list[str] = []
    penalty = 0.0

    moves = [m.strip().lower() for m in member.moves]
    damaging = _damaging_moves(moves)
    invested = _invested_offensive_category(member)

    # ── Move muerto ──────────────────────────────────────────────────────
    # Sólo cuando el build tiene una categoría de inversión clara (invested
    # no None): un move de daño de la categoría OPUESTA es "muerto" (sus EVs/
    # naturaleza no lo potencian — el bug clase Abomasnow Ice Beam).
    if invested is not None:
        dead = [mv for mv in damaging
                if replica_exporter._MOVE_CATEGORY.get(mv) != invested]
        if dead:
            dead_penalty = min(_PEN_DEAD_MOVE * len(dead), _PEN_DEAD_MOVE_CAP)
            penalty += dead_penalty
            cat_es = "físico" if invested == "physical" else "especial"
            reasons.append(
                f"move(s) muerto(s) — tu build es {cat_es} pero "
                f"{', '.join(dead)} es de la categoría opuesta"
            )

    # ── Naturaleza ↔ moveset ──────────────────────────────────────────────
    primary = member.role[0] if member.role else "physical_sweeper"
    recommended_nature = _derive_nature(primary, list(member.role), moves)
    if member.nature.strip().lower() != recommended_nature.strip().lower():
        # Sólo penaliza si la naturaleza del usuario boostea una stat ofensiva
        # que el moveset no usa (ADR §4.1: "boosts the stat the moveset
        # doesn't use"). Una naturaleza defensiva distinta NO es incoherente.
        boosted, _ = _normalise_nature(member.nature)
        boosted_cat = _BOOSTED_TO_CATEGORY.get(boosted) if boosted else None
        from pokemon_team_builder.services.team_generator import (
            _dominant_attack_category,
        )
        dom_cat = _dominant_attack_category(moves)
        if boosted_cat is not None and dom_cat is not None and boosted_cat != dom_cat:
            penalty += _PEN_NATURE_MISMATCH
            reasons.append(
                f"naturaleza {member.nature} incoherente con el moveset "
                f"(recomendada: {recommended_nature})"
            )

    # ── EV desperdiciado ──────────────────────────────────────────────────
    # SP en la stat ofensiva OPUESTA a la categoría invertida del build: esos
    # EVs no potencian ningún move de la categoría dominante. Anclamos al
    # mismo ``invested`` que el move-muerto para NO contradecirnos (si el build
    # es físico, los EVs físicos NUNCA son "desperdicio" aunque la tabla curada
    # _MOVE_CATEGORY —~150 moves, no exhaustiva— no reconozca el STAB físico).
    # Sólo penaliza el desperdicio claro: invertir en la stat contraria.
    sp = member.sp_distribution
    if invested == "physical" and sp.spa > 0 and sp.spa >= sp.atk:
        penalty += _PEN_EV_WASTE
        reasons.append(
            "EVs desperdiciados — inviertes en SpA pero tu build es físico"
        )
    elif invested == "special" and sp.atk > 0 and sp.atk >= sp.spa:
        penalty += _PEN_EV_WASTE
        reasons.append(
            "EVs desperdiciados — inviertes en Atk pero tu build es especial"
        )

    # ── SP no maximizado ──────────────────────────────────────────────────
    # Only a REAL deficit (below the maxed floor) counts; a standard paste at
    # ~62 SP is the EV→SP floor-division artifact, not under-investment
    # (see _SP_MAXED_TOLERANCE).
    sp_total = sp.hp + sp.atk + sp.def_ + sp.spa + sp.spd + sp.spe
    if sp_total < _SP_MAXED_FLOOR:
        penalty += _PEN_SP_NOT_MAXED
        reasons.append(
            f"SP sin maximizar ({sp_total}/{MAX_SP_TOTAL})"
        )

    # ── Sin STAB ──────────────────────────────────────────────────────────
    # CONSERVADOR: sólo concluimos "sin STAB" cuando tenemos info de tipo
    # COMPLETA de los moves de daño (todos en _MOVE_TYPE) y ninguno coincide
    # con los tipos del mon. _MOVE_TYPE/_MOVE_CATEGORY son tablas curadas e
    # incompletas (~150 moves); si el STAB del mon no está en ellas (p.ej.
    # Heavy Slam de Aggron), antes salía un FALSO "sin STAB". Si algún move de
    # daño tiene tipo desconocido — o no hay moves de daño reconocidos — no
    # podemos descartar el STAB, así que NO lo marcamos.
    own_types = {t.strip().lower() for t in member.pokemon.types}
    move_types = [_MOVE_TYPE.get(mv) for mv in damaging]
    all_types_known = bool(damaging) and all(t is not None for t in move_types)
    if all_types_known and not any(t in own_types for t in move_types):
        penalty += _PEN_NO_STAB
        reasons.append("sin STAB — ningún move de daño es del tipo del Pokémon")

    coherence = max(0.0, min(1.0, 1.0 - penalty))
    return coherence, reasons


# ── B3: nota por Pokémon (1–100) (ADR §4) ────────────────────────────────────

# Pesos de la nota por Pokémon (decisión de producto, §4.2): fit domina.
W_FIT: float = 0.50
W_COHERENCE: float = 0.30
W_INTRINSIC: float = 0.20

# Pesos internos de la componente fit (§4.1). [UNCERTAIN] calibrate.
_FIT_W_PRESENCE: float = 0.4
_FIT_W_TAG_NEED: float = 0.4
_FIT_W_MARGINAL: float = 0.2

# Needed-tags por arquetipo (§4.1): DERIVADO de las señales §3 (no es dato
# competitivo nuevo — es la misma taxonomía de derive_doubles_tags). Un mon que
# aporta un tag que el equipo necesita puntúa alto en fit; uno redundante, medio;
# uno fuera de estrategia, bajo. 'balance' no exige tags concretos (neutral).
_NEEDED_TAGS_BY_ARCHETYPE: dict[str, frozenset[str]] = {
    "hyper_offense":   frozenset({"offensive_threat", "speed_control"}),
    "hard_trick_room": frozenset({"trick_room_setter", "trick_room_abuser"}),
    "weather_based":   frozenset({"weather_setter", "weather_abuser"}),
    "stall":           frozenset({"defensive_pivot", "support_enabler"}),
    "bulky_offense":   frozenset({"offensive_threat", "defensive_pivot"}),
    "perish_trap":     frozenset({"speed_control", "support_enabler"}),
    "balance":         frozenset(),  # sin tags exigidos → fit neutral en tags
}


@dataclass(frozen=True)
class Suggestion:
    """Sugerencia concreta de ajuste (item/moveset/naturaleza/EVs) — §6."""

    kind: str               # "move_swap" | "nature" | "evs" | "item"
    target_field: str       # "slot_2" | "nature" | "sp_distribution" | "item"
    from_value: str
    to_value: str
    reason_es: str
    priority: int           # 0 = más alta


@dataclass(frozen=True)
class MemberRating:
    """Valoración de un miembro (§6). Índice-alineado con el variant parseado."""

    name: str
    score: int              # 1..100
    fit: float              # [0,1]
    intrinsic: float        # [0.5,1.0] (C6)
    coherence: float        # [0,1]
    moves: list[str]        # los 4 moves del set del usuario (para la UI)
    strengths: list[str]
    weaknesses: list[str]
    suggestions: list[Suggestion]


def _tag_need_match(
    member_tags: list[str], archetype: str, team_tag_counts: dict[str, int]
) -> float:
    """¿Aporta el miembro un tag que el equipo necesita para el arquetipo?

    Devuelve [0,1]:
      - 1.0 si aporta ≥1 needed-tag del que el equipo va escaso (sólo este
        miembro u otro más lo tienen) → pieza clave.
      - 0.6 si aporta un needed-tag pero el equipo va sobrado (redundante).
      - 0.3 si no aporta ningún needed-tag pero sí algún tag útil (offensive_
        threat / support_enabler) → contribuye genéricamente.
      - 0.0 si no aporta ningún tag (mon pasivo / fuera de estrategia).

    'balance' no exige tags → devuelve un 0.6 neutral para cualquier mon con
    presencia (no premia ni castiga por encaje de arquetipo).
    """
    needed = _NEEDED_TAGS_BY_ARCHETYPE.get(archetype, frozenset())
    member_set = set(member_tags)

    if not needed:  # balance
        return 0.6 if member_set else 0.3

    supplied_needed = member_set & needed
    if supplied_needed:
        # ¿El equipo va escaso de ese tag? (≤2 miembros lo aportan).
        scarce = any(team_tag_counts.get(t, 0) <= 2 for t in supplied_needed)
        return 1.0 if scarce else 0.6

    # No aporta needed-tags pero sí algo útil genérico.
    if member_set & {"offensive_threat", "support_enabler", "speed_control"}:
        return 0.3
    return 0.0


def _marginal_coverage_contribution(variant: TeamVariant, index: int) -> float:
    """Contribución marginal del miembro a la cobertura ofensiva del equipo.

    Reusa analyze_coverage con y sin las moves del miembro: si quitarlo ABRE
    huecos ofensivos, su contribución es alta. Devuelve [0,1].
    """
    members = variant.members
    pokemons = [m.pokemon for m in members]
    movesets = [list(m.moves) for m in members]

    full = analyze_coverage(pokemons, movesets=movesets)
    # Sin las moves del miembro (moveset vacío → no aporta tipos de cobertura).
    without_movesets = [
        [] if i == index else list(members[i].moves) for i in range(len(members))
    ]
    without = analyze_coverage(pokemons, movesets=without_movesets)

    opened = len(without.offensive_gaps) - len(full.offensive_gaps)
    if opened <= 0:
        return 0.0
    # Normaliza: abrir ≥3 huecos = contribución máxima (1.0).
    return min(1.0, opened / 3.0)


def _compute_fit(
    variant: TeamVariant,
    index: int,
    archetype: str,
    per_member_tags: list[list[str]],
    team_tag_counts: dict[str, int],
) -> float:
    """Componente fit ∈ [0,1] (§4.1): presencia + encaje-de-tag + marginal."""
    member = variant.members[index]
    presence = assess_presence(
        member.pokemon, moves=list(member.moves), ability=member.ability
    )
    tag_match = _tag_need_match(per_member_tags[index], archetype, team_tag_counts)
    marginal = _marginal_coverage_contribution(variant, index)
    fit = (
        _FIT_W_PRESENCE * presence.presence_weight
        + _FIT_W_TAG_NEED * tag_match
        + _FIT_W_MARGINAL * marginal
    )
    return max(0.0, min(1.0, fit))


def rate_member(variant: TeamVariant, index: int, archetype: str) -> MemberRating:
    """Valora un miembro (1–100) combinando fit/coherencia/intrínseco (§4.2).

    note = round(100 * clamp(W_FIT*fit + W_COHERENCE*coh + W_INTRINSIC*intr, 0, 1))
    con piso 1 (el usuario pidió 1–100, nunca 0).

    Las strengths/weaknesses y suggestions se rellenan en bloques posteriores
    (B4/B5); aquí van como listas vacías para mantener la firma estable.
    """
    member = variant.members[index]
    per_member_tags = derive_team_tags(variant)
    team_tag_counts = _tag_counts(per_member_tags)

    fit = _compute_fit(variant, index, archetype, per_member_tags, team_tag_counts)
    quality = evaluate_pokemon_quality(member.pokemon)
    intrinsic = quality.score
    coherence, reasons = _set_coherence(member, variant)

    blended = W_FIT * fit + W_COHERENCE * coherence + W_INTRINSIC * intrinsic
    blended = max(0.0, min(1.0, blended))
    score = round(100 * blended)
    score = max(1, min(100, score))

    strengths, weaknesses = _member_strengths_weaknesses(
        variant, index, archetype, per_member_tags, team_tag_counts,
        fit, coherence, quality, reasons,
    )

    return MemberRating(
        name=member.pokemon.name,
        score=score,
        fit=fit,
        intrinsic=intrinsic,
        coherence=coherence,
        moves=list(member.moves),
        strengths=strengths,
        weaknesses=weaknesses,
        suggestions=_build_suggestions(variant, index, archetype, reasons),
    )


def _member_strengths_weaknesses(
    variant: TeamVariant,
    index: int,
    archetype: str,
    per_member_tags: list[list[str]],
    team_tag_counts: dict[str, int],
    fit: float,
    coherence: float,
    quality,
    coherence_reasons: list[str],
) -> tuple[list[str], list[str]]:
    """Puntos fuertes/débiles por mon (§5.4), derivados de las mismas señales."""
    member = variant.members[index]
    strengths: list[str] = []
    weaknesses: list[str] = []

    presence = assess_presence(
        member.pokemon, moves=list(member.moves), ability=member.ability
    )

    # Fuertes
    needed = _NEEDED_TAGS_BY_ARCHETYPE.get(archetype, frozenset())
    supplied_needed = set(per_member_tags[index]) & needed
    scarce_needed = {t for t in supplied_needed if team_tag_counts.get(t, 0) <= 2}
    if scarce_needed:
        strengths.append(
            "pieza clave de la estrategia ("
            + ", ".join(sorted(scarce_needed)) + ")"
        )
    if coherence >= 0.99:
        strengths.append("set coherente (naturaleza/EVs/moves alineados)")
    if quality.score >= 0.99:
        strengths.append("Pokémon de alto valor intrínseco")
    if presence.has_disruption:
        strengths.append(
            "aporta disrupción (" + ", ".join(presence.disruption_sources) + ")"
        )

    # Débiles
    if presence.is_passive_liability:
        weaknesses.append(
            "lastre pasivo: sin presencia ofensiva ni disrupción (el rival lo ignora)"
        )
    # Flags de C6 verbatim (§5.4).
    for flag in quality.flags:
        weaknesses.append(flag)
    # Razones de incoherencia del set.
    for reason in coherence_reasons:
        weaknesses.append(reason)
    if fit < 0.3 and not presence.is_passive_liability:
        weaknesses.append("encaje débil con la estrategia detectada")

    return strengths, weaknesses


# ── B4: motor de sugerencias (diff build-usuario vs recomendación) (ADR §5) ──
# Prioridades (§5.3): dead move > item ilegal > EVs desperdiciados > sidegrade.
_PRIO_DEAD_MOVE: int = 0
_PRIO_ILLEGAL_ITEM: int = 1
_PRIO_WASTED_EVS: int = 2
_PRIO_NATURE: int = 3
_PRIO_SIDEGRADE: int = 4

_VALID_SUGGESTION_KINDS: frozenset[str] = frozenset(
    {"move_swap", "nature", "evs", "item"}
)


def _sp_summary(sp) -> str:
    """Resumen legible de un SPDistribution (sólo stats > 0)."""
    parts = []
    for label, val in (
        ("HP", sp.hp), ("Atk", sp.atk), ("Def", sp.def_),
        ("SpA", sp.spa), ("SpD", sp.spd), ("Spe", sp.spe),
    ):
        if val > 0:
            parts.append(f"{val} {label}")
    return " / ".join(parts) if parts else "—"


def _build_suggestions(
    variant: TeamVariant,
    index: int,
    archetype: str,
    coherence_reasons: list[str],
) -> list[Suggestion]:
    """Diff del build del usuario vs recommend_member_build → sugerencias (§5.3).

    RESTRICCIÓN DURA: jamás sugiere cambiar de especie — se recomputa siempre
    sobre el MISMO PokemonData (todas las kinds ∈ {move_swap, nature, evs, item}).
    Conservador por defecto: sólo emite cuando el diff es MATERIAL.
    """
    from pokemon_team_builder.data.mega_loader import load_mega_evolutions
    from pokemon_team_builder.services.team_generator import (
        recommend_member_build,
        _load_champions_legal_items,
    )

    member = variant.members[index]
    rec = recommend_member_build(
        member.pokemon, list(member.role),
        archetype=archetype, team_sheet=variant.team_sheet,
    )

    suggestions: list[Suggestion] = []
    user_moves = [m.strip().lower() for m in member.moves]
    rec_moves = [m.strip().lower() for m in rec.moves]

    # ── 1. Move swap — sólo para moves muertos que la coherencia ya marcó
    #    (§5.3: no spamear; sólo swaps flagueados o que cierran hueco). El
    #    move recomendado del mismo tipo/categoría que el muerto es el destino.
    dead_moves = _dead_moves_from_reasons(member, coherence_reasons)
    for dead in dead_moves:
        replacement = _pick_replacement(dead, user_moves, rec_moves, member)
        if replacement is None:
            continue
        slot = user_moves.index(dead) if dead in user_moves else 0
        suggestions.append(Suggestion(
            kind="move_swap",
            target_field=f"slot_{slot + 1}",
            from_value=dead,
            to_value=replacement,
            reason_es=(
                f"{dead} es de categoría contraria a tu build (move muerto); "
                f"cámbialo por {replacement} o ajusta naturaleza/EVs"
            ),
            priority=_PRIO_DEAD_MOVE,
        ))

    # ── 2. Item — sólo con razón clara: ilegal en M-A, o el recomendado domina
    #    por necesidad concreta. Conservador (muchos items son sidegrades).
    #    Las MEGA-PIEDRAS son legales-por-datos-de-mega (viven en
    #    mega_evolutions.json, NO en champions_legal_items.json), así que se
    #    excluyen del flag de ilegalidad — si no, CUALQUIER mega-piedra
    #    (Aggronite, Charizardite, ...) saldría como "ilegal, usa Shell Bell".
    legal_items, _ = _load_champions_legal_items()
    mega_stones = {
        mf.mega_stone
        for forms in load_mega_evolutions().values()
        for mf in forms
    }
    user_item = member.item.strip()
    if (
        legal_items
        and user_item
        and user_item not in legal_items
        and user_item not in mega_stones
    ):
        suggestions.append(Suggestion(
            kind="item",
            target_field="item",
            from_value=user_item,
            to_value=rec.item,
            reason_es=(
                f"{user_item} no es legal en Pokémon Champions M-A; "
                f"el builder recomienda {rec.item}"
            ),
            priority=_PRIO_ILLEGAL_ITEM,
        ))

    # ── 3. EVs — SP desperdiciado en stat ofensiva no usada, o total < 66.
    sp = member.sp_distribution
    sp_total = sp.hp + sp.atk + sp.def_ + sp.spa + sp.spd + sp.spe
    # Suggest an EV change only on a genuine EV-waste reason OR a REAL SP
    # deficit — never on the ~62-SP EV→SP round-trip artifact (Brief #1).
    ev_reason = next((r for r in coherence_reasons if "EVs desperdiciados" in r), None)
    if ev_reason is not None or sp_total < _SP_MAXED_FLOOR:
        why = (
            ev_reason
            if ev_reason is not None
            else f"SP sin maximizar ({sp_total}/{MAX_SP_TOTAL})"
        )
        suggestions.append(Suggestion(
            kind="evs",
            target_field="sp_distribution",
            from_value=_sp_summary(sp),
            to_value=_sp_summary(rec.sp_distribution),
            reason_es=f"{why}; usa el spread recomendado",
            priority=_PRIO_WASTED_EVS,
        ))

    # ── 4. Naturaleza — sólo si la del usuario boostea una stat ofensiva no
    #    usada (la coherencia ya lo marcó) y difiere de la recomendada.
    nature_reason = next(
        (r for r in coherence_reasons if "naturaleza" in r.lower()), None
    )
    if (
        nature_reason is not None
        and member.nature.strip().lower() != rec.nature.strip().lower()
    ):
        suggestions.append(Suggestion(
            kind="nature",
            target_field="nature",
            from_value=member.nature,
            to_value=rec.nature,
            reason_es=(
                f"tu naturaleza {member.nature} potencia una stat que el moveset "
                f"no usa; el builder recomienda {rec.nature}"
            ),
            priority=_PRIO_NATURE,
        ))

    suggestions.sort(key=lambda s: s.priority)
    return suggestions


def _dead_moves_from_reasons(
    member: TeamMember, coherence_reasons: list[str]
) -> list[str]:
    """Extrae los slugs de moves muertas señaladas por _set_coherence.

    Recalcula la categoría invertida y lista las moves de daño de la categoría
    opuesta — exactamente las que disparan el penalty (sin re-parsear el texto).
    """
    has_dead = any("muerto" in r.lower() for r in coherence_reasons)
    if not has_dead:
        return []
    invested = _invested_offensive_category(member)
    if invested is None:
        return []
    moves = [m.strip().lower() for m in member.moves]
    return [
        mv for mv in _damaging_moves(moves)
        if replica_exporter._MOVE_CATEGORY.get(mv) != invested
    ]


def _pick_replacement(
    dead: str, user_moves: list[str], rec_moves: list[str], member: TeamMember
) -> str | None:
    """Elige un reemplazo concreto para una move muerta.

    Preferencia: una move recomendada por el builder (rec_moves) que NO esté ya
    en el set del usuario y sea de la categoría correcta (el builder ya las
    selecciona category-coherentes). Si no hay candidato, no sugiere swap (no
    inventa moves).
    """
    invested = _invested_offensive_category(member)
    for cand in rec_moves:
        if cand in user_moves:
            continue
        cat = replica_exporter._MOVE_CATEGORY.get(cand)
        # El reemplazo ideal es de la categoría invertida (o categoría
        # desconocida — el builder ya la eligió coherente).
        if invested is None or cat is None or cat == invested:
            return cand
    return None


# ── B5: rate_team orquestador (ADR §5.4, §6) ─────────────────────────────────

@dataclass(frozen=True)
class TeamRating:
    """Valoración completa de un equipo (§6)."""

    score: float                  # 0..100 (reusa score_team)
    detected_archetype: str
    archetype_confidence: float   # [0,1]; UI muestra aviso si baja
    strengths: list[str]
    weaknesses: list[str]
    members: list[MemberRating]   # índice-alineado con el variant parseado
    import_warnings: list[str]


def _team_strengths_weaknesses(
    variant: TeamVariant,
    archetype: str,
    score: float,
    confidence: float,
    member_ratings: list[MemberRating],
) -> tuple[list[str], list[str]]:
    """Fuertes/débiles a nivel equipo (§5.4): generate_explanation + aumentos."""
    strengths: list[str] = []
    weaknesses: list[str] = []

    # Base: la prosa del scorer existente (reuso verbatim).
    explanation = generate_explanation(variant, score)
    strengths.append(explanation)

    # Aumentos sobre señales existentes.
    if confidence < LOW_CONFIDENCE_CUTOFF:
        weaknesses.append(AMBIGUOUS_STRATEGY_WARNING)

    if variant_requires_speed_control(variant, archetype):
        weaknesses.append(
            "sin control de velocidad suficiente — el equipo cede la iniciativa"
        )

    liabilities = _count_passive_liabilities(variant.members)
    if liabilities > 0:
        names = [
            m.pokemon.name
            for m in variant.members
            if assess_presence(
                m.pokemon, moves=list(m.moves), ability=m.ability
            ).is_passive_liability
        ]
        weaknesses.append(
            f"{liabilities} lastre(s) pasivo(s): {', '.join(names)}"
        )

    # Núcleo coherente: si la mayoría de miembros tienen sets coherentes.
    coherent = sum(1 for mr in member_ratings if mr.coherence >= 0.99)
    if coherent >= 4:
        strengths.append("la mayoría de los sets son coherentes y están maximizados")

    # Piezas clave del equipo.
    key_pieces = [mr.name for mr in member_ratings if mr.fit >= 0.8]
    if key_pieces:
        strengths.append("piezas clave: " + ", ".join(key_pieces))

    return strengths, weaknesses


def rate_team(
    variant: TeamVariant, import_warnings: list[str] | None = None
) -> TeamRating:
    """Orquesta la valoración completa de un equipo (§6.1).

    Flujo: detect_archetype → (regla de baja confianza) → score_team →
    rate_member por índice → fuertes/débiles a nivel equipo.

    DECISIÓN DE PRODUCTO (§12 [DECISION NEEDED]): si la confianza del
    clasificador < LOW_CONFIDENCE_CUTOFF (0.4), valoramos bajo 'balance'
    (neutral, pesos 1.0) para no castigar un equipo equilibrado por un
    arquetipo mal detectado, PERO seguimos mostrando el label detectado como
    pista y añadimos el aviso de estrategia ambigua.
    """
    warnings = list(import_warnings) if import_warnings else []

    detected, confidence = detect_archetype(variant)
    # Arquetipo usado para PUNTUAR: balance si la confianza es baja.
    scoring_archetype = (
        "balance" if confidence < LOW_CONFIDENCE_CUTOFF else detected
    )

    score, _flex = score_team(
        variant, archetype=scoring_archetype, team_sheet=variant.team_sheet
    )

    member_ratings = [
        rate_member(variant, i, scoring_archetype)
        for i in range(len(variant.members))
    ]

    strengths, weaknesses = _team_strengths_weaknesses(
        variant, scoring_archetype, score, confidence, member_ratings
    )

    return TeamRating(
        score=score,
        detected_archetype=detected,  # siempre el label detectado (pista UI)
        archetype_confidence=confidence,
        strengths=strengths,
        weaknesses=weaknesses,
        members=member_ratings,
        import_warnings=warnings,
    )
