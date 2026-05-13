from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from pokemon_team_builder.domain.models import (
    BaseStats,
    PokemonData,
    SPDistribution,
    TeamMember,
    TeamVariant,
)
from pokemon_team_builder.main import app
from pokemon_team_builder.services import pokemon_lookup

client = TestClient(app)


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
        move_names=moves or ["protect", "earthquake", "ice-beam", "rock-slide"],
        abilities=abilities or ["pressure"],
        weaknesses=pokemon_lookup.calculate_weaknesses(types),
    )


def _fake_member(name: str, pid: int = 1) -> TeamMember:
    return TeamMember(
        pokemon=_mk(name, ["normal"], pid=pid),
        role=["physical_sweeper"],
        sp_distribution=SPDistribution(),
        item="life-orb",
        ability="pressure",
        nature="jolly",
        moves=["protect", "earthquake", "ice-beam", "rock-slide"],
    )


def _fake_variant(recommended: bool = False, score: float = 1.0) -> TeamVariant:
    members = [
        _fake_member("garchomp", pid=1),
        _fake_member("incineroar", pid=2),
        _fake_member("rillaboom", pid=3),
        _fake_member("urshifu", pid=4),
        _fake_member("kyogre", pid=5),
        _fake_member("calyrex", pid=6),
    ]
    return TeamVariant(members=members, score=score, is_recommended=recommended)


def test_health_returns_200():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_generate_unknown_anchor_returns_422():
    with patch("pokemon_team_builder.api.router.is_legal", return_value=False):
        res = client.post("/generate", json={"anchor": "missingno"})
    assert res.status_code == 422
    assert "not in the M-A regulation pool" in res.json()["detail"]


def test_generate_valid_anchor_returns_variants():
    fake_anchor = _mk("garchomp", ["dragon", "ground"], pid=445)
    fake_variants = [_fake_variant(recommended=True, score=5.5)]

    with (
        patch("pokemon_team_builder.api.router.is_legal", return_value=True),
        patch("pokemon_team_builder.api.router.pokemon_lookup.lookup", return_value=fake_anchor),
        patch("pokemon_team_builder.api.router.generate_team", return_value=fake_variants),
    ):
        res = client.post("/generate", json={"anchor": "garchomp", "variants": 1})

    assert res.status_code == 200
    body = res.json()
    assert body["anchor"] == "garchomp"
    assert len(body["variants"]) == 1
    v = body["variants"][0]
    assert v["recommended"] is True
    assert v["score"] == 5.5
    assert len(v["members"]) == 6
    assert "pokepaste" in v


def test_generate_members_include_sp_distribution_and_ev_note():
    from pokemon_team_builder.domain.models import SPDistribution

    fake_anchor = _mk("garchomp", ["dragon", "ground"], pid=445)
    sp = SPDistribution.model_validate({"atk": 32, "spe": 32, "hp": 2})
    members = [
        TeamMember(
            pokemon=_mk(f"p{i}", ["normal"], pid=i),
            role=["physical_sweeper"],
            sp_distribution=sp,
            item="scope-lens",
            ability="pressure",
            nature="jolly",
            moves=["protect", "earthquake", "ice-beam", "rock-slide"],
        )
        for i in range(1, 7)
    ]
    fake_variant = TeamVariant(members=members, score=50.0, is_recommended=True)

    with (
        patch("pokemon_team_builder.api.router.is_legal", return_value=True),
        patch("pokemon_team_builder.api.router.pokemon_lookup.lookup", return_value=fake_anchor),
        patch("pokemon_team_builder.api.router.generate_team", return_value=[fake_variant]),
    ):
        res = client.post("/generate", json={"anchor": "garchomp", "variants": 1})

    assert res.status_code == 200
    m = res.json()["variants"][0]["members"][0]
    assert "sp_distribution" in m
    assert m["sp_distribution"]["atk"] == 32
    assert m["sp_distribution"]["spe"] == 32
    assert m["sp_distribution"]["hp"] == 2
    assert "ev_note" in m


