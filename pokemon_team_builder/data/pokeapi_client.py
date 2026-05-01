from __future__ import annotations

from typing import Any, Union

import hishel
import httpx
from hishel.httpx import SyncCacheClient

from pokemon_team_builder.config import (
    CACHE_DB,
    CACHE_DIR,
    CACHE_TTL_SECONDS,
    POKEAPI_BASE,
    POKEAPI_TIMEOUT,
)
from pokemon_team_builder.domain.exceptions import (
    PokeAPIError,
    PokemonNotFoundError,
)


_client: SyncCacheClient | None = None


def _get_client() -> SyncCacheClient:
    """Return a process-wide cached httpx client backed by hishel + SQLite.

    The SQLite database under ``config.CACHE_DB`` persists between processes,
    so the 30-day TTL is honored across runs. ``CACHE_DIR`` is created lazily
    here (not at module import) so importing the module never has filesystem
    side effects.
    """
    global _client
    if _client is not None:
        return _client

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    storage = hishel.SyncSqliteStorage(
        database_path=str(CACHE_DB),
        default_ttl=float(CACHE_TTL_SECONDS),
    )
    _client = SyncCacheClient(
        base_url=POKEAPI_BASE,
        timeout=POKEAPI_TIMEOUT,
        storage=storage,
    )
    return _client


def _request_json(path: str) -> dict[str, Any]:
    client = _get_client()
    try:
        # WHY: we override the per-request TTL to our 30-day window, ignoring
        # whatever max-age PokeAPI advertises (currently 86400 = 1 day).
        response = client.get(
            path,
            extensions={"hishel_ttl": float(CACHE_TTL_SECONDS)},
        )
    except httpx.TimeoutException as exc:
        raise PokeAPIError(
            f"PokeAPI no respondio a tiempo ({POKEAPI_TIMEOUT}s) "
            f"al consultar '{path}'."
        ) from exc
    except httpx.HTTPError as exc:
        raise PokeAPIError(
            f"Error de red al consultar PokeAPI ('{path}'): {exc}"
        ) from exc

    if response.status_code == 404:
        raise PokemonNotFoundError(path)
    if response.status_code >= 400:
        raise PokeAPIError(
            f"PokeAPI respondio con codigo {response.status_code} "
            f"al consultar '{path}'."
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise PokeAPIError(
            f"PokeAPI devolvio una respuesta no-JSON para '{path}'."
        ) from exc

    if not isinstance(payload, dict):
        raise PokeAPIError(
            f"PokeAPI devolvio JSON inesperado (no objeto) para '{path}'."
        )
    return payload


def _normalize_identifier(name_or_id: Union[str, int]) -> str:
    if isinstance(name_or_id, bool):
        raise PokeAPIError(
            f"Identificador invalido para PokeAPI: {name_or_id!r}"
        )
    if isinstance(name_or_id, int):
        if name_or_id <= 0:
            raise PokeAPIError(
                f"Identificador numerico invalido para PokeAPI: {name_or_id}"
            )
        return str(name_or_id)
    if isinstance(name_or_id, str):
        cleaned = name_or_id.strip().lower()
        if not cleaned:
            raise PokeAPIError("Identificador vacio para PokeAPI.")
        return cleaned
    raise PokeAPIError(
        f"Tipo de identificador no soportado: {type(name_or_id).__name__}"
    )


def get_pokemon(name_or_id: Union[str, int]) -> dict[str, Any]:
    """Fetch raw /pokemon/{id} response from PokeAPI (cached on disk)."""
    identifier = _normalize_identifier(name_or_id)
    try:
        return _request_json(f"/pokemon/{identifier}")
    except PokemonNotFoundError:
        raise PokemonNotFoundError(name_or_id) from None


def get_move(move_name: str) -> dict[str, Any]:
    """Fetch raw /move/{name} response from PokeAPI (cached on disk)."""
    identifier = _normalize_identifier(move_name)
    try:
        return _request_json(f"/move/{identifier}")
    except PokemonNotFoundError:
        # WHY: PokemonNotFoundError is the generic 404 here; for moves we
        # surface it as PokeAPIError so callers don't confuse it with a
        # missing Pokemon.
        raise PokeAPIError(
            f"Movimiento no encontrado en PokeAPI: '{move_name}'."
        ) from None


def reset_client() -> None:
    """Reset the cached httpx client. Intended for tests."""
    global _client
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
    _client = None
