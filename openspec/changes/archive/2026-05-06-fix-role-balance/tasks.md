## 1. synergy_engine.py — Weather setter role

- [x] 1.1 Añadir `_WEATHER_SETTER_ABILITIES: frozenset[str] = frozenset({"drought", "drizzle", "snow-warning", "sand-stream"})` como constante de módulo
- [x] 1.2 En `assign_role`, antes del bloque de stat-based roles, comprobar si alguna ability del pokemon está en `_WEATHER_SETTER_ABILITIES` e insertar `"lead_support"` al inicio de `roles` si es así
- [x] 1.3 Añadir test `test_weather_setter_gets_lead_support_primary`: verificar Ninetales-A (Snow Warning) → primer rol es `lead_support`
- [x] 1.4 Añadir test `test_weather_setter_tyranitar_lead_plus_physical`: Tyranitar (Sand Stream, Atk 134) → `["lead_support", "physical_sweeper"]`
- [x] 1.5 Añadir test `test_non_weather_ability_unaffected`: Pokémon sin weather ability no recibe `lead_support` por esta ruta

## 2. team_generator.py — Sweeper cap en _partial_score

- [x] 2.1 En `_partial_score`, calcular `pure_sweeper_count`: número de miembros cuya lista de roles es subconjunto de `{"physical_sweeper", "special_sweeper"}`
- [x] 2.2 Aplicar penalización `-(pure_sweeper_count - 2) * 4.0` cuando `pure_sweeper_count > 2`
- [x] 2.3 Añadir test `test_partial_score_penalizes_excess_sweepers`: equipo de 3 sweepers puros tiene score menor que equipo de 2 sweepers + 1 lead
- [x] 2.4 Añadir test `test_weather_setter_not_counted_as_pure_sweeper`: Pokémon con roles `["lead_support", "special_sweeper"]` no incrementa `pure_sweeper_count`

## 3. replica_exporter.py — Ability-aware STAB override

- [x] 3.1 Añadir `_ABILITY_STAB_OVERRIDES: dict[str, dict[str, str]] = {"snow-warning": {"ice-beam": "blizzard"}}` como constante de módulo
- [x] 3.2 En `select_moves_for_role`, después de determinar `slot2`, comprobar si la ability primaria del pokemon está en `_ABILITY_STAB_OVERRIDES` y si `slot2` tiene un override mapeado
- [x] 3.3 Si el override target está en `move_pool` y no en `used`, reemplazar `slot2` con el override target
- [x] 3.4 Añadir test `test_snow_warning_prefers_blizzard`: Pokémon con Snow Warning y ambos moves → slot2 es `blizzard`
- [x] 3.5 Añadir test `test_snow_warning_fallback_ice_beam`: Snow Warning pero sin Blizzard en pool → slot2 es `ice-beam`
- [x] 3.6 Añadir test `test_no_override_without_weather_ability`: Pokémon Ice sin Snow Warning → slot2 es `ice-beam` (sin cambios)

## 4. Verificación final

- [x] 4.1 Ejecutar suite completa: `pytest` — todos los tests existentes deben pasar
- [x] 4.2 Test manual: generar equipo con Ninetales-A como anchor, verificar Blizzard en slot2 y nature Calm/Jolly según moveset
