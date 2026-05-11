from __future__ import annotations

import pytest
from unittest.mock import patch

from pokemon_team_builder.config import MAX_SP_STAT, MAX_SP_TOTAL
from pokemon_team_builder.domain.models import (
    BaseStats,
    MegaForm,
    PokemonData,
    SPDistribution,
)
from pokemon_team_builder.services.pokepaste_parser import (
    _evs_to_sps,
    parse_pokepaste,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mk_poke(
    name: str,
    moves: list[str] | None = None,
    abilities: list[str] | None = None,
    pid: int = 1,
) -> PokemonData:
    return PokemonData(
        id=pid,
        name=name,
        types=["normal"],
        base_stats=BaseStats(hp=80, atk=80, **{"def": 80}, spa=80, spd=80, spe=80),
        move_names=moves or [
            "tackle", "protect", "earthquake", "ice-beam",
            "flamethrower", "thunderbolt", "rock-slide", "surf",
            "shadow-ball", "dragon-claw",
        ],
        abilities=abilities or ["pressure"],
        weaknesses={},
    )


def _mk_mega(form_id: str, stone: str) -> MegaForm:
    return MegaForm(
        form_id=form_id,
        mega_stone=stone,
        types=["fire", "dragon"],
        ability="tough-claws",
        stats=BaseStats(hp=78, atk=130, **{"def": 111}, spa=130, spd=85, spe=100),
    )


_NAMES_6 = ["venusaur", "charizard", "blastoise", "pikachu", "gengar", "machamp"]


def _six_paste(names: list[str] | None = None, eol: str = "\n") -> str:
    """Build a minimal 6-block PokePaste with the given species names."""
    ns = names or _NAMES_6
    blocks = []
    for n in ns:
        display = n.replace("-", " ").title().replace(" ", "-")
        blocks.append(
            f"{display} @ Sitrus Berry{eol}"
            f"Ability: Pressure{eol}"
            f"EVs: 252 Atk / 4 HP / 252 Spe{eol}"
            f"Jolly Nature{eol}"
            f"- Tackle{eol}"
            f"- Protect{eol}"
            f"- Earthquake{eol}"
            f"- Ice-Beam{eol}"
        )
    return (eol + eol).join(blocks)


def _make_lookup(names: list[str]):
    pokes = {n: _mk_poke(n, pid=i + 1) for i, n in enumerate(names)}

    def _lookup(slug: str) -> PokemonData:
        if slug not in pokes:
            raise ValueError(f"Unknown: {slug}")
        return pokes[slug]

    return _lookup


def _parse(
    text: str,
    names: list[str] | None = None,
    legal_fn=None,
    mega_fn=None,
    extra_pokes: dict[str, PokemonData] | None = None,
):
    """Invoke parse_pokepaste with all external deps mocked."""
    ns = names or _NAMES_6
    base_lookup = _make_lookup(ns)

    def _lookup(slug: str) -> PokemonData:
        if extra_pokes and slug in extra_pokes:
            return extra_pokes[slug]
        return base_lookup(slug)

    _legal = legal_fn or (lambda _: True)
    _megas = mega_fn or (lambda: {})

    with (
        patch("pokemon_team_builder.services.pokepaste_parser.pokemon_lookup.lookup", side_effect=_lookup),
        patch("pokemon_team_builder.services.pokepaste_parser.is_legal", side_effect=_legal),
        patch("pokemon_team_builder.services.pokepaste_parser.load_mega_evolutions", side_effect=_megas),
        patch("pokemon_team_builder.services.pokepaste_parser.assign_role", return_value=["physical_sweeper"]),
    ):
        return parse_pokepaste(text)


# ---------------------------------------------------------------------------
# 1. Standard block
# ---------------------------------------------------------------------------

def test_standard_six_block_parses_successfully():
    variant, warnings = _parse(_six_paste())
    assert len(variant.members) == 6
    assert variant.members[0].pokemon.name == "venusaur"
    assert variant.members[0].item == "Sitrus Berry"
    assert variant.members[0].nature == "Jolly"
    assert variant.members[0].ability == "Pressure"


# ---------------------------------------------------------------------------
# 2. Altered metadata order
# ---------------------------------------------------------------------------

def test_metadata_any_order_parsed():
    """Nature before EVs, Ability last — parser must handle any order."""
    block = (
        "Venusaur @ Lum Berry\n"
        "Jolly Nature\n"
        "EVs: 4 HP / 252 Atk / 252 Spe\n"
        "Ability: Pressure\n"
        "- Tackle\n- Protect\n- Earthquake\n- Ice-Beam\n"
    )
    filler = (
        "Charizard @ Lum Berry\nAbility: Pressure\nJolly Nature\n"
        "- Tackle\n- Protect\n- Earthquake\n- Ice-Beam\n"
    )
    paste = block + "\n\n" + "\n\n".join(filler for _ in range(5)).replace(
        "Charizard", {1: "Blastoise", 2: "Pikachu", 3: "Gengar", 4: "Machamp", 5: "Arcanine"}
        .get(1, "Blastoise")
    )

    names_used = ["venusaur", "charizard", "blastoise", "pikachu", "gengar", "machamp"]
    filler_blocks = "\n\n".join(
        f"{n.title()} @ Lum Berry\nAbility: Pressure\nJolly Nature\n"
        f"- Tackle\n- Protect\n- Earthquake\n- Ice-Beam"
        for n in names_used[1:]
    )
    paste = block + "\n\n" + filler_blocks

    variant, _ = _parse(paste, names=names_used)
    m0 = variant.members[0]
    assert m0.nature == "Jolly"
    assert m0.ability == "Pressure"
    assert m0.sp_distribution.atk == 252 // 8
    assert m0.sp_distribution.spe == 252 // 8


# ---------------------------------------------------------------------------
# 3. CRLF line endings
# ---------------------------------------------------------------------------

def test_crlf_line_endings_parsed():
    text = _six_paste(eol="\r\n")
    variant, warnings = _parse(text)
    assert len(variant.members) == 6


# ---------------------------------------------------------------------------
# 4. Extra blank lines between blocks
# ---------------------------------------------------------------------------

def test_multiple_blank_lines_between_blocks():
    """Two or more blank lines between blocks must still parse to 6 members."""
    text = _six_paste().replace("\n\n", "\n\n\n\n")
    variant, warnings = _parse(text)
    assert len(variant.members) == 6


# ---------------------------------------------------------------------------
# 5. Standard EVs: 252/252/4
# ---------------------------------------------------------------------------

def test_evs_252_252_4_conversion():
    sp, warns = _evs_to_sps("252 Atk / 4 HP / 252 Spe")
    assert sp.atk == 252 // 8      # 31
    assert sp.spe == 252 // 8      # 31
    assert sp.hp == 0               # 4 // 8 = 0
    assert sp.atk + sp.spe + sp.hp <= MAX_SP_TOTAL
    assert not warns


# ---------------------------------------------------------------------------
# 6. No EVs → fallback al spread sugerido por rol + warning
# ---------------------------------------------------------------------------

def test_no_evs_falls_back_to_role_template_with_warning():
    """Paste sin línea EVs → suggest_sp_distribution + warning informativo."""
    block = (
        "Venusaur @ Sitrus Berry\n"
        "Ability: Pressure\n"
        "Jolly Nature\n"
        "- Tackle\n- Protect\n- Earthquake\n- Ice-Beam\n"
    )
    filler_blocks = "\n\n".join(
        f"{n.title()} @ Sitrus Berry\nAbility: Pressure\nJolly Nature\n"
        f"- Tackle\n- Protect\n- Earthquake\n- Ice-Beam"
        for n in _NAMES_6[1:]
    )
    paste = block + "\n\n" + filler_blocks

    variant, warns = _parse(paste)
    sp = variant.members[0].sp_distribution
    # Spread sugerido no debe ser todo cero
    assert sp != SPDistribution()
    assert sp.hp + sp.atk + sp.def_ + sp.spa + sp.spd + sp.spe > 0
    # Warning informativo presente para el primer miembro
    assert any("paste sin EVs" in w for w in warns)


# ---------------------------------------------------------------------------
# 7. EVs > 256 clamped with warning
# ---------------------------------------------------------------------------

def test_evs_above_256_clamped_to_max_sp_stat():
    sp, warns = _evs_to_sps("300 Atk / 4 HP / 252 Spe")
    assert sp.atk == MAX_SP_STAT       # clamped: 256 // 8 = 32
    assert len(warns) == 1
    assert "300" in warns[0]


# ---------------------------------------------------------------------------
# 8. Mega detection — Mega-X variant
# ---------------------------------------------------------------------------

def test_mega_x_form_detected_and_stone_set():
    mega_x = _mk_mega("charizard-mega-x", "Charizardite X")
    mega_y = _mk_mega("charizard-mega-y", "Charizardite Y")
    mega_map = {"charizard": [mega_x, mega_y]}

    # filler must not include "charizard" (Species Clause)
    filler_names = ["venusaur", "blastoise", "pikachu", "gengar", "machamp"]
    filler_blocks = "\n\n".join(
        f"{n.title()} @ Sitrus Berry\nAbility: Pressure\nJolly Nature\n"
        f"- Tackle\n- Protect\n- Earthquake\n- Ice-Beam"
        for n in filler_names
    )
    paste = (
        "Charizard-Mega-X @ Charizardite X\n"
        "Ability: Tough-Claws\n"
        "Jolly Nature\n"
        "- Tackle\n- Protect\n- Earthquake\n- Ice-Beam\n"
        "\n\n" + filler_blocks
    )
    charizard_poke = _mk_poke("charizard", pid=10)
    all_names = ["charizard"] + filler_names

    variant, warnings = _parse(
        paste,
        names=all_names,
        mega_fn=lambda: mega_map,
        extra_pokes={"charizard": charizard_poke},
    )
    m0 = variant.members[0]
    assert m0.mega_form is not None
    assert m0.mega_form.form_id == "charizard-mega-x"
    assert m0.item == "Charizardite X"


# ---------------------------------------------------------------------------
# 9. Mega detection — base Mega (no X/Y suffix)
# ---------------------------------------------------------------------------

def test_mega_base_form_uses_first_mega():
    mega = _mk_mega("garchomp-mega", "Garchompite")
    mega_map = {"garchomp": [mega]}

    filler_blocks = "\n\n".join(
        f"{n.title()} @ Sitrus Berry\nAbility: Pressure\nJolly Nature\n"
        f"- Tackle\n- Protect\n- Earthquake\n- Ice-Beam"
        for n in _NAMES_6[1:]
    )
    paste = (
        "Garchomp-Mega @ Garchompite\n"
        "Ability: Sand-Force\n"
        "Jolly Nature\n"
        "- Tackle\n- Protect\n- Earthquake\n- Ice-Beam\n"
        "\n\n" + filler_blocks
    )
    garchomp_poke = _mk_poke("garchomp", pid=99)
    names_in_paste = ["garchomp"] + _NAMES_6[1:]

    variant, _ = _parse(
        paste,
        names=names_in_paste,
        mega_fn=lambda: mega_map,
        extra_pokes={"garchomp": garchomp_poke},
    )
    m0 = variant.members[0]
    assert m0.mega_form is not None
    assert m0.mega_form.form_id == "garchomp-mega"
    assert m0.item == "Garchompite"


# ---------------------------------------------------------------------------
# 10. Move outside pool — warning, not error
# ---------------------------------------------------------------------------

def test_move_outside_pool_produces_warning():
    block = (
        "Venusaur @ Sitrus Berry\n"
        "Ability: Pressure\n"
        "Jolly Nature\n"
        "- Tackle\n- Protect\n- Earthquake\n- Psychic\n"  # Psychic not in default pool
    )
    filler_blocks = "\n\n".join(
        f"{n.title()} @ Sitrus Berry\nAbility: Pressure\nJolly Nature\n"
        f"- Tackle\n- Protect\n- Earthquake\n- Ice-Beam"
        for n in _NAMES_6[1:]
    )
    paste = block + "\n\n" + filler_blocks

    # venusaur's move pool does NOT include "psychic"
    venusaur = _mk_poke("venusaur", moves=["tackle", "protect", "earthquake", "ice-beam"])
    variant, warnings = _parse(paste, extra_pokes={"venusaur": venusaur})

    assert len(variant.members[0].moves) == 4
    assert "psychic" in variant.members[0].moves
    assert any("psychic" in w for w in warnings)


# ---------------------------------------------------------------------------
# 11. Less than 4 moves — padded with tackle + warning
# ---------------------------------------------------------------------------

def test_fewer_than_4_moves_padded_with_tackle():
    block = (
        "Venusaur @ Sitrus Berry\n"
        "Ability: Pressure\n"
        "Jolly Nature\n"
        "- Tackle\n- Protect\n"  # only 2 moves
    )
    filler_blocks = "\n\n".join(
        f"{n.title()} @ Sitrus Berry\nAbility: Pressure\nJolly Nature\n"
        f"- Tackle\n- Protect\n- Earthquake\n- Ice-Beam"
        for n in _NAMES_6[1:]
    )
    paste = block + "\n\n" + filler_blocks

    variant, warnings = _parse(paste)
    moves = variant.members[0].moves
    assert len(moves) == 4
    assert moves.count("tackle") >= 2     # padded with tackle
    assert any("tackle" in w.lower() for w in warnings)


# ---------------------------------------------------------------------------
# 12. 5 members → ValueError
# ---------------------------------------------------------------------------

def test_five_members_raises_value_error():
    paste = _six_paste(names=_NAMES_6[:5])
    with pytest.raises(ValueError, match="5"):
        _parse(paste, names=_NAMES_6[:5])


# ---------------------------------------------------------------------------
# 13. 7 members → ValueError
# ---------------------------------------------------------------------------

def test_seven_members_raises_value_error():
    extra = _NAMES_6 + ["arcanine"]
    paste = _six_paste(names=extra)
    with pytest.raises(ValueError, match="7"):
        _parse(paste, names=extra)


# ---------------------------------------------------------------------------
# 14. Illegal Pokémon → ValueError
# ---------------------------------------------------------------------------

def test_illegal_pokemon_raises_value_error():
    paste = _six_paste()

    def _legal(name: str) -> bool:
        return name != "venusaur"  # first in paste is illegal

    with pytest.raises(ValueError, match="venusaur"):
        _parse(paste, legal_fn=_legal)


# ---------------------------------------------------------------------------
# 15. Duplicate species → ValueError (Species Clause)
# ---------------------------------------------------------------------------

def test_duplicate_species_raises_value_error():
    # Use same name in two slots
    names_with_dup = ["venusaur", "charizard", "venusaur", "pikachu", "gengar", "machamp"]
    paste = _six_paste(names=names_with_dup)

    with pytest.raises(ValueError, match="(?i)species|venusaur"):
        _parse(paste, names=names_with_dup)
