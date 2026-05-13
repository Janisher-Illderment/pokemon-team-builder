## ADDED Requirements

### Requirement: Ability-driven weather synergy awards a +3 META-weighted bonus
`viability_rater._weather_synergy_points(members, weather_data) -> float` SHALL detect members with a weather-dependent ability (per `data/weather_dependent_abilities.json`). For each such member, if any teammate SETS the matching weather (ability setter per `data/weather_setters.json` OR holds the weather-setting move), the team SHALL receive **+3 points**. The bonus stacks per matched ability-setter pair.

#### Scenario: Excadrill + Tyranitar
- **WHEN** a team contains Excadrill (Sand Rush) AND Tyranitar (Sand Stream)
- **THEN** `_weather_synergy_points` returns at least +3.0

#### Scenario: Two weather-ability members + one setter
- **WHEN** a team contains Excadrill (Sand Rush), Tyranitar (Sand Stream), AND Garchomp (Sand Force)
- **THEN** the bonus is +6.0 (two ability-driven matches, one setter)

#### Scenario: Weather-ability member without matching setter
- **WHEN** a team contains Excadrill (Sand Rush) but no Sand setter
- **THEN** `_weather_synergy_points` returns 0.0 for that ability match

### Requirement: Passive weather synergy awards a +2 bonus
When a weather is present on the team (any setter regardless of ability gating) AND a member benefits passively (the weather covers one of the member's type weaknesses, or boosts a STAB the member already has — Hurricane in Rain, Solar Beam in Sun without Chlorophyll, Blizzard accuracy in Snow), the team SHALL receive **+2 points** per beneficiary, capped at the number of distinct (member × passive-benefit) pairs.

#### Scenario: Hurricane user benefits from Rain without Swift Swim
- **WHEN** a team contains a Hurricane user (not Swift Swim / Hydration / Rain Dish) and a Drizzle setter
- **THEN** `_weather_synergy_points` adds +2 for the passive Hurricane accuracy benefit

#### Scenario: Passive bonus does not stack with ability-driven on same member
- **WHEN** a member is both Swift Swim AND has Hurricane, paired with a Drizzle setter
- **THEN** the +3 ability-driven bonus applies and the +2 passive bonus does NOT double-count for the same member

### Requirement: Weather data files are versioned
`data/weather_dependent_abilities.json` and `data/weather_setters.json` SHALL include `regulation` and `data_version` headers. Versions SHALL be echoed in `VariantOut.meta_versions.weather`.

**Initial seed data (Inte verified, Bulbapedia + StrataDex + Game8, HIGH confidence):**

`weather_dependent_abilities.json` (ability → required_weather):
- Sun: Chlorophyll, Solar Power, Leaf Guard, Flower Gift, Orichalcum Pulse, Protosynthesis, Harvest
- Rain: Swift Swim, Dry Skin, Hydration, Rain Dish
- Sand: Sand Rush, Sand Force, Sand Veil
- Hail/Snow: Slush Rush, Ice Body, Snow Cloak, Ice Face

`weather_setters.json` (pokémon → ability → weather):
- Torkoal → Drought → Sun
- Pelipper → Drizzle → Rain
- Tyranitar → Sand Stream → Sand
- Hippowdon → Sand Stream → Sand
- Ninetales-Alola → Snow Warning → Snow
- Abomasnow → Snow Warning → Snow
- Mega-Froslass → Snow Warning → Snow (mega-only setter)

Move-based setters (Sunny Day, Rain Dance, Sandstorm, Snowscape) exist but SHALL be tracked separately under `weather_move_setters` with a lower confidence flag — ability-based setters dominate the meta.

#### Scenario: Weather data version recorded on variant
- **WHEN** any team is generated
- **THEN** `VariantOut.meta_versions.weather` is set to the loaded `data_version` integer

### Requirement: Weather synergy is amplified by weather_based archetype, ignored by stall
`_weather_synergy_points` SHALL be multiplied by `archetype_weights[archetype].weather_synergy` before being added to the total. `weather_based` SHALL have `weather_synergy >= 1.5`; `stall` SHALL have `weather_synergy = 0.0` (weather doesn't help a stall team).

#### Scenario: weather_based amplifies the bonus
- **WHEN** `_weather_synergy_points` returns +3.0 raw and archetype is `weather_based` with weight 1.5
- **THEN** the contribution to the team score is +4.5

#### Scenario: stall zeros the bonus
- **WHEN** `_weather_synergy_points` returns +3.0 raw and archetype is `stall` with weight 0.0
- **THEN** the contribution to the team score is 0.0
