from __future__ import annotations

from pokemon_team_builder.data.speed_tiers import SpeedTierDB
from pokemon_team_builder.domain.models import TeamMember
from pokemon_team_builder.services.damage_calc import (
    COMMON_ATTACKS,
    calc_stat,
    get_nature_mod,
)

# Representative meta attacker: base 120 offensive stat, neutral nature, 0 SPs
_META_ATTACKER_BASE = 120
_META_ATTACKER_STAT = calc_stat(_META_ATTACKER_BASE, 0, 1.0)

_MAX_COMPARISONS = 3   # max names shown in speed note
_MAX_THREATS = 1       # max names shown as threats we can't outspeed


def explain(member: TeamMember, speed_db: SpeedTierDB, meta=None) -> str:  # noqa: ANN001
    """Return a Spanish ev_note string for this member. Empty string if no SPs invested."""
    sp = member.sp_distribution
    has_speed = sp.spe > 0
    has_bulk = sp.hp > 0 or sp.def_ > 0 or sp.spd > 0

    if not has_speed and not has_bulk:
        return ""

    parts: list[str] = []

    if has_speed:
        note = _speed_note(member, speed_db)
        if note:
            parts.append(note)

    if has_bulk:
        note = _defensive_note(member)
        if note:
            parts.append(note)

    return ". ".join(parts)


def _speed_note(member: TeamMember, speed_db: SpeedTierDB) -> str:
    sp = member.sp_distribution
    bs = member.pokemon.base_stats
    nature_mod = get_nature_mod(member.nature, "spe")
    my_speed = speed_db.compute_speed(bs.spe, sp.spe, member.nature)

    # Compute neutral-0SP speed for each entry in the DB for display
    entries_with_speed = [
        (e.name, speed_db.compute_speed(e.base_spe, 0, "hardy"), e.usage_rank)
        for e in speed_db.entries()
    ]

    # What we outspeed: their 0-SP neutral speed < our speed
    we_beat = [(name, spd) for name, spd, _ in entries_with_speed if spd < my_speed]
    # Sort by usage_rank (competitive relevance = lower rank first)
    we_beat_ranked = sorted(
        [(name, spd) for name, spd, rank in entries_with_speed if spd < my_speed],
        key=lambda x: next(e.usage_rank for e in speed_db.entries() if e.name == x[0]),
    )[:_MAX_COMPARISONS]

    # What outspeeds us: their 0-SP neutral speed > our speed
    threats_ranked = sorted(
        [(name, spd) for name, spd, rank in entries_with_speed if spd > my_speed],
        key=lambda x: next(e.usage_rank for e in speed_db.entries() if e.name == x[0]),
    )[:_MAX_THREATS]

    if not we_beat_ranked and not threats_ranked:
        return ""

    nature_tag = "+" if nature_mod > 1.0 else ("−" if nature_mod < 1.0 else "")
    spe_label = f"{sp.spe} Spe{nature_tag}"

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
