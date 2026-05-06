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


def test_assign_role_mixed_stat_dominant() -> None:
    """T2: when both Atk and SpA >=100, the dominant stat drives primary role.

    Hydreigon (Atk 105, SpA 125) should resolve to special_sweeper as
    the primary role, since SpA is clearly higher. The earlier rule
    appended physical_sweeper unconditionally first, locking the build
    pipeline into Jolly + physical EVs even on a special attacker.
    """
    p = _mk(
        "hydreigon",
        ["dark", "dragon"],
        atk=105,
        spa=125,
        spe=98,
        moves=["draco-meteor", "dark-pulse", "fire-blast"],
    )
    roles = assign_role(p)
    # Both roles still appear (it has 100+ in each), but the dominant
    # one comes first — that's the one the team builder uses as primary.
    assert roles[0] == "special_sweeper", roles
    assert "physical_sweeper" in roles


def test_assign_role_mixed_stat_dominant_physical() -> None:
    """T2 inverse: a 130 Atk / 110 SpA mon resolves to physical_sweeper first."""
    p = _mk(
        "salamence-mixed",
        ["dragon", "flying"],
        atk=130,
        spa=110,
        spe=100,
        moves=["dragon-claw", "earthquake", "fire-blast"],
    )
    roles = assign_role(p)
    assert roles[0] == "physical_sweeper", roles
    assert "special_sweeper" in roles


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


def test_weather_setter_gets_lead_support_primary() -> None:
    # Ninetales-A: Snow Warning, SpA 81 (< 100 threshold) → lead_support only
    # (no sweeper role since neither offensive stat reaches 100)
    ninetales_a = _mk(
        "ninetales-alola",
        ["ice", "fairy"],
        hp=73, atk=67, def_=75, spa=81, spd=100, spe=109,
        abilities=["snow-warning"],
    )
    roles = assign_role(ninetales_a)
    assert roles[0] == "lead_support"


def test_weather_setter_tyranitar_lead_plus_physical() -> None:
    # Tyranitar: Sand Stream, Atk 134 >= 100 → lead_support first, physical_sweeper second
    tyranitar = _mk(
        "tyranitar",
        ["rock", "dark"],
        hp=100, atk=134, def_=110, spa=95, spd=100, spe=61,
        abilities=["sand-stream"],
    )
    roles = assign_role(tyranitar)
    assert roles[0] == "lead_support"
    assert "physical_sweeper" in roles


def test_non_weather_ability_unaffected() -> None:
    # Intimidate is not a weather ability → no lead_support injected by weather rule
    arcanine = _mk(
        "arcanine",
        ["fire"],
        hp=90, atk=110, def_=80, spa=100, spd=80, spe=95,
        abilities=["intimidate"],
        moves=["tackle"],
    )
    roles = assign_role(arcanine)
    assert roles[0] != "lead_support" or "tailwind" in arcanine.move_names


def test_prankster_primary_is_lead() -> None:
    # Whimsicott: prankster at abilities[0] → roles[0] == lead_support
    p = _mk("whimsicott", ["grass", "fairy"], spe=116, abilities=["prankster"])
    roles = assign_role(p)
    assert roles[0] == "lead_support"


def test_prankster_hidden_not_lead() -> None:
    # Prankster at index 2 (hidden ability) must NOT trigger lead_support via ability rule
    p = _mk(
        "meowstic",
        ["psychic"],
        spe=104,
        abilities=["keen-eye", "infiltrator", "prankster"],
    )
    roles = assign_role(p)
    # lead_support must not be roles[0] unless a move also triggers it
    # (no moves given here, so the ability rule is the only possible trigger)
    assert roles[0] != "lead_support"


def test_fake_out_slow_mon_is_lead() -> None:
    # Incineroar: spe=60, fake-out in pool → lead_support (no speed gate for priority)
    p = _mk(
        "incineroar",
        ["fire", "dark"],
        hp=95, atk=115, def_=90, spa=80, spd=90, spe=60,
        moves=["fake-out", "protect", "flare-blitz", "knock-off"],
    )
    roles = assign_role(p)
    assert "lead_support" in roles


def test_tailwind_slow_not_lead() -> None:
    # spe=50, only tailwind — must NOT get lead_support (speed gate applies to tailwind)
    p = _mk("bronzong", ["steel", "psychic"], spe=33, moves=["tailwind", "gyro-ball"])
    roles = assign_role(p)
    assert "lead_support" not in roles


def test_aurorus_not_weather_setter() -> None:
    # Aurorus: abilities[0]=refrigerate, snow-warning at idx 1, NOT in whitelist
    # → no lead_support injected by weather/ability rule
    p = _mk(
        "aurorus",
        ["rock", "ice"],
        hp=123, atk=77, def_=72, spa=99, spd=92, spe=58,
        abilities=["refrigerate", "snow-warning"],
    )
    roles = assign_role(p)
    assert "lead_support" not in roles


def test_ninetales_alola_whitelist_lead() -> None:
    # Ninetales-A: snow-cloak primary, snow-warning idx 1, but species in whitelist
    p = _mk(
        "ninetales-alola",
        ["ice", "fairy"],
        hp=73, atk=67, def_=75, spa=81, spd=100, spe=109,
        abilities=["snow-cloak", "snow-warning"],
    )
    roles = assign_role(p)
    assert roles[0] == "lead_support"
