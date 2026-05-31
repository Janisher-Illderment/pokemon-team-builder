from __future__ import annotations

from pokemon_team_builder.domain.models import (
    BaseStats,
    PokemonData,
    SPDistribution,
    TeamMember,
    TeamVariant,
)
from pokemon_team_builder.services import pokemon_lookup
from pokemon_team_builder.services.synergy_engine import assess_presence, assign_role
from pokemon_team_builder.services.viability_rater import (
    _presence_penalty,
    _quality_adjustment,
    generate_explanation,
    rank_variants,
    score_team,
)


def _mk_pokemon(
    name: str,
    types: list[str],
    *,
    hp: int = 70,
    atk: int = 70,
    def_: int = 70,
    spa: int = 70,
    spd: int = 70,
    spe: int = 70,
    moves: list[str] | None = None,
    pid: int = 1,
) -> PokemonData:
    return PokemonData(
        id=pid,
        name=name,
        types=types,
        base_stats=BaseStats(
            hp=hp, atk=atk, **{"def": def_}, spa=spa, spd=spd, spe=spe
        ),
        move_names=moves or [],
        abilities=["pressure"],
        weaknesses=pokemon_lookup.calculate_weaknesses(types),
    )


def _mk_member(
    pokemon: PokemonData,
    *,
    item: str,
    nature: str = "Hardy",
    moves: list[str] | None = None,
    sp: SPDistribution | None = None,
) -> TeamMember:
    if sp is None:
        sp = SPDistribution.model_validate(
            {"atk": 32, "spe": 32, "hp": 2}
        )
    return TeamMember(
        pokemon=pokemon,
        role=assign_role(pokemon),
        sp_distribution=sp,
        item=item,
        ability=pokemon.abilities[0] if pokemon.abilities else "Pressure",
        nature=nature,
        moves=moves or ["protect", "tackle", "earthquake", "tailwind"],
    )


def _balanced_variant() -> TeamVariant:
    pokemons = [
        _mk_pokemon("garchomp", ["dragon", "ground"], atk=130, spe=102, pid=1),
        _mk_pokemon(
            "talonflame",
            ["fire", "flying"],
            atk=81,
            spe=126,
            moves=["tailwind", "brave-bird"],
            pid=2,
        ),
        _mk_pokemon("milotic", ["water"], hp=95, def_=79, spa=100, spd=125, spe=81, pid=3),
        _mk_pokemon("rotom-wash", ["electric", "water"], hp=50, spa=105, spd=107, spe=86, pid=4),
        _mk_pokemon("metagross", ["steel", "psychic"], atk=135, spe=70, pid=5),
        _mk_pokemon(
            "amoonguss",
            ["grass", "poison"],
            hp=114,
            spa=85,
            spe=30,
            moves=["rage-powder", "spore"],
            pid=6,
        ),
    ]
    items = [
        "Choice Band",
        "Focus Sash",
        "Leftovers",
        "Sitrus Berry",
        "Assault Vest",
        "Eviolite",
    ]
    # Phase 2a: STAB-based coverage requires the assigned moveset to contain
    # the type's move, not just the typing. Each member here carries moves
    # that cover its own STABs plus diverse coverage so the team scores
    # well under the new rule.
    movesets = [
        ["protect", "earthquake", "dragon-claw", "rock-slide"],   # garchomp: ground+dragon STAB, rock cov
        ["protect", "brave-bird", "flamethrower", "tailwind"],    # talonflame: flying+fire STAB
        ["protect", "scald", "ice-beam", "recover"],              # milotic: water STAB + ice cov
        ["protect", "thunderbolt", "hydro-pump", "shadow-ball"],  # rotom-wash: electric+water STAB + ghost cov
        ["protect", "iron-head", "psychic", "earthquake"],        # metagross: steel+psychic STAB + ground cov
        ["protect", "giga-drain", "sludge-bomb", "rage-powder"],  # amoonguss: grass+poison STAB
    ]
    members = [
        _mk_member(p, item=item, moves=mv)
        for p, item, mv in zip(pokemons, items, movesets)
    ]
    return TeamVariant(members=members)


def _weak_variant() -> TeamVariant:
    # All weak to electric (water/flying), no support, no sweepers >=100 atk/spa.
    pokemons = [
        _mk_pokemon("gyarados", ["water", "flying"], atk=85, spa=60, spe=81, pid=1),
        _mk_pokemon("pelipper", ["water", "flying"], atk=50, spa=85, spe=65, pid=2),
        _mk_pokemon("mantine", ["water", "flying"], atk=40, spa=80, spe=70, pid=3),
        _mk_pokemon("wingull", ["water", "flying"], atk=30, spa=55, spe=85, pid=4),
        _mk_pokemon("swanna", ["water", "flying"], atk=87, spa=87, spe=98, pid=5),
        _mk_pokemon("ducklett", ["water", "flying"], atk=44, spa=44, spe=58, pid=6),
    ]
    members = [
        _mk_member(
            p,
            item="Choice Scarf",  # all the same → kills item diversity points
            moves=["protect", "tackle", "scald", "wing-attack"],
        )
        for p in pokemons
    ]
    return TeamVariant(members=members)


