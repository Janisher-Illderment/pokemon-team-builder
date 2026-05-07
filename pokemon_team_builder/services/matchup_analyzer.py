from __future__ import annotations

from pokemon_team_builder.api.schemas import AdjustmentOut, MatchupAnalysisResponse
from pokemon_team_builder.domain.models import PokemonData, TeamMember
from pokemon_team_builder.services.meta_service import MetaService
from pokemon_team_builder.services.synergy_engine import ALL_TYPES
from pokemon_team_builder.services import pokemon_lookup as _lookup_module


class UnknownThreatError(Exception):
    pass


# Archetype keywords → representative pokemon names from the Reg M-A pool.
ARCHETYPE_MAP: dict[str, list[str]] = {
    "trick room": ["slowbro", "snorlax", "reuniclus", "aromatisse"],
    "trick-room": ["slowbro", "snorlax", "reuniclus", "aromatisse"],
    "tailwind": ["talonflame", "hawlucha", "arcanine", "aerodactyl"],
    "rain": ["pelipper", "politoed", "kingdra", "ludicolo"],
    "sun": ["torkoal", "venusaur", "victreebel"],
    "sand": ["tyranitar", "excadrill", "garchomp"],
    "snow": ["abomasnow", "aurorus", "beartic"],
    "redirect": ["incineroar", "aromatisse", "arcanine"],
    "hyper offense": ["aerodactyl", "garchomp", "arcanine"],
    "stall": ["snorlax", "incineroar", "slowbro"],
}

# STAB coverage by type (attacking type → bonus)
_COVERAGE_BONUS: dict[str, float] = {t: 0.5 for t in ALL_TYPES}


def _lookup_pokemon(name: str) -> PokemonData | None:
    try:
        return _lookup_module.lookup(name.strip().lower())
    except Exception:
        return None


def resolve_threat(threat: str, lookup=None) -> list[PokemonData]:
    """Return a list of PokemonData representing the threat.

    Tries direct lookup first (single pokemon), then archetype map,
    then raises UnknownThreatError.
    """
    key = threat.strip().lower()
    direct = _lookup_pokemon(key)
    if direct is not None:
        return [direct]

    for archetype_key, names in ARCHETYPE_MAP.items():
        if archetype_key in key or key in archetype_key:
            resolved: list[PokemonData] = []
            for name in names:
                mon = _lookup_pokemon(name)
                if mon is not None:
                    resolved.append(mon)
                if len(resolved) >= 3:
                    break
            if resolved:
                return resolved

    raise UnknownThreatError(threat)


def score_handler(
    member: TeamMember,
    threat_mons: list[PokemonData],
) -> tuple[float, str]:
    """Score how well a member handles the given threat pokémon list.

    Returns (score, spanish_explanation).
    Scoring: type resistance (+2 each), type immunity (+4), STAB coverage bonus (+1),
    support role bonus (+1).
    """
    score = 0.0
    reasons: list[str] = []

    member_types = {t.lower() for t in member.pokemon.types}

    for threat in threat_mons:
        for atk_type in threat.types:
            resistance = member.pokemon.weaknesses.get(atk_type.lower(), 1.0)
            if resistance < 0.5:
                score += 4.0
                reasons.append(f"inmune a {atk_type}")
            elif resistance < 1.0:
                score += 2.0
                reasons.append(f"resiste {atk_type}")
            elif resistance > 1.0:
                score -= 1.5

        # Check if member's types can hit the threat for super-effective damage
        # using the threat's own weakness dict (reversed perspective)
        for mem_type in member_types:
            threat_weakness = threat.weaknesses.get(mem_type, 1.0)
            if threat_weakness > 1.0:
                score += 1.0
                reasons.append(f"cubre tipo {mem_type}")
                break

    support_roles = {"lead_support", "redirect", "trick_room_setter"}
    if set(member.role) & support_roles:
        score += 1.0
        reasons.append("rol de soporte")

    if not reasons:
        reasons.append("sin ventaja directa")

    explanation = f"{member.pokemon.name.title()}: {', '.join(dict.fromkeys(reasons))}"
    return score, explanation


