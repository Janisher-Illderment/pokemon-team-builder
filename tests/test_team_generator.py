from __future__ import annotations

import pytest

from pokemon_team_builder.config import MAX_SP_TOTAL
from pokemon_team_builder.domain.exceptions import TeamBuildError
from pokemon_team_builder.domain.models import (
    BaseStats,
    PokemonData,
    TeamVariant,
)
from pokemon_team_builder.services import pokemon_lookup
from pokemon_team_builder.services.team_generator import (
    generate_team,
    suggest_sp_distribution,
)


def _mk(
    name: str,
    types: list[str],
    *,
    hp: int = 80,
    atk: int = 80,
    def_: int = 80,
    spa: int = 80,
    spd: int = 80,
    spe: int = 80,
    moves: list[str] | None = None,
    abilities: list[str] | None = None,
    pid: int = 1,
) -> PokemonData:
    return PokemonData(
        id=pid,
        name=name,
        types=types,
        base_stats=BaseStats(
            hp=hp, atk=atk, **{"def": def_}, spa=spa, spd=spd, spe=spe
        ),
        move_names=moves
        or [
            "protect",
            "tackle",
            "earthquake",
            "ice-beam",
            "thunderbolt",
            "tailwind",
            "swords-dance",
            "nasty-plot",
        ],
        abilities=abilities or ["pressure"],
        weaknesses=pokemon_lookup.calculate_weaknesses(types),
    )


def _diverse_pool() -> list[PokemonData]:
    """A 15-member pool of varied types and roles for generator tests."""
    return [
        _mk(
            "talonflame",
            ["fire", "flying"],
            atk=81,
            spe=126,
            moves=[
                "protect",
                "tailwind",
                "brave-bird",
                "flamethrower",
                "u-turn",
                "fake-out",
            ],
            pid=10,
        ),
        _mk(
            "amoonguss",
            ["grass", "poison"],
            hp=114,
            spa=85,
            spe=30,
            moves=[
                "protect",
                "rage-powder",
                "spore",
                "giga-drain",
                "sludge-bomb",
            ],
            pid=11,
        ),
        _mk("milotic", ["water"], hp=95, spa=100, spd=125, spe=81, pid=12,
            moves=["protect", "scald", "ice-beam", "recover"]),
        _mk("rotom-wash", ["electric", "water"], hp=50, spa=105, spd=107, spe=86, pid=13,
            moves=["protect", "thunderbolt", "hydro-pump", "will-o-wisp"]),
        _mk("metagross", ["steel", "psychic"], atk=135, spe=70, pid=14,
            moves=["protect", "iron-head", "earthquake", "psychic"]),
        _mk("garchomp", ["dragon", "ground"], atk=130, spe=102, pid=15,
            moves=["protect", "earthquake", "dragon-claw", "swords-dance"]),
        _mk("salamence", ["dragon", "flying"], atk=135, spe=100, pid=16,
            moves=["protect", "dragon-claw", "earthquake", "fire-blast"]),
        _mk("tyranitar", ["rock", "dark"], atk=134, spe=61, pid=17,
            moves=["protect", "stone-edge", "crunch", "earthquake"]),
        _mk("gengar", ["ghost", "poison"], spa=130, spe=110, pid=18,
            moves=["protect", "shadow-ball", "sludge-bomb", "thunderbolt"]),
        _mk("hatterene", ["psychic", "fairy"], hp=57, spa=114, spe=29, pid=19,
            moves=["protect", "trick-room", "psychic", "moonblast"]),
        _mk("blissey", ["normal"], hp=255, def_=10, spd=135, spe=55, pid=20,
            moves=["protect", "soft-boiled", "seismic-toss", "thunder-wave"]),
        _mk("excadrill", ["ground", "steel"], atk=135, spe=88, pid=21,
            moves=["protect", "earthquake", "iron-head", "rock-slide"]),
        _mk("gyarados", ["water", "flying"], atk=125, spe=81, pid=22,
            moves=["protect", "waterfall", "earthquake", "dragon-dance"]),
        _mk("conkeldurr", ["fighting"], atk=140, hp=105, pid=23,
            moves=["protect", "drain-punch", "knock-off", "mach-punch"]),
        _mk("sylveon", ["fairy"], hp=95, spa=110, spd=130, pid=24,
            moves=["protect", "moonblast", "hyper-voice", "calm-mind"]),
    ]


def test_suggest_sp_physical_sweeper() -> None:
    pokemon = _mk("test", ["dragon"], atk=120, spa=70)
    sp = suggest_sp_distribution(pokemon, "physical_sweeper")
    assert sp.atk == 32
    assert sp.spe == 32
    assert sp.hp == 2
    total = sp.hp + sp.atk + sp.def_ + sp.spa + sp.spd + sp.spe
    assert total == MAX_SP_TOTAL


def test_suggest_sp_special_wall() -> None:
    pokemon = _mk("test", ["water"], spa=70, spd=120)
    sp = suggest_sp_distribution(pokemon, "special_wall")
    assert sp.hp == 32
    assert sp.spd == 32
    assert sp.def_ == 2


