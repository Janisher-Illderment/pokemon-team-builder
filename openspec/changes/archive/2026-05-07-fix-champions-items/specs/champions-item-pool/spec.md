## ADDED Requirements

### Requirement: Role items are Champions-legal
`_DEFAULT_ITEM_BY_ROLE` SHALL contain only items confirmed to exist in Pokémon Champions.
Assignments: physical_sweeper → Weakness Policy, special_sweeper → Throat Spray,
physical_wall → Rocky Helmet, special_wall → Leftovers, lead_support → Focus Sash,
trick_room_setter → Mental Herb, redirect → Clear Amulet.

#### Scenario: No illegal role item is emitted
- **WHEN** `_assign_items` is called for any supported role
- **THEN** the returned item appears in the confirmed Champions item list

#### Scenario: Role item has competitive rationale for Doubles
- **WHEN** a physical_sweeper receives an item
- **THEN** the item is Weakness Policy (activatable via ally attacks in Doubles)

### Requirement: Fallback item is Champions-legal
`_FALLBACK_ITEM` SHALL be Choice Scarf, which is confirmed in the Champions item list.

#### Scenario: Fallback item is used when role item is taken
- **WHEN** `_assign_items` processes a second Pokémon of the same role
- **THEN** the assigned item is Choice Scarf (not a non-existent item like Life Orb)

### Requirement: Backup pool guarantees Item Clause for 6 members
`_BACKUP_ITEMS` SHALL contain at least 30 distinct Champions-legal items so that even
a team of 6 Pokémon assigned the same primary role can each receive a unique item.
Items SHALL be ordered by competitive utility (utility items first, type-boosters last).

#### Scenario: Item Clause satisfied for 6 same-role team
- **WHEN** `_assign_items` is called with 6 members all assigned the same role
- **THEN** all 6 receive distinct items without raising `TeamBuildError`

#### Scenario: Backup pool contains no non-Champions items
- **WHEN** any item from `_BACKUP_ITEMS` is inspected
- **THEN** it is NOT one of: Choice Band, Choice Specs, Assault Vest, Life Orb, Eject Button, Rocky Helmet (already in role map), Focus Sash (already in role map), Mental Herb (already in role map)

#### Scenario: Backup pool ordering prioritizes utility
- **WHEN** the first 10 items of `_BACKUP_ITEMS` are listed
- **THEN** they are utility/support items (Sitrus Berry, Scope Lens, Power Herb, etc.)
  before type-boosting plates (Mystic Water, Charcoal, Magnet, etc.)

### Requirement: Resistance berries are legal but deprioritized
The 18 resistance berries (Occa, Passho, Wacan, Rindo, Yache, Chople, Kebia, Shuca,
Coba, Payapa, Tanga, Charti, Kasib, Haban, Colbur, Babiri, Chilan, Roseli) SHALL be
excluded from `_BACKUP_ITEMS` because their situational nature makes them poor generic
fallbacks, even though they are Champions-legal.

#### Scenario: No resistance berry appears in backup pool
- **WHEN** `_BACKUP_ITEMS` is inspected
- **THEN** none of the 18 resistance berries (e.g., Occa Berry, Passho Berry) appear

### Requirement: Status berries are legal and may appear in pool
Status-curing berries (Sitrus, Lum, Persim, Oran, Leppa, Aspear, Rawst, Pecha, Chesto,
Cheri) are confirmed Champions items and SHALL be eligible for `_BACKUP_ITEMS`.
Sitrus Berry SHALL be the first entry as the highest-utility generic berry.

#### Scenario: Sitrus Berry is first in backup pool
- **WHEN** `_BACKUP_ITEMS[0]` is read
- **THEN** it equals "Sitrus Berry"

### Requirement: Mega Stones are excluded from item constants
Mega Stones are managed by the Mega Evolution mechanic in Champions and SHALL NOT
appear in `_DEFAULT_ITEM_BY_ROLE`, `_FALLBACK_ITEM`, or `_BACKUP_ITEMS`.

#### Scenario: No Mega Stone in any item constant
- **WHEN** all three item constants are inspected
- **THEN** no item name ends with "ite" (e.g., Charizardite X, Lucarionite, Scizorite)

### Requirement: PokePaste import does not silently drop items
Any item string emitted by `_assign_items` SHALL be accepted by PikaChampions and
ChampTeams.gg importers without silent removal.

#### Scenario: Generated team imports cleanly in PikaChampions
- **WHEN** `to_pokepaste` is called on a generated `TeamVariant`
- **THEN** every `@ <item>` line uses an item from the confirmed Champions list