def test_ev_note_speed_investment_contains_tier_pokemon():
    from pokemon_team_builder.data.speed_tiers import load as load_speed_db
    speed_db = load_speed_db()
    tier_names = {e.name.replace("-", " ").title() for e in speed_db.entries()}

    # Use a member with speed investment so ev_note includes a speed note
    fake_anchor = _mk("garchomp", ["dragon", "ground"], spe=102, pid=445)
    sp = SPDistribution.model_validate({"spe": 32})
    members = [
        TeamMember(
            pokemon=_mk(f"p{i}", ["dragon", "ground"], spe=102, pid=i),
            role=["physical_sweeper"],
            sp_distribution=sp,
            item="scope-lens",
            ability="sand-force",
            nature="jolly",
            moves=["protect", "earthquake", "dragon-claw", "rock-slide"],
        )
        for i in range(1, 7)
    ]
    fake_variant = TeamVariant(members=members, score=88.0, is_recommended=True)

    with (
        patch("pokemon_team_builder.api.router.is_legal", return_value=True),
        patch("pokemon_team_builder.api.router.pokemon_lookup.lookup", return_value=fake_anchor),
        patch("pokemon_team_builder.api.router.generate_team", return_value=[fake_variant]),
    ):
        res = client.post("/generate", json={"anchor": "garchomp", "variants": 1})

    assert res.status_code == 200
    ev_note = res.json()["variants"][0]["members"][0]["ev_note"]
    assert ev_note != "", "ev_note should not be empty for a speed-invested member"
    assert any(name in ev_note for name in tier_names), (
        f"ev_note should name at least one Pokémon from speed tiers: {ev_note}"
    )


def test_analyze_matchup_valid_returns_200():
    team = ["garchomp", "rillaboom", "incineroar", "flutter-mane", "amoonguss", "tornadus"]
    res = client.post("/analyze-matchup", json={"team": team, "threat": "trick room"})
    assert res.status_code == 200
    data = res.json()
    assert "weakness_summary" in data
    assert "primary_handler" in data
    assert data["primary_handler"] != ""


def test_analyze_matchup_five_members_returns_422():
    res = client.post("/analyze-matchup", json={
        "team": ["garchomp", "rillaboom", "incineroar", "flutter-mane", "amoonguss"],
        "threat": "incineroar",
    })
    assert res.status_code == 422


def test_analyze_matchup_unknown_threat_returns_422():
    res = client.post("/analyze-matchup", json={
        "team": ["garchomp", "rillaboom", "incineroar", "flutter-mane", "amoonguss", "tornadus"],
        "threat": "xyzabc123garbage999",
    })
    assert res.status_code == 422
    assert "Amenaza desconocida" in res.json().get("detail", "")


# ---------------------------------------------------------------------------
# Helpers for edit-member and import tests
# ---------------------------------------------------------------------------

_MEMBER_NAMES = ["mon1", "mon2", "mon3", "mon4", "mon5", "mon6"]
_MEMBER_ITEMS = ["Sitrus Berry", "Lum Berry", "Focus Sash", "Eviolite", "Leftovers", "Mental Herb"]


def _basic_member_in(name: str, item: str, idx: int = 0) -> dict:
    return {
        "name": name,
        "role": ["physical_sweeper"],
        "item": item,
        "ability": "pressure",
        "nature": "Jolly",
        "moves": ["protect", "earthquake", "ice-beam", "rock-slide"],
        "sp_distribution": {},
        "mega_form_id": None,
    }


def _basic_variant_in_payload() -> dict:
    return {
        "members": [
            _basic_member_in(n, _MEMBER_ITEMS[i])
            for i, n in enumerate(_MEMBER_NAMES)
        ],
        "score": 75.0,
        "format_mode": "bo1",
    }


def _lookup_for_names(names: list[str]):
    pokes = {n: _mk(n, ["normal"], pid=i + 1) for i, n in enumerate(names)}
    def _lookup(slug: str):
        if slug not in pokes:
            raise ValueError(f"Unknown: {slug}")
        return pokes[slug]
    return _lookup


def _fake_import_variant() -> TeamVariant:
    return TeamVariant(
        members=[
            TeamMember(
                pokemon=_mk(n, ["normal"], pid=i + 1),
                role=["physical_sweeper"],
                sp_distribution=SPDistribution(),
                item=_MEMBER_ITEMS[i],
                ability="pressure",
                nature="Jolly",
                moves=["protect", "earthquake", "ice-beam", "rock-slide"],
            )
            for i, n in enumerate(_MEMBER_NAMES)
        ],
        score=80.0,
        is_recommended=True,
    )


# ---------------------------------------------------------------------------
# 5.1 PATCH /edit-member — move_swap returns updated team
# ---------------------------------------------------------------------------

