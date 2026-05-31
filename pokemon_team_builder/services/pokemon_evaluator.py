"""C6 — intrinsic Pokémon quality evaluation beyond the BST (ADR §4).

A Pokémon's raw base-stat total does not capture how useful it is in VGC
Doubles. ``docs/vgc-principles.md`` §8 (video V7, "Estos Pokémon Son Peores
de lo que Piensas") lists concrete signals that make a mon worse than its
stats suggest: offensive stats split across both attacking categories, a
defensive-bulk profile on a poor defensive type, a Speed stuck in the
"limbo" between Trick Room and Tailwind tiers, unreliable low-accuracy Rock
moves, and a movepool that can't actually support the mon's role.

This module is intentionally **decoupled from the team scorer and from any
network/meta fetch**. ``evaluate_pokemon_quality`` takes a single
:class:`~pokemon_team_builder.domain.models.PokemonData` and returns a
deterministic :class:`QualityReport`. ``viability_rater.score_team`` consumes
the report (term ``quality_adjustment``); the lives-here/used-there split is
the ADR §4.1 decision (team scoring vs per-mon evaluation are different
responsibilities, and intrinsic quality must not couple to MunchStats HTTP).

ADR §4.2 thresholds are conservative starting points marked ``[UNCERTAIN]``
and are meant to be calibrated against the real legal pool — see the
non-regression test in ``tests/test_pokemon_evaluator.py``. The "resource
cost / team-revolves-around-the-mon" signal (V7, Mega Chesnaught) is
DEFERRED: it needs team-dependency modelling and does not fit a pure
per-mon evaluator.

Limitation — moveset vs learnset (documented per the task brief):
``evaluate_pokemon_quality`` receives only a ``PokemonData`` with no assigned
4-move set, so the move-dependent signals (unreliable Rock moves, STAB
movepool) are evaluated against ``pokemon.move_names`` (the full learnset),
NOT against a chosen moveset. The unreliable-move signal is gated on Rock
typing + physical orientation (V7 is specifically about Rock-type physical
attackers), so a non-Rock mon that merely *can* learn Rock Slide as coverage
is NOT penalised; the movepool signal checks whether a same-type damaging
STAB exists *anywhere* in the learnset. A future iteration with the assigned
moveset can tighten this further.
"""

from __future__ import annotations

from dataclasses import dataclass

from pokemon_team_builder.data.move_types import MOVE_TYPE
from pokemon_team_builder.domain.models import PokemonData
from pokemon_team_builder.services.synergy_engine import (
    ROLE_PRESENCE_CUTOFF,
    assign_role_weights,
)


# Base quality multiplier and clamp floor (ADR §4.2). A mon never drops to
# zero — it is still legal and playable — so the multiplier floors at 0.5.
_QUALITY_BASE: float = 1.0
_QUALITY_FLOOR: float = 0.5
_QUALITY_CEIL: float = 1.0

# Penalty magnitudes (subtract from the base multiplier). Verbatim ADR §4.2.
_PENALTY_SPLIT_ATTACKER: float = 0.10
_PENALTY_TYPE_BULK_MISMATCH: float = 0.10
_PENALTY_SPEED_LIMBO: float = 0.05
_PENALTY_UNRELIABLE_MOVE: float = 0.05
_PENALTY_UNRELIABLE_MOVE_CAP: float = 0.10
_PENALTY_MOVEPOOL_INSUFFICIENT: float = 0.10

# Split-attacker thresholds: both offensive stats relevant (≥ 90) → one is
# wasted under the 66-SP budget (ADR §4.2; V7: Goodra/Greninja).
_SPLIT_ATTACKER_STAT: int = 90

# Type↔bulk coherence: a defensive-bulk profile on a poor defensive type.
# Rock and Ice are the canonical bad defensive types (V7); a high combined
# def+spd on such a mon is "inverted" bulk.
_BAD_DEFENSIVE_TYPES: frozenset[str] = frozenset({"rock", "ice"})
_TYPE_BULK_DEF_SUM_THRESHOLD: int = 180

# Speed limbo: neither slow enough to enable Trick Room nor fast enough to
# reach a Tailwind / scarf-tier offensive speed (ADR §4.2). Exclusive bounds.
_SPEED_LIMBO_LOW: int = 60
_SPEED_LIMBO_HIGH: int = 95

# Low-accuracy physical Rock moves (ADR §4.2; V6: avalancha/roca afilada
# fallan). Rock Slide = 90 acc, Stone Edge = 80 acc. Both are physical Rock
# damaging moves present in MOVE_TYPE.
_LOW_ACCURACY_ROCK_PHYS: frozenset[str] = frozenset({"rock-slide", "stone-edge"})

@dataclass(frozen=True)
class QualityReport:
    """C6 intrinsic-quality report for a single Pokémon (ADR §1.4 / §4.2).

    - ``score``: 0.5..1.0 quality multiplier (base 1.0 minus penalties,
      clamped). 1.0 means no quality red flags fired.
    - ``flags``: human-readable Spanish labels for the UI, one per fired
      signal.
    - ``split_attacker``: atk AND spa both ≥ 90 (one category wasted).
    - ``type_bulk_mismatch``: Rock/Ice typing with inverted defensive bulk.
    - ``speed_limbo``: 60 < spe < 95 (neither TR-slow nor fast).
    - ``unreliable_moves``: low-accuracy Rock STAB moves carried by a
      Rock-type physical attacker (the cursed-STAB profile from V7); empty
      for non-Rock mons that merely carry Rock Slide as coverage.
    """

    score: float
    flags: list[str]
    split_attacker: bool
    type_bulk_mismatch: bool
    speed_limbo: bool
    unreliable_moves: list[str]


