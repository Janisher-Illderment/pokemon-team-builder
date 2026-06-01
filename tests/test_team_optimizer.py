"""Tests del Team Optimizer (ADR docs/adr-team-optimizer.md §7).

Invariantes DUROS pedidos por Sergio (§7):
  - los FIJADOS nunca cambian; la ESPECIE nunca cambia;
  - score_after >= score_before; Σ(deltas) == delta_total;
  - determinismo (misma entrada → misma salida); all-locked = no-op.

Más: equipo ya óptimo no degrada, y el paste de salida re-importa (sin asertar
SP==66 por el artefacto EV→SP del parser, memoria feedback_pokepaste_ev_sp_lossy).

Fixtures: parseamos PokePastes reales de mons del pool legal M-A (mismo estilo
que test_team_rater._REAL_PASTE) para ejercer el camino completo parser→
optimizer→exporter.
"""

from __future__ import annotations

import pytest

from pokemon_team_builder.services import team_optimizer
from pokemon_team_builder.services.pokepaste_parser import parse_pokepaste
from pokemon_team_builder.services.replica_exporter import to_pokepaste


# PokePaste competitivo realista (252/252/4 → ~62 SP tras el //8 del parser).
_PASTE = """Garchomp @ Choice Scarf
Ability: Rough Skin
Level: 50
EVs: 4 HP / 252 Atk / 252 Spe
Jolly Nature
- Protect
- Earthquake
- Dragon Claw
- Rock Slide

Snorlax @ Leftovers
Ability: Thick Fat
Level: 50
EVs: 252 HP / 4 Atk / 252 SpD
Careful Nature
- Body Slam
- Protect
- Curse
- Rest

Gengar @ Black Sludge
Ability: Levitate
Level: 50
EVs: 4 HP / 252 SpA / 252 Spe
Timid Nature
- Shadow Ball
- Sludge Bomb
- Protect
- Icy Wind

Metagross @ Sitrus Berry
Ability: Clear Body
Level: 50
EVs: 252 HP / 252 Atk / 4 Spe
Adamant Nature
- Meteor Mash
- Bullet Punch
- Protect
- Earthquake

Milotic @ Leftovers
Ability: Marvel Scale
Level: 50
EVs: 252 HP / 4 Def / 252 SpA
Modest Nature
- Scald
- Ice Beam
- Recover
- Protect

Dragonite @ Lum Berry
Ability: Multiscale
Level: 50
EVs: 4 HP / 252 Atk / 252 Spe
Adamant Nature
- Dragon Claw
- Earthquake
- Extreme Speed
- Protect
"""


def _variant():
    variant, _ = parse_pokepaste(_PASTE)
    return variant


def _species_fingerprint(m):
    return (
        m.pokemon.name.strip().lower(),
        m.mega_form.mega_stone.strip().lower() if m.mega_form else None,
    )


# ── Invariante: los FIJADOS nunca cambian ────────────────────────────────────

def test_locked_members_never_change():
    """Los bloques PokePaste de los miembros fijados son IDÉNTICOS a los del
    input serializado. Comparamos a nivel de bloque serializado (no re-parseado)
    porque el round-trip EV→SP del parser distorsiona el SP de TODOS los
    miembros por igual (artefacto //8, memoria feedback_pokepaste_ev_sp_lossy);
    lo que el invariante protege es que el optimizador no TOQUE el build fijado,
    no que el parser sea sin pérdidas."""
    variant = _variant()
    locked = [0, 2, 5]
    result = team_optimizer.optimize_team(variant, locked)

    input_blocks = to_pokepaste(variant).split("\n\n")
    after_blocks = result.pokepaste_after.split("\n\n")
    assert len(after_blocks) == 6
    for i in locked:
        assert after_blocks[i] == input_blocks[i], f"el miembro fijado {i} cambió"
    # Ningún cambio aceptado apunta a un índice fijado.
    for c in result.changes:
        assert c.member_index not in locked


# ── Invariante: la ESPECIE (y mega_form) nunca cambia ────────────────────────

def test_species_never_changes():
    variant = _variant()
    result = team_optimizer.optimize_team(variant, [])

    after, _ = parse_pokepaste(result.pokepaste_after)
    assert len(after.members) == 6
    for orig, new in zip(variant.members, after.members):
        assert _species_fingerprint(orig) == _species_fingerprint(new)
    # Ninguna sugerencia es de especie (kinds acotadas).
    for c in result.changes:
        for s in c.suggestions:
            assert s.kind in {"move_swap", "nature", "evs", "item"}


# ── Invariante: score_after >= score_before ──────────────────────────────────

def test_score_after_ge_before():
    variant = _variant()
    for locked in ([], [0], [0, 1, 2], [1, 3, 4]):
        result = team_optimizer.optimize_team(variant, locked)
        assert result.score_after >= result.score_before - team_optimizer.EPSILON, (
            locked, result.score_before, result.score_after
        )


# ── Invariante: Σ(deltas) == delta_total ─────────────────────────────────────

def test_delta_attribution_sums():
    variant = _variant()
    result = team_optimizer.optimize_team(variant, [0])
    total = sum(c.delta for c in result.changes)
    assert abs(total - result.delta_total) < 1e-6
    # delta_total es exactamente score_after - score_before.
    assert abs(
        result.delta_total - (result.score_after - result.score_before)
    ) < 1e-9


