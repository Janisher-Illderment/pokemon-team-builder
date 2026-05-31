# ADR — Corrección del modelo de scoring/roles para VGC Dobles (C2, C3, C6)

> **Status:** Proposed
> **Fecha:** 2026-05-31
> **Autor:** Sola (Solution Architect)
> **Fuente autorizada:** `docs/vgc-principles.md` (síntesis de 7 vídeos)
> **Rama:** `feat/vgc-design-corrections`
> **Precedente:** C1 (cobertura no-STAB, `synergy_engine.analyze_coverage`) y C4
> (stall no exento de penalización de velocidad, `viability_rater._speed_control_penalty`)
> ya implementados. Este ADR es la continuación coherente con esos patrones.

Las rutas de fichero en `docs/vgc-principles.md` omiten el prefijo de paquete.
La ruta real es `pokemon_team_builder/services/…`. Todas las referencias `file:línea`
de este ADR usan la ruta real verificada.

---

## 0. Contexto y restricciones

### Restricciones duras (NO tocar — confirmadas por vídeos + datos in-game de Sergio)
- **Sistema SP** (66 total / 32 por stat): mecánica real de Champions (V1).
  `config.MAX_SP_TOTAL` / `MAX_SP_STAT`. **No tocar.**
- **Pool de 48 items**: `champions_legal_items.json`. No re-añadir Focus
  Sash / Choice Scarf / Sitrus (no existen en Champions). **No tocar.**
- **7 arquetipos**: `archetype_weights.json`. Correctos (V3). **No tocar.**

### Restricción blanda dominante (gobierna toda la estrategia de migración)
Los **labels de rol son claves de diccionario** en 4 mapas estáticos y **sets de
literales** en 6 servicios:

| Consumidor | Uso del label | file:línea |
|---|---|---|
| `role_sp_templates.json` | clave → plantilla SP | todo el fichero |
| `team_generator._DEFAULT_ITEM_BY_ROLE` | clave → item default | `team_generator.py:62-67` |
| `team_generator` nature defaults | clave → naturaleza | `team_generator.py:256-261` |
| `team_generator._OFFENSIVE_FALLBACK_*` | orden de fallback | `team_generator.py:218-222` |
| `ev_explainer` descripciones | clave → texto ES | `ev_explainer.py:78-84` |
| `ability_implicit_roles.json` | `role` apunta a estos labels | `flame-body→physical_wall`, etc. |
| `synergy_engine` sets | `_SWEEPER_ROLES`, `_SUPPORT_ROLES` | `synergy_engine.py:53-54` |
| `viability_rater` sets | `_SWEEPER_ROLES`, `_SUPPORT_ROLES`, `_BO3_*` | `viability_rater.py:38-49` |
| `matchup_analyzer` | `support_roles` literal set | `matchup_analyzer.py:101` |
| `favorite_first_builder` | sets literales sweeper/redirect | `favorite_first_builder.py:165,170` |

**Consecuencia de diseño:** renombrar los 7 labels es BREAKING en cascada y
rompería buena parte de los 487 tests. Por tanto este ADR **EXTIENDE, NO
REEMPLAZA**. Los 7 labels viejos se conservan como sustrato mecánico (siguen
siendo las claves de SP/item/nature); las 3 correcciones se implementan como una
**capa aditiva de "presencia/penalización"** sobre el modelo existente.

### Decisión arquitectónica central
> **Separar "qué es mecánicamente un Pokémon" (roles, sin cambios) de "cuánto
> aporta en dobles" (presencia + calidad, capa nueva).** La taxonomía de dobles
> (C3) se modela como **tags derivados** computados desde los roles+moves+abilities
> existentes, no como un reemplazo de los labels.

Esto respeta el principio del repo ("boring technology wins", migración gradual)
y reutiliza `assign_role_weights`, `analyze_coverage`, `_count_speed_control`,
`_core_diversity_points` sin reescribirlos.

---

## 1. Modelo de datos y firmas afectadas

### 1.1 Nuevo dataclass: `PresenceReport` (en `synergy_engine.py`)
Junto a `RoleAssignment` (`synergy_engine.py:89-105`). Frozen, no muta nada.

