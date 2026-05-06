## Why

Los equipos generados muestran 4–6 sweepers con natures ofensivos y EVs puramente ofensivos, sin suportes ni bulk. Feedback competitivo confirmó que el sistema no respeta composición de equipo mínima (máx. 2 sweepers, al menos 1 soporte) y que Pokémon de clima como Ninetales-A reciben sets incorrectos.

## What Changes

- **Sweeper cap**: equipos con más de 2 sweepers puros reciben penalización fuerte en el beam search, forzando selección de suportes/walls cuando existen en el pool.
- **Weather setter role**: Pokémon con abilities de clima (Snow Warning, Drought, Drizzle, Sand Stream) reciben `lead_support` como rol primario automáticamente, sin depender de que aprendan Tailwind/Fake Out.
- **Ability-aware STAB selection**: cuando un Pokémon tiene una ability que otorga precisión perfecta a un move (Snow Warning → Blizzard, Drizzle → Thunder), ese move se prefiere sobre la alternativa de menor BP en la lista `_STAB_BY_TYPE`.

## Capabilities

### New Capabilities

- `role-balance`: Reglas de composición de equipo: cap de sweepers puros, detección de weather setters, selección de STAB ability-aware.

### Modified Capabilities

*(ninguna — no hay specs existentes)*

## Impact

- `pokemon_team_builder/services/synergy_engine.py` — `assign_role`: añade `_WEATHER_SETTER_ABILITIES`, inserta `lead_support` para weather setters.
- `pokemon_team_builder/services/team_generator.py` — `_partial_score`: añade penalización por pure sweeper count > 2.
- `pokemon_team_builder/services/replica_exporter.py` — `select_moves_for_role`: añade `_ABILITY_STAB_OVERRIDES` y lógica de override post-slot2.
- Tests: añadir casos para los 3 fixes. Sin cambios en modelos, API, CLI ni formato de salida.
