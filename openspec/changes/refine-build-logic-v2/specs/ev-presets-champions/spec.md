## ADDED Requirements

### Requirement: SP allocation uses Champions 66-SP cap
The SP optimiser SHALL allocate exactly **66 Stat Points** total per pokémon, with a hard cap of **32 SP per individual stat** (Inte verified: Victory Road regulation M-A + Centro Leaks + Switchblade SP guide, HIGH confidence). The 1 SP = 8 legacy EV equivalence is documented for migration only; new code SHALL operate exclusively in SP units. IVs SHALL remain locked at 31. The legacy 508-EV math and "504 vs 508" penalty SHALL be removed from the codebase.

#### Scenario: Total SPs equal 66
- **WHEN** the SP optimiser builds any preset for any pokémon
- **THEN** the sum of allocated SPs across all six stats equals 66

#### Scenario: No stat exceeds the per-stat cap
- **WHEN** any preset is generated
- **THEN** no single stat receives more SPs than the configured per-stat cap

#### Scenario: Legacy 508 references removed
- **WHEN** the codebase is grepped for the literals `508` or `504` after this change
- **THEN** no live SP/EV-math references remain (test-fixture historical data is excluded)

### Requirement: Multiple SP presets per pokémon
`services/sp_preset_builder.build_presets(member, item, nature, threats_to_OHKO, threats_to_survive) -> dict[str, SpRead]` SHALL return at least two presets: `offensive_preset` optimised to OHKO/2HKO meta pokémon weak to this member, and `defensive_preset` optimised to survive top damaging moves from meta pokémon strong vs this member. Each preset SHALL satisfy the 66-SP cap independently.

#### Scenario: Two presets returned per member
- **WHEN** `build_presets` is called for any member
- **THEN** the returned dict contains both `offensive_preset` and `defensive_preset` keys, each summing to 66 SPs

#### Scenario: Variant exposes both presets
- **WHEN** any team is generated
- **THEN** each `VariantOut` member entry includes `sp_presets: {offensive: SpRead, defensive: SpRead}`

#### Scenario: Default export preset is offensive
- **WHEN** `to_pokepaste` is called without an explicit preset selection
- **THEN** the exported SPs come from `offensive_preset`

### Requirement: Preset optimisation accounts for held-item stat modifiers
The SP optimiser SHALL incorporate the equipped item's effective stat modifier when allocating SPs. Specifically: Choice Band → physical_attack treated as ×1.5 (optimiser invests less in Attack, more in Speed/bulk); Choice Specs → special_attack ×1.5; Choice Scarf → speed ×1.5; Assault Vest → special_defense ×1.5; Eviolite (NFE only) → defense and special_defense ×1.5.

#### Scenario: Choice Band attacker invests in speed over attack
- **WHEN** an `offensive_preset` is built for a member holding Choice Band
- **THEN** the SPs allocated to Speed exceed those allocated to Attack (because Choice Band already inflates Attack)

#### Scenario: Eviolite NFE invests in offense
- **WHEN** a `defensive_preset` is built for an NFE pokémon holding Eviolite
- **THEN** the SPs allocated to Defense + SpDef are reduced (Eviolite already inflates them) and offensive stats receive more

#### Scenario: Assault Vest defender invests in physical defense
- **WHEN** a `defensive_preset` is built for a member holding Assault Vest
- **THEN** the SPs allocated to Defense exceed those allocated to Special Defense

### Requirement: Nature multiplier and nature-jump detection via programmatic stat-calc
The optimiser SHALL compute final-stat values using the canonical Pokémon stat formula `floor((floor((2*base + IV + floor(EV/4)) * level / 100) + 5) * nature_mult)` where `nature_mult ∈ {0.9, 1.0, 1.1}` and `EV = SP * 8`. **Nature-jump thresholds SHALL be detected programmatically per (pokémon, stat, nature) at allocation time** — no precomputed `nature_jumps.json` table (Inte confirmed: thresholds are pokémon-specific due to base-stat × IV × nature interaction; no public table exists). The optimiser SHALL prefer SP allocations that trigger a +2 final-stat jump over the next-lower SP value, breaking ties toward the lower SP investment.

#### Scenario: Optimiser detects and hits nature jump at runtime
- **WHEN** allocating SPs for a stat where the canonical stat formula yields a +2 final-stat jump between SP=N and SP=N+1 (for the given pokémon base stat, IV=31, level=50, nature multiplier)
- **THEN** the optimiser allocates exactly SP=N+1 rather than SP=N+2 (the jump value is preferred over over-investment, breaking ties toward lower SP)

#### Scenario: Nature with negative modifier deprioritised for that stat
- **WHEN** a pokémon has a -SpA nature and `offensive_preset` is being built around physical attacks
- **THEN** zero (or near-zero) SPs go into Special Attack

### Requirement: SP-presets versioning
The SP mechanics module SHALL expose `SP_MECHANICS_VERSION` (int constant) and `REGULATION` (string, e.g. "M-A"). `VariantOut.meta_versions.sp_mechanics` SHALL echo this version. The exported `SPs:` line in the PokePaste output SHALL come from the active preset only. (Note: no `nature_jumps.json` data file — jumps computed at runtime per Requirement 4.)

#### Scenario: SP mechanics version recorded
- **WHEN** any team is generated
- **THEN** `VariantOut.meta_versions.sp_mechanics` is set to the loaded `data_version` integer

#### Scenario: PokePaste export uses active preset
- **WHEN** `to_pokepaste` is called with `preset="defensive"` for a member
- **THEN** the `SPs:` line in the output reflects `defensive_preset` values, not `offensive_preset`