def test_suggest_sp_unknown_role_fallback() -> None:
    pokemon = _mk("test", ["normal"], atk=120, spa=60)
    sp = suggest_sp_distribution(pokemon, "unknown_role")
    total = sp.hp + sp.atk + sp.def_ + sp.spa + sp.spd + sp.spe
    assert total <= MAX_SP_TOTAL


def test_generate_team_returns_variant_with_anchor() -> None:
    anchor = _mk("charizard", ["fire", "flying"], atk=84, spa=109, spe=100, pid=6,
                 moves=["protect", "flamethrower", "air-slash", "earthquake", "heat-wave"])
    pool = _diverse_pool()
    variants = generate_team(anchor, pool=pool, num_variants=2)
    assert len(variants) >= 1
    for variant in variants:
        assert variant.members[0].pokemon.name == "charizard"


def test_generate_team_species_clause() -> None:
    anchor = _mk("charizard", ["fire", "flying"], atk=84, spa=109, spe=100, pid=6,
                 moves=["protect", "flamethrower", "air-slash", "earthquake"])
    pool = _diverse_pool()
    variants = generate_team(anchor, pool=pool, num_variants=2)
    for variant in variants:
        names = [m.pokemon.name for m in variant.members]
        assert len(set(names)) == 6, f"duplicate species in {names}"


def test_generate_team_item_clause() -> None:
    anchor = _mk("charizard", ["fire", "flying"], atk=84, spa=109, spe=100, pid=6,
                 moves=["protect", "flamethrower", "air-slash", "earthquake"])
    pool = _diverse_pool()
    variants = generate_team(anchor, pool=pool, num_variants=2)
    for variant in variants:
        items = [m.item for m in variant.members]
        assert len(set(items)) == 6, f"duplicate items in {items}"


def test_generate_team_sp_valid() -> None:
    anchor = _mk("charizard", ["fire", "flying"], atk=84, spa=109, spe=100, pid=6,
                 moves=["protect", "flamethrower", "air-slash", "earthquake"])
    pool = _diverse_pool()
    variants = generate_team(anchor, pool=pool, num_variants=2)
    for variant in variants:
        for member in variant.members:
            sp = member.sp_distribution
            total = sp.hp + sp.atk + sp.def_ + sp.spa + sp.spd + sp.spe
            assert total <= MAX_SP_TOTAL


def test_generate_team_6_members() -> None:
    anchor = _mk("charizard", ["fire", "flying"], atk=84, spa=109, spe=100, pid=6,
                 moves=["protect", "flamethrower", "air-slash", "earthquake"])
    pool = _diverse_pool()
    variants = generate_team(anchor, pool=pool, num_variants=2)
    for variant in variants:
        assert isinstance(variant, TeamVariant)
        assert len(variant.members) == 6


def test_no_illegal_items_in_constants() -> None:
    """No mainline-only items leak into Champions item constants.

    Champions M-A has a curated pool (~117 items). Importing a team with
    an unknown item into PikaChampions / champteams.gg silently drops it,
    so the team builder must never emit one. Inte v2 cross-check (HIGH)
    confirmed: Weakness Policy, Throat Spray, Rocky Helmet, AND Life Orb
    are NOT in M-A. Choice Band / Choice Specs / Assault Vest ARE legal
    per the same cross-check (corrected from prior memory).
    """
    from pokemon_team_builder.services.team_generator import (
        _BACKUP_ITEMS,
        _DEFAULT_ITEM_BY_ROLE,
        _FALLBACK_ITEM,
    )

    # v0.3 (refine-build-logic-v2): WP / Throat Spray / Rocky Helmet / Life Orb
    # removed from M-A. Eject Button is mainline-only and never confirmed.
    illegal = {
        "Weakness Policy",
        "Throat Spray",
        "Rocky Helmet",
        "Life Orb",
        "Eject Button",
    }

    for role, item in _DEFAULT_ITEM_BY_ROLE.items():
        assert item not in illegal, (
            f"_DEFAULT_ITEM_BY_ROLE[{role!r}] = {item!r} is not legal in Champions"
        )

    assert _FALLBACK_ITEM not in illegal, (
        f"_FALLBACK_ITEM = {_FALLBACK_ITEM!r} is not legal in Champions"
    )

    leaked = set(_BACKUP_ITEMS) & illegal
    assert not leaked, f"illegal items in _BACKUP_ITEMS: {sorted(leaked)}"


def test_no_setup_move_with_choice_item() -> None:
    """A special_sweeper with Choice Scarf must not get a setup move in slot 4."""
    from pokemon_team_builder.services.replica_exporter import (
        _SETUP_MOVES,
        select_moves_for_role,
    )

    pokemon = _mk(
        "slowking",
        ["water", "psychic"],
        spa=100,
        atk=75,
        moves=[
            "protect",
            "scald",
            "psychic",
            "ice-beam",
            "nasty-plot",
            "calm-mind",
        ],
    )
    moves = select_moves_for_role(
        pokemon, ["special_sweeper"], item="Choice Scarf"
    )
    assert not any(m in _SETUP_MOVES for m in moves), (
        f"setup move leaked into Choice Scarf set: {moves}"
    )


