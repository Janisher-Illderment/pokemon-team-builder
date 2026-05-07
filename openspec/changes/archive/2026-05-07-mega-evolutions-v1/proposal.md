# Proposal — mega-evolutions-v1

## Why
35 of 167 pool Pokémon can Mega Evolve in Champions Regulation M-A.
Current tool ignores this — assigns wrong role (base stats), wrong item (backup pool),
and produces PokePastes that don't trigger Mega Evolution in-game.

## What Changes
- New data file: `mega_evolutions.json` (35 species, 37 forms including Charizard X/Y)
- Role assignment uses mega stats when anchor mega-evolves
- Mega Stone auto-assigned to item slot; bypasses backup pool
- `--mega {auto,off,x,y}` CLI flag
- At most 1 Mega per team (anchor-only in v1)

## Out of Scope (v1)
- Auto X/Y selection heuristic (v1.2)
- Non-anchor mega teammate (v1.2)
- Mega-aware viability scoring (v1.3)
- Rayquaza (no stone, deferred)

## Impact
- All existing tests: no change (additive code path)
- New tests: ~16-20
- LOC: ~500-700
