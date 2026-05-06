from __future__ import annotations

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    anchor: str = Field(min_length=1, examples=["garchomp"])
    variants: int = Field(default=3, ge=1, le=5)
    mega: str = Field(default="auto", examples=["auto", "x", "y"])


class MemberOut(BaseModel):
    name: str
    item: str
    ability: str
    nature: str
    moves: list[str]
    roles: list[str]


class VariantOut(BaseModel):
    score: float
    recommended: bool
    pokepaste: str
    members: list[MemberOut]


class GenerateResponse(BaseModel):
    anchor: str
    variants: list[VariantOut]
