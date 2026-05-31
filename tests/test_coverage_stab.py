"""Phase 2a: STAB-based coverage and STAB-presence invariant on move selection.

Specs: openspec/changes/refine-build-logic-v2/specs/coverage-analysis/spec.md
"""

from __future__ import annotations

import pytest

from pokemon_team_builder.domain.models import BaseStats, PokemonData
from pokemon_team_builder.services import pokemon_lookup
from pokemon_team_builder.services.replica_exporter import (
    select_moves_for_role,
)
from pokemon_team_builder.services.synergy_engine import analyze_coverage


def _mk(
    name: str,
    types: list[str],
    *,
    hp: int = 80,
    atk: int = 80,
    def_: int = 80,
    spa: int = 80,
    spd: int = 80,
    spe: int = 80,
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


# ── STAB-based offensive coverage ────────────────────────────────────────


def test_steelix_without_iron_head_does_not_cover_steel() -> None:
    """Spec scenario: Steelix (Steel/Ground) without a Steel move → Steel not
    counted as covered, despite typing.
    """
    steelix = _mk(
        "steelix",
        ["steel", "ground"],
        hp=75, atk=85, def_=200, spa=55, spd=65, spe=30,
    )
    movesets = [["earthquake", "stealth-rock", "roar", "dragon-tail"]]
    report = analyze_coverage([steelix], movesets=movesets)
    assert "steel" in report.offensive_gaps
    # Sanity: Ground is covered by Earthquake.
    assert "ground" not in report.offensive_gaps


def test_steelix_with_iron_head_covers_steel() -> None:
    """Same Steelix but with Iron Head → Steel IS counted as covered."""
    steelix = _mk(
        "steelix",
        ["steel", "ground"],
        hp=75, atk=85, def_=200, spa=55, spd=65, spe=30,
    )
    movesets = [["iron-head", "earthquake", "stealth-rock", "roar"]]
    report = analyze_coverage([steelix], movesets=movesets)
    assert "steel" not in report.offensive_gaps
    assert "ground" not in report.offensive_gaps


def test_coverage_falls_back_to_typing_when_no_movesets() -> None:
    """Legacy fallback: when no movesets are passed, typing-based coverage
    is used so pre-Phase-2a callers (partial teams in beam search) still
    work without regressions.
    """
    steelix = _mk("steelix", ["steel", "ground"])
    # No movesets → legacy typing-based path.
    report = analyze_coverage([steelix])
    # Steel covered by typing.
    assert "steel" not in report.offensive_gaps
    # Ground covered by typing.
    assert "ground" not in report.offensive_gaps


# ── STAB-presence invariant on move selection ────────────────────────────


def test_garchomp_mono_ground_forced_to_carry_ground_move() -> None:
    """A Ground-only member must carry at least 1 Ground move in slots 1–4
    when the pool offers one.
    """
    # Mono-Ground for the invariant — using mock "garchomp-ground" so we
    # control typing without depending on PokeAPI data.
    mon = _mk(
        "garchomp-ground",
        ["ground"],
        atk=130,
        spa=80,
        spe=102,
        moves=[
            "protect",
            "earthquake",      # Ground STAB
            "dragon-claw",     # non-STAB here (mono Ground)
            "fire-fang",
            "swords-dance",
        ],
    )
    moves = select_moves_for_role(mon, ["physical_sweeper"])
    # Earthquake (Ground STAB) MUST be present.
    assert "earthquake" in moves, (
        f"Mono-Ground member missing Ground STAB: {moves}"
    )


def test_garchomp_dual_type_carries_both_stabs() -> None:
    """Dual-type Garchomp (Ground/Dragon) with Earthquake AND a Dragon move
    available → slot 2 picks one STAB, slot 3 carries the other STAB
    (STAB-presence invariant for both types).
    """
    garchomp = _mk(
        "garchomp",
        ["dragon", "ground"],
        atk=130, spa=80, spe=102,
        moves=[
            "protect",
            "earthquake",      # Ground STAB
            "dragon-claw",     # Dragon STAB
            "fire-fang",       # coverage
            "swords-dance",
        ],
    )
    moves = select_moves_for_role(garchomp, ["physical_sweeper"])
    # Both STABs present in the moveset.
    assert "earthquake" in moves, f"Ground STAB missing: {moves}"
    assert "dragon-claw" in moves, f"Dragon STAB missing: {moves}"


def test_water_only_member_keeps_water_stab() -> None:
    """Mono-Water member with Hydro Pump in pool → Hydro Pump in moveset."""
    milotic = _mk(
        "milotic",
        ["water"],
        spa=100, spd=125, spe=81, hp=95,
        moves=[
            "protect",
            "hydro-pump",  # Water STAB
            "ice-beam",    # coverage
            "recover",
        ],
    )
    moves = select_moves_for_role(milotic, ["special_sweeper"])
    assert "hydro-pump" in moves, f"Water STAB missing on mono-Water: {moves}"


def test_dual_type_with_only_one_stab_available_keeps_it() -> None:
    """If a dual-type member's pool has STAB for only ONE of its types, the
    invariant still holds for the available STAB. The missing type does not
    fail the test — the spec allows it when no STAB move exists for it.
    """
    mon = _mk(
        "lava-dragon",
        ["fire", "dragon"],
        atk=120, spa=80,
        moves=[
            "protect",
            "fire-punch",   # Fire STAB
            "earthquake",   # coverage (not Dragon STAB)
            "rock-slide",   # coverage
            "swords-dance",
        ],
    )
    moves = select_moves_for_role(mon, ["physical_sweeper"])
    # Fire STAB (only STAB available in pool) MUST be present.
    assert "fire-punch" in moves, f"Fire STAB missing: {moves}"


# ── Levitate / Ground immunity for defensive coverage ────────────────────


def test_levitate_member_not_counted_as_ground_weak() -> None:
    """A Levitate member with Ground in its weakness map is still treated as
    Ground-immune by analyze_coverage. With 3 normally-Ground-weak teammates,
    the Levitate mon doesn't tip the team over the 3-member threshold.
    """
    # 3 Ground-weak members (Fire types) + 1 Levitate flying mon that
    # WOULD be ground-weak by weakness map (we synthesize one for the test).
    fire_mon_template = lambda i: _mk(
        f"fire-{i}",
        ["fire"],
        pid=100 + i,
    )
    fire_1 = fire_mon_template(1)
    fire_2 = fire_mon_template(2)
    # Synthetic 4th member: types Rock (weak to Ground 2x) but ability Levitate.
    rock_mon = _mk(
        "rock-floater",
        ["rock"],
        abilities=["levitate"],
        pid=200,
    )
    # Sanity: rock_mon is normally Ground-weak; weaknesses calculator confirms.
    assert rock_mon.weaknesses.get("ground", 1.0) >= 2.0
    # Team-of-3 with all three Ground-weak — should trigger weakness.
    report_no_levitate = analyze_coverage([fire_1, fire_2, rock_mon])
    # Without Levitate handling, 3 Ground-weak members would trigger the
    # defensive_weakness threshold. With Levitate stripping the rock_mon,
    # we drop to 2/3 and "ground" should NOT appear.
    assert "ground" not in report_no_levitate.defensive_weaknesses, (
        f"Levitate should remove Ground weakness from rock-floater; "
        f"report: {report_no_levitate}"
    )


def test_team_with_three_ground_weak_no_levitate_flags_ground() -> None:
    """Control: 3 Ground-weak members WITHOUT Levitate → ground IS recorded."""
    fire_1 = _mk("fire-1", ["fire"], pid=100)
    fire_2 = _mk("fire-2", ["fire"], pid=101)
    fire_3 = _mk("fire-3", ["fire"], pid=102)
    report = analyze_coverage([fire_1, fire_2, fire_3])
    assert "ground" in report.defensive_weaknesses, report


# ── Brief #8 additions: STAB filter + dual-type sacrifice + weather setters ──


def test_non_stab_ice_beam_covers_ice() -> None:
    """VGC-corrected coverage (docs/vgc-principles.md §4, video V4): a
    non-STAB damaging move DOES count toward coverage.

    A mono-Water member carrying Ice Beam makes Ice a covered type, even
    though Ice is not the member's own type — in VGC coverage moves are how
    you threaten what your STABs can't. Ice must NOT appear in
    offensive_gaps. This supersedes the earlier STAB-only rule.
    """
    water_mon = _mk(
        "non-stab-water",
        ["water"],
        moves=["hydro-pump", "ice-beam", "protect", "scald"],
    )
    movesets = [["hydro-pump", "ice-beam", "protect", "scald"]]
    report = analyze_coverage([water_mon], movesets=movesets)
    assert "ice" not in report.offensive_gaps, (
        f"Non-STAB Ice Beam SHOULD cover Ice; "
        f"offensive_gaps={report.offensive_gaps}"
    )
    # Water STAB on Water mon also counts.
    assert "water" not in report.offensive_gaps, report


def test_dual_type_with_two_stabs_may_sacrifice_one() -> None:
    """Spec coverage-analysis: dual-type with 2 STABs in pool may drop one.

    Garchomp (Ground/Dragon) with both Earthquake (Ground STAB) and Dragon
    Claw (Dragon STAB) in pool — select_moves_for_role MAY include both or
    just one when slot pressure exists. Test asserts at least ONE STAB is
    present in the final moveset (the invariant), not both.
    """
    garchomp = _mk(
        "garchomp",
        ["ground", "dragon"],
        atk=130, spe=102,
        moves=[
            "protect",
            "earthquake",       # Ground STAB
            "dragon-claw",      # Dragon STAB
            "stone-edge",       # coverage
            "swords-dance",
        ],
    )
    moves = select_moves_for_role(garchomp, ["physical_sweeper"])
    has_ground_stab = "earthquake" in moves
    has_dragon_stab = "dragon-claw" in moves
    assert has_ground_stab or has_dragon_stab, (
        f"At least one STAB must be present in dual-type set; got {moves}"
    )


def test_weather_setter_drought_gets_lead_support_weight() -> None:
    """Spec role-balance: weather setters receive lead_support >= 0.8.

    A Drought-ability member (e.g. Torkoal-like SpA-heavy mon) should have
    lead_support weight >= 0.8 regardless of its sweeper stats. This is the
    "primary role" guarantee for weather setters.
    """
    from pokemon_team_builder.services.synergy_engine import assign_role_weights
    drought_setter = _mk(
        "drought-setter",
        ["fire"],
        spa=85, spe=20, hp=70, def_=140, spd=90,
        abilities=["drought"],
    )
    assignment = assign_role_weights(drought_setter)
    assert assignment.role_weights.get("lead_support", 0.0) >= 0.8, (
        f"Drought weather setter should have lead_support >= 0.8; "
        f"got {assignment.role_weights}"
    )


def test_tyranitar_sand_stream_lead_support_and_sweeper() -> None:
    """Spec role-balance: Sand Stream Tyranitar gets BOTH lead_support and
    physical_sweeper. lead_support from the weather-setter clause (>=0.8),
    physical_sweeper from raw Atk 134 (full weight, 134 >> 115 threshold).
    """
    from pokemon_team_builder.services.synergy_engine import assign_role_weights
    tyranitar = _mk(
        "tyranitar",
        ["rock", "dark"],
        hp=100, atk=134, def_=110, spa=95, spd=100, spe=61,
        abilities=["sand-stream"],
    )
    assignment = assign_role_weights(tyranitar)
    assert assignment.role_weights.get("lead_support", 0.0) >= 0.8, (
        f"Sand Stream should grant lead_support >= 0.8; "
        f"got {assignment.role_weights}"
    )
    assert assignment.role_weights.get("physical_sweeper", 0.0) == 1.0, (
        f"Atk 134 should give full physical_sweeper weight; "
        f"got {assignment.role_weights}"
    )


def test_non_weather_ability_unaffected_by_weather_clause() -> None:
    """Spec role-balance: non-weather ability does NOT trigger the
    weather-setter lead_support floor. A regular sweeper without weather
    ability is scored purely from stats + ability_implicit_roles.json.
    """
    from pokemon_team_builder.services.synergy_engine import assign_role_weights
    regular = _mk(
        "regular-sweeper",
        ["normal"],
        atk=130, spe=110, hp=80, def_=70, spd=70, spa=60,
        abilities=["adaptability"],  # not a weather ability
    )
    assignment = assign_role_weights(regular)
    # Should not have a forced 0.8 lead_support floor.
    lead_support_weight = assignment.role_weights.get("lead_support", 0.0)
    # Adaptability is not in ability_implicit_roles.json → no bump.
    assert lead_support_weight < 0.8, (
        f"Non-weather ability should not trigger weather-setter floor; "
        f"lead_support={lead_support_weight}"
    )
