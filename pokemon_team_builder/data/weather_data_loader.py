"""Weather setters + weather-dependent abilities loaders (Phase 3, §8).

Reads the two Phase 1 JSONs (`weather_dependent_abilities.json` and
`weather_setters.json`) into memoised maps that the viability rater
consumes.  Both files carry a ``data_version`` integer that propagates
to ``VariantOut.meta_versions.weather``.

Design choices:
  - lru_cache(maxsize=1) — the data is static at runtime; reload would
    require a process restart anyway.
  - On any load failure we return empty maps + version=0 (degrades to
    "no weather synergy" rather than crashing the API). The rater
    treats empty maps as "no synergy detected" — score is unaffected.
  - Ability and pokemon names are normalised to lowercase-hyphen slugs
    so callers can compare against the slug-form already used in
    ``pokemon.abilities`` / ``pokemon.name``.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache

from pokemon_team_builder.config import (
    WEATHER_DEPENDENT_ABILITIES_FILE,
    WEATHER_SETTERS_FILE,
)

_logger = logging.getLogger(__name__)


def _slug(name: str) -> str:
    return name.strip().lower().replace(" ", "-")


@lru_cache(maxsize=1)
def load_weather_dependent_abilities() -> tuple[dict[str, str], int]:
    """Return ``(ability_slug -> required_weather, data_version)``.

    Each value is the weather string (``sun``, ``rain``, ``sand``,
    ``snow``) the ability requires to activate. On load failure returns
    ``({}, 0)`` so the rater silently skips the weather component.
    """
    try:
        with open(WEATHER_DEPENDENT_ABILITIES_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as exc:
        _logger.warning(
            "weather_dependent_abilities.json load failed (%s: %s); "
            "weather synergy disabled.",
            type(exc).__name__, exc,
        )
        return {}, 0

    abilities = raw.get("abilities", {})
    out: dict[str, str] = {}
    for ability, payload in abilities.items():
        if isinstance(payload, dict) and "weather" in payload:
            out[_slug(ability)] = str(payload["weather"]).lower()
    version = int(raw.get("data_version", 0))
    return out, version


@lru_cache(maxsize=1)
def load_weather_setters() -> tuple[dict[str, set[str]], int]:
    """Return ``(weather -> set of setter pokemon slugs, data_version)``.

    Only ability-based setters are included (move-setters carry lower
    confidence per the spec).  ``mega_only`` setters still appear under
    the species slug — the rater is conservative and assumes the mega
    form is available; future work may gate this on the variant's mega
    assignment.
    """
    try:
        with open(WEATHER_SETTERS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as exc:
        _logger.warning(
            "weather_setters.json load failed (%s: %s); "
            "weather synergy disabled.",
            type(exc).__name__, exc,
        )
        return {}, 0

    setters_raw = raw.get("setters", {})
    out: dict[str, set[str]] = {}
    for weather, payload in setters_raw.items():
        names: set[str] = set()
        if isinstance(payload, dict):
            for entry in payload.get("ability_setters", []) or []:
                if isinstance(entry, dict) and "pokemon" in entry:
                    names.add(_slug(entry["pokemon"]))
        out[weather.lower()] = names
    version = int(raw.get("data_version", 0))
    return out, version


def get_weather_version() -> int:
    """Return the max of the two weather data file versions.

    A single integer simplifies ``meta_versions.weather`` exposure.
    The two files are bumped together in practice so taking max is safe.
    """
    _, v1 = load_weather_dependent_abilities()
    _, v2 = load_weather_setters()
    return max(v1, v2)
