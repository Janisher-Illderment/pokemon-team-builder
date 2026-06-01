# ADR — Team Optimizer + Rol coherente + EVs en "Valorar equipo"

- **Status:** Proposed
- **Date:** 2026-06-01
- **Author:** Sola (Solution Architect)
- **Supersedes / extends:** `docs/adr-team-rater.md` (la feature "Valorar equipo" — `services/team_rater.py`, `POST /rate-team`, schemas `TeamRatingOut`/`MemberRatingOut`/`SuggestionOut`, pestaña SPA "Valorar"). Este ADR es **estrictamente aditivo** sobre esa base.
- **Scope:** tres adiciones a "Valorar equipo": (1) rol coherente por mon en la tarjeta, (2) EVs/SP por mon en la tarjeta, (3) un **optimizador greedy por-mon con fijar/desfijar**.

---

## 1. Contexto

La feature "Valorar equipo" ya valora un PokePaste pegado: `team_rater.rate_team(variant)` devuelve un `TeamRating` con nota global (vía `score_team`), arquetipo auto-detectado, y un `MemberRating` por mon (fit/coherence/intrinsic + moves + strengths/weaknesses + `Suggestion`s builder-diff). Roster FIJO: nunca se sugiere cambiar de especie; las sugerencias son sólo item/moveset/naturaleza/EVs.

Sergio pide tres incrementos. Los dos primeros son de **display** (campos nuevos, sin lógica de juego nueva — todo derivado de servicios existentes). El tercero es el grande: un **optimizador** que, a petición del usuario y respetando los mons que él haya fijado, aplica builds coherentes a los no-fijados para **subir la nota global del equipo**, y muestra el antes→después, el PokePaste resultante y un desglose rankeado de cada cambio aceptado.

**Principio rector (igual que el rater):** orquestación pura por encima de servicios existentes. El optimizador NO introduce conocimiento competitivo nuevo — sólo combina `recommend_member_build` (qué build coherente daría el builder a un mon), `score_team` (cuánto vale el equipo) y `to_pokepaste` (cómo se serializa). La decisión de producto greedy ya está tomada; este ADR la formaliza para que sea **determinista, conservadora y testeable**.

### 1.1. Hechos del código verificados (anclas de reuso)

| Símbolo | Ubicación | Firma / forma relevante |
|---|---|---|
| `rate_team(variant, import_warnings=None) -> TeamRating` | `services/team_rater.py:865` | orquestador del rater |
| `detect_archetype(variant) -> (str, float)` | `team_rater.py:103` | arquetipo + confianza |
| `LOW_CONFIDENCE_CUTOFF = 0.4` | `team_rater.py:75` | regla de baja confianza |
| `_set_coherence(member, variant) -> (float, list[str])` | `team_rater.py:267` | coherencia del set |
| `derive_doubles_tags(pokemon, moves=None, ability=None) -> list[str]` | `synergy_engine.py:607` | tags por mon (C3) |
| `derive_team_tags(variant) -> list[list[str]]` | `synergy_engine.py:702` | tags por mon con contexto de equipo |
| `_sp_summary(sp) -> str` | `team_rater.py:619` | resumen legible de EVs/SP |
| `recommend_member_build(pokemon, roles, archetype="balance", team_sheet="closed", *, format_mode="bo1") -> RecommendedBuild` | `team_generator.py:1222` | build coherente del builder para UNA especie; **nunca cambia de especie** (recomputa sobre el mismo `PokemonData`) |
| `RecommendedBuild(moves, item, nature, sp_distribution, ability, roles)` | `team_generator.py:1203` | dataclass del build recomendado |
| `score_team(variant, format_mode="bo1", *, archetype="balance", team_sheet="closed") -> (float, float)` | `viability_rater.py:395` | nota 0–100 + flex ratio |
| `to_pokepaste(variant) -> str` | `replica_exporter.py:752` | serializa el equipo a PokePaste |
| `apply_edit` / `model_copy(update={"members": ...})` | `team_editor.py:31,52` | patrón canónico para reemplazar un miembro inmutablemente |
| `TeamVariant(members[6], score, archetype, team_sheet, ...)` | `domain/models.py:103` | modelo de equipo (Pydantic, inmutable vía `model_copy`) |
| `TeamMember(pokemon, role, sp_distribution, item, ability, nature, moves[4], mega_form)` | `domain/models.py:88` | modelo de miembro |
| `parse_pokepaste(text) -> (TeamVariant, list[str])` | `pokepaste_parser` (usado en router) | parser de entrada |
| `_team_rating_to_out(rating) -> TeamRatingOut` | `api/router.py:361` | serializador rater→API |