def test_ability_skips_sand_veil() -> None:
    """_pick_ability should return the first non-situational ability."""
    from pokemon_team_builder.services.team_generator import _pick_ability

    pokemon = _mk(
        "garchomp",
        ["dragon", "ground"],
        atk=130,
        spe=102,
        abilities=["sand-veil", "rough-skin"],
    )
    assert _pick_ability(pokemon) == "rough-skin"


def test_pick_ability_empty_list_raises() -> None:
    """_pick_ability must raise TeamBuildError when abilities list is empty."""
    from pokemon_team_builder.services.team_generator import _pick_ability
    from pokemon_team_builder.domain.exceptions import TeamBuildError
    from pokemon_team_builder.domain.models import BaseStats

    pokemon = PokemonData(
        id=99, name="ditto", types=["normal"],
        base_stats=BaseStats(hp=48, atk=48, **{"def": 48}, spa=48, spd=48, spe=48),
        move_names=["transform"], abilities=[],
        weaknesses={},
    )
    with pytest.raises(TeamBuildError):
        _pick_ability(pokemon)


def test_throat_spray_never_assigned() -> None:
    """Throat Spray is NOT in the M-A pool (Inte v2 cross-check).

    Pre-v0.3 this test verified Throat Spray was gated on sound moves;
    post-v0.3 it must verify the item is never assigned at all because
    it is not in champions_legal_items.json.
    """
    from pokemon_team_builder.services.team_generator import _assign_items

    pokemon = _mk(
        "sound-mon",
        ["fairy"],
        atk=60,
        spa=130,
        spe=100,
        moves=["protect", "hyper-voice", "psychic", "thunderbolt"],
    )
    items = _assign_items([["special_sweeper"]], [pokemon])
    assert items[0] != "Throat Spray", (
        f"Throat Spray must not be assigned (not Champions M-A legal): {items}"
    )


def test_white_herb_not_assigned_without_stat_drop_move() -> None:
    """White Herb must not be assigned if the Pokemon has no stat-drop moves.

    v6 (2026-05-31): White Herb (Hierba Blanca) IS legal in Champions — it
    is a "Beginning" item, missing from the earlier shop-only paste. So it
    now lives in the backup pool. The meaningful invariant is the
    activation predicate (_ITEM_ACTIVATION): White Herb is only assignable
    to a Pokémon carrying a self-stat-dropping move (Overheat, Close
    Combat, Draco Meteor, ...) — never to a mon without one.
    """
    from pokemon_team_builder.services.team_generator import (
        _BACKUP_ITEMS,
        _assign_items,
    )

    # White Herb IS legal now and present in the backup pool.
    assert "White Herb" in _BACKUP_ITEMS

    # Build 6 same-role mons (force fallback chain), none with stat-drop moves.
    members = [
        _mk(
            f"mon-{i}",
            ["normal"],
            atk=120,
            spa=70,
            spe=90,
            moves=["protect", "tackle", "earthquake", "ice-beam"],
            pid=100 + i,
        )
        for i in range(6)
    ]
    members_roles = [["physical_sweeper"]] * 6
    items = _assign_items(members_roles, members)

    assert "White Herb" not in items, (
        f"White Herb assigned despite no stat-drop moves anywhere: {items}"
    )


def test_special_sweeper_default_item_is_choice_specs() -> None:
    """Special sweepers default to Choice Specs (v0.3 — Throat Spray removed).

    Inte v2 cross-check confirmed Throat Spray is NOT in M-A; the spec
    designates Choice Specs as the provisional replacement.
    """
    from pokemon_team_builder.services.team_generator import _assign_items

    pokemon = _mk(
        "sound-mon",
        ["fairy"],
        atk=60,
        spa=130,
        spe=100,
        moves=["protect", "hyper-voice", "psychic", "thunderbolt"],
    )
    items = _assign_items([["special_sweeper"]], [pokemon])
    assert items[0] == "Scope Lens", (
        f"v0.10.3 (Sergio's complete paste): special_sweeper default is Scope Lens: {items}"
    )


def test_assign_items_no_synthetic_item_strings() -> None:
    """Item Clause: 6 same-role mons must each get a distinct, real item.

    Regression: previously ``_assign_items`` could emit ``"Item-1"``,
    ``"Item-2"`` etc. when the curated pool was exhausted. Those strings
    fail to import in PikaChampions/champteams.gg. The function must now
    either return 6 distinct real items or raise TeamBuildError.
    """
    from pokemon_team_builder.services.team_generator import _assign_items

    # All 6 members share the same primary role — they will collide on
    # the role-default item, forcing _assign_items to walk the entire
    # backup pool.
    members_roles = [["physical_sweeper"]] * 6
    items = _assign_items(members_roles)

    assert len(items) == 6
    assert len(set(items)) == 6, f"duplicate items: {items}"
    for item in items:
        assert not item.startswith("Item-"), (
            f"synthetic placeholder leaked into items: {items}"
        )


