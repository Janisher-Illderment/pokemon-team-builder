## ADDED Requirements

### Requirement: Generation flow anchors on the favorite Pokémon and builds a core duo before filling remaining slots
`generate_team()` SHALL execute four phases in order: (1) anchor lookup from the `favorite` request field, (2) `build_core_duo(anchor, archetype, legal_pool, meta_service) -> tuple[PokemonData, float]` returning the single best partner and its synergy score, (3) `cover_shared_weakness(core_duo, archetype, legal_pool) -> PokemonData` returning slot 3 chosen to address the *intersection* of core-duo weaknesses, (4) beam search over the remaining 3 slots seeded with the first three members. Slots 1–3 SHALL be deterministic per `(anchor, archetype, format, mega_preference)` tuple.

#### Scenario: Anchor + best partner forms core duo
- **WHEN** `generate_team` is called with `favorite="excadrill"`, `archetype="weather_based"`
- **THEN** slot 1 is Excadrill and slot 2 is the partner returned by `build_core_duo(excadrill, "weather_based", ...)` — for this anchor + archetype the partner is Tyranitar (Sand Stream)

#### Scenario: Slot 3 covers shared weakness, not single-member weakness
- **WHEN** the core duo has weaknesses `{Fighting: 4×, Water: 2×}` for member A and `{Fighting: 2×, Grass: 2×}` for member B, with intersection `{Fighting}`
- **THEN** slot 3 is chosen to maximally cover Fighting (the shared weakness), not Water or Grass

#### Scenario: Same input produces same first three slots
- **WHEN** `generate_team(favorite="garchomp", archetype="balance", format="bo1", mega_preference=None)` is called twice
- **THEN** slots 1–3 are identical between the two calls; only slots 4–6 may vary due to beam-search tie-breaking

### Requirement: Partner synergy scoring weights type complement, role complement, ability/move compatibility, and meta presence
`build_core_duo` SHALL score every legal-pool candidate against the anchor using a weighted sum of: (a) **type complement** — anchor weaknesses that the partner resists; (b) **role complement** — partner role differs from anchor role unless archetype is `hyper_offense`; (c) **ability/move compatibility** — weather setter for weather-dependent ability anchor; Trick Room setter for slow anchor in `hard_trick_room`; redirect/support for fragile sweeper anchor; (d) **meta presence** from `MetaService.usage_weight(candidate)`. The candidate with the highest weighted score is the partner.

#### Scenario: Type complement preferred over raw meta presence
- **WHEN** two candidates have similar role complement but candidate A covers 2 anchor weaknesses and candidate B covers 0 with higher meta usage
- **THEN** candidate A is selected (type complement weight exceeds meta delta)

#### Scenario: Weather-ability anchor pairs with matching weather setter
- **WHEN** anchor is a Sand Rush pokémon and one candidate sets Sand Stream
- **THEN** the candidate setting Sand Stream receives the synergy bonus that places it above non-setter alternatives

#### Scenario: Hyper offense allows duplicate role in core duo
- **WHEN** archetype is `hyper_offense` and anchor is a `physical_sweeper`
- **THEN** a second `physical_sweeper` IS eligible as partner; the role-complement penalty is not applied for this archetype

### Requirement: Beam search seeded with the first three members
The beam-search component of `generate_team()` SHALL operate only over slots 4–6 with anchor, partner, and slot 3 already fixed. Beam search SHALL respect the archetype's `cheese_allowance`, mega clause (≤1 mega per team), and item uniqueness during expansion. Beam width and depth parameters are unchanged from v0.2.0.

#### Scenario: Beam search receives 3-member seed
- **WHEN** `generate_team` reaches the beam-search phase
- **THEN** beam search initial state contains exactly 3 members and expands to depth 3

#### Scenario: Beam rejects 4th member that would create a 2nd mega
- **WHEN** the seed already contains 1 mega holder and a candidate 4th member would also hold a mega stone
- **THEN** the candidate is pruned before partial scoring

### Requirement: Variance comes from archetype and SP-preset selection, not RNG
Given a fixed `(favorite, archetype, format, mega_preference)` tuple, `generate_team` SHALL produce a deterministic sequence of variants. Different variants in the response SHALL differ by SP-preset choice and beam-search tie-breaking only, not by random sampling.

#### Scenario: Repeated identical calls produce identical variant lists
- **WHEN** `generate_team` is called twice with the same input
- **THEN** the returned `variants` list is byte-identical between calls

#### Scenario: Changing archetype changes variant lineup
- **WHEN** `generate_team` is called with `archetype="hyper_offense"` then `archetype="hard_trick_room"` for the same favorite
- **THEN** the variant lists differ (different partner selection, different scoring weights, different slot 4–6 outputs)
