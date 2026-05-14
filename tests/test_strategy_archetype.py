"""Phase 2b — strategy-archetype tests.

Covers:
  - GenerateRequest schema accepts the seven-element archetype Literal
    and defaults to "balance".
  - Invalid archetype values produce HTTP 422 via Pydantic.
  - ``archetype_weights.json`` loads cleanly and validates schema shape.
  - Out-of-range weights raise on load.
  - Cheese-allowance gates Perish Song / Destiny Bond selection.
  - VariantOut echoes the request's archetype.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from pokemon_team_builder.api.schemas import GenerateRequest, VariantOut
from pokemon_team_builder.main import app
from pokemon_team_builder.config import ARCHETYPE_WEIGHTS_FILE
from pokemon_team_builder.data.archetype_weights_loader import (
    _balance_baseline,
    get_weights,
    load_archetype_weights,
    known_archetypes,
)
from pokemon_team_builder.domain.exceptions import TeamBuildError
from pokemon_team_builder.domain.models import BaseStats, PokemonData
from pokemon_team_builder.services import pokemon_lookup
from pokemon_team_builder.services.replica_exporter import select_moves_for_role


# ---------------------------------------------------------------------------
# GenerateRequest validation
# ---------------------------------------------------------------------------

def test_generate_request_defaults_archetype_to_balance() -> None:
    """A request without an archetype field defaults to balance.

    Backward-compatibility guarantee — clients that pre-date Phase 2b
    keep working without changes.
    """
    req = GenerateRequest(anchor="garchomp")
    assert req.archetype == "balance"


def test_generate_request_accepts_all_seven_archetypes() -> None:
    """All seven canonical archetypes are accepted by the Literal."""
    for archetype in known_archetypes():
        req = GenerateRequest(anchor="garchomp", archetype=archetype)
        assert req.archetype == archetype


def test_invalid_archetype_rejected_by_pydantic() -> None:
    """Pydantic v2 rejects unknown archetypes with a ValidationError."""
    with pytest.raises(ValidationError):
        GenerateRequest(anchor="garchomp", archetype="foobar")  # type: ignore[arg-type]


def test_invalid_archetype_returns_422() -> None:
    """End-to-end: an invalid archetype on /generate produces HTTP 422.

    Exercises the FastAPI Pydantic plumbing — confirms the Literal
    annotation is wired correctly in the route schema.
    """
    client = TestClient(app)
    resp = client.post("/generate", json={"anchor": "garchomp", "archetype": "foobar"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# archetype_weights.json loader
# ---------------------------------------------------------------------------

def test_archetype_weights_load_from_json() -> None:
    """``load_archetype_weights`` returns one entry per known archetype.

    Confirms the file ships with the canonical seven matrices and each
    one passes the schema validator.
    """
    weights = load_archetype_weights()
    for archetype in known_archetypes():
        assert archetype in weights, (
            f"archetype_weights.json is missing entry '{archetype}'"
        )
        w = weights[archetype]
        # All 8 required keys are present and in range.
        for key in (
            "coverage", "roles", "sp", "items",
            "speed", "bulk", "cheese_allowance", "weather_synergy",
        ):
            value = getattr(w, key)
            assert 0.0 <= value <= 2.0, (
                f"{archetype}.{key} = {value} is outside [0.0, 2.0]"
            )


def test_get_weights_falls_back_to_balance() -> None:
    """Unknown archetype names degrade to the balance matrix.

    Defence-in-depth — the API layer validates input, but internal
    callers might not. We should never crash on an unknown name.
    """
    bal = get_weights("balance")
    weird = get_weights("definitely-not-a-real-archetype")
    assert weird == bal


def test_balance_baseline_scoring_multipliers_are_baseline() -> None:
    """The in-code balance fallback is the scoring-multiplier baseline.

    Scoring components (coverage/roles/sp/items/speed/bulk/weather_synergy)
    are all 1.0 — balance is the reference everything else scales against.
    ``cheese_allowance`` is intentionally < 1.0 because it is a gate
    threshold, not a multiplier — per the strategy-archetype spec only
    ``perish_trap`` opens the cheese-move gate.
    """
    bal = _balance_baseline()
    assert bal.coverage == 1.0
    assert bal.roles == 1.0
    assert bal.sp == 1.0
    assert bal.items == 1.0
    assert bal.speed == 1.0
    assert bal.bulk == 1.0
    assert bal.weather_synergy == 1.0
    # cheese_allowance is the only sub-1.0 default — balance MUST skip
    # cheese moves per the spec.
    assert bal.cheese_allowance < 1.0


def test_archetype_weights_out_of_range_raises_on_startup(tmp_path: Path) -> None:
    """A weight outside [0.0, 2.0] raises ``TeamBuildError`` at load.

    Uses tmp_path to write a synthetic broken file and patches the
    loader's ``ARCHETYPE_WEIGHTS_FILE`` constant; lru_cache is cleared
    so the bad file is actually read.
    """
    bad_file = tmp_path / "archetype_weights.json"
    bad_file.write_text(
        json.dumps({
            "regulation": "M-A",
            "data_version": 1,
            "archetypes": {
                "balance": {
                    "coverage": 1.0, "roles": 1.0, "sp": 1.0, "items": 1.0,
                    "speed": 1.0, "bulk": 1.0,
                    # Out of range — must trigger the validator.
                    "cheese_allowance": 5.0,
                    "weather_synergy": 1.0,
                },
            },
        }),
        encoding="utf-8",
    )

    import pokemon_team_builder.data.archetype_weights_loader as loader_mod
    load_archetype_weights.cache_clear()
    with patch.object(loader_mod, "ARCHETYPE_WEIGHTS_FILE", bad_file):
        with pytest.raises(TeamBuildError) as exc_info:
            load_archetype_weights()
    # Reset cache so the next test re-reads the real file.
    load_archetype_weights.cache_clear()
    assert "cheese_allowance" in str(exc_info.value), (
        f"error message should reference the offending key; got: {exc_info.value}"
    )


def test_archetype_weights_missing_key_raises(tmp_path: Path) -> None:
    """Missing required key raises ``TeamBuildError`` with the key name."""
    bad_file = tmp_path / "archetype_weights.json"
    bad_file.write_text(
        json.dumps({
            "regulation": "M-A",
            "data_version": 1,
            "archetypes": {
                "balance": {
                    "coverage": 1.0, "roles": 1.0, "sp": 1.0, "items": 1.0,
                    "speed": 1.0, "bulk": 1.0, "cheese_allowance": 1.0,
                    # weather_synergy omitted.
                },
            },
        }),
        encoding="utf-8",
    )

    import pokemon_team_builder.data.archetype_weights_loader as loader_mod
    load_archetype_weights.cache_clear()
    with patch.object(loader_mod, "ARCHETYPE_WEIGHTS_FILE", bad_file):
        with pytest.raises(TeamBuildError) as exc_info:
            load_archetype_weights()
    load_archetype_weights.cache_clear()
    assert "weather_synergy" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Cheese-allowance gating in select_moves_for_role
# ---------------------------------------------------------------------------

def _mk(
    name: str,
    types: list[str],
    *,
    hp: int = 80,
    atk: int = 80,
    def_: int = 80,
    spa: int = 80,
    spd: int = 80,
    spe: int = 80,
    moves: list[str] | None = None,
    abilities: list[str] | None = None,
    pid: int = 1,
) -> PokemonData:
    return PokemonData(
        id=pid,
        name=name,
        types=types,
        base_stats=BaseStats(
            hp=hp, atk=atk, **{"def": def_}, spa=spa, spd=spd, spe=spe
        ),
        move_names=moves or [
            "protect", "tackle", "earthquake", "ice-beam", "thunderbolt",
        ],
        abilities=abilities or ["pressure"],
        weaknesses=pokemon_lookup.calculate_weaknesses(types),
    )


def test_perish_song_allowed_in_perish_trap() -> None:
    """Perish Song is assignable when archetype is perish_trap."""
    # A typical perish-trap user: bulky, slow, knows Perish Song.
    gothitelle = _mk(
        "gothitelle", ["psychic"],
        hp=70, atk=55, def_=95, spa=95, spd=110, spe=65,
        abilities=["shadow-tag"],
        moves=["protect", "psychic", "trick-room", "perish-song"],
        pid=576,
    )
    moves = select_moves_for_role(
        gothitelle, ["lead_support"],
        archetype="perish_trap",
    )
    assert "perish-song" in moves, (
        f"perish-song must appear in perish_trap moveset; got {moves}"
    )


def test_destiny_bond_skipped_in_balance() -> None:
    """Destiny Bond is excluded from a balance-archetype moveset.

    Note: Destiny Bond appears only via fallback (it isn't in the role
    priority lists). The cheese gate adds it to the fallback's exclusion
    set, so the slot never resolves to Destiny Bond.
    """
    # Force fallback to consider Destiny Bond by giving a tiny move pool.
    misdreavus = _mk(
        "misdreavus", ["ghost"],
        hp=60, spa=85, spd=85, spe=85,
        abilities=["levitate"],
        moves=["protect", "shadow-ball", "thunderbolt", "destiny-bond"],
        pid=200,
    )
    moves = select_moves_for_role(
        misdreavus, ["special_sweeper"], archetype="balance",
    )
    assert "destiny-bond" not in moves, (
        f"destiny-bond leaked into balance moveset: {moves}"
    )


def test_destiny_bond_allowed_in_perish_trap() -> None:
    """The cheese set unlocks in perish_trap.

    Different cheese move from the perish-song test so we cover the gate
    rather than just the dedicated perish-song path.
    """
    misdreavus = _mk(
        "misdreavus", ["ghost"],
        hp=60, spa=85, spd=85, spe=85,
        abilities=["levitate"],
        moves=["protect", "shadow-ball", "thunderbolt", "destiny-bond"],
        pid=200,
    )
    moves = select_moves_for_role(
        misdreavus, ["special_sweeper"], archetype="perish_trap",
    )
    # Destiny Bond is in the move pool; under perish_trap the cheese gate
    # is open, so the fallback for slot 4 is free to pick it.
    assert "destiny-bond" in moves, (
        f"destiny-bond should be allowed under perish_trap; got {moves}"
    )


# ---------------------------------------------------------------------------
# VariantOut echoes archetype
# ---------------------------------------------------------------------------

def test_variantout_echoes_archetype() -> None:
    """VariantOut.archetype defaults to balance and accepts overrides.

    Validates the schema field — the full integration through
    /generate is exercised by the favorite-first test suite.
    """
    from pokemon_team_builder.api.schemas import MemberOut, VariantOut

    v = VariantOut(
        score=80.0,
        recommended=True,
        pokepaste="",
        members=[
            MemberOut(
                name=f"m{i}", item="X", ability="Y", nature="Hardy",
                moves=["a", "b", "c", "d"], roles=["physical_sweeper"],
            )
            for i in range(6)
        ],
        format_mode="bo1",
        archetype="hyper_offense",
    )
    assert v.archetype == "hyper_offense"

    # Default path: archetype omitted → "balance"
    v2 = VariantOut(
        score=80.0,
        recommended=False,
        pokepaste="",
        members=v.members,
        format_mode="bo1",
    )
    assert v2.archetype == "balance"


# ── C1: team_sheet propagation + auto-resolution ──────────────────────────


def test_generate_request_defaults_team_sheet_to_auto():
    req = GenerateRequest(anchor="garchomp")
    assert req.team_sheet == "auto"


def test_generate_request_accepts_explicit_open_closed():
    req_open = GenerateRequest(anchor="garchomp", team_sheet="open")
    assert req_open.team_sheet == "open"
    req_closed = GenerateRequest(anchor="garchomp", team_sheet="closed")
    assert req_closed.team_sheet == "closed"


def test_generate_request_rejects_invalid_team_sheet():
    with pytest.raises(ValidationError):
        GenerateRequest(anchor="garchomp", team_sheet="halfopen")


def test_variantout_team_sheet_defaults_to_closed():
    """Phase 1 importers and legacy paths should produce closed by default."""
    from pokemon_team_builder.api.schemas import MemberOut
    m = MemberOut(
        name="garchomp", item="Choice Band", ability="sand-veil",
        nature="jolly",
        moves=["protect", "earthquake", "dragon-claw", "rock-slide"],
        roles=["physical_sweeper"],
    )
    v = VariantOut(
        score=80.0, recommended=False, pokepaste="",
        members=[m] * 6, format_mode="bo1",
    )
    assert v.team_sheet == "closed"


def test_open_sheet_blocks_perish_song_even_for_perish_trap():
    """C1 trade-off: open sheet × 0.7 multiplier reduces perish_trap's
    cheese_allowance from 1.0 to 0.7, which trips the < 1.0 gate. Per
    the design rationale in select_moves_for_role, open sheet pressures
    EVERY archetype away from cheese. Test confirms that semantics.
    """
    from pokemon_team_builder.domain.models import BaseStats, PokemonData
    from pokemon_team_builder.services.replica_exporter import select_moves_for_role
    gengar = PokemonData(
        id=94, name="gengar", types=["ghost", "poison"],
        base_stats=BaseStats(hp=60, atk=65, **{"def": 60},
                             spa=130, spd=75, spe=110),
        move_names=["protect", "shadow-ball", "sludge-bomb", "thunderbolt",
                    "perish-song", "destiny-bond"],
        abilities=["cursed-body"], weaknesses={},
    )
    # Closed sheet + perish_trap → Perish Song allowed
    closed_moves = select_moves_for_role(
        gengar, ["lead_support"], archetype="perish_trap", team_sheet="closed",
    )
    # Open sheet + perish_trap → cheese gated (multiplier drops below 1.0)
    open_moves = select_moves_for_role(
        gengar, ["lead_support"], archetype="perish_trap", team_sheet="open",
    )
    assert "perish-song" in closed_moves, (
        f"closed sheet + perish_trap should allow perish-song; got {closed_moves}"
    )
    assert "perish-song" not in open_moves, (
        f"open sheet should gate cheese even in perish_trap; got {open_moves}"
    )
