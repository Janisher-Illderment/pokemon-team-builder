---
name: pokemon-team-builder project
description: CLI tool for Pokémon Champions team building (Regulation M-A); Python/Click/SQLite stack mirroring mtg-wizard pattern
type: project
---

`pokemon-team-builder` is a Python CLI that takes a favorite Pokémon and generates a 6-Pokémon team compatible with Pokémon Champions (F2P Switch game launched April 2026).

**Game ruleset (Regulation M-A):**
- Doubles, Pick 4 of 6 format
- ~263 legal Pokémon (no legendaries / Paradox / Treasures of Ruin)
- IVs locked to 31; Stat Points (SPs) replace EVs: max 66 per Pokémon, max 32 per stat
- Item Clause + Species Clause active
- Export target: PikaChampions / ChampTeams.gg PokePaste variant (NOT Showdown native)

**Why:** User builds tooling around competitive games (also has mtg-wizard for MTG Commander). Champions is a fresh competitive scene; existing Showdown ecosystem doesn't fit because EVs/IVs system replaced.

**How to apply:**
- Stack mirrors mtg-wizard: Python 3.11 + Click + Rich + SQLite + pytest, layered as `config → data → service → CLI`.
- 5 capabilities specified in OpenSpec: pokemon-lookup, synergy-engine, team-generator, viability-rater, replica-export.
- Architecture decisions delivered 2026-05-01 in conversation; key choices:
  - SQLite cache + JSON static (champions_legal_pool.json, doubles_roles.json, type_chart.json)
  - httpx + hishel (sync) for PokéAPI (no async — overkill for this scale)
  - Beam search 3-phase for team generation (filter → beam k=10 → re-rank); rejected exhaustive (9.6B combos) and ILP (overkill v1)
  - Rule-based SP optimizer with role templates (rejected LP — function objective is subjective)
  - PokePaste variant uses custom `SPs:` line, omits IVs (always 31)
- v1 explicitly defers: async, optimization libraries (OR-Tools), GA/CMA-ES, usage-stats-driven viability rating.
- Open decisions left for user: uv vs pip, viability-rater scope in v1, exact ChampTeams.gg paste format (needs round-trip verification).
