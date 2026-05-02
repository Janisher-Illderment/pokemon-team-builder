from __future__ import annotations

import json
from functools import lru_cache
from typing import Callable, Iterable

from pokemon_team_builder.config import (
    MAX_SP_TOTAL,
    ROLE_SP_TEMPLATES_FILE,
)
from pokemon_team_builder.data.legal_pool_loader import get_all_names
from pokemon_team_builder.domain.exceptions import TeamBuildError
from pokemon_team_builder.domain.models import (
    PokemonData,
    SPDistribution,
    TeamMember,
    TeamVariant,
)
from pokemon_team_builder.services import (
    pokemon_lookup,
    replica_exporter,
    viability_rater,
)
from pokemon_team_builder.services.synergy_engine import (
    ALL_TYPES,
    analyze_coverage,
    assign_role,
)


_DEFAULT_ITEM_BY_ROLE: dict[str, str] = {
    # Choice Band / Specs / Assault Vest / Life Orb are NOT in Champions.
    "physical_sweeper": "Weakness Policy",
    "special_sweeper": "Throat Spray",
    "physical_wall": "Rocky Helmet",
    "special_wall": "Leftovers",
    "lead_support": "Focus Sash",
    "trick_room_setter": "Mental Herb",
    "redirect": "Clear Amulet",
}
_FALLBACK_ITEM = "Choice Scarf"
# Champions-legal backup items (Serebii/MetaVGC confirmed). Order is
# preference: utility first, then type-boosting items so that even six
# same-role mons can each receive a distinct, importable item.
_BACKUP_ITEMS: tuple[str, ...] = (
    "Sitrus Berry",
    "Lum Berry",
    "Scope Lens",
    "Power Herb",
    "White Herb",
    "Shell Bell",
    "Loaded Dice",
    "Covert Cloak",
    "Focus Band",
    "Adrenaline Orb",
    "Safety Goggles",  # NOT Light Clay — Light Clay is NOT in Champions
    "King's Rock",
    "Mystic Water",
    "Charcoal",
    "Magnet",
    "Black Belt",
    "Soft Sand",
    "Sharp Beak",
    "Silver Powder",
    "Dragon Fang",
    "Spell Tag",
    "Miracle Seed",
    "Never-Melt Ice",
    "Poison Barb",
    "Metal Coat",
    "Black Glasses",
    "Twisted Spoon",
    "Hard Stone",
    "Silk Scarf",
    "Fairy Feather",
)

_SITUATIONAL_ABILITIES: frozenset[str] = frozenset({
    "sand-veil", "snow-cloak", "swift-swim", "chlorophyll",
    "solar-power", "sand-rush", "slush-rush", "surge-surfer",
    "leaf-guard", "flower-gift", "forecast",
})


_NATURE_BY_ROLE: dict[str, str] = {
    "physical_sweeper": "Jolly",
    "special_sweeper": "Timid",
    "physical_wall": "Impish",
    "special_wall": "Calm",
    "lead_support": "Jolly",
    "trick_room_setter": "Sassy",
    "redirect": "Calm",
}
_FALLBACK_NATURE = "Hardy"


_BEAM_WIDTH = 10
_HEURISTIC_POOL_LIMIT = 50


