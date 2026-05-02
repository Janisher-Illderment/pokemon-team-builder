from __future__ import annotations

from pokemon_team_builder.config import MAX_SP_TOTAL
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