Baseline de tests: **36 ficheros `tests/test_*.py`** (la consigna cita 572 tests). El objetivo es **no romper ninguno** ni cambiar ninguna firma pública.

---

## 2. Decisión — visión general

Tres bloques de cambio, todos aditivos:

1. **Rol coherente (display).** Añadir un campo `role: str` (un label primario legible en ES) a `MemberRating` y `MemberRatingOut`. Se deriva de `derive_doubles_tags(pokemon, moves, ability)` + un refinamiento ligero por item/EVs, mapeado a UN label vía una tabla determinista. Se renderiza en la cabecera de la tarjeta del mon.

2. **EVs (display).** Añadir un campo `sp: dict[str, int]` a `MemberRating`/`MemberRatingOut` (las 6 stats canónicas), poblado desde `member.sp_distribution`. La UI lo renderiza como una rejilla compacta junto a los moves. (Se elige un dict por-stat en vez del string `_sp_summary` para que el front lo formatee y resalte como ya hace en la pestaña de generación.)

3. **Optimizador (POST `/optimize-team`).** Nuevo servicio `services/team_optimizer.py` + endpoint. Entrada: el PokePaste + qué índices están fijados. Salida: nota antes→después, PokePaste optimizado, y lista **rankeada** de cambios aceptados (reusando `Suggestion`). Algoritmo: **greedy por mon** sobre los no-fijados.

Los puntos (1) y (2) son baratos y los hace el rater existente; (3) es un módulo nuevo que **reusa el rater y el builder sin tocarlos**.

---

## 3. Adición (1) — Rol coherente por Pokémon

### 3.1. Por qué `derive_doubles_tags` y no `assign_role`

`assign_role` (synergy_engine) asigna roles a nivel de **especie** (stats base). El usuario pidió explícitamente un rol derivado del **SET real** (moveset + item + EVs + habilidad). `derive_doubles_tags(pokemon, moves, ability)` ya hace exactamente esto: deriva los tags de dobles del moveset+habilidad (es la pieza C3 que el rater ya importa). Reusarlo es lo correcto y evita lógica de juego nueva.

`derive_doubles_tags` produce un subconjunto de: `offensive_threat`, `support_enabler`, `speed_control`, `defensive_pivot`, `weather_setter`, `trick_room_setter` (verificado en `synergy_engine.py:648-691`). No toma item/EVs. El refinamiento por item/EVs (abajo) es lo único nuevo y es puramente de **desempate de label**, no de juego.

### 3.2. De tags → UN label primario legible (ES)

Nueva función pura en `team_rater.py` (donde ya viven los tags y `_invested_offensive_category`):

```
def derive_member_role(member: TeamMember) -> str  # devuelve label ES
```

Algoritmo determinista (primer match gana; orden = prioridad de identidad del mon):

1. `trick_room_setter` ∈ tags → **"Trick Room"**
2. `weather_setter` ∈ tags → **"Inductor de clima"**
3. `support_enabler` ∈ tags Y NO `offensive_threat` → **"Apoyo"**
4. `defensive_pivot` ∈ tags → **"Muro / pivote"**
5. `offensive_threat` ∈ tags → desempate ofensivo por **`_invested_offensive_category(member)`** (ya existe, mira naturaleza+EVs):
   - `"physical"` → **"Atacante físico"**
   - `"special"` → **"Atacante especial"**
   - `None` (sin compromiso claro) → **"Atacante"**
6. `speed_control` ∈ tags → **"Control de velocidad"**
7. fallback (sin tags) → **"Versátil"**

**Refinamiento por item/EVs (lo que aporta más allá de los tags):** sólo se usa en el paso 5 para distinguir físico/especial, vía `_invested_offensive_category` que ya combina naturaleza+EVs. El item NO cambia el label primario (un Choice Scarf no convierte a un atacante en "control de velocidad"); se considera ruido para el label y se deja para una posible mejora futura. Esto mantiene el refinamiento mínimo y conservador.

**Decisión:** la función vive en `team_rater.py` y se llama desde `rate_member` justo después de calcular tags (ya disponibles allí vía `derive_team_tags`). Para evitar recomputar tags, `rate_member` pasa `per_member_tags[index]` a un helper interno `_role_label_from_tags(tags, member)`; `derive_member_role(member)` queda como wrapper público autosuficiente para tests/CLI.

