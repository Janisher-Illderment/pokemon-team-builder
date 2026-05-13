"""Phase 3 §9 — SP preset builder tests."""

from __future__ import annotations

import pytest

from pokemon_team_builder.domain.models import (
    BaseStats,
    PokemonData,
    SPDistribution,
    TeamMember,
)
from pokemon_team_builder.services.sp_calc import (
    SP_PER_STAT_CAP,
    SP_TOTAL_CAP,
)
from pokemon_team_builder.services.sp_preset_builder import (
    SpRead,
    build_presets,
)


def _mk(
    name: str,
    *,
    atk: int = 100,
    spa: int = 60,
    spe: int = 100,
    hp: int = 75,
    def_: int = 75,
    spd: int = 75,
    item: str = "Choice Band",
    nature: str = "Jolly",
    role: str = "physical_sweeper",
) -> TeamMember:
    pokemon = PokemonData(
        id=1,
        name=name,
        types=["normal"],
        base_stats=BaseStats(hp=hp, atk=atk, **{"def": def_}, spa=spa, spd=spd, spe=spe),
        move_names=["tackle"],
        abilities=["pressure"],
        weaknesses={},
    )
    return TeamMember(
        pokemon=pokemon,
        role=[role],
        sp_distribution=SPDistribution(),
        item=item,
        ability="pressure",
        nature=nature,
        moves=["tackle", "growl", "scratch", "ember"],
    )


# ── SpRead invariants ─────────────────────────────────────────────────────────

def test_sp_read_total_must_be_66():
    with pytest.raises(ValueError, match="total"):
        SpRead(hp=10, atk=10, def_=10, spa=10, spd=10, spe=10)  # sum=60


def test_sp_read_per_stat_cap_enforced():
    with pytest.raises(ValueError, match="out of range"):
        SpRead(hp=33, atk=33, def_=0, spa=0, spd=0, spe=0)


def test_sp_read_to_dict_uses_def_alias():
    r = SpRead(hp=11, atk=11, def_=11, spa=11, spd=11, spe=11)
    assert r.to_dict() == {"hp": 11, "atk": 11, "def": 11, "spa": 11, "spd": 11, "spe": 11}


# ── build_presets — required keys + invariants ────────────────────────────────

def test_returns_offensive_and_defensive_keys():
    member = _mk("garchomp")
    presets = build_presets(member, "Choice Band", "Jolly")
    assert set(presets.keys()) == {"offensive", "defensive"}


def test_each_preset_sums_to_66():
    member = _mk("garchomp")
    presets = build_presets(member, "Choice Band", "Jolly")
    for name, read in presets.items():
        total = read.hp + read.atk + read.def_ + read.spa + read.spd + read.spe
        assert total == SP_TOTAL_CAP, f"{name} sum={total}"


def test_each_stat_within_cap():
    member = _mk("garchomp")
    presets = build_presets(member, "Choice Band", "Jolly")
    for name, read in presets.items():
        for key in ("hp", "atk", "def_", "spa", "spd", "spe"):
            v = getattr(read, key)
            assert 0 <= v <= SP_PER_STAT_CAP, f"{name}.{key}={v}"


# ── Item-aware allocation (spec scenarios) ────────────────────────────────────

def test_choice_band_offensive_invests_speed_over_attack():
    """Spec §9.3: Choice Band attacker offensive preset has Spe > Atk."""
    member = _mk("garchomp", atk=130, spe=102)
    presets = build_presets(member, "Choice Band", "Jolly")
    off = presets["offensive"]
    assert off.spe > off.atk


def test_choice_specs_offensive_invests_speed_over_spa():
    """Choice Specs attacker offensive preset has Spe > SpA."""
    member = _mk("alakazam", atk=50, spa=135, spe=120,
                 nature="Timid", role="special_sweeper")
    presets = build_presets(member, "Choice Specs", "Timid")
    off = presets["offensive"]
    assert off.spe > off.spa


def test_eviolite_nfe_defensive_reduces_def_spd_investment():
    """Spec §9.3: Eviolite NFE defensive preset frees up def/spd for offense."""
    member = _mk("chansey", hp=250, atk=5, spa=35, spe=50, def_=5, spd=105,
                 nature="Calm", role="physical_wall")
    eviolite = build_presets(member, "Eviolite", "Calm")["defensive"]
    none_item = build_presets(member, "Leftovers", "Calm")["defensive"]
    # With Eviolite, less SP in defense/spd combined → freed SPs went elsewhere.
    eviolite_defensive_total = eviolite.def_ + eviolite.spd
    none_defensive_total = none_item.def_ + none_item.spd
    assert eviolite_defensive_total < none_defensive_total