# ── C5: frail-attacker type-resist berry (docs/vgc-principles.md §5, V7) ──


def test_frail_psychic_attacker_gets_dark_resist_berry() -> None:
    """A frail Psychic special sweeper (weak to Dark/Ghost/Bug) gets the
    berry for its highest-priority worst weakness — Dark → Colbur Berry."""
    from pokemon_team_builder.services.team_generator import (
        _assign_items,
        _frail_attacker_resist_berry,
    )

    alakazam = _mk(
        "alakazam", ["psychic"],
        hp=55, atk=50, def_=45, spa=135, spd=95, spe=120,
        moves=["protect", "psychic", "shadow-ball", "dazzling-gleam"],
    )
    assert _frail_attacker_resist_berry(alakazam, ["special_sweeper"]) == "Colbur Berry"
    items = _assign_items([["special_sweeper"]], [alakazam])
    assert items[0] == "Colbur Berry", items


def test_bulky_attacker_keeps_role_default_not_berry() -> None:
    """A bulky attacker (high HP/bulk) is NOT frail → keeps its role default,
    never the frail-attacker berry."""
    from pokemon_team_builder.services.team_generator import (
        _assign_items,
        _frail_attacker_resist_berry,
    )

    snorlax = _mk(
        "snorlax", ["normal"],
        hp=160, atk=110, def_=65, spa=65, spd=110, spe=30,
        moves=["protect", "body-slam", "earthquake", "crunch"],
    )
    assert _frail_attacker_resist_berry(snorlax, ["physical_sweeper"]) is None
    items = _assign_items([["physical_sweeper"]], [snorlax])
    assert items[0] == "Shell Bell", items  # physical_sweeper static default


def test_frail_non_offensive_role_no_berry() -> None:
    """The berry preference only applies to offensive roles."""
    from pokemon_team_builder.services.team_generator import (
        _frail_attacker_resist_berry,
    )

    frail_support = _mk(
        "support", ["psychic"], hp=55, def_=45, spd=95, spa=60, spe=120,
    )
    assert _frail_attacker_resist_berry(frail_support, ["lead_support"]) is None


def test_choice_scarf_not_assigned_to_trick_room_setter() -> None:
    """Trick Room setters must never receive a Choice item."""
    from pokemon_team_builder.services.team_generator import (
        _CHOICE_ITEMS,
        _assign_items,
    )

    # Build six trick_room_setter mons. The role-default ("Mental Herb")
    # is unique to one slot, so the other five must walk the fallback
    # chain — which historically picks "Choice Scarf" first. With the
    # fix, no Choice item must be selected for any slot.
    pokemon = _mk(
        "tr-mon",
        ["psychic"],
        atk=60,
        spa=120,
        spe=30,
        moves=["protect", "trick-room", "psychic", "shadow-ball"],
    )
    members = [pokemon] * 6
    members_roles = [["trick_room_setter"]] * 6
    items = _assign_items(members_roles, members)

    leaked = [item for item in items if item in _CHOICE_ITEMS]
    assert not leaked, (
        f"Choice item assigned to trick_room_setter: {items}"
    )


def test_choice_scarf_not_assigned_to_redirect() -> None:
    """Redirect roles (Follow Me) must never receive a Choice item."""
    from pokemon_team_builder.services.team_generator import (
        _CHOICE_ITEMS,
        _assign_items,
    )

    pokemon = _mk(
        "redirect-mon",
        ["fairy"],
        atk=60,
        spa=100,
        spd=120,
        moves=["protect", "follow-me", "moonblast", "helping-hand"],
    )
    members = [pokemon] * 6
    members_roles = [["redirect"]] * 6
    items = _assign_items(members_roles, members)

    leaked = [item for item in items if item in _CHOICE_ITEMS]
    assert not leaked, f"Choice item assigned to redirect: {items}"


def test_ditto_excluded_from_candidate_pool() -> None:
    """Ditto must never appear as a generated team member."""
    anchor = _mk(
        "charizard",
        ["fire", "flying"],
        atk=84,
        spa=109,
        spe=100,
        pid=6,
        moves=["protect", "flamethrower", "air-slash", "earthquake"],
    )
    pool = _diverse_pool()
    # Inject Ditto into the pool — generator must filter it out.
    pool.append(
        _mk(
            "ditto",
            ["normal"],
            hp=48,
            atk=48,
            def_=48,
            spa=48,
            spd=48,
            spe=48,
            moves=["transform"],
            abilities=["limber"],
            pid=132,
        )
    )
    variants = generate_team(anchor, pool=pool, num_variants=3)
    assert variants, "expected at least one variant"
    for variant in variants:
        names = [m.pokemon.name for m in variant.members]
        assert "ditto" not in names, f"ditto leaked into team: {names}"


