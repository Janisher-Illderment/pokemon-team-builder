from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from pokemon_team_builder.domain.models import (
    BaseStats,
    PokemonData,
    SPDistribution,
    TeamMember,
    TeamVariant,
)
from pokemon_team_builder.main import app
from pokemon_team_builder.services import pokemon_lookup

client = TestClient(app)


def _mk(
    name: str,
    types: list[str],
    *,
    hp: int = 80,
    atk: int = 80,
    def_: int = 80,
    spa: int = 80,
    spd: int = 80,
    spe: int = 80,
    moves: list[str] | None = None,
    abilities: list[str] | None = None,
    pid: int = 1,
) -> PokemonData:
    return PokemonData(
        id=pid,
        name=name,
        types=types,
        base_stats=BaseStats(
            hp=hp, atk=atk, **{"def": def_}, spa=spa, spd=spd, spe=spe
        ),
        move_names=moves or ["protect", "earthquake", "ice-beam", "rock-slide"],
        abilities=abilities or ["pressure"],
        weaknesses=pokemon_lookup.calculate_weaknesses(types),
    )


def _fake_member(name: str, pid: int = 1) -> TeamMember:
    return TeamMember(
        pokemon=_mk(name, ["normal"], pid=pid),
        role=["physical_sweeper"],
        sp_distribution=SPDistribution(),
        item="life-orb",
        ability="pressure",
        nature="jolly",
        moves=["protect", "earthquake", "ice-beam", "rock-slide"],
    )


def _fake_variant(recommended: bool = False, score: float = 1.0) -> TeamVariant:
    members = [
        _fake_member("garchomp", pid=1),
        _fake_member("incineroar", pid=2),
        _fake_member("rillaboom", pid=3),
        _fake_member("urshifu", pid=4),
        _fake_member("kyogre", pid=5),
        _fake_member("calyrex", pid=6),
    ]
    return TeamVariant(members=members, score=score, is_recommended=recommended)


def test_health_returns_200():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_generate_unknown_anchor_returns_422():
    with patch("pokemon_team_builder.api.router.is_legal", return_value=False):
        res = client.post("/generate", json={"anchor": "missingno"})
    assert res.status_code == 422
    assert "not in the M-A regulation pool" in res.json()["detail"]


def test_generate_valid_anchor_returns_variants():
    fake_anchor = _mk("garchomp", ["dragon", "ground"], pid=445)
    fake_variants = [_fake_variant(recommended=True, score=5.5)]

    with (
        patch("pokemon_team_builder.api.router.is_legal", return_value=True),
        patch("pokemon_team_builder.api.router.pokemon_lookup.lookup", return_value=fake_anchor),
        patch("pokemon_team_builder.api.router.generate_team", return_value=fake_variants),
    ):
        res = client.post("/generate", json={"anchor": "garchomp", "variants": 1})

    assert res.status_code == 200
    body = res.json()
    assert body["anchor"] == "garchomp"
    assert len(body["variants"]) == 1
    v = body["variants"][0]
    assert v["recommended"] is True
    assert v["score"] == 5.5
    assert len(v["members"]) == 6
    assert "pokepaste" in v
