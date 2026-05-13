## ADDED Requirements

### Requirement: GenerateRequest accepts an archetype parameter
`GenerateRequest` in `schemas.py` SHALL accept an `archetype` field of type `Literal["hyper_offense", "hard_trick_room", "bulky_offense", "weather_based", "stall", "balance", "perish_trap"]` with default `"balance"`. The value SHALL be propagated through `generate_team()`, `build_core_duo()`, `cover_shared_weakness()`, `_partial_score()`, and `score_team()` so every scoring decision honors archetype weights.

#### Scenario: Default archetype is balance
- **WHEN** a client calls `/generate` without an `archetype` field
- **THEN** the request is processed with `archetype="balance"` and balance weights apply

#### Scenario: Invalid archetype rejected
- **WHEN** a client calls `/generate` with `archetype="foobar"`
- **THEN** the request is rejected with HTTP 422 and the error message lists the seven valid values

### Requirement: Archetype weights loaded from versioned JSON
On startup the system SHALL load `data/archetype_weights.json` into an `ArchetypeWeights` dataclass. The file SHALL contain a weight matrix per archetype with at minimum the keys `coverage`, `roles`, `sp`, `items`, `speed`, `bulk`, `cheese_allowance`, `weather_synergy`. Weights SHALL be floats in `[0.0, 2.0]` (relative multipliers vs balance baseline = 1.0).

#### Scenario: archetype_weights.json validated at startup
- **WHEN** the application boots
- **THEN** missing archetype keys or weight values outside `[0.0, 2.0]` raise a clear startup error referencing the file path and key

#### Scenario: Weights file echoes regulation and data_version
- **WHEN** `archetype_weights.json` is loaded
- **THEN** the `regulation` and `data_version` headers are recorded in `VariantOut.meta_versions.archetype_weights`

### Requirement: Cheese allowance gates cheese-move selection
`select_moves_for_role` SHALL only assign moves from the cheese set (`destiny-bond`, `mirror-coat`, `counter`, `memento`, `perish-song`) when `archetype_weights[archetype].cheese_allowance >= 1.0`. `perish_trap` SHALL have `cheese_allowance = 1.0` so Perish Song is assignable; `balance`, `bulky_offense`, `stall` SHALL have `cheese_allowance < 1.0` so cheese moves are skipped.

#### Scenario: Perish Song allowed in perish_trap
- **WHEN** archetype is `perish_trap` and a member's slot-4 candidate is Perish Song
- **THEN** Perish Song is assigned

#### Scenario: Destiny Bond skipped in balance
- **WHEN** archetype is `balance` and a member's slot-4 candidate is Destiny Bond
- **THEN** Destiny Bond is skipped and the next candidate is used

### Requirement: Archetype echoed on VariantOut
`VariantOut` SHALL include `archetype: str` echoing the request's archetype value. The UI uses this to render an archetype badge per variant.

#### Scenario: archetype field present on every variant
- **WHEN** any team is generated
- **THEN** each `VariantOut` in the response has `archetype` set to the request's archetype string

### Requirement: Archetype affects core-duo and slot-3 selection
`build_core_duo` and `cover_shared_weakness` SHALL apply archetype weights when scoring candidates. Specifically: in `hard_trick_room` the partner score adds bonus weight for slow stats and Trick Room setters; in `weather_based` the partner score adds bonus weight for weather setters matching the anchor's ability needs; in `hyper_offense` the role-complement penalty is suppressed and offensive stats are weighted more heavily.

#### Scenario: hard_trick_room favours Trick Room setters
- **WHEN** `build_core_duo` runs with anchor=slow physical attacker and archetype=`hard_trick_room`
- **THEN** the partner is a known Trick Room setter (e.g. Hatterene, Porygon2, Indeedee-F) over alternatives that don't set Trick Room

#### Scenario: weather_based favours weather setters when anchor has weather ability
- **WHEN** anchor has Swift Swim and archetype=`weather_based`
- **THEN** the partner is a Drizzle / Rain Dance setter (e.g. Pelipper) over non-setter alternatives
