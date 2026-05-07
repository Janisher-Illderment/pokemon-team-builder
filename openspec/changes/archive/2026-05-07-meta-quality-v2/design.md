## Context

The team builder currently selects items via role-lookup tables (`_DEFAULT_ITEM_BY_ROLE`) and moves via static type tables (`_STAB_BY_TYPE`, `_COVERAGE_PRIORITY`). Both are role-heuristics with no knowledge of actual competitive usage. The result is predictable but weak — competitive players immediately notice items like Scope Lens or Shell Bell that almost nobody runs.

MunchStats (https://munchstats.com/) aggregates Pokémon Showdown usage stats into a per-pokémon JSON endpoint. The format closest to Champions Regulation M-A is VGC Gen 9, which shares the same Pokémon pool, moves, and most items. The Champions-specific format (`gen9championsvgc2026regmabo3`) may or may not be tracked yet (game launched April 2026).

Frontend currently exposes moves/roles/item only — `sp_distribution` exists in the domain model but was never wired to `MemberOut` or rendered.

Team presets are pure frontend work — no backend state needed.

## Goals / Non-Goals

**Goals:**
- Items selected from per-pokémon meta data instead of role defaults
- Move selection prefers meta-popular moves the pokémon actually knows
- Beam search gives bonus to meta-frequent teammates of the anchor
- `sp_distribution` and `ev_note` exposed via API and shown in frontend
- Browser-side team save/load (localStorage) with sprites and PokePaste export

**Non-Goals:**
- No new Python packages
- No backend team storage (localStorage only for presets)
- No damage calculator integration
- No Showdown → Champions SP conversion beyond what role templates already do
- No tournament data scraping (labmaus, victoryroad)

## Decisions

### D1: MunchStats format fallback chain
Try `gen9championsvgc2026regmabo3` first; if 404 fall back to `gen9vgc2025regibo3` (the most recent stable VGC format with a large dataset). Cache both results with the same 24 h TTL. **Why**: Champions is new — its Showdown format may have thin data. VGC Gen 9 shares the full Pokémon pool and most competitive items/moves.

### D2: Meta data as advisory, not mandatory
Meta items/moves only override the heuristic when the pokémon actually knows the move or the item is in `_BACKUP_ITEMS ∪ {meta_item}`. The existing Item Clause and `_item_is_activatable` guards remain. **Why**: MunchStats reflects Showdown (no Item Clause, different EV math). Blindly copying a Showdown team would break Champions rules.

### D3: Cache location
`pokemon_team_builder/cache/meta/` directory, one file per `{pokemon_name}.json`. Use hishel with `FileStorage` pointing there (already configured for PokeAPI cache). TTL = 86 400 s. **Why**: hishel is already in the stack and handles conditional revalidation automatically.

### D4: `ev_note` generation at API layer, not domain
`ev_note` is a human-readable string computed in `api/router.py` from `TeamMember.sp_distribution` + `PokemonData.base_stats`. No changes to domain models needed. Formula: identify the two largest SP allocations and explain them in plain Spanish (e.g. "32 Spe para velocidad máxima, 32 Atk para daño"). **Why**: Keeps domain models clean; note is a presentation concern.

### D5: Sprites from Showdown CDN
URL pattern: `https://play.pokemonshowdown.com/sprites/gen5/{name}.png` (lowercase, no special chars). For mega forms: `{name}-mega.png` or `{name}-mega-x.png`. **Why**: Free, stable CDN with broad coverage; already used widely by VGC tools.

### D6: Team presets — Alpine.js component, no new JS files
Add a second Alpine component `savedTeams()` alongside `app()` in `app.js`. Data stored under `localStorage['poke-builder-presets']`. **Why**: Keeps the frontend single-file, no build step needed.

## Risks / Trade-offs

- [MunchStats rate limits / downtime] → All generation falls back to heuristic if meta fetch fails; user never sees an error from this
- [VGC format data diverges from Champions] → Items/moves are directionally correct even if not identical; D2 guards prevent rule violations
- [Showdown sprites not available for a pokémon] → Fallback to text name in preset card; no broken images via `onerror` handler
- [localStorage full] → Cap presets at 20; show warning and block save if at limit

## Open Questions

- None blocking implementation.
