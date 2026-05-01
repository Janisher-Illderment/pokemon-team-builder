---
name: ChampTeams.gg / PikaChampions PokePaste format
description: Champions-specific PokePaste variant differs from Showdown — uses SPs line, no IVs
type: reference
---

ChampTeams.gg and PikaChampions accept a PokePaste-like format that is NOT Showdown-native because Pokémon Champions replaced EVs with Stat Points (SPs) and locks IVs to 31.

**Differences from Showdown PokePaste:**
- `EVs:` line replaced by `SPs:` line (max 66 total, max 32 per stat)
- `IVs:` line omitted (always 31)
- `Level:` line omitted (always 50 in Doubles)
- `Tera Type:` included (mechanic active in Champions)
- Nature, Ability, Item, 4 Moves: same as Showdown

**Verification needed before serializer ships:** round-trip a real team exported from ChampTeams.gg → parse → re-serialize → re-import. Document exact spec in `docs/pokepaste-champions-spec.md`.

**How to apply:** When working on `replica-export` capability or any PokePaste parser/serializer in pokemon-team-builder, use `SPs:` not `EVs:`, validate sum ≤ 66 and per-stat ≤ 32, fail clearly on violations. Reference: <https://champteams.gg/> (verify URL when needed).
