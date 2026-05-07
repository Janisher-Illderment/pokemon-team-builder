from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

import pokemon_team_builder.services.tournament_service as svc
from pokemon_team_builder.services.tournament_service import Tournament, get_upcoming

_FIXTURE = Path(__file__).parent / "fixtures" / "labmaus_upcoming_tournaments.json"

_TENERIFE_LAT = 28.4636
_TENERIFE_LON = -16.2518


def _fixture_data() -> list:
    with _FIXTURE.open(encoding="utf-8") as f:
        return json.load(f)


def _mock_client(status: int = 200, data: object = None, raise_exc: Exception | None = None):
    mock = MagicMock()
    if raise_exc is not None:
        mock.get.side_effect = raise_exc
    else:
        resp = MagicMock()
        resp.status_code = status
        resp.json.return_value = data if data is not None else _fixture_data()
        mock.get.return_value = resp
    return mock


def _patched(mock_client):
    return patch.object(svc, "_get_client", return_value=mock_client)


_NEARBY_ITEMS = [
    {"id": "T1", "name": "Copa Madrid", "date": "2026-06-01", "lat": 40.4, "lng": -3.7, "regulation": "Regulation Set M-A"},
    {"id": "T2", "name": "Londres Cup", "date": "2026-05-15", "lat": 51.5, "lng": -0.1, "regulation": "Regulation Set M-A"},
]
_FAR_ITEM = {"id": "T3", "name": "Tokio Cup", "date": "2026-06-10", "lat": 35.7, "lng": 139.7, "regulation": "Regulation Set M-A"}


# ── 5.2 happy path ────────────────────────────────────────────────────────────

def test_happy_path_returns_tournaments_sorted() -> None:
    data = _NEARBY_ITEMS + [_FAR_ITEM]
    mc = _mock_client(data=data)
    with _patched(mc):
        results = get_upcoming(lat=_TENERIFE_LAT, lon=_TENERIFE_LON, radius_miles=5000)
    assert len(results) >= 2
    dates = [t.date for t in results]
    assert dates == sorted(dates), "Results should be sorted ascending by date"
    for t in results:
        assert isinstance(t, Tournament)
        assert t.name
        assert t.date


# ── 5.3 radius filter excludes far events ────────────────────────────────────

def test_radius_filters_distant_events() -> None:
    data = _NEARBY_ITEMS + [_FAR_ITEM]
    mc = _mock_client(data=data)
    with _patched(mc):
        results = get_upcoming(lat=_TENERIFE_LAT, lon=_TENERIFE_LON, radius_miles=500)
    names = [t.name for t in results]
    assert "Tokio Cup" not in names


# ── 5.4 network failure ───────────────────────────────────────────────────────

def test_network_failure_returns_empty() -> None:
    mc = _mock_client(raise_exc=httpx.ConnectError("unreachable"))
    with _patched(mc):
        result = get_upcoming()
    assert result == []


# ── 5.5 empty response ───────────────────────────────────────────────────────

def test_empty_response_returns_empty() -> None:
    mc = _mock_client(data=[])
    with _patched(mc):
        result = get_upcoming()
    assert result == []


# ── 5.6 non-200 returns empty ────────────────────────────────────────────────

def test_non_200_returns_empty() -> None:
    mc = _mock_client(status=503)
    with _patched(mc):
        result = get_upcoming()
    assert result == []


# ── haversine sanity ──────────────────────────────────────────────────────────

def test_haversine_same_point_is_zero() -> None:
    from pokemon_team_builder.services.tournament_service import _haversine_miles
    assert _haversine_miles(0.0, 0.0, 0.0, 0.0) == pytest.approx(0.0, abs=0.01)


def test_haversine_tenerife_to_madrid() -> None:
    from pokemon_team_builder.services.tournament_service import _haversine_miles
    dist = _haversine_miles(_TENERIFE_LAT, _TENERIFE_LON, 40.4, -3.7)
    assert 900 < dist < 1200, f"Expected ~1089 miles, got {dist:.0f}"
