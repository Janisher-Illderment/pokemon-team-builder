## ADDED Requirements

### Requirement: POST /analyze-matchup endpoint accepts team and threat
The system SHALL expose `POST /analyze-matchup` in `api/router.py` that accepts `AnalyzeMatchupRequest` with `team: list[str]` (exactly 6 pokémon names) and `threat: str` (a pokémon name or archetype keyword). It SHALL return `MatchupAnalysisResponse` with structured analysis. The endpoint SHALL respond in under 3 seconds on warm cache.

#### Scenario: Valid request with known pokémon threat
- **WHEN** client posts `{"team": ["rillaboom", "flutter-mane", "landorus-therian", "amoonguss", "incineroar", "torkoal"], "threat": "flutter-mane"}`
- **THEN** the response contains a non-empty `weakness_summary`, at least one `handler`, and 1–2 `adjustments`

#### Scenario: Team with fewer than 6 members rejected
- **WHEN** client posts a team with 5 or fewer names
- **THEN** the endpoint returns HTTP 422 with a validation error

#### Scenario: Unknown threat name
- **WHEN** `threat` is not a legal pokémon name and not a known archetype keyword
- **THEN** the endpoint returns `{"error": "Amenaza desconocida: <threat>"}` with HTTP 422

### Requirement: Threat resolution supports pokémon names and archetype keywords
`services/matchup_analyzer.py` SHALL resolve `threat` first as a pokémon name via `pokemon_lookup.lookup()`; if lookup fails, it SHALL match against a keyword map: `"trick room"` → `["hatterene", "dusclops", "porygon2"]`, `"weather"` → `["torkoal", "pelipper", "ninetales-alola"]`, `"tailwind"` → `["talonflame", "whimsicott", "murkrow"]`, `"redirection"` → `["amoonguss", "togekiss"]`. Any match returns the list of canonical threat pokémon to analyze against. Unresolvable strings raise `UnknownThreatError`.

#### Scenario: Archetype keyword resolved
- **WHEN** `threat = "trick room"`
- **THEN** the analyzer uses `["hatterene", "dusclops", "porygon2"]` as the canonical threat list

#### Scenario: Pokémon name resolved directly
- **WHEN** `threat = "flutter-mane"`
- **THEN** the analyzer uses `[flutter_mane_pokemon_data]` as the threat

### Requirement: Weakness summary identifies team members weak to the threat
The analyzer SHALL identify team members with a type-effectiveness weakness ≥ 2.0 to any of the threat's primary types. The `weakness_summary` field SHALL list the vulnerable team members by name and the specific type they are weak to, in Spanish.

#### Scenario: Multiple members weak to threat type
- **WHEN** the threat is Fire-type and 2 team members have Fire weakness ≥ 2.0
- **THEN** `weakness_summary` names both pokémon and mentions Fire type

#### Scenario: No type weaknesses
- **WHEN** no team member is weak to any of the threat's types
- **THEN** `weakness_summary` states "Ningún miembro del equipo tiene debilidad de tipo al threat"

### Requirement: Handler identification selects the best team member to deal with the threat
The analyzer SHALL score each team member by: (a) type resistance to the threat's types (+2 per resistance ≥ 0.5×, +4 per immunity), (b) super-effective STAB move vs the threat's types (+3), (c) relevant role bonus (redirector +2, wall +1 if threat is a sweeper). The top-scoring member SHALL be returned as `primary_handler` with a Spanish explanation. A second member MAY be returned as `secondary_handler` if its score is ≥ 50% of the top score.

#### Scenario: Member with resistance and super-effective move
- **WHEN** a team member resists the threat's type AND has a super-effective STAB move
- **THEN** it is returned as `primary_handler` with a note explaining both the resistance and the offensive coverage

#### Scenario: No team member handles the threat well
- **WHEN** no team member scores above 0
- **THEN** `primary_handler` is the highest-scoring member anyway, but the explanation notes that the team has a genuine gap against this threat

### Requirement: Adjustment suggestions provide 1–2 concrete actionable changes
The analyzer SHALL generate 1–2 `adjustments`, each with `type` (`"move_swap"`, `"item_swap"`, or `"pokemon_swap"`), `target` (the team member to change), `change` (specific new move/item/replacement pokémon name), and `reason` (Spanish explanation of why this helps against the threat). Adjustments SHALL prefer move swaps over item swaps over pokémon swaps (less disruptive first).

#### Scenario: Move swap suggested
- **WHEN** a team member could answer the threat by replacing a low-priority slot-4 move with a coverage move
- **THEN** an adjustment of `type="move_swap"` is returned naming the specific member, old move, new move, and reason

#### Scenario: Pokémon swap as last resort
- **WHEN** no move or item change would meaningfully address the threat
- **THEN** an adjustment of `type="pokemon_swap"` is returned naming a specific replacement pokémon from the legal pool with the same role
