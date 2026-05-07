## ADDED Requirements

### Requirement: Import endpoint accepts a PokePaste body
The API SHALL expose `POST /import` that accepts a JSON body `{"pokepaste": "<string>"}` containing a Showdown-format PokePaste with exactly 6 member blocks separated by blank lines, parses it into a `TeamVariant`, scores it, and returns the analysis as a `VariantOut`.

#### Scenario: Valid 6-member PokePaste returns analysis
- **WHEN** `POST /import` is called with a body whose `pokepaste` field contains 6 valid blocks (anchor + 5 partners) for legal M-A Pokemon
- **THEN** response status is 200 and the body contains `score`, `score_explanation`, `members` (length 6), `pokepaste` (re-serialized) and `recommended` (always `true` for an imported team)

#### Scenario: Empty body returns 422
- **WHEN** `POST /import` is called with `{}` or with `pokepaste = ""`
- **THEN** response status is 422 with a message stating the field is required

### Requirement: Parser tolerates Showdown block layout
The parser SHALL accept the standard Showdown layout for each member:
```
<Species> @ <Item>
Ability: <Ability>
Level: 50
EVs: <ev list>
<Nature> Nature
- <Move 1>
- <Move 2>
- <Move 3>
- <Move 4>
```
Lines other than the species line MAY appear in any order. Unknown lines (`Shiny: Yes`, `Tera Type: <T>`, `IVs: ...`, `Happiness: <n>`) SHALL be ignored. Blocks SHALL be separated by one or more blank lines. Trailing whitespace and CRLF line endings SHALL be tolerated.

#### Scenario: Order of metadata lines does not matter
- **WHEN** a block places `EVs:` before `Ability:` and the `<Nature> Nature` line at the end of the metadata
- **THEN** the resulting `TeamMember` has the correct ability, EVs and nature

#### Scenario: Unknown metadata lines are ignored
- **WHEN** a block contains lines like `Shiny: Yes`, `Tera Type: Ground`, `IVs: 0 Atk`
- **THEN** parsing succeeds and those lines do not appear in the resulting member

#### Scenario: CRLF line endings are accepted
- **WHEN** the input PokePaste uses `\r\n` line endings
- **THEN** the parser succeeds with the same result as `\n` endings

#### Scenario: Multiple blank lines between blocks are accepted
- **WHEN** blocks are separated by two or more blank lines
- **THEN** the parser still produces 6 members

### Requirement: Item parsing
The species line SHALL be parsed as `<Species> @ <Item>`. If `@` is absent, the member SHALL be assigned `item == ""` and a warning SHALL be added to `import_warnings` naming the member.

#### Scenario: Species and item are parsed
- **WHEN** the species line is `Garchomp @ Life Orb`
- **THEN** the resulting member has `pokemon.name == "garchomp"` and `item == "Life Orb"`

#### Scenario: No item is tolerated with a warning
- **WHEN** the species line is `Garchomp` (no `@`)
- **THEN** the member is created with `item == ""` and `import_warnings` includes a string mentioning the member's name

### Requirement: EV-to-SP conversion
The `EVs:` line SHALL be parsed as a slash-separated list `<value> <stat> [/ <value> <stat> ...]` where stat is one of `HP|Atk|Def|SpA|SpD|Spe`. Each value is converted to SP via `sp = min(MAX_SP_STAT, value // 8)`. Stats not present default to 0. After per-stat clamp, if the SP total exceeds `MAX_SP_TOTAL`, SP values SHALL be reduced (largest first) until the total fits.

#### Scenario: Standard 252/252/4 spread converts correctly
- **WHEN** the EV line is `EVs: 252 Atk / 4 HP / 252 Spe`
- **THEN** the resulting `SPDistribution` has `atk=31`, `hp=0`, `spe=31` (and others 0), with total 62 (≤ 66)

#### Scenario: Single stat at 32 EVs converts to 4 SP
- **WHEN** the EV line is `EVs: 32 Def`
- **THEN** the resulting distribution has `def_=4` and the rest 0

#### Scenario: No EV line yields all-zero SPs
- **WHEN** the block does not include an `EVs:` line
- **THEN** the resulting distribution has all stats equal to 0

#### Scenario: Per-stat values above 256 are clamped
- **WHEN** an EV line includes a stat value above 256 (defensive case, not produced by Showdown)
- **THEN** the per-stat SP is clamped to `MAX_SP_STAT` (32) and a warning is added to `import_warnings`

