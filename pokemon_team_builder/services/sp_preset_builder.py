"""SP preset builder (Phase 3, §9 — ev-presets-champions).

Replaces the legacy role-template-driven SP allocation with two presets
per member: ``offensive`` and ``defensive``. Each preset sums to exactly
66 SP with a hard cap of 32 SP per stat (Champions Reg M-A).

Design:
  - ``SpRead`` is a frozen dataclass (immutable, hashable, debuggable).
  - ``build_presets`` is pure and deterministic: given identical inputs
    it returns identical presets. Variance comes from the threat lists.
  - Held items skew the allocation: Choice Band / Specs / Scarf shift
    investment AWAY from the stat the item already inflates, INTO Speed
    or bulk; Eviolite (NFE-only) frees up SPs for offense.
  - Nature jumps: when the relevant nature has a 0.9 / 1.1 multiplier
    on a key stat, the optimiser nudges SPs toward the jump value (so
    1 SP yields +2 final stat) using ``sp_calc.find_nature_jumps``.

Threat lists are accepted but currently used as advisory inputs (the
length is consulted to prioritise offense vs defense). Future work
will plug `MetaService` data into damage calculations once the
damage_calc service supports speed-aware OHKO/2HKO simulation.
"""

from __future__ import annotations

from dataclasses import dataclass

from pokemon_team_builder.domain.models import SPDistribution, TeamMember
from pokemon_team_builder.services.sp_calc import (
    SP_PER_STAT_CAP,
    SP_TOTAL_CAP,
    find_nature_jumps,
)


# Nature → (boosted_stat, hindered_stat). Lower-case is canonical here;
# call sites pass natures in arbitrary case (e.g. "Jolly").
_NATURE_MODIFIERS: dict[str, tuple[str | None, str | None]] = {
    "hardy":   (None, None),
    "lonely":  ("atk", "def"),
    "brave":   ("atk", "spe"),
    "adamant": ("atk", "spa"),
    "naughty": ("atk", "spd"),
    "bold":    ("def", "atk"),
    "docile":  (None, None),
    "relaxed": ("def", "spe"),
    "impish":  ("def", "spa"),
    "lax":     ("def", "spd"),
    "timid":   ("spe", "atk"),
    "hasty":   ("spe", "def"),
    "serious": (None, None),
    "jolly":   ("spe", "spa"),
    "naive":   ("spe", "spd"),
    "modest":  ("spa", "atk"),
    "mild":    ("spa", "def"),
    "quiet":   ("spa", "spe"),
    "bashful": (None, None),
    "rash":    ("spa", "spd"),
    "calm":    ("spd", "atk"),
    "gentle":  ("spd", "def"),
    "sassy":   ("spd", "spe"),
    "careful": ("spd", "spa"),
    "quirky":  (None, None),
}


# Stat key canonical order — used by SpRead and the SPDistribution model.
_STAT_KEYS: tuple[str, ...] = ("hp", "atk", "def_", "spa", "spd", "spe")


# Items that pre-inflate a single stat by 1.5×. Optimiser invests LESS
# in the inflated stat, MORE elsewhere — the 1.5× already covers the gap.
_ITEM_INFLATED_STAT: dict[str, str] = {
    "Choice Band":   "atk",
    "Choice Specs":  "spa",
    "Choice Scarf":  "spe",
    "Assault Vest":  "spd",
}

# Eviolite inflates BOTH defensive stats (NFE-only). Caller is responsible
# for ensuring the holder is an NFE pokemon — we trust the input here.
_EVIOLITE_INFLATED: tuple[str, ...] = ("def_", "spd")


