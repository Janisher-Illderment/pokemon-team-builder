from __future__ import annotations

from pokemon_team_builder.data.speed_tiers import SpeedTierDB
from pokemon_team_builder.domain.models import TeamMember
from pokemon_team_builder.services.damage_calc import (
    COMMON_ATTACKS,
    calc_stat,
    get_nature_mod,
)
from pokemon_team_builder.services.synergy_engine import (
    _ALLY_BOOST_MOVES,
    _REDIRECT_MOVES,
    _SCREEN_MOVES,
    _SETTER_ABILITY_TO_WEATHER,
    _SETUP_MOVES,
)

# Spanish weather names for the derived support hint (keys match
# _SETTER_ABILITY_TO_WEATHER values).
_WEATHER_ES: dict[str, str] = {
    "sun": "sol", "rain": "lluvia", "snow": "nieve", "sand": "tormenta de arena",
}

# Mechanical role labels whose ev-note hint is purely stat-based and always
# true for the build (so the canned string is safe). Support-family roles are
# derived from the actual moveset/ability instead (see _role_hint).
_STAT_BASED_ROLES: frozenset[str] = frozenset({
    "physical_sweeper", "special_sweeper", "physical_wall", "special_wall",
})

# Representative meta attacker: base 120 offensive stat, neutral nature, 0 SPs
_META_ATTACKER_BASE = 120
_META_ATTACKER_STAT = calc_stat(_META_ATTACKER_BASE, 0, 1.0)

_MAX_COMPARISONS = 3   # max names shown in speed note
_MAX_THREATS = 1       # max names shown as threats we can't outspeed
# Speed benchmarks must come from the actual meta — comparing "Spe 154
# supera a Dedenne (rank 153)" is dead information because Sergio will
# never face Dedenne competitively. The threshold caps speed_tiers entries
# at the top-30 by usage_rank so every name in the ev_note is one the
# user might actually fight.
_TOP_USAGE_BENCHMARK_THRESHOLD = 30


# v0.10.2 (2026-05-15): ev_note context expansion. Each item-aware note
# captures the mechanic Sergio cares about when picking the kit — "what
# does this item *do* for this member?" — so the explanation is specific
# to the build, not generic.
# v0.10.3 item note table: covers ONLY the 48 items in
# champions_legal_items.json v5. Items not in the legal pool get no note
# even if the kit somehow references them (defensive against drift).
_ITEM_NOTES: dict[str, str] = {
    # NOTE: Mental Herb is handled in _item_note (context-sensitive on setup
    # presence), not here.
    "Shell Bell": "Shell Bell drena 1/8 del daño infligido — recovery pasivo ofensivo",
    "Scope Lens": "Scope Lens +1 nivel de probabilidad de golpes críticos",
    "Light Ball": "Light Ball (sólo Pikachu) duplica Atk y SpA",
    "Oran Berry": "Oran Berry restaura 10 PS al bajar a la mitad — una vez por combate",
    "Persim Berry": "Persim Berry cura confusión — una vez por combate",
    "Cheri Berry": "Cheri Berry cura parálisis — una vez por combate",
    "Chesto Berry": "Chesto Berry cura sueño — una vez por combate",
    "Pecha Berry": "Pecha Berry cura envenenamiento — una vez por combate",
    "Rawst Berry": "Rawst Berry cura quemaduras — una vez por combate",
    "Aspear Berry": "Aspear Berry cura congelación — una vez por combate",
    "Leppa Berry": "Leppa Berry restaura 10 PP a un movimiento sin PP — una vez por combate",
}

# Type-resist berries get a generic note since the trigger is uniform.
_TYPE_RESIST_BERRIES: frozenset[str] = frozenset({
    "Chilan Berry", "Occa Berry", "Passho Berry", "Wacan Berry", "Rindo Berry",
    "Yache Berry", "Chople Berry", "Kebia Berry", "Shuca Berry", "Coba Berry",
    "Payapa Berry", "Tanga Berry", "Charti Berry", "Kasib Berry", "Haban Berry",
    "Colbur Berry", "Babiri Berry", "Roseli Berry",
})

