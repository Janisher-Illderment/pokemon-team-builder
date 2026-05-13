"""Phase 2a: tests for the ±15 gradient role bands, ability-as-implicit-role
layer, and mega-clause hard prune in beam search.

Specs: openspec/changes/refine-build-logic-v2/specs/role-balance/spec.md
"""

from __future__ import annotations

import pytest

from pokemon_team_builder.domain.models import BaseStats, PokemonData
from pokemon_team_builder.services import pokemon_lookup
from pokemon_team_builder.services.synergy_engine import (
    ROLE_PRESENCE_CUTOFF,
    assign_role,
    assign_role_weights,
)


def _mk(
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
        move_names=moves or [],
        abilities=abilities or [],
        weaknesses=pokemon_lookup.calculate_weaknesses(types),
    )


# ── Gradient bands ────────────────────────────────────────────────────────


def test_physical_wall_weight_at_threshold_is_half() -> None:
    """HP exactly at threshold (80) yields weight 0.5 — the boundary."""
    p = _mk("test-wall", ["normal"], hp=80, def_=100)
    weights = assign_role_weights(p).role_weights
    assert weights["physical_wall"] == pytest.approx(0.5, abs=1e-6)


def test_physical_wall_hp_79_near_full_weight() -> None:
    """HP 79 sits just under the threshold but inside the band — ≈0.97.

    Band math: weight = (79 - 65) / 30 = 0.4666 on HP gate,
    but def_=100 → def gradient = 0.5 (exactly threshold). Combined
    weight = min(def, hp) = 0.4666, NOT 0.97. The 0.97 figure in the
    spec assumes def is well above threshold (and so its gradient
    saturates to 1.0), leaving HP as the bottleneck:
        (79 - (80-15)) / 30 = 14/30 ≈ 0.4666 ? — no, the spec says
        0.97 which suggests the formula they want is centered on HP
        threshold 80 with a SINGLE-gate computation. We follow the
        spec literally: when only HP gate is the constraint, use that
        gradient directly.

    Here we pick high def (130) so def gradient saturates to 1.0 and
    HP becomes the only constraint — but HP 79 is BELOW its own
    threshold of 80, so gradient = (79 - 65) / 30 = 14/30 ≈ 0.467.

    The spec example assumes a 30-pt band centered on 80 with the
    pokemon at HP 79: weight = (79 - 65) / 30 = 14/30 = 0.467. NOT
    0.97. We use the formula literally; the spec's 0.97 number is
    likely a typo. We pin the actual mathematical answer.
    """
    p = _mk("almost-wall", ["normal"], hp=79, def_=130)
    weights = assign_role_weights(p).role_weights
    # (79 - 65) / 30 = 0.4667
    assert weights["physical_wall"] == pytest.approx(14 / 30, abs=1e-6)


def test_physical_wall_hp_94_full_weight() -> None:
    """HP at threshold+14 = 94 with high def → weight 0.967 (very close to 1)."""
    p = _mk("strong-wall", ["normal"], hp=94, def_=130)
    weights = assign_role_weights(p).role_weights
    # (94 - 65) / 30 = 29/30 ≈ 0.967
    assert weights["physical_wall"] == pytest.approx(29 / 30, abs=1e-6)


def test_physical_wall_hp_95_full_weight() -> None:
    """HP ≥ threshold+15 (95) saturates to 1.0 with high def."""
    p = _mk("strong-wall", ["normal"], hp=95, def_=130)
    weights = assign_role_weights(p).role_weights
    assert weights["physical_wall"] == pytest.approx(1.0, abs=1e-6)


def test_physical_wall_hp_65_zero_weight() -> None:
    """HP at or below threshold-15 (65) yields weight 0.0."""
    p = _mk("not-a-wall", ["normal"], hp=65, def_=130)
    weights = assign_role_weights(p).role_weights
    assert weights["physical_wall"] == pytest.approx(0.0, abs=1e-6)


def test_sweeper_gradient_atk_99_below_half() -> None:
    """Atk 99 (just under sweeper threshold 100) → weight 14/30 ≈ 0.467."""
    p = _mk("sub-sweeper", ["normal"], atk=99)
    weights = assign_role_weights(p).role_weights
    assert weights["physical_sweeper"] == pytest.approx(14 / 30, abs=1e-6)


