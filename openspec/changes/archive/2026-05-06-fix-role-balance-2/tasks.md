## 1. synergy_engine.py — Rename + Prankster + Whitelist + Speed gate fix

- [x] 1.1 Renombrar `_WEATHER_SETTER_ABILITIES` → `_AUTO_LEAD_ABILITIES` y añadir `"prankster"` al frozenset
- [x] 1.2 Añadir `_COMPETITIVE_WEATHER_SPECIES: frozenset[str] = frozenset({"ninetales-alola", "pelipper", "politoed", "torkoal"})` como constante de módulo
- [x] 1.3 En `assign_role`: reemplazar `any(a.lower() in _AUTO_LEAD_ABILITIES for a in pokemon.abilities)` por lógica que comprueba `abilities[0]` O `pokemon.name in _COMPETITIVE_WEATHER_SPECIES` con alguna ability en `_AUTO_LEAD_ABILITIES`
- [x] 1.4 Dividir `_LEAD_SUPPORT_MARKERS` en dos: `_TAILWIND_MARKERS = ("tailwind",)` (requiere spe>=90) y `_PRIORITY_SUPPORT_MARKERS = ("fake-out", "follow-me", "rage-powder")` (sin gate de velocidad)
- [x] 1.5 Actualizar la rama de detección `lead_support` en `assign_role` para usar las dos listas por separado
- [x] 1.6 Actualizar `_move_contains_any` calls o añadir lógica inline para la nueva separación
- [x] 1.7 Test `test_prankster_primary_is_lead`: Pokémon con `abilities[0]="prankster"` → `roles[0]=="lead_support"`
- [x] 1.8 Test `test_prankster_hidden_not_lead`: Pokémon con prankster en índice 2 → NO inyecta `lead_support` por prankster
- [x] 1.9 Test `test_fake_out_slow_mon_is_lead`: Pokémon con `spe=60` y `fake-out` en pool → `lead_support` en roles
- [x] 1.10 Test `test_tailwind_slow_not_lead`: Pokémon con `spe=50` y solo `tailwind` → NO `lead_support`
- [x] 1.11 Test `test_aurorus_not_weather_setter`: `name="aurorus"`, `abilities=["refrigerate","snow-warning"]` → NO `lead_support` por weather
- [x] 1.12 Test `test_ninetales_alola_whitelist_lead`: `name="ninetales-alola"`, `abilities=["snow-cloak","snow-warning"]` → `roles[0]=="lead_support"`

## 2. replica_exporter.py — Ability lookup fix + nuevos overrides

- [x] 2.1 Añadir `"dynamic-punch"` al final de `_STAB_BY_TYPE["fighting"]`
- [x] 2.2 Añadir `"dynamic-punch": "fighting"` a `_MOVE_TYPE` y `"dynamic-punch": "physical"` a `_MOVE_CATEGORY`
- [x] 2.3 Añadir overrides a `_ABILITY_STAB_OVERRIDES`: `"no-guard": {"close-combat": "dynamic-punch"}` y `"drizzle": {"air-slash": "hurricane"}`
- [x] 2.4 En `select_moves_for_role`: reemplazar `pokemon.abilities[0].lower() if pokemon.abilities else ""` por un loop que itera `pokemon.abilities` y retorna la primera ability que tenga entrada en `_ABILITY_STAB_OVERRIDES`
- [x] 2.5 Test `test_ninetales_a_blizzard_via_ability_idx1`: `abilities=["snow-cloak","snow-warning"]`, pool con blizzard+ice-beam → `slot2=="blizzard"`
- [x] 2.6 Test `test_machamp_dynamic_punch_via_no_guard_idx1`: `abilities=["guts","no-guard"]`, pool con close-combat+dynamic-punch → `slot2=="dynamic-punch"`
- [x] 2.7 Test `test_pelipper_hurricane_via_drizzle`: `abilities=["keen-eye","drizzle"]`, pool con air-slash+hurricane → `slot2=="hurricane"`
- [x] 2.8 Test `test_no_override_no_matching_ability`: `abilities=["pressure"]`, pool con ice-beam → `slot2=="ice-beam"` (sin override)
- [x] 2.9 Test `test_fighting_no_guard_absent_uses_close_combat`: `abilities=["guts"]`, pool con close-combat+dynamic-punch → `slot2=="close-combat"`
- [x] 2.10 Test `test_flying_no_drizzle_uses_air_slash`: `abilities=["keen-eye"]`, pool con air-slash+hurricane → `slot2=="air-slash"`

## 3. Verificación final

- [x] 3.1 Ejecutar suite completa: `pytest` — todos los tests deben pasar
- [x] 3.2 Verificar Incineroar: `assign_role` con `spe=60, moves=["fake-out","protect","flare-blitz","knock-off"]` → `lead_support` en roles
- [x] 3.3 Verificar Whimsicott: `assign_role` con `abilities=["prankster"]` → `roles[0]=="lead_support"`
