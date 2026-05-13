> Tasks are ordered by dependency: **research → static data → core logic → API/UI → tests**.
> Sections 1–2 unblock the rest. Sections 3–9 may proceed in parallel once their data inputs exist.
> Tags: **[RESEARCH-PENDING]** = blocked on Inte data; **[DEFERRED]** = out of scope per user.

## 1. Research (Inte) — blockers for static-data and logic tasks

- [x] 1.1 **RESOLVED (Inte v2 cross-check, HIGH confidence)** Weakness Policy, Throat Spray, Rocky Helmet, **and Life Orb** confirmed NOT in M-A item pool. Champions ships with curated ~117-item subset, not a blacklist. Sources: Game8, Serebii, TheGamer, NintendoEverything, Smogon Reg-M-A discussion, VideoGamesChronicle. Inte v1 was wrong (used pre-launch Victory Road/Dexerto/Pokémon-Zone data).
- [ ] 1.1b **PENDING (data-build phase)** Cross-reference Game8 + Serebii M-A item pages to produce canonical list of ~117 legal items with category tags (`competitive`, `type_boost`, `consumable`, `mega_stone`, etc.) for `champions_legal_items.json`.
- [x] 1.2 **RESOLVED (Inte v1, HIGH confidence)** SP cap = 66 total, **32 max per stat**. 1 SP = 8 legacy EVs. Sources: Victory Road, Centro Leaks, Switchblade SP guide.
- [x] 1.2b **RESOLVED (Inte v1 + user decision)** No public nature-jump threshold table exists — they are pokémon-specific. Implementation MUST compute jumps programmatically using the canonical stat formula `floor((floor((2×base + IV + floor(EV/4)) × level / 100) + 5) × nature_mult)`. NO `nature_jumps.json` static file.
- [x] 1.3 **RESOLVED (Inte v1, HIGH confidence)** Weather-dependent abilities by weather: Sun → Chlorophyll, Solar Power, Leaf Guard, Flower Gift, Orichalcum Pulse, Protosynthesis, Harvest. Rain → Swift Swim, Dry Skin, Hydration, Rain Dish. Sand → Sand Rush, Sand Force, Sand Veil. Snow → Slush Rush, Ice Body, Snow Cloak, Ice Face. Sources: Bulbapedia, StrataDex, Game8.
- [x] 1.4 **RESOLVED (Inte v1, HIGH confidence)** Ability setters in Champions: Sun → Torkoal (Drought). Rain → Pelipper (Drizzle). Sand → Tyranitar, Hippowdon (Sand Stream). Snow → Ninetales-Alola, Abomasnow, Mega-Froslass (Snow Warning). Move setters (Sunny Day / Rain Dance / Sandstorm / Snowscape) exist but are secondary.
- [ ] 1.5 **[RESEARCH-PENDING]** Compile ability→implicit-role mapping. Required entries: Flame Body, Static, Effect Spore, Poison Point, Cute Charm → physical_wall partial weight; Intimidate → physical_wall partial weight; Levitate → ground immunity for coverage; Magic Bounce → redirect/lead_support partial; Prankster → lead_support partial; Sturdy → physical_wall partial; Multiscale → physical_wall + special_wall partial; Regenerator → wall partial.
- [ ] 1.6 **[DEFERRED]** Behaviour for favorite Pokémon absent from MunchStats meta data — record decision as a follow-up change, not in this change's scope.

## 2. Static-data files (depend on §1)

- [ ] 2.1 Create `pokemon_team_builder/data/champions_legal_items.json` with schema `{regulation: "mA", data_version: 1, items: [{name, category}]}`. Populate from §1.1.
- [ ] 2.2 Create `pokemon_team_builder/data/weather_dependent_abilities.json` `{regulation, data_version, abilities: {<ability>: {weather: <sun|rain|sand|snow>, effect: <speed|special_attack|defense|...>}}}`. Populate from §1.3.
- [ ] 2.3 Create `pokemon_team_builder/data/weather_setters.json` `{regulation, data_version, setters: {<weather>: {ability_setters: [pokémon names], move_setters: [{move, pokémon names}]}}}`. Populate from §1.4.
- [ ] 2.4 Create `pokemon_team_builder/data/archetype_weights.json` `{regulation, data_version, archetypes: {<archetype>: {coverage, roles, sp, items, speed, bulk, cheese_allowance, weather_synergy}}}`. Define seven archetype weight matrices: `hyper_offense`, `hard_trick_room`, `bulky_offense`, `weather_based`, `stall`, `balance`, `perish_trap`.
- [ ] 2.5 ~~Create `nature_jumps.json`~~ **SKIPPED** — nature jumps computed at runtime per (pokémon, stat, nature) via canonical stat formula. Implementation goes in `services/sp_calc.py` instead of static data (see §7.1).
- [ ] 2.6 Create `pokemon_team_builder/data/ability_implicit_roles.json` `{regulation, data_version, abilities: {<ability>: {role: <role_name>, weight: <0.0..1.0>}}}`. Populate from §1.5.
- [ ] 2.7 Add `data_version` + `regulation` headers to existing `legal_pool_mA.json`, `mega_evolutions.json`, `type_chart.json`, `doubles_roles.json` if not already present.

