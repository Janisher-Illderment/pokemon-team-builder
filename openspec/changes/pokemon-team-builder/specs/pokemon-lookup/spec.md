## ADDED Requirements

### Requirement: Consultar datos de un Pokémon por nombre o número y verificar legalidad en Champions
El sistema SHALL consultar PokéAPI para obtener tipo(s), stats base (HP, Atk, Def, SpAtk, SpDef, Spe) y moveset del Pokémon indicado, y verificar que esté en el pool legal de Champions Regulation M-A (~263 Pokémon). El nombre es case-insensitive y acepta el número nacional de la Pokédex.

#### Scenario: Búsqueda de Pokémon legal en Champions
- **WHEN** el usuario introduce "garchomp"
- **THEN** el sistema retorna tipo [dragon, ground], stats base completos y moveset; y confirma que Garchomp es legal en Regulation M-A

#### Scenario: Pokémon no incluido en el pool de Champions
- **WHEN** el usuario introduce "mewtwo" (legendario, no existe en Champions)
- **THEN** el sistema retorna un error claro indicando que ese Pokémon no está disponible en Pokémon Champions y no puede usarse como ancla

#### Scenario: Pokémon no encontrado en PokéAPI
- **WHEN** el usuario introduce un nombre que no existe
- **THEN** el sistema retorna un error indicando que el Pokémon no fue encontrado, sin fallar silenciosamente

#### Scenario: PokéAPI no disponible
- **WHEN** PokéAPI no responde en un plazo de 5 segundos
- **THEN** el sistema retorna un error de conectividad con mensaje legible para el usuario

### Requirement: Calcular debilidades y resistencias del Pokémon
El sistema SHALL calcular el multiplicador de daño recibido para cada tipo de ataque basándose en los tipos del Pokémon, considerando inmunidades y dobles resistencias/debilidades para Pokémon de tipo dual.

#### Scenario: Doble debilidad por tipo dual
- **WHEN** el Pokémon es de tipo [rock, flying] como Aerodactyl
- **THEN** el sistema marca water, electric, ice, rock y steel con multiplicador ×2 o ×4 según corresponda

#### Scenario: Inmunidad por tipo dual
- **WHEN** el Pokémon es de tipo [ghost, normal]
- **THEN** el sistema calcula inmunidad a fighting y normal correctamente

### Requirement: Mantener y consultar la lista legal de Champions (Regulation M-A)
El sistema SHALL incluir un fichero local con los ~263 Pokémon legales en Champions Regulation M-A. Este fichero es la fuente autoritativa para determinar legalidad; PokéAPI es la fuente de stats.

#### Scenario: Pokémon Paradox baneado
- **WHEN** el usuario introduce "iron-valiant" (Paradox Pokémon)
- **THEN** el sistema lo rechaza indicando que no está en el pool legal de Champions

#### Scenario: Consulta a la lista legal
- **WHEN** el sistema verifica cualquier Pokémon
- **THEN** lo compara contra la lista local sin depender de conexión adicional a internet para la verificación de legalidad
