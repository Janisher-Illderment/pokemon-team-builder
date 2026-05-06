## Context

El generador usa beam search con `_partial_score` para evaluar equipos parciales. La asignación de roles (`assign_role`) determina natures, EVs y movimientos. Tres componentes necesitan corrección coordinada: `synergy_engine.assign_role`, `team_generator._partial_score`, y `replica_exporter.select_moves_for_role`. No hay cambios de modelo, API ni formato de salida.

## Goals / Non-Goals

**Goals:**
- Máximo 2 sweepers puros por equipo generado (beam search despenaliza suportes)
- Pokémon con weather abilities reciben `lead_support` como rol primario
- Snow Warning → Blizzard; Drizzle → Thunder (ability-aware STAB)
- Tests unitarios para los 3 fixes; tests existentes siguen pasando

**Non-Goals:**
- Cambios en modelos de datos, CLI, formato PokePaste, o lógica de viability_rater
- Roles nuevos adicionales (weather_setter no se añade como tipo independiente — se mapea a lead_support)
- Soporte para abilities secundarias (solo la ability primaria influye en la detección)

## Decisions

**D1 — weather_setter → lead_support (no nuevo rol)**
Alternativa: añadir rol `weather_setter` con sus propios templates de EVs, moves, nature.
Elegido lead_support porque: (1) reutiliza templates ya validados (Mental Herb, Focus Sash, nature Calm/Jolly), (2) evita cambios en todos los dict keyed-by-role, (3) los weather setters comparten el objetivo de suporte de los leads (van al frente, no a hacer daño).

**D2 — Penalización en _partial_score (no hard-filter)**
Alternativa: rechazar estados con >2 sweepers en _beam_search directamente.
Elegido penalización porque: permite que el beam search maneje casos degenerados (pool pequeño con pocos suportes) sin crashear — el equipo resultado puede tener 3 sweepers si no hay alternativa, pero no 6.
Penalización: `-(pure_sweeper_count - 2) * 4.0` por cada sweeper extra (ajustable si el balance de la fórmula cambia).

**D3 — _ABILITY_STAB_OVERRIDES post-slot2 (no pre-order)**
Alternativa: reordenar `_STAB_BY_TYPE["ice"]` poniendo blizzard antes.
Rechazado: Blizzard sin Snow Warning tiene 70% accuracy — el orden actual es correcto para mons sin esa ability. El override post-selección es la mínima intervención correcta.
Implementación: después de determinar slot2, si `pokemon.abilities[0]` (ability primaria) está en `_ABILITY_STAB_OVERRIDES` y el move seleccionado está en el mapa de overrides, intentar el move alternativo si existe en el move pool.

## Risks / Trade-offs

- [Penalización ajustable] El valor 4.0 es una heurística. Si el pool tiene ≤3 Pokémon con roles de suporte, el equipo seguirá teniendo 3 sweepers pero no 6. Aceptable para v1. → Mitigation: test con pool pequeño forzado.
- [ability primaria only] Un Pokémon con Snow Warning como ability oculta (hidden) no activa el override. → Mitigation: en Champions el matchmaking revela la ability; los weather setters usan siempre su weather ability.
- [Roles no exclusivos] Weather setters seguirán teniendo roles de sweeper en posición 2+ si sus stats lo dictan (e.g., Tyranitar Atk 134). Esto es correcto — son suportes primarios con capacidad ofensiva.

## Open Questions

*(ninguna — alcance suficientemente acotado)*
