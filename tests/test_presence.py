"""C2 — offensive-presence tests (ADR §2.1, docs/vgc-principles.md §2).

A Pokémon with neither an offensive stat (atk/spa gradient weight ≥ 0.5,
≈ base stat ≥ 100) nor real disruption is a *passive liability* in VGC
Doubles: the opponent ignores it and doubles its attacks onto the ally.

Base stats below are the real species values (Gen 9). See the module-level
note on Garganacl: its real Atk of 100 sits exactly at the gradient
midpoint (weight 0.5), so under the literal §2.1 formula it reads as
"has_offensive_stat" rather than as a liability — a boundary artifact
flagged to Sola. Blissey and Toxapex are unambiguous liability cases and
stand in for the §5.1 canonical "passive wall" assertion here.
"""

from __future__ import annotations

from pokemon_team_builder.domain.models import BaseStats, PokemonData
from pokemon_team_builder.services.synergy_engine import (
    PresenceReport,
    assess_presence,
)


def _mk(
    name: str,
    *,
    hp: int,
    atk: int,
    def_: int,
    spa: int,
    spd: int,
    spe: int,
    abilities: list[str] | None = None,
    moves: list[str] | None = None,
) -> PokemonData:
    return PokemonData(
        id=1,
        name=name,
        types=["normal"],
        base_stats=BaseStats(hp=hp, atk=atk, **{"def": def_}, spa=spa, spd=spd, spe=spe),
        move_names=moves or [],
        abilities=abilities or ["pressure"],
        weaknesses={},
    )


# ── Passive liability: bulky, no offensive stat, no disruption ────────────────

def test_blissey_is_passive_liability():
    """Blissey (Atk 10 / SpA 75): no offensive stat, no disruption → liability."""
    blissey = _mk(
        "blissey", hp=255, atk=10, def_=10, spa=75, spd=135, spe=55,
        abilities=["natural-cure"],
        moves=["soft-boiled", "protect", "seismic-toss", "heal-bell"],
    )
    report = assess_presence(blissey)
    assert isinstance(report, PresenceReport)
    assert report.has_offensive_stat is False
    assert report.has_disruption is False
    assert report.is_passive_liability is True
    assert report.presence_weight == 0.0


def test_passive_wall_no_disruption_is_liability():
    """A Toxapex-profile wall with purely defensive moves is a liability."""
    wall = _mk(
        "toxapex", hp=50, atk=63, def_=152, spa=53, spd=142, spe=35,
        abilities=["regenerator"],
        moves=["recover", "protect", "baneful-bunker", "haze"],
    )
    report = assess_presence(wall)
    assert report.has_offensive_stat is False
    assert report.has_disruption is False
    assert report.is_passive_liability is True


def test_passive_wall_with_status_is_not_liability():
    """Same wall but carrying Toxic (pure status) → has disruption, not a liability.

    Demonstrates the disruption axis rescues an otherwise-passive bulky mon
    (ADR §2.3): a wall that pressures the opponent is not ignored.
    """
    wall = _mk(
        "toxapex", hp=50, atk=63, def_=152, spa=53, spd=142, spe=35,
        abilities=["regenerator"],
        moves=["recover", "protect", "toxic", "haze"],
    )
    report = assess_presence(wall)
    assert report.has_offensive_stat is False
    assert report.has_disruption is True
    assert "estado" in report.disruption_sources
    assert report.is_passive_liability is False
    assert report.presence_weight == 1.0


# ── Disruption rescues a non-offensive mon (Incineroar / Intimidate) ──────────

def test_incineroar_intimidate_has_disruption_not_liability():
    """Incineroar (Atk 115 but the canonical case is its Intimidate disruption).

    Spec §5.1: Intimidate → has_disruption=True, is_passive_liability=False.
    """
    incineroar = _mk(
        "incineroar", hp=95, atk=115, def_=90, spa=80, spd=90, spe=60,
        abilities=["intimidate"],
        moves=["fake-out", "flare-blitz", "parting-shot", "knock-off"],
    )
    report = assess_presence(incineroar)
    assert report.has_disruption is True
    assert "intimidación" in report.disruption_sources
    assert report.is_passive_liability is False


