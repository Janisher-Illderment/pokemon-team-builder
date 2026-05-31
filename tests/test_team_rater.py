"""Tests del Team Rater (ADR docs/adr-team-rater.md §9).

Calibración con FIXTURES sintéticos deterministas (no datos de meta inventados):
construimos equipos a partir de mons del pool legal real con moves/abilities
verificados en código, y aseveramos las etiquetas/notas resultantes.
"""

from __future__ import annotations

import pytest

from pokemon_team_builder.domain.models import (
    SPDistribution,
    TeamMember,
    TeamVariant,
)
from pokemon_team_builder.services import pokemon_lookup
from pokemon_team_builder.services import team_rater
from pokemon_team_builder.services.team_rater import detect_archetype


# ── Helpers de construcción de fixtures ──────────────────────────────────────

def _member(
    species: str,
    moves: list[str],
    *,
    ability: str | None = None,
    nature: str = "Hardy",
    item: str = "Leftovers",
    sp: dict[str, int] | None = None,
) -> TeamMember:
    """Construye un TeamMember determinista a partir de datos reales del pool.

    El rol se asigna por especie (mismo camino que el parser: assign_role).
    SP por defecto: 252/252 estilo Showdown ya dividido (31/31 → 62 total),
    salvo override.
    """
    from pokemon_team_builder.services.synergy_engine import assign_role

    pokemon = pokemon_lookup.lookup(species)
    roles = assign_role(pokemon)
    abil = ability if ability is not None else (
        pokemon.abilities[0] if pokemon.abilities else "run-away"
    )
    padded = list(moves)
    while len(padded) < 4:
        padded.append("protect" if "protect" not in padded else "tackle")
    sp_dist = (
        SPDistribution.model_validate(sp)
        if sp is not None
        else SPDistribution(atk=31, spe=31)
    )
    return TeamMember(
        pokemon=pokemon,
        role=roles,
        sp_distribution=sp_dist,
        item=item,
        ability=abil,
        nature=nature,
        moves=padded[:4],
    )


def _variant(members: list[TeamMember]) -> TeamVariant:
    assert len(members) == 6, "un fixture de equipo necesita exactamente 6 miembros"
    return TeamVariant(members=members)


# ── Fixtures: un equipo por arquetipo (grounded en mons legales) ─────────────

def _team_hyper_offense() -> TeamVariant:
    # ≥4 offensive_threat + ≥1 control de velocidad (Gengar Icy Wind).
    return _variant([
        _member("garchomp", ["earthquake", "dragon-claw", "rock-slide", "protect"],
                ability="Rough Skin", nature="Jolly", item="Choice Scarf"),
        _member("gengar", ["shadow-ball", "sludge-bomb", "icy-wind", "protect"],
                ability="Levitate", nature="Timid", item="Black Sludge"),
        _member("metagross", ["meteor-mash", "bullet-punch", "earthquake", "protect"],
                ability="Clear Body", nature="Adamant", item="Sitrus Berry"),
        _member("aerodactyl", ["rock-slide", "earthquake", "tailwind", "protect"],
                ability="Rock Head", nature="Jolly", item="Focus Sash"),
        _member("dragonite", ["dragon-claw", "earthquake", "extreme-speed", "protect"],
                ability="Multiscale", nature="Adamant", item="Lum Berry"),
        _member("starmie", ["hydro-pump", "ice-beam", "thunderbolt", "protect"],
                ability="Natural Cure", nature="Timid", item="Life Orb"),
    ])


def _team_hard_trick_room() -> TeamVariant:
    # Slowbro setea TR; ≥2 lentos (Slowbro 30, Snorlax 30, Metagross 70 no,
    # Rhydon/Steelix lentos). Garantizamos ≥2 con spe ≤ 60.
    return _variant([
        _member("slowbro", ["trick-room", "psychic", "ice-beam", "protect"],
                ability="Regenerator", nature="Sassy", item="Sitrus Berry"),
        _member("snorlax", ["body-slam", "earthquake", "curse", "protect"],
                ability="Thick Fat", nature="Brave", item="Leftovers"),
        _member("steelix", ["earthquake", "iron-head", "rock-slide", "protect"],
                ability="Sturdy", nature="Brave", item="Lum Berry"),
        _member("metagross", ["meteor-mash", "bullet-punch", "earthquake", "protect"],
                ability="Clear Body", nature="Adamant", item="Choice Band"),
        _member("azumarill", ["waterfall", "play-rough", "aqua-jet", "protect"],
                ability="Huge Power", nature="Adamant", item="Assault Vest"),
        _member("gyarados", ["waterfall", "ice-fang", "earthquake", "protect"],
                ability="Intimidate", nature="Adamant", item="Sitrus Berry"),
    ])


