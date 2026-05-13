"""Champions 66-SP stat calculator and nature-jump detector.

Champions uses the canonical Gen 9 stat formula but allocates 66 Stat Points
total per Pokemon (max 32 per stat), where 1 SP = 8 legacy EVs. The formula
collapses to:

    final_stat = floor((floor((2*base + iv + floor(8*sp/4)) * level / 100) + 5)
                       * nature_mult)

For HP the formula differs (no nature multiplier, +level +10 instead of +5):

    final_hp = floor((2*base + iv + floor(8*sp/4)) * level / 100) + level + 10

Note: ``8*sp/4`` is ``sp*2`` algebraically, but we keep the explicit form so
the lineage to the legacy EV system (EVs = 8*SP) stays visible.

This module is **pure math** — no Pokemon data, no team logic. It is the
foundation for the SP preset builder added later in the refactor.
"""

from __future__ import annotations

from typing import Final

REGULATION: Final[str] = "M-A"
SP_MECHANICS_VERSION: Final[int] = 1

# Champions SP system constants.
SP_TOTAL_CAP: Final[int] = 66      # total SPs available per Pokemon
SP_PER_STAT_CAP: Final[int] = 32   # max SPs in any one stat
SP_TO_EV_RATIO: Final[int] = 8     # 1 SP = 8 legacy EVs

# Defaults aligned with Champions Reg M-A: every mon at level 50, IVs 31.
IV_DEFAULT: Final[int] = 31
LEVEL_DEFAULT: Final[int] = 50


def _ev_from_sp(sp: int) -> int:
    """Convert SP to legacy EV equivalent (``sp * 8``)."""
    return sp * SP_TO_EV_RATIO


def final_stat(
    base: int,
    sp: int,
    iv: int = IV_DEFAULT,
    level: int = LEVEL_DEFAULT,
    nature_mult: float = 1.0,
) -> int:
    """Compute the final value of a non-HP stat.

    Formula:
        floor((floor((2*base + iv + floor(ev/4)) * level / 100) + 5) * nature_mult)
    where ``ev = sp * 8``.

    Args:
        base: Pokemon's base stat (e.g. Garchomp Atk = 130).
        sp: Stat Points invested (0..SP_PER_STAT_CAP).
        iv: Individual Value, default 31.
        level: Pokemon level, default 50.
        nature_mult: Nature multiplier for this stat (0.9, 1.0, or 1.1).

    Returns:
        Integer final stat value after all rounding and nature.
    """
    if sp < 0:
        raise ValueError(f"sp must be >= 0, got {sp}")
    if nature_mult not in (0.9, 1.0, 1.1):
        raise ValueError(
            f"nature_mult must be one of (0.9, 1.0, 1.1), got {nature_mult!r}"
        )
    ev = _ev_from_sp(sp)
    inner = ((2 * base + iv + ev // 4) * level) // 100 + 5
    return int(inner * nature_mult)


def final_hp_stat(
    base: int,
    sp: int,
    iv: int = IV_DEFAULT,
    level: int = LEVEL_DEFAULT,
) -> int:
    """Compute the final HP stat (nature does not affect HP).

    Formula:
        floor((2*base + iv + floor(ev/4)) * level / 100) + level + 10
    where ``ev = sp * 8``.
    """
    if sp < 0:
        raise ValueError(f"sp must be >= 0, got {sp}")
    ev = _ev_from_sp(sp)
    return ((2 * base + iv + ev // 4) * level) // 100 + level + 10


def find_nature_jumps(
    base: int,
    nature_mult: float,
    max_sp: int = SP_PER_STAT_CAP,
    iv: int = IV_DEFAULT,
    level: int = LEVEL_DEFAULT,
) -> list[int]:
    """Return SP values where 1 extra SP yields +2 (or more) final stat.

    These are the canonical "nature jumps": rounding through the nature
    multiplier occasionally turns 1 SP into a 2-point gain. Hitting those
    SP values preferentially lets the optimiser squeeze an extra point
    out of the 66-SP budget.

    The list contains the SP value AFTER the jump, i.e. ``sp`` such that
    ``final_stat(base, sp) - final_stat(base, sp - 1) >= 2``.
    """
    if max_sp < 1:
        return []
    jumps: list[int] = []
    prev = final_stat(base, 0, iv=iv, level=level, nature_mult=nature_mult)
    for sp in range(1, max_sp + 1):
        curr = final_stat(base, sp, iv=iv, level=level, nature_mult=nature_mult)
        if curr - prev >= 2:
            jumps.append(sp)
        prev = curr
    return jumps


def optimal_sp_for_target(
    base: int,
    target_stat: int,
    nature_mult: float,
    max_sp: int = SP_PER_STAT_CAP,
    iv: int = IV_DEFAULT,
    level: int = LEVEL_DEFAULT,
) -> int:
    """Return minimum SP to reach ``target_stat``, or -1 if unreachable.

    Walks SPs ascending from 0; returns the first SP whose final_stat
    meets or exceeds the target. If even ``max_sp`` falls short, returns
    -1 — caller decides whether to relax IVs, change nature, or accept.
    """
    if max_sp < 0:
        return -1
    for sp in range(0, max_sp + 1):
        if final_stat(base, sp, iv=iv, level=level, nature_mult=nature_mult) >= target_stat:
            return sp
    return -1
