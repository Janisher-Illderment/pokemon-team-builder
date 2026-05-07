## ADDED Requirements

### Requirement: calc_stat computes level-50 stat from base, SPs, and nature
`services/damage_calc.py` SHALL expose `calc_stat(base: int, sps: int, nature_mod: float, is_hp: bool) -> int` using the standard formula at level 50 with IVs = 31 and SP contribution `floor(sps * 8 / 4)` added to the base term.

#### Scenario: HP stat calculation
- **WHEN** `calc_stat(95, 0, 1.0, is_hp=True)` is called (Amoonguss, no SPs)
- **THEN** the result matches the known level-50 HP for Amoonguss at 0 EVs

#### Scenario: Non-HP stat with nature boost
- **WHEN** `calc_stat(145, 32, 1.1, is_hp=False)` is called (Landorus-T, max Atk SPs, Adamant)
- **THEN** the result matches the boosted level-50 Attack

### Requirement: calc_damage computes a damage estimate as percentage of defender HP
`calc_damage(atk_stat: int, def_stat: int, move_power: int, effectiveness: float, stab: bool) -> tuple[float, float]` SHALL return `(min_pct, max_pct)` as a percentage of the defender's HP, using the standard damage formula at level 50 with a ±15% roll range (0.85 low roll, 1.0 high roll).

#### Scenario: Super-effective STAB move
- **WHEN** a 120-power super-effective STAB move is used with appropriate stats
- **THEN** `min_pct` and `max_pct` are both above 50.0 (clearly threatening)

#### Scenario: Resisted move
- **WHEN** a 90-power resisted (0.5×) non-STAB move is used
- **THEN** `max_pct` is below 50.0 (not threatening)

### Requirement: COMMON_ATTACKS fallback table covers all 18 types
`damage_calc.py` SHALL include a `COMMON_ATTACKS` dict mapping each of the 18 types to a representative high-usage attack: `{power: int, name: str}`. This is used when MetaService data is unavailable to identify the most likely damaging attack of a given type.

#### Scenario: All types covered
- **WHEN** `COMMON_ATTACKS` is imported
- **THEN** it contains exactly 18 entries, one per type, each with `power` and `name` keys
