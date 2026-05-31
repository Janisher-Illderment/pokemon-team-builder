# ADR — Categoría ofensiva como única fuente de verdad para la selección de moves (cierre del residuo Abomasnow)

> **Status:** Proposed
> **Fecha:** 2026-05-31
> **Autor:** Sola (Solution Architect)
> **Rama:** `fix/ev-notes-derive-build` (continúa el trabajo del ADR previo)
> **Precedente directo:** `docs/adr-weather-setter-coherence.md` (YA IMPLEMENTADO por Deva:
> rol gateado, `_derive_nature` consume `_dominant_attack_category`, SP via
> `_offensive_stat_from_nature`).
> **Fuente autorizada:** `docs/vgc-principles.md` + evidencia runtime de Sergio.

El ADR previo cerró la coherencia **rol ↔ naturaleza ↔ SP** *dado un moveset*. Este ADR
cierra el residuo que queda **un nivel antes**: la **selección del moveset** todavía puede
producir un move muerto, porque elige los STAB sin mirar la categoría con la que el build
va a acabar. Rutas `file:línea` verificadas contra la rama actual.

---

## 1. Síntoma y causa raíz (verificada en código)

### 1.1 Evidencia runtime
`poke-builder build abomasnow` produce hoy:
- rol = `lead_support`, nature = Jolly (+Spe/−SpA),
- moves = `[protect, seed-bomb (físico), ice-beam (ESPECIAL), mega-punch (físico)]`,
- SP atk30 / spe20 / hp16 / **spa0**.

→ **ice-beam es un move muerto** (0 SpA + naturaleza que baja SpA). Dos defectos
independientes que el ADR previo NO cerró.

### 1.2 Por qué el ADR previo no lo cierra (verificación)
El ADR previo hizo coherentes naturaleza/SP **a partir de** `_dominant_attack_category(moves)`
(`team_generator.py:1023-1048`, `:1082`) y `_offensive_stat_from_nature`
(`sp_preset_builder.py:159-180`, consumido en `:293-295`). Pero sus tests e2e
(`test_e2e_abomasnow_*`, `test_team_generator.py:1112-1166`) usan el helper
`_coherence_chain` (`:1086-1109`), que recibe un **moveset hecho a mano** y **nunca llama a
`select_moves_for_role`**. Es decir: la coherencia *posterior* a la selección está probada;
la **selección misma** no. El residuo vive exactamente en esa grieta no cubierta.

### 1.3 Defecto 1 — la selección de STAB ignora la categoría del build

`replica_exporter.select_moves_for_role` calcula `primary_cat` desde **base stats**, no desde
la categoría con la que el build va a acabar:

```python
# replica_exporter.py:374-378
primary_cat = (
    "physical" if pokemon.base_stats.atk >= pokemon.base_stats.spa else "special"
)
```

Para Abomasnow atk92 == spa92 → desempate a **físico**. El slot-2 (STAB) filtra por
`primary_cat` en pass 0 (`:412`) → Grass físico → `seed-bomb`. Hasta aquí bien.

El fallo está en el **slot-3 / invariante de segundo STAB** (`replica_exporter.py:450-478`),
que rellena el STAB del tipo no cubierto **SIN filtrar por categoría**:

```python
# replica_exporter.py:472-476 — invariante de segundo STAB
for candidate in _STAB_BY_TYPE.get(missing_type, ()):
    if candidate in used or candidate not in move_pool:
        continue
    second_stab = candidate          # ← NO mira _MOVE_CATEGORY
    break
```

`_STAB_BY_TYPE["ice"]` (`:48`) empieza por `ice-beam` (especial), antes que los físicos
`icicle-crash` / `ice-punch`. Como `missing_type == "ice"`, el invariante mete **ice-beam
(especial)** en un build que ya es físico. `_STAB_BY_TYPE` está **ordenado por potencia
base**, no por categoría, así que la categoría del build no influye en este lazo.

**Resultado:** moveset mixto `seed-bomb (físico) + ice-beam (especial)` → empate 1-1 en
`_dominant_attack_category` → `None` → `_derive_nature` cae al slot-2 (físico) → Jolly → SP
físico → **ice-beam con 0 SpA = muerto**. El ADR previo es coherente *dado* este moveset
incoherente: hace exactamente lo que se le pide, pero el move ya nació muerto.

