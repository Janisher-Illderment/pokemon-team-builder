## ADDED Requirements

### Requirement: Analizar cobertura de tipos del equipo en formato Doubles
El sistema SHALL calcular la cobertura ofensiva y defensiva combinada del equipo orientada a **Doubles** (formato de Pokémon Champions), identificando huecos ofensivos (tipos sin cobertura STAB ni move) y vulnerabilidades defensivas compartidas (≥3 miembros con debilidad ×2 o mayor al mismo tipo).

#### Scenario: Hueco ofensivo detectado
- **WHEN** ningún Pokémon del equipo actual tiene STAB ni move de tipo fairy disponible
- **THEN** el synergy-engine marca "fairy" como hueco ofensivo a cubrir en la selección de compañeros

#### Scenario: Vulnerabilidad defensiva crítica
- **WHEN** 4 de los 6 Pokémon tienen debilidad a electric
- **THEN** el synergy-engine marca "electric" como punto débil crítico y prioriza compañeros con resistencia o inmunidad a electric

### Requirement: Asignar roles de Doubles a cada Pokémon
El sistema SHALL asignar al menos un rol orientado a Doubles a cada Pokémon basándose en sus stats base y moveset disponible:
- **Sweeper físico**: Atk ≥ 100
- **Sweeper especial**: SpAtk ≥ 100
- **Wall físico**: Def ≥ 100 y HP ≥ 80
- **Wall especial**: SpDef ≥ 100 y HP ≥ 80
- **Lead/Soporte**: Speed ≥ 90 y aprende Tailwind, Follow Me, Rage Powder o Fake Out
- **Trick Room setter**: Speed ≤ 60 y aprende Trick Room
- **Redirect**: puede aprender Follow Me o Rage Powder

#### Scenario: Lead con Tailwind
- **WHEN** el Pokémon tiene Speed 110 y aprende Tailwind
- **THEN** el sistema le asigna rol "Lead/Soporte" con subtipo "Tailwind setter"

#### Scenario: Trick Room setter lento
- **WHEN** el Pokémon tiene Speed 30 y aprende Trick Room
- **THEN** el sistema le asigna rol "Trick Room setter"

#### Scenario: Pokémon con stats mixtos
- **WHEN** un Pokémon tiene Atk 110 y SpAtk 95
- **THEN** el sistema le asigna rol "Sweeper físico" (prioriza el stat más alto)

### Requirement: Detectar huecos de roles en el equipo para Doubles
El sistema SHALL identificar qué roles de Doubles están ausentes del equipo actual. Un equipo equilibrado para Champions Doubles MUST tener al menos: un sweeper (físico o especial), un soporte o lead, y cobertura de tipos no redundante entre los 4 seleccionados para batalla.

#### Scenario: Equipo sin soporte
- **WHEN** el equipo de 6 no tiene ningún Pokémon con rol Lead/Soporte ni Redirect
- **THEN** el synergy-engine reporta "soporte" como rol prioritario a añadir

#### Scenario: Equipo con Trick Room viable
- **WHEN** el equipo tiene un setter de Trick Room y al menos 2 Pokémon con Speed ≤ 60
- **THEN** el synergy-engine reporta la estrategia "Trick Room" como viable y cohesionada

### Requirement: Considerar la selección de 4 de 6 en el análisis
El sistema SHALL analizar el equipo considerando que en cada batalla se seleccionan 4 de los 6 Pokémon. El equipo MUST tener suficiente flexibilidad para afrontar múltiples arquetipos enemigos con distintas combinaciones de 4.

#### Scenario: Equipo flexible en selección
- **WHEN** el equipo tiene 3 posibles leads y compañeros que se complementan en pares
- **THEN** el synergy-engine reporta alta flexibilidad de selección (3 o más combinaciones de 4 viables)

#### Scenario: Equipo rígido sin opciones
- **WHEN** solo existe una combinación de 4 viable (los otros 2 slots son prescindibles en cualquier escenario)
- **THEN** el synergy-engine reporta baja flexibilidad y lo penaliza en la puntuación
