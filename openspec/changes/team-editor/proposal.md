## Why

El flujo actual es de un solo disparo: el usuario introduce un anchor, recibe 1–3 variantes y, si quiere ajustar algo (cambiar un move, swap un Pokémon), solo le queda regenerar todo desde cero o editar a mano el PokePaste — perdiendo score y validación. Además, la comunidad ya comparte muchos equipos en formato PokePaste (LabMaus, torneos, Discord); poder pegar uno y obtener un análisis automático (debilidades de tipo, gaps de cobertura, score) acerca la herramienta a los equipos que ya circulan en el meta sin obligar al usuario a empezar desde el generador.

Estas dos features son complementarias: la edición iterativa cubre el "generé esto, lo quiero refinar" y el import cubre el "tengo este equipo de fuera, ¿es bueno?". Ambas reutilizan los servicios puros existentes (`viability_rater`, `synergy_engine`, `replica_exporter`) sin tocar el core de generación.

## What Changes

- Añadir endpoint `PATCH /edit-member` que recibe el `TeamVariant` actual, el índice del miembro a modificar y la edición (`move_swap`, `item_swap`, `pokemon_swap`); recompila el `TeamVariant` resultante y devuelve el equipo con score, score_explanation y EV notes recalculados — sin volver a llamar al generador.
- Añadir endpoint `POST /import` que acepta texto PokePaste estándar Showdown, parsea los 6 miembros (nombre, item, ability, nature, EVs, moves), construye un `TeamVariant` y devuelve el mismo formato `VariantOut` que `/generate` (score, recommended, members, pokepaste re-serializado).
- Conversión EVs Showdown → SP: el formato de PokePaste usa EVs Showdown (0–252 por stat, hasta 508 totales); el dominio interno usa SP (0–32 por stat, máx 66 totales). La conversión es `sp = ev // 8` con clamp a `MAX_SP_STAT` y `MAX_SP_TOTAL`.
- Frontend Alpine.js: añadir botones "Editar" por miembro en cada variant card (selector inline de move/item/Pokémon) y una sección separada "Importar PokePaste" con textarea + botón "Analizar".

## Capabilities

### New Capabilities

- `team-editing`: Endpoint `PATCH /edit-member` que aplica una edición puntual (move_swap | item_swap | pokemon_swap) sobre un `TeamVariant` recibido como input, valida la edición contra el pool legal y el move pool del Pokémon afectado, y devuelve el `VariantOut` actualizado con score y EV notes recomputados. NO regenera el equipo entero.
- `pokepaste-import`: Endpoint `POST /import` que parsea un PokePaste de Showdown (1–6 miembros), convierte EVs a SP, valida cada miembro contra el pool legal M-A, construye un `TeamVariant`, lo puntúa con `viability_rater` y devuelve el análisis en formato `VariantOut`.

### Modified Capabilities

- `web-ui`: La interfaz añade dos zonas: (a) controles de edición por miembro dentro de cada variant card (botones "Cambiar move", "Cambiar item", "Swap Pokémon"); (b) sección "Importar PokePaste" con textarea + botón "Analizar" que muestra el resultado en una variant card adicional.

## Impact

- `pokemon_team_builder/api/router.py`: añadir handlers `edit_member` y `import_pokepaste`.
- `pokemon_team_builder/api/schemas.py`: añadir `EditMemberRequest`, `EditKind`, `ImportRequest`, `ImportResponse` (reutiliza `VariantOut`).
- `pokemon_team_builder/services/pokepaste_parser.py` (nuevo): parser puro `parse_pokepaste(text: str) -> TeamVariant` con conversión EV→SP.
- `pokemon_team_builder/services/team_editor.py` (nuevo): orquestador `apply_edit(variant, index, edit) -> TeamVariant` que aplica la edición y rescore; reutiliza `select_moves_for_role` de `replica_exporter` cuando un swap de Pokémon necesita rederivar moves.
- `pokemon_team_builder/web/static/index.html` y `app.js`: nuevos componentes Alpine.js para edición y para import.
- Tests: `tests/test_pokepaste_parser.py`, `tests/test_team_editor.py`, ampliación de `tests/test_api.py` con casos de `/edit-member` y `/import`.
- Sin nuevas dependencias en `pyproject.toml`. Sin cambios en `team_generator.py`, `synergy_engine.py`, `viability_rater.py`, `replica_exporter.py` ni en los modelos de dominio.
- Tests actuales: 173 passing — la meta es seguir en verde tras la suma de tests nuevos del editor y del parser.
