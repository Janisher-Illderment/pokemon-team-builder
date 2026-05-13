"""Phase 2b — favorite-first build flow tests.

Covers ``build_core_duo`` (slot 2 picker), ``cover_shared_weakness``
(slot 3 picker), and the end-to-end ``generate_team`` flow when the new
favorite-first pipeline is in effect (i.e. always — the flow runs for
every archetype now).
"""
from __future__ import annotations

from unittest.mock import patch

from pokemon_team_builder.domain.models import BaseStats, PokemonData
from pokemon_team_builder.services import pokemon_lookup, team_generator
from pokemon_team_builder.services.favorite_first_builder import (
    build_core_duo,
    cover_shared_weakness,
)
from pokemon_team_builder.services.meta_service import MetaEntry, MetaService
from pokemon_team_builder.services.synergy_engine import assign_role


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
    """Build a PokemonData fixture with real weakness math.

    Mirrors the helper in ``test_team_generator.py`` so the fixtures
    behave consistently across the suite.
    """
    return PokemonData(
        id=pid,
        name=name,
        types=types,
        base_stats=BaseStats(
            hp=hp, atk=atk, **{"def": def_}, spa=spa, spd=spd, spe=spe
        ),
        move_names=moves or [
            "protect", "tackle", "earthquake", "ice-beam", "thunderbolt",
        ],
        abilities=abilities or ["pressure"],
        weaknesses=pokemon_lookup.calculate_weaknesses(types),
    )


class _StubMetaService(MetaService):
    """In-memory MetaService double — returns scripted entries.

    Tests want explicit control over meta presence so partner scoring is
    deterministic. The real MetaService hits MunchStats over HTTP which
    is both slow and externally-mutating.
    """

    def __init__(self, entries: dict[str, MetaEntry] | None = None) -> None:
        self._entries = entries or {}

    def get(self, name: str) -> MetaEntry | None:  # type: ignore[override]
        return self._entries.get(name.lower())


def _build_role_map(*members: PokemonData) -> dict[str, list[str]]:
    return {m.name: assign_role(m) for m in members}


# ---------------------------------------------------------------------------
# build_core_duo
# ---------------------------------------------------------------------------

def test_excadrill_weather_based_pairs_with_tyranitar() -> None:
    """Excadrill (Sand Rush) + weather_based archetype → Tyranitar wins.

    Sand Stream is the only ability that turns on Sand Rush, so the
    weather_based archetype's weather_synergy weight (1.8) drives
    Tyranitar to the top of the partner list against any non-setter
    alternative.
    """
    excadrill = _mk(
        "excadrill", ["ground", "steel"],
        atk=135, spe=88,
        abilities=["sand-rush"],
        pid=530,
    )
    tyranitar = _mk(
        "tyranitar", ["rock", "dark"],
        atk=134, spe=61,
        abilities=["sand-stream"],
        pid=248,
    )
    # Decoy candidates that don't set sand — must NOT win.
    landorus = _mk(
        "landorus-therian", ["ground", "flying"],
        atk=145, spe=91,
        abilities=["intimidate"],
        pid=645,
    )
    rotom_wash = _mk(
        "rotom-wash", ["electric", "water"],
        spa=105, spd=107, spe=86,
        abilities=["levitate"],
        pid=479,
    )

    pool = [tyranitar, landorus, rotom_wash]
    role_map = _build_role_map(excadrill, *pool)

    partner, score = build_core_duo(
        excadrill, "weather_based", pool, _StubMetaService(), role_map,
    )
    assert partner.name == "tyranitar", (
        f"weather_based excadrill should pair with tyranitar (Sand Stream); "
        f"got {partner.name} (score {score})"
    )


