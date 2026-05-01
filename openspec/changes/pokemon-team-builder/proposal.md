## Why

Fans de Pokémon quieren construir equipos competitivos o semi-competitivos alrededor de su Pokémon favorito, pero sin conocimiento profundo de la metagame es difícil conseguir un equipo equilibrado. Esta herramienta elimina esa barrera: el usuario elige su Pokémon ancla y el sistema construye el equipo por él.

## What Changes

- Nueva herramienta CLI/web que recibe un Pokémon de entrada y genera un equipo de 6 miembros sinérgico y viable.
- Consulta a PokéAPI para obtener tipos, stats base, moveset y debilidades de cada Pokémon.
- Motor de análisis de sinergias: cobertura de tipos, roles de equipo (sweeper, tank, support, hazard setter, etc.) y resistencias cruzadas.
- Generador de equipo que rellena los 5 slots restantes para cubrir las debilidades del Pokémon ancla.
- Evaluador de viabilidad que puntúa el equipo resultante y explica los motivos.
- Exportación del equipo en formato Showdown (texto copiable para Pokémon Showdown).

## Capabilities

### New Capabilities

- `pokemon-lookup`: Consulta PokéAPI para obtener datos completos de un Pokémon (tipos, stats, debilidades, moveset). Es la fuente de datos de todo el sistema.
- `synergy-engine`: Analiza cobertura de tipos ofensiva/defensiva, identifica huecos y asigna roles de equipo. Núcleo del producto.
- `team-generator`: Selecciona los 5 Pokémon que mejor complementan al ancla usando los datos del synergy-engine. Genera 1-3 variantes de equipo.
- `viability-rater`: Puntúa cada equipo generado (0–100) basándose en cobertura, balance de roles y stats combinados. Muestra explicación legible.
- `showdown-export`: Serializa el equipo al formato texto de Pokémon Showdown para importar directamente.

### Modified Capabilities

## Impact

- **Stack nuevo** — proyecto desde cero; sin código previo.
- **Dependencia externa** — PokéAPI (REST, sin autenticación, rate limit generoso).
- **GitHub** — repo nuevo `Janisher-Illderment/pokemon-team-builder` (público o privado según usuario).
- **Sin datos locales propios** — toda la data de Pokémon viene de PokéAPI; no se almacena una base de datos propia en v1.
