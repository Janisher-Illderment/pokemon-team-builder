## 1. LabMausService — Core

- [x] 1.1 Live-inspect `https://labmaus.net/teams/top-teams` once with `httpx.get` to capture a fresh HTML snapshot; save it as `tests/fixtures/labmaus_top_teams.html` for parser tests
  **Note:** Source is actually a JSON API at `/api/top_teams` (React SPA). Saved JSON fixture to `tests/fixtures/labmaus_top_teams.json` instead. No HTML to parse.
- [x] 1.2 Create `pokemon_team_builder/services/labmaus_service.py` with `LabMausMember` and `LabMausTeam` dataclasses (fields per spec) and `LabMausService` class with `get_top_teams(regulation: str = "M-A") -> list[LabMausTeam]`
- [x] 1.3 Configure httpx + hishel `SyncSqliteStorage` at `pokemon_team_builder/cache/labmaus/` with TTL=21600s (6h); polite `User-Agent` header identifying the app
- [x] 1.4 Implement HTML parser using `html.parser.HTMLParser` (stdlib) — extract team blocks via stable structural cues (e.g. card class names confirmed in 1.1); extract pokémon names from `<img alt>` or text nodes; extract `pokepaste`, `tournament`, `placement` when present
  **Note:** JSON parser instead — API returns structured data. 3-level nesting: composition → group → individual team.
- [x] 1.5 Apply `pokemon_lookup.normalize_display_name` to every parsed name before returning
- [x] 1.6 Wrap network + parse paths in try/except — return `[]` on `httpx.HTTPError`, non-2xx status, or any parser exception; log the failure at WARNING level

## 2. Pokémon Name Normalization

- [x] 2.1 Add `normalize_display_name(raw: str) -> str` to `pokemon_team_builder/services/pokemon_lookup.py`
- [x] 2.2 Implement: lowercase, strip accents (`unicodedata.normalize("NFKD", ...)`), replace whitespace and `.` `:` with `-`, collapse repeated `-`, strip leading/trailing `-`
- [x] 2.3 Add explicit mapping table for known forms that don't follow the rule cleanly (e.g. mega forms, Urshifu styles, Indeedee gender, Calyrex riders, Ogerpon masks, Tatsugiri patterns)
- [x] 2.4 Add unit tests in `tests/test_pokemon_lookup.py` covering: space, punctuation, accents, form suffixes, already-canonical input, empty/whitespace input

## 3. LabMausService — Tests

- [x] 3.1 Create `tests/test_labmaus_service.py`; use the captured fixture from 1.1 with `respx` or httpx `MockTransport` to simulate the live response
- [x] 3.2 Test happy path: fixture returns 200, parser extracts ≥ 8 teams, names are normalized
- [x] 3.3 Test names-only path: feed a stripped-down fixture without items/moves; assert teams populate but `item is None` and `moves == []`
- [x] 3.4 Test network failure: mock raises `httpx.ConnectError` → returns `[]`, no exception
- [x] 3.5 Test non-200: mock returns 503 → returns `[]`
- [x] 3.6 Test parse failure: mock returns 200 with garbage HTML → returns `[]`
- [x] 3.7 Test cache: two consecutive calls produce only one mocked HTTP request

## 4. TournamentService — Core

- [x] 4.1 Live-inspect `https://events.pokemon.com/EventLocator/` with default Tenerife params; capture a fresh response as `tests/fixtures/events_pokemon_locator.html` (or `.json` if the page exposes a structured payload)
  **Note:** Used LabMaus `/api/upcoming_tournaments` instead — same data, already authenticated. Saved `tests/fixtures/labmaus_upcoming_tournaments.json`.
- [x] 4.2 Create `pokemon_team_builder/services/tournament_service.py` with `Tournament` dataclass and `TournamentService` class with `get_upcoming(lat: float = 28.4636, lon: float = -16.2518, radius_miles: int = 500) -> list[Tournament]`
- [x] 4.3 Configure httpx + hishel `SyncSqliteStorage` at `pokemon_team_builder/cache/tournaments/` with TTL=43200s (12h); cache key includes lat/lon/radius
- [x] 4.4 Implement parser (stdlib `html.parser` or `json` if response is JSON) — extract name, start/end date, city, country, format, url; filter to Pokémon VGC / Champions formats only; sort ascending by start date
- [x] 4.5 Wrap network + parse paths in try/except — return `[]` on any failure; log at WARNING

## 5. TournamentService — Tests

