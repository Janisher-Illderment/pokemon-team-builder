## ADDED Requirements

### Requirement: Health endpoint
The API SHALL expose `GET /health` returning `{"status": "ok"}` so that hosting
platforms can verify the service is running.

#### Scenario: Health check returns 200
- **WHEN** `GET /health` is called
- **THEN** response status is 200 and body is `{"status": "ok"}`

### Requirement: Generate endpoint accepts a valid anchor Pokemon
`POST /generate` SHALL accept a JSON body `{"anchor": "<pokemon-slug>"}` where the
slug is a Champions Regulation M-A legal name (e.g., "garchomp", "charizard").

#### Scenario: Valid anchor returns team variants
- **WHEN** `POST /generate` is called with `{"anchor": "garchomp"}`
- **THEN** response status is 200 and body contains a list of 1–3 team variants

#### Scenario: Unknown anchor returns 422
- **WHEN** `POST /generate` is called with `{"anchor": "dragapult"}` (not in M-A pool)
- **THEN** response status is 422 and body contains a human-readable error message

#### Scenario: Missing anchor field returns 422
- **WHEN** `POST /generate` is called with an empty body `{}`
- **THEN** response status is 422

### Requirement: Each variant in the response includes PokePaste and metadata
The generate response SHALL include for each variant:
- `pokepaste`: string in PokePaste format, ready to import in PikaChampions
- `score`: float viability score
- `score_explanation`: string explanation
- `members`: list of 6 objects with `name`, `role`, `item`, `nature`, `moves`

#### Scenario: PokePaste field is non-empty
- **WHEN** a valid generate response is received
- **THEN** each variant's `pokepaste` field starts with a Pokémon name line and contains exactly 6 blocks

#### Scenario: Members list has exactly 6 entries
- **WHEN** a valid generate response is received
- **THEN** each variant's `members` list has length 6

### Requirement: CORS allows browser requests
The API SHALL include CORS headers that allow requests from any origin so that the
frontend (served as static files) can call the API without browser security errors.

#### Scenario: OPTIONS preflight returns CORS headers
- **WHEN** a CORS preflight `OPTIONS /generate` is sent
- **THEN** response includes `Access-Control-Allow-Origin: *`