```
@dataclass(frozen=True)
class PresenceReport:
    has_offensive_stat: bool      # atk o spa >= UMBRAL_PRESENCIA (100)
    has_disruption: bool          # intimidate/fake-out/redirect/speed-ctrl/estado/boost-aliado
    disruption_sources: list[str] # etiquetas legibles para la explicación ES
    is_passive_liability: bool    # NOT has_offensive_stat AND NOT has_disruption
    presence_weight: float        # 0.0..1.0, gradiente (ver §2.1)
```

### 1.2 Nueva función (C2): `assess_presence(pokemon, moves, ability) -> PresenceReport`
- **Ubicación:** `synergy_engine.py`, después de `assign_role_weights`.
- **Reutiliza:** `assign_role_weights(pokemon).role_weights` (stat ofensivo via
  `physical_sweeper`/`special_sweeper` weight), y los marcadores de disrupción.
- **Firma:**
  ```
  def assess_presence(
      pokemon: PokemonData,
      moves: list[str] | None = None,
      ability: str | None = None,
  ) -> PresenceReport
  ```
- `moves`/`ability` opcionales: si son `None` cae a `pokemon.move_names` /
  `pokemon.abilities[0]` (mismo patrón degradante que `analyze_coverage`
  cuando `movesets is None`, `synergy_engine.py:427-453`).

### 1.3 Nueva función (C3): `derive_doubles_tags(pokemon, moves, ability) -> list[str]`
- **Ubicación:** `synergy_engine.py`.
- **Output:** lista de tags de la taxonomía de dobles (§3), derivada — NO almacenada.
- **Reutiliza:** `assign_role_weights`, `assess_presence`, `_count_speed_control`
  (movido/compartido, ver §3.3).

### 1.4 Nueva función (C6): `evaluate_pokemon_quality(pokemon) -> QualityReport`
- **Ubicación:** **nuevo módulo** `pokemon_team_builder/services/pokemon_evaluator.py`.
  Justificación en §4.
- **Dataclass:**
  ```
  @dataclass(frozen=True)
  class QualityReport:
      score: float                  # 0.0..1.0 multiplicador de calidad
      flags: list[str]              # etiquetas legibles ES para UI
      split_attacker: bool          # atk Y spa ambos altos
      type_bulk_mismatch: bool      # Roca/Hielo con bulk invertido en stats
      speed_limbo: bool             # velocidad ni rápida ni lenta
      unreliable_moves: list[str]   # moves físicos Roca de baja precisión asignados
  ```

### 1.5 Integración en el scorer (`viability_rater.py`)
- **`_roles_points`** (`viability_rater.py:141-159`): se le añade **penalización
  por lastres pasivos** (C2) y deja de contar walls puros como positivo neto
  (ver §2.2). Firma intacta `(_roles_points(variant) -> int)`.
- **`score_team`** (`viability_rater.py:319-387`): añade dos términos nuevos al
  total ANTES del clamp (mismo punto de inserción que `weather_pts` y
  `speed_penalty` ya existentes, `viability_rater.py:366-374` y `379-386`):
  `+ presence_penalty` (C2) y `+ quality_adjustment` (C6). Firma de retorno
  intacta `(float, float)`.

**Ningún cambio de firma pública.** `assign_role`, `assign_role_weights`,
`analyze_coverage`, `score_team`, `RoleAssignment`, `TeamMember.role` permanecen
exactamente igual. Todo lo nuevo es additivo.

---

## 2. C2 — Presencia ofensiva: fórmula

### 2.1 `presence_weight` (gradiente, no cliff)
Coherente con la banda ±15 de `_gradient_weight` (`synergy_engine.py:116-130`).

```
off = max(role_weights["physical_sweeper"], role_weights["special_sweeper"])
       # ya gradiente sobre umbral 100, reutilizado tal cual

disr = 1.0 si has_disruption else 0.0

presence_weight = clamp(max(off, disr), 0.0, 1.0)
is_passive_liability = (off < 0.5) AND (not has_disruption)
```

`has_disruption` es `True` si el Pokémon aporta **cualquiera** de:

