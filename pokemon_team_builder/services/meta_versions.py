"""Aggregator for data-file ``data_version`` integers (Phase 3, §13).

Provides a single function ``collect()`` that reads each tunable
static-data JSON and returns the version map exposed under
``VariantOut.meta_versions`` and the ``/health`` endpoint.

Design:
  - Pure lookup, no mutation. Cached via ``lru_cache`` because data
    files are read-only at runtime.
  - Missing or malformed files default to 0 (no hard failure) — the
    individual loaders already log warnings.
  - Keys are stable: ``legal_pool``, ``items``, ``weather``,
    ``archetype_weights``, ``sp_mechanics``, ``ability_roles``,
    ``mega_evolutions``, ``doubles_roles``, ``type_chart``.
    ``meta_teams`` is intentionally absent — MunchStats is an external
    source with its own freshness, not a static file we ship.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from pokemon_team_builder.config import (
    ABILITY_IMPLICIT_ROLES_FILE,
    ARCHETYPE_WEIGHTS_FILE,
    CHAMPIONS_LEGAL_ITEMS_FILE,
    DATA_DIR,
    LEGAL_POOL_FILE,
    ROLE_SP_TEMPLATES_FILE,
    TYPE_CHART_FILE,
)
from pokemon_team_builder.data.weather_data_loader import get_weather_version
from pokemon_team_builder.services.sp_calc import SP_MECHANICS_VERSION

_logger = logging.getLogger(__name__)


def _read_version(path: Path) -> int:
    """Return the ``data_version`` int from a JSON file (top-level or _meta)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as exc:
        _logger.warning("meta_versions: failed to read %s (%s)", path, exc)
        return 0
    if isinstance(raw, dict):
        if "data_version" in raw:
            try:
                return int(raw["data_version"])
            except (TypeError, ValueError):
                return 0
        meta = raw.get("_meta")
        if isinstance(meta, dict) and "data_version" in meta:
            try:
                return int(meta["data_version"])
            except (TypeError, ValueError):
                return 0
    return 0


@lru_cache(maxsize=1)
def collect() -> dict[str, int]:
    """Return the data_version map for all tunable static files."""
    mega_path = DATA_DIR / "mega_evolutions.json"
    doubles_path = DATA_DIR / "doubles_roles.json"
    return {
        "legal_pool":         _read_version(LEGAL_POOL_FILE),
        "items":              _read_version(CHAMPIONS_LEGAL_ITEMS_FILE),
        "weather":            get_weather_version(),
        "archetype_weights":  _read_version(ARCHETYPE_WEIGHTS_FILE),
        "sp_mechanics":       SP_MECHANICS_VERSION,
        "ability_roles":      _read_version(ABILITY_IMPLICIT_ROLES_FILE),
        "mega_evolutions":    _read_version(mega_path),
        "doubles_roles":      _read_version(doubles_path),
        "type_chart":         _read_version(TYPE_CHART_FILE),
        "role_sp_templates":  _read_version(ROLE_SP_TEMPLATES_FILE),
        # meta_teams intentionally omitted — MunchStats is external.
    }


def log_startup() -> None:
    """Emit a structured INFO line listing all loaded data versions."""
    versions = collect()
    _logger.info("meta_versions=%s", versions)
