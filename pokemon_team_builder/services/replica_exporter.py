from __future__ import annotations

from pathlib import Path

from pokemon_team_builder.data.archetype_weights_loader import get_weights
from pokemon_team_builder.domain.exceptions import TeamBuildError
from pokemon_team_builder.domain.models import (
    PokemonData,
    SPDistribution,
    TeamMember,
    TeamVariant,
)


# Champions replica format uses raw SP values (0–32) in the EVs: line, NOT
# the traditional Showdown ×8 conversion. Max per stat is 32.


# Curated STAB candidates per type. We pick the first one that the Pokemon
# actually knows. The list is order-of-preference (high-base power moves
# usable in Doubles regulation come first).
_STAB_BY_TYPE: dict[str, tuple[str, ...]] = {
    "normal": ("body-slam", "double-edge", "return", "hyper-voice", "tackle"),
    "fire": (
        "flamethrower",
        "fire-blast",
        "heat-wave",
        "fire-punch",
        "overheat",
        "ember",
    ),
    "water": ("hydro-pump", "scald", "muddy-water", "waterfall", "water-pulse", "surf"),
    "electric": (
        "thunderbolt",
        "thunder",
        "thunder-punch",
        "wild-charge",
        "discharge",   # last — hits ally in Doubles
    ),
    "grass": (
        "energy-ball",
        "leaf-storm",
        "giga-drain",
        "grass-knot",
        "leaf-blade",
        "seed-bomb",
    ),
    "ice": ("ice-beam", "blizzard", "icicle-crash", "ice-punch", "ice-fang", "freeze-dry"),
    "fighting": (
        "close-combat",
        "drain-punch",
        "focus-blast",
        "aura-sphere",
        "brick-break",
        "dynamic-punch",
    ),
    "poison": ("sludge-bomb", "gunk-shot", "poison-jab", "sludge-wave"),
    "ground": ("earthquake", "earth-power", "high-horsepower", "bulldoze"),
    "flying": (
        "brave-bird",
        "air-slash",
        "hurricane",
        "drill-peck",
        "aerial-ace",
    ),
    "psychic": (
        "psychic",
        "psyshock",
        "psystrike",
        "expanding-force",
    ),
    "bug": ("u-turn", "bug-buzz", "x-scissor", "megahorn", "leech-life"),
    "rock": ("rock-slide", "stone-edge", "power-gem", "ancient-power"),
    "ghost": ("shadow-ball", "shadow-claw", "poltergeist"),
    "dragon": ("draco-meteor", "dragon-pulse", "dragon-claw"),
    "dark": ("dark-pulse", "knock-off", "crunch", "foul-play"),
    "steel": ("iron-head", "flash-cannon", "meteor-mash", "iron-tail"),
    "fairy": ("moonblast", "dazzling-gleam", "play-rough", "fleur-cannon"),
}

# Generic coverage moves (non-STAB), in priority order.
_COVERAGE_PRIORITY: tuple[str, ...] = (
    "ice-beam",
    "thunderbolt",
    "psychic",
    "dazzling-gleam",
    "shadow-ball",
    "focus-blast",
    "rock-slide",
    "flamethrower",
    "energy-ball",
    "earth-power",  # before earthquake — special, no ally hit
    "earthquake",   # last — hits ally in Doubles unless partner has Ground immunity
)

