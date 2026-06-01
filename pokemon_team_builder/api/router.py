from __future__ import annotations

from fastapi import APIRouter, HTTPException

from pokemon_team_builder.api.schemas import (
    AnalyzeMatchupRequest,
    EditMemberRequest,
    GenerateRequest,
    GenerateResponse,
    ImportRequest,
    ImportResponse,
    LabMausMemberOut,
    LabMausTeamOut,
    MatchupAnalysisResponse,
    MemberIn,
    MemberOut,
    MemberRatingOut,
    MetaTeamsResponse,
    OptimizedChangeOut,
    OptimizeTeamRequest,
    OptimizeTeamResponse,
    PresetKitOut,
    RateTeamRequest,
    SpReadOut,
    SuggestionOut,
    TeamRatingOut,
    TournamentOut,
    TournamentsResponse,
    VariantIn,
    VariantOut,
)
from pokemon_team_builder.cli.main import _lazy_pool_candidates
from pokemon_team_builder.data.legal_pool_loader import is_legal
from pokemon_team_builder.data.speed_tiers import load as load_speed_db
from pokemon_team_builder.domain.exceptions import TeamBuildError
from pokemon_team_builder.domain.models import SPDistribution
from pokemon_team_builder.services import preset_kit_builder, sp_preset_builder
from pokemon_team_builder.services import meta_versions as _meta_versions_mod
from pokemon_team_builder.services import pokemon_lookup
from pokemon_team_builder.services import ev_explainer
from pokemon_team_builder.services.meta_service import MetaService
from pokemon_team_builder.services.replica_exporter import to_pokepaste
from pokemon_team_builder.services import matchup_analyzer
from pokemon_team_builder.services.matchup_analyzer import UnknownThreatError
from pokemon_team_builder.data.mega_loader import load_mega_evolutions
from pokemon_team_builder.domain.models import MegaForm, TeamMember, TeamVariant
from pokemon_team_builder.services import team_editor, viability_rater
from pokemon_team_builder.services import pokepaste_parser
from pokemon_team_builder.services import team_rater
from pokemon_team_builder.services import team_optimizer
from pokemon_team_builder.services.team_generator import generate_team
from pokemon_team_builder.services import labmaus_service, tournament_service

router = APIRouter()

_speed_db = load_speed_db()
_meta_svc = MetaService()


def _build_sp_dict(sp: SPDistribution) -> dict[str, int]:
    return {
        k: v for k, v in {
            "hp": sp.hp, "atk": sp.atk, "def": sp.def_,
            "spa": sp.spa, "spd": sp.spd, "spe": sp.spe,
        }.items() if v > 0
    }


def _build_sp_presets(member: TeamMember) -> dict[str, SpReadOut]:
    """Build the per-member SP presets dict for the API response.

    Returns ``{}`` on any failure — the UI gracefully falls back to the
    legacy ``sp_distribution`` field when presets are absent.
    """
    try:
        presets = sp_preset_builder.build_presets(
            member, member.item, member.nature,
            threats_to_OHKO=None, threats_to_survive=None,
        )
    except Exception:
        return {}
    return {
        name: SpReadOut(
            hp=read.hp, atk=read.atk, **{"def": read.def_},
            spa=read.spa, spd=read.spd, spe=read.spe,
        )
        for name, read in presets.items()
    }


def _build_preset_kits(
    member: TeamMember,
    *,
    defensive_used_items: set[str] | None = None,
) -> dict[str, PresetKitOut]:
    """Build full Ofensivo/Defensivo kits for the API response.

    Each kit carries its own item, ability, nature, moves, and SPs so the
    UI toggle can swap the whole member card without falling back to the
    offensive build for the missing fields.

    Returns ``{}`` on any failure — the UI gracefully falls back to the
    legacy ``sp_presets`` SPs-only view when this dict is absent.
    """
    try:
        # The visible item on a Mega-evolved anchor is the mega stone, not
        # member.item — use the same precedence as MemberOut.item below so
        # the Ofensivo kit echoes what the user actually sees.
        visible_item = member.mega_form.mega_stone if member.mega_form else member.item
        kits = preset_kit_builder.build_kits(
            member.pokemon,
            item=visible_item,
            ability=member.ability,
            nature=member.nature,
            moves=member.moves,
            sp_distribution=member.sp_distribution,
            defensive_used_items=defensive_used_items,
        )
    except Exception:
        return {}
    return {
        name: PresetKitOut(
            item=kit.item,
            ability=kit.ability,
            nature=kit.nature,
            moves=list(kit.moves),
            sp_distribution=_build_sp_dict(kit.sp_distribution),
        )
        for name, kit in kits.items()
    }


