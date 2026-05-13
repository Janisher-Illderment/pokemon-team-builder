from __future__ import annotations

import itertools
import math

from pokemon_team_builder.config import MAX_SP_TOTAL
from pokemon_team_builder.data.archetype_weights_loader import get_weights
from pokemon_team_builder.domain.models import TeamMember, TeamVariant
from pokemon_team_builder.services.synergy_engine import (
    analyze_coverage,
    score_flexibility,
)


# Weight budgets per component. Sum to 100.
_W_COVERAGE = 35
_W_ROLES = 35
_W_SPS = 15
_W_ITEMS = 15

# Bo3 weights (coverage 30; roles replaced by lead_flex + core_div)
_W_COVERAGE_BO3 = 30
_W_LEAD_FLEX = 25
_W_CORE_DIV = 15

_SWEEPER_ROLES = frozenset({"physical_sweeper", "special_sweeper"})
_SUPPORT_ROLES = frozenset({"lead_support", "redirect"})

_LEAD_VIABLE_MOVES = frozenset({
    "tailwind", "trick-room", "fake-out", "extreme-speed", "quick-attack",
    "helping-hand", "thunder-wave", "icy-wind", "follow-me", "rage-powder",
})

_BO3_SWEEPER_ROLES = frozenset({"physical_sweeper", "special_sweeper"})
_BO3_SUPPORT_ROLES = frozenset({"lead_support", "redirect", "trick_room_setter"})


def _lead_flexibility_points(members: list[TeamMember]) -> tuple[float, float]:
    """Return (raw_ratio 0-1, points) for Bo3 lead flexibility.

    Iterates all C(6,4)=15 combinations; a combo is lead-viable if at least
    one member has a speed-control or redirect move in its moveset.
    Returns (viable/15, ratio * _W_LEAD_FLEX).
    """
    viable = 0
    total = 0
    for combo in itertools.combinations(members, 4):
        total += 1
        for m in combo:
            if any(mv in _LEAD_VIABLE_MOVES for mv in m.moves):
                viable += 1
                break
    ratio = viable / total if total else 0.0
    return ratio, ratio * _W_LEAD_FLEX


def _core_diversity_points(members: list[TeamMember]) -> float:
    """Count distinct sweeper–support pairs; return up to _W_CORE_DIV points."""
    cores = 0
    for a, b in itertools.combinations(members, 2):
        a_is_sweeper = bool(set(a.role) & _BO3_SWEEPER_ROLES)
        b_is_sweeper = bool(set(b.role) & _BO3_SWEEPER_ROLES)
        a_is_support = bool(set(a.role) & _BO3_SUPPORT_ROLES)
        b_is_support = bool(set(b.role) & _BO3_SUPPORT_ROLES)
        if (a_is_sweeper and b_is_support) or (b_is_sweeper and a_is_support):
            cores += 1
    return min(cores / 3, 1.0) * _W_CORE_DIV


def _coverage_points(variant: TeamVariant) -> int:
    pokemons = [m.pokemon for m in variant.members]
    # Phase 2a: pass assigned movesets so offensive gaps are STAB-based
    # (member must have a move of type X, not just type X in pokemon.types).
    movesets = [list(m.moves) for m in variant.members]
    report = analyze_coverage(pokemons, movesets=movesets)
    pts = (
        _W_COVERAGE
        - len(report.offensive_gaps) * 2
        - len(report.defensive_weaknesses) * 3
    )
    return max(0, min(_W_COVERAGE, pts))


def _roles_points(variant: TeamVariant) -> int:
    all_roles: set[str] = set()
    for member in variant.members:
        all_roles.update(member.role)
    pokemons = [m.pokemon for m in variant.members]

    pts = 0
    if all_roles & _SWEEPER_ROLES:
        pts += 15
    if all_roles & _SUPPORT_ROLES:
        pts += 10

    flex = score_flexibility(pokemons)
    if flex >= 3:
        pts += 10
    elif flex >= 1:
        pts += 5

    return max(0, min(_W_ROLES, pts))


def _sps_points(variant: TeamVariant) -> int:
    if not variant.members:
        return 0
    per_member = _W_SPS / len(variant.members)
    pts = 0.0
    for member in variant.members:
        sp = member.sp_distribution
        total = sp.hp + sp.atk + sp.def_ + sp.spa + sp.spd + sp.spe
        if total == MAX_SP_TOTAL:
            pts += per_member
    # WHY: floor so partial SP allocation never rounds up to full credit.
    # A member not at MAX_SP_TOTAL loses its 2.5-pt share entirely — conservative
    # but predictable (never surprises the user with a score that feels too high).
    return max(0, min(_W_SPS, math.floor(pts)))


