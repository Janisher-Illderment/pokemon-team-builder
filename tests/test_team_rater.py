"""Tests del Team Rater (ADR docs/adr-team-rater.md §9).

Calibración con FIXTURES sintéticos deterministas (no datos de meta inventados):
construimos equipos a partir de mons del pool legal real con moves/abilities
verificados en código, y aseveramos las etiquetas/notas resultantes.
"""

from __future__ import annotations

import pytest

from pokemon_team_builder.domain.models import (
    SPDistribution,
    TeamMember,
    TeamVariant,
)
from pokemon_team_builder.services import pokemon_lookup
from pokemon_team_builder.services import team_rater
from pokemon_team_builder.services.team_rater import detect_archetype


# ── Helpers de construcción de fixtures ──────────────────────────────────────

def _member(
    species: str,
    moves: list[str],
    *,
    ability: str | None = None,
    nature: str = "Hardy",
    item: str = "Leftovers",
    sp: dict[str, int] | None = None,
) -> TeamMember:
    """Construye un TeamMember determinista a partir de datos reales del pool.

    El rol se asigna por especie (mismo camino que el parser: assign_role).
    SP por defecto: 252/252 estilo Showdown ya dividido (31/31 → 62 total),
    salvo override.
    """
    from pokemon_team_builder.services.synergy_engine import assign_role

    pokemon = pokemon_lookup.lookup(species)
    roles = assign_role(pokemon)
    abil = ability if ability is not None else (
        pokemon.abilities[0] if pokemon.abilities else "run-away"
    )
    padded = list(moves)
    while len(padded) < 4:
        padded.append("protect" if "protect" not in padded else "tackle")
    sp_dist = (
        SPDistribution.model_validate(sp)
        if sp is not None
        else SPDistribution(atk=31, spe=31)
    )
    return TeamMember(
        pokemon=pokemon,
        role=roles,
        sp_distribution=sp_dist,
        item=item,
        ability=abil,
        nature=nature,
        moves=padded[:4],
    )


def _variant(members: list[TeamMember]) -> TeamVariant:
    assert len(members) == 6, "un fixture de equipo necesita exactamente 6 miembros"
    return TeamVariant(members=members)


# ── Fixtures: un equipo por arquetipo (grounded en mons legales) ─────────────

def _team_hyper_offense() -> TeamVariant:
    # ≥4 offensive_threat + ≥1 control de velocidad (Gengar Icy Wind).
    return _variant([
        _member("garchomp", ["earthquake", "dragon-claw", "rock-slide", "protect"],
                ability="Rough Skin", nature="Jolly", item="Choice Scarf"),
        _member("gengar", ["shadow-ball", "sludge-bomb", "icy-wind", "protect"],
                ability="Levitate", nature="Timid", item="Black Sludge"),
        _member("metagross", ["meteor-mash", "bullet-punch", "earthquake", "protect"],
                ability="Clear Body", nature="Adamant", item="Sitrus Berry"),
        _member("aerodactyl", ["rock-slide", "earthquake", "tailwind", "protect"],
                ability="Rock Head", nature="Jolly", item="Focus Sash"),
        _member("dragonite", ["dragon-claw", "earthquake", "extreme-speed", "protect"],
                ability="Multiscale", nature="Adamant", item="Lum Berry"),
        _member("starmie", ["hydro-pump", "ice-beam", "thunderbolt", "protect"],
                ability="Natural Cure", nature="Timid", item="Life Orb"),
    ])


def _team_hard_trick_room() -> TeamVariant:
    # Slowbro setea TR; ≥2 lentos (Slowbro 30, Snorlax 30, Metagross 70 no,
    # Rhydon/Steelix lentos). Garantizamos ≥2 con spe ≤ 60.
    return _variant([
        _member("slowbro", ["trick-room", "psychic", "ice-beam", "protect"],
                ability="Regenerator", nature="Sassy", item="Sitrus Berry"),
        _member("snorlax", ["body-slam", "earthquake", "curse", "protect"],
                ability="Thick Fat", nature="Brave", item="Leftovers"),
        _member("steelix", ["earthquake", "iron-head", "rock-slide", "protect"],
                ability="Sturdy", nature="Brave", item="Lum Berry"),
        _member("metagross", ["meteor-mash", "bullet-punch", "earthquake", "protect"],
                ability="Clear Body", nature="Adamant", item="Choice Band"),
        _member("azumarill", ["waterfall", "play-rough", "aqua-jet", "protect"],
                ability="Huge Power", nature="Adamant", item="Assault Vest"),
        _member("gyarados", ["waterfall", "ice-fang", "earthquake", "protect"],
                ability="Intimidate", nature="Adamant", item="Sitrus Berry"),
    ])


