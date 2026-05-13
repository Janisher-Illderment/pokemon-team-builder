from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


# Phase 2b (strategy-archetype): canonical archetype set — must stay in
# sync with ``data/archetype_weights.json`` and
# ``data.archetype_weights_loader.known_archetypes()``.
Archetype = Literal[
    "hyper_offense",
    "hard_trick_room",
    "bulky_offense",
    "weather_based",
    "stall",
    "balance",
    "perish_trap",
]


class GenerateRequest(BaseModel):
    anchor: str = Field(min_length=1, examples=["garchomp"])
    variants: int = Field(default=3, ge=1, le=5)
    mega: str = Field(default="auto", examples=["auto", "x", "y"])
    format: Literal["bo1", "bo3"] = "bo1"
    # Phase 2b: strategy archetype. Default 'balance' for backward
    # compatibility with clients that pre-date Phase 2b. Pydantic v2
    # validates the literal automatically — invalid values produce HTTP
    # 422 with the list of valid options.
    archetype: Archetype = "balance"


class MemberOut(BaseModel):
    name: str
    item: str
    ability: str
    nature: str
    moves: list[str]
    roles: list[str]
    sp_distribution: dict[str, int] = {}
    ev_note: str = ""
    move_names: list[str] = []
    mega_form_id: str | None = None


class VariantOut(BaseModel):
    score: float
    recommended: bool
    pokepaste: str
    members: list[MemberOut]
    format_mode: str = "bo1"
    lead_flexibility_score: float = 0.0
    # Phase 2b: echoes the archetype the team was generated under. The
    # UI uses this to render an archetype badge per variant.
    archetype: str = "balance"


class GenerateResponse(BaseModel):
    anchor: str
    variants: list[VariantOut]


class AdjustmentOut(BaseModel):
    type: str       # "move_swap" | "item_swap" | "pokemon_swap"
    target: str     # team member name
    change: str     # new move / new item / replacement pokemon
    reason: str     # Spanish explanation


class AnalyzeMatchupRequest(BaseModel):
    team: list[str] = Field(min_length=6, max_length=6)
    threat: str = Field(min_length=1)


class MatchupAnalysisResponse(BaseModel):
    weakness_summary: str
    primary_handler: str
    primary_handler_explanation: str
    secondary_handler: str = ""
    secondary_handler_explanation: str = ""
    adjustments: list[AdjustmentOut] = []


# ---------------------------------------------------------------------------
# Team editor schemas (PATCH /edit-member)
# ---------------------------------------------------------------------------

EditKind = Literal["move_swap", "item_swap", "pokemon_swap"]


class MoveSwapEdit(BaseModel):
    kind: Literal["move_swap"]
    slot_index: int = Field(ge=0, le=3)
    new_move: str = Field(min_length=1)


class ItemSwapEdit(BaseModel):
    kind: Literal["item_swap"]
    new_item: str = Field(min_length=1)


class PokemonSwapEdit(BaseModel):
    kind: Literal["pokemon_swap"]
    new_pokemon_name: str = Field(min_length=1)


Edit = Annotated[
    Union[MoveSwapEdit, ItemSwapEdit, PokemonSwapEdit],
    Field(discriminator="kind"),
]


class MemberIn(BaseModel):
    """Compact member representation sent from client — server rehydrates PokemonData."""
    name: str = Field(min_length=1)
    role: list[str] = Field(min_length=1)
    item: str = Field(min_length=1)
    ability: str = Field(min_length=1)
    nature: str = Field(min_length=1)
    moves: list[str] = Field(min_length=4, max_length=4)
    sp_distribution: dict[str, int] = {}
    mega_form_id: str | None = None


class VariantIn(BaseModel):
    members: list[MemberIn] = Field(min_length=6, max_length=6)
    score: float = 0.0
    format_mode: str = "bo1"


class EditMemberRequest(BaseModel):
    variant: VariantIn
    member_index: int = Field(ge=0, le=5)
    edit: Edit


# ---------------------------------------------------------------------------
# PokePaste import schemas (POST /import)
# ---------------------------------------------------------------------------

class ImportRequest(BaseModel):
    pokepaste: str = Field(min_length=1)


class ImportResponse(VariantOut):
    import_warnings: list[str] = []


# ---------------------------------------------------------------------------
# Meta-sources schemas (GET /meta-teams, GET /tournaments)
# ---------------------------------------------------------------------------

class LabMausMemberOut(BaseModel):
    name: str
    item: str | None = None
    moves: list[str] = []


class LabMausTeamOut(BaseModel):
    members: list[LabMausMemberOut]
    player: str
    tournament: str
    placement: int
    pokepaste_url: str
    regulation: str


class MetaTeamsResponse(BaseModel):
    regulation: str
    teams: list[LabMausTeamOut]
    stale: bool


class TournamentOut(BaseModel):
    id: str
    name: str
    date: str
    city: str
    country: str
    regulation: str
    lat: float
    lon: float
    url: str = ""


class TournamentsResponse(BaseModel):
    tournaments: list[TournamentOut]
    stale: bool