## 3. capability: `champions-item-pool` (modified) — depends on §2.1

- [ ] 3.1 Remove Weakness Policy from `_DEFAULT_ITEM_BY_ROLE[physical_sweeper]`; replace with a legal alternative (Choice Band or Life Orb pending §1.1).
- [ ] 3.2 Remove Throat Spray from `_DEFAULT_ITEM_BY_ROLE[special_sweeper]`; replace pending §1.1.
- [ ] 3.3 Remove Rocky Helmet from `_DEFAULT_ITEM_BY_ROLE[physical_wall]`; replace pending §1.1.
- [ ] 3.4 Replace hard-coded item constants in `replica_exporter.py` with a loader that reads `champions_legal_items.json`. Existing constants become a fallback only if the JSON is missing.
- [ ] 3.5 Convert item-duplication penalty into hard rejection: in `_assign_items` (or wherever item dedupe lives today), raise `TeamBuildError` on duplicate; in beam search, prune any partial team where two members share an item before scoring.
- [ ] 3.6 Tests: `tests/test_champions_item_pool.py` — none of Weakness Policy / Throat Spray / Rocky Helmet appear in any role default; duplicate-item team raises `TeamBuildError`; loading `champions_legal_items.json` exposes all roles with valid items.

## 4. capability: `role-balance` (modified) — depends on §2.6

- [ ] 4.1 In `assign_role` (or equivalent role-assignment function), replace each hard threshold (e.g. `HP >= 80`) with a gradient: `role_weight = clamp((stat - (threshold - 15)) / 30, 0.0, 1.0)`. Apply to physical_wall, special_wall, physical_sweeper, special_sweeper, trick_room_setter thresholds.
- [ ] 4.2 Update `PokemonData.roles` from `list[str]` to `list[tuple[str, float]]` (or add a parallel `role_weights: dict[str, float]`) so partial role assignments propagate.
- [ ] 4.3 Add ability-as-implicit-role layer: after stat-based role assignment, load `ability_implicit_roles.json` and merge ability-driven role weights into the per-pokémon role map.
- [ ] 4.4 Update all role consumers (`_partial_score`, `_core_flexibility_points`, item assignment, move selection) to use weighted roles where they currently use boolean role membership. Where boolean is still required, treat weight ≥ 0.5 as "has role".
- [ ] 4.5 Make mega clause a hard constraint: in beam-search expansion, reject any partial team where the count of members holding a mega stone (or having `mega_form` assigned) exceeds 1.
- [ ] 4.6 Tests: `tests/test_role_gradient.py` — HP 79 → physical_wall weight ≈ 0.97; HP 65 → 0.0; HP 95 → 1.0; ability=Flame Body bumps physical_wall weight by configured amount; team with 2 mega slots is rejected by beam search.

## 5. capability: `coverage-analysis` (modified) — depends on §4

- [ ] 5.1 Change coverage computation in `synergy_engine.py` (or wherever `_coverage_points` lives) to scan each member's assigned moveset for STAB moves, not `pokemon.types`. A type is covered iff `any(move.type == X and move.type in member.types for member in team for move in member.moves)`.
- [ ] 5.2 Add invariant enforcement in `select_moves_for_role`: every member with type X SHALL have ≥1 move of type X in slots 1–4. If a member has only 1 STAB type available and 2 STAB moves, one slot MAY be repurposed for coverage; if only 1 STAB move exists, it SHALL be in the moveset.
- [ ] 5.3 Tests: `tests/test_coverage_stab.py` — Steelix without Steel-type move does NOT count Steel as covered; same Steelix with Iron Head DOES; mono-type member always has its type as a STAB slot.

