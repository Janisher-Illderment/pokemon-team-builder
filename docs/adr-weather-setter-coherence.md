# ADR — Coherencia rol ↔ naturaleza ↔ SP ↔ moveset para weather-setters (y en general)

> **Status:** Proposed
> **Fecha:** 2026-05-31
> **Autor:** Sola (Solution Architect)
> **Rama sugerida:** `fix/weather-setter-coherence`
> **Fuente autorizada:** `docs/vgc-principles.md` + datos in-game de Sergio
> **Precedente:** ADR `docs/adr-vgc-scoring.md` (C2 presencia, C3 tags de dobles, C6 calidad).
> Este ADR reutiliza la maquinaria C2/C3 ya diseñada (`assess_presence`,
> `derive_doubles_tags`, tag `weather_setter`) en lugar de duplicarla.

Las rutas `file:línea` de este ADR están verificadas contra el código de la rama actual.
La ruta real de los servicios es `pokemon_team_builder/services/…`.

---

## 1. Síntoma y causa raíz (verificada en código)

### Síntoma (reportado por Sergio)
Abomasnow (Grass/Ice, atk 92 / spa 92, habilidad **Snow Warning**) se genera con:
- **Rol:** `lead_support`
- **Naturaleza:** desfavorable a SpA (Impish +Def/−SpA en el report; el código
  actual produce **Jolly** +Spe/−SpA — ver §1.3, la incoherencia es idéntica:
  ambas anulan SpA)
- **SP / EVs:** preset ofensivo **físico** (atk/spe/hp, **0 SpA**)
- **Moveset:** Protect / Seed Bomb (físico) / **Ice Beam (especial)** / Mega Punch (físico)

Incoherencias:
1. **Ice Beam es ESPECIAL** pero el mon lleva 0 SP en SpA y naturaleza que baja SpA
   → el move hace daño basura.
2. Se etiqueta "support turno 1" sin tener **ningún** move de soporte; su única
   utilidad real es la habilidad Snow Warning (poner el clima), que **no requiere
   un rol mecánico de soporte**.

### 1.1 Causa raíz primaria — el *floor* de weather-setter fuerza `lead_support` como PRIMARY

`pokemon_team_builder/services/synergy_engine.py`:

- **`assign_role_weights`**, paso 2 (`synergy_engine.py:347-372`): si la habilidad es
  weather-setter, se hace `_merge_weight(role_weights, "lead_support", 0.8)` y se
  marca `is_weather_setter = True`. El floor es `_WEATHER_SETTER_LEAD_WEIGHT = 0.8`
  (`synergy_engine.py:152`).
- **Construcción de la lista ordenada**, paso 5 (`synergy_engine.py:407-409`):
  ```python
  if is_weather_setter:
      ordered.append("lead_support")   # ← PRIMARY incondicional
  ```
  `lead_support` queda como **`roles[0]`** (primary) para CUALQUIER mon con
  Drought/Drizzle/Snow Warning/Sand Stream, **independientemente de su perfil
  ofensivo**.

Para Abomasnow: `physical_sweeper = special_sweeper = _gradient_weight(92,100) =
(92−85)/30 = 0.233` (`synergy_engine.py:321-322`, `_gradient_weight` :228-242).
Ambos < 0.5 → no entran en la lista. El floor 0.8 gana → `roles = ["lead_support"]`.

### 1.2 Causa raíz secundaria — naturaleza/SP se derivan del LABEL de rol, no del moveset real

- **Naturaleza:** `team_generator._derive_nature` (`team_generator.py:1023-1056`).
  YA lee la categoría del slot-2 STAB para `physical_sweeper`/`lead_support`/
  `special_sweeper` (fix Pelipper, :1031-1051). Para Abomasnow primary=`lead_support`,
  `primary_cat` = físico (atk 92 ≥ spa 92), slot-2 STAB = `seed-bomb` (físico) →
  devuelve **Jolly** (+Spe/−SpA). Coherente con un kit físico… pero el slot-3
  (`ice-beam`, especial) queda huérfano.
- **SP (default export = preset ofensivo):** `sp_preset_builder.build_presets` →
  `_offensive_weights` (`sp_preset_builder.py:252-288`) usa
  `_is_physical_attacker` (`sp_preset_builder.py:140-156`), que decide por
  **base atk vs spa** con desempate a físico. Abomasnow 92==92 → físico →
  `primary_atk="atk"`, pesos atk 10 / spe 9 / hp 2, y Jolly pone spa→0
  (`:280`). Resultado: **0 SP en SpA** con Ice Beam en el set.