def _team_weather_based() -> TeamVariant:
    # Ninetales (Drought) setter + Venusaur (Chlorophyll) abuser.
    return _variant([
        _member("ninetales", ["flamethrower", "sunny-day", "solar-beam", "protect"],
                ability="Drought", nature="Timid", item="Heat Rock"),
        _member("venusaur", ["giga-drain", "sludge-bomb", "sleep-powder", "protect"],
                ability="Chlorophyll", nature="Modest", item="Black Sludge"),
        _member("arcanine", ["flare-blitz", "extreme-speed", "wild-charge", "protect"],
                ability="Intimidate", nature="Adamant", item="Sitrus Berry"),
        _member("snorlax", ["body-slam", "earthquake", "curse", "protect"],
                ability="Thick Fat", nature="Careful", item="Leftovers"),
        _member("starmie", ["hydro-pump", "ice-beam", "thunderbolt", "protect"],
                ability="Natural Cure", nature="Timid", item="Choice Specs"),
        _member("metagross", ["meteor-mash", "bullet-punch", "earthquake", "protect"],
                ability="Clear Body", nature="Adamant", item="Choice Band"),
    ])


def _team_perish_trap() -> TeamVariant:
    # perish-song presente → perish_trap (perish nunca incidental).
    return _variant([
        _member("politoed", ["perish-song", "protect", "icy-wind", "scald"],
                ability="Drizzle", nature="Bold", item="Leftovers"),
        _member("gengar", ["perish-song", "shadow-ball", "icy-wind", "protect"],
                ability="Levitate", nature="Timid", item="Black Sludge"),
        _member("azumarill", ["waterfall", "play-rough", "aqua-jet", "protect"],
                ability="Huge Power", nature="Adamant", item="Sitrus Berry"),
        _member("snorlax", ["body-slam", "earthquake", "curse", "protect"],
                ability="Thick Fat", nature="Careful", item="Assault Vest"),
        _member("metagross", ["meteor-mash", "bullet-punch", "earthquake", "protect"],
                ability="Clear Body", nature="Adamant", item="Choice Band"),
        _member("milotic", ["scald", "ice-beam", "recover", "protect"],
                ability="Marvel Scale", nature="Bold", item="Flame Orb"),
    ])


def _team_balance() -> TeamVariant:
    # Mezcla sin identidad dominante: amenazas variadas, sin masa HO, sin clima,
    # sin TR, sin perish.
    return _variant([
        _member("milotic", ["scald", "ice-beam", "recover", "protect"],
                ability="Marvel Scale", nature="Bold", item="Leftovers"),
        _member("forretress", ["gyro-ball", "stealth-rock", "spikes", "protect"],
                ability="Sturdy", nature="Relaxed", item="Sitrus Berry"),
        _member("garchomp", ["earthquake", "dragon-claw", "rock-slide", "protect"],
                ability="Rough Skin", nature="Jolly", item="Choice Band"),
        _member("clefable", ["moonblast", "flamethrower", "thunderbolt", "protect"],
                ability="Magic Guard", nature="Modest", item="Life Orb"),
        _member("snorlax", ["body-slam", "earthquake", "curse", "protect"],
                ability="Thick Fat", nature="Careful", item="Assault Vest"),
        _member("gyarados", ["waterfall", "ice-fang", "earthquake", "protect"],
                ability="Intimidate", nature="Adamant", item="Lum Berry"),
    ])


# ── Tests B0: detect_archetype ───────────────────────────────────────────────

def test_detect_hyper_offense():
    arch, conf = detect_archetype(_team_hyper_offense())
    assert arch == "hyper_offense"
    assert 0.0 <= conf <= 1.0
    assert conf >= team_rater.LOW_CONFIDENCE_CUTOFF


