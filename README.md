# pokemon-team-builder

> **Champions VGC Doubles team builder · Regulation M-A · v0.11.0**

Generador de equipos competitivos para **Pokémon Champions** (formato Doubles, Regulation M-A). Web app + CLI. Construye equipos alrededor de tu Pokémon favorito con archetype selector, weather synergy, EV presets y análisis de matchups.

**🌐 Live:** [pokemon-team-builder-jswg.onrender.com](https://pokemon-team-builder-jswg.onrender.com/)
**📦 GitHub:** [Janisher-Illderment/pokemon-team-builder](https://github.com/Janisher-Illderment/pokemon-team-builder)

> ⚠️ **Fan-made tool.** Pokémon y todos los nombres/marcas son © Nintendo / Game Freak / The Pokémon Company. Esta herramienta NO está afiliada ni respaldada por ellos.

---

## ✨ Features (v0.10.0)

### Nuevo en v0.10.0

- **🎴 Toggle Carta abierta/cerrada** independiente de Bo1/Bo3. Auto-resuelve (Bo3 = abierta, Bo1 = cerrada) o override manual. Cheese moves bloqueados en carta abierta (multiplicador 0.5) incluso en `perish_trap`.
- **🔍 Páginas SEO server-rendered**: `/pokemon/{slug}` y `/archetype/{slug}` (~210 URLs indexables). Cada página renderiza datos competitivos + Schema.org JSON-LD + CTA al generador pre-filled.
- **🔗 Loop SEO cerrado**: home lee `?anchor=` `?archetype=` `?format=` `?team_sheet=` y pre-rellena form. Sección "Explora" en home con 7 archetypes + 12 Pokémon populares.
- **🔤 Autocomplete nativo** en input de anchor (HTML5 datalist con 201 nombres legales).
- **🧹 Backlog técnico 100% resuelto** (11 items Tecle DEFER cerrados: `_MOVE_TYPE` extraído, weather setter validation strict, mega-only flag respected, meta_service pre-fetch, `_partial_score` archetype-aware, ADRs documentados).

### Core generation

- **Favorite-first 4-phase flow**: anchor → core duo → shared-weakness slot 3 → beam search slots 4-6 (determinístico por anchor+archetype+format+mega)
- **7 strategy archetypes**: hyper_offense · hard_trick_room · bulky_offense · weather_based · stall · balance · perish_trap
- **Weather synergy scoring**: +3 puntos por ability-setter pairs (Excadrill+Tyranitar), +2 por sinergias pasivas
- **Speed control enforcement**: −15 score penalty si no hay control velocidad (Tailwind, Trick Room, Icy Wind, Thunder Wave, Sticky Web, etc.). Stall exento.
- **EV presets Champions**: 66 SP cap / 32 max per stat. Dos presets por miembro (offensive/defensive), item-aware (Choice Band → invierte menos atk, más speed), nature-jump detection.
- **Coverage STAB-based**: un tipo está cubierto SII algún miembro lleva move de ese tipo Y le es STAB (no solo por typing).
- **Role gradient ±15**: thresholds suaves en lugar de cliffs. Pokémon "casi-muros" reciben peso parcial.
- **Ability como rol implícito**: Flame Body / Intimidate / Multiscale / etc. bump role weights.
- **Mega Clause hard prune**: ≤1 mega stone holder por equipo, garantizado pre-scoring.

### Champions data (Regulation M-A)

- **201 entradas pool legal** (188 especies + 13 formas regionales) — Champions Reg M-A hasta 2026-06-17
- **69 items legales** verificados (Pokéxperto cross-check). Sin Weakness Policy / Throat Spray / Rocky Helmet / Life Orb / Assault Vest (NO disponibles M-A).
- **18 type-resist berries** (Chilan, Occa, Passho, etc.)
- **59 mega evolutions** modeladas
- **Item Clause**: hard rejection de equipos con items duplicados

### Web UI

- Selector archetype + format (Bo1/Bo3) + variants
- Preset toggle por miembro (Ofensivo / Defensivo)
- Speed control warning banner cuando aplica
- "Núcleo flex" badge en Bo3 (renamed from "Lead" pre-v0.10.0)
- Top Teams del Meta (LabMaus integration)
- Torneos Próximos (geolocation + Leaflet map)
- Import/Export PokePaste
- Editor inline de miembros (move swap, item swap, pokemon swap)
- Matchup analyzer vs threat específico
- LocalStorage: guarda hasta 20 equipos con nombre + color

### Legal + monetización (Phase 5)

- Footer disclaimer trademark fan-made
- `/terms.html` Términos de uso (ley española + EU)
- `/privacy.html` Privacy Policy GDPR + LSSI-CE compliant
- Cookie banner consentimiento (accept/reject)
- SEO: meta tags, Open Graph, Twitter Cards, Schema.org JSON-LD
- `/sitemap.xml` + `/robots.txt`
- Buy Me a Coffee button (placeholder — pending user account setup)
- AdSense slots (placeholder — pending account approval)

---

## 🚀 Quick start

### Web app (recomendado)

Visita [pokemon-team-builder-jswg.onrender.com](https://pokemon-team-builder-jswg.onrender.com/) — sin instalación.

### CLI local

```bash
# Instalación
pip install git+https://github.com/Janisher-Illderment/pokemon-team-builder.git

# Build a team
poke-builder build garchomp

# Más variantes + output a file
poke-builder build garchomp --variants 5 --output team.txt

# Inspect a Pokémon
poke-builder check garchomp

# JSON output
poke-builder build dragapult --json
```

### Self-host

```bash
git clone https://github.com/Janisher-Illderment/pokemon-team-builder.git
cd pokemon-team-builder
pip install -e ".[dev,web]"

# Run web server
uv run uvicorn pokemon_team_builder.main:app --reload

# Run CLI
poke-builder build charizard
```

### Docker

```bash
docker build -t pokemon-team-builder .
docker run -p 8000:8000 pokemon-team-builder
```

---

## 📥 Importing into Champions

1. Genera equipo: `poke-builder build <anchor> --output team.txt` (o usa web app + Copy Pokepaste)
2. Copia el texto
3. Ve a [pikachampions.com](https://pikachampions.com/) o [champteams.gg](https://champteams.gg/)
4. Paste + **Import Replica Team**
5. Usa el código generado in-game

Format: Showdown PokePaste estándar (`Level: 50`, `EVs:` line en SPs × 8, no `IVs:` line, Protect en slot 1).

---

## 🏗️ Architecture

```
pokemon_team_builder/
├── api/              # FastAPI router + schemas (Pydantic v2)
├── cli/              # Click + Rich
├── data/             # Loaders + versioned JSONs (regulation, data_version)
│   ├── champions_legal_items.json    (69 items)
│   ├── legal_pool_mA.json            (201 entries)
│   ├── mega_evolutions.json          (59 megas)
│   ├── archetype_weights.json        (7 archetypes × 8 weights)
│   ├── weather_dependent_abilities.json
│   ├── weather_setters.json
│   ├── ability_implicit_roles.json
│   └── speed_tiers.json
├── domain/           # PokemonData / TeamMember / TeamVariant dataclasses
├── services/         # Core logic
│   ├── team_generator.py              # 4-phase favorite-first flow
│   ├── favorite_first_builder.py     # build_core_duo + cover_shared_weakness
│   ├── viability_rater.py            # score_team(format, archetype) → 0-100
│   ├── synergy_engine.py             # gradient roles + STAB coverage
│   ├── replica_exporter.py           # PokePaste + move selection + cheese gate
│   ├── sp_preset_builder.py          # 66-SP cap, item-aware presets
│   ├── sp_calc.py                    # final_stat + nature jumps
│   ├── matchup_analyzer.py           # /analyze-matchup endpoint
│   ├── meta_service.py               # MunchStats integration
│   └── ev_explainer.py               # speed tier + bulk explanations
└── web/static/       # SPA: Alpine.js + custom CSS
```

**Stack:** Python 3.11 · FastAPI + uvicorn · Pydantic v2 · Click · Rich · httpx + hishel · pytest + respx · Alpine.js · Leaflet

---

## 🧪 Testing

```bash
# Full suite (463 tests)
uv run pytest

# Specific
uv run pytest tests/test_favorite_first.py -v

# Coverage
uv run pytest --cov
```

**Status:** 463/463 verde · 0 xfail/skip · CI verde en GitHub Actions.

---

## 🔄 BREAKING changes en v0.10.0

Ver [MIGRATION.md](MIGRATION.md) completo. Cambios principales:

- **API field rename**: `VariantOut.lead_flexibility_score` → `core_flexibility_score`
- **Items removed**: Weakness Policy, Throat Spray, Rocky Helmet, Life Orb, Assault Vest (NO en pool M-A)
- **Pokémon Champions SP system**: 66 SP total / 32 max stat (era 508 EVs / 252 max en v0.6.x)
- **Score components Bo1**: coverage(35) + roles(35) + sp(15) + items(15) — Bo3: coverage(30) + core_flex(25) + core_div(15) + sp(15) + items(15) — multiplicado por archetype weights

---

## 📊 OpenSpec changes

Documentación de cambios en `openspec/changes/`:

- `refine-build-logic-v2/` — release v0.10.0 (10 capabilities, 5 NEW + 5 MODIFIED) — MERGED 2026-05-14
- Archivos `archive/` — cambios anteriores

---

## 🛡️ Limitations & disclaimers

- **Move pool**: PokéAPI mainline. Algunos moves pueden no existir en Champions exactamente como listed.
- **Sprites**: hot-linked desde Pokémon Showdown. Branch `feat/sprite-preview` (Option D) disponible como escape hatch — ver `docs/sprite-alternatives.md`.
- **Regulation expiry**: M-A válida hasta **2026-06-17**. Tras esa fecha, regulation M-B requerirá update de pool y weights.
- **Data freshness**: meta data (LabMaus, MunchStats) se cachea con TTL 30 días. Para refresh manual, borrar `~/.pokemon-builder/cache.db`.

---

## 🤝 Contributing

Issues y PRs bienvenidos. Para fixes pequeños: PR directo. Para features: abrir issue primero.

Para reportes de contenido IP (Nintendo / Game Freak / TPC), abrir issue con etiqueta `legal` — cooperación garantizada.

---

## 📄 License

MIT. Ver [LICENSE](LICENSE).

Datos competitivos y nombres de Pokémon son propiedad de sus respectivos titulares. Uso al amparo de uso justo educativo.