### 1.3 Conclusión de la causa raíz

El sistema produce un build **internamente coherente en el eje físico**
(rol lead_support → Jolly → SP físicos → slot-2 físico) **pero el selector de
moves mete un coverage ESPECIAL (Ice Beam) que ningún otro subsistema "ve"**:

- `replica_exporter.select_moves_for_role` (`replica_exporter.py:480-522`) elige
  slot-3 coverage filtrando por `primary_cat` en el **pass 0**, pero en el
  **pass 1** (fallback) acepta cualquier categoría (`replica_exporter.py:504-517`).
  Para Abomasnow, `_COVERAGE_PRIORITY` empieza por `ice-beam` (especial); como
  Ice es uno de sus tipos STAB, slot-3 NO debería ser ice-beam por la guarda
  `candidate_type in own_types` (:509) — **[UNCERTAIN]**: el move exacto en
  slot-3/slot-4 depende del movepool real de PokeAPI (Mega Punch sugiere que el
  fallback `_fallback_move` rellenó con un move arbitrario del pool). El punto
  estructural se sostiene: **la categoría del moveset final no realimenta la
  naturaleza ni el reparto de SP de forma robusta** — solo el slot-2 lo hace, y
  solo para algunos roles.

La incoherencia tiene **dos grietas independientes** y el fix sólido cierra ambas:
- **(A) Rol:** un setter ofensivo no debería tener `lead_support` como PRIMARY.
- **(B) Derivación:** naturaleza y SP deben casar con la **categoría dominante del
  moveset realmente asignado**, no con el label de rol ni con base atk vs spa.

> **Verificación de datos pendiente [UNCERTAIN]:** índice exacto de Snow Warning en
> `abilities` de Abomasnow vía PokeAPI (Abomasnow tiene Snow Warning como habilidad
> normal en slot 0 — **HIGH** confianza como hecho Pokémon, pero el orden que
> devuelve la capa de fetch debe confirmarse en runtime). Stats 92/92 y tipos
> Grass/Ice: **HIGH**. Movepool exacto (¿aprende Mega Punch? ¿Ice Beam?): **[UNCERTAIN]**,
> confirmar con la fuente real antes de fijar el test de moveset.

---

## 2. Opciones consideradas

### Opción (a) — No forzar `lead_support` PRIMARY; degradar el floor a tag/secundario
Cuando el mon tiene perfil ofensivo (sweeper weight ≥ 0.5), el rol mecánico primary
es el sweeper; "weather setter" pasa a ser **tag derivado C3** (ya existe:
`derive_doubles_tags` → `weather_setter`, `synergy_engine.py:602-607`) y/o rol
secundario, no primary.

- **Pro:** ataca la causa raíz primaria (A). El tag C3 `weather_setter` ya modela
  "pone clima" sin pisar el rol mecánico — exactamente la separación que pide el
  enunciado. Tyranitar (atk 134) sería `physical_sweeper` primary + tag
  `weather_setter`, que es lo correcto.
- **Contra:** rompe `test_weather_setter_tyranitar_lead_plus_physical`
  (`test_synergy_engine.py:237-247`, asserta `roles[0]=="lead_support"`). Cambio de
  expectativa **justificado** (el test codifica el bug). No arregla por sí sola la
  grieta (B): un setter genuinamente NO-ofensivo (Ninetales-A spa 81) sigue siendo
  `lead_support` y su SP/naturaleza aún se derivan del label.

### Opción (b) — Derivar naturaleza/SP de la categoría dominante del MOVESET
Un único punto de verdad: tras seleccionar los 4 moves, calcular
`dominant_category(moves)` (físico vs especial por conteo de slots de daño) y que
**naturaleza Y reparto de SP** lo respeten.

- **Pro:** ataca la causa raíz secundaria (B) de forma general, no sólo para
  setters (beneficia a cualquier mixto mal clasificado). Reutiliza `_MOVE_CATEGORY`
  (`replica_exporter.py:100-205`) ya existente.
- **Contra:** por sí sola NO arregla (A): Abomasnow seguiría con rol `lead_support`
  y se seguiría etiquetando "support turno 1" sin moves de soporte. El "support
  inútil" persiste aunque el daño ya case.