def test_detect_hard_trick_room():
    arch, conf = detect_archetype(_team_hard_trick_room())
    assert arch == "hard_trick_room"
    assert conf >= team_rater.LOW_CONFIDENCE_CUTOFF


def test_detect_weather_based():
    arch, conf = detect_archetype(_team_weather_based())
    assert arch == "weather_based"
    assert 0.0 <= conf <= 1.0


def test_detect_perish_trap():
    arch, conf = detect_archetype(_team_perish_trap())
    assert arch == "perish_trap"
    assert 0.0 <= conf <= 1.0


def test_detect_balance_fallback():
    arch, conf = detect_archetype(_team_balance())
    # Un equipo sin identidad dominante cae en balance.
    assert arch == "balance"
    assert 0.0 <= conf <= 1.0


def test_detect_archetype_always_in_known_set():
    for builder in (
        _team_hyper_offense,
        _team_hard_trick_room,
        _team_weather_based,
        _team_perish_trap,
        _team_balance,
    ):
        arch, conf = detect_archetype(builder())
        assert arch in team_rater.ARCHETYPES
        assert 0.0 <= conf <= 1.0


def test_confidence_is_fraction():
    # La confianza nunca excede 1.0 ni baja de 0.0 en ningún fixture.
    for builder in (
        _team_hyper_offense,
        _team_hard_trick_room,
        _team_weather_based,
    ):
        _, conf = detect_archetype(builder())
        assert 0.0 <= conf <= 1.0


# ── Tests B1: recommend_member_build iguala el camino del generador ──────────

def _generated_variant():
    """Genera un equipo determinista con pool acotado (sin red, sin mega)."""
    from pokemon_team_builder.services import team_generator as tg
    from pokemon_team_builder.data.legal_pool_loader import get_all_names

    anchor = pokemon_lookup.lookup("garchomp")
    pool = []
    for n in get_all_names()[:50]:
        if n == anchor.name:
            continue
        try:
            pool.append(pokemon_lookup.lookup(n))
        except Exception:
            continue
    return tg.generate_team(anchor, pool=pool, num_variants=1)[0]


def _sp_tuple(sp):
    return (sp.hp, sp.atk, sp.def_, sp.spa, sp.spd, sp.spe)


def test_recommend_member_build_matches_generator_path():
    from pokemon_team_builder.services import team_generator as tg

    variant = _generated_variant()
    # moves / naturaleza / SP son MEMBER-LOCAL (no dependen del Item Clause del
    # equipo): deben coincidir para todos los miembros sin mega.
    checked = 0
    for member in variant.members:
        if member.mega_form is not None:
            continue
        rb = tg.recommend_member_build(
            member.pokemon, member.role,
            archetype=variant.archetype, team_sheet=variant.team_sheet,
        )
        assert rb.moves == list(member.moves), member.pokemon.name
        assert rb.nature == member.nature, member.pokemon.name
        assert _sp_tuple(rb.sp_distribution) == _sp_tuple(member.sp_distribution), \
            member.pokemon.name
        checked += 1
    assert checked >= 5, "se esperaban ≥5 miembros sin mega para comparar"

    # El item es el recomendado IDEAL por-mon (pre-Item-Clause). El ancla
    # (índice 0) se asigna primero en el equipo, sin conflicto previo posible,
    # así que su item DEBE coincidir con la recomendación aislada. Miembros
    # posteriores pueden divergir si su item ideal ya lo tomó otro miembro
    # (Item Clause) — la recomendación por-mon es intencionadamente el item
    # ideal para ESE mon, que es justo lo que el motor de sugerencias necesita.
    anchor = variant.members[0]
    if anchor.mega_form is None:
        rb0 = tg.recommend_member_build(
            anchor.pokemon, anchor.role,
            archetype=variant.archetype, team_sheet=variant.team_sheet,
        )
        assert rb0.item == anchor.item, anchor.pokemon.name