> El mega-punch del runtime es el relleno de `_fallback_move` (`:604-619`) — un coverage
> arbitrario del pool tras agotar slots; síntoma secundario del mismo mixto, no causa.

> **[UNCERTAIN — requiere PokeAPI]** El movepool real de Abomasnow (¿incluye `icicle-crash`?
> ¿`ice-punch`? ¿`ice-shard`?) decide qué hielo físico sustituirá a ice-beam. NO inventar el
> set; confirmar contra la fuente real antes de fijar el assert exacto del test de moveset
> (§5.3.1). El defecto estructural — el lazo no filtra por categoría — se sostiene
> independientemente del movepool.

### 1.4 Defecto 2 — el floor `lead_support` sobre-promociona setters ofensivo-leaning

`synergy_engine.assign_role_weights` decide si un setter es "ofensivo" por un cutoff de stat:

```python
# synergy_engine.py:427-434
offensive_weight = max(physical_sweeper_weight, special_sweeper_weight)
setter_is_offensive = offensive_weight >= ROLE_PRESENCE_CUTOFF   # 0.5  (:144)
setter_lead_primary = setter_supports and not setter_is_offensive
```

`_gradient_weight(92, 100) = (92−85)/30 = 0.233 < 0.5` (`:249-263`) → `setter_is_offensive =
False`. Y `_has_support_kit` (`:166-184`) mira el **learnset completo** vía `pokemon.move_names`
— Abomasnow aprende `icy-wind` (∈ `_SPEED_CONTROL_MOVES`, `:74`) **aunque su set real no lo
lleve** → `setter_supports = True` → `setter_lead_primary = True` → `lead_support` PRIMARY.

Esto contradice el test que el ADR previo dejó (`test_abomasnow_offensive_setter_not_lead_support`,
`test_synergy_engine.py:269-288`), cuyo fixture lista `moves=["protect","blizzard","energy-ball",
"ice-beam"]` (sin icy-wind) → ahí `_has_support_kit` es False y el test pasa. **Pero el build
real arranca del learnset completo (que sí tiene icy-wind), no del fixture** → en runtime
`setter_supports` es True y reaparece `lead_support`. La grieta: **`_has_support_kit` evalúa
soporte sobre el learnset, no sobre el moveset que el mon realmente va a llevar.**

El perfil de Abomasnow es **ofensivo-leaning** (atk92/spa92 > def75/spd85), su set real no
lleva soporte, y se etiqueta "support turno 1" sin un move de soporte asignado. Debería ser
`*_sweeper` (débil) + tag C3 `weather_setter`.

### 1.5 El problema de ORDEN de pipeline (núcleo del residuo)

Orden actual en `_build_variant`:

```
assign_role (stats + LEARNSET)           team_generator.py:1108
   → select_moves (por rol, base stats)  team_generator.py:1124-1133, 1158-1165
   → _derive_nature (del MOVESET)         team_generator.py:1166
   → build_presets (de la naturaleza)     team_generator.py:1185
```

La categoría que gobierna naturaleza/SP (`_dominant_attack_category`) se calcula **después**
de seleccionar moves, pero la **selección de STAB** decide con `primary_cat` (base stats) y el
invariante de 2º STAB **sin categoría**. Y el ROL se decide **antes** de los moves, con un
proxy de soporte sobre el learnset. Hay **tres consumidores de "categoría"** desincronizados:
selección de STAB (base stats), rol (learnset), naturaleza/SP (moveset). El move muerto nace
de que la **selección** usa la señal equivocada.

### 1.6 Conclusión de causa raíz
> **Falta una única fuente de verdad de la CATEGORÍA OFENSIVA, fijada ANTES de seleccionar
> moves, y propagada a (a) selección de STAB+coverage, (b) decisión de setter ofensivo,
> (c) naturaleza/SP.** Hoy (c) ya deriva del moveset (ADR previo), pero (a) usa base stats y
> el invariante de 2º STAB no filtra por categoría, y (b) usa un proxy de soporte sobre el
> learnset. Cerrar el residuo = **definir la categoría una vez y que (a) y (b) la respeten**;
> (c) ya queda consistente porque deriva del moveset que (a) producirá coherente.

---

## 2. Opciones consideradas

