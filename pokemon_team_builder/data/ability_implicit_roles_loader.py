from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache

from pokemon_team_builder.config import ABILITY_IMPLICIT_ROLES_FILE

_logger = logging.getLogger(__name__)


# Sentinel role label used to flag Levitate-style coverage hints. The role
# itself is NEVER summed into role_weights; it lives in the parallel
# ``coverage_flags`` map.
_GROUND_IMMUNITY_FLAG: str = "ground_immunity_flag"


@dataclass(frozen=True)
class AbilityRoleEntry:
    """One ability's contribution to role / coverage scoring.

    ``role`` and ``weight`` are the primary contribution (added to
    ``role_weights[role]``). ``secondary_role`` / ``secondary_weight``
    are optional (Multiscale → physical_wall AND special_wall).
    ``is_coverage_hint=True`` means the entry does NOT bump
    ``role_weights`` at all — it sets a coverage-side flag instead
    (Levitate → ground_immune).
    """

    role: str
    weight: float
    secondary_role: str | None = None
    secondary_weight: float = 0.0
    is_coverage_hint: bool = False


@lru_cache(maxsize=1)
def load_ability_implicit_roles() -> dict[str, AbilityRoleEntry]:
    """Return ``{ability_lower: AbilityRoleEntry}`` from the data file.

    Cached. On any failure (missing file, bad JSON, schema mismatch) we
    log a warning and return an empty dict — the caller treats missing
    entries as "no implicit role contribution", which is the safe
    degradation path.
    """
    try:
        with open(ABILITY_IMPLICIT_ROLES_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        abilities_raw = raw.get("abilities", {})
        out: dict[str, AbilityRoleEntry] = {}
        for ability, entry in abilities_raw.items():
            if not isinstance(entry, dict):
                continue
            role = entry.get("role")
            weight = entry.get("weight")
            if not isinstance(role, str) or not isinstance(weight, (int, float)):
                continue
            out[ability.lower()] = AbilityRoleEntry(
                role=role,
                weight=float(weight),
                secondary_role=entry.get("secondary_role"),
                secondary_weight=float(entry.get("secondary_weight", 0.0)),
                is_coverage_hint=bool(entry.get("is_coverage_hint", False)),
            )
        return out
    except Exception as exc:
        _logger.warning(
            "ability_implicit_roles.json load failed (%s: %s) — implicit roles disabled",
            type(exc).__name__, exc,
        )
        return {}


def is_ground_immunity_role(role_label: str) -> bool:
    """Return True if ``role_label`` is the Levitate-style coverage sentinel."""
    return role_label == _GROUND_IMMUNITY_FLAG
