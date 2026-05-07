from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_DATA_FILE = Path(__file__).parent / "speed_tiers.json"
_LEVEL = 50
_IV = 31


def _calc_speed(base_spe: int, sps: int, nature_mod: float) -> int:
    """Level-50 speed stat. SPs map to EVs as sp*8 (max 32→256≈252)."""
    evs = sps * 8
    raw = math.floor((math.floor(2 * base_spe + _IV + math.floor(evs / 4)) * _LEVEL / 100) + 5)
    return math.floor(raw * nature_mod)


@dataclass(frozen=True)
class TierEntry:
    name: str
    base_spe: int
    usage_rank: int


class SpeedTierDB:
    def __init__(self, entries: list[TierEntry]) -> None:
        self._entries = entries

    def compute_speed(self, base_spe: int, sps: int, nature: str) -> int:
        mod = _nature_spe_mod(nature)
        return _calc_speed(base_spe, sps, mod)

    def faster_than(self, speed: int) -> list[str]:
        """Names of tier entries whose max-investment speed is BELOW the given speed."""
        return [
            e.name for e in self._entries
            if _calc_speed(e.base_spe, 0, 1.0) < speed
        ]

    def slower_than(self, speed: int) -> list[str]:
        """Names of tier entries whose neutral-0SP speed is ABOVE the given speed."""
        return [
            e.name for e in self._entries
            if _calc_speed(e.base_spe, 0, 1.0) > speed
        ]

    def entries(self) -> list[TierEntry]:
        return list(self._entries)


def _nature_spe_mod(nature: str) -> float:
    _BOOSTING = {"timid", "hasty", "jolly", "naive"}
    _REDUCING = {"brave", "relaxed", "quiet", "sassy"}
    n = nature.lower()
    if n in _BOOSTING:
        return 1.1
    if n in _REDUCING:
        return 0.9
    return 1.0


@lru_cache(maxsize=1)
def load() -> SpeedTierDB:
    raw = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    entries = [TierEntry(name=e["name"], base_spe=e["base_spe"], usage_rank=e["usage_rank"]) for e in raw]
    entries.sort(key=lambda e: (-e.base_spe, e.usage_rank))
    return SpeedTierDB(entries)
