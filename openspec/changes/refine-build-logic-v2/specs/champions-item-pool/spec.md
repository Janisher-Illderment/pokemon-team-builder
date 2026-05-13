## MODIFIED Requirements

### Requirement: Role items are Champions-legal
`_DEFAULT_ITEM_BY_ROLE` SHALL contain only items present in the Pokémon Champions Regulation M-A item pool (~117 items at launch — Champions ships with a curated subset of historical VGC items, not a blacklist of banned items). Weakness Policy, Throat Spray, and Rocky Helmet SHALL be removed from the role map (Inte cross-checked HIGH confidence: Game8 + Serebii + TheGamer + NintendoEverything + Smogon Reg M-A discussion + VideoGamesChronicle all confirm exclusion from the launch pool; no patch through v1.0.3 / 2026-04-23 adds them). Note that **Life Orb is also NOT in the M-A pool** per Smogon community report ("no Lorb"). The legal-items list SHALL be loaded from `data/champions_legal_items.json` (to be populated from Game8 + Serebii cross-reference during data-build phase). Provisional replacements: physical_sweeper → Choice Band, special_sweeper → Choice Specs, physical_wall → Leftovers.

#### Scenario: No removed items emitted
- **WHEN** `_assign_items` is called for any supported role
- **THEN** the returned item is NOT Weakness Policy, Throat Spray, or Rocky Helmet

#### Scenario: All role items present in champions_legal_items.json
- **WHEN** every value in `_DEFAULT_ITEM_BY_ROLE` is checked against `champions_legal_items.json`
- **THEN** every value appears in the file's `items` array

#### Scenario: Role item map sourced from JSON
- **WHEN** the application boots
- **THEN** `_DEFAULT_ITEM_BY_ROLE` is populated from `champions_legal_items.json` with the in-code constant retained only as a fallback if the file is missing

### Requirement: Item Clause enforced as hard rejection
Item duplication across a generated team SHALL be a **hard rejection**, not a scoring penalty. Items are assigned post-beam-search inside `_build_variant`; if `_assign_items` cannot produce 6 distinct legal items for a given beam-state pokémon roster, the variant SHALL be dropped and the next beam state SHALL be tried. `score_team` SHALL NOT receive any variant with duplicate items.

#### Scenario: Variant assembly discards duplicate-item team
- **WHEN** `_build_variant` runs item assignment on a beam-search output and `_assign_items` cannot produce 6 distinct legal items
- **THEN** the variant is dropped and never passed to `score_team`; the orchestrator tries the next beam state

#### Scenario: Item Clause failure on saturated pool
- **WHEN** `_assign_items` cannot assign 6 distinct items because the legal pool is exhausted
- **THEN** `TeamBuildError` is raised with a Spanish message indicating Item Clause violation

#### Scenario: No team output contains duplicate items
- **WHEN** `/generate` returns a successful response
- **THEN** every variant in the response has 6 distinct item values across members

### Requirement: Removed items detection
After this change, the codebase SHALL contain no live references to Weakness Policy, Throat Spray, Rocky Helmet, or Life Orb as default role items (all four excluded from M-A pool). Test fixtures referencing these items SHALL be updated to use legal alternatives.

#### Scenario: Grep yields no live references
- **WHEN** the codebase is grepped for "Weakness Policy", "Throat Spray", "Rocky Helmet", "Life Orb"
- **THEN** the only matches are in MIGRATION.md / changelog entries documenting the removal, not in `services/` or `data/` source

### Requirement: Backup pool guarantees Item Clause for 6 members
`_BACKUP_ITEMS` SHALL contain at least 30 distinct Champions-legal items so that even a team of 6 Pokémon assigned the same primary role can each receive a unique item. Items SHALL be ordered by competitive utility (utility items first, type-boosters last). Backup pool SHALL be loaded from `champions_legal_items.json` filtered to items not already in `_DEFAULT_ITEM_BY_ROLE`.

#### Scenario: Item Clause satisfied for 6 same-role team
- **WHEN** `_assign_items` is called with 6 members all assigned the same primary role
- **THEN** all 6 receive distinct items without raising `TeamBuildError`

#### Scenario: Backup pool sourced from versioned JSON
- **WHEN** `_BACKUP_ITEMS` is built at startup
- **THEN** it is derived from `champions_legal_items.json` minus role-default items, with the same regulation and data_version recorded on `VariantOut.meta_versions.items`

### Requirement: Mega Stones are excluded from item constants
Mega Stones are managed by the Mega Evolution mechanic in Champions and SHALL NOT appear in `_DEFAULT_ITEM_BY_ROLE`, `_FALLBACK_ITEM`, or `_BACKUP_ITEMS`. Mega-stone assignment is the sole responsibility of the mega-evolution path.

#### Scenario: No Mega Stone in any item constant
- **WHEN** all three item constants are inspected
- **THEN** no item name ends with "ite" (e.g., Charizardite X, Lucarionite, Scizorite)

### Requirement: PokePaste import does not silently drop items
Any item string emitted by `_assign_items` SHALL be accepted by PikaChampions and ChampTeams.gg importers without silent removal. The legal-item list in `champions_legal_items.json` is the authority for what those importers accept.

#### Scenario: Generated team imports cleanly in PikaChampions
- **WHEN** `to_pokepaste` is called on a generated `TeamVariant`
- **THEN** every `@ <item>` line uses an item from `champions_legal_items.json`
