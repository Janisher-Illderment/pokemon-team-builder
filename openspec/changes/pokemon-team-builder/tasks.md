## 1. Scaffolding y setup

- [ ] 1.1 Crear `pyproject.toml` con `uv`: dependencias (`click`, `rich`, `httpx`, `hishel`, `pydantic`), entry point `poke-builder`
- [ ] 1.2 Crear estructura de directorios: `pokemon_team_builder/{cli,data,domain,services}/`, `data/`, `tests/`
- [ ] 1.3 Crear `config.py` con constantes: rutas de cache (`~/.pokemon-builder/`), TTL PokéAPI (30 días), límites SP (MAX_SP=66, MAX_SP_STAT=32)
- [ ] 1.4 Inicializar `pytest` con `conftest.py` y un test de smoke que valide el entry point

## 2. Data estática — pool legal y type chart

- [ ] 2.1 Crear `data/legal_pool_mA.json` con los ~263 Pokémon legales de Regulation M-A (nombres y números de Pokédex), campo `regulation: "M-A"` y `valid_until: "2026-06-17"`
- [ ] 2.2 Crear `data/type_chart.json` con la tabla 18×18 de multiplicadores de daño (todos los tipos)
- [ ] 2.3 Crear `data/role_sp_templates.json` con las plantillas de SPs por rol (sweeper físico/especial, wall físico/especial, lead/soporte, trick room setter)
- [ ] 2.4 Crear `pokemon_team_builder/data/legal_pool_loader.py`: carga `legal_pool_mA.json`, expone `is_legal(name_or_id) -> bool` y `valid_until() -> date`; advierte en CLI si la fecha expiró

## 3. PokéAPI client con cache SQLite

- [ ] 3.1 Crear `pokemon_team_builder/data/pokeapi_client.py` con `httpx` + `hishel` (cache SQLite TTL 30d): métodos `get_pokemon(name_or_id)` y `get_type(type_name)`
- [ ] 3.2 Definir modelos Pydantic en `pokemon_team_builder/domain/models.py`: `PokemonData` (nombre, tipos, base stats, movelist), `TypeChart`, `Team`, `TeamVariant`
- [ ] 3.3 Test: mock HTTP → verificar que el client cachea correctamente y que falla con error claro si PokéAPI no responde en 5s

## 4. pokemon-lookup service

- [ ] 4.1 Crear `pokemon_team_builder/services/pokemon_lookup.py`: combina PokéAPI client + legal pool loader; retorna `PokemonData` o lanza error con mensaje legible si ilegal o no encontrado
- [ ] 4.2 Implementar `calculate_weaknesses(types: list[str]) -> dict[str, float]` usando `type_chart.json`: multiplicadores correctos para tipos duales (inmunidades, dobles debilidades)
- [ ] 4.3 Tests: Garchomp (legal, tipo dual), Mewtwo (ilegal), nombre inválido, Pokémon Paradox (baneado)

## 5. synergy-engine service

- [ ] 5.1 Crear `pokemon_team_builder/services/synergy_engine.py`: función `assign_role(pokemon: PokemonData) -> list[Role]` con la lógica de stats y moveset del spec (sweeper, wall, lead, trick room, redirect)
- [ ] 5.2 Implementar `analyze_coverage(team: list[PokemonData]) -> CoverageReport`: huecos ofensivos (tipos sin STAB/move) y vulnerabilidades defensivas compartidas (≥3 miembros con debilidad ×2+)
- [ ] 5.3 Implementar `detect_role_gaps(team: list[PokemonData]) -> list[Role]`: roles ausentes; detectar estrategia Trick Room si hay setter + ≥2 Pokémon lentos
- [ ] 5.4 Implementar `score_flexibility(team: list[PokemonData]) -> int`: evalúa número de combinaciones de 4 viables para Pick-4-de-6
- [ ] 5.5 Tests: equipo sin soporte, equipo Trick Room, equipo con doble debilidad crítica, equipo equilibrado

## 6. team-generator service

