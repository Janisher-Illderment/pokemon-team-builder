## Why

Players using the team builder have no in-app reference for what is actually winning the current VGC Champions meta, nor visibility into upcoming Pokémon Champions tournaments. Today they leave the app to check sites like LabMaus and events.pokemon.com, then come back and copy lists by hand. Surfacing both signals directly in the UI shortens the loop from "what's winning?" to "let me try it" and gives Spanish players a reason to keep the builder open as their meta dashboard.

## What Changes

- **LabMaus scraping service**: New `services/labmaus_service.py` fetches `https://labmaus.net/teams/top-teams` with httpx, parses the HTML to extract the top 8–10 teams (each with up to 6 pokémon, plus moves/items when LabMaus exposes them) and caches the result for 6 hours via hishel.
- **Tournament scraping service**: New `services/tournament_service.py` fetches `https://events.pokemon.com/EventLocator/` with default geo parameters for Tenerife (configurable), parses upcoming Pokémon Champions tournaments (name, start date, city/country, format) and caches for 12 hours.
- **API endpoints**: `GET /meta-teams?regulation=M-A` returns LabMaus top teams; `GET /tournaments?lat=&lon=&radius=` returns upcoming events. Both endpoints SHALL return `200 OK` with an empty list when scraping fails — never 5xx.
- **Pokémon name normalization**: Extend `services/pokemon_lookup.py` (or add a thin helper) so LabMaus display names map cleanly to the canonical PokeAPI form before sprites/imports are attempted.
- **Frontend — Top Teams panel**: Collapsible "Top Teams del Meta" section in `index.html` rendered by a new `metaTeams()` Alpine component; lazy-fetches `/meta-teams` on first expand; each team card shows 6 sprites and an "Importar" button that either POSTs the PokePaste to the existing import flow or pre-fills the anchor field with the lead.
- **Frontend — Tournaments panel**: Collapsible "Torneos Próximos" section rendered by a new `tournaments()` Alpine component; lazy-fetches `/tournaments` on first expand; renders a compact list (date · city · format · name).

## Capabilities

### New Capabilities

- `labmaus-teams`: Scraped per-day snapshot of LabMaus top VGC teams (top 8–10, up to 6 pokémon each with optional item/moves), 6 h cache, exposed as `GET /meta-teams` and rendered in a collapsible frontend panel with an Importar action per team.
- `tournament-finder`: Scraped list of upcoming Pokémon Champions tournaments around a configurable geo point (Tenerife default), 12 h cache, exposed as `GET /tournaments` and rendered in a collapsible frontend panel.

## Impact

- **New files**: `pokemon_team_builder/services/labmaus_service.py`, `pokemon_team_builder/services/tournament_service.py`, `tests/test_labmaus_service.py`, `tests/test_tournament_service.py`, `pokemon_team_builder/cache/labmaus/`, `pokemon_team_builder/cache/tournaments/`
- **Modified files**: `pokemon_team_builder/api/router.py`, `pokemon_team_builder/api/schemas.py`, `pokemon_team_builder/services/pokemon_lookup.py` (name normalization helper), `pokemon_team_builder/web/static/index.html`, `pokemon_team_builder/web/static/app.js`, `pokemon_team_builder/web/static/style.css`
- **New dependency**: None — `httpx` and `hishel` are already in the stack; HTML parsing uses stdlib `html.parser` (no `beautifulsoup4`)
- **Breaking**: None — new endpoints are additive; existing API consumers unaffected
- **Tests**: 173 currently passing; this change adds at least 2 new test modules covering happy path, scrape failure, cache hit, and name normalization
