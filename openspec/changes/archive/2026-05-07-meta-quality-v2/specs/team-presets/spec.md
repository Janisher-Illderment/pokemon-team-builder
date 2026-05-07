## ADDED Requirements

### Requirement: User can save a generated team variant as a named preset
The frontend SHALL provide a "Save Team" button on each variant card. Clicking it SHALL save the variant (pokepaste, member list, score) to `localStorage['poke-builder-presets']` with a default name `Team {N}` and a randomly assigned color tag from a fixed palette of 6 colors. The maximum number of saved presets is 20; attempting to save beyond this limit SHALL display an inline warning.

#### Scenario: Save new preset
- **WHEN** user clicks "Save Team" on a variant card
- **THEN** the variant is added to localStorage with a default name, color tag, and current timestamp

#### Scenario: Save at limit
- **WHEN** 20 presets already exist and user clicks "Save Team"
- **THEN** no preset is saved and an inline warning "Máximo 20 equipos guardados" is shown

### Requirement: Saved presets panel shows Pokémon sprites and editable metadata
The frontend SHALL render a "Saved Teams" panel (initially collapsed, togglable) listing all presets. Each preset SHALL display:
- Pokémon sprites from Showdown CDN (`https://play.pokemonshowdown.com/sprites/gen5/{name}.png`) for all 6 members
- Editable name field (inline edit on click)
- Color tag dot (clickable cycles through 6 colors)
- Save timestamp
- "Copy Pokepaste" button
- "Delete" button

Sprites that fail to load SHALL fall back to displaying the pokémon's text name.

#### Scenario: Preset displayed with sprites
- **WHEN** a saved preset is listed in the panel
- **THEN** each of the 6 member sprites loads from Showdown CDN with `onerror` fallback to text name

#### Scenario: Edit preset name
- **WHEN** user clicks the preset name
- **THEN** it becomes an editable text input; changes are persisted to localStorage on blur/enter

#### Scenario: Copy PokePaste from preset
- **WHEN** user clicks "Copy Pokepaste" on a saved preset
- **THEN** the stored pokepaste string is written to the clipboard

#### Scenario: Delete preset
- **WHEN** user clicks "Delete" on a saved preset
- **THEN** the preset is removed from localStorage and the panel updates immediately

### Requirement: Presets persist across browser sessions
Presets stored in `localStorage['poke-builder-presets']` SHALL be available after a page reload or browser restart. The `savedTeams()` Alpine component SHALL read localStorage on initialization.

#### Scenario: Presets survive page reload
- **WHEN** user saves a preset and reloads the page
- **THEN** the preset appears in the Saved Teams panel on next load

#### Scenario: localStorage empty on first load
- **WHEN** no presets are stored
- **THEN** the Saved Teams panel renders an empty state message "No hay equipos guardados aún"