- [x] 5.1 Create `tests/test_tournament_service.py` using the fixture from 4.1
- [x] 5.2 Test happy path: fixture returns 200, parser extracts ≥ 1 event with all required fields, sorted by date
- [x] 5.3 Test format filter: fixture includes a TCG event → it is excluded from the result
  **Note:** Adapted as radius filter (LabMaus API only returns VGC/Champions events — no TCG events to filter). Tested radius exclusion instead.
- [x] 5.4 Test network failure: mock raises `httpx.ConnectError` → returns `[]`
- [x] 5.5 Test empty response: mock returns 200 with no events → returns `[]`
- [x] 5.6 Test cache key by params: calling with two different lat/lon makes two HTTP requests; calling twice with the same params makes one

## 6. API Endpoints

- [x] 6.1 Add `LabMausTeamOut`, `LabMausMemberOut`, `MetaTeamsResponse`, `TournamentOut`, `TournamentsResponse` to `pokemon_team_builder/api/schemas.py`
- [x] 6.2 Add `GET /meta-teams` to `pokemon_team_builder/api/router.py`: accept `regulation: str = "M-A"`; call `LabMausService.get_top_teams`; return `MetaTeamsResponse(regulation=..., teams=..., stale=len(teams)==0)`; never raise 5xx
- [x] 6.3 Add `GET /tournaments` to router: accept optional `lat: float | None`, `lon: float | None`, `radius: int | None`; apply Tenerife defaults; call service; return `TournamentsResponse(tournaments=..., stale=len(tournaments)==0)`; never raise 5xx
- [x] 6.4 Add tests to `tests/test_api.py` (or equivalent): both endpoints return 200 even when the service returns `[]`; `stale: true` in that case; `stale: false` when service returns data; custom query params are forwarded

## 7. Frontend — Top Teams Panel

- [x] 7.1 In `web/static/index.html`: add collapsible section `<section x-data="metaTeams()">` with header button toggling `open`, body bound to `x-show="open"` with `x-init` triggering first-fetch on `open` true
- [x] 7.2 In `web/static/app.js`: define `metaTeams()` Alpine component with state `open=false`, `loaded=false`, `loading=false`, `error=false`, `teams=[]`, `stale=false`; method `expand()` triggers fetch on first open; method `importTeam(team)` dispatches PokePaste path or anchor-prefill path
- [x] 7.3 Render team cards: 6 sprites via `spriteUrl(name)` helper (reuse from `meta-quality-v2` if present, else add it); `onerror` falls back to text name; show rank/placement/tournament when present
- [x] 7.4 "Importar" button: if `team.pokepaste` truthy → reuse import flow; else pre-fill anchor field with `team.members[0].name` and scroll/focus the generate form
- [x] 7.5 Stale/empty state: render "No hay datos del meta ahora mismo" when `teams.length === 0 && stale`
- [x] 7.6 Add CSS in `web/static/style.css`: panel styling, team card grid, sprite size (40–48px), rank/placement badge

## 8. Frontend — Tournaments Panel

- [x] 8.1 In `index.html`: add collapsible section `<section x-data="tournaments()">` mirroring the meta panel structure (collapsed default, lazy fetch on first expand)
- [x] 8.2 In `app.js`: define `tournaments()` Alpine component with state `open`, `loaded`, `loading`, `error`, `items=[]`, `stale`; method `expand()` triggers fetch on first open
- [x] 8.3 Render compact one-line rows: `{date} · {city}, {country} · {format} · {name}`; if `url` present render as `<a target="_blank" rel="noopener noreferrer">`
- [x] 8.4 Stale/empty state: "No hay torneos próximos en tu zona"
- [x] 8.5 Add CSS for tournament list (compact rows, hover state, link color)

## 9. Final Verification

- [x] 9.1 Run full test suite (`pytest`): all existing 301 tests still pass plus new tests from sections 2, 3, 5, 6 → **338 tests passing**
- [ ] 9.2 Start dev server, expand "Top Teams del Meta" panel — verify ≥ 1 team renders with sprites and an Importar button; click Importar and verify the import flow accepts it (or anchor field gets pre-filled)
- [ ] 9.3 Expand "Torneos Próximos" panel — verify ≥ 1 tournament row renders or the friendly empty-state message appears
- [ ] 9.4 Stop the dev server, disconnect from the network, restart, expand both panels — confirm cache hit serves data without errors and that consecutive panel toggles within the session do not re-fetch
- [ ] 9.5 Run `openspec validate meta-sources --strict` and confirm clean
