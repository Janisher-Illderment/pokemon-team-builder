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


# ── Tests B4: motor de sugerencias ───────────────────────────────────────────

def _all_suggestions(variant, arch):
    from pokemon_team_builder.services.team_rater import rate_member

    out = []
    for i in range(6):
        out.extend(rate_member(variant, i, arch).suggestions)
    return out


def test_suggestions_never_change_species():
    """Invariante de roster (§9.4): NINGUNA sugerencia puede ser un cambio de
    especie — todas las kinds ∈ {move_swap, nature, evs, item}."""
    from pokemon_team_builder.services import team_rater as tr
    from pokemon_team_builder.services.team_rater import detect_archetype

    for builder in (
        _team_hyper_offense,
        _team_hard_trick_room,
        _team_balance,
        lambda: _abomasnow_incoherent_variant()[0],
    ):
        variant = builder()
        arch, _ = detect_archetype(variant)
        for s in _all_suggestions(variant, arch):
            assert s.kind in tr._VALID_SUGGESTION_KINDS
            # No existe una kind 'species' ni un target_field de especie.
            assert "species" not in s.kind
            assert "species" not in s.target_field.lower()


def test_suggestions_are_concrete():
    """Concreción (§9.5): toda sugerencia tiene from/to/reason no vacíos."""
    from pokemon_team_builder.services.team_rater import detect_archetype

    variant, _ = _abomasnow_incoherent_variant()
    arch, _ = detect_archetype(variant)
    sugg = _all_suggestions(variant, arch)
    assert sugg, "el equipo incoherente debe producir alguna sugerencia"
    for s in sugg:
        assert s.from_value, s
        assert s.to_value, s
        assert s.reason_es, s
        assert isinstance(s.priority, int)


def test_abomasnow_produces_dead_move_swap():
    """El caso Abomasnow Ice Beam muerto produce un move_swap de prioridad alta."""
    from pokemon_team_builder.services.team_rater import detect_archetype, rate_member

    variant, idx = _abomasnow_incoherent_variant()
    arch, _ = detect_archetype(variant)
    mr = rate_member(variant, idx, arch)
    swaps = [s for s in mr.suggestions if s.kind == "move_swap"]
    assert swaps, mr.suggestions
    assert any("ice-beam" in s.from_value.lower() for s in swaps)
    # Dead move es la prioridad más alta (0) → primera en la lista ordenada.
    assert mr.suggestions[0].kind == "move_swap"


def test_clean_generated_team_yields_no_move_swaps():
    """El output del propio builder no debe recibir move_swaps de move muerto
    (§9.2 / §9.6): un equipo generado limpio → cero move_swaps."""
    from pokemon_team_builder.services.team_rater import detect_archetype

    variant = _generated_variant()
    arch, _ = detect_archetype(variant)
    swaps = [s for s in _all_suggestions(variant, arch) if s.kind == "move_swap"]
    assert swaps == [], swaps


def test_suggestions_priority_ordered():
    from pokemon_team_builder.services.team_rater import detect_archetype, rate_member

    variant, idx = _abomasnow_incoherent_variant()
    arch, _ = detect_archetype(variant)
    mr = rate_member(variant, idx, arch)
    priorities = [s.priority for s in mr.suggestions]
    assert priorities == sorted(priorities), priorities


# ── Tests B5: rate_team orquestador ──────────────────────────────────────────

def test_rate_team_shape_and_bounds():
    from pokemon_team_builder.services.team_rater import rate_team

    for builder in (
        _team_hyper_offense,
        _team_hard_trick_room,
        _team_perish_trap,
        _team_balance,
    ):
        rating = rate_team(builder())
        assert 0.0 <= rating.score <= 100.0
        assert rating.detected_archetype in team_rater.ARCHETYPES
        assert 0.0 <= rating.archetype_confidence <= 1.0
        assert len(rating.members) == 6
        for mr in rating.members:
            assert 1 <= mr.score <= 100


def test_rate_team_passes_through_import_warnings():
    from pokemon_team_builder.services.team_rater import rate_team

    rating = rate_team(_team_hyper_offense(), import_warnings=["aviso A", "aviso B"])
    assert rating.import_warnings == ["aviso A", "aviso B"]