@router.get("/health")
def health() -> dict[str, object]:
    """Health endpoint — Phase 3 §13 exposes loaded data versions."""
    return {"status": "ok", "meta_versions": _meta_versions_mod.collect()}


@router.get("/legal-pool")
def legal_pool() -> dict[str, list[str]]:
    from pokemon_team_builder.data.legal_pool_loader import get_all_names
    return {"names": sorted(get_all_names())}


@router.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest) -> GenerateResponse:
    name = req.anchor.strip().lower()
    if not is_legal(name):
        raise HTTPException(
            status_code=422,
            detail=f"'{req.anchor}' is not in the M-A regulation pool",
        )

    try:
        anchor = pokemon_lookup.lookup(name)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        variants = generate_team(
            anchor,
            num_variants=req.variants,
            candidate_loader=_lazy_pool_candidates,
            mega_choice=req.mega,
            format_mode=req.format,
            archetype=req.archetype,
            team_sheet=req.team_sheet,
        )
    except TeamBuildError as exc:
        # Pool exhaustion / cold-cache / structural pool issues → 503 so the
        # client knows to retry, vs a 200 with empty variants which silently
        # masks the problem (Phase 4b fail-clearly fix).
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    variant_outs = []
    versions = _meta_versions_mod.collect()
    for v in variants:
        defensive_used: set[str] = set()
        members = []
        for m in v.members:
            kits = _build_preset_kits(m, defensive_used_items=defensive_used)
            if "defensive" in kits:
                defensive_used.add(kits["defensive"].item)
            members.append(MemberOut(
                name=m.pokemon.name,
                item=m.mega_form.mega_stone if m.mega_form else m.item,
                ability=m.ability,
                nature=m.nature,
                moves=m.moves,
                roles=m.role,
                sp_distribution=_build_sp_dict(m.sp_distribution),
                ev_note=ev_explainer.explain(
                    m, _speed_db, _meta_svc, archetype=v.archetype,
                ),
                move_names=m.pokemon.move_names,
                sp_presets=_build_sp_presets(m),
                preset_kits=kits,
            ))
        variant_outs.append(
            VariantOut(
                score=round(v.score, 2),
                recommended=v.is_recommended,
                pokepaste=to_pokepaste(v),
                members=members,
                format_mode=req.format,
                core_flexibility_score=round(v.core_flexibility_ratio, 4),
                archetype=v.archetype,
                requires_speed_control=viability_rater.variant_requires_speed_control(
                    v, v.archetype,
                ),
                meta_versions=versions,
                team_sheet=v.team_sheet if v.team_sheet in ("open", "closed") else "closed",
            )
        )

    return GenerateResponse(anchor=anchor.name, variants=variant_outs)


def _dict_to_sp(d: dict[str, int]) -> SPDistribution:
    return SPDistribution(
        hp=d.get("hp", 0),
        atk=d.get("atk", 0),
        **{"def": d.get("def", 0)},
        spa=d.get("spa", 0),
        spd=d.get("spd", 0),
        spe=d.get("spe", 0),
    )


def _hydrate_variant(v_in: VariantIn) -> TeamVariant:
    """Reconstruct a TeamVariant domain object from the compact VariantIn payload."""
    all_megas = load_mega_evolutions()
    members: list[TeamMember] = []
    for m_in in v_in.members:
        slug = m_in.name.strip().lower()
        try:
            pokemon = pokemon_lookup.lookup(slug)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"No se puede resolver '{slug}': {exc}",
            ) from exc

        mega_form: MegaForm | None = None
        if m_in.mega_form_id:
            species_megas = all_megas.get(slug, [])
            mega_form = next(
                (mf for mf in species_megas if mf.form_id == m_in.mega_form_id),
                None,
            )

        members.append(TeamMember(
            pokemon=pokemon,
            role=m_in.role,
            sp_distribution=_dict_to_sp(m_in.sp_distribution),
            item=m_in.item,
            ability=m_in.ability,
            nature=m_in.nature,
            moves=m_in.moves,
            mega_form=mega_form,
        ))
    return TeamVariant(
        members=members,
        score=v_in.score,
        score_explanation="",
        is_recommended=False,
        # Phase 3 §11 rename (BREAKING).
        core_flexibility_ratio=0.0,
    )