### Opción A — Filtro mínimo: el invariante de 2º STAB respeta `primary_cat`
Añadir el mismo filtro de categoría que ya tiene el slot-3 coverage al lazo de 2º STAB
(`:472-476`), con un pase relajado de fallback (igual patrón que slot-2/slot-3: pass 0
category-matching, pass 1 cualquiera).

- **Pro:** cambio quirúrgico, ~6 líneas, cero firmas tocadas. Cierra el move muerto de
  Abomasnow en el caso físico (escogería `icicle-crash`/`ice-punch` antes que `ice-beam`).
- **Contra:** NO resuelve la raíz. `primary_cat` sigue saliendo de base stats; un mixto
  92/92 cuyo set real es especial (Blizzard+Energy Ball) seguiría arrancando "físico" por el
  desempate y podría desalinear el slot-2. Tampoco toca el Defecto 2 (rol).

### Opción B — Categoría ofensiva como fuente de verdad, derivada de stats + desempate, fijada antes de seleccionar
Definir `offensive_category(pokemon) -> "physical"|"special"` (de atk vs spa; desempate físico,
consistente con el comportamiento actual y con `_is_physical_attacker`) y pasarla a
`select_moves_for_role` como la base de `primary_cat`. El invariante de 2º STAB y el coverage
filtran por esa misma categoría. La naturaleza/SP ya derivan del moveset resultante (ADR
previo) → quedan consistentes por construcción.

- **Pro:** una sola definición de categoría alimenta selección de STAB+coverage. Elimina el
  move muerto en ambos caminos (físico y especial) porque **todos** los slots de daño se
  filtran por la misma categoría → el moveset es monocategoría salvo que el pool no tenga STAB
  de esa categoría para un tipo (caso degenerado documentado). `_dominant_attack_category` deja
  de empatar → naturaleza/SP deterministas.
- **Contra:** para un mon con base 92/92 la categoría "verdad" es un desempate (físico). Si el
  meta-set real fuera especial, forzaríamos físico. Mitigación: el override de meta-moves
  (slot-2, `:384-397`) y el override de habilidad (`snow-warning: ice-beam→blizzard`, `:222`)
  ya empujan a especial cuando procede; ver §3.2. No toca el Defecto 2 por sí solo.

### Opción C — B + corregir el Defecto 2: "setter ofensivo" por INCLINACIÓN, no por cutoff 0.5; soporte por MOVESET, no por learnset
Sobre B, cambiar el Defecto 2 en `assign_role_weights`:
1. `setter_is_offensive` deja de ser `weight >= 0.5` y pasa a **inclinación ofensiva**:
   `max(atk, spa) >= max(def, spd)` (un mon cuyo mejor ataque iguala o supera su mejor defensa
   es ofensivo-leaning, aunque no llegue a stat 100). Abomasnow 92 vs 85 → ofensivo-leaning →
   NO lead primary.
2. **[UNCERTAIN/DECISION — §7]** Endurecer `_has_support_kit` para que la promoción a
   `lead_support` PRIMARY exija soporte en el contexto del build, no solo en el learnset.

- **Pro:** cierra los DOS defectos con una sola noción de "categoría/inclinación ofensiva".
  Abomasnow → `*_sweeper` + tag `weather_setter` (honesto). Cero moves muertos vía B.
- **Contra:** el cambio de `setter_is_offensive` puede mover algún caso límite de setter
  ofensivo-leaning pero defensivamente-construido; cubierto por tests (§5). El punto 2 toca un
  helper compartido → riesgo de regresión en Ninetales-A (§6) → por eso va detrás de una
  decisión (§7) y de un bloque atómico aislado.

**Decisión: Opción C** (B + Defecto 2 por inclinación), con el endurecimiento de
`_has_support_kit` (C.2) **condicionado a §7**. Es la única que cumple el objetivo del enunciado:
*cero moves muertos* (B) **y** *etiqueta de rol que refleja lo que el mon hace* (C.1).

---

## 3. Decisión recomendada

### Principio rector
> Existe **una** categoría ofensiva por Pokémon, derivada de stats con desempate físico,
> **fijada antes de seleccionar moves**. La **selección de STAB y coverage** la respeta en
> TODOS los slots de daño (incluido el invariante de 2º STAB). La **inclinación ofensiva**
> (mejor ataque ≥ mejor defensa) decide si un setter es atacante; "poner clima" es el tag C3
> `weather_setter`. Naturaleza y SP ya derivan del moveset (ADR previo) y quedan consistentes
> por construcción.

