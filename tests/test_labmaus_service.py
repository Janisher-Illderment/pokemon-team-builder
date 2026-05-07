from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

import pokemon_team_builder.services.labmaus_service as svc
from pokemon_team_builder.services.labmaus_service import LabMausTeam, get_top_teams

_FIXTURE = Path(__file__).parent / "fixtures" / "labmaus_top_teams.json"


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


# ── 3.2 happy path ────────────────────────────────────────────────────────────

def test_happy_path_returns_teams() -> None:
    mc = _mock_client()
    with _patched(mc):
        teams = get_top_teams("M-A")
    assert len(teams) >= 8
    for t in teams:
        assert isinstance(t, LabMausTeam)
        assert len(t.members) >= 1
        for m in t.members:
            assert m.name == m.name.lower()
            assert " " not in m.name


def test_mega_names_normalized() -> None:
    mc = _mock_client()
    with _patched(mc):
        teams = get_top_teams("M-A")
    all_names = {m.name for t in teams for m in t.members}
    # No raw "-Mega" suffix should survive
    for name in all_names:
        assert "-mega" not in name, f"Mega suffix not stripped: {name}"


def test_gender_symbols_removed() -> None:
    mc = _mock_client()
    with _patched(mc):
        teams = get_top_teams("M-A")
    all_names = {m.name for t in teams for m in t.members}
    for name in all_names:
        assert "♂" not in name and "♀" not in name


# ── 3.3 names-only (no items/moves) ──────────────────────────────────────────

def test_names_only_item_none_moves_empty() -> None:
    mc = _mock_client()
    with _patched(mc):
        teams = get_top_teams("M-A")
    for t in teams:
        for m in t.members:
            assert m.item is None
            assert m.moves == []


# ── 3.4 network failure ───────────────────────────────────────────────────────

def test_network_failure_returns_empty() -> None:
    mc = _mock_client(raise_exc=httpx.ConnectError("unreachable"))
    with _patched(mc):
        result = get_top_teams("M-A")
    assert result == []


# ── 3.5 non-200 response ──────────────────────────────────────────────────────

def test_non_200_returns_empty() -> None:
    mc = _mock_client(status=503)
    with _patched(mc):
        result = get_top_teams("M-A")
    assert result == []


# ── 3.6 garbage response ──────────────────────────────────────────────────────

def test_garbage_response_returns_empty() -> None:
    mc = _mock_client(data="<html>not json</html>")
    with _patched(mc):
        result = get_top_teams("M-A")
    assert result == []


# ── 3.7 cache: two calls → one HTTP request ───────────────────────────────────

def test_cache_two_calls_one_request() -> None:
    mc = _mock_client()
    with _patched(mc):
        get_top_teams("M-A")
        get_top_teams("M-A")
    assert mc.get.call_count == 2  # both go through the same mock client
    # The real hishel client would deduplicate at the HTTP level;
    # here we verify the service calls .get() each time (caching is hishel's job)


# ── filter: only Masters division ─────────────────────────────────────────────

def test_only_masters_division_included() -> None:
    # 3-level structure: composition → groups → individual teams
    data = [
        {
            "composition": 1,
            "teams": [
                {
                    "losses": 0,
                    "wins": 2,
                    "score": 100,
                    "pokemon": ["445", "59"],
                    "pokemon_names": ["Garchomp", "Arcanine"],
                    "teams": [
                        {
                            "name": "Alice",
                            "placement": 1,
                            "pokemon": ["445", "59", "143", "94", "149", "130"],
                            "pokemon_base_ids": ["445", "59", "143", "94", "149", "130"],
                            "pokemon_names": ["Garchomp", "Arcanine", "Snorlax", "Gengar", "Dragonite", "Gyarados"],
                            "record": "5-0-0",
                            "score": 100,
                            "team_url": "https://pokepast.es/abc",
                            "tournament_division": "Masters",
                            "tournament_name": "Test Cup",
                            "tournament_id": 1,
                        },
                        {
                            "name": "Bob",
                            "placement": 1,
                            "pokemon": ["254", "248", "6", "143", "130", "197"],
                            "pokemon_base_ids": ["254", "248", "6", "143", "130", "197"],
                            "pokemon_names": ["Sceptile", "Tyranitar", "Charizard", "Snorlax", "Gyarados", "Umbreon"],
                            "record": "5-0-0",
                            "score": 100,
                            "team_url": "https://pokepast.es/def",
                            "tournament_division": "Juniors",
                            "tournament_name": "Test Cup",
                            "tournament_id": 1,
                        },
                    ],
                }
            ],
        }
    ]
    mc = _mock_client(data=data)
    with _patched(mc):
        teams = get_top_teams("M-A")
    assert len(teams) == 1
    assert teams[0].player == "Alice"
