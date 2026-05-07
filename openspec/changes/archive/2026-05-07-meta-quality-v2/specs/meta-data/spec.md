## ADDED Requirements

### Requirement: MetaService fetches per-pokémon usage data from MunchStats
The system SHALL provide a `MetaService` class in `services/meta_service.py` that retrieves competitive usage data for a named pokémon from the MunchStats API. It SHALL try the Champions format first (`gen9championsvgc2026regmabo3`) and fall back to the most recent stable VGC format (`gen9vgc2025regibo3`) if the first returns a 404.

#### Scenario: Champions format available
- **WHEN** `MetaService.get(name)` is called for a pokémon whose Champions format data exists on MunchStats
- **THEN** it returns a `MetaEntry` with `items`, `moves`, and `teammates` populated from the Champions format response

#### Scenario: Champions format 404, VGC fallback
- **WHEN** MunchStats returns 404 for the Champions format URL
- **THEN** `MetaService.get(name)` retries with the VGC fallback format and returns data from that response

#### Scenario: Both formats unavailable
- **WHEN** MunchStats returns non-200 for both format URLs
- **THEN** `MetaService.get(name)` returns `None` without raising an exception

### Requirement: MetaService caches responses for 24 hours
The system SHALL cache MunchStats responses to disk for 24 hours using hishel `FileStorage` at `pokemon_team_builder/cache/meta/`. A pokémon with a cached response SHALL NOT trigger an outbound HTTP request until the TTL expires.

#### Scenario: Cache hit
- **WHEN** `MetaService.get(name)` is called for a pokémon already cached
- **THEN** no HTTP request is made and the cached `MetaEntry` is returned

#### Scenario: Cache miss
- **WHEN** `MetaService.get(name)` is called for an uncached pokémon
- **THEN** an HTTP GET is made to MunchStats and the response is written to cache

### Requirement: Item assignment prefers the pokémon's most-used meta item
When `_assign_items` in `team_generator.py` selects an item for a team member, it SHALL first attempt to use the top-ranked item from `MetaService.get(pokemon_name).items`, subject to Item Clause and `_item_is_activatable` validation. It SHALL fall back to the existing role-based logic when meta data is unavailable or all meta items fail validation.

#### Scenario: Meta item available and valid
- **WHEN** the top meta item for a pokémon passes Item Clause and activatability checks
- **THEN** that item is assigned instead of the role default

#### Scenario: Meta item already taken by another team member (Item Clause)
- **WHEN** the top meta item is already in the `used` set for this team
- **THEN** the system tries the second-ranked meta item, then role-based fallback

#### Scenario: Meta service returns None
- **WHEN** `MetaService.get` returns `None` for a pokémon
- **THEN** item assignment proceeds entirely with existing role-based logic, no exception raised

### Requirement: Move selection prefers meta-popular moves the pokémon knows
`select_moves_for_role` in `replica_exporter.py` SHALL, before consulting static type tables, check whether any of the pokémon's top-3 meta moves (from `MetaService`) intersect with its known `move_names`. Matching moves SHALL be preferred for slots 2–4 when compatible with the role assignment and not already selected.

#### Scenario: Meta move in pool and role-compatible
- **WHEN** a pokémon's top meta move is in its `move_names` and fits the STAB/coverage role for its slot
- **THEN** that move is selected for the slot in preference to the static table entry

#### Scenario: Meta move not in pokémon's move pool
- **WHEN** none of the top-3 meta moves appear in the pokémon's `move_names`
- **THEN** selection falls back to existing static tables without error

### Requirement: Heuristic filter boosts meta teammates of the anchor
`_heuristic_filter` in `team_generator.py` SHALL add a `meta_affinity_bonus` of `+3.0` to the heuristic score of any candidate pokémon that appears in the anchor's `MetaService` teammates list (top 6). If meta data is unavailable the bonus is not applied and scores are unchanged.

#### Scenario: Candidate is a meta teammate
- **WHEN** a candidate pokémon appears in the anchor's top-6 meta teammates list
- **THEN** its heuristic score receives a +3.0 bonus before ranking

#### Scenario: Meta data unavailable for anchor
- **WHEN** `MetaService.get(anchor_name)` returns `None`
- **THEN** `_heuristic_filter` runs unchanged with no bonus applied to any candidate
