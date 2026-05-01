from __future__ import annotations

from typing import Any

import pytest

from pokemon_team_builder.domain.exceptions import (
    PokemonIllegalError,
    PokemonNotFoundError,
)
from pokemon_team_builder.domain.models import PokemonData
from pokemon_team_builder.services import pokemon_lookup


CHARIZARD_RAW: dict[str, Any] = {
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
        {"move": {"name": "earthquake"}},
    ],
    "abilities": [
        {"ability": {"name": "blaze"}, "is_hidden": False, "slot": 1},
        {"ability": {"name": "solar-power"}, "is_hidden": True, "slot": 3},
    ],
}


def test_lookup_charizard_returns_pokemon_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pokemon_lookup, "is_legal", lambda _: True)
    monkeypatch.setattr(
        pokemon_lookup.pokeapi_client,
        "get_pokemon",
        lambda _: CHARIZARD_RAW,
    )

    result = pokemon_lookup.lookup("charizard")

    assert isinstance(result, PokemonData)
    assert result.id == 6
    assert result.name == "charizard"
    assert result.types == ["fire", "flying"]
    assert result.base_stats.hp == 78
    assert result.base_stats.atk == 84
    assert result.base_stats.def_ == 78
    assert result.base_stats.spa == 109
    assert result.base_stats.spd == 85
    assert result.base_stats.spe == 100
    assert "flamethrower" in result.move_names
    assert isinstance(result.abilities, list)
    assert len(result.abilities) > 0
    assert "blaze" in result.abilities
    assert "rock" in result.weaknesses
    # Charizard (fire/flying) takes 4x rock damage.
    assert result.weaknesses["rock"] == pytest.approx(4.0)


def test_lookup_mewtwo_raises_illegal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # WHY: real legal_pool already excludes mewtwo, but we mock to keep the
    # test independent of pool data drift.
    monkeypatch.setattr(pokemon_lookup, "is_legal", lambda _: False)

    def _should_not_be_called(_: Any) -> Any:
        raise AssertionError("pokeapi_client.get_pokemon must not run for illegal Pokemon")

    monkeypatch.setattr(
        pokemon_lookup.pokeapi_client,
        "get_pokemon",
        _should_not_be_called,
    )

    with pytest.raises(PokemonIllegalError):
        pokemon_lookup.lookup("mewtwo")


def test_lookup_nonexistent_raises_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # We assume the name passes legality (e.g., legal pool would have it),
    # but PokeAPI says 404.
    monkeypatch.setattr(pokemon_lookup, "is_legal", lambda _: True)

    def _raise_404(name_or_id: Any) -> Any:
        raise PokemonNotFoundError(name_or_id)

    monkeypatch.setattr(
        pokemon_lookup.pokeapi_client, "get_pokemon", _raise_404
    )

    with pytest.raises(PokemonNotFoundError):
        pokemon_lookup.lookup("xyz_nonexistent")


def test_lookup_iron_valiant_is_illegal_paradox() -> None:
    # WHY: iron-valiant is a Paradox Pokemon, excluded by Regulation M-A.
    # No mocks here — relies on the real legal_pool_mA.json contents.
    with pytest.raises(PokemonIllegalError):
        pokemon_lookup.lookup("iron-valiant")


def test_calculate_weaknesses_rock_flying() -> None:
    # Rock/Flying defender:
    #   - water:    x2 (rock=2, flying=1)  -> 2
    #   - electric: x2 (rock=1, flying=2)  -> 2
    #   - ice:      x2 (rock=1, flying=2)  -> 2
    # NOTE: a common misconception is that Rock/Flying is x4 to water/electric/ice;
    # the canonical type chart only yields x2 (one type weak, the other neutral).
    weaknesses = pokemon_lookup.calculate_weaknesses(["rock", "flying"])
    assert weaknesses["water"] == pytest.approx(2.0)
    assert weaknesses["electric"] == pytest.approx(2.0)
    assert weaknesses["ice"] == pytest.approx(2.0)


def test_calculate_weaknesses_fire_flying_quadruple_to_rock() -> None:
    # Fire/Flying defender (e.g., Charizard) takes x4 from Rock attackers
    # because rock vs fire = 2 and rock vs flying = 2.
    weaknesses = pokemon_lookup.calculate_weaknesses(["fire", "flying"])
    assert weaknesses["rock"] == pytest.approx(4.0)


def test_calculate_weaknesses_ghost_normal_immunities() -> None:
    # Ghost is immune to normal+fighting; Normal is immune to ghost.
    # Defender Ghost/Normal:
    #   - normal attacker: x1 (vs normal) * x0 (vs ghost) = 0
    #   - fighting attacker: x2 (vs normal) * x0 (vs ghost) = 0
    weaknesses = pokemon_lookup.calculate_weaknesses(["ghost", "normal"])
    assert weaknesses["normal"] == pytest.approx(0.0)
    assert weaknesses["fighting"] == pytest.approx(0.0)


def test_calculate_weaknesses_single_type() -> None:
    weaknesses = pokemon_lookup.calculate_weaknesses(["fire"])
    assert weaknesses["water"] == pytest.approx(2.0)
    assert weaknesses["grass"] == pytest.approx(0.5)
    assert weaknesses["fire"] == pytest.approx(0.5)


def test_calculate_weaknesses_unknown_type_raises() -> None:
    with pytest.raises(ValueError):
        pokemon_lookup.calculate_weaknesses(["fakemon"])


def test_calculate_weaknesses_empty_raises() -> None:
    with pytest.raises(ValueError):
        pokemon_lookup.calculate_weaknesses([])
