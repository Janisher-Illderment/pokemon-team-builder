# Migration notes

Tracks BREAKING changes for API consumers and importers of
`pokemon_team_builder`. Newer entries appear first.

## 0.9.0-phase3 (Phase 3 — refine-build-logic-v2)

### API field renames (BREAKING)

- `VariantOut.lead_flexibility_score` → `VariantOut.core_flexibility_score`
- `TeamVariant.lead_flexibility_ratio` → `TeamVariant.core_flexibility_ratio`
- `viability_rater._lead_flexibility_points` → `viability_rater._core_flexibility_points`

The semantics are unchanged — both fields carry the 0..1 ratio of
4-of-6 combinations that include at least one speed-control or
redirect-move member. The rename aligns with VGC vocabulary (Bo3
"core" rather than "lead").

Action for API consumers: update field reads from
`lead_flexibility_score` to `core_flexibility_score`. Pre-Phase-3 keys
no longer exist; absent fields default to `0.0`.

### New API fields (additive)

- `VariantOut.requires_speed_control: bool` — surfaces the new
  speed-control mandate (Phase 3 §10).
- `VariantOut.meta_versions: dict[str, int]` — data-file version map
  for provenance (Phase 3 §13). Keys: `legal_pool`, `items`, `weather`,
  `archetype_weights`, `sp_mechanics`, `ability_roles`,
  `mega_evolutions`, `doubles_roles`, `type_chart`, `role_sp_templates`.
- `MemberOut.sp_presets: dict[str, SpReadOut]` — two SP presets per
  member (`offensive`, `defensive`). Empty for imported variants that
  pre-date Phase 3.

### Health endpoint shape change (additive)

- `GET /health` now returns `{"status": "ok", "meta_versions": {...}}`.
  Old shape `{"status": "ok"}` is replaced — clients that asserted
  exact-equality on the response body must accept the additional key.

### Removed items (Phase 1, referenced here for completeness)

- Weakness Policy, Throat Spray, Rocky Helmet, Life Orb are not in the
  Champions Reg M-A pool. The replicas no longer attempt to assign
  them; if a PokePaste import includes one of these, the importer
  surfaces a warning and substitutes a legal default.

### Legacy 508-EV math removed

- The pre-Champions 508-EV / 504-vs-508 penalty branches were removed
  in Phase 1; Phase 3 removes any remaining doc references. The 66-SP
  system is now the only allocation API. The 1 SP = 8 legacy EVs
  conversion remains in `services/sp_calc._ev_from_sp` for backward
  compatibility with the existing PokePaste `EVs:` line format.
