## MODIFIED Requirements

### Requirement: `_items_points` elimina código muerto y documenta su limitación
The Life Orb duplicate penalty in `_items_points` SHALL be removed — Life Orb is not
in the Champions item pool and the check can never trigger.
A comment SHALL be added documenting that the 15-point component is structurally
a constant offset (Item Clause guarantees uniqueness), and that this is intentional
in v1 (discriminating item quality is a v2 concern).

#### Scenario: No hay referencia a Life Orb en _items_points
- **WHEN** `_items_points` es inspeccionado
- **THEN** no hay ninguna referencia a "Life Orb" en el código de la función

#### Scenario: Teams generados normalmente siguen recibiendo 15 puntos por items
- **WHEN** `_items_points` se llama sobre un TeamVariant con 6 items distintos
- **THEN** devuelve 15

---

### Requirement: `analyze_coverage` documenta que mide tipos del Pokémon, no moves
`analyze_coverage` is documented to use `pokemon.types` for offensive gap detection,
not the actual moveset. This is a known limitation.
A docstring note SHALL be added explaining the limitation and that v2 will use actual moves.

#### Scenario: Coverage report incluye el tipo del Pokémon aunque el moveset no lo cubra
- **WHEN** `analyze_coverage` se llama con un equipo donde un Pokémon es tipo Fire
  pero su moveset no incluye ningún Fire move
- **THEN** "fire" NO aparece en `offensive_gaps` (porque el Pokémon lo "cubre" por tipo)
- **AND** hay un comentario en el código documentando esta limitación conocida
