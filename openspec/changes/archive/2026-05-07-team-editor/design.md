## Context

La aplicación expone un único endpoint stateful-free `POST /generate` que devuelve 1–3 variantes completas. Los servicios de dominio (`team_generator`, `viability_rater`, `synergy_engine`, `replica_exporter`) son funciones puras sobre modelos Pydantic, lo cual hace barato componerlos en flujos nuevos. El frontend es Alpine.js (sin build step) sirviendo desde `web/static/`. La regulación competitiva objetivo es Champions M-A (pool legal en `data/legal_pool_mA.json`, validación con `is_legal`). El formato de output canónico es PokePaste Showdown (EVs en notación 0–252) pero el dominio interno usa SP raw (0–32 por stat, max 66 totales).

## Goals / Non-Goals

**Goals:**
- Permitir refinar un equipo recién generado sin perder el resto del trabajo (cambiar 1 move o 1 Pokémon NO debe re-llamar a `generate_team`).
- Aceptar PokePaste externo (LabMaus, torneos, mensajes Discord) y devolver score + análisis sin pedir al usuario que escriba un anchor.
- Mantener arquitectura: servicios puros + endpoints finos + frontend reactivo sin nuevas dependencias.
- Recálculo de score y EV notes consistente con `/generate` — el usuario debe poder comparar manzanas con manzanas.

**Non-Goals:**
- Persistencia de equipos editados (sin BD, sin sesiones — el cliente envía el state cada vez).
- Editor avanzado tipo Showdown Teambuilder (drag-and-drop completo, autocomplete de move pool en tiempo real). v1 = selectores inline.
- Edición de SPs en el editor — los SPs se rederivan del role en cada swap. (El usuario que quiera afinar SPs manualmente exporta, edita el PokePaste, vuelve a importar.)
- Análisis de equipos de menos de 6 miembros: el import requiere exactamente 6 (rechaza 422 si vienen 1–5; rechaza 422 si vienen >6).
- Validación de torneos no Champions (el pool legal es M-A; un PokePaste con un Pokémon fuera de pool se rechaza).

## Decisions

**Decisión 1: PATCH /edit-member en lugar de POST /regenerate**
- El endpoint recibe el `TeamVariant` completo + índice + edición. El servidor es stateless — no guarda el equipo entre requests.
- Alternativa descartada: guardar el equipo en sesión y referenciarlo por id. Añade estado, complica el tier gratuito de Render (memoria volátil entre cold starts) y no aporta — el payload completo es ~3 KB JSON.
- Verbo PATCH (no PUT): es una modificación parcial sobre un recurso lógico (el `TeamVariant`), idempotente para la misma edición.

**Decisión 2: Tres tipos de edit, discriminator field `kind`**
- `EditKind = Literal["move_swap", "item_swap", "pokemon_swap"]`
- `move_swap`: requiere `slot_index` (0–3) y `new_move` (slug); valida que `new_move ∈ pokemon.move_names`.
- `item_swap`: requiere `new_item` (string libre, validado solo contra duplicados con otros miembros — Item Clause).
- `pokemon_swap`: requiere `new_pokemon_name` (slug); valida `is_legal` + Species Clause; rederiva ability/nature/SPs/moves usando los mismos defaults que `team_generator` (primer ability, nature por role, SP template por role, `select_moves_for_role`).
- Alternativa descartada: un solo endpoint genérico con `Optional` por campo. Discriminator union es más explícita y FastAPI valida el shape completo por `kind`.

**Decisión 3: Re-score completo en cada edit (no diff)**
- Tras aplicar la edición, llamamos `score_team(variant)` y `generate_explanation(variant, score)` enteros sobre el equipo modificado.
- El cálculo es O(6) y no toca red — coste despreciable. El intento de "diff scoring" añadiría complejidad sin ganancia.
- EV notes: si existe `ev_explainer` (cambio `ev-precision` aplicado) se reutiliza; si no, las EV notes vienen del fallback genérico actual del router.

**Decisión 4: PokePaste parser en `services/pokepaste_parser.py` (no en api/)**
- El parser es lógica de dominio pura (string → modelo Pydantic). No depende de FastAPI.
- Esto permite testearlo con `pytest` sin levantar TestClient y reutilizarlo desde la CLI si en el futuro se añade `pokemon-team-builder import team.txt`.
- Estructura de bloque PokePaste tolerada (orden flexible salvo línea 1):
  ```
  Garchomp @ Life Orb         <- línea 1: "Nombre @ Item" (item opcional)
  Ability: Rough Skin         <- "Ability: X"
  Level: 50                   <- ignorada (siempre 50 en M-A)
  EVs: 252 Atk / 4 HP / 252 Spe   <- "EVs: ..." (opcional)
  Jolly Nature                <- "<Nature> Nature"
  - Earthquake                <- 4 líneas "- Move"
  - Dragon Claw
  - Stone Edge
  - Protect
  ```
- Bloques separados por línea en blanco (uno o más); trailing whitespace tolerado.
- Líneas no reconocidas (p. ej. `Shiny: Yes`, `Tera Type: Ground`, `IVs: 0 Atk`) se ignoran silenciosamente — no son competitivamente relevantes en M-A.

**Decisión 5: Conversión EV → SP determinista con clamp**
- `sp = min(MAX_SP_STAT, ev // 8)` por stat (Showdown EV 252 → SP 31, 250 → SP 31; Showdown EV 4 → SP 0).
- WHY `// 8`: 1 SP = 8 EVs en términos de Champions (los SPs son la abstracción Champions del sistema EV de juego principal).
- Si la suma de SPs convertidos excede `MAX_SP_TOTAL` (66), se trunca proporcionalmente (sort por SP desc, recortar el último que cabe). Es defensivo — un PokePaste válido de Showdown nunca llega a 66 SP totales (508 EVs / 8 = 63.5).
- Tests cubren: 252/252/4 estándar, splits raros (88/156/etc.), todo a 0, valores >252 (defensivo, no debería pasar — clamp).

