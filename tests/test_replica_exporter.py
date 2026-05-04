from __future__ import annotations

from pathlib import Path

import pytest

from pokemon_team_builder.domain.models import (
    BaseStats,
    PokemonData,
    SPDistribution,
    TeamMember,
    TeamVariant,
)
from pokemon_team_builder.services import pokemon_lookup
from pokemon_team_builder.services.replica_exporter import (
    IMPORT_INSTRUCTIONS,
    save_to_file,
    select_moves_for_role,
    to_pokepaste,
)


def _mk_pokemon(
    name: str,
    types: list[str],
    moves: list[str],
    *,
    pid: int = 1,
    abilities: list[str] | None = None,
) -> PokemonData:
    return PokemonData(
        id=pid,
        name=name,
        types=types,
        base_stats=BaseStats(hp=70, atk=70, **{"def": 70}, spa=70, spd=70, spe=70),
        move_names=moves,
        abilities=abilities or ["pressure"],
        weaknesses=pokemon_lookup.calculate_weaknesses(types),
    )


def _mk_member(
    pokemon: PokemonData,
    *,
    item: str,
    nature: str = "Jolly",
    moves: list[str],
    sp: SPDistribution | None = None,
) -> TeamMember:
    if sp is None:
        sp = SPDistribution.model_validate({"atk": 32, "spe": 32, "hp": 2})
    return TeamMember(
        pokemon=pokemon,
        role=["physical_sweeper"],
        sp_distribution=sp,
        item=item,
        ability=pokemon.abilities[0],
        nature=nature,
        moves=moves,
    )


def _basic_variant() -> TeamVariant:
    pokemons = [
        _mk_pokemon(
            f"poke-{i}",
            ["fire"],
            moves=["protect", "flamethrower", "earthquake", "tailwind"],
            pid=i + 1,
        )
        for i in range(6)
    ]
    items = [
        "Weakness Policy",
        "Focus Sash",
        "Sitrus Berry",
        "Leftovers",
        "Rocky Helmet",
        "Choice Scarf",
    ]
    members = [
        _mk_member(
            p,
            item=item,
            moves=["protect", "flamethrower", "earthquake", "tailwind"],
        )
        for p, item in zip(pokemons, items)
    ]
    return TeamVariant(members=members)


def test_select_moves_for_role_includes_protect_first() -> None:
    pokemon = _mk_pokemon(
        "talonflame",
        ["fire", "flying"],
        moves=[
            "protect",
            "tailwind",
            "brave-bird",
            "flamethrower",
            "earthquake",
            "u-turn",
        ],
    )
    moves = select_moves_for_role(pokemon, ["lead_support"])
    assert moves[0] == "protect"
    assert len(moves) == 4


def test_select_moves_for_role_picks_role_move() -> None:
    pokemon = _mk_pokemon(
        "talonflame",
        ["fire", "flying"],
        moves=["tailwind", "brave-bird", "flamethrower", "earthquake"],
    )
    moves = select_moves_for_role(pokemon, ["lead_support"])
    assert "tailwind" in moves


def test_sp_values_written_raw() -> None:
    # Champions uses raw SP values (max 32) in the EVs: line, not ×8.
    pokemon = _mk_pokemon(
        "garchomp",
        ["dragon", "ground"],
        moves=["protect", "earthquake", "dragon-claw", "swords-dance"],
    )
    member = _mk_member(
        pokemon,
        item="Weakness Policy",
        nature="Jolly",
        moves=["protect", "earthquake", "dragon-claw", "swords-dance"],
        sp=SPDistribution.model_validate({"atk": 32, "spe": 32, "hp": 2}),
    )
    variant = TeamVariant(members=[member] * 6)
    paste = to_pokepaste(variant)
    assert "32 Atk" in paste
    assert "32 Spe" in paste
    assert "2 HP" in paste
    assert "252" not in paste


def test_pokepaste_has_level_50() -> None:
    variant = _basic_variant()
    paste = to_pokepaste(variant)
    assert paste.count("Level: 50") == 6


def test_pokepaste_no_ivs_line() -> None:
    variant = _basic_variant()
    paste = to_pokepaste(variant)
    assert "IVs:" not in paste


def test_pokepaste_protect_in_slot_1() -> None:
    variant = _basic_variant()
    paste = to_pokepaste(variant)
    blocks = paste.split("\n\n")
    assert len(blocks) == 6
    for block in blocks:
        lines = block.split("\n")
        # First move line is the first line that begins with "- ".
        move_lines = [line for line in lines if line.startswith("- ")]
        assert move_lines, f"no moves in block:\n{block}"
        assert move_lines[0] == "- Protect"


