## ADDED Requirements

### Requirement: speed_tiers.json contains meta-relevant pokémon speed data
`pokemon_team_builder/data/speed_tiers.json` SHALL be a JSON array of objects with fields `name` (lowercase pokémon name), `base_spe` (integer base Speed stat), and `usage_rank` (integer 1–50, lower = more used). It SHALL include at minimum the top 50 pokémon by Regulation M-A usage.

#### Scenario: File loads without error
- **WHEN** `SpeedTierDB.load()` is called at startup
- **THEN** it parses the JSON and returns a non-empty list of speed tier entries

#### Scenario: Known fast pokémon present
- **WHEN** the database is loaded
- **THEN** entries for "flutter-mane" (base 135) and "miraidon" (base 135) are present

### Requirement: SpeedTierDB computes level-50 Speed for any SP and nature
`SpeedTierDB.compute_speed(base_spe: int, sps: int, nature: str) -> int` SHALL use the formula `floor((floor((2*base + 31 + sps*8/4) * 50/100) + 5) * nature_mod)` where `nature_mod` is 1.1 for +Spe natures (Timid, Jolly), 0.9 for −Spe natures (Brave, Quiet, Relaxed, Sassy), and 1.0 otherwise.

#### Scenario: Neutral nature max SPs
- **WHEN** `compute_speed(85, 32, "adamant")` is called (Rillaboom, 32 SPs, neutral speed nature)
- **THEN** the result matches the known level-50 Speed for Rillaboom at max SPs

#### Scenario: Timid nature zero SPs
- **WHEN** `compute_speed(135, 0, "timid")` is called (Flutter Mane, no SPs, Timid)
- **THEN** the result is the level-50 Speed for Flutter Mane with Timid and no investment

### Requirement: SpeedTierDB.faster_than and slower_than return ordered lists
`SpeedTierDB.faster_than(speed_value: int) -> list[str]` SHALL return pokémon names from the database whose level-50 Speed (neutral nature, 0 SPs) exceeds `speed_value`, ordered by base_spe ascending (slowest-fastest-among-faster-mons first). `SpeedTierDB.slower_than(speed_value: int) -> list[str]` SHALL return pokémon whose level-50 Speed is strictly less than `speed_value`, ordered by base_spe descending (fastest-among-slower-mons first).

#### Scenario: Speed in a middle tier
- **WHEN** a pokémon's computed speed is 100
- **THEN** `faster_than(100)` returns pokémon with base speed resulting in level-50 Speed > 100
- **AND** `slower_than(100)` returns pokémon with level-50 Speed < 100
