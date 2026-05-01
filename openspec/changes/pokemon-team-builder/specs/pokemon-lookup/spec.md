## ADDED Requirements

### Requirement: Consultar datos de un Pokémon por nombre o número
El sistema SHALL consultar PokéAPI para obtener tipo(s), stats base (HP, Atk, Def, SpAtk, SpDef, Spe), lista de debilidades calculadas y moveset del Pokémon indicado. El nombre es case-insensitive y acepta el número nacional de la Pokédex.

#### Scenario: Búsqueda por nombre válido
- **WHEN** el usuario introduce "charizard"
- **THEN** el sistema retorna tipo [fire, flying], stats base completos, lista de debilidades (water, rock, electric) y moveset disponible

#### Scenario: Búsqueda por número válido
- **WHEN** el usuario introduce "6"
- **THEN** el sistema retorna los mismos datos que al buscar "charizard"

#### Scenario: Pokémon no encontrado
- **WHEN** el usuario introduce un nombre o número que no existe en PokéAPI
- **THEN** el sistema retorna un error claro indicando que el Pokémon no fue encontrado, sin fallar silenciosamente

#### Scenario: PokéAPI no disponible
- **WHEN** PokéAPI no responde en un plazo de 5 segundos
- **THEN** el sistema retorna un error de conectividad con mensaje legible para el usuario

### Requirement: Calcular debilidades y resistencias del Pokémon
El sistema SHALL calcular el multiplicador de daño recibido para cada tipo de ataque basándose en los tipos del Pokémon, considerando inmunidades y dobles resistencias/debilidades para Pokémon de tipo dual.

#### Scenario: Cálculo para tipo dual con inmunidad
- **WHEN** el Pokémon es de tipo [ghost, normal]
- **THEN** el sistema calcula inmunidad a fighting y normal, y las demás interacciones correctamente

#### Scenario: Doble debilidad
- **WHEN** el Pokémon es de tipo [rock, flying] como Aerodactyl
- **THEN** el sistema marca water, electric, ice, rock y steel con multiplicador ×2 o ×4 según corresponda