@dataclass(frozen=True)
class SpRead:
    """Immutable SP allocation for a single preset.

    All six stats sum to exactly ``SP_TOTAL_CAP`` (66) and each stat is
    in ``[0, SP_PER_STAT_CAP]`` (0..32). ``def_`` mirrors the Python
    reserved-word workaround used by ``BaseStats`` / ``SPDistribution``.
    """

    hp: int
    atk: int
    def_: int
    spa: int
    spd: int
    spe: int

    def __post_init__(self) -> None:
        for key in _STAT_KEYS:
            v = getattr(self, key)
            if not isinstance(v, int) or v < 0 or v > SP_PER_STAT_CAP:
                raise ValueError(
                    f"SpRead.{key}={v!r} out of range [0, {SP_PER_STAT_CAP}]"
                )
        total = self.hp + self.atk + self.def_ + self.spa + self.spd + self.spe
        if total != SP_TOTAL_CAP:
            raise ValueError(
                f"SpRead total={total}, expected {SP_TOTAL_CAP}"
            )

    def to_dict(self) -> dict[str, int]:
        """Return a dict using SP-distribution key convention (``def`` not ``def_``)."""
        return {
            "hp": self.hp,
            "atk": self.atk,
            "def": self.def_,
            "spa": self.spa,
            "spd": self.spd,
            "spe": self.spe,
        }

    def to_sp_distribution(self) -> SPDistribution:
        """Build a domain SPDistribution from this preset."""
        return SPDistribution(
            hp=self.hp,
            atk=self.atk,
            **{"def": self.def_},
            spa=self.spa,
            spd=self.spd,
            spe=self.spe,
        )


def _normalise_nature(nature: str) -> tuple[str | None, str | None]:
    """Return (boosted, hindered) stat keys for a nature name (case-insensitive)."""
    return _NATURE_MODIFIERS.get(nature.strip().lower(), (None, None))


def _is_physical_attacker(member: TeamMember) -> bool:
    """Heuristic: classify member as physical or special attacker.

    Uses the pokemon's base atk vs spa, then falls back to role hint.
    A tie or close call defaults to physical (Champions M-A skews
    physical-heavy in usage data).
    """
    bs = member.pokemon.base_stats
    if bs.atk > bs.spa:
        return True
    if bs.spa > bs.atk:
        return False
    # Tie-breaker by role tag.
    roles = [r.lower() for r in member.role]
    if any("special" in r for r in roles):
        return False
    return True


def _apply_nature_jump(
    base: int,
    target_sp: int,
    nature_mult: float,
) -> int:
    """Nudge ``target_sp`` toward the nearest +2 nature-jump SP at or below it.

    Falls back to ``target_sp`` if no jump exists in [0, target_sp].
    The spec breaks ties toward the LOWER SP investment — so we pick the
    largest jump SP that is ≤ target_sp.
    """
    jumps = find_nature_jumps(base, nature_mult, max_sp=SP_PER_STAT_CAP)
    if not jumps:
        return target_sp
    eligible = [j for j in jumps if j <= target_sp]
    if not eligible:
        return target_sp
    return max(eligible)


def _distribute(weights: dict[str, float]) -> dict[str, int]:
    """Convert a weight map into integer SPs summing to ``SP_TOTAL_CAP``.

    Each weight in ``weights`` represents the relative "desire" for SPs
    in that stat (negative weights are clamped to 0). The result respects
    the per-stat cap of 32 and the total cap of 66.

    Algorithm:
      1. Normalise weights → fractional SPs.
      2. Floor each → integer base; track leftover via fractional parts.
      3. Distribute the leftover SPs to the stats with the largest
         fractional remainders, skipping stats already at the cap.
      4. If a stat would exceed 32, clamp it and redistribute the
         overflow to other under-cap stats.

    Returns:
        Dict keyed by ``_STAT_KEYS`` (``def_``, not ``def``).
    """
    cleaned: dict[str, float] = {
        k: max(0.0, float(weights.get(k, 0.0))) for k in _STAT_KEYS
    }
    total = sum(cleaned.values())
    if total <= 0:
        # Nothing to allocate — distribute evenly under the cap.
        # 66 = 11 per stat, all under 32 cap.
        return {k: 11 for k in _STAT_KEYS}

    fractional: dict[str, float] = {
        k: (cleaned[k] / total) * SP_TOTAL_CAP for k in _STAT_KEYS
    }
    floored: dict[str, int] = {k: min(int(fractional[k]), SP_PER_STAT_CAP) for k in _STAT_KEYS}
    leftover = SP_TOTAL_CAP - sum(floored.values())

    # Distribute leftover SPs by largest fractional remainder, then by
    # input weight as a tiebreaker. Stats with weight == 0 are EXCLUDED
    # from leftover distribution — a 0-weight stat means the caller
    # explicitly wants nothing there (e.g. hindered nature stat). Stats
    # already at cap are also skipped.
    eligible = [k for k in _STAT_KEYS if cleaned[k] > 0.0]
    if not eligible:
        # All weights zero — fall back to all eligible.
        eligible = list(_STAT_KEYS)
    remainders = sorted(
        eligible,
        key=lambda k: (fractional[k] - floored[k], cleaned[k]),
        reverse=True,
    )
    safety = 0
    while leftover > 0 and safety < 1000:
        safety += 1
        progressed = False
        for stat in remainders:
            if leftover <= 0:
                break
            if floored[stat] < SP_PER_STAT_CAP:
                floored[stat] += 1
                leftover -= 1
                progressed = True
        if not progressed:
            # All eligible stats hit the cap; spread remaining to any
            # under-cap stat (last-resort to keep total = 66).
            spillover = [k for k in _STAT_KEYS if floored[k] < SP_PER_STAT_CAP]
            if not spillover:
                break
            for stat in spillover:
                if leftover <= 0:
                    break
                floored[stat] += 1
                leftover -= 1

    return floored


