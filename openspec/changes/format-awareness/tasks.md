## 1. API Schema — format param + new response fields

- [x] 1.1 Add `format: Literal["bo1", "bo3"] = "bo1"` to `GenerateRequest` in `schemas.py`
- [x] 1.2 Add `format_mode: str` and `lead_flexibility_score: float` to `VariantOut` in `schemas.py`
- [x] 1.3 Add `AnalyzeMatchupRequest` (team: list[str] len=6, threat: str) and `MatchupAnalysisResponse` (weakness_summary, primary_handler, secondary_handler, adjustments) to `schemas.py`
- [x] 1.4 Add `AdjustmentOut` schema: `type: str`, `target: str`, `change: str`, `reason: str`

## 2. Bo3 Viability Scoring

- [x] 2.1 Add `_lead_flexibility_points(members: list[TeamMember]) -> float` to `viability_rater.py`: iterate all C(6,4) combinations, check each for lead-viable pair (speed-control or redirect move), return `(viable/15) * 25`
- [x] 2.2 Add `_core_diversity_points(members: list[TeamMember]) -> float`: count sweeper–support pairs, return `min(count/3, 1.0) * 15`
- [x] 2.3 Add `format_mode: str = "bo1"` parameter to `score_team()`; in Bo3 mode call `_lead_flexibility_points + _core_diversity_points` instead of `_roles_points`, keep coverage/sp/items weights at 30/15/15
- [x] 2.4 Populate `lead_flexibility_score` in `VariantOut` from the ratio computed in step 2.1 (store intermediate float before multiplying by 25)
- [x] 2.5 Add tests in `tests/test_bo3_mode.py`: Bo3 score formula sums to ≤100; all-speed team scores high flexibility; single-lead team scores low flexibility; Bo1 score unchanged

## 3. Bo3 Generation — cheese deprioritization + format propagation

- [x] 3.1 Add `_BO3_CHEESE_MOVES = frozenset({"destiny-bond", "mirror-coat", "counter", "memento", "perish-song"})` to `replica_exporter.py`
- [x] 3.2 In `select_moves_for_role`: accept `format_mode: str = "bo1"`; skip `_BO3_CHEESE_MOVES` entries when selecting slot 4 and `format_mode="bo3"`
- [x] 3.3 Thread `format_mode` from `generate_team()` → `_build_variant()` → `select_moves_for_role()` and `score_team()`
- [x] 3.4 Set `format_mode` on `VariantOut` in `api/router.py` from the request
- [x] 3.5 Add tests: Destiny Bond not assigned in Bo3; assigned normally in Bo1

## 4. Matchup Analyzer Service

- [x] 4.1 Create `services/matchup_analyzer.py` with `UnknownThreatError` exception and `ARCHETYPE_MAP` dict (`"trick room"` → pokémon list, etc.)
- [x] 4.2 Implement `resolve_threat(threat: str, lookup) -> list[PokemonData]`: try `pokemon_lookup.lookup(threat)` first, then archetype map, raise `UnknownThreatError` if neither matches
- [x] 4.3 Implement `score_handler(member: TeamMember, threat_mons: list[PokemonData], type_chart) -> tuple[float, str]`: type resistance bonus + STAB coverage bonus + role bonus; return score and Spanish explanation string
- [x] 4.4 Implement `suggest_adjustments(member: TeamMember, threat_mons, legal_pool, meta_service) -> list[AdjustmentOut]`: move swap first (slot 4 replace with coverage move for threat type), then item swap (e.g., resist berry), then pokémon swap with same-role replacement from legal pool
- [x] 4.5 Implement `analyze(team_names, threat, lookup, type_chart, legal_pool, meta_service) -> MatchupAnalysisResponse`: orchestrate resolve → score handlers → build weakness summary → build adjustments
- [x] 4.6 Create `tests/test_matchup_analyzer.py`: trick room archetype resolved correctly; primary handler identified; move swap adjustment generated; UnknownThreatError on garbage input

## 5. API Endpoint — /analyze-matchup

- [x] 5.1 Add `POST /analyze-matchup` route to `api/router.py` using `AnalyzeMatchupRequest` / `MatchupAnalysisResponse`
- [x] 5.2 Validate team length = 6; return HTTP 422 with Spanish message if not
- [x] 5.3 Catch `UnknownThreatError` → return HTTP 422 `{"error": "Amenaza desconocida: <threat>"}`
- [x] 5.4 Wire `matchup_analyzer.analyze()` using existing `pokemon_lookup`, `type_chart`, `legal_pool_loader`, and `meta_service` instances
- [x] 5.5 Add tests in `tests/test_api.py`: valid request returns 200 with handlers and adjustments; 5-member team returns 422; unknown threat returns 422

## 6. Frontend — Bo3 toggle + matchup panel

- [x] 6.1 Add Bo3/Bo1 radio toggle to `index.html` form (default Bo1); bind to `format` in `app()` Alpine state
- [x] 6.2 Send `format` field in POST body to `/generate` in `app.js`
- [x] 6.3 Show `lead_flexibility_score` as a percentage badge on each Bo3 variant card (hidden in Bo1)
- [x] 6.4 Add "Analizar matchup" section below results: input for threat name + "Analizar" button; calls `POST /analyze-matchup` with current team names
- [x] 6.5 Render matchup analysis response: weakness summary, handler cards (name + explanation), adjustment list with type badge (swap/item/reemplazo)

## 7. Final Verification

- [x] 7.1 Run full test suite: all existing tests still pass plus new Bo3 + matchup tests
- [x] 7.2 Generate Bo3 team for Rillaboom: verify lead_flexibility_score > 0 and Destiny Bond absent
- [x] 7.3 Generate Bo1 team for same anchor: verify output identical to pre-change baseline
- [x] 7.4 Call `/analyze-matchup` with trick room threat on a generated team: verify Spanish analysis with handlers and at least one adjustment
