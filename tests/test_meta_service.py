from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pokemon_team_builder.services.meta_service import MetaEntry, MetaService, _parse, _slug


# ---------------------------------------------------------------------------
# _slug helper
# ---------------------------------------------------------------------------

def test_slug_space_to_hyphen():
    assert _slug("Wood Hammer") == "wood-hammer"


def test_slug_already_lowercase():
    assert _slug("earthquake") == "earthquake"


def test_slug_apostrophe_removed():
    assert _slug("King's Rock") == "kings-rock"


# ---------------------------------------------------------------------------
# _parse helper
# ---------------------------------------------------------------------------

_SAMPLE_RESPONSE = {
    "Items": {
        "Sitrus Berry": 40.0,
        "Life Orb": 35.0,
        "Lum Berry": 15.0,
        "Focus Sash": 8.0,
        "Scope Lens": 2.0,
        "Shell Bell": 0.5,
    },
    "Moves": {
        "wood-hammer": 88.0,
        "protect": 99.5,
        "earthquake": 60.0,
        "u-turn": 50.0,
        "grassy-glide": 45.0,
        "fake-out": 40.0,
        "knock-off": 35.0,
        "drain-punch": 25.0,
    },
    "Teammates": {
        "Flutter Mane": 55.0,
        "Incineroar": 50.0,
        "Landorus-Therian": 45.0,
        "Amoonguss": 40.0,
        "Torkoal": 35.0,
        "Chien-Pao": 30.0,
    },
}


def test_parse_items_top5():
    entry = _parse(_SAMPLE_RESPONSE)
    assert entry.items == [
        "Sitrus Berry", "Life Orb", "Lum Berry", "Focus Sash", "Scope Lens"
    ]


def test_parse_moves_excludes_protect_top6():
    entry = _parse(_SAMPLE_RESPONSE)
    assert "protect" not in entry.moves
    assert len(entry.moves) == 6
    assert entry.moves[0] == "wood-hammer"


def test_parse_teammates_slugified():
    entry = _parse(_SAMPLE_RESPONSE)
    assert "flutter-mane" in entry.teammates
    assert "incineroar" in entry.teammates
    assert len(entry.teammates) == 6


def test_parse_empty_response():
    entry = _parse({})
    assert entry.items == []
    assert entry.moves == []
    assert entry.teammates == []


def test_parse_non_dict_values():
    entry = _parse({"Items": None, "Moves": [], "Teammates": "oops"})
    assert entry.items == []
    assert entry.moves == []
    assert entry.teammates == []


# ---------------------------------------------------------------------------
# MetaService.get
# ---------------------------------------------------------------------------

def _make_mock_response(status: int, json_data: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = ValueError("no body")
    return resp


def _make_client(responses: list) -> MagicMock:
    """Return a mock client whose .get() yields successive responses."""
    client = MagicMock()
    client.get.side_effect = responses
    return client


def test_get_champions_format_hit():
    """Champions format succeeds on first try."""
    client = _make_client([_make_mock_response(200, _SAMPLE_RESPONSE)])
    with patch("pokemon_team_builder.services.meta_service._get_client", return_value=client):
        svc = MetaService()
        entry = svc.get("rillaboom")
    assert entry is not None
    assert "Sitrus Berry" in entry.items
    assert "wood-hammer" in entry.moves
    # Used exactly one request (Champions format)
    assert client.get.call_count == 1


def test_get_fallback_on_404():
    """Champions format 404 → retry with VGC fallback."""
    client = _make_client([
        _make_mock_response(404),
        _make_mock_response(200, _SAMPLE_RESPONSE),
    ])
    with patch("pokemon_team_builder.services.meta_service._get_client", return_value=client):
        svc = MetaService()
        entry = svc.get("rillaboom")
    assert entry is not None
    assert client.get.call_count == 2


def test_get_returns_none_on_full_failure():
    """Both formats fail → returns None without raising."""
    client = _make_client([
        _make_mock_response(404),
        _make_mock_response(500),
    ])
    with patch("pokemon_team_builder.services.meta_service._get_client", return_value=client):
        svc = MetaService()
        entry = svc.get("unknownpoke")
    assert entry is None


def test_get_returns_none_on_network_error():
    """Network exception → returns None without raising."""
    import httpx
    client = MagicMock()
    client.get.side_effect = httpx.ConnectError("unreachable")
    with patch("pokemon_team_builder.services.meta_service._get_client", return_value=client):
        svc = MetaService()
        entry = svc.get("rillaboom")
    assert entry is None


def test_get_returns_none_on_bad_json():
    """Non-JSON body on 200 → returns None."""
    client = _make_client([
        _make_mock_response(404),
        _make_mock_response(200, None),
    ])
    with patch("pokemon_team_builder.services.meta_service._get_client", return_value=client):
        svc = MetaService()
        entry = svc.get("rillaboom")
    assert entry is None