### 3.3. Modelo de datos y render

- `MemberRating`: añadir `role: str` (campo nuevo, **al final** del dataclass para no alterar posicionales — aunque se construye por keyword en `rate_member`, mantenemos orden seguro).
- `MemberRatingOut`: añadir `role: str = ""` (default vacío → retrocompatible; ningún cliente viejo se rompe).
- `_team_rating_to_out` (`router.py:370`): añadir `role=m.role`.
- SPA (`index.html`, cabecera de la tarjeta `rate-member`, junto al `<strong x-text="capitalize(m.name)">` y la nota, ~línea 549): añadir
  `<span class="role-tag" x-text="m.role"></span>`.
  Reusa la clase `.role-tag` ya existente (usada en `.roles` de la pestaña generación, líneas 297/455).

[UNCERTAIN] El orden de prioridad de los pasos 1–7 es una decisión de presentación, no de juego. Se calibra con fixtures (un mon que es a la vez setter de clima y amenaza ofensiva mostrará "Inductor de clima" — su identidad de equipo). Verificable y barato de ajustar.

---

## 4. Adición (2) — Mostrar EVs/SP

### 4.1. Modelo de datos

- `MemberRating`: añadir `sp: dict[str, int]` (claves canónicas `"hp","atk","def","spa","spd","spe"`).
- En `rate_member`, poblar desde `member.sp_distribution`:
  ```
  sp = member.sp_distribution
  sp_dict = {"hp": sp.hp, "atk": sp.atk, "def": sp.def_, "spa": sp.spa, "spd": sp.spd, "spe": sp.spe}
  ```
  (Nota: el campo Pydantic es `def_` con alias `def`; el dict de salida usa la clave `"def"` para que el front la lea igual que en la pestaña generación.)
- `MemberRatingOut`: añadir `sp: dict[str, int] = {}`.
- `_team_rating_to_out`: añadir `sp=dict(m.sp)`.

### 4.2. Render

En la tarjeta `rate-member`, tras el bloque de moves (~línea 570), una rejilla compacta que muestra **sólo las stats > 0** (igual criterio que `_sp_summary`):

```html
<div class="rate-mon-sp sp-grid">
  <template x-for="stat in ['hp','atk','def','spa','spd','spe']" :key="stat">
    <span class="sp-cell" x-show="m.sp[stat] > 0"
          x-text="m.sp[stat] + ' ' + stat.toUpperCase()"></span>
  </template>
</div>
```

Reusa el patrón de rejilla SP de la pestaña de generación (la SPA ya itera SP por stat, app.js:167-183). No se introduce CSS estructural nuevo obligatorio; `.sp-grid`/`.sp-cell` pueden reusar estilos existentes o añadirse mínimamente.

### 4.3. Interacción con el artefacto EV→SP del parser [UNCERTAIN — documentado]

El parser convierte EVs→SP por `val // 8`, así que un spread maxeado real (252/252/4 EVs) aterriza en ~62 SP, no 66 (memoria `feedback_pokepaste_ev_sp_lossy`). Esto **ya está tolerado** en el rater (`_SP_MAXED_FLOOR = 60`). Para el display NO es un problema: mostramos los SP tal cual están en el modelo (lo que el rater puntúa). No asertamos `total == 66` en ningún test de display. El optimizador (§5) hereda este modelo: compara SP-equipo contra SP-equipo bajo la misma convención, así que el artefacto se cancela.

---

## 5. Adición (3) — El Optimizador (lo grande)

### 5.1. Modelo de datos

**Nuevo módulo:** `services/team_optimizer.py` (orquestador puro; importa rater + builder + exporter, nunca al revés — sin ciclo). Dataclasses frozen:

```
@dataclass(frozen=True)
class AcceptedChange:
    member_index: int
    member_name: str
    delta: float                  # +score atribuido a ESTE cambio (≥ 0)
    suggestions: list[Suggestion] # reusa team_rater.Suggestion: el diff build-usuario → build óptimo
    # (item/moveset/naturaleza/EVs; NUNCA species)

@dataclass(frozen=True)
class OptimizationResult:
    score_before: float
    score_after: float
    delta_total: float            # score_after - score_before (≥ 0)
    detected_archetype: str
    archetype_confidence: float
    changes: list[AcceptedChange] # rankeada desc por delta (orden de presentación)
    pokepaste_after: str          # to_pokepaste(variant optimizado)
    locked_indices: list[int]     # echo de los fijados (para la UI)
    import_warnings: list[str]
```

