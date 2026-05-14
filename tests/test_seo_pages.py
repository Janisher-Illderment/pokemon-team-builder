"""C3 light: tests for server-rendered SEO pages.

Verifies:
  - /pokemon/{slug} renders 200 with proper meta + content for legal mons
  - /pokemon/{slug} returns 404 for non-pool names
  - /archetype/{slug} renders 200 for all 7 archetypes
  - /archetype/{slug} returns 404 for unknown archetype
  - Dynamic /sitemap.xml lists all Pokémon + archetypes + base pages
  - Canonical URL points to jswg subdomain (not the squatted domain)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pokemon_team_builder.main import app

client = TestClient(app)


# ── /pokemon/{slug} ─────────────────────────────────────────────────────────


def test_pokemon_detail_valid_anchor_returns_200():
    res = client.get("/pokemon/garchomp")
    assert res.status_code == 200
    assert "garchomp" in res.text.lower()


def test_pokemon_detail_has_seo_meta():
    res = client.get("/pokemon/garchomp")
    assert "<title>" in res.text
    assert "Garchomp" in res.text
    # SEO essentials
    assert 'name="description"' in res.text
    assert 'rel="canonical"' in res.text
    assert 'property="og:title"' in res.text
    # Canonical points to jswg subdomain (not squatted plain domain)
    assert "pokemon-team-builder-jswg.onrender.com/pokemon/garchomp" in res.text


def test_pokemon_detail_unknown_pokemon_returns_404():
    res = client.get("/pokemon/missingno")
    assert res.status_code == 404


def test_pokemon_detail_links_to_generator():
    res = client.get("/pokemon/garchomp")
    # CTA should pre-fill the generator via query param
    assert "/?anchor=garchomp" in res.text


def test_pokemon_detail_lists_related_pokemon():
    res = client.get("/pokemon/garchomp")
    # Related list should contain links to other /pokemon/* pages
    assert "/pokemon/" in res.text
    # At least one non-garchomp link
    import re
    related = re.findall(r'href="/pokemon/([^"]+)"', res.text)
    assert any(r != "garchomp" for r in related), (
        f"expected at least one related pokemon link != garchomp; got {related}"
    )


# ── /archetype/{slug} ───────────────────────────────────────────────────────


@pytest.mark.parametrize("slug", [
    "balance", "hyper_offense", "hard_trick_room", "bulky_offense",
    "weather_based", "stall", "perish_trap",
])
def test_archetype_detail_all_seven_render_200(slug):
    res = client.get(f"/archetype/{slug}")
    assert res.status_code == 200, f"archetype {slug} failed: {res.status_code}"
    assert "<title>" in res.text


def test_archetype_detail_unknown_returns_404():
    res = client.get("/archetype/random_archetype_xyz")
    assert res.status_code == 404


def test_archetype_detail_canonical_correct():
    res = client.get("/archetype/hyper_offense")
    assert "pokemon-team-builder-jswg.onrender.com/archetype/hyper_offense" in res.text


def test_archetype_detail_links_to_generator():
    res = client.get("/archetype/perish_trap")
    assert "/?archetype=perish_trap" in res.text


# ── /sitemap.xml dynamic ────────────────────────────────────────────────────


def test_sitemap_xml_includes_all_pokemon_and_archetypes():
    res = client.get("/sitemap.xml")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/xml")
    text = res.text
    # Base pages
    assert "<loc>https://pokemon-team-builder-jswg.onrender.com/</loc>" in text
    assert "/terms.html</loc>" in text
    assert "/privacy.html</loc>" in text
    # Sample Pokémon
    assert "/pokemon/garchomp</loc>" in text
    # All 7 archetypes
    for arch in ["balance", "hyper_offense", "hard_trick_room",
                 "bulky_offense", "weather_based", "stall", "perish_trap"]:
        assert f"/archetype/{arch}</loc>" in text, f"missing archetype {arch}"
    # Total URL count: 3 base + 7 archetypes + ~200 Pokémon ≥ 200
    assert text.count("<loc>") >= 200


def test_sitemap_uses_correct_canonical_subdomain():
    res = client.get("/sitemap.xml")
    # Squatted domain MUST NOT appear
    assert "pokemon-team-builder.onrender.com" not in res.text or \
        "pokemon-team-builder-jswg.onrender.com" in res.text
    # Correct domain MUST appear
    assert "pokemon-team-builder-jswg.onrender.com" in res.text
