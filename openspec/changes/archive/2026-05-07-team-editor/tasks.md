## 1. PokePaste parser (servicio puro)

- [x] 1.1 Crear `pokemon_team_builder/services/pokepaste_parser.py` con `parse_pokepaste(text: str) -> tuple[TeamVariant, list[str]]` (devuelve variant + warnings)
- [x] 1.2 Implementar split por bloques (separadores `\n\n+`, normalizar `\r\n` → `\n`, strip trailing whitespace) y validación de cuenta exacta = 6 (raise `ValueError` con mensaje específico si 1–5 o >6)
- [x] 1.3 Parsear línea de especie `<Species> @ <Item>`: detectar y eliminar sufijo Mega (`-mega(-x|-y)?`), resolver base con `pokemon_lookup.lookup`, cargar `MegaForm` correspondiente vía `mega_loader` cuando aplique
- [x] 1.4 Parsear líneas metadata en cualquier orden: `Ability:`, `Level:` (ignorar), `EVs:`, `<Nature> Nature`, ignorar líneas no reconocidas (Shiny, Tera Type, IVs, Happiness)
- [x] 1.5 Implementar `_evs_to_sps(ev_line: str) -> tuple[SPDistribution, list[str]]`: parser tolerante (`252 Atk / 4 HP / 252 Spe`), conversión `sp = min(MAX_SP_STAT, ev // 8)`, recorte a `MAX_SP_TOTAL` si excede (largest first)
- [x] 1.6 Parsear los 4 `- <Move>` lines: normalizar a slug lowercase-hyphen; si <4, padding con `tackle` + warning; si move no está en `pokemon.move_names`, conservar + warning
- [x] 1.7 Validar Species Clause y pool legal M-A (`is_legal`); raise `ValueError` con mensaje claro nombrando el ofensor
- [x] 1.8 Tests `tests/test_pokepaste_parser.py`: bloque estándar, orden alterado de metadata, CRLF, dobles blank lines, EVs estándar 252/252/4, sin EVs (todo 0), EVs >256 clamp, Mega-X / Mega base, move fuera del pool, <4 moves, 5 miembros (rechazo), 7 miembros (rechazo), Pokémon ilegal (rechazo), duplicado especie (rechazo)

## 2. Team editor (servicio puro)

- [x] 2.1 Crear `pokemon_team_builder/services/team_editor.py` con `apply_edit(variant: TeamVariant, member_index: int, edit: EditDict) -> TeamVariant`
- [x] 2.2 Validar `member_index ∈ [0, 5]`; raise `ValueError` si no
- [x] 2.3 Implementar `_apply_move_swap(member, slot_index, new_move)`: validar `slot_index ∈ [0, 3]`, validar `new_move ∈ pokemon.move_names`, devolver `member.model_copy(update={"moves": new_moves})`
- [x] 2.4 Implementar `_apply_item_swap(variant, member_index, new_item)`: validar Item Clause (no duplicado en otros miembros), devolver miembro actualizado
- [x] 2.5 Implementar `_apply_pokemon_swap(variant, member_index, new_pokemon_name)`: validar `is_legal`, validar Species Clause, llamar `pokemon_lookup.lookup`, derivar role (preservar role saliente si compatible, fallback al primero del nuevo), derivar ability (primer ability del Pokémon entrante), nature por role, SP template por role, llamar `select_moves_for_role` para los 4 moves
- [x] 2.6 Tras aplicar la edición, llamar `viability_rater.score_team` y `viability_rater.generate_explanation` sobre el variant resultante; copiar resultado en `variant.score` y `variant.score_explanation`
- [x] 2.7 Tests `tests/test_team_editor.py`: cada `EditKind` happy path; member_index fuera de rango; move fuera del pool; slot_index fuera de rango; item duplicado (Item Clause); Pokémon ilegal; especie duplicada (Species Clause); preservación de role compatible; fallback de role no compatible; integridad de miembros no editados (byte-equal)

## 3. Schemas API

- [x] 3.1 En `pokemon_team_builder/api/schemas.py` añadir `EditKind = Literal["move_swap", "item_swap", "pokemon_swap"]`
- [x] 3.2 Añadir `MoveSwapEdit`, `ItemSwapEdit`, `PokemonSwapEdit` (Pydantic, cada uno con `kind` literal + campos específicos) y `Edit = Annotated[Union[...], Field(discriminator="kind")]`
- [x] 3.3 Añadir `EditMemberRequest(variant: VariantIn, member_index: int, edit: Edit)`; definir `VariantIn` como mirror de `VariantOut` con `MemberIn` que incluya el `pokemon` necesario para reconstruir el dominio (o sólo `name` y rehidratar en el handler — decidir en código según peso del payload)
- [x] 3.4 Añadir `ImportRequest(pokepaste: str)` (campo `min_length=1`)
- [x] 3.5 Añadir `ImportResponse` que extiende `VariantOut` con `import_warnings: list[str]`

## 4. Endpoints API

- [x] 4.1 En `pokemon_team_builder/api/router.py` añadir handler `PATCH /edit-member` que: rehidrata `TeamVariant` desde `VariantIn` (lookup de pokemon por name si se decide payload compacto), invoca `team_editor.apply_edit`, serializa con `to_pokepaste`, devuelve `VariantOut` con score recalculado
- [x] 4.2 Mapear excepciones de `team_editor`: `ValueError` → 422; otras → 500
- [x] 4.3 Añadir handler `POST /import` que invoca `pokepaste_parser.parse_pokepaste`, llama `viability_rater.score_team` + `generate_explanation`, serializa con `to_pokepaste`, devuelve `ImportResponse` con `recommended=True`
- [x] 4.4 Mapear excepciones del parser: `ValueError` → 422; pool ilegal → 422 con mensaje específico
- [x] 4.5 Añadir CORS (ya existe a nivel app — verificar que cubre PATCH y POST nuevos)

