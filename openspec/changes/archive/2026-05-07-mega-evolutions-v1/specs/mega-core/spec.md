# Spec — mega-core

## Requirements

### R1: mega_evolutions.json data file
SHALL contain all 35 mega-eligible species in the 167 pool.
Each entry: form_id, mega_stone (PokePaste canonical), types, ability, stats, verified flag.
Dual-form species (Charizard) stored as array of 2 entries under species key.

#### Scenario: Data integrity
- WHEN file loaded
- THEN every entry has non-null mega_stone, types (1-2), ability, and all 6 stats
- AND every mega_stone is unique across entries (no duplicates)

### R2: MegaForm domain model
SHALL be a dataclass/Pydantic model with: form_id, mega_stone, types, ability, stats (StatBlock), verified.
PokemonData SHALL have `megas: list[MegaForm]` field (empty = not eligible).

### R3: assign_role_with_mega
SHALL exist as a sibling to assign_role in synergy_engine.py.
When mega is None: delegates to assign_role unchanged.
When mega provided: uses mega.stats and mega.types for role determination.

#### Scenario: Garchomp mega gets physical_sweeper from mega stats
- WHEN assign_role_with_mega(garchomp, mega_garchomp)
- THEN primary role is physical_sweeper (Atk 170 >> SpA 65)

#### Scenario: Non-mega path unchanged
- WHEN assign_role_with_mega(pokemon, None)
- THEN result equals assign_role(pokemon)

### R4: _assign_items mega_slot parameter
WHEN mega_slot=(0, "Gengarite") passed:
- THEN items[0] == "Gengarite"
- AND "Gengarite" added to used set (no other slot gets it)
- AND remaining 5 slots assigned normally

### R5: _resolve_mega in generate_team
- choice="off" OR pokemon.megas empty → returns None
- Single form + choice="auto" → returns that form
- Multi-form + choice in ("x","y") → returns matching form
- Multi-form + choice="auto" → raises TeamBuildError with clear message

#### Scenario: Charizard --mega auto raises error
- WHEN _resolve_mega(charizard_data, "auto")
- THEN raises TeamBuildError mentioning "x" and "y"

#### Scenario: Charizard --mega x returns X form
- WHEN _resolve_mega(charizard_data, "x")
- THEN returns MegaForm with form_id ending in "x" and mega_stone "Charizardite X"

### R6: CLI --mega flag
ptb generate <anchor> accepts --mega with choices: auto, off, x, y.
Default: auto.
Passed as mega_choice param to generate_team.

### R7: TeamMember carries mega_form
TeamMember gets optional mega_form: MegaForm | None = None.
replica_exporter reads TeamMember.mega_form.mega_stone as item when set.
base species name unchanged in PokePaste output.

#### Scenario: PokePaste for Mega Gengar
- WHEN anchor=gengar, --mega auto
- THEN PokePaste item line = "Item: Gengarite"
- AND species line = "Gengar" (not "Gengar-Mega")

### R8: Runtime warning for unverified entries
WHEN mega_evolutions.json loaded and any entry has verified=false:
- THEN warning printed to stderr listing unverified species
- AND generation proceeds normally

## Acceptance criteria
- [ ] pytest tests/ -q → all pass (existing + new)
- [ ] Gengar anchor → item = Gengarite, role from mega stats (SpA 170 → special_sweeper)
- [ ] Charizard anchor + --mega x → item = "Charizardite X", types Fire/Dragon
- [ ] Charizard anchor + --mega auto → clear error message
- [ ] Non-mega anchor → item pool unchanged
- [ ] PokePaste species line: base form always (no "-Mega" suffix)