### Opción (c) — AMBAS (recomendada)
(a) corrige el **rol** (qué ES el mon), (b) corrige la **derivación** (cómo se
CONSTRUYE). Son ortogonales y se refuerzan: tras (a), Abomasnow ya no es
`lead_support`; tras (b), su naturaleza/SP casan con el moveset aunque el rol
hubiera quedado ambiguo.

**Decisión: Opción (c).**

---

## 3. Decisión recomendada

### Principio rector
> El **rol mecánico primary** describe qué hace el mon en el turno (atacar, muralla,
> soporte, TR). **Poner el clima es una propiedad de la habilidad** y se modela como
> **tag C3 `weather_setter`**, no como rol de soporte. La **naturaleza y el reparto
> de SP** se derivan de la **categoría dominante del moveset realmente asignado**.

### 3.1 Cambio (A) — `assign_role_weights`: floor de setter condicionado al perfil

En `synergy_engine.assign_role_weights`, paso 2 y paso 5:

- **Mantener** el `_merge_weight(role_weights, "lead_support", 0.8)` (no rompe el
  diccionario de pesos; el floor sigue informando al scorer de equipo).
- **Condicionar el PRIMARY:** `lead_support` sólo va a `ordered[0]` por la regla de
  weather-setter **cuando el mon NO tiene presencia ofensiva propia**. Definir:

  ```
  offensive_weight = max(physical_sweeper, special_sweeper)   # ya calculado
  setter_is_offensive = offensive_weight >= ROLE_PRESENCE_CUTOFF   # 0.5
  ```

  - Si `setter_is_offensive` → el orden de sweeper dominante (paso 5,
    `synergy_engine.py:418-431`) decide `roles[0]`; `lead_support` NO se antepone.
    `lead_support` puede seguir apareciendo como rol secundario si su weight ≥ 0.5
    (lo cual sólo ocurre por moves de soporte reales — el floor 0.8 ya no lo
    promociona a primary, pero la lógica de `boolean_roles` lo añadiría; ver
    §3.1.1).
  - Si NO `setter_is_offensive` (Ninetales-A, Abomasnow) → comportamiento actual:
    `lead_support` primary. **Ojo:** Abomasnow (0.233 < 0.5) cae aquí → seguiría
    `lead_support`. Por eso (A) **no basta** y la coherencia la cierra (b)+(C') ↓.

#### 3.1.1 Sub-decisión clave para el caso Abomasnow (setter sin presencia NI soporte)

Abomasnow no es ofensivo (0.233) **ni** tiene moves de soporte. Forzarlo a
`lead_support` es justo lo que genera el "support inútil". Regla refinada:

> El floor de weather-setter promociona `lead_support` a **primary** SÓLO si el mon
> **además** puede ejercer soporte real (tiene al menos un move de
> `_CORE_VIABLE_MOVES` / `_REDIRECT_MOVES` / `_SPEED_CONTROL_MOVES` en su movepool,
> o gate de Tailwind+spe≥90). Si es un setter **sin** kit de soporte y **sin**
> presencia ofensiva (≥0.5), su primary cae al **mejor sweeper por stat dominante**
> (regla de fallback ya existente, `synergy_engine.py:444-447`), y `weather_setter`
> queda como **tag C3** (su utilidad declarada).

Esto convierte a Abomasnow en `special_sweeper`/`physical_sweeper` (92==92 →
desempate a físico por la regla de fallback existente) + tag `weather_setter`.
Es honesto: "es un atacante mediocre cuyo valor es poner nieve", no "un soporte".

> **Firma:** `assign_role_weights(pokemon) -> RoleAssignment` **NO cambia**.
> Internamente necesita leer `pokemon.move_names` (ya lo hace, :313) para evaluar
> "kit de soporte". El `RoleAssignment.role_weights` sigue conteniendo
> `lead_support: 0.8` (el scorer de equipo lo sigue viendo), sólo cambia el ORDEN
> de `roles`.

### 3.2 Cambio (B) — derivar naturaleza de la categoría dominante del moveset

Extender `team_generator._derive_nature` para que, **además** del slot-2, considere
la **categoría dominante de los 4 moves** cuando el primary es ofensivo o
`lead_support`:

- Nueva función pura `_dominant_attack_category(moves: list[str]) -> str | None`
  en `team_generator` (o helper privado): cuenta moves de daño por categoría usando
  `replica_exporter._MOVE_CATEGORY`; devuelve `"physical"`/`"special"`/`None` (empate
  o sin daño).
- En `_derive_nature`, para `physical_sweeper`/`special_sweeper`/`lead_support`:
  usar `dominant = _dominant_attack_category(moves)`; si `dominant` existe, mandar
  sobre el slot-2 aislado:
  - `dominant == "special"` → Timid; `dominant == "physical"` → Jolly.
  - Empate o `None` → comportamiento actual (slot-2, luego default por rol).
- **Walls / TR / redirect:** sin cambios (naturaleza defensiva fija; su trabajo no
  es atacar — ya documentado, :1027-1029).

> **Firma:** `_derive_nature(primary, roles, moves)` **NO cambia** (privada; se
> amplía el cuerpo). El caso Pelipper (`test_nature_timid_for_special_lead`,
> `test_team_generator.py:755-766`) sigue verde: Hurricane+Scald (2 especiales) →
> dominante especial → Timid. El caso `test_nature_jolly_for_physical_lead`
> (brave-bird+u-turn, 2 físicos) → dominante físico → Jolly. **Ambos pinned tests
> pasan sin cambio.**

### 3.3 Cambio (C') — alinear el reparto de SP con el moveset (no con base atk vs spa)

El default export usa el preset **offensive** (`team_generator.py:1147`). El preset
elige stat ofensivo vía `_is_physical_attacker` (base atk vs spa). Para un mixto
en stats (Abomasnow 92/92) o un mon cuyo moveset contradice sus stats, esto se
desalinea de la naturaleza.

**Decisión:** hacer que la **naturaleza ya derivada** (Cambio B, que SÍ refleja el
moveset) gobierne el stat ofensivo del preset. Dos vías, ordenadas por preferencia:

- **C'-preferida (mínima, sin tocar firmas):** en `build_presets`, derivar
  `primary_atk` de la **naturaleza** cuando ésta delata categoría:
  - Naturaleza con `boosted == "spe"` y `hindered == "spa"` (Jolly) **o**
    `boosted/hindered` que penaliza spa (Adamant, Impish…) → físico.
  - Naturaleza que penaliza atk (Timid, Modest, Calm, Bold…) → especial.
  - Si la naturaleza es neutra/ambigua → fallback actual `_is_physical_attacker`.

  `_NATURE_MODIFIERS` (`sp_preset_builder.py:38-64`) ya da `(boosted, hindered)`;
  basta una función `_offensive_stat_from_nature(nature) -> "atk"|"spa"|None`.
  `build_presets(member, item, nature, …)` ya recibe `nature` → **sin cambio de
  firma.**

- **C'-alternativa (descartada de momento):** pasar la lista de moves a
  `build_presets`. Cambia la firma pública y duplica la señal que la naturaleza ya
  codifica. **No recomendada** (viola "mantener firmas públicas" sin beneficio
  adicional sobre C'-preferida).

> **Efecto en Abomasnow tras (A)+(B)+(C'):**
> - (A): rol primary = sweeper (físico por desempate) + tag `weather_setter`.
> - Moveset: con primary físico, `select_moves_for_role` ya prioriza slot-2/slot-3
>   físicos (`primary_cat` físico). Si el resultado es dominante-físico, (B) →
>   Jolly, (C') → atk/spe → **coherente**. Si el movepool real fuerza un kit
>   dominante-especial (p.ej. Ice Beam + Energy Ball + Blizzard), (B) → Timid,
>   (C') → spa/spe → **también coherente**. La grieta "Ice Beam con 0 SpA" se cierra
>   en ambos caminos.
> - El override de Snow Warning (`_ABILITY_STAB_OVERRIDES["snow-warning"]:
>   ice-beam→blizzard`, `replica_exporter.py:222`) ya empuja hacia Blizzard
>   (especial) como STAB de hielo si está en el pool — un argumento extra para que
>   el camino dominante-especial sea el natural de Abomasnow. **[UNCERTAIN]:**
>   confirmar movepool.

### 3.4 Qué NO se toca (restricciones duras)
- Sistema SP 66/32 (`sp_calc`, `MAX_SP_TOTAL`), pool de 48 items, 7 arquetipos.
- Los 7 labels de rol (claves de dict) — se preservan; sólo cambia su **orden** y la
  **derivación** de naturaleza/SP.
- `derive_doubles_tags` / `weather_setter` tag — se **reutiliza** tal cual.
- Firmas públicas: `assign_role_weights`, `assign_role`, `select_moves_for_role`,
  `build_presets`, `suggest_sp_distribution` — **intactas**.

---

## 4. Cambios concretos (ficheros / símbolos)

| # | Fichero | Símbolo | Cambio |
|---|---|---|---|
| A1 | `services/synergy_engine.py` | `assign_role_weights` (paso 2/5, `:347-447`) | Condicionar promoción de `lead_support` a PRIMARY: sólo si `offensive_weight < 0.5` **y** el mon tiene kit de soporte real (move en `_CORE_VIABLE_MOVES`/`_REDIRECT_MOVES`/`_SPEED_CONTROL_MOVES` o Tailwind+spe≥90). Si setter sin presencia ni soporte → primary = fallback sweeper por stat dominante. `role_weights` sin cambios. |
| A2 | `services/synergy_engine.py` | (helper privado nuevo) `_has_support_kit(moves) -> bool` | Reutiliza los frozensets ya definidos en el módulo (`:71-99`). Puro. |
| B1 | `services/team_generator.py` | `_dominant_attack_category(moves) -> str\|None` (nuevo, privado) | Conteo de daño por categoría vía `replica_exporter._MOVE_CATEGORY`. |
| B2 | `services/team_generator.py` | `_derive_nature` (`:1023-1056`) | Anteponer `_dominant_attack_category(moves)` al slot-2 para roles ofensivos + `lead_support`. Walls/TR/redirect sin cambio. |
| C1 | `services/sp_preset_builder.py` | `_offensive_stat_from_nature(nature) -> "atk"\|"spa"\|None` (nuevo, privado) | Lee `_NATURE_MODIFIERS`. |
| C2 | `services/sp_preset_builder.py` | `_offensive_weights` (`:252-288`) | Si `_offensive_stat_from_nature(nature)` no es None, úsalo como `primary_atk`; si None, fallback `_is_physical_attacker`. (Opcional, simétrico) mismo en `_defensive_weights`.) |

Ningún cambio en JSON de datos, ni en `config`, ni en firmas públicas.

---

## 5. Tests a añadir / actualizar

### 5.1 Actualizar (expectativa que codifica el bug — cambio justificado)
- `tests/test_synergy_engine.py::test_weather_setter_tyranitar_lead_plus_physical`
  (`:237-247`): hoy asserta `roles[0]=="lead_support"`. **Cambiar a**
  `roles[0]=="physical_sweeper"` (atk 134, ofensivo) y `assert "lead_support" not in
  roles` salvo que tenga move de soporte; el carácter de setter se verifica con
  `assert "weather_setter" in derive_doubles_tags(tyranitar)`. Documentar en el
  test el porqué (ADR §3.1).

### 5.2 Mantener verdes sin cambio (regresión protegida)
- `test_weather_setter_gets_lead_support_primary` (`:224-234`, Ninetales-A spa 81):
  sin presencia ofensiva **y** [UNCERTAIN: ¿tiene move de soporte en el fixture? no
  — `_mk` sin moves]. **Atención:** con la regla §3.1.1, Ninetales-A sin moves de
  soporte y sin presencia caería a fallback sweeper. **[DECISION NEEDED]** ver §7.
- `test_ninetales_alola_whitelist_lead` (`:316-325`), `test_aurorus_not_weather_setter`
  (`:303-313`), `test_prankster_*`, `test_fake_out_slow_mon_is_lead`,
  `test_tailwind_slow_not_lead`: revisar bajo la nueva regla; los de Prankster/
  Fake-Out/Tailwind no dependen del floor de weather y deben seguir igual.
- `test_nature_jolly_for_physical_lead` / `test_nature_timid_for_special_lead`
  (`test_team_generator.py:745-766`): siguen verdes con (B) (ambos movesets son
  monocategoría → dominante == slot-2).

### 5.3 Añadir (cobertura del fix)
1. **Abomasnow coherente (caso del bug):** fixture atk 92/spa 92, Grass/Ice,
   `snow-warning`, movepool realista **[UNCERTAIN: confirmar moves]**. Asserts:
   - `assign_role(abomasnow)[0]` ∈ {`physical_sweeper`,`special_sweeper`} (no
     `lead_support`).
   - `"weather_setter" in derive_doubles_tags(abomasnow)`.
   - Tras build: naturaleza ∈ {Jolly,Timid} coherente con
     `_dominant_attack_category(moves)`; y el preset ofensivo invierte en el stat
     que la naturaleza potencia (si Timid → SpA>0 y atk==0; si Jolly → atk>0 y
     SpA==0). **Invariante anti-bug:** `NOT (hay move especial de daño AND spa_SP==0)`
     y viceversa.
2. **Setter especial ofensivo — Torkoal+Eruption:** atk 85/spa 85, `drought`,
   moves `["eruption","heat-wave","protect","body-press"]` (Eruption/Heat-Wave
   especiales). **[UNCERTAIN: spa 85 < 100 → no es "ofensivo" por el cutoff 0.5]**.
   - Si se decide (§7) que Torkoal-Eruption debe ser tratable como atacante
     especial pese a spa 85: assert naturaleza Timid + SP en SpA, NO Sassy/defensivo
     con Eruption huérfano. Este es el "weather-setter especial" pedido por el
     enunciado y **expone que el cutoff 0.5 por stat no captura abusadores de
     clima** (Eruption escala con HP%/clima, no con stat alto) → ver §7.
3. **Setter físico vs especial — comparación directa:** un setter atacante físico
   (Tyranitar, atk 134, Stone Edge/Crunch) → Jolly/Adamant + atk-SP; vs un setter
   atacante especial → Timid/Modest + spa-SP. Garantiza que (B)+(C') discriminan
   por moveset, no por etiqueta.
4. **`_dominant_attack_category`:** unit test puro — todo físico → "physical";
   todo especial → "special"; mixto 2-2 → None; sólo status (protect/tailwind) →
   None.
5. **`_offensive_stat_from_nature`:** Jolly/Adamant/Impish → "atk"; Timid/Modest/
   Calm → "spa"; Hardy/Serious → None.
6. **Setter NO-ofensivo CON soporte real (Pelipper):** drizzle, spa 95, con
   `tailwind` en moves → DEBE conservar `lead_support` primary (es un soporte
   genuino) y naturaleza Timid (Hurricane especial). Protege que el fix no
   "rompa" los setters que SÍ son soportes.

---

## 6. Riesgos

- **[RISK alto] Ninetales-A sin moveset de soporte (§5.2).** La regla §3.1.1 exige
  "kit de soporte" para promocionar a `lead_support`. Ninetales-A real lleva casi
  siempre Aurora Veil/Encore/Icy Wind (soporte), así que en producción seguiría
  siendo lead. Pero el **fixture del test no tiene moves** → caería a sweeper y
  rompería el test tal cual. Mitigación: añadir moves de soporte al fixture (refleja
  el set real) **o** ajustar el assert. Decisión en §7.
- **[RISK medio] Cutoff 0.5 por stat no modela abusadores de clima de baja stat.**
  Torkoal (spa 85) y Abomasnow (92) quedan bajo 0.5 aunque su Eruption/Blizzard
  pegan fuerte por clima. (A) los manda a sweeper por fallback igualmente (no a
  lead), y (B)+(C') los construyen coherentes, así que el daño NO se desalinea —
  pero su *rol* declarado será "sweeper mediocre". Aceptable para este fix; la señal
  de calidad C6 (`pokemon_evaluator`, ADR vgc-scoring) es el lugar correcto para
  valorar "su valor es el clima, no el stat".
- **[RISK medio] Empates de categoría (2 físicos + 2 especiales) → naturaleza/SP
  caen a fallback.** Para un mixto real es ambiguo por diseño; documentar que el
  fallback (slot-2 / base stat) es el desempate y es aceptable.
- **[RISK bajo] `_MOVE_CATEGORY` incompleto.** Moves sin entrada cuentan como
  "categoría desconocida" y no votan en `_dominant_attack_category`. Es seguro
  (no introduce categoría falsa); sólo reduce la señal. Verificar que los STAB/
  coverage comunes están mapeados (lo están, `:100-205`).
- **[RISK bajo] Orden de bloques.** (B) y (C') deben ir juntos o (C') tras (B):
  (C') depende de que la naturaleza ya refleje el moveset. Si se mergea (C') sin
  (B), un mon con naturaleza-por-label seguiría desalineado.

---

## 7. Decisiones abiertas [DECISION NEEDED]

1. **Definición de "weather-setter ofensivo".** ¿Cutoff por stat (≥0.5 ≈ stat 100)
   o ampliarlo a "tiene ≥2 moves de daño y ningún move de soporte"? Lo segundo
   clasificaría Abomasnow/Torkoal como atacantes aunque su stat sea <100, lo que
   probablemente es lo que Sergio quiere ("su moveset es ofensivo → constrúyelo
   ofensivo"). **Recomendación de Sola:** usar "tiene kit de soporte" como criterio
   de promoción a lead (§3.1.1) y dejar el rol primary ofensivo por defecto para
   setters sin soporte — es lo que arregla el caso reportado. Confirmar con Sergio.
2. **Fixture Ninetales-A (§6).** ¿Añadir moves de soporte al fixture (más realista)
   o relajar el assert a "lead_support en roles si tiene soporte, sweeper si no"?
   Recomendación: añadir `moves=["aurora-veil","encore","protect","blizzard"]` al
   fixture — refleja el set competitivo real y mantiene la intención del test.
3. **¿Aplicar (C') también al preset defensivo?** El default export es offensive,
   pero el preset defensivo también usa `_is_physical_attacker`. Por consistencia,
   recomendado aplicar el mismo `_offensive_stat_from_nature` al stake ofensivo del
   preset defensivo. Bajo impacto. Confirmar.

---

## 8. Orden de bloques atómicos para Deva

Cada bloque deja la suite verde y es revertible por sí solo.

- **B0 — `_dominant_attack_category` + `_offensive_stat_from_nature` (helpers puros).**
  Añadir ambas funciones privadas con sus unit tests (§5.3.4, §5.3.5). Sin
  integración aún → cero cambio de comportamiento. Suite verde.
- **B1 — Cambio (B): `_derive_nature` consume `_dominant_attack_category`.**
  Integra B0 en naturaleza. Pinned tests Pelipper/physical-lead siguen verdes;
  añadir test setter especial vs físico de naturaleza (§5.3.3 parcial). Suite verde.
- **B2 — Cambio (C'): `_offensive_weights` (y opcional `_defensive_weights`)
  consumen `_offensive_stat_from_nature`.** Ahora SP casa con la naturaleza
  (que ya casa con el moveset). Añadir invariante anti-bug "no daño-especial con
  0 SpA" (§5.3.1 parcial, sobre mons ya existentes). Suite verde.
- **B3 — Cambio (A1/A2): floor de setter condicionado en `assign_role_weights`.**
  `_has_support_kit` + condicionar promoción a primary. AQUÍ se actualiza
  `test_weather_setter_tyranitar_lead_plus_physical` (§5.1) y se ajusta el fixture
  Ninetales-A (§7.2). Añadir tests Abomasnow (§5.3.1), Pelipper-soporte (§5.3.6),
  Torkoal (§5.3.2 según §7.1). Suite verde.
- **B4 — Test de integración end-to-end del caso del bug.** Generar (o construir
  un `TeamVariant` con) Abomasnow y asertar el build completo coherente
  (rol no-lead, tag weather_setter, naturaleza↔SP↔categoría de moves alineados).
  Cierra el ADR.

Orden obligatorio: **B0 → B1 → B2 → B3 → B4** (B3 depende de B0; B4 verifica el
conjunto). B1 y B2 deben mergear juntos o B2 tras B1 (§6 riesgo de orden).

---

## 9. Resumen ejecutivo

La incoherencia de Abomasnow tiene dos causas independientes: **(A)** el floor de
weather-setter (`synergy_engine.py:347-372, 407-409`, `_WEATHER_SETTER_LEAD_WEIGHT
=0.8`) lo fuerza a `lead_support` primary pese a no ser soporte ni tener stat
ofensivo; **(B)** naturaleza/SP se derivan del label de rol y de base atk vs spa,
no del moveset real, así que un coverage especial (Ice Beam) queda con 0 SpA.

Fix recomendado = **ambos ejes**: (A) el rol primary de un setter sin kit de
soporte cae al sweeper por stat dominante y "poner clima" pasa a ser el **tag C3
`weather_setter`** ya existente; (B)+(C') naturaleza y SP se derivan de la
**categoría dominante del moveset asignado** (vía la naturaleza, que actúa de
único punto de verdad). Sin tocar SP 66, items, arquetipos ni firmas públicas;
un test de expectativa-bug (Tyranitar) se actualiza con justificación.