# Physical/special category for moves that appear in coverage or STAB slots.
# WHY: slot-2 prefers STAB moves that match the Pokemon's primary attack stat,
# and slot-3 skips coverage moves of the wrong attack category (e.g. no
# Earthquake on a special attacker like Charizard).
_MOVE_CATEGORY: dict[str, str] = {
    # Coverage priority moves
    "earthquake": "physical",
    "ice-beam": "special",
    "thunderbolt": "special",
    "psychic": "special",
    "dazzling-gleam": "special",
    "shadow-ball": "special",
    "focus-blast": "special",
    "rock-slide": "physical",
    "flamethrower": "special",
    "energy-ball": "special",
    # STAB moves — normal
    "body-slam": "physical",
    "double-edge": "physical",
    "return": "physical",
    "hyper-voice": "special",
    "tackle": "physical",
    # fire
    "fire-blast": "special",
    "heat-wave": "special",
    "fire-punch": "physical",
    "overheat": "special",
    "ember": "special",
    # water
    "hydro-pump": "special",
    "surf": "special",
    "scald": "special",
    "muddy-water": "special",
    "water-pulse": "special",
    "waterfall": "physical",
    # electric
    "thunder": "special",
    "discharge": "special",
    "thunder-punch": "physical",
    "wild-charge": "physical",
    # grass
    "leaf-storm": "special",
    "giga-drain": "special",
    "grass-knot": "special",
    "leaf-blade": "physical",
    "seed-bomb": "physical",
    # ice
    "blizzard": "special",
    "icicle-crash": "physical",
    "ice-punch": "physical",
    "ice-fang": "physical",
    "freeze-dry": "special",
    # fighting
    "close-combat": "physical",
    "drain-punch": "physical",
    "aura-sphere": "special",
    "brick-break": "physical",
    "dynamic-punch": "physical",
    # poison
    "sludge-bomb": "special",
    "gunk-shot": "physical",
    "poison-jab": "physical",
    "sludge-wave": "special",
    # ground
    "earth-power": "special",
    "high-horsepower": "physical",
    "bulldoze": "physical",
    # flying
    "brave-bird": "physical",
    "air-slash": "special",
    "hurricane": "special",
    "drill-peck": "physical",
    "aerial-ace": "physical",
    # psychic
    "psyshock": "special",
    "psystrike": "special",
    "expanding-force": "special",
    "stored-power": "special",
    # bug
    "u-turn": "physical",
    "bug-buzz": "special",
    "x-scissor": "physical",
    "megahorn": "physical",
    "leech-life": "physical",
    # rock
    "stone-edge": "physical",
    "power-gem": "special",
    "ancient-power": "special",
    # ghost
    "shadow-claw": "physical",
    "poltergeist": "physical",
    # dragon
    "draco-meteor": "special",
    "dragon-pulse": "special",
    "dragon-claw": "physical",
    # dark
    "dark-pulse": "special",
    "knock-off": "physical",
    "crunch": "physical",
    "foul-play": "physical",
    # steel
    "iron-head": "physical",
    "flash-cannon": "special",
    "meteor-mash": "physical",
    "iron-tail": "physical",
    # fairy
    "moonblast": "special",
    "play-rough": "physical",
    "fleur-cannon": "special",
}

# Move → damage type table. Phase 4b cleanup (Tecle Brief #9): the
# canonical map lives in ``pokemon_team_builder.data.move_types`` so
# both this module and ``synergy_engine.analyze_coverage`` can import
# it without the previous lazy cross-service hop. To add a move, edit
# ``data/move_types.py`` — this name is an alias kept for the legacy
# call sites in this module (and only this module).
from pokemon_team_builder.data.move_types import MOVE_TYPE as _MOVE_TYPE

_CHOICE_ITEMS: frozenset[str] = frozenset({"Choice Scarf", "Choice Band", "Choice Specs"})

# When a Pokemon has a weather-setting ability, certain moves become strictly
# better than the default preferred alternative (Blizzard never misses in
# snow — 110 BP vs 90 BP of Ice Beam with 100% accuracy). Override slot-2
# when the preferred move is in the Pokemon's actual move pool.
_ABILITY_STAB_OVERRIDES: dict[str, dict[str, str]] = {
    "snow-warning": {"ice-beam": "blizzard"},
    "no-guard": {"close-combat": "dynamic-punch"},
    # Drizzle: rain makes Thunder 100% accurate (vs 70% normal). 110 BP
    # vs Thunderbolt's 90 BP — clear win when the user is on a Drizzle team.
    # Hurricane override stays for Flying STAB.
    "drizzle": {
        "air-slash": "hurricane",
        "thunderbolt": "thunder",
        "thunder-shock": "thunder",
    },
}
_SETUP_MOVES: frozenset[str] = frozenset({
    "nasty-plot", "calm-mind", "tail-glow",
    "swords-dance", "dragon-dance", "bulk-up",
    "quiver-dance", "shell-smash", "coil", "hone-claws", "work-up",
})


# Support roles that should be checked first in slot-4 selection. When a
# Pokémon has both sweeper and support roles, the support move wins slot 4
# (Rage Powder > Calm Mind, Trick Room > Nasty Plot).
_SLOT4_SUPPORT_ROLES: frozenset[str] = frozenset({
    "lead_support", "redirect", "trick_room_setter",
})

