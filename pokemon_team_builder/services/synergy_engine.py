from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from pokemon_team_builder.data.ability_implicit_roles_loader import (
    AbilityRoleEntry,
    is_ground_immunity_role,
    load_ability_implicit_roles,
)
from pokemon_team_builder.domain.models import MegaForm, PokemonData


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


_AUTO_LEAD_ABILITIES: frozenset[str] = frozenset({
    "drought", "drizzle", "snow-warning", "sand-stream", "prankster",
})

# Species whose competitive ability is at a non-zero index in PokeAPI but
# are definitively weather setters in VGC context.
_COMPETITIVE_WEATHER_SPECIES: frozenset[str] = frozenset({
    "ninetales-alola", "pelipper", "politoed", "torkoal",
})

# Tailwind requires a fast setter (spe >= 90 threshold).
_TAILWIND_MARKERS: tuple[str, ...] = ("tailwind",)
# Priority/redirect moves work regardless of Speed — no gate needed.
_PRIORITY_SUPPORT_MARKERS: tuple[str, ...] = ("fake-out", "follow-me", "rage-powder")

_SWEEPER_ROLES: frozenset[str] = frozenset({"physical_sweeper", "special_sweeper"})
_SUPPORT_ROLES: frozenset[str] = frozenset({"lead_support", "redirect"})


# Threshold center for each stat-based role. The gradient band is ±15 around
# this center: weight = 0.0 at (threshold − 15), 0.5 at threshold, 1.0 at
# (threshold + 15). Linear in between.
#
# WHY a 30-point band: a stat one point under the threshold should not lose
# the role entirely. The band gives the scorer information without forcing
# arbitrary cliff tie-breaks. Boolean consumers use weight ≥ 0.5 as "has the
# role" (preserves the legacy threshold semantics — at the threshold itself
# the weight crosses 0.5).
_ROLE_BAND_HALF: float = 15.0
_ROLE_BAND_FULL: float = 30.0

# Weight at or above which a role is considered boolean-present. The number
# is intentionally exactly 0.5 so the boundary aligns with the gradient
# midpoint at ``threshold``.
ROLE_PRESENCE_CUTOFF: float = 0.5

# Weather-setter abilities that grant a fixed lead_support floor (≥ 0.8)
# regardless of stat-based weight. Mirrors the auto-lead set but is
# explicitly named to make the spec rule traceable.
_WEATHER_SETTER_ABILITIES: frozenset[str] = frozenset({
    "drought", "drizzle", "snow-warning", "sand-stream",
})
_WEATHER_SETTER_LEAD_WEIGHT: float = 0.8


@dataclass(frozen=True)
class CoverageReport:
    offensive_gaps: list[str] = field(default_factory=list)
    defensive_weaknesses: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RoleAssignment:
    """Full output of role assignment with gradient weights and coverage flags.

    - ``role_weights``: {role_name: weight in [0.0, 1.0]} — granular score.
    - ``roles``: ordered list of role labels with ``weight >= 0.5`` plus
      move-driven roles (lead_support from priority moves, redirect from
      Rage Powder / Follow Me, trick_room_setter from Trick Room knowledge).
      First element is the primary role used for item / nature / SP.
    - ``coverage_flags``: {flag_name: True} for ability-driven hints that
      affect coverage but NOT role scoring (e.g. ``ground_immune`` from
      Levitate).
    """

    role_weights: dict[str, float]
    roles: list[str]
    coverage_flags: dict[str, bool]


def _move_contains_any(move_names: list[str], markers: tuple[str, ...]) -> bool:
    for move in move_names:
        for marker in markers:
            if marker in move:
                return True
    return False


def _gradient_weight(stat_value: int, threshold: int) -> float:
    """Return a 0.0–1.0 role weight for ``stat_value`` against ``threshold``.

    Band:
      stat <= threshold - 15  → 0.0
      stat == threshold       → 0.5
      stat >= threshold + 15  → 1.0
      linear interpolation otherwise.
    """
    raw = (stat_value - (threshold - _ROLE_BAND_HALF)) / _ROLE_BAND_FULL
    if raw <= 0.0:
        return 0.0
    if raw >= 1.0:
        return 1.0
    return raw


def _merge_weight(
    role_weights: dict[str, float], role: str, delta: float
) -> None:
    """Add ``delta`` to ``role_weights[role]`` capped at 1.0."""
    current = role_weights.get(role, 0.0)
    role_weights[role] = min(1.0, current + delta)