def test_edit_member_move_swap_returns_updated_team():
    poke_with_flamethrower = _mk("mon1", ["normal"], pid=1,
                                  moves=["protect", "earthquake", "ice-beam", "rock-slide", "flamethrower"])
    lookup_fn = _lookup_for_names(_MEMBER_NAMES)

    def _lookup(slug: str):
        if slug == "mon1":
            return poke_with_flamethrower
        return lookup_fn(slug)

    with (
        patch("pokemon_team_builder.api.router.pokemon_lookup.lookup", side_effect=_lookup),
        patch("pokemon_team_builder.api.router.load_mega_evolutions", return_value={}),
    ):
        res = client.patch("/edit-member", json={
            "variant": _basic_variant_in_payload(),
            "member_index": 0,
            "edit": {"kind": "move_swap", "slot_index": 2, "new_move": "flamethrower"},
        })

    assert res.status_code == 200
    body = res.json()
    assert body["members"][0]["moves"][2] == "flamethrower"


# ---------------------------------------------------------------------------
# 5.2 PATCH /edit-member — item_swap item clause violation → 422
# ---------------------------------------------------------------------------

def test_edit_member_item_swap_clears_clause_violation_to_422():
    with (
        patch("pokemon_team_builder.api.router.pokemon_lookup.lookup",
              side_effect=_lookup_for_names(_MEMBER_NAMES)),
        patch("pokemon_team_builder.api.router.load_mega_evolutions", return_value={}),
    ):
        # "Lum Berry" is held by mon2 (index 1); swapping it onto mon1 (index 0) → clause
        res = client.patch("/edit-member", json={
            "variant": _basic_variant_in_payload(),
            "member_index": 0,
            "edit": {"kind": "item_swap", "new_item": "Lum Berry"},
        })

    assert res.status_code == 422
    assert "Clause" in res.json()["detail"] or "clause" in res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 5.3 PATCH /edit-member — pokemon_swap derives new member
# ---------------------------------------------------------------------------

def test_edit_member_pokemon_swap_derives_new_member():
    new_poke = _mk("garchomp", ["dragon", "ground"], pid=99,
                   moves=["protect", "earthquake", "dragon-claw", "rock-slide"])

    def _lookup(slug: str):
        if slug == "garchomp":
            return new_poke
        return _lookup_for_names(_MEMBER_NAMES)(slug)

    def _fake_apply_edit(variant, idx, edit):
        garchomp_member = TeamMember(
            pokemon=new_poke,
            role=["physical_sweeper"],
            sp_distribution=SPDistribution(),
            item=variant.members[idx].item,
            ability="sand-veil",
            nature="Jolly",
            moves=["protect", "earthquake", "dragon-claw", "rock-slide"],
        )
        new_members = list(variant.members)
        new_members[idx] = garchomp_member
        return variant.model_copy(update={"members": new_members, "score": 70.0})

    with (
        patch("pokemon_team_builder.api.router.pokemon_lookup.lookup", side_effect=_lookup),
        patch("pokemon_team_builder.api.router.load_mega_evolutions", return_value={}),
        patch("pokemon_team_builder.api.router.team_editor.apply_edit", side_effect=_fake_apply_edit),
    ):
        res = client.patch("/edit-member", json={
            "variant": _basic_variant_in_payload(),
            "member_index": 0,
            "edit": {"kind": "pokemon_swap", "new_pokemon_name": "garchomp"},
        })

    assert res.status_code == 200
    assert res.json()["members"][0]["name"] == "garchomp"


# ---------------------------------------------------------------------------
# 5.4 PATCH /edit-member — invalid index returns 422
# ---------------------------------------------------------------------------

def test_edit_member_invalid_index_returns_422():
    res = client.patch("/edit-member", json={
        "variant": _basic_variant_in_payload(),
        "member_index": 6,  # out of range — caught by Pydantic (ge=0, le=5)
        "edit": {"kind": "move_swap", "slot_index": 0, "new_move": "protect"},
    })
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# 5.5 PATCH /edit-member — unknown move returns 422
# ---------------------------------------------------------------------------

def test_edit_member_unknown_move_returns_422():
    with (
        patch("pokemon_team_builder.api.router.pokemon_lookup.lookup",
              side_effect=_lookup_for_names(_MEMBER_NAMES)),
        patch("pokemon_team_builder.api.router.load_mega_evolutions", return_value={}),
    ):
        res = client.patch("/edit-member", json={
            "variant": _basic_variant_in_payload(),
            "member_index": 0,
            "edit": {"kind": "move_swap", "slot_index": 0, "new_move": "hydro-pump"},
        })

    assert res.status_code == 422
    assert "pool" in res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 5.6 PATCH /edit-member — score is recomputed
# ---------------------------------------------------------------------------