def test_hard_trick_room_partner_is_tr_setter() -> None:
    """Slow physical attacker + hard_trick_room → partner sets Trick Room."""
    # Slow attacker anchor — needs TR to outpace foes.
    rhyperior = _mk(
        "rhyperior", ["ground", "rock"],
        hp=115, atk=140, spe=40,
        abilities=["lightning-rod"],
        pid=464,
    )
    hatterene = _mk(
        "hatterene", ["psychic", "fairy"],
        hp=57, spa=114, spe=29,
        moves=["protect", "trick-room", "psychic", "moonblast"],
        abilities=["magic-bounce"],
        pid=858,
    )
    # Faster non-setter decoy.
    fast_decoy = _mk(
        "tornadus", ["flying"],
        spa=115, spe=121,
        moves=["protect", "hurricane", "tailwind", "u-turn"],
        abilities=["prankster"],
        pid=641,
    )

    pool = [hatterene, fast_decoy]
    role_map = _build_role_map(rhyperior, *pool)

    partner, _ = build_core_duo(
        rhyperior, "hard_trick_room", pool, _StubMetaService(), role_map,
    )
    assert partner.name == "hatterene", (
        f"hard_trick_room should pick a TR setter; got {partner.name}"
    )


def test_hyper_offense_allows_duplicate_role_in_core_duo() -> None:
    """hyper_offense suppresses the role-complement penalty.

    Two physical sweepers MAY form the core under hyper_offense even
    when a non-sweeper alternative is in the pool. Validates the
    archetype-specific rule directly in ``_synergy_score``.
    """
    gyarados = _mk(
        "gyarados", ["water", "flying"],
        atk=125, spe=81,
        abilities=["intimidate"],
        pid=130,
    )
    # Another sweeper — same role group as the anchor.
    rillaboom = _mk(
        "rillaboom", ["grass"],
        atk=125, hp=100, spe=85,
        abilities=["grassy-surge"],
        pid=812,
    )
    # Role-complement support that would normally win.
    blissey = _mk(
        "blissey", ["normal"],
        hp=255, def_=10, spd=135, spe=55,
        abilities=["natural-cure"],
        pid=242,
    )

    pool = [rillaboom, blissey]
    role_map = _build_role_map(gyarados, *pool)

    partner_ho, _ = build_core_duo(
        gyarados, "hyper_offense", pool, _StubMetaService(), role_map,
    )
    # When the role-complement bonus is suppressed AND meta is empty AND
    # neither candidate sets weather for gyarados, type-complement is the
    # dominant signal. We assert that the duplicate-role partner IS
    # eligible — i.e. the result is permitted to be Rillaboom — by
    # confirming we get back one of the two candidates without raising.
    assert partner_ho.name in {"rillaboom", "blissey"}
    # Under hyper_offense the role-complement bonus is OFF, so rillaboom
    # is the natural winner unless blissey covers strictly more
    # weaknesses. Confirm rillaboom is the pick — this is the test's
    # actual claim (duplicate-role partner WINS, not just is eligible).
    assert partner_ho.name == "rillaboom", (
        f"hyper_offense should permit gyarados + rillaboom (duplicate role); "
        f"got {partner_ho.name}"
    )


def test_meta_teammate_bonus_applied() -> None:
    """MunchStats teammates get a +3.0 bump regardless of archetype.

    Confirms the synergy formula's (d) component is wired up correctly
    and acts independently of archetype-scaled components.
    """
    rillaboom = _mk("rillaboom", ["grass"], atk=125, spe=85, pid=812)
    ally = _mk("ally", ["water"], spe=80, pid=11)
    other = _mk("other", ["fire"], spe=90, pid=12)
    pool = [ally, other]
    role_map = _build_role_map(rillaboom, *pool)

    meta = _StubMetaService({
        "rillaboom": MetaEntry(items=[], moves=[], teammates=["ally"]),
    })
    partner, _ = build_core_duo(
        rillaboom, "balance", pool, meta, role_map,
    )
    assert partner.name == "ally"


# ---------------------------------------------------------------------------
# cover_shared_weakness
# ---------------------------------------------------------------------------

