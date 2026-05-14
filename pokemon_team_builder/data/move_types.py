"""Canonical move → damage type mapping.

Neutral module — consumed by both ``services.replica_exporter`` (for
STAB-aware slot 3 selection) and ``services.synergy_engine`` (for STAB
filter in ``analyze_coverage``). Lives in ``data/`` to avoid the prior
cross-service lazy import that violated DRY and risked drift between
the two consumers.

Phase 4b cleanup (2026-05-14): extracted from
``services.replica_exporter._MOVE_TYPE`` per Tecle review Brief #9.

Extending this list:
1. Add the move slug here (PokeAPI normalised, lowercase, hyphenated).
2. If the move is in ``_COVERAGE_PRIORITY`` or any ``_STAB_BY_TYPE``
   list of replica_exporter, no further action — both consumers
   pick it up automatically.
3. Run ``pytest tests/test_coverage_stab.py`` to confirm STAB
   coverage continues to work for the new move.
"""

from __future__ import annotations

# Map: move slug (PokeAPI normalised) → damage type (lowercase).
# Covers all moves that appear in coverage slots or STAB selection.
MOVE_TYPE: dict[str, str] = {
    # Coverage priority moves
    "earthquake": "ground",
    "ice-beam": "ice",
    "thunderbolt": "electric",
    "psychic": "psychic",
    "dazzling-gleam": "fairy",
    "shadow-ball": "ghost",
    "focus-blast": "fighting",
    "rock-slide": "rock",
    "energy-ball": "grass",
    "flamethrower": "fire",
    # Additional coverage
    "surf": "water",
    "air-slash": "flying",
    "iron-head": "steel",
    "dark-pulse": "dark",
    "dragon-pulse": "dragon",
    "poison-jab": "poison",
    "bug-buzz": "bug",
    "flash-cannon": "steel",
    # STAB — normal
    "body-slam": "normal",
    "double-edge": "normal",
    "return": "normal",
    "hyper-voice": "normal",
    "tackle": "normal",
    # fire
    "fire-blast": "fire",
    "heat-wave": "fire",
    "fire-punch": "fire",
    "overheat": "fire",
    "ember": "fire",
    # water
    "hydro-pump": "water",
    "scald": "water",
    "muddy-water": "water",
    "waterfall": "water",
    "water-pulse": "water",
    # electric
    "thunder": "electric",
    "thunder-punch": "electric",
    "wild-charge": "electric",
    "discharge": "electric",
    # grass
    "leaf-storm": "grass",
    "giga-drain": "grass",
    "grass-knot": "grass",
    "leaf-blade": "grass",
    "seed-bomb": "grass",
    # ice
    "blizzard": "ice",
    "icicle-crash": "ice",
    "ice-punch": "ice",
    "ice-fang": "ice",
    "freeze-dry": "ice",
    # fighting
    "close-combat": "fighting",
    "drain-punch": "fighting",
    "aura-sphere": "fighting",
    "brick-break": "fighting",
    "dynamic-punch": "fighting",
    # poison
    "sludge-bomb": "poison",
    "gunk-shot": "poison",
    "sludge-wave": "poison",
    # ground
    "earth-power": "ground",
    "high-horsepower": "ground",
    "bulldoze": "ground",
    # flying
    "brave-bird": "flying",
    "hurricane": "flying",
    "drill-peck": "flying",
    "aerial-ace": "flying",
    # psychic
    "psyshock": "psychic",
    "psystrike": "psychic",
    "expanding-force": "psychic",
    "stored-power": "psychic",
    # bug
    "u-turn": "bug",
    "x-scissor": "bug",
    "megahorn": "bug",
    "leech-life": "bug",
    # rock
    "stone-edge": "rock",
    "power-gem": "rock",
    "ancient-power": "rock",
    # ghost
    "shadow-claw": "ghost",
    "poltergeist": "ghost",
    # dragon
    "draco-meteor": "dragon",
    "dragon-claw": "dragon",
    # dark
    "knock-off": "dark",
    "crunch": "dark",
    "foul-play": "dark",
    # steel
    "meteor-mash": "steel",
    "iron-tail": "steel",
    # fairy
    "moonblast": "fairy",
    "play-rough": "fairy",
    "fleur-cannon": "fairy",
}