### 3.1 Cambio (1) — categoría ofensiva como parámetro de selección de STAB+coverage

`select_moves_for_role` ya calcula `primary_cat` de base stats (`:374-378`). Cambios:

- **Extraer** la definición a un helper puro reutilizable:
  `_offensive_category(stats) -> "physical"|"special"` = `"physical" if atk >= spa else
  "special"` (desempate físico, idéntico al actual → cero cambio de comportamiento para los
  monocategoría). Vive en `replica_exporter` (mismo módulo que `_MOVE_CATEGORY`).
- **Invariante de 2º STAB (`:457-478`) filtra por categoría** con el patrón de dos pases ya
  usado en slot-2/slot-3:
  - pass 0: solo `_MOVE_CATEGORY.get(candidate) == primary_cat`;
  - pass 1 (fallback): cualquier categoría, **solo si** pass 0 no encontró STAB de la
    categoría correcta para ese tipo (preserva el invariante "≥1 STAB del 2º tipo si existe"
    de `test_garchomp_dual_type_carries_both_stabs`).
  - **Importante:** el filtro aplica también a la rama de `meta_moves` del 2º STAB
    (`:460-468`), simétrico con el slot-2 meta (`:393-395`).

> **Firma:** `select_moves_for_role(...)` **NO cambia** — `primary_cat` ya se calcula dentro.
> Solo se extrae a helper y se aplica en el lazo de 2º STAB. El override de meta-moves y de
> habilidad (`snow-warning: ice-beam→blizzard`) se mantienen y siguen pudiendo elevar a
> especial cuando el pool y la habilidad lo justifican (ver §3.2).

### 3.2 Interacción con meta-moves y el override de habilidad (clave para el caso especial)

El enunciado pide también que un **setter especial-leaning** reciba **STAB especial**. Con
(1) por sí solo, un 92/92 desempata a físico. Dos mecanismos ya existentes lo corrigen sin
añadir nada nuevo:

- **meta-moves** (slot-2, `:384-397`): si el meta del mon prioriza un STAB especial de su
  tipo (Blizzard), el slot-2 lo toma **antes** que la tabla estática, y ese slot-2 ya filtra
  por `primary_cat`. **[DECISION NEEDED — §7.3]:** para que un especial-leaning gane especial,
  `primary_cat` debe poder ser "special". Ver §3.3.
- **override de habilidad** (`_ABILITY_STAB_OVERRIDES["snow-warning"]: ice-beam→blizzard`,
  `:222`): si slot-2 acabara en `ice-beam` (especial) bajo nieve, ya lo sube a `blizzard`
  (especial, 110 BP, nunca falla en nieve). Refuerza la coherencia del camino especial.

### 3.3 Desempate de categoría para mixtos 50/50 — la naturaleza ya derivada NO está disponible aún

Limitación de orden: en `select_moves_for_role` aún no existe el moveset, así que no podemos
desempatar por "categoría dominante del moveset" (circular). Opciones de desempate para 92/92:

- **(i) físico** (status quo del código): determinista, simple. Abomasnow → físico → set
  físico coherente (icicle-crash/ice-punch en vez de ice-beam). Cero moves muertos.
- **(ii) preferir la categoría con más STAB *de calidad* en el pool**: requiere mirar el pool,
  más complejo, marginal.

**Recomendación:** **(i)** para el desempate base, **dejando que meta-moves (§3.2) eleve a
especial** cuando el meta lo pida. Esto satisface ambos casos del enunciado: el Abomasnow
"genérico" sale físico-coherente; un setter cuyo meta es especial (Blizzard-first) sale
especial-coherente vía el override de slot-2. El resultado clave — **cero moves muertos** — se
cumple en los dos caminos porque todos los slots de daño comparten `primary_cat`.

### 3.4 Cambio (2) — Defecto 2: "setter ofensivo" por inclinación; soporte por contexto de build

En `assign_role_weights` (`synergy_engine.py:427-434`):

