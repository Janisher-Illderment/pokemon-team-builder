## Context

`pokemon-team-builder` v0.2.0 currently generates teams via a greedy beam search that fills roles independently from slot 2 onward, with several legacy assumptions inherited from the pre-Champions / standard-Pokémon era:

- **EV math** computes against a 508 cap with a "504 vs 508" penalty — Champions actually uses **66 Stat Points** total, not 508 EVs.
- **Item pool** still contains Weakness Policy, Throat Spray, and Rocky Helmet — items not legal in Champions Regulation M-A.
- **Item duplication** is a *soft penalty* in scoring — Champions enforces Item Clause as a hard rule; soft penalty produces variants that are technically illegal yet score well.
- **Mega clause** is enforced implicitly via item uniqueness — fragile.
- **Coverage scoring** rewards "having a Steel-type member" rather than "having a Steel-type STAB attack" — Steelix without Iron Head currently counts as covering Steel.
- **Role thresholds** are hard cliffs — HP 79 misses the physical_wall threshold at 80 entirely, producing brittle outputs.
- **Bo3 "Lead"** terminology — VGC players call the two openers a **core**, not a "lead". The misnomer leaks across schema, scorer, and UI.
- **No archetype awareness** — Hyper Offense and Hard Trick Room produce the same generation flow; only the scoring weights would differ, but there's nothing to weight against.
- **No weather synergy bonus** — Excadrill+Tyranitar (a defining archetype of competitive doubles) scores no better than two random members.
- **Greedy slot-filling** — the existing flow picks slot 2 to fill a missing role, not to *synergise* with the favorite. The user's intent ("build around my favorite") is structurally not captured.

The user has explicitly accepted that this change is large and disruptive, in exchange for a flow that mirrors how VGC players actually build teams: **favorite → best partner → cover shared weakness → fill the rest with balance criteria**.

Several inputs require Inte to confirm Champions-specific data (legal items, SP cap mechanics, nature jumps, weather-ability list, weather setters, ability→role map). Those are tagged **[RESEARCH-PENDING]** in `tasks.md` and gate the relevant logic tasks.

## Goals / Non-Goals

**Goals**
- Replace greedy role-fill with **favorite-first → best-partner → cover-shared-weakness → fill 4–6**.
- Allow users to declare a **strategy archetype** up front; the scorer honors that intent rather than guessing.
- Add **weather synergy scoring** as a first-class scoring component.
- Enforce **mega clause** and **item uniqueness** as hard constraints, not penalties.
- Replace EV math with **Champions 66-SP** system. Generate **multiple SP presets per member** (offensive + defensive).
- Fix **coverage** to be STAB-based (the move type, not the member type).
- Replace **hard role thresholds** with ±15 gradient bands.
- Treat certain **abilities as implicit roles** (Flame Body → partial physical_wall, etc.).
- Mandate **speed control** (or flag its absence) with a meaningful scoring penalty.
- Rename the Bo3 surface from **Lead → Core** to match VGC vocabulary.
- Version all tunable static-data files so a generated team's data provenance is traceable.

**Non-Goals**
- No team simulator / damage calculator integration in this change.
- No automatic detection of the user's preferred archetype — the user declares it explicitly.
- No support for users whose favorite Pokémon is absent from MunchStats meta data — **DEFERRED** per user direction. Partner ranking falls back to type-synergy only.
- No RNG-based variant diversification — variance comes from `archetype × ev_preset` selection, not random seeds.
- No tuning of beam search width / depth parameters; the flow refactor handles the greedy fragility.
- No two-pokémon-same-role item priority logic; the combination of legal-item pool + hard uniqueness already resolves it.

## Decisions

### D1: Favorite-first build flow replaces greedy slot fill

**Decision.** Generation runs in four phases:
1. `anchor = favorite_pokemon`.
2. `partner = best_partner(anchor, archetype)` — pure function over `(anchor, archetype, legal_pool, meta_data)`, returns the single best partner. Together, anchor + partner = **core duo**.
3. `slot3 = best_coverage_for_shared_weakness(core_duo, archetype, legal_pool)`.
4. `slots 4..6 = beam_search(seed=[anchor, partner, slot3], archetype, ...)`.

**Why.** The current flow expresses "give me a balanced team that contains my favorite," but the user wants "build the best possible team **around** my favorite." The structural difference is that slot 2 must be picked **for its synergy with slot 1**, not to fill an open role. Greedy role-fill cannot express that.

