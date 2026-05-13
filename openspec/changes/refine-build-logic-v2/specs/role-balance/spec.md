## MODIFIED Requirements

### Requirement: Role thresholds use ±15 gradient bands instead of hard cliffs
`assign_role` (or equivalent stat-based role assignment) SHALL compute each role's weight as a gradient over a 30-point band centered on the role's threshold: `weight = clamp((stat - (threshold - 15)) / 30, 0.0, 1.0)`. Pokémon roles SHALL be represented as weighted (e.g. `role_weights: dict[str, float]`) with weight ≥ 0.5 treated as "has the role" in boolean consumers.

#### Scenario: HP 79 receives partial physical_wall weight just below the midpoint
- **WHEN** `assign_role` evaluates a pokémon with HP 79 (physical_wall threshold 80)
- **THEN** the pokémon's `role_weights["physical_wall"]` is approximately 0.467 (= (79 − 65) / 30)

#### Scenario: HP 65 receives zero physical_wall weight
- **WHEN** `assign_role` evaluates a pokémon with HP 65
- **THEN** the pokémon's `role_weights["physical_wall"]` is 0.0

#### Scenario: HP 95 receives full physical_wall weight
- **WHEN** `assign_role` evaluates a pokémon with HP 95
- **THEN** the pokémon's `role_weights["physical_wall"]` is 1.0

#### Scenario: Boolean role membership preserved for weight ≥ 0.5
- **WHEN** a boolean consumer asks "does this pokémon have role X?"
- **THEN** the answer is `role_weights[X] >= 0.5`

### Requirement: Abilities contribute partial role weight as implicit roles
After stat-based role assignment, `assign_role` SHALL merge ability-driven role weights from `data/ability_implicit_roles.json` into each pokémon's `role_weights`. **[RESEARCH-PENDING Inte for full ability list.]** Required mappings include Flame Body/Static/Effect Spore/Cute Charm/Poison Point → +partial physical_wall; Intimidate → +partial physical_wall; Magic Bounce → +partial lead_support; Prankster → +partial lead_support; Sturdy → +partial physical_wall; Multiscale → +partial physical_wall and special_wall; Regenerator → +partial wall weight.

#### Scenario: Flame Body adds physical_wall weight
- **WHEN** `assign_role` evaluates a pokémon with Flame Body whose stat-based physical_wall weight is 0.4
- **THEN** the merged `role_weights["physical_wall"]` is greater than 0.4 (Flame Body's configured bonus is added)

#### Scenario: Intimidate adds physical_wall weight even on offensive pokémon
- **WHEN** `assign_role` evaluates Landorus-T (Intimidate, HP 89)
- **THEN** the merged `role_weights["physical_wall"]` reflects both stat-based weight and Intimidate's contribution

#### Scenario: Levitate marks ground immunity for coverage
- **WHEN** `assign_role` evaluates a pokémon with Levitate
- **THEN** the pokémon's coverage profile records ground-immunity in addition to stat-based roles

### Requirement: Mega clause enforced as hard constraint in beam search
Beam search expansion SHALL reject any partial team where the count of members holding a mega stone (or having `mega_form` assigned) exceeds 1. The check is structural and runs BEFORE partial scoring.

#### Scenario: Beam rejects 2nd mega holder
- **WHEN** beam search expansion considers a candidate that would be the team's second mega holder
- **THEN** the candidate is pruned and not scored

#### Scenario: No emitted variant has more than one mega
- **WHEN** `/generate` returns variants
- **THEN** every variant has at most one mega-stone holder across its 6 members

### Requirement: Beam search penalizes equipos con más de 2 sweepers puros
Un sweeper puro se define como un Pokémon cuyo `role_weights` tiene `physical_sweeper` o `special_sweeper` ≥ 0.5 y todos los roles de soporte (`lead_support`, `redirect`, `physical_wall`, `special_wall`, `trick_room_setter`) en < 0.5. El scoring SHALL aplicar una penalización de `(pure_sweeper_count - 2) * 4.0` cuando `pure_sweeper_count > 2`. Adicionalmente `score_team` SHALL aceptar `format_mode: str = "bo1"` y `archetype: str = "balance"`; en archetype `hyper_offense` la penalización por sweepers excess SHALL ser reducida a la mitad.

#### Scenario: Equipo con 3 sweepers puros en archetype balance
- **WHEN** `_partial_score` evalúa un equipo parcial de 3 Pokémon todos con `role_weights["physical_sweeper"] >= 0.5` y todos los roles de soporte < 0.5, archetype=balance
- **THEN** el score se reduce en `(3 - 2) * 4.0 = 4.0` puntos

#### Scenario: Equipo con 3 sweepers puros en archetype hyper_offense
- **WHEN** el mismo equipo se evalúa con archetype=hyper_offense
- **THEN** el score se reduce solo en 2.0 (mitad de la penalización)

#### Scenario: Weather setter no cuenta como sweeper puro
- **WHEN** `_partial_score` evalúa un Pokémon con `role_weights["lead_support"]=0.9, role_weights["special_sweeper"]=0.7`
- **THEN** ese Pokémon NO cuenta como sweeper puro

### Requirement: Weather setters receive lead_support as primary role
Pokémon cuya ability primaria sea Snow Warning, Drought, Drizzle, o Sand Stream SHALL recibir `lead_support` con peso ≥ 0.8 en `role_weights`, independientemente de sus stats ofensivos. Otros roles derivados de stats se añaden con sus pesos correspondientes.

#### Scenario: Ninetales-A con Snow Warning
- **WHEN** `assign_role` evalúa Ninetales-Alola (Snow Warning, SpA 81)
- **THEN** `role_weights["lead_support"] >= 0.8` y `role_weights["special_sweeper"]` refleja la gradient de SpA 81

#### Scenario: Tyranitar con Sand Stream
- **WHEN** `assign_role` evalúa Tyranitar (Sand Stream, Atk 134)
- **THEN** `role_weights["lead_support"] >= 0.8` y `role_weights["physical_sweeper"] = 1.0`

#### Scenario: Pokémon sin weather ability no se ve afectado
- **WHEN** `assign_role` evalúa un Pokémon con ability no meteorológica
- **THEN** `role_weights` se calcula solo desde stats + ability_implicit_roles, sin el bonus weather-setter

### Requirement: STAB selection es ability-aware para moves de clima
Cuando un Pokémon tiene una ability primaria que otorga precisión perfecta a un move específico bajo clima (Snow Warning → Blizzard, Drizzle → Thunder), y el move alternativo de mayor BP está en su move pool, ese move SHALL seleccionarse en slot 2 en lugar del move de menor BP.

#### Scenario: Ninetales-A prefiere Blizzard sobre Ice Beam
- **WHEN** `select_moves_for_role` selecciona slot2 para un Pokémon con Snow Warning que conoce ambos Blizzard e Ice Beam
- **THEN** slot2 es `blizzard`

#### Scenario: Pokémon con Snow Warning sin Blizzard en pool usa Ice Beam
- **WHEN** `select_moves_for_role` selecciona slot2 para un Pokémon con Snow Warning que NO conoce Blizzard pero sí Ice Beam
- **THEN** slot2 es `ice-beam`

#### Scenario: Pokémon sin weather ability usa Ice Beam normalmente
- **WHEN** `select_moves_for_role` selecciona slot2 para un Pokémon Ice sin Snow Warning
- **THEN** slot2 es `ice-beam` si está disponible