@lru_cache(maxsize=1)
def _load_sp_templates() -> dict[str, dict[str, int]]:
    with open(ROLE_SP_TEMPLATES_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError("role_sp_templates.json: estructura raiz invalida.")
    out: dict[str, dict[str, int]] = {}
    for role, template in raw.items():
        if not isinstance(template, dict):
            continue
        out[role] = {k: int(v) for k, v in template.items()}
    return out


def suggest_sp_distribution(pokemon: PokemonData, role: str) -> SPDistribution:
    """Pick an SP template for the role and return as SPDistribution.

    Unknown roles fall back to ``physical_sweeper`` if Atk >= SpA, else
    ``special_sweeper``. The JSON uses ``"def"`` as the key; SPDistribution
    uses ``def_`` internally — model_validate handles the alias.
    """
    templates = _load_sp_templates()
    if role in templates:
        template = templates[role]
    else:
        fallback = (
            "physical_sweeper"
            if pokemon.base_stats.atk >= pokemon.base_stats.spa
            else "special_sweeper"
        )
        template = templates.get(fallback, {"atk": 32, "spe": 32, "hp": 2})
    return SPDistribution.model_validate(template)


def _resistant_or_immune(pokemon: PokemonData, attacker_type: str) -> bool:
    return pokemon.weaknesses.get(attacker_type, 1.0) < 1.0


def _heuristic_filter(
    anchor: PokemonData,
    pool: list[PokemonData],
    role_map: dict[str, list[str]],
    limit: int = _HEURISTIC_POOL_LIMIT,
) -> list[PokemonData]:
    """Trim a candidate pool to those that complement the anchor.

    Keep candidates that either:
      - resist or are immune to a type the anchor is weak to, or
      - bring a role that complements the anchor's primary role
        (e.g., a sweeper anchor pairs well with a lead/wall).
    Always exclude the anchor itself and exact type-list duplicates.
    """
    anchor_weak = {
        t for t, mult in anchor.weaknesses.items() if mult >= 2.0
    }
    anchor_roles = set(role_map.get(anchor.name, assign_role(anchor)))
    anchor_is_sweeper = bool(
        anchor_roles & {"physical_sweeper", "special_sweeper"}
    )

    scored: list[tuple[float, PokemonData]] = []
    for cand in pool:
        if cand.name == anchor.name:
            continue
        if sorted(cand.types) == sorted(anchor.types):
            # Exact same defensive shape adds no coverage.
            continue
        cand_roles = set(role_map.get(cand.name, assign_role(cand)))

        score = 0.0
        for weak in anchor_weak:
            if _resistant_or_immune(cand, weak):
                score += 1.0
        if anchor_is_sweeper and (
            cand_roles & {"lead_support", "redirect", "physical_wall", "special_wall"}
        ):
            score += 0.5
        if not anchor_is_sweeper and (
            cand_roles & {"physical_sweeper", "special_sweeper"}
        ):
            score += 0.5
        # Small base weight so candidates with no specific synergy still
        # have a chance to be considered, ensuring we always have enough
        # to assemble a 6-mon team.
        score += 0.01
        scored.append((score, cand))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [cand for _, cand in scored[:limit]]


def _partial_score(
    partial_team: list[PokemonData], role_map: dict[str, list[str]]
) -> float:
    """Heuristic score for a beam state. Higher is better."""
    if not partial_team:
        return 0.0

    report = analyze_coverage(partial_team)
    score = 0.0
    score += (len(ALL_TYPES) - len(report.offensive_gaps)) * 1.0
    score -= len(report.defensive_weaknesses) * 2.0

    role_counter: set[str] = set()
    for member in partial_team:
        role_counter.update(role_map.get(member.name, assign_role(member)))
    score += len(role_counter) * 1.5

    type_counts: dict[str, int] = {}
    for member in partial_team:
        for t in member.types:
            type_counts[t] = type_counts.get(t, 0) + 1
    for count in type_counts.values():
        if count >= 3:
            score -= (count - 2) * 1.5

    return score


def _beam_search(
    anchor: PokemonData,
    candidates: list[PokemonData],
    role_map: dict[str, list[str]],
    target_size: int = 6,
    beam_width: int = _BEAM_WIDTH,
) -> list[list[PokemonData]]:
    """Build candidate teams of ``target_size`` via beam search.

    Beam state = a list of PokemonData (already-chosen members starting
    with the anchor). At each expansion we add one new candidate from
    ``candidates`` (no duplicates) and score the resulting partial team,
    keeping the top ``beam_width`` states.

    Returns up to ``beam_width`` complete teams, sorted by their final
    partial score descending.
    """
    if target_size <= 1:
        return [[anchor]]

    states: list[list[PokemonData]] = [[anchor]]
    for _ in range(target_size - 1):
        next_states: list[tuple[float, list[PokemonData]]] = []
        for state in states:
            chosen_names = {p.name for p in state}
            for cand in candidates:
                if cand.name in chosen_names:
                    continue
                new_state = state + [cand]
                next_states.append(
                    (_partial_score(new_state, role_map), new_state)
                )
        if not next_states:
            break
        next_states.sort(key=lambda pair: pair[0], reverse=True)
        seen_keys: set[frozenset[str]] = set()
        kept: list[list[PokemonData]] = []
        for _, state in next_states:
            key = frozenset(p.name for p in state)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            kept.append(state)
            if len(kept) >= beam_width:
                break
        states = kept

    states.sort(key=lambda s: _partial_score(s, role_map), reverse=True)
    return states


def _assign_items(members_roles: list[list[str]]) -> list[str]:
    """Allocate items by role honoring the no-duplicates Item Clause.

    Raises:
        TeamBuildError: if the curated pool of real items is exhausted
            before every member receives a distinct item. We never emit
            a synthetic placeholder — downstream PokePaste imports would
            silently drop a mon whose item the importer doesn't know.
    """
    used: set[str] = set()
    out: list[str] = []
    for roles in members_roles:
        primary = roles[0] if roles else "physical_sweeper"
        candidate = _DEFAULT_ITEM_BY_ROLE.get(primary, _FALLBACK_ITEM)
        if candidate in used:
            # Fallback chain: Life Orb → backup pool. Keep walking until
            # we find an unused real item.
            chosen: str | None = None
            for alt in (_FALLBACK_ITEM, *_BACKUP_ITEMS):
                if alt not in used:
                    chosen = alt
                    break
            if chosen is None:
                raise TeamBuildError(
                    "Item Clause: el pool de items reales se agoto antes "
                    "de asignar un item distinto a cada miembro del equipo. "
                    "Amplia _BACKUP_ITEMS en team_generator."
                )
            candidate = chosen
        used.add(candidate)
        out.append(candidate)
    return out


def _team_signature(members: Iterable[PokemonData]) -> frozenset[str]:
    return frozenset(m.name for m in members)


def generate_team(
    anchor: PokemonData,
    pool: list[PokemonData] | None = None,
    num_variants: int = 3,
    *,
    candidate_loader: Callable[[PokemonData], list[PokemonData]] | None = None,
) -> list[TeamVariant]:
    """Generate up to ``num_variants`` 6-mon team variants around ``anchor``.

    The pool is resolved in this order:
      1. Explicit ``pool`` argument (used by tests with fake fixtures).
      2. ``candidate_loader(anchor)`` callback (used by the CLI for lazy
         PokeAPI fetching).
      3. Auto-load: pull every legal name from the regulation pool via
         ``pokemon_lookup.lookup``. This is the slow path and only kicks
         in when the caller hasn't pre-populated a pool.

    Variants are deduplicated by member set: any two returned variants
    differ in at least one Pokemon.
    """
    if num_variants < 1:
        return []

    if pool is None:
        if candidate_loader is not None:
            pool = candidate_loader(anchor)
        else:
            pool = _default_pool_loader(anchor)

    if not pool:
        return []

    # Precompute roles once per Pokemon — assign_role is pure and pool is
    # fixed for this call. Avoids O(pool × beam_width × steps) recomputation.
    all_pokemon = [anchor] + pool
    role_map: dict[str, list[str]] = {p.name: assign_role(p) for p in all_pokemon}

    candidates = _heuristic_filter(anchor, pool, role_map)
    if not candidates:
        return []

    if len(candidates) < 5:
        return []

    states = _beam_search(anchor, candidates, role_map, target_size=6)
    if not states:
        return []

    variants: list[TeamVariant] = []
    seen_signatures: set[frozenset[str]] = set()
    for state in states:
        if len(state) != 6:
            continue
        signature = _team_signature(state)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        try:
            variant = _build_variant(state, role_map)
        except ValueError:
            continue
        score = viability_rater.score_team(variant)
        explanation = viability_rater.generate_explanation(variant, score)
        variant = variant.model_copy(
            update={"score": score, "score_explanation": explanation}
        )
        variants.append(variant)
        if len(variants) >= num_variants:
            break

    return variants


def _pick_ability(pokemon: PokemonData) -> str:
    """Prefer the first ability that is not weather/condition-dependent."""
    for ability in pokemon.abilities:
        if ability.lower() not in _SITUATIONAL_ABILITIES:
            return ability
    return pokemon.abilities[0] if pokemon.abilities else "pressure"


def _build_variant(
    team: list[PokemonData], role_map: dict[str, list[str]]
) -> TeamVariant:
    members_roles = [role_map.get(p.name, assign_role(p)) for p in team]
    items = _assign_items(members_roles)

    members: list[TeamMember] = []
    for pokemon, roles, item in zip(team, members_roles, items):
        primary = roles[0] if roles else "physical_sweeper"
        sp = suggest_sp_distribution(pokemon, primary)
        nature = _NATURE_BY_ROLE.get(primary, _FALLBACK_NATURE)
        ability = _pick_ability(pokemon)
        moves = replica_exporter.select_moves_for_role(pokemon, roles, item=item)
        members.append(
            TeamMember(
                pokemon=pokemon,
                role=roles,
                sp_distribution=sp,
                item=item,
                ability=ability,
                nature=nature,
                moves=moves,
            )
        )
    if len(members) != 6:
        raise ValueError("Team must have exactly 6 members.")
    return TeamVariant(members=members)


def _default_pool_loader(anchor: PokemonData) -> list[PokemonData]:
    """Fallback pool loader: lookup() every legal name except the anchor.

    WARNING: this fan-outs to the entire regulation pool through PokeAPI.
    Only used when no ``pool`` and no ``candidate_loader`` are provided.
    The CLI prefers a name-prefiltered lazy loader for performance.
    """
    pool: list[PokemonData] = []
    for name in get_all_names():
        if name == anchor.name:
            continue
        try:
            pool.append(pokemon_lookup.lookup(name))
        except Exception:
            # Skip anything that can't be resolved; we don't want a single
            # missing entry to fail team generation.
            continue
    return pool


# Convenience re-export for the CLI to keep MAX_SP_TOTAL accessible without
# reaching into config from the CLI module.
__all__ = [
    "generate_team",
    "suggest_sp_distribution",
    "MAX_SP_TOTAL",
]