def _variant_to_out(v: TeamVariant, *, format_mode: str = "bo1") -> VariantOut:
    defensive_used: set[str] = set()
    members = []
    for m in v.members:
        kits = _build_preset_kits(m, defensive_used_items=defensive_used)
        if "defensive" in kits:
            defensive_used.add(kits["defensive"].item)
        members.append(MemberOut(
            name=m.pokemon.name,
            item=m.mega_form.mega_stone if m.mega_form else m.item,
            ability=m.ability,
            nature=m.nature,
            moves=m.moves,
            roles=m.role,
            sp_distribution=_build_sp_dict(m.sp_distribution),
            ev_note=ev_explainer.explain(
                m, _speed_db, _meta_svc, archetype=v.archetype,
            ),
            move_names=m.pokemon.move_names,
            mega_form_id=m.mega_form.form_id if m.mega_form else None,
            sp_presets=_build_sp_presets(m),
            preset_kits=kits,
        ))
    return VariantOut(
        score=round(v.score, 2),
        recommended=v.is_recommended,
        pokepaste=to_pokepaste(v),
        members=members,
        format_mode=format_mode,
        core_flexibility_score=round(v.core_flexibility_ratio, 4),
        archetype=v.archetype,
        requires_speed_control=viability_rater.variant_requires_speed_control(
            v, v.archetype,
        ),
        meta_versions=_meta_versions_mod.collect(),
        team_sheet=v.team_sheet if v.team_sheet in ("open", "closed") else "closed",
    )