- **(2a)** Sustituir `setter_is_offensive = offensive_weight >= ROLE_PRESENCE_CUTOFF` por una
  noción de **inclinación ofensiva** que NO dependa del cutoff de stat 100:

  ```
  offensive_lean = max(stats.atk, stats.spa) >= max(stats.def_, stats.spd)
  setter_is_offensive = offensive_weight >= ROLE_PRESENCE_CUTOFF or offensive_lean
  ```

  Abomasnow: `max(92,92)=92 >= max(75,85)=85` → True → NO `lead_support` primary. Pelipper
  (atk50/spa95 vs def100/spd70): `max(50,95)=95 >= max(100,70)=100` → **False** → sigue
  pudiendo ser lead si tiene soporte (correcto: Pelipper es soporte genuino). Tyranitar
  (134 vs 110) → True (ya lo era por el cutoff). La cláusula `or` es aditiva: nadie que ya
  fuera ofensivo deja de serlo.

- **(2b) [DECISION — §7.1]** Endurecer `setter_supports` para que la promoción a `lead_support`
  PRIMARY no se dispare por un move de soporte que está en el **learnset** pero no en el set.
  Como en `select_moves_for_role` el moveset se decide después del rol, NO podemos pasar el
  moveset al rol sin invertir el pipeline. Dos sub-opciones:
  - **(2b-i) recomendada, sin invertir pipeline:** mantener `_has_support_kit(learnset)` para
    el peso, pero condicionar la **promoción a primary** además a que el mon **no sea
    ofensivo-leaning** — que es justo lo que hace (2a). Con (2a), Abomasnow ya no es lead
    primary aunque su learnset tenga icy-wind, porque `setter_is_offensive=True`. **(2b-i)
    NO requiere tocar `_has_support_kit`** → menor superficie de regresión. **Esta es la
    recomendación de Sola.**
  - **(2b-ii) descartada de momento:** invertir el pipeline (seleccionar moves antes del rol)
    para evaluar soporte sobre el set real. Cambio estructural grande, rompería el orden del
    que dependen items/preview; desproporcionado para este residuo.

> Con **(2a)** sola, el Defecto 2 de Abomasnow queda cerrado (ofensivo-leaning gana al floor).
> `_has_support_kit` **no se toca** → Ninetales-A (no ofensivo-leaning: max(67,81)=81 <
> max(75,100)=100, y con icy-wind) **conserva** `lead_support` primary. Pelipper igual.

### 3.5 Qué NO se toca (restricciones duras)
- SP 66/32, pool de items, 7 arquetipos, 7 labels de rol (claves de dict — solo cambia su
  orden/derivación).
- Firmas públicas: `select_moves_for_role`, `assign_role`, `assign_role_weights`,
  `build_presets`, `suggest_sp_distribution`, `derive_doubles_tags` — **intactas**.
- `_dominant_attack_category`, `_offensive_stat_from_nature`, `_derive_nature` (ADR previo) —
  **reutilizados sin cambio**; solo dejan de recibir empates en el caso Abomasnow porque (1)
  produce un moveset monocategoría.
- `_STAB_BY_TYPE` y `_MOVE_CATEGORY` — se **leen**, no se reordenan ni amplían (salvo
  [UNCERTAIN §5.3.1] si falta mapear algún hielo físico del pool real de Abomasnow).

---

## 4. Cambios concretos (ficheros / símbolos)

| # | Fichero | Símbolo | Cambio |
|---|---|---|---|
| 1a | `services/replica_exporter.py` | `_offensive_category(stats) -> str` (nuevo, privado) | Extrae `"physical" if atk>=spa else "special"` (desempate físico). Puro. |
| 1b | `services/replica_exporter.py` | `select_moves_for_role` `primary_cat` (`:374-378`) | Sustituir el inline por `primary_cat = _offensive_category(pokemon.base_stats)`. Cero cambio de comportamiento (misma fórmula). |
| 1c | `services/replica_exporter.py` | invariante 2º STAB (`:457-478`) | Filtrar por `primary_cat` con patrón dos pases (pass 0 category-match, pass 1 fallback solo si pass 0 vacío). Aplica a rama meta y a tabla estática. |
| 2a | `services/synergy_engine.py` | `assign_role_weights` (`:427-434`) | `setter_is_offensive` añade `or (max(atk,spa) >= max(def_,spd))` (inclinación ofensiva). Aditivo. |

Sin cambios en JSON de datos, config, ni firmas públicas. `_has_support_kit` **no se toca**
(recomendación 2b-i). Total: 3 puntos de edición en 2 ficheros.

---

## 5. Tests