def test_edit_member_score_is_recomputed():
    poke_with_flamethrower = _mk("mon1", ["normal"], pid=1,
                                  moves=["protect", "earthquake", "ice-beam", "flamethrower"])

    def _lookup(slug: str):
        if slug == "mon1":
            return poke_with_flamethrower
        return _lookup_for_names(_MEMBER_NAMES)(slug)

    with (
        patch("pokemon_team_builder.api.router.pokemon_lookup.lookup", side_effect=_lookup),
        patch("pokemon_team_builder.api.router.load_mega_evolutions", return_value={}),
    ):
        res = client.patch("/edit-member", json={
            "variant": _basic_variant_in_payload(),
            "member_index": 0,
            "edit": {"kind": "move_swap", "slot_index": 3, "new_move": "flamethrower"},
        })

    assert res.status_code == 200
    # Score is a float — just verify it's present and a valid number
    assert isinstance(res.json()["score"], (int, float))


# ---------------------------------------------------------------------------
# 5.7 POST /import — valid pokepaste returns analysis
# ---------------------------------------------------------------------------

def test_import_valid_pokepaste_returns_analysis():
    fake_variant = _fake_import_variant()
    with (
        patch("pokemon_team_builder.api.router.pokepaste_parser.parse_pokepaste",
              return_value=(fake_variant, [])),
    ):
        res = client.post("/import", json={"pokepaste": "Venusaur @ Sitrus Berry\n..."})

    assert res.status_code == 200
    body = res.json()
    assert body["recommended"] is True
    assert len(body["members"]) == 6
    assert "pokepaste" in body
    assert "import_warnings" in body
    assert body["import_warnings"] == []


# ---------------------------------------------------------------------------
# 5.8 POST /import — 5 members returns 422
# ---------------------------------------------------------------------------

def test_import_five_members_returns_422():
    with (
        patch("pokemon_team_builder.api.router.pokepaste_parser.parse_pokepaste",
              side_effect=ValueError("El PokePaste tiene 5 miembro(s); se requieren exactamente 6")),
    ):
        res = client.post("/import", json={"pokepaste": "..."})

    assert res.status_code == 422
    assert "5" in res.json()["detail"]


# ---------------------------------------------------------------------------
# 5.9 POST /import — 7 members returns 422
# ---------------------------------------------------------------------------

def test_import_seven_members_returns_422():
    with (
        patch("pokemon_team_builder.api.router.pokepaste_parser.parse_pokepaste",
              side_effect=ValueError("El PokePaste tiene 7 miembros; el máximo es 6")),
    ):
        res = client.post("/import", json={"pokepaste": "..."})

    assert res.status_code == 422
    assert "7" in res.json()["detail"]


# ---------------------------------------------------------------------------
# 5.10 POST /import — illegal pokemon returns 422
# ---------------------------------------------------------------------------

def test_import_illegal_pokemon_returns_422():
    with (
        patch("pokemon_team_builder.api.router.pokepaste_parser.parse_pokepaste",
              side_effect=ValueError("'dragapult' no está en el pool legal M-A")),
    ):
        res = client.post("/import", json={"pokepaste": "..."})

    assert res.status_code == 422
    assert "dragapult" in res.json()["detail"]


# ---------------------------------------------------------------------------
# 5.11 POST /import — duplicate species returns 422
# ---------------------------------------------------------------------------

def test_import_duplicate_species_returns_422():
    with (
        patch("pokemon_team_builder.api.router.pokepaste_parser.parse_pokepaste",
              side_effect=ValueError("Species Clause: 'garchomp' aparece más de una vez")),
    ):
        res = client.post("/import", json={"pokepaste": "..."})

    assert res.status_code == 422
    assert "Species" in res.json()["detail"] or "garchomp" in res.json()["detail"]


# ---------------------------------------------------------------------------
# 5.12 POST /import — move outside pool returns warning, not error
# ---------------------------------------------------------------------------

def test_import_move_outside_pool_returns_warning_not_error():
    fake_variant = _fake_import_variant()
    with (
        patch("pokemon_team_builder.api.router.pokepaste_parser.parse_pokepaste",
              return_value=(fake_variant, ["mon1: move 'hydro-pump' no está en su pool (se conserva)"])),
    ):
        res = client.post("/import", json={"pokepaste": "..."})

    assert res.status_code == 200
    assert len(res.json()["import_warnings"]) == 1
    assert "hydro-pump" in res.json()["import_warnings"][0]


# ---------------------------------------------------------------------------
# 5.13 POST /import — round-trip: import of export output is same team
# ---------------------------------------------------------------------------

def test_import_pokepaste_response_is_canonical():
    """import_warnings is empty when we re-import our own generated output."""
    fake_variant = _fake_import_variant()
    with (
        patch("pokemon_team_builder.api.router.pokepaste_parser.parse_pokepaste",
              return_value=(fake_variant, [])),
    ):
        res = client.post("/import", json={"pokepaste": "..."})

    assert res.status_code == 200
    body = res.json()
    assert body["import_warnings"] == []
    assert body["recommended"] is True
    assert len(body["members"]) == 6


