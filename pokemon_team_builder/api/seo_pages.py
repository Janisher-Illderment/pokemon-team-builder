"""C3-light: server-rendered SEO pages for /pokemon/{slug} and /archetype/{slug}.

Each route renders a Jinja2 template with real data from the existing
loaders (legal pool, archetype weights, synergy roles). Pages are
indexable by search engines without JS execution — opposite of the home
SPA which is Alpine.js-rendered.

Why this exists (Phase 5+ SEO push):
  - Home `/` is a single page that Google indexes once.
  - These pages expose ~210 long-tail URLs (200 Pokémon + 7 archetypes)
    each with focused content + meta + Schema.org markup.
  - All pages link back to the home generator pre-filled via query
    params (`?anchor=garchomp` or `?archetype=hyper_offense`).

Routing precedence: this router is included BEFORE the StaticFiles
mount in main.py so `/pokemon/{name}` is captured here instead of
matching the static fallback handler.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from pokemon_team_builder.data.archetype_weights_loader import (
    get_weights,
    known_archetypes,
)
from pokemon_team_builder.data.legal_pool_loader import get_all_names, is_legal
from pokemon_team_builder.services import pokemon_lookup
from pokemon_team_builder.services.synergy_engine import assign_role


_TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "web", "templates"
)
templates = Jinja2Templates(directory=_TEMPLATES_DIR)

seo_router = APIRouter()


# ── Archetype meta — labels + descriptions for SEO copy ──────────────────────
@dataclass(frozen=True)
class ArchetypeMeta:
    slug: str
    label: str
    lead: str
    description: str
    examples: str


_ARCHETYPE_META: dict[str, ArchetypeMeta] = {
    "balance": ArchetypeMeta(
        slug="balance",
        label="Balance",
        lead="El arquetipo por defecto: equipos versátiles sin sesgo extremo hacia ofensa o defensa.",
        description=(
            "Balance es el punto medio del scoring competitivo. Combina cobertura "
            "de tipos, roles complementarios, y nature/EV spreads sensatos sin "
            "comprometerse con una sola win-condition. Útil cuando aún no sabes "
            "qué estrategia quieres explorar o quieres un equipo que se adapta "
            "a distintos matchups."
        ),
        examples=(
            "Garchomp + Rotom-Wash + Heatran + Tornadus-Therian + Tapu Fini + Ferrothorn — "
            "un pivote físico, un Volt-Switch, un Earth Power user, momentum, defensa "
            "especial, y un anti-water. Sin cheese, sin extremos."
        ),
    ),
    "hyper_offense": ArchetypeMeta(
        slug="hyper_offense",
        label="Hiperofensivo",
        lead="Equipos full ofensivos: momentum + presión + cambios rápidos. Cheese permitido.",
        description=(
            "Hyper Offense busca eliminar al rival antes de que pueda establecer "
            "su estrategia. Prioriza Pokémon con stats ofensivas altas, moves de "
            "momentum (U-turn, Volt Switch), Tailwind como speed control, e items "
            "agresivos (Choice Band/Specs/Scarf, Focus Sash en leads). El scoring "
            "permite duplicar roles ofensivos y mantiene cheese moves disponibles."
        ),
        examples=(
            "Tornadus-T (Bleakwind Storm + U-turn) + Urshifu-S (Wicked Blow) + "
            "Tapu Koko (Volt Switch) + Garchomp + Calyrex-Shadow + Whimsicott (Tailwind)."
        ),
    ),
    "hard_trick_room": ArchetypeMeta(
        slug="hard_trick_room",
        label="Trick Room duro",
        lead="Invierte velocidad con Trick Room y juega a favor del orden inverso 5 turnos.",
        description=(
            "Hard Trick Room construye alrededor de un setter (Indeedee-F, Porygon2, "
            "Hatterene, Dusclops) que activa Trick Room turno 1 para invertir el "
            "orden de velocidad. Los atacantes son lentos pero pegan fuerte. "
            "El scoring premia setters confiables (Prankster, Mental Herb), "
            "atacantes con Spe baja (<60), y reduce penalización por Pokémon poco veloces."
        ),
        examples=(
            "Indeedee-F (Psychic Surge + Trick Room) + Ursaluna (Atk 140, Spe 50) + "
            "Hatterene (Magic Bounce + Trick Room) + Glastrier + Rillaboom + Amoonguss."
        ),
    ),
    "bulky_offense": ArchetypeMeta(
        slug="bulky_offense",
        label="Ofensivo Bulky",
        lead="Mezcla ofensiva con tankiness: sweepers con bulk decente, walls con presencia ofensiva.",
        description=(
            "Bulky Offense es el balance entre Hyper Offense y Balance. Premia "
            "Pokémon con HP/Def/SpD razonables que aún pueden ofrecer presión "
            "ofensiva. EV spreads suelen tener inversión defensiva además de "
            "ataque/velocidad. Cheese moves bloqueados."
        ),
        examples=(
            "Landorus-T (Intimidate + Earthquake) + Heatran (Air Balloon + Magma Storm) + "
            "Tapu Fini (Calm Mind + Moonblast) + Amoonguss + Rillaboom + Garchomp."
        ),
    ),
    "weather_based": ArchetypeMeta(
        slug="weather_based",
        label="Weather",
        lead="Equipos construidos alrededor de un clima: Sol, Lluvia, Arena, Nieve.",
        description=(
            "Weather Based amplifica el componente weather_synergy ×1.8. Un Pokémon "
            "settea el clima (Torkoal/Drought, Pelipper/Drizzle, Tyranitar/Sand Stream, "
            "Ninetales-Alola/Snow Warning) y los compañeros explotan habilidades "
            "weather-dependent (Chlorophyll, Swift Swim, Sand Rush, Slush Rush). "
            "Sinergias de tipo + clima son centrales: Hurricane en Rain, Solar Beam "
            "en Sun, Blizzard 100% acc en Snow."
        ),
        examples=(
            "Excadrill (Sand Rush) + Tyranitar (Sand Stream) + Garchomp + Ferrothorn + "
            "Tapu Lele + Toxapex — sand sweeper core con apoyo defensivo."
        ),
    ),
    "stall": ArchetypeMeta(
        slug="stall",
        label="Stall",
        lead="Equipos defensivos extremos: el muro aguanta y gana por residual damage.",
        description=(
            "Stall es raro en Doubles pero válido para metas lentos. Premia Pokémon "
            "con HP/Def/SpD muy altos, recovery moves (Recover, Slack Off, Roost), "
            "status conditions (Will-O-Wisp, Toxic), y phazing (Whirlwind, Roar). "
            "Speed control penalty exento — stall no necesita velocidad. "
            "weather_synergy = 0 (no aplica)."
        ),
        examples=(
            "Toxapex (Regenerator + Toxic) + Blissey (Soft-Boiled) + Skarmory + "
            "Clefable (Magic Guard + Moonblast) + Reuniclus (Magic Guard) + Dondozo."
        ),
    ),
    "perish_trap": ArchetypeMeta(
        slug="perish_trap",
        label="Perish Trap",
        lead="Atrapa al rival con Shadow Tag + Perish Song para forzar KO sin atacar.",
        description=(
            "Perish Trap es una estrategia técnica que combina Mega-Gengar (Shadow Tag) "
            "con un setter de Perish Song. El rival no puede cambiar y muere en 3 turnos. "
            "El arquetipo es el único que tiene cheese_allowance ≥ 1.0 con carta cerrada, "
            "permitiendo Perish Song en moveset. Con carta abierta el cheese se gates "
            "(el rival ve el equipo y juega alrededor)."
        ),
        examples=(
            "Mega-Gengar (Shadow Tag + Perish Song + Hypnosis) + Whimsicott (Encore + "
            "Tailwind + Substitute) + Tapu Fini (Misty Surge anti-status) + "
            "support core defensivo."
        ),
    ),
}


# ── /pokemon/{name} ──────────────────────────────────────────────────────────


def _suggested_roles(pokemon) -> list[str]:  # noqa: ANN001
    """Compute suggested roles for the Pokémon (best-effort)."""
    try:
        return assign_role(pokemon)
    except Exception:
        return []


def _weakness_buckets(weaknesses: dict[str, float]) -> tuple[list[str], list[str]]:
    """Split weaknesses dict into (4x, 2x) lists, sorted alphabetically."""
    fourx = sorted([t for t, mult in weaknesses.items() if mult >= 4.0])
    twox = sorted([t for t, mult in weaknesses.items() if 2.0 <= mult < 4.0])
    return fourx, twox


def _related_pokemon(slug: str, limit: int = 8) -> list[str]:
    """Return up to ``limit`` other legal pool names (alphabetical neighbors)."""
    all_names = sorted(get_all_names())
    if slug not in all_names:
        return all_names[:limit]
    idx = all_names.index(slug)
    # Take a slice centered on the slug — wraps if near edges.
    start = max(0, idx - limit // 2)
    end = min(len(all_names), start + limit + 1)
    neighbors = [n for n in all_names[start:end] if n != slug]
    return neighbors[:limit]


@seo_router.get("/pokemon/{name}", response_class=HTMLResponse)
def pokemon_detail(name: str, request: Request) -> Any:
    """Render the /pokemon/{slug} SEO landing page."""
    slug = name.strip().lower()
    if not is_legal(slug):
        raise HTTPException(
            status_code=404,
            detail=f"'{name}' is not in the Champions M-A regulation pool.",
        )
    try:
        pokemon = pokemon_lookup.lookup(slug)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    fourx, twox = _weakness_buckets(pokemon.weaknesses)
    bs = pokemon.base_stats
    bst = bs.hp + bs.atk + bs.def_ + bs.spa + bs.spd + bs.spe

    return templates.TemplateResponse(
        request,
        "pokemon_detail.html",
        {
            "pokemon": {
                "slug": slug,
                "display_name": slug.replace("-", " ").title(),
                "types": pokemon.types,
                "base_stats": {
                    "hp": bs.hp, "atk": bs.atk, "def_": bs.def_,
                    "spa": bs.spa, "spd": bs.spd, "spe": bs.spe,
                },
                "bst": bst,
                "weaknesses_4x": fourx,
                "weaknesses_2x": twox,
                "suggested_roles": _suggested_roles(pokemon),
            },
            "related_pokemon": _related_pokemon(slug),
            "archetypes": list(known_archetypes()),
        },
    )


# ── /archetype/{name} ────────────────────────────────────────────────────────


# ── Dynamic sitemap.xml (overrides static) ──────────────────────────────────

_SITE_BASE = "https://pokemon-team-builder-jswg.onrender.com"


@seo_router.get("/sitemap.xml", response_class=Response)
def sitemap() -> Response:
    """Dynamic sitemap covering / + legal pages + SEO landing pages.

    Includes every legal pool Pokémon (~200) and every archetype (7),
    so search engines can crawl all long-tail URLs. Overrides the static
    sitemap.xml shipped in /static/ because this router is registered
    before the StaticFiles mount.
    """
    today = "2026-05-14"  # last regeneration date
    urls: list[tuple[str, str, str, str]] = [
        ("/", today, "weekly", "1.0"),
        ("/terms.html", today, "monthly", "0.3"),
        ("/privacy.html", today, "monthly", "0.3"),
    ]
    # /pokemon/{slug} for every legal pool member
    for name in sorted(get_all_names()):
        urls.append((f"/pokemon/{name}", today, "monthly", "0.6"))
    # /archetype/{slug} for every known archetype
    for slug in sorted(_ARCHETYPE_META):
        urls.append((f"/archetype/{slug}", today, "monthly", "0.7"))

    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, lastmod, freq, prio in urls:
        parts.append(
            f"  <url>\n"
            f"    <loc>{_SITE_BASE}{path}</loc>\n"
            f"    <lastmod>{lastmod}</lastmod>\n"
            f"    <changefreq>{freq}</changefreq>\n"
            f"    <priority>{prio}</priority>\n"
            f"  </url>"
        )
    parts.append("</urlset>")
    return Response(content="\n".join(parts), media_type="application/xml")


@seo_router.get("/archetype/{name}", response_class=HTMLResponse)
def archetype_detail(name: str, request: Request) -> Any:
    """Render the /archetype/{slug} SEO landing page."""
    slug = name.strip().lower()
    if slug not in _ARCHETYPE_META:
        raise HTTPException(
            status_code=404,
            detail=f"'{name}' is not a known archetype. Valid: {sorted(_ARCHETYPE_META)}.",
        )

    meta = _ARCHETYPE_META[slug]
    weights = get_weights(slug)
    other = [m for s, m in _ARCHETYPE_META.items() if s != slug]

    return templates.TemplateResponse(
        request,
        "archetype_detail.html",
        {
            "archetype": {
                "slug": meta.slug,
                "label": meta.label,
                "lead": meta.lead,
                "description": meta.description,
                "examples": meta.examples,
                "weights": {
                    "coverage": weights.coverage,
                    "roles": weights.roles,
                    "sp": weights.sp,
                    "items": weights.items,
                    "speed": weights.speed,
                    "bulk": weights.bulk,
                    "weather_synergy": weights.weather_synergy,
                    "cheese_allowance": weights.cheese_allowance,
                },
            },
            "other_archetypes": [{"slug": m.slug, "label": m.label} for m in other],
        },
    )
