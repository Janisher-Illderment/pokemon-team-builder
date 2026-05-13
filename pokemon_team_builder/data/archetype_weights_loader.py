from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache

from pokemon_team_builder.config import ARCHETYPE_WEIGHTS_FILE
from pokemon_team_builder.domain.exceptions import TeamBuildError

_logger = logging.getLogger(__name__)


# Keys every archetype weight matrix MUST expose. Missing keys or
# out-of-range values raise at startup so the data file stays honest.
_REQUIRED_KEYS: tuple[str, ...] = (
    "coverage",
    "roles",
    "sp",
    "items",
    "speed",
    "bulk",
    "cheese_allowance",
    "weather_synergy",
)

# Hard validation range per the strategy-archetype spec. Multipliers are
# relative to the ``balance`` baseline = 1.0 across the board.
_MIN_WEIGHT: float = 0.0
_MAX_WEIGHT: float = 2.0

# The seven canonical archetypes (must match the GenerateRequest Literal).
_KNOWN_ARCHETYPES: tuple[str, ...] = (
    "hyper_offense",
    "hard_trick_room",
    "bulky_offense",
    "weather_based",
    "stall",
    "balance",
    "perish_trap",
)

# Default fallback used when a caller asks for an archetype absent from the
# file (or after a malformed entry was dropped). ``balance`` is the canonical
# baseline so callers can rely on multiplier == 1.0 across components.
_DEFAULT_ARCHETYPE: str = "balance"


@dataclass(frozen=True)
class ArchetypeWeights:
    """Scoring weight multipliers for a single archetype.

    All weights are floats in ``[0.0, 2.0]`` — relative to ``balance`` (1.0).
    The eight components are: coverage, roles, sp, items, speed, bulk,
    cheese_allowance (gates cheese-move selection — see
    ``replica_exporter.select_moves_for_role``), and weather_synergy.
    """

    coverage: float
    roles: float
    sp: float
    items: float
    speed: float
    bulk: float
    cheese_allowance: float
    weather_synergy: float


def _balance_default() -> ArchetypeWeights:
    """Return a hard-coded ``balance`` weight matrix.

    Used as a last-resort fallback when ``archetype_weights.json`` is
    missing or unparsable. Mirrors the in-file ``balance`` entry so
    behavior in the offline / broken-file case is identical to a healthy
    ``balance`` request — no silent score skew.

    All *scoring multipliers* are 1.0 (balance IS the baseline). The
    ``cheese_allowance`` field is intentionally < 1.0 because it is a
    gate threshold, not a multiplier — per the strategy-archetype spec,
    ``balance`` skips cheese moves (Destiny Bond / Mirror Coat / Counter
    / Memento / Perish Song). Only ``perish_trap`` opens the gate.
    """
    return ArchetypeWeights(
        coverage=1.0,
        roles=1.0,
        sp=1.0,
        items=1.0,
        speed=1.0,
        bulk=1.0,
        cheese_allowance=0.8,
        weather_synergy=1.0,
    )


@lru_cache(maxsize=1)
def load_archetype_weights() -> dict[str, ArchetypeWeights]:
    """Load and validate ``archetype_weights.json`` into a name → weights map.

    Validation policy (per strategy-archetype spec):
      - Each archetype entry MUST expose all 8 required keys.
      - Each weight MUST be a float in ``[0.0, 2.0]``.
      - A missing key OR an out-of-range value raises ``TeamBuildError``
        with the file path and offending key — surfaced at startup so a
        broken file does not silently degrade scoring.
      - ``balance`` MUST be present. If absent it is synthesized from the
        in-code default so callers can always fall back deterministically.

    Returns:
        Dict keyed by archetype name (e.g. ``"hyper_offense"``).

    Raises:
        TeamBuildError: when the file exists but is malformed (missing
            keys / out-of-range weights). When the file is entirely
            missing, we log a warning and return a single ``balance``
            entry so the application still boots.
    """
    try:
        with open(ARCHETYPE_WEIGHTS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        _logger.warning(
            "archetype_weights.json not found at %s — falling back to "
            "balance-only defaults",
            ARCHETYPE_WEIGHTS_FILE,
        )
        return {_DEFAULT_ARCHETYPE: _balance_default()}
    except json.JSONDecodeError as exc:
        raise TeamBuildError(
            f"archetype_weights.json is not valid JSON at "
            f"{ARCHETYPE_WEIGHTS_FILE}: {exc}"
        ) from exc

    archetypes_raw = raw.get("archetypes")
    if not isinstance(archetypes_raw, dict):
        raise TeamBuildError(
            f"archetype_weights.json at {ARCHETYPE_WEIGHTS_FILE} is "
            f"missing the required top-level 'archetypes' object."
        )

    out: dict[str, ArchetypeWeights] = {}
    # Iterate the file in sorted order so validation errors surface
    # deterministically (no test flake on dict insertion order).
    for archetype in sorted(archetypes_raw.keys()):
        entry = archetypes_raw[archetype]
        if not isinstance(entry, dict):
            raise TeamBuildError(
                f"archetype_weights.json: entry for "
                f"'{archetype}' is not an object (path={ARCHETYPE_WEIGHTS_FILE})."
            )
        values: dict[str, float] = {}
        for key in _REQUIRED_KEYS:
            if key not in entry:
                raise TeamBuildError(
                    f"archetype_weights.json: archetype '{archetype}' is "
                    f"missing required key '{key}' "
                    f"(path={ARCHETYPE_WEIGHTS_FILE})."
                )
            value = entry[key]
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise TeamBuildError(
                    f"archetype_weights.json: archetype '{archetype}' "
                    f"key '{key}' must be a number, got "
                    f"{type(value).__name__} (path={ARCHETYPE_WEIGHTS_FILE})."
                )
            fvalue = float(value)
            if fvalue < _MIN_WEIGHT or fvalue > _MAX_WEIGHT:
                raise TeamBuildError(
                    f"archetype_weights.json: archetype '{archetype}' "
                    f"key '{key}' value {fvalue} is outside the allowed "
                    f"range [{_MIN_WEIGHT}, {_MAX_WEIGHT}] "
                    f"(path={ARCHETYPE_WEIGHTS_FILE})."
                )
            values[key] = fvalue
        out[archetype] = ArchetypeWeights(**values)

    # Guarantee a 'balance' entry exists so get_weights() can always
    # fall back deterministically without a None branch at call sites.
    if _DEFAULT_ARCHETYPE not in out:
        _logger.warning(
            "archetype_weights.json missing '%s' entry — synthesizing "
            "in-code defaults (all 1.0).",
            _DEFAULT_ARCHETYPE,
        )
        out[_DEFAULT_ARCHETYPE] = _balance_default()

    return out


def get_weights(archetype: str) -> ArchetypeWeights:
    """Return the ``ArchetypeWeights`` for ``archetype``.

    Unknown / unrecognised archetype names fall back to ``balance`` —
    the API layer already validates the input with a Pydantic ``Literal``
    so this branch should never fire in normal use. It exists as a
    defence-in-depth measure for internal callers that haven't been
    threaded through the validated schema yet.
    """
    weights = load_archetype_weights()
    if archetype in weights:
        return weights[archetype]
    _logger.warning(
        "Unknown archetype '%s' — falling back to '%s'.",
        archetype, _DEFAULT_ARCHETYPE,
    )
    return weights.get(_DEFAULT_ARCHETYPE, _balance_default())


def known_archetypes() -> tuple[str, ...]:
    """Return the canonical archetype tuple — the source of truth for the
    Pydantic ``Literal`` on ``GenerateRequest``.
    """
    return _KNOWN_ARCHETYPES
