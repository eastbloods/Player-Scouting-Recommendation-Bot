from pydantic import BaseModel
from typing import Optional


class SearchPlayerRequest(BaseModel):
    text: str = ""
    # Hard filters from UI panel (bypass LLM extraction when set)
    position: Optional[str] = None          # e.g. "winger", "centre-back"
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    min_height: Optional[int] = None
    max_height: Optional[int] = None
    nationality: Optional[str] = None       # player nationality e.g. "France"
    league: Optional[str] = None            # exact league name e.g. "Super Lig"
    team_country: Optional[str] = None      # country where team plays e.g. "Portugal"
    team: Optional[str] = None              # specific team name (semantic filter)


class SearchPlayerResponse(BaseModel):
    text: str
