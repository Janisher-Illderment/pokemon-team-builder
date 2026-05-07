from __future__ import annotations

import logging
from dataclasses import dataclass, field

import hishel
import httpx
from hishel.httpx import SyncCacheClient

from pokemon_team_builder.config import CACHE_DIR
from pokemon_team_builder.services.pokemon_lookup import normalize_display_name

_logger = logging.getLogger(__name__)

_LABMAUS_BASE = "https://labmaus.net"
_LABMAUS_TTL = 21_600.0  # 6 hours
_REGULATION_MAP = {
    "M-A": "Regulation Set M-A",
    "Regulation Set M-A": "Regulation Set M-A",
}
_DEFAULT_HEADERS = {
    "User-Agent": "pokemon-team-builder/1.0 (personal team tool)",
    "Accept": "application/json, text/plain, */*",
    "Referer": f"{_LABMAUS_BASE}/teams/top-teams",
    "Origin": _LABMAUS_BASE,
}

_client: SyncCacheClient | None = None


def _get_client() -> SyncCacheClient:
    global _client
    if _client is not None:
        return _client
    cache_dir = CACHE_DIR / "labmaus"
    cache_dir.mkdir(parents=True, exist_ok=True)
    storage = hishel.SyncSqliteStorage(
        database_path=str(cache_dir / "cache.db"),
        default_ttl=_LABMAUS_TTL,
    )
    _client = SyncCacheClient(
        base_url=_LABMAUS_BASE,
        timeout=15.0,
        storage=storage,
        headers=_DEFAULT_HEADERS,
    )
    return _client


@dataclass
class LabMausMember:
    name: str
    item: str | None = None
    moves: list[str] = field(default_factory=list)


@dataclass
class LabMausTeam:
    members: list[LabMausMember]
    player: str
    tournament: str
    placement: int
    pokepaste_url: str
    regulation: str


def get_top_teams(regulation: str = "M-A") -> list[LabMausTeam]:
    """Return top teams for the given regulation from the LabMaus API.

    Returns an empty list on any network or parse failure (never raises).
    """
    reg_full = _REGULATION_MAP.get(regulation, regulation)
    try:
        client = _get_client()
        resp = client.get(
            "/api/top_teams",
            params={"language": "en", "regulation": reg_full},
            extensions={"hishel_ttl": _LABMAUS_TTL},
        )
        if resp.status_code != 200:
            _logger.warning("LabMaus API returned %d", resp.status_code)
            return []
        return _parse_response(resp.json(), reg_full)
    except httpx.HTTPError as exc:
        _logger.warning("LabMaus network error: %s", exc)
        return []
    except Exception as exc:
        _logger.warning("LabMaus parse error: %s", exc)
        return []


def _parse_response(data: object, regulation: str) -> list[LabMausTeam]:
    # Structure: data[i].teams[j].teams[k] = individual team entry
    if not isinstance(data, list):
        return []
    teams: list[LabMausTeam] = []
    seen: set[str] = set()
    for composition in data:
        if not isinstance(composition, dict):
            continue
        for group in composition.get("teams", []):
            if not isinstance(group, dict):
                continue
            for entry in group.get("teams", []):
                if not isinstance(entry, dict):
                    continue
                if entry.get("tournament_division", "").lower() != "masters":
                    continue
                pokepaste = entry.get("team_url", "")
                if pokepaste in seen:
                    continue
                seen.add(pokepaste)
                raw_names: list[str] = entry.get("pokemon_names", [])
                members = [
                    LabMausMember(name=normalize_display_name(n))
                    for n in raw_names
                    if n
                ]
                if not members:
                    continue
                teams.append(
                    LabMausTeam(
                        members=members,
                        player=str(entry.get("name", "")),
                        tournament=str(entry.get("tournament_name", "")),
                        placement=int(entry.get("placement", 0)),
                        pokepaste_url=pokepaste,
                        regulation=regulation,
                    )
                )
    return teams
