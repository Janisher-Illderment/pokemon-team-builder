## Context

Three independent bugs share a common root: role-aware logic checks only `roles[0]` (the primary role) instead of the full role list. Pokémon with secondary support roles (trick_room_setter, lead_support, redirect) bypass guards that were intended to protect them. Additionally, the move priority list for `lead_support` was written for weather/Tailwind/Fake Out leads and never anticipated Prankster leads whose support moves are categorically different.

## Goals / Non-Goals

**Goals:**
- Choice items blocked whenever ANY role in the list is in `_NO_CHOICE_ROLES`
- Prankster leads (Klefki, Whimsicott) get thunder-wave / spiky-shield / encore in slot 4
- Multi-role Pokémon with support + sweeper roles emit a support move in slot 4

**Non-Goals:**
- No changes to role assignment logic (that is fix-role-balance territory)
- No new items or item eligibility rules beyond the guard fix
- No changes to slot 1, 2, or 3 selection logic

## Decisions

**D1 — Any-role check for Choice guard: `set(roles) & _NO_CHOICE_ROLES`**
Replaces `primary in _NO_CHOICE_ROLES` in both guard sites inside `_assign_items` (fallback chain and last-resort loop). The set intersection is O(n) with a small n (≤7 roles) and reads directly as "any role from this Pokémon's full role list is in the no-choice set."
Alternative rejected: checking each role in sequence with `any()` — functionally identical but set intersection is idiomatic.

**D2 — Extend `_ROLE_MOVE_PRIORITY["lead_support"]` with three Prankster moves**
`"thunder-wave"`, `"spiky-shield"`, `"encore"` appended after the existing entries. Appending (not prepending) preserves priority: Tailwind > Fake Out > Follow Me > Rage Powder > Thunder Wave > Spiky Shield > Encore. Weather setters and Fake Out leads are unaffected.
Alternative rejected: a separate `_PRANKSTER_MOVE_PRIORITY` list — unnecessary complexity; the existing list is a flat priority list and extending it is coherent.

**D3 — Slot-4 role reorder: support roles first, stable within each group**
Before the slot-4 candidate loop, sort `roles` so that `{"lead_support", "redirect", "trick_room_setter"}` come first, preserving original order within each group. This reorder is local to slot 4 — it does not change `roles[0]` used for item/nature/SP selection.
Alternative rejected: checking support roles explicitly before the main loop (early-exit on first match) — equivalent but a second loop body duplicates the candidate logic and is harder to maintain.

## Risks / Trade-offs

- [Slot-4 reorder changes behavior for all multi-role Pokémon] Pokémon that previously got a setup move because their primary is a sweeper will now get a support move instead. This is the intended fix, but it may surface other cases. → Mitigated by tests verifying both the fixed scenarios and a regression guard for a pure sweeper (no support role) that must keep its setup move.
- [thunder-wave in lead_support priority] Any lead_support Pokémon that learns thunder-wave will now prefer it over the fallback, even non-Prankster ones. In practice this is correct (Thunder Wave is always good on a support lead) but it's a behavior change for e.g. Incineroar if it had thunder-wave in pool. → Acceptable; Thunder Wave is never a wrong choice on a support lead.
