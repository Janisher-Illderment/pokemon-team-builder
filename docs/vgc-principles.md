# Principios VGC (Pokémon Champions) — fuente para decisiones de diseño

> Síntesis de 7 videos de la serie de competitivo (Pokémon Champions, **VGC Dobles**)
> usados como fuente autorizada para corregir la lógica de `pokemon-team-builder`.
> Transcripciones crudas en `transcripts/<id>.txt` (gitignored). Cada principio cita su video.

## Índice de videos
- **V1** `wPwuF-nzoBU` — Introducción al Competitivo
- **V2** `kGoO3B0Z5_c` — Climas, control de velocidad, prioridad, campos
- **V3** `fxrwx3bo_kc` — "Tus Equipos No Tienen Sentido" (arquetipos)
- **V4** `AY9ncxTo0nU` — Cores y sinergias (tipo / habilidad / movimiento / rol)
- **V5** `7L9XKbade7U` — "Los Combates Se Ganan Antes de Empezar" (Team Preview, win condition)
- **V6** `sje92jycerk` — "Xokas No Tiene Razón" (RNG, proactividad, fiabilidad de moves)
- **V7** `KKd7Ayygbsk` — "Estos Pokémon Son Peores de lo que Piensas" (valoración de Pokémon)

---

## 1. Mecánicas confirmadas (el builder YA las modela bien)
- **Sistema "puntos de estadística" = 66 total, máx 32 por stat** (V1). Es la mecánica REAL de Champions
  (sustituye 510 EV / 252). 1 punto = 1 punto de stat final. → `config.py:MAX_SP_TOTAL/MAX_SP_STAT` **correcto, no tocar**.
- **IVs**: probablemente todos a 31 en Champions (V1, sin confirmar 100%). Naturalezas presentes.
- **Pool de objetos restringido** (V5, V7): en Champions NO están chaleco asalto, casco dentado, etc.
  → la restricción del pool **es correcta**. (Lo dudoso son los *defaults por rol*, ver §5.)
- **Megaevoluciones** son la mecánica del primer formato; ≤1 por equipo (V1). Correcto.
- **Protect/Detect** y movimientos de área (golpean a 2) son centrales en dobles (V1). Correcto.
- **7 arquetipos** = hyper offense, hard trick room, bulky offense, weather (sol/lluvia/arena/nieve),
  stall, perish trap, balance (V3). **Coinciden exactamente con el código.**

## 2. Concepto núcleo: PRESENCIA OFENSIVA (gap del builder)
- En dobles, un Pokémon **pasivo / sin amenaza** es un LASTRE: el rival lo ignora y ataca 2x al compañero
  (V3: Garganacl, Blissey; V7). "Falta de presencia ofensiva".
- Por eso **stall es INVIABLE en dobles** (V3) y los equipos puramente defensivos/reactivos pierden por
  desgaste y varianza (V6).
- Implicación de diseño: el rol "wall puro" **no debe premiarse**; debe valorarse que cada miembro
  represente una amenaza (stat ofensivo alto **o** disrupción real: redirección, intimidación, sorpresa,
  control de velocidad, estado). → contradice los roles `physical_wall/special_wall` como positivos.

## 3. Roles reales en dobles (taxonomía a alinear)
De V3/V4/V5, las funciones que de verdad importan:
- **Amenaza ofensiva / win condition** — hace daño inmediato o se setea (danza espada, paz mental).
- **Habilitador / support** — redirección (señuelo/polvo ira = follow-me/rage-powder), **sorpresa (fake-out)**,
  **intimidación**, boost al aliado (decoración/refuerzo/motivación = helping-hand etc.), pantallas.
- **Control de velocidad** — viento afín (tailwind), espacio raro (trick room), viento hielo (icy-wind),
  onda trueno (thunder-wave), **prioridad**, **pañuelo elegido (choice scarf)**. Casi obligatorio (V2,V3,V5).
- **Pivote defensivo** — bulky offense: aguanta pero conserva presencia ofensiva (NO wall pasivo).
- **Setter/abuser de clima** y **setter/abuser de Trick Room**.

## 4. Cobertura: NO es solo STAB (corrige el builder)
- "A veces pegar **neutro** con STAB vale lo mismo que superefectivo… no te obsesiones con el superefectivo" (V4).
- Pero **los ataques de cobertura NO-STAB sí importan**: la core hada/dragón/acero "no cubre al acero con sus
  STAB → es importante que alguno tenga **ataques de cobertura** para dañar al acero" (V4).
- → La regla actual (un tipo solo cuenta como cubierto si el move es STAB del portador,
  `synergy_engine.py:423-439`) **descarta justo la cobertura no-STAB que el video valora**. Debe contar
  cobertura no-STAB (ponderando STAB por encima), y no exigir cobrir los 18 tipos (neutro es válido).