def test_generate_team_raises_for_ditto_anchor() -> None:
    """generate_team must raise TeamBuildError when anchor is Ditto."""
    ditto = _mk(
        "ditto",
        ["normal"],
        hp=48,
        atk=48,
        def_=48,
        spa=48,
        spd=48,
        spe=48,
        moves=["transform"],
        abilities=["limber"],
        pid=132,
    )
    pool = _diverse_pool()
    with pytest.raises(TeamBuildError, match="Ditto"):
        generate_team(ditto, pool=pool, num_variants=1)


def test_type_boost_item_not_assigned_to_wrong_type() -> None:
    """Mystic Water must not be assigned to a Fire-type Pokemon."""
    from pokemon_team_builder.services.team_generator import (
        _TYPE_BOOST_ITEMS,
        _assign_items,
    )

    # Sanity: Mystic Water is a known type-booster.
    assert _TYPE_BOOST_ITEMS["Mystic Water"] == "water"

    # Six Fire-type mons sharing physical_sweeper — the fallback chain
    # will walk past Choice Scarf into the type-booster section. The
    # generator must skip Mystic Water (water) on a Fire-type and pick
    # something type-appropriate (e.g. Charcoal) or a typeless item.
    members = [
        _mk(
            f"fire-{i}",
            ["fire"],
            atk=120,
            spa=70,
            spe=90,
            moves=["protect", "flare-blitz", "earthquake", "rock-slide"],
            pid=200 + i,
        )
        for i in range(6)
    ]
    members_roles = [["physical_sweeper"]] * 6
    items = _assign_items(members_roles, members)

    for pokemon, item in zip(members, items):
        if item in _TYPE_BOOST_ITEMS:
            boost_type = _TYPE_BOOST_ITEMS[item]
            assert boost_type in {t.lower() for t in pokemon.types}, (
                f"{item} (boosts {boost_type}) assigned to "
                f"{pokemon.name} (types={pokemon.types})"
            )


# ---------------------------------------------------------------------------
# fix-logic-v1 — T1, T4, T5, T9 regression tests
# ---------------------------------------------------------------------------


def test_choice_item_not_assigned_to_lead_support() -> None:
    """T1: lead_support roles must never receive a Choice item.

    Locking a fast support mon into Tailwind / Fake Out wastes its turn
    cycle — once the buff is up the Pokemon is dead weight. _NO_CHOICE_ROLES
    must include lead_support so the fallback chain skips Choice Scarf.
    """
    from pokemon_team_builder.services.team_generator import (
        _CHOICE_ITEMS,
        _assign_items,
    )

    # Six lead_support mons sharing the role — only one can take the
    # role default (Focus Sash); the rest walk the fallback chain.
    pokemon = _mk(
        "lead-mon",
        ["fire", "flying"],
        atk=81,
        spa=81,
        spe=126,
        moves=["protect", "tailwind", "brave-bird", "fake-out"],
    )
    members = [pokemon] * 6
    members_roles = [["lead_support"]] * 6
    items = _assign_items(members_roles, members)

    leaked = [item for item in items if item in _CHOICE_ITEMS]
    assert not leaked, f"Choice item assigned to lead_support: {items}"


def test_suggest_sp_redirect() -> None:
    """T4: redirect role uses the bulky template (HP/SpD/Def)."""
    pokemon = _mk(
        "amoonguss",
        ["grass", "poison"],
        hp=114,
        spa=85,
        spe=30,
        moves=["protect", "rage-powder", "spore", "giga-drain"],
    )
    sp = suggest_sp_distribution(pokemon, "redirect")
    assert sp.hp == 32
    assert sp.spd == 32
    assert sp.def_ == 2
    total = sp.hp + sp.atk + sp.def_ + sp.spa + sp.spd + sp.spe
    assert total == MAX_SP_TOTAL


def test_weakness_policy_never_assigned() -> None:
    """Weakness Policy is NOT in the M-A pool (Inte v2 cross-check).

    Pre-v0.3 this test verified WP was gated against setup-move synergy
    conflicts; post-v0.3 WP is simply unavailable, so we assert it never
    appears in any assignment regardless of the moveset.
    """
    from pokemon_team_builder.services.team_generator import _assign_items
    from pokemon_team_builder.services.replica_exporter import (
        select_moves_for_role,
    )

    pokemon = _mk(
        "dd-chomp",
        ["dragon", "ground"],
        atk=130,
        spa=80,
        spe=102,
        moves=[
            "protect",
            "earthquake",
            "dragon-claw",
            "dragon-dance",
            "stone-edge",
        ],
    )
    preview = select_moves_for_role(pokemon, ["physical_sweeper"])

    items = _assign_items(
        [["physical_sweeper"]],
        [pokemon],
        preview_moves=[preview],
    )
    assert items[0] != "Weakness Policy", (
        f"WP assigned despite removal from M-A legal pool: {items}"
    )