Beam search is retained only for slots 4–6 because at that point most synergy constraints are locked and the search problem collapses back to "balance the remaining roles" — exactly what beam search is good at.

### D2: Strategy Archetype Selector as a pre-generation input

**Decision.** The user supplies `archetype` on `/generate` from a 7-element enum (`hyper_offense | hard_trick_room | bulky_offense | weather_based | stall | balance | perish_trap`). Each archetype owns a weight matrix that re-scales scoring components. Default = `balance` for backward compatibility.

**Why not auto-detect?** We considered inferring archetype from the favorite's stats and ability:
- Pros: zero user friction.
- Cons: ambiguous favorites (Garchomp can anchor hyper_offense OR weather_based OR balance — all three are real teams), and incorrect inference would silently produce a wrong team. The cost of asking the user one question is much lower than the cost of silently building the wrong archetype.

The archetype matrix lives in `archetype_weights.json` so it can be tuned without code changes — important because the relative weights of (coverage / role / speed / bulk / cheese_allowance / weather_synergy) per archetype are inherently subjective and will need adjustment after user testing.

### D3: Weather Synergy Scoring split into ability-driven and passive

**Decision.** Two distinct bonuses:
- **+3 META-weighted** when a member has a weather-dependent ability AND a teammate sets the matching weather. This is the canonical Excadrill+Tyranitar case.
- **+2** when the synergy is passive — the weather covers a member's type weakness, boosts a sympathetic STAB (e.g. Hurricane in Rain), or empowers a Solar-Beam'er without ability gating.

**Why two tiers?** Ability-gated synergy is a hard binding (Sand Rush is useless without Sand). Passive synergy is opportunistic (Hurricane in Rain is better than in Sun but works in any). Collapsing them into one weight understates the importance of the ability-gated case. We weight the ability-gated case higher because it's load-bearing for the entire archetype.

### D4: Mega clause as hard constraint, not soft penalty

**Decision.** Beam search and the core-duo phase SHALL reject any partial team with > 1 mega-stone holder. This is a structural prune, not a score reduction.

**Why.** Champions allows exactly one mega per team. A "scored low but technically illegal" output is worse than no output. Hard pruning also reduces beam-search branching factor, making generation faster.

### D5: Item uniqueness as hard rejection

**Decision.** Item Clause becomes a hard constraint in `_assign_items` and in beam search. Two members with the same item → variant discarded before scoring.

**Why.** Same reasoning as D4 — a soft-penalty variant that violates Item Clause is illegal output. The current soft-penalty was a defensive measure when the legal-item pool was small; with the corrected legal-item list (§1.1 in `tasks.md`), the pool is large enough that hard uniqueness is feasible.

### D6: EV system rewrite — 66 SPs, multi-preset, item-aware

**Decision.** Drop the 508-EV math entirely. Build SPs against the Champions 66-cap with per-stat max **[RESEARCH-PENDING]** (memory says 32). Generate **two presets per member**:
- `offensive_preset` — optimised to OHKO/2HKO meta pokémon that are *weak to this member*.
- `defensive_preset` — optimised to survive named threats *strong vs this member*.

Item modifiers are baked into the optimisation: Choice Band → physical_attack is already ×1.5 effectively, so the optimiser invests *less* in attack and *more* in speed/bulk. Eviolite NFE → defenses already ×1.5, so the optimiser favours offense. Assault Vest → SpDef already ×1.5, so the optimiser can pour SPs into other defensive stats.

**Nature jumps** — at certain (base_stat, SP, nature) tuples, 1 SP yields +2 final-stat due to rounding through the nature multiplier. The optimiser SHALL hit those thresholds preferentially. **[RESEARCH-PENDING]** for the exact thresholds.

**Why multi-preset?** The user pointed out that one SP spread cannot be both "OHKO weak threats" and "survive strong threats" — the optimisation objectives are in tension. Exposing both presets lets the player pick per-matchup, and contributes to variant variance (each preset selection produces a different export).

### D7: STAB-based coverage with STAB invariant

**Decision.** Type X is covered iff at least one member has a STAB move of type X in their moveset (NOT iff a member has X in `pokemon.types`). To prevent regressions, every member with type X SHALL have ≥1 STAB-X move in slots 1–4. If a member has 2 STAB types AND 2 STAB moves available, exactly one STAB slot MAY be repurposed for coverage.