def test_intimidate_alone_rescues_a_weak_mon():
    """Intimidate makes even a non-offensive mon non-passive (ability override).

    Uses a deliberately weak body (atk/spa well below 100, no disruptive
    moves) so the only disruption signal is the ability itself.
    """
    mon = _mk(
        "intimidate-pivot", hp=80, atk=70, def_=110, spa=60, spd=110, spe=50,
        abilities=["intimidate"],
        moves=["protect", "recover", "iron-defense", "body-press"],
    )
    report = assess_presence(mon)
    assert report.has_offensive_stat is False
    assert report.has_disruption is True
    assert report.is_passive_liability is False


# ── Pure offensive threat ─────────────────────────────────────────────────────

def test_pure_sweeper_has_offensive_stat():
    """Chi-Yu (SpA 135): pure special sweeper → has_offensive_stat=True."""
    chi_yu = _mk(
        "chi-yu", hp=55, atk=55, def_=80, spa=135, spd=120, spe=100,
        abilities=["beads-of-ruin"],
        moves=["heat-wave", "dark-pulse", "protect", "nasty-plot"],
    )
    report = assess_presence(chi_yu)
    assert report.has_offensive_stat is True
    assert report.is_passive_liability is False
    assert report.presence_weight == 1.0  # SpA 135 → gradient weight 1.0


def test_physical_sweeper_has_offensive_stat():
    """A high-Atk physical attacker reads as offensive presence."""
    chomp = _mk(
        "garchomp", hp=108, atk=130, def_=95, spa=80, spd=85, spe=102,
        abilities=["rough-skin"],
        moves=["earthquake", "dragon-claw", "rock-slide", "protect"],
    )
    report = assess_presence(chomp)
    assert report.has_offensive_stat is True
    assert report.is_passive_liability is False


# ── Override / fallback behaviour ─────────────────────────────────────────────

def test_moves_override_takes_precedence_over_move_names():
    """assess_presence uses the passed moveset, not pokemon.move_names.

    The species knows Fake Out in its learnset, but the *assigned* moveset
    omits it → no fake-out disruption from that move.
    """
    mon = _mk(
        "tornadus", hp=79, atk=115, def_=70, spa=125, spd=80, spe=111,
        abilities=["prankster"],
        moves=["fake-out", "u-turn", "protect", "tailwind"],  # learnset
    )
    # Assigned moveset has no fake-out and no other disruption; but SpA 125
    # already makes it offensive, so liability is False regardless.
    report = assess_presence(mon, moves=["acrobatics", "hurricane", "protect", "rain-dance"])
    assert report.has_offensive_stat is True
    # Fake-out from the learnset must NOT leak in.
    assert "sorpresa (fake-out)" not in report.disruption_sources


def test_ability_override_detects_intimidate():
    """ability override is honoured even when pokemon.abilities[0] differs."""
    mon = _mk(
        "wildcard", hp=80, atk=70, def_=90, spa=60, spd=90, spe=70,
        abilities=["pressure"],  # default ability is not intimidate
        moves=["protect", "recover", "wish", "body-press"],
    )
    report = assess_presence(mon, ability="intimidate")
    assert report.has_disruption is True
    assert "intimidación" in report.disruption_sources
    assert report.is_passive_liability is False


def test_redirect_and_ally_boost_detected():
    """Redirection (Rage Powder) and ally boost (Helping Hand) are disruption."""
    amoonguss = _mk(
        "amoonguss", hp=114, atk=85, def_=70, spa=85, spd=80, spe=30,
        abilities=["regenerator"],
        moves=["rage-powder", "spore", "pollen-puff", "protect"],
    )
    report = assess_presence(amoonguss)
    assert report.has_offensive_stat is False
    assert "redirección" in report.disruption_sources
    assert "estado" in report.disruption_sources  # spore
    assert report.is_passive_liability is False

    coacher = _mk(
        "coacher", hp=80, atk=70, def_=90, spa=60, spd=90, spe=70,
        abilities=["pressure"],
        moves=["coaching", "protect", "recover", "wish"],
    )
    creport = assess_presence(coacher)
    assert "boost a aliado" in creport.disruption_sources
    assert creport.is_passive_liability is False