@router.patch("/edit-member", response_model=VariantOut)
def edit_member(req: EditMemberRequest) -> VariantOut:
    try:
        variant = _hydrate_variant(req.variant)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        updated = team_editor.apply_edit(variant, req.member_index, req.edit.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return _variant_to_out(updated, format_mode=req.variant.format_mode)


@router.post("/import", response_model=ImportResponse)
def import_pokepaste(req: ImportRequest) -> ImportResponse:
    try:
        variant, warnings = pokepaste_parser.parse_pokepaste(req.pokepaste)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    score, flex = viability_rater.score_team(variant)
    explanation = viability_rater.generate_explanation(variant, score)
    variant = variant.model_copy(update={
        "score": score,
        "score_explanation": explanation,
        "is_recommended": True,
        # Phase 3 §11 rename (BREAKING) — replaces lead_flexibility_ratio.
        "core_flexibility_ratio": flex,
    })

    base_out = _variant_to_out(variant)
    return ImportResponse(
        score=base_out.score,
        recommended=base_out.recommended,
        pokepaste=base_out.pokepaste,
        members=base_out.members,
        format_mode=base_out.format_mode,
        core_flexibility_score=base_out.core_flexibility_score,
        archetype=base_out.archetype,
        requires_speed_control=base_out.requires_speed_control,
        meta_versions=base_out.meta_versions,
        team_sheet=base_out.team_sheet,
        import_warnings=warnings,
    )


def _team_rating_to_out(rating: team_rater.TeamRating) -> TeamRatingOut:
    """Serializa un TeamRating (servicio) a TeamRatingOut (API) — ADR §7."""
    return TeamRatingOut(
        score=rating.score,
        detected_archetype=rating.detected_archetype,
        archetype_confidence=rating.archetype_confidence,
        strengths=list(rating.strengths),
        weaknesses=list(rating.weaknesses),
        members=[
            MemberRatingOut(
                name=m.name,
                score=m.score,
                fit=m.fit,
                intrinsic=m.intrinsic,
                coherence=m.coherence,
                moves=list(m.moves),
                strengths=list(m.strengths),
                weaknesses=list(m.weaknesses),
                suggestions=[
                    SuggestionOut(
                        kind=s.kind,
                        target_field=s.target_field,
                        from_value=s.from_value,
                        to_value=s.to_value,
                        reason=s.reason_es,
                        priority=s.priority,
                    )
                    for s in m.suggestions
                ],
                role=m.role,
                sp=dict(m.sp),
                stats=dict(m.stats),
            )
            for m in rating.members
        ],
        import_warnings=list(rating.import_warnings),
    )


@router.post("/rate-team", response_model=TeamRatingOut)
def rate_team_endpoint(req: RateTeamRequest) -> TeamRatingOut:
    try:
        variant, warnings = pokepaste_parser.parse_pokepaste(req.pokepaste)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    rating = team_rater.rate_team(variant, import_warnings=warnings)
    return _team_rating_to_out(rating)


def _optimization_to_out(
    result: team_optimizer.OptimizationResult,
) -> OptimizeTeamResponse:
    """Serializa un OptimizationResult (servicio) a OptimizeTeamResponse (API).

    Reusa SuggestionOut (mismo mapeo reason_es→reason que _team_rating_to_out).
    """
    return OptimizeTeamResponse(
        score_before=result.score_before,
        score_after=result.score_after,
        delta_total=result.delta_total,
        detected_archetype=result.detected_archetype,
        archetype_confidence=result.archetype_confidence,
        pokepaste_after=result.pokepaste_after,
        locked_indices=list(result.locked_indices),
        changes=[
            OptimizedChangeOut(
                member_index=c.member_index,
                member_name=c.member_name,
                delta=c.delta,
                suggestions=[
                    SuggestionOut(
                        kind=s.kind,
                        target_field=s.target_field,
                        from_value=s.from_value,
                        to_value=s.to_value,
                        reason=s.reason_es,
                        priority=s.priority,
                    )
                    for s in c.suggestions
                ],
            )
            for c in result.changes
        ],
        import_warnings=list(result.import_warnings),
    )


@router.post("/optimize-team", response_model=OptimizeTeamResponse)
def optimize_team_endpoint(req: OptimizeTeamRequest) -> OptimizeTeamResponse:
    try:
        variant, warnings = pokepaste_parser.parse_pokepaste(req.pokepaste)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Validación de locked_indices: cada índice ∈ [0,5]; dedup + orden estable.
    # (len puede ser 6 → all-locked = no-op, NO error, ADR §5.2.)
    for idx in req.locked_indices:
        if idx < 0 or idx > 5:
            raise HTTPException(
                status_code=422,
                detail=f"locked_indices fuera de rango [0,5]: {idx}",
            )
    locked = sorted(set(req.locked_indices))

    result = team_optimizer.optimize_team(
        variant, locked, import_warnings=warnings
    )
    return _optimization_to_out(result)


@router.post("/analyze-matchup", response_model=MatchupAnalysisResponse)
def analyze_matchup(req: AnalyzeMatchupRequest) -> MatchupAnalysisResponse:
    if len(req.team) != 6:
        raise HTTPException(
            status_code=422,
            detail="El equipo debe tener exactamente 6 Pokémon",
        )
    try:
        return matchup_analyzer.analyze(
            team_names=req.team,
            threat=req.threat,
            meta_service=_meta_svc,
        )
    except UnknownThreatError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Amenaza desconocida: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/meta-teams", response_model=MetaTeamsResponse)
def get_meta_teams(regulation: str = "M-A") -> MetaTeamsResponse:
    teams = labmaus_service.get_top_teams(regulation)
    team_outs = [
        LabMausTeamOut(
            members=[LabMausMemberOut(name=m.name, item=m.item, moves=m.moves) for m in t.members],
            player=t.player,
            tournament=t.tournament,
            placement=t.placement,
            pokepaste_url=t.pokepaste_url,
            regulation=t.regulation,
        )
        for t in teams
    ]
    return MetaTeamsResponse(
        regulation=regulation,
        teams=team_outs,
        stale=len(team_outs) == 0,
    )


@router.get("/tournaments", response_model=TournamentsResponse)
def get_tournaments(
    lat: float | None = None,
    lon: float | None = None,
    radius: int | None = None,
) -> TournamentsResponse:
    kwargs: dict = {}
    if lat is not None:
        kwargs["lat"] = lat
    if lon is not None:
        kwargs["lon"] = lon
    if radius is not None:
        kwargs["radius_miles"] = radius
    items = tournament_service.get_upcoming(**kwargs)
    tournament_outs = [
        TournamentOut(
            id=t.id,
            name=t.name,
            date=t.date,
            city=t.city,
            country=t.country,
            regulation=t.regulation,
            lat=t.lat,
            lon=t.lon,
            url=t.url,
        )
        for t in items
    ]
    return TournamentsResponse(
        tournaments=tournament_outs,
        stale=len(tournament_outs) == 0,
    )
