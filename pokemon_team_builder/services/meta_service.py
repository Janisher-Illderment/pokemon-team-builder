from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import hishel
import httpx
from hishel.httpx import SyncCacheClient

from pokemon_team_builder.config import CACHE_DIR


_META_CHAMPIONS_FORMAT = "gen9championsvgc2026regmabo3"
_META_VGC_FALLBACK = "gen9vgc2025regibo3"
_META_RATING = "1825"
_META_BASE_URL = "https://munchstats.com"
_META_TTL = 86_400.0  # 24 hours

_client: SyncCacheClient | None = None


def _get_client() -> SyncCacheClient:
    global _client
    if _client is not None:
        return _client
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    storage = hishel.SyncSqliteStorage(
        database_path=str(CACHE_DIR / "meta_cache.db"),
        default_ttl=_META_TTL,
    )
    _client = SyncCacheClient(
        base_url=_META_BASE_URL,
        timeout=10.0,
        storage=storage,
    )
    return _client


def _slug(display: str) -> str:
    """Convert display name 'Wood Hammer' → 'wood-hammer'."""
    return display.strip().lower().replace(" ", "-").replace("'", "")


@dataclass
class MetaEntry:
    items: list[str] = field(default_factory=list)
    moves: list[str] = field(default_factory=list)
    teammates: list[str] = field(default_factory=list)


def _parse(data: dict[str, Any]) -> MetaEntry:
    def top_keys(d: object, n: int) -> list[str]:
        if not isinstance(d, dict):
            return []
        return [k for k, _ in sorted(d.items(), key=lambda x: x[1], reverse=True)[:n]]

    items_raw = data.get("Items", {})
    moves_raw = data.get("Moves", {})
    teammates_raw = data.get("Teammates", {})

    # Items keep display-name format (Title Case with spaces) to match
    # Champions item pool names used in _BACKUP_ITEMS and _DEFAULT_ITEM_BY_ROLE.
    items = top_keys(items_raw, 5)

    # Moves may come as hyphenated slugs or Title Case — normalise to slug.
    # Always exclude protect since slot 1 is always protect.
    moves = [
        _slug(m) for m in top_keys(moves_raw, 9) if _slug(m) != "protect"
    ][:6]

    # Teammates come as display names; normalise to slug for name comparisons.
    teammates = [_slug(t) for t in top_keys(teammates_raw, 6)]

    return MetaEntry(items=items, moves=moves, teammates=teammates)


class MetaService:
    def get(self, name: str) -> MetaEntry | None:
        """Fetch usage data for *name* from MunchStats. Returns None on failure."""
        client = _get_client()
        clean = name.strip().lower()
        for fmt in (_META_CHAMPIONS_FORMAT, _META_VGC_FALLBACK):
            url = f"/api/{fmt}/{_META_RATING}/{clean}"
            try:
                resp = client.get(url, extensions={"hishel_ttl": _META_TTL})
            except (httpx.HTTPError, OSError, Exception):
                continue
            if resp.status_code == 404:
                continue
            if resp.status_code != 200:
                continue
            try:
                data = resp.json()
            except Exception:
                continue
            return _parse(data)
        return None


def reset_client() -> None:
    """Reset the cached httpx client. For use in tests."""
    global _client
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
    _client = None
