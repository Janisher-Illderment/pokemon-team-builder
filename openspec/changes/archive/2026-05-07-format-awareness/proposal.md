## Why

Pokémon Champions is played in two very different contexts: Swiss/ladder (Bo1, closed team sheet — opponent doesn't see your team before the battle starts) and tournaments (Bo3, open team sheet — opponent sees all 6 pokémon and can prepare leads). The current builder generates teams with no awareness of this distinction, producing output that's mediocre for both contexts. Additionally, users need a way to diagnose weaknesses in a finished team against a specific threat or archetype — a "what do I change against trick room?" capability that reasons from type coverage + role data rather than just listing stats.

## What Changes

- **`format` parameter on `/generate`**: `"bo1"` (default) or `"bo3"` — propagated through `GenerateRequest` → `generate_team()` → `score_team()`.
- **Bo3 lead flexibility scoring**: `viability_rater.py` gains a new `lead_flexibility` component (replaces or supplements the existing roles component in Bo3 mode) that counts how many distinct 4-of-6 combinations produce a viable lead pair, rewarding teams that can adapt leads vs different opponents.
- **Bo3 consistency weighting**: `team_generator.py` beam search deprioritizes mono-strategy cheese (Destiny Bond, Mirror Coat as primary moves) in Bo3 mode; `synergy_engine.py` gains a `count_cores()` helper that identifies how many distinct 2-pokémon offensive cores the team has.
- **`format_mode` and `lead_flexibility_score` in `VariantOut`**: new fields exposed on the API response.
- **`POST /analyze-matchup` endpoint**: accepts `{team: [6 names], threat: str}`, returns a Spanish-language analysis object with weakness summary, best handlers from the team, and 1–2 concrete adjustments (move swap, item swap, or pokémon swap with a specific replacement name).

## Capabilities

### New Capabilities

- `bo3-mode`: Bo3-aware generation mode — lead flexibility scoring, core diversity evaluation, cheese-move deprioritization; exposed via `format` param on `/generate`.
- `matchup-analysis`: Computational matchup analysis endpoint that diagnoses a team's vulnerability to a named threat and suggests concrete adjustments using type chart + meta data, no LLM required.

### Modified Capabilities

- `role-balance`: `score_team` in `viability_rater.py` gains a `format_mode` parameter; in Bo3 mode the roles component is replaced by lead flexibility + core diversity scoring.

## Impact

- **Modified files**: `schemas.py`, `api/router.py`, `services/team_generator.py`, `services/viability_rater.py`, `services/synergy_engine.py`
- **New files**: `services/matchup_analyzer.py`, `tests/test_bo3_mode.py`, `tests/test_matchup_analyzer.py`
- **Dependencies**: none new — uses existing type_chart, meta_service (from meta-quality-v2), pokemon_lookup
- **Breaking**: `VariantOut` gets new additive fields; existing consumers unaffected
