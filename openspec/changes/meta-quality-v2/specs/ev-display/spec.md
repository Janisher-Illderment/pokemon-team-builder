## ADDED Requirements

### Requirement: API exposes SP distribution per team member
`MemberOut` in `schemas.py` SHALL include a `sp_distribution` field of type `dict[str, int]` containing only non-zero stat keys (`hp`, `atk`, `def`, `spa`, `spd`, `spe`). The API router SHALL populate it from `TeamMember.sp_distribution`.

#### Scenario: Member with full SP allocation
- **WHEN** `/generate` returns a team member with `sp_distribution = {hp:2, atk:32, spe:32}`
- **THEN** `MemberOut.sp_distribution` equals `{"hp": 2, "atk": 32, "spe": 32}` (zero-value stats omitted)

#### Scenario: Member with all-zero distribution
- **WHEN** a team member has no SP allocated
- **THEN** `MemberOut.sp_distribution` is an empty dict `{}`

### Requirement: API exposes an EV rationale note per team member
`MemberOut` SHALL include an `ev_note` field of type `str`. The API router SHALL generate this note in Spanish by identifying the two largest SP allocations and explaining them in plain language referencing the pokémon's role.

#### Scenario: Standard sweeper note
- **WHEN** a physical sweeper has `sp_distribution = {atk: 32, spe: 32, hp: 2}`
- **THEN** `ev_note` contains a Spanish sentence referencing max attack and max speed (e.g. "32 Atk para daño máximo, 32 Spe para velocidad máxima")

#### Scenario: Wall note
- **WHEN** a physical wall has `sp_distribution = {hp: 32, def: 32, spd: 2}`
- **THEN** `ev_note` references bulk and defense stats

#### Scenario: Empty distribution
- **WHEN** `sp_distribution` is all zeros
- **THEN** `ev_note` is an empty string `""`

### Requirement: Frontend renders SP distribution as a stat grid
The web frontend SHALL display each team member's SP distribution as a compact stat grid (6 stats: HP / Atk / Def / SpA / SpD / Spe) with numeric values, shown below the moves list. Stats with value 0 SHALL be shown grayed out. The EV note SHALL appear as a small italic line below the grid.

#### Scenario: Grid shown for each member
- **WHEN** the generate response includes `sp_distribution` and `ev_note` for each member
- **THEN** the frontend renders a stat grid and note beneath each member's move list

#### Scenario: Zero stats grayed out
- **WHEN** a stat in `sp_distribution` is 0 (absent from the dict)
- **THEN** that stat cell renders with a muted/gray style to indicate no investment
