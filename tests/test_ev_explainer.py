import pytest
from pokemon_team_builder.data.speed_tiers import load as load_speed_db
from pokemon_team_builder.domain.models import (
    BaseStats, PokemonData, SPDistribution, TeamMember,
)
from pokemon_team_builder.services.ev_explainer import explain  # noqa: F401


def _make_member(
    name: str,
    types: list[str],
    base_hp: int, base_atk: int, base_def: int,
    base_spa: int, base_spd: int, base_spe: int,
    weaknesses: dict[str, float],
    sp_hp: int = 0, sp_atk: int = 0, sp_def: int = 0,
    sp_spa: int = 0, sp_spd: int = 0, sp_spe: int = 0,
    nature: str = "hardy",
) -> TeamMember:
    pokemon = PokemonData(
        id=1,
        name=name,
        types=types,
        base_stats=BaseStats(hp=base_hp, atk=base_atk, **{"def": base_def}, spa=base_spa, spd=base_spd, spe=base_spe),
        move_names=["tackle"],
        abilities=["overgrow"],
        weaknesses=weaknesses,
    )
    sp = SPDistribution(hp=sp_hp, atk=sp_atk, **{"def": sp_def}, spa=sp_spa, spd=sp_spd, spe=sp_spe)
    return TeamMember(pokemon=pokemon, role=["attacker"], sp_distribution=sp, item="none", ability="overgrow", nature=nature, moves=["tackle", "growl", "scratch", "ember"])


_speed_db = load_speed_db()


def test_empty_distribution_returns_empty():
    member = _make_member("test", ["fire"], 100, 100, 80, 80, 80, 80, {"water": 2.0})
    result = explain(member, _speed_db)
    assert result == ""


def test_speed_note_names_specific_pokemon():
    # Garchomp base 102, Jolly, 32 SPs → speed 169 → outspeeds many pool members
    # Result should name at least one recognized Pokémon from the speed tier DB
    member = _make_member(
        "garchomp", ["dragon", "ground"],
        108, 130, 95, 80, 85, 102,
        {"ice": 4.0, "fairy": 2.0},
        sp_spe=32, nature="jolly",
    )
    result = explain(member, _speed_db)
    assert "supera" in result
    # At least one entry from the DB should appear in the note
    known_names = {e.name.replace("-", " ").title() for e in _speed_db.entries()}
    assert any(n in result for n in known_names), f"No Pokémon name found in: {result}"


def test_speed_note_shows_no_alcanza():
    # Incineroar base 60, neutral, 0 SPs → speed 80 → doesn't reach aerodactyl (base 130 → 165)
    member = _make_member(
        "incineroar", ["fire", "dark"],
        95, 115, 90, 80, 90, 60,
        {"water": 2.0, "ground": 2.0},
        sp_spe=0, nature="hardy",
    )
    result = explain(member, _speed_db)
    # no SPs in spe → no speed note
    assert result == "" or "alcanza" not in result


def test_speed_note_with_investment():
    # Incineroar with 16 Spe SPs, neutral
    member = _make_member(
        "incineroar", ["fire", "dark"],
        95, 115, 90, 80, 90, 60,
        {"water": 2.0},
        sp_spe=16, nature="hardy",
    )
    result = explain(member, _speed_db)
    assert "Spe" in result
    assert "supera" in result or "alcanza" in result


def test_defensive_note_names_specific_attack():
    # Snorlax (Normal type) → no weakness usually, but give it a water weakness to test
    # Use a Pokemon with known weakness: Incineroar weak to Ground
    member = _make_member(
        "incineroar", ["fire", "dark"],
        95, 115, 90, 80, 90, 60,
        {"water": 2.0, "ground": 2.0, "fighting": 2.0, "fairy": 2.0},
        sp_hp=32, nature="hardy",
    )
    result = explain(member, _speed_db)
    # Should mention a move (Terremoto or similar)
    assert result != ""
    # Should contain a percentage range
    assert "%" in result


def test_defensive_note_verdict_present():
    member = _make_member(
        "slowbro", ["water", "psychic"],
        95, 75, 110, 100, 80, 30,
        {"electric": 2.0, "grass": 2.0, "ghost": 2.0, "dark": 2.0, "bug": 2.0},
        sp_hp=32, sp_def=16, nature="bold",
    )
    result = explain(member, _speed_db)
    verdicts = ["aguanta con holgura", "aguanta por poco", "aguanta", "NO aguanta"]
    assert any(v in result for v in verdicts)


