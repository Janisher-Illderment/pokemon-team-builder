from __future__ import annotations

import json
import sys

import pytest

from pokemon_team_builder.config import DATA_DIR
from pokemon_team_builder.data import mega_loader
from pokemon_team_builder.data.mega_loader import (
    MEGA_EVOLUTIONS_FILE,
    load_mega_evolutions,
)
from pokemon_team_builder.domain.exceptions import TeamBuildError
from pokemon_team_builder.domain.models import (
    BaseStats,
    MegaForm,
    PokemonData,
    SPDistribution,
    TeamMember,
    TeamVariant,
)
from pokemon_team_builder.services import pokemon_lookup
from pokemon_team_builder.services.replica_exporter import to_pokepaste
from pokemon_team_builder.services.synergy_engine import (
    assign_role,
    assign_role_with_mega,
)
from pokemon_team_builder.services.team_generator import (
    _assign_items,
    _resolve_mega,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mk(
    name: str,
    types: list[str],
    *,
    hp: int = 70,
    atk: int = 70,
    def_: int = 70,
    spa: int = 70,
    spd: int = 70,
    spe: int = 70,
    moves: list[str] | None = None,
    abilities: list[str] | None = None,
    pid: int = 1,
    megas: list[MegaForm] | None = None,
) -> PokemonData:
    return PokemonData(
        id=pid,
        name=name,
        types=types,
        base_stats=BaseStats(
            hp=hp, atk=atk, **{"def": def_}, spa=spa, spd=spd, spe=spe
        ),
        move_names=moves or ["protect", "tackle"],
        abilities=abilities or ["pressure"],
        weaknesses=pokemon_lookup.calculate_weaknesses(types),
        megas=megas or [],
    )


def _mega(
    form_id: str,
    stone: str,
    types: list[str],
    *,
    ability: str = "blaze",
    hp: int = 78,
    atk: int = 100,
    def_: int = 78,
    spa: int = 100,
    spd: int = 85,
    spe: int = 100,
    verified: bool = True,
) -> MegaForm:
    return MegaForm(
        form_id=form_id,
        mega_stone=stone,
        types=types,
        ability=ability,
        stats=BaseStats(
            hp=hp, atk=atk, **{"def": def_}, spa=spa, spd=spd, spe=spe
        ),
        verified=verified,
    )


# ---------------------------------------------------------------------------
# T1 — data file integrity
# ---------------------------------------------------------------------------


def test_mega_data_integrity() -> None:
    """Every entry in mega_evolutions.json has all required fields and
    every mega_stone is unique across all entries."""
    with open(MEGA_EVOLUTIONS_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    assert raw["regulation"] == "M-A"
    megas_block = raw["megas"]
    assert isinstance(megas_block, dict)

    seen_stones: set[str] = set()
    seen_form_ids: set[str] = set()
    required_keys = {"form_id", "mega_stone", "types", "ability", "stats", "verified"}
    required_stat_keys = {"hp", "atk", "def", "spa", "spd", "spe"}

    for species, entries in megas_block.items():
        assert isinstance(entries, list) and entries, f"empty entries for {species}"
        for entry in entries:
            missing = required_keys - set(entry.keys())
            assert not missing, f"{species}: missing keys {missing}"

            stone = entry["mega_stone"]
            assert isinstance(stone, str) and stone
            assert stone not in seen_stones, f"duplicate mega_stone: {stone}"
            seen_stones.add(stone)

            form_id = entry["form_id"]
            assert form_id not in seen_form_ids, f"duplicate form_id: {form_id}"
            seen_form_ids.add(form_id)

            types = entry["types"]
            assert isinstance(types, list) and 1 <= len(types) <= 2

            assert isinstance(entry["ability"], str) and entry["ability"]

            stats = entry["stats"]
            stat_missing = required_stat_keys - set(stats.keys())
            assert not stat_missing, f"{species}: missing stats {stat_missing}"
            for stat_name in required_stat_keys:
                assert isinstance(stats[stat_name], int) and stats[stat_name] >= 1


def test_mega_data_contains_all_59_species() -> None:
    """59 mega-eligible species: original Champions set + Metagross + Glimmora + Scovillain.

    Total forms = 60 (Charizard X/Y; all others have one form each).
    Mega Raichu X/Y and Mega Tatsugiri excluded — not in game at launch (trailers only).
    """
    data = load_mega_evolutions()
    assert len(data) == 59
    total_forms = sum(len(forms) for forms in data.values())
    assert total_forms == 60
    # Charizard is the only species with two forms
    multi_form = {sp for sp, forms in data.items() if len(forms) > 1}
    assert multi_form == {"charizard"}


# ---------------------------------------------------------------------------
# T2 — domain model
# ---------------------------------------------------------------------------


def test_pokemon_data_has_megas_field_default_empty() -> None:
    p = _mk("pikachu", ["electric"])
    assert p.megas == []


def test_pokemon_data_megas_field_accepts_list() -> None:
    mega = _mega("pikachu-mega", "Pikachunite", ["electric"])
    p = _mk("pikachu", ["electric"], megas=[mega])
    assert len(p.megas) == 1
    assert p.megas[0].mega_stone == "Pikachunite"


# ---------------------------------------------------------------------------
# T3 — loader warning for unverified entries
# ---------------------------------------------------------------------------


def test_mega_loader_warns_unverified(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Loading the data file must print a stderr warning listing every
    entry whose verified flag is False."""
    # The lru_cache holds a reference to a previously-warmed dict — clear
    # it so this test exercises the warning path on a fresh load.
    load_mega_evolutions.cache_clear()
    load_mega_evolutions()
    captured = capsys.readouterr()
    assert "warning" in captured.err.lower()
    assert "unverified" in captured.err.lower()
    # At least the canonical unverified set per ADR (sableye, scizor,
    # sharpedo, slowbro, steelix, tyranitar, manectric, houndoom).
    for form in (
        "sableye-mega",
        "scizor-mega",
        "sharpedo-mega",
        "slowbro-mega",
        "steelix-mega",
        "tyranitar-mega",
        "manectric-mega",
        "houndoom-mega",
    ):
        assert form in captured.err, f"{form} not in stderr warning"


# ---------------------------------------------------------------------------
# T4 — pokemon_lookup enrichment
# ---------------------------------------------------------------------------


def test_lookup_gengar_has_mega(monkeypatch: pytest.MonkeyPatch) -> None:
    """lookup('gengar') populates pokemon.megas with one form using stone
    'Gengarite'."""
    raw_gengar = {
        "id": 94,
        "name": "gengar",
        "types": [
            {"slot": 1, "type": {"name": "ghost"}},
            {"slot": 2, "type": {"name": "poison"}},
        ],
        "stats": [
            {"base_stat": 60, "stat": {"name": "hp"}},
            {"base_stat": 65, "stat": {"name": "attack"}},
            {"base_stat": 60, "stat": {"name": "defense"}},
            {"base_stat": 130, "stat": {"name": "special-attack"}},
            {"base_stat": 75, "stat": {"name": "special-defense"}},
            {"base_stat": 110, "stat": {"name": "speed"}},
        ],
        "moves": [{"move": {"name": "shadow-ball"}}],
        "abilities": [
            {"ability": {"name": "cursed-body"}, "is_hidden": False, "slot": 1}
        ],
    }
    monkeypatch.setattr(pokemon_lookup, "is_legal", lambda _: True)
    monkeypatch.setattr(
        pokemon_lookup.pokeapi_client, "get_pokemon", lambda _: raw_gengar
    )

    result = pokemon_lookup.lookup("gengar")
    assert len(result.megas) == 1
    assert result.megas[0].mega_stone == "Gengarite"
    assert result.megas[0].form_id == "gengar-mega"


# ---------------------------------------------------------------------------
# T5 — assign_role_with_mega
# ---------------------------------------------------------------------------


def test_assign_role_with_mega_garchomp() -> None:
    """Mega Garchomp's 170 Atk dwarfs its 65 SpA → primary role
    physical_sweeper."""
    base = _mk(
        "garchomp",
        ["dragon", "ground"],
        atk=130,
        spa=80,
        spe=102,
    )
    mega = _mega(
        "garchomp-mega",
        "Garchompite",
        ["dragon", "ground"],
        ability="sand-force",
        hp=108,
        atk=170,
        def_=115,
        spa=65,
        spd=95,
        spe=102,
    )
    roles = assign_role_with_mega(base, mega)
    assert roles[0] == "physical_sweeper", roles


def test_assign_role_with_mega_none_unchanged() -> None:
    """When mega=None, assign_role_with_mega must equal assign_role."""
    p = _mk(
        "talonflame",
        ["fire", "flying"],
        atk=81,
        spe=126,
        moves=["tailwind", "brave-bird"],
    )
    assert assign_role_with_mega(p, None) == assign_role(p)


def test_assign_role_with_mega_uses_mega_types() -> None:
    """Charizard X is Fire/Dragon — synthesizing the role uses the new types."""
    base = _mk("charizard", ["fire", "flying"], atk=84, spa=109, spe=100)
    mega_x = _mega(
        "charizard-mega-x",
        "Charizardite X",
        ["fire", "dragon"],
        ability="tough-claws",
        hp=78,
        atk=130,
        def_=111,
        spa=130,
        spd=85,
        spe=100,
    )
    roles = assign_role_with_mega(base, mega_x)
    # 130 Atk == 130 SpA, with the >= tiebreak in assign_role this resolves
    # to physical_sweeper as primary.
    assert roles[0] == "physical_sweeper", roles
    assert "special_sweeper" in roles


# ---------------------------------------------------------------------------
# T6 — _assign_items mega_slot
# ---------------------------------------------------------------------------


def test_assign_items_mega_slot_pre_fixes_item() -> None:
    """When mega_slot=(0, 'Gengarite'), items[0] is exactly 'Gengarite' and
    no other slot can pick it up."""
    members = [
        _mk(
            f"mon-{i}",
            ["psychic"],
            atk=60,
            spa=120,
            spe=100,
            moves=["protect", "psychic", "shadow-ball", "thunderbolt"],
            pid=400 + i,
        )
        for i in range(6)
    ]
    members_roles = [["special_sweeper"]] * 6
    items = _assign_items(
        members_roles, members, mega_slot=(0, "Gengarite")
    )
    assert items[0] == "Gengarite"
    # No duplicates — Item Clause holds even with the pre-fixed slot.
    assert len(set(items)) == 6
    # Stone reserved → no other slot can pick it up.
    assert items[1:].count("Gengarite") == 0


def test_assign_items_mega_slot_other_slots_normal() -> None:
    """The remaining 5 slots receive their role-based items as usual."""
    members = [
        _mk(
            f"mon-{i}",
            ["normal"],
            atk=120,
            spa=70,
            spe=90,
            moves=["protect", "body-slam", "earthquake", "ice-beam"],
            pid=500 + i,
        )
        for i in range(6)
    ]
    members_roles = [["physical_sweeper"]] * 6
    items = _assign_items(
        members_roles, members, mega_slot=(0, "Charizardite Y")
    )
    assert items[0] == "Charizardite Y"
    # Slot 1 (and onwards) gets the role default first, then fallbacks.
    # v0.3: physical_sweeper default is Choice Band (Champions M-A confirmed,
    # Weakness Policy removed per Inte v2 cross-check).
    assert items[1] == "Choice Band"


# ---------------------------------------------------------------------------
# T7 — _resolve_mega
# ---------------------------------------------------------------------------


def test_resolve_mega_off_returns_none() -> None:
    """choice='off' always returns None even on a mega-eligible species."""
    mega = _mega("gengar-mega", "Gengarite", ["ghost", "poison"])
    p = _mk("gengar", ["ghost", "poison"], megas=[mega])
    assert _resolve_mega(p, "off") is None


def test_resolve_mega_no_megas_returns_none() -> None:
    """A species with no mega entries returns None regardless of choice."""
    p = _mk("milotic", ["water"])
    assert _resolve_mega(p, "auto") is None
    assert _resolve_mega(p, "x") is None


def test_resolve_mega_auto_single_form() -> None:
    """Single-form species + 'auto' returns the only form."""
    mega = _mega("gengar-mega", "Gengarite", ["ghost", "poison"])
    p = _mk("gengar", ["ghost", "poison"], megas=[mega])
    result = _resolve_mega(p, "auto")
    assert result is mega


def test_resolve_mega_auto_multiform_raises() -> None:
    """Multi-form species + 'auto' raises TeamBuildError mentioning x and y."""
    mega_x = _mega("charizard-mega-x", "Charizardite X", ["fire", "dragon"])
    mega_y = _mega("charizard-mega-y", "Charizardite Y", ["fire", "flying"])
    p = _mk("charizard", ["fire", "flying"], megas=[mega_x, mega_y])
    with pytest.raises(TeamBuildError) as exc:
        _resolve_mega(p, "auto")
    msg = str(exc.value).lower()
    assert "x" in msg and "y" in msg


def test_resolve_mega_x_charizard() -> None:
    """choice='x' on a multi-form species returns the X form."""
    mega_x = _mega("charizard-mega-x", "Charizardite X", ["fire", "dragon"])
    mega_y = _mega("charizard-mega-y", "Charizardite Y", ["fire", "flying"])
    p = _mk("charizard", ["fire", "flying"], megas=[mega_x, mega_y])
    result = _resolve_mega(p, "x")
    assert result is mega_x
    assert result.mega_stone == "Charizardite X"


def test_resolve_mega_y_charizard() -> None:
    """choice='y' on a multi-form species returns the Y form."""
    mega_x = _mega("charizard-mega-x", "Charizardite X", ["fire", "dragon"])
    mega_y = _mega("charizard-mega-y", "Charizardite Y", ["fire", "flying"])
    p = _mk("charizard", ["fire", "flying"], megas=[mega_x, mega_y])
    result = _resolve_mega(p, "y")
    assert result is mega_y


def test_resolve_mega_x_on_single_form_raises() -> None:
    """Asking for 'x' on a single-form species without an X form raises."""
    mega = _mega("gengar-mega", "Gengarite", ["ghost", "poison"])
    p = _mk("gengar", ["ghost", "poison"], megas=[mega])
    with pytest.raises(TeamBuildError):
        _resolve_mega(p, "x")


# ---------------------------------------------------------------------------
# T8 — TeamMember.mega_form + replica_exporter
# ---------------------------------------------------------------------------


def _make_member(
    pokemon: PokemonData,
    *,
    item: str,
    mega_form: MegaForm | None = None,
) -> TeamMember:
    return TeamMember(
        pokemon=pokemon,
        role=["special_sweeper"],
        sp_distribution=SPDistribution.model_validate(
            {"spa": 32, "spe": 32, "hp": 2}
        ),
        item=item,
        ability=pokemon.abilities[0],
        nature="Timid",
        moves=["protect", "shadow-ball", "sludge-bomb", "thunderbolt"],
        mega_form=mega_form,
    )


def test_team_member_mega_form_default_none() -> None:
    p = _mk(
        "gengar",
        ["ghost", "poison"],
        moves=["protect", "shadow-ball", "sludge-bomb", "thunderbolt"],
        abilities=["cursed-body"],
    )
    member = _make_member(p, item="Sitrus Berry")
    assert member.mega_form is None


def test_pokepaste_mega_gengar_item() -> None:
    """A Mega-Gengar member produces 'Item: Gengarite' in PokePaste output.

    Note: PokePaste format uses ``Name @ Item`` on the species line, not
    ``Item:`` on its own. The check matches the canonical ``@ Gengarite``
    form to be precise.
    """
    p = _mk(
        "gengar",
        ["ghost", "poison"],
        moves=["protect", "shadow-ball", "sludge-bomb", "thunderbolt"],
        abilities=["cursed-body"],
    )
    mega = _mega(
        "gengar-mega",
        "Gengarite",
        ["ghost", "poison"],
        ability="shadow-tag",
        hp=60,
        atk=65,
        def_=80,
        spa=170,
        spd=95,
        spe=130,
    )
    # item field intentionally set to a different stone — exporter must
    # prefer mega_form.mega_stone.
    member = _make_member(p, item="Leftovers", mega_form=mega)
    fillers = [
        _make_member(
            _mk(
                f"filler-{i}",
                ["normal"],
                moves=["protect", "body-slam", "earthquake", "ice-beam"],
                abilities=["limber"],
                pid=600 + i,
            ),
            item=f"Filler-Item-{i}-Sitrus Berry",
        )
        for i in range(5)
    ]
    # Need 5 distinct filler items that won't collide.
    filler_items = [
        "Sitrus Berry",
        "Lum Berry",
        "Scope Lens",
        "Persim Berry",
        "White Herb",
    ]
    fillers = [
        _make_member(
            _mk(
                f"filler-{i}",
                ["normal"],
                moves=["protect", "body-slam", "earthquake", "ice-beam"],
                abilities=["limber"],
                pid=600 + i,
            ),
            item=item,
        )
        for i, item in enumerate(filler_items)
    ]
    variant = TeamVariant(members=[member, *fillers])
    paste = to_pokepaste(variant)
    # The first block (Gengar) must show Gengarite as the held item.
    first_block = paste.split("\n\n")[0]
    assert "@ Gengarite" in first_block, first_block


def test_pokepaste_mega_species_base_form() -> None:
    """Mega Gengar's species line stays 'Gengar', not 'Gengar-Mega'."""
    p = _mk(
        "gengar",
        ["ghost", "poison"],
        moves=["protect", "shadow-ball", "sludge-bomb", "thunderbolt"],
        abilities=["cursed-body"],
    )
    mega = _mega("gengar-mega", "Gengarite", ["ghost", "poison"])
    member = _make_member(p, item="Gengarite", mega_form=mega)
    fillers = [
        _make_member(
            _mk(
                f"filler-{i}",
                ["normal"],
                moves=["protect", "body-slam", "earthquake", "ice-beam"],
                abilities=["limber"],
                pid=700 + i,
            ),
            item=item,
        )
        for i, item in enumerate(
            ["Sitrus Berry", "Lum Berry", "Scope Lens", "Persim Berry", "White Herb"]
        )
    ]
    variant = TeamVariant(members=[member, *fillers])
    paste = to_pokepaste(variant)
    first_block = paste.split("\n\n")[0]
    # Species line is 'Gengar @ Gengarite' — base species, not '-Mega'.
    assert first_block.startswith("Gengar @ "), first_block
    assert "Gengar-Mega" not in paste
    assert "Mega Gengar" not in paste


# ---------------------------------------------------------------------------
# T9 — CLI flag
# ---------------------------------------------------------------------------


def test_cli_mega_flag_passed_to_generate_team(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The --mega CLI flag forwards as mega_choice= to generate_team."""
    from click.testing import CliRunner

    from pokemon_team_builder.cli import main as cli_main

    captured: dict[str, str] = {}

    anchor = _mk(
        "charizard", ["fire", "flying"], atk=84, spa=109, spe=100, pid=6
    )

    def _spy(anchor, num_variants=3, candidate_loader=None, mega_choice="auto"):
        captured["mega_choice"] = mega_choice
        # Return an empty list — the CLI will fail with a friendly error,
        # but we only care that mega_choice was forwarded correctly.
        return []

    monkeypatch.setattr(
        cli_main.pokemon_lookup, "lookup", lambda _name: anchor
    )
    monkeypatch.setattr(cli_main.team_generator, "generate_team", _spy)

    runner = CliRunner()
    result = runner.invoke(
        cli_main.cli, ["build", "charizard", "--mega", "x"]
    )
    # exit_code != 0 because team_variants == [] — that's expected here.
    assert captured["mega_choice"] == "x", (
        f"mega_choice not forwarded: captured={captured}, output={result.output}"
    )


def test_cli_mega_default_is_auto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When --mega is omitted, generate_team is called with mega_choice='auto'."""
    from click.testing import CliRunner

    from pokemon_team_builder.cli import main as cli_main

    captured: dict[str, str] = {}

    anchor = _mk(
        "charizard", ["fire", "flying"], atk=84, spa=109, spe=100, pid=6
    )

    def _spy(anchor, num_variants=3, candidate_loader=None, mega_choice="auto"):
        captured["mega_choice"] = mega_choice
        return []

    monkeypatch.setattr(
        cli_main.pokemon_lookup, "lookup", lambda _name: anchor
    )
    monkeypatch.setattr(cli_main.team_generator, "generate_team", _spy)

    runner = CliRunner()
    runner.invoke(cli_main.cli, ["build", "charizard"])
    assert captured["mega_choice"] == "auto"
