import pytest
from pokemon_team_builder.data.speed_tiers import load, _calc_speed, _nature_spe_mod


def test_calc_speed_base85_neutral_0sps():
    # Rillaboom base 85 not in pool, but formula: floor((floor(2*85+31)*50/100)+5)*1.0 = floor((floor(201)*0.5)+5) = floor(100.5+5) = 105
    # floor(2*85+31) = floor(201) = 201; 201*50/100 = 100.5 → floor = 100; +5 = 105
    assert _calc_speed(85, 0, 1.0) == 105


def test_calc_speed_base135_neutral_0sps():
    # Flutter Mane base 135: floor(2*135+31) = 301; 301*50/100 = 150.5 → 150; +5 = 155
    assert _calc_speed(135, 0, 1.0) == 155


def test_calc_speed_base102_jolly_32sps():
    # Garchomp 102, Jolly (+10%), 32 SPs (= 256 EVs → floor(256/4)=64 added)
    # floor(2*102+31 + floor(256/4)) = floor(204+31+64) = 299; 299*50/100=149.5→149; +5=154; *1.1=169.4→169
    result = _calc_speed(102, 32, 1.1)
    assert result == 169


def test_calc_speed_base60_nature_neutral_0sps():
    # Incineroar base 60: floor(2*60+31)=151; 151*50/100=75.5→75; +5=80
    assert _calc_speed(60, 0, 1.0) == 80


def test_nature_mod_jolly():
    assert _nature_spe_mod("jolly") == 1.1


def test_nature_mod_brave():
    assert _nature_spe_mod("brave") == 0.9


def test_nature_mod_neutral():
    assert _nature_spe_mod("hardy") == 1.0


def test_load_returns_db():
    db = load()
    assert db is not None


def test_db_has_enough_entries():
    db = load()
    assert len(db.entries()) >= 50


def test_db_contains_key_pokemon():
    db = load()
    names = {e.name for e in db.entries()}
    assert "incineroar" in names
    assert "aerodactyl" in names
    assert "garchomp" in names


def test_compute_speed_garchomp_jolly_32():
    db = load()
    speed = db.compute_speed(102, 32, "jolly")
    assert speed == 169


def test_faster_than_incineroar():
    db = load()
    # Incineroar base 60, 0 SPs, neutral = 80 speed
    incineroar_speed = 80
    faster = db.faster_than(incineroar_speed + 1)  # things slower than 81
    assert "incineroar" in faster


def test_slower_than_aerodactyl():
    db = load()
    # Aerodactyl base 130, neutral 0SP = 165 speed
    aerodactyl_speed = _calc_speed(130, 0, 1.0)
    slower = db.slower_than(aerodactyl_speed - 1)
    assert "aerodactyl" in slower


def test_faster_than_excludes_faster_pokemon():
    db = load()
    fast = _calc_speed(130, 0, 1.0)  # aerodactyl base speed neutral
    slower = db.faster_than(fast)
    assert "aerodactyl" not in slower


def test_sorted_by_base_spe_descending():
    db = load()
    entries = db.entries()
    speeds = [e.base_spe for e in entries]
    assert speeds == sorted(speeds, reverse=True)