- [ ] 6.1 Crear `pokemon_team_builder/services/team_generator.py`: fase 1 — filtrado heurístico (descarta tipos redundantes y candidatos sin cobertura útil), reduce pool a ~30–50 candidatos
- [ ] 6.2 Implementar fase 2 — beam search (k=10): construye equipo slot a slot maximizando score de cobertura incremental; aplica Species Clause e Item Clause
- [ ] 6.3 Implementar `suggest_sp_distribution(pokemon: PokemonData, role: Role) -> SPDistribution` usando plantillas de `role_sp_templates.json`; total MUST ser ≤ 66, ninguna stat > 32
- [ ] 6.4 Integrar fase 3 — re-ranking con viability-rater; retornar top 3 variantes distintas
- [ ] 6.5 Tests: Garchomp como ancla → equipo legal, sin duplicados de Pokémon ni ítem; SP totales ≤ 66

## 7. viability-rater service

- [ ] 7.1 Crear `pokemon_team_builder/services/viability_rater.py`: función `score_team(variant: TeamVariant) -> ViabilityScore` con los 4 componentes (cobertura 35pts, roles 35pts, SPs 15pts, ítems 15pts)
- [ ] 7.2 Implementar generación de explicación textual en español con Rich: puntos fuertes y débiles concretos
- [ ] 7.3 Implementar `rank_variants(variants: list[TeamVariant]) -> list[TeamVariant]`: ordena por score, marca la primera como "Recomendado"
- [ ] 7.4 Tests: equipo equilibrado → score ≥ 75; equipo sin soporte + 4 debilidades compartidas → score < 50

## 8. replica-exporter service

- [ ] 8.1 Crear `pokemon_team_builder/services/replica_exporter.py`: función `to_pokepaste(variant: TeamVariant) -> str` — formato Showdown estándar con `Level: 50`, `EVs:` convertidos (SP × 8), sin `IVs:`, 4 moves por Pokémon
- [ ] 8.2 Implementar selección de moves genéricos por rol: Protect en slot 1 + 3 moves del moveset real (PokéAPI) según prioridad de rol; fallback a STAB más potente si el move genérico no está disponible
- [ ] 8.3 Implementar `save_to_file(content: str, path: Path, force: bool)`: pide confirmación si el archivo existe y `force=False`
- [ ] 8.4 Implementar bloque de instrucciones de importación (texto fijo con URL de PikaChampions y pasos)
- [ ] 8.5 Tests: SP → EVs correctos (32 SPs = 256 EVs); Protect en slot 1; fallback de moves si el genérico no está en moveset

## 9. CLI (`poke-builder`)

- [ ] 9.1 Crear `pokemon_team_builder/cli/main.py` con grupo Click `poke-builder` y comando `build <pokemon>` con flags: `--variants N` (default 3), `--output FILE`, `--force`, `--json`
- [ ] 9.2 Implementar flujo completo de `build`: lookup → synergy → generate → rate → display con Rich (tabla de equipo + score + explicación) → export si `--output`
- [ ] 9.3 Crear comando `poke-builder check <pokemon>`: muestra datos del Pokémon, legalidad, debilidades y roles asignados (útil para explorar antes de hacer un equipo)
- [ ] 9.4 Manejo de errores en CLI: Pokémon ilegal, PokéAPI no disponible, regulación expirada — mensajes con Rich en rojo, exit code 1
- [ ] 9.5 Tests de integración: `poke-builder build charizard` end-to-end con PokéAPI mockeada; verificar output PokePaste válido

## 10. Documentación y entrega

- [ ] 10.1 Escribir `README.md`: instalación (`uv pip install -e .`), uso básico (`poke-builder build <pokemon>`), descripción del formato de export y enlace a PikaChampions
- [ ] 10.2 Verificar round-trip: exportar equipo generado → importar manualmente en PikaChampions/ChampTeams.gg → confirmar que carga sin errores
- [ ] 10.3 Commit final en rama `feat/initial-implementation` y push a `Janisher-Illderment/pokemon-team-builder`
