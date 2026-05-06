## Why

El fix anterior (`fix-role-balance`) introdujo un bug crítico: el STAB override consulta `abilities[0]` pero la ability competitiva no es siempre la primera en PokeAPI. Ninetales-A, Pelipper, Machamp y otros nunca reciben sus mejores moves. Además, Incineroar (soporte VGC #1) nunca se detecta como `lead_support` por un gate de velocidad incorrecto, y Whimsicott/Klefki (Prankster setters) siguen siendo clasificados como sweepers.

## What Changes

- **Bug 0 fix**: STAB override itera todas las abilities del Pokémon en lugar de solo `abilities[0]`
- **Fix A**: la detección de `lead_support` por Fake Out / Follow Me / Rage Powder elimina el requisito `spe >= 90` (solo Tailwind lo mantiene)
- **Fix B**: `_WEATHER_SETTER_ABILITIES` renombrado a `_AUTO_LEAD_ABILITIES` e incluye `"prankster"` — Whimsicott y Klefki pasan a `lead_support`
- **Fix C**: `dynamic-punch` añadido a `_STAB_BY_TYPE["fighting"]` + override `"no-guard": {"close-combat": "dynamic-punch"}` para Machamp/Golurk
- **Fix D**: override `"drizzle": {"air-slash": "hurricane"}` para Pelipper
- **Fix E**: detección de weather setters usa `abilities[0]` + whitelist de species competitivos (`ninetales-alola`, `pelipper`, `politoed`, `torkoal`) en lugar de `any()` — elimina falsos positivos en Aurorus y Vanilluxe

## Capabilities

### New Capabilities

- `ability-aware-roles`: Detección precisa de roles competitivos basada en ability primaria, whitelist de species, y tipo de move (priority vs velocidad-dependiente).

### Modified Capabilities

*(sin specs anteriores)*

## Impact

- `pokemon_team_builder/services/synergy_engine.py`: rename constante, add prankster, add `_COMPETITIVE_WEATHER_SPECIES`, fix gate de velocidad para Fake Out
- `pokemon_team_builder/services/replica_exporter.py`: fix ability lookup loop, add dynamic-punch al STAB list, add no-guard y drizzle overrides
- Tests: nuevos tests para cada fix; todos los existentes deben seguir pasando
