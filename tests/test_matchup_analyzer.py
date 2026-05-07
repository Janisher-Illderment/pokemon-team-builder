from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from pokemon_team_builder.api.schemas import MatchupAnalysisResponse
from pokemon_team_builder.domain.models import BaseStats, PokemonData, SPDistribution, TeamMember
from pokemon_team_builder.services.matchup_analyzer import (
    ARCHETYPE_MAP,
    UnknownThreatError,
    analyze,
    resolve_threat,
    score_handler,
    suggest_adjustments,
)
from pokemon_team_builder.services.meta_service import MetaService


def _make_pokemon(
    name: str,
    types: list[str],
    weaknesses: dict[str, float] | None = None,
) -> PokemonData:
    return PokemonData(
        id=1,
        name=name,
        types=types,
        base_stats=BaseStats(hp=80, atk=80, **{"def": 80}, spa=80, spd=80, spe=80),
        move_names=["tackle", "growl", "scratch", "ember"],
        abilities=["run-away"],
        weaknesses=weaknesses or {},
    )


def _make_member(pokemon: PokemonData, roles: list[str]) -> TeamMember:
    return TeamMember(
        pokemon=pokemon,
        role=roles,
        sp_distribution=SPDistribution(),
        item="leftovers",
        ability="run-away",
        nature="hardy",
        moves=["tackle", "growl", "scratch", "ember"],
    )


# ── resolve_threat ────────────────────────────────────────────────────────────

def test_resolve_threat_direct_pokemon():
    indeedee = _make_pokemon("indeedee", ["psychic", "normal"])
    with patch("pokemon_team_builder.services.matchup_analyzer._lookup_pokemon", return_value=indeedee):
        result = resolve_threat("indeedee")
    assert len(result) == 1
    assert result[0].name == "indeedee"


def test_resolve_threat_archetype_trick_room():
    fake_mons = {
        "slowbro": _make_pokemon("slowbro", ["water", "psychic"]),
        "snorlax": _make_pokemon("snorlax", ["normal"]),
        "reuniclus": _make_pokemon("reuniclus", ["psychic"]),
        "aromatisse": _make_pokemon("aromatisse", ["fairy"]),
    }

    def mock_lookup(name: str) -> PokemonData | None:
        return fake_mons.get(name)

    with patch("pokemon_team_builder.services.matchup_analyzer._lookup_pokemon", side_effect=mock_lookup):
        result = resolve_threat("trick room")
    assert len(result) >= 1
    assert all(m.name in fake_mons for m in result)


def test_resolve_threat_unknown_raises():
    with patch("pokemon_team_builder.services.matchup_analyzer._lookup_pokemon", return_value=None):
        with pytest.raises(UnknownThreatError):
            resolve_threat("xyzabc123garbage")


# ── score_handler ─────────────────────────────────────────────────────────────

def test_primary_handler_identified_by_resistance():
    threat = _make_pokemon("trick-room-setter", ["psychic"])
    # dark type resists/is immune to psychic
    dark_mon = _make_pokemon("darkrai", ["dark"], weaknesses={"psychic": 0.0})
    dark_member = _make_member(dark_mon, ["physical_sweeper"])

    normal_mon = _make_pokemon("raticate", ["normal"], weaknesses={"psychic": 1.0})
    normal_member = _make_member(normal_mon, ["physical_sweeper"])

    dark_score, _ = score_handler(dark_member, [threat])
    normal_score, _ = score_handler(normal_member, [threat])
    assert dark_score > normal_score


def test_support_role_gets_bonus():
    threat = _make_pokemon("mon", ["normal"])
    support_mon = _make_pokemon("supporter", ["normal"])
    support_member = _make_member(support_mon, ["lead_support"])
    attacker_member = _make_member(_make_pokemon("attacker", ["normal"]), ["physical_sweeper"])

    sup_score, _ = score_handler(support_member, [threat])
    atk_score, _ = score_handler(attacker_member, [threat])
    assert sup_score > atk_score


# ── suggest_adjustments ───────────────────────────────────────────────────────

def test_move_swap_adjustment_generated():
    threat = _make_pokemon("psychic-mon", ["psychic"])
    member = _make_member(
        _make_pokemon("handler", ["normal"], weaknesses={"psychic": 2.0}),
        ["physical_sweeper"],
    )
    adjustments = suggest_adjustments(member, [threat], [], MetaService())
    move_swaps = [a for a in adjustments if a.type == "move_swap"]
    assert len(move_swaps) >= 1


def test_item_swap_adjustment_when_weak():
    threat = _make_pokemon("fire-attacker", ["fire"])
    member = _make_member(
        _make_pokemon("handler", ["grass"], weaknesses={"fire": 2.0}),
        ["physical_sweeper"],
    )
    adjustments = suggest_adjustments(member, [threat], [], MetaService())
    item_swaps = [a for a in adjustments if a.type == "item_swap"]
    assert len(item_swaps) >= 1
    assert "Occa Berry" in [a.change for a in item_swaps]


# ── full analyze ──────────────────────────────────────────────────────────────

def test_analyze_returns_response_with_handlers():
    fake_team_mons = {n: _make_pokemon(n, ["normal"]) for n in ["mon1", "mon2", "mon3", "mon4", "mon5", "mon6"]}
    fake_team_mons["mon1"] = _make_pokemon("mon1", ["dark"], weaknesses={"psychic": 0.0})
    threat_mon = _make_pokemon("indeedee", ["psychic", "normal"])

    def mock_lookup(name: str) -> PokemonData | None:
        if name == "indeedee":
            return threat_mon
        return fake_team_mons.get(name)

    with patch("pokemon_team_builder.services.matchup_analyzer._lookup_pokemon", side_effect=mock_lookup):
        result = analyze(
            team_names=list(fake_team_mons.keys()),
            threat="indeedee",
            meta_service=MetaService(),
        )

    assert isinstance(result, MatchupAnalysisResponse)
    assert result.primary_handler != ""
    assert result.weakness_summary != ""
