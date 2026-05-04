## MODIFIED Requirements

### Requirement: `lead_support` nunca recibe un Choice item
`lead_support` SHALL be added to `_NO_CHOICE_ROLES`.
Un soporte con Choice item queda locked-in Tailwind o Fake Out desde turno 2 — inutilizable.

#### Scenario: lead_support no recibe Choice Scarf en fallback
- **WHEN** `_assign_items` procesa un segundo `lead_support` cuyo default (Focus Sash) ya está en uso
- **THEN** el item asignado no es ningún item de `_CHOICE_ITEMS`

---

### Requirement: `assign_role` asigna sweeper role por stat dominante, no por orden de evaluación
`assign_role` SHALL compare `max(atk, spa)` to determine sweeper role when both stats qualify.
Un Pokémon con Atk 105 / SpA 125 (e.g., Hydreigon) debe recibir `special_sweeper`, no `physical_sweeper`.

#### Scenario: Hydreigon recibe special_sweeper aunque Atk >= 100
- **WHEN** `assign_role` se llama con un Pokémon con Atk=105, SpA=125
- **THEN** el rol primario devuelto es `special_sweeper`

#### Scenario: Mon con solo Atk >= 100 sigue recibiendo physical_sweeper
- **WHEN** `assign_role` se llama con Atk=130, SpA=70
- **THEN** el rol primario devuelto es `physical_sweeper`

#### Scenario: Mon con ambos >= 100 y Atk > SpA recibe physical_sweeper
- **WHEN** `assign_role` se llama con Atk=125, SpA=105
- **THEN** el rol primario devuelto es `physical_sweeper`

---

### Requirement: Loaded Dice eliminado del backup pool
`Loaded Dice` SHALL be removed from `_BACKUP_ITEMS`.
El sistema nunca genera multi-hit moves — el item nunca puede activarse.

#### Scenario: Loaded Dice no aparece en ningún equipo generado
- **WHEN** se genera un equipo para cualquier ancla
- **THEN** ningún miembro lleva `"Loaded Dice"`

---

### Requirement: SP template para `redirect`
`role_sp_templates.json` SHALL include a `redirect` template: `{"hp": 32, "spd": 32, "def": 2}`.
Los redirectores necesitan bulk para sobrevivir mientras absorben ataques; el fallback a sweeper (Atk/SpA 32) es incorrecto.

#### Scenario: Redirect recibe SP template de bulk
- **WHEN** `suggest_sp_distribution` se llama con role="redirect"
- **THEN** `sp.hp == 32` y `sp.spd == 32`

---

### Requirement: `_item_is_activatable` verifica contra moveset generado, no solo learnset
Para `White Herb`, `Throat Spray`, y futuros items con precondición de move,
`_assign_items` SHALL check activatability against the actual moves that `select_moves_for_role`
will produce for that role, not against the full learnset.

Esto requiere calcular los moves antes de asignar el item, o pre-verificar que el role
genera el move requerido en algún slot.

#### Scenario: Wall con White Herb no recibe el item si su moveset no incluye stat-drop move
- **WHEN** `_assign_items` evalúa White Herb para un `physical_wall`
- **THEN** White Herb es descartado porque el moveset de wall no incluye moves de auto-stat-drop

#### Scenario: Sweeper especial con Overheat en moveset recibe White Herb
- **WHEN** `_assign_items` evalúa White Herb para un `special_sweeper` que conoce overheat
  Y overheat aparece en slot 4 (role move de sweeper especial)
- **THEN** White Herb puede ser asignado

---

### Requirement: Tabla de incompatibilidades item↔moveset
`_assign_items` SHALL enforce que Weakness Policy no se asigne a un Pokémon cuyo
rol primario lleva setup move en slot 4 (swords-dance, dragon-dance, nasty-plot, etc.).
WP + setup move es anti-sinérgico: si setupeas no quieres recibir un super-effective;
si te lo meten para activar WP, normalmente mueres antes de aprovechar el boost.

#### Scenario: Physical sweeper con Dragon Dance no recibe Weakness Policy
- **WHEN** `_assign_items` asigna el item a un physical_sweeper que conoce dragon-dance
  Y dragon-dance es el role move del slot 4
- **THEN** Weakness Policy es descartado; el siguiente item válido en la chain es asignado

#### Scenario: Physical sweeper sin setup move mantiene Weakness Policy
- **WHEN** el physical_sweeper no tiene ningún setup move en `_SETUP_MOVES`
- **THEN** Weakness Policy es asignado normalmente
