from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pokemon_team_builder.config import MAX_SP_STAT, MAX_SP_TOTAL


class BaseStats(BaseModel):
    # `def` is a Python keyword, so the field is named `def_` and aliased to "def".
    model_config = ConfigDict(populate_by_name=True)

    hp: int = Field(ge=1)
    atk: int = Field(ge=1)
    def_: int = Field(ge=1, alias="def")
    spa: int = Field(ge=1)
    spd: int = Field(ge=1)
    spe: int = Field(ge=1)


class PokemonData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(ge=1)
    name: str = Field(min_length=1)
    types: list[str] = Field(min_length=1, max_length=2)
    base_stats: BaseStats
    move_names: list[str]
    weaknesses: dict[str, float] = Field(default_factory=dict)


class TypeChart(BaseModel):
    chart: dict[str, dict[str, float]]


class SPDistribution(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    hp: int = Field(default=0, ge=0)
    atk: int = Field(default=0, ge=0)
    def_: int = Field(default=0, ge=0, alias="def")
    spa: int = Field(default=0, ge=0)
    spd: int = Field(default=0, ge=0)
    spe: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_sp_limits(self) -> "SPDistribution":
        for stat_name, value in (
            ("hp", self.hp),
            ("atk", self.atk),
            ("def", self.def_),
            ("spa", self.spa),
            ("spd", self.spd),
            ("spe", self.spe),
        ):
            if value > MAX_SP_STAT:
                raise ValueError(
                    f"SP for '{stat_name}' is {value}, "
                    f"max per stat is {MAX_SP_STAT}"
                )
        total = self.hp + self.atk + self.def_ + self.spa + self.spd + self.spe
        if total > MAX_SP_TOTAL:
            raise ValueError(
                f"Total SP is {total}, max total is {MAX_SP_TOTAL}"
            )
        return self


class TeamMember(BaseModel):
    pokemon: PokemonData
    role: list[str] = Field(min_length=1)
    sp_distribution: SPDistribution
    item: str = Field(min_length=1)
    ability: str = Field(min_length=1)
    nature: str = Field(min_length=1)
    moves: list[str] = Field(min_length=4, max_length=4)


class TeamVariant(BaseModel):
    members: list[TeamMember] = Field(min_length=6, max_length=6)
    score: float = 0.0
    score_explanation: str = ""
    is_recommended: bool = False