def _items_points(variant: TeamVariant) -> int:
    # WHY: Item Clause is enforced by construction in `_assign_items`
    # (raises TeamBuildError on duplicates), so any team that reaches
    # the rater has 6 distinct items and earns the full _W_ITEMS budget.
    # The old Life Orb-specific penalty is gone — Life Orb isn't even a
    # legal Champions item, so it cannot appear here in v1.
    items = [m.item for m in variant.members]
    pts = 0
    if len(set(items)) == len(items):
        pts += _W_ITEMS
    return max(0, min(_W_ITEMS, pts))


def score_team(
    variant: TeamVariant,
    format_mode: str = "bo1",
    *,
    archetype: str = "balance",
) -> tuple[float, float]:
    """Score a 6-member team variant on a 0-100 scale.

    Returns (total_score, lead_flexibility_ratio).
    lead_flexibility_ratio is 0.0 in Bo1 mode.

    Bo1: coverage(35) + roles(35) + sp(15) + items(15)
    Bo3: coverage(30) + lead_flex(25) + core_div(15) + sp(15) + items(15)

    Phase 2b archetype weighting: per-component scores are multiplied by
    the archetype's weight matrix from ``archetype_weights.json`` BEFORE
    the final clamp to [0, 100]. Balance (default) has weights = 1.0 on
    every component, so the v0.2.0 scoring behavior is preserved when
    archetype is not specified. The lead_flexibility_ratio is returned
    raw (not weighted) because it is a UI-facing 0–1 ratio, not a
    scoring contribution — multiplying it would mislead the badge text.
    """
    sps = _sps_points(variant)
    items = _items_points(variant)
    weights = get_weights(archetype)

    if format_mode == "bo3":
        # Phase 2a: STAB-based coverage using the variant's assigned movesets.
        bo3_pokemons = [m.pokemon for m in variant.members]
        bo3_movesets = [list(m.moves) for m in variant.members]
        bo3_report = analyze_coverage(bo3_pokemons, movesets=bo3_movesets)
        coverage = max(0, min(_W_COVERAGE_BO3,
            _W_COVERAGE_BO3
            - len(bo3_report.offensive_gaps) * 2
            - len(bo3_report.defensive_weaknesses) * 3
        ))
        flex_ratio, flex_pts = _lead_flexibility_points(variant.members)
        core_pts = _core_diversity_points(variant.members)
        total = float(
            coverage * weights.coverage
            + flex_pts * weights.roles
            + core_pts * weights.roles
            + sps * weights.sp
            + items * weights.items
        )
        return max(0.0, min(100.0, total)), flex_ratio
    else:
        coverage = _coverage_points(variant)
        roles = _roles_points(variant)
        total = float(
            coverage * weights.coverage
            + roles * weights.roles
            + sps * weights.sp
            + items * weights.items
        )
        return max(0.0, min(100.0, total)), 0.0


def generate_explanation(variant: TeamVariant, score: float) -> str:
    """Produce a short Spanish summary of the score with red flags."""
    coverage_pts = _coverage_points(variant)
    roles_pts = _roles_points(variant)

    parts: list[str] = [f"Equipo con puntuacion {score:.0f}/100."]

    if coverage_pts < 20:
        # Phase 2a: STAB-based coverage gaps for the explanation surface.
        report = analyze_coverage(
            [m.pokemon for m in variant.members],
            movesets=[list(m.moves) for m in variant.members],
        )
        gap_text = ", ".join(report.offensive_gaps[:5]) or "—"
        parts.append(f"Cobertura de tipos debil: faltan {gap_text}.")

    if roles_pts < 25:
        all_roles: set[str] = set()
        for member in variant.members:
            all_roles.update(member.role)
        missing: list[str] = []
        if not (all_roles & _SWEEPER_ROLES):
            missing.append("sweeper")
        if not (all_roles & _SUPPORT_ROLES):
            missing.append("soporte")
        missing_text = ", ".join(missing) if missing else "balance"
        parts.append(f"Falta balance de roles: sin {missing_text}.")

    if coverage_pts >= 20 and roles_pts >= 25:
        parts.append(
            "Equipo equilibrado con buena cobertura y balance de roles."
        )

    return " ".join(parts)


def rank_variants(variants: list[TeamVariant]) -> list[TeamVariant]:
    """Return a new list ordered by score desc, with the top one recommended."""
    if not variants:
        return []

    def _sort_key(pair: tuple[int, TeamVariant]) -> tuple[float, float, float, float, int]:
        idx, v = pair
        return (
            -v.score,
            -_coverage_points(v),
            -_roles_points(v),
            -_sps_points(v),
            idx,
        )

    indexed = list(enumerate(variants))
    indexed.sort(key=_sort_key)

    out: list[TeamVariant] = []
    for rank, (_, variant) in enumerate(indexed):
        out.append(variant.model_copy(update={"is_recommended": rank == 0}))
    return out