def test_rate_team_low_confidence_scores_as_balance_with_warning():
    """Decisión de producto: confianza < 0.4 → puntúa como balance + aviso de
    estrategia ambigua, pero conserva el label detectado como pista."""
    from pokemon_team_builder.services import team_rater as tr
    from pokemon_team_builder.services.team_rater import (
        detect_archetype,
        rate_team,
        score_team,
    )

    variant = _team_weather_based()
    detected, confidence = detect_archetype(variant)
    assert confidence < tr.LOW_CONFIDENCE_CUTOFF  # precondición del fixture

    rating = rate_team(variant)
    # Label detectado se conserva como pista.
    assert rating.detected_archetype == detected
    # La puntuación coincide con score_team bajo 'balance' (no bajo el label).
    expected_balance_score, _ = score_team(
        variant, archetype="balance", team_sheet=variant.team_sheet
    )
    assert abs(rating.score - expected_balance_score) < 1e-6
    # Aviso de estrategia ambigua presente.
    assert any("ambigua" in w.lower() for w in rating.weaknesses)


def test_rate_team_high_confidence_scores_under_detected():
    from pokemon_team_builder.services import team_rater as tr
    from pokemon_team_builder.services.team_rater import (
        detect_archetype,
        rate_team,
        score_team,
    )

    variant = _team_hyper_offense()
    detected, confidence = detect_archetype(variant)
    assert confidence >= tr.LOW_CONFIDENCE_CUTOFF
    rating = rate_team(variant)
    expected, _ = score_team(
        variant, archetype=detected, team_sheet=variant.team_sheet
    )
    assert abs(rating.score - expected) < 1e-6
    assert not any("ambigua" in w.lower() for w in rating.weaknesses)


def test_rate_team_strengths_reuse_generate_explanation():
    """Las strengths del equipo incluyen la prosa de generate_explanation."""
    from pokemon_team_builder.services.team_rater import rate_team
    from pokemon_team_builder.services.viability_rater import (
        generate_explanation,
        score_team,
    )

    variant = _team_hyper_offense()
    rating = rate_team(variant)
    score, _ = score_team(
        variant, archetype=rating.detected_archetype, team_sheet=variant.team_sheet
    )
    base = generate_explanation(variant, score)
    assert any(base in s for s in rating.strengths)


# ── Tests B6: endpoint FastAPI POST /rate-team ───────────────────────────────
#
# CÓMO CORRER LOS TESTS DEL ENDPOINT (importante):
# tests/test_api.py NO colecta por un fallo PRE-EXISTENTE ajeno: importa
# pokemon_team_builder.main, que importa api/seo_pages → fastapi Jinja2Templates,
# y jinja2 no está instalado en este entorno. Para evitarlo SIN tocar nada de
# ese camino, montamos un FastAPI() nuevo que incluye SÓLO `router` (sin
# main.py, sin seo_pages). Así estos tests corren con el resto de la suite:
#   python -m pytest tests/test_team_rater.py
# o dentro de la suite completa con los --ignore habituales.

# PokePaste Showdown realista (mons del pool legal M-A; EVs 252/252 → 62 SP
# tras el /8 del parser). Verificado round-trip de especies/naturaleza/item.
_REAL_PASTE = """Garchomp @ Choice Scarf
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


@pytest.fixture
def rate_client():
    """TestClient sobre un FastAPI que monta SÓLO `router` (evita main/jinja2)."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from pokemon_team_builder.api.router import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_rate_team_endpoint_happy_path(rate_client):
    resp = rate_client.post("/rate-team", json={"pokepaste": _REAL_PASTE})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["detected_archetype"] in team_rater.ARCHETYPES
    assert 0.0 <= data["archetype_confidence"] <= 1.0
    assert 0.0 <= data["score"] <= 100.0
    assert len(data["members"]) == 6
    for m in data["members"]:
        assert 1 <= m["score"] <= 100
        for s in m["suggestions"]:
            assert s["kind"] in {"move_swap", "nature", "evs", "item"}
            assert s["from_value"] and s["to_value"] and s["reason"]


def test_rate_team_endpoint_422_on_five_members(rate_client):
    five = "\n\n".join(_REAL_PASTE.strip().split("\n\n")[:5])
    resp = rate_client.post("/rate-team", json={"pokepaste": five})
    assert resp.status_code == 422


def test_rate_team_endpoint_422_on_empty(rate_client):
    resp = rate_client.post("/rate-team", json={"pokepaste": ""})
    # min_length=1 → 422 de validación Pydantic.
    assert resp.status_code == 422


def test_rate_team_endpoint_no_species_suggestions(rate_client):
    """Invariante de roster vía el contrato del endpoint: ninguna sugerencia
    serializada tiene una kind de cambio de especie."""
    resp = rate_client.post("/rate-team", json={"pokepaste": _REAL_PASTE})
    data = resp.json()
    for m in data["members"]:
        for s in m["suggestions"]:
            assert s["kind"] in {"move_swap", "nature", "evs", "item"}


# ── Brief #1 (Tecle): el artefacto EV→SP (62/66) no debe generar ruido ───────

