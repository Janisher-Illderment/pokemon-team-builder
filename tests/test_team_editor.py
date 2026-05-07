from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from pokemon_team_builder.domain.models import (
    BaseStats,
    PokemonData,
    SPDistribution,
    TeamMember,
    TeamVariant,
)
from pokemon_team_builder.services.team_editor import apply_edit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mk_poke(
    name: str,
    moves: list[str] | None = None,
    abilities: list[str] | None = None,
    pid: int = 1,
    types: list[str] | None = None,
) -> PokemonData:
    return PokemonData(
        id=pid,
        name=name,
        types=types or ["normal"],
        base_stats=BaseStats(hp=80, atk=80, **{"def": 80}, spa=80, spd=80, spe=80),
        move_names=moves or [
            "tackle", "protect", "earthquake", "ice-beam",
            "flamethrower", "thunderbolt", "rock-slide",
        ],
        abilities=abilities or ["pressure"],
        weaknesses={},
    )


def _mk_member(
    pokemon: PokemonData,
    roles: list[str] | None = None,
    item: str = "Sitrus Berry",
    moves: list[str] | None = None,
) -> TeamMember:
    return TeamMember(
        pokemon=pokemon,
        role=roles or ["physical_sweeper"],
        sp_distribution=SPDistribution(),
        item=item,
        ability=pokemon.abilities[0],
        nature="Jolly",
        moves=moves or ["tackle", "protect", "earthquake", "ice-beam"],
    )


def _six_member_variant(overrides: dict[int, TeamMember] | None = None) -> TeamVariant:
    names = ["mon1", "mon2", "mon3", "mon4", "mon5", "mon6"]
    items = [
        "Sitrus Berry", "Lum Berry", "Focus Sash",
        "Rocky Helmet", "Leftovers", "Mental Herb",
    ]
    members = [
        _mk_member(_mk_poke(n, pid=i + 1), item=items[i])
        for i, n in enumerate(names)
    ]
    if overrides:
        for idx, m in overrides.items():
            members[idx] = m
    return TeamVariant(members=members)


def _patched_apply_edit(variant, member_index, edit, *, new_poke=None, is_legal_val=True):
    """Call apply_edit with viability_rater (and optionally lookup) mocked out."""
    import contextlib
    patches = [
        patch(
            "pokemon_team_builder.services.team_editor.viability_rater.score_team",
            return_value=(75.0, 0.5),
        ),
        patch(
            "pokemon_team_builder.services.team_editor.viability_rater.generate_explanation",
            return_value="Test explanation",
        ),
    ]
    if new_poke is not None:
        patches += [
            patch("pokemon_team_builder.services.team_editor.is_legal", return_value=is_legal_val),
            patch("pokemon_team_builder.services.team_editor.pokemon_lookup.lookup", return_value=new_poke),
            patch("pokemon_team_builder.services.team_editor.assign_role", return_value=["physical_sweeper"]),
            patch("pokemon_team_builder.services.team_editor.suggest_sp_distribution", return_value=SPDistribution()),
            patch("pokemon_team_builder.services.team_editor.select_moves_for_role",
                  return_value=["tackle", "protect", "earthquake", "ice-beam"]),
        ]
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        return apply_edit(variant, member_index, edit)


# ---------------------------------------------------------------------------
# move_swap — happy path
# ---------------------------------------------------------------------------

def test_move_swap_updates_correct_slot():
    variant = _six_member_variant()
    result = _patched_apply_edit(
        variant, 0,
        {"kind": "move_swap", "slot_index": 2, "new_move": "flamethrower"},
    )
    assert result.members[0].moves[2] == "flamethrower"
    # Other members unchanged
    for i in range(1, 6):
        assert result.members[i].moves == variant.members[i].moves


def test_move_swap_score_is_updated():
    variant = _six_member_variant()
    result = _patched_apply_edit(
        variant, 0,
        {"kind": "move_swap", "slot_index": 0, "new_move": "protect"},
    )
    assert result.score == 75.0
    assert result.score_explanation == "Test explanation"


# ---------------------------------------------------------------------------
# move_swap — error cases
# ---------------------------------------------------------------------------

def test_move_swap_invalid_slot_raises():
    variant = _six_member_variant()
    with pytest.raises(ValueError, match="slot_index"):
        _patched_apply_edit(
            variant, 0,
            {"kind": "move_swap", "slot_index": 4, "new_move": "tackle"},
        )