**Why.** The current bug — Steelix counts as covering Steel without an Iron Head — silently miscounts coverage. The fix is mechanically simple but requires a STAB-presence invariant to avoid the opposite failure (selecting a moveset that drops STAB entirely in favor of coverage moves).

### D8: Soft role thresholds (±15 gradient) + ability-as-implicit-role

**Decision.** Each stat-based role gets a 30-point band centered on its current threshold: weight 0 at `threshold − 15`, weight 1.0 at `threshold + 15`, linear in between. Abilities like Flame Body, Intimidate, Magic Bounce, Sturdy, etc., contribute partial weight to specific roles via `ability_implicit_roles.json`.

**Why soft.** Hard cliffs at exactly the threshold (HP 80 for physical_wall) produce brittle outputs: a stat one point under the threshold loses the role entirely. The gradient gives the scorer the information it needs without forcing arbitrary tie-breaks. We considered keeping hard thresholds with a wider band (e.g. `>= 70`) but that just moves the cliff — the gradient is the right answer.

**Why abilities as implicit roles.** Flame Body's 30% burn-on-contact reduces effective incoming physical pressure ≈ 15% across the game; that's a real wall property the current scorer ignores entirely. Modelling it as partial role weight is a clean way to surface ability value without a separate scoring component.

### D9: Speed control mandatory, scored as penalty when absent

**Decision.** Every generated team (except `stall` archetype) SHALL include ≥1 speed-control mechanism. Absence = −15 pt penalty + `requires_speed_control: true` flag on `VariantOut`. The detection set spans moves (Trick Room, Tailwind, Icy Wind, Electroweb, paralysis-inducers, Sticky Web) and abilities (Static, Cute Charm contribute partial credit via §10.1 list).

**Why penalty, not hard reject?** The user said "preferiblemente debe tener al menos 1" — strongly preferred but not absolute. A team built around a Drought + Solar Power abuser can be viable without explicit speed control if the offense is overwhelming. The flag allows users to make an informed call.

### D10: Bo3 "Lead" → "Core" rename

**Decision.** Rename `lead_flexibility_score` → `core_flexibility_score`, `_lead_flexibility_points` → `_core_flexibility_points`, UI strings "Lead" → "Core" / "Núcleo".

**Why.** "Lead" in VGC means the *first two pokémon on the field*, i.e. the core duo. Calling our flexibility score "Lead" implies it's about who leads game 1; it's actually about how many viable openers the team has across the Bo3 set. "Core" is the term VGC players use. The rename is BREAKING for API consumers — flagged explicitly in `tasks.md` §13.3.

### D11: Versioned data files for parche pipeline

**Decision.** Every tunable static data file gains `regulation` + `data_version` headers. `VariantOut` echoes `meta_versions: {...}` so a generated team's data provenance is traceable. When Champions parches, bumping `data_version` makes it explicit that the regenerated team uses the new meta.

**Why.** Without versioning, the user cannot tell whether a team was generated under pre-patch or post-patch data. Versioned files also unlock a future "rebuild this team under the latest meta" workflow.

## Tradeoffs and decisions

### Why favorite-first over greedy

| Aspect | Greedy (current) | Favorite-first (proposed) |
|---|---|---|
| Captures user intent ("build around X") | Indirectly — X is one of 6, no preference | Directly — X anchors, partner picked for X |
| Slot 2 selection | Best role-fill regardless of slot 1 | Best synergy with slot 1 |
| Beam fragility | High — single bad early pick propagates | Lower — first 3 slots are deterministic |
| Determinism | Yes per seed | Yes per (anchor, archetype) |
| Implementation cost | n/a (baseline) | Medium — new partner/coverage modules |
| Risk of regression | n/a | Anchor's role coverage may need explicit handling in slots 4–6 |

Greedy's strength is *balance*; favorite-first's strength is *intent capture*. The user's complaint is that greedy doesn't express what they're trying to do. Beam search is retained for slots 4–6 to preserve greedy's balance virtues where they matter.

### Why archetype selector over auto-detection

| Aspect | Auto-detect | User-selected |
|---|---|---|
| User friction | Zero | One choice (7 options) |
| Ambiguity tolerance | Low — guesses for ambiguous favorites | None — user resolves ambiguity |
| Bad-output cost | High — silent wrong archetype | Low — wrong selection is the user's call |
| Testability | Hard — depends on inference correctness | Easy — input is explicit |
| Future tuning | Inference logic changes are risky | Weight matrix changes are isolated |