### Requirement: Move parsing and validation
The four `- <Move>` lines SHALL be parsed as ordered moves. Move names SHALL be normalized to lowercase-hyphenated slugs (e.g. `Stone Edge` → `stone-edge`). If a parsed move is not in the resolved Pokemon's `move_names`, the move SHALL be retained as-is in the member, AND a warning SHALL be added to `import_warnings` naming the move and the Pokemon. If fewer than 4 move lines are present, the missing slots SHALL be filled with `tackle` and a warning SHALL be added.

#### Scenario: Standard 4 moves parse correctly
- **WHEN** the block has lines `- Earthquake`, `- Dragon Claw`, `- Stone Edge`, `- Protect`
- **THEN** the resulting member's `moves == ["earthquake", "dragon-claw", "stone-edge", "protect"]`

#### Scenario: Move not in the Pokemon's pool produces a warning
- **WHEN** a Garchomp block lists `- Hydro Pump` (not in its move pool)
- **THEN** the member is created with `hydro-pump` in `moves` AND `import_warnings` contains a string naming Garchomp and Hydro Pump

#### Scenario: Fewer than 4 moves are padded
- **WHEN** a block has only 2 move lines
- **THEN** the member has 4 moves (the original two plus `tackle` twice or with deduplication best-effort) and `import_warnings` contains a padding notice for that member

### Requirement: Mega form detection
If a species line names a Mega form (`Charizard-Mega-X`, `Charizard-Mega-Y`, `Garchomp-Mega`, etc.), the parser SHALL strip the `-mega(-x|-y)?` suffix, resolve the base form via `pokemon_lookup`, and attach the corresponding `MegaForm` (loaded via `mega_loader`) to the resulting `TeamMember.mega_form`. The held item SHALL be set to the species' Mega Stone overriding the parsed `@ <Item>` value.

#### Scenario: Mega-X form is mapped to base + mega form
- **WHEN** a block starts with `Charizard-Mega-X @ Charizardite X`
- **THEN** the resulting member has `pokemon.name == "charizard"`, `mega_form.form_id == "charizard-mega-x"` and `item == "Charizardite X"`

#### Scenario: Mega Stone is auto-set even if @ Item is generic
- **WHEN** a block starts with `Garchomp-Mega @ Life Orb`
- **THEN** the resulting member has `mega_form.form_id == "garchomp-mega"` and `item == "Garchompite"` (the canonical Mega Stone)

### Requirement: Hard rejections produce 422
The endpoint SHALL reject the import with HTTP 422 in the following cases, with a human-readable Spanish message:

#### Scenario: Fewer than 6 members
- **WHEN** the PokePaste contains 1 to 5 valid blocks
- **THEN** response status is 422 with a message stating the team must have exactly 6 members and naming the count received

#### Scenario: More than 6 members
- **WHEN** the PokePaste contains 7 or more blocks
- **THEN** response status is 422 with a message stating the limit is 6

#### Scenario: Pokemon not in M-A legal pool
- **WHEN** any species line names a Pokemon not in the M-A legal pool (e.g. `Dragapult`)
- **THEN** response status is 422 with a message naming the offending Pokemon

#### Scenario: Species cannot be resolved
- **WHEN** any species line names a Pokemon that `pokemon_lookup.lookup` cannot resolve (typo, fictional species)
- **THEN** response status is 422 with a message naming the offending name

#### Scenario: Duplicate species (Species Clause)
- **WHEN** two blocks resolve to the same species
- **THEN** response status is 422 with a message stating the Species Clause conflict

### Requirement: Import response shape
The response SHALL be a JSON object with the same shape as a single `VariantOut` from `/generate`, plus an `import_warnings: list[str]` field. The `pokepaste` field SHALL be the team re-serialized by `replica_exporter.to_pokepaste` (canonical form, not the user's input). The `recommended` field SHALL be `true`.

#### Scenario: Response includes import warnings list
- **WHEN** the import succeeds with non-fatal issues (e.g. moves outside the move pool)
- **THEN** the response body includes `import_warnings` as a list of strings (possibly empty)

#### Scenario: Response PokePaste is canonical
- **WHEN** the input PokePaste has unusual whitespace or stat-line ordering
- **THEN** the response `pokepaste` is the output of `to_pokepaste` over the parsed variant — uniform across all imports

#### Scenario: Score and explanation come from viability_rater
- **WHEN** the import succeeds
- **THEN** `score` equals `viability_rater.score_team(variant)` and `score_explanation` equals `viability_rater.generate_explanation(variant, score)`