`AcceptedChange.suggestions` reusa el modelo `Suggestion` ya existente: cada `Suggestion` describe un campo cambiado (kind ∈ {move_swap, nature, evs, item}, from_value→to_value, reason_es, priority). Esto da el "qué cambió exactamente" sin un modelo nuevo, y la UI ya sabe renderizar `Suggestion`.

### 5.2. Request / Response (endpoint `POST /optimize-team`)

**Request** (`OptimizeTeamRequest` en `api/schemas.py`):
```
class OptimizeTeamRequest(BaseModel):
    pokepaste: str = Field(min_length=1, max_length=20000)
    locked_indices: list[int] = []   # índices 0..5 de los mons FIJADOS (no se tocan)
```
- `locked_indices` se valida: cada índice ∈ [0,5], deduplicado, y `len < 6` (si los 6 están fijados, no hay nada que optimizar → se devuelve `score_after == score_before`, `changes == []`; no es error).
- Forma deliberadamente igual a `RateTeamRequest` + un campo → mínima superficie nueva.

**Response** (`OptimizeTeamResponse` en `api/schemas.py`):
```
class OptimizeTeamResponse(BaseModel):
    score_before: float
    score_after: float
    delta_total: float
    detected_archetype: str
    archetype_confidence: float
    pokepaste_after: str
    locked_indices: list[int] = []
    changes: list[OptimizedChangeOut] = []
    import_warnings: list[str] = []

class OptimizedChangeOut(BaseModel):
    member_index: int
    member_name: str
    delta: float
    suggestions: list[SuggestionOut] = []   # reusa el SuggestionOut existente
```

La salida da **ambas vistas** que pidió Sergio: (a) resumen `score_before/after/delta_total + pokepaste_after`, y (b) desglose rankeado `changes` (ya ordenado desc por `delta`).

### 5.3. Algoritmo greedy (exacto, determinista)

Función pública:
```
def optimize_team(variant, locked_indices, import_warnings=None) -> OptimizationResult
```

Pasos:

**0. Arquetipo y baseline.** Igual que el rater para mantener la misma escala de nota:
```
detected, confidence = detect_archetype(variant)
scoring_archetype = "balance" if confidence < LOW_CONFIDENCE_CUTOFF else detected
score_before, _ = score_team(variant, archetype=scoring_archetype, team_sheet=variant.team_sheet)
```
**Invariante de escala:** todas las puntuaciones del optimizador usan `scoring_archetype` y `variant.team_sheet` fijos durante toda la corrida. El arquetipo se calcula UNA vez sobre el equipo original y **no se recalcula** tras cada cambio (evita que un swap relabele el equipo y mueva la escala — mismo razonamiento que `team_editor.py:54-60`).

**1. Conjunto candidato.** `candidates = [i for i in range(6) if i not in locked_set]`. Iteración en **orden ascendente de índice** (determinismo total; no depende de scores intermedios).

**2. Por cada candidato `i` (en una sola pasada — ver §5.4 sobre iteración):**
   a. `build = recommend_member_build(member.pokemon, member.role, archetype=scoring_archetype, team_sheet=variant.team_sheet)`. Esto da el build coherente ideal **de la MISMA especie** (estructuralmente imposible cambiar de especie — recomputa sobre `member.pokemon`).
   b. Construir `candidate_member` = el miembro con item/nature/sp_distribution/moves/ability reemplazados por los de `build`, **mismo `pokemon` y `mega_form`** (no se toca especie ni mega):
      ```
      candidate_member = current_member.model_copy(update={
          "item": build.item, "nature": build.nature,
          "sp_distribution": build.sp_distribution,
          "moves": list(build.moves), "ability": build.ability,
          "role": list(build.roles),
      })
      ```
   c. `candidate_variant = current_variant.model_copy(update={"members": <lista con i reemplazado>})` (patrón `team_editor.py:50-52`).
   d. `cand_score, _ = score_team(candidate_variant, archetype=scoring_archetype, team_sheet=current_variant.team_sheet)`.
   e. **Criterio de aceptación:** aceptar si `cand_score > current_score + EPSILON` (mejora **estricta**; `EPSILON = 1e-9` para ruido de float). Si se acepta:
      - `delta = cand_score - current_score` → atribuido a este cambio.
      - `current_variant = candidate_variant`; `current_score = cand_score` (el equipo evoluciona; los cambios siguientes se evalúan sobre el equipo ya mejorado).
      - Diff build-usuario → `list[Suggestion]`: **reusar la maquinaria de diff del rater**. Se extrae el constructor de sugerencias de `_build_suggestions` de modo que se pueda invocar con un `RecommendedBuild` ya calculado (ver §5.5 sobre refactor mínimo). Cada `Suggestion` describe item/move/nature/EVs cambiado.
      - Registrar `AcceptedChange(i, name, delta, suggestions)`.
      Si NO mejora: descartar (el mon se queda con su build original).

