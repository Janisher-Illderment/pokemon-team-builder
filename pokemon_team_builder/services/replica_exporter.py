from __future__ import annotations

from pathlib import Path

from pokemon_team_builder.domain.models import (
    PokemonData,
    SPDistribution,
    TeamMember,
    TeamVariant,
)


# WHY: 1 SP equates to 8 EVs in Pokemon Champions' replica format. Showdown
# caps per-stat EVs at 252 — past that the surplus is wasted, so we clamp.
_SP_TO_EV = 8
_SHOWDOWN_EV_CAP = 252


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
    "water": ("hydro-pump", "surf", "scald", "muddy-water", "water-pulse", "waterfall"),
    "electric": (
        "thunderbolt",
        "thunder",
        "discharge",
        "thunder-punch",
        "wild-charge",
    ),
    "grass": (
        "energy-ball",
        "leaf-storm",
        "giga-drain",
        "grass-knot",
        "leaf-blade",
        "seed-bomb",
    ),
    "ice": ("ice-beam", "blizzard", "icicle-crash", "ice-punch", "freeze-dry"),
    "fighting": (
        "close-combat",
        "drain-punch",
        "focus-blast",
        "aura-sphere",
        "brick-break",
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
        "stored-power",
    ),
    "bug": ("u-turn", "bug-buzz", "x-scissor", "megahorn", "leech-life"),
    "rock": ("rock-slide", "stone-edge", "power-gem", "ancient-power"),
    "ghost": ("shadow-ball", "shadow-claw", "poltergeist", "phantom-force"),
    "dragon": ("draco-meteor", "dragon-pulse", "outrage", "dragon-claw"),
    "dark": ("dark-pulse", "knock-off", "crunch", "foul-play"),
    "steel": ("iron-head", "flash-cannon", "meteor-mash", "iron-tail"),
    "fairy": ("moonblast", "dazzling-gleam", "play-rough", "fleur-cannon"),
}

# Generic coverage moves (non-STAB), in priority order.
_COVERAGE_PRIORITY: tuple[str, ...] = (
    "earthquake",
    "ice-beam",
    "thunderbolt",
    "psychic",
    "dazzling-gleam",
    "shadow-ball",
    "focus-blast",
    "rock-slide",
    "flamethrower",
    "energy-ball",
)

# Damage type for every move that may appear in a coverage / STAB slot.
# WHY: previously slot-3 used ``candidate.startswith(t)`` against the
# Pokemon's own types to skip same-type coverage; that was coincidentally
# correct (e.g. "flamethrower".startswith("fire")) but semantically wrong
# (e.g. "ice-beam".startswith("ice") only works because of slug ordering).
# An explicit move→type table keeps the filter intentional and robust to
# future additions like "icicle-crash" (ice) or "iron-tail" (steel).
_MOVE_TYPE: dict[str, str] = {
    "earthquake": "ground",
    "ice-beam": "ice",
    "thunderbolt": "electric",
    "psychic": "psychic",
    "dazzling-gleam": "fairy",
    "shadow-ball": "ghost",
    "focus-blast": "fighting",
    "rock-slide": "rock",
    "energy-ball": "grass",
    "flamethrower": "fire",
    "surf": "water",
    "air-slash": "flying",
    "iron-head": "steel",
    "dark-pulse": "dark",
    "dragon-pulse": "dragon",
    "poison-jab": "poison",
    "bug-buzz": "bug",
    "flash-cannon": "steel",
}

# Role -> ordered list of preferred role moves.
_ROLE_MOVE_PRIORITY: dict[str, tuple[str, ...]] = {
    "lead_support": ("tailwind", "fake-out", "follow-me", "rage-powder"),
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


def select_moves_for_role(
    pokemon: PokemonData, roles: list[str]
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

    # Slot 1: protect (always present in the team — universally available
    # in modern formats and required by the spec).
    slot1 = "protect"
    used.add(slot1)

    # Slot 2: STAB based on the primary type.
    slot2 = None
    for ptype in pokemon.types:
        candidates = _STAB_BY_TYPE.get(ptype.lower(), ())
        chosen = _first_available(candidates, move_pool)
        if chosen and chosen not in used:
            slot2 = chosen
            break
    if slot2 is None:
        slot2 = _fallback_move(move_pool, used)
    used.add(slot2)

    # Slot 3: coverage (skip moves of the Pokemon's own types when possible).
    own_types = {t.lower() for t in pokemon.types}
    slot3 = None
    for candidate in _COVERAGE_PRIORITY:
        if candidate in used:
            continue
        if candidate not in move_pool:
            continue
        # Skip same-type moves so slot 3 actually broadens coverage
        # beyond the STAB locked in slot 2. Falls back to "" for moves
        # not in the table — those are kept (we err on inclusion).
        candidate_type = _MOVE_TYPE.get(candidate, "")
        if candidate_type and candidate_type in own_types:
            continue
        slot3 = candidate
        break
    if slot3 is None:
        slot3 = _fallback_move(move_pool, used)
    used.add(slot3)

    # Slot 4: role move — walk all assigned roles, not just primary, so a
    # pokemon with roles ["lead_support", "redirect"] gets follow-me/tailwind
    # even if the primary-role list is exhausted.
    slot4 = None
    for role in roles:
        for candidate in _ROLE_MOVE_PRIORITY.get(role, ()):
            if candidate in used:
                continue
            if candidate in move_pool:
                slot4 = candidate
                break
        if slot4 is not None:
            break
    if slot4 is None:
        slot4 = _fallback_move(move_pool, used)
    used.add(slot4)

    return [slot1, slot2, slot3, slot4]


def _fallback_move(move_pool: list[str], used: set[str]) -> str:
    for m in move_pool:
        if m not in used:
            return m
    # Pool exhausted — cycle through universal generics before repeating.
    # WHY: returning a move already in ``used`` would create a duplicate-move
    # set that fails PikaChampions / Showdown validation.
    for generic in ("tackle", "scratch", "pound", "growl", "leer"):
        if generic not in used:
            return generic
    return "tackle"  # absolute last resort — cannot deduplicate further


def _format_name(slug: str) -> str:
    """Convert ``"air-slash"`` to ``"Air Slash"``.

    Used for moves, abilities, and natures — every space-separated word
    is capitalized and the original hyphens are dropped.
    """
    return " ".join(part.capitalize() for part in slug.split("-") if part)


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
    """
    return "-".join(part.capitalize() for part in slug.split("-") if part)


def _ev_line(sp: SPDistribution) -> str:
    """Format the ``EVs:`` line, skipping zero-stat entries."""
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
        ev = min(_SHOWDOWN_EV_CAP, sp_value * _SP_TO_EV)
        parts.append(f"{ev} {label}")
    if not parts:
        return ""
    return "EVs: " + " / ".join(parts)


def _serialize_member(member: TeamMember) -> str:
    name = _format_species(member.pokemon.name)
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