# Role -> ordered list of preferred role moves.
_ROLE_MOVE_PRIORITY: dict[str, tuple[str, ...]] = {
    "lead_support": (
        "tailwind", "fake-out", "follow-me", "rage-powder",
        "thunder-wave", "spiky-shield", "encore",
    ),
    "trick_room_setter": ("trick-room",),
    "redirect": ("follow-me", "rage-powder"),
    "physical_sweeper": ("swords-dance", "dragon-dance", "bulk-up"),
    "special_sweeper": ("nasty-plot", "calm-mind", "tail-glow"),
    "physical_wall": ("recover", "roost", "slack-off", "wish", "synthesis"),
    "special_wall": ("recover", "roost", "slack-off", "wish", "synthesis"),
}


IMPORT_INSTRUCTIONS: str = (
    "Para importar tu equipo en Pokemon Champions:\n"
    "1. Copia el texto PokePaste generado\n"
    "2. Ve a https://pikachampions.com/ o https://champteams.gg/\n"
    "3. Importa el equipo como \"Replica Team\"\n"
    "4. El codigo de replica aparecera para usarlo en el juego"
)


def _first_available(candidates: tuple[str, ...], move_pool: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in move_pool:
            return candidate
    return None


_BO3_CHEESE_MOVES = frozenset({
    "destiny-bond", "mirror-coat", "counter", "memento", "perish-song",
})

# Phase 2b (strategy-archetype): the cheese-move gate. When the active
# archetype's ``cheese_allowance < 1.0`` we skip moves in this set during
# selection so they never end up in a moveset. ``perish_trap`` has
# ``cheese_allowance = 1.0`` and explicitly wants Perish Song; balance /
# bulky_offense / stall have <1.0 and skip the cheese set entirely.
#
# WHY a separate set from ``_BO3_CHEESE_MOVES``: the Bo3 gate has always
# been about "open sheet means cheese is dead weight" — it is an
# orthogonal concern. The two sets happen to be identical today but may
# diverge (e.g. Perish Song behaves fine in Bo3 perish_trap, and a future
# archetype might allow Destiny Bond while Bo3 still vetoes it). Keeping
# them separate avoids coupling the two policies.
_ARCHETYPE_CHEESE_MOVES: frozenset[str] = frozenset({
    "destiny-bond", "mirror-coat", "counter", "memento", "perish-song",
})

# Threshold at which the cheese set is allowed. Strict ``>=`` so a value
# of exactly 1.0 (perish_trap) opens the gate, anything below blocks.
_CHEESE_GATE_THRESHOLD: float = 1.0


def select_moves_for_role(
    pokemon: PokemonData,
    roles: list[str],
    *,
    item: str = "",
    meta_moves: list[str] | None = None,
    format_mode: str = "bo1",
    archetype: str = "balance",
) -> list[str]:
    """Pick exactly 4 moves for a Pokemon given its assigned roles.

    Slot 1 is always Protect. Slot 2 is the best STAB move that the
    Pokemon actually knows. Slot 3 is a coverage move (non-STAB). Slot 4
    fills the role need (e.g. Tailwind for a lead_support).

    Falls back gracefully: missing slot-3 / slot-4 candidates are filled
    by the first known move, then by ``tackle`` if the move pool is empty.
    """
    primary_role = roles[0] if roles else "physical_sweeper"
    move_pool = list(pokemon.move_names)
    used: set[str] = set()

    # Phase 2b cheese-allowance gate. We resolve the archetype's weights
    # once and decide whether the cheese set is on-limits. Any move
    # selection pass below (meta, STAB tables, coverage, role priority,
    # fallback) must respect this gate when ``archetype_blocks_cheese``
    # is True.
    archetype_weights = get_weights(archetype)
    archetype_blocks_cheese = (
        archetype_weights.cheese_allowance < _CHEESE_GATE_THRESHOLD
    )

    # Slot 1: protect when the Pokemon actually knows it. Most legal mons
    # learn Protect, but a handful (e.g. species locked to specific
    # tutors) don't — in that case the slot falls back to whatever the
    # move pool offers so we don't emit a move the importer rejects.
    if "protect" in move_pool:
        slot1 = "protect"
    else:
        slot1 = _fallback_move(move_pool, set())
    used.add(slot1)

    # Primary attack category: physical if Atk >= SpA, else special.
    primary_cat = (
        "physical"
        if pokemon.base_stats.atk >= pokemon.base_stats.spa
        else "special"
    )

    # Slot 2: STAB — try meta moves that are STAB for this pokémon and
    # category-matching first; then fall through to the static STAB table.
    own_types_lower = {t.lower() for t in pokemon.types}
    slot2 = None
    if meta_moves:
        for candidate in meta_moves:
            if candidate in used or candidate not in move_pool:
                continue
            cand_type = _MOVE_TYPE.get(candidate, "")
            # Only skip when we know the type and it isn't STAB;
            # unknown types (not in table) are allowed through.
            if cand_type and cand_type not in own_types_lower:
                continue
            cand_cat = _MOVE_CATEGORY.get(candidate, "")
            if cand_cat and cand_cat != primary_cat:
                continue  # category mismatch in strict pass
            slot2 = candidate
            break

    if slot2 is None:
        for pass_num in range(2):
            for ptype in pokemon.types:
                for candidate in _STAB_BY_TYPE.get(ptype.lower(), ()):
                    if candidate in used or candidate not in move_pool:
                        continue
                    cand_cat = _MOVE_CATEGORY.get(candidate, "")
                    # WHY: ``cand_cat == ""`` means we have no category metadata
                    # for this move. The earlier guard ``cand_cat and cand_cat
                    # != primary_cat`` would let it through pass 0, which is
                    # too permissive — an unknown move could pre-empt a
                    # category-matching one. Treat unknown as ineligible in
                    # pass 0; pass 1 still picks it up.
                    if pass_num == 0 and cand_cat != primary_cat:
                        continue  # first pass: category-matching only
                    slot2 = candidate
                    break
                if slot2:
                    break
            if slot2:
                break
    if slot2 is None:
        slot2 = _fallback_move(move_pool, used)

    # Ability-aware STAB upgrade: iterate all abilities in order, use the first
    # one found in _ABILITY_STAB_OVERRIDES (PokeAPI lists abilities as
    # [slot1, slot2, hidden] — competitive ability is not always at index 0).
    ability_overrides: dict[str, str] = {}
    for _ab in pokemon.abilities:
        _overrides = _ABILITY_STAB_OVERRIDES.get(_ab.lower(), {})
        if _overrides:
            ability_overrides = _overrides
            break
    upgrade = ability_overrides.get(slot2)
    if upgrade and upgrade in move_pool and upgrade not in used:
        slot2 = upgrade

    used.add(slot2)

    # STAB-presence invariant (Phase 2a, spec §5.2):
    # Every Pokemon with type X SHALL have ≥1 STAB move of type X in slots 1–4
    # WHEN such a move exists in its movepool. For dual-type members, this
    # means slot 3 may need to carry a second STAB instead of coverage if the
    # member's other type was not picked up by slot 2.
    #
    # WHY this comes BEFORE the coverage slot 3 logic: slot 3's default is
    # "best coverage move that is NOT one of the member's types". If we
    # blindly pick coverage first, a Garchomp (Ground/Dragon) with slot 2 =
    # Earthquake (Ground STAB) would never end up with Dragon STAB — its
    # second type would be uncovered by its own attacks. The invariant
    # forces slot 3 to a Dragon STAB when one is available in the pool.
    slot2_type = _MOVE_TYPE.get(slot2, "")
    covered_stab_types: set[str] = {slot2_type} if slot2_type else set()
    missing_stab_types: list[str] = [
        t.lower() for t in pokemon.types
        if t.lower() not in covered_stab_types
    ]

    second_stab: str | None = None
    for missing_type in missing_stab_types:
        # Prefer a meta-listed STAB move (PokeAPI-aligned vocabulary).
        if meta_moves:
            for candidate in meta_moves:
                if candidate in used or candidate not in move_pool:
                    continue
                cand_type = _MOVE_TYPE.get(candidate, "")
                if cand_type != missing_type:
                    continue
                second_stab = candidate
                break
        if second_stab is not None:
            break
        # Fall back to the curated STAB-by-type table.
        for candidate in _STAB_BY_TYPE.get(missing_type, ()):
            if candidate in used or candidate not in move_pool:
                continue
            second_stab = candidate
            break
        if second_stab is not None:
            break

    # Slot 3: coverage — try meta moves that are non-STAB and category-matching
    # first; then fall through to the static coverage table. When the STAB
    # invariant requires a second STAB AND the pool has it, slot 3 carries
    # the missing STAB instead of generic coverage.
    own_types = own_types_lower  # alias kept for readability in guards below
    slot3 = None
    if second_stab is not None:
        slot3 = second_stab
    else:
        if meta_moves:
            for candidate in meta_moves:
                if candidate in used or candidate not in move_pool:
                    continue
                cand_type = _MOVE_TYPE.get(candidate, "")
                if cand_type and cand_type in own_types_lower:
                    continue  # skip STAB moves
                cand_cat = _MOVE_CATEGORY.get(candidate, "")
                if cand_cat and cand_cat != primary_cat:
                    continue  # category mismatch
                # accept meta coverage move
                slot3 = candidate
                break

        if slot3 is None:
            for pass_num in range(2):
                for candidate in _COVERAGE_PRIORITY:
                    if candidate in used or candidate not in move_pool:
                        continue
                    candidate_type = _MOVE_TYPE.get(candidate, "")
                    if candidate_type and candidate_type in own_types:
                        continue
                    cand_cat = _MOVE_CATEGORY.get(candidate, "")
                    # See slot-2 comment: unknown category is treated as ineligible
                    # in pass 0 so a categorized move always wins the strict pass.
                    if pass_num == 0 and cand_cat != primary_cat:
                        continue  # first pass: category-matching only
                    slot3 = candidate
                    break
                if slot3:
                    break
    if slot3 is None:
        slot3 = _fallback_move(move_pool, used)
    used.add(slot3)

    # Slot 4: role move — walk all assigned roles, support roles first so that
    # a Pokemon with both sweeper and support roles emits the support move
    # (Rage Powder > Calm Mind, Trick Room > Nasty Plot). Order within each
    # group is preserved from the original roles list.
    #
    # Phase 2b perish_trap special case: when the archetype is perish_trap
    # AND the member knows Perish Song, slot 4 prefers Perish Song over any
    # other role-priority move. This is the archetype's central strategy
    # so its enablers win the slot when present.
    slot4_order = sorted(
        roles, key=lambda r: (0 if r in _SLOT4_SUPPORT_ROLES else 1, roles.index(r))
    )
    slot4 = None
    if (
        archetype == "perish_trap"
        and "perish-song" in move_pool
        and "perish-song" not in used
    ):
        slot4 = "perish-song"

    if slot4 is None:
        for role in slot4_order:
            for candidate in _ROLE_MOVE_PRIORITY.get(role, ()):
                if candidate in used:
                    continue
                if item in _CHOICE_ITEMS and candidate in _SETUP_MOVES:
                    continue  # locked-in setup is useless with a Choice item
                if format_mode == "bo3" and candidate in _BO3_CHEESE_MOVES:
                    continue  # open sheet: cheese moves are dead weight in Bo3
                if archetype_blocks_cheese and candidate in _ARCHETYPE_CHEESE_MOVES:
                    # Phase 2b: archetype's cheese_allowance < 1.0, drop
                    # destiny-bond / mirror-coat / counter / memento /
                    # perish-song from slot-4 candidates.
                    continue
                if candidate in move_pool:
                    slot4 = candidate
                    break
            if slot4 is not None:
                break
    if slot4 is None:
        # Build the exclusion set: Bo3 always vetoes cheese; archetype
        # gate optionally adds the archetype cheese set on top.
        exclude_set: set[str] = set()
        if format_mode == "bo3":
            exclude_set |= _BO3_CHEESE_MOVES
        if archetype_blocks_cheese:
            exclude_set |= _ARCHETYPE_CHEESE_MOVES
        slot4 = _fallback_move(move_pool, used | exclude_set)
    used.add(slot4)

    return [slot1, slot2, slot3, slot4]


def _fallback_move(move_pool: list[str], used: set[str]) -> str:
    for m in move_pool:
        if m not in used:
            return m
    # Pool exhausted — cycle through universal generics before repeating.
    # WHY: returning a move already in ``used`` would create a duplicate-move
    # set that fails PikaChampions / Showdown validation. The previous
    # implementation fell back to ``return "tackle"`` even when ``tackle``
    # was already in ``used``, silently emitting an invalid moveset.
    for generic in ("tackle", "scratch", "pound", "growl", "leer"):
        if generic not in used:
            return generic
    raise TeamBuildError(
        "No hay move disponible para este Pokemon — move pool demasiado "
        "pequeno para generar 4 moves unicos."
    )


def _format_name(slug: str) -> str:
    """Convert ``"air-slash"`` to ``"Air Slash"``.

    Used for moves, abilities, and natures — every space-separated word
    is capitalized and the original hyphens are dropped.
    """
    return " ".join(part.capitalize() for part in slug.split("-") if part)


# Showdown / PikaChampions species names that do NOT follow the
# split-on-hyphen-then-Capitalize rule. Each entry has been verified
# against PokePaste output. Add new exceptions here when found.
_SPECIES_OVERRIDES: dict[str, str] = {
    "kommo-o": "Kommo-o",
    "ho-oh": "Ho-Oh",
    "porygon-z": "Porygon-Z",
}


def _format_species(slug: str) -> str:
    """Convert species slug to PokePaste form preserving hyphens.

    Showdown / PokePaste use hyphens to express species variants (forms,
    regional sub-species, etc.). Examples:
        ``"rotom-wash"``            -> ``"Rotom-Wash"``
        ``"tapu-koko"``             -> ``"Tapu-Koko"``
        ``"urshifu-single-strike"`` -> ``"Urshifu-Single-Strike"``

    WHY: ``_format_name`` would turn ``"rotom-wash"`` into
    ``"Rotom Wash"``, which PikaChampions / champteams.gg do not match
    against their species table — the import silently drops the mon.

    A small override table handles species whose canonical name does
    not follow the title-case-each-segment rule (e.g. ``Kommo-o`` keeps
    a lowercase ``o``).
    """
    if slug in _SPECIES_OVERRIDES:
        return _SPECIES_OVERRIDES[slug]
    return "-".join(part.capitalize() for part in slug.split("-") if part)


def _ev_line(sp: SPDistribution) -> str:
    """Format the ``EVs:`` line using raw SP values (0–32), skipping zeros."""
    pairs: list[tuple[str, int]] = [
        ("HP", sp.hp),
        ("Atk", sp.atk),
        ("Def", sp.def_),
        ("SpA", sp.spa),
        ("SpD", sp.spd),
        ("Spe", sp.spe),
    ]
    parts: list[str] = []
    for label, sp_value in pairs:
        if sp_value <= 0:
            continue
        parts.append(f"{sp_value} {label}")
    if not parts:
        return ""
    return "EVs: " + " / ".join(parts)


def _serialize_member(member: TeamMember) -> str:
    name = _format_species(member.pokemon.name)
    # WHY: when the member is Mega-evolved, the held item is the Mega
    # Stone and is the authoritative source — read it directly from
    # ``mega_form`` instead of trusting a possibly-stale ``item`` field.
    # The species line stays the base form (Showdown convention — the
    # importer auto-detects Mega from the held stone).
    if member.mega_form is not None:
        item = member.mega_form.mega_stone
    else:
        item = member.item
    ability = _format_name(member.ability)
    nature = _format_name(member.nature)

    lines: list[str] = []
    lines.append(f"{name} @ {item}")
    lines.append(f"Ability: {ability}")
    lines.append("Level: 50")
    ev_line = _ev_line(member.sp_distribution)
    if ev_line:
        lines.append(ev_line)
    lines.append(f"{nature} Nature")
    for move in member.moves:
        lines.append(f"- {_format_name(move)}")
    return "\n".join(lines)


def to_pokepaste(variant: TeamVariant) -> str:
    """Serialize a TeamVariant to Showdown PokePaste format.

    Compatible with PikaChampions / champteams.gg replica imports.
    Members are separated by a single blank line; no trailing newline.
    """
    blocks = [_serialize_member(member) for member in variant.members]
    return "\n\n".join(blocks)


def save_to_file(content: str, path: Path, force: bool = False) -> None:
    """Write ``content`` to ``path`` in UTF-8.

    Raises FileExistsError if ``path`` already exists and ``force`` is
    False — keeps the user from accidentally overwriting a saved team.
    """
    if path.exists() and not force:
        raise FileExistsError(
            f"El archivo '{path}' ya existe. Usa --force para sobreescribir."
        )
    path.write_text(content, encoding="utf-8")
