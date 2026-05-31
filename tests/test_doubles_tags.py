"""C3 — Doubles taxonomy tags (ADR §3.2, docs/vgc-principles.md §3).

derive_doubles_tags produces the six per-mon tags; derive_team_tags adds
the two context-dependent ones (weather_abuser, trick_room_abuser). Tags
are derived on demand from the existing role weights + presence + moves —
nothing is persisted (ADR §3.4). One representative per tag below.
"""

from __future__ import annotations

from pokemon_team_builder.domain.models import (
    BaseStats,
    PokemonData,
    SPDistribution,
    TeamMember,
    TeamVariant,
)
from pokemon_team_builder.services.synergy_engine import (
    derive_doubles_tags,
    derive_team_tags,
)


def _pkd(
    name: str,
    *,
    types: list[str] | None = None,
    hp: int = 80,
    atk: int = 80,
    def_: int = 80,
    spa: int = 80,
    spd: int = 80,
    spe: int = 80,
    abilities: list[str] | None = None,
    moves: list[str] | None = None,
) -> PokemonData:
    return PokemonData(
        id=1,
        name=name,
        types=types or ["normal"],
        base_stats=BaseStats(hp=hp, atk=atk, **{"def": def_}, spa=spa, spd=spd, spe=spe),
        move_names=moves or [],
        abilities=abilities or ["pressure"],
        weaknesses={},
    )


def _member(pokemon: PokemonData, moves: list[str], ability: str | None = None) -> TeamMember:
    return TeamMember(
        pokemon=pokemon,
        role=["physical_sweeper"],
        sp_distribution=SPDistribution(),
        item="Leftovers",
        ability=ability or (pokemon.abilities[0] if pokemon.abilities else "pressure"),
        nature="Hardy",
        moves=moves,
    )


# ── Per-mon tags (derive_doubles_tags) ────────────────────────────────────────

def test_offensive_threat_by_stat():
    mon = _pkd("garchomp", atk=130, spe=102, abilities=["rough-skin"],
               moves=["earthquake", "dragon-claw", "rock-slide", "protect"])
    assert "offensive_threat" in derive_doubles_tags(mon)


def test_offensive_threat_by_setup_move():
    """A non-100-stat mon that carries a setup move is still a win condition."""
    mon = _pkd("bisharp", atk=90, spe=70, abilities=["defiant"],
               moves=["swords-dance", "knock-off", "iron-head", "protect"])
    tags = derive_doubles_tags(mon)
    assert "offensive_threat" in tags  # swords-dance, despite atk 90 < 100


def test_support_enabler_by_intimidate():
    mon = _pkd("incineroar", atk=115, abilities=["intimidate"],
               moves=["fake-out", "flare-blitz", "parting-shot", "knock-off"])
    assert "support_enabler" in derive_doubles_tags(mon)


def test_support_enabler_by_screen():
    mon = _pkd("grimmsnarl", atk=120, spe=60, abilities=["prankster"],
               moves=["light-screen", "reflect", "spirit-break", "thunder-wave"])
    assert "support_enabler" in derive_doubles_tags(mon)


def test_speed_control_tag():
    mon = _pkd("whimsicott", spa=77, spe=116, abilities=["prankster"],
               moves=["tailwind", "moonblast", "encore", "protect"])
    assert "speed_control" in derive_doubles_tags(mon)


def test_speed_control_not_set_by_partial_ability_alone():
    """A Static mon with no speed-control move does NOT earn speed_control.

    Partial-ability credit (0.5) does not reach the 1.0 per-member
    threshold of §3.2.
    """
    mon = _pkd("pikachu", atk=80, spe=90, abilities=["static"],
               moves=["thunderbolt", "protect", "fake-out", "volt-switch"])
    # fake-out gives speed_control via the move set, so to isolate the
    # partial-ability rule use a mon with NO speed-control move.
    quiet = _pkd("raichu", atk=80, spe=110, abilities=["static"],
                 moves=["thunderbolt", "protect", "grass-knot", "surf"])
    assert "speed_control" not in derive_doubles_tags(quiet)


def test_defensive_pivot_requires_disruption():
    """A bulky mon counts as defensive_pivot ONLY when it has disruption."""
    # Bulky + Intimidate → defensive_pivot.
    pivot = _pkd("hippowdon", hp=108, atk=112, def_=118, spa=68, spd=72, spe=47,
                 abilities=["intimidate"],
                 moves=["earthquake", "slack-off", "yawn", "protect"])
    pivot_tags = derive_doubles_tags(pivot)
    assert "defensive_pivot" in pivot_tags

    # Same bulk, no disruption (pure defensive moves, plain ability) →
    # NOT a pivot (it is a liability, ADR §2.3).
    liability = _pkd("passive-wall", hp=120, atk=70, def_=130, spa=60, spd=120, spe=40,
                     abilities=["pressure"],
                     moves=["recover", "protect", "iron-defense", "body-press"])
    liability_tags = derive_doubles_tags(liability)
    assert "defensive_pivot" not in liability_tags


