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

# C1 (2026-05-14): team sheet visibility — affects whether opponent sees
# the team before lead selection. Decouples sheet visibility from Bo1/Bo3
# since Bo1 is NOT always closed in casual leagues.
#   "auto"   → bo3 = open, bo1 = closed (current default behavior)
#   "open"   → opponent will see all 6, cheese moves less valuable
#   "closed" → opponent picks blind, lure / surprise sets viable
TeamSheet = Literal["auto", "open", "closed"]


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
    # C1: team sheet visibility (open/closed). Default "auto" preserves
    # legacy behavior (bo3=open, bo1=closed). Override with explicit
    # "open" / "closed" for casual leagues that don't follow that pattern.
    team_sheet: TeamSheet = "auto"


class SpReadOut(BaseModel):
    """Phase 3 §9 — single SP preset (sums to 66, max 32 per stat)."""

    hp: int = 0
    atk: int = 0
    def_: int = Field(default=0, alias="def")
    spa: int = 0
    spd: int = 0
    spe: int = 0

    model_config = {"populate_by_name": True}


class PresetKitOut(BaseModel):
    """v0.10.1 (2026-05-15) — full kit per preset (offensive | defensive).

    Replaces the previous SPs-only ``sp_presets`` view. The defensive
    kit carries its own item / ability / nature / moves so toggling
    preset in the UI swaps the whole card, not just the SP grid.
    """

    item: str
    ability: str
    nature: str
    moves: list[str] = []
    sp_distribution: dict[str, int] = {}


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
    # Phase 3 §9 — keyed dict ``{"offensive": SpReadOut, "defensive": SpReadOut}``.
    # Empty dict for imported/edited variants that pre-date Phase 3 — UI
    # falls back to the legacy ``sp_distribution`` field in that case.
    sp_presets: dict[str, SpReadOut] = {}
    # v0.10.1: full per-preset kit (item + ability + nature + moves + SPs)
    # so the UI Ofensivo/Defensivo toggle swaps the entire member card.
    # Empty dict for imported / edited variants that pre-date this field.
    preset_kits: dict[str, PresetKitOut] = {}


class VariantOut(BaseModel):
    score: float
    recommended: bool
    pokepaste: str
    members: list[MemberOut]
    format_mode: str = "bo1"
    # Phase 3 §11 — renamed from ``lead_flexibility_score`` (BREAKING).
    core_flexibility_score: float = 0.0
    # Phase 2b: echoes the archetype the team was generated under. The
    # UI uses this to render an archetype badge per variant.
    archetype: str = "balance"
    # Phase 3 §10 — true when the team has no speed-control mechanism
    # and archetype != "stall". UI renders a warning banner.
    requires_speed_control: bool = False
    # Phase 3 §13 — data-file versions baked into this team. Keys:
    # legal_pool, items, weather, archetype_weights, sp_mechanics,
    # ability_roles, meta_teams. Missing files default to 0.
    meta_versions: dict[str, int] = {}
    # C1 (2026-05-14): resolved team_sheet for this variant. Always
    # "open" or "closed" (never "auto" — that's resolved server-side).
    team_sheet: Literal["open", "closed"] = "closed"


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
    pokepaste: str = Field(min_length=1, max_length=20000)


class ImportResponse(VariantOut):
    import_warnings: list[str] = []


# ---------------------------------------------------------------------------
# Team Rater schemas (POST /rate-team) — ADR docs/adr-team-rater.md §7
# ---------------------------------------------------------------------------

class RateTeamRequest(BaseModel):
    # max_length: a 6-mon PokePaste is ~1KB; 20000 is generous headroom and
    # bounds the per-request compute (rate-team runs several lookups per
    # member). Oversized payloads get a 422 instead of a slow response.
    pokepaste: str = Field(min_length=1, max_length=20000)


class SuggestionOut(BaseModel):
    kind: Literal["move_swap", "nature", "evs", "item"]
    target_field: str
    from_value: str
    to_value: str
    reason: str          # español
    priority: int


class MemberRatingOut(BaseModel):
    name: str
    score: int           # 1..100
    fit: float
    intrinsic: float
    coherence: float
    moves: list[str] = []
    strengths: list[str] = []
    weaknesses: list[str] = []
    suggestions: list[SuggestionOut] = []
    # Adiciones display "Valorar equipo": rol primario legible (ES) y EVs/SP
    # por stat. Defaults retrocompatibles (clientes viejos no se rompen).
    role: str = ""
    sp: dict[str, int] = {}
    stats: dict[str, int] = {}        # stats finales de combate (lvl50) para el hexágono
    base_stats: dict[str, int] = {}   # stats finales SIN EVs (0 SP) — anillo base del hexágono


class TeamRatingOut(BaseModel):
    score: float
    detected_archetype: str
    archetype_confidence: float
    strengths: list[str] = []
    weaknesses: list[str] = []
    members: list[MemberRatingOut]
    import_warnings: list[str] = []


# ---------------------------------------------------------------------------
# Team Optimizer schemas (POST /optimize-team) — ADR docs/adr-team-optimizer.md §5.2
# ---------------------------------------------------------------------------

class OptimizeTeamRequest(BaseModel):
    # Misma forma que RateTeamRequest + locked_indices (mínima superficie nueva).
    pokepaste: str = Field(min_length=1, max_length=20000)
    # Índices 0..5 de los mons FIJADOS (no se tocan). Validados en el endpoint:
    # cada índice ∈ [0,5], deduplicado. all-locked NO es error (no-op).
    locked_indices: list[int] = []


class OptimizedChangeOut(BaseModel):
    member_index: int
    member_name: str
    delta: float
    suggestions: list[SuggestionOut] = []   # reusa SuggestionOut existente


class OptimizeTeamResponse(BaseModel):
    score_before: float
    score_after: float
    delta_total: float
    detected_archetype: str
    archetype_confidence: float
    pokepaste_after: str
    locked_indices: list[int] = []
    changes: list[OptimizedChangeOut] = []
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
