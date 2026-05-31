from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import TYPE_CHECKING

from pokemon_team_builder.data.ability_implicit_roles_loader import (
    AbilityRoleEntry,
    is_ground_immunity_role,
    load_ability_implicit_roles,
)
from pokemon_team_builder.domain.models import MegaForm, PokemonData

if TYPE_CHECKING:
    from pokemon_team_builder.domain.models import TeamVariant


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


# ── Disruption move/ability sets (ADR §2.1 / R3) ────────────────────────────
# These frozensets live HERE in the low layer (synergy_engine) and are
# re-exported by viability_rater. synergy_engine must never import
# viability_rater (would be a circular import), so the single source of
# truth for disruption markers is this module. assess_presence and
# derive_doubles_tags consume them directly; the team scorer imports them
# from here via viability_rater's re-export. Moved verbatim from
# viability_rater — no value changes.

# Speed control mechanisms (full credit 1.0 per member with one of these).
_SPEED_CONTROL_MOVES: frozenset[str] = frozenset({
    "trick-room",
    "tailwind",
    "icy-wind",
    "electroweb",
    "thunder-wave",
    "glare",
    "nuzzle",
    "stun-spore",
    "sticky-web",
    "fake-out",
    "quick-guard",
})
# Abilities that contribute partial speed-control credit (0.5 each) —
# paralysis-on-contact.
_SPEED_CONTROL_PARTIAL_ABILITIES: frozenset[str] = frozenset({
    "static",
    "cute-charm",
})
# Core-viable means the member can fill a Bo3 lead/core slot (speed control
# or redirect). Previously _LEAD_VIABLE_MOVES.
_CORE_VIABLE_MOVES: frozenset[str] = frozenset({
    "tailwind", "trick-room", "fake-out", "extreme-speed", "quick-attack",
    "helping-hand", "thunder-wave", "icy-wind", "follow-me", "rage-powder",
})

# Redirection moves (señuelo / polvo ira). Pulls the opponent's attacks
# onto the user, protecting the ally — a real disruption (ADR §2.1).
_REDIRECT_MOVES: frozenset[str] = frozenset({"follow-me", "rage-powder"})

# Ally-boost moves: directly buff the partner's output (ADR §2.1, slugs
# fixed by Sergio). Distinct from self-setup moves.
_ALLY_BOOST_MOVES: frozenset[str] = frozenset({
    "helping-hand", "decorate", "coaching",
})

# Pure status moves that pressure the opponent without an offensive stat.
# Slugs fixed by Sergio (ADR §2.1 + R4). Superset of the status-flavoured
# speed-control moves (thunder-wave/glare/nuzzle/stun-spore appear in both
# _SPEED_CONTROL_MOVES and here on purpose — a status move is disruption
# whether or not it also slows).
_STATUS_MOVES: frozenset[str] = frozenset({
    "thunder-wave", "will-o-wisp", "spore", "sleep-powder", "glare",
    "nuzzle", "stun-spore", "yawn", "toxic",
})

# Setup moves — self-buffs that turn a mon into a win condition (C3 §3.2
# offensive_threat). hyphen-lower PokeAPI slugs.
_SETUP_MOVES: frozenset[str] = frozenset({
    "swords-dance", "dragon-dance", "calm-mind", "nasty-plot",
})

# Screen moves — dual screens / Aurora Veil (C3 §3.2 support_enabler).
_SCREEN_MOVES: frozenset[str] = frozenset({
    "light-screen", "reflect", "aurora-veil",
})


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

# Maps each weather-setter ability to the weather it produces. Used by
# derive_team_tags to connect a team's setters to weather-dependent abusers
# (C3 §3.2 weather_abuser). The weather strings match the keys used by
# weather_dependent_abilities.json (sun / rain / snow / sand).
_SETTER_ABILITY_TO_WEATHER: dict[str, str] = {
    "drought": "sun",
    "drizzle": "rain",
    "snow-warning": "snow",
    "sand-stream": "sand",
}