def _apply_ability_implicit_roles(
    role_weights: dict[str, float],
    coverage_flags: dict[str, bool],
    abilities_lower: list[str],
) -> None:
    """Merge ability-driven role weights and coverage flags in place.

    Iterates abilities in PokeAPI order; first ability that has an entry
    in ``ability_implicit_roles.json`` is applied. Coverage-hint entries
    (Levitate → ground_immune) DO NOT touch ``role_weights`` — they set a
    flag for the coverage layer to consume.
    """
    ability_roles: dict[str, AbilityRoleEntry] = load_ability_implicit_roles()
    for ability in abilities_lower:
        entry = ability_roles.get(ability)
        if entry is None:
            continue
        if entry.is_coverage_hint and is_ground_immunity_role(entry.role):
            coverage_flags["ground_immune"] = True
            # Levitate is a hard immunity; never bump role weights.
            return
        _merge_weight(role_weights, entry.role, entry.weight)
        if entry.secondary_role is not None and entry.secondary_weight > 0.0:
            _merge_weight(role_weights, entry.secondary_role, entry.secondary_weight)
        # Only the first matching ability contributes (typical Pokemon has
        # one competitive ability; merging multiple would double-count
        # situational abilities like Sand Veil + Sand Force).
        return


def assign_role_weights(pokemon: PokemonData) -> RoleAssignment:
    """Compute gradient role weights, the derived role list, and coverage flags.

    This is the canonical role-assignment entry point post-Phase-2a.
    ``assign_role`` is a thin wrapper that returns just the role list for
    backward compatibility with existing callers.

    Algorithm:
      1. Stat-derived role weights (sweepers, walls, trick_room_setter)
         using ±15 gradient bands.
      2. Weather-setter lead_support floor (Drought / Drizzle / Snow
         Warning / Sand Stream, with the same whitelist guard as before).
      3. Move-driven role injections (Tailwind + spe>=90 → lead_support,
         Fake Out / Follow Me / Rage Powder → lead_support, Trick Room
         + spe<=60 → trick_room_setter, Rage Powder / Follow Me →
         redirect). These set weight = 1.0 directly — moves are binary
         signals, not gradients.
      4. Ability-as-implicit-role bonus (Flame Body etc.) merged on top
         of stat weights, capped at 1.0. Coverage hints (Levitate) set
         flags without touching weights.
      5. Build the ordered role list:
         - Primary slot: weather-setter lead_support if applicable
           (preserves the old precedence).
         - When both Atk and SpA gradient weights are ≥ 0.5, the dominant
           one comes first (matches the legacy Hydreigon test).
         - Other roles appended in spec order with dedup.
         - Fallback to physical_sweeper / special_sweeper when nothing
           else fires (preserves the legacy empty-roles guard).
    """
    stats = pokemon.base_stats
    moves = pokemon.move_names
    abilities_lower = [a.lower() for a in pokemon.abilities]

    role_weights: dict[str, float] = {}
    coverage_flags: dict[str, bool] = {}

    # ── 1. Stat-derived gradient weights ────────────────────────────
    # Sweepers: threshold 100 on offensive stats.
    role_weights["physical_sweeper"] = _gradient_weight(stats.atk, 100)
    role_weights["special_sweeper"] = _gradient_weight(stats.spa, 100)
    # Walls: bulk gates on def/spd 100 AND hp 80. We combine both gates
    # using the MIN of the two gradient weights so a low-HP mon with
    # huge defense doesn't qualify (Shedinja-style).
    pwall_def = _gradient_weight(stats.def_, 100)
    pwall_hp = _gradient_weight(stats.hp, 80)
    role_weights["physical_wall"] = min(pwall_def, pwall_hp)
    swall_spd = _gradient_weight(stats.spd, 100)
    swall_hp = _gradient_weight(stats.hp, 80)
    role_weights["special_wall"] = min(swall_spd, swall_hp)
    # Trick Room setter: speed ≤ 60 AND knows Trick Room. Inverted
    # gradient — slower is better. We treat spe == 60 as 0.5 by mirroring
    # the band: weight = 1.0 at spe ≤ 45, 0.5 at spe == 60, 0.0 at spe ≥ 75.
    if "trick-room" in moves:
        # Inverted: use (75 - spe) against threshold 15 in a ±15 band.
        # Equivalent formulation: weight = clamp((75 - spe) / 30, 0, 1).
        inv_raw = (75 - stats.spe) / _ROLE_BAND_FULL
        if inv_raw <= 0.0:
            tr_weight = 0.0
        elif inv_raw >= 1.0:
            tr_weight = 1.0
        else:
            tr_weight = inv_raw
        role_weights["trick_room_setter"] = tr_weight

    # ── 2. Weather-setter lead_support floor ────────────────────────
    # abilities[0] check prevents false positives (e.g. Aurorus whose primary
    # is Refrigerate, not Snow Warning). Whitelist covers species where the
    # competitive ability is at a non-zero index in PokeAPI ordering.
    is_weather_setter = False
    if abilities_lower and (
        abilities_lower[0] in _AUTO_LEAD_ABILITIES
        or (
            pokemon.name in _COMPETITIVE_WEATHER_SPECIES
            and any(a in _AUTO_LEAD_ABILITIES for a in abilities_lower)
        )
    ):
        # Distinguish the four canonical weather setters from Prankster
        # (also in _AUTO_LEAD_ABILITIES) — both get lead_support but
        # weather setters get the higher floor per spec.
        first_ability = abilities_lower[0]
        if first_ability in _WEATHER_SETTER_ABILITIES or (
            pokemon.name in _COMPETITIVE_WEATHER_SPECIES
            and any(a in _WEATHER_SETTER_ABILITIES for a in abilities_lower)
        ):
            is_weather_setter = True
            _merge_weight(role_weights, "lead_support", _WEATHER_SETTER_LEAD_WEIGHT)
        else:
            # Prankster path: keep parity with legacy assign_role behaviour
            # (Prankster mon emits lead_support as primary).
            _merge_weight(role_weights, "lead_support", 1.0)

    # ── 3. Move-driven role injections (binary) ─────────────────────
    move_lead_support = False
    if stats.spe >= 90 and _move_contains_any(moves, _TAILWIND_MARKERS):
        _merge_weight(role_weights, "lead_support", 1.0)
        move_lead_support = True
    if _move_contains_any(moves, _PRIORITY_SUPPORT_MARKERS):
        _merge_weight(role_weights, "lead_support", 1.0)
        move_lead_support = True
    move_redirect = "follow-me" in moves or "rage-powder" in moves
    if move_redirect:
        _merge_weight(role_weights, "redirect", 1.0)
    # trick_room_setter already handled in step 1 (gradient); the binary
    # move check is implicit there.

    # ── 4. Ability-as-implicit-role layer ────────────────────────────
    _apply_ability_implicit_roles(role_weights, coverage_flags, abilities_lower)

    # ── 5. Build the ordered role list ───────────────────────────────
    # Boolean view: role names whose weight crosses the presence cutoff.
    boolean_roles: set[str] = {
        r for r, w in role_weights.items() if w >= ROLE_PRESENCE_CUTOFF
    }
    # Move-driven roles are always boolean-present even if a hypothetical
    # weight calc disagreed.
    if move_lead_support:
        boolean_roles.add("lead_support")
    if move_redirect:
        boolean_roles.add("redirect")
    if is_weather_setter:
        boolean_roles.add("lead_support")

    ordered: list[str] = []

    # Weather setter → primary role.
    if is_weather_setter:
        ordered.append("lead_support")
    # Prankster also gets lead_support primary (legacy behaviour).
    elif (
        abilities_lower
        and abilities_lower[0] in _AUTO_LEAD_ABILITIES
        and abilities_lower[0] not in _WEATHER_SETTER_ABILITIES
    ):
        ordered.append("lead_support")

    # Dominant-stat sweeper ordering.
    has_phys = role_weights.get("physical_sweeper", 0.0) >= ROLE_PRESENCE_CUTOFF
    has_spec = role_weights.get("special_sweeper", 0.0) >= ROLE_PRESENCE_CUTOFF
    if has_phys and has_spec:
        if stats.atk >= stats.spa:
            ordered.append("physical_sweeper")
            ordered.append("special_sweeper")
        else:
            ordered.append("special_sweeper")
            ordered.append("physical_sweeper")
    elif has_phys:
        ordered.append("physical_sweeper")
    elif has_spec:
        ordered.append("special_sweeper")

    # Walls and the rest in spec order.
    for role in (
        "physical_wall",
        "special_wall",
        "lead_support",
        "trick_room_setter",
        "redirect",
    ):
        if role in boolean_roles and role not in ordered:
            ordered.append(role)

    # Fallback: ensure non-empty result (preserves legacy contract).
    if not ordered:
        fallback = "physical_sweeper" if stats.atk >= stats.spa else "special_sweeper"
        ordered.append(fallback)

    return RoleAssignment(
        role_weights=role_weights,
        roles=ordered,
        coverage_flags=coverage_flags,
    )


