from pathlib import Path

CACHE_DIR = Path.home() / ".pokemon-builder"
CACHE_DB = CACHE_DIR / "cache.db"
CACHE_TTL_SECONDS = 30 * 24 * 3600  # 30 days
DATA_DIR = Path(__file__).parent.parent / "data"
LEGAL_POOL_FILE = DATA_DIR / "legal_pool_mA.json"
TYPE_CHART_FILE = DATA_DIR / "type_chart.json"
ROLE_SP_TEMPLATES_FILE = DATA_DIR / "role_sp_templates.json"
MAX_SP_TOTAL = 66
MAX_SP_STAT = 32
POKEAPI_BASE = "https://pokeapi.co/api/v2"
POKEAPI_TIMEOUT = 5.0
