## MODIFIED Requirements

### Requirement: Choice items are forbidden for roles that cannot cycle utility
`_assign_items` SHALL block Choice items when ANY role in the Pokémon's full role list is in `_NO_CHOICE_ROLES = {"trick_room_setter", "redirect", "physical_wall", "special_wall", "lead_support"}`. The check SHALL use `set(roles) & _NO_CHOICE_ROLES` rather than inspecting only `roles[0]`. This applies to both the fallback chain loop and the last-resort loop inside `_assign_items`.

#### Scenario: Slowbro (trick_room_setter secondary) does not receive Choice Scarf
- **WHEN** `_assign_items` processes a Pokémon with `roles=["special_sweeper", "physical_wall", "trick_room_setter"]` and Shell Bell is already taken
- **THEN** Choice Scarf is skipped and the next non-Choice backup item is assigned instead

#### Scenario: Pure sweeper still receives Choice Scarf as fallback
- **WHEN** `_assign_items` processes a Pokémon with `roles=["physical_sweeper"]` and its preferred item is taken
- **THEN** Choice Scarf is eligible as the fallback item (no support/setter role to block it)

#### Scenario: redirect Pokémon does not receive Choice Scarf
- **WHEN** `_assign_items` processes a Pokémon with `roles=["special_sweeper", "redirect"]` and its preferred item is taken
- **THEN** Choice Scarf is skipped (redirect is in _NO_CHOICE_ROLES)
