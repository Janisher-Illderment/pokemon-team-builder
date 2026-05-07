## MODIFIED Requirements

### Requirement: Beam search penalizes equipos con más de 2 sweepers puros
Un sweeper puro se define como un Pokémon cuya lista de roles consiste únicamente en `physical_sweeper` y/o `special_sweeper`, sin ningún rol de soporte (`lead_support`, `redirect`, `physical_wall`, `special_wall`, `trick_room_setter`). El scoring SHALL aplicar una penalización de `(pure_sweeper_count - 2) * 4.0` cuando `pure_sweeper_count > 2`. Adicionalmente, `score_team` SHALL aceptar un parámetro opcional `format_mode: str = "bo1"` y en Bo3 SHALL sustituir el componente `_roles_points` por `_lead_flexibility_points + _core_diversity_points` manteniendo el total máximo en 100 pts.

#### Scenario: Equipo con 3 sweepers puros
- **WHEN** `_partial_score` evalúa un equipo parcial de 3 Pokémon todos con roles `["physical_sweeper"]`
- **THEN** el score se reduce en `(3 - 2) * 4.0 = 4.0` puntos respecto a la base

#### Scenario: Equipo con 2 sweepers no penalizado
- **WHEN** `_partial_score` evalúa un equipo con exactamente 2 sweepers puros y otros roles
- **THEN** no se aplica penalización por sweeper excess

#### Scenario: Weather setter no cuenta como sweeper puro
- **WHEN** `_partial_score` evalúa un Pokémon con roles `["lead_support", "special_sweeper"]`
- **THEN** ese Pokémon NO cuenta como sweeper puro para el cálculo de penalización

#### Scenario: Bo3 mode uses lead flexibility scoring
- **WHEN** `score_team` se llama con `format_mode="bo3"`
- **THEN** el componente de roles es reemplazado por lead_flexibility + core_diversity y el total máximo sigue siendo 100

#### Scenario: Bo1 mode unchanged
- **WHEN** `score_team` se llama con `format_mode="bo1"` o sin parámetro
- **THEN** el scoring es idéntico al comportamiento anterior