def test_move_swap_move_not_in_pool_raises():
    variant = _six_member_variant()
    with pytest.raises(ValueError, match="pool"):
        _patched_apply_edit(
            variant, 0,
            {"kind": "move_swap", "slot_index": 0, "new_move": "hydro-pump"},
        )


# ---------------------------------------------------------------------------
# item_swap — happy path
# ---------------------------------------------------------------------------

def test_item_swap_updates_item():
    variant = _six_member_variant()
    # "Choice Scarf" is not held by any member in the fixture
    result = _patched_apply_edit(
        variant, 0,
        {"kind": "item_swap", "new_item": "Choice Scarf"},
    )
    assert result.members[0].item == "Choice Scarf"


def test_item_swap_unique_item_applied():
    variant = _six_member_variant()
    result = _patched_apply_edit(
        variant, 0,
        {"kind": "item_swap", "new_item": "Choice Scarf"},
    )
    assert result.members[0].item == "Choice Scarf"
    for i in range(1, 6):
        assert result.members[i].item == variant.members[i].item


# ---------------------------------------------------------------------------
# item_swap — Item Clause violation
# ---------------------------------------------------------------------------

def test_item_swap_duplicate_raises():
    """Using an item already held by another member must raise ValueError."""
    variant = _six_member_variant()
    # mon2 holds "Lum Berry"
    with pytest.raises(ValueError, match="(?i)item|clause|lum berry"):
        _patched_apply_edit(
            variant, 0,
            {"kind": "item_swap", "new_item": "Lum Berry"},
        )


# ---------------------------------------------------------------------------
# pokemon_swap — happy path
# ---------------------------------------------------------------------------

def test_pokemon_swap_replaces_member():
    variant = _six_member_variant()
    new_poke = _mk_poke("garchomp", pid=99, moves=["tackle", "protect", "earthquake", "ice-beam"])

    result = _patched_apply_edit(
        variant, 0,
        {"kind": "pokemon_swap", "new_pokemon_name": "garchomp"},
        new_poke=new_poke,
    )
    assert result.members[0].pokemon.name == "garchomp"
    # Other members untouched
    for i in range(1, 6):
        assert result.members[i].pokemon.name == variant.members[i].pokemon.name


def test_pokemon_swap_preserves_item():
    """The swapped-in Pokemon inherits the outgoing member's item."""
    variant = _six_member_variant()
    new_poke = _mk_poke("gengar", pid=50)

    result = _patched_apply_edit(
        variant, 2,
        {"kind": "pokemon_swap", "new_pokemon_name": "gengar"},
        new_poke=new_poke,
    )
    # Member at index 2 had "Focus Sash"
    assert result.members[2].item == "Focus Sash"


# ---------------------------------------------------------------------------
# pokemon_swap — compatible role preservation
# ---------------------------------------------------------------------------

def test_pokemon_swap_preserves_compatible_role():
    """If new Pokemon supports the outgoing role, it should be kept."""
    outgoing = _mk_member(
        _mk_poke("old-mon", pid=1),
        roles=["special_sweeper"],
    )
    variant = _six_member_variant(overrides={0: outgoing})
    new_poke = _mk_poke("new-mon", pid=99)

    import contextlib
    with contextlib.ExitStack() as stack:
        stack.enter_context(
            patch("pokemon_team_builder.services.team_editor.viability_rater.score_team",
                  return_value=(70.0, 0.0))
        )
        stack.enter_context(
            patch("pokemon_team_builder.services.team_editor.viability_rater.generate_explanation",
                  return_value="")
        )
        stack.enter_context(
            patch("pokemon_team_builder.services.team_editor.is_legal", return_value=True)
        )
        stack.enter_context(
            patch("pokemon_team_builder.services.team_editor.pokemon_lookup.lookup",
                  return_value=new_poke)
        )
        # assign_role returns something that INCLUDES "special_sweeper"
        stack.enter_context(
            patch("pokemon_team_builder.services.team_editor.assign_role",
                  return_value=["special_sweeper", "lead_support"])
        )
        stack.enter_context(
            patch("pokemon_team_builder.services.team_editor.suggest_sp_distribution",
                  return_value=SPDistribution())
        )
        stack.enter_context(
            patch("pokemon_team_builder.services.team_editor.select_moves_for_role",
                  return_value=["tackle", "protect", "earthquake", "ice-beam"])
        )
        result = apply_edit(variant, 0, {"kind": "pokemon_swap", "new_pokemon_name": "new-mon"})

    assert "special_sweeper" in result.members[0].role


# ---------------------------------------------------------------------------
# pokemon_swap — fallback role when incompatible
# ---------------------------------------------------------------------------

