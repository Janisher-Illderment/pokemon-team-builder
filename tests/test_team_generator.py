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

    Champions has a closed item pool (~117 items). Importing a team with
    an unknown item into PikaChampions / champteams.gg silently drops it,
    so the team builder must never emit one. Guards against regressions
    where confirmed-illegal items (Choice Band, Choice Specs, Assault
    Vest, Life Orb, Eject Button) sneak back in via copy-paste from
    mainline VGC references.
    """
    from pokemon_team_builder.services.team_generator import (
        _BACKUP_ITEMS,
        _DEFAULT_ITEM_BY_ROLE,
        _FALLBACK_ITEM,
    )

    illegal = {
        "Choice Band",
        "Choice Specs",
        "Assault Vest",
        "Life Orb",
        "Eject Button",
        "Loaded Dice",
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


def test_throat_spray_not_assigned_without_sound_move() -> None:
    """special_sweeper without sound moves must not get Throat Spray."""
    from pokemon_team_builder.services.team_generator import _assign_items

    # Special-leaning Pokemon (spa > atk) but no sound moves in pool.
    pokemon = _mk(
        "no-sound-mon",
        ["psychic"],
        atk=60,
        spa=130,
        spe=100,
        moves=["protect", "psychic", "shadow-ball", "thunderbolt"],
    )
    items = _assign_items([["special_sweeper"]], [pokemon])
    assert items[0] != "Throat Spray", (
        f"Throat Spray assigned despite no sound moves: {items}"
    )


def test_white_herb_not_assigned_without_stat_drop_move() -> None:
    """White Herb must not be assigned if the Pokemon has no stat-drop moves."""
    from pokemon_team_builder.services.team_generator import (
        _BACKUP_ITEMS,
        _assign_items,
    )

    # Sanity: White Herb is in the backup pool, so we know it could
    # theoretically be picked if activatability weren't enforced.
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


def test_throat_spray_assigned_with_sound_move() -> None:
    """special_sweeper WITH a sound move SHOULD keep Throat Spray."""
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
    assert items[0] == "Throat Spray", (
        f"Throat Spray not assigned despite hyper-voice in pool: {items}"
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


def test_weakness_policy_not_assigned_with_setup_move() -> None:
    """T5: a physical_sweeper with Dragon Dance must not get Weakness Policy.

    Setup moves give the +2 manually; layering Weakness Policy on top
    is a dead-weight redundancy — once setup is up the WP slot does
    nothing useful.
    """
    from pokemon_team_builder.services.team_generator import _assign_items

    # The Pokemon's preview moveset will include "dragon-dance" in slot 4
    # (physical sweeper role, dragon-dance in pool, item="" so the choice
    # guard does not trip). _assign_items must see it and refuse WP.
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
    # Compute the preview moveset the same way _build_variant does.
    from pokemon_team_builder.services.replica_exporter import (
        select_moves_for_role,
    )
    preview = select_moves_for_role(pokemon, ["physical_sweeper"])
    assert "dragon-dance" in preview, (
        "fixture invariant: setup move must end up in preview"
    )

    items = _assign_items(
        [["physical_sweeper"]],
        [pokemon],
        preview_moves=[preview],
    )
    assert items[0] != "Weakness Policy", (
        f"WP assigned despite setup move in preview: {items}"
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

    # 6 same-role walls so Rocky Helmet only goes to one slot — the
    # remaining 5 must walk the fallback chain. None of the picked
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