## 6. capability: `favorite-first-build` (new) — depends on §4, §5

- [ ] 6.1 Add `services/favorite_first_builder.py` with `build_core_duo(anchor: PokemonData, archetype: str, legal_pool, ...) -> tuple[PokemonData, float]` returning the best partner and the synergy score.
- [ ] 6.2 Implement partner-synergy scoring: complementary type coverage (anchor weaknesses are partner resistances) + shared role coverage avoidance (no double sweeper unless archetype=hyper_offense) + ability/move compatibility (weather pairs, Trick Room setter + slow attacker) + meta presence (MetaService usage weight).
- [ ] 6.3 Implement `cover_shared_weakness(core: list[PokemonData, PokemonData], legal_pool, ...) -> PokemonData` for slot 3, scoring candidates against the **intersection** of core-duo weaknesses (NOT the union).
- [ ] 6.4 Refactor `generate_team()` to call: (a) anchor lookup, (b) `build_core_duo`, (c) `cover_shared_weakness`, (d) existing beam-search for slots 4–6 only. Keep beam search behavior intact for slots 4–6 but seed it with the 3 fixed members.
- [ ] 6.5 Ensure determinism per `(anchor, archetype, format, mega_pref)` tuple; variance comes from `archetype × ev_preset`, not from RNG inside the build flow.
- [ ] 6.6 Tests: `tests/test_favorite_first_build.py` — anchor=Excadrill, archetype=weather_based → partner is Tyranitar (Sand Stream); same call twice → identical output; slot 3 covers core-duo *shared* weaknesses, not just one member's.

## 7. capability: `strategy-archetype` (new) — depends on §2.4

- [ ] 7.1 Add `archetype: Literal["hyper_offense","hard_trick_room","bulky_offense","weather_based","stall","balance","perish_trap"] = "balance"` to `GenerateRequest` in `schemas.py`.
- [ ] 7.2 Load `archetype_weights.json` at startup into `ArchetypeWeights` dataclass; pass weights through `generate_team()` → `_partial_score()` → `score_team()` so all scoring components honor archetype weights.
- [ ] 7.3 In `replica_exporter.select_moves_for_role`, gate cheese-move availability by archetype's `cheese_allowance` weight (e.g. `perish_trap` allows Perish Song, `bulky_offense` does not).
- [ ] 7.4 Add `archetype: str` to `VariantOut` echoing the request value.
- [ ] 7.5 Tests: `tests/test_archetype_weights.py` — hyper_offense team has higher coverage weight than balance; hard_trick_room favours slow members in slot 1–2; perish_trap allows Perish Song while balance does not.

## 8. capability: `weather-synergy-scoring` (new) — depends on §2.2, §2.3

- [ ] 8.1 Add `_weather_synergy_points(members, weather_data) -> float` to `viability_rater.py`. Logic: for each member with a weather-dependent ability, if a teammate sets the matching weather → +3; if no teammate sets it but the weather still aids type coverage / passive bulk → +2; if no synergy → 0.
- [ ] 8.2 Include `weather_synergy` in the archetype weights matrix (§2.4) so `weather_based` archetype amplifies it and `stall` ignores it.
- [ ] 8.3 Tests: `tests/test_weather_synergy.py` — Excadrill + Tyranitar → +3 (Sand Rush + Sand Stream); Excadrill alone → 0; Venusaur (Chlorophyll) + Torkoal (Drought) → +3; Venusaur + Volcarona (Solar Power synergy via type complement) → +2 with no setter.

## 9. capability: `ev-presets-champions` (new) — depends on §2.5, §1.2

- [ ] 9.1 Replace existing SP/EV optimizer with `services/sp_preset_builder.py` exposing `build_presets(member, item, nature, threats_to_OHKO, threats_to_survive) -> {offensive: SpRead, defensive: SpRead}`.
- [ ] 9.2 Implement 66-SP cap, max-per-stat cap (per §1.2), nature multiplier handling, item-modifier-aware allocation (Choice Band → physical_attack ×1.5 baked into hit-power calc; Eviolite → defenses ×1.5; Assault Vest → SpDef ×1.5; etc.).
- [ ] 9.3 Implement nature-jump optimization: if reading `nature_jumps.json` reveals a base-stat / SP combination where 1 SP yields +2 final-stat, prefer those allocations.
- [ ] 9.4 Generate two presets per pokémon: `offensive_preset` optimised to OHKO/2HKO meta pokémon weak to the member; `defensive_preset` optimised to survive top damaging moves from meta pokémon strong vs the member.
- [ ] 9.5 Remove the existing "504 vs 508" penalty / validation entirely from the codebase. Grep for `508` and `504` and remove dead branches.
- [ ] 9.6 Add `sp_presets: {offensive: SpRead, defensive: SpRead}` to `VariantOut` member entries; default preset on export is `offensive` (configurable via API later).
- [ ] 9.7 Tests: `tests/test_sp_presets.py` — total SPs per preset = 66; max per stat ≤ cap; Choice Band attacker's offensive preset puts more SPs in Speed than Attack (because item already inflates Attack); Eviolite NFE's defensive preset weights defenses; nature-jump threshold hit when applicable.

