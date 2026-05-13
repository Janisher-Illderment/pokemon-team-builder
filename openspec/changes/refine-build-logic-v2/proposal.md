## Why

The current team builder fills roles greedily from a favorite Pokémon outward, with no notion of strategy archetype, no enforcement of "1 mega per team", soft penalties where Champions requires hard constraints (item duplication), and Bo3 scoring built around a "Lead" concept that doesn't match VGC vocabulary (the two openers form a **core**, not a "lead"). Several systems are also flat-out wrong for Champions: the EV system computes against 508 EVs (the standard Pokémon ceiling) when Champions actually allots **66 Stat Points** total; the legal-item pool contains items (Weakness Policy, Throat Spray, Rocky Helmet) that are not in Champions; coverage scoring rewards "having a type X member" instead of "having a STAB attack of type X"; role thresholds are hard cliffs (HP 79 vs threshold 80 → no wall role) instead of gradients; and no scoring component rewards weather-ability synergies (Sand Rush + Sand Stream) that are core to several archetypes.

This change rewrites the build flow to **favorite-first → best-partner → cover-shared-weakness → fill remaining slots**, adds a **Strategy Archetype Selector** that reweights scoring per archetype, adds **Weather Synergy Scoring**, enforces **mega clause** and **item uniqueness** as hard constraints, replaces the EV system with a **66-SP multi-preset** system, fixes coverage to be STAB-based, softens role thresholds into gradients, treats abilities as implicit roles, and renames the Bo3 "Lead" surface to "Core" to match VGC vocabulary.

Several inputs require data verification by Inte before implementation can finalize — those are tagged **[RESEARCH-PENDING]** throughout this proposal and in `tasks.md`.

## What Changes

### Build flow (largest refactor)
- Replace the current greedy role-fill pass with a **favorite-first, partner-first** flow:
  1. Anchor = user's favorite Pokémon.
  2. Pick the **best partner** (slot 2) by max synergy with anchor: complementary types, weaknesses covered, ability/move compatibility, meta presence. This pair forms the **core duo**.
  3. Pick **slot 3** to cover the *shared* weaknesses of the core duo.
  4. Fill slots 4–6 with balance criteria + speed control + weather support if applicable.
- This replaces the current beam-search role-fill from slot 2 onward; the core-duo phase is deterministic per (anchor, archetype), and only slots 4–6 retain beam variation.

### Strategy Archetype Selector (new pre-generation input)
- New `archetype` parameter on `/generate`: `"hyper_offense" | "hard_trick_room" | "bulky_offense" | "weather_based" | "stall" | "balance" | "perish_trap"`.
- Each archetype owns a **weight matrix** that re-scales coverage / role / speed / bulk / cheese-allowance components in `score_team` and `_partial_score`.
- Replaces auto-detection: the user declares intent up front instead of the scorer guessing.

### Weather Synergy Scoring (new component)
- If the favorite has a **weather-dependent ability** (Sand Rush, Swift Swim, Chlorophyll, Slush Rush, Solar Power, etc. — full list **[RESEARCH-PENDING Inte]**), partner pokémon that **set** the matching weather earn a **+3 pt META-weighted bonus**.
- If the synergy is passive (the weather covers a type weakness, boosts a sympathetic STAB, etc., without being ability-gated), the bonus is **+2 pts**.
- Setter list per weather **[RESEARCH-PENDING Inte: legal weather setters in Champions Regulation M-A]**.

