## ADDED Requirements

### Requirement: Anchor search field
The UI SHALL provide a text input where the user types a Pokémon name (or partial name)
to select the anchor for team generation.

#### Scenario: User types a valid name and submits
- **WHEN** the user types "garchomp" in the search field and clicks "Generate"
- **THEN** a loading indicator appears and the team generation request is sent to the API

#### Scenario: Empty input is blocked
- **WHEN** the user clicks "Generate" with an empty input
- **THEN** no API request is sent and an inline validation message is shown

### Requirement: Loading feedback during generation
The UI SHALL show a visible loading state while the API is processing, since generation
can take 2–5 seconds.

#### Scenario: Loading indicator shown after submit
- **WHEN** the Generate button is clicked with a valid anchor
- **THEN** a loading spinner or progress message appears immediately

#### Scenario: Loading indicator hidden after response
- **WHEN** the API response is received (success or error)
- **THEN** the loading indicator disappears

### Requirement: Team variants are displayed as cards
Each generated team variant SHALL be shown in a distinct card that includes:
- The 6 Pokémon names, each with their role badge and item
- The viability score and score explanation
- A "Copy PokePaste" button

#### Scenario: Copy PokePaste writes to clipboard
- **WHEN** the user clicks "Copy PokePaste" on a variant card
- **THEN** the full PokePaste string is written to the clipboard and a confirmation toast appears

### Requirement: Error state is communicated
If the API returns an error (422 unknown Pokémon, 500, network failure), the UI SHALL
display a human-readable message and allow the user to try again.

#### Scenario: API 422 shown as user-friendly message
- **WHEN** the API returns 422 for an unknown anchor
- **THEN** the UI shows a message like "Pokémon not found in Champions M-A pool" (not a raw JSON dump)

### Requirement: UI is usable on mobile
The layout SHALL be responsive and usable on a 375 px wide screen (iPhone SE viewport).

#### Scenario: Cards stack vertically on narrow viewport
- **WHEN** the page is viewed at 375 px width
- **THEN** variant cards stack vertically and the Copy button is reachable without horizontal scroll
