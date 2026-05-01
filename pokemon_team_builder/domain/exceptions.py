from __future__ import annotations


class PokeBuilderError(Exception):
    """Base class for all errors raised by pokemon-team-builder."""


class PokemonNotFoundError(PokeBuilderError):
    """Raised when a Pokemon is not found in PokeAPI (HTTP 404)."""

    def __init__(self, name_or_id: str | int) -> None:
        self.name_or_id = name_or_id
        super().__init__(
            f"Pokemon no encontrado en PokeAPI: '{name_or_id}'."
        )


class PokemonIllegalError(PokeBuilderError):
    """Raised when a Pokemon is not legal in the current regulation pool."""

    def __init__(self, name_or_id: str | int) -> None:
        self.name_or_id = name_or_id
        super().__init__(
            f"Pokemon no permitido en la regulacion actual: '{name_or_id}'."
        )


class PokeAPIError(PokeBuilderError):
    """Raised when PokeAPI returns an unexpected error or is unreachable."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class TeamBuildError(PokeBuilderError):
    """Raised when team construction cannot satisfy a domain invariant.

    Examples: the curated item pool is exhausted while honoring the
    Item Clause (no two team members may share an item), or any other
    case where we would otherwise be forced to emit a synthetic / invalid
    artifact that downstream importers (PokePaste, PikaChampions) would
    reject.
    """
