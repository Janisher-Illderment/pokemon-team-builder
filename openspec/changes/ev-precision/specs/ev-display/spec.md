## MODIFIED Requirements

### Requirement: API exposes an EV rationale note per team member
`MemberOut` SHALL include an `ev_note` field of type `str`. The API router SHALL generate this note by calling `ev_explainer.explain(member, speed_db, meta_service)` — producing a specific Spanish sentence referencing real speed tier comparisons or named damage calculations rather than a generic role description.

#### Scenario: Speed-invested member note is specific
- **WHEN** a team member has spe SPs and the speed tier DB is loaded
- **THEN** `ev_note` names at least one pokémon the member outspeed and one it does not

#### Scenario: Bulk-invested member note names a specific attack
- **WHEN** a team member has hp/def/spd SPs and meta or fallback data is available
- **THEN** `ev_note` names a specific attack and attacker, not a generic phrase like "para bulk máximo"

#### Scenario: Empty distribution
- **WHEN** `sp_distribution` is all zeros
- **THEN** `ev_note` is an empty string `""`
