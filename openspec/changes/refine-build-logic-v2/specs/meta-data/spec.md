## MODIFIED Requirements

### Requirement: All tunable static data files include regulation and data_version headers
Each tunable static-data JSON file under `pokemon_team_builder/data/` SHALL include a top-level object with `regulation: str` and `data_version: int` fields. The list of files SHALL include: `legal_pool_mA.json`, `mega_evolutions.json`, `type_chart.json`, `doubles_roles.json`, `champions_legal_items.json`, `weather_setters.json`, `weather_dependent_abilities.json`, `archetype_weights.json`, `nature_jumps.json`, `ability_implicit_roles.json`. Bumping `data_version` SHALL be the protocol for shipping meta parches.

#### Scenario: Every data file has a regulation and version header
- **WHEN** each data JSON file under `data/` is loaded at startup
- **THEN** loading succeeds only if both `regulation` and `data_version` keys are present at the top level

#### Scenario: Mismatched regulation rejected
- **WHEN** any data file's `regulation` field does not match the running app's expected regulation (currently `"mA"`)
- **THEN** the application fails to start with a clear error naming the offending file

### Requirement: Generated variants record meta_versions for provenance
`VariantOut` SHALL include `meta_versions: dict[str, int]` mapping each data-file logical name (`legal_pool`, `items`, `weather`, `archetype_weights`, `sp_mechanics`, `ability_roles`, `mega_evolutions`, `doubles_roles`, `type_chart`) to the `data_version` integer of the file that was loaded at request-handling time.

#### Scenario: Variant carries meta versions
- **WHEN** any team is generated
- **THEN** `VariantOut.meta_versions` is non-empty and contains a numeric version for each loaded data file

#### Scenario: Versions are stable per data file
- **WHEN** two variants are returned in the same response
- **THEN** their `meta_versions` are byte-identical (the data files do not hot-reload mid-request)

### Requirement: Health endpoint exposes loaded data versions
`GET /health` SHALL include `meta_versions: dict[str, int]` in its response so operators can verify what meta the running app loaded without generating a team.

#### Scenario: /health reports versions
- **WHEN** a client calls `GET /health`
- **THEN** the response body contains `meta_versions` with the same keys as `VariantOut.meta_versions`

### Requirement: Startup logging records data versions
At application startup the system SHALL log a single structured line listing each data file's logical name and `data_version`. This enables ops to confirm meta state from log inspection.

#### Scenario: Startup log contains all data versions
- **WHEN** the application boots successfully
- **THEN** stdout/stderr contains a log line of the form `meta_versions={...}` listing every loaded data file
