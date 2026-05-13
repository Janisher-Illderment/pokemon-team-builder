## MODIFIED Requirements

### Requirement: Coverage scoring is STAB-based, not typing-based
The coverage component (`_coverage_points` in `synergy_engine.py` or equivalent) SHALL compute "type X covered" as: at least one team member's assigned moveset (slots 1–4) contains a move of type X where the move's type is also one of the member's types (i.e. STAB). Typing-only coverage (member has type X but no move of type X) SHALL NO LONGER count as coverage.

#### Scenario: Steelix without Iron Head does not cover Steel
- **WHEN** the team contains Steelix (Steel/Ground) whose assigned moveset is `[earthquake, stealth-rock, roar, dragon-tail]`
- **THEN** Steel is NOT counted as covered by this member

#### Scenario: Steelix with Iron Head covers Steel
- **WHEN** the team contains Steelix whose assigned moveset includes `iron-head`
- **THEN** Steel IS counted as covered

#### Scenario: Non-STAB type move does not count
- **WHEN** a Water-type member has Ice Beam (Ice move, non-STAB) and no other Ice-type member is on the team
- **THEN** Ice is NOT counted as covered (Ice Beam is coverage, not STAB)

### Requirement: STAB-presence invariant enforced during move selection
`select_moves_for_role` SHALL guarantee that every team member with type X has at least one STAB move of type X in slots 1–4. If a member has two STAB types AND multiple STAB moves available across both types, exactly one STAB slot MAY be repurposed for coverage; if only one STAB type or only one STAB move is available, that STAB move SHALL occupy at least one slot.

#### Scenario: Mono-type member always has STAB
- **WHEN** a Fire-type member's available move pool contains at least one Fire-type move
- **THEN** the assigned moveset contains at least one Fire-type move

#### Scenario: Dual-type member with two STAB types may sacrifice one
- **WHEN** a Water/Ice member has both Hydro Pump and Ice Beam available
- **THEN** the assigned moveset MAY contain only one of them, allowing the other slot for coverage; but at least one STAB MUST remain

#### Scenario: Dual-type member with only one STAB type keeps it
- **WHEN** a Water/Ice member's pool contains Hydro Pump (Water STAB) but no Ice STAB moves
- **THEN** Hydro Pump SHALL be in the assigned moveset (it's the only STAB available)

### Requirement: Coverage scoring weighted by archetype
The final coverage component SHALL be multiplied by `archetype_weights[archetype].coverage` before contributing to the team score. `hyper_offense` SHALL have `coverage >= 1.2`; `stall` SHALL have `coverage <= 0.8` (stall cares less about offensive coverage breadth).

#### Scenario: hyper_offense amplifies coverage
- **WHEN** a team's raw `_coverage_points` is 28 and archetype is `hyper_offense` with coverage weight 1.2
- **THEN** the coverage contribution to the team score is 33.6

#### Scenario: stall dampens coverage
- **WHEN** a team's raw `_coverage_points` is 28 and archetype is `stall` with coverage weight 0.8
- **THEN** the coverage contribution to the team score is 22.4

### Requirement: Ground-immunity from Levitate counted in coverage
When evaluating defensive coverage (resistance/immunity to incoming types), a member with the Levitate ability SHALL be treated as immune to Ground regardless of typing. The coverage calculator SHALL consider this when scoring how the team handles Ground threats.

#### Scenario: Levitate member counted as ground-immune
- **WHEN** the team contains a member with Levitate
- **THEN** the team's Ground-threat handling score reflects this member as Ground-immune even if the member's typing alone is Ground-weak

#### Scenario: Iron Ball or other items that nullify Levitate not factored in
- **WHEN** a Levitate member holds Iron Ball
- **THEN** the immunity calculation still treats them as Ground-immune for coverage (item-induced ability suppression is a future enhancement, out of scope)
