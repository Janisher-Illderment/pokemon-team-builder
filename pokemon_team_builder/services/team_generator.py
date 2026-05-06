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
from pokemon_team_builder.services.synergy_engine import (
    ALL_TYPES,
    analyze_coverage,
    assign_role,
    assign_role_with_mega,
)


_DEFAULT_ITEM_BY_ROLE: dict[str, str] = {
    # NOT in Champions: Choice Band, Choice Specs, Assault Vest, Life Orb,
    # Weakness Policy, Throat Spray, Rocky Helmet, Clear Amulet, Safety Goggles,
    # Covert Cloak, Adrenaline Orb.
    "physical_sweeper": "Scope Lens",
    "special_sweeper": "Shell Bell",
    "physical_wall": "Leftovers",
    "special_wall": "Leftovers",
    "lead_support": "Focus Sash",
    "trick_room_setter": "Mental Herb",
    "redirect": "Mental Herb",
}
_FALLBACK_ITEM = "Choice Scarf"
# Champions-legal backup items (Serebii/MetaVGC confirmed). Order is
# preference: utility first, then type-boosting items so that even six
# same-role mons can each receive a distinct, importable item.
_BACKUP_ITEMS: tuple[str, ...] = (
    "Sitrus Berry",
    "Lum Berry",
    "Scope Lens",
    "Persim Berry",
    "White Herb",
    "Shell Bell",
    "Focus Sash",
    "Focus Band",
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


# Declarative table of item preconditions. Each predicate receives the
# Pokemon and either the actual generated moveset (preferred) or ``None``
# to fall back to the Pokemon's full learnset.
#
# WHY: refactored from an if/elif chain so adding a new item-aware rule
# is a one-line tuple entry. Predicates that only care about types are
# kept out of this table — see ``_item_is_activatable`` below.
_ITEM_PRECONDITIONS_MOVESET: dict[str, Callable[[PokemonData, list[str] | None], bool]] = {
    # White Herb resets stat drops from moves like Overheat / Close Combat.
    # Throat Spray and Weakness Policy are NOT in Champions — removed.
    "White Herb": lambda p, moves: any(
        m in _STAT_DROP_MOVES for m in (moves if moves is not None else p.move_names)
    ),
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
        candidate = _DEFAULT_ITEM_BY_ROLE.get(primary, _FALLBACK_ITEM)
        moves_for_i = preview_moves[i] if preview_moves is not None else None
        # If this item requires moves the Pokemon doesn't have, skip it immediately
        # and let the fallback chain find something useful.
        if members is not None and not _item_is_activatable(
            candidate, members[i], moves_for_i
        ):
            candidate = "__skip__"  # sentinel — not a real item name, forces fallback
        if candidate in used or candidate == "__skip__":
            # Fallback chain: Choice Scarf → backup pool. Keep walking until
            # we find an unused real item that can also activate.
            chosen: str | None = None
            for alt in (_FALLBACK_ITEM, *_BACKUP_ITEMS):
                if alt not in used:
                    # Choice items lock the holder into one move — useless
                    # for setters/redirectors/walls/leads.
                    if primary in _NO_CHOICE_ROLES and alt in _CHOICE_ITEMS:
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
                        if primary in _NO_CHOICE_ROLES and alt in _CHOICE_ITEMS:
                            continue
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
            variant = _build_variant(state, role_map, anchor_mega=anchor_mega)
        except (ValueError, TeamBuildError):
            # ValueError → wrong member count; TeamBuildError → move
            # selection ran out of moves or items pool exhausted. In
            # either case skip this state and try the next.
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
) -> TeamVariant:
    members_roles = [role_map.get(p.name, assign_role(p)) for p in team]

    # 1. Pre-compute a preview moveset per Pokemon so item activation
    #    predicates (Throat Spray needs sound, White Herb needs stat-drop,
    #    Weakness Policy must avoid setup) can read the actual moves
    #    instead of guessing from the full learnset.
    preview_moves = [
        replica_exporter.select_moves_for_role(pokemon, roles)
        for pokemon, roles in zip(team, members_roles)
    ]

    # 2. Assign items using the preview moves. When a Mega is resolved
    #    for the anchor (slot 0), pin its stone there before any role-
    #    based allocation runs — and reserve the stone in ``used`` so
    #    no other slot can collide.
    mega_slot = (0, anchor_mega.mega_stone) if anchor_mega is not None else None
    items = _assign_items(
        members_roles,
        team,
        preview_moves=preview_moves,
        mega_slot=mega_slot,
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
        moves = replica_exporter.select_moves_for_role(pokemon, roles, item=item)
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
    return TeamVariant(members=members)


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
