from __future__ import annotations

import json
import logging
import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pokemon_team_builder.api.router import router
from pokemon_team_builder.config import (
    ABILITY_IMPLICIT_ROLES_FILE,
    ARCHETYPE_WEIGHTS_FILE,
    CHAMPIONS_LEGAL_ITEMS_FILE,
    LEGAL_POOL_FILE,
    ROLE_SP_TEMPLATES_FILE,
    TYPE_CHART_FILE,
    WEATHER_DEPENDENT_ABILITIES_FILE,
    WEATHER_SETTERS_FILE,
)
from pokemon_team_builder.services import sp_calc
from pokemon_team_builder.services import meta_versions as _meta_versions_mod

_logger = logging.getLogger("pokemon_team_builder.data_versions")
_logger.setLevel(logging.INFO)


def _read_version(path) -> tuple[str, int]:
    """Return ``(regulation, data_version)`` for a versioned data file.

    Returns ``("?", 0)`` on any failure so a missing/legacy file degrades
    to a visible-but-non-fatal log line instead of crashing the boot.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            # Top-level header (legal_pool, items, weather, archetype).
            reg = str(raw.get("regulation", "?"))
            ver = int(raw.get("data_version", 0))
            if ver:
                return reg, ver
            # Nested _meta wrapper (type_chart, role_sp_templates).
            meta = raw.get("_meta", {})
            if isinstance(meta, dict):
                return str(meta.get("regulation", "?")), int(meta.get("data_version", 0))
    except Exception:
        pass
    return "?", 0


def _log_data_versions() -> None:
    """Log a single line per versioned data file at app boot.

    Output is structured (file=... regulation=... data_version=...) so log
    aggregators can grep / parse it cheaply. A team variant's provenance is
    traceable to this snapshot.
    """
    files = [
        ("legal_pool",                LEGAL_POOL_FILE),
        ("items",                     CHAMPIONS_LEGAL_ITEMS_FILE),
        ("weather_abilities",         WEATHER_DEPENDENT_ABILITIES_FILE),
        ("weather_setters",           WEATHER_SETTERS_FILE),
        ("archetype_weights",         ARCHETYPE_WEIGHTS_FILE),
        ("ability_implicit_roles",    ABILITY_IMPLICIT_ROLES_FILE),
        ("type_chart",                TYPE_CHART_FILE),
        ("role_sp_templates",         ROLE_SP_TEMPLATES_FILE),
    ]
    for label, path in files:
        reg, ver = _read_version(path)
        _logger.info(
            "data_version file=%s regulation=%s data_version=%d", label, reg, ver
        )
    _logger.info(
        "data_version file=sp_mechanics regulation=%s data_version=%d",
        sp_calc.REGULATION, sp_calc.SP_MECHANICS_VERSION,
    )


_log_data_versions()
# Phase 3 §13.2 — emit a single structured line summarising every data
# file's version. The verbose per-file lines above remain for ops who
# want to filter / grep individual files; this line is the canonical
# "meta_versions" marker expected by the spec scenario.
_logger.info("meta_versions=%s", _meta_versions_mod.collect())

app = FastAPI(title="Pokemon Team Builder", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "web", "static")
if os.path.isdir(_STATIC_DIR):
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("pokemon_team_builder.main:app", host="0.0.0.0", port=port, reload=False)
