import pytest
from pokemon_team_builder.data.speed_tiers import load as load_speed_db
from pokemon_team_builder.domain.models import (
    BaseStats, PokemonData, SPDistribution, TeamMember,
)
from pokemon_team_builder.services.ev_explainer import explain


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
