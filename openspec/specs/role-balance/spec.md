# role-balance Specification

## Purpose
TBD - created by archiving change fix-role-balance. Update Purpose after archive.
## Requirements
### Requirement: Weather setters receive lead_support as primary role
Pokémon cuya ability primaria (primera en `pokemon.abilities`) sea Snow Warning, Drought, Drizzle, o Sand Stream SHALL recibir `lead_support` como primer elemento de su lista de roles, independientemente de sus stats ofensivos. Roles adicionales derivados de stats se añaden a continuación.

#### Scenario: Ninetales-A con Snow Warning
- **WHEN** `assign_role` evalúa Ninetales-Alola (Snow Warning, SpA 81)
- **THEN** el primer rol es `lead_support`, seguido de `special_sweeper` (SpA > Atk)

#### Scenario: Tyranitar con Sand Stream
- **WHEN** `assign_role` evalúa Tyranitar (Sand Stream, Atk 134)
- **THEN** el primer rol es `lead_support`, seguido de `physical_sweeper`

#### Scenario: Pokémon sin weather ability no se ve afectado
- **WHEN** `assign_role` evalúa un Pokémon con ability no meteorológica (e.g., Intimidate)
- **THEN** el resultado es idéntico al comportamiento anterior (sin `lead_support` insertado por weather)

### Requirement: Beam search penaliza equipos con más de 2 sweepers puros
Un sweeper puro se define como un Pokémon cuya lista de roles consiste únicamente en `physical_sweeper` y/o `special_sweeper`, sin ningún rol de soporte (`lead_support`, `redirect`, `physical_wall`, `special_wall`, `trick_room_setter`). El scoring SHALL aplicar una penalización de `(pure_sweeper_count - 2) * 4.0` cuando `pure_sweeper_count > 2`.

#### Scenario: Equipo con 3 sweepers puros
- **WHEN** `_partial_score` evalúa un equipo parcial de 3 Pokémon todos con roles `["physical_sweeper"]`
- **THEN** el score se reduce en `(3 - 2) * 4.0 = 4.0` puntos respecto a la base

#### Scenario: Equipo con 2 sweepers no penalizado
- **WHEN** `_partial_score` evalúa un equipo con exactamente 2 sweepers puros y otros roles
- **THEN** no se aplica penalización por sweeper excess

#### Scenario: Weather setter no cuenta como sweeper puro
- **WHEN** `_partial_score` evalúa un Pokémon con roles `["lead_support", "special_sweeper"]`
- **THEN** ese Pokémon NO cuenta como sweeper puro para el cálculo de penalización

### Requirement: STAB selection es ability-aware para moves de clima
Cuando un Pokémon tiene una ability primaria que otorga precisión perfecta a un move específico bajo clima (Snow Warning → Blizzard, Drizzle → Thunder), y el move alternativo de mayor BP está en su move pool, ese move SHALL seleccionarse en slot 2 en lugar del move de menor BP.

#### Scenario: Ninetales-A prefiere Blizzard sobre Ice Beam
- **WHEN** `select_moves_for_role` selecciona slot2 para un Pokémon con Snow Warning que conoce ambos Blizzard e Ice Beam
- **THEN** slot2 es `blizzard`

#### Scenario: Pokémon con Snow Warning sin Blizzard en pool usa Ice Beam
- **WHEN** `select_moves_for_role` selecciona slot2 para un Pokémon con Snow Warning que NO conoce Blizzard pero sí Ice Beam
- **THEN** slot2 es `ice-beam` (el override no aplica si el move alternativo no está en el pool)

#### Scenario: Pokémon sin weather ability usa Ice Beam normalmente
- **WHEN** `select_moves_for_role` selecciona slot2 para un Pokémon Ice sin Snow Warning
- **THEN** slot2 es `ice-beam` si está disponible (comportamiento sin cambios)