def _has_support_kit(moves: list[str]) -> bool:
    """True if the moveset contains at least one genuine support move.

    "Support kit" = a move that lets the mon actually do a lead/support job:
    a core-viable lead move, a redirection move, or a speed-control move.
    Reuses the module's existing frozensets (single source of truth).

    WHY (ADR weather-setter-coherence §3.1.1): the weather-setter lead_support
    floor should only promote ``lead_support`` to PRIMARY when the mon can
    really support. A weather setter with no support move and no offensive
    presence (Abomasnow) is an attacker whose value is "set the weather" —
    that is the C3 ``weather_setter`` tag, not a mechanical support role.
    """
    move_set = {m.lower() for m in moves}
    return bool(
        move_set & _CORE_VIABLE_MOVES
        or move_set & _REDIRECT_MOVES
        or move_set & _SPEED_CONTROL_MOVES
    )


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


# Offensive-presence threshold: a sweeper gradient weight of 0.5 maps
# exactly to a base stat of 100 (the gradient midpoint), matching the
# "atk o spa >= 100" rule in the spec.
PRESENCE_OFFENSIVE_CUTOFF: float = ROLE_PRESENCE_CUTOFF


@dataclass(frozen=True)
class PresenceReport:
    """C2 — does this Pokémon represent a threat in VGC Doubles? (ADR §2.1)

    A Pokémon with neither an offensive stat nor real disruption is a
    *passive liability*: the opponent ignores it and doubles its attacks
    onto the ally (docs/vgc-principles.md §2, video V3 — Garganacl/Blissey).

    - ``has_offensive_stat``: atk or spa gradient weight ≥ 0.5 (≈ stat ≥ 100).
    - ``has_disruption``: provides intimidate / fake-out / redirect /
      speed-control / pure status / ally-boost.
    - ``disruption_sources``: human-readable ES labels for the explanation.
    - ``is_passive_liability``: NOT offensive AND NOT disruption.
    - ``presence_weight``: 0.0..1.0 gradient = clamp(max(off, disr)).
    """

    has_offensive_stat: bool
    has_disruption: bool
    disruption_sources: list[str]
    is_passive_liability: bool
    presence_weight: float


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
    # ADR weather-setter-coherence §3.1/§3.1.1: the weather-setter floor only
    # surfaces ``lead_support`` as a mechanical ROLE (primary or secondary) when
    # the mon can actually support — i.e. it has a real support kit. A setter
    # with no support move (Abomasnow) is an attacker that happens to set the
    # weather; "set the weather" is the C3 ``weather_setter`` tag, not a role.
    # The 0.8 floor stays in ``role_weights`` regardless (the team scorer still
    # sees it); only the role list is gated. The independent move-driven
    # ``move_lead_support`` path (Tailwind+spe>=90 / priority support) is a
    # genuine support signal and is NOT gated by this.
    # A weather setter "supports" (lead_support is a real role) only when it
    # carries a genuine support move. An "offensive" setter (sweeper weight at
    # or above the cutoff) keeps its sweeper as PRIMARY even if it also
    # supports — lead_support may still trail as a secondary role (§3.1).
    setter_supports = is_weather_setter and _has_support_kit(moves)
    offensive_weight = max(
        role_weights.get("physical_sweeper", 0.0),
        role_weights.get("special_sweeper", 0.0),
    )
    # ADR move-category-coherence §3.4 (2a): "offensive setter" by INCLINATION,
    # not just by the stat-100 sweeper cutoff. A mon whose best attacking stat
    # meets or exceeds its best defensive stat is offensive-leaning even if it
    # falls short of stat 100 — so it should NOT be promoted to lead_support
    # PRIMARY by the weather floor. This is additive (``or``): nobody who was
    # already offensive by the cutoff stops being offensive.
    #   Abomasnow: max(92,92)=92 >= max(75,85)=85 → True  → not lead primary.
    #   Pelipper:  max(50,95)=95 >= max(100,70)=100 → False → genuine support lead.
    #   Ninetales-A: max(67,81)=81 >= max(75,100)=100 → False → stays lead.
    offensive_lean = max(stats.atk, stats.spa) >= max(stats.def_, stats.spd)
    setter_is_offensive = offensive_weight >= ROLE_PRESENCE_CUTOFF or offensive_lean
    # lead_support is promoted to PRIMARY by the weather floor only for a
    # non-offensive setter that actually supports.
    setter_lead_primary = setter_supports and not setter_is_offensive

    # Boolean view: role names whose weight crosses the presence cutoff.
    boolean_roles: set[str] = {
        r for r, w in role_weights.items() if w >= ROLE_PRESENCE_CUTOFF
    }
    # The weather-setter floor (0.8 >= cutoff) would otherwise force
    # lead_support into the boolean set; drop it unless the setter truly
    # supports or another (move-driven) path re-adds it below.
    if is_weather_setter and not setter_supports:
        boolean_roles.discard("lead_support")
    # Move-driven roles are always boolean-present even if a hypothetical
    # weight calc disagreed.
    if move_lead_support:
        boolean_roles.add("lead_support")
    if move_redirect:
        boolean_roles.add("redirect")
    if setter_supports:
        boolean_roles.add("lead_support")

    ordered: list[str] = []

    # Weather setter → primary role ONLY when it supports and is not offensive.
    if setter_lead_primary:
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

    # ADR move-category-coherence §1.4 / §3.4: an offensive-leaning weather
    # setter (best attack >= best defence) whose sweeper weights fall short of
    # the stat-100 cutoff must STILL lead with its dominant-stat sweeper, not
    # with lead_support. Without this, a sub-cutoff offensive setter (Abomasnow
    # 92/92) whose learnset carries a support move keeps lead_support in
    # ``boolean_roles`` and, with no sweeper ordered above, lands as roles[0] —
    # the reported bug. We append the dominant sweeper here so lead_support can
    # only trail as a secondary. ``setter_lead_primary`` is already False for
    # an offensive setter, so this never demotes a genuine support lead
    # (Pelipper / Ninetales-A are not offensive-leaning → unaffected).
    if (
        is_weather_setter
        and setter_is_offensive
        and not (has_phys or has_spec)
        and not setter_lead_primary
    ):
        ordered.append(
            "physical_sweeper" if stats.atk >= stats.spa else "special_sweeper"
        )

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