**3. Ranking de presentación.** `changes.sort(key=lambda c: (-c.delta, c.member_index))` → desc por delta, desempate determinista por índice.

**4. Salida.** `score_after = current_score`; `pokepaste_after = to_pokepaste(current_variant)`; `delta_total = score_after - score_before`.

### 5.4. Atribución del delta, orden e idempotencia

- **Atribución:** el `delta` de cada cambio es la mejora **marginal en el momento de aplicarlo**, sobre el equipo ya parcialmente optimizado. Es la atribución natural y honesta para un greedy secuencial (suma exacta: `Σ delta == delta_total`, garantía testeable). NO es la mejora "en aislamiento" — y eso es correcto y se documenta: el valor de un cambio depende de los anteriores.
- **Orden de iteración = ascendente por índice** (no por delta estimado). Esto hace la corrida **determinista** e independiente del orden de presentación. El ranking por delta es sólo para mostrar; no afecta qué se acepta.
- **¿Una pasada o varias?** Decisión: **una sola pasada** sobre los candidatos. Una segunda pasada podría exprimir más score (un cambio tardío puede reabrir mejora en uno temprano ya evaluado), pero (a) complica la atribución (un mon aparecería dos veces), (b) el coste sube (≈ `n_candidatos²` llamadas a `score_team`), y (c) greedy de una pasada es suficiente para el objetivo de producto ("subir el score"). Se documenta como límite aceptado en §8. [UNCERTAIN] si una segunda pasada aporta valor material — medible con fixtures; ampliable sin romper la API.

### 5.5. Reuso máximo / refactor mínimo necesario

El optimizador necesita, por cada cambio aceptado, el **diff build-usuario → `list[Suggestion]`**. Esa lógica ya existe en `team_rater._build_suggestions`, pero allí está acoplada a recomputar `recommend_member_build` internamente y a `coherence_reasons`. Para reusarla limpiamente:

- **Refactor mínimo, aditivo, sin romper firmas:** extraer de `_build_suggestions` un helper interno `_diff_to_suggestions(member, rec_build, coherence_reasons, archetype)` que toma un `RecommendedBuild` ya calculado. `_build_suggestions` pasa a ser un wrapper que calcula `rec` + `coherence_reasons` y delega. El optimizador llama al helper directamente con el `build` que ya tiene (evita recomputar `recommend_member_build`). **`_build_suggestions` mantiene su firma pública intacta** → el rater y sus tests no se enteran.
- Alternativamente, si el coste de recomputar es trivial, el optimizador puede llamar a `_build_suggestions(candidate_variant_pre, i, scoring_archetype, coherence_reasons)` directamente. **Decisión:** preferir el helper extraído para no duplicar la llamada a `recommend_member_build` (que dispara lookups). Se valida que el refactor es behavior-preserving con los tests del rater existentes.

Funciones reusadas verbatim: `detect_archetype`, `LOW_CONFIDENCE_CUTOFF`, `recommend_member_build`, `score_team`, `to_pokepaste`, `Suggestion`, `_set_coherence` (para `coherence_reasons` del diff), `derive_doubles_tags` (indirecto vía el rol). Ninguna se modifica salvo el refactor aditivo de `_build_suggestions`.

### 5.6. Endpoint

`api/router.py`, junto a `rate_team_endpoint`:
```
@router.post("/optimize-team", response_model=OptimizeTeamResponse)
def optimize_team_endpoint(req: OptimizeTeamRequest) -> OptimizeTeamResponse:
    try:
        variant, warnings = pokepaste_parser.parse_pokepaste(req.pokepaste)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    # validar locked_indices ∈ [0,5], dedup
    result = team_optimizer.optimize_team(variant, sorted(set(req.locked_indices)), import_warnings=warnings)
    return _optimization_to_out(result)
```
Serializador `_optimization_to_out` análogo a `_team_rating_to_out` (reusa `SuggestionOut`).