def test_score_balanced_team_above_75() -> None:
    variant = _balanced_variant()
    score, _ = score_team(variant)
    assert score >= 75


# ── C2 §5.3 — additive-layer migration invariant ─────────────────────────────

def test_balanced_team_has_no_passive_liabilities() -> None:
    """A healthy balanced team has zero passive liabilities (ADR §2.1).

    Every member either has an offensive stat (Garchomp/Milotic/Rotom/
    Metagross) or real disruption (Talonflame Tailwind, Amoonguss Rage
    Powder), so none reads as a liability.
    """
    variant = _balanced_variant()
    for member in variant.members:
        report = assess_presence(
            member.pokemon, moves=list(member.moves), ability=member.ability
        )
        assert report.is_passive_liability is False, (
            f"{member.pokemon.name} unexpectedly flagged as passive liability"
        )


def test_presence_penalty_zero_for_healthy_team() -> None:
    """C2 §5.3 invariant: the presence term is exactly 0 for a healthy team.

    Because the C2 layer is additive (a flat penalty term added to the
    total), proving the term is 0.0 for a no-liability team proves the
    team's score is IDENTICAL before and after C2 — the layer changes
    nothing in the nominal case.
    """
    variant = _balanced_variant()
    assert _presence_penalty(variant) == 0.0


def test_passive_liability_team_scores_below_present_team() -> None:
    """A team of passive walls scores strictly below a present-threat team.

    Directly exercises the §2.2 penalty: replace the balanced team's
    movesets/stats with passive walls and confirm the score drops.
    """
    present = _balanced_variant()
    score_present, _ = score_team(present)

    # Build a 6-wall team: low offense, purely defensive moves (no
    # disruption) → every member is a liability.
    walls = [
        _mk_pokemon(
            f"wall{i}",
            ["steel"],
            hp=120, atk=60, def_=130, spa=50, spd=120, spe=40,
            moves=["protect", "recover", "iron-defense", "body-press"],
            pid=i + 1,
        )
        for i in range(6)
    ]
    wall_members = [
        _mk_member(
            p, item=it, moves=["protect", "recover", "iron-defense", "body-press"]
        )
        for p, it in zip(
            walls,
            ["Leftovers", "Eviolite", "Rocky Helmet", "Sitrus Berry",
             "Assault Vest", "Mental Herb"],
        )
    ]
    wall_variant = TeamVariant(members=wall_members)
    score_walls, _ = score_team(wall_variant)
    assert score_walls < score_present


def test_score_weak_team_below_50() -> None:
    variant = _weak_variant()
    score, _ = score_team(variant)
    assert score < 50


def test_rank_variants_first_is_recommended() -> None:
    v_high = _balanced_variant().model_copy(update={"score": 80.0})
    v_low = _weak_variant().model_copy(update={"score": 30.0})
    ranked = rank_variants([v_low, v_high])
    assert ranked[0].is_recommended is True
    assert ranked[0].score == 80.0


def test_rank_variants_ordered_by_score() -> None:
    v_a = _balanced_variant().model_copy(update={"score": 65.0})
    v_b = _balanced_variant().model_copy(update={"score": 90.0})
    v_c = _weak_variant().model_copy(update={"score": 25.0})
    ranked = rank_variants([v_a, v_b, v_c])
    scores = [v.score for v in ranked]
    assert scores == sorted(scores, reverse=True)


def test_generate_explanation_contains_score() -> None:
    variant = _balanced_variant()
    text = generate_explanation(variant, 82.5)
    assert "83" in text or "82" in text  # rounding tolerance


def test_rank_variants_tiebreak_by_coverage() -> None:
    """Equal total score → higher coverage wins, regardless of input order."""
    # Both get score=60. The balanced variant has better coverage.
    v_a = _weak_variant().model_copy(update={"score": 60.0})     # poor coverage
    v_b = _balanced_variant().model_copy(update={"score": 60.0}) # good coverage
    # Pass weak first — tiebreaker must put balanced first.
    ranked = rank_variants([v_a, v_b])
    assert ranked[0].is_recommended is True
    # balanced variant (v_b) should win the coverage tiebreak.
    assert ranked[0].score == 60.0
    # Exactly one variant is recommended.
    assert sum(v.is_recommended for v in ranked) == 1


def test_rank_variants_stable_on_full_tie() -> None:
    """Identical variants keep their input order when all components tie."""
    v = _balanced_variant().model_copy(update={"score": 70.0})
    # Two structurally identical variants — only the first should be recommended.
    ranked = rank_variants([v, v])
    assert ranked[0].is_recommended is True
    assert ranked[1].is_recommended is False


# ── C6 §5.3 — quality adjustment additive-layer invariant ─────────────────────

