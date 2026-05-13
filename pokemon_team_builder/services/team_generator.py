from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Callable, Iterable

from pathlib import Path

_logger = logging.getLogger(__name__)

from pokemon_team_builder.config import (
    CHAMPIONS_LEGAL_ITEMS_FILE,
    DATA_DIR,
    MAX_SP_TOTAL,
    ROLE_SP_TEMPLATES_FILE,
)
from pokemon_team_builder.data.legal_pool_loader import get_all_names
from pokemon_team_builder.domain.exceptions import TeamBuildError
from pokemon_team_builder.domain.models import (
    MegaForm,
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
from pokemon_team_builder.services import favorite_first_builder
from pokemon_team_builder.services.meta_service import MetaService
from pokemon_team_builder.services.synergy_engine import (
    ALL_TYPES,
    analyze_coverage,
    assign_role,
    assign_role_with_mega,
)

_meta_service = MetaService()


# Default item by role. Champions Reg M-A legal items only — Weakness Policy,
# Throat Spray, Rocky Helmet, and Life Orb are NOT in the M-A pool (Inte v2
# cross-checked: Game8, Serebii, TheGamer, NintendoEverything, Smogon, VGC).
# Source: champions_legal_items.json (data_version 1).
# Provisional replacements per spec: physical_sweeper → Choice Band,
# special_sweeper → Choice Specs, physical_wall → Leftovers.
_DEFAULT_ITEM_BY_ROLE_FALLBACK: dict[str, str] = {
    "physical_sweeper": "Choice Band",
    "special_sweeper": "Choice Specs",
    "physical_wall": "Leftovers",
    "special_wall": "Leftovers",
    "lead_support": "Focus Sash",
    "trick_room_setter": "Mental Herb",
    "redirect": "Clear Amulet",
}
_FALLBACK_ITEM = "Choice Scarf"
# Champions-legal backup pool (utility first, type-boosters last) — kept as a
# fallback when champions_legal_items.json is missing or unparsable. The JSON
# is the authoritative source; this constant just prevents a cold-start crash.
_BACKUP_ITEMS_FALLBACK: tuple[str, ...] = (
    "Sitrus Berry",
    "Lum Berry",
    "Scope Lens",
    "Power Herb",
    "Persim Berry",
    "White Herb",
    "Shell Bell",
    "Oran Berry",
    "Focus Band",
    "King's Rock",
    "Bright Powder",
    "Quick Claw",
    "Assault Vest",
    "Eviolite",
    "Safety Goggles",
    "Light Clay",
    "Covert Cloak",
    "Booster Energy",
    "Mirror Herb",
    "Loaded Dice",
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


@lru_cache(maxsize=1)
def _load_champions_legal_items() -> tuple[frozenset[str], int]:
    """Return ``(legal_item_names, data_version)``.

    Reads ``champions_legal_items.json`` if present; on any failure falls
    back to the in-code constants below — same shape (frozenset + version 0)
    so callers don't need a None branch.
    """
    path: Path = CHAMPIONS_LEGAL_ITEMS_FILE  # type: ignore[name-defined]
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        items = raw.get("items", [])
        names = frozenset(entry["name"] for entry in items if "name" in entry)
        version = int(raw.get("data_version", 0))
        return names, version
    except Exception as exc:
        _logger.warning(
            "champions_legal_items.json load failed (%s: %s) at %s — using fallback pool with data_version=0",
            type(exc).__name__, exc, path,
        )
        fallback = (
            set(_DEFAULT_ITEM_BY_ROLE_FALLBACK.values())
            | set(_BACKUP_ITEMS_FALLBACK)
            | {_FALLBACK_ITEM}
        )
        return frozenset(fallback), 0


@lru_cache(maxsize=1)
def _build_default_item_by_role() -> dict[str, str]:
    """Return the active role → default-item map.

    Currently identical to ``_DEFAULT_ITEM_BY_ROLE_FALLBACK`` because the
    JSON only carries the legal-pool inventory, not the role mapping. This
    indirection keeps the call sites stable for when the role map graduates
    to JSON.
    """
    return dict(_DEFAULT_ITEM_BY_ROLE_FALLBACK)


@lru_cache(maxsize=1)
def _build_backup_items() -> tuple[str, ...]:
    """Return the backup item pool, sourced from JSON when available.

    Backup pool = champions_legal_items.json items, excluding the role-
    default items and the fallback (Choice Scarf). Order: utility first
    (alphabetical within category), type_boost last. The JSON is the
    authority; if it fails to load we use the in-code fallback so the
    generator still works offline.
    """
    legal, _ = _load_champions_legal_items()
    if not legal:
        return _BACKUP_ITEMS_FALLBACK
    defaults = set(_build_default_item_by_role().values()) | {_FALLBACK_ITEM}
    # Preserve the ordering of _BACKUP_ITEMS_FALLBACK for any item that
    # appears in both; append JSON-only items at the end. This keeps the
    # competitive ordering we already had (utility before type-boost).
    ordered: list[str] = []
    seen: set[str] = set()
    for item in _BACKUP_ITEMS_FALLBACK:
        if item in legal and item not in defaults and item not in seen:
            ordered.append(item)
            seen.add(item)
    for item in legal:
        if item not in defaults and item not in seen:
            ordered.append(item)
            seen.add(item)
    return tuple(ordered)


# Public accessors — call-sites read these names so the loading is lazy
# and the JSON cache is shared.
_DEFAULT_ITEM_BY_ROLE: dict[str, str] = _build_default_item_by_role()
_BACKUP_ITEMS: tuple[str, ...] = _build_backup_items()

_SITUATIONAL_ABILITIES: frozenset[str] = frozenset({
    "sand-veil", "snow-cloak", "swift-swim", "chlorophyll",
    "solar-power", "sand-rush", "slush-rush", "surge-surfer",
    "leaf-guard", "flower-gift", "forecast",
})

_SOUND_MOVES: frozenset[str] = frozenset({
    "hyper-voice", "bug-buzz", "boomburst", "round", "disarming-voice",
    "chatter", "echoed-voice", "relic-song", "sparkling-aria",
    "torch-song", "clangorous-soul",
})

_STAT_DROP_MOVES: frozenset[str] = frozenset({
    "overheat", "draco-meteor", "leaf-storm", "fleur-cannon",
    "close-combat", "superpower", "v-create",
})

# Mirrors replica_exporter._CHOICE_ITEMS — kept as a local copy so
# team_generator does not depend on a private constant in another module.
# These two sets must always agree.
_CHOICE_ITEMS: frozenset[str] = frozenset(
    {"Choice Scarf", "Choice Band", "Choice Specs"}
)

# Mirrors replica_exporter._SETUP_MOVES — used by the Choice-item + setup-move
# guard so a Choice-locked attacker doesn't get a useless setup move in slot 4.
_SETUP_MOVES: frozenset[str] = frozenset({
    "nasty-plot", "calm-mind", "tail-glow",
    "swords-dance", "dragon-dance", "bulk-up",
    "quiver-dance", "shell-smash", "coil", "hone-claws", "work-up",
})

# Roles where ANY Choice item is forbidden — locking these into a single
# move makes the Pokemon useless for the rest of the match (TR setter
# stuck on Trick Room, redirect stuck on Follow Me, walls stuck on
# recovery moves with no offensive option, lead_support stuck on
# Tailwind/Fake Out instead of cycling utility).
_NO_CHOICE_ROLES: frozenset[str] = frozenset({
    "trick_room_setter",
    "redirect",
    "physical_wall",
    "special_wall",
    "lead_support",
})

# Pokemon that cannot be built into a legal team member by the move
# selection system (e.g., Ditto's only legal move in Champions is
# Transform — no STAB/coverage moveset is producible).
_UNGENERABLE_POKEMON: frozenset[str] = frozenset({"ditto"})

# Type-boosting items only buff moves of their specific type. Heuristic:
# only assign one if the Pokemon is itself that type (so it has STAB
# moves of that type to actually benefit).
_TYPE_BOOST_ITEMS: dict[str, str] = {
    "Mystic Water": "water",
    "Charcoal": "fire",
    "Magnet": "electric",
    "Black Belt": "fighting",
    "Soft Sand": "ground",
    "Sharp Beak": "flying",
    "Silver Powder": "bug",
    "Dragon Fang": "dragon",
    "Spell Tag": "ghost",
    "Miracle Seed": "grass",
    "Never-Melt Ice": "ice",
    "Poison Barb": "poison",
    "Metal Coat": "steel",
    "Black Glasses": "dark",
    "Twisted Spoon": "psychic",
    "Hard Stone": "rock",
    "Silk Scarf": "normal",
    "Fairy Feather": "fairy",
}


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
        if role.startswith("_"):
            # Reserved metadata keys (e.g. ``_meta`` carrying regulation /
            # data_version). Skip — not a real role.
            continue
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
    Candidates that are meta-frequent teammates of the anchor receive
    a +3.0 affinity bonus from MunchStats data.
    """
    anchor_weak = {
        t for t, mult in anchor.weaknesses.items() if mult >= 2.0
    }
    anchor_roles = set(role_map.get(anchor.name, assign_role(anchor)))
    anchor_is_sweeper = bool(
        anchor_roles & {"physical_sweeper", "special_sweeper"}
    )

    # Fetch meta teammates once for the anchor; degrade gracefully to empty.
    anchor_meta = _meta_service.get(anchor.name)
    meta_teammates: set[str] = (
        set(anchor_meta.teammates) if anchor_meta is not None else set()
    )

    scored: list[tuple[float, PokemonData]] = []
    for cand in pool:
        if cand.name == anchor.name:
            continue
        if cand.name in _UNGENERABLE_POKEMON:
            # No buildable moveset in Champions — never include.
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
        if cand.name in meta_teammates:
            score += 3.0
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

    _pure_sweeper_roles = {"physical_sweeper", "special_sweeper"}
    _support_roles = {"lead_support", "redirect", "physical_wall", "special_wall", "trick_room_setter"}
    pure_sweeper_count = sum(
        1 for member in partial_team
        if set(role_map.get(member.name, assign_role(member))).issubset(_pure_sweeper_roles)
        and not set(role_map.get(member.name, assign_role(member))) & _support_roles
    )
    if pure_sweeper_count > 2:
        score -= (pure_sweeper_count - 2) * 4.0

    return score


def _count_mega_potentials(
    state: list[PokemonData], anchor_is_mega: bool
) -> int:
    """Count how many slots in ``state`` could end up holding a Mega Stone.

    Used by the Phase 2a mega-clause prune in :func:`_beam_search`.

    - Slot 0 (anchor) counts iff the caller has already locked a mega
      assignment for it (``anchor_is_mega`` True).
    - Any other slot counts iff its species has at least one
      :class:`MegaForm` entry — i.e. it COULD be Mega-evolved if we
      later assigned a stone. Since today only the anchor gets one
      stone, two mega-capable members in slots ≥ 1 are a *latent*
      duplication risk, not an actual one. We still prune them
      conservatively because the favorite-first/best-partner phase
      (Phase 2b) will introduce mega assignment for slot 2, at which
      point the prune protects against the real duplicate case.
    """
    count = 0
    for idx, member in enumerate(state):
        if idx == 0:
            if anchor_is_mega:
                count += 1
        else:
            if member.megas:
                count += 1
    return count


def _beam_search(
    anchor: PokemonData,
    candidates: list[PokemonData],
    role_map: dict[str, list[str]],
    target_size: int = 6,
    beam_width: int = _BEAM_WIDTH,
    *,
    anchor_is_mega: bool = False,
    seed: list[PokemonData] | None = None,
) -> list[list[PokemonData]]:
    """Build candidate teams of ``target_size`` via beam search.

    Beam state = a list of PokemonData (already-chosen members starting
    with the anchor — or the full ``seed`` when one is provided). At each
    expansion we add one new candidate from ``candidates`` (no duplicates)
    and score the resulting partial team, keeping the top ``beam_width``
    states.

    Phase 2b ``seed``: when supplied, the initial beam state is exactly
    ``seed`` (which MUST start with ``anchor``). This is how the
    favorite-first flow pre-locks slots 1–3 — beam search then expands
    only the remaining ``target_size - len(seed)`` slots. When ``seed``
    is None we fall back to the legacy ``[[anchor]]`` initial state, so
    older callers (tests + non-favorite-first paths) keep working.

    Mega Clause (Phase 2a, spec §4.5): any partial state where the count
    of mega-capable members exceeds 1 is pruned BEFORE scoring. This is a
    structural hard constraint, not a soft penalty — Champions allows
    exactly one mega per team. Pre-score pruning also reduces branching.

    Returns up to ``beam_width`` complete teams, sorted by their final
    partial score descending.
    """
    if target_size <= 1:
        return [[anchor]]

    if seed is not None:
        if not seed or seed[0].name != anchor.name:
            # Programmer error: the favorite-first flow always seeds with
            # the anchor as slot 0. Fail loud rather than silently
            # mis-anchor the variant.
            raise ValueError(
                "_beam_search: seed must start with the anchor "
                f"(got first={seed[0].name if seed else None!r}, "
                f"anchor={anchor.name!r})."
            )
        if len(seed) >= target_size:
            return [list(seed)]
        initial_state: list[PokemonData] = list(seed)
    else:
        initial_state = [anchor]

    expansion_steps = target_size - len(initial_state)
    states: list[list[PokemonData]] = [initial_state]
    for _ in range(expansion_steps):
        next_states: list[tuple[float, list[PokemonData]]] = []
        for state in states:
            chosen_names = {p.name for p in state}
            for cand in candidates:
                if cand.name in chosen_names:
                    continue
                new_state = state + [cand]
                # Phase 2a mega-clause hard prune (pre-score).
                if _count_mega_potentials(new_state, anchor_is_mega) > 1:
                    continue
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


# Declarative table of item preconditions. Each predicate receives the
# Pokemon and either the actual generated moveset (preferred) or ``None``
# to fall back to the Pokemon's full learnset.
#
# WHY: refactored from an if/elif chain so adding a new item-aware rule
# is a one-line tuple entry. Predicates that only care about types are
# kept out of this table — see ``_item_is_activatable`` below.
_ITEM_PRECONDITIONS_MOVESET: dict[str, Callable[[PokemonData, list[str] | None], bool]] = {
    # White Herb resets stat drops from moves like Overheat / Close Combat.
    "White Herb": lambda p, moves: any(
        m in _STAT_DROP_MOVES for m in (moves if moves is not None else p.move_names)
    ),
    # NOTE: Throat Spray and Weakness Policy preconditions removed in v0.3
    # (refine-build-logic-v2) — those items are NOT in the Champions Reg M-A
    # legal pool. If meta-service returns them for a member they will be
    # filtered upstream by the legal-items check, never reaching this map.
}


def _item_is_activatable(
    item: str,
    pokemon: PokemonData,
    moves: list[str] | None = None,
) -> bool:
    """Return False when an item requires specific moves the Pokemon doesn't have.

    When ``moves`` is provided, moveset-aware predicates check against the
    actual generated moves. When it is ``None``, they fall back to the
    full learnset (legacy behavior, used pre-moveset selection).
    """
    if item in _ITEM_PRECONDITIONS_MOVESET:
        return _ITEM_PRECONDITIONS_MOVESET[item](pokemon, moves)
    if item in _TYPE_BOOST_ITEMS:
        boost_type = _TYPE_BOOST_ITEMS[item]
        return boost_type.lower() in {t.lower() for t in pokemon.types}
    return True


def _assign_items(
    members_roles: list[list[str]],
    members: list[PokemonData] | None = None,
    preview_moves: list[list[str]] | None = None,
    mega_slot: tuple[int, str] | None = None,
    meta_items_by_member: list[list[str]] | None = None,
) -> list[str]:
    """Allocate items by role honoring the no-duplicates Item Clause.

    When ``preview_moves`` is provided (a parallel list of generated
    movesets, one per member), moveset-aware activation predicates use
    the actual moves. Otherwise they fall back to the full learnset.

    When ``mega_slot=(idx, stone_name)`` is provided, the item at index
    ``idx`` is pre-fixed to ``stone_name``. The stone is added to the
    ``used`` set so no other slot can collide with it (Item Clause
    extends to Mega Stones), and the mega-eligible slot is skipped in
    the role-based allocation loop.

    Raises:
        TeamBuildError: if the curated pool of real items is exhausted
            before every member receives a distinct item. We never emit
            a synthetic placeholder — downstream PokePaste imports would
            silently drop a mon whose item the importer doesn't know.
    """
    used: set[str] = set()
    # Pre-fill: the mega slot reserves its stone before any role-based
    # allocation walks the candidate / fallback chain. Using a dict keyed
    # by index lets us slot the result back at the exact position once
    # the loop has filled the rest.
    pre_assigned: dict[int, str] = {}
    if mega_slot is not None:
        slot_idx, stone_name = mega_slot
        if not 0 <= slot_idx < len(members_roles):
            raise TeamBuildError(
                f"mega_slot index {slot_idx} out of range "
                f"(team size {len(members_roles)})."
            )
        pre_assigned[slot_idx] = stone_name
        used.add(stone_name)

    out: list[str] = []
    for i, roles in enumerate(members_roles):
        if i in pre_assigned:
            out.append(pre_assigned[i])
            continue
        primary = roles[0] if roles else "physical_sweeper"
        moves_for_i = preview_moves[i] if preview_moves is not None else None

        # Try meta items first (ranked by usage), subject to all existing guards.
        # Filter against the Champions M-A legal pool so meta items like
        # Life Orb / Weakness Policy (legal elsewhere, banned in M-A) never
        # leak into a generated team.
        legal_items, _ = _load_champions_legal_items()
        candidate: str | None = None
        meta_items = meta_items_by_member[i] if meta_items_by_member is not None else []
        for meta_item in meta_items:
            if meta_item in used:
                continue
            if legal_items and meta_item not in legal_items:
                continue  # not Champions M-A legal
            if set(roles) & _NO_CHOICE_ROLES and meta_item in _CHOICE_ITEMS:
                continue
            if members is not None and not _item_is_activatable(
                meta_item, members[i], moves_for_i
            ):
                continue
            candidate = meta_item
            break

        # Fall back to role-based default if no meta item worked.
        if candidate is None:
            candidate = _DEFAULT_ITEM_BY_ROLE.get(primary, _FALLBACK_ITEM)
            if members is not None and not _item_is_activatable(
                candidate, members[i], moves_for_i
            ):
                candidate = "__skip__"

        if candidate in used or candidate == "__skip__":
            # Fallback chain: Choice Scarf → backup pool. Keep walking until
            # we find an unused real item that can also activate.
            chosen: str | None = None
            for alt in (_FALLBACK_ITEM, *_BACKUP_ITEMS):
                if alt not in used:
                    # Choice items lock the holder into one move — useless
                    # for setters/redirectors/walls/leads. Check ALL roles,
                    # not just primary, since e.g. a secondary trick_room_setter
                    # is equally unable to cycle utility when Choice-locked.
                    if set(roles) & _NO_CHOICE_ROLES and alt in _CHOICE_ITEMS:
                        continue
                    if members is None or _item_is_activatable(
                        alt, members[i], moves_for_i
                    ):
                        chosen = alt
                        break
            if chosen is None:
                # Last resort: take any unused item, activation or not — better than nothing
                for alt in (_FALLBACK_ITEM, *_BACKUP_ITEMS):
                    if alt not in used:
                        if set(roles) & _NO_CHOICE_ROLES and alt in _CHOICE_ITEMS:
                            continue
                        chosen = alt
                        break
            if chosen is None:
                raise TeamBuildError(
                    "Item Clause: pool insuficiente para 6 items unicos. "
                    "El pool de Champions M-A legales (champions_legal_items.json) "
                    "se agoto antes de asignar items distintos a todos los miembros. "
                    "Amplia el pool o reduce el numero de Pokemon del mismo rol."
                )
            candidate = chosen
        used.add(candidate)
        out.append(candidate)
    return out


def _team_signature(members: Iterable[PokemonData]) -> frozenset[str]:
    return frozenset(m.name for m in members)


def _resolve_mega(pokemon: PokemonData, choice: str) -> MegaForm | None:
    """Pick the right MegaForm (if any) for ``pokemon`` given a CLI choice.

    - ``choice == "off"`` or species has no megas → returns ``None``.
    - Single-form species + ``choice == "auto"`` → returns the only form.
    - Multi-form species (Charizard X/Y) + ``choice in {"x","y"}`` →
      returns the matching form (form_id ends with ``-x`` / ``-y``).
    - Multi-form species + ``choice == "auto"`` → raises
      ``TeamBuildError`` asking the user to pick X or Y explicitly. We
      do not silently default — surface the ambiguity.
    - Multi-form species + ``choice in {"x","y"}`` with no matching form
      → raises ``TeamBuildError``.
    """
    if choice == "off" or not pokemon.megas:
        return None

    forms = pokemon.megas
    if len(forms) == 1 and choice == "auto":
        return forms[0]

    if choice in ("x", "y"):
        suffix = "-" + choice
        for form in forms:
            if form.form_id.endswith(suffix):
                return form
        raise TeamBuildError(
            f"{pokemon.name} no tiene una forma Mega '{choice}'. "
            f"Formas disponibles: "
            f"{', '.join(f.form_id for f in forms)}."
        )

    # Multi-form species + auto (or unknown choice) → ambiguous.
    raise TeamBuildError(
        f"{pokemon.name} tiene varias formas Mega. Usa --mega x o --mega y "
        f"para seleccionar (formas: "
        f"{', '.join(f.form_id for f in forms)})."
    )


def generate_team(
    anchor: PokemonData,
    pool: list[PokemonData] | None = None,
    num_variants: int = 3,
    *,
    candidate_loader: Callable[[PokemonData], list[PokemonData]] | None = None,
    mega_choice: str = "auto",
    format_mode: str = "bo1",
    archetype: str = "balance",
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

    Phase 2b — favorite-first build flow:
      The generator now runs in four phases instead of pure beam search:
        1. Resolve the anchor and its mega.
        2. ``build_core_duo(anchor, archetype, pool, ...)`` picks slot 2.
        3. ``cover_shared_weakness([anchor, partner], ...)`` picks slot 3.
        4. ``_beam_search(seed=[anchor, partner, slot3], ...)`` fills
           slots 4–6 only.

      Backward compatibility: ``archetype`` defaults to ``"balance"``, so
      callers that pre-date Phase 2b (tests, CLI scripts) automatically
      run the new flow with balanced weights. We deliberately do NOT gate
      the new flow behind the default — switching paths by archetype
      would create two divergent code paths to maintain. Instead, the
      ``balance`` weights matrix (all 1.0) reproduces the v0.2.0 scoring
      ranking closely enough that the legacy tests pass. The two surface-
      level changes vs v0.2.0 are:
        - Slot 2 is now picked by ``build_core_duo`` (which honors meta
          teammates and type complement, the same signals that
          ``_heuristic_filter`` used to rank candidates).
        - Slot 3 is now picked by ``cover_shared_weakness`` (which scores
          against the duo's shared weakness, a strict subset of what beam
          search used to do).
      Legacy tests assert at the variant-level (anchor in slot 0, 6
      distinct members, valid items / SPs) — none of those invariants are
      affected by the flow change.
    """
    if num_variants < 1:
        return []

    if anchor.name in _UNGENERABLE_POKEMON:
        raise TeamBuildError(
            "Ditto cannot be used as a team anchor — it has no buildable "
            "moveset in Champions."
        )

    # Resolve the anchor's Mega Evolution choice up-front. This raises
    # TeamBuildError on ambiguity (Charizard auto) before we burn time
    # building a pool — fail fast with a clear message.
    anchor_mega = _resolve_mega(anchor, mega_choice)

    if pool is None:
        if candidate_loader is not None:
            pool = candidate_loader(anchor)
        else:
            pool = _default_pool_loader(anchor)

    if not pool:
        return []

    # Precompute roles once per Pokemon — assign_role is pure and pool is
    # fixed for this call. Avoids O(pool × beam_width × steps) recomputation.
    # The anchor's role is computed against its Mega-form stats when one
    # was resolved; pool members are always evaluated as their base form.
    all_pokemon = [anchor] + pool
    role_map: dict[str, list[str]] = {p.name: assign_role(p) for p in all_pokemon}
    if anchor_mega is not None:
        role_map[anchor.name] = assign_role_with_mega(anchor, anchor_mega)

    candidates = _heuristic_filter(anchor, pool, role_map)
    if not candidates:
        return []

    if len(candidates) < 5:
        return []

    # ── Phase 2b: favorite-first build flow ─────────────────────────
    # The favorite-first phases pick slots 2 and 3 deterministically; the
    # heuristic-filtered ``candidates`` pool feeds both phases so the
    # pruning logic stays consistent with the legacy beam-search input.
    try:
        partner, _partner_score = favorite_first_builder.build_core_duo(
            anchor, archetype, candidates, _meta_service, role_map,
        )
        slot3 = favorite_first_builder.cover_shared_weakness(
            [anchor, partner], archetype, candidates, role_map,
        )
    except ValueError:
        # Insufficient pool to form the duo / trio. Fall through to the
        # empty result rather than blowing up the API response.
        return []

    seed = [anchor, partner, slot3]

    states = _beam_search(
        anchor,
        candidates,
        role_map,
        target_size=6,
        anchor_is_mega=anchor_mega is not None,
        seed=seed,
    )
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
            variant = _build_variant(
                state, role_map,
                anchor_mega=anchor_mega,
                format_mode=format_mode,
                archetype=archetype,
            )
        except (ValueError, TeamBuildError):
            # ValueError → wrong member count; TeamBuildError → move
            # selection ran out of moves or items pool exhausted. In
            # either case skip this state and try the next.
            continue
        score, flex_ratio = viability_rater.score_team(
            variant, format_mode, archetype=archetype,
        )
        explanation = viability_rater.generate_explanation(variant, score)
        variant = variant.model_copy(
            update={
                "score": score,
                "score_explanation": explanation,
                "lead_flexibility_ratio": flex_ratio,
                "archetype": archetype,
            }
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
    if not pokemon.abilities:
        raise TeamBuildError(f"No abilities found for {pokemon.name}")
    return pokemon.abilities[0]


def _derive_nature(primary: str, roles: list[str], moves: list[str]) -> str:
    """Pick a nature from the slot-2 STAB category when possible.

    Sweepers and leads default to a speed-positive nature whose category
    matches their slot-2 STAB. Walls / TR setters / redirects keep their
    fixed role-based nature regardless of the moveset, since their job
    is not to attack.

    WHY: a Pelipper lead with Hurricane (special) was getting Jolly under
    the role-only mapping, wasting its 95 SpA. Reading the actual STAB
    category is more accurate than role alone.
    """
    if primary == "trick_room_setter":
        return "Sassy"
    if primary == "redirect":
        return "Calm"
    slot2_cat = (
        replica_exporter._MOVE_CATEGORY.get(moves[1], "")
        if len(moves) > 1
        else ""
    )
    if primary in ("physical_sweeper", "lead_support"):
        if slot2_cat == "special":
            return "Timid"
        return "Jolly"  # default for physical or unknown
    if primary == "special_sweeper":
        if slot2_cat == "physical":
            return "Jolly"
        return "Timid"  # default for special or unknown
    if primary == "physical_wall":
        return "Impish"
    if primary == "special_wall":
        return "Calm"
    return _FALLBACK_NATURE


def _build_variant(
    team: list[PokemonData],
    role_map: dict[str, list[str]],
    *,
    anchor_mega: MegaForm | None = None,
    format_mode: str = "bo1",
    archetype: str = "balance",
) -> TeamVariant:
    members_roles = [role_map.get(p.name, assign_role(p)) for p in team]

    # Fetch meta data for each team member once (None on failure — all logic
    # is advisory and falls back gracefully when meta is unavailable).
    meta_entries = [_meta_service.get(p.name) for p in team]
    meta_items_by_member = [
        (e.items if e is not None else []) for e in meta_entries
    ]
    meta_moves_by_member = [
        (e.moves if e is not None else []) for e in meta_entries
    ]

    # 1. Pre-compute a preview moveset per Pokemon so item activation
    #    predicates (White Herb needs stat-drop, and any future moveset-aware
    #    items) can read the actual moves instead of guessing from the
    #    full learnset.
    preview_moves = [
        replica_exporter.select_moves_for_role(
            pokemon, roles,
            meta_moves=meta_moves_by_member[i],
            format_mode=format_mode,
            archetype=archetype,
        )
        for i, (pokemon, roles) in enumerate(zip(team, members_roles))
    ]

    # 2. Assign items using the preview moves and meta items.
    mega_slot = (0, anchor_mega.mega_stone) if anchor_mega is not None else None
    items = _assign_items(
        members_roles,
        team,
        preview_moves=preview_moves,
        mega_slot=mega_slot,
        meta_items_by_member=meta_items_by_member,
    )

    # 3. Re-select moves with the actual item context — slot 4's
    #    Choice+setup guard depends on the assigned item, so a Choice
    #    Scarf user must drop Swords Dance / Nasty Plot from slot 4.
    members: list[TeamMember] = []
    for idx, (pokemon, roles, item) in enumerate(zip(team, members_roles, items)):
        primary = roles[0] if roles else "physical_sweeper"
        sp = suggest_sp_distribution(pokemon, primary)
        # The anchor mega contributes its own ability and stat block. The
        # SP template is already keyed off the mega-driven role above, so
        # the spread targets the mega's offensive profile.
        if idx == 0 and anchor_mega is not None:
            ability = anchor_mega.ability
        else:
            ability = _pick_ability(pokemon)
        moves = replica_exporter.select_moves_for_role(
            pokemon, roles,
            item=item,
            meta_moves=meta_moves_by_member[idx],
            format_mode=format_mode,
            archetype=archetype,
        )
        nature = _derive_nature(primary, roles, moves)
        members.append(
            TeamMember(
                pokemon=pokemon,
                role=roles,
                sp_distribution=sp,
                item=item,
                ability=ability,
                nature=nature,
                moves=moves,
                mega_form=anchor_mega if idx == 0 else None,
            )
        )
    if len(members) != 6:
        raise ValueError("Team must have exactly 6 members.")
    return TeamVariant(members=members, archetype=archetype)


def _default_pool_loader(anchor: PokemonData) -> list[PokemonData]:
    """Fallback pool loader: lookup() every legal name except the anchor.

    WARNING: this fan-outs to the entire regulation pool through PokeAPI.
    Only used when no ``pool`` and no ``candidate_loader`` are provided.
    The CLI prefers a name-prefiltered lazy loader for performance.
    """
    pool: list[PokemonData] = []
    for name in get_all_names():
        if name == anchor.name or name in _UNGENERABLE_POKEMON:
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