def test_white_herb_not_assigned_to_wall_moveset() -> None:
    """T5: White Herb is gated on the actual moveset, not the learnset.

    A wall has Recover/Roost in its moveset even when its learnset
    contains an Overheat-class move (which would never be picked).
    The activatability check must see the picked moveset and skip
    White Herb in that case.
    """
    from pokemon_team_builder.services.team_generator import _assign_items
    from pokemon_team_builder.services.replica_exporter import (
        select_moves_for_role,
    )

    # 6 same-role walls so the Leftovers default only goes to one slot —
    # the remaining 5 must walk the fallback chain. None of the picked
    # movesets will include a stat-drop move, so White Herb must be
    # rejected even though it sits in _BACKUP_ITEMS.
    walls = [
        _mk(
            f"wall-{i}",
            ["steel"],
            hp=100,
            atk=80,
            def_=130,
            spa=60,
            spd=80,
            spe=50,
            moves=[
                "protect",
                "iron-head",
                "earthquake",
                "stealth-rock",
                # learnset contains overheat, but the wall picks no
                # special move and no stat-drop move
                "overheat",
            ],
            pid=300 + i,
        )
        for i in range(6)
    ]
    preview = [select_moves_for_role(w, ["physical_wall"]) for w in walls]
    members_roles = [["physical_wall"]] * 6
    items = _assign_items(members_roles, walls, preview_moves=preview)

    # Sanity: none of the chosen movesets contains a stat-drop move.
    from pokemon_team_builder.services.team_generator import _STAT_DROP_MOVES
    for moves in preview:
        assert not (set(moves) & _STAT_DROP_MOVES), (
            f"fixture invariant violated: {moves} contains a stat-drop move"
        )

    assert "White Herb" not in items, (
        f"White Herb assigned despite no stat-drop move in any preview: "
        f"{items}"
    )


def test_nature_jolly_for_physical_lead() -> None:
    """T9: a physical lead derives Jolly from a physical slot-2 STAB."""
    from pokemon_team_builder.services.team_generator import _derive_nature

    # talonflame-style: slot-2 will be brave-bird (physical).
    moves = ["protect", "brave-bird", "u-turn", "tailwind"]
    nature = _derive_nature("lead_support", ["lead_support"], moves)
    assert nature == "Jolly"


def test_nature_timid_for_special_lead() -> None:
    """T9: a special-leaning lead with Hurricane gets Timid, not Jolly.

    Pelipper is the canonical case: 95 SpA, 50 Atk, but the role-only
    nature mapping pinned lead_support to Jolly. Reading the slot-2
    category (Hurricane → special) yields Timid instead.
    """
    from pokemon_team_builder.services.team_generator import _derive_nature

    moves = ["protect", "hurricane", "scald", "tailwind"]
    nature = _derive_nature("lead_support", ["lead_support"], moves)
    assert nature == "Timid"


def test_dominant_attack_category_all_physical() -> None:
    """ADR weather-setter-coherence §5.3.4: all-physical set → 'physical'."""
    from pokemon_team_builder.services.team_generator import (
        _dominant_attack_category,
    )

    moves = ["seed-bomb", "earthquake", "rock-slide", "protect"]
    assert _dominant_attack_category(moves) == "physical"


def test_dominant_attack_category_all_special() -> None:
    """ADR §5.3.4: all-special set → 'special'."""
    from pokemon_team_builder.services.team_generator import (
        _dominant_attack_category,
    )

    moves = ["blizzard", "energy-ball", "ice-beam", "protect"]
    assert _dominant_attack_category(moves) == "special"


def test_dominant_attack_category_tie_is_none() -> None:
    """ADR §5.3.4: 2 physical + 2 special → None (ambiguous mixed set)."""
    from pokemon_team_builder.services.team_generator import (
        _dominant_attack_category,
    )

    moves = ["seed-bomb", "ice-beam", "earthquake", "energy-ball"]
    assert _dominant_attack_category(moves) is None


def test_dominant_attack_category_status_only_is_none() -> None:
    """ADR §5.3.4: no known damage moves (status/unknown) → None.

    Status moves like protect/tailwind are absent from _MOVE_CATEGORY, so they
    do not vote. This must NOT invent a category.
    """
    from pokemon_team_builder.services.team_generator import (
        _dominant_attack_category,
    )

    assert _dominant_attack_category(["protect", "tailwind", "helping-hand"]) is None
    assert _dominant_attack_category([]) is None


def test_dominant_attack_category_majority_wins() -> None:
    """A single unknown/status move does not break a clear physical majority."""
    from pokemon_team_builder.services.team_generator import (
        _dominant_attack_category,
    )

    moves = ["seed-bomb", "earthquake", "ice-beam", "protect"]  # 2 phys, 1 spec
    assert _dominant_attack_category(moves) == "physical"


