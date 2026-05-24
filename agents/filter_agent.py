from pydantic import BaseModel, Field
from typing import Optional
from llama_index.core.vector_stores import MetadataFilter, MetadataFilters
import re


def extract_number(value: str) -> int | None:
    match = re.search(r'\d+', value)
    return int(match.group()) if match else None


class PlayerFilter(BaseModel):
    """Detailed Information for a football player."""
    height: Optional[str] = Field(default=None, description="Height of the player as integer number in cm, e.g. 185")
    position: Optional[str] = Field(default=None, description="Player position, one of: defender, attacker, "
                                                              "midfielder, goalkeeper")
    age: Optional[str] = Field(default=None, description="Age of the player as integer, e.g. 25")
    nationality: Optional[str] = Field(default=None, description="Maximum age filter as integer, e.g. 30")
    team: Optional[str] = Field(default=None, description="Nationality of the player in English, e.g. English, "
                                                          "Scottish, Danish")
    league: Optional[str] = Field(default=None, description="Team name the player belongs to, e.g. Celtic, Aberdeen")


def build_filters(player_filter: PlayerFilter) -> MetadataFilters:
    filters = []
    if player_filter.position:
        filters.append(MetadataFilter(key="position", value=player_filter.position.lower(), operator="=="))
    if player_filter.height:
        num = extract_number(player_filter.height)
        if num:
            filters.append(MetadataFilter(key="height", value=num, operator="<="))
    if player_filter.age:
        num = extract_number(player_filter.age)
        if num:
            filters.append(MetadataFilter(key="age", value=num, operator="<="))
    if player_filter.nationality:
        filters.append(MetadataFilter(key="nationality", value=player_filter.nationality, operator="=="))
    if player_filter.team:
        filters.append(MetadataFilter(key="team", value=player_filter.team, operator="=="))
    if player_filter.league:
        filters.append(MetadataFilter(key="league", value=player_filter.league, operator="=="))

    return MetadataFilters(filters=filters)



