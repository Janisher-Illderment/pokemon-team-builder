"""Phase 2b: favorite-first build flow — pick the partner and the slot-3
weakness-cover for the anchor *before* beam-search fills slots 4–6.

The previous greedy flow filled every slot to maximise role coverage,
which structurally cannot express "build around my favorite": the partner
in slot 2 was chosen to fill a missing role, not to synergise with slot 1.
This module replaces that with two deterministic phases:

  build_core_duo(anchor, archetype, pool, meta_service, role_map)
      -> (best_partner, synergy_score)

  cover_shared_weakness([anchor, partner], archetype, pool, role_map)
      -> slot_3

Phase 4 (beam search for slots 4–6) lives in team_generator. Designed to
be deterministic per (anchor, archetype, mega_preference, format) — ties
are broken on (name alphabetical, id).
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from pokemon_team_builder.config import (
    WEATHER_DEPENDENT_ABILITIES_FILE,
    WEATHER_SETTERS_FILE,
)
from pokemon_team_builder.data.archetype_weights_loader import (
    ArchetypeWeights,
    get_weights,
)
from pokemon_team_builder.domain.models import PokemonData
from pokemon_team_builder.services.meta_service import MetaService
from pokemon_team_builder.services.synergy_engine import assign_role

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Weather data — minimal lookup for partner synergy bonus
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_weather_dependent_abilities() -> dict[str, str]:
    """Return ``{ability_lower: weather_name}`` from the static data file.

    Missing or unparsable file → empty map (synergy bonus simply doesn't
    fire — same observable effect as if no member had a weather ability).
    """
    try:
        with open(WEATHER_DEPENDENT_ABILITIES_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        abilities = raw.get("abilities", {})
        return {
            ability.lower(): entry.get("weather", "")
            for ability, entry in abilities.items()
            if isinstance(entry, dict) and entry.get("weather")
        }
    except Exception as exc:
        _logger.warning(
            "weather_dependent_abilities.json load failed: %s: %s",
            type(exc).__name__, exc,
        )
        return {}


@lru_cache(maxsize=1)
def _load_weather_setters() -> dict[str, set[str]]:
    """Return ``{weather: {pokemon_name, ...}}`` of ability-based setters.

    Move setters (Sunny Day / Rain Dance etc.) are not enumerated here —
    they are checked by ``_knows_move`` against the candidate's move
    pool at scoring time.
    """
    try:
        with open(WEATHER_SETTERS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        setters_raw = raw.get("setters", {})
        out: dict[str, set[str]] = {}
        for weather, entry in setters_raw.items():
            if not isinstance(entry, dict):
                continue
            names: set[str] = set()
            for setter in entry.get("ability_setters", []):
                if isinstance(setter, dict) and "pokemon" in setter:
                    names.add(str(setter["pokemon"]).lower())
            out[weather] = names
        return out
    except Exception as exc:
        _logger.warning(
            "weather_setters.json load failed: %s: %s",
            type(exc).__name__, exc,
        )
        return {}


def _setters_for_weather(weather: str) -> set[str]:
    return _load_weather_setters().get(weather, set())


# ---------------------------------------------------------------------------
# Helpers — type and ability checks
# ---------------------------------------------------------------------------

def _resists_or_immune(member: PokemonData, attacking_type: str) -> bool:
    """True iff ``member`` takes ``< 1.0×`` from ``attacking_type``.

    Mirrors team_generator._resistant_or_immune — duplicated here so this
    module stays independent of the team_generator's internals.
    """
    return member.weaknesses.get(attacking_type, 1.0) < 1.0


def _weaknesses_2x_plus(member: PokemonData) -> set[str]:
    """Return the set of types ``member`` takes ``>= 2.0×`` from."""
    return {t for t, mult in member.weaknesses.items() if mult >= 2.0}


def _knows_move(member: PokemonData, move: str) -> bool:
    """Cheap membership check against the move pool — case-insensitive."""
    return move.lower() in {m.lower() for m in member.move_names}


def _has_weather_ability(member: PokemonData) -> str | None:
    """Return the weather that ``member``'s ability depends on, or None.

    Iterates abilities in declared order; first ability that maps to a
    weather wins. For multi-ability species this favours the first slot —
    matches the convention used in team_generator._pick_ability.
    """
    table = _load_weather_dependent_abilities()
    for ability in member.abilities:
        weather = table.get(ability.lower())
        if weather:
            return weather
    return None


# Trick Room setter detection: candidate must know Trick Room AND be on
# the slow side (spe ≤ 70). The Speed cap mirrors the soft TR setter
# threshold from synergy_engine — fast TR setters exist but they are not
# the canonical 'hard_trick_room partner' target.
_TR_SETTER_SPE_CAP: int = 70


def _is_trick_room_setter(member: PokemonData) -> bool:
    return (
        _knows_move(member, "trick-room")
        and member.base_stats.spe <= _TR_SETTER_SPE_CAP
    )


# HP cap below which a sweeper is treated as 'fragile' for hyper_offense
# redirect bonus. 70 HP is the historical cutoff (e.g. Gengar 60, Tapu
# Koko 70 — both want redirect support; Garchomp 108 does not).
_FRAGILE_HP_CAP: int = 70


def _is_fragile_sweeper(member: PokemonData, roles: list[str]) -> bool:
    return (
        member.base_stats.hp < _FRAGILE_HP_CAP
        and bool(set(roles) & {"physical_sweeper", "special_sweeper"})
    )


def _is_redirect_or_lead_support(roles: list[str]) -> bool:
    return bool(set(roles) & {"redirect", "lead_support"})


# ---------------------------------------------------------------------------
# Synergy score
# ---------------------------------------------------------------------------

def _synergy_score(
    anchor: PokemonData,
    candidate: PokemonData,
    archetype: str,
    role_map: dict[str, list[str]],
    meta_service: MetaService,
    *,
    weights: ArchetypeWeights | None = None,
) -> float:
    """Score ``candidate`` as a potential partner for ``anchor``.

    Components (per favorite-first-build spec):
      (a) Type complement   — anchor weaknesses that candidate resists,
                              weighted by ``archetype.coverage``.
      (b) Role complement   — bonus when candidate's roles differ from
                              anchor's, weighted by ``archetype.roles``.
                              ``hyper_offense`` SUPPRESSES this bonus so
                              two sweepers are eligible to form the core.
      (c) Ability / move    — weighted by ``archetype.weather_synergy``;
                              also gates the hard_trick_room TR-setter
                              bonus and the hyper_offense redirect bonus.
      (d) Meta presence     — fixed +3.0 when ``candidate`` appears in
                              ``anchor.teammates`` per MunchStats.

    ``weights`` is an optional override to avoid re-reading the loader in
    tight loops — passing None looks it up by archetype name.
    """
    if weights is None:
        weights = get_weights(archetype)

    anchor_roles = role_map.get(anchor.name, assign_role(anchor))
    cand_roles = role_map.get(candidate.name, assign_role(candidate))

    score = 0.0

    # (a) Type complement — each anchor weakness covered by the candidate
    #     contributes 1.0 * archetype.coverage.
    anchor_weak = _weaknesses_2x_plus(anchor)
    type_complement = 0.0
    for weak in anchor_weak:
        if _resists_or_immune(candidate, weak):
            type_complement += 1.0
    score += type_complement * weights.coverage

    # (b) Role complement — +0.5 * archetype.roles when the role sets
    #     differ. hyper_offense SUPPRESSES this bonus (a duplicate sweeper
    #     core is allowed and expected for that archetype).
    if archetype != "hyper_offense":
        if set(anchor_roles) != set(cand_roles):
            score += 0.5 * weights.roles

    # (c) Ability / move compatibility, weighted by weather_synergy.
    #     Several archetype-specific bonuses live here because they all
    #     describe "candidate makes anchor's strategy work."
    anchor_weather = _has_weather_ability(anchor)
    if anchor_weather is not None:
        # Anchor wants weather X — candidate that sets X is a top partner.
        weather_setters = _setters_for_weather(anchor_weather)
        if candidate.name.lower() in weather_setters:
            score += 3.0 * weights.weather_synergy

    if archetype == "hard_trick_room" and _is_trick_room_setter(candidate):
        # TR setter is the strategy-defining partner for hard_trick_room.
        # The spec scales this with ``weather_synergy`` but hard_trick_room
        # weights weather low (0.3) since TR teams ignore weather. To make
        # the bonus actually decisive we ALSO scale by ``roles`` and
        # ``bulk`` (TR teams care about role identity + bulk a lot). Sum
        # of these weights for hard_trick_room (0.3 + 1.2 + 1.3 = 2.8)
        # yields a ~3× headline bonus, which beats typical type-complement
        # margins.
        score += 3.0 * (weights.weather_synergy + weights.roles + weights.bulk)

    if archetype == "hyper_offense":
        # Fragile sweeper anchor benefits from redirect / lead_support
        # cover. Lower bonus than weather/TR pairings because the binding
        # is softer (anchor can survive without it, just less optimally).
        if _is_fragile_sweeper(anchor, anchor_roles) and _is_redirect_or_lead_support(cand_roles):
            score += 1.5 * weights.weather_synergy

    # (d) Meta presence — fixed weight (not archetype-scaled) so meta
    #     pairings remain visible even in archetypes that downweight
    #     other components.
    anchor_meta = meta_service.get(anchor.name)
    if anchor_meta is not None and candidate.name.lower() in {
        t.lower() for t in anchor_meta.teammates
    }:
        score += 3.0

    return score


def _sorted_for_determinism(pool: Iterable[PokemonData]) -> list[PokemonData]:
    """Stable name-then-id ordering — used as the tie-break for
    deterministic outputs.

    Why name first, id second: id is unique per species, but name is the
    surface identifier the user sees; sorting alphabetically by name
    matches the convention in heuristic_filter and keeps the determinism
    contract human-readable.
    """
    return sorted(pool, key=lambda p: (p.name, p.id))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_core_duo(
    anchor: PokemonData,
    archetype: str,
    legal_pool: list[PokemonData],
    meta_service: MetaService,
    role_map: dict[str, list[str]],
    *,
    anchor_is_mega: bool = False,
) -> tuple[PokemonData, float]:
    """Pick the single best partner for ``anchor`` given ``archetype``.

    Returns ``(partner, synergy_score)``. Raises ``ValueError`` only if
    ``legal_pool`` contains no candidates other than the anchor itself —
    that is a caller-side bug (pool resolution should have filtered).

    Determinism: ties on synergy score are broken by ``(name, id)``
    ascending. Two calls with the same inputs return the same partner.

    Mega Clause (Phase 4b hot-fix): when ``anchor_is_mega`` is True the
    anchor already occupies the team's single mega slot, so any candidate
    that *could* hold a Mega Stone is filtered out here — otherwise the
    seed [mega_anchor, mega_partner, slot3] would have
    ``_count_mega_potentials > 1`` and the beam search would prune every
    possible expansion, producing 0 variants silently.
    """
    weights = get_weights(archetype)

    # Filter out the anchor itself; everything else is a candidate.
    candidates = [c for c in legal_pool if c.name != anchor.name]
    if anchor_is_mega:
        candidates = [c for c in candidates if not c.megas]
    if not candidates:
        raise ValueError(
            f"build_core_duo: legal_pool has no candidates other than "
            f"the anchor '{anchor.name}'."
        )

    # Stable secondary sort first, then sort by score desc — Python's
    # sort is stable, so equal scores fall back to the (name, id) order.
    ordered = _sorted_for_determinism(candidates)
    scored: list[tuple[float, PokemonData]] = [
        (
            _synergy_score(
                anchor, cand, archetype, role_map, meta_service,
                weights=weights,
            ),
            cand,
        )
        for cand in ordered
    ]
    # Sort by score desc; stable sort preserves the deterministic
    # (name, id) tie-break from the pre-sort.
    scored.sort(key=lambda pair: -pair[0])
    best_score, best_partner = scored[0]
    return best_partner, best_score


def cover_shared_weakness(
    core_duo: list[PokemonData],
    archetype: str,
    legal_pool: list[PokemonData],
    role_map: dict[str, list[str]],
    *,
    anchor_is_mega: bool = False,
) -> PokemonData:
    """Pick slot 3 — the member that best covers the *shared* weakness of
    ``core_duo``.

    "Shared" = the INTERSECTION of weakness sets across all core_duo
    members. Slot 3 receives +1.0 for each shared weakness it resists or
    is immune to. Role complement and meta presence are NOT scored at
    this slot — slots 4–6 handle that via beam search. The point of the
    slot-3 phase is structural type coverage of the (anchor + partner)
    pair, not balance.

    Tie-break: ``(name, id)`` ascending. Raises ``ValueError`` only if
    ``legal_pool`` has nothing left to pick from.
    """
    if len(core_duo) < 1:
        raise ValueError("cover_shared_weakness: core_duo cannot be empty.")
    weights = get_weights(archetype)

    chosen_names = {m.name for m in core_duo}
    candidates = [c for c in legal_pool if c.name not in chosen_names]
    if anchor_is_mega:
        # Phase 4b hot-fix: anchor already owns the team's single mega
        # slot, so slot 3 candidates that could hold a Mega Stone would
        # poison the seed and starve the beam-search expansion.
        candidates = [c for c in candidates if not c.megas]
    if not candidates:
        raise ValueError(
            "cover_shared_weakness: legal_pool has no candidates left "
            "after removing core_duo members."
        )

    # Intersection of weaknesses across the duo. For a single-member
    # 'duo' (defensive coding — never happens in the real flow) this
    # collapses to that member's full weakness set.
    shared: set[str] = _weaknesses_2x_plus(core_duo[0])
    for member in core_duo[1:]:
        shared &= _weaknesses_2x_plus(member)

    ordered = _sorted_for_determinism(candidates)

    scored: list[tuple[float, PokemonData]] = []
    for cand in ordered:
        score = 0.0
        for weak in shared:
            if _resists_or_immune(cand, weak):
                score += 1.0
        # Use archetype.coverage as a uniform multiplier so the slot-3
        # importance scales with how much the archetype cares about
        # coverage. This matters because hyper_offense (coverage 1.3)
        # prefers a coverage-heavy slot 3 more strongly than stall
        # (coverage 0.8). Keeps the same ranking when only one candidate
        # covers a shared weakness — only nudges the tie-breaks.
        score *= weights.coverage

        # Light role-complement nudge: prefer a slot 3 whose role differs
        # from BOTH core members. Encourages the duo→trio composition to
        # diversify roles before beam search.
        core_role_sets = [set(role_map.get(m.name, assign_role(m))) for m in core_duo]
        cand_role_set = set(role_map.get(cand.name, assign_role(cand)))
        if all(cand_role_set != crs for crs in core_role_sets):
            score += 0.1 * weights.roles

        scored.append((score, cand))

    scored.sort(key=lambda pair: -pair[0])
    return scored[0][1]


__all__ = [
    "ArchetypeWeights",
    "build_core_duo",
    "cover_shared_weakness",
]
