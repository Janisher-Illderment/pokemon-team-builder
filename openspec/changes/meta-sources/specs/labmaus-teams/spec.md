## ADDED Requirements

### Requirement: LabMausService scrapes top teams from labmaus.net
The system SHALL provide a `LabMausService` class in `services/labmaus_service.py` that retrieves the current top teams from `https://labmaus.net/teams/top-teams` and returns a list of `LabMausTeam` records (each with `rank`, `members: list[LabMausMember]`, optional `pokepaste: str | None`, optional `tournament: str | None`, optional `placement: str | None`). Each `LabMausMember` SHALL contain `name: str` (already normalized via `pokemon_lookup.normalize_display_name`), optional `item: str | None`, and optional `moves: list[str]` (max 4).

#### Scenario: Live fetch succeeds with full team data
- **WHEN** `LabMausService.get_top_teams(regulation="M-A")` is called and labmaus.net returns 200 with a parseable team listing including items and moves
- **THEN** it returns a list of 8–10 `LabMausTeam` records, each with up to 6 members and `item`/`moves` populated where the markup exposes them

#### Scenario: Live fetch succeeds with names only
- **WHEN** the LabMaus response is 200 but the markup only exposes pokémon names (no items/moves)
- **THEN** each `LabMausMember.item` is `None` and `LabMausMember.moves` is an empty list, but the team list itself is fully populated

#### Scenario: Live fetch fails (network or non-200)
- **WHEN** the request to labmaus.net raises `httpx.HTTPError` or returns a non-2xx status
- **THEN** `get_top_teams` returns an empty list and does not raise

#### Scenario: Parsing fails (markup changed)
- **WHEN** the response is 200 but the parser cannot extract any team blocks
- **THEN** `get_top_teams` returns an empty list and does not raise

### Requirement: LabMausService caches responses for 6 hours
The system SHALL cache LabMaus responses to disk for 6 hours using hishel `SyncSqliteStorage` at `pokemon_team_builder/cache/labmaus/`. A subsequent call within the TTL SHALL be served from cache without an outbound HTTP request.

#### Scenario: Cache hit
- **WHEN** `get_top_teams` is called and a cached response exists with TTL remaining
- **THEN** no HTTP request is made and the cached team list is returned

#### Scenario: Cache miss
- **WHEN** `get_top_teams` is called and no cached response exists (or TTL expired)
- **THEN** an HTTP GET is made to labmaus.net and the response is stored in the cache

### Requirement: Pokémon name normalization for LabMaus display names
The system SHALL provide a `normalize_display_name(raw: str) -> str` helper in `services/pokemon_lookup.py` that converts human-readable LabMaus names (e.g. "Tapu Koko", "Mr. Mime", "Urshifu-Single Strike", "Flutter Mane") into the canonical PokeAPI slug form (e.g. "tapu-koko", "mr-mime", "urshifu-single-strike", "flutter-mane"). `LabMausService` SHALL apply this helper to every parsed pokémon name before returning the result.

#### Scenario: Name with space
- **WHEN** the helper receives "Flutter Mane"
- **THEN** it returns "flutter-mane"

#### Scenario: Name with punctuation
- **WHEN** the helper receives "Mr. Mime" or "Type: Null"
- **THEN** it returns "mr-mime" / "type-null"

#### Scenario: Form suffix
- **WHEN** the helper receives "Urshifu-Single Strike" or "Indeedee-F"
- **THEN** it returns "urshifu-single-strike" / "indeedee-f"

#### Scenario: Already-canonical input
- **WHEN** the helper receives "garchomp"
- **THEN** it returns "garchomp" unchanged

### Requirement: GET /meta-teams endpoint
The system SHALL expose `GET /meta-teams` accepting an optional `regulation` query parameter (default `"M-A"`). The endpoint SHALL return a JSON object `{"regulation": str, "teams": list[LabMausTeamOut], "stale": bool}` where `stale` is `true` only when the underlying scrape failed and the response is the empty fallback. The endpoint SHALL NEVER return 5xx for upstream scraping failures — those become `{"teams": [], "stale": true}` with status 200.

#### Scenario: Successful scrape
- **WHEN** a client calls `GET /meta-teams`
- **AND** `LabMausService.get_top_teams` returns a non-empty list
- **THEN** the response is 200 with `teams` populated and `stale: false`

#### Scenario: Scrape failure
- **WHEN** a client calls `GET /meta-teams`
- **AND** `LabMausService.get_top_teams` returns an empty list (failure or empty parse)
- **THEN** the response is 200 with `teams: []` and `stale: true`

#### Scenario: Custom regulation parameter
- **WHEN** a client calls `GET /meta-teams?regulation=M-B`
- **THEN** the endpoint forwards the regulation value to the service and echoes it in `regulation` in the response payload

### Requirement: Frontend Top Teams panel
The web frontend SHALL render a collapsible "Top Teams del Meta" panel in `index.html`, controlled by a new `metaTeams()` Alpine component in `app.js`. The panel SHALL be collapsed by default and SHALL only fetch `/meta-teams` the first time it is expanded (subsequent toggles in the same session SHALL reuse the in-memory result). Each team card SHALL display 6 sprites (using the `meta-quality-v2` Showdown sprite helper or equivalent), the team's rank/placement/tournament when available, and an "Importar" button.

#### Scenario: Panel expanded for first time
- **WHEN** the user clicks the panel header to expand it
- **AND** no fetch has yet occurred this session
- **THEN** the component fetches `/meta-teams`, sets a loading state, and renders the resulting team cards

#### Scenario: Panel re-toggled in the same session
- **WHEN** the user collapses then re-expands the panel within the same page session
- **THEN** no new HTTP request is made; the previously fetched team list is shown

#### Scenario: Importar with full PokePaste
- **WHEN** a team card has a non-null `pokepaste` field and the user clicks "Importar"
- **THEN** the PokePaste is handed to the existing import flow (textarea pre-fill or POST, depending on what the import path uses) so the user can immediately analyze the team

#### Scenario: Importar with names only
- **WHEN** a team card has `pokepaste: null` and the user clicks "Importar"
- **THEN** the anchor field is pre-filled with the first team member's name and the user is scrolled to or focused on the generate form

#### Scenario: Stale/empty state
- **WHEN** the API responds with `teams: []` and `stale: true`
- **THEN** the panel renders a friendly "No hay datos del meta ahora mismo" message instead of an empty card grid