| Categoría | Detección | Fuente reutilizada |
|---|---|---|
| Intimidación | ability == `intimidate` | `ability_implicit_roles.json` |
| Sorpresa (fake-out) | `fake-out` in moves | `_PRIORITY_SUPPORT_MARKERS` `synergy_engine.py:51` |
| Redirección | `follow-me`/`rage-powder` in moves | `synergy_engine.py:270` |
| Control de velocidad | move ∈ `_SPEED_CONTROL_MOVES` | `viability_rater.py:53-65` |
| Estado | `thunder-wave`/`will-o-wisp`/`spore`/`glare`/`nuzzle`/`stun-spore` | subset de speed-control + estado puro |
| Boost a aliado | `helping-hand`/`decorate`/`coaching` in moves | nuevo set pequeño `_ALLY_BOOST_MOVES` |

> **NOTA de implementación (reuso):** los sets de moves de disrupción YA viven en
> `viability_rater` (`_SPEED_CONTROL_MOVES`, `_CORE_VIABLE_MOVES`,
> `_PRIORITY_SUPPORT_MARKERS`). Para evitar import circular
> (`synergy_engine` no importa `viability_rater`), **mover los frozensets de
> moves de disrupción a `synergy_engine.py`** (capa más baja) y que
> `viability_rater` los importe. Es un move puro de constantes, sin cambio de
> valores → los tests de `viability_rater` que referencian esos nombres siguen
> pasando si se re-exportan. Ver riesgo R3.

### 2.2 Penalización en el scorer (C2 en `_roles_points` y `score_team`)

**Cambio en `_roles_points`** (`viability_rater.py:141-159`): hoy suma +15 por
sweeper presente y +10 por support. **No premia walls** (correcto — los walls
nunca sumaban). El bug real es que un equipo de walls puros igual obtenía buen
score por cobertura/SP/items. La corrección es una **penalización a nivel equipo**:

```
# Nuevo término en score_team, junto a speed_penalty.
passive_count = sum(1 for m in members if assess_presence(...).is_passive_liability)

presence_penalty = -PASSIVE_LIABILITY_PENALTY * passive_count
   con PASSIVE_LIABILITY_PENALTY = 8.0  (≤ speed_penalty=15; un lastre duele,
   dos lastres es casi descalificatorio sin invalidar el equipo entero)
```

**Por qué a nivel equipo y no por miembro en `_roles_points`:** `_roles_points`
está clampeado a `[0, _W_ROLES]` (`viability_rater.py:159`); meter ahí la
penalización la "comería" el clamp inferior. El patrón correcto ya existe:
`speed_penalty` se aplica fuera de los componentes clampeados, directo al total
(`viability_rater.py:374` y `385`). C2 sigue ese patrón exacto.

**Escalado por arquetipo:** la penalización NO se multiplica por
`weights.roles`. Un lastre pasivo es malo en TODO arquetipo (V3: stall inviable).
Igual que `speed_penalty` es plano. **Excepción explícita:** `stall` y
`perish_trap` — ver R1. Decisión: **no eximir** (coherente con C4, que dejó de
eximir stall del speed penalty). El gating de dificultad de esos arquetipos ya es
razonable (memoria de proyecto).

### 2.3 Qué pasa con `physical_wall`/`special_wall`
**No se eliminan** (son claves de SP/item/nature/explainer). Pero un Pokémon cuyo
ÚNICO rol ≥0.5 es wall y que NO tiene disrupción → `is_passive_liability = True`
→ penalizado. Un wall CON intimidación o redirección (p.ej. Incineroar) →
`has_disruption = True` → NO penalizado (es un "pivote defensivo no pasivo", §3).
Esto implementa exactamente §2/§3 de los principios sin tocar la mecánica.

---

## 3. C3 — Taxonomía de roles para dobles

### 3.1 Decisión: EXTENDER vía tags derivados (no reemplazar)
La taxonomía de dobles se expone como **`doubles_tags`** computados, mapeados
desde los 7 labels mecánicos + presence + speed-control. Los labels viejos siguen
gobernando SP/item/nature. Los tags nuevos gobiernan explicación, badges y futuras
heurísticas de construcción.

### 3.2 Mapeo viejo → tag de dobles