def test_slot_3_covers_shared_weakness() -> None:
    """Slot 3 picks against the INTERSECTION of duo weaknesses.

    Anchor (Normal — Fighting-weak) + partner (Rock/Dark — Fighting-weak
    4x) share Fighting; the candidate that resists Fighting MUST beat
    one that resists only a non-shared weakness.
    """
    # Normal-type anchor: weak to Fighting (2x). No other weaknesses.
    blissey = _mk("blissey", ["normal"], hp=255, spd=135, pid=242)
    # Rock/Dark partner: weak to Fighting (4x), Ground, Water, Grass,
    # Bug, Steel, Fairy. Intersection with Normal = {Fighting}.
    tyranitar = _mk(
        "tyranitar", ["rock", "dark"],
        atk=134, spe=61,
        abilities=["sand-stream"],
        pid=248,
    )

    # Candidate that resists Fighting (Ghost type — immune).
    gengar = _mk(
        "gengar", ["ghost", "poison"],
        spa=130, spe=110,
        abilities=["levitate"],
        pid=94,
    )
    # Candidate that does NOT resist Fighting but resists Fire (irrelevant
    # to the shared set).
    starmie = _mk(
        "starmie", ["water", "psychic"],
        spa=100, spe=115,
        abilities=["natural-cure"],
        pid=121,
    )

    pool = [gengar, starmie]
    role_map = _build_role_map(blissey, tyranitar, *pool)

    # Sanity: confirm Fighting IS the shared weakness.
    blissey_weak = {t for t, m in blissey.weaknesses.items() if m >= 2.0}
    tyranitar_weak = {t for t, m in tyranitar.weaknesses.items() if m >= 2.0}
    shared = blissey_weak & tyranitar_weak
    assert "fighting" in shared, (
        f"test fixture is wrong; expected fighting in shared, got {shared}"
    )

    slot3 = cover_shared_weakness(
        [blissey, tyranitar], "balance", pool, role_map,
    )
    assert slot3.name == "gengar", (
        f"slot 3 must cover the shared Fighting weakness; got {slot3.name}"
    )


# ---------------------------------------------------------------------------
# generate_team — end-to-end deterministic flow
# ---------------------------------------------------------------------------


def _legacy_diverse_pool() -> list[PokemonData]:
    """Reuse a 15-member pool similar to ``test_team_generator._diverse_pool``.

    Defined here so ``test_favorite_first.py`` is self-contained — no
    cross-test-module imports.
    """
    return [
        _mk("talonflame", ["fire", "flying"], atk=81, spe=126,
            moves=["protect", "tailwind", "brave-bird", "flamethrower",
                   "u-turn", "fake-out"],
            pid=10),
        _mk("amoonguss", ["grass", "poison"], hp=114, spa=85, spe=30,
            moves=["protect", "rage-powder", "spore", "giga-drain",
                   "sludge-bomb"],
            pid=11),
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
            moves=["protect", "stone-edge", "crunch", "earthquake"],
            abilities=["sand-stream"]),
        _mk("gengar", ["ghost", "poison"], spa=130, spe=110, pid=18,
            moves=["protect", "shadow-ball", "sludge-bomb", "thunderbolt"]),
        _mk("hatterene", ["psychic", "fairy"], hp=57, spa=114, spe=29, pid=19,
            moves=["protect", "trick-room", "psychic", "moonblast"]),
        _mk("blissey", ["normal"], hp=255, def_=10, spd=135, spe=55, pid=20,
            moves=["protect", "soft-boiled", "seismic-toss", "thunder-wave"]),
        _mk("excadrill", ["ground", "steel"], atk=135, spe=88, pid=21,
            moves=["protect", "earthquake", "iron-head", "rock-slide"],
            abilities=["sand-rush"]),
        _mk("gyarados", ["water", "flying"], atk=125, spe=81, pid=22,
            moves=["protect", "waterfall", "earthquake", "dragon-dance"]),
        _mk("conkeldurr", ["fighting"], atk=140, hp=105, pid=23,
            moves=["protect", "drain-punch", "knock-off", "mach-punch"]),
        _mk("sylveon", ["fairy"], hp=95, spa=110, spd=130, pid=24,
            moves=["protect", "moonblast", "hyper-voice", "calm-mind"]),
    ]