# Type-boost items (Charcoal, Mystic Water, etc.) — pattern is uniform so
# a single generic note covers them.
_TYPE_BOOST_ITEM_PATTERNS: frozenset[str] = frozenset({
    "Mystic Water", "Charcoal", "Magnet", "Black Belt", "Soft Sand",
    "Sharp Beak", "Silver Powder", "Dragon Fang", "Spell Tag",
    "Miracle Seed", "Never-Melt Ice", "Poison Barb", "Metal Coat",
    "Black Glasses", "Twisted Spoon", "Hard Stone", "Silk Scarf",
    "Fairy Feather",
})


_ARCHETYPE_NOTES: dict[str, str] = {
    "hyper_offense": "arquetipo Hyper Offense: turnos limitados, ofensiva sobre bulk",
    "hard_trick_room": "arquetipo Hard TR: Spe invertida, ataque bajo Trick Room",
    "bulky_offense": "arquetipo Bulky Offense: HP/Def para aguantar 2HKO mientras pega",
    "weather_based": "arquetipo Weather: la build asume clima activo (Drought/Drizzle/Sand/Snow)",
    "stall": "arquetipo Stall: ciclos de status + recovery, no KO directo",
    "perish_trap": "arquetipo Perish Trap: ganar via Perish Song + pivots/Shadow Tag",
    # "balance" intentionally omitted — adds no info beyond defaults.
}


# Stat-based role hints only. Support-family roles (lead_support / redirect /
# trick_room_setter) are NOT here — their hint is derived from the actual
# moveset+ability in _role_hint so it never states utility the mon lacks.
_ROLE_HINTS: dict[str, str] = {
    "physical_sweeper": "rol físico: Atk + Spe son prioridad — nature +Atk o +Spe",
    "special_sweeper": "rol especial: SpA + Spe son prioridad — nature +SpA o +Spe",
    "physical_wall": "muro físico: máximo HP + Def, nature +Def",
    "special_wall": "muro especial: máximo HP + SpD, nature +SpD",
}


def explain(  # noqa: ANN001
    member: TeamMember,
    speed_db: SpeedTierDB,
    meta=None,
    *,
    archetype: str | None = None,
) -> str:
    """Return a Spanish ev_note string for this member.

    Returns "" if the member has 0 SP invested AND no item/role context
    worth surfacing. With v0.10.2 expansion, the note can carry:

    - Speed benchmark (when sp.spe > 0): "Spe 222 (32 SP+) supera a X, Y, Z"
    - Defensive verdict (when bulk SPs > 0): "32 HP + 16 Def aguanta Terremoto (45-60%)"
    - Item insight (always, when item is recognised): "Sitrus Berry cura ~25%..."
    - Role + archetype hint (always, when archetype != balance): "lead support: ..."

    The combined string stays compact — each component is 1 short Spanish
    clause separated by ". ".

    Args:
        member: The team member to explain.
        speed_db: Speed-tier database for benchmark comparisons.
        meta: Optional MetaService (reserved for future use, currently
            unused — kept for backward compatibility with the router call
            sites that already pass it).
        archetype: The TeamVariant.archetype the member was generated
            under. When provided, an archetype hint is appended to the
            note so the user understands why the kit looks the way it
            does. ``None`` or "balance" suppresses the hint.
    """
    sp = member.sp_distribution
    has_speed = sp.spe > 0
    has_bulk = sp.hp > 0 or sp.def_ > 0 or sp.spd > 0

    parts: list[str] = []

    if has_speed:
        note = _speed_note(member, speed_db)
        if note:
            parts.append(note)

    if has_bulk:
        note = _defensive_note(member)
        if note:
            parts.append(note)

    context = _context_note(member, archetype)
    if context:
        parts.append(context)

    return ". ".join(parts)


def _context_note(member: TeamMember, archetype: str | None) -> str:
    """Return one short Spanish clause covering role + item + archetype.

    Order: role hint → item insight → archetype note. Each component is
    optional and omitted when the input is unknown. The final string is
    the joined non-empty components separated by " · " so the speed and
    defensive notes (which use ". ") stay visually distinct.
    """
    bits: list[str] = []
    role_hint = _role_hint(member)
    if role_hint:
        bits.append(role_hint)
    item_note = _item_note(member.item, member)
    if item_note:
        bits.append(item_note)
    if archetype and archetype != "balance":
        arch_note = _ARCHETYPE_NOTES.get(archetype)
        if arch_note:
            bits.append(arch_note)
    return " · ".join(bits)