def test_pokemon_swap_fallback_role_when_incompatible():
    """If no overlap between outgoing and new roles, use new Pokemon's first role."""
    outgoing = _mk_member(
        _mk_poke("old-mon", pid=1),
        roles=["trick_room_setter"],
    )
    variant = _six_member_variant(overrides={0: outgoing})
    new_poke = _mk_poke("new-mon", pid=99)

    import contextlib
    with contextlib.ExitStack() as stack:
        stack.enter_context(
            patch("pokemon_team_builder.services.team_editor.viability_rater.score_team",
                  return_value=(70.0, 0.0))
        )
        stack.enter_context(
            patch("pokemon_team_builder.services.team_editor.viability_rater.generate_explanation",
                  return_value="")
        )
        stack.enter_context(
            patch("pokemon_team_builder.services.team_editor.is_legal", return_value=True)
        )
        stack.enter_context(
            patch("pokemon_team_builder.services.team_editor.pokemon_lookup.lookup",
                  return_value=new_poke)
        )
        # assign_role returns roles that do NOT include "trick_room_setter"
        stack.enter_context(
            patch("pokemon_team_builder.services.team_editor.assign_role",
                  return_value=["physical_sweeper"])
        )
        stack.enter_context(
            patch("pokemon_team_builder.services.team_editor.suggest_sp_distribution",
                  return_value=SPDistribution())
        )
        stack.enter_context(
            patch("pokemon_team_builder.services.team_editor.select_moves_for_role",
                  return_value=["tackle", "protect", "earthquake", "ice-beam"])
        )
        result = apply_edit(variant, 0, {"kind": "pokemon_swap", "new_pokemon_name": "new-mon"})

    assert result.members[0].role == ["physical_sweeper"]


# ---------------------------------------------------------------------------
# pokemon_swap — error cases
# ---------------------------------------------------------------------------

def test_pokemon_swap_illegal_raises():
    variant = _six_member_variant()
    import contextlib
    with contextlib.ExitStack() as stack:
        stack.enter_context(
            patch("pokemon_team_builder.services.team_editor.viability_rater.score_team",
                  return_value=(70.0, 0.0))
        )
        stack.enter_context(
            patch("pokemon_team_builder.services.team_editor.viability_rater.generate_explanation",
                  return_value="")
        )
        stack.enter_context(
            patch("pokemon_team_builder.services.team_editor.is_legal", return_value=False)
        )
        with pytest.raises(ValueError, match="(?i)legal|pool"):
            apply_edit(variant, 0, {"kind": "pokemon_swap", "new_pokemon_name": "dragapult"})


def test_pokemon_swap_species_clause_raises():
    variant = _six_member_variant()
    # "mon2" is already in the team (index 1)
    import contextlib
    with contextlib.ExitStack() as stack:
        stack.enter_context(
            patch("pokemon_team_builder.services.team_editor.viability_rater.score_team",
                  return_value=(70.0, 0.0))
        )
        stack.enter_context(
            patch("pokemon_team_builder.services.team_editor.viability_rater.generate_explanation",
                  return_value="")
        )
        stack.enter_context(
            patch("pokemon_team_builder.services.team_editor.is_legal", return_value=True)
        )
        with pytest.raises(ValueError, match="(?i)species|mon2"):
            apply_edit(variant, 0, {"kind": "pokemon_swap", "new_pokemon_name": "mon2"})


# ---------------------------------------------------------------------------
# member_index validation
# ---------------------------------------------------------------------------

def test_member_index_out_of_range_raises():
    variant = _six_member_variant()
    with pytest.raises(ValueError, match="member_index"):
        _patched_apply_edit(variant, 6, {"kind": "move_swap", "slot_index": 0, "new_move": "tackle"})


def test_member_index_negative_raises():
    variant = _six_member_variant()
    with pytest.raises(ValueError, match="member_index"):
        _patched_apply_edit(variant, -1, {"kind": "move_swap", "slot_index": 0, "new_move": "tackle"})


# ---------------------------------------------------------------------------
# Non-edited members integrity
# ---------------------------------------------------------------------------

def test_other_members_byte_equal_after_move_swap():
    """A move_swap on member 0 must leave members 1-5 byte-identical."""
    variant = _six_member_variant()
    result = _patched_apply_edit(
        variant, 0,
        {"kind": "move_swap", "slot_index": 3, "new_move": "flamethrower"},
    )
    for i in range(1, 6):
        assert result.members[i].model_dump() == variant.members[i].model_dump()
