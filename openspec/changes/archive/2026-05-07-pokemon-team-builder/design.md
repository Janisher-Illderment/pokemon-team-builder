## Context

Herramienta CLI nueva, sin código previo. El usuario tiene proyectos Python similares (mtg-wizard: Click + Rich + SQLite + pytest) — se adopta el mismo patrón de capas para reducir fricción y mantener consistencia. El juego Pokémon Champions tiene un sistema de stats propio (SPs, no EVs/IVs) y un pool cerrado de ~263 Pokémon legales que PokéAPI no conoce: hay que superponer ambas fuentes.

## Goals / Non-Goals

**Goals:**
- CLI instalable (`pip install -e .`) que funcione offline tras la primera sincronización con PokéAPI
- Genera equipos legales para Champions Regulation M-A (Species Clause, Item Clause, pool ~263)
- Orientado a Doubles: roles de Doubles, flexibilidad Pick-4-de-6, sinergias de pares
- Export en formato PokePaste compatible con PikaChampions y ChampTeams.gg
- Distribución de SPs sugerida por rol (no requiere que el usuario conozca el sistema)

**Non-Goals:**
- Sin UI web ni servidor en v1
- Sin integración con API oficial de Champions (no existe API pública)
- Sin tier list dinámica ni meta-tracking en tiempo real
- Sin autenticación ni cuentas de usuario
- Sin soporte a otras regulaciones que no sea M-A en v1

## Decisions

### D1 — Stack: Python 3.11 + Click + Rich + httpx + SQLite + Pydantic
Mismo stack que mtg-wizard. `httpx` + `hishel` para cache HTTP automático en SQLite (TTL 30 días); `pydantic` para validar respuestas de PokéAPI y modelos de dominio. Alternativa descartada: `requests` + cache manual — más verboso, mismo resultado.

**Gestión de dependencias:** `uv` + `pyproject.toml` (más rápido que pip, estándar moderno). Alternativa descartada: pip + requirements.txt — funciona pero `uv` es claramente superior para nuevos proyectos.

### D2 — Estructura de capas (unidireccional, sin dependencias circulares)
```
pokemon_team_builder/
  cli/          # Comandos Click; solo orquesta, sin lógica de negocio
  data/         # Clientes externos: PokéAPI client, legal-pool loader
  domain/       # Modelos Pydantic puros: Pokemon, Team, Role, SPDistribution
  services/     # Lógica de negocio: synergy_engine, team_generator, viability_rater, replica_exporter
  config.py     # Constantes globales: rutas, TTLs, límites de SPs
data/
  legal_pool_mA.json   # Lista legal Regulation M-A (~263 Pokémon) — versionada en repo
  type_chart.json      # Multiplicadores de daño por tipo (18×18) — estático
  role_sp_templates.json  # Plantillas de SPs por rol (sweeper, wall, support, TR setter)
```
Flujo de dependencias: `cli → services → domain ← data`. Los servicios no importan entre sí directamente; se componen en la CLI.

### D3 — Estrategia de datos: PokéAPI con cache SQLite (TTL 30 días)
PokéAPI no tiene datos Champions-específicos. Se usa como fuente de stats base, tipos y moveset. Cache local en SQLite (`~/.pokemon-builder/cache.db`) con TTL de 30 días; tras el primer fetch el tool funciona offline.

La **lista legal de Champions** (legal_pool_mA.json) vive en el repo como fichero estático. Cuando cambie la regulación se actualiza el fichero y se sube un commit. Alternativa descartada: consulta dinámica a Serebii/Victory Road — frágil ante cambios de estructura HTML.

### D4 — Synergy engine: pipeline 3 fases
La búsqueda exhaustiva de 5 compañeros dentro de 263 Pokémon es inmanejable (C(262,5) ≈ 9.6B combinaciones). Pipeline elegido:

1. **Filtrado heurístico** — descarta Pokémon que repliquen tipo(s) del ancla o que no cubran ningún hueco detectado. Reduce candidatos a ~30–50.
2. **Beam search (k=10)** — construye el equipo slot a slot seleccionando los 10 mejores candidatos en cada paso según score de cobertura incremental.
3. **Re-ranking con viability-rater** — puntúa los 10 equipos completos resultantes y ordena; devuelve las 3 mejores variantes.

