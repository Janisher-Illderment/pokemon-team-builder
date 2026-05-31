from __future__ import annotations

from pokemon_team_builder.domain.models import BaseStats, PokemonData
from pokemon_team_builder.services import pokemon_lookup
from pokemon_team_builder.services.synergy_engine import (
    CoverageReport,
    analyze_coverage,
    assign_role,
    derive_doubles_tags,
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
    # Ninetales-A: Snow Warning, SpA 81 (< 100 threshold). Non-offensive AND
    # carries a genuine support move (icy-wind, a speed-control move) → it is a
    # real support, so lead_support stays PRIMARY (ADR §3.1.1 / §7.2).
    #
    # ADR weather-setter-coherence §7.2: the original fixture had NO moves, so
    # under the new "must have a support kit to be promoted to lead" rule it
    # would fall to sweeper. Adding icy-wind reflects the real competitive set
    # (Aurora Veil / Icy Wind / Blizzard / Freeze-Dry) and preserves the test's
    # intent: a genuine support weather-setter leads.
    ninetales_a = _mk(
        "ninetales-alola",
        ["ice", "fairy"],
        hp=73, atk=67, def_=75, spa=81, spd=100, spe=109,
        abilities=["snow-warning"],
        moves=["icy-wind", "blizzard", "freeze-dry", "protect"],
    )
    roles = assign_role(ninetales_a)
    assert roles[0] == "lead_support"


def test_weather_setter_tyranitar_lead_plus_physical() -> None:
    # ADR weather-setter-coherence §5.1: this test previously asserted
    # roles[0] == "lead_support", which CODIFIED the bug — an offensive
    # weather-setter was forced to a support PRIMARY role with no support kit.
    #
    # New decision (ADR §3.1, option c): "setting the weather" is the ability's
    # job, modelled by the C3 `weather_setter` TAG, not a mechanical support
    # role. Tyranitar (Atk 134, no support move) is a physical_sweeper PRIMARY;
    # it does NOT get lead_support (no support kit, and it is offensive anyway).
    # Its weather identity is verified via the derive_doubles_tags tag.
    tyranitar = _mk(
        "tyranitar",
        ["rock", "dark"],
        hp=100, atk=134, def_=110, spa=95, spd=100, spe=61,
        abilities=["sand-stream"],
    )
    roles = assign_role(tyranitar)
    assert roles[0] == "physical_sweeper"
    assert "lead_support" not in roles
    # The weather-setter character is now a tag, not a role.
    assert "weather_setter" in derive_doubles_tags(tyranitar)


def test_abomasnow_offensive_setter_not_lead_support() -> None:
    """ADR §3.1.1 / §5.3.1: Abomasnow (Snow Warning, atk 92 / spa 92) has no
    support move and no offensive presence (both < 100 threshold). It must NOT
    be lead_support primary — it falls to the dominant-stat sweeper, and its
    "set the weather" identity is the C3 weather_setter TAG.

    This is the reported bug: a weather-setter with a special coverage move
    (Ice Beam) was shipped as lead_support with an incoherent physical spread.
    """
    abomasnow = _mk(
        "abomasnow",
        ["grass", "ice"],
        hp=90, atk=92, def_=75, spa=92, spd=85, spe=60,
        abilities=["snow-warning"],
        moves=["protect", "blizzard", "energy-ball", "ice-beam"],
    )
    roles = assign_role(abomasnow)
    assert roles[0] in ("physical_sweeper", "special_sweeper")
    assert "lead_support" not in roles
    assert "weather_setter" in derive_doubles_tags(abomasnow)


def test_abomasnow_offensive_setter_not_lead_support_even_with_support_in_set() -> None:
    """ADR move-category-coherence §5.2: reinforces the test above by closing
    the actual runtime grietas. The OLD test passed only because its fixture
    OMITTED icy-wind — but the real build starts from the full learnset (which
    DOES include icy-wind, confirmed via PokeAPI), so _has_support_kit was True
    in runtime and lead_support reappeared.

    With (2a) "offensive by inclination", Abomasnow (max(92,92)=92 >=
    max(75,85)=85 → offensive-leaning) is NOT promoted to lead_support PRIMARY
    EVEN WHEN a support move (icy-wind) is present in the set. This codifies
    that a learnset-with-support no longer resurrects the bug.
    """
    abomasnow = _mk(
        "abomasnow",
        ["grass", "ice"],
        hp=90, atk=92, def_=75, spa=92, spd=85, spe=60,
        abilities=["snow-warning"],
        moves=["protect", "icicle-crash", "wood-hammer", "icy-wind"],
    )
    roles = assign_role(abomasnow)
    assert roles[0] != "lead_support", (
        f"offensive-leaning setter must not be lead primary even with a "
        f"support move in set; got {roles}"
    )
    assert "weather_setter" in derive_doubles_tags(abomasnow)


def test_setter_with_support_move_keeps_lead() -> None:
    """ADR §5.3.6: a NON-offensive weather setter WITH a real support move
    (Pelipper + tailwind) keeps lead_support primary. The fix must not break
    genuine support setters.
    """
    pelipper = _mk(
        "pelipper",
        ["water", "flying"],
        hp=60, atk=50, def_=100, spa=95, spd=70, spe=65,
        abilities=["drizzle"],
        moves=["protect", "hurricane", "scald", "tailwind"],
    )
    roles = assign_role(pelipper)
    assert roles[0] == "lead_support"
    assert "weather_setter" in derive_doubles_tags(pelipper)


def test_offensive_setter_with_support_is_sweeper_primary_lead_secondary() -> None:
    """ADR §3.1: an OFFENSIVE setter (sweeper weight >= 0.5) that also carries a
    support move keeps the sweeper as PRIMARY; lead_support may trail as a
    secondary role.
    """
    # atk 130 >= 100 → physical_sweeper weight >= 0.5; tailwind + spe>=90 makes
    # it a genuine support too.
    mon = _mk(
        "landorus-ish",
        ["ground", "flying"],
        hp=89, atk=130, def_=80, spa=80, spd=80, spe=101,
        abilities=["sand-stream"],
        moves=["protect", "earthquake", "rock-slide", "icy-wind"],
    )
    roles = assign_role(mon)
    assert roles[0] == "physical_sweeper"
    assert "lead_support" in roles  # secondary, via the support move


def test_offensive_lean_boundary_synergy() -> None:
    """ADR move-category-coherence §5.3.5: the (2a) offensive-inclination
    clause classifies a weather setter as offensive when its best attacking
    stat >= its best defensive stat, gating it out of lead_support PRIMARY.

    - Abomasnow (92/92 vs 75/85): max(92,92)=92 >= max(75,85)=85 → offensive
      → NOT lead primary (its set has icy-wind in learnset, which previously
      promoted it).
    - Pelipper (50/95 vs 100/70): max(50,95)=95 >= max(100,70)=100 → False
      → still eligible for genuine support lead.
    - A pure wall (60/60 vs 120/120) → max(60,60)=60 >= max(120,120)=120
      → False → not offensive (guards against over-promotion of the clause).
    """
    abomasnow = _mk(
        "abomasnow", ["grass", "ice"],
        hp=90, atk=92, def_=75, spa=92, spd=85, spe=60,
        abilities=["snow-warning"],
        moves=["protect", "icy-wind", "blizzard", "energy-ball"],
    )
    assert assign_role(abomasnow)[0] != "lead_support"

    pelipper = _mk(
        "pelipper", ["water", "flying"],
        hp=60, atk=50, def_=100, spa=95, spd=70, spe=65,
        abilities=["drizzle"],
        moves=["protect", "hurricane", "scald", "tailwind"],
    )
    # Pelipper is NOT offensive-leaning → genuine support lead survives.
    assert assign_role(pelipper)[0] == "lead_support"

    wall_setter = _mk(
        "wall-setter", ["water"],
        hp=100, atk=60, def_=120, spa=60, spd=120, spe=40,
        abilities=["drizzle"],
        moves=["protect", "scald", "icy-wind", "recover"],
    )
    # Defensive wall that sets weather and supports → still a genuine lead.
    assert assign_role(wall_setter)[0] == "lead_support"


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
    # Ninetales-A: snow-cloak primary, snow-warning idx 1, but species in
    # whitelist → recognised as a weather setter. With a genuine support move
    # (icy-wind) and no offensive presence it stays lead_support PRIMARY.
    # ADR §7.2: moves added to the fixture so the support-kit gate (§3.1.1)
    # keeps the intended lead behaviour (was move-less before).
    p = _mk(
        "ninetales-alola",
        ["ice", "fairy"],
        hp=73, atk=67, def_=75, spa=81, spd=100, spe=109,
        abilities=["snow-cloak", "snow-warning"],
        moves=["icy-wind", "blizzard", "freeze-dry", "protect"],
    )
    roles = assign_role(p)
    assert roles[0] == "lead_support"
