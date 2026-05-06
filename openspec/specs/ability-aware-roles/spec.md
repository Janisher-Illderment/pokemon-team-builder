# ability-aware-roles Specification

## Purpose
TBD - created by archiving change fix-role-balance-2. Update Purpose after archive.
## Requirements
### Requirement: STAB override searches all abilities, not just abilities[0]
`select_moves_for_role` SHALL iterate `pokemon.abilities` in order and use the first ability found in `_ABILITY_STAB_OVERRIDES` to determine the upgrade. If no ability matches, no override is applied.

#### Scenario: Ninetales-A Snow Warning override fires (ability at index 1)
- **WHEN** `select_moves_for_role` runs for a Pokémon with `abilities=["snow-cloak", "snow-warning"]` that knows both `ice-beam` and `blizzard`
- **THEN** `slot2` is `blizzard`

#### Scenario: Machamp No Guard override fires (ability at index 1)
- **WHEN** `select_moves_for_role` runs for a Pokémon with `abilities=["guts", "no-guard"]` that knows both `close-combat` and `dynamic-punch`
- **THEN** `slot2` is `dynamic-punch`

#### Scenario: No matching ability leaves slot2 unchanged
- **WHEN** `select_moves_for_role` runs for a Pokémon with `abilities=["pressure"]` that knows `ice-beam`
- **THEN** `slot2` is `ice-beam` (no override applied)

### Requirement: Fake Out and redirect moves detect lead_support without speed gate
`assign_role` SHALL add `lead_support` when the Pokémon's move pool contains `fake-out`, `follow-me`, or `rage-powder`, regardless of its Speed stat. The `spe >= 90` gate SHALL only apply to `tailwind`.

#### Scenario: Incineroar with Fake Out is lead_support despite low speed
- **WHEN** `assign_role` evaluates a Pokémon with `spe=60` and `fake-out` in its move pool
- **THEN** `lead_support` is in its roles

#### Scenario: Tailwind still requires spe >= 90
- **WHEN** `assign_role` evaluates a Pokémon with `spe=50` and only `tailwind` as a support move
- **THEN** `lead_support` is NOT assigned (speed too low for Tailwind to be useful)

#### Scenario: High-speed Tailwind setter still detected
- **WHEN** `assign_role` evaluates a Pokémon with `spe=126` and `tailwind` in its move pool
- **THEN** `lead_support` is in its roles

### Requirement: Prankster ability triggers lead_support as primary role
Pokémon whose `abilities[0]` is `"prankster"` SHALL receive `lead_support` as their first role, regardless of stats or move pool.

#### Scenario: Whimsicott (Prankster primary) is lead_support
- **WHEN** `assign_role` evaluates a Pokémon with `abilities[0]="prankster"` and `spe=116`
- **THEN** `roles[0]` is `lead_support`

#### Scenario: Pokémon with Prankster as hidden ability is not affected
- **WHEN** `assign_role` evaluates a Pokémon with `abilities=["keen-eye", "stall", "prankster"]`
- **THEN** `lead_support` is NOT injected by the Prankster rule (abilities[0] is not prankster)

### Requirement: dynamic-punch is preferred over close-combat for No Guard Pokémon
`_STAB_BY_TYPE["fighting"]` SHALL include `dynamic-punch`. The `_ABILITY_STAB_OVERRIDES` dict SHALL map `"no-guard"` to `{"close-combat": "dynamic-punch"}`.

#### Scenario: Machamp with No Guard prefers Dynamic Punch
- **WHEN** `select_moves_for_role` runs for a Pokémon with No Guard knowing both `close-combat` and `dynamic-punch`
- **THEN** `slot2` is `dynamic-punch`

#### Scenario: Fighting-type without No Guard does not get Dynamic Punch as STAB priority
- **WHEN** `select_moves_for_role` runs for a Pokémon with `abilities=["guts"]` knowing both `close-combat` and `dynamic-punch`
- **THEN** `slot2` is `close-combat` (no override without No Guard)

### Requirement: Hurricane is preferred over Air Slash for Drizzle Pokémon
`_ABILITY_STAB_OVERRIDES` SHALL map `"drizzle"` to `{"air-slash": "hurricane"}`.

#### Scenario: Pelipper with Drizzle prefers Hurricane
- **WHEN** `select_moves_for_role` runs for a Pokémon with Drizzle knowing both `air-slash` and `hurricane`
- **THEN** `slot2` is `hurricane`

#### Scenario: Flying-type without Drizzle uses Air Slash normally
- **WHEN** `select_moves_for_role` runs for a Pokémon with `abilities=["keen-eye"]` knowing both `air-slash` and `hurricane`
- **THEN** `slot2` is `air-slash`

### Requirement: Weather ability at non-zero index only triggers lead_support for whitelisted species
`assign_role` SHALL only inject `lead_support` from a weather ability if: (a) the ability is `abilities[0]`, OR (b) the Pokémon's name is in `_COMPETITIVE_WEATHER_SPECIES = {"ninetales-alola", "pelipper", "politoed", "torkoal"}`.

#### Scenario: Aurorus with Refrigerate primary is NOT a weather setter
- **WHEN** `assign_role` evaluates Aurorus (`abilities=["refrigerate", "snow-warning"]`, `name="aurorus"`)
- **THEN** `lead_support` is NOT injected (refrigerate is not a weather ability; snow-warning is at index 1 and aurorus is not in the whitelist)

#### Scenario: Ninetales-A is a weather setter despite Snow Warning at index 1
- **WHEN** `assign_role` evaluates a Pokémon with `name="ninetales-alola"` and `abilities=["snow-cloak", "snow-warning"]`
- **THEN** `roles[0]` is `lead_support` (species is in _COMPETITIVE_WEATHER_SPECIES)

#### Scenario: Hippowdon (Sand Stream at index 0) remains a weather setter
- **WHEN** `assign_role` evaluates a Pokémon with `abilities=["sand-stream", "sand-force"]`
- **THEN** `lead_support` is injected (abilities[0] is in _AUTO_LEAD_ABILITIES)

