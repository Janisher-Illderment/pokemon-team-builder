## Context

`fix-role-balance` dejó un bug activo: `replica_exporter.select_moves_for_role` usa `pokemon.abilities[0]` para buscar overrides, pero PokeAPI ordena abilities como [ability1, ability2, hidden] — la ability competitiva puede estar en cualquier índice. Los weather setters más importantes (Ninetales-A, Pelipper, Politoed, Torkoal, Machamp) tienen su ability relevante en índice 1 o 2. En `synergy_engine`, la gate `spe >= 90` unificada bloquea a Incineroar (spe=60) aunque tenga Fake Out, y Prankster nunca activa `lead_support`.

## Goals / Non-Goals

**Goals:**
- STAB override funciona para todos los Pokémon con ability en cualquier índice
- Incineroar y otros Fake Out lentos → `lead_support`
- Whimsicott, Klefki (Prankster) → `lead_support`
- Machamp → Dynamic Punch con No Guard
- Pelipper → Hurricane con Drizzle
- Aurorus y Vanilluxe NO clasificados como weather setters cuando su primary es refrigerate/ice-body

**Non-Goals:**
- Soporte para Mega abilities (se manejan en assign_role_with_mega)
- Detección de abilities hidden que no sean weather/prankster
- Cambios en modelos, CLI ni formato PokePaste

## Decisions

**D1 — Iterar abilities en orden para STAB override (no any() ni dict lookup)**
El loop para en la primera ability que tenga una entrada en `_ABILITY_STAB_OVERRIDES`. Esto preserva la semántica "primera ability que aplica" sin necesitar un mapping especie→ability.
Alternativa rechazada: `any()` — no devuelve la ability concreta, necesitaría un segundo pass para obtener el override dict.

**D2 — Gate de velocidad solo para Tailwind; no para moves de prioridad**
`_LEAD_SUPPORT_MARKERS` se divide en:
- `_TAILWIND_MARKERS = ("tailwind",)` → requiere `spe >= 90`
- `_PRIORITY_SUPPORT_MARKERS = ("fake-out", "follow-me", "rage-powder")` → sin gate
Alternativa rechazada: bajar el umbral a 60 — afectaría Pokémon que simplemente aprendieron Tailwind pero no lo usan como rol principal.

**D3 — Rename + add prankster a _AUTO_LEAD_ABILITIES**
El rename de `_WEATHER_SETTER_ABILITIES` a `_AUTO_LEAD_ABILITIES` hace explícito que el set cubre más que clima.
La detección de este set usa `abilities[0]` para evitar falsos positivos (Aurorus/Vanilluxe).
Excepción vía `_COMPETITIVE_WEATHER_SPECIES`: whitelist de 4 species donde la weather ability es secundaria en PokeAPI pero primaria en uso competitivo.

**D4 — dynamic-punch al final de _STAB_BY_TYPE["fighting"], override no-guard**
Al final del STAB list significa que sin No Guard nunca se elige (close-combat, drain-punch, etc. vienen antes). El override lo eleva a primera opción cuando No Guard está activo.

## Risks / Trade-offs

- [Whitelist _COMPETITIVE_WEATHER_SPECIES] Requiere mantenimiento manual si se añaden nuevas species. → Mitigado: lista pequeña (4 mons), los weather setters son estables en Champions.
- [Prankster en _AUTO_LEAD_ABILITIES] Sableye y Liepard tienen prankster como hidden ability (índice 2). Con check abilities[0] no los afecta. Correcto: Sableye competitivo suele no ser lead.
- [dynamic-punch al final] Si en el futuro se añade un Fighting-type sin No Guard cuyo mejor move es dynamic-punch (imposible por definición), se elegiría por fallback. Aceptable.

## Open Questions

*(ninguna)*
