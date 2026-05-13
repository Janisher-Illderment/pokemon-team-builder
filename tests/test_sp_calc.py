"""Tests for the Champions 66-SP stat calculator.

These tests pin the canonical Gen 9 stat formula adapted to Champions's
66-SP system (1 SP = 8 legacy EVs). They are the foundation for the
SP preset builder added later; correctness here is load-bearing.
"""

from __future__ import annotations

import pytest

from pokemon_team_builder.services import sp_calc


# ---------------------------------------------------------------------------
# Canonical anchor: Garchomp
# Atk base 130, Adamant (+Atk = 1.1), IVs 31, Level 50, SP=32 (= 252 EVs).
# Expected final Atk = 200. This is the most-cited reference in Champions
# math guides — if this fails, the formula is wrong.
# ---------------------------------------------------------------------------


def test_garchomp_atk_max_sp_plus_nature_equals_200() -> None:
    assert sp_calc.final_stat(130, 32, nature_mult=1.1) == 200


def test_garchomp_atk_zero_sp_neutral_nature() -> None:
    # (2*130 + 31 + 0)*50/100 + 5 = floor(14550/100) + 5 = 145 + 5 = 150
    assert sp_calc.final_stat(130, 0, nature_mult=1.0) == 150


def test_garchomp_atk_negative_nature() -> None:
    # SP=32, 0.9x nature. floor((355*50/100 + 5) * 0.9) = floor(182*0.9) = 163
    assert sp_calc.final_stat(130, 32, nature_mult=0.9) == 163


# ---------------------------------------------------------------------------
# HP formula uses a different shape (no nature mult, +level +10).
# ---------------------------------------------------------------------------


def test_garchomp_hp_zero_sp() -> None:
    # base 108, SP=0 → (2*108 + 31)*50/100 + 50 + 10 = 247*50//100 + 60
    # = 12350//100 + 60 = 123 + 60 = 183
    assert sp_calc.final_hp_stat(108, 0) == 183


def test_garchomp_hp_max_sp() -> None:
    # base 108, SP=32 → (2*108 + 31 + 64)*50/100 + 50 + 10
    # = 311*50//100 + 60 = 15550//100 + 60 = 155 + 60 = 215
    assert sp_calc.final_hp_stat(108, 32) == 215


def test_hp_helper_does_not_apply_nature_path() -> None:
    # Regression guard: ensure HP path stays separate from the nature-aware
    # final_stat path. If someone refactored HP via final_stat(...,
    # nature_mult=1.1) by mistake, the value would change. HP must not be
    # nature-scaled — that path produces a structurally different number.
    hp_value = sp_calc.final_hp_stat(100, 32)
    nature_scaled_non_hp = sp_calc.final_stat(100, 32, nature_mult=1.1)
    assert hp_value != nature_scaled_non_hp, (
        "HP helper output coincides with nature-scaled non-HP path — "
        "this suggests HP is being computed via the wrong formula."
    )


# ---------------------------------------------------------------------------
# Nature jumps detection.
# At certain (base, sp, nature) tuples, +1 SP yields +2 final stat due to
# rounding through the multiplier. The detector returns the SP values
# where the jump occurs.
# ---------------------------------------------------------------------------


def test_find_nature_jumps_on_common_speed_base() -> None:
    # Garchomp Spe base 102, Jolly (+Spe = 1.1) has multiple jump points
    # — exact set verified empirically: 8, 18, 28.
    jumps = sp_calc.find_nature_jumps(102, 1.1)
    assert jumps == [8, 18, 28]


def test_find_nature_jumps_neutral_nature_returns_empty() -> None:
    # 1.0x nature can never produce a 2-point jump from a 1-SP delta —
    # the SP→stat function is monotonic in steps of 0 or 1.
    jumps = sp_calc.find_nature_jumps(100, 1.0)
    assert jumps == []


def test_find_nature_jumps_negative_max_sp_returns_empty() -> None:
    assert sp_calc.find_nature_jumps(100, 1.1, max_sp=0) == []


# ---------------------------------------------------------------------------
# optimal_sp_for_target — minimum SP to reach a target stat.
# ---------------------------------------------------------------------------


def test_optimal_sp_for_target_reaches_garchomp_200_atk() -> None:
    # 200 attack on base 130 +nature requires exactly 32 SPs (max).
    assert sp_calc.optimal_sp_for_target(130, 200, 1.1) == 32


def test_optimal_sp_for_target_returns_zero_when_already_met() -> None:
    # 150 attack on base 130, neutral nature, is met at SP=0.
    assert sp_calc.optimal_sp_for_target(130, 150, 1.0) == 0


def test_optimal_sp_for_target_returns_minus_one_when_unreachable() -> None:
    # Asking for 500 atk on a base-130 mon is impossible — the function
    # signals "no spread reaches this" with -1 so the caller can decide
    # whether to relax IVs, nature, or accept.
    assert sp_calc.optimal_sp_for_target(130, 500, 1.1) == -1


# ---------------------------------------------------------------------------
# Input validation.
# ---------------------------------------------------------------------------


def test_negative_sp_raises_in_final_stat() -> None:
    with pytest.raises(ValueError):
        sp_calc.final_stat(100, -1)


def test_negative_sp_raises_in_final_hp_stat() -> None:
    with pytest.raises(ValueError):
        sp_calc.final_hp_stat(100, -1)


# ---------------------------------------------------------------------------
# Constants — exposed as module-level Final values; pinned so downstream
# code referencing them doesn't drift if someone "tunes" the cap.
# ---------------------------------------------------------------------------


def test_constants_pinned() -> None:
    assert sp_calc.SP_TOTAL_CAP == 66
    assert sp_calc.SP_PER_STAT_CAP == 32
    assert sp_calc.SP_TO_EV_RATIO == 8
    assert sp_calc.IV_DEFAULT == 31
    assert sp_calc.LEVEL_DEFAULT == 50
    assert sp_calc.SP_MECHANICS_VERSION == 1
    assert sp_calc.REGULATION == "M-A"