def _offensive_weights(
    member: TeamMember,
    item: str,
    nature: str,
    threats_to_OHKO: int,
) -> dict[str, float]:
    """Compute relative weights for the offensive preset.

    Base profile: max attack stat (atk or spa) + speed + small HP buffer.
    Item shifts: Choice items lock the inflated stat → invest in the
    OTHER offensive levers (speed, bulk). Choice Scarf already gives the
    speed boost → invest in raw attack instead.
    """
    is_physical = _is_physical_attacker(member)
    primary_atk = "atk" if is_physical else "spa"

    weights: dict[str, float] = {k: 0.0 for k in _STAT_KEYS}
    weights[primary_atk] = 10.0
    weights["spe"] = 9.0
    weights["hp"] = 2.0

    # Item adjustments — bake in the 1.5× inflation per spec scenarios.
    if item == "Choice Band" and is_physical:
        # Band already inflates Atk 1.5×; shift to Speed (spec: "spe > atk").
        weights["atk"] = 4.0
        weights["spe"] = 11.0
        weights["hp"] = 4.0
    elif item == "Choice Specs" and not is_physical:
        weights["spa"] = 4.0
        weights["spe"] = 11.0
        weights["hp"] = 4.0
    elif item == "Choice Scarf":
        # Scarf inflates Speed 1.5× — invest more in raw attack instead.
        weights[primary_atk] = 12.0
        weights["spe"] = 4.0
        weights["hp"] = 3.0
    elif item == "Assault Vest":
        # AV inflates SpD; offensive preset still leans attack but adds bulk.
        weights[primary_atk] = 9.0
        weights["spe"] = 7.0
        weights["hp"] = 4.0
        weights["spd"] = 1.0

    # Hindered nature → zero out that stat.
    boosted, hindered = _normalise_nature(nature)
    if hindered is not None and hindered in weights:
        weights[hindered] = 0.0

    # If the optimiser has fewer threats to OHKO, lean more on bulk
    # (the offensive preset still leans offense — small effect).
    if threats_to_OHKO <= 1:
        weights["hp"] += 1.0

    return weights


def _defensive_weights(
    member: TeamMember,
    item: str,
    nature: str,
    threats_to_survive: int,
) -> dict[str, float]:
    """Compute relative weights for the defensive preset.

    Base profile: HP + both defenses + small attack stake. Item shifts:
    Eviolite inflates Def + SpD → free up SPs for offense; Assault Vest
    inflates SpD → invest more in Def to balance.
    """
    is_physical = _is_physical_attacker(member)
    primary_atk = "atk" if is_physical else "spa"

    weights: dict[str, float] = {k: 0.0 for k in _STAT_KEYS}
    weights["hp"] = 10.0
    weights["def_"] = 7.0
    weights["spd"] = 7.0
    weights[primary_atk] = 4.0
    weights["spe"] = 2.0

    if item == "Eviolite":
        # NFE-only: defenses already inflated → invest in offense (spec).
        weights["hp"] = 8.0
        weights["def_"] = 3.0
        weights["spd"] = 3.0
        weights[primary_atk] = 8.0
        weights["spe"] = 4.0
    elif item == "Assault Vest":
        # SpD already inflated 1.5× → invest more in Def (spec scenario).
        weights["hp"] = 10.0
        weights["def_"] = 11.0
        weights["spd"] = 2.0
        weights[primary_atk] = 5.0
        weights["spe"] = 2.0
    elif item == "Choice Band" and is_physical:
        weights["hp"] = 8.0
        weights["def_"] = 6.0
        weights["spd"] = 6.0
        weights["atk"] = 3.0
        weights["spe"] = 4.0
    elif item == "Choice Specs" and not is_physical:
        weights["hp"] = 8.0
        weights["def_"] = 6.0
        weights["spd"] = 6.0
        weights["spa"] = 3.0
        weights["spe"] = 4.0

    boosted, hindered = _normalise_nature(nature)
    if hindered is not None and hindered in weights:
        weights[hindered] = max(0.0, weights[hindered] - 2.0)

    if threats_to_survive >= 3:
        weights["hp"] += 2.0

    return weights