def assess_presence(
    pokemon: PokemonData,
    moves: list[str] | None = None,
    ability: str | None = None,
) -> PresenceReport:
    """Assess a Pokémon's offensive presence / disruption (C2, ADR §2.1).

    ``moves`` / ``ability`` are optional overrides. When ``None`` they fall
    back to ``pokemon.move_names`` / ``pokemon.abilities[0]`` — the same
    degrading pattern as :func:`analyze_coverage` when ``movesets is None``.
    This lets callers pass an *assigned* moveset (the 4 chosen moves) while
    species lookups can rely on the full learnset.

    Formula (ADR §2.1):
      off  = max(physical_sweeper weight, special_sweeper weight)  # gradient
      disr = 1.0 if has_disruption else 0.0
      presence_weight   = clamp(max(off, disr), 0.0, 1.0)
      has_offensive_stat = off >= 0.5            # ≈ atk or spa >= 100
      is_passive_liability = (off < 0.5) AND (not has_disruption)
    """
    move_list = moves if moves is not None else list(pokemon.move_names)
    move_set = {m.strip().lower() for m in move_list}

    if ability is not None:
        ability_slug = ability.strip().lower().replace(" ", "-")
    elif pokemon.abilities:
        ability_slug = pokemon.abilities[0].strip().lower().replace(" ", "-")
    else:
        ability_slug = ""

    weights = assign_role_weights(pokemon).role_weights
    off = max(
        weights.get("physical_sweeper", 0.0),
        weights.get("special_sweeper", 0.0),
    )
    has_offensive_stat = off >= PRESENCE_OFFENSIVE_CUTOFF

    # ── Disruption detection (ADR §2.1 table) ────────────────────────────
    disruption_sources: list[str] = []
    if ability_slug == "intimidate":
        disruption_sources.append("intimidación")
    if "fake-out" in move_set:
        disruption_sources.append("sorpresa (fake-out)")
    if move_set & _REDIRECT_MOVES:
        disruption_sources.append("redirección")
    if move_set & _SPEED_CONTROL_MOVES:
        disruption_sources.append("control de velocidad")
    if move_set & _STATUS_MOVES:
        disruption_sources.append("estado")
    if move_set & _ALLY_BOOST_MOVES:
        disruption_sources.append("boost a aliado")

    has_disruption = bool(disruption_sources)
    disr = 1.0 if has_disruption else 0.0

    presence_weight = max(off, disr)
    if presence_weight < 0.0:
        presence_weight = 0.0
    elif presence_weight > 1.0:
        presence_weight = 1.0

    is_passive_liability = (off < PRESENCE_OFFENSIVE_CUTOFF) and (not has_disruption)

    return PresenceReport(
        has_offensive_stat=has_offensive_stat,
        has_disruption=has_disruption,
        disruption_sources=disruption_sources,
        is_passive_liability=is_passive_liability,
        presence_weight=presence_weight,
    )