### 5.1 Mantener verdes sin cambio (regresión protegida)
- `test_garchomp_dual_type_carries_both_stabs` (`test_coverage_stab.py:121-141`): Garchomp
  físico, earthquake (físico) + dragon-claw (físico) — ambos físicos → el filtro de categoría
  los acepta en pass 0. **Verde.**
- `test_dual_type_with_two_stabs_may_sacrifice_one` (`:256-281`): asserta "≥1 STAB"; el filtro
  no reduce la presencia (pass 1 fallback garantiza el invariante). **Verde.**
- `test_water_only_member_keeps_water_stab`, `test_dual_type_with_only_one_stab_available_keeps_it`
  (`:144-180`): monocategoría, sin 2º tipo conflictivo. **Verde.**
- `test_meta_move_preferred_for_stab_slot2` / `_coverage_slot3`
  (`test_replica_exporter.py:653-685`): slot-2/slot-3, no el 2º STAB. **Verde** (verificar que
  el meta sigue ganando — el filtro nuevo es solo en el lazo de 2º STAB).
- `test_unknown_category_not_chosen_pass0` (`:321`): el patrón dos-pases que replicamos ya está
  validado aquí. **Verde.**
- ADR previo: `test_e2e_abomasnow_*`, `test_e2e_physical_vs_special_*`
  (`test_team_generator.py:1112-1166`): siguen verdes (reciben moveset hecho a mano; no tocan
  selección). **Pero ahora son insuficientes** → §5.3 añade el e2e que SÍ selecciona.
- `test_setter_with_support_move_keeps_lead` (Pelipper, `test_synergy_engine.py:291-305`):
  Pelipper no es ofensivo-leaning (95 < 100) → (2a) no lo promueve a ofensivo → conserva lead.
  **Verde.**
- `test_weather_setter_gets_lead_support_primary` (Ninetales-A, `:225-243`): no ofensivo-leaning
  (81 < 100) + icy-wind → lead primary. **Verde.**

### 5.2 Probablemente CAMBIAN (con justificación)
- `test_abomasnow_offensive_setter_not_lead_support` (`test_synergy_engine.py:269-288`): hoy
  pasa **solo porque el fixture omite icy-wind**. Tras (2a) pasa por la razón correcta
  (inclinación ofensiva), **independientemente de icy-wind**. **Acción:** añadir un segundo
  assert/variante con `moves` que SÍ incluya `icy-wind` y `assert roles[0] != "lead_support"`
  — codifica que el learnset-con-soporte ya no resucita el bug. (No rompe; refuerza.)
- `test_offensive_setter_with_support_is_sweeper_primary_lead_secondary` (`:308-324`): atk130,
  ya ofensivo por cutoff; (2a) no cambia el resultado. **Verde**, pero revisar que `lead_support`
  siga como secundario (la lógica de boolean_roles via move_lead_support no cambia). **Verde.**

> **[UNCERTAIN]** Estos son los tests que el análisis identifica como tocables. La suite
> completa (524) debe correrse tras cada bloque; cualquier test de `test_coverage_stab.py` o
> `test_replica_exporter.py` que asuma un STAB especial concreto en un mon de base atk>=spa
> podría requerir ajuste — revisar en B1.

### 5.3 Añadir (cobertura del residuo)

1. **Abomasnow seleccionado e2e — ningún move muerto (caso del bug):** fixture con el
   **learnset realista** incl. icy-wind y candidatos de hielo físico **[UNCERTAIN: confirmar
   `icicle-crash`/`ice-punch`/`ice-shard` en PokeAPI antes de fijar el assert exacto]**. Flujo
   REAL: `moves = select_moves_for_role(abomasnow, assign_role(abomasnow))` → `nature =
   _derive_nature(...)` → `build_presets(...)`. Asserts:
   - `roles[0] != "lead_support"` (Defecto 2 cerrado).
   - `"weather_setter" in derive_doubles_tags(abomasnow)`.
   - **Invariante anti-move-muerto (el assert central de este ADR):**
     `not any(_MOVE_CATEGORY.get(m) and _MOVE_CATEGORY[m] != dominant and sp_of_that_cat == 0
     for m in moves)` — formalizado como: no existe move de daño cuya categoría tenga 0 SP.
     Equivalente práctico: si hay un move especial de daño → `off.spa > 0`; si hay físico →
     `off.atk > 0`. Para el caso físico de Abomasnow: `"ice-beam" not in moves` (sustituido por
     hielo físico) **[UNCERTAIN: assert el slug físico exacto según el pool real]**.
   - Diferencia con los e2e previos: este **llama a `select_moves_for_role`** (no recibe el set
     a mano) → cubre la grieta de §1.2.

