from __future__ import annotations

from typing import Any

from pokemon_team_builder.data.legal_pool_loader import is_legal
from pokemon_team_builder.domain.models import (
    SPDistribution,
    TeamMember,
    TeamVariant,
)
from pokemon_team_builder.services import pokemon_lookup
from pokemon_team_builder.services.replica_exporter import select_moves_for_role
from pokemon_team_builder.services.synergy_engine import assign_role
from pokemon_team_builder.services.team_generator import suggest_sp_distribution
from pokemon_team_builder.services import viability_rater

_ROLE_NATURE: dict[str, str] = {
    "physical_sweeper": "Jolly",
    "special_sweeper": "Timid",
    "physical_wall": "Impish",
    "special_wall": "Calm",
    "lead_support": "Jolly",
    "trick_room_setter": "Sassy",
    "redirect": "Calm",
}
_FALLBACK_NATURE = "Hardy"

EditDict = dict[str, Any]


def apply_edit(variant: TeamVariant, member_index: int, edit: EditDict) -> TeamVariant:
    """Apply a single edit to one member and return the rescored variant."""
    if member_index < 0 or member_index > 5:
        raise ValueError(f"member_index debe estar en [0, 5]; recibido: {member_index}")

    kind = edit.get("kind")
    if kind == "move_swap":
        updated = _apply_move_swap(
            variant.members[member_index],
            edit["slot_index"],
            edit["new_move"],
        )
    elif kind == "item_swap":
        updated = _apply_item_swap(variant, member_index, edit["new_item"])
    elif kind == "pokemon_swap":
        updated = _apply_pokemon_swap(variant, member_index, edit["new_pokemon_name"])
    else:
        raise ValueError(f"EditKind desconocido: '{kind}'")

    new_members = list(variant.members)
    new_members[member_index] = updated
    new_variant = variant.model_copy(update={"members": new_members})

    score, flex = viability_rater.score_team(new_variant)
    explanation = viability_rater.generate_explanation(new_variant, score)
    return new_variant.model_copy(update={
        "score": score,
        "score_explanation": explanation,
        "lead_flexibility_ratio": flex,
    })


def _apply_move_swap(member: TeamMember, slot_index: int, new_move: str) -> TeamMember:
    if slot_index < 0 or slot_index > 3:
        raise ValueError(f"slot_index debe estar en [0, 3]; recibido: {slot_index}")
    slug = new_move.strip().lower().replace(" ", "-")
    if slug not in member.pokemon.move_names:
        raise ValueError(
            f"'{slug}' no está en el pool de moves de {member.pokemon.name}"
        )
    new_moves = list(member.moves)
    new_moves[slot_index] = slug
    return member.model_copy(update={"moves": new_moves})


def _apply_item_swap(variant: TeamVariant, member_index: int, new_item: str) -> TeamMember:
    item = new_item.strip()
    other_items = {
        m.item
        for i, m in enumerate(variant.members)
        if i != member_index and m.item
    }
    if item in other_items:
        raise ValueError(f"Item Clause: '{item}' ya lo lleva otro miembro del equipo")
    return variant.members[member_index].model_copy(update={"item": item})


def _apply_pokemon_swap(
    variant: TeamVariant,
    member_index: int,
    new_pokemon_name: str,
) -> TeamMember:
    slug = new_pokemon_name.strip().lower().replace(" ", "-")

    if not is_legal(slug):
        raise ValueError(f"'{slug}' no está en el pool legal M-A")

    other_names = {
        m.pokemon.name
        for i, m in enumerate(variant.members)
        if i != member_index
    }
    if slug in other_names:
        raise ValueError(f"Species Clause: '{slug}' ya está en el equipo")

    try:
        pokemon = pokemon_lookup.lookup(slug)
    except Exception as exc:
        raise ValueError(f"No se puede resolver '{slug}': {exc}") from exc

    outgoing_roles = variant.members[member_index].role
    new_roles = assign_role(pokemon)

    # Preserve outgoing role if the new Pokemon supports it
    if any(r in new_roles for r in outgoing_roles):
        roles = [r for r in outgoing_roles if r in new_roles] + [
            r for r in new_roles if r not in outgoing_roles
        ]
    else:
        roles = new_roles

    primary = roles[0]
    ability = pokemon.abilities[0] if pokemon.abilities else "run-away"
    nature = _ROLE_NATURE.get(primary, _FALLBACK_NATURE)
    sp = suggest_sp_distribution(pokemon, primary)
    moves = select_moves_for_role(pokemon, roles)
    item = variant.members[member_index].item

    return TeamMember(
        pokemon=pokemon,
        role=roles,
        sp_distribution=sp,
        item=item,
        ability=ability,
        nature=nature,
        moves=moves,
        mega_form=None,
    )