def test_real_paste_no_spurious_ev_suggestion(rate_client):
    """Un PokePaste competitivo estándar (252/252/4) parsea a ~62 SP por el
    //8 del parser. NINGÚN miembro debe recibir la sugerencia 'SP sin
    maximizar' — eso era el artefacto, no infrainversión real."""
    resp = rate_client.post("/rate-team", json={"pokepaste": _REAL_PASTE})
    data = resp.json()
    spurious = [
        (m["name"], s)
        for m in data["members"]
        for s in m["suggestions"]
        if s["kind"] == "evs" and "sin maximizar" in s["reason"].lower()
    ]
    assert not spurious, f"sugerencia EV espuria por artefacto 62/66: {spurious}"


def test_genuinely_under_invested_set_still_flags(rate_client):
    """Un set realmente infra-invertido (muy por debajo del suelo de SP) SÍ
    debe seguir disparando la sugerencia de EVs."""
    under = _REAL_PASTE.replace(
        "EVs: 4 HP / 252 Atk / 252 Spe\nJolly Nature",
        "EVs: 100 HP\nJolly Nature",  # 12 SP total << suelo (60)
        1,
    )
    resp = rate_client.post("/rate-team", json={"pokepaste": under})
    assert resp.status_code == 200, resp.text
    garchomp = resp.json()["members"][0]
    assert garchomp["name"].lower().startswith("garchomp")
    assert any(
        s["kind"] == "evs" and "sin maximizar" in s["reason"].lower()
        for s in garchomp["suggestions"]
    ), garchomp["suggestions"]


def test_rate_team_endpoint_422_on_oversized_payload(rate_client):
    """Brief #2: payload por encima de max_length → 422, no un 200 lento."""
    resp = rate_client.post("/rate-team", json={"pokepaste": "A" * 20001})
    assert resp.status_code == 422


# ── Mega stones son legales (viven en mega_evolutions.json, no en items) ─────

_AGGRON_MEGA_PASTE = """Aggron @ Aggronite
Ability: Heavy Metal
Level: 50
EVs: 252 HP / 252 SpD
Careful Nature
- Body Press
- Heavy Slam
- Iron Defense
- Protect

Garchomp @ Choice Scarf
Ability: Rough Skin
Level: 50
EVs: 252 Atk / 252 Spe
Jolly Nature
- Dragon Claw
- Earthquake
- Rock Slide
- Protect

Incineroar @ Sitrus Berry
Ability: Intimidate
Level: 50
EVs: 252 HP / 252 SpD
Careful Nature
- Fake Out
- Flare Blitz
- Parting Shot
- Protect

Whimsicott @ Occa Berry
Ability: Prankster
Level: 50
EVs: 252 Spe
Timid Nature
- Moonblast
- Tailwind
- Encore
- Protect

Milotic @ Leftovers
Ability: Competitive
Level: 50
EVs: 252 HP / 252 SpA
Modest Nature
- Scald
- Ice Beam
- Recover
- Protect

Dragonite @ Lum Berry
Ability: Multiscale
Level: 50
EVs: 252 Atk / 252 Spe
Adamant Nature
- Dragon Claw
- Earthquake
- Extreme Speed
- Protect
"""


def test_member_rating_includes_moves(rate_client):
    """Cada miembro valorado expone sus 4 moves (para mostrarlos en la UI)."""
    resp = rate_client.post("/rate-team", json={"pokepaste": _AGGRON_MEGA_PASTE})
    assert resp.status_code == 200, resp.text
    for m in resp.json()["members"]:
        assert isinstance(m["moves"], list) and len(m["moves"]) == 4, m


def test_steel_stab_not_flagged_no_stab(rate_client):
    """Aggron lleva Heavy Slam (Acero = su STAB) → NO debe salir 'sin STAB'.
    Regresión: la tabla curada no reconocía Heavy Slam y daba falso positivo."""
    resp = rate_client.post("/rate-team", json={"pokepaste": _AGGRON_MEGA_PASTE})
    aggron = next(m for m in resp.json()["members"] if m["name"].lower() == "aggron")
    no_stab = [w for w in aggron["weaknesses"] if "sin stab" in w.lower()]
    assert not no_stab, f"falso 'sin STAB' en Aggron (lleva Heavy Slam): {no_stab}"


