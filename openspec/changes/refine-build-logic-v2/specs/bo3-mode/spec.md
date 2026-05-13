## MODIFIED Requirements

### Requirement: VariantOut exposes core_flexibility_score (renamed from lead_flexibility_score)
`VariantOut` in `schemas.py` SHALL include `core_flexibility_score: float` (clamped 0.0–1.0) replacing the previous `lead_flexibility_score` field. This is a **BREAKING** change for API consumers. In Bo1 mode `core_flexibility_score` SHALL be `0.0` (not computed).

#### Scenario: Bo3 response includes core flexibility score
- **WHEN** a Bo3 team is generated
- **THEN** `VariantOut.core_flexibility_score` is between 0.0 and 1.0 inclusive

#### Scenario: Old field name no longer present
- **WHEN** any Bo1 or Bo3 response is inspected
- **THEN** the JSON has no `lead_flexibility_score` key

#### Scenario: Bo1 response has zero core flexibility score
- **WHEN** a Bo1 team is generated
- **THEN** `VariantOut.core_flexibility_score` is `0.0`

### Requirement: Core flexibility score counts viable 4-of-6 combinations
`_core_flexibility_points(members) -> float` in `viability_rater.py` (renamed from `_lead_flexibility_points`) SHALL iterate all C(6,4)=15 combinations of the team, count how many contain at least one pair that is "core-viable" (a pair where at least one member has a speed-control move — Tailwind, Trick Room, Fake Out, Extreme Speed — or a redirect move — Follow Me, Rage Powder), and return `(viable_count / 15) * 25`.

#### Scenario: All combinations core-viable
- **WHEN** every 4-of-6 combination contains a speed-control or redirect member
- **THEN** `core_flexibility_score` is 1.0 and the component contributes 25 pts

#### Scenario: No combination core-viable
- **WHEN** no team member has a speed-control or redirect move
- **THEN** `core_flexibility_score` is 0.0 and the component contributes 0 pts

### Requirement: Bo3 scoring uses core flexibility and core diversity instead of roles
In Bo3 mode `score_team` in `viability_rater.py` SHALL use the formula `coverage(30) + core_flexibility(25) + core_diversity(15) + sp(15) + items(15)`. The `_roles_points` component SHALL NOT be called in Bo3 mode. In Bo1 mode the existing formula is unchanged. Both Bo1 and Bo3 SHALL accept `archetype: str = "balance"` and multiply each component by `archetype_weights[archetype]` for that component.

#### Scenario: Bo3 score excludes roles component
- **WHEN** `score_team` is called with `format_mode="bo3"`
- **THEN** the score is the sum of coverage + core_flexibility + core_diversity + sp + items, each multiplied by its archetype weight

#### Scenario: Bo1 score unchanged shape
- **WHEN** `score_team` is called with `format_mode="bo1"`
- **THEN** the score uses the legacy 5-component formula, each multiplied by its archetype weight

### Requirement: UI strings updated from Lead to Core / Núcleo
The web UI (`web/index.html`, `web/app.js`) SHALL render "Core" (English) or "Núcleo" (Spanish) wherever it previously rendered "Lead". Tooltips, badges, and section headings related to the flexibility score SHALL use the new term.

#### Scenario: UI shows "Núcleo" badge in Spanish
- **WHEN** the UI is displayed in Spanish and a Bo3 variant has `core_flexibility_score > 0`
- **THEN** the variant card shows a badge labeled "Flexibilidad de núcleo" or equivalent — not "Lead"

#### Scenario: No "Lead" string remains in UI source
- **WHEN** `web/index.html` and `web/app.js` are inspected
- **THEN** no string literal "Lead" remains in user-facing copy (matched-case search)

### Requirement: Bo3 move selection deprioritizes cheese moves subject to archetype cheese_allowance
When `format_mode="bo3"`, `select_moves_for_role` in `replica_exporter.py` SHALL skip any move in `_BO3_CHEESE_MOVES = {"destiny-bond", "mirror-coat", "counter", "memento", "perish-song"}` when selecting slot 4 — UNLESS `archetype_weights[archetype].cheese_allowance >= 1.0` (e.g. `perish_trap`).

#### Scenario: Destiny Bond skipped in Bo3 balance
- **WHEN** archetype=`balance`, `format_mode=bo3`, slot-4 candidate is `destiny-bond`
- **THEN** `destiny-bond` is not assigned

#### Scenario: Perish Song allowed in Bo3 perish_trap
- **WHEN** archetype=`perish_trap`, `format_mode=bo3`, slot-4 candidate is `perish-song`
- **THEN** `perish-song` IS assigned (cheese_allowance permits it)

#### Scenario: Cheese moves allowed in Bo1 default
- **WHEN** `format_mode="bo1"` (default)
- **THEN** cheese moves are selected normally with no restriction