def test_nature_dominant_special_overrides_physical_slot2() -> None:
    """ADR §3.2: a special-dominant moveset yields Timid even if slot-2 is
    physical.

    This is the weather-setter coherence case: a mon whose slot-2 STAB is
    physical (seed-bomb) but whose moveset is overall special-dominant
    (ice-beam + energy-ball + blizzard) must NOT get Jolly (which would zero
    its SpA). The whole-moveset dominant category wins over the isolated
    slot-2.
    """
    from pokemon_team_builder.services.team_generator import _derive_nature

    moves = ["seed-bomb", "ice-beam", "energy-ball", "blizzard"]  # 3 spec, 1 phys
    nature = _derive_nature("physical_sweeper", ["physical_sweeper"], moves)
    assert nature == "Timid"


def test_nature_dominant_physical_overrides_special_slot2() -> None:
    """ADR §3.2: a physical-dominant moveset yields Jolly even if slot-2 is
    special, for a special_sweeper primary label.
    """
    from pokemon_team_builder.services.team_generator import _derive_nature

    moves = ["ice-beam", "seed-bomb", "earthquake", "rock-slide"]  # 3 phys, 1 spec
    nature = _derive_nature("special_sweeper", ["special_sweeper"], moves)
    assert nature == "Jolly"


def test_nature_tie_falls_back_to_slot2() -> None:
    """ADR §3.2: on a 2-2 category tie, the dominant category is None and the
    isolated slot-2 decides (preserving legacy behaviour for true mixed sets).
    """
    from pokemon_team_builder.services.team_generator import _derive_nature

    # slot-2 = hurricane (special) → Timid despite the physical coverage.
    moves = ["protect", "hurricane", "earthquake", "scald"]  # 2 spec, 1 phys (+status)
    # Make it a real 2-2 tie:
    moves = ["seed-bomb", "hurricane", "earthquake", "scald"]  # 2 phys, 2 spec
    nature = _derive_nature("lead_support", ["lead_support"], moves)
    assert nature == "Timid"  # slot-2 hurricane is special


def test_nature_sassy_for_trick_room_setter_regardless_of_slot2() -> None:
    """T9: TR setters always get Sassy, ignoring the slot-2 category."""
    from pokemon_team_builder.services.team_generator import _derive_nature

    # Even with a physical slot-2 move, Sassy must win.
    moves = ["protect", "iron-head", "trick-room", "earthquake"]
    nature = _derive_nature(
        "trick_room_setter", ["trick_room_setter"], moves
    )
    assert nature == "Sassy"


def test_nature_calm_for_redirect_regardless_of_slot2() -> None:
    """T9: redirect always gets Calm."""
    from pokemon_team_builder.services.team_generator import _derive_nature

    moves = ["protect", "iron-head", "follow-me", "earthquake"]
    nature = _derive_nature("redirect", ["redirect"], moves)
    assert nature == "Calm"


def test_partial_score_penalizes_excess_sweepers() -> None:
    from pokemon_team_builder.services.team_generator import _partial_score

    # Three pure physical sweepers → penalized
    sweeper = _mk("sweeper", ["normal"], atk=120, spa=60, spe=100)
    three_sweepers = [sweeper, sweeper, _mk("sweeper2", ["fire"], atk=120, spa=60, spe=100, pid=2)]
    role_map_all_sweep = {p.name: ["physical_sweeper"] for p in three_sweepers}
    score_3_sweepers = _partial_score(three_sweepers, role_map_all_sweep)

    # Two sweepers + one lead → not penalized
    lead = _mk("lead", ["water"], spe=110, moves=["protect", "tailwind", "surf", "ice-beam"], pid=3)
    mixed = [sweeper, _mk("sweeper2", ["fire"], atk=120, spa=60, spe=100, pid=2), lead]
    role_map_mixed = {
        sweeper.name: ["physical_sweeper"],
        "sweeper2": ["physical_sweeper"],
        lead.name: ["lead_support"],
    }
    score_mixed = _partial_score(mixed, role_map_mixed)

    assert score_3_sweepers < score_mixed


def test_weather_setter_not_counted_as_pure_sweeper() -> None:
    from pokemon_team_builder.services.team_generator import _partial_score

    # Pokemon with lead_support + special_sweeper is NOT a pure sweeper
    weather_setter = _mk(
        "ninetales-alola", ["ice", "fairy"],
        hp=73, atk=67, def_=75, spa=81, spd=100, spe=109,
        abilities=["snow-warning"], pid=10,
    )
    sweeper1 = _mk("garchomp", ["dragon", "ground"], atk=130, spe=102, pid=11)
    sweeper2 = _mk("dragonite", ["dragon", "flying"], atk=134, spe=80, pid=12)
    # weather setter gets lead_support as primary from assign_role
    # → should not trigger the sweeper penalty
    team = [weather_setter, sweeper1, sweeper2]
    role_map = {
        weather_setter.name: ["lead_support", "special_sweeper"],
        sweeper1.name: ["physical_sweeper"],
        sweeper2.name: ["physical_sweeper"],
    }
    score = _partial_score(team, role_map)
    # pure_sweeper_count = 2 (weather_setter excluded) → no penalty applied
    assert score > 0  # score would be negative if penalty wrongly applied to 3


