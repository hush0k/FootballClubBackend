from pydantic import BaseModel, ConfigDict, Field

from app.team.models import League


class TeamBase(BaseModel):
    name: str = Field(max_length=100)
    img_url: str = Field(max_length=255)
    power: int = Field(ge=0, le=100)
    stadium: str = Field(max_length=100)
    league: League = League.LALIGA


class TeamCreate(TeamBase):
    pass


class TeamUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    img_url: str | None = Field(default=None, max_length=255)
    power: int | None = Field(default=None, ge=0, le=100)
    stadium: str | None = Field(default=None, max_length=100)
    league: League | None = None


class TeamRead(TeamBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
