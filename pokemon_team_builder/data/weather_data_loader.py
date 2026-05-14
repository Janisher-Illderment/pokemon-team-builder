"""Weather setters + weather-dependent abilities loaders (Phase 3, §8).

Reads the two Phase 1 JSONs (`weather_dependent_abilities.json` and
`weather_setters.json`) into memoised maps that the viability rater
consumes. Both files carry a ``data_version`` integer that propagates
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

Phase 4b cleanup (Tecle Briefs 3-1 + 3-2): `load_weather_setters`
returns ``WeatherSetterEntry`` dataclasses (not bare slugs) so the
rater can verify ``member.ability`` matches the setter ability AND
respect the ``mega_only`` flag (e.g. Froslass only sets Snow when
mega-evolved).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache

from pokemon_team_builder.config import (
    WEATHER_DEPENDENT_ABILITIES_FILE,
    WEATHER_SETTERS_FILE,
)

_logger = logging.getLogger(__name__)


def _slug(name: str) -> str:
    return name.strip().lower().replace(" ", "-")


@dataclass(frozen=True)
class WeatherSetterEntry:
    """One row of the setters list — species + the ability that sets weather.

    ``mega_only`` means the species sets the weather **only** when its
    mega form is active. E.g. Froslass-mega sets Snow via Snow Warning,
    but base Froslass (Cursed Body) does not. Consumers must check the
    member's ``mega_form`` before counting this setter.
    """

    pokemon: str
    ability: str
    mega_only: bool = False


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
def load_weather_setters() -> tuple[dict[str, list[WeatherSetterEntry]], int]:
    """Return ``(weather -> list[WeatherSetterEntry], data_version)``.

    Only ability-based setters are included (move-setters carry lower
    confidence per the spec). The entries carry the setter ability slug
    AND the ``mega_only`` flag so consumers can verify the member
    actually has the setter ability assigned (not just shares a species
    slug with a setter) and respect mega-form gating.
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
    out: dict[str, list[WeatherSetterEntry]] = {}
    for weather, payload in setters_raw.items():
        entries: list[WeatherSetterEntry] = []
        if isinstance(payload, dict):
            for entry in payload.get("ability_setters", []) or []:
                if isinstance(entry, dict) and "pokemon" in entry:
                    entries.append(WeatherSetterEntry(
                        pokemon=_slug(entry["pokemon"]),
                        ability=_slug(entry.get("ability", "")),
                        mega_only=bool(entry.get("mega_only", False)),
                    ))
        out[weather.lower()] = entries
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