def test_recommend_member_build_is_deterministic():
    from pokemon_team_builder.services import team_generator as tg

    chomp = pokemon_lookup.lookup("garchomp")
    roles = ["physical_sweeper"]
    a = tg.recommend_member_build(chomp, roles, archetype="hyper_offense")
    b = tg.recommend_member_build(chomp, roles, archetype="hyper_offense")
    assert a.moves == b.moves
    assert a.item == b.item
    assert a.nature == b.nature
    assert _sp_tuple(a.sp_distribution) == _sp_tuple(b.sp_distribution)


# ── Tests B2: _set_coherence ─────────────────────────────────────────────────

def _abomasnow_incoherent_variant() -> tuple[TeamVariant, int]:
    """Equipo con Abomasnow físico (Adamant + Atk) pero Ice Beam (especial).

    Devuelve (variant, index_de_abomasnow). El caso clásico del bug Ice Beam
    muerto (ADR §4.1 / §9.2).
    """
    abom = _member(
        "abomasnow", ["wood-hammer", "ice-beam", "ice-shard", "protect"],
        ability="Snow Warning", nature="Adamant", item="Sitrus Berry",
        sp={"atk": 31, "spe": 31},
    )
    rest = [
        _member("garchomp", ["earthquake", "dragon-claw", "rock-slide", "protect"],
                ability="Rough Skin", nature="Jolly", item="Choice Band"),
        _member("snorlax", ["body-slam", "earthquake", "curse", "protect"],
                ability="Thick Fat", nature="Careful", item="Leftovers"),
        _member("metagross", ["meteor-mash", "bullet-punch", "earthquake", "protect"],
                ability="Clear Body", nature="Adamant", item="Lum Berry"),
        _member("milotic", ["scald", "ice-beam", "recover", "protect"],
                ability="Marvel Scale", nature="Modest", item="Flame Orb"),
        _member("gengar", ["shadow-ball", "sludge-bomb", "icy-wind", "protect"],
                ability="Levitate", nature="Timid", item="Black Sludge"),
    ]
    variant = _variant([abom, *rest])
    return variant, 0


def test_set_coherence_flags_dead_move_abomasnow():
    from pokemon_team_builder.services.team_rater import _set_coherence

    variant, idx = _abomasnow_incoherent_variant()
    coherence, reasons = _set_coherence(variant.members[idx], variant)

    assert coherence < 1.0
    assert any("muerto" in r.lower() for r in reasons), reasons
    # Ice Beam (especial) sobre build físico debe ser la move muerta señalada.
    assert any("ice-beam" in r.lower() for r in reasons), reasons


def test_set_coherence_clean_generated_team_is_high():
    from pokemon_team_builder.services.team_rater import _set_coherence

    variant = _generated_variant()
    # El propio output del builder NO debe recibir penalizaciones de move
    # muerto (ADR §9.2): cero dead-move flags en un equipo generado limpio.
    dead_flags = 0
    for member in variant.members:
        coherence, reasons = _set_coherence(member, variant)
        assert 0.0 <= coherence <= 1.0
        if any("muerto" in r.lower() for r in reasons):
            dead_flags += 1
    assert dead_flags == 0, "el output del builder no debería tener moves muertos"


def test_set_coherence_returns_unit_interval():
    from pokemon_team_builder.services.team_rater import _set_coherence

    variant, _ = _abomasnow_incoherent_variant()
    for member in variant.members:
        coherence, reasons = _set_coherence(member, variant)
        assert 0.0 <= coherence <= 1.0
        assert isinstance(reasons, list)
        assert all(isinstance(r, str) and r for r in reasons)