def test_pokepaste_6_pokemon_blocks() -> None:
    variant = _basic_variant()
    paste = to_pokepaste(variant)
    blocks = paste.split("\n\n")
    assert len(blocks) == 6


def test_save_to_file_raises_if_exists(tmp_path: Path) -> None:
    target = tmp_path / "team.txt"
    target.write_text("old content", encoding="utf-8")
    with pytest.raises(FileExistsError):
        save_to_file("new content", target, force=False)


def test_save_to_file_force_overwrites(tmp_path: Path) -> None:
    target = tmp_path / "team.txt"
    target.write_text("old content", encoding="utf-8")
    save_to_file("new content", target, force=True)
    assert target.read_text(encoding="utf-8") == "new content"


def test_save_to_file_creates_when_missing(tmp_path: Path) -> None:
    target = tmp_path / "team.txt"
    save_to_file("hello", target, force=False)
    assert target.read_text(encoding="utf-8") == "hello"


def test_import_instructions_mentions_replica_team() -> None:
    assert "Replica Team" in IMPORT_INSTRUCTIONS


def test_select_moves_for_role_skips_same_type_in_slot3() -> None:
    """Slot 3 must be cross-type coverage, not the Pokemon's own STAB.

    Regression: the previous filter used ``candidate.startswith(t)`` so
    a fire-type with ``flamethrower`` in its move pool could still slip
    through if the slug ordering hid the prefix. With the explicit
    move->type table, ``flamethrower`` (fire) is excluded for a fire
    Pokemon and ``earthquake`` (ground) is picked instead.
    """
    pokemon = _mk_pokemon(
        "charmander",
        ["fire"],
        moves=["protect", "flamethrower", "earthquake", "tackle"],
    )
    moves = select_moves_for_role(pokemon, ["physical_sweeper"])
    # Slot 2 (STAB) is flamethrower; slot 3 (coverage) must NOT be it.
    assert moves[1] == "flamethrower"
    assert moves[2] != "flamethrower"
    assert moves[2] == "earthquake"


def test_pokepaste_preserves_hyphen_in_species_name() -> None:
    """Species variants like ``rotom-wash`` keep their hyphen in the paste.

    Regression: ``_format_name`` would turn ``rotom-wash`` into
    ``Rotom Wash``, which PikaChampions / champteams.gg do not accept
    as a valid species. The new ``_format_species`` keeps the hyphen
    so the import resolves to the Wash form.
    """
    pokemon = _mk_pokemon(
        "rotom-wash",
        ["electric", "water"],
        moves=["protect", "thunderbolt", "hydro-pump", "will-o-wisp"],
    )
    member = _mk_member(
        pokemon,
        item="Sitrus Berry",
        nature="Calm",
        moves=["protect", "thunderbolt", "hydro-pump", "will-o-wisp"],
    )
    variant = TeamVariant(members=[member] * 6)
    paste = to_pokepaste(variant)
    assert "Rotom-Wash @" in paste
    assert "Rotom Wash @" not in paste


def test_fallback_move_avoids_duplicate_when_tackle_in_used() -> None:
    """_fallback_move must not return a move that is already in ``used``."""
    from pokemon_team_builder.services.replica_exporter import _fallback_move

    # Pool exhausted; "tackle" is already used.
    pool: list[str] = []
    used = {"protect", "tackle"}
    result = _fallback_move(pool, used)
    assert result not in used


def test_earthquake_not_first_coverage_priority() -> None:
    """EQ must not be slot-3 when safer coverage exists (hits ally in Doubles)."""
    # A ground-immune special attacker with full coverage pool should get
    # ice-beam/thunderbolt/etc before earthquake.
    # NOTE: _mk_pokemon ties atk == spa, so primary_cat resolves to physical;
    # we include "rock-slide" in the pool so that the strict-physical pass
    # has a non-earthquake physical option to pick first.
    pokemon = _mk_pokemon(
        "gardevoir",
        ["psychic", "fairy"],
        moves=[
            "protect",
            "moonblast",
            "ice-beam",
            "earthquake",
            "thunderbolt",
            "rock-slide",
        ],
    )
    moves = select_moves_for_role(pokemon, ["special_sweeper"])
    # ice-beam or thunderbolt or rock-slide should win over earthquake as slot 3
    assert moves[2] != "earthquake"


def test_outrage_not_in_dragon_stab() -> None:
    """Outrage must never appear — random target in Doubles."""
    from pokemon_team_builder.services.replica_exporter import _STAB_BY_TYPE
    assert "outrage" not in _STAB_BY_TYPE["dragon"]


