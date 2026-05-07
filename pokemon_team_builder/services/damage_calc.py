from __future__ import annotations

import math

_LEVEL = 50
_IV = 31

COMMON_ATTACKS: dict[str, dict] = {
    "normal":   {"power": 90,  "name": "Return",           "category": "physical"},
    "fire":     {"power": 90,  "name": "Llamarada",         "category": "special"},
    "water":    {"power": 90,  "name": "Hidrobomba",        "category": "special"},
    "electric": {"power": 90,  "name": "Trueno",            "category": "special"},
    "grass":    {"power": 90,  "name": "Hoja Aguda",        "category": "special"},
    "ice":      {"power": 90,  "name": "Vendaval Gélido",   "category": "special"},
    "fighting": {"power": 80,  "name": "Close Combat",      "category": "physical"},
    "poison":   {"power": 90,  "name": "Bomba Lodo",        "category": "special"},
    "ground":   {"power": 100, "name": "Terremoto",         "category": "physical"},
    "flying":   {"power": 85,  "name": "Acrobacia",         "category": "physical"},
    "psychic":  {"power": 90,  "name": "Psíquico",          "category": "special"},
    "bug":      {"power": 80,  "name": "Megacuerno",        "category": "physical"},
    "rock":     {"power": 100, "name": "Pedrada",           "category": "physical"},
    "ghost":    {"power": 90,  "name": "Bola Sombra",       "category": "special"},
    "dragon":   {"power": 90,  "name": "Draco Meteor",      "category": "special"},
    "dark":     {"power": 80,  "name": "Golpe Umbrío",      "category": "physical"},
    "steel":    {"power": 80,  "name": "Giro Bola",         "category": "physical"},
    "fairy":    {"power": 90,  "name": "Luz Lunar",         "category": "special"},
}

_NATURE_TABLE: dict[str, tuple[str, str]] = {
    "hardy":   ("", ""),   "lonely":  ("atk", "def"),
    "brave":   ("atk", "spe"), "adamant": ("atk", "spa"),
    "naughty": ("atk", "spd"), "bold":    ("def", "atk"),
    "docile":  ("", ""),   "relaxed": ("def", "spe"),
    "impish":  ("def", "spa"), "lax":     ("def", "spd"),
    "timid":   ("spe", "atk"), "hasty":   ("spe", "def"),
    "serious": ("", ""),   "jolly":   ("spe", "spa"),
    "naive":   ("spe", "spd"), "modest":  ("spa", "atk"),
    "mild":    ("spa", "def"), "quiet":   ("spa", "spe"),
    "bashful": ("", ""),   "rash":    ("spa", "spd"),
    "calm":    ("spd", "atk"), "gentle":  ("spd", "def"),
    "sassy":   ("spd", "spe"), "careful": ("spd", "spa"),
    "quirky":  ("", ""),
}


def get_nature_mod(nature: str, stat: str) -> float:
    entry = _NATURE_TABLE.get(nature.lower())
    if entry is None:
        return 1.0
    boost, reduce = entry
    if stat == boost:
        return 1.1
    if stat == reduce:
        return 0.9
    return 1.0


def calc_stat(base: int, sps: int, nature_mod: float, is_hp: bool = False) -> int:
    """Level-50 stat formula. SPs map as sp*8 EVs (max 32 SP → 256 EVs)."""
    evs = sps * 8
    ev_bonus = math.floor(evs / 4)
    inner = math.floor(2 * base + _IV) + ev_bonus
    if is_hp:
        return math.floor(inner * _LEVEL / 100) + _LEVEL + 10
    raw = math.floor(inner * _LEVEL / 100) + 5
    return math.floor(raw * nature_mod)


def calc_damage(
    atk_stat: int,
    def_stat: int,
    move_power: int,
    effectiveness: float,
    stab: bool,
    defender_hp: int,
) -> tuple[float, float]:
    """Returns (min_pct, max_pct) as % of defender HP. Standard gen3+ formula at level 50."""
    base_dmg = math.floor(math.floor(2 * _LEVEL / 5 + 2) * move_power * atk_stat / def_stat) // 50 + 2
    stab_mod = 1.5 if stab else 1.0
    eff_dmg = base_dmg * stab_mod * effectiveness
    min_dmg = math.floor(eff_dmg * 0.85)
    max_dmg = math.floor(eff_dmg)
    min_pct = round(min_dmg / defender_hp * 100, 1)
    max_pct = round(max_dmg / defender_hp * 100, 1)
    return (min_pct, max_pct)
