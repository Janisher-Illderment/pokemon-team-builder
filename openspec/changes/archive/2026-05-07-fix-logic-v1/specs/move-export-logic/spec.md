## MODIFIED Requirements

### Requirement: `_fallback_move` nunca devuelve un move ya en `used`
`_fallback_move` SHALL check `used` in every return path, including the last-resort
generic list. If all options are exhausted, SHALL raise `TeamBuildError`, not silently
return a duplicate.

#### Scenario: Move pool exhausto con genéricos en used
- **WHEN** `_fallback_move` se llama con `used = {"protect","tackle","scratch","pound","growl","leer"}`
  Y `move_pool` no contiene ningún move fuera de esos
- **THEN** se levanta `TeamBuildError`, no se devuelve un duplicado

#### Scenario: Move pool normal devuelve move no usado
- **WHEN** `_fallback_move` se llama con un pool normal y `used = {"protect"}`
- **THEN** devuelve cualquier move del pool que no sea "protect"

---

### Requirement: `_MOVE_CATEGORY` vacío falla en pass 0
When `_MOVE_CATEGORY.get(candidate, "")` returns `""` (move not registered),
the slot-2 and slot-3 pass-0 guards SHALL treat it as ineligible in pass 0,
not silently accept it.

#### Scenario: Move desconocido no se elige en pass 0
- **WHEN** hay un move en `_STAB_BY_TYPE` que no tiene entrada en `_MOVE_CATEGORY`
- **THEN** ese move no se elige en pass 0 independientemente del `primary_cat`

#### Scenario: Move desconocido sí puede elegirse en pass 1
- **WHEN** no hay otro STAB/coverage disponible y el move desconocido es la única opción
- **THEN** se elige en pass 1 (fallback — mejor que nada)

---

### Requirement: Protect verificado contra move_pool
Slot 1 SHALL only assign `"protect"` if `"protect"` is in `pokemon.move_names`.
If not, slot 1 SHALL fall back to `_fallback_move` for that slot.

#### Scenario: Pokémon con Protect en learnset recibe Protect en slot 1
- **WHEN** `"protect"` está en `pokemon.move_names`
- **THEN** `slot1 == "protect"`

#### Scenario: Pokémon sin Protect recibe otro move en slot 1
- **WHEN** `"protect"` NO está en `pokemon.move_names`
- **THEN** `slot1` es el primer move disponible del pool (no "protect")

---

### Requirement: Nature derivada del primary attack stat del moveset elegido
Nature SHALL be derived from the actual attack category of the Pokémon's slot-2 move
(the STAB move), not from the role label alone.

Rules:
- If slot-2 is physical → speed-boosting physical nature (Jolly for sweepers/leads, Careful [wrong] → use Jolly)
- If slot-2 is special → speed-boosting special nature (Timid for sweepers, Calm for walls/support)
- For walls: Impish (physical) or Calm (special) based on dominant defensive stat, not role
- For trick_room_setter: always Sassy (wants low Spe)
- For redirect: Calm (always wants bulk/SpD regardless of STAB category)

#### Scenario: Lead especial recibe Timid, no Jolly
- **WHEN** un `lead_support` tiene slot-2 STAB especial (e.g., Hurricane)
- **THEN** nature = "Timid" (no "Jolly")

#### Scenario: Lead físico mantiene Jolly
- **WHEN** un `lead_support` tiene slot-2 STAB físico (e.g., Fake Out, Brave Bird)
- **THEN** nature = "Jolly"

#### Scenario: TR setter siempre recibe Sassy
- **WHEN** role primario es `trick_room_setter`
- **THEN** nature = "Sassy" independientemente del moveset

---

### Requirement: `_format_species` tiene tabla de overrides para nombres especiales
Some Pokémon names have lowercase letters that must be preserved.
`_format_species` SHALL apply a lookup table of overrides before the generic capitalize logic.

Known overrides (verified against Showdown Pokédex and pokepast.es):
- `"kommo-o"` → `"Kommo-o"` (NOT "Kommo-O")
- `"ho-oh"` → `"Ho-Oh"` (both uppercase — already correct with current logic, but add for explicitness)
- `"porygon-z"` → `"Porygon-Z"` (already correct)

#### Scenario: kommo-o se formatea correctamente
- **WHEN** `_format_species("kommo-o")` se llama
- **THEN** devuelve `"Kommo-o"`

#### Scenario: Species normal sigue funcionando igual
- **WHEN** `_format_species("charizard")` se llama
- **THEN** devuelve `"Charizard"`

#### Scenario: Forma regional se formatea correctamente
- **WHEN** `_format_species("raichu-alola")` se llama
- **THEN** devuelve `"Raichu-Alola"`
