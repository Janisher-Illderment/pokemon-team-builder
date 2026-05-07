## Context

`team_generator.py` asigna objetos a los Pokémon en tres puntos:
- `_DEFAULT_ITEM_BY_ROLE`: item preferido por rol (7 entradas)
- `_FALLBACK_ITEM`: usado cuando el item por rol ya está tomado
- `_BACKUP_ITEMS`: pool de 30 items de relleno para garantizar el Item Clause

Pokémon Champions tiene un pool limitado de ~117 items (según MetaVGC) — un subconjunto muy pequeño comparado con los juegos principales. Serebii confirma 30 items en su lista básica. Items como Choice Band, Choice Specs, Assault Vest, Life Orb y Eject Button **no existen** en el juego. PikaChampions / ChampTeams.gg fallan silenciosamente al importar un Pokémon con un item desconocido.

La investigación mediante Inte (agente de research) aportará la lista canónica antes de implementar.

## Goals / Non-Goals

**Goals:**
- `_DEFAULT_ITEM_BY_ROLE`, `_FALLBACK_ITEM` y `_BACKUP_ITEMS` solo contienen items Champions-legales
- El pool de backup es suficientemente grande para garantizar el Item Clause (6 items distintos sin repetir) incluso cuando 6 Pokémon del mismo rol ocupan los slots
- Items asignados por rol tienen sentido competitivo en Doubles (no solo ser "legales", sino útiles)

**Non-Goals:**
- Modelar Mega Stones (gestionados por una mecánica aparte en Champions)
- Optimizar sets específicos por Pokémon (eso es trabajo del experto, no del generador)
- Cambiar la lógica de asignación (Item Clause, fallback chain) — solo los datos

## Decisions

**Decisión 1: Fuente de verdad para items = Serebii + investigación Inte**
- Serebii (serebii.net/pokemonchampions/items.shtml) es la fuente más fiable ya verificada
- MetaVGC indica 117 totales — Inte investigará para completar la lista
- Alternativa descartada: asumir lista completa de mainline — demasiado riesgo de incluir items inexistentes

**Decisión 2: Mantener la estructura de tres constantes en team_generator.py**
- `_DEFAULT_ITEM_BY_ROLE`: máximo impacto competitivo por rol
- `_FALLBACK_ITEM`: item genérico neutro que funciona en cualquier rol
- `_BACKUP_ITEMS`: pool ordenado por utilidad competitiva decreciente
- Alternativa descartada: fichero JSON externo — overkill para una lista fija de <120 items

**Decisión 3: Asignaciones por rol basadas en la mecánica real de Champions**
- physical_sweeper → Weakness Policy (se activa con el aliado en doubles)
- special_sweeper → Throat Spray (potencia sound moves) o Scope Lens
- physical_wall → Rocky Helmet (confirmado en Champions)
- special_wall → Leftovers (confirmado en Champions)
- lead_support → Focus Sash (confirmado en Champions)
- trick_room_setter → Mental Herb (confirmado en Champions)
- redirect → Clear Amulet o Shell Bell

## Risks / Trade-offs

- [Riesgo] Lista de Serebii podría estar incompleta (30 items << 117) → Mitigación: Inte investiga fuentes adicionales; la spec define que solo se incluyen items *verificados*
- [Riesgo] Items de berries resistencia (Occa Berry, Passho Berry…) podrían ser legales pero tienen valor situacional → Mitigación: incluirlos en `_BACKUP_ITEMS` ordenados al final
- [Trade-off] Pool más pequeño significa menos variedad en teams con muchos Pokémon del mismo rol → Aceptable: es consecuencia de las reglas del juego, no un bug del tool
