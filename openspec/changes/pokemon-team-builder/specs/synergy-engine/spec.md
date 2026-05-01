## ADDED Requirements

### Requirement: Analizar cobertura de tipos del equipo
El sistema SHALL calcular la cobertura ofensiva y defensiva combinada del equipo, identificando qué tipos de ataque no están cubiertos ofensivamente y qué tipos de ataque dejan al equipo vulnerable defensivamente (al menos 3 miembros con debilidad ×2 o mayor).

#### Scenario: Cobertura ofensiva incompleta
- **WHEN** el equipo actual no tiene ningún Pokémon con STAB o move de tipo rock
- **THEN** el synergy-engine marca "rock" como hueco ofensivo a cubrir

#### Scenario: Vulnerabilidad defensiva detectada
- **WHEN** 4 de los 6 Pokémon del equipo tienen debilidad a electric
- **THEN** el synergy-engine marca "electric" como punto débil crítico del equipo

### Requirement: Asignar roles de equipo a cada Pokémon
El sistema SHALL asignar al menos un rol a cada Pokémon basándose en sus stats base: sweeper físico (Atk ≥ 100), sweeper especial (SpAtk ≥ 100), wall físico (Def ≥ 100 y HP ≥ 80), wall especial (SpDef ≥ 100 y HP ≥ 80), soporte (Speed ≥ 90 y ningún stat ofensivo ≥ 100), hazard setter (capacidad de aprender Stealth Rock o Spikes).

#### Scenario: Pokémon con stats mixtos
- **WHEN** un Pokémon tiene Atk 110 y SpAtk 95
- **THEN** el sistema le asigna rol "sweeper físico" y no "sweeper especial"

#### Scenario: Pokémon de soporte
- **WHEN** el Pokémon tiene Speed 110, Atk 60 y SpAtk 70
- **THEN** el sistema le asigna rol "soporte"

### Requirement: Detectar huecos de roles en el equipo
El sistema SHALL identificar qué roles están ausentes del equipo actual y priorizarlos para la selección de los slots restantes. Un equipo equilibrado MUST tener al menos: un sweeper, un wall y un soporte o hazard setter.

#### Scenario: Equipo sin wall
- **WHEN** el equipo de 6 no tiene ningún Pokémon con rol wall físico o especial
- **THEN** el synergy-engine retorna "wall" como rol prioritario a añadir

#### Scenario: Equipo equilibrado
- **WHEN** el equipo tiene al menos un sweeper, un wall y un soporte
- **THEN** el synergy-engine reporta el equipo como equilibrado en roles
