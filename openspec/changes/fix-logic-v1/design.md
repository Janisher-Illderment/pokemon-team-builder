## Context

Análisis adversarial de 2026-05-03 (Sola + Tecle) sobre el estado de master post-v0.2.0.
100 tests pasando, pero 18 issues confirmados en la lógica — varios producen output
que PikaChampions rechaza silenciosamente o que daña la viabilidad del equipo en partida.

Este change no toca el beam search, el viability-rater conceptual, ni el filtro de
same-type del heurístico — esos van a v2. Solo arregla bugs confirmados en código.

## Goals / Non-Goals

**Goals:**
- Eliminar todos los casos donde el sistema genera PokePastes inválidos o con moves duplicados
- Natures que reflejen el moveset real generado, no el role label
- Items que tengan sentido con el moveset asignado (no WP+setup, no Choice+support)
- Código muerto eliminado (Life Orb penalty, Loaded Dice)

**Non-Goals:**
- Rediseño del beam search o del scoring de viability (v2)
- Soporte de Mega Evoluciones (spec separado)
- Verificación del item pool contra lista oficial (C1 — depende de confirmación manual del usuario)
- Filtrar Hidden Abilities (Inte confirmó: TODAS las HAs son legales en Champions)

## Decisions

### D1 — Nature derivada de slot-2 STAB, no del role
El role es un proxy del stat dominante — pero el moveset puede disentir (mixed-stat mons,
leads con STAB especial pero rol "lead_support"). La source of truth más cercana a lo que
el usuario verá en juego es el move de slot 2.

Implementación: `select_moves_for_role` ya devuelve los 4 moves. `_build_variant` calcula
la nature DESPUÉS de llamar a `select_moves_for_role`, mirando `_MOVE_CATEGORY[moves[1]]`.
Fallback: si moves[1] no está en `_MOVE_CATEGORY`, se usa el rol como antes.

Casos fijos por design (ignoran el moveset):
- `trick_room_setter`: siempre Sassy (bajo Spe es el objetivo, no el ataque)
- `redirect`: siempre Calm (bulk SpD independientemente del moveset)

### D2 — `_item_is_activatable` refactorizado con tabla declarativa
En lugar de if/elif por item, se introduce `_ITEM_PRECONDITIONS: dict[str, Callable]`
que mapea cada item a un predicado. Esto hace extensible añadir nuevos items sin tocar
el cuerpo de la función.

Estructura:
```python
_ITEM_PRECONDITIONS: dict[str, Callable[[PokemonData, list[str]], bool]] = {
    "Throat Spray": lambda p, moves: bool(frozenset(p.move_names) & _SOUND_MOVES),
    "White Herb": lambda p, moves: any(m in _STAT_DROP_MOVES for m in moves),
    # type-boosters: verificados por tipo del pokemon (sin cambio)
}
```
El segundo argumento `moves` es el moveset generado (no el learnset completo).
Cuando `moves=None` (llamadas sin moveset aún calculado), se usa el learnset como fallback.

### D3 — WP incompatibility via `_ITEM_PRECONDITIONS`
Weakness Policy entra en la tabla con predicado:
```python
"Weakness Policy": lambda p, moves: not any(m in _SETUP_MOVES for m in (moves or []))
```
Si el moveset incluye un setup move, WP es descartado y se pasa al siguiente item.

### D4 — `_fallback_move` propaga error, no retorna duplicado
Cambio mínimo: en el último `return "tackle"`, verificar si "tackle" está en `used`.
Si sí, iterar los genéricos buscando uno libre. Si todos están usados, levantar
`TeamBuildError("No move disponible para este Pokémon — move pool demasiado pequeño")`.
`generate_team` captura el error y filtra ese variant (ya lo hace con `ValueError`).

### D5 — `_format_species` overrides como dict constante
```python
_SPECIES_OVERRIDES: dict[str, str] = {
    "kommo-o": "Kommo-o",
    "ho-oh": "Ho-Oh",     # ya correcto con la lógica genérica pero explícito
    "porygon-z": "Porygon-Z",  # idem
}
```
Se aplica antes del capitalize genérico.

## Risks / Trade-offs

- **Nature desde slot-2**: si slot-2 cae en `_fallback_move` (pool escaso), la nature
  puede ser aún incorrecta. Mitigación: fallback al método viejo (role-based) cuando
  `_MOVE_CATEGORY.get(moves[1])` devuelve vacío.
- **WP incompatibility**: puede hacer que ningún sweeper lleve WP si todos tienen setup
  moves. Mitigación: dejar Weakness Policy disponible como item de fallback cuando
  el moveset no incluye setup.
- **Loaded Dice removal**: reduce la pool de 30 a 29 items de backup. El pool sigue
  siendo suficiente para Item Clause con 6 miembros.
