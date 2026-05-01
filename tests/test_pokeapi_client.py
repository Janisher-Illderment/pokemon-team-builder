from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from pokemon_team_builder import config
from pokemon_team_builder.data import pokeapi_client
from pokemon_team_builder.domain.exceptions import (
    PokeAPIError,
    PokemonNotFoundError,
)


CHARIZARD_FIXTURE: dict[str, Any] = {
    "id": 6,
    "name": "charizard",
    "types": [
        {"slot": 1, "type": {"name": "fire"}},
        {"slot": 2, "type": {"name": "flying"}},
    ],
    "stats": [
        {"base_stat": 78, "stat": {"name": "hp"}},
        {"base_stat": 84, "stat": {"name": "attack"}},
        {"base_stat": 78, "stat": {"name": "defense"}},
        {"base_stat": 109, "stat": {"name": "special-attack"}},
        {"base_stat": 85, "stat": {"name": "special-defense"}},
        {"base_stat": 100, "stat": {"name": "speed"}},
    ],
    "moves": [
        {"move": {"name": "flamethrower"}},
        {"move": {"name": "air-slash"}},
    ],
}


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect cache to a temp dir per test and reset the module client."""
    cache_dir = tmp_path / ".pokemon-builder-test"
    cache_db = cache_dir / "cache.db"
    monkeypatch.setattr(config, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(config, "CACHE_DB", cache_db)
    monkeypatch.setattr(pokeapi_client, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(pokeapi_client, "CACHE_DB", cache_db)
    pokeapi_client.reset_client()
    yield
    pokeapi_client.reset_client()
    if cache_dir.exists():
        shutil.rmtree(cache_dir, ignore_errors=True)


def test_get_pokemon_returns_dict() -> None:
    with respx.mock(base_url=config.POKEAPI_BASE) as router:
        router.get("/pokemon/charizard").mock(
            return_value=httpx.Response(200, json=CHARIZARD_FIXTURE)
        )
        result = pokeapi_client.get_pokemon("charizard")

    assert isinstance(result, dict)
    assert result["id"] == 6
    assert result["name"] == "charizard"
    assert result["types"][0]["type"]["name"] == "fire"


def test_get_pokemon_404_raises_not_found() -> None:
    with respx.mock(base_url=config.POKEAPI_BASE) as router:
        router.get("/pokemon/xyz_nonexistent").mock(
            return_value=httpx.Response(404, json={"detail": "Not found."})
        )
        with pytest.raises(PokemonNotFoundError) as exc_info:
            pokeapi_client.get_pokemon("xyz_nonexistent")

    assert "xyz_nonexistent" in str(exc_info.value)


def test_get_pokemon_timeout_raises_pokeapi_error() -> None:
    with respx.mock(base_url=config.POKEAPI_BASE) as router:
        router.get("/pokemon/charizard").mock(
            side_effect=httpx.TimeoutException("timed out")
        )
        with pytest.raises(PokeAPIError) as exc_info:
            pokeapi_client.get_pokemon("charizard")

    assert "PokeAPI" in str(exc_info.value)


def test_get_pokemon_network_error_raises_pokeapi_error() -> None:
    with respx.mock(base_url=config.POKEAPI_BASE) as router:
        router.get("/pokemon/charizard").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        with pytest.raises(PokeAPIError):
            pokeapi_client.get_pokemon("charizard")


def test_cache_dir_is_created_if_missing(tmp_path: Path) -> None:
    """First call must create CACHE_DIR; module import must NOT."""
    # The autouse fixture already redirects to a non-existent dir.
    assert not config.CACHE_DIR.exists()
    with respx.mock(base_url=config.POKEAPI_BASE) as router:
        router.get("/pokemon/1").mock(
            return_value=httpx.Response(200, json=CHARIZARD_FIXTURE)
        )
        pokeapi_client.get_pokemon(1)

    assert config.CACHE_DIR.exists()
    assert config.CACHE_DIR.is_dir()


def test_get_pokemon_accepts_int_id() -> None:
    with respx.mock(base_url=config.POKEAPI_BASE) as router:
        router.get("/pokemon/6").mock(
            return_value=httpx.Response(200, json=CHARIZARD_FIXTURE)
        )
        result = pokeapi_client.get_pokemon(6)
    assert result["name"] == "charizard"


def test_get_pokemon_500_raises_pokeapi_error() -> None:
    with respx.mock(base_url=config.POKEAPI_BASE) as router:
        router.get("/pokemon/charizard").mock(
            return_value=httpx.Response(500, text="boom")
        )
        with pytest.raises(PokeAPIError) as exc_info:
            pokeapi_client.get_pokemon("charizard")
    assert "500" in str(exc_info.value)


def test_get_move_404_raises_pokeapi_error() -> None:
    # WHY: for moves we map 404 to PokeAPIError, not PokemonNotFoundError,
    # so that callers don't confuse "missing move" with "missing pokemon".
    with respx.mock(base_url=config.POKEAPI_BASE) as router:
        router.get("/move/zzz").mock(
            return_value=httpx.Response(404, json={"detail": "Not found."})
        )
        with pytest.raises(PokeAPIError):
            pokeapi_client.get_move("zzz")