def _role_hint(member: TeamMember) -> str:
    """Return a role hint DERIVED from the build, never a canned per-label lie.

    Stat-based roles (sweeper/wall) keep their always-true stat hint. For
    support-family roles the hint is built from what the member ACTUALLY
    brings — its weather-setter ability and its real support moves — so we
    never claim "Tailwind / Fake Out / Follow Me" for a mon that has none of
    them (the Abomasnow-as-lead_support bug). If a support-role mon brings no
    recognisable utility, we say nothing rather than something false.
    """
    primary_role = member.role[0] if member.role else ""
    if primary_role in _STAT_BASED_ROLES:
        return _ROLE_HINTS.get(primary_role, "")

    moves = {m.strip().lower() for m in member.moves}
    ability = (member.ability or "").strip().lower().replace(" ", "-")
    util: list[str] = []

    weather = _WEATHER_ES.get(_SETTER_ABILITY_TO_WEATHER.get(ability, ""))
    if weather:
        util.append(f"pone {weather} turno 1 (habilidad)")
    if ability == "intimidate":
        util.append("intimida (−Atk rival) al entrar")
    if "fake-out" in moves:
        util.append("Fake Out (flinch turno 1)")
    if moves & _REDIRECT_MOVES:
        util.append("redirección (protege al aliado)")
    if "tailwind" in moves:
        util.append("Tailwind (+Spe al equipo)")
    if "trick-room" in moves:
        util.append("Trick Room (invierte velocidades)")
    if moves & _ALLY_BOOST_MOVES:
        util.append("refuerzo al aliado")
    if moves & _SCREEN_MOVES:
        util.append("pantallas")

    if util:
        return "soporte: " + ", ".join(util)
    # Support-role label but no actual utility move/ability → don't fabricate.
    return ""


def _item_note(item: str, member: TeamMember | None = None) -> str:
    """Return the item-specific Spanish clause, or "" when the item is unknown.

    Context-sensitive where it matters: Mental Herb only claims it "blinda el
    setup" when the build actually carries a setup move (otherwise it just
    cancels Taunt/Encore).
    """
    if not item:
        return ""
    if item == "Mental Herb":
        has_setup = bool(
            member is not None
            and {m.strip().lower() for m in member.moves} & _SETUP_MOVES
        )
        base = "Mental Herb cancela Mofa/Encore/Cura anulada una vez"
        return base + (" — blinda el setup" if has_setup else "")
    if item in _ITEM_NOTES:
        return _ITEM_NOTES[item]
    if item in _TYPE_RESIST_BERRIES:
        return f"{item} reduce x0.5 el primer hit super-efectivo de su tipo (consumible)"
    if item in _TYPE_BOOST_ITEM_PATTERNS:
        return f"{item} +20% poder a moves de su tipo (sólo STAB efectivo)"
    return ""


