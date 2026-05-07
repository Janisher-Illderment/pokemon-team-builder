## ADDED Requirements

### Requirement: Edit member endpoint
The API SHALL expose `PATCH /edit-member` that accepts a `TeamVariant` payload, a `member_index` (0–5) and an `edit` discriminated by `kind`. The endpoint applies a single, in-place change to the indicated member, recomputes the team score and EV notes, and returns the updated team in the same `VariantOut` shape used by `/generate`. The endpoint SHALL NOT regenerate other members.

#### Scenario: Successful move swap
- **WHEN** `PATCH /edit-member` is called with a valid variant, `member_index=0`, and `edit={"kind": "move_swap", "slot_index": 2, "new_move": "stone-edge"}` where `stone-edge` is in the target Pokemon's move pool
- **THEN** the response status is 200 and the returned variant has `members[0].moves[2] == "stone-edge"`, with all other members unchanged

#### Scenario: Successful item swap
- **WHEN** `PATCH /edit-member` is called with `edit={"kind": "item_swap", "new_item": "Choice Scarf"}` and no other member already holds Choice Scarf
- **THEN** the response status is 200 and the returned variant has `members[member_index].item == "Choice Scarf"`

#### Scenario: Successful pokemon swap
- **WHEN** `PATCH /edit-member` is called with `edit={"kind": "pokemon_swap", "new_pokemon_name": "rotom-wash"}` and rotom-wash is in the M-A legal pool, not already on the team, and the team has 6 distinct species after the swap
- **THEN** the response status is 200 and the returned variant has `members[member_index].pokemon.name == "rotom-wash"` with a freshly derived ability, nature, SP distribution and 4 moves

#### Scenario: Score and explanation are recomputed
- **WHEN** any edit is applied
- **THEN** the response `score` and `score_explanation` are produced from `viability_rater.score_team` and `viability_rater.generate_explanation` over the modified variant, not copied from the input

### Requirement: Edit member input validation
The endpoint SHALL reject malformed or illegal edits with HTTP 422 and a human-readable Spanish message describing the failure.

#### Scenario: Member index out of range
- **WHEN** `member_index` is negative or `>= 6`
- **THEN** response status is 422 with a message naming the offending index

#### Scenario: Move not in the Pokemon's move pool
- **WHEN** `kind == "move_swap"` and `new_move` is not present in the target member's `pokemon.move_names`
- **THEN** response status is 422 with a message naming the move and the Pokemon

#### Scenario: Move slot index out of range
- **WHEN** `kind == "move_swap"` and `slot_index` is not in `[0, 3]`
- **THEN** response status is 422

#### Scenario: Item swap creates a duplicate item (Item Clause)
- **WHEN** `kind == "item_swap"` and `new_item` is already held by another member of the same variant
- **THEN** response status is 422 with a message stating the Item Clause conflict and the holder

#### Scenario: Pokemon swap with non-legal target
- **WHEN** `kind == "pokemon_swap"` and `new_pokemon_name` is not in the M-A legal pool
- **THEN** response status is 422 with a message stating the Pokemon is not in the M-A pool

#### Scenario: Pokemon swap creates a duplicate species (Species Clause)
- **WHEN** `kind == "pokemon_swap"` and the new Pokemon is already a member of the variant (excluding the slot being replaced)
- **THEN** response status is 422 with a message stating the Species Clause conflict

#### Scenario: Pokemon swap target cannot be resolved
- **WHEN** `kind == "pokemon_swap"` and `pokemon_lookup.lookup(new_pokemon_name)` fails
- **THEN** response status is 422 with a message including the upstream error

### Requirement: Edit member produces a fresh PokePaste
The response of `PATCH /edit-member` SHALL include a `pokepaste` field re-serialized from the modified variant by `replica_exporter.to_pokepaste`, so the frontend can offer a Copy button without re-implementing serialization.

#### Scenario: PokePaste reflects the edit
- **WHEN** a successful `move_swap` edit returns
- **THEN** the response `pokepaste` string contains the new move name in the affected member's block and not the previous move

### Requirement: Pokemon swap derives a coherent member
When `kind == "pokemon_swap"`, the new `TeamMember` SHALL be constructed using the same defaults as `team_generator`: ability is the first ability of the new Pokemon, nature is the role's default nature, SP distribution comes from the role's SP template, and moves are derived by `replica_exporter.select_moves_for_role` against the new Pokemon's move pool.

#### Scenario: Role is preserved when compatible
- **WHEN** `pokemon_swap` is applied and the new Pokemon's candidate role set includes the previous member's primary role
- **THEN** the new member's `role` keeps the previous primary role as its first entry

#### Scenario: Role falls back when not compatible
- **WHEN** `pokemon_swap` is applied and the new Pokemon's candidate role set does NOT include the previous member's primary role
- **THEN** the new member's `role` uses the first role from the new Pokemon's candidate set

#### Scenario: New member has exactly 4 moves
- **WHEN** `pokemon_swap` returns successfully
- **THEN** `members[member_index].moves` has length 4 and contains no duplicates

### Requirement: Edit member is stateless
The server SHALL NOT persist any team state between requests. Each `PATCH /edit-member` request carries the entire variant in the request body and returns the entire updated variant in the response.

#### Scenario: Two independent edits do not interfere
- **WHEN** the same client sends two `PATCH /edit-member` requests for the same original team in parallel
- **THEN** each response reflects the corresponding edit applied to the input variant of that request, with no cross-talk

### Requirement: Edit member preserves unrelated members
After any edit, members other than the one at `member_index` SHALL be byte-identical to the corresponding members in the input variant.

#### Scenario: Other members untouched after a move swap
- **WHEN** an edit at `member_index=2` succeeds
- **THEN** for `i in {0, 1, 3, 4, 5}` the response `members[i]` equals the input `members[i]` field-by-field