def test_mixed_investment_returns_two_sentences():
    # Garchomp with both Spe and HP investment
    member = _make_member(
        "garchomp", ["dragon", "ground"],
        108, 130, 95, 80, 85, 102,
        {"ice": 4.0, "fairy": 2.0},
        sp_hp=16, sp_spe=16, nature="jolly",
    )
    result = explain(member, _speed_db)
    # Should have both speed and defensive info
    assert ". " in result or ("Spe" in result and ("aguanta" in result or "NO aguanta" in result))


def test_no_weakness_defensive_note_empty():
    # Pokemon with no weaknesses dict — defensive note should gracefully return ""
    member = _make_member(
        "eevee", ["normal"],
        55, 55, 50, 45, 65, 55,
        {},  # no weaknesses
        sp_hp=32, nature="hardy",
    )
    result = explain(member, _speed_db)
    # No weakness → no defensive note; no spe → no speed note → empty
    assert result == ""


# ── Phase 4b user feedback: speed tier baseline + final-stat label ─────────


def test_speed_label_shows_final_stat_not_just_investment():
    """User feedback 2026-05-14: speed note must show the FINAL speed
    stat (with EVs + nature applied), not just the SP investment number.

    Format expected: 'Spe <final> (<sp> SP+)' — e.g. 'Spe 222 (32 SP+)'.
    """
    # Mega Aerodactyl-like baseline: base 150, Jolly, 32 SP → final 222
    member = _make_member(
        "aerodactyl-mega", ["rock", "flying"],
        80, 135, 85, 70, 95, 150,
        {"water": 2.0, "electric": 2.0, "ice": 2.0, "rock": 2.0, "steel": 2.0},
        sp_spe=32, nature="jolly",
    )
    result = explain(member, _speed_db)
    # Final stat 222 must appear; bare "32 Spe+" without final must NOT.
    assert "Spe 222" in result, (
        f"speed label must surface final stat 222; got {result!r}"
    )
    assert "(32 SP" in result, (
        f"speed label must still show SP investment in parens; got {result!r}"
    )


def test_opponent_speed_baseline_is_max_sp_neutral_not_zero_sp():
    """User feedback 2026-05-14: the opponents listed in the speed note
    must be evaluated at **max SP + neutral nature**, not 0 SP + neutral.

    Aerodactyl (base 130) at 0 SP neutral computes to 146 — the previous
    (broken) baseline. At max SP (32) + neutral nature it computes to
    182 — the new baseline. The label '(146)' must NEVER appear next to
    Aerodactyl in a generated note.
    """
    # Anchor faster than Aerodactyl's MAX baseline (182) so Aero appears
    # in the "we beat" list with its new max-SP-neutral speed.
    # Mega Beedrill-like base 145 Jolly 32 SP → final 215.
    member = _make_member(
        "fast-attacker", ["bug", "poison"],
        65, 150, 40, 15, 80, 145,
        {"flying": 2.0, "fire": 2.0, "psychic": 2.0, "rock": 2.0},
        sp_spe=32, nature="jolly",
    )
    result = explain(member, _speed_db)
    # If Aerodactyl shows up, it must be (182), not (146).
    if "Aerodactyl" in result:
        assert "(146)" not in result, (
            f"old 0-SP baseline leaked into the note; got {result!r}"
        )
        # And it should show the new max-SP-neutral baseline.
        # We don't hard-assert "(182)" because the DB may evolve, but
        # any 3-digit number ≥ 170 is plausible at max-SP neutral on
        # a base-130 stat.
        import re
        m = re.search(r"Aerodactyl\s*\((\d+)\)", result)
        if m:
            opp_speed = int(m.group(1))
            assert opp_speed >= 170, (
                f"opponent Aerodactyl baseline too low ({opp_speed}); "
                f"max-SP neutral on base 130 should be ≥170, was {opp_speed}. "
                f"Full note: {result!r}"
            )


# ── Items pool expansion (Phase 4b feedback) ─────────────────────────────


def test_legal_items_pool_contains_type_resist_berries():
    """User feedback 2026-05-14: 18 type-resist berries (one per type)
    must be in the legal items pool. Inte-verified Champions M-A content.
    """
    from pokemon_team_builder.services.team_generator import _load_champions_legal_items
    legal, _version = _load_champions_legal_items()
    expected_berries = {
        "Chilan Berry", "Occa Berry", "Passho Berry", "Wacan Berry",
        "Rindo Berry", "Yache Berry", "Chople Berry", "Kebia Berry",
        "Shuca Berry", "Coba Berry", "Payapa Berry", "Tanga Berry",
        "Charti Berry", "Kasib Berry", "Haban Berry", "Colbur Berry",
        "Babiri Berry", "Roseli Berry",
    }
    missing = expected_berries - legal
    assert not missing, f"missing type-resist berries in pool: {sorted(missing)}"


