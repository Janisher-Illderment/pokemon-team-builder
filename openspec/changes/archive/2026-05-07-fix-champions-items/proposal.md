## Why

El pool de objetos de `team_generator.py` asigna items que no existen en Pokémon Champions (Choice Band, Choice Specs, Assault Vest, Life Orb, Eject Button). Cualquier equipo exportado con estos objetos falla silenciosamente al importarlo en PikaChampions / ChampTeams.gg — el Pokémon se importa sin objeto. Se necesita corregir antes del primer uso real del tool.

## What Changes

- Reemplazar `_DEFAULT_ITEM_BY_ROLE` con objetos Champions-legales por rol
- Reemplazar `_FALLBACK_ITEM` (actualmente "Choice Scarf" — verificar si está en el juego)
- Reemplazar `_BACKUP_ITEMS` para que el pool de 30 objetos de relleno use solo items confirmados en Champions
- Actualizar tests que usen items ahora ilegales como fixtures

## Capabilities

### New Capabilities

- `champions-item-pool`: Pool de objetos válidos para Pokémon Champions — define qué items puede asignar el generador de equipos y la lógica de fallback por rol

### Modified Capabilities

<!-- ninguna — no hay specs existentes aún -->

## Impact

- `pokemon_team_builder/services/team_generator.py`: `_DEFAULT_ITEM_BY_ROLE`, `_FALLBACK_ITEM`, `_BACKUP_ITEMS`
- `tests/test_team_generator.py`: fixtures con items ilegales
- `tests/test_replica_exporter.py`: fixture `_basic_variant()` si usa items ilegales