def test_all_deltas_non_negative():
    variant = _variant()
    result = team_optimizer.optimize_team(variant, [])
    for c in result.changes:
        assert c.delta >= 0.0


# ── Invariante: determinismo (misma entrada → misma salida) ──────────────────

def test_determinism():
    variant = _variant()
    r1 = team_optimizer.optimize_team(variant, [1, 3])
    r2 = team_optimizer.optimize_team(variant, [1, 3])
    assert r1.pokepaste_after == r2.pokepaste_after
    assert r1.score_after == r2.score_after
    assert [c.member_index for c in r1.changes] == [
        c.member_index for c in r2.changes
    ]
    assert [c.delta for c in r1.changes] == [c.delta for c in r2.changes]


# ── Invariante: all-locked = no-op ───────────────────────────────────────────

def test_all_locked_is_noop():
    variant = _variant()
    result = team_optimizer.optimize_team(variant, [0, 1, 2, 3, 4, 5])
    assert result.changes == []
    assert result.score_after == result.score_before
    assert result.delta_total == 0.0
    assert result.pokepaste_after == to_pokepaste(variant)


# ── Greedy no degrada un equipo ya construido por el builder ─────────────────

def test_already_optimal_no_negative_changes():
    """Optimizar dos veces: la segunda corrida (sobre el ya optimizado) no debe
    bajar la nota y todos sus deltas son ≥ 0."""
    variant = _variant()
    first = team_optimizer.optimize_team(variant, [])
    optimized, _ = parse_pokepaste(first.pokepaste_after)
    second = team_optimizer.optimize_team(optimized, [])
    assert second.score_after >= second.score_before - team_optimizer.EPSILON
    for c in second.changes:
        assert c.delta >= 0.0


# ── El paste optimizado re-importa (sin asertar SP==66) ──────────────────────

def test_optimized_paste_roundtrips():
    variant = _variant()
    result = team_optimizer.optimize_team(variant, [0, 3])
    reparsed, warnings = parse_pokepaste(result.pokepaste_after)
    assert len(reparsed.members) == 6
    # NO asertamos SP==66 (artefacto EV→SP del parser; memoria
    # feedback_pokepaste_ev_sp_lossy). Sólo que importa y da 6 miembros.


# ── La optimización mejora estrictamente cuando hay margen ───────────────────

def test_optimization_improves_when_room():
    """Con todos los mons libres, el paste de ejemplo (builds de muestra, no
    óptimos) debe mejorar su nota."""
    variant = _variant()
    result = team_optimizer.optimize_team(variant, [])
    assert result.score_after > result.score_before
    assert len(result.changes) >= 1


# ── Tests del endpoint POST /optimize-team ───────────────────────────────────
#
# Montamos un FastAPI() con SÓLO `router` (evita main/jinja2), igual que
# tests/test_team_rater.py::rate_client.

@pytest.fixture
def opt_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from pokemon_team_builder.api.router import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_endpoint_optimize_team(opt_client):
    resp = opt_client.post(
        "/optimize-team",
        json={"pokepaste": _PASTE, "locked_indices": [0, 3]},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # Forma de OptimizeTeamResponse.
    for key in (
        "score_before", "score_after", "delta_total", "detected_archetype",
        "archetype_confidence", "pokepaste_after", "locked_indices", "changes",
        "import_warnings",
    ):
        assert key in data, key
    assert data["score_after"] >= data["score_before"] - 1e-6
    assert data["locked_indices"] == [0, 3]
    assert isinstance(data["pokepaste_after"], str) and data["pokepaste_after"]
    # Σ(deltas) == delta_total (tolerancia float).
    total = sum(c["delta"] for c in data["changes"])
    assert abs(total - data["delta_total"]) < 1e-6
    # Ningún cambio toca un fijado; sugerencias con kinds acotadas.
    for c in data["changes"]:
        assert c["member_index"] not in (0, 3)
        for s in c["suggestions"]:
            assert s["kind"] in {"move_swap", "nature", "evs", "item"}


def test_endpoint_optimize_team_no_locks(opt_client):
    resp = opt_client.post("/optimize-team", json={"pokepaste": _PASTE})
    assert resp.status_code == 200, resp.text
    assert resp.json()["locked_indices"] == []


def test_endpoint_422_on_invalid_paste(opt_client):
    resp = opt_client.post(
        "/optimize-team", json={"pokepaste": "esto no es un equipo"}
    )
    assert resp.status_code == 422


def test_endpoint_422_on_empty_paste(opt_client):
    resp = opt_client.post("/optimize-team", json={"pokepaste": ""})
    assert resp.status_code == 422  # min_length=1 (Pydantic)


def test_invalid_locked_indices(opt_client):
    """Un índice fuera de [0,5] → 422 (contrato fijado)."""
    resp = opt_client.post(
        "/optimize-team", json={"pokepaste": _PASTE, "locked_indices": [0, 9]}
    )
    assert resp.status_code == 422


def test_invalid_negative_locked_index(opt_client):
    """Tecle LOW: un índice negativo también → 422 (cierra el contrato)."""
    resp = opt_client.post(
        "/optimize-team", json={"pokepaste": _PASTE, "locked_indices": [-1]}
    )
    assert resp.status_code == 422


def test_endpoint_all_locked_noop(opt_client):
    resp = opt_client.post(
        "/optimize-team",
        json={"pokepaste": _PASTE, "locked_indices": [0, 1, 2, 3, 4, 5]},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["changes"] == []
    assert data["score_after"] == data["score_before"]