def derive_doubles_tags(
    pokemon: PokemonData,
    moves: list[str] | None = None,
    ability: str | None = None,
) -> list[str]:
    """Derive the Doubles taxonomy tags for a single Pokémon (C3, ADR §3.2).

    Per-mon tags only — the two context-dependent tags (``weather_abuser``,
    ``trick_room_abuser``) need the whole team and are produced by
    :func:`derive_team_tags`. Tags are DERIVED on demand from the existing
    role weights + presence + moves; nothing is persisted (ADR §3.4).

    ``moves`` / ``ability`` follow the same fallback rule as
    :func:`assess_presence`. Returned in a stable, deduplicated order.

    Tag rules (ADR §3.2):
      - ``offensive_threat``: sweeper weight ≥ 0.5 OR a setup move.
      - ``support_enabler``: redirect role OR intimidate OR fake-out OR
        helping-hand OR a screen move.
      - ``speed_control``: a full speed-control move (≥ 1.0 credit).
      - ``defensive_pivot``: wall weight ≥ 0.5 AND has_disruption (a bulky
        mon with NO disruption is a liability, not a pivot — §2.3).
      - ``weather_setter``: weather-setter ability OR competitive weather
        species.
      - ``trick_room_setter``: trick_room_setter weight ≥ 0.5.
    """
    move_list = moves if moves is not None else list(pokemon.move_names)
    move_set = {m.strip().lower() for m in move_list}

    if ability is not None:
        ability_slug = ability.strip().lower().replace(" ", "-")
    elif pokemon.abilities:
        ability_slug = pokemon.abilities[0].strip().lower().replace(" ", "-")
    else:
        ability_slug = ""

    assignment = assign_role_weights(pokemon)
    weights = assignment.role_weights
    roles = assignment.roles
    presence = assess_presence(pokemon, moves=move_list, ability=ability_slug)

    tags: list[str] = []

    # offensive_threat
    sweeper_weight = max(
        weights.get("physical_sweeper", 0.0),
        weights.get("special_sweeper", 0.0),
    )
    if sweeper_weight >= ROLE_PRESENCE_CUTOFF or (move_set & _SETUP_MOVES):
        tags.append("offensive_threat")

    # support_enabler
    if (
        "redirect" in roles
        or ability_slug == "intimidate"
        or "fake-out" in move_set
        or "helping-hand" in move_set
        or (move_set & _SCREEN_MOVES)
    ):
        tags.append("support_enabler")

    # speed_control — a full speed-control MOVE (partial abilities alone,
    # worth 0.5, do not reach the 1.0 per-member threshold of §3.2).
    if move_set & _SPEED_CONTROL_MOVES:
        tags.append("speed_control")

    # defensive_pivot — bulky AND non-passive (disruption present).
    wall_weight = max(
        weights.get("physical_wall", 0.0),
        weights.get("special_wall", 0.0),
    )
    if wall_weight >= ROLE_PRESENCE_CUTOFF and presence.has_disruption:
        tags.append("defensive_pivot")

    # weather_setter
    if (
        ability_slug in _WEATHER_SETTER_ABILITIES
        or pokemon.name.strip().lower() in _COMPETITIVE_WEATHER_SPECIES
    ):
        tags.append("weather_setter")

    # trick_room_setter
    if weights.get("trick_room_setter", 0.0) >= ROLE_PRESENCE_CUTOFF:
        tags.append("trick_room_setter")

    # Dedup while preserving first-seen order.
    seen: set[str] = set()
    ordered: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            ordered.append(tag)
    return ordered