### 5.7. Integración SPA

En la pestaña "Valorar", sobre las tarjetas que el rating ya pinta (`teamRating.members`):

1. **Toggle fijar/desfijar por miembro.** Estado nuevo en Alpine: `lockedMembers: {}` (dict `index → bool`). En la cabecera de cada `rate-member` (junto a `m.role` y la nota), un botón:
   ```html
   <button class="lock-toggle" :class="{ 'lock-toggle--on': lockedMembers[mi] }"
           @click="lockedMembers[mi] = !lockedMembers[mi]"
           :title="lockedMembers[mi] ? 'Fijado (no se tocará al optimizar)' : 'Sin fijar'">
     <span x-text="lockedMembers[mi] ? '🔒' : '🔓'"></span>
   </button>
   ```
   Reusa la tarjeta existente; no se duplica el render del mon.

2. **Botón "Optimizar"** junto al de "Valorar" (visible sólo con `teamRating` presente):
   ```html
   <button class="import-btn" @click="optimizeTeam()" :disabled="optimizeLoading || !teamRating">
     <span x-show="!optimizeLoading">Optimizar (no fijados)</span>
     <span x-show="optimizeLoading">Optimizando…</span>
   </button>
   ```

3. **`optimizeTeam()`** en app.js (espejo de `rateTeam`, `app.js:341`): POST `/optimize-team` con `{ pokepaste: ratePaste, locked_indices: Object.keys(lockedMembers).filter(k => lockedMembers[k]).map(Number) }`, `cache:'no-store'`; guarda en `this.optimization`.

4. **Render de AMBAS vistas** (sección nueva `x-show="optimization"`):
   - **(a) Resumen:** `score_before → score_after` (con `scoreTier` para tintar) + `delta_total` (+X) + el `pokepaste_after` en un `<textarea readonly>` con botón "Copiar" reusando `copyPaste(pokepaste, event)` (`app.js:445`).
   - **(b) Desglose rankeado:** `x-for` sobre `optimization.changes` (ya viene ordenado desc por delta); por cada cambio: sprite del mon (`memberSprite`), nombre, `+delta` redondeado, y la lista de `suggestions` reusando exactamente el bloque `.rate-suggestion` ya existente (líneas 588-604) — mismo `kind` badge, `from→to`, `reason`.

   Si `changes.length === 0`: mensaje "El equipo ya está optimizado para los mons no fijados (ningún cambio mejora la nota)".

No se añade pestaña ni ruta nueva; todo vive bajo la sección "Valorar" existente.

---

## 6. Endpoint nuevo — resumen de forma JSON

```
POST /optimize-team
Request:  { "pokepaste": "<texto>", "locked_indices": [0, 3] }
Response: {
  "score_before": 61.0,
  "score_after": 78.0,
  "delta_total": 17.0,
  "detected_archetype": "hyper_offense",
  "archetype_confidence": 0.83,
  "pokepaste_after": "Incineroar @ ...\n\n...",
  "locked_indices": [0, 3],
  "changes": [
    { "member_index": 4, "member_name": "Flutter Mane", "delta": 11.0,
      "suggestions": [ { "kind":"evs","target_field":"sp_distribution","from_value":"...","to_value":"...","reason":"...","priority":2 } ] },
    { "member_index": 1, "member_name": "Landorus", "delta": 6.0, "suggestions": [ ... ] }
  ],
  "import_warnings": []
}
```

---

## 7. Tests a añadir

Nuevo fichero `tests/test_team_optimizer.py` (+ extensiones a `tests/test_team_rater.py` para rol/EVs). Sin tocar conteos de tests existentes salvo añadir.

**Display (rol + EVs):**
- `test_member_role_label_es`: para builds conocidos, `derive_member_role` devuelve el label esperado (atacante físico vs especial vía `_invested_offensive_category`; setter de TR; muro; etc.).
- `test_member_rating_includes_role_and_sp`: `rate_member` puebla `role` (no vacío) y `sp` (dict de 6 claves, suma == suma del `sp_distribution`).
- `test_rate_team_out_serializes_role_sp`: el endpoint `/rate-team` devuelve `role` y `sp` en cada miembro (retrocompatibilidad: clientes que no los lean no rompen).