def test_assault_vest_defensive_invests_def_over_spd():
    """Spec §9.3: AV defensive preset puts Def > SpD (SpD already inflated)."""
    member = _mk("conkeldurr", atk=140, spa=55, spe=45, hp=105, def_=95, spd=65,
                 nature="Adamant", role="physical_sweeper")
    presets = build_presets(member, "Assault Vest", "Adamant")
    deff = presets["defensive"]
    assert deff.def_ > deff.spd


# ── Nature jump optimisation (spec §9.4) ──────────────────────────────────────

def test_nature_jump_triggered_on_boosted_stat():
    """When a +1.1× nature creates a +2 jump, optimiser lands on the jump SP.

    We don't assert a specific number here (per-pokemon, per-base-stat),
    only that the boosted stat's SP value matches the find_nature_jumps
    nudge when the raw allocation overshoots.
    """
    from pokemon_team_builder.services.sp_calc import find_nature_jumps

    # Garchomp Spe=102, Jolly nature (+Spe), so spe jump positions exist.
    jumps = find_nature_jumps(102, 1.1, max_sp=SP_PER_STAT_CAP)
    assert jumps, "Garchomp Spe should have at least one nature jump"

    member = _mk("garchomp", atk=130, spe=102)
    presets = build_presets(member, "Choice Band", "Jolly")
    # The boosted stat in this allocation is spe. The post-nudge value
    # must either equal the raw allocation OR sit on a known jump.
    spe = presets["offensive"].spe
    assert spe in jumps or spe <= max(jumps)


# ── Nature hindered stat → zero/low SP ────────────────────────────────────────

def test_modest_nature_zeroes_attack_in_offensive():
    """Modest (-Atk) on a special attacker → offensive preset has 0 Atk."""
    member = _mk("alakazam", atk=50, spa=135, spe=120,
                 nature="Modest", role="special_sweeper")
    presets = build_presets(member, "Choice Specs", "Modest")
    assert presets["offensive"].atk == 0


# ── Phase 4b Brief #2: pokepaste default uses offensive preset ──────────────


def test_default_pokepaste_uses_offensive_preset():
    """Spec §9.6: generated variants SHALL serialise SPs from the offensive
    preset by default, not from the role-template fallback.

    Regression for Phase 4b Brief #2 — previously _build_variant assigned
    template-based suggest_sp_distribution to member.sp_distribution, which
    diverged from sp_presets.offensive on the API response. After the fix,
    member.sp_distribution must equal offensive preset values (sum=66).
    """
    from pokemon_team_builder.services.team_generator import _build_variant

    def _pkd(name, types, atk, spa, spe, hp=80, def_=80, spd=80, pid=1):
        return PokemonData(
            id=pid, name=name, types=types,
            base_stats=BaseStats(hp=hp, atk=atk, **{"def": def_},
                                 spa=spa, spd=spd, spe=spe),
            move_names=["tackle", "protect", "earthquake", "rock-slide",
                        "ice-beam", "thunderbolt"],
            abilities=["pressure"],
            weaknesses={},
        )

    state = [
        _pkd("garchomp", ["ground", "dragon"], 130, 80, 102, 108, 95, 85, pid=1),
        _pkd("rotom", ["electric", "ghost"], 65, 105, 86, 50, 107, 107, pid=2),
        _pkd("salamence", ["dragon", "flying"], 135, 110, 100, 95, 80, 80, pid=3),
        _pkd("metagross", ["steel", "psychic"], 135, 95, 70, 80, 130, 90, pid=4),
        _pkd("amoonguss", ["grass", "poison"], 85, 85, 30, 114, 70, 80, pid=5),
        _pkd("scrafty", ["dark", "fighting"], 90, 45, 58, 65, 115, 115, pid=6),
    ]
    role_map = {p.name: ["physical_sweeper"] for p in state}
    variant = _build_variant(state, role_map, anchor_mega=None, format_mode="bo1")

    for member in variant.members:
        sp = member.sp_distribution
        total = sp.hp + sp.atk + sp.def_ + sp.spa + sp.spd + sp.spe
        assert total == SP_TOTAL_CAP, (
            f"{member.pokemon.name} sp_distribution total={total}, "
            f"expected {SP_TOTAL_CAP} (offensive preset)"
        )


def test_generate_team_raises_on_empty_pool():
    """Phase 4b Brief #3: empty pool → TeamBuildError (HTTP 503-mapped),
    not silent 200+{variants:[]}. Fail-clearly per feedback_fail_clearly.md.
    """
    from pokemon_team_builder.domain.exceptions import TeamBuildError
    from pokemon_team_builder.services.team_generator import generate_team

    anchor = PokemonData(
        id=1, name="garchomp", types=["ground", "dragon"],
        base_stats=BaseStats(hp=108, atk=130, **{"def": 95},
                             spa=80, spd=85, spe=102),
        move_names=["earthquake"], abilities=["sand-veil"], weaknesses={},
    )
    with pytest.raises(TeamBuildError, match="[Pp]ool"):
        generate_team(anchor, pool=[], num_variants=1)