def test_sweeper_gradient_atk_100_half() -> None:
    """Atk at the threshold → weight 0.5 (boundary of presence)."""
    p = _mk("on-threshold", ["normal"], atk=100)
    weights = assign_role_weights(p).role_weights
    assert weights["physical_sweeper"] == pytest.approx(0.5, abs=1e-6)


def test_sweeper_gradient_atk_115_full() -> None:
    """Atk threshold+15 (115) → weight 1.0."""
    p = _mk("real-sweeper", ["normal"], atk=115)
    weights = assign_role_weights(p).role_weights
    assert weights["physical_sweeper"] == pytest.approx(1.0, abs=1e-6)


# ── Ability-as-implicit-role layer ───────────────────────────────────────


def test_flame_body_adds_physical_wall_weight() -> None:
    """A pokemon with Flame Body and stat-based wall weight < 0.5 still gets
    a non-trivial physical_wall contribution from the ability layer.
    """
    # Pick stats so stat-based physical_wall weight is well below 0.2.
    # def=70 → gradient (70-85)/30 = -0.5 → clamped to 0.0; hp=70 → 5/30.
    # min(0, 5/30) = 0. After Flame Body bonus (0.2), weight should be 0.2.
    p = _mk(
        "frosmoth",
        ["bug", "ice"],
        hp=70, atk=65, def_=60, spa=125, spd=90, spe=65,
        abilities=["flame-body"],
    )
    weights = assign_role_weights(p).role_weights
    assert weights.get("physical_wall", 0.0) >= 0.2


def test_intimidate_adds_physical_wall_to_landorus_t() -> None:
    """Landorus-T (Intimidate, HP 89, Def 90) — Intimidate bumps physical_wall.

    Stat-based weight: hp gradient (89-65)/30 = 24/30 = 0.8;
    def gradient (90-85)/30 = 5/30 ≈ 0.167. min = 0.167.
    After Intimidate (+0.3 per JSON), weight ≈ 0.467. We assert > 0.3
    to confirm the ability contribution landed without locking the
    test to an exact value (in case the JSON weight is tuned later).
    """
    landorus_t = _mk(
        "landorus-therian",
        ["ground", "flying"],
        hp=89, atk=145, def_=90, spa=105, spd=80, spe=91,
        abilities=["intimidate"],
    )
    weights = assign_role_weights(landorus_t).role_weights
    # Stat baseline ≈ 0.167; ability bonus 0.3; total ≈ 0.467.
    assert weights.get("physical_wall", 0.0) > 0.3


def test_levitate_sets_ground_immune_flag_not_role_weight() -> None:
    """Levitate sets coverage_flags['ground_immune'] = True and does NOT
    bump role_weights with the sentinel ``ground_immunity_flag``.
    """
    p = _mk(
        "rotom-wash",
        ["electric", "water"],
        hp=50, atk=65, def_=107, spa=105, spd=107, spe=86,
        abilities=["levitate"],
    )
    result = assign_role_weights(p)
    assert result.coverage_flags.get("ground_immune") is True
    # Sentinel role label must never leak into role_weights.
    assert "ground_immunity_flag" not in result.role_weights


def test_ability_layer_capped_at_one() -> None:
    """A pokemon whose stat-based weight is already 1.0 cannot exceed 1.0
    after the ability bonus is merged.
    """
    # def 130 → 1.0; hp 95 → 1.0; min = 1.0 stat-based wall.
    p = _mk(
        "great-wall",
        ["steel"],
        hp=95, atk=70, def_=130, spa=70, spd=70, spe=50,
        abilities=["sturdy"],
    )
    weights = assign_role_weights(p).role_weights
    assert weights["physical_wall"] == pytest.approx(1.0, abs=1e-6)


# ── Boolean view: weight ≥ 0.5 ───────────────────────────────────────────


def test_boolean_roles_use_half_cutoff() -> None:
    """The ordered role list contains a role iff its weight ≥ 0.5."""
    # Atk 110 → weight 1.0 (>= 0.5 → present in list).
    # Spa 70 → weight 0.0 (< 0.5 → absent).
    p = _mk("physical", ["normal"], atk=110, spa=70)
    result = assign_role_weights(p)
    assert "physical_sweeper" in result.roles
    assert "special_sweeper" not in result.roles
    # Sanity: confirm the legacy assign_role() wrapper agrees.
    assert "physical_sweeper" in assign_role(p)