## 5. Objetos: pool restringido OK, defaults por rol cuestionables
- Objetos realmente usados en Champions (V4,V5,V7): **banda focus** (focus sash), **pañuelo elegido**
  (choice scarf), **vallas de tipo** (p.ej. valla Pomaro / type-resist berries) para sobrevivir un golpe,
  Sitrus, intimidación+sorpresa como "items virtuales". Nervio (Aerodáctil) desactiva vallas.
- → Revisar `team_generator.py:47-74`: defaults como Shell Bell / Scope Lens / Leppa / Persim no reflejan
  lo que se juega. Sustituir por elecciones reales DENTRO del pool legal (`champions_legal_items.json`).

## 6. Win condition + Team Preview (gap)
- "Los combates se ganan antes de empezar" (V5): identificar **tu condición de victoria** y la del rival,
  proteger la tuya, eliminar las piezas que la bloquean. La win condition puede ser ofensiva o defensiva.
- **Checks vs Counters** (V3): check = respuesta situacional; counter = entra siempre y para en seco.
  Balance necesita counters reales; hyper offense suele tener solo checks.
- → El builder podría **articular la win condition** del equipo y clasificar respuestas como check/counter
  (enriquece `matchup_analyzer.py`), en vez de quedarse en un score 0-100.

## 7. Cores canónicos (V4) — para `favorite_first_builder`
- **Tipo**: firewater = **agua/fuego/planta** (THE core de balance, recomendada a novatos);
  **hada/dragón/acero** (ofensiva, pide cobertura anti-acero).
- **Habilidad**: arena (Tyranitar+Excadrill), redirección+frágil ofensivo, "competitivo" (Kingambit)
  castiga bajadas de stats.
- **Movimiento**: Pelipper+Archaludón (electrorayo en lluvia), campo de hierba + fitoimpulso.
- **Rol/modo dual ("Taelroom")**: equipo con espacio raro (modo lento) **y** viento afín (modo rápido);
  ganó el mundial 2024.

## 8. Valoración de Pokémon — más allá del BST (V7)
Un Pokémon NO vale por stats totales. Penalizar / señalar:
- **Stats ofensivas partidas** (atk Y spa altos): se desperdicia una (Goodra, Greninja).
- **Movepool**: ¿aprende los moves que necesita su rol? (Mewtwo X sin A bocajarro = malo).
- **Coherencia tipo↔bulk**: tipo Roca defensivo es malo; tipo Hielo es el peor defensivo.
- **Velocidad "en el limbo"** (ni rápido ni lento) = mala.
- **Fiabilidad de moves** (V6): moves físicos Roca fallan (avalancha/roca afilada); precisión importa.
- **Coste de recursos**: si el equipo debe girar TODO alrededor del mon para que funcione (Mega Chesnaught)
  = lastre. Habilidad debe diferenciarlo de otros del mismo rol.

## 9. RNG y proactividad (V6)
- Equipos **proactivos** sufren menos varianza; los reactivos/defensivos sufren más → refuerza §2.
- Estrategias gimmick (evasión, OHKO moves guillotina/fisura, sweep dependiente de 1 combo) = no viables.
- Control de velocidad y prioridad mitigan RNG (p.ej. avalancha flinch). Refuerza §3.

---

## Mapeo a correcciones de código (propuesta — pendiente de confirmar alcance)

| ID | Corrección | Archivo(s) | Soporte video | Prioridad |
|----|-----------|-----------|---------------|-----------|
| C1 | Cobertura cuenta moves NO-STAB (STAB pondera más); no exigir 18 tipos | `synergy_engine.py:393-467` + tests | V4 §4 | **Alta** |
| C2 | Penalizar "presencia ofensiva" ausente; dejar de premiar wall puro | `viability_rater.py`, `synergy_engine.py` roles | V3,V6,V7 §2 | **Alta** |
| C3 | Re-alinear taxonomía de roles a dobles (amenaza/habilitador/speed/pivote) | `synergy_engine.py:171-352` | V3,V4 §3 | **Alta** (arch → Sola) |
| C4 | Stall: no inviable-pero-bien-puntuado; advertir/penalizar en dobles | `archetype_weights.json`, `viability_rater.py` | V3 §2 | Media |
| C5 | Defaults de objeto por rol → items realmente usados del pool legal | `team_generator.py:47-74` | V4,V5,V7 §5 | Media |
| C6 | Heurística de valoración de Pokémon (stats partidas, fiabilidad, tipo/bulk) | `meta_service.py`/scoring | V7 §8 | Media (arch → Sola) |
| C7 | Articular win condition + check/counter en análisis | `matchup_analyzer.py` | V5 §6 | Baja (aditivo) |
| C8 | Reconocer cores canónicos (firewater, etc.) en core duo | `favorite_first_builder.py` | V4 §7 | Baja (aditivo) |

**Descartadas tras leer los videos:** sistema SP→EV (mecánica real, V1); quitar restricción de pool
(la restricción es correcta, V5/V7); reclasificar perish-trap como no-cheese (es un arquetipo legítimo
pero muy difícil — el gating actual es razonable).
