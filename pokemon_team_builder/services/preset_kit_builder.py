"""Preset KIT builder (v0.10.1 — issue 2026-05-15).

The legacy ``sp_preset_builder`` returns two SP allocations (offensive,
defensive) but every other field — item, ability, nature, moves — stays
locked to the offensive build. Sergio's feedback 2026-05-15:

    "el ofensivo y el defensivo solo le cambia los Evs, pero no te cambia
    ataques y literalmente de eso trata cambiar un kit del poke <-
    Necesario ajustar ataque + item además de EVs (Incluso verificar
    Habilidad / Habilidad Secreta)"

This module returns a full *kit* per preset — item, ability, nature,
moves, sp_distribution. The Pokemon's actual moveset / ability pool
constrains the substitutions; we never invent moves or abilities that
the species can't learn.
"""

from __future__ import annotations

from dataclasses import dataclass

from pokemon_team_builder.domain.models import PokemonData, SPDistribution
from pokemon_team_builder.services.sp_preset_builder import (
    SpRead,
    _is_physical_attacker as _is_physical_attacker_member,
    build_presets,
)


# Abilities that turn a member into a defensive pivot when available.
# Order matters: Regenerator (recovery on switch) > Magic Guard (no chip
# damage) > Magic Bounce (status reflection) > Unaware (ignores opponent
# boosts) > Thick Fat (halves Fire/Ice) > Intimidate (Atk drop on entry).
# Anything below Intimidate is a tier-2 fallback used only when the species
# has no tier-1 option.
_DEFENSIVE_ABILITY_PRIORITY: tuple[str, ...] = (
    "regenerator",
    "magic-guard",
    "magic-bounce",
    "unaware",
    "thick-fat",
    "levitate",
    "intimidate",
    "prankster",
    "natural-cure",
    "bulletproof",
    "filter",
    "solid-rock",
    "ice-scales",
    "fluffy",
    "fur-coat",
    "water-absorb",
    "volt-absorb",
    "flash-fire",
    "storm-drain",
    "lightning-rod",
    "good-as-gold",
    "purifying-salt",
    "well-baked-body",
)

# Recovery moves to prefer in slot 4 of the defensive kit. Order: instant
# self-heal first (Recover / Roost / Slack-Off), then turn-delay or
# conditional recovery, then HP-trading (Pain Split / Leech Seed).
_DEFENSIVE_RECOVERY_MOVES: tuple[str, ...] = (
    "recover",
    "roost",
    "slack-off",
    "milk-drink",
    "soft-boiled",
    "wish",
    "synthesis",
    "moonlight",
    "morning-sun",
    "shore-up",
    "rest",
    "pain-split",
    "leech-seed",
)

# Status moves used as the slot-4 secondary fallback when no recovery is
# available. Burn / paralysis cripple the opposing attacker which is more
# defensive value than a second coverage move.
_DEFENSIVE_STATUS_MOVES: tuple[str, ...] = (
    "will-o-wisp",
    "thunder-wave",
    "toxic",
    "spore",
    "sleep-powder",
    "stun-spore",
    "yawn",
)

# Setup / pure-attack moves that should NEVER appear in the defensive
# slot 4 — they trade slot value for offense the defensive kit doesn't
# care about.
_OFFENSIVE_SLOT4_MOVES: frozenset[str] = frozenset({
    "swords-dance", "dragon-dance", "bulk-up", "coil", "hone-claws",
    "nasty-plot", "calm-mind", "tail-glow", "quiver-dance",
    "shell-smash", "work-up", "clangorous-soul",
})

# Defensive items, in priority order. Every entry MUST be present in
# champions_legal_items.json v5 (Sergio's official paste 2026-05-15).
# Champions has no Leftovers / Sitrus Berry / Lum Berry / Eviolite /
# Covert Cloak / etc. — the realistic defensive picks are recovery
# berries (Oran Berry one-shot heal), Mental Herb (anti-Taunt), and
# status-cure berries that swap status for an HP-neutral cure.
_DEFENSIVE_ITEM_FALLBACKS: tuple[str, ...] = (
    "Mental Herb",
    "Oran Berry",
    "Leppa Berry",
    "Persim Berry",
    "Chesto Berry",
    "Cheri Berry",
    "Pecha Berry",
    "Rawst Berry",
    "Aspear Berry",
    "Shell Bell",
)


@dataclass(frozen=True)
class PresetKit:
    """Complete kit for one preset (offensive or defensive).

    Every field is what the UI / PokePaste exporter would consume — there
    is no "fallback to the offensive build" logic on the consumer side.
    """

    item: str
    ability: str
    nature: str
    moves: list[str]
    sp_distribution: SPDistribution


def _pick_defensive_ability(pokemon: PokemonData, current_ability: str) -> str:
    """Return the best defensive ability the species learns.

    Falls back to ``current_ability`` when no priority-list match exists
    in the Pokemon's ability pool — never invents abilities.
    """
    abilities_lower = [a.lower() for a in pokemon.abilities]
    for candidate in _DEFENSIVE_ABILITY_PRIORITY:
        if candidate in abilities_lower:
            # Return the original-cased variant from pokemon.abilities so
            # the PokePaste serializer prints e.g. "Regenerator" not
            # "regenerator".
            for orig in pokemon.abilities:
                if orig.lower() == candidate:
                    return orig
    return current_ability


