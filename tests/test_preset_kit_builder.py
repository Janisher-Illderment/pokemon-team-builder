"""Tests for preset_kit_builder (v0.10.1, 2026-05-15).

Regression for Sergio's feedback: the Ofensivo/Defensivo toggle must
swap item + ability + nature + moves + SPs, not just SPs. The kit
builder is the canonical place that diff happens.
"""

from __future__ import annotations

import pytest

from pokemon_team_builder.domain.models import (
    BaseStats,
    PokemonData,
    SPDistribution,
)
from pokemon_team_builder.services.preset_kit_builder import (
    PresetKit,
    build_kits,
)


def _mk(
    name: str,
    types: list[str],
    *,
    atk: int = 80,
    spa: int = 80,
    spe: int = 80,
    hp: int = 80,
    def_: int = 80,
    spd: int = 80,
    moves: list[str] | None = None,
    abilities: list[str] | None = None,
) -> PokemonData:
    return PokemonData(
        id=1,
        name=name,
        types=types,
        base_stats=BaseStats(hp=hp, atk=atk, **{"def": def_}, spa=spa, spd=spd, spe=spe),
        move_names=moves or ["protect", "tackle", "swords-dance"],
        abilities=abilities or ["overgrow"],
        weaknesses={},
    )


def _sp(**kwargs: int) -> SPDistribution:
    """Build an SPDistribution using only the explicitly passed stats.

    Sums must not exceed the 66-cap per Champions Reg M-A; tests pass in
    small focused distributions to stay under it.
    """
    base = {"hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}
    base.update(kwargs)
    return SPDistribution(**base)


def test_offensive_kit_mirrors_input() -> None:
    """The offensive kit is the generated build unchanged."""
    p = _mk("garchomp", ["dragon", "ground"], atk=130, spe=102,
            moves=["protect", "earthquake", "dragon-claw", "swords-dance"],
            abilities=["rough-skin"])
    kits = build_kits(
        p,
        item="Sitrus Berry",
        ability="rough-skin",
        nature="Jolly",
        moves=["protect", "earthquake", "dragon-claw", "swords-dance"],
        sp_distribution=_sp(atk=32, spe=32, hp=2),
    )
    off = kits["offensive"]
    assert off.item == "Sitrus Berry"
    assert off.ability == "rough-skin"
    assert off.nature == "Jolly"
    assert off.moves == ["protect", "earthquake", "dragon-claw", "swords-dance"]


def test_defensive_kit_swaps_setup_for_recovery() -> None:
    """Slot 4 setup move becomes a recovery move when one exists."""
    p = _mk("slowking", ["water", "psychic"],
            atk=75, spa=100, spe=30,
            moves=["protect", "scald", "psychic", "calm-mind", "slack-off"],
            abilities=["regenerator", "oblivious"])
    kits = build_kits(
        p,
        item="Mirror Herb",
        ability="oblivious",
        nature="Modest",
        moves=["protect", "scald", "psychic", "calm-mind"],
        sp_distribution=_sp(spa=32, hp=32, spe=2),
    )
    deff = kits["defensive"]
    assert "calm-mind" not in deff.moves
    assert "slack-off" in deff.moves


def test_defensive_kit_picks_regenerator_when_available() -> None:
    """Defensive HA selection: Regenerator beats the offensive ability."""
    p = _mk("slowking", ["water", "psychic"],
            atk=75, spa=100, spe=30,
            moves=["protect", "scald", "psychic", "calm-mind"],
            abilities=["regenerator", "oblivious"])
    kits = build_kits(
        p,
        item="Mirror Herb",
        ability="oblivious",
        nature="Modest",
        moves=["protect", "scald", "psychic", "calm-mind"],
        sp_distribution=_sp(spa=32, hp=32, spe=2),
    )
    assert kits["defensive"].ability == "regenerator"


def test_defensive_kit_picks_calm_for_special_attacker() -> None:
    p = _mk("alakazam", ["psychic"], atk=50, spa=135, spe=120,
            moves=["protect", "psychic", "shadow-ball", "calm-mind"],
            abilities=["magic-guard"])
    kits = build_kits(
        p,
        item="Mirror Herb",
        ability="magic-guard",
        nature="Timid",
        moves=["protect", "psychic", "shadow-ball", "calm-mind"],
        sp_distribution=_sp(spa=32, spe=32, hp=2),
    )
    assert kits["defensive"].nature == "Calm"


def test_defensive_kit_picks_impish_for_physical_attacker() -> None:
    p = _mk("garchomp", ["dragon", "ground"], atk=130, spa=80, spe=102,
            moves=["protect", "earthquake", "dragon-claw", "swords-dance"],
            abilities=["rough-skin"])
    kits = build_kits(
        p,
        item="Sitrus Berry",
        ability="rough-skin",
        nature="Jolly",
        moves=["protect", "earthquake", "dragon-claw", "swords-dance"],
        sp_distribution=_sp(atk=32, spe=32, hp=2),
    )
    assert kits["defensive"].nature == "Impish"


def test_defensive_kit_swaps_item_when_offense_item() -> None:
    """A non-defensive item gets replaced in the defensive kit.

    Scope Lens is offensive (crit-rate boost); the defensive kit must
    pivot to Mental Herb — first entry in the v0.10.3 defensive pool.
    """
    p = _mk("garchomp", ["dragon", "ground"], atk=130, spe=102,
            moves=["protect", "earthquake", "dragon-claw", "swords-dance"],
            abilities=["rough-skin"])
    kits = build_kits(
        p,
        item="Scope Lens",
        ability="rough-skin",
        nature="Jolly",
        moves=["protect", "earthquake", "dragon-claw", "swords-dance"],
        sp_distribution=_sp(atk=32, spe=32, hp=2),
    )
    assert kits["defensive"].item != "Scope Lens"
    assert kits["defensive"].item == "Mental Herb"  # first fallback v0.10.3


def test_defensive_kit_keeps_already_defensive_item() -> None:
    """If the offensive item already belongs to the defensive pool, keep it.

    Oran Berry is in the v0.10.3 defensive pool — must be preserved.
    """
    p = _mk("garchomp", ["dragon", "ground"], atk=130, spe=102,
            moves=["protect", "earthquake", "dragon-claw", "swords-dance"],
            abilities=["rough-skin"])
    kits = build_kits(
        p,
        item="Oran Berry",
        ability="rough-skin",
        nature="Jolly",
        moves=["protect", "earthquake", "dragon-claw", "swords-dance"],
        sp_distribution=_sp(atk=32, spe=32, hp=2),
    )
    assert kits["defensive"].item == "Oran Berry"


def test_defensive_kit_respects_team_used_items() -> None:
    """Item Clause carries over: a used defensive item is skipped.

    When Mental Herb is already taken by another defensive kit on the
    team, this kit falls through to Oran Berry (next entry).
    """
    p = _mk("garchomp", ["dragon", "ground"], atk=130, spe=102,
            moves=["protect", "earthquake", "dragon-claw", "swords-dance"],
            abilities=["rough-skin"])
    kits = build_kits(
        p,
        item="Scope Lens",
        ability="rough-skin",
        nature="Jolly",
        moves=["protect", "earthquake", "dragon-claw", "swords-dance"],
        sp_distribution=_sp(atk=32, spe=32, hp=2),
        defensive_used_items={"Mental Herb"},
    )
    assert kits["defensive"].item == "Oran Berry"


def test_defensive_kit_keeps_utility_slot4() -> None:
    """Slot 4 utility moves (Tailwind etc.) are kept, not replaced."""
    p = _mk("whimsicott", ["grass", "fairy"], atk=67, spa=77, spe=116,
            moves=["protect", "moonblast", "energy-ball", "tailwind", "moonlight"],
            abilities=["prankster"])
    kits = build_kits(
        p,
        item="Mental Herb",
        ability="prankster",
        nature="Timid",
        moves=["protect", "moonblast", "energy-ball", "tailwind"],
        sp_distribution=_sp(spa=32, spe=32, hp=2),
    )
    # Tailwind is not in _OFFENSIVE_SLOT4_MOVES so it stays.
    assert kits["defensive"].moves[3] == "tailwind"


def test_defensive_kit_keeps_offensive_when_no_recovery_known() -> None:
    """No recovery / status in the move pool → slot 4 unchanged."""
    p = _mk("smallmon", ["normal"], atk=120, spe=100,
            moves=["protect", "body-slam", "earthquake", "swords-dance"],
            abilities=["scrappy"])
    kits = build_kits(
        p,
        item="Scope Lens",
        ability="scrappy",
        nature="Jolly",
        moves=["protect", "body-slam", "earthquake", "swords-dance"],
        sp_distribution=_sp(atk=32, spe=32, hp=2),
    )
    # No recovery available → slot 4 setup stays. The kit is still
    # "defensive" in nature / item / sp_distribution.
    assert kits["defensive"].moves[3] == "swords-dance"
