from __future__ import annotations

import json as json_module
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from pokemon_team_builder.data.legal_pool_loader import (
    check_pool_validity,
    get_all_names,
    is_legal,
    valid_until,
)
from pokemon_team_builder.domain.exceptions import (
    PokeAPIError,
    PokemonIllegalError,
    PokemonNotFoundError,
)
from pokemon_team_builder.domain.models import PokemonData, TeamVariant
from pokemon_team_builder.services import (
    pokemon_lookup,
    replica_exporter,
    team_generator,
    viability_rater,
)
from pokemon_team_builder.services.synergy_engine import assign_role


_console = Console()
_err_console = Console(stderr=True)


def _fail(message: str, code: int = 1) -> None:
    _err_console.print(f"[red]error:[/red] {message}")
    sys.exit(code)


def _lazy_pool_candidates(anchor: PokemonData) -> list[PokemonData]:
    """Resolve a pool of legal Pokemon for ``anchor`` to be teamed with.

    The legal pool is filtered by name first (cheap) before any PokeAPI
    fetch. We lookup() each surviving name; a single failure is logged
    but does not abort generation.
    """
    pool: list[PokemonData] = []
    for name in get_all_names():
        if name == anchor.name:
            continue
        try:
            pool.append(pokemon_lookup.lookup(name))
        except (PokemonNotFoundError, PokeAPIError, PokemonIllegalError):
            continue
    return pool


def _render_variant(variant: TeamVariant) -> None:
    table = Table(title="Equipo recomendado", show_header=True)
    table.add_column("#", justify="right")
    table.add_column("Nombre")
    table.add_column("Tipo")
    table.add_column("Rol")
    table.add_column("Item")
    table.add_column("Nat.")
    table.add_column("SPs (total)", justify="right")
    for idx, member in enumerate(variant.members, start=1):
        sp = member.sp_distribution
        total = sp.hp + sp.atk + sp.def_ + sp.spa + sp.spd + sp.spe
        types = "/".join(member.pokemon.types)
        roles = ", ".join(member.role)
        table.add_row(
            str(idx),
            member.pokemon.name,
            types,
            roles,
            member.item,
            member.nature,
            str(total),
        )
    _console.print(table)
    _console.print(f"[bold]Score:[/bold] {variant.score:.1f}/100")
    if variant.score_explanation:
        _console.print(variant.score_explanation)


def _variant_to_json_dict(variant: TeamVariant) -> dict:
    return variant.model_dump()


@click.group("poke-builder")
def cli() -> None:
    """CLI para generar equipos competitivos en Pokemon Champions."""


@cli.command("build")
@click.argument("pokemon_name")
@click.option("--variants", "-n", default=3, show_default=True, type=int)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
)
@click.option("--force", "-f", is_flag=True, default=False)
@click.option("--json", "as_json", is_flag=True, default=False)
def build_cmd(
    pokemon_name: str,
    variants: int,
    output: Path | None,
    force: bool,
    as_json: bool,
) -> None:
    """Genera variantes de equipo en torno al ``pokemon_name`` indicado."""
    check_pool_validity()

    try:
        anchor = pokemon_lookup.lookup(pokemon_name)
    except PokemonIllegalError as exc:
        _fail(str(exc))
        return  # for type checkers
    except PokemonNotFoundError as exc:
        _fail(str(exc))
        return
    except PokeAPIError as exc:
        _fail(f"{exc} Verifica tu conexion o intenta mas tarde.")
        return

    try:
        team_variants = team_generator.generate_team(
            anchor,
            num_variants=variants,
            candidate_loader=_lazy_pool_candidates,
        )
    except PokeAPIError as exc:
        _fail(f"{exc} Verifica tu conexion o intenta mas tarde.")
        return

    if not team_variants:
        _fail(
            "No se pudo generar ningun equipo viable para "
            f"'{pokemon_name}'. Prueba con otro Pokemon."
        )
        return

    ranked = viability_rater.rank_variants(team_variants)
    top = ranked[0]

    if as_json:
        click.echo(json_module.dumps(_variant_to_json_dict(top), indent=2))
    else:
        _render_variant(top)

    if output is not None:
        paste = replica_exporter.to_pokepaste(top)
        try:
            replica_exporter.save_to_file(paste, output, force=force)
        except FileExistsError as exc:
            _fail(str(exc))
            return
        _console.print(f"[green]Guardado en:[/green] {output}")

    _console.print()
    _console.print(replica_exporter.IMPORT_INSTRUCTIONS)


@cli.command("check")
@click.argument("pokemon_name")
def check_cmd(pokemon_name: str) -> None:
    """Inspecciona la legalidad y stats de un Pokemon."""
    check_pool_validity()

    if not is_legal(pokemon_name):
        _err_console.print(
            f"[red]Ilegal:[/red] '{pokemon_name}' no esta permitido en la "
            f"regulacion actual (valida hasta {valid_until().isoformat()})."
        )
        sys.exit(1)

    try:
        pokemon = pokemon_lookup.lookup(pokemon_name)
    except PokemonNotFoundError as exc:
        _fail(str(exc))
        return
    except PokeAPIError as exc:
        _fail(f"{exc} Verifica tu conexion o intenta mas tarde.")
        return

    types = "/".join(pokemon.types)
    _console.print(
        f"[bold]{pokemon.name}[/bold] (#{pokemon.id}) — Tipo: {types}"
    )
    _console.print(
        "[green]Legal en Regulation M-A:[/green] [green]si[/green]"
    )

    stats_table = Table(title="Base stats", show_header=True)
    stats_table.add_column("Stat")
    stats_table.add_column("Valor", justify="right")
    bs = pokemon.base_stats
    for label, value in (
        ("HP", bs.hp),
        ("Atk", bs.atk),
        ("Def", bs.def_),
        ("SpA", bs.spa),
        ("SpD", bs.spd),
        ("Spe", bs.spe),
    ):
        stats_table.add_row(label, str(value))
    _console.print(stats_table)

    weak_table = Table(title="Debilidades (>=2x)")
    weak_table.add_column("Tipo atacante")
    weak_table.add_column("Multiplicador", justify="right")
    has_weak = False
    for attacker, mult in sorted(
        pokemon.weaknesses.items(), key=lambda kv: -kv[1]
    ):
        if mult < 2.0:
            continue
        has_weak = True
        color = "red" if mult >= 4.0 else "yellow"
        weak_table.add_row(attacker, f"[{color}]{mult:g}x[/{color}]")
    if has_weak:
        _console.print(weak_table)
    else:
        _console.print("[green]Sin debilidades >=2x.[/green]")

    roles = assign_role(pokemon)
    _console.print(f"[bold]Roles:[/bold] {', '.join(roles)}")