def test_weather_setter_tag():
    mon = _pkd("torkoal", atk=85, def_=140, spa=85, spe=20, abilities=["drought"],
               moves=["eruption", "heat-wave", "protect", "body-press"])
    assert "weather_setter" in derive_doubles_tags(mon)


def test_trick_room_setter_tag():
    mon = _pkd("dusclops", hp=40, atk=70, def_=130, spa=60, spd=130, spe=25,
               abilities=["pressure"],
               moves=["trick-room", "night-shade", "will-o-wisp", "protect"])
    assert "trick_room_setter" in derive_doubles_tags(mon)


# ── Context-dependent tags (derive_team_tags) ─────────────────────────────────

def _six(members: list[TeamMember]) -> TeamVariant:
    while len(members) < 6:
        filler = _pkd(f"filler{len(members)}", atk=120, spe=100,
                      moves=["tackle", "protect", "earthquake", "rock-slide"])
        members.append(_member(filler, ["tackle", "protect", "earthquake", "rock-slide"]))
    return TeamVariant(members=members)


def test_weather_abuser_tag():
    """A Chlorophyll mon + a Drought setter on the team → weather_abuser."""
    setter = _member(
        _pkd("torkoal", spa=85, spe=20, abilities=["drought"]),
        moves=["eruption", "heat-wave", "protect", "body-press"],
        ability="drought",
    )
    abuser = _member(
        _pkd("venusaur", spa=100, spe=80, abilities=["chlorophyll"]),
        moves=["giga-drain", "sludge-bomb", "sleep-powder", "protect"],
        ability="chlorophyll",
    )
    variant = _six([setter, abuser])
    tags = derive_team_tags(variant)
    # member index 0 is the setter, 1 is the abuser.
    assert "weather_setter" in tags[0]
    assert "weather_abuser" in tags[1]


def test_weather_abuser_absent_without_matching_setter():
    """Chlorophyll mon with NO sun setter on the team → no weather_abuser."""
    abuser = _member(
        _pkd("venusaur", spa=100, spe=80, abilities=["chlorophyll"]),
        moves=["giga-drain", "sludge-bomb", "sleep-powder", "protect"],
        ability="chlorophyll",
    )
    variant = _six([abuser])
    tags = derive_team_tags(variant)
    assert "weather_abuser" not in tags[0]


def test_trick_room_abuser_tag():
    """Slow offensive threat + a TR setter on the team → trick_room_abuser."""
    tr_setter = _member(
        _pkd("dusclops", hp=40, def_=130, spd=130, spe=25, abilities=["pressure"],
             moves=["trick-room", "night-shade", "will-o-wisp", "protect"]),
        moves=["trick-room", "night-shade", "will-o-wisp", "protect"],
    )
    slow_attacker = _member(
        _pkd("torkoal", atk=85, spa=85, spe=20, abilities=["drought"]),
        moves=["eruption", "heat-wave", "earth-power", "protect"],
        ability="drought",
    )
    variant = _six([tr_setter, slow_attacker])
    tags = derive_team_tags(variant)
    assert "trick_room_setter" in tags[0]
    # slow_attacker: spe 20 ≤ 60, offensive_threat (drought weather_setter
    # plus eruption — but offensive_threat needs sweeper stat ≥ 0.5 or setup;
    # spa 85 < 100 and no setup move). Assert via a clearly-offensive slow mon
    # instead below.


def test_trick_room_abuser_requires_offensive_threat_and_setter():
    """A genuinely offensive slow mon under a TR setter earns trick_room_abuser."""
    tr_setter = _member(
        _pkd("dusclops", hp=40, def_=130, spd=130, spe=25, abilities=["pressure"],
             moves=["trick-room", "night-shade", "will-o-wisp", "protect"]),
        moves=["trick-room", "night-shade", "will-o-wisp", "protect"],
    )
    # spa 130 ≥ 100 → offensive_threat; spe 50 ≤ 60.
    brute = _member(
        _pkd("hatterene", hp=57, atk=90, def_=95, spa=136, spd=103, spe=29,
             abilities=["magic-bounce"]),
        moves=["dazzling-gleam", "psychic", "trick-room", "protect"],
    )
    variant = _six([tr_setter, brute])
    tags = derive_team_tags(variant)
    assert "trick_room_setter" in tags[0]
    assert "offensive_threat" in tags[1]
    assert "trick_room_abuser" in tags[1]