**Optimizador — invariantes duros (los que pidió Sergio):**
- `test_locked_members_never_change`: con `locked_indices=[0,2,5]`, en el `pokepaste_after` esos miembros tienen item/nature/SP/moves **idénticos** al input; ningún `AcceptedChange.member_index` ∈ locked.
- `test_species_never_changes`: para todo miembro, la especie (y `mega_form`) en `pokepaste_after` == input. Ningún `Suggestion.kind` es species.
- `test_score_after_ge_before`: `score_after >= score_before` SIEMPRE (criterio de aceptación es mejora estricta; si nada mejora, igualdad).
- `test_delta_attribution_sums`: `sum(c.delta for c in changes) == delta_total` (tolerancia float).
- `test_determinism`: dos corridas con el mismo input + mismos locks → resultado byte-idéntico (mismo `pokepaste_after`, mismo orden de `changes`).
- `test_all_locked_is_noop`: `locked_indices=[0..5]` → `changes==[]`, `score_after==score_before`, `pokepaste_after==to_pokepaste(input)`.
- `test_already_optimal_no_changes`: un equipo ya construido por el builder no produce cambios (o sólo no-negativos) — greedy no degrada.
- `test_optimized_paste_roundtrips`: `parse_pokepaste(pokepaste_after)` no lanza y produce 6 miembros (la salida es importable). [UNCERTAIN] tolerar artefacto EV→SP — NO asertar `SP==66`.
- `test_endpoint_optimize_team`: POST con paste real + locks → 200, forma de `OptimizeTeamResponse`; paste inválido → 422.
- `test_invalid_locked_indices`: índice fuera de [0,5] → 422 (o se ignora, según validación elegida; el test fija el contrato).

**No-regresión:** correr la suite completa; los 36 ficheros / 572 tests deben seguir verdes (el refactor de `_build_suggestions` es behavior-preserving).

---

## 8. Riesgos, límites y `[UNCERTAIN]`

- **[RISK] Greedy no es óptimo global — ACEPTADO.** Greedy por-mon de una pasada no garantiza el máximo global del score (interacciones entre mons: cambiar A puede hacer que el build de B, ya evaluado, deje de ser óptimo). Es la decisión de producto tomada. Se documenta en la UI implícitamente ("propone cambios que suben la nota", no "la maximiza"). Mitigación futura barata (no en v1): segunda pasada hasta punto fijo. No rompe la API.
- **[RISK] `recommend_member_build` puede producir un build que NO suba el score** para ese mon en ese equipo (p.ej. su build "coherente ideal" en aislamiento empeora la cobertura del equipo). El criterio de aceptación estricto (`> current + EPSILON`) lo cubre: ese cambio simplemente se descarta. Invariante `score_after >= score_before` se mantiene por construcción.
- **[UNCERTAIN] Artefacto EV→SP del parser (ya tolerado).** El parser hace `EV//8`, los builds del optimizador pasan por `sp_preset_builder` (que produce SP nativo). Al comparar score-equipo vs score-equipo bajo la misma convención de `score_team`, el artefacto se cancela. **Riesgo residual:** el `pokepaste_after` re-serializa SP que, al re-importar, vuelven a pasar por `//8` — round-trip potencialmente lossy. Mitigación: el test `test_optimized_paste_roundtrips` no asierta igualdad exacta de SP, sólo que importa y da 6 miembros. Ver memoria `feedback_pokepaste_ev_sp_lossy` y `reference_champtteams_pokepaste`.
- **[RISK] Coste de cómputo.** Cada candidato dispara `recommend_member_build` (varios lookups + preset builder) + un `score_team`. Peor caso: 6 candidatos → ~6 builds + ~7 `score_team`. Acotado y aceptable para una petición interactiva; el `max_length=20000` del request ya limita el payload. Si en el futuro se hace multi-pasada, vigilar el `n²`.
- **[UNCERTAIN] Orden de prioridad del label de rol (§3.2)** y mapeo a ES — decisión de presentación, calibrable con fixtures.
- **[RISK] Refactor de `_build_suggestions`.** Es el único cambio a código existente del rater. Debe ser estrictamente behavior-preserving; los tests del rater son la red de seguridad. Si extraer el helper resultara arriesgado, el fallback (§5.5) es llamar a `_build_suggestions` tal cual desde el optimizador (a coste de un `recommend_member_build` extra) — sin tocar nada.

---

## 9. Restricciones respetadas