def _team_weather_based() -> TeamVariant:
    # Ninetales (Drought) setter + Venusaur (Chlorophyll) abuser.
    return _variant([
        _member("ninetales", ["flamethrower", "sunny-day", "solar-beam", "protect"],
                ability="Drought", nature="Timid", item="Heat Rock"),
        _member("venusaur", ["giga-drain", "sludge-bomb", "sleep-powder", "protect"],
                ability="Chlorophyll", nature="Modest", item="Black Sludge"),
        _member("arcanine", ["flare-blitz", "extreme-speed", "wild-charge", "protect"],
                ability="Intimidate", nature="Adamant", item="Sitrus Berry"),
        _member("snorlax", ["body-slam", "earthquake", "curse", "protect"],
                ability="Thick Fat", nature="Careful", item="Leftovers"),
        _member("starmie", ["hydro-pump", "ice-beam", "thunderbolt", "protect"],
                ability="Natural Cure", nature="Timid", item="Choice Specs"),
        _member("metagross", ["meteor-mash", "bullet-punch", "earthquake", "protect"],
                ability="Clear Body", nature="Adamant", item="Choice Band"),
    ])


def _team_perish_trap() -> TeamVariant:
    # perish-song presente → perish_trap (perish nunca incidental).
    return _variant([
        _member("politoed", ["perish-song", "protect", "icy-wind", "scald"],
                ability="Drizzle", nature="Bold", item="Leftovers"),
        _member("gengar", ["perish-song", "shadow-ball", "icy-wind", "protect"],
                ability="Levitate", nature="Timid", item="Black Sludge"),
        _member("azumarill", ["waterfall", "play-rough", "aqua-jet", "protect"],
                ability="Huge Power", nature="Adamant", item="Sitrus Berry"),
        _member("snorlax", ["body-slam", "earthquake", "curse", "protect"],
                ability="Thick Fat", nature="Careful", item="Assault Vest"),
        _member("metagross", ["meteor-mash", "bullet-punch", "earthquake", "protect"],
                ability="Clear Body", nature="Adamant", item="Choice Band"),
        _member("milotic", ["scald", "ice-beam", "recover", "protect"],
                ability="Marvel Scale", nature="Bold", item="Flame Orb"),
    ])


def _team_balance() -> TeamVariant:
    # Mezcla sin identidad dominante: amenazas variadas, sin masa HO, sin clima,
    # sin TR, sin perish.
    return _variant([
        _member("milotic", ["scald", "ice-beam", "recover", "protect"],
                ability="Marvel Scale", nature="Bold", item="Leftovers"),
        _member("forretress", ["gyro-ball", "stealth-rock", "spikes", "protect"],
                ability="Sturdy", nature="Relaxed", item="Sitrus Berry"),
        _member("garchomp", ["earthquake", "dragon-claw", "rock-slide", "protect"],
                ability="Rough Skin", nature="Jolly", item="Choice Band"),
        _member("clefable", ["moonblast", "flamethrower", "thunderbolt", "protect"],
                ability="Magic Guard", nature="Modest", item="Life Orb"),
        _member("snorlax", ["body-slam", "earthquake", "curse", "protect"],
                ability="Thick Fat", nature="Careful", item="Assault Vest"),
        _member("gyarados", ["waterfall", "ice-fang", "earthquake", "protect"],
                ability="Intimidate", nature="Adamant", item="Lum Berry"),
    ])


# ── Tests B0: detect_archetype ───────────────────────────────────────────────

def test_detect_hyper_offense():
    arch, conf = detect_archetype(_team_hyper_offense())
    assert arch == "hyper_offense"
    assert 0.0 <= conf <= 1.0
    assert conf >= team_rater.LOW_CONFIDENCE_CUTOFF


def test_detect_hard_trick_room():
    arch, conf = detect_archetype(_team_hard_trick_room())
    assert arch == "hard_trick_room"
    assert conf >= team_rater.LOW_CONFIDENCE_CUTOFF


def test_detect_weather_based():
    arch, conf = detect_archetype(_team_weather_based())
    assert arch == "weather_based"
    assert 0.0 <= conf <= 1.0


def test_detect_perish_trap():
    arch, conf = detect_archetype(_team_perish_trap())
    assert arch == "perish_trap"
    assert 0.0 <= conf <= 1.0


def test_detect_balance_fallback():
    arch, conf = detect_archetype(_team_balance())
    # Un equipo sin identidad dominante cae en balance.
    assert arch == "balance"
    assert 0.0 <= conf <= 1.0


def test_detect_archetype_always_in_known_set():
    for builder in (
        _team_hyper_offense,
        _team_hard_trick_room,
        _team_weather_based,
        _team_perish_trap,
        _team_balance,
    ):
        arch, conf = detect_archetype(builder())
        assert arch in team_rater.ARCHETYPES
        assert 0.0 <= conf <= 1.0


def test_confidence_is_fraction():
    # La confianza nunca excede 1.0 ni baja de 0.0 en ningún fixture.
    for builder in (
        _team_hyper_offense,
        _team_hard_trick_room,
        _team_weather_based,
    ):
        _, conf = detect_archetype(builder())
        assert 0.0 <= conf <= 1.0
