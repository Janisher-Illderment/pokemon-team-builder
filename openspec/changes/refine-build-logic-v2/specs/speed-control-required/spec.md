## ADDED Requirements

### Requirement: Speed control mandatory or penalised
Every generated team (except `stall` archetype) SHALL contain at least one speed-control mechanism. Speed-control mechanisms include the moves Trick Room, Tailwind, Icy Wind, Electroweb, Thunder Wave, Glare, Nuzzle, Stun Spore, Sticky Web, Fake Out, and Quick Guard; AND the abilities Static and Cute Charm (partial credit). If no mechanism is present (and archetype is not `stall`), `score_team` SHALL apply a **−15 point** penalty and `VariantOut.requires_speed_control` SHALL be `true`.

#### Scenario: Team with Tailwind passes check
- **WHEN** any member's assigned moveset contains Tailwind
- **THEN** `_speed_control_penalty` returns 0 and `VariantOut.requires_speed_control` is `false`

#### Scenario: Team with Trick Room passes check
- **WHEN** any member's assigned moveset contains Trick Room
- **THEN** `_speed_control_penalty` returns 0

#### Scenario: Team without speed control penalised
- **WHEN** no member has a speed-control move and no member has a partial-credit ability, and archetype is `balance`
- **THEN** the team score is reduced by 15 and `VariantOut.requires_speed_control` is `true`

#### Scenario: stall archetype exempt
- **WHEN** archetype is `stall` and the team has no speed-control move
- **THEN** no penalty is applied (stall teams rely on residual damage, not speed manipulation)

### Requirement: Paralysis-inducing abilities contribute partial credit
Abilities that inflict paralysis on contact (Static, Cute Charm via attraction-as-disruption) SHALL contribute partial credit (0.5 mechanism count). A team with two such ability holders and no speed-control moves SHALL be treated as having ≥1 mechanism (total 1.0).

#### Scenario: Two Static members count as one mechanism
- **WHEN** a team has two members with Static and no speed-control moves
- **THEN** no penalty is applied (combined partial credit = 1.0)

#### Scenario: One Static member alone insufficient
- **WHEN** a team has one Static member and no speed-control moves
- **THEN** the −15 penalty applies (combined partial credit = 0.5 < 1.0)

### Requirement: requires_speed_control flag exposed on VariantOut
`VariantOut` SHALL include `requires_speed_control: bool` with `false` by default. The UI SHALL render a warning banner on variants where this flag is `true`.

#### Scenario: Flag visible in API response
- **WHEN** any team is generated
- **THEN** `VariantOut.requires_speed_control` is present in the JSON response

#### Scenario: UI surfaces the warning
- **WHEN** a variant has `requires_speed_control=true`
- **THEN** the variant card renders a warning indicator with Spanish text ("Falta control de velocidad" or similar)