## 10. capability: `speed-control-required` (new) — depends on §7

- [ ] 10.1 Add `_speed_control_penalty(members) -> float` to `viability_rater.py`. Logic: detect speed-control mechanisms (Trick Room, Tailwind, Icy Wind, Electroweb, Thunder Wave, Glare, Nuzzle, Stun Spore, paralysis-inducing abilities like Static / Cute Charm, Fake Out for tempo, Quick Guard, Sticky Web — full list ratified during implementation review). If `count == 0` and archetype ≠ `stall`: penalty = −15 pts.
- [ ] 10.2 Add `requires_speed_control: bool` to `VariantOut` for UI surfacing.
- [ ] 10.3 Tests: `tests/test_speed_control_required.py` — team with no speed control + balance archetype → score reduced by 15 + `requires_speed_control=true`; team with Tailwind → no penalty + flag false; stall archetype → no penalty even without speed control.

## 11. capability: `bo3-mode` (modified) — terminology rename

- [ ] 11.1 Rename `lead_flexibility_score` → `core_flexibility_score` in `schemas.py` (`VariantOut`). Note: BREAKING for API consumers; document in changelog.
- [ ] 11.2 Rename `_lead_flexibility_points` → `_core_flexibility_points` in `viability_rater.py`. Update all internal call sites.
- [ ] 11.3 Update UI strings in `web/index.html` and `web/app.js`: "Lead" → "Core" (English) / "Núcleo" (Spanish); tooltips and badge labels updated.
- [ ] 11.4 Update existing tests in `tests/test_bo3_mode.py` to assert the new field names.

## 12. API + UI integration

- [ ] 12.1 Add `archetype` selector to `index.html` (radio group or dropdown, 7 options, default `balance`).
- [ ] 12.2 Add `archetype` to POST `/generate` body in `app.js`.
- [ ] 12.3 Render `archetype`, `core_flexibility_score`, `requires_speed_control`, and `sp_presets` on each variant card. Show a preset toggle (Offensive/Defensive) per member.
- [ ] 12.4 Show speed-control warning banner on variant when `requires_speed_control=true`.
- [ ] 12.5 Wire `archetype` through `api/router.py` into `generate_team()`.

## 13. Versioning + provenance

- [ ] 13.1 Add `data_version` echo to `VariantOut`: include `meta_versions: {legal_pool, items, weather, archetype_weights, sp_mechanics, ability_roles}` so a generated team's data provenance is traceable.
- [ ] 13.2 Log data versions at app startup and include them in `/health` endpoint response.
- [ ] 13.3 Add a `MIGRATION.md` (or update the changelog) documenting the BREAKING field renames (`lead_flexibility_score` → `core_flexibility_score`) and removed items (Weakness Policy / Throat Spray / Rocky Helmet).

## 14. Final verification

- [ ] 14.1 Full test suite green.
- [ ] 14.2 Generate team for Excadrill, archetype=weather_based → variant contains Tyranitar (Sand Stream), `weather_synergy` component non-zero, ≤1 mega.
- [ ] 14.3 Generate team for Pikachu, archetype=hyper_offense → speed-control present or `requires_speed_control=true` flag; no item duplicates; STAB Electric move on the moveset.
- [ ] 14.4 Generate team in Bo3 mode → variant exposes `core_flexibility_score`, no `lead_flexibility_score`; UI shows "Núcleo".
- [ ] 14.5 Generate team with 2 mega-stone candidates → only one assigned a mega stone; no mega duplication.
- [ ] 14.6 Grep codebase for `508`, `504`, `lead_flexibility`, `WeaknessPolicy`, `ThroatSpray`, `RockyHelmet` and confirm no live references remain.
