## ADDED Requirements

### Requirement: GenerateRequest accepts a format parameter
`GenerateRequest` in `schemas.py` SHALL accept a `format` field of type `Literal["bo1", "bo3"]` with default `"bo1"`. The value SHALL be propagated through `generate_team()` and `score_team()` without altering the Bo1 code path.

#### Scenario: Default is Bo1
- **WHEN** a client calls `/generate` without a `format` field
- **THEN** the request is processed with `format="bo1"` and existing scoring applies

#### Scenario: Bo3 format accepted
- **WHEN** a client calls `/generate` with `format="bo3"`
- **THEN** generation and scoring use Bo3 logic and the response includes `format_mode="bo3"`

### Requirement: VariantOut exposes format_mode and lead_flexibility_score
`VariantOut` in `schemas.py` SHALL include `format_mode: str` and `lead_flexibility_score: float` (clamped 0.0–1.0). In Bo1 mode `lead_flexibility_score` SHALL be `0.0` (not computed).

#### Scenario: Bo3 response includes flexibility score
- **WHEN** a Bo3 team is generated
- **THEN** `VariantOut.lead_flexibility_score` is between 0.0 and 1.0 inclusive

#### Scenario: Bo1 response has zero flexibility score
- **WHEN** a Bo1 team is generated
- **THEN** `VariantOut.lead_flexibility_score` is `0.0`

### Requirement: Bo3 scoring uses lead flexibility and core diversity instead of roles
In Bo3 mode `score_team` in `viability_rater.py` SHALL use the formula `coverage(30) + lead_flexibility(25) + core_diversity(15) + sp(15) + items(15)`. The `_roles_points` component SHALL NOT be called in Bo3 mode. In Bo1 mode the existing formula is unchanged.

#### Scenario: Bo3 score excludes roles component
- **WHEN** `score_team` is called with `format_mode="bo3"`
- **THEN** the score is the sum of coverage + lead_flexibility + core_diversity + sp + items (max 100)

#### Scenario: Bo1 score unchanged
- **WHEN** `score_team` is called with `format_mode="bo1"` or no mode
- **THEN** the score is computed with the existing formula

### Requirement: Lead flexibility score counts viable 4-of-6 combinations
`_lead_flexibility_points(members) -> float` in `viability_rater.py` SHALL iterate all C(6,4)=15 combinations of the team, count how many contain at least one pair that is "lead-viable" (a pair where at least one member has a speed-control move — Tailwind, Trick Room, Fake Out, Extreme Speed — or a redirect move — Follow Me, Rage Powder), and return `(viable_count / 15) * 25`.

#### Scenario: All combinations lead-viable
- **WHEN** every 4-of-6 combination contains a speed-control or redirect member
- **THEN** `lead_flexibility_score` is 1.0 and the component contributes 25 pts

#### Scenario: No combination lead-viable
- **WHEN** no team member has a speed-control or redirect move
- **THEN** `lead_flexibility_score` is 0.0 and the component contributes 0 pts

### Requirement: Core diversity counts distinct sweeper–support pairs
`_core_diversity_points(members) -> float` in `viability_rater.py` SHALL count the number of distinct 2-pokémon pairs where one member's role is in `{physical_sweeper, special_sweeper}` and the other's role is in `{lead_support, redirect, trick_room_setter}`. Return `min(core_count / 3, 1.0) * 15`.

#### Scenario: Three or more cores
- **WHEN** a team has at least 3 distinct sweeper–support pairs
- **THEN** core diversity contributes 15 pts

#### Scenario: One core
- **WHEN** a team has exactly 1 sweeper–support pair
- **THEN** core diversity contributes 5 pts (1/3 × 15)

### Requirement: Bo3 move selection deprioritizes cheese moves
When `format_mode="bo3"`, `select_moves_for_role` in `replica_exporter.py` SHALL skip any move in `_BO3_CHEESE_MOVES = {"destiny-bond", "mirror-coat", "counter", "memento", "perish-song"}` when selecting slot 4, replacing it with the next available role move or utility fallback.

#### Scenario: Destiny Bond skipped in Bo3
- **WHEN** a pokémon's slot-4 candidate is `destiny-bond` and `format_mode="bo3"`
- **THEN** `destiny-bond` is not assigned and the next candidate is used instead

#### Scenario: Cheese moves allowed in Bo1
- **WHEN** `format_mode="bo1"` (default)
- **THEN** cheese moves are selected normally with no restriction
