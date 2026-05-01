from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Union

from pokemon_team_builder.config import TYPE_CHART_FILE
from pokemon_team_builder.data import pokeapi_client
from pokemon_team_builder.data.legal_pool_loader import is_legal
from pokemon_team_builder.domain.exceptions import (
    PokeAPIError,
    PokemonIllegalError,
    PokemonNotFoundError,
)
from pokemon_team_builder.domain.models import BaseStats, PokemonData


@lru_cache(maxsize=1)
def _load_type_chart() -> dict[str, dict[str, float]]:
    with open(TYPE_CHART_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise PokeAPIError("type_chart.json: estructura raiz invalida.")
    chart: dict[str, dict[str, float]] = {}
    for attacker, row in raw.items():
        if not isinstance(row, dict):
            raise PokeAPIError(
                f"type_chart.json: fila invalida para '{attacker}'."
            )
        chart[attacker] = {
            defender: float(multiplier)
            for defender, multiplier in row.items()
        }
    return chart


def calculate_weaknesses(types: list[str]) -> dict[str, float]:
    """Return ``attacker_type -> damage_multiplier`` for a defender.

    Uses ``data/type_chart.json`` keyed as ``attacker -> defender -> mult``.
    For dual-type defenders the multipliers from both defending types are
    multiplied together.
    """
    if not types:
        raise ValueError("types must contain at least one element")
    if len(types) > 2:
        raise ValueError("a Pokemon can have at most 2 types")

    chart = _load_type_chart()
    normalized_types = [t.lower() for t in types]
    for t in normalized_types:
        if t not in chart:
            raise ValueError(f"unknown type: '{t}'")

    result: dict[str, float] = {}
    for attacker in chart.keys():
        attacker_row = chart[attacker]
        multiplier = 1.0
        for defender in normalized_types:
            multiplier *= attacker_row.get(defender, 1.0)
        result[attacker] = multiplier
    return result


def _extract_types(raw: dict[str, Any]) -> list[str]:
    types_field = raw.get("types")
    if not isinstance(types_field, list) or not types_field:
        raise PokeAPIError("Respuesta PokeAPI: campo 'types' invalido.")
    out: list[str] = []
    for entry in types_field:
        if not isinstance(entry, dict):
            raise PokeAPIError("Respuesta PokeAPI: 'types[i]' no es objeto.")
        type_obj = entry.get("type")
        if not isinstance(type_obj, dict):
            raise PokeAPIError(
                "Respuesta PokeAPI: 'types[i].type' no es objeto."
            )
        name = type_obj.get("name")
        if not isinstance(name, str) or not name:
            raise PokeAPIError(
                "Respuesta PokeAPI: 'types[i].type.name' invalido."
            )
        out.append(name.lower())
    return out


def _extract_base_stats(raw: dict[str, Any]) -> BaseStats:
    stats_field = raw.get("stats")
    if not isinstance(stats_field, list):
        raise PokeAPIError("Respuesta PokeAPI: campo 'stats' invalido.")
    # PokeAPI uses these slugs; map to our model names.
    pokeapi_to_model = {
        "hp": "hp",
        "attack": "atk",
        "defense": "def",
        "special-attack": "spa",
        "special-defense": "spd",
        "speed": "spe",
    }
    collected: dict[str, int] = {}
    for entry in stats_field:
        if not isinstance(entry, dict):
            raise PokeAPIError("Respuesta PokeAPI: 'stats[i]' no es objeto.")
        stat_obj = entry.get("stat")
        base = entry.get("base_stat")
        if not isinstance(stat_obj, dict) or not isinstance(base, int):
            raise PokeAPIError("Respuesta PokeAPI: 'stats[i]' incompleto.")
        slug = stat_obj.get("name")
        if slug in pokeapi_to_model:
            collected[pokeapi_to_model[slug]] = base
    missing = set(pokeapi_to_model.values()) - set(collected.keys())
    if missing:
        raise PokeAPIError(
            f"Respuesta PokeAPI: faltan stats {sorted(missing)}."
        )
    return BaseStats.model_validate(collected)


def _extract_abilities(raw: dict[str, Any]) -> list[str]:
    """Extract ability slugs from PokeAPI ``abilities`` block.

    Structure: ``[{"ability": {"name": "speed-boost"}, "is_hidden": false, "slot": 1}, ...]``.
    Returned in slot order; hidden abilities included.
    """
    abilities_field = raw.get("abilities")
    if not isinstance(abilities_field, list):
        return []
    # WHY: PokeAPI usually returns slot 1, slot 2, then hidden (slot 3) — we
    # respect that order. If slot is missing we fall back to list order.
    entries: list[tuple[int, str]] = []
    for idx, entry in enumerate(abilities_field):
        if not isinstance(entry, dict):
            continue
        ab_obj = entry.get("ability")
        if not isinstance(ab_obj, dict):
            continue
        name = ab_obj.get("name")
        if not isinstance(name, str) or not name:
            continue
        slot = entry.get("slot")
        order = slot if isinstance(slot, int) else idx
        entries.append((order, name.lower()))
    entries.sort(key=lambda pair: pair[0])
    seen: set[str] = set()
    out: list[str] = []
    for _, name in entries:
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def _extract_move_names(raw: dict[str, Any]) -> list[str]:
    moves_field = raw.get("moves")
    if not isinstance(moves_field, list):
        raise PokeAPIError("Respuesta PokeAPI: campo 'moves' invalido.")
    names: list[str] = []
    for entry in moves_field:
        if not isinstance(entry, dict):
            continue
        move_obj = entry.get("move")
        if not isinstance(move_obj, dict):
            continue
        name = move_obj.get("name")
        if isinstance(name, str) and name:
            names.append(name.lower())
    # WHY: dedupe while preserving order; PokeAPI rarely repeats but cheap to be safe.
    seen: set[str] = set()
    unique: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            unique.append(n)
    return unique


def lookup(name_or_id: Union[str, int]) -> PokemonData:
    """Resolve a Pokemon by name or ID into a fully-populated ``PokemonData``.

    Steps:
    1. Reject if not legal in the current regulation pool.
    2. Fetch raw data from PokeAPI (cached).
    3. Parse types, base stats, and move names.
    4. Compute ``weaknesses`` from the static type chart.
    """
    if not is_legal(name_or_id):
        raise PokemonIllegalError(name_or_id)

    try:
        raw = pokeapi_client.get_pokemon(name_or_id)
    except PokemonNotFoundError:
        raise PokemonNotFoundError(name_or_id) from None

    pid = raw.get("id")
    if not isinstance(pid, int):
        raise PokeAPIError("Respuesta PokeAPI: campo 'id' invalido.")
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise PokeAPIError("Respuesta PokeAPI: campo 'name' invalido.")

    types = _extract_types(raw)
    base_stats = _extract_base_stats(raw)
    move_names = _extract_move_names(raw)
    abilities = _extract_abilities(raw)
    weaknesses = calculate_weaknesses(types)

    return PokemonData(
        id=pid,
        name=name.lower(),
        types=types,
        base_stats=base_stats,
        move_names=move_names,
        abilities=abilities,
        weaknesses=weaknesses,
    )
