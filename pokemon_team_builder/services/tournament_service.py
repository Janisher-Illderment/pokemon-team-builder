from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import hishel
import httpx
from hishel.httpx import SyncCacheClient

from pokemon_team_builder.config import CACHE_DIR

_logger = logging.getLogger(__name__)

_LABMAUS_BASE = "https://labmaus.net"
_TOURNAMENT_TTL = 43_200.0  # 12 hours
_DEFAULT_HEADERS = {
    "User-Agent": "pokemon-team-builder/1.0 (personal team tool)",
    "Accept": "application/json, text/plain, */*",
    "Referer": f"{_LABMAUS_BASE}/",
    "Origin": _LABMAUS_BASE,
}

_DEFAULT_LAT = 28.4636
_DEFAULT_LON = -16.2518
_DEFAULT_RADIUS_MILES = 500

_client: SyncCacheClient | None = None


def _get_client() -> SyncCacheClient:
    global _client
    if _client is not None:
        return _client
    cache_dir = CACHE_DIR / "tournaments"
    cache_dir.mkdir(parents=True, exist_ok=True)
    storage = hishel.SyncSqliteStorage(
        database_path=str(cache_dir / "cache.db"),
        default_ttl=_TOURNAMENT_TTL,
    )
    _client = SyncCacheClient(
        base_url=_LABMAUS_BASE,
        timeout=15.0,
        storage=storage,
        headers=_DEFAULT_HEADERS,
    )
    return _client


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles."""
    R = 3_958.8
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


@dataclass
class Tournament:
    id: str
    name: str
    date: str
    city: str
    country: str
    regulation: str
    lat: float
    lon: float
    url: str = ""


def get_upcoming(
    lat: float = _DEFAULT_LAT,
    lon: float = _DEFAULT_LON,
    radius_miles: int = _DEFAULT_RADIUS_MILES,
) -> list[Tournament]:
    """Return upcoming tournaments within radius_miles of (lat, lon).

    Returns empty list on any failure (never raises).
    """
    try:
        client = _get_client()
        resp = client.get(
            "/api/upcoming_tournaments",
            extensions={"hishel_ttl": _TOURNAMENT_TTL},
        )
        if resp.status_code != 200:
            _logger.warning("Tournament API returned %d", resp.status_code)
            return []
        return _parse_response(resp.json(), lat, lon, radius_miles)
    except httpx.HTTPError as exc:
        _logger.warning("Tournament network error: %s", exc)
        return []
    except Exception as exc:
        _logger.warning("Tournament parse error: %s", exc)
        return []


def _parse_response(
    data: object, lat: float, lon: float, radius_miles: int
) -> list[Tournament]:
    if not isinstance(data, list):
        return []
    results: list[Tournament] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        t_lat = item.get("lat")
        t_lon = item.get("lng")
        if not isinstance(t_lat, (int, float)) or not isinstance(t_lon, (int, float)):
            continue
        dist = _haversine_miles(lat, lon, float(t_lat), float(t_lon))
        if dist > radius_miles:
            continue
        results.append(
            Tournament(
                id=str(item.get("id", "")),
                name=str(item.get("name", "")),
                date=str(item.get("date", "")),
                city="",
                country="",
                regulation=str(item.get("regulation", "")),
                lat=float(t_lat),
                lon=float(t_lon),
                url="",
            )
        )
    results.sort(key=lambda t: t.date)
    return results