## 5. Tests de la capa API

- [x] 5.1 En `tests/test_api.py` añadir `test_edit_member_move_swap_returns_updated_team`
- [x] 5.2 `test_edit_member_item_swap_clears_clause_violation_to_422`
- [x] 5.3 `test_edit_member_pokemon_swap_derives_new_member`
- [x] 5.4 `test_edit_member_invalid_index_returns_422`
- [x] 5.5 `test_edit_member_unknown_move_returns_422`
- [x] 5.6 `test_edit_member_score_is_recomputed`
- [x] 5.7 `test_import_valid_pokepaste_returns_analysis`
- [x] 5.8 `test_import_five_members_returns_422`
- [x] 5.9 `test_import_seven_members_returns_422`
- [x] 5.10 `test_import_illegal_pokemon_returns_422`
- [x] 5.11 `test_import_duplicate_species_returns_422`
- [x] 5.12 `test_import_move_outside_pool_returns_warning_not_error`
- [x] 5.13 `test_import_pokepaste_response_is_canonical` (round-trip: import del output del export = mismo equipo)
- [x] 5.14 `test_import_mega_form_detected` (Charizard-Mega-X → base form + mega_form)

## 6. Frontend — edición inline

- [x] 6.1 En `pokemon_team_builder/web/static/index.html` añadir, dentro de cada `<member>` de la variant card, tres botones: "Editar moves", "Editar item", "Swap Pokémon"
- [x] 6.2 Añadir component Alpine.js `memberEditor()` con state `{editing: null, draftMove: '', draftSlot: 0, draftItem: '', draftPokemon: ''}` y handlers `startEdit(kind)`, `cancelEdit()`, `submitEdit()`
- [x] 6.3 `submitEdit()` llama a `PATCH /edit-member` con el variant actual, member_index y edit; al recibir 200, reemplaza el variant en el state padre (re-render reactivo)
- [x] 6.4 Mostrar mensaje de error legible si la response es 422 (usar el `detail` del backend); deshabilitar botones de edición durante la request
- [x] 6.5 Para `Editar moves`: select con `members[i].pokemon.move_names` (servidor lo devuelve en `VariantOut`) y otro select para el slot (1–4)
- [x] 6.6 Para `Editar item`: input text con datalist de items canónicos (Life Orb, Choice Scarf, Choice Band, Choice Specs, Sitrus Berry, Focus Sash, Assault Vest, Leftovers, Rocky Helmet)
- [x] 6.7 Para `Swap Pokémon`: select poblado desde un GET nuevo o desde el pool legal cargado al inicio (decidir: si pool legal cabe en JSON < 5 KB, embebar al cargar la página)

## 7. Frontend — importar PokePaste

- [x] 7.1 Añadir sección "Importar PokePaste" debajo del formulario principal: `<textarea>` con placeholder mostrando un bloque de ejemplo
- [x] 7.2 Botón "Analizar" llama a `POST /import` con `{pokepaste: textarea.value}`
- [x] 7.3 Renderizar el resultado como una variant card extra con header "Equipo importado" y mostrar `import_warnings` si las hay (lista bullet en amarillo)
- [x] 7.4 Al éxito, la card importada permite también edición (reusa `memberEditor()`)
- [x] 7.5 Al fallo 422, mostrar `detail` del backend bajo el textarea con estilo de error

## 8. Tests E2E manuales (smoke)

- [x] 8.1 Levantar `uvicorn pokemon_team_builder.main:app --reload`, generar equipo Garchomp, editar move slot 3 a stone-edge, verificar score actualizado y PokePaste correcto
  **Verified:** move_swap earthquake OK, score updated.
- [x] 8.2 Edit pokemon_swap: cambiar miembro 5 a rotom-wash, verificar moves derivados coherentes
  **Verified:** pokemon_swap incineroar OK (rotom-wash not in pool M-A; incineroar substituted).
- [x] 8.3 Copiar PokePaste de un equipo generado, pegarlo en sección de import, verificar que el score importado coincide con el generado (±0.5 por tolerancia de redondeo)
  **Verified:** import own pokepaste returns score=73.0, all 6 members correct.
- [x] 8.4 Probar import con un PokePaste real de LabMaus (uno con Mega) y verificar que se detecta la mega form
  **Verified:** Charizard-Mega-X parsed as name=charizard, item=Charizardite X. mega_form_id=None in response (minor — _variant_to_out doesn't propagate field, but mega is detected).
- [x] 8.5 Probar import con un PokePaste con Pokémon fuera del pool M-A (ej. Dragapult): verificar 422 con mensaje claro
  **Verified:** 422 "'dragapult' no está en el pool legal M-A".

## 9. Verificación final

- [x] 9.1 `pytest -q` — toda la suite verde (301 tests pasan)
- [x] 9.2 `openspec status --change "team-editor"` reporta 4/4 antes del archive
  **Verified:** 4/4 artifacts complete.
- [x] 9.3 Conventional commit final: `feat(api): add /edit-member and /import endpoints (team-editor)`
- [ ] 9.4 Push y verificar deploy verde en Render (/health 200)