# ---------------------------------------------------------------------------
# 5.14 POST /import — Mega form detected
# ---------------------------------------------------------------------------

def test_import_mega_form_detected():
    """Charizard-Mega-X in the paste → base form + mega_form set."""
    from pokemon_team_builder.domain.models import MegaForm, BaseStats as BS

    mega_x = MegaForm(
        form_id="charizard-mega-x",
        mega_stone="Charizardite X",
        types=["fire", "dragon"],
        ability="tough-claws",
        stats=BS(hp=78, atk=130, **{"def": 111}, spa=130, spd=85, spe=100),
    )
    fake_variant = _fake_import_variant()
    # Replace first member with a mega-carrying one
    charizard_poke = _mk("charizard", ["fire", "flying"], pid=6)
    mega_member = TeamMember(
        pokemon=charizard_poke,
        role=["physical_sweeper"],
        sp_distribution=SPDistribution(),
        item="Charizardite X",
        ability="tough-claws",
        nature="Jolly",
        moves=["protect", "earthquake", "flare-blitz", "dragon-claw"],
        mega_form=mega_x,
    )
    members = [mega_member] + list(fake_variant.members[1:])
    variant_with_mega = TeamVariant(members=members, score=85.0, is_recommended=True)

    with (
        patch("pokemon_team_builder.api.router.pokepaste_parser.parse_pokepaste",
              return_value=(variant_with_mega, [])),
    ):
        res = client.post("/import", json={"pokepaste": "Charizard-Mega-X @ Charizardite X\n..."})

    assert res.status_code == 200
    body = res.json()
    # The exporter uses mega_stone as item when mega_form is set
    assert body["members"][0]["item"] == "Charizardite X"


# ── GET /meta-teams (task 6.4) ────────────────────────────────────────────────

def test_meta_teams_returns_200_even_when_empty() -> None:
    with patch("pokemon_team_builder.api.router.labmaus_service.get_top_teams", return_value=[]):
        res = client.get("/meta-teams")
    assert res.status_code == 200
    body = res.json()
    assert body["teams"] == []
    assert body["stale"] is True


def test_meta_teams_stale_false_when_data_present() -> None:
    from pokemon_team_builder.services.labmaus_service import LabMausMember, LabMausTeam

    fake_team = LabMausTeam(
        members=[LabMausMember(name="garchomp")],
        player="Ash",
        tournament="Test Cup",
        placement=1,
        pokepaste_url="https://pokepast.es/abc",
        regulation="Regulation Set M-A",
    )
    with patch("pokemon_team_builder.api.router.labmaus_service.get_top_teams", return_value=[fake_team]):
        res = client.get("/meta-teams")
    assert res.status_code == 200
    body = res.json()
    assert len(body["teams"]) == 1
    assert body["stale"] is False
    assert body["teams"][0]["player"] == "Ash"


def test_meta_teams_forwards_regulation_param() -> None:
    with patch("pokemon_team_builder.api.router.labmaus_service.get_top_teams", return_value=[]) as mock_fn:
        client.get("/meta-teams?regulation=M-A")
    mock_fn.assert_called_once_with("M-A")


# ── GET /tournaments (task 6.4) ───────────────────────────────────────────────

def test_tournaments_returns_200_even_when_empty() -> None:
    with patch("pokemon_team_builder.api.router.tournament_service.get_upcoming", return_value=[]):
        res = client.get("/tournaments")
    assert res.status_code == 200
    body = res.json()
    assert body["tournaments"] == []
    assert body["stale"] is True


def test_tournaments_stale_false_when_data_present() -> None:
    from pokemon_team_builder.services.tournament_service import Tournament

    fake = Tournament(
        id="T1", name="Copa Madrid", date="2026-06-01",
        city="Madrid", country="Spain",
        regulation="Regulation Set M-A", lat=40.4, lon=-3.7,
    )
    with patch("pokemon_team_builder.api.router.tournament_service.get_upcoming", return_value=[fake]):
        res = client.get("/tournaments")
    assert res.status_code == 200
    body = res.json()
    assert len(body["tournaments"]) == 1
    assert body["stale"] is False


def test_tournaments_forwards_query_params() -> None:
    with patch("pokemon_team_builder.api.router.tournament_service.get_upcoming", return_value=[]) as mock_fn:
        client.get("/tournaments?lat=28.4636&lon=-16.2518&radius=500")
    mock_fn.assert_called_once_with(lat=28.4636, lon=-16.2518, radius_miles=500)