def _apply_nature_jumps_to_allocation(
    member: TeamMember,
    alloc: dict[str, int],
    nature: str,
) -> dict[str, int]:
    """Nudge SPs to land on +2 nature-jump thresholds where possible.

    Only applies to the boosted stat (jumps come from the 1.1× rounding
    interactions). When the jump SP value is ≤ the current allocation,
    we lower the allocation to that jump value and redistribute the
    freed SPs into HP (a safe fallback — never overshoots the cap).
    """
    boosted, _ = _normalise_nature(nature)
    if boosted is None or boosted not in alloc:
        return alloc
    base_attr = boosted if boosted != "def_" else "def_"
    # Map alloc key to PokemonData base_stats attribute.
    base_value = getattr(member.pokemon.base_stats, base_attr, None)
    if base_value is None:
        return alloc
    current = alloc[boosted]
    if current <= 0:
        return alloc
    nudged = _apply_nature_jump(base_value, current, 1.1)
    if nudged == current:
        return alloc
    freed = current - nudged
    if freed <= 0:
        return alloc
    # Redistribute freed SPs into HP (under-cap), then SpD as fallback.
    out = dict(alloc)
    out[boosted] = nudged
    for sink in ("hp", "spd", "def_"):
        if sink == boosted:
            continue
        room = SP_PER_STAT_CAP - out[sink]
        if room <= 0:
            continue
        give = min(room, freed)
        out[sink] += give
        freed -= give
        if freed <= 0:
            break
    # If freed SPs remain (cap saturation — rare), give back to boosted.
    if freed > 0:
        out[boosted] += freed
    return out


def _alloc_to_sp_read(alloc: dict[str, int]) -> SpRead:
    return SpRead(
        hp=alloc["hp"],
        atk=alloc["atk"],
        def_=alloc["def_"],
        spa=alloc["spa"],
        spd=alloc["spd"],
        spe=alloc["spe"],
    )


def build_presets(
    member: TeamMember,
    item: str,
    nature: str,
    threats_to_OHKO: list[str] | None = None,
    threats_to_survive: list[str] | None = None,
) -> dict[str, SpRead]:
    """Build offensive + defensive SP presets for a single team member.

    Args:
        member: The team member (provides base stats and role hints).
        item: The held item name (display form, e.g. "Choice Band").
        nature: The nature name (any case, e.g. "Jolly" or "jolly").
        threats_to_OHKO: List of threat names the offensive preset
            should be able to OHKO/2HKO. Currently only the length is
            consulted; future versions will run damage calc per threat.
        threats_to_survive: List of threat names the defensive preset
            should survive. Same caveat as above.

    Returns:
        ``{"offensive": SpRead, "defensive": SpRead}`` — each preset
        sums to 66 SP with per-stat ≤ 32.
    """
    ohko = threats_to_OHKO or []
    survive = threats_to_survive or []

    off_w = _offensive_weights(member, item, nature, len(ohko))
    def_w = _defensive_weights(member, item, nature, len(survive))

    off_alloc = _distribute(off_w)
    def_alloc = _distribute(def_w)

    off_alloc = _apply_nature_jumps_to_allocation(member, off_alloc, nature)
    def_alloc = _apply_nature_jumps_to_allocation(member, def_alloc, nature)

    return {
        "offensive": _alloc_to_sp_read(off_alloc),
        "defensive": _alloc_to_sp_read(def_alloc),
    }
