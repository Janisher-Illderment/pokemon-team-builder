"""Phase 3 §10 — speed-control-required penalty + flag tests."""

from __future__ import annotations

import pytest

from pokemon_team_builder.domain.models import (
    BaseStats,
    PokemonData,
    SPDistribution,
    TeamMember,
    TeamVariant,
)
from pokemon_team_builder.services.viability_rater import (
    _speed_control_penalty,
    _count_speed_control,
    score_team,
    variant_requires_speed_control,
)


def _mk(
    name: str,
    *,
    ability: str = "pressure",
    moves: list[str] | None = None,
) -> TeamMember:
    pokemon = PokemonData(
        id=1,
        name=name,
        types=["normal"],
        base_stats=BaseStats(hp=90, atk=90, **{"def": 80}, spa=85, spd=80, spe=90),
        move_names=moves or ["tackle"],
        abilities=[ability],
        weaknesses={},
    )
    return TeamMember(
        pokemon=pokemon,
        role=["physical_sweeper"],
        sp_distribution=SPDistribution(),
        item="Leftovers",
        ability=ability,
        nature="Hardy",
        moves=moves or ["tackle", "growl", "scratch", "ember"],
    )


def _fill(members: list[TeamMember]) -> list[TeamMember]:
    while len(members) < 6:
        members.append(_mk(f"filler{len(members)}"))
    return members


# ── Penalty function ──────────────────────────────────────────────────────────

def test_no_speed_control_balance_penalised():
    members = _fill([_mk("mon1"), _mk("mon2")])
    variant = TeamVariant(members=members)
    assert _speed_control_penalty(variant, "balance") == pytest.approx(-15.0)
    assert variant_requires_speed_control(variant, "balance") is True


def test_tailwind_member_passes():
    members = _fill([
        _mk("talonflame", moves=["protect", "brave-bird", "tailwind", "u-turn"]),
    ])
    variant = TeamVariant(members=members)
    assert _speed_control_penalty(variant, "balance") == pytest.approx(0.0)
    assert variant_requires_speed_control(variant, "balance") is False


def test_trick_room_member_passes():
    members = _fill([
        _mk("dusclops", moves=["protect", "shadow-ball", "trick-room", "will-o-wisp"]),
    ])
    variant = TeamVariant(members=members)
    assert _speed_control_penalty(variant, "balance") == pytest.approx(0.0)


def test_stall_archetype_exempt():
    members = _fill([_mk("mon1"), _mk("mon2")])
    variant = TeamVariant(members=members)
    assert _speed_control_penalty(variant, "stall") == pytest.approx(0.0)
    assert variant_requires_speed_control(variant, "stall") is False


def test_two_static_members_count_as_one_mechanism():
    """Static + Static = 0.5 + 0.5 = 1.0 → no penalty."""
    members = _fill([
        _mk("electabuzz", ability="static"),
        _mk("jolteon", ability="static"),
    ])
    variant = TeamVariant(members=members)
    assert _count_speed_control(members) == pytest.approx(1.0)
    assert _speed_control_penalty(variant, "balance") == pytest.approx(0.0)


def test_single_static_member_insufficient():
    """One Static = 0.5 < 1.0 → penalty applies."""
    members = _fill([_mk("pikachu", ability="static")])
    variant = TeamVariant(members=members)
    assert _count_speed_control(members) == pytest.approx(0.5)
    assert _speed_control_penalty(variant, "balance") == pytest.approx(-15.0)


def test_icy_wind_passes():
    members = _fill([
        _mk("walrein", moves=["protect", "ice-beam", "icy-wind", "surf"]),
    ])
    variant = TeamVariant(members=members)
    assert _speed_control_penalty(variant, "balance") == pytest.approx(0.0)


def test_fake_out_passes():
    members = _fill([
        _mk("incineroar", moves=["protect", "flare-blitz", "fake-out", "u-turn"]),
    ])
    variant = TeamVariant(members=members)
    assert _speed_control_penalty(variant, "balance") == pytest.approx(0.0)


# ── score_team integration ────────────────────────────────────────────────────

def test_score_team_penalty_propagates_in_bo1():
    """Balance team with no speed control loses 15 points vs same with Tailwind."""
    no_sc = _fill([_mk("alakazam"), _mk("dragonite")])
    with_sc = _fill([
        _mk("talonflame", moves=["protect", "brave-bird", "tailwind", "u-turn"]),
        _mk("alakazam"),
    ])
    v_no = TeamVariant(members=no_sc)
    v_with = TeamVariant(members=with_sc)
    score_no, _ = score_team(v_no, "bo1", archetype="balance")
    score_with, _ = score_team(v_with, "bo1", archetype="balance")
    # Difference dominated by the -15 penalty on v_no.
    assert score_with > score_no


def test_score_team_no_penalty_in_bo3_with_tailwind():
    """Bo3 + Tailwind → no speed control penalty triggered."""
    members = _fill([
        _mk("talonflame", moves=["protect", "brave-bird", "tailwind", "u-turn"]),
    ])
    variant = TeamVariant(members=members)
    assert _speed_control_penalty(variant, "balance") == pytest.approx(0.0)
    # Smoke: score_team runs without error in Bo3.
    score, ratio = score_team(variant, "bo3", archetype="balance")
    assert 0.0 <= score <= 100.0
    assert 0.0 <= ratio <= 1.0