def _speed_note(member: TeamMember, speed_db: SpeedTierDB) -> str:
    sp = member.sp_distribution
    bs = member.pokemon.base_stats
    nature_mod = get_nature_mod(member.nature, "spe")
    my_speed = speed_db.compute_speed(bs.spe, sp.spe, member.nature)

    # Phase 4b feedback fix: opponents in the speed tier are assumed to
    # run **max SP (32) + neutral nature** rather than the prior
    # 0 SP + neutral baseline. The old baseline produced misleading
    # comparisons — e.g. Aerodactyl (base 130) reported as 146 when its
    # realistic competitive speed sits around 182 (max SP, neutral). We
    # don't force a +Spe nature on opponents because that would assume a
    # strategy the user can't infer from typing alone; max-SP-neutral is
    # the closest neutral-strategy approximation. A future enhancement
    # can override per-entry via speed_tiers.json (e.g. Trick Room mons).
    # Restrict the benchmark pool to the top of the usage chart — anything
    # past _TOP_USAGE_BENCHMARK_THRESHOLD is competitively irrelevant
    # (Dedenne at rank 153 etc.) and only adds noise to the ev_note.
    top_meta_entries = [
        e for e in speed_db.entries()
        if e.usage_rank <= _TOP_USAGE_BENCHMARK_THRESHOLD
    ]
    entries_with_speed = [
        (e.name, speed_db.compute_speed(e.base_spe, 32, "hardy"), e.usage_rank)
        for e in top_meta_entries
    ]

    # What we outspeed (from the top-meta pool): their max-SP neutral speed
    # < our speed. Sort by usage_rank so the most-used names come first.
    we_beat = [(name, spd) for name, spd, _ in entries_with_speed if spd < my_speed]
    we_beat_ranked = sorted(
        [(name, spd, rank) for name, spd, rank in entries_with_speed if spd < my_speed],
        key=lambda x: x[2],
    )[:_MAX_COMPARISONS]
    we_beat_ranked = [(name, spd) for name, spd, _ in we_beat_ranked]

    # What outspeeds us (from the top-meta pool).
    threats_ranked = sorted(
        [(name, spd, rank) for name, spd, rank in entries_with_speed if spd > my_speed],
        key=lambda x: x[2],
    )[:_MAX_THREATS]
    threats_ranked = [(name, spd) for name, spd, _ in threats_ranked]

    if not we_beat_ranked and not threats_ranked:
        return ""

    nature_tag = "+" if nature_mod > 1.0 else ("−" if nature_mod < 1.0 else "")
    # Show final stat (my_speed) so the user sees the real competitive
    # number, not just the SP investment. Format: "Spe 222 (32 SP+)".
    spe_label = f"Spe {my_speed} ({sp.spe} SP{nature_tag})"

    beat_str = ""
    if we_beat_ranked:
        beat_parts = [f"{_fmt_name(n)} ({s})" for n, s in we_beat_ranked]
        if len(we_beat) > _MAX_COMPARISONS:
            beat_parts.append("y otros")
        beat_str = "supera a " + ", ".join(beat_parts)

    threat_str = ""
    if threats_ranked:
        n, s = threats_ranked[0]
        threat_str = f"no alcanza a {_fmt_name(n)} ({s})"

    parts = [p for p in [beat_str, threat_str] if p]
    if not parts:
        return ""
    return f"{spe_label} {' — '.join(parts)}"


def _defensive_note(member: TeamMember) -> str:
    sp = member.sp_distribution
    bs = member.pokemon.base_stats
    weaknesses: dict[str, float] = member.pokemon.weaknesses

    if not weaknesses:
        return ""

    # Find biggest weakness (highest multiplier)
    worst_type = max(weaknesses, key=lambda t: weaknesses[t])
    worst_mult = weaknesses[worst_type]
    if worst_mult < 1.0:
        return ""

    attack_data = COMMON_ATTACKS.get(worst_type)
    if not attack_data:
        return ""

    is_physical = attack_data["category"] == "physical"
    move_name = attack_data["name"]

    # Compute defender bulk stats with invested SPs
    hp_mod = get_nature_mod(member.nature, "hp")
    def_mod = get_nature_mod(member.nature, "def")
    spd_mod = get_nature_mod(member.nature, "spd")

    hp_stat = calc_stat(bs.hp, sp.hp, hp_mod, is_hp=True)
    def_stat = calc_stat(bs.def_, sp.def_, def_mod)
    spd_stat = calc_stat(bs.spd, sp.spd, spd_mod)
    bulk_stat = def_stat if is_physical else spd_stat

    # Damage calculation
    from pokemon_team_builder.services.damage_calc import calc_damage  # local import avoids circular
    min_pct, max_pct = calc_damage(
        atk_stat=_META_ATTACKER_STAT,
        def_stat=bulk_stat,
        move_power=attack_data["power"],
        effectiveness=worst_mult,
        stab=False,
        defender_hp=hp_stat,
    )

    if max_pct >= 100.0:
        verdict = "NO aguanta"
    elif max_pct >= 85.0:
        verdict = "aguanta por poco"
    elif max_pct >= 50.0:
        verdict = "aguanta"
    else:
        verdict = "aguanta con holgura"

    # Format bulk investments
    bulk_parts: list[str] = []
    if sp.hp > 0:
        bulk_parts.append(f"{sp.hp} HP")
    if is_physical and sp.def_ > 0:
        bulk_parts.append(f"{sp.def_} Def")
    elif not is_physical and sp.spd > 0:
        bulk_parts.append(f"{sp.spd} SpD")
    bulk_label = " + ".join(bulk_parts) if bulk_parts else ("HP" if sp.hp > 0 else "Def/SpD")

    return f"{bulk_label} {verdict} el {move_name} ({int(min_pct)}–{int(max_pct)}%)"


def _fmt_name(name: str) -> str:
    return name.replace("-", " ").title()
