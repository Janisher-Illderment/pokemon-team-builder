# Sprite Alternatives — Cost / Time / UX / Legal Analysis

**Context:** App actualmente hot-linkea sprites de `play.pokemonshowdown.com/sprites/dex/*.png`. Riesgo legal alto al monetizar (sprites son derivative de IP Pokémon) y riesgo técnico (Showdown puede bloquear hotlink). Documento alternativas para migración futura.

**Decision actual (2026-05-14):** mantener Showdown hotlink con disclaimer reforzado. Re-evaluar tras Capa 1 legal + AdSense aprobación.

---

## Comparativa de approaches

| ID | Approach | Coste € | Tiempo | UX vs actual | Legal safety | Maintenance |
|----|----------|---------|--------|--------------|--------------|-------------|
| A | Designer pixel-art manual | 1.500–6.000 | 4–8 semanas | Excelente | 100% | Bajo (sprites estáticos) |
| B | AI generation (Midjourney/SDXL) | 30–80 | 1 semana | Buena | 75–85%* | Medio (regen al añadir mons) |
| C | Asset pack libre (CC0/itch.io) | 0–30 | 1–2 días | Aceptable | 100% | Bajo |
| D | Texto + color por tipo | 0 | 1–2h | Pobre | 100% | Cero |
| E | Procedural generation custom | 0 (dev time) | 8–16h dev | Variable | 100% | Medio (tweaks) |

\* AI puede inadvertidamente reproducir styles copyrightados. Requiere revisión manual sprite-by-sprite.

---

## Detalle por approach

### A — Designer pixel-art manual
- **Scope:** ~200 Pokémon × 1 sprite × 30–60 min/sprite = 100–200h trabajo
- **Tarifas referencia (2026):** freelance pixel-art designer EU/España €15–30/h. Top-tier €40–60/h.
- **Cálculo:** 150h × €20/h = **€3.000** (estimación central)
- **Pros:** estilo coherente, calidad alta, licencia limpia (transfer total al pagar)
- **Cons:** coste alto, tiempo largo, lock-in con un designer
- **Recomendación:** solo si la app escala a revenue >€500/mes y justifica inversión

### B — AI generation (Midjourney / Stable Diffusion XL local)
- **Scope:** generar 200 sprites pixel-monster style + curation
- **Coste:** Midjourney €30/mes × 1 mes + 10h curation manual
- **Local SDXL:** €0 monetario + hardware existente (RTX, M-series Mac) + ~20h trabajo
- **Workflow:**
  1. Prompt template: "pixel art monster, [type:dragon] colors, 64x64, transparent bg, generic creature design, NOT Pokemon"
  2. Generar 5–10 variantes por mon
  3. Revisar cada batch para detectar similitud accidental con Pokémon real (Charizard-like dragon = legal risk)
  4. Seleccionar mejor + post-process (downscale, palette quantize)
- **Pros:** rápido, barato, control sobre estilo
- **Cons:** AI legal landscape en evolución (EU AI Act, sentencias copyright sobre training data). Algunas generaciones pueden parecerse a IP existente — requiere humano que verifique cada sprite.
- **Recomendación:** viable como prototyping; problemático para producción sin revisión legal

### C — Asset pack libre (CC0 / itch.io / OpenGameArt)
- **Fuentes:**
  - [OpenGameArt.org](https://opengameart.org/) — CC0/CC-BY monsters packs
  - [itch.io asset store](https://itch.io/game-assets) — packs €0–30, licencias variadas
  - [Kenney.nl](https://kenney.nl/) — pixel asset packs CC0 referente
- **Workflow:** matchear 200 Pokémon a 200 monsters genéricos del pack por tipo/silueta
- **Coste:** €0–30 (pack) + 6–10h matching
- **Pros:** 100% licencia limpia, rápido
- **Cons:** estilo NO Pokémon, look "indie game" no familiar para el usuario. Riesgo de aspecto bootleg / cutre
- **Recomendación:** mejor coste/safety si UX no-Pokémon es aceptable

### D — Texto + color por tipo
- **Implementación:** CSS card con primera letra del nombre + background gradient color del tipo (Fire = rojo gradient, Water = azul, etc.)
- **Coste:** 1–2h CSS + JS pequeño
- **Pros:** trivial, info clara (tipo + nombre visible), cero IP risk, cero maintenance
- **Cons:** UX muy pobre, "página web 2010"
- **Recomendación:** fallback de emergencia si Showdown bloquea hotlink. Útil como preview rápido en branch experimental

### E — Procedural generation custom
- **Concept:** algoritmo JS/Python que genera sprite 64x64 único por Pokémon basándose en (tipo primario, tipo secundario, BST, role)
- **Approach:** combinar shapes geométricas pre-diseñadas + paleta tipo-based + symmetry rules
- **Coste:** 8–16h desarrollo + tuning iteraciones
- **Pros:** único por Pokémon, escalable a nuevas adiciones automáticamente, cero IP risk
- **Cons:** outcome impredecible visualmente, puede salir feo, requiere iteración
- **Recomendación:** experimento interesante, no para producción primera versión

---

## Recomendación priorizada

**Si app sigue siendo personal / low-traffic:**
- Mantener Showdown sprites + disclaimer fuerte (estado actual)

**Si AdSense aprueba + traffic >5k visitas/mes:**
- Migrar a **B (AI generation)** con curation cuidadosa
- O a **C (asset pack)** si UX no-Pokémon aceptable

**Si app escala a revenue significativo (>€500/mes):**
- Inversión en **A (designer profesional)** justificable
- ROI sobre 6–12 meses

**Si Showdown bloquea hotlink hoy:**
- Fallback inmediato **D (texto + color)** como branch hotfix
- Comprar tiempo para implementar B o C correctamente

---

## Branch experimental

Branch `feat/sprite-preview` implementa Opción **D** (texto + color por tipo) como prototype rápido. Permite evaluar UX sin sprites Showdown.

Acceso:
```bash
git checkout feat/sprite-preview
uv run uvicorn pokemon_team_builder.main:app --reload
```

Vuelta a master:
```bash
git checkout master
```

---

## Riesgo legal — re-evaluación

Documento de referencia para revisión futura. **NO es asesoría legal profesional** — para certeza, consultar abogado IP especializado (€150–300/h).

**Vectores de riesgo (orden severidad):**
1. **C&D Nintendo/TPC** por sprites hot-linked → migración a B/C reduce
2. **Showdown blocking** del hotlink por bandwidth abuse → migración A/B/C/D resuelve
3. **AdSense rechazo** por IP content policy → mitigado por disclaimer + legal pages, no por sprites en sí
4. **GDPR violation** por terceros (sprite host registra IPs) → migración a self-hosted resuelve

**Última actualización:** 2026-05-14.