def test_repeated_calls_byte_identical() -> None:
    """Same inputs → byte-identical variant lists.

    Determinism is the headline guarantee of the favorite-first flow —
    the user gets the same team twice from the same anchor + archetype.
    """
    anchor = _mk(
        "charizard", ["fire", "flying"],
        atk=84, spa=109, spe=100,
        moves=["protect", "flamethrower", "air-slash", "earthquake"],
        pid=6,
    )
    pool = _legacy_diverse_pool()

    # Stub the meta service so we don't hit MunchStats during the test.
    with patch(
        "pokemon_team_builder.services.team_generator._meta_service",
        new=_StubMetaService(),
    ):
        variants_a = team_generator.generate_team(
            anchor, pool=list(pool), num_variants=3, archetype="balance",
        )
        variants_b = team_generator.generate_team(
            anchor, pool=list(pool), num_variants=3, archetype="balance",
        )

    assert len(variants_a) == len(variants_b) > 0
    for va, vb in zip(variants_a, variants_b):
        names_a = [m.pokemon.name for m in va.members]
        names_b = [m.pokemon.name for m in vb.members]
        assert names_a == names_b, (
            f"non-deterministic team composition: {names_a} vs {names_b}"
        )
        # Scores and movesets MUST match too — variance comes from
        # archetype × ev_preset, not RNG.
        assert va.score == vb.score
        for ma, mb in zip(va.members, vb.members):
            assert ma.moves == mb.moves
            assert ma.item == mb.item


def test_changing_archetype_changes_lineup() -> None:
    """hyper_offense vs hard_trick_room for the same anchor → distinct lineups.

    The two archetypes weight role complement, weather_synergy, and
    speed/bulk very differently — at least slot 2 (partner) should
    diverge when the pool contains both a sweeper and a TR setter.
    """
    # Slow attacker so hard_trick_room has a real reason to fire.
    anchor = _mk(
        "rhydon", ["ground", "rock"],
        hp=105, atk=130, spe=40,
        moves=["protect", "earthquake", "stone-edge", "megahorn"],
        pid=112,
    )
    pool = _legacy_diverse_pool()

    with patch(
        "pokemon_team_builder.services.team_generator._meta_service",
        new=_StubMetaService(),
    ):
        ho = team_generator.generate_team(
            anchor, pool=list(pool), num_variants=1, archetype="hyper_offense",
        )
        tr = team_generator.generate_team(
            anchor, pool=list(pool), num_variants=1, archetype="hard_trick_room",
        )

    assert ho and tr
    ho_names = [m.pokemon.name for m in ho[0].members]
    tr_names = [m.pokemon.name for m in tr[0].members]
    assert ho_names != tr_names, (
        f"different archetypes should produce different lineups; "
        f"both returned {ho_names}"
    )


def test_beam_search_receives_3_member_seed() -> None:
    """The new flow seeds beam search with anchor + partner + slot3.

    We verify by patching ``_beam_search`` and inspecting its kwargs.
    A 3-member seed proves slots 1–3 are locked before beam search runs.
    """
    anchor = _mk(
        "charizard", ["fire", "flying"],
        atk=84, spa=109, spe=100,
        moves=["protect", "flamethrower", "air-slash", "earthquake"],
        pid=6,
    )
    pool = _legacy_diverse_pool()

    captured_kwargs: dict = {}

    real_beam_search = team_generator._beam_search

    def _spy_beam_search(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return real_beam_search(*args, **kwargs)

    with patch(
        "pokemon_team_builder.services.team_generator._meta_service",
        new=_StubMetaService(),
    ), patch(
        "pokemon_team_builder.services.team_generator._beam_search",
        side_effect=_spy_beam_search,
    ):
        team_generator.generate_team(
            anchor, pool=list(pool), num_variants=1, archetype="balance",
        )

    seed = captured_kwargs.get("seed")
    assert seed is not None and len(seed) == 3, (
        f"beam search should be seeded with 3 members; got {seed}"
    )
    assert seed[0].name == anchor.name, (
        f"seed must start with the anchor; got {seed[0].name}"
    )
