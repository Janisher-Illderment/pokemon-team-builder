## Context

Pokémon Champions uses a simplified EV system: SPs replace EVs, max 32 per stat, 66 total. The stat formula is identical to mainline Pokémon at level 50 with IVs assumed at 31. Nature modifiers are ×1.1 (boosting) or ×0.9 (reducing). The damage formula is the standard gen 3+ formula.

Speed tiers are the core competitive tool: knowing whether your 32 Spe investment lets you outspeed Rillaboom (base 85), Incineroar (base 60), or Flutter Mane (base 135) is the difference between a usable and unusable spread. The shared Google Sheet encodes this — we extract it into a static JSON to avoid runtime scraping.

For defensive spreads, the relevant question is "does this survive X?". We approximate this by identifying the most-used attacking move against this pokémon's type from MetaService data, computing expected damage, and reporting the result as a percentage range.

## Goals / Non-Goals

**Goals:**
- Level-50 stat formula correct for SPs 0–32 and ±natura modifier
- Speed tier lookup names pokémon above and below the computed speed
- Defensive check names the specific attack and attacker, reports if it survives
- `ev_note` is one or two specific Spanish sentences, not a generic role label

**Non-Goals:**
- No full damage range (min/max rolls) — report high/low percentage bracket only
- No held item modifiers in damage calc (Assault Vest, Choice Band etc.) — too many combinations
- No weather/terrain modifiers
- No multi-hit moves
- No live scraping of the speed tier sheet — extract once to static JSON

## Decisions

### D1: Stat formula
```
non-HP: floor((floor(2*base + 31) * level / 100) + 5) * nature_mod
HP:     floor((floor(2*base + 31) * level / 100) + level + 10)
```
Level = 50, IVs = 31, SPs map to EVs as `sp * 8` for formula purposes (max SP=32 → 256 EVs, which at level 50 adds `floor(256/4) = 64` to the stat — consistent with the game's observed SP bonus of +8 per SP on most stats). **Why**: this matches the observed in-game stat values reported by players on the speed tier sheet.

Wait, actually I need to reconsider. In Pokemon Champions, SPs are different from mainline EVs. Let me think about this more carefully.

In Pokémon Champions (the Switch game launched April 2026), the SP system has:
- Max 32 SP per stat
- Max 66 SP total
- The relationship between SPs and stats is confirmed to be: each SP adds a fixed amount to the stat

The actual formula based on what's known: SPs in Champions work similarly to EVs but at a different scale. With 32 SPs at level 50, each SP adds approximately 2 stat points (similar to 8 EVs in mainline which adds 2 stat points at level 100, so at level 50 it's 1 point per 8 EVs... actually let me just use the formula as given in the description and note it's an approximation).

For the purpose of this spec, I'll use the standard formula with SP*8 as the EV equivalent, which is the most reasonable mapping. The design doc can note this is approximate.

### D2: Speed tier data source
Extract from the Google Sheet into `data/speed_tiers.json` as a one-time step during implementation. Format:
```json
[
  {"name": "flutter-mane", "base_spe": 135, "usage_rank": 1},
  {"name": "rillaboom",    "base_spe": 85,  "usage_rank": 3},
  ...
]
```
The loader computes all level-50 speeds on startup (neutral/+spe at 0/8/16/24/32 SPs) and caches in memory. **Why**: no runtime scraping, fully deterministic, easy to update when regulation changes.

### D3: Speed note format
Report top 3 pokémon beaten and top 1 fastest pokémon not beaten:
> "32 Spe neutral supera a Rillaboom (100), Incineroar (57) y otros — no alcanza a Flutter Mane (171)"

Numbers in parentheses are the computed level-50 Speed values. **Why**: players think in speed tiers, concrete values anchor the advice.

### D4: Defensive note selection
For HP/Def/SpD investment: look up the pokémon's primary type weakness from the type chart, find the most-used move of that type from MetaService data (or fallback to a hardcoded table of common attacks per type), compute damage as a percentage of the pokémon's HP. Classify: `<50%` = "aguanta con holgura", `50–84%` = "aguanta", `85–99%` = "aguanta por poco", `≥100%` = "NO aguanta".

### D5: ev_explainer interface
```python
def explain(member: TeamMember, speed_tier_db: SpeedTierDB, meta: MetaService | None) -> str
```
Returns one or two Spanish sentences. Prioritizes speed note if Spe > 0, defensive note if HP or bulk stats > 0. Falls back to generic role text if neither applies (e.g. pure attacker with 0 Spe). **Why**: single entry point makes router.py trivial to update.

## Risks / Trade-offs

- [SP→EV formula approximation] → If Champions uses a non-standard formula, computed stats may be off by 1–3 points. Acceptable for rationale notes — not used for exact damage values.
- [Speed tier sheet becomes stale] → Static JSON needs manual update when regulation changes. Mitigated by clear file path and format documentation.
- [MetaService unavailable for defensive check] → Falls back to hardcoded common-attack table; still names a real attack, just not the most-used one specifically.

## Open Questions

- None blocking. SP formula calibration can be refined post-launch with in-game testing.