Alternativas descartadas: algoritmo genético y programación lineal entera — overkill para v1 con un pool de ~263 Pokémon.

### D5 — SP optimizer: plantillas por rol con ajuste fino
Los SPs se distribuyen según plantillas predefinidas en `role_sp_templates.json`:
- **Sweeper físico**: Atk 32 / Spe 32 / HP 2
- **Sweeper especial**: SpAtk 32 / Spe 32 / HP 2
- **Wall físico**: HP 32 / Def 32 / SpDef 2
- **Wall especial**: HP 32 / SpDef 32 / Def 2
- **Lead/Soporte**: Spe 32 / HP 32 / Def 2
- **Trick Room setter**: HP 32 / SpDef 32 / Def 2

Para roles mixtos se usa la plantilla del rol primario. Alternativa descartada: Linear Programming — la función objetivo es subjetiva y las plantillas cubren el 90% de los casos reales.

### D6 — Formato PokePaste para Champions [VERIFICADO]
Formato verificado contra ChampTeams.gg y PikaChampions (fuente: Inte research + pokepast.es ejemplos reales). Ambas herramientas usan el **formato Showdown estándar con `EVs:`** — no existe línea `SPs:` en el export. Conversión: `1 SP × 8 = valor EVs`. `IVs:` se omite (asumir 31 es comportamiento por defecto de Showdown). `Level: 50` se incluye siempre explícitamente.

Formato por Pokémon:
```
Nombre @ Ítem
Ability: Habilidad
Level: 50
EVs: 252 Atk / 252 Spe / 16 HP
Jolly Nature
- Protect
- [STAB move]
- [Coverage move]
- [Role move]
```

Conversión interna: SP → EVs en el momento de serialización (32 SPs = 256 EVs, 2 SPs = 16 EVs).

### D7 — Movesets genéricos por rol
Los team builders competitivos exportan 4 moves concretos por Pokémon (verificado: DevonCorp 38-teams paste, VGCPastes). Se generarán moves genéricos por rol:
- **Universal**: `Protect` en slot 1 (presente en ~95% de sets Doubles competitivos)
- **Sweeper físico**: STAB físico principal + move de cobertura + Protect + flex (Tera Blast o segundo STAB)
- **Sweeper especial**: STAB especial principal + cobertura + Protect + flex
- **Wall físico**: Move de recuperación (si lo aprende) + Protect + move de daño + utility
- **Lead/Soporte**: Tailwind o Follow Me + Protect + move de daño + flex
- **Trick Room setter**: Trick Room + Protect + move de daño + utility

Los moves se seleccionan del moveset real del Pokémon (vía PokéAPI). Si el Pokémon no aprende el move genérico esperado para su rol, se sustituye por el STAB más potente disponible. Se documenta que los moves son sugerencias de partida, no sets optimizados.

## Risks / Trade-offs

- **Lista legal desactualizada** → La regulación cambia cada 2–3 meses. `legal_pool_mA.json` necesita actualización manual. Mitigación: campo `regulation` + `valid_until` en el JSON; la CLI advierte si la fecha de validez pasó.
- **PokéAPI sin datos Champions** → Movesets de PokéAPI son del main series, no de Champions específicamente. Algunos moves pueden no estar disponibles en Champions. Mitigación: aceptable en v1; se documenta como limitación conocida.
- **Calidad subjetiva del viability-rater** → La puntuación 0–100 es heurística, no refleja el meta real. Mitigación: se muestra siempre la explicación textual junto al número para que el usuario pueda juzgar.
- **Beam search no garantiza el óptimo global** → Puede perderse combinaciones con sinergia no obvia. Mitigación: aceptable en v1; el output es un punto de partida, no un oráculo.

## Open Questions

~~1. Formato PokePaste~~ → Resuelto: `EVs:` estándar Showdown, `Level: 50`, sin `IVs:`. Ver D6.
~~2. Scope de moveset~~ → Resuelto: moves genéricos por rol con Protect universal. Ver D7.
~~3. Nombre del comando~~ → Resuelto: `poke-builder`.
