from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from typing import Union

from pydantic import BaseModel, Field
from rich.console import Console

from pokemon_team_builder.config import LEGAL_POOL_FILE


class LegalPokemon(BaseModel):
    id: int = Field(ge=1)
    name: str = Field(min_length=1)


class LegalPool(BaseModel):
    regulation: str
    valid_until: date
    note: str | None = None
    pokemon: list[LegalPokemon]


@lru_cache(maxsize=1)
def _load_pool() -> LegalPool:
    with open(LEGAL_POOL_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return LegalPool.model_validate(raw)


@lru_cache(maxsize=1)
def _name_index() -> frozenset[str]:
    pool = _load_pool()
    return frozenset(p.name.lower() for p in pool.pokemon)


@lru_cache(maxsize=1)
def _id_index() -> frozenset[int]:
    pool = _load_pool()
    return frozenset(p.id for p in pool.pokemon)


def is_legal(name_or_id: Union[str, int]) -> bool:
    if isinstance(name_or_id, bool):
        # Guard: bool is a subclass of int in Python; reject explicitly.
        return False
    if isinstance(name_or_id, int):
        return name_or_id in _id_index()
    if isinstance(name_or_id, str):
        return name_or_id.strip().lower() in _name_index()
    return False


def valid_until() -> date:
    return _load_pool().valid_until


def get_all_names() -> list[str]:
    return [p.name for p in _load_pool().pokemon]


def check_pool_validity() -> None:
    try:
        expiry = valid_until()
    except Exception:
        # Loader will raise on first real call; don't crash on validity check.
        return
    if date.today() > expiry:
        Console(stderr=True).print(
            f"[yellow]warning:[/yellow] legal pool expired on "
            f"{expiry.isoformat()} — update legal_pool_mA.json"
        )
