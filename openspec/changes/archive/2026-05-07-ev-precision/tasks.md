## 1. Speed Tier Data

- [x] 1.1 Fetch and parse the Champions speed tier sheet (https://docs.google.com/spreadsheets/d/1TPQIsDAZaeRmwrqRMbENDp6NJdoFxg87/edit); extract top 50 pokémon by Reg M-A usage with their base_spe values
- [x] 1.2 Create `pokemon_team_builder/data/speed_tiers.json` as JSON array: `[{"name": "flutter-mane", "base_spe": 135, "usage_rank": 1}, ...]` covering at least 50 entries
- [x] 1.3 Create `SpeedTierDB` class in `pokemon_team_builder/data/speed_tiers.py`: `load() -> SpeedTierDB`, `compute_speed(base_spe, sps, nature) -> int`, `faster_than(speed) -> list[str]`, `slower_than(speed) -> list[str]`
- [x] 1.4 Add tests in `tests/test_speed_tiers.py`: formula correct for known pokémon (Rillaboom base 85, Flutter Mane base 135); faster_than/slower_than return correct lists

## 2. Damage Calculator

- [x] 2.1 Create `pokemon_team_builder/services/damage_calc.py` with `calc_stat(base, sps, nature_mod, is_hp) -> int` using level-50 formula
- [x] 2.2 Add `calc_damage(atk_stat, def_stat, move_power, effectiveness, stab) -> tuple[float, float]` returning (min_pct, max_pct) as % of defender HP
- [x] 2.3 Add `COMMON_ATTACKS: dict[str, dict]` with all 18 types → `{power, name, category}` (e.g. `"ground": {"power": 100, "name": "Terremoto", "category": "physical"}`)
- [x] 2.4 Add `get_nature_mod(nature: str, stat: str) -> float`: returns 1.1 / 0.9 / 1.0 based on nature table
- [x] 2.5 Add tests in `tests/test_damage_calc.py`: calc_stat matches known level-50 values; calc_damage super-effective hit > 50%; COMMON_ATTACKS has 18 entries

## 3. EV Explainer Service

- [x] 3.1 Create `pokemon_team_builder/services/ev_explainer.py` with `explain(member, speed_db, meta) -> str`
- [x] 3.2 Speed note logic: if `spe > 0` → compute member speed → call `faster_than` + `slower_than` → format "X Spe supera a A (N) y B (N) — no alcanza a C (N)"
- [x] 3.3 Defensive note logic: identify largest bulk stat (hp/def/spd) → look up member's type weaknesses → find most-used attacking move for that type from meta (or COMMON_ATTACKS fallback) → compute damage % → format "X HP + Y Def aguanta el Z de W [con holgura / por poco / NO aguanta]"
- [x] 3.4 Mixed investment: return speed note + ". " + defensive note as single string
- [x] 3.5 Add tests in `tests/test_ev_explainer.py`: speed note names specific pokémon; defensive note names specific attack; empty distribution returns ""; mixed returns both sentences

## 4. Wire into API

- [x] 4.1 Instantiate `SpeedTierDB` once at app startup in `api/router.py` (alongside existing pokemon_lookup / legal_pool_loader singletons)
- [x] 4.2 Replace `_build_ev_note()` call in member serialization with `ev_explainer.explain(member, speed_db, meta_service)`
- [x] 4.3 Add/update tests in `tests/test_api.py`: `/generate` response `ev_note` for a speed-invested member contains a pokémon name from the speed tier DB

## 5. Final Verification

- [x] 5.1 Run full test suite — all existing tests pass plus new speed/damage/explainer tests
- [x] 5.2 Generate a team for Garchomp; verify ev_note names pokémon it outspeeds and at least one it does not
- [x] 5.3 Generate a team with a wall (Slowbro or Snorlax); verify ev_note names a specific attack it survives
