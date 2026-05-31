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

from pokemon_team_builder.domain.models import TeamVariant
from pokemon_team_builder.services.synergy_engine import derive_team_tags
from pokemon_team_builder.services.viability_rater import _count_speed_control

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
