from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from pokemon_team_builder.domain.models import PokemonData


# WHY: 18 canonical Pokemon types. Used to enumerate offensive/defensive
# coverage gaps across the type chart.
ALL_TYPES: tuple[str, ...] = (
    "normal",
    "fire",
    "water",
    "electric",
    "grass",
    "ice",
    "fighting",
    "poison",
    "ground",
    "flying",
    "psychic",
    "bug",
    "rock",
    "ghost",
    "dragon",
    "dark",
    "steel",
    "fairy",
)


# Substring markers for detecting "support-y" moves on a fast Pokemon.
_LEAD_SUPPORT_MARKERS: tuple[str, ...] = (
    "tailwind",
    "follow-me",
    "rage-powder",
    "fake-out",
)

_SWEEPER_ROLES: frozenset[str] = frozenset({"physical_sweeper", "special_sweeper"})
_SUPPORT_ROLES: frozenset[str] = frozenset({"lead_support", "redirect"})


@dataclass(frozen=True)
class CoverageReport:
    offensive_gaps: list[str] = field(default_factory=list)
    defensive_weaknesses: list[str] = field(default_factory=list)


def _move_contains_any(move_names: list[str], markers: tuple[str, ...]) -> bool:
    for move in move_names:
        for marker in markers:
            if marker in move:
                return True
    return False


def assign_role(pokemon: PokemonData) -> list[str]:
    """Return one or more role labels based on stats and known moves.

    Rules accumulate (a single Pokemon may carry several roles). If no rule
    triggers, falls back to ``physical_sweeper`` or ``special_sweeper``
    depending on which offensive stat is higher.
    """
    stats = pokemon.base_stats
    moves = pokemon.move_names

    roles: list[str] = []

    if stats.atk >= 100:
        roles.append("physical_sweeper")
    if stats.spa >= 100:
        roles.append("special_sweeper")
    if stats.def_ >= 100 and stats.hp >= 80:
        roles.append("physical_wall")
    if stats.spd >= 100 and stats.hp >= 80:
        roles.append("special_wall")
    if stats.spe >= 90 and _move_contains_any(moves, _LEAD_SUPPORT_MARKERS):
        roles.append("lead_support")
    if stats.spe <= 60 and "trick-room" in moves:
        roles.append("trick_room_setter")
    if "follow-me" in moves or "rage-powder" in moves:
        roles.append("redirect")

    if not roles:
        roles.append(
            "physical_sweeper" if stats.atk >= stats.spa else "special_sweeper"
        )

    # WHY: dedupe while preserving rule order. ``redirect`` and
    # ``lead_support`` can overlap legitimately.
    seen: set[str] = set()
    deduped: list[str] = []
    for role in roles:
        if role not in seen:
            seen.add(role)
            deduped.append(role)
    return deduped


def analyze_coverage(team: list[PokemonData]) -> CoverageReport:
    """Inspect a team for offensive STAB gaps and shared defensive weaknesses.

    - Offensive gap: no member has the type as STAB (i.e., among its
      ``types``). Move-based coverage is intentionally out of scope here;
      see module docstring / TODO for future work.
    - Defensive weakness: 3+ members take >= 2.0x damage from a given
      attacker type.
    Empty team yields an empty report.
    """
    if not team:
        return CoverageReport(offensive_gaps=[], defensive_weaknesses=[])

    offensive_gaps: list[str] = []
    team_types: set[str] = set()
    for member in team:
        for t in member.types:
            team_types.add(t.lower())
    for type_name in ALL_TYPES:
        if type_name not in team_types:
            offensive_gaps.append(type_name)

    defensive_weaknesses: list[str] = []
    for type_name in ALL_TYPES:
        weak_count = sum(
            1
            for member in team
            if member.weaknesses.get(type_name, 1.0) >= 2.0
        )
        if weak_count >= 3:
            defensive_weaknesses.append(type_name)

    return CoverageReport(
        offensive_gaps=offensive_gaps,
        defensive_weaknesses=defensive_weaknesses,
    )


def detect_role_gaps(team: list[PokemonData]) -> list[str]:
    """Return the role labels missing from a balanced Doubles team.

    A balanced team needs:
      - at least one sweeper (physical or special)
      - at least one support-style member (lead_support or redirect)
      - if a trick_room_setter is present, at least 2 slow members
        (spe <= 60); otherwise the gap label ``slow_trio`` is emitted.
    """
    gaps: list[str] = []
    if not team:
        # WHY: an empty team is missing everything; emit the canonical
        # critical roles to keep the output deterministic.
        return ["sweeper", "lead_support"]

    all_roles: list[str] = []
    has_tr_setter = False
    for member in team:
        roles = assign_role(member)
        all_roles.extend(roles)
        if "trick_room_setter" in roles:
            has_tr_setter = True

    role_set = set(all_roles)
    if not (role_set & _SWEEPER_ROLES):
        gaps.append("sweeper")
    if not (role_set & _SUPPORT_ROLES):
        gaps.append("lead_support")

    if has_tr_setter:
        slow_members = sum(1 for m in team if m.base_stats.spe <= 60)
        if slow_members < 2:
            gaps.append("slow_trio")

    return gaps


def score_flexibility(team: list[PokemonData]) -> int:
    """Count 4-of-6 subsets that contain at least one sweeper and one support.

    Range: 0..C(6,4)=15. Smaller teams still work but produce smaller
    counts (e.g., a 5-member team has C(5,4)=5 combinations).
    """
    if len(team) < 4:
        return 0

    member_roles = [set(assign_role(m)) for m in team]
    count = 0
    for combo in combinations(range(len(team)), 4):
        roles_in_combo: set[str] = set()
        for idx in combo:
            roles_in_combo |= member_roles[idx]
        has_sweeper = bool(roles_in_combo & _SWEEPER_ROLES)
        has_support = bool(roles_in_combo & _SUPPORT_ROLES)
        if has_sweeper and has_support:
            count += 1
    return count
