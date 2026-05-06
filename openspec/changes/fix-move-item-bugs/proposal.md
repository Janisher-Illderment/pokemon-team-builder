## Why

Three bugs in move/item assignment produce invalid or competitively useless outputs: Pokémon with a secondary `trick_room_setter` role receive Choice Scarf (locking them out of Trick Room), Prankster leads fall back to junk moves (Cut) because their signature support moves are absent from the priority list, and multi-role Pokémon with both sweeper and support roles always pick the sweeper's setup move over the support move in slot 4.

## What Changes

- **Bug 1 fix**: `_assign_items` blocks Choice items when **any** role is in `_NO_CHOICE_ROLES`, not only the primary role
- **Bug 2 fix**: `_ROLE_MOVE_PRIORITY["lead_support"]` extended with `"thunder-wave"`, `"spiky-shield"`, `"encore"` — covers Prankster leads (Klefki, Whimsicott)
- **Bug 3 fix**: slot-4 role iteration reordered so support roles (`lead_support`, `redirect`, `trick_room_setter`) are evaluated before sweeper/wall roles — Rage Powder beats Calm Mind on Volcarona

## Capabilities

### New Capabilities

*(none — all fixes are correctness changes within existing capabilities)*

### Modified Capabilities

- `role-balance`: Choice item guard now applies to any role in the list, not just the primary
- `ability-aware-roles`: slot-4 support priority rule; Prankster lead support moves extended

## Impact

- `pokemon_team_builder/services/team_generator.py`: `_assign_items` — two guard sites
- `pokemon_team_builder/services/replica_exporter.py`: `_ROLE_MOVE_PRIORITY["lead_support"]`; slot-4 loop reorder
- Tests: all existing must pass; new tests for each of the 3 fixes