The user explicitly framed archetype as **input to scoring weight**, not as something the system should figure out. Auto-detection adds inference risk without removing meaningful user friction.

### Why soft borders over hard cliff

| Aspect | Hard threshold | ±15 gradient |
|---|---|---|
| Brittleness at boundary | High — HP 79 vs 80 swings the whole role | Low — score moves smoothly |
| Implementation cost | n/a (current) | Low — single function change + propagate weight |
| Downstream complexity | Roles are bool sets | Roles are weighted (list of (role, weight)) |
| Captures "almost a wall" | No | Yes |
| Risk of over-assignment | n/a | Members can have many partial roles — needs threshold≥0.5 in boolean consumers |

The downstream-complexity cost is real (every consumer of `pokemon.roles` needs updating), but the brittleness fix is worth it. We mitigate by introducing a convention: `weight ≥ 0.5` = "has the role" in boolean contexts.

### Why hard item-uniqueness over soft penalty

Item Clause is a rule of the game, not a preference. A team violating Item Clause cannot legally be entered into a tournament. Scoring a violating team as "lower but acceptable" produces output that fails its primary use case (importable to PikaChampions / ChampTeams.gg). Hard rejection is the only correct enforcement.

### Why multi-preset over single SP spread

The user's framing: one preset cannot simultaneously OHKO weak threats AND survive strong threats. The optimisations are antagonistic. Choosing one preset per member is a tactical decision the player makes per-matchup. Exposing both in the variant output:
- Lets the player pick based on their expected opponent.
- Provides variance between variants (different preset choices = different exported teams).
- Is the natural answer to "more variation" without resorting to RNG.

## Risks / Trade-offs

- **[Research blockers]** Sections §3, §4, §8, §9 of `tasks.md` are gated on Inte data. Generation logic for those capabilities cannot be implemented correctly without confirmed legal-item list, SP mechanics, weather ability list, and ability→role map. Mitigation: parallelise §1 with §2 (data file scaffolding can land empty and be filled in later).
- **[Breaking API changes]** `lead_flexibility_score` removal + new required-ish `archetype` field. UI clients SHALL migrate. Mitigation: `archetype` defaults to `balance` so callers omitting it get sane behaviour; rename is documented in MIGRATION.md.
- **[Soft borders cascade]** Switching `pokemon.roles` from `list[str]` to weighted form touches every role consumer. Mitigation: keep a `pokemon.role_strings` derived view (roles where weight ≥ 0.5) for callers that don't need weights.
- **[Multi-preset complexity]** Two SP spreads per member doubles the SP-preset payload and complicates the exporter. Mitigation: default export uses `offensive_preset`; defensive is opt-in via UI toggle.
- **[Nature jumps research]** If nature-jump thresholds turn out to be non-deterministic or game-version-dependent, the optimisation falls back to plain SP allocation; jump-targeting becomes a future enhancement.
- **[Favorite-not-in-meta]** Explicitly **DEFERRED**. Partner ranking falls back to type-synergy only with no meta multiplier; a TODO marker is added for the follow-up change.
- **[Archetype matrix calibration]** The seven weight matrices in `archetype_weights.json` are initial guesses. Real calibration requires user-testing against generated outputs. Mitigation: matrix lives in JSON so it can be tuned without code changes; treat first-version weights as a baseline.

## Open Questions

The following items are flagged in `tasks.md` and proposal.md as **[RESEARCH-PENDING]**; they MUST be resolved by Inte before the corresponding implementation tasks begin:

1. **Complete Champions legal-item list (Regulation M-A)** — required for §2.1, §3.
2. **Champions SP cap mechanics** — total cap (66 likely confirmed), max per stat, final-stat formula, nature-jump thresholds. Required for §2.5, §9.
3. **Weather-dependent ability list** — required for §2.2, §8.
4. **Weather-setter list per weather type (Champions Regulation M-A)** — required for §2.3, §8.
5. **Ability→implicit-role mapping** — required for §2.6, §4.3.

Deferred (explicitly out of scope):

- **Favorite Pokémon not in MunchStats data** — user said "perfilar después, buscar alternativas." Documented for a follow-up change.