def _pick_defensive_slot4(
    pokemon: PokemonData,
    offensive_moves: list[str],
) -> str | None:
    """Pick a recovery / status move for slot 4 of the defensive kit.

    Returns None if no improvement over the offensive slot 4 is possible
    — caller keeps the offensive move in that case.
    """
    move_pool = pokemon.move_names
    used = set(offensive_moves[:3])  # keep slots 1-3 (Protect + attacks)
    for candidate in _DEFENSIVE_RECOVERY_MOVES:
        if candidate in move_pool and candidate not in used:
            return candidate
    for candidate in _DEFENSIVE_STATUS_MOVES:
        if candidate in move_pool and candidate not in used:
            return candidate
    return None


def _pick_defensive_nature(is_physical_attacker: bool) -> str:
    """Pick a defensive nature that does NOT cripple the kept STABs.

    A physical attacker should drop SpA (unused) and boost Def → Impish.
    A special attacker drops Atk (unused) and boosts SpD → Calm. This
    keeps the slots-2/3 attacks at full power while moving the SP-free
    defensive stat up by 10 %.
    """
    return "Impish" if is_physical_attacker else "Calm"


def _pick_defensive_item(item: str, *, used_items: set[str] | None = None) -> str:
    """Return a defensive-flavored item.

    If the current item is already defensive (Leftovers, Sitrus, etc.),
    keep it. Otherwise pick the first available fallback that is not in
    ``used_items`` so two defensive kits on the same team don't collide.
    """
    used_items = used_items or set()
    if item in _DEFENSIVE_ITEM_FALLBACKS:
        return item
    for candidate in _DEFENSIVE_ITEM_FALLBACKS:
        if candidate not in used_items:
            return candidate
    return _DEFENSIVE_ITEM_FALLBACKS[0]


def build_kits(
    pokemon: PokemonData,
    item: str,
    ability: str,
    nature: str,
    moves: list[str],
    sp_distribution: SPDistribution,
    *,
    is_physical_attacker: bool | None = None,
    defensive_used_items: set[str] | None = None,
) -> dict[str, PresetKit]:
    """Build offensive + defensive kits for a single team member.

    The offensive kit is the *generated* member as-is — same item, ability,
    nature, moves, and SP allocation. The defensive kit substitutes:

    - item   → first defensive item not already claimed by another kit
    - ability → defensive HA if the species learns one
    - nature → Impish (physical attacker) / Calm (special attacker)
    - moves[3] → recovery or status when available; otherwise unchanged
    - sp_distribution → defensive SP preset (from build_presets)

    Args:
        pokemon: The species (provides ability + move pools).
        item: Currently assigned item.
        ability: Currently assigned ability.
        nature: Currently assigned nature.
        moves: Currently assigned 4-move list (offensive build).
        sp_distribution: Currently assigned SPs (offensive build).
        is_physical_attacker: Optional override; computed from stats when
            None (used by tests that want to force one or the other).
        defensive_used_items: Item names already taken by other defensive
            kits on the same team (Item Clause carries over to the
            defensive view).

    Returns:
        ``{"offensive": PresetKit, "defensive": PresetKit}``.
    """
    if is_physical_attacker is None:
        is_physical_attacker = pokemon.base_stats.atk >= pokemon.base_stats.spa

    offensive = PresetKit(
        item=item,
        ability=ability,
        nature=nature,
        moves=list(moves),
        sp_distribution=sp_distribution,
    )

    # Build the defensive SP preset via the legacy preset builder, then
    # wrap it together with the substituted item / ability / nature /
    # moves into a PresetKit. We synthesise a TeamMember on the fly so we
    # can reuse the existing weighting logic without duplicating it.
    from pokemon_team_builder.domain.models import TeamMember
    synth_member = TeamMember(
        pokemon=pokemon,
        role=["physical_sweeper" if is_physical_attacker else "special_sweeper"],
        sp_distribution=sp_distribution,
        item=item,
        ability=ability,
        nature=nature,
        moves=moves,
    )
    sp_presets = build_presets(synth_member, item, nature)
    defensive_sp = sp_presets["defensive"].to_sp_distribution()

    defensive_item = _pick_defensive_item(
        item, used_items=defensive_used_items,
    )
    defensive_ability = _pick_defensive_ability(pokemon, ability)
    defensive_nature = _pick_defensive_nature(is_physical_attacker)
    defensive_moves = list(moves)
    new_slot4 = _pick_defensive_slot4(pokemon, moves)
    if new_slot4 is not None and moves[3] in _OFFENSIVE_SLOT4_MOVES:
        # Only swap when the existing slot 4 is an offensive setup — a
        # team-utility move (Tailwind, Fake Out, Follow Me) is just as
        # valuable in the defensive kit and should stay.
        defensive_moves[3] = new_slot4

    defensive = PresetKit(
        item=defensive_item,
        ability=defensive_ability,
        nature=defensive_nature,
        moves=defensive_moves,
        sp_distribution=defensive_sp,
    )
    return {"offensive": offensive, "defensive": defensive}
