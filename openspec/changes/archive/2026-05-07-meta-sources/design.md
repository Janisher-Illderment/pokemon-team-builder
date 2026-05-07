## Context

The team builder is a single-user web app whose data comes from PokeAPI (legality, base stats, learnsets) and MunchStats (per-pokémon competitive usage). Both are JSON APIs. This change adds two new sources that **only ship HTML**: LabMaus (no public API) and events.pokemon.com (the official Locator only renders client-side HTML/embedded data). Scraping HTML from a Python backend is acceptable for low-volume informational use, but it is fragile by definition — site markup can change without notice.

The existing httpx + hishel stack already handles caching cleanly (`SyncSqliteStorage` for the PokeAPI client). We want the new services to follow the same pattern with their own dedicated cache namespaces, so a stale LabMaus snapshot never invalidates PokeAPI cache and vice versa.

The frontend is single-file vanilla Alpine.js (`web/static/app.js`) with no build step. Adding two more collapsible panels keeps that constraint.

## Goals / Non-Goals

**Goals:**
- Surface the current VGC top teams from LabMaus inside the app, with a one-click path to importing one for analysis.
- Surface upcoming Pokémon Champions tournaments around a configurable geo point so Spanish players see local events first.
- Both features degrade gracefully: if scraping fails, the user sees an empty panel with a friendly note, never an error.
- Keep payload + bandwidth modest: aggressive cache (6 h LabMaus, 12 h tournaments) and lazy fetch (panel must be expanded before any HTTP call fires).
- No new Python packages.

**Non-Goals:**
- No real-time scraping on every page load — cache is mandatory.
- No user-controlled scraping triggers ("refresh now" button) in this change; cache TTL controls freshness.
- No write-back to LabMaus or events.pokemon.com.
- No tournament registration / signup flow — this is read-only display.
- No multi-region tournament search UI — Tenerife default with optional `lat`/`lon` query overrides; richer UI is a follow-up.
- No persisted user preferences for the panels (no remembering "I expanded this last time").

## Decisions

### D1: Stdlib HTML parser, no BeautifulSoup
Use `html.parser.HTMLParser` (or `re` for narrow extractions) to parse LabMaus and events.pokemon.com responses. **Why**: The user explicitly asked for no new packages; stdlib is sufficient because we only need to walk a known structure (team cards, event rows). If the parsing logic becomes unwieldy later, that's the trigger to add `beautifulsoup4`, not now.

### D2: Cache namespaces per source
LabMaus → `pokemon_team_builder/cache/labmaus/` (hishel `SyncSqliteStorage`, TTL=21600s = 6h). Tournaments → `pokemon_team_builder/cache/tournaments/` (hishel `SyncSqliteStorage`, TTL=43200s = 12h). **Why**: Independent invalidation, easy to nuke one without affecting the other or the PokeAPI cache. Mirrors the existing `pokeapi` cache pattern.

### D3: Failure mode = empty list, never 5xx
Both services catch `httpx.HTTPError`, parse failures, and unexpected exceptions, log them, and return `[]`. The endpoints return `200 OK` with `{"teams": []}` or `{"tournaments": []}` plus a `stale: bool` flag indicating whether the response came from a failed live fetch (frontend can show a subtle "no data right now" hint). **Why**: A meta panel that 500s blocks the rest of the UI in users' minds; silent empty state is the right UX for non-critical informational data.

### D4: Pokémon name normalization helper
Add `services/pokemon_lookup.normalize_display_name(raw: str) -> str` that lowercases, strips accents, replaces spaces/special chars (e.g. "Mr. Mime" → "mr-mime", "Tapu Koko" → "tapu-koko", "Flutter Mane" → "flutter-mane"), and strips known LabMaus suffixes (e.g. "(Therian)" → suffix-style name). LabMaus parsing uses this helper before any sprite URL build or `pokemon_lookup.lookup()` call. **Why**: LabMaus team cards display human-readable names that don't always match PokeAPI's slug form; centralizing the conversion keeps the parser focused on HTML and avoids duplication with the team presets sprite helper from `meta-quality-v2`.

### D5: LabMaus parser is structural, not visual
Find team blocks by stable structural cues (e.g. `class="team-card"` or whatever the actual markup uses — to be confirmed during implementation by inspecting the live page once). For each block, extract the pokémon names from `<img alt="...">` or text nodes; item and moves are best-effort (parser returns `None` for those fields if not present in the markup). **Why**: Visual selectors (CSS classes that look layout-related, e.g. `mt-4`) break on every redesign; structural and semantic selectors survive longer.

### D6: events.pokemon.com query parameters
The Locator accepts `latitude`, `longitude`, `range_miles`, and a product/format filter. Default to Tenerife (lat ≈ 28.4636, lon ≈ -16.2518), `range_miles=500`, format = Champions/VGC. Endpoint accepts overrides: `GET /tournaments?lat=...&lon=...&radius=...`. **Why**: Spanish-default for the user but configurable for anyone else who lands on the app. Wide radius makes sense in a low-density region.

### D7: Frontend lazy fetch + collapsed default
Both panels render with `x-show="open"`, default `open=false`. The fetch happens on the first time `open` becomes `true` (use a `loaded` flag to avoid re-fetch on every toggle). Subsequent toggles within the same page session reuse the in-memory result. **Why**: Avoids drive-by HTTP traffic for users who never look at these panels, and matches user-stated requirement.

### D8: Importar button — PokePaste preferred, name fallback
If LabMaus parser returns a usable PokePaste blob (full team with moves/items/natures), the Importar button POSTs it to the existing import flow (or pastes into the import textarea — depends on what the import endpoint looks like at implementation time). If only names are available, the button pre-fills the anchor field with the team's lead and lets the user generate from there. **Why**: Two-tier fallback maximizes the feature's usefulness across LabMaus markup variations.

## Risks / Trade-offs

- **LabMaus markup change** → parser returns empty list; users see "no data right now"; we ship a fix in a follow-up. Tests use a fixture HTML file so we know when our parser regresses against a known-good snapshot.
- **events.pokemon.com Cloudflare / bot protection** → if scraping is blocked we ship the empty panel and re-evaluate (could fall back to manually curated JSON, but out of scope here).
- **Aggressive cache hides fresh data** → 6 h / 12 h TTLs are deliberate; users who want real-time refresh need to wait or we add a manual refresh button in a later change.
- **Pokémon name normalization edge cases** → forms like Urshifu-Single-Strike, Calyrex-Ice/Shadow, Indeedee-F, Ogerpon-Wellspring etc. will need explicit mappings or a robust slug rule. Tests cover the cases we know about; unknown forms degrade to "sprite not found, name shown as text".
- **Legal/ToS** → Both sites are publicly accessible; we send a polite User-Agent identifying the app, respect robots.txt, and cap request frequency via cache. No login bypass, no commercial redistribution.

## Open Questions

- None blocking — implementation will resolve the exact LabMaus selectors against the live page and confirm the events.pokemon.com query format with a one-off curl during task 1.x / 2.x.