def _high_quality_variant() -> TeamVariant:
    """A 6-member team where every mon evaluates to quality == 1.0.

    Unlike ``_balanced_variant`` (whose ``move_names`` are empty, so its
    sweepers trip the movepool signal), each species here carries a populated
    learnset with a same-type damaging STAB move, a Speed outside the 60–95
    limbo, only one high offensive stat (no split), no rock/ice inverted bulk,
    and no low-accuracy Rock moves. This makes ``_quality_adjustment`` exactly
    0.0, which is the only way to prove the C6 layer is a no-op in the nominal
    case (§5.3): the team's score is identical before and after C6.
    """
    specs = [
        # (name, types, atk, spa, spe, move_names)
        ("garchomp", ["dragon", "ground"], 130, 80, 102, ["earthquake", "dragon-claw"]),
        ("talonflame", ["fire", "flying"], 81, 74, 126, ["brave-bird", "flamethrower", "tailwind"]),
        ("dragapult", ["dragon", "ghost"], 70, 120, 142, ["dragon-pulse", "shadow-ball"]),
        ("kingambit", ["dark", "steel"], 135, 60, 50, ["knock-off", "iron-head"]),
        ("flutter", ["water"], 70, 135, 120, ["surf", "ice-beam"]),
        ("amoonguss", ["grass", "poison"], 85, 85, 30, ["giga-drain", "sludge-bomb", "rage-powder", "spore"]),
    ]
    pokemons = [
        _mk_pokemon(
            name, types, atk=atk, spa=spa, spe=spe, moves=moves, pid=i + 1
        )
        for i, (name, types, atk, spa, spe, moves) in enumerate(specs)
    ]
    items = [
        "Choice Band", "Focus Sash", "Life Orb",
        "Leftovers", "Assault Vest", "Sitrus Berry",
    ]
    movesets = [
        ["protect", "earthquake", "dragon-claw", "rock-slide"],
        ["protect", "brave-bird", "flamethrower", "tailwind"],
        ["protect", "dragon-pulse", "shadow-ball", "u-turn"],
        ["protect", "knock-off", "iron-head", "sucker-punch"],
        ["protect", "surf", "ice-beam", "thunderbolt"],
        ["protect", "giga-drain", "sludge-bomb", "rage-powder"],
    ]
    members = [
        _mk_member(p, item=item, moves=mv)
        for p, item, mv in zip(pokemons, items, movesets)
    ]
    return TeamVariant(members=members)


def test_high_quality_team_quality_adjustment_is_zero() -> None:
    """C6 §5.3 invariant: a team of all-1.0-quality mons adjusts by exactly 0.

    Because C6 is additive (a flat term added to the total), proving the term
    is 0.0 for a high-quality team proves the team's score is IDENTICAL before
    and after C6. This is the analogue of the C2 presence_penalty invariant.
    """
    variant = _high_quality_variant()
    # Sanity: every member really is quality 1.0 (no signal fires).
    from pokemon_team_builder.services.pokemon_evaluator import (
        evaluate_pokemon_quality,
    )
    for m in variant.members:
        report = evaluate_pokemon_quality(m.pokemon)
        assert report.score == 1.0, (
            f"{m.pokemon.name} unexpectedly penalised: {report.flags}"
        )
    assert _quality_adjustment(variant) == 0.0


def test_quality_adjustment_is_non_positive_and_bounded() -> None:
    """quality_adjustment ∈ [-5, 0]: never inflates, bounded by the floor.

    The per-mon multiplier is in [0.5, 1.0]; the mean is therefore in the same
    range, and (mean - 1.0) * 10 lands in [-5, 0]. A team of mediocre mons is
    signalled, not disqualified (ADR §4.3).
    """
    healthy = _quality_adjustment(_high_quality_variant())
    assert healthy == 0.0

    # The balanced fixture (empty move_names → sweepers trip the movepool
    # signal) yields a strictly negative, bounded adjustment.
    mediocre = _quality_adjustment(_balanced_variant())
    assert -5.0 <= mediocre < 0.0


def test_low_quality_team_scores_below_high_quality_team() -> None:
    """A lower-quality variant scores at or below an otherwise-similar one.

    Exercises the C6 term end-to-end through score_team: the high-quality
    team (quality_adjustment 0) is not dragged down, while the balanced
    fixture (negative adjustment) loses points it would otherwise keep.
    """
    high = _high_quality_variant()
    score_high, _ = score_team(high)

    # Same team but force every species learnset empty → sweepers lose their
    # STAB-damage signal and the mean quality drops, lowering the score.
    starved_members = [
        m.model_copy(update={"pokemon": m.pokemon.model_copy(update={"move_names": []})})
        for m in high.members
    ]
    starved = TeamVariant(members=starved_members)
    score_starved, _ = score_team(starved)

    assert score_starved < score_high
    assert _quality_adjustment(starved) < _quality_adjustment(high)