| Tag de dobles (V3/V4 §3) | Condición derivada (reutiliza funciones existentes) |
|---|---|
| `offensive_threat` (amenaza/win-con) | `physical_sweeper`/`special_sweeper` weight ≥ 0.5, **o** conoce move de setup (`swords-dance`/`dragon-dance`/`calm-mind`/`nasty-plot`) |
| `support_enabler` (habilitador) | `redirect` ∈ roles, **o** `intimidate`, **o** `fake-out`, **o** `helping-hand`, **o** screens (`light-screen`/`reflect`/`aurora-veil`) |
| `speed_control` | `_count_speed_control` aporta ≥1.0 para ese miembro (extraído per-member del existente `viability_rater.py:277-293`) |
| `defensive_pivot` (bulky NO pasivo) | `physical_wall`/`special_wall` weight ≥ 0.5 **AND** `has_disruption` (si no → es lastre, no pivote) |
| `weather_setter` | ability ∈ `_WEATHER_SETTER_ABILITIES` (`synergy_engine.py:77-79`) o species ∈ `_COMPETITIVE_WEATHER_SPECIES` |
| `weather_abuser` | ability ∈ `weather_dependent_abilities.json` |
| `trick_room_setter` | `trick_room_setter` weight ≥ 0.5 (label existente, reutilizado 1:1) |
| `trick_room_abuser` | spe ≤ 60 AND `offensive_threat` AND equipo tiene TR setter |

`weather_abuser`/`trick_room_abuser` son context-dependientes (necesitan el equipo),
así que se computan en una variante de equipo `derive_team_tags(variant)`, mientras
los per-mon se computan en `derive_doubles_tags(pokemon, moves, ability)`.

### 3.3 Reuso de `_count_speed_control`
Hoy `_count_speed_control` (`viability_rater.py:277-293`) recibe `members` y
suma. Se **refactoriza a una función per-member** `_member_speed_control(member)
-> float` y `_count_speed_control` se reescribe como `sum(_member_speed_control(m)
for m in members)`. Comportamiento idéntico (los tests de
`test_speed_control_required` siguen pasando), pero ahora `derive_doubles_tags`
puede consultarla por miembro. Refactor mecánico, sin cambio de valores.

### 3.4 Dónde se exponen los tags
- `TeamMember` **no cambia su esquema** (los tags se derivan on-demand, no se
  persisten — evita migración de datos serializados y mantiene `pokepaste_parser`
  y `replica_exporter` intactos).
- El API/CLI los pide vía `derive_doubles_tags(...)` en el punto de presentación.
- `matchup_analyzer.support_roles` (`matchup_analyzer.py:101`) puede migrar a
  consultar `support_enabler` tag en una iteración POSTERIOR (no en esta — fuera
  de alcance, ver orden §6).

---

## 4. C6 — Valoración más allá del BST

### 4.1 Decisión de ubicación: NUEVO módulo `pokemon_evaluator.py`
Descartadas las dos alternativas:
- **`meta_service.py`** — NO. `meta_service` es un cliente HTTP de MunchStats
  (uso real). La calidad intrínseca de un Pokémon no depende del meta online y no
  debe acoplarse a un fetch con TTL/caché. Mezclar responsabilidades.
- **dentro de `viability_rater`** — NO como hogar de la lógica. `viability_rater`
  puntúa EQUIPOS; C6 evalúa Pokémon individuales. Pero `viability_rater` SÍ
  **consume** el `QualityReport` (term `quality_adjustment` en `score_team`).

Un módulo dedicado mantiene `viability_rater` enfocado y permite testear C6 de
forma aislada (input = un `PokemonData`, output = `QualityReport` determinista,
sin red, sin equipo).

### 4.2 Componentes de `evaluate_pokemon_quality` (señales V7 §8)

Cada componente resta de un multiplicador base 1.0 (clamp a [0.5, 1.0] — un mon
nunca vale 0; sigue siendo legal y jugable):

| Señal | Detección | Penalización al multiplicador |
|---|---|---|
| **Stats ofensivas partidas** | `atk ≥ 90 AND spa ≥ 90` (ambos relevantes → uno se desperdicia con 66 SP) | −0.10 |
| **Coherencia tipo↔bulk** | tipo ∈ {`rock`,`ice`} **AND** (def_ + spd) ≥ 180 (bulk "invertido" en un tipo defensivo malo) | −0.10 |
| **Velocidad en el limbo** | `60 < spe < 95` (ni habilita TR ni gana tailwind/scarf-tier) | −0.05 |
| **Moves no fiables** | move asignado ∈ `_LOW_ACCURACY_ROCK_PHYS` (`rock-slide` 90, `stone-edge` 80) | −0.05 por move, máx −0.10 |
| **Movepool insuficiente para rol** | rol primario sweeper pero sin move STAB damaging del propio tipo en `move_names` | −0.10 |

