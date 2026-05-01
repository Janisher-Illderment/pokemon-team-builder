from __future__ import annotations

import math
from collections import Counter

from pokemon_team_builder.config import MAX_SP_TOTAL
from pokemon_team_builder.domain.models import TeamVariant
from pokemon_team_builder.services.synergy_engine import (
    analyze_coverage,
    score_flexibility,
)


# Weight budgets per component. Sum to 100.
_W_COVERAGE = 35
_W_ROLES = 35
_W_SPS = 15
_W_ITEMS = 15

_SWEEPER_ROLES = frozenset({"physical_sweeper", "special_sweeper"})
_SUPPORT_ROLES = frozenset({"lead_support", "redirect"})


def _coverage_points(variant: TeamVariant) -> int:
    pokemons = [m.pokemon for m in variant.members]
    report = analyze_coverage(pokemons)
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
    items = [m.item for m in variant.members]
    pts = 0
    if len(set(items)) == len(items):
        pts += _W_ITEMS

    # Penalize repeated "Life Orb" specifically (-3 per extra beyond the
    # first). This applies even when items aren't all unique.
    counts = Counter(items)
    life_orb = counts.get("Life Orb", 0)
    if life_orb > 1:
        pts -= 3 * (life_orb - 1)

    return max(0, min(_W_ITEMS, pts))


def score_team(variant: TeamVariant) -> float:
    """Score a 6-member team variant on a 0-100 scale.

    Components: type coverage (35), role balance (35), SP allocation (15),
    item diversity (15). Each is clamped to its own budget; the total is
    the sum, also clamped to [0, 100].
    """
    coverage = _coverage_points(variant)
    roles = _roles_points(variant)
    sps = _sps_points(variant)
    items = _items_points(variant)
    total = float(coverage + roles + sps + items)
    return max(0.0, min(100.0, total))


def generate_explanation(variant: TeamVariant, score: float) -> str:
    """Produce a short Spanish summary of the score with red flags."""
    coverage_pts = _coverage_points(variant)
    roles_pts = _roles_points(variant)

    parts: list[str] = [f"Equipo con puntuacion {score:.0f}/100."]

    if coverage_pts < 20:
        report = analyze_coverage([m.pokemon for m in variant.members])
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
    """Return a new list ordered by score desc, with the top one recommended.

    Tiebreak chain (all descending): total score → coverage pts → roles pts
    → SP pts → original input order. The first entry is marked recommended.
    Returns model_copy instances so callers don't observe in-place mutation.
    """
    if not variants:
        return []

    def _sort_key(pair: tuple[int, TeamVariant]) -> tuple[float, float, float, float, int]:
        idx, v = pair
        return (
            -v.score,
            -_coverage_points(v),
            -_roles_points(v),
            -_sps_points(v),
            idx,  # stable on full tie
        )

    indexed = list(enumerate(variants))
    indexed.sort(key=_sort_key)

    out: list[TeamVariant] = []
    for rank, (_, variant) in enumerate(indexed):
        out.append(variant.model_copy(update={"is_recommended": rank == 0}))
    return out