def assign_role(pokemon: PokemonData) -> list[str]:
    """Return one or more role labels based on stats, moves, and abilities.

    Thin wrapper over :func:`assign_role_weights` kept for backward
    compatibility — existing callers consume only the role list. New
    code that wants gradient weights or ability-driven coverage flags
    SHOULD call :func:`assign_role_weights` directly.
    """
    return assign_role_weights(pokemon).roles


def assign_role_with_mega(
    pokemon: PokemonData, mega: MegaForm | None
) -> list[str]:
    """Like ``assign_role`` but uses Mega-form stats/types when ``mega`` is set.

    When ``mega is None`` this is a pass-through to ``assign_role`` — no
    behavioral change for non-mega callers. When a ``MegaForm`` is given
    we synthesize a temporary ``PokemonData`` whose ``base_stats`` and
    ``types`` are the mega's, leaving moves and abilities intact.

    WHY: ``assign_role`` is intentionally not modified — its existing
    contract and tests are stable. Building a synthetic copy keeps role
    determination consistent regardless of how the stats arrived.
    """
    if mega is None:
        return assign_role(pokemon)
    # PokemonData is a Pydantic BaseModel; model_copy(update=...) is the
    # equivalent of dataclasses.replace — it returns a new instance with
    # the listed fields overridden and is non-mutating.
    synthetic = pokemon.model_copy(
        update={"base_stats": mega.stats, "types": list(mega.types)}
    )
    return assign_role(synthetic)


