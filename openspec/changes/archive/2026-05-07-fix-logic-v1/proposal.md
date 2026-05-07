## Why

Análisis adversarial combinado (Sola + Tecle, 2026-05-03) identificó 18 issues confirmados
en la lógica de generación de equipos. Los más graves producen PokePastes con moves
duplicados (rechazados por el importador), natures que penalizan el moveset que el propio
sistema generó, y una métrica de viability que siempre da la misma puntuación a la
componente de items (código muerto). Este change agrupa todos los fixes de v1 scope —
sin rediseño del beam search ni del viability-rater completo (eso va a v2).

## What Changes

- `team_generator.py`: añadir `lead_support` a `_NO_CHOICE_ROLES`; remover `Loaded Dice`;
  añadir SP template para `redirect`; corregir `assign_role` para comparar max(Atk, SpA)
  antes de asignar sweeper role; tabla de incompatibilidades item↔moveset (WP+setup);
  `_item_is_activatable` verifica moveset generado, no solo learnset
- `replica_exporter.py`: `_fallback_move` nunca ignora `used`; `_MOVE_CATEGORY` vacío
  falla en pass 0; Protect verifica move_pool; nature derivada del moveset, no del role;
  tabla de overrides en `_format_species` para nombres especiales (kommo-o, ho-oh, etc.)
- `viability_rater.py`: eliminar penalización de Life Orb (código muerto); documentar
  limitación de `_items_points`
- `data/role_sp_templates.json`: añadir template `redirect`

## Capabilities

### Modified Capabilities

- `team-generator-logic`: Correcciones a la asignación de roles, items y SPs en `team_generator.py`
- `move-export-logic`: Correcciones a la selección de moves, natures y format de especies en `replica_exporter.py`
- `viability-cleanup`: Limpieza de código muerto y documentación de limitaciones en `viability_rater.py`

## Impact

- `pokemon_team_builder/services/team_generator.py`
- `pokemon_team_builder/services/replica_exporter.py`
- `pokemon_team_builder/services/viability_rater.py`
- `pokemon_team_builder/data/role_sp_templates.json`
- `tests/test_team_generator.py`
- `tests/test_replica_exporter.py`
- `tests/test_viability_rater.py`
