from __future__ import annotations

from typing import Any

import pytest
from click.testing import CliRunner

from pokemon_team_builder.cli import main as cli_main
from pokemon_team_builder.domain.exceptions import (
    PokemonIllegalError,
    PokemonNotFoundError,
)
from pokemon_team_builder.domain.models import (
    BaseStats,
    PokemonData,
    SPDistribution,
    TeamMember,
    TeamVariant,
)
from pokemon_team_builder.services import pokemon_lookup


def _mk_pokemon(
    name: str,
    types: list[str],
    *,
    pid: int = 1,
    moves: list[str] | None = None,
) -> PokemonData:
    return PokemonData(
        id=pid,
        name=name,
        types=types,
        base_stats=BaseStats(hp=78, atk=84, **{"def": 78}, spa=109, spd=85, spe=100),
        move_names=moves
        or ["protect", "flamethrower", "air-slash", "earthquake"],
        abilities=["blaze"],
        weaknesses=pokemon_lookup.calculate_weaknesses(types),
    )


def _mk_member(p: PokemonData, item: str) -> TeamMember:
    return TeamMember(
        pokemon=p,
        role=["physical_sweeper"],
        sp_distribution=SPDistribution.model_validate(
            {"atk": 32, "spe": 32, "hp": 2}
        ),
        item=item,
        ability=p.abilities[0] if p.abilities else "Pressure",
        nature="Jolly",
        moves=["protect", "flamethrower", "earthquake", "tailwind"],
    )


def _stub_variant(anchor: PokemonData) -> TeamVariant:
    members = [_mk_member(anchor, "Choice Band")]
    items = ["Focus Sash", "Sitrus Berry", "Assault Vest", "Rocky Helmet", "Life Orb"]
    for i, item in enumerate(items):
        # Reuse the same Pokemon shape for the stub fillers; the CLI tests
        # don't validate Item Clause / Species Clause from the stub.
        filler = PokemonData(
            id=anchor.id + i + 1,
            name=f"filler-{i}",
            types=["normal"],
            base_stats=anchor.base_stats,
            move_names=anchor.move_names,
            abilities=["pressure"],
            weaknesses=pokemon_lookup.calculate_weaknesses(["normal"]),
        )
        members.append(_mk_member(filler, item))
    return TeamVariant(
        members=members, score=85.0, score_explanation="OK", is_recommended=True
    )


def test_build_charizard_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    anchor = _mk_pokemon("charizard", ["fire", "flying"], pid=6)

    monkeypatch.setattr(
        cli_main.pokemon_lookup, "lookup", lambda _name: anchor
    )
    monkeypatch.setattr(
        cli_main.team_generator,
        "generate_team",
        lambda anchor, num_variants=3, candidate_loader=None: [_stub_variant(anchor)],
    )

    runner = CliRunner()
    result = runner.invoke(cli_main.cli, ["build", "charizard", "--json"])
    assert result.exit_code == 0, result.output
    assert "charizard" in result.output


def test_build_with_output_writes_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    anchor = _mk_pokemon("charizard", ["fire", "flying"], pid=6)

    monkeypatch.setattr(
        cli_main.pokemon_lookup, "lookup", lambda _name: anchor
    )
    monkeypatch.setattr(
        cli_main.team_generator,
        "generate_team",
        lambda anchor, num_variants=3, candidate_loader=None: [_stub_variant(anchor)],
    )

    out = tmp_path / "team.txt"
    runner = CliRunner()
    result = runner.invoke(
        cli_main.cli, ["build", "charizard", "-o", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "Level: 50" in content


def test_build_illegal_pokemon_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_illegal(name: Any) -> Any:
        raise PokemonIllegalError(name)

    monkeypatch.setattr(cli_main.pokemon_lookup, "lookup", _raise_illegal)
    runner = CliRunner()
    result = runner.invoke(cli_main.cli, ["build", "mewtwo"])
    assert result.exit_code == 1


def test_build_not_found_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_404(name: Any) -> Any:
        raise PokemonNotFoundError(name)

    monkeypatch.setattr(cli_main.pokemon_lookup, "lookup", _raise_404)
    runner = CliRunner()
    result = runner.invoke(cli_main.cli, ["build", "xyz_unknown"])
    assert result.exit_code == 1


def test_check_charizard_shows_info(monkeypatch: pytest.MonkeyPatch) -> None:
    anchor = _mk_pokemon("charizard", ["fire", "flying"], pid=6)
    monkeypatch.setattr(cli_main, "is_legal", lambda _name: True)
    monkeypatch.setattr(
        cli_main.pokemon_lookup, "lookup", lambda _name: anchor
    )
    runner = CliRunner()
    result = runner.invoke(cli_main.cli, ["check", "charizard"])
    assert result.exit_code == 0, result.output
    assert "charizard" in result.output
    assert "fire" in result.output


def test_check_illegal_exits_1() -> None:
    # Uses real legal pool — mewtwo is excluded from Reg M-A.
    runner = CliRunner()
    result = runner.invoke(cli_main.cli, ["check", "mewtwo"])
    assert result.exit_code == 1
