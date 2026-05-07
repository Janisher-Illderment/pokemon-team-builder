from __future__ import annotations

import pytest
from pokemon_team_builder.domain.models import (
    BaseStats, PokemonData, SPDistribution, TeamMember, TeamVariant,
)
from pokemon_team_builder.services.viability_rater import (
    _lead_flexibility_points,
    _core_diversity_points,
    score_team,
)


def _make_member(
    name: str,
    roles: list[str],
    moves: list[str] | None = None,
    base_spe: int = 100,
) -> TeamMember:
    pokemon = PokemonData(
        id=1,
        name=name,
        types=["normal"],
        base_stats=BaseStats(hp=90, atk=90, **{"def": 80}, spa=85, spd=80, spe=base_spe),
        move_names=moves or ["tackle"],
        abilities=["run-away"],
        weaknesses={"fighting": 2.0},
    )
    sp = SPDistribution(hp=0, atk=0, **{"def": 0}, spa=0, spd=0, spe=0)
    return TeamMember(
        pokemon=pokemon,
        role=roles,
        sp_distribution=sp,
        item="leftovers",
        ability="run-away",
        nature="hardy",
        moves=moves or ["tackle", "growl", "scratch", "ember"],
    )


def _make_variant(members: list[TeamMember]) -> TeamVariant:
    return TeamVariant(members=members)


def _six_members(overrides: dict[int, TeamMember] | None = None) -> list[TeamMember]:
    base = [
        _make_member(f"mon{i}", ["physical_sweeper"]) for i in range(6)
    ]
    if overrides:
        for idx, member in overrides.items():
            base[idx] = member
    return base


# ── lead flexibility ──────────────────────────────────────────────────────────

def test_lead_flexibility_all_speed_control():
    members = [
        _make_member(f"mon{i}", ["lead_support"], moves=["tailwind", "tackle", "growl", "roost"])
        for i in range(6)
    ]
    ratio, pts = _lead_flexibility_points(members)
    assert ratio == pytest.approx(1.0)
    assert pts == pytest.approx(25.0)


def test_lead_flexibility_none_viable():
    members = [
        _make_member(f"mon{i}", ["physical_sweeper"], moves=["tackle", "scratch", "growl", "ember"])
        for i in range(6)
    ]
    ratio, pts = _lead_flexibility_points(members)
    assert ratio == pytest.approx(0.0)
    assert pts == pytest.approx(0.0)


def test_lead_flexibility_single_viable_member():
    members = _six_members({
        0: _make_member("supporter", ["lead_support"], moves=["fake-out", "tackle", "growl", "roost"])
    })
    ratio, pts = _lead_flexibility_points(members)
    # C(5,3)/C(6,4) = 10/15 combos include the viable member
    assert ratio == pytest.approx(10 / 15)


# ── core diversity ────────────────────────────────────────────────────────────

def test_core_diversity_three_pairs():
    members = [
        _make_member("sweeper1", ["physical_sweeper"]),
        _make_member("sweeper2", ["special_sweeper"]),
        _make_member("sweeper3", ["physical_sweeper"]),
        _make_member("support1", ["lead_support"]),
        _make_member("support2", ["redirect"]),
        _make_member("support3", ["trick_room_setter"]),
    ]
    pts = _core_diversity_points(members)
    # 3 sweepers × 3 supports = 9 pairs; min(9/3,1)*15 = 15
    assert pts == pytest.approx(15.0)


def test_core_diversity_no_supports():
    members = [_make_member(f"s{i}", ["physical_sweeper"]) for i in range(6)]
    assert _core_diversity_points(members) == pytest.approx(0.0)


def test_core_diversity_single_pair():
    # 1 sweeper + 1 support, rest are walls (neither role)
    members = [
        _make_member("sweeper", ["physical_sweeper"]),
        _make_member("support", ["lead_support"]),
        _make_member("wall1", ["physical_wall"]),
        _make_member("wall2", ["physical_wall"]),
        _make_member("wall3", ["special_wall"]),
        _make_member("wall4", ["special_wall"]),
    ]
    pts = _core_diversity_points(members)
    # 1 pair; min(1/3,1)*15 = 5
    assert pts == pytest.approx(15 / 3)


# ── score_team Bo3 formula ────────────────────────────────────────────────────

def test_bo3_score_at_most_100():
    members = [
        _make_member(f"mon{i}", ["physical_sweeper", "lead_support"],
                     moves=["tailwind", "fake-out", "tackle", "roost"])
        for i in range(6)
    ]
    variant = _make_variant(members)
    score, flex_ratio = score_team(variant, "bo3")
    assert 0.0 <= score <= 100.0


def test_bo3_flex_ratio_matches_points():
    members = [
        _make_member(f"mon{i}", ["lead_support"],
                     moves=["tailwind", "tackle", "growl", "roost"])
        for i in range(6)
    ]
    variant = _make_variant(members)
    score, flex_ratio = score_team(variant, "bo3")
    assert flex_ratio == pytest.approx(1.0)


def test_bo1_score_unchanged_by_format_param():
    members = _six_members()
    variant = _make_variant(members)
    score_default, _ = score_team(variant)
    score_bo1, _ = score_team(variant, "bo1")
    assert score_default == pytest.approx(score_bo1)


def test_bo1_flex_ratio_always_zero():
    members = _six_members()
    variant = _make_variant(members)
    _, flex_ratio = score_team(variant, "bo1")
    assert flex_ratio == pytest.approx(0.0)


# ── cheese moves not in Bo3 ───────────────────────────────────────────────────

def _sableye() -> "PokemonData":
    from pokemon_team_builder.domain.models import PokemonData, BaseStats
    # shadow-ball covers slot2 (ghost STAB), earthquake slot3 (coverage),
    # no tailwind/fake-out etc. so slot4 falls back to destiny-bond.
    return PokemonData(
        id=1, name="sableye",
        types=["dark", "ghost"],
        base_stats=BaseStats(hp=50, atk=75, **{"def": 75}, spa=65, spd=65, spe=50),
        move_names=["protect", "shadow-ball", "earthquake", "destiny-bond"],
        abilities=["prankster"],
        weaknesses={"fairy": 2.0},
    )


def test_destiny_bond_absent_in_bo3():
    from pokemon_team_builder.services.replica_exporter import select_moves_for_role
    moves_bo3 = select_moves_for_role(_sableye(), ["lead_support"], format_mode="bo3")
    assert "destiny-bond" not in moves_bo3


def test_destiny_bond_present_in_bo1():
    from pokemon_team_builder.services.replica_exporter import select_moves_for_role
    moves_bo1 = select_moves_for_role(_sableye(), ["lead_support"], format_mode="bo1")
    assert "destiny-bond" in moves_bo1