**Decisión 6: Validación de moves en pokepaste-import**
- Al parsear, cada move se compara con `pokemon.move_names` (vía `pokemon_lookup.lookup`). Si un move NO está en el pool del Pokémon, se conserva tal cual en el `TeamMember.moves` y se añade a un campo `import_warnings: list[str]` en la response (no rechaza el import — el usuario decide).
- WHY: muchos PokePaste de torneo tienen typos (`Earthquake` vs `earthquake`, espacios, mayúsculas); además, PokeAPI no tiene siempre el move pool completo de Gen 9 events. Rechazar daría más fricción que valor.
- Las validaciones HARD (rechazo 422) son: 1–5 miembros (faltan), >6 miembros (sobran), un nombre de Pokémon que no se puede resolver (`pokemon_lookup` falla), o un Pokémon fuera del pool legal.

**Decisión 7: Frontend — selectores inline, no modals**
- Cada miembro muestra: `[Editar moves ▾] [Editar item ▾] [Swap ▾]`.
- Click en `Editar moves` → expande un `<select>` con los 4 slots × move pool del Pokémon, "Aplicar" + "Cancelar".
- Click en `Editar item` → expande un `<input type="text">` libre con autocomplete contra una lista estática de items canónicos (Life Orb, Choice Scarf, Choice Band, etc.).
- Click en `Swap` → expande un `<select>` con todos los Pokémon del pool legal (≈ 50 en M-A), excluyendo los ya presentes (Species Clause).
- El re-render de la card usa el `VariantOut` devuelto por `PATCH /edit-member` — Alpine.js reactiva el `x-data` y la card se actualiza in-place.
- Sección "Importar PokePaste" debajo del formulario principal: textarea + botón "Analizar"; el resultado renderiza una variant card EXTRA con la etiqueta "Imported".
- Alternativa descartada: modals — añaden ruido visual y el flujo de edición es lo bastante simple para inline.

## Risks / Trade-offs

- [Riesgo] Payload `PATCH /edit-member` envía el `TeamVariant` completo, incluido `PokemonData` con todos los moves (move_names puede ser >100 entradas). → Mitigación: el move_names del input se ignora; el servidor llama a `pokemon_lookup` para revalidar el state desde scratch. El cliente puede enviar una versión "compacta" (solo nombre + role + item + nature + sp + moves + ability) y el servidor enriquece. Aceptable: ~10 KB de payload no es problema.
- [Riesgo] Race condition cliente-servidor: usuario edita Member A, mientras la response viaja edita Member B sobre el state stale. → Mitigación: el cliente serializa edits (deshabilita botones de edit hasta que vuelve la response). Sin optimistic UI en v1.
- [Riesgo] PokePaste con Pokémon Mega forms (Charizard-Mega-X, Garchomp-Mega) llega como nombre con sufijo. → Mitigación: el parser detecta sufijo `-mega(-x|-y)?` y lo despoja, lookup va al base form, y se asigna el `mega_form` correspondiente desde el catálogo (`mega_loader`).
- [Trade-off] Sin edición de SPs/nature en el editor v1 → simplifica UI; el power user usa export → editar PokePaste → import.
- [Trade-off] El score tras `pokemon_swap` puede caer drásticamente si el nuevo Pokémon rompe coverage o roles. → Aceptable y deseable: es justo el feedback que el usuario quiere.

## Migration Plan

1. Implementar `services/pokepaste_parser.py` + tests (parsing aislado, sin red).
2. Implementar `services/team_editor.py` + tests (apply_edit aislado, mocks de `pokemon_lookup`).
3. Añadir schemas a `api/schemas.py` (`EditMemberRequest`, `EditKind` discriminated union, `ImportRequest`, `ImportResponse`).
4. Añadir handlers `PATCH /edit-member` y `POST /import` a `api/router.py`.
5. Tests de integración en `tests/test_api.py`: cubrir cada `EditKind` + casos de error + import válido + import malformado + import con Pokémon ilegal.
6. Frontend: añadir Alpine.js components a `web/static/index.html` y handlers en `app.js`.
7. Manual smoke en local (`uvicorn ... --reload`): generar equipo, editar miembros, copiar PokePaste, pegarlo en sección de import, ver el mismo score.
8. Deploy a Render: commit, push, healthcheck verde.
9. Rollback: los endpoints son aditivos; revertir = quitar handlers + schemas. Frontend: revertir `index.html` y `app.js`. Sin migraciones de datos.

## Open Questions

- ¿El `pokemon_swap` debe permitir que el reemplazo herede el role del miembro saliente, o derivar role nuevo desde la heurística de roles del Pokémon entrante? → Recomendación: heredar role saliente cuando el Pokémon entrante lo soporta (su set de roles candidatos lo incluye); fallback al primer role del Pokémon entrante. Razón: preservar la intención del equipo.
- ¿Devolver PokePaste re-serializado en la response de `/edit-member` o que el cliente lo regenere? → Decisión: devolverlo (consistente con `/generate`, evita duplicar lógica de serialización en JS).
- ¿`/import` debe aceptar también el formato JSON de Showdown Teambuilder (no solo texto)? → Fuera de scope v1; añadir si los usuarios lo piden.
- ¿Renderizar el "Imported" card encima o debajo del bloque de variantes generadas? → Decisión: debajo, con separador visual ("Equipos importados") — no se confunden con generados.