# ---------------------------------------------------------------------------
# fix-move-item-bugs — Bug 1: Choice guard any-role
# ---------------------------------------------------------------------------


def test_choice_blocked_when_setter_is_secondary_role() -> None:
    from pokemon_team_builder.services.team_generator import (
        _assign_items,
        _CHOICE_ITEMS,
    )

    # Member 0 takes Shell Bell (special_sweeper default).
    # Member 1 has trick_room_setter as secondary role → Choice Scarf must be skipped.
    items = _assign_items([
        ["special_sweeper"],
        ["special_sweeper", "trick_room_setter"],
    ])
    assert items[1] not in _CHOICE_ITEMS


def test_choice_blocked_when_redirect_is_secondary_role() -> None:
    from pokemon_team_builder.services.team_generator import (
        _assign_items,
        _CHOICE_ITEMS,
    )

    items = _assign_items([
        ["special_sweeper"],
        ["special_sweeper", "redirect"],
    ])
    assert items[1] not in _CHOICE_ITEMS


def test_pure_sweeper_falls_back_to_first_legal_backup() -> None:
    """v0.10.3: fallback chain after Sergio's full in-game store paste.

    Member 0 takes the role default (Shell Bell for physical_sweeper).
    Member 1 collides on the default and walks the chain: _FALLBACK_ITEM
    is now Cheri Berry (universal status-cure berry, no Choice items in
    Champions).
    """
    from pokemon_team_builder.services.team_generator import _assign_items

    items = _assign_items([
        ["physical_sweeper"],
        ["physical_sweeper"],
    ])
    assert items[0] == "Shell Bell"
    assert items[1] == "Cheri Berry"


# ---------------------------------------------------------------------------
# Meta-service integration tests
# ---------------------------------------------------------------------------

def test_assign_items_prefers_meta_item() -> None:
    from unittest.mock import patch
    from pokemon_team_builder.services.team_generator import _assign_items
    from pokemon_team_builder.services.meta_service import MetaEntry

    # v0.10.3: Oran Berry is the closest Champions analog to Sitrus
    # Berry (Sitrus Berry removed from Champions per Sergio's paste).
    meta_entry = MetaEntry(items=["Oran Berry"], moves=[], teammates=[])
    with patch(
        "pokemon_team_builder.services.team_generator._meta_service"
    ) as mock_svc:
        mock_svc.get.return_value = meta_entry
        items = _assign_items(
            [["physical_sweeper"]],
            meta_items_by_member=[["Oran Berry"]],
        )
    assert items[0] == "Oran Berry"


def test_assign_items_skips_meta_item_on_clause_conflict() -> None:
    from unittest.mock import patch
    from pokemon_team_builder.services.team_generator import _assign_items

    # Both members get the same meta item → second should fall back.
    items = _assign_items(
        [["physical_sweeper"], ["special_sweeper"]],
        meta_items_by_member=[["Oran Berry"], ["Oran Berry"]],
    )
    assert items[0] == "Oran Berry"
    assert items[1] != "Oran Berry"


def test_heuristic_filter_meta_teammate_bonus() -> None:
    from unittest.mock import patch
    from pokemon_team_builder.services.team_generator import _heuristic_filter
    from pokemon_team_builder.services.meta_service import MetaEntry

    anchor = _mk("rillaboom", ["grass"], spe=85)
    ally = _mk("ally", ["water"], spe=80)       # meta teammate
    other = _mk("other", ["fire"], spe=90)      # not meta teammate

    role_map = {
        "rillaboom": ["physical_sweeper"],
        "ally": ["lead_support"],
        "other": ["physical_sweeper"],
    }
    meta_entry = MetaEntry(items=[], moves=[], teammates=["ally"])
    with patch(
        "pokemon_team_builder.services.team_generator._meta_service"
    ) as mock_svc:
        mock_svc.get.return_value = meta_entry
        result = _heuristic_filter(anchor, [ally, other], role_map)

    names = [p.name for p in result]
    assert names.index("ally") < names.index("other"), \
        "meta teammate 'ally' should rank above 'other'"


def test_heuristic_filter_no_meta_unchanged() -> None:
    from unittest.mock import patch
    from pokemon_team_builder.services.team_generator import _heuristic_filter

    anchor = _mk("rillaboom", ["grass"], spe=85)
    cand1 = _mk("water_mon", ["water"], spe=80)
    cand2 = _mk("fire_mon", ["fire"], spe=90)
    role_map = {
        "rillaboom": ["physical_sweeper"],
        "water_mon": ["lead_support"],
        "fire_mon": ["physical_sweeper"],
    }
    with patch(
        "pokemon_team_builder.services.team_generator._meta_service"
    ) as mock_svc:
        mock_svc.get.return_value = None
        # should not raise, returns candidates ordered by synergy only
        result = _heuristic_filter(anchor, [cand1, cand2], role_map)
    assert len(result) == 2