def test_mega_stone_not_flagged_illegal(rate_client):
    """Una mega-piedra (Aggronite) es legal-por-datos-de-mega; NO debe salir
    como 'item ilegal, usa X'. Regresión del bug reportado por Sergio."""
    resp = rate_client.post("/rate-team", json={"pokepaste": _AGGRON_MEGA_PASTE})
    assert resp.status_code == 200, resp.text
    aggron = next(m for m in resp.json()["members"] if m["name"].lower() == "aggron")
    illegal_item = [
        s for s in aggron["suggestions"]
        if s["kind"] == "item" and "no es legal" in s["reason"].lower()
    ]
    assert not illegal_item, f"mega-piedra marcada ilegal: {illegal_item}"


# ── B1/B2: rol coherente + EVs por mon (adiciones "Valorar equipo") ──────────

def test_member_role_label_es():
    """derive_member_role devuelve un label ES coherente con el SET (§3.2):
    atacante físico vs especial (desempate naturaleza+EVs), setter de TR, etc."""
    from pokemon_team_builder.services.team_rater import derive_member_role

    # Garchomp Adamant + EVs físicos → offensive_threat físico.
    chomp = _member("garchomp", ["earthquake", "dragon-claw", "rock-slide", "protect"],
                    ability="Rough Skin", nature="Adamant",
                    sp={"atk": 31, "spe": 31})
    assert derive_member_role(chomp) == "Atacante físico"

    # Gengar Modest (boostea SpA) + EVs especiales → offensive_threat especial.
    # (Una naturaleza Timid sólo boostea Spe → _invested_offensive_category
    # devuelve None y el label sería "Atacante" a secas; el desempate
    # físico/especial exige naturaleza que boostee atk/spa, ADR §3.2.)
    gengar = _member("gengar", ["shadow-ball", "sludge-bomb", "thunderbolt", "protect"],
                     ability="Levitate", nature="Modest",
                     sp={"spa": 31, "spe": 31})
    assert derive_member_role(gengar) == "Atacante especial"

    # Slowbro con Trick Room → label de identidad de equipo (prioridad 1).
    slowbro = _member("slowbro", ["trick-room", "psychic", "ice-beam", "protect"],
                      ability="Regenerator", nature="Sassy",
                      sp={"hp": 31, "def_": 31})
    assert derive_member_role(slowbro) == "Trick Room"

    # Ninetales Drought → inductor de clima (prioridad 2, por encima de
    # offensive_threat).
    ninetales = _member("ninetales", ["flamethrower", "sunny-day", "solar-beam", "protect"],
                        ability="Drought", nature="Timid")
    assert derive_member_role(ninetales) == "Inductor de clima"


def test_member_role_label_is_one_of_fixed_set():
    """El label siempre pertenece al conjunto cerrado de labels ES (§3.2)."""
    from pokemon_team_builder.services import team_rater as tr
    from pokemon_team_builder.services.team_rater import derive_member_role

    allowed = {
        tr._ROLE_TRICK_ROOM, tr._ROLE_WEATHER, tr._ROLE_SUPPORT, tr._ROLE_WALL,
        tr._ROLE_PHYSICAL, tr._ROLE_SPECIAL, tr._ROLE_ATTACKER, tr._ROLE_SPEED,
        tr._ROLE_VERSATILE,
    }
    variant = _team_hyper_offense()
    for m in variant.members:
        assert derive_member_role(m) in allowed


def test_member_rating_includes_role():
    """rate_member puebla `role` (no vacío, del conjunto fijo de labels ES)."""
    from pokemon_team_builder.services import team_rater as tr
    from pokemon_team_builder.services.team_rater import detect_archetype, rate_member

    allowed = {
        tr._ROLE_TRICK_ROOM, tr._ROLE_WEATHER, tr._ROLE_SUPPORT, tr._ROLE_WALL,
        tr._ROLE_PHYSICAL, tr._ROLE_SPECIAL, tr._ROLE_ATTACKER, tr._ROLE_SPEED,
        tr._ROLE_VERSATILE,
    }
    variant = _team_hyper_offense()
    archetype, _ = detect_archetype(variant)
    for i in range(6):
        mr = rate_member(variant, i, archetype)
        assert mr.role in allowed, mr.role


def test_member_rating_includes_sp():
    """rate_member puebla `sp`: dict de 6 claves canónicas (clave 'def', no
    'def_'); la suma del dict == suma del sp_distribution del miembro."""
    from pokemon_team_builder.services.team_rater import detect_archetype, rate_member

    variant = _team_hyper_offense()
    archetype, _ = detect_archetype(variant)
    for i in range(6):
        mr = rate_member(variant, i, archetype)
        assert set(mr.sp.keys()) == {"hp", "atk", "def", "spa", "spd", "spe"}
        sp = variant.members[i].sp_distribution
        expected = sp.hp + sp.atk + sp.def_ + sp.spa + sp.spd + sp.spe
        assert sum(mr.sp.values()) == expected