def suggest_adjustments(
    member: TeamMember,
    threat_mons: list[PokemonData],
    legal_pool: list[str],
    meta_service: MetaService,
) -> list[AdjustmentOut]:
    adjustments: list[AdjustmentOut] = []
    threat_types = {t.lower() for threat in threat_mons for t in threat.types}

    # Move swap: suggest coverage move for the dominant threat type
    if threat_types:
        dominant_type = next(iter(threat_types))
        from pokemon_team_builder.services.damage_calc import COMMON_ATTACKS
        attack_info = COMMON_ATTACKS.get(dominant_type, {})
        if attack_info:
            move_name = attack_info.get("name", dominant_type)
            adjustments.append(AdjustmentOut(
                type="move_swap",
                target=member.pokemon.name,
                change=move_name,
                reason=f"cubre la debilidad {dominant_type} del rival con {move_name}",
            ))

    # Item swap: suggest a relevant resist berry if weak to threat type
    if threat_types:
        dominant_type = next(iter(threat_types))
        berry_map = {
            "fire": "Occa Berry", "water": "Passho Berry", "grass": "Roseli Berry",
            "electric": "Wacan Berry", "ice": "Yache Berry", "fighting": "Chople Berry",
            "poison": "Kebia Berry", "ground": "Shuca Berry", "flying": "Coba Berry",
            "psychic": "Payapa Berry", "bug": "Tanga Berry", "rock": "Charti Berry",
            "ghost": "Kasib Berry", "dragon": "Haban Berry", "dark": "Colbur Berry",
            "steel": "Babiri Berry", "fairy": "Roseli Berry", "normal": "Sitrus Berry",
        }
        berry = berry_map.get(dominant_type)
        weakness = member.pokemon.weaknesses.get(dominant_type, 1.0)
        if berry and weakness > 1.0 and member.item != berry:
            adjustments.append(AdjustmentOut(
                type="item_swap",
                target=member.pokemon.name,
                change=berry,
                reason=f"{member.pokemon.name.title()} recibe x{weakness} de {dominant_type}; {berry} reduce el daño",
            ))

    return adjustments


def analyze(
    team_names: list[str],
    threat: str,
    meta_service: MetaService,
    lookup=None,
) -> MatchupAnalysisResponse:
    """Orchestrate the full matchup analysis."""
    threat_mons = resolve_threat(threat, lookup)
    threat_names = ", ".join(m.name.title() for m in threat_mons[:2])

    team_members: list[TeamMember] = []
    for name in team_names:
        mon = _lookup_pokemon(name)
        if mon is None:
            continue
        from pokemon_team_builder.services.synergy_engine import assign_role
        from pokemon_team_builder.domain.models import SPDistribution
        roles = assign_role(mon)
        sp = SPDistribution()
        member = TeamMember(
            pokemon=mon, role=roles, sp_distribution=sp,
            item="leftovers", ability=(mon.abilities[0] if mon.abilities else "run-away"),
            nature="hardy", moves=["tackle", "growl", "scratch", "ember"],
        )
        team_members.append(member)

    if not team_members:
        raise UnknownThreatError("equipo vacío")

    scored = [(score_handler(m, threat_mons), m) for m in team_members]
    scored.sort(key=lambda x: -x[0][0])

    primary_score, primary_explanation = scored[0][0]
    primary_handler = scored[0][1]

    secondary_handler_name = ""
    secondary_handler_explanation = ""
    if len(scored) > 1:
        secondary_score, secondary_explanation = scored[1][0]
        secondary_handler = scored[1][1]
        secondary_handler_name = secondary_handler.pokemon.name
        secondary_handler_explanation = secondary_explanation

    threat_type_list = ", ".join(
        t for m in threat_mons for t in m.types
    )
    weakness_summary = (
        f"Amenaza: {threat_names}. Tipos: {threat_type_list}. "
        f"Handler principal: {primary_handler.pokemon.name.title()}."
    )

    adjustments = suggest_adjustments(
        primary_handler, threat_mons, [], meta_service
    )

    return MatchupAnalysisResponse(
        weakness_summary=weakness_summary,
        primary_handler=primary_handler.pokemon.name,
        primary_handler_explanation=primary_explanation,
        secondary_handler=secondary_handler_name,
        secondary_handler_explanation=secondary_handler_explanation,
        adjustments=adjustments,
    )
