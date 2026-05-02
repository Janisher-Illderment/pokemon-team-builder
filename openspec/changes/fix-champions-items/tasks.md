## 1. Verify item constants in team_generator.py

- [ ] 1.1 Confirm `_DEFAULT_ITEM_BY_ROLE` has exactly 7 entries, all Champions-legal (Weakness Policy, Throat Spray, Rocky Helmet, Leftovers, Focus Sash, Mental Herb, Clear Amulet)
- [ ] 1.2 Confirm `_FALLBACK_ITEM = "Choice Scarf"` (verified in Champions item list)
- [ ] 1.3 Confirm `_BACKUP_ITEMS` has ≥30 entries, starts with "Sitrus Berry", and contains no non-Champions items

## 2. Audit and patch _BACKUP_ITEMS

- [ ] 2.1 Cross-check every item in `_BACKUP_ITEMS` against the confirmed Champions list (pokemon-zone.com + Serebii): remove any that are not confirmed
- [ ] 2.2 Remove items already covered by `_DEFAULT_ITEM_BY_ROLE` (Rocky Helmet, Leftovers, Focus Sash, Mental Herb, Clear Amulet, Weakness Policy, Throat Spray) to avoid duplication in fallback chain
- [ ] 2.3 Ensure no Mega Stone (names ending in "ite") appears in any constant
- [ ] 2.4 Ensure no resistance berry (Occa, Passho, Wacan, Rindo, Yache, Chople, Kebia, Shuca, Coba, Payapa, Tanga, Charti, Kasib, Haban, Colbur, Babiri, Chilan, Roseli) appears in `_BACKUP_ITEMS`
- [ ] 2.5 Pad pool with additional Champions-confirmed battle items if count drops below 30: candidates include Lum Berry, Bright Powder, Quick Claw, Light Ball, Persim Berry, Oran Berry

## 3. Update tests

- [ ] 3.1 In `tests/test_team_generator.py`: replace any fixture items that are not Champions-legal (e.g., if "Choice Band" or "Assault Vest" appear as expected values)
- [ ] 3.2 In `tests/test_replica_exporter.py`: verify `_basic_variant()` fixture uses only Champions-legal items (Weakness Policy, Focus Sash, Sitrus Berry, Leftovers, Rocky Helmet, Choice Scarf — already updated)
- [ ] 3.3 Add a test `test_no_illegal_items_in_constants` that asserts none of Choice Band, Choice Specs, Assault Vest, Life Orb, Eject Button appear in any item constant

## 4. Integration check

- [ ] 4.1 Run `pytest tests/test_team_generator.py tests/test_replica_exporter.py -v` — all tests pass
- [ ] 4.2 Manually verify a generated team's PokePaste contains only Champions-legal items
