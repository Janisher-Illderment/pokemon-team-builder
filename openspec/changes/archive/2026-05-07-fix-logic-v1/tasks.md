# Tasks — fix-logic-v1

## Grupo 1 — team_generator.py (A1, A2, A3, B1, B2, B3+E7, E4)

- [x] **T1** Añadir `"lead_support"` a `_NO_CHOICE_ROLES` (A1+E4)
  - File: `team_generator.py:106-111`
  - Test: `test_choice_item_not_assigned_to_lead_support`

- [x] **T2** Corregir `assign_role`: comparar `max(atk, spa)` cuando ambos >= 100 (B1)
  - File: `synergy_engine.py:71-73`
  - Lógica: si ambos >= 100 → usar el mayor; si solo uno >= 100 → ese
  - Test: `test_assign_role_mixed_stat_uses_dominant` (Hydreigon: Atk 105, SpA 125 → special_sweeper)

- [x] **T3** Remover `"Loaded Dice"` de `_BACKUP_ITEMS` (A2)
  - File: `team_generator.py:46-76`
  - Test: actualizar `test_no_illegal_items_in_constants` para incluir Loaded Dice en lista de inválidos

- [x] **T4** Añadir `redirect` a `role_sp_templates.json` con `{"hp": 32, "spd": 32, "def": 2}` (A3)
  - File: `pokemon_team_builder/data/role_sp_templates.json`
  - Test: `test_suggest_sp_redirect_uses_bulk_template`

- [x] **T5** Refactorizar `_item_is_activatable` con tabla `_ITEM_PRECONDITIONS` (B3+E7)
  - File: `team_generator.py:332-342`
  - Incluir: Throat Spray, White Herb, Weakness Policy, type-boosters
  - `White Herb` y `Throat Spray`: verifican contra `moves` (moveset generado), no solo learnset
  - `Weakness Policy`: descartada si `moves` incluye algún setup move
  - Signature: `_item_is_activatable(item, pokemon, moves=None)`
  - Test: `test_weakness_policy_not_assigned_with_setup_move`
  - Test: `test_white_herb_not_assigned_to_wall_moveset`

## Grupo 2 — replica_exporter.py (E1, E3, B4, E9, E8)

- [x] **T6** Corregir `_fallback_move` — nunca retornar move en `used` (E1)
  - File: `replica_exporter.py` — función `_fallback_move`
  - El último `return "tackle"` debe verificar `used`
  - Si todos los genéricos están en `used`: raise `TeamBuildError`
  - Test: `test_fallback_move_never_returns_duplicate`

- [x] **T7** Corregir guardias de pass 0 en slot-2 y slot-3 para `cand_cat == ""` (E3)
  - File: `replica_exporter.py:384-385` (slot-2) y `409-410` (slot-3)
  - Cambio: `if pass_num == 0 and cand_cat != primary_cat: continue`
    (tratar `""` como "no elegible en pass 0", no como "cualquier categoría")
  - Test: `test_unknown_category_move_not_chosen_in_pass0`

- [x] **T8** Verificar Protect en move_pool antes de asignar slot 1 (B4)
  - File: `replica_exporter.py` — inicio de `select_moves_for_role`
  - Si `"protect"` no está en move_pool: usar `_fallback_move` para slot 1
  - Test: `test_protect_slot1_fallback_when_not_in_learnset`

- [x] **T9** Derivar nature desde slot-2 STAB category (E9, B1 extension)
  - File: `team_generator.py:_build_variant` — calcular moves ANTES de la nature
  - Lógica: `_MOVE_CATEGORY.get(moves[1])` → si "physical": Jolly/Impish; si "special": Timid/Calm
  - Excepciones fijas: trick_room_setter → Sassy, redirect → Calm
  - Fallback: role-based (comportamiento actual) cuando slot-2 no está en `_MOVE_CATEGORY`
  - Test: `test_nature_matches_slot2_category_for_lead`
  - Test: `test_nature_timid_for_special_lead` (Pelipper con Hurricane → Timid)

- [x] **T10** Añadir `_SPECIES_OVERRIDES` y aplicar en `_format_species` (E8)
  - File: `replica_exporter.py` — función `_format_species`
  - Overrides confirmados: `{"kommo-o": "Kommo-o", "ho-oh": "Ho-Oh", "porygon-z": "Porygon-Z"}`
  - Test: `test_format_species_kommo_o`
  - Test: `test_format_species_overrides_applied_before_capitalize`

## Grupo 3 — viability_rater.py (E5, E6)

- [x] **T11** Eliminar penalización de Life Orb en `_items_points` + añadir comment (E5)
  - File: `viability_rater.py:72-85`
  - Remover: `counts = Counter(items)` y bloque `life_orb`
  - Añadir comment: `# WHY: Item Clause guarantees uniqueness by construction — always 15pts in v1`
  - Test: actualizar `test_items_points_*` si existen

- [x] **T12** Añadir docstring a `analyze_coverage` documentando limitación (E6)
  - File: `synergy_engine.py:102-137`
  - Añadir nota: offensive_gaps mide por tipos del Pokémon, no por moves del moveset — limitación conocida, v2 usará moves reales

## Criterios de aceptación globales

- [x] `python -m pytest tests/ -q` → 100% passing (338 tests, 2026-05-07)
- [x] Ningún equipo generado con ancla del pool de 167 emite moves duplicados
- [x] Hydreigon con ancla recibe `special_sweeper` como rol primario
- [x] Pelipper como lead_support recibe `Timid` o `Calm`, no `Jolly`
- [x] Un physical_sweeper con Dragon Dance no recibe Weakness Policy
- [x] kommo-o como ancla exporta `"Kommo-o"` en PokePaste