Umbrales marcados `[UNCERTAIN]` — son puntos de partida conservadores; deben
calibrarse contra el pool legal real (`legal_pool_mA.json`, 167 mons) en un test
de no-regresión (§5). **Coste de recursos / "gira todo alrededor del mon"**
(Mega Chesnaught, V7) se marca `[DECISION NEEDED]` y se DIFIERE — requiere modelar
dependencia de equipo, no encaja en un evaluador per-mon puro.

### 4.3 Integración con el scorer
```
# En score_team, junto a presence_penalty:
quality_mult_avg = mean(evaluate_pokemon_quality(m.pokemon).score for m in members)
quality_adjustment = (quality_mult_avg - 1.0) * QUALITY_WEIGHT
   con QUALITY_WEIGHT = 10.0  (un equipo de mons mediocres pierde hasta ~5 pts;
   señal, no descalificación — V7 dice "peores de lo que piensas", no "ilegales")
```

`quality_adjustment` es ≤ 0 (multiplicador ≤ 1.0). No infla scores; solo señala.
Se aplica plano (no por arquetipo) — la calidad intrínseca es arquetipo-agnóstica.

---

## 5. Tests a añadir / actualizar

### 5.1 Nuevos ficheros de test
- `tests/test_presence.py` (C2): `assess_presence` con casos canónicos de V3 —
  Garganacl/Blissey → `is_passive_liability=True`; Incineroar (intimidate) →
  `has_disruption=True, is_passive_liability=False`; un sweeper puro →
  `has_offensive_stat=True`. Test del término `presence_penalty` en `score_team`:
  equipo de 6 walls pasivos vs equipo con presencia → el primero puntúa menos.
- `tests/test_doubles_tags.py` (C3): `derive_doubles_tags` para un representante
  de cada uno de los 8 tags; `defensive_pivot` SOLO cuando hay disrupción.
- `tests/test_pokemon_evaluator.py` (C6): cada señal de §4.2 aislada + un test
  de **no-regresión sobre el pool legal completo** que afirma que ningún mon cae
  por debajo de 0.5 y que el reparto de penalizaciones es razonable (p.ej. no
  más del X% del pool marcado split_attacker).

### 5.2 Tests existentes a actualizar (esperado, no accidental)
- `tests/test_viability_rater.py`: los scores absolutos de equipos que contengan
  walls pasivos o mons de baja calidad **bajarán**. Actualizar asserts de valor
  exacto a rangos o a comparaciones relativas. **Auditar primero** los asserts de
  igualdad exacta de score (patrón de proyecto: contar asserts antes de bulk
  change). El término por defecto (balance, equipo sano) NO debe cambiar si el
  equipo no tiene lastres → muchos tests seguirán pasando sin tocar.
- `tests/test_strategy_archetype.py` y `tests/test_bo3_mode.py`: idem, revisar
  asserts de score exacto.
- `tests/test_speed_control_required.py`: el refactor de `_count_speed_control`
  (§3.3) debe dejarlos verdes sin cambios; si alguno referencia la firma interna,
  ajustar import.
- `tests/test_synergy_engine.py` y `tests/test_role_gradient.py`: NO deben
  cambiar (no tocamos `assign_role_weights` ni `_gradient_weight`). Si cambian, es
  señal de regresión.

### 5.3 Invariante de migración
Un test de "compatibilidad hacia atrás": para un equipo balance sano y sin
lastres, `score_team(...)[0]` antes y después debe ser **idéntico** (los nuevos
términos valen 0). Esto prueba que la capa es additiva pura en el caso nominal.

---

## 6. Riesgos y orden de implementación

