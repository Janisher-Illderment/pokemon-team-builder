## ADDED Requirements

### Requirement: Generar equipo de 6 alrededor de un Pokémon ancla respetando las reglas de Champions
El sistema SHALL, dado un Pokémon ancla legal en Champions, seleccionar 5 Pokémon adicionales del pool de Regulation M-A que cubran los huecos detectados por el synergy-engine. El equipo resultante MUST respetar:
- **Species Clause**: sin Pokémon duplicados
- **Item Clause**: sin ítems duplicados
- **Pool legal**: solo los ~263 Pokémon de Champions Regulation M-A
- El Pokémon ancla ocupa el slot 1

#### Scenario: Generación exitosa
- **WHEN** el usuario introduce "Garchomp" como ancla
- **THEN** el sistema retorna un equipo de 6 con Garchomp en slot 1, ítems distintos para cada miembro, y 5 compañeros que cubren sus debilidades (ice, fairy, dragon) con roles de Doubles complementarios

#### Scenario: Item Clause aplicada
- **WHEN** el ancla lleva Choice Scarf
- **THEN** ninguno de los 5 compañeros generados lleva Choice Scarf

### Requirement: Sugerir distribución de Stat Points (SPs) para cada Pokémon
El sistema SHALL proponer una distribución de SPs para cada Pokémon del equipo respetando:
- Máximo **66 SPs** por Pokémon
- Máximo **32 SPs** en una sola stat
- IVs son 31 fijos en Champions (no configurables)
La distribución se basa en el rol asignado al Pokémon.

#### Scenario: SPs para sweeper físico
- **WHEN** un Pokémon tiene rol "Sweeper físico"
- **THEN** el sistema sugiere 32 SPs en Atk, 32 SPs en Spe y 2 SPs en HP (total 66)

#### Scenario: SPs para wall especial
- **WHEN** un Pokémon tiene rol "Wall especial"
- **THEN** el sistema sugiere 32 SPs en SpDef, 32 SPs en HP y 2 SPs en Def (total 66)

#### Scenario: Distribución mixta
- **WHEN** el Pokémon tiene un rol híbrido (Sweeper físico + Redirect)
- **THEN** el sistema justifica la distribución elegida en lenguaje natural

### Requirement: Generar hasta 3 variantes de equipo
El sistema SHALL ofrecer entre 1 y 3 variantes de equipo distintas usando diferentes combinaciones de Pokémon para cubrir los mismos huecos, dando al usuario opciones de elección.

#### Scenario: Múltiples variantes disponibles
- **WHEN** existen varios candidatos para cubrir el mismo hueco dentro del pool legal de Champions
- **THEN** el sistema genera 3 variantes con diferente selección en al menos 2 slots

#### Scenario: Variantes limitadas
- **WHEN** el pool legal limita los candidatos para cubrir huecos muy específicos
- **THEN** el sistema genera las variantes posibles (mínimo 1) sin repetir equipos idénticos
