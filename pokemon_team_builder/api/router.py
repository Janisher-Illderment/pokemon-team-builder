from __future__ import annotations

from fastapi import APIRouter, HTTPException

from pokemon_team_builder.api.schemas import (
    GenerateRequest,
    GenerateResponse,
    MemberOut,
    VariantOut,
)
from pokemon_team_builder.cli.main import _lazy_pool_candidates
from pokemon_team_builder.data.legal_pool_loader import is_legal
from pokemon_team_builder.services import pokemon_lookup
from pokemon_team_builder.services.replica_exporter import to_pokepaste
from pokemon_team_builder.services.team_generator import generate_team

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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
            )
            for m in v.members
        ]
        variant_outs.append(
            VariantOut(
                score=round(v.score, 2),
                recommended=v.is_recommended,
                pokepaste=to_pokepaste(v),
                members=members,
            )
        )

    return GenerateResponse(anchor=anchor.name, variants=variant_outs)