- No se cambia ninguna firma pública: `rate_team`, `rate_member`, `detect_archetype`, `recommend_member_build`, `score_team`, `to_pokepaste`, `_build_suggestions` (firma intacta; sólo delega internamente). Campos nuevos en `MemberRating`/`MemberRatingOut` son **aditivos con defaults** → retrocompatibles.
- No se toca SP66/MAX_SP_TOTAL, la asignación de items, los 7 arquetipos ni `archetype_weights.json`.
- Roster fijo: el optimizador **nunca** cambia de especie (estructural: `recommend_member_build` recomputa sobre el mismo `PokemonData`; el `model_copy` del miembro conserva `pokemon` y `mega_form`). Los fijados nunca se tocan.
- Endpoint nuevo aislado (`/optimize-team`); `/rate-team` e `/import` intactos.

---

## 10. Orden de bloques atómicos para Deva

Cada bloque = 1 feature = 1 invocación (regla `feedback_deva_sprint_atomic`). Dependencias marcadas.

- **B1 — Rol coherente (servicio).** `derive_member_role(member)` + `_role_label_from_tags` en `team_rater.py`; añadir `role` a `MemberRating`; poblar en `rate_member`. Tests: `test_member_role_label_es`, parte de `test_member_rating_includes_role_and_sp`.
- **B2 — EVs (servicio).** Añadir `sp: dict` a `MemberRating`; poblar en `rate_member`. Tests: resto de `test_member_rating_includes_role_and_sp`. (B1 ∥ B2 — independientes salvo que tocan el mismo dataclass; secuenciar B1→B2 para evitar conflicto de edición.)
- **B3 — Serialización rater (API+SPA display).** `role`/`sp` en `MemberRatingOut` + `_team_rating_to_out`; render de `role` y rejilla SP en la tarjeta. Test `test_rate_team_out_serializes_role_sp`. (Depende de B1+B2.)
- **B4 — Refactor aditivo `_build_suggestions`.** Extraer `_diff_to_suggestions(member, rec_build, coherence_reasons, archetype)`; `_build_suggestions` delega. Sin cambios de comportamiento; correr tests del rater. (Pre-requisito de B5.)
- **B5 — Núcleo del optimizador.** `services/team_optimizer.py`: dataclasses + `optimize_team`. Greedy §5.3. Tests de invariantes §7 (locked/species/score≥/delta-sum/determinism/all-locked). (Depende de B4.)
- **B6 — Endpoint + schemas.** `OptimizeTeamRequest`/`Response`/`OptimizedChangeOut`; `_optimization_to_out`; `POST /optimize-team`. Tests `test_endpoint_optimize_team`, `test_invalid_locked_indices`, `test_optimized_paste_roundtrips`. (Depende de B5.)
- **B7 — SPA optimizador.** Toggle fijar/desfijar por miembro, botón "Optimizar", `optimizeTeam()`, render de ambas vistas (resumen + desglose rankeado, reusando `.rate-suggestion` y `copyPaste`). Entrada en `changelog.json` en el mismo commit (`feedback_changelog_in_same_commit`). (Depende de B6.)

---

## 11. ADRs embebidos (decisiones clave)

```
ADR-OPT-1: Greedy por-mon de una sola pasada, orden ascendente de índice.
Status: Accepted
Context: hay que subir el score global tocando sólo no-fijados; decisión de producto = greedy.
Decision: iterar candidatos en orden de índice; aceptar un build sólo si mejora estrictamente
  el score del equipo-en-progreso; atribuir a cada cambio su mejora marginal en el momento.
Consequences: determinista y testeable; Σdelta == delta_total; NO óptimo global (aceptado);
  ranking de presentación por delta desacoplado del orden de evaluación.

ADR-OPT-2: El arquetipo se fija una vez sobre el equipo original.
Status: Accepted
Context: score_team es archetype-weighted; recalcular el arquetipo tras cada cambio movería la escala.
Decision: detect_archetype una vez; usar scoring_archetype (balance si confianza<0.4) y
  variant.team_sheet constantes toda la corrida (mismo patrón que team_editor).
Consequences: score_before y score_after son comparables; sin "deriva" de escala por relabel.

ADR-OPT-3: Reuso de Suggestion + refactor aditivo de _build_suggestions.
Status: Accepted
Context: el desglose de cambios necesita el diff build-usuario, que ya vive en el rater.
Decision: extraer _diff_to_suggestions; _build_suggestions delega sin cambiar su firma.
Consequences: cero duplicación de conocimiento; el optimizador no recomputa recommend_member_build;
  los tests del rater protegen el refactor.
```