### Riesgos
- **[R1] Arquetipos defensivos legítimos.** `stall`/`perish_trap` tendrán muchos
  lastres por construcción. La penalización C2 podría hacerlos no-construibles.
  *Mitigación:* `PASSIVE_LIABILITY_PENALTY=8` es señal, no veto; y C4 ya estableció
  el precedente de no eximir stall. **[DECISION NEEDED]** confirmar con Sergio que
  queremos que perish_trap también coma la penalización (probablemente sí — es
  difícil a propósito).
- **[R2] Calibración de umbrales C6.** Los valores de §4.2 son `[UNCERTAIN]`. Sin
  el test de no-regresión sobre el pool, podríamos penalizar de más. *Mitigación:*
  el test 5.1 sobre los 167 mons es BLOQUEANTE para mergear C6.
- **[R3] Import circular.** `synergy_engine` (capa baja) no puede importar
  `viability_rater`. Los sets de disrupción se mueven A `synergy_engine` y
  `viability_rater` los re-importa. *Mitigación:* hacerlo en un commit de
  refactor puro y separado (bloque 0), verificando que `test_viability_rater`
  sigue verde antes de añadir lógica nueva.
- **[R4] Detección de moves de estado/boost depende del slug exacto.** Igual que
  el resto del codebase, asume slugs hyphen-lower de PokeAPI. *Mitigación:* tomar
  los slugs de una fuente verificada (Inte) antes de poblar `_ALLY_BOOST_MOVES` y
  `_STATUS_MOVES`; no inventar (memoria: nunca fabricar datos competitivos sin
  cross-check).

### Orden recomendado (bloques atómicos para Deva — 1 feature = 1 invocación)

> **Bloque 0 (refactor puro, sin lógica nueva):** mover frozensets de disrupción
> a `synergy_engine.py`, re-exportar desde `viability_rater`; extraer
> `_member_speed_control`. Verde en toda la suite. **Gate:** suite intacta.

> **Bloque 1 — C2 presencia:** `PresenceReport` + `assess_presence` +
> `tests/test_presence.py`. Sin tocar el scorer aún. **Gate:** tests nuevos verdes.

> **Bloque 2 — C2 integración scorer:** término `presence_penalty` en
> `score_team`; actualizar asserts de `test_viability_rater`/`test_strategy_archetype`.
> **Gate:** invariante 5.3 (equipo sano sin cambio de score).

> **Bloque 3 — C3 tags:** `derive_doubles_tags` + `derive_team_tags` +
> `tests/test_doubles_tags.py`. Solo derivación, sin tocar consumidores.
> **Gate:** tags correctos para los 8 representantes.

> **Bloque 4 — C6 evaluador:** nuevo `pokemon_evaluator.py` + `QualityReport` +
> `tests/test_pokemon_evaluator.py` incluyendo no-regresión sobre el pool.
> **Gate:** ningún mon < 0.5; calibración revisada por Sergio.

> **Bloque 5 — C6 integración scorer:** término `quality_adjustment` en
> `score_team`. **Gate:** invariante 5.3 sigue válido.

> **(Diferido, NO en este ADR):** migrar `matchup_analyzer.support_roles` y
> `favorite_first_builder` a consumir tags C3; señal "coste de recursos" de C6;
> exponer tags en CLI/API.

Cada bloque deja la suite verde y es revertible de forma independiente.

---

## 7. Resumen de trade-offs

| Decisión | Elegido | Alternativa rechazada | Por qué |
|---|---|---|---|
| Roles C3 | Tags derivados aditivos | Renombrar 7 labels | Labels son claves de 4 mapas + sets en 6 servicios → break masivo de 487 tests |
| C2 en scorer | Penalización plana a nivel equipo (como speed_penalty) | Restar dentro de `_roles_points` | El clamp `[0,_W_ROLES]` se comería la penalización |
| C6 ubicación | Módulo nuevo `pokemon_evaluator.py` | `meta_service` / dentro de `viability_rater` | Evita acoplar calidad intrínseca a fetch HTTP; separa scoring de equipo vs de mon |
| Disrupción moves | Mover sets a `synergy_engine` y re-importar | Duplicar sets | Evita import circular sin duplicar fuente de verdad |
| Walls puros | Penalizar vía `is_passive_liability`, conservar labels | Borrar `physical_wall`/`special_wall` | Los labels siguen siendo necesarios para SP/item/nature |