def test_select_moves_slot4_uses_secondary_role() -> None:
    """Slot 4 should pick a role move from secondary roles when primary has none."""
    # Primary role "physical_sweeper" has no swords-dance/dragon-dance in pool.
    # Secondary role "redirect" has "follow-me" in pool.
    pokemon = _mk_pokemon(
        "togekiss",
        ["fairy", "flying"],
        moves=["protect", "dazzling-gleam", "air-slash", "follow-me"],
    )
    # physical_sweeper as primary (atk heuristic), but also redirect role.
    moves = select_moves_for_role(pokemon, ["physical_sweeper", "redirect"])
    assert "follow-me" in moves


# ---------------------------------------------------------------------------
# fix-logic-v1 — T6, T7, T8, T10 regression tests
# ---------------------------------------------------------------------------


def test_fallback_move_raises_when_pool_and_generics_exhausted() -> None:
    """T6: _fallback_move raises TeamBuildError instead of returning a duplicate.

    Previously the function fell back to ``return "tackle"`` even when
    every generic ("tackle", "scratch", "pound", "growl", "leer") was
    already in ``used``, silently emitting a moveset with two copies of
    "tackle". That is invalid in PikaChampions / Showdown.
    """
    from pokemon_team_builder.domain.exceptions import TeamBuildError
    from pokemon_team_builder.services.replica_exporter import _fallback_move

    pool: list[str] = []
    used = {"protect", "tackle", "scratch", "pound", "growl", "leer"}
    with pytest.raises(TeamBuildError, match="move pool"):
        _fallback_move(pool, used)


def test_unknown_category_not_chosen_pass0() -> None:
    """T7: a move missing from _MOVE_CATEGORY is ineligible during pass 0.

    When the Pokemon's primary attack category is "physical" and a known
    physical move is available, an uncategorized fallback move must NOT
    win over it. The earlier guard ``cand_cat and cand_cat != primary_cat``
    accepted unknown-category moves into pass 0, breaking strict matching.
    """
    # Build a fake STAB list with one uncategorized move, then the canonical
    # categorized one. We don't actually patch the table — instead we
    # exercise the existing one with a Pokemon whose pool guarantees a
    # known physical STAB winner over an unknown sibling.
    pokemon = _mk_pokemon(
        "physical-fire",
        ["fire"],
        moves=[
            "protect",
            # ``ember`` is in _STAB_BY_TYPE but ``_MOVE_CATEGORY[ember]`` is
            # "special" → pass 0 must reject it on a physical attacker.
            # ``fire-punch`` is physical → that's what slot 2 must pick.
            "ember",
            "fire-punch",
            "earthquake",
        ],
    )
    # Force primary_cat physical: atk equal, spa lower. (The fixture's
    # _mk_pokemon sets atk=spa=70; we need atk >= spa for physical primary.
    # _mk_pokemon already does atk=spa, so primary_cat resolves to physical
    # via the >= tiebreak.)
    moves = select_moves_for_role(pokemon, ["physical_sweeper"])
    # Slot 2 (STAB) on a physical attacker must be a categorized physical
    # STAB, not the special ember nor an unknown move.
    assert moves[1] == "fire-punch", moves


def test_protect_replaced_when_not_in_learnset() -> None:
    """T8: Pokemon without Protect get a fallback in slot 1, not "protect".

    A handful of legal mons don't learn Protect at all. Hard-coding it
    in slot 1 produces a moveset that PikaChampions silently rejects.
    """
    pokemon = _mk_pokemon(
        "no-protect",
        ["normal"],
        moves=["body-slam", "earthquake", "ice-beam", "tackle"],
    )
    moves = select_moves_for_role(pokemon, ["physical_sweeper"])
    assert moves[0] != "protect", (
        f"slot 1 emitted 'protect' even though it isn't in the move pool: "
        f"{moves}"
    )
    # Whatever filled slot 1 must come from the move pool.
    assert moves[0] in pokemon.move_names


def test_format_species_kommo_o() -> None:
    """T10: kommo-o keeps its lowercase ``o`` (Kommo-o, not Kommo-O)."""
    from pokemon_team_builder.services.replica_exporter import _format_species

    assert _format_species("kommo-o") == "Kommo-o"


def test_format_species_ho_oh_and_porygon_z() -> None:
    """T10: ho-oh → Ho-Oh, porygon-z → Porygon-Z."""
    from pokemon_team_builder.services.replica_exporter import _format_species

    assert _format_species("ho-oh") == "Ho-Oh"
    assert _format_species("porygon-z") == "Porygon-Z"


def test_format_species_default_capitalize_unchanged() -> None:
    """T10 sanity: species not in the override table still split-capitalize."""
    from pokemon_team_builder.services.replica_exporter import _format_species

    assert _format_species("rotom-wash") == "Rotom-Wash"
    assert _format_species("urshifu-single-strike") == "Urshifu-Single-Strike"
