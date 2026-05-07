## ADDED Requirements

### Requirement: TournamentService scrapes events.pokemon.com
The system SHALL provide a `TournamentService` class in `services/tournament_service.py` that retrieves upcoming Pokémon Champions tournaments from `https://events.pokemon.com/EventLocator/` and returns a list of `Tournament` records (each with `name: str`, `start_date: date`, `end_date: date | None`, `city: str`, `country: str`, `format: str`, optional `url: str | None`). The service SHALL accept `lat: float`, `lon: float`, and `radius_miles: int` parameters with defaults targeting Tenerife (lat ≈ 28.4636, lon ≈ -16.2518, radius=500).

#### Scenario: Live fetch succeeds
- **WHEN** `TournamentService.get_upcoming(lat, lon, radius_miles)` is called and events.pokemon.com returns a parseable response containing Champions/VGC events
- **THEN** it returns a list of `Tournament` records sorted ascending by `start_date`, with all required fields populated

#### Scenario: Live fetch fails
- **WHEN** the request raises `httpx.HTTPError` or returns a non-2xx status
- **THEN** `get_upcoming` returns an empty list and does not raise

#### Scenario: No tournaments in radius
- **WHEN** the live fetch succeeds but the response contains zero matching events
- **THEN** `get_upcoming` returns an empty list

#### Scenario: Format filter
- **WHEN** the response includes events for non-Champions formats (e.g. TCG, Pokémon GO)
- **THEN** only events whose format matches Pokémon VGC / Champions are included in the result

### Requirement: TournamentService caches responses for 12 hours
The system SHALL cache tournament responses to disk for 12 hours using hishel `SyncSqliteStorage` at `pokemon_team_builder/cache/tournaments/`. The cache key SHALL include the lat/lon/radius parameters so different geo queries are cached independently.

#### Scenario: Cache hit
- **WHEN** `get_upcoming` is called with parameters matching a cached entry within TTL
- **THEN** no HTTP request is made and the cached list is returned

#### Scenario: Cache miss for new geo parameters
- **WHEN** `get_upcoming` is called with parameters that have never been queried (or whose TTL expired)
- **THEN** an HTTP GET is made to events.pokemon.com and the response is stored in the cache under those parameters

### Requirement: GET /tournaments endpoint
The system SHALL expose `GET /tournaments` accepting optional `lat`, `lon`, and `radius` query parameters (defaults: Tenerife coordinates, radius=500 miles). The endpoint SHALL return `{"tournaments": list[TournamentOut], "stale": bool}` where `stale` is `true` only when the underlying scrape failed and the response is the empty fallback. The endpoint SHALL NEVER return 5xx for upstream scraping failures.

#### Scenario: Default geo parameters
- **WHEN** a client calls `GET /tournaments` without query parameters
- **THEN** the service is called with the Tenerife defaults and the response includes the matching events

#### Scenario: Custom geo parameters
- **WHEN** a client calls `GET /tournaments?lat=40.4168&lon=-3.7038&radius=200`
- **THEN** the service is called with those parameters and the response reflects events near Madrid

#### Scenario: Scrape failure
- **WHEN** the underlying service returns an empty list due to fetch or parse failure
- **THEN** the endpoint returns 200 with `tournaments: []` and `stale: true`

### Requirement: Frontend Tournaments panel
The web frontend SHALL render a collapsible "Torneos Próximos" panel in `index.html`, controlled by a new `tournaments()` Alpine component in `app.js`. The panel SHALL be collapsed by default and SHALL only fetch `/tournaments` the first time it is expanded. Each tournament SHALL render compactly as one row showing date · city/country · format · name, with the row linking to `url` when present.

#### Scenario: Panel expanded for first time
- **WHEN** the user clicks the panel header to expand it
- **AND** no fetch has yet occurred this session
- **THEN** the component fetches `/tournaments` (with default Tenerife geo params) and renders the resulting list ordered by date

#### Scenario: Panel re-toggled in the same session
- **WHEN** the user collapses then re-expands the panel within the same page session
- **THEN** no new HTTP request is made; the previously fetched list is shown

#### Scenario: Stale/empty state
- **WHEN** the API responds with `tournaments: []` and `stale: true`
- **THEN** the panel renders "No hay torneos próximos en tu zona" instead of an empty list

#### Scenario: Tournament with URL
- **WHEN** a tournament item has a non-null `url`
- **THEN** the row is rendered as a link that opens the URL in a new tab (`target="_blank"`, `rel="noopener noreferrer"`)