def evaluate_pokemon_quality(pokemon: PokemonData) -> QualityReport:
    """Return the intrinsic :class:`QualityReport` for ``pokemon`` (ADR §4.2).

    Pure and deterministic: no network, no team context. Each signal subtracts
    from a base multiplier of 1.0; the result is clamped to [0.5, 1.0].

    Signals (ADR §4.2):
      1. Split attacker — ``atk >= 90 AND spa >= 90``                  → −0.10
      2. Type↔bulk mismatch — type ∈ {rock, ice} AND (def+spd) >= 180  → −0.10
      3. Speed limbo — ``60 < spe < 95``                               → −0.05
      4. Unreliable moves — Rock-type physical attacker (rock in types,
         atk >= spa) carrying rock-slide / stone-edge                  → −0.05
         each, capped at −0.10
      5. Movepool insufficient — primary role is a sweeper but no
         same-type damaging STAB in move_names                         → −0.10

    Move-dependent signals (4, 5) read ``pokemon.move_names`` (the learnset);
    see the module docstring on the moveset-vs-learnset limitation.
    """
    stats = pokemon.base_stats
    flags: list[str] = []
    multiplier = _QUALITY_BASE

    # ── 1. Split offensive stats ─────────────────────────────────────────
    split_attacker = (
        stats.atk >= _SPLIT_ATTACKER_STAT and stats.spa >= _SPLIT_ATTACKER_STAT
    )
    if split_attacker:
        multiplier -= _PENALTY_SPLIT_ATTACKER
        flags.append("stats ofensivas partidas (atk y spa altos)")

    # ── 2. Type↔bulk coherence ───────────────────────────────────────────
    types_lower = {t.strip().lower() for t in pokemon.types}
    bulk_sum = stats.def_ + stats.spd
    type_bulk_mismatch = bool(types_lower & _BAD_DEFENSIVE_TYPES) and (
        bulk_sum >= _TYPE_BULK_DEF_SUM_THRESHOLD
    )
    if type_bulk_mismatch:
        multiplier -= _PENALTY_TYPE_BULK_MISMATCH
        flags.append("tipo defensivo malo (roca/hielo) con bulk invertido")

    # ── 3. Speed in the limbo ─────────────────────────────────────────────
    speed_limbo = _SPEED_LIMBO_LOW < stats.spe < _SPEED_LIMBO_HIGH
    if speed_limbo:
        multiplier -= _PENALTY_SPEED_LIMBO
        flags.append("velocidad en el limbo (ni rapida ni lenta)")

    # ── 4. Unreliable low-accuracy Rock moves ─────────────────────────────
    # V7's claim is specifically about ROCK-TYPE PHYSICAL attackers: their
    # STAB Rock moves (Rock Slide 90 / Stone Edge 80) miss, and Rock has no
    # high-power reliable physical option. A non-Rock mon merely carrying
    # Rock Slide as coverage is NOT what V7 laments, so the signal is gated
    # on Rock typing + a physical orientation (atk >= spa). This keeps the
    # penalty on the cursed Tyranitar/Rampardos/Aerodactyl profile and avoids
    # false-positives on every Garchomp-style coverage Rock Slide.
    move_set = {m.strip().lower() for m in pokemon.move_names}
    is_rock_physical = "rock" in types_lower and stats.atk >= stats.spa
    unreliable_moves = (
        sorted(move_set & _LOW_ACCURACY_ROCK_PHYS) if is_rock_physical else []
    )
    if unreliable_moves:
        penalty = min(
            _PENALTY_UNRELIABLE_MOVE * len(unreliable_moves),
            _PENALTY_UNRELIABLE_MOVE_CAP,
        )
        multiplier -= penalty
        flags.append(
            "moves de roca poco fiables: " + ", ".join(unreliable_moves)
        )

    # ── 5. Movepool insufficient for a sweeper role ───────────────────────
    # Gate on a REAL sweeper, not assign_role's non-empty fallback (Tecle
    # Brief #1): assign_role_weights falls back to physical/special_sweeper
    # for any mon when no role qualifies (synergy_engine.py:444-447), so a
    # weak roleless mon would otherwise be wrongly penalised here. Require the
    # sweeper gradient weight to clear the presence cutoff (stat actually
    # high enough). Then the mon needs a same-type damaging STAB in its
    # learnset (reuse MOVE_TYPE for move→damage-type).
    role_weights = assign_role_weights(pokemon).role_weights
    sweeper_weight = max(
        role_weights.get("physical_sweeper", 0.0),
        role_weights.get("special_sweeper", 0.0),
    )
    movepool_insufficient = False
    if sweeper_weight >= ROLE_PRESENCE_CUTOFF:
        has_stab_damage = any(
            MOVE_TYPE.get(move) in types_lower for move in move_set
        )
        if not has_stab_damage:
            movepool_insufficient = True
            multiplier -= _PENALTY_MOVEPOOL_INSUFFICIENT
            flags.append("movepool insuficiente para su rol (sin STAB de daño)")

    # ── Clamp ─────────────────────────────────────────────────────────────
    if multiplier < _QUALITY_FLOOR:
        multiplier = _QUALITY_FLOOR
    elif multiplier > _QUALITY_CEIL:
        multiplier = _QUALITY_CEIL

    return QualityReport(
        score=multiplier,
        flags=flags,
        split_attacker=split_attacker,
        type_bulk_mismatch=type_bulk_mismatch,
        speed_limbo=speed_limbo,
        unreliable_moves=unreliable_moves,
    )