### Mega clause — hard constraint
- Beam search and the core-duo phase SHALL reject any team containing more than 1 mega slot. Currently mega support exists (v0.2.0 / PR #6) but the constraint is enforced only by item-uniqueness side-effect; this change makes it explicit.

### Champions item pool — legality + uniqueness
- Remove **Weakness Policy, Throat Spray, Rocky Helmet** from `_DEFAULT_ITEM_BY_ROLE` and `_BACKUP_ITEMS` (not Champions-legal). Full legal-item list **[RESEARCH-PENDING Inte]**.
- Item duplication becomes a **hard rejection** (currently a soft penalty in `_assign_items` / scoring): any variant assembled with two members holding the same item SHALL be discarded before scoring.

### EV system → Champions 66-SP system (full rewrite)
- Replace the existing EV math (508-cap, "504 vs 508" penalty) with **Champions SP math**: 66 total SPs per pokémon. Max per stat **[RESEARCH-PENDING Inte]** (current memory says 32). Nature multiplier mechanics **[RESEARCH-PENDING Inte]** — specifically the existence and exact thresholds of **"nature jumps"** where 1 SP yields +2 final-stat due to rounding.
- Generate **multiple presets per pokémon**, not one fixed spread:
  - **Offensive preset**: optimised to OHKO/2HKO meta pokémon that are weak to this member.
  - **Defensive preset**: optimised to survive named threats that are strong vs this member.
- Spread allocation SHALL consider the equipped item's stat modifier (Choice Band → physical attack ×1.5, Eviolite → defenses ×1.5 for NFE forms, Assault Vest → SpDef ×1.5, etc.) and the nature when choosing where the last SPs go.
- Remove the "504 vs 508" code path entirely.

### Coverage scoring — STAB-based, not typing-based
- Today: type X is "covered" if any team member has type X in `pokemon.types`. **Bug:** Steelix counts as covering Steel-type even without a Steel-type move.
- New rule: type X is covered only if at least one team member has a **STAB move of type X** in their assigned moveset.
- Invariant: every team member with type X SHALL have ≥1 STAB move of type X in slots 1–4 (i.e. STAB is guaranteed before coverage scoring runs). If a member has 2 STABs available, one MAY be sacrificed for coverage.

### Role thresholds — soft borders + ability-as-implicit-role
- Replace hard thresholds (e.g. `HP >= 80 → physical_wall`) with **±15 gradient bands**: a pokémon with HP 79 receives partial physical_wall weight ≈ 0.97; HP 65 receives ≈ 0.0; HP 95 receives 1.0.
- Treat certain abilities as **implicit roles**:
  - Flame Body / Static / Effect Spore → implicit physical_wall (burns/paralyses on contact, reducing incoming physical pressure).
  - Intimidate → implicit physical_wall.
  - Levitate → implicit ground-immunity for coverage scoring.
  - Full ability→role map **[RESEARCH-PENDING Inte]**.

### Speed control — mandatory or penalised
- Every generated team SHOULD contain ≥1 speed-control mechanism (Trick Room, Tailwind, paralysis-inducing move, Icy Wind, Electroweb, Thunder Wave, Glare, Nuzzle, etc.).
- If absent, apply a **−15 pt** scoring penalty and surface a `requires_speed_control: true` flag on the variant for UI visibility.

### Bo3 mode — rename Lead → Core
- `lead_flexibility_score` → `core_flexibility_score` on `VariantOut`.
- `_lead_flexibility_points` → `_core_flexibility_points` in `viability_rater.py`.
- "Lead" string references in `index.html` / `app.js` → "Core". Spanish UI uses "Núcleo".

### Meta data versioning (parche pipeline)
- Extend the existing `legal_pool_mA.json` versioning to **all tunable data files**: `champions_legal_items.json` (new), `weather_setters.json` (new), `weather_dependent_abilities.json` (new), `archetype_weights.json` (new), `nature_jumps.json` (new) **[RESEARCH-PENDING Inte]**. Each file SHALL include a `regulation` field and a `data_version` integer that team generation logs alongside variant output, so a team's provenance is traceable to a specific meta snapshot.

## Capabilities

### New Capabilities

- `favorite-first-build`: New build flow — anchor → best partner → cover shared weakness → fill 4–6. Replaces greedy role-fill from slot 2 onward.
- `strategy-archetype`: Pre-generation archetype selector (`hyper_offense | hard_trick_room | bulky_offense | weather_based | stall | balance | perish_trap`) that re-weights scoring components.
- `weather-synergy-scoring`: Scoring bonus for ability-driven weather pairs (+3 META) and passive weather synergies (+2). Requires weather-ability list and setter list **[RESEARCH-PENDING]**.
- `ev-presets-champions`: Multi-preset SP allocator (offensive + defensive) using 66-SP cap, item-modifier-aware, nature-aware, nature-jump-aware **[RESEARCH-PENDING for thresholds]**.
- `speed-control-required`: Mandatory speed-control check with −15 pt penalty when absent + UI surfacing.

### Modified Capabilities

- `champions-item-pool`: Remove non-legal items (Weakness Policy, Throat Spray, Rocky Helmet); convert duplicate-item from soft penalty to hard rejection. Full legal-item list **[RESEARCH-PENDING]**.
- `role-balance`: Replace hard role thresholds with ±15 gradient bands; add ability-as-implicit-role mapping **[RESEARCH-PENDING for full map]**; enforce mega clause as hard constraint in beam search.
- `bo3-mode`: Rename Lead → Core across schema, scorer, and UI (`lead_flexibility_score` → `core_flexibility_score`, `_lead_flexibility_points` → `_core_flexibility_points`, UI string "Lead" → "Core" / "Núcleo").
- `coverage-analysis`: Switch from typing-based to STAB-based coverage. Add invariant that every member with type X has ≥1 STAB move of type X.
- `meta-data`: Extend `regulation` + `data_version` headers to all tunable static-data files; log data versions on generated variants.

## Impact

- **Modified files**: `services/team_generator.py` (build flow rewrite), `services/synergy_engine.py` (core-duo scoring + STAB coverage), `services/viability_rater.py` (archetype weights + weather synergy + speed-control penalty + Core rename), `services/sp_optimizer.py` (66-SP system + multi-preset; current name may differ — confirm in implementation), `services/replica_exporter.py` (item legality + uniqueness + Core rename), `services/role_assigner.py` (gradient bands + ability-as-implicit-role), `schemas.py` (`archetype` param, `core_flexibility_score`, preset fields, `requires_speed_control` flag), `api/router.py` (archetype propagation), `web/index.html` + `web/app.js` (archetype selector + Lead→Core rename + preset toggle + speed-control warning).
- **New files**: `pokemon_team_builder/data/champions_legal_items.json`, `data/weather_setters.json`, `data/weather_dependent_abilities.json`, `data/archetype_weights.json`, `data/nature_jumps.json`, `data/ability_implicit_roles.json`, `services/sp_preset_builder.py`, `tests/test_favorite_first_build.py`, `tests/test_archetype_weights.py`, `tests/test_weather_synergy.py`, `tests/test_sp_presets.py`, `tests/test_speed_control_required.py`, `tests/test_coverage_stab.py`, `tests/test_role_gradient.py`.
- **Dependencies**: none new — uses existing `type_chart`, `meta_service`, `pokemon_lookup`, `mega_evolutions.json`.
- **Breaking**:
  - `GenerateRequest` gains required-ish `archetype` field (default `"balance"` to keep existing clients working).
  - `VariantOut.lead_flexibility_score` removed; replaced by `core_flexibility_score`. API consumers SHALL migrate.
  - SP system rewrite invalidates any cached SP spreads emitted under the old 508-EV math.
  - Any item override defaulting to Weakness Policy / Throat Spray / Rocky Helmet SHALL fail validation after legal-item pool change.
- **Out of scope (DEFERRED)**:
  - Behaviour when the favorite Pokémon is absent from MunchStats / meta data — the user explicitly deferred this; partner ranking SHALL fall back to type-synergy-only with no meta multiplier, with a TODO marker for a follow-up change.
  - RNG-based variant diversification — variance comes from `archetype × ev_preset` selection, not from explicit randomness.
  - Beam search tuning (k width, depth) — flow rewrite addresses the greedy fragility, no beam parameter tuning in this change.
  - Items conflict resolution for two pokémon of the same role — solved by the legal-pool + hard uniqueness combination; no further item-priority logic in this change.