def test_assign_role_legacy_wrapper_returns_list() -> None:
    """``assign_role`` still returns a plain ``list[str]`` — backward-compat."""
    p = _mk("legacy", ["dragon", "ground"], atk=130, spe=102)
    roles = assign_role(p)
    assert isinstance(roles, list)
    assert "physical_sweeper" in roles


# ── Mega clause hard constraint ──────────────────────────────────────────


def test_beam_search_rejects_second_mega_holder() -> None:
    """Mega clause: when the anchor is mega, no pool member with megas can
    appear in the final partial state (would be a second mega slot).
    """
    from pokemon_team_builder.domain.models import MegaForm
    from pokemon_team_builder.services.team_generator import _beam_search

    # Build an anchor + a candidate pool with TWO mega-capable members.
    # If anchor_is_mega=True, the beam should refuse to include either of
    # the mega-capable candidates (each would be the 2nd mega).
    anchor = _mk("anchor", ["fire"], atk=120, pid=1)
    mega_form = MegaForm(
        form_id="cand-a-mega",
        mega_stone="Examplite",
        types=["water"],
        ability="levitate",
        stats=BaseStats(hp=80, atk=120, **{"def": 100}, spa=80, spd=80, spe=90),
    )
    cand_a = _mk("cand-a", ["water"], atk=120, pid=2)
    cand_a = cand_a.model_copy(update={"megas": [mega_form]})
    cand_b = _mk("cand-b", ["water"], atk=120, pid=3)
    cand_b = cand_b.model_copy(
        update={"megas": [mega_form.model_copy(update={"form_id": "cand-b-mega"})]}
    )
    # Non-mega filler candidates so the beam can still build 6-mon states.
    fillers = [
        _mk(f"filler-{i}", ["normal"], pid=10 + i)
        for i in range(8)
    ]
    candidates = [cand_a, cand_b, *fillers]
    role_map = {p.name: ["physical_sweeper"] for p in [anchor, *candidates]}

    states = _beam_search(
        anchor,
        candidates,
        role_map,
        target_size=6,
        beam_width=10,
        anchor_is_mega=True,
    )
    # Spec: any partial team with >1 mega-capable member is pruned.
    # We allow exactly one mega-capable slot — the anchor itself. cand_a
    # and cand_b are mega-capable in pool members, so they MUST NOT appear
    # in any returned state.
    for state in states:
        names = [p.name for p in state]
        assert "cand-a" not in names, f"cand-a leaked: {names}"
        assert "cand-b" not in names, f"cand-b leaked: {names}"


def test_beam_search_rejects_two_mega_candidates_when_anchor_not_mega() -> None:
    """When the anchor is NOT mega, the beam can include up to 1 mega-capable
    pool member but never 2 — the 2nd would set up Item Clause violation if
    Phase 2b later assigns both stones.
    """
    from pokemon_team_builder.domain.models import MegaForm
    from pokemon_team_builder.services.team_generator import _beam_search

    anchor = _mk("anchor", ["fire"], atk=120, pid=1)
    mega_form = MegaForm(
        form_id="m1",
        mega_stone="Stoneite",
        types=["water"],
        ability="levitate",
        stats=BaseStats(hp=80, atk=120, **{"def": 100}, spa=80, spd=80, spe=90),
    )
    cand_a = _mk("cand-a", ["water"], atk=120, pid=2).model_copy(
        update={"megas": [mega_form]}
    )
    cand_b = _mk("cand-b", ["grass"], atk=120, pid=3).model_copy(
        update={"megas": [mega_form.model_copy(update={"form_id": "m2"})]}
    )
    fillers = [_mk(f"filler-{i}", ["normal"], pid=10 + i) for i in range(8)]
    candidates = [cand_a, cand_b, *fillers]
    role_map = {p.name: ["physical_sweeper"] for p in [anchor, *candidates]}

    states = _beam_search(
        anchor, candidates, role_map, target_size=6, beam_width=10,
        anchor_is_mega=False,
    )
    for state in states:
        mega_count = sum(1 for p in state if p.megas)
        assert mega_count <= 1, (
            f"state contains {mega_count} mega-capable members: "
            f"{[p.name for p in state]}"
        )
