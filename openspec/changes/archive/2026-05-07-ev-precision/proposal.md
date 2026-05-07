## Why

The current EV notes are generic strings like "32 Atk para daño máximo" that tell a player nothing useful — any VGC player already knows max attack means max damage. What competitive players actually care about is: "does my Garchomp outspeed Flutter Mane?" and "does this bulk spread survive Landorus-T's Earthquake?". Without real speed tier data and damage math, the EV rationale is noise rather than signal.

## What Changes

- **`data/speed_tiers.json`**: Static data file with ~50 meta-relevant pokémon, their base Speed stats, and level-50 Speed values at common SP investment levels (0, 4, 8, 16, 24, 32) for neutral and +Spe natures. Sourced from the Champions speed tier sheet.
- **`services/damage_calc.py`**: Pure function damage calculator using the standard Pokémon damage formula at level 50, computing final stats from base stats + SP investment + nature modifier.
- **`services/ev_explainer.py`**: Orchestration service that builds the `ev_note` using speed tier comparison (for Spe investment) and damage survival check (for HP/Def/SpD investment), replacing the generic role-based note generator in `api/router.py`.
- **API `ev_note` upgraded**: From generic ("32 Spe para velocidad máxima") to specific ("32 Spe supera a Rillaboom (base 85) y Incineroar (base 60) — no alcanza a Flutter Mane (base 135)").

## Capabilities

### New Capabilities

- `speed-tiers`: Speed tier data file + lookup service that computes level-50 Speed for any base stat / SP / nature combination and identifies which meta pokémon a given speed investment beats or loses to.
- `damage-calc`: Standard damage formula implementation at level 50, computing stats from base + SP + nature; used to determine whether a defensive EV spread survives a specific attack.
- `ev-explainer`: Orchestration layer that uses speed-tiers and damage-calc to produce specific, accurate EV rationale notes per team member.

### Modified Capabilities

- `ev-display`: The `ev_note` field in `MemberOut` (introduced in meta-quality-v2) is now populated by `ev_explainer` instead of the generic role-based string in `api/router.py`.

## Impact

- **New files**: `pokemon_team_builder/data/speed_tiers.json`, `pokemon_team_builder/services/damage_calc.py`, `pokemon_team_builder/services/ev_explainer.py`, `tests/test_damage_calc.py`, `tests/test_ev_explainer.py`
- **Modified files**: `api/router.py` (replace `_build_ev_note` with `ev_explainer.explain()`), `pokemon_team_builder/data/speed_tiers.json` (new static file)
- **Breaking**: None — `ev_note` is already in the schema from meta-quality-v2; content changes from generic to specific
- **Dependencies**: Requires meta-quality-v2 to be applied first (`ev_note` field must exist in `MemberOut`)