def derive_team_tags(variant: "TeamVariant") -> list[list[str]]:
    """Derive per-member Doubles tags including team-context tags (C3, §3.2).

    Returns one tag list per member, index-aligned with ``variant.members``.
    Each member's list starts from :func:`derive_doubles_tags` (assessed
    with the member's *assigned* moves + ability) and then adds the two
    context-dependent tags:

      - ``weather_abuser``: the member's ability is weather-dependent
        (``weather_dependent_abilities.json``) AND some teammate sets the
        matching weather (a ``weather_setter``).
      - ``trick_room_abuser``: spe ≤ 60 AND the member is an
        ``offensive_threat`` AND the team has a ``trick_room_setter``.

    Import of the weather loader is local to keep the module-level import
    graph minimal; the loader is memoised so the cost is one-time.
    """
    from pokemon_team_builder.data.weather_data_loader import (
        load_weather_dependent_abilities,
    )

    members = variant.members

    # First pass: per-mon tags + collect team-level setter facts.
    per_member_tags: list[list[str]] = []
    team_has_tr_setter = False
    weathers_set_on_team: set[str] = set()
    dep_abilities, _ = load_weather_dependent_abilities()

    for member in members:
        tags = derive_doubles_tags(
            member.pokemon, moves=list(member.moves), ability=member.ability
        )
        per_member_tags.append(tags)
        if "trick_room_setter" in tags:
            team_has_tr_setter = True
        if "weather_setter" in tags:
            # Map the setter's ability to the weather it produces, if known.
            ability_slug = member.ability.strip().lower().replace(" ", "-")
            weather = _SETTER_ABILITY_TO_WEATHER.get(ability_slug)
            if weather is not None:
                weathers_set_on_team.add(weather)

    # Second pass: add context-dependent tags.
    for idx, member in enumerate(members):
        tags = per_member_tags[idx]
        ability_slug = member.ability.strip().lower().replace(" ", "-")

        required_weather = dep_abilities.get(ability_slug)
        if required_weather is not None and required_weather in weathers_set_on_team:
            if "weather_abuser" not in tags:
                tags.append("weather_abuser")

        if (
            member.pokemon.base_stats.spe <= 60
            and "offensive_threat" in tags
            and team_has_tr_setter
        ):
            if "trick_room_abuser" not in tags:
                tags.append("trick_room_abuser")

    return per_member_tags


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

    Coverage rule (VGC-corrected, move-based — supersedes the earlier
    "STAB-based" rule; see docs/vgc-principles.md §4, video V4):
      A type X is "covered" iff at least one team member has a damaging
      move of type X in their **assigned moveset**, whether or not that
      move is STAB. Non-STAB coverage moves DO count — e.g. a Water-mon
      carrying Ice Beam covers Ice, because in VGC coverage moves are how
      you threaten what your STABs can't (V4: "es importante que alguno
      tenga ataques de cobertura para dañar al acero"). Only damaging
      moves appear in ``MOVE_TYPE`` (status moves like Tailwind are
      absent), so this naturally excludes non-offensive moves.
      If ``movesets`` is omitted the function falls back to the v1
      typing-based heuristic (every member assumed to cover its own
      types) — this preserves call sites that only have a partial team,
      no items assigned yet, and no moves selected.

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
        # VGC-corrected: a damaging move covers its type regardless of STAB
        # (docs/vgc-principles.md §4). The MOVE_TYPE table (data/move_types.py)
        # lists only damaging moves, so iterating it excludes status moves
        # without an explicit category check.
        from pokemon_team_builder.data.move_types import MOVE_TYPE

        move_types: set[str] = set()
        for member, moves in zip(team, movesets):
            for move in moves:
                mtype = MOVE_TYPE.get(move)
                if mtype:
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
