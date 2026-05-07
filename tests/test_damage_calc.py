import pytest
from pokemon_team_builder.services.damage_calc import (
    calc_stat, calc_damage, get_nature_mod, COMMON_ATTACKS
)


def test_calc_stat_hp_snorlax():
    # Snorlax base HP 160, 0 SPs, neutral: floor(2*160+31)*50/100 + 50 + 10 = floor(351*0.5)+60 = 175+60 = 235
    assert calc_stat(160, 0, 1.0, is_hp=True) == 235


def test_calc_stat_atk_garchomp_jolly_32():
    # Garchomp base Atk 130, 32 SPs, Jolly (+10% to Spe, not Atk → 1.0 for Atk)
    # EVs=256, ev_bonus=64; inner=floor(260+31)+64=355; raw=floor(355*0.5)+5=177+5=182; *1.0=182
    assert calc_stat(130, 32, 1.0) == 182


def test_calc_stat_spa_modifiers():
    # Base 100, 0 SPs, 1.1 modifier: inner=floor(200+31)=231; raw=floor(231*0.5)+5=115+5=120; *1.1=132
    assert calc_stat(100, 0, 1.1) == 132


def test_calc_stat_spe_0_neutral():
    # Base 60 (Incineroar): inner=floor(120+31)=151; raw=floor(151*0.5)+5=75+5=80; *1.0=80
    assert calc_stat(60, 0, 1.0) == 80


def test_get_nature_mod_adamant_atk():
    assert get_nature_mod("adamant", "atk") == 1.1


def test_get_nature_mod_adamant_spa():
    assert get_nature_mod("adamant", "spa") == 0.9


def test_get_nature_mod_neutral_stat():
    assert get_nature_mod("adamant", "spe") == 1.0


def test_get_nature_mod_jolly_spe():
    assert get_nature_mod("jolly", "spe") == 1.1


def test_get_nature_mod_unknown_nature():
    assert get_nature_mod("unknown", "atk") == 1.0


def test_common_attacks_has_18_entries():
    assert len(COMMON_ATTACKS) == 18


def test_common_attacks_all_types_present():
    expected = {
        "normal", "fire", "water", "electric", "grass", "ice",
        "fighting", "poison", "ground", "flying", "psychic", "bug",
        "rock", "ghost", "dragon", "dark", "steel", "fairy",
    }
    assert set(COMMON_ATTACKS.keys()) == expected


def test_common_attacks_have_power_and_name():
    for t, entry in COMMON_ATTACKS.items():
        assert "power" in entry, f"Missing power for {t}"
        assert "name" in entry, f"Missing name for {t}"
        assert entry["power"] > 0


def test_calc_damage_super_effective_over_50pct():
    # Landorus-T Earthquake (power 100) vs Incineroar: super-effective (ground vs fire)
    # Landorus-T base Atk 145, 32 SPs, Jolly → atk_stat ~218
    # Incineroar base HP 95, 0 SPs → 205; base Def 90, 0 SPs → 125
    atk = calc_stat(145, 32, 1.0)   # neutral nature on atk
    def_ = calc_stat(90, 0, 1.0)
    hp = calc_stat(95, 0, 1.0, is_hp=True)
    min_pct, max_pct = calc_damage(atk, def_, 100, 2.0, False, hp)
    assert max_pct > 50.0, f"Expected >50%, got {max_pct}%"


def test_calc_damage_resisted_low():
    # Grass move vs Steel type (0.25x effectiveness) should deal very little
    atk = calc_stat(100, 0, 1.0)
    def_ = calc_stat(100, 0, 1.0)
    hp = calc_stat(100, 0, 1.0, is_hp=True)
    min_pct, max_pct = calc_damage(atk, def_, 90, 0.25, False, hp)
    assert max_pct < 25.0


def test_calc_damage_returns_tuple():
    result = calc_damage(100, 100, 80, 1.0, False, 150)
    assert isinstance(result, tuple)
    assert len(result) == 2
    min_p, max_p = result
    assert min_p <= max_p
