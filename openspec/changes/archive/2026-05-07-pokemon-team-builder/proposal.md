## Why

Fans de Pokémon Champions quieren construir equipos competitivos alrededor de su Pokémon favorito, pero el sistema de Doubles (Pick 4 de 6), la mecánica de Stat Points y el pool reducido (~263 Pokémon legales) hacen difícil saber qué compañeros cubren mejor las debilidades del ancla. Esta herramienta elimina esa barrera: el usuario elige su Pokémon favorito y el sistema construye un equipo equilibrado y legal para Pokémon Champions.

## What Changes

- Nueva herramienta CLI que recibe un Pokémon ancla y genera un equipo de 6 miembros legal para Champions (Regulation M-A).
- Consulta a PokéAPI para tipos, stats base y moveset; filtra al pool legal de Champions (~263 Pokémon).
- Motor de sinergias orientado a **Doubles**: cobertura de tipos, roles de Doubles (lead, sweeper, support, trick room setter, redirect), resistencias cruzadas y synergy de moves de área.
- Sistema de **Stat Points (SPs)**: distribución sugerida respetando máx. 66 SPs por Pokémon y máx. 32 por stat (reemplaza EVs/IVs del sistema antiguo; IVs son 31 fijos).
- **Item Clause**: garantiza que ningún ítem se repita en el equipo.
- Generador de hasta 3 variantes de equipo con puntuación de viabilidad para Doubles.
- Exportación en formato **PokePaste** compatible con PikaChampions y ChampTeams.gg (herramientas oficiales de la comunidad Champions); también genera código **Replica Team** si la API lo permite.

## Capabilities

### New Capabilities

- `pokemon-lookup`: Consulta PokéAPI para datos del Pokémon (tipos, stats base, moveset) y verifica que esté en el pool legal de Champions (~263 Pokémon). Calcula debilidades con multiplicadores.
- `synergy-engine`: Analiza cobertura de tipos y roles orientados a **Doubles** (Pick 4 de 6). Detecta huecos de roles y vulnerabilidades compartidas. Considera la mecánica de selección de 4.
- `team-generator`: Genera hasta 3 variantes de equipo de 6 alrededor del ancla, respetando Species Clause, Item Clause y el pool legal de Champions. Sugiere distribución de SPs por Pokémon.
- `viability-rater`: Puntúa cada variante (0–100) para el meta de Doubles de Champions. Compara variantes y recomienda la mejor.
- `replica-export`: Exporta el equipo seleccionado en formato PokePaste compatible con PikaChampions/ChampTeams.gg, incluyendo SPs en lugar de EVs.

### Modified Capabilities

## Impact

- **Stack nuevo** — proyecto desde cero; sin código previo.
- **PokéAPI** — fuente de datos de Pokémon (REST, sin auth); se superpone la lista legal de Champions mantenida localmente.
- **Lista legal Champions** — fichero local con los ~263 Pokémon de Regulation M-A; debe actualizarse cuando cambie la regulación.
- **GitHub** — repo `Janisher-Illderment/pokemon-team-builder` (público).
- **Formato de export** — PokePaste (texto), NO formato nativo Showdown; compatible con PikaChampions y ChampTeams.gg.
- **No base de datos propia** — toda la data de Pokémon viene de PokéAPI + lista legal local; sin persistencia en v1.
