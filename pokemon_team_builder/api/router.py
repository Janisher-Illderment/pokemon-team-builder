from __future__ import annotations

from fastapi import APIRouter, HTTPException

from pokemon_team_builder.api.schemas import (
    AnalyzeMatchupRequest,
    EditMemberRequest,
    GenerateRequest,
    GenerateResponse,
    ImportRequest,
    ImportResponse,
    MatchupAnalysisResponse,
    MemberIn,
    MemberOut,
    VariantIn,
    VariantOut,
)
from pokemon_team_builder.cli.main import _lazy_pool_candidates
from pokemon_team_builder.data.legal_pool_loader import is_legal
from pokemon_team_builder.data.speed_tiers import load as load_speed_db
from pokemon_team_builder.domain.models import SPDistribution
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
from pokemon_team_builder.services.team_generator import generate_team

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


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    variant_outs = []
    for v in variants:
        members = [
            MemberOut(
                name=m.pokemon.name,
                item=m.mega_form.mega_stone if m.mega_form else m.item,
                ability=m.ability,
                nature=m.nature,
                moves=m.moves,
                roles=m.role,
                sp_distribution=_build_sp_dict(m.sp_distribution),
                ev_note=ev_explainer.explain(m, _speed_db, _meta_svc),
                move_names=m.pokemon.move_names,
            )
            for m in v.members
        ]
        variant_outs.append(
            VariantOut(
                score=round(v.score, 2),
                recommended=v.is_recommended,
                pokepaste=to_pokepaste(v),
                members=members,
                format_mode=req.format,
                lead_flexibility_score=round(v.lead_flexibility_ratio, 4),
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
        lead_flexibility_ratio=0.0,
    )


def _variant_to_out(v: TeamVariant, *, format_mode: str = "bo1") -> VariantOut:
    members = [
        MemberOut(
            name=m.pokemon.name,
            item=m.mega_form.mega_stone if m.mega_form else m.item,
            ability=m.ability,
            nature=m.nature,
            moves=m.moves,
            roles=m.role,
            sp_distribution=_build_sp_dict(m.sp_distribution),
            ev_note=ev_explainer.explain(m, _speed_db, _meta_svc),
            move_names=m.pokemon.move_names,
        )
        for m in v.members
    ]
    return VariantOut(
        score=round(v.score, 2),
        recommended=v.is_recommended,
        pokepaste=to_pokepaste(v),
        members=members,
        format_mode=format_mode,
        lead_flexibility_score=round(v.lead_flexibility_ratio, 4),
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
        "lead_flexibility_ratio": flex,
    })

    base_out = _variant_to_out(variant)
    return ImportResponse(
        score=base_out.score,
        recommended=base_out.recommended,
        pokepaste=base_out.pokepaste,
        members=base_out.members,
        format_mode=base_out.format_mode,
        lead_flexibility_score=base_out.lead_flexibility_score,
        import_warnings=warnings,
    )


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