def _has_ground_immunity(pokemon: PokemonData) -> bool:
    """Return True iff the pokémon has a Ground-immunity ability.

    Single source of truth: defers to :func:`assign_role_weights`, which
    reads ``ability_implicit_roles.json`` and sets
    ``coverage_flags["ground_immune"]`` for abilities tagged with the
    ``ground_immunity_flag`` sentinel role (currently: Levitate). Item-
    induced suppression (Iron Ball) is OUT OF SCOPE per spec — coverage
    still treats the holder as Ground-immune.
    """
    return assign_role_weights(pokemon).coverage_flags.get("ground_immune", False)


def analyze_coverage(
    team: list[PokemonData],
    movesets: list[list[str]] | None = None,
) -> CoverageReport:
    """Inspect a team for offensive coverage gaps and defensive weaknesses.

    Coverage rule (Phase 2a, STAB-based — see spec coverage-analysis
    Requirement "Coverage scoring is STAB-based"):
      A type X is "covered" iff at least one team member has a move of
      type X in their **assigned moveset** AND that move's type is one
      of the member's own types (STAB). Non-STAB coverage moves (e.g. a
      Water-mon carrying Ice Beam) do NOT count toward Ice coverage.
      If ``movesets`` is omitted the function falls back to the v1
      typing-based heuristic (every member assumed to cover its own
      types) — this preserves pre-Phase-2a call sites that only have a
      partial team, no items assigned yet, and no moves selected.

    Defensive weakness rule: a type is recorded as a shared defensive
    weakness when 3+ members take >= 2.0x damage from it. Levitate
    members are treated as ground-immune (multiplier 0.0 for Ground)
    irrespective of typing.

    ``movesets``, when provided, MUST be index-aligned with ``team``:
    ``movesets[i]`` is the 4-move list for ``team[i]``.
    """
    if not team:
        return CoverageReport(offensive_gaps=[], defensive_weaknesses=[])

    offensive_gaps: list[str] = []

    if movesets is not None:
        # Lazy-import to keep synergy_engine free of replica_exporter cycles.
        # The local _MOVE_TYPE table is the canonical move→type map.
        from pokemon_team_builder.services.replica_exporter import _MOVE_TYPE

        # STAB filter: only count a move toward type-X coverage when the
        # move's type matches one of the carrying member's types.
        move_types: set[str] = set()
        for member, moves in zip(team, movesets):
            member_types = {t.lower() for t in member.types}
            for move in moves:
                mtype = _MOVE_TYPE.get(move)
                if mtype and mtype.lower() in member_types:
                    move_types.add(mtype.lower())
        for type_name in ALL_TYPES:
            if type_name not in move_types:
                offensive_gaps.append(type_name)
    else:
        # Legacy fallback: derive coverage from member typing. Documented
        # limitation — kept so callers that don't have movesets yet (beam
        # search heuristic, _partial_score) keep working.
        team_types: set[str] = set()
        for member in team:
            for t in member.types:
                team_types.add(t.lower())
        for type_name in ALL_TYPES:
            if type_name not in team_types:
                offensive_gaps.append(type_name)

    defensive_weaknesses: list[str] = []
    for type_name in ALL_TYPES:
        weak_count = 0
        for member in team:
            # Levitate overrides Ground weakness regardless of typing.
            if type_name == "ground" and _has_ground_immunity(member):
                continue
            if member.weaknesses.get(type_name, 1.0) >= 2.0:
                weak_count += 1
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
