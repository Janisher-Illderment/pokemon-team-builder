import sys
from pathlib import Path

CACHE_DIR = Path.home() / ".pokemon-builder"
CACHE_DB = CACHE_DIR / "cache.db"
CACHE_TTL_SECONDS = 30 * 24 * 3600  # 30 days

# PyInstaller bundles package data under sys._MEIPASS; fall back to the
# normal source-relative path for editable installs and regular pip installs.
if getattr(sys, "frozen", False):
    DATA_DIR = Path(sys._MEIPASS) / "pokemon_team_builder" / "data"  # type: ignore[attr-defined]
else:
    DATA_DIR = Path(__file__).parent / "data"
LEGAL_POOL_FILE = DATA_DIR / "legal_pool_mA.json"
TYPE_CHART_FILE = DATA_DIR / "type_chart.json"
ROLE_SP_TEMPLATES_FILE = DATA_DIR / "role_sp_templates.json"
CHAMPIONS_LEGAL_ITEMS_FILE = DATA_DIR / "champions_legal_items.json"
WEATHER_DEPENDENT_ABILITIES_FILE = DATA_DIR / "weather_dependent_abilities.json"
WEATHER_SETTERS_FILE = DATA_DIR / "weather_setters.json"
ARCHETYPE_WEIGHTS_FILE = DATA_DIR / "archetype_weights.json"
ABILITY_IMPLICIT_ROLES_FILE = DATA_DIR / "ability_implicit_roles.json"
MAX_SP_TOTAL = 66
MAX_SP_STAT = 32
POKEAPI_BASE = "https://pokeapi.co/api/v2"
POKEAPI_TIMEOUT = 5.0
