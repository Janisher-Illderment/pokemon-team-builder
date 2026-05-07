## MODIFIED Requirements

### Requirement: Beam search penalizes equipos con más de 2 sweepers puros
Un sweeper puro se define como un Pokémon cuya lista de roles consiste únicamente en `physical_sweeper` y/o `special_sweeper`, sin ningún rol de soporte (`lead_support`, `redirect`, `physical_wall`, `special_wall`, `trick_room_setter`). El scoring SHALL aplicar una penalización de `(pure_sweeper_count - 2) * 4.0` cuando `pure_sweeper_count > 2`. Adicionalmente, `_heuristic_filter` SHALL añadir un `meta_affinity_bonus` de `+3.0` al score de cualquier candidato que aparezca en la lista de teammates frecuentes del anchor según `MetaService` (top 6). Si los datos meta no están disponibles, el bonus no se aplica y los scores quedan sin cambios.

#### Scenario: Equipo con 3 sweepers puros
- **WHEN** `_partial_score` evalúa un equipo parcial de 3 Pokémon todos con roles `["physical_sweeper"]`
- **THEN** el score se reduce en `(3 - 2) * 4.0 = 4.0` puntos respecto a la base

#### Scenario: Equipo con 2 sweepers no penalizado
- **WHEN** `_partial_score` evalúa un equipo con exactamente 2 sweepers puros y otros roles
- **THEN** no se aplica penalización por sweeper excess

#### Scenario: Weather setter no cuenta como sweeper puro
- **WHEN** `_partial_score` evalúa un Pokémon con roles `["lead_support", "special_sweeper"]`
- **THEN** ese Pokémon NO cuenta como sweeper puro para el cálculo de penalización

#### Scenario: Candidate is a meta teammate
- **WHEN** un candidato aparece en la lista top-6 de teammates del anchor según MetaService
- **THEN** su heuristic score recibe un bonus de +3.0 antes del ranking

#### Scenario: Meta data unavailable for anchor
- **WHEN** `MetaService.get(anchor_name)` devuelve `None`
- **THEN** `_heuristic_filter` funciona sin cambios y no aplica ningún bonus