2. **Setter especial-leaning → STAB especial (pedido por el enunciado):** un setter cuyo perfil
   y meta sean especiales (p.ej. base spa > atk, o 92/92 con meta-moves priorizando Blizzard).
   `select_moves_for_role` → slot de hielo es **especial** (`blizzard`/`ice-beam`), nature Timid,
   `off.spa > 0` y `off.atk == 0`. Verifica el camino especial de §3.2/§3.3.

3. **Invariante de 2º STAB respeta categoría (unit, replica_exporter):** mon físico dual-type
   cuyo 2º tipo tiene en el pool TANTO un STAB físico como uno especial (el especial primero en
   `_STAB_BY_TYPE`). Assert: el moveset toma el **físico** (pass 0), no el especial. Mon especial
   simétrico → toma el especial. Caso degenerado: si el 2º tipo solo tiene STAB de la categoría
   "equivocada" en el pool, pass 1 lo admite (invariante "≥1 STAB" preservado).

4. **`_offensive_category` (unit puro):** atk>spa→physical; spa>atk→special; atk==spa→physical
   (desempate documentado).

5. **(2a) inclinación ofensiva (unit, synergy_engine):** Abomasnow (92/92 vs 75/85) → ofensivo;
   Pelipper (50/95 vs 100/70) → NO ofensivo; un muro puro (atk60/spa60 vs def120/spd120) → NO
   ofensivo. Protege el límite de la nueva cláusula.

---

## 6. Riesgos

- **[RISK medio] Desempate físico para mixtos 50/50 reales especiales.** Un setter 92/92 cuyo
  set competitivo es especial pero cuyo meta NO prioriza un STAB especial caería a físico por
  (i). Mitigación: meta-moves (§3.2) cubre el caso normal; el invariante anti-move-muerto se
  cumple igual (el set sería físico-coherente, no muerto). Si aparece un caso real mal
  clasificado, se resuelve añadiendo su STAB especial al meta, no cambiando el desempate.
- **[RISK medio] (2a) mueve algún setter ofensivo-leaning defensivamente construido.** Un mon
  con max(atk,spa) == max(def,spd) ahora cuenta como ofensivo (`>=`). Es intencional (empate →
  ofensivo, coherente con el desempate físico general). Cubierto por test §5.3.5. Si Sergio
  prefiere `>` estricto para empate, es un one-liner — **[DECISION §7.2]**.
- **[RISK bajo] `_MOVE_CATEGORY` incompleto para el hielo físico del pool real.** Si el pool de
  Abomasnow trae un hielo físico no mapeado (p.ej. `ice-shard` no está en `_MOVE_CATEGORY`), el
  filtro lo trata como categoría desconocida → ineligible en pass 0 → podría volver a ice-beam
  en pass 1. Mitigación: en B1 verificar que `icicle-crash`/`ice-punch`/`ice-shard` están en
  `_MOVE_CATEGORY` (`icicle-crash`, `ice-punch`, `ice-fang` SÍ están, `:144-146`; `ice-shard`
  **[UNCERTAIN]** — añadir si el pool lo usa). **No inventar movesets.**
- **[RISK bajo] Orden de slots tras el filtro.** Si el filtro de 2º STAB deja el slot vacío en
  pass 0 y pass 1, el flujo cae al coverage genérico (`:486-521`) y luego a `_fallback_move`.
  El invariante "≥1 STAB del 2º tipo si existe en pool de la categoría correcta" se mantiene;
  el "si existe de cualquier categoría" lo cubre pass 1. Verificado contra
  `test_garchomp_*`/`test_dual_type_*`.
- **[RISK bajo] 524 tests.** Solo se identifican 2 tocables (§5.2, ambos refuerzo no ruptura).
  El riesgo residual son asserts implícitos sobre STAB especial en mons físicos — correr la
  suite por bloque (B0→B3) lo detecta temprano.

---

## 7. Decisiones abiertas [DECISION NEEDED]

