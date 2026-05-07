## 1. MetaService — Core

- [x] 1.1 Create `pokemon_team_builder/services/meta_service.py` with `MetaEntry` dataclass (items, moves, teammates as lists of strings) and `MetaService` class with `get(name: str) -> MetaEntry | None`
- [x] 1.2 Implement Champions format URL first, VGC fallback on 404; both use httpx via hishel `FileStorage` at `pokemon_team_builder/cache/meta/` with TTL=86400s
- [x] 1.3 Parse MunchStats JSON response: extract top-5 items, top-6 moves, top-6 teammates into `MetaEntry`
- [x] 1.4 Return `None` (no exception) on any non-200 / network error
- [x] 1.5 Create `tests/test_meta_service.py`: mock httpx responses for Champions hit, fallback, full failure; assert correct parsing and None return

## 2. Item Selection Upgrade

- [x] 2.1 In `team_generator.py` `_assign_items`: instantiate `MetaService` and call `get()` before the role-lookup block
- [x] 2.2 Try meta items in ranked order first (Item Clause + `_item_is_activatable` guards unchanged); fall through to existing role-based logic if all fail or meta is None
- [x] 2.3 Add/update tests in `tests/test_team_generator.py`: meta item preferred over role default, meta item skipped when Item Clause conflict

## 3. Move Selection Upgrade

- [x] 3.1 In `replica_exporter.py` `select_moves_for_role`: accept optional `meta_moves: list[str]` parameter (default `None`)
- [x] 3.2 For slots 2–4: if `meta_moves` provided, try intersection with `pokemon.move_names` before consulting static tables; only use if role-compatible (category check for slot 2, no duplicate check)
- [x] 3.3 Pass meta moves from team_generator when calling `_build_variant`
- [x] 3.4 Add/update tests: meta move preferred when in pool and role-compatible; falls back when meta move not in pool

## 4. Teammate Affinity Boost

- [x] 4.1 In `team_generator.py` `_heuristic_filter`: fetch anchor's `MetaEntry` once before the loop; build a `meta_teammates` set (lowercase)
- [x] 4.2 Add `+3.0` to heuristic score for each candidate whose name is in `meta_teammates`
- [x] 4.3 Graceful no-op when MetaService returns None for anchor
- [x] 4.4 Add/update tests: candidate in meta teammates gets higher score; anchor with no meta data produces unchanged scores

## 5. EV Display — API Layer

- [x] 5.1 Add `sp_distribution: dict[str, int]` and `ev_note: str` to `MemberOut` in `schemas.py`
- [x] 5.2 In `api/router.py` member serialization: populate `sp_distribution` from `TeamMember.sp_distribution` omitting zero-value stats
- [x] 5.3 Implement `_build_ev_note(sp: SPDistribution, role: list[str]) -> str` in `api/router.py`: identify two largest allocations, return Spanish sentence (empty string if all zero)
- [x] 5.4 Add tests in `tests/test_api.py` (or `tests/test_router.py`): response includes `sp_distribution` and non-empty `ev_note` for a generated team

## 6. EV Display — Frontend

- [x] 6.1 In `app.js` `app()`: add helper `spGrid(member)` returning `[{stat, val, active}]` for all 6 stats
- [x] 6.2 In `index.html` member template: add stat grid div (6 cells, HP/Atk/Def/SpA/SpD/Spe labels + values) below moves `<ul>`; gray-out cells where `active=false`
- [x] 6.3 Add `ev_note` italic line below stat grid; hide when empty
- [x] 6.4 Add stat grid CSS to `style.css` (compact, 3-column grid, muted color for zero stats)

## 7. Team Presets — Frontend

- [x] 7.1 Add `savedTeams()` Alpine component in `app.js`: initializes from `localStorage['poke-builder-presets']`, manages add/delete/update operations, cap at 20 with warning
- [x] 7.2 Add `saveTeam(variant)` method to `app()` that serializes pokepaste + member names + score into a preset object and delegates to `savedTeams()`
- [x] 7.3 In `index.html`: add "Save Team" button to each variant card header
- [x] 7.4 In `index.html`: add Saved Teams panel (toggle button in header) listing presets with sprites, name, color dot, timestamp, Copy Pokepaste, Delete
- [x] 7.5 Sprite URL helper: `spriteUrl(name)` → `https://play.pokemonshowdown.com/sprites/gen5/{normalized_name}.png`; `onerror` fallback to text name
- [x] 7.6 Add preset CSS: panel layout, sprite size (40px), color tag dots (6 palette), empty state message
- [x] 7.7 Manual smoke test: save a team, reload page, verify it persists; edit name, verify localStorage update; delete, verify removal

## 8. Final Verification

- [x] 8.1 Run full test suite (`pytest`): all existing 173 tests still pass plus new tests
- [x] 8.2 Start dev server and generate a team for Garchomp; verify meta items appear (e.g., Garchompite, Sitrus Berry, Focus Sash)
- [x] 8.3 Verify EV grid renders correctly in the browser with non-zero stats visible and zero stats grayed
- [x] 8.4 Save a team, reload, edit name, copy pokepaste — all working
