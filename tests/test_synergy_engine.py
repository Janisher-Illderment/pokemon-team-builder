from __future__ import annotations

from pokemon_team_builder.domain.models import BaseStats, PokemonData
from pokemon_team_builder.services import pokemon_lookup
from pokemon_team_builder.services.synergy_engine import (
    CoverageReport,
    analyze_coverage,
    assign_role,
    detect_role_gaps,
    score_flexibility,
)


def _mk(
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
    abilities: list[str] | None = None,
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
        abilities=abilities or [],
        weaknesses=pokemon_lookup.calculate_weaknesses(types),
    )


def test_assign_role_physical_sweeper() -> None:
    p = _mk("garchomp", ["dragon", "ground"], atk=130, spa=80, spe=102)
    roles = assign_role(p)
    assert "physical_sweeper" in roles


def test_assign_role_lead_with_tailwind() -> None:
    p = _mk(
        "talonflame",
        ["fire", "flying"],
        atk=81,
        spe=126,
        moves=["tailwind", "brave-bird"],
    )
    roles = assign_role(p)
    assert "lead_support" in roles


def test_assign_role_trick_room_setter() -> None:
    p = _mk(
        "hatterene",
        ["psychic", "fairy"],
        hp=57,
        atk=90,
        spa=114,
        spe=29,
        moves=["trick-room", "psychic"],
    )
    roles = assign_role(p)
    assert "trick_room_setter" in roles


def test_assign_role_fallback() -> None:
    # No rule fires (atk=60, spa=70 — under 100; no support moves; spe>60).
    # spa > atk → special_sweeper fallback.
    p = _mk("nobody", ["normal"], atk=60, spa=70, spe=70, moves=["tackle"])
    roles = assign_role(p)
    assert roles == ["special_sweeper"]


def test_assign_role_redirect() -> None:
    p = _mk(
        "amoonguss",
        ["grass", "poison"],
        hp=114,
        spa=85,
        spe=30,
        moves=["rage-powder", "spore"],
    )
    roles = assign_role(p)
    assert "redirect" in roles


def test_analyze_coverage_empty_team() -> None:
    report = analyze_coverage([])
    assert isinstance(report, CoverageReport)
    assert report.offensive_gaps == []
    assert report.defensive_weaknesses == []


def test_analyze_coverage_no_water_type_in_team() -> None:
    team = [
        _mk("charizard", ["fire", "flying"]),
        _mk("garchomp", ["dragon", "ground"]),
        _mk("dragonite", ["dragon", "flying"]),
    ]
    report = analyze_coverage(team)
    assert "water" in report.offensive_gaps


def test_analyze_coverage_critical_electric_weakness() -> None:
    # 4 members weak to electric → defensive_weakness.
    # water/flying types take 2x from electric.
    team = [
        _mk("gyarados", ["water", "flying"]),
        _mk("pelipper", ["water", "flying"]),
        _mk("mantine", ["water", "flying"]),
        _mk("wingull", ["water", "flying"]),
        _mk("charizard", ["fire", "flying"]),
        _mk("garchomp", ["dragon", "ground"]),
    ]
    report = analyze_coverage(team)
    assert "electric" in report.defensive_weaknesses


def test_detect_role_gaps_no_support() -> None:
    team = [
        _mk("garchomp", ["dragon", "ground"], atk=130, spe=102),
        _mk("dragonite", ["dragon", "flying"], atk=134, spe=80),
        _mk("tyranitar", ["rock", "dark"], atk=134, spe=61),
        _mk("metagross", ["steel", "psychic"], atk=135, spe=70),
        _mk("salamence", ["dragon", "flying"], atk=135, spe=100),
        _mk("haxorus", ["dragon"], atk=147, spe=97),
    ]
    gaps = detect_role_gaps(team)
    assert "lead_support" in gaps


def test_detect_role_gaps_balanced() -> None:
    team = [
        _mk("garchomp", ["dragon", "ground"], atk=130, spe=102),
        _mk(
            "talonflame",
            ["fire", "flying"],
            atk=81,
            spe=126,
            moves=["tailwind"],
        ),
        _mk("dragonite", ["dragon", "flying"], atk=134, spe=80),
        _mk("tyranitar", ["rock", "dark"], atk=134, spe=61),
        _mk("metagross", ["steel", "psychic"], atk=135, spe=70),
        _mk("salamence", ["dragon", "flying"], atk=135, spe=100),
    ]
    gaps = detect_role_gaps(team)
    assert "lead_support" not in gaps
    assert "sweeper" not in gaps


def test_score_flexibility() -> None:
    team = [
        _mk("garchomp", ["dragon", "ground"], atk=130, spe=102),
        _mk(
            "talonflame",
            ["fire", "flying"],
            atk=81,
            spe=126,
            moves=["tailwind"],
        ),
        _mk("dragonite", ["dragon", "flying"], atk=134, spe=80),
        _mk(
            "amoonguss",
            ["grass", "poison"],
            hp=114,
            spa=85,
            spe=30,
            moves=["rage-powder"],
        ),
        _mk("metagross", ["steel", "psychic"], atk=135, spe=70),
        _mk("salamence", ["dragon", "flying"], atk=135, spe=100),
    ]
    score = score_flexibility(team)
    assert isinstance(score, int)
    assert 0 <= score <= 15