1. **¿(2b-i) o (2b-ii)?** Recomendación Sola: **(2b-i)** — no tocar `_has_support_kit`; (2a)
   ya cierra el caso Abomasnow vía inclinación ofensiva. (2b-ii) (invertir pipeline) es
   desproporcionado. Confirmar.
2. **¿Empate de inclinación `>=` o `>`?** Recomendación: **`>=`** (empate → ofensivo, coherente
   con el desempate físico de categoría). Confirmar con Sergio.
3. **¿Permitir que `primary_cat` sea "special" para un 92/92 sin meta especial?** Recomendación:
   **no** — mantener desempate físico determinista y delegar a meta-moves la elevación a
   especial. Evita un desempate frágil "por pool". Confirmar.
4. **Movepool real de Abomasnow [UNCERTAIN — PokeAPI].** Confirmar qué STAB de hielo físico
   sustituye a ice-beam (`icicle-crash`? `ice-punch`? `ice-shard`?) antes de fijar el assert
   exacto de §5.3.1, y que está en `_MOVE_CATEGORY`. **No inventar el set.**

---

## 8. Orden de bloques atómicos para Deva

Cada bloque deja la suite verde y es revertible por sí solo.

- **B0 — `_offensive_category` (helper puro) + unit test (§5.3.4).** Sin integración → cero
  cambio de comportamiento. Suite verde.
- **B1 — Cambio (1b)+(1c): `select_moves_for_role` usa `_offensive_category` y el 2º STAB
  filtra por categoría.** Aquí se confirma el movepool real de Abomasnow [UNCERTAIN §7.4] y se
  verifica `_MOVE_CATEGORY`. Añadir unit de 2º STAB (§5.3.3). Correr `test_coverage_stab.py` +
  `test_replica_exporter.py` completos. Suite verde.
- **B2 — Cambio (2a): inclinación ofensiva en `assign_role_weights`.** Añadir unit (§5.3.5);
  reforzar `test_abomasnow_offensive_setter_not_lead_support` con variante icy-wind (§5.2).
  Suite verde.
- **B3 — Test e2e que SÍ selecciona (§5.3.1 + §5.3.2).** El assert central anti-move-muerto
  llamando a `select_moves_for_role` end-to-end. Cierra el residuo del ADR. Suite verde.

Orden obligatorio: **B0 → B1 → B2 → B3** (B1 depende de B0; B3 verifica el conjunto e integra
B1+B2). B1 y B2 son ortogonales entre sí (uno cierra Defecto 1, otro Defecto 2) pero B3 los
necesita a ambos.

---

## 9. Resumen ejecutivo

El ADR previo hizo coherentes naturaleza/SP **dado** un moveset, pero sus e2e usan movesets
hechos a mano (`_coherence_chain`, `team_generator.py:1086-1109`) y **nunca ejercen
`select_moves_for_role`**. El residuo vive ahí:

- **Defecto 1:** el invariante de 2º STAB (`replica_exporter.py:457-478`) rellena el STAB del
  2º tipo **sin filtrar por categoría**, y `_STAB_BY_TYPE["ice"]` empieza por `ice-beam`
  (especial). Un Abomasnow físico recibe ice-beam → empate de categoría → naturaleza física →
  **0 SpA → move muerto**.
- **Defecto 2:** `setter_is_offensive` usa el cutoff de stat 100 (`synergy_engine.py:431`),
  y `_has_support_kit` mira el **learnset** (que incluye icy-wind) → Abomasnow ofensivo-leaning
  pero sub-100 se promociona a `lead_support` sin soporte real en su set.

Fix recomendado = **Opción C**: (1) una `_offensive_category` única, fijada antes de
seleccionar, que el slot-2, el 2º STAB y el coverage respetan → cero moves muertos en ambos
caminos; (2a) "setter ofensivo" por **inclinación** (mejor ataque ≥ mejor defensa), no por
cutoff de stat → Abomasnow es `*_sweeper` + tag `weather_setter`, no support. No se invierte el
pipeline ni se toca `_has_support_kit` (recomendación §7.1). Sin tocar SP 66, items, arquetipos
ni firmas públicas. 3 puntos de edición en 2 ficheros; 2 tests reforzados, 5 añadidos
(incl. el e2e que por fin selecciona). Bloqueante de datos: movepool real de Abomasnow vía
PokeAPI (§7.4) — no inventar.
