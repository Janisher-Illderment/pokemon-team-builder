## ADDED Requirements

### Requirement: Prankster lead support moves appear in slot 4
`_ROLE_MOVE_PRIORITY["lead_support"]` SHALL include `"thunder-wave"`, `"spiky-shield"`, and `"encore"` after the existing entries. These moves cover Prankster leads (Klefki, Whimsicott) whose signature utility does not overlap with weather/Tailwind/Fake Out leads.

#### Scenario: Klefki gets thunder-wave in slot 4
- **WHEN** `select_moves_for_role` runs for a Pokémon with `roles=["lead_support"]` that knows `thunder-wave` but not `tailwind`, `fake-out`, `follow-me`, or `rage-powder`
- **THEN** slot 4 is `thunder-wave`

#### Scenario: Klefki gets spiky-shield when thunder-wave is unavailable
- **WHEN** `select_moves_for_role` runs for a Pokémon with `roles=["lead_support"]` that knows `spiky-shield` but not any higher-priority lead move
- **THEN** slot 4 is `spiky-shield`

#### Scenario: Encore fills slot 4 as last Prankster option
- **WHEN** `select_moves_for_role` runs for a Pokémon with `roles=["lead_support"]` that knows only `encore` from the full priority list
- **THEN** slot 4 is `encore`

### Requirement: Support role move takes priority over setup move in slot 4
`select_moves_for_role` SHALL evaluate `lead_support`, `redirect`, and `trick_room_setter` roles before sweeper and wall roles when selecting slot 4. The reorder SHALL only apply to slot 4 — it SHALL NOT affect which role is `roles[0]` (used for item/nature/SP selection).

#### Scenario: Volcarona emits Rage Powder over Calm Mind
- **WHEN** `select_moves_for_role` runs for a Pokémon with `roles=["special_sweeper", "special_wall", "lead_support", "redirect"]` that knows both `calm-mind` and `rage-powder`
- **THEN** slot 4 is `rage-powder` (lead_support/redirect checked before special_sweeper)

#### Scenario: Pure sweeper still gets its setup move
- **WHEN** `select_moves_for_role` runs for a Pokémon with `roles=["physical_sweeper"]` that knows `swords-dance`
- **THEN** slot 4 is `swords-dance` (no support role to override it)

#### Scenario: trick_room_setter role prioritizes trick-room in slot 4
- **WHEN** `select_moves_for_role` runs for a Pokémon with `roles=["special_sweeper", "trick_room_setter"]` that knows `trick-room` and `calm-mind`
- **THEN** slot 4 is `trick-room` (trick_room_setter checked before special_sweeper)
