from __future__ import annotations

from pokemon_team_builder.domain.models import (
    BaseStats,
    PokemonData,
    SPDistribution,
    TeamMember,
    TeamVariant,
)
from pokemon_team_builder.services import pokemon_lookup
from pokemon_team_builder.services.synergy_engine import assign_role
from pokemon_team_builder.services.viability_rater import (
    generate_explanation,
    rank_variants,
    score_team,
)


def _mk_pokemon(
    name: str,
    types: list[str],
    *,
    hp: int = 70,
    atk: int = 70,
    def_: int = 70,
    spa: int = 70,
    spd: int = 70,
    spe: int = 70,
    moves: list[str] | None = None,
    pid: int = 1,
) -> PokemonData:
    return PokemonData(
        id=pid,
        name=name,
        types=types,
        base_stats=BaseStats(
            hp=hp, atk=atk, **{"def": def_}, spa=spa, spd=spd, spe=spe
        ),
        move_names=moves or [],
        abilities=["pressure"],
        weaknesses=pokemon_lookup.calculate_weaknesses(types),
    )


def _mk_member(
    pokemon: PokemonData,
    *,
    item: str,
    nature: str = "Hardy",
    moves: list[str] | None = None,
    sp: SPDistribution | None = None,
) -> TeamMember:
    if sp is None:
        sp = SPDistribution.model_validate(
            {"atk": 32, "spe": 32, "hp": 2}
        )
    return TeamMember(
        pokemon=pokemon,
        role=assign_role(pokemon),
        sp_distribution=sp,
        item=item,
        ability=pokemon.abilities[0] if pokemon.abilities else "Pressure",
        nature=nature,
        moves=moves or ["protect", "tackle", "earthquake", "tailwind"],
    )


def _balanced_variant() -> TeamVariant:
    pokemons = [
        _mk_pokemon("garchomp", ["dragon", "ground"], atk=130, spe=102, pid=1),
        _mk_pokemon(
            "talonflame",
            ["fire", "flying"],
            atk=81,
            spe=126,
            moves=["tailwind", "brave-bird"],
            pid=2,
        ),
        _mk_pokemon("milotic", ["water"], hp=95, def_=79, spa=100, spd=125, spe=81, pid=3),
        _mk_pokemon("rotom-wash", ["electric", "water"], hp=50, spa=105, spd=107, spe=86, pid=4),
        _mk_pokemon("metagross", ["steel", "psychic"], atk=135, spe=70, pid=5),
        _mk_pokemon(
            "amoonguss",
            ["grass", "poison"],
            hp=114,
            spa=85,
            spe=30,
            moves=["rage-powder", "spore"],
            pid=6,
        ),
    ]
    items = [
        "Choice Band",
        "Focus Sash",
        "Leftovers",
        "Sitrus Berry",
        "Assault Vest",
        "Rocky Helmet",
    ]
    members = [
        _mk_member(p, item=item) for p, item in zip(pokemons, items)
    ]
    return TeamVariant(members=members)


def _weak_variant() -> TeamVariant:
    # All weak to electric (water/flying), no support, no sweepers >=100 atk/spa.
    pokemons = [
        _mk_pokemon("gyarados", ["water", "flying"], atk=85, spa=60, spe=81, pid=1),
        _mk_pokemon("pelipper", ["water", "flying"], atk=50, spa=85, spe=65, pid=2),
        _mk_pokemon("mantine", ["water", "flying"], atk=40, spa=80, spe=70, pid=3),
        _mk_pokemon("wingull", ["water", "flying"], atk=30, spa=55, spe=85, pid=4),
        _mk_pokemon("swanna", ["water", "flying"], atk=87, spa=87, spe=98, pid=5),
        _mk_pokemon("ducklett", ["water", "flying"], atk=44, spa=44, spe=58, pid=6),
    ]
    members = [
        _mk_member(
            p,
            item="Life Orb",  # all the same → kills item diversity points
            moves=["protect", "tackle", "scald", "wing-attack"],
        )
        for p in pokemons
    ]
    return TeamVariant(members=members)


def test_score_balanced_team_above_75() -> None:
    variant = _balanced_variant()
    score = score_team(variant)
    assert score >= 75


def test_score_weak_team_below_50() -> None:
    variant = _weak_variant()
    score = score_team(variant)
    assert score < 50


def test_rank_variants_first_is_recommended() -> None:
    v_high = _balanced_variant().model_copy(update={"score": 80.0})
    v_low = _weak_variant().model_copy(update={"score": 30.0})
    ranked = rank_variants([v_low, v_high])
    assert ranked[0].is_recommended is True
    assert ranked[0].score == 80.0


def test_rank_variants_ordered_by_score() -> None:
    v_a = _balanced_variant().model_copy(update={"score": 65.0})
    v_b = _balanced_variant().model_copy(update={"score": 90.0})
    v_c = _weak_variant().model_copy(update={"score": 25.0})
    ranked = rank_variants([v_a, v_b, v_c])
    scores = [v.score for v in ranked]
    assert scores == sorted(scores, reverse=True)


def test_generate_explanation_contains_score() -> None:
    variant = _balanced_variant()
    text = generate_explanation(variant, 82.5)
    assert "83" in text or "82" in text  # rounding tolerance
