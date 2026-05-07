## 1. team_generator.py — Choice guard any-role fix (Bug 1)

- [x] 1.1 En `_assign_items`, reemplazar `if primary in _NO_CHOICE_ROLES and alt in _CHOICE_ITEMS` por `if set(roles) & _NO_CHOICE_ROLES and alt in _CHOICE_ITEMS` en el fallback chain loop
- [x] 1.2 Aplicar el mismo cambio en el last-resort loop (segunda ocurrencia del mismo guard)
- [x] 1.3 Test `test_choice_blocked_when_setter_is_secondary_role`: `roles=["special_sweeper", "trick_room_setter"]`, Shell Bell tomado → el item asignado NO es ningún Choice item
- [x] 1.4 Test `test_choice_blocked_when_redirect_is_secondary_role`: `roles=["special_sweeper", "redirect"]`, Shell Bell tomado → el item asignado NO es ningún Choice item
- [x] 1.5 Test `test_pure_sweeper_still_gets_choice_scarf_as_fallback`: `roles=["physical_sweeper"]`, Scope Lens tomado → Choice Scarf es elegible

## 2. replica_exporter.py — Prankster move priority (Bug 2)

- [x] 2.1 En `_ROLE_MOVE_PRIORITY["lead_support"]`, añadir `"thunder-wave"`, `"spiky-shield"`, `"encore"` al final del tuple
- [x] 2.2 Test `test_prankster_lead_gets_thunder_wave`: `roles=["lead_support"]`, pool con `thunder-wave` pero sin tailwind/fake-out/follow-me/rage-powder → `slot4 == "thunder-wave"`
- [x] 2.3 Test `test_prankster_lead_gets_spiky_shield`: `roles=["lead_support"]`, pool con `spiky-shield` (sin thunder-wave ni moves más altos) → `slot4 == "spiky-shield"`
- [x] 2.4 Test `test_prankster_lead_gets_encore`: `roles=["lead_support"]`, pool con `encore` únicamente → `slot4 == "encore"`

## 3. replica_exporter.py — Slot-4 support-first reorder (Bug 3)

- [x] 3.1 Añadir `_SLOT4_SUPPORT_ROLES: frozenset[str] = frozenset({"lead_support", "redirect", "trick_room_setter"})` como constante de módulo
- [x] 3.2 En `select_moves_for_role`, antes del loop de slot4, construir `slot4_order` reordenando `roles` para que los roles en `_SLOT4_SUPPORT_ROLES` vayan primero (preservar orden relativo dentro de cada grupo)
- [x] 3.3 Usar `slot4_order` en el loop de slot4 en lugar de `roles`
- [x] 3.4 Test `test_support_role_beats_setup_in_slot4`: `roles=["special_sweeper", "lead_support"]`, pool con `calm-mind` y `tailwind` → `slot4 == "tailwind"`
- [x] 3.5 Test `test_rage_powder_beats_calm_mind`: `roles=["special_sweeper", "special_wall", "lead_support", "redirect"]`, pool con `calm-mind` y `rage-powder` → `slot4 == "rage-powder"`
- [x] 3.6 Test `test_trick_room_beats_nasty_plot`: `roles=["special_sweeper", "trick_room_setter"]`, pool con `nasty-plot` y `trick-room` → `slot4 == "trick-room"`
- [x] 3.7 Test `test_pure_sweeper_keeps_setup_move`: `roles=["physical_sweeper"]`, pool con `swords-dance` → `slot4 == "swords-dance"` (sin rol de soporte que lo desplace)

## 4. Verificación final

- [x] 4.1 Ejecutar suite completa: `pytest` — todos los tests deben pasar
- [x] 4.2 Verificar Slowbro: `_assign_items` con `roles=["special_sweeper","physical_wall","trick_room_setter"]`, Shell Bell tomado → item NO es Choice Scarf
- [x] 4.3 Verificar Klefki: `select_moves_for_role` con `roles=["lead_support"]`, pool con `thunder-wave` → slot4 == `thunder-wave`
- [x] 4.4 Verificar Volcarona: `select_moves_for_role` con `roles=["special_sweeper","special_wall","lead_support","redirect"]`, pool con `calm-mind` y `rage-powder` → slot4 == `rage-powder`