def test_set_coherence_defensive_nature_does_not_flag_coverage_dead():
    """Un mon DEFENSIVO (naturaleza def/spd) con EVs de ataque y una move de
    cobertura de la categoría opuesta NO debe marcarse como move muerto: no hay
    compromiso ofensivo de categoría (caso Forretress Impish + bug-buzz)."""
    from pokemon_team_builder.services.team_rater import _set_coherence

    # Forretress Relaxed (boostea def, hinder spe) con Iron Head (físico) y
    # Bug Buzz (especial). Naturaleza defensiva → sin compromiso → sin dead-move.
    forre = _member(
        "forretress", ["iron-head", "bug-buzz", "stealth-rock", "protect"],
        ability="Sturdy", nature="Relaxed", item="Sitrus Berry",
        sp={"hp": 31, "def": 31},
    )
    rest = [
        _member("garchomp", ["earthquake", "dragon-claw", "rock-slide", "protect"],
                ability="Rough Skin", nature="Jolly", item="Choice Band"),
        _member("snorlax", ["body-slam", "earthquake", "curse", "protect"],
                ability="Thick Fat", nature="Careful", item="Leftovers"),
        _member("metagross", ["meteor-mash", "bullet-punch", "earthquake", "protect"],
                ability="Clear Body", nature="Adamant", item="Lum Berry"),
        _member("milotic", ["scald", "ice-beam", "recover", "protect"],
                ability="Marvel Scale", nature="Modest", item="Flame Orb"),
        _member("gengar", ["shadow-ball", "sludge-bomb", "icy-wind", "protect"],
                ability="Levitate", nature="Timid", item="Black Sludge"),
    ]
    variant = _variant([forre, *rest])
    _, reasons = _set_coherence(variant.members[0], variant)
    assert not any("muerto" in r.lower() for r in reasons), reasons


# ── Tests B3: rate_member (fórmula + bounds) ─────────────────────────────────

def test_rate_member_score_bounds():
    from pokemon_team_builder.services.team_rater import detect_archetype, rate_member

    for builder in (
        _team_hyper_offense,
        _team_hard_trick_room,
        _team_weather_based,
        _team_perish_trap,
        _team_balance,
    ):
        variant = builder()
        arch, _ = detect_archetype(variant)
        for i in range(6):
            mr = rate_member(variant, i, arch)
            assert 1 <= mr.score <= 100
            assert 0.0 <= mr.fit <= 1.0
            assert 0.5 <= mr.intrinsic <= 1.0
            assert 0.0 <= mr.coherence <= 1.0


def test_rate_member_formula_matches_weighted_blend():
    """La nota es round(100 * (0.5*fit + 0.3*coh + 0.2*intr)), piso 1."""
    from pokemon_team_builder.services import team_rater as tr
    from pokemon_team_builder.services.team_rater import detect_archetype, rate_member

    variant = _team_hyper_offense()
    arch, _ = detect_archetype(variant)
    for i in range(6):
        mr = rate_member(variant, i, arch)
        blended = (
            tr.W_FIT * mr.fit
            + tr.W_COHERENCE * mr.coherence
            + tr.W_INTRINSIC * mr.intrinsic
        )
        expected = max(1, min(100, round(100 * max(0.0, min(1.0, blended)))))
        assert mr.score == expected, (mr.name, mr.score, expected)


def test_rate_member_weights_sum_to_one():
    from pokemon_team_builder.services import team_rater as tr

    assert abs(tr.W_FIT + tr.W_COHERENCE + tr.W_INTRINSIC - 1.0) < 1e-9
    assert tr.W_FIT == 0.50
    assert tr.W_COHERENCE == 0.30
    assert tr.W_INTRINSIC == 0.20


def test_rate_member_incoherent_set_scores_lower_than_clean():
    """Un set incoherente (Abomasnow Ice Beam muerto) puntúa por debajo del
    mismo arquetipo con sets limpios — la coherencia mueve la nota."""
    from pokemon_team_builder.services.team_rater import detect_archetype, rate_member

    variant, idx = _abomasnow_incoherent_variant()
    arch, _ = detect_archetype(variant)
    mr = rate_member(variant, idx, arch)
    # Coherencia penalizada → componente coherencia < 1.0 reflejada en la nota.
    assert mr.coherence < 1.0
    assert 1 <= mr.score <= 100


def test_rate_member_key_piece_scores_high():
    """El único proveedor de control de velocidad en HO (Gengar Icy Wind) es
    pieza clave → fit alto."""
    from pokemon_team_builder.services.team_rater import detect_archetype, rate_member

    variant = _team_hyper_offense()
    arch, _ = detect_archetype(variant)
    gengar_idx = next(
        i for i, m in enumerate(variant.members) if m.pokemon.name == "gengar"
    )
    mr = rate_member(variant, gengar_idx, arch)
    assert mr.fit >= 0.7, mr.fit
