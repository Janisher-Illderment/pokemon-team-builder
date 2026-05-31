"""C6 — intrinsic Pokémon quality tests (ADR §4.2, docs/vgc-principles.md §8).

Two layers:
  1. Each §4.2 signal exercised in isolation with synthetic stat lines so the
     penalty and the report flags are verified independently.
  2. A BLOCKING non-regression test over the full legal pool (ADR §5.1 / R2):
     loads every legal Pokémon offline (PokeAPI disk cache) and asserts that
     NO mon drops below the 0.5 floor, and reports the distribution of each
     signal so the conservative thresholds can be calibrated.

Base stats in the isolated tests are chosen to trigger exactly one signal at
a time (or none), not to match any real species.
"""

from __future__ import annotations

from pokemon_team_builder.domain.models import BaseStats, PokemonData
from pokemon_team_builder.services.pokemon_evaluator import (
    QualityReport,
    evaluate_pokemon_quality,
)


def _mk(
    name: str,
    *,
    types: list[str] | None = None,
    hp: int = 80,
    atk: int = 80,
    def_: int = 80,
    spa: int = 80,
    spd: int = 80,
    spe: int = 80,
    moves: list[str] | None = None,
    abilities: list[str] | None = None,
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


# ── Clean baseline (no signal fires) ──────────────────────────────────────────

def test_clean_mon_scores_one():
    """A mon that trips no signal keeps the full 1.0 multiplier."""
    # spe 100 (out of limbo), only one offensive stat high, neutral type,
    # modest bulk, no rock moves, primary role not a starved sweeper.
    mon = _mk(
        "cleanmon", types=["water"], hp=80, atk=120, def_=80, spa=60, spd=80, spe=100,
        moves=["waterfall", "protect"],
    )
    report = evaluate_pokemon_quality(mon)
    assert isinstance(report, QualityReport)
    assert report.score == 1.0
    assert report.flags == []
    assert report.split_attacker is False
    assert report.type_bulk_mismatch is False
    assert report.speed_limbo is False
    assert report.unreliable_moves == []


# ── Signal 1: split attacker (atk >= 90 AND spa >= 90 → −0.10) ─────────────────

def test_split_attacker_penalised():
    mon = _mk(
        "splitter", types=["dragon"], atk=100, spa=110, spe=100,
        moves=["dragon-claw"],
    )
    report = evaluate_pokemon_quality(mon)
    assert report.split_attacker is True
    assert report.score == 0.90
    assert any("partidas" in f for f in report.flags)


def test_split_attacker_boundary_exactly_90():
    """Threshold is inclusive (>= 90) on BOTH stats."""
    mon = _mk("edge", types=["dragon"], atk=90, spa=90, spe=100, moves=["dragon-claw"])
    assert evaluate_pokemon_quality(mon).split_attacker is True

    mon_under = _mk(
        "under", types=["dragon"], atk=89, spa=120, spe=100, moves=["dragon-claw"]
    )
    assert evaluate_pokemon_quality(mon_under).split_attacker is False


# ── Signal 2: type↔bulk mismatch (rock/ice AND def+spd >= 180 → −0.10) ─────────

def test_rock_type_inverted_bulk_penalised():
    mon = _mk(
        "rockwall", types=["rock"], atk=120, def_=100, spa=40, spd=100, spe=100,
        moves=["stone-edge"],
    )
    report = evaluate_pokemon_quality(mon)
    assert report.type_bulk_mismatch is True
    assert any("roca/hielo" in f for f in report.flags)


def test_ice_type_inverted_bulk_penalised():
    mon = _mk(
        "icewall", types=["ice"], atk=120, def_=95, spa=40, spd=95, spe=100,
        moves=["icicle-crash"],
    )
    assert evaluate_pokemon_quality(mon).type_bulk_mismatch is True


def test_rock_type_low_bulk_not_penalised():
    """A frail Rock-type does not trip the type↔bulk signal."""
    mon = _mk(
        "rockfrail", types=["rock"], atk=120, def_=60, spa=40, spd=60, spe=100,
        moves=["stone-edge"],
    )
    assert evaluate_pokemon_quality(mon).type_bulk_mismatch is False


def test_bulk_on_good_defensive_type_not_penalised():
    """High bulk on a non-rock/ice type is fine."""
    mon = _mk(
        "steelwall", types=["steel"], atk=120, def_=130, spa=40, spd=100, spe=100,
        moves=["iron-head"],
    )
    assert evaluate_pokemon_quality(mon).type_bulk_mismatch is False


# ── Signal 3: speed limbo (60 < spe < 95 → −0.05) ──────────────────────────────

def test_speed_limbo_penalised():
    mon = _mk("limbo", types=["normal"], atk=120, spe=80, moves=["body-slam"])
    report = evaluate_pokemon_quality(mon)
    assert report.speed_limbo is True
    assert report.score == 0.95
    assert any("limbo" in f for f in report.flags)


def test_speed_boundaries_exclusive():
    """Bounds are exclusive: spe == 60 and spe == 95 are NOT limbo."""
    slow = _mk("slow", types=["normal"], atk=120, spe=60, moves=["body-slam"])
    assert evaluate_pokemon_quality(slow).speed_limbo is False

    fast = _mk("fast", types=["normal"], atk=120, spe=95, moves=["body-slam"])
    assert evaluate_pokemon_quality(fast).speed_limbo is False

    mid = _mk("mid", types=["normal"], atk=120, spe=61, moves=["body-slam"])
    assert evaluate_pokemon_quality(mid).speed_limbo is True


# ── Signal 4: unreliable Rock moves (−0.05 each, cap −0.10) ────────────────────

def test_one_unreliable_rock_move():
    mon = _mk(
        "slider", types=["ground"], atk=120, spe=100,
        moves=["earthquake", "rock-slide"],
    )
    report = evaluate_pokemon_quality(mon)
    assert report.unreliable_moves == ["rock-slide"]
    assert report.score == 0.95


def test_two_unreliable_rock_moves_capped():
    """Both rock-slide and stone-edge → −0.10 cap, not −0.10? (0.05*2 == 0.10)."""
    mon = _mk(
        "doublerock", types=["ground"], atk=120, spe=100,
        moves=["earthquake", "rock-slide", "stone-edge"],
    )
    report = evaluate_pokemon_quality(mon)
    assert report.unreliable_moves == ["rock-slide", "stone-edge"]
    # 0.05 * 2 = 0.10, equal to the cap.
    assert report.score == 0.90


# ── Signal 5: movepool insufficient for sweeper role (−0.10) ───────────────────

def test_sweeper_without_stab_damage_penalised():
    """A physical sweeper with no same-type damaging STAB in the learnset."""
    # Atk 130 → primary role physical_sweeper. Type fire, but no fire damaging
    # move in MOVE_TYPE present in move_names (only coverage + status).
    mon = _mk(
        "starved", types=["fire"], atk=130, spa=40, spe=100,
        moves=["earthquake", "protect", "swords-dance"],
    )
    report = evaluate_pokemon_quality(mon)
    assert any("movepool" in f for f in report.flags)
    # Atk 130 ≥ 90 but spa 40 → no split. Only the movepool signal fires.
    assert report.score == 0.90


def test_sweeper_with_stab_damage_not_penalised():
    """Same sweeper but carrying a fire STAB damaging move → no penalty."""
    # "fire-punch" is a fire damaging move present in MOVE_TYPE; it provides
    # the same-type STAB the sweeper signal looks for. (flare-blitz is not in
    # MOVE_TYPE, so it would NOT count — the signal only sees mapped moves.)
    mon = _mk(
        "armed", types=["fire"], atk=130, spa=40, spe=100,
        moves=["fire-punch", "earthquake", "protect"],
    )
    report = evaluate_pokemon_quality(mon)
    assert all("movepool" not in f for f in report.flags)
    assert report.score == 1.0


# ── Combined signals stack and clamp ───────────────────────────────────────────

def test_multiple_signals_stack():
    """Split + speed limbo + one rock move = 1.0 − 0.10 − 0.05 − 0.05 = 0.80."""
    mon = _mk(
        "messy", types=["dragon"], atk=100, spa=100, spe=80,
        moves=["dragon-claw", "rock-slide"],
    )
    report = evaluate_pokemon_quality(mon)
    assert report.split_attacker is True
    assert report.speed_limbo is True
    assert report.unreliable_moves == ["rock-slide"]
    assert abs(report.score - 0.80) < 1e-9


def test_score_never_below_floor():
    """Even with every signal firing, the multiplier floors at 0.5.

    Max possible subtraction = 0.10+0.10+0.05+0.10+0.10 = 0.45 → 0.55, so the
    0.5 floor is defensive; assert the clamp holds regardless.
    """
    mon = _mk(
        "worst", types=["ice"], atk=100, def_=100, spa=100, spd=100, spe=80,
        # ice sweeper, no ice STAB damage in learnset → movepool signal;
        # split; type-bulk; speed limbo; two rock moves.
        moves=["rock-slide", "stone-edge", "earthquake"],
    )
    report = evaluate_pokemon_quality(mon)
    assert report.score >= 0.5


# ── BLOCKING non-regression over the full legal pool (ADR §5.1 / R2) ───────────

def test_legal_pool_no_mon_below_floor_and_report_distribution(capsys):
    """No legal mon scores below 0.5; print the signal distribution.

    Loads every legal Pokémon from the PokeAPI disk cache (offline). Mons that
    cannot be resolved (network-only, returns a fallback stub) are skipped so
    the test stays deterministic offline. The distribution print is the
    calibration artifact requested for C6 (ADR R2: thresholds are conservative
    starting points to be tuned against the real pool).
    """
    from pokemon_team_builder.data.legal_pool_loader import get_all_names
    from pokemon_team_builder.services.pokemon_lookup import lookup

    names = get_all_names()
    evaluated = 0
    skipped: list[str] = []
    counts = {
        "split_attacker": 0,
        "type_bulk_mismatch": 0,
        "speed_limbo": 0,
        "unreliable_moves": 0,
        "movepool_insufficient": 0,
    }
    score_buckets = {"1.00": 0, "0.95": 0, "0.90": 0, "0.85": 0, "<=0.80": 0}
    min_score = 1.0
    worst: tuple[str, float] = ("", 1.0)

    for name in names:
        try:
            pokemon = lookup(name)
        except Exception:
            skipped.append(name)
            continue
        # Skip fallback stubs (PokeAPI couldn't resolve → id 9999 / empty moves);
        # they are placeholder data, not a real evaluation.
        if pokemon.id == 9999 or not pokemon.move_names:
            skipped.append(name)
            continue

        report = evaluate_pokemon_quality(pokemon)
        evaluated += 1

        # Floor invariant — BLOCKING.
        assert report.score >= 0.5, f"{name} scored {report.score} (< 0.5 floor)"

        if report.split_attacker:
            counts["split_attacker"] += 1
        if report.type_bulk_mismatch:
            counts["type_bulk_mismatch"] += 1
        if report.speed_limbo:
            counts["speed_limbo"] += 1
        if report.unreliable_moves:
            counts["unreliable_moves"] += 1
        if any("movepool" in f for f in report.flags):
            counts["movepool_insufficient"] += 1

        s = report.score
        if s >= 0.999:
            score_buckets["1.00"] += 1
        elif abs(s - 0.95) < 1e-6:
            score_buckets["0.95"] += 1
        elif abs(s - 0.90) < 1e-6:
            score_buckets["0.90"] += 1
        elif abs(s - 0.85) < 1e-6:
            score_buckets["0.85"] += 1
        else:
            score_buckets["<=0.80"] += 1

        if s < min_score:
            min_score = s
            worst = (name, s)

    # Must have evaluated a meaningful slice of the pool offline.
    assert evaluated >= 100, (
        f"only {evaluated} mons evaluated offline "
        f"({len(skipped)} skipped) — cache may be cold"
    )

    # Sanity ceiling on each signal: a conservative heuristic should not flag
    # a majority of the pool. If any signal exceeds ~50% it is mis-calibrated.
    for signal, n in counts.items():
        assert n <= evaluated * 0.5, (
            f"signal '{signal}' fired on {n}/{evaluated} mons (>50%) — "
            f"likely mis-calibrated"
        )

    # Calibration report (visible with `pytest -s`).
    print("\n=== C6 quality distribution over legal pool ===")
    print(f"evaluated={evaluated}  skipped={len(skipped)}")
    print("signal counts (mons firing each):")
    for signal, n in counts.items():
        pct = 100.0 * n / evaluated if evaluated else 0.0
        print(f"  {signal:24s} {n:4d}  ({pct:5.1f}%)")
    print("score buckets:")
    for bucket, n in score_buckets.items():
        pct = 100.0 * n / evaluated if evaluated else 0.0
        print(f"  {bucket:8s} {n:4d}  ({pct:5.1f}%)")
    print(f"min score = {worst[1]:.2f} ({worst[0]})")