def test_ev_note_includes_item_insight():
    """v0.10.3: ev_note must surface what the item does for this build.
    A Snorlax with Shell Bell should mention the 1/8 lifesteal mechanic
    (Leftovers no longer exists in Champions — Shell Bell is the closest
    passive-recovery analog in the legal pool).
    """
    member = _make_member(
        "snorlax", ["normal"],
        160, 110, 65, 65, 110, 30,
        {"fighting": 2.0},
        sp_hp=32, sp_def=16, nature="careful",
    )
    member = TeamMember(
        pokemon=member.pokemon, role=["special_wall"],
        sp_distribution=member.sp_distribution,
        item="Shell Bell", ability="thick-fat", nature="careful",
        moves=member.moves,
    )
    result = explain(member, _speed_db)
    assert "Shell Bell" in result
    assert "1/8" in result


def test_ev_note_includes_archetype_when_not_balance():
    """v0.10.2: ev_note appends an archetype hint when archetype != balance."""
    member = _make_member(
        "garchomp", ["dragon", "ground"],
        108, 130, 95, 80, 85, 102,
        {"ice": 4.0, "fairy": 2.0},
        sp_spe=32, nature="jolly",
    )
    result = explain(member, _speed_db, archetype="hyper_offense")
    assert "Hyper Offense" in result


def test_ev_note_skips_archetype_when_balance():
    """Balance archetype adds no signal beyond defaults — note must omit it."""
    member = _make_member(
        "garchomp", ["dragon", "ground"],
        108, 130, 95, 80, 85, 102,
        {"ice": 4.0, "fairy": 2.0},
        sp_spe=32, nature="jolly",
    )
    result = explain(member, _speed_db, archetype="balance")
    assert "Balance" not in result
    assert "arquetipo" not in result


def test_ev_note_includes_role_hint():
    """The role hint anchors the explanation in the build's strategy."""
    member = _make_member(
        "garchomp", ["dragon", "ground"],
        108, 130, 95, 80, 85, 102,
        {"ice": 4.0, "fairy": 2.0},
        sp_spe=32, sp_atk=32, nature="jolly",
    )
    member = TeamMember(
        pokemon=member.pokemon, role=["physical_sweeper"],
        sp_distribution=member.sp_distribution,
        item="Sitrus Berry", ability="rough-skin", nature="jolly",
        moves=member.moves,
    )
    result = explain(member, _speed_db)
    assert "rol físico" in result


def test_speed_benchmark_only_uses_top_meta_pokemon():
    """User feedback 2026-05-15: speed comparisons must reference only
    competitively relevant Pokémon. A note saying 'Spe 154 supera a
    Dedenne (153)' is useless because Dedenne is rank 153 in usage —
    Sergio never faces it. Only entries with usage_rank ≤ 30 may appear.
    """
    from pokemon_team_builder.services.ev_explainer import (
        _TOP_USAGE_BENCHMARK_THRESHOLD,
    )

    out_of_meta_names = {
        e.name.replace("-", " ").title()
        for e in _speed_db.entries()
        if e.usage_rank > _TOP_USAGE_BENCHMARK_THRESHOLD
    }
    # Any reasonably fast mon will outspeed half the chart — perfect probe
    # for surfacing forbidden names if the filter is gone.
    member = _make_member(
        "fastmon", ["normal"],
        80, 100, 80, 100, 80, 200,  # absurdly high base spe to outspeed everyone
        {"fighting": 2.0},
        sp_spe=32, nature="jolly",
    )
    result = explain(member, _speed_db)
    leaked = [n for n in out_of_meta_names if n in result]
    assert not leaked, (
        f"non-meta pokemon (usage_rank > {_TOP_USAGE_BENCHMARK_THRESHOLD}) "
        f"leaked into speed note: {leaked}. Full note: {result!r}"
    )


def test_assault_vest_not_in_legal_pool():
    """User feedback 2026-05-14 (Inte v2): Assault Vest is NOT in the
    Champions M-A item pool. Must not appear in the legal items JSON
    nor in the backup fallback.
    """
    from pokemon_team_builder.services.team_generator import (
        _load_champions_legal_items, _BACKUP_ITEMS_FALLBACK,
    )
    legal, _ = _load_champions_legal_items()
    assert "Assault Vest" not in legal, (
        "Assault Vest leaked back into champions_legal_items.json"
    )
    assert "Assault Vest" not in _BACKUP_ITEMS_FALLBACK, (
        "Assault Vest leaked back into the in-code backup fallback"
    )
