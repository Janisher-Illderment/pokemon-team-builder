from __future__ import annotations

import re

from pokemon_team_builder.config import MAX_SP_STAT, MAX_SP_TOTAL
from pokemon_team_builder.data.legal_pool_loader import is_legal
from pokemon_team_builder.data.mega_loader import load_mega_evolutions
from pokemon_team_builder.domain.models import (
    MegaForm,
    SPDistribution,
    TeamMember,
    TeamVariant,
)
from pokemon_team_builder.services import pokemon_lookup
from pokemon_team_builder.services.synergy_engine import assign_role

# stat name → SPDistribution field name
_EV_STAT_MAP: dict[str, str] = {
    "hp": "hp", "atk": "atk", "def": "def_",
    "spa": "spa", "spd": "spd", "spe": "spe",
}

# Regex to detect Mega suffixes: -Mega, -Mega-X, -Mega-Y
_MEGA_RE = re.compile(r"^(.+)-mega(-x|-y)?$", re.IGNORECASE)


def _slugify(name: str) -> str:
    return name.strip().lower().replace(" ", "-")


def _evs_to_sps(ev_line: str) -> tuple[SPDistribution, list[str]]:
    """Convert a Showdown EV line to SPDistribution.

    Returns (sp_distribution, warnings).
    """
    warnings: list[str] = []
    raw: dict[str, int] = {}

    for part in ev_line.split("/"):
        part = part.strip()
        m = re.match(r"(\d+)\s+(\w+)", part)
        if not m:
            continue
        val = int(m.group(1))
        stat_key = m.group(2).lower()
        field = _EV_STAT_MAP.get(stat_key)
        if field is None:
            continue
        if val > 256:
            warnings.append(f"EV valor {val} para {stat_key} excede 256; clamp a MAX_SP_STAT")
            val = 256
        raw[field] = min(MAX_SP_STAT, val // 8)

    # Clamp total to MAX_SP_TOTAL (reduce largest first)
    total = sum(raw.values())
    if total > MAX_SP_TOTAL:
        excess = total - MAX_SP_TOTAL
        for field in sorted(raw, key=lambda k: raw[k], reverse=True):
            reduction = min(excess, raw[field])
            raw[field] -= reduction
            excess -= reduction
            if excess <= 0:
                break

    sp = SPDistribution(
        hp=raw.get("hp", 0),
        atk=raw.get("atk", 0),
        **{"def": raw.get("def_", 0)},
        spa=raw.get("spa", 0),
        spd=raw.get("spd", 0),
        spe=raw.get("spe", 0),
    )
    return sp, warnings


def _parse_block(block: str) -> tuple[TeamMember, list[str]]:
    """Parse a single PokePaste block into a TeamMember + warnings."""
    warnings: list[str] = []
    lines = [line.rstrip() for line in block.strip().splitlines()]
    if not lines:
        raise ValueError("Bloque vacío en el PokePaste")

    # Line 1: "Species @ Item" or just "Species"
    species_line = lines[0]
    if "@" in species_line:
        raw_name, raw_item = species_line.split("@", 1)
        item = raw_item.strip()
    else:
        raw_name = species_line
        item = ""
        warnings.append(f"Sin item para {raw_name.strip()}")

    raw_name = raw_name.strip()

    # Detect and strip Mega suffix
    mega_match = _MEGA_RE.match(raw_name)
    mega_form: MegaForm | None = None
    if mega_match:
        base_name = mega_match.group(1).strip()
        variant_suffix = (mega_match.group(2) or "").lower()  # "-x", "-y", or ""
        base_slug = _slugify(base_name)
        all_megas = load_mega_evolutions()
        megas_for_base = all_megas.get(base_slug, [])
        if megas_for_base:
            if variant_suffix:
                form_id = f"{base_slug}-mega{variant_suffix}"
                mega_form = next(
                    (mf for mf in megas_for_base if mf.form_id == form_id),
                    megas_for_base[0],
                )
            else:
                mega_form = megas_for_base[0]
            item = mega_form.mega_stone
        species_slug = base_slug
    else:
        species_slug = _slugify(raw_name)

    # Validate legal pool
    if not is_legal(species_slug):
        raise ValueError(f"'{species_slug}' no está en el pool legal M-A")

    # Lookup pokemon data
    try:
        pokemon = pokemon_lookup.lookup(species_slug)
    except Exception as exc:
        raise ValueError(f"No se puede resolver '{species_slug}': {exc}") from exc

    # Parse remaining lines
    ability = pokemon.abilities[0] if pokemon.abilities else "run-away"
    sp = SPDistribution()
    has_evs = False
    nature = "Hardy"
    moves: list[str] = []

    for line in lines[1:]:
        if line.startswith("- "):
            moves.append(_slugify(line[2:]))
        elif line.lower().startswith("ability:"):
            ability = line.split(":", 1)[1].strip()
        elif line.lower().startswith("evs:"):
            sp, ev_warns = _evs_to_sps(line.split(":", 1)[1].strip())
            warnings.extend(ev_warns)
            has_evs = True
        elif re.match(r"^\w+ nature$", line, re.IGNORECASE):
            nature = line.split()[0].title()
        # else: ignore (Level, Shiny, Tera Type, IVs, Happiness, etc.)

    roles = assign_role(pokemon)

    # Fallback: paste sin EVs (común en LabMaus top teams) → sugerir spread por rol
    if not has_evs:
        from pokemon_team_builder.services.team_generator import suggest_sp_distribution
        primary = roles[0] if roles else "physical_sweeper"
        sp = suggest_sp_distribution(pokemon, primary)
        warnings.append(
            f"ℹ {pokemon.name}: paste sin EVs — spread sugerido por rol '{primary}'"
        )

    # Validate and pad moves
    validated_moves: list[str] = []
    for mv in moves[:4]:
        if mv not in pokemon.move_names:
            warnings.append(
                f"ℹ {pokemon.name}: '{mv}' no está en datos PokeAPI — incluido igualmente"
            )
        validated_moves.append(mv)

    while len(validated_moves) < 4:
        warnings.append(f"{pokemon.name}: menos de 4 moves; relleno con 'tackle'")
        validated_moves.append("tackle")

    member = TeamMember(
        pokemon=pokemon,
        role=roles,
        sp_distribution=sp,
        item=item,
        ability=ability,
        nature=nature,
        moves=validated_moves[:4],
        mega_form=mega_form,
    )
    return member, warnings


def parse_pokepaste(text: str) -> tuple[TeamVariant, list[str]]:
    """Parse a Showdown PokePaste into a TeamVariant + warnings.

    Raises ValueError with a descriptive Spanish message on hard errors:
    - not exactly 6 member blocks
    - illegal/unresolvable Pokemon
    - duplicate species
    """
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Split on blank lines (one or more)
    blocks = [b.strip() for b in re.split(r"\n{2,}", text) if b.strip()]

    if len(blocks) < 6:
        raise ValueError(
            f"El PokePaste tiene {len(blocks)} miembro(s); se requieren exactamente 6"
        )
    if len(blocks) > 6:
        raise ValueError(
            f"El PokePaste tiene {len(blocks)} miembros; el máximo es 6"
        )

    members: list[TeamMember] = []
    all_warnings: list[str] = []
    seen_species: set[str] = set()

    for block in blocks:
        member, warns = _parse_block(block)
        all_warnings.extend(warns)
        name = member.pokemon.name
        if name in seen_species:
            raise ValueError(
                f"Species Clause: '{name}' aparece más de una vez en el PokePaste"
            )
        seen_species.add(name)
        members.append(member)

    return TeamVariant(members=members), all_warnings
