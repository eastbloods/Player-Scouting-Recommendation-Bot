from pydantic import BaseModel, Field
from typing import Optional
from llama_index.core.vector_stores import MetadataFilter, MetadataFilters
import re


def extract_number(value: str) -> int | None:
    match = re.search(r'\d+', value)
    return int(match.group()) if match else None


class PlayerFilter(BaseModel):
    """Extract structured filters from a football player search query."""

    min_height: Optional[str] = Field(
        default=None,
        description="Minimum height in cm, e.g. '185'. Use when query says 'tall', 'over Xcm', 'at least Xcm'."
    )
    max_height: Optional[str] = Field(
        default=None,
        description="Maximum height in cm, e.g. '175'. Use when query says 'short', 'under Xcm', 'at most Xcm'."
    )
    position: Optional[str] = Field(
        default=None,
        description=(
            "Player position. Must be one of: defender, attacker, midfielder, goalkeeper. "
            "Map sub-positions: striker/forward/winger/centre-forward → attacker. "
            "centre-back/full-back/left-back/right-back → defender. "
            "Turkish: forvet/kanat/santrafor → attacker, defans/stoper/bek → defender, "
            "kaleci → goalkeeper, orta saha → midfielder."
        )
    )
    min_age: Optional[str] = Field(
        default=None,
        description="Minimum age. Use when query says 'over X', 'older than X', 'experienced', 'veteran' (use 30)."
    )
    max_age: Optional[str] = Field(
        default=None,
        description="Maximum age. Use when query says 'under X', 'young' (use 23), 'youth', 'teenage' (use 19)."
    )
    nationality: Optional[str] = Field(
        default=None,
        description="Player nationality in English, e.g. 'French', 'Scottish', 'Danish'."
    )
    team: Optional[str] = Field(
        default=None,
        description="Team/club name, e.g. 'Celtic', 'Rangers', 'Aberdeen'."
    )
    league: Optional[str] = Field(
        default=None,
        description="League name, e.g. 'Premiership', 'Championship'."
    )


def build_filters(player_filter: PlayerFilter) -> MetadataFilters:
    filters = []

    if player_filter.position:
        filters.append(MetadataFilter(key="position", value=player_filter.position.lower(), operator="=="))

    if player_filter.min_height:
        num = extract_number(player_filter.min_height)
        if num:
            filters.append(MetadataFilter(key="height", value=num, operator=">="))

    if player_filter.max_height:
        num = extract_number(player_filter.max_height)
        if num:
            filters.append(MetadataFilter(key="height", value=num, operator="<="))

    if player_filter.min_age:
        num = extract_number(player_filter.min_age)
        if num:
            filters.append(MetadataFilter(key="age", value=num, operator=">="))

    if player_filter.max_age:
        num = extract_number(player_filter.max_age)
        if num:
            filters.append(MetadataFilter(key="age", value=num, operator="<="))

    if player_filter.nationality:
        filters.append(MetadataFilter(key="nationality", value=player_filter.nationality, operator="=="))

    if player_filter.team:
        filters.append(MetadataFilter(key="team", value=player_filter.team, operator="=="))

    if player_filter.league:
        filters.append(MetadataFilter(key="league", value=player_filter.league, operator="=="))

    return MetadataFilters(filters=filters)
