from pydantic import BaseModel, Field
from typing import Optional
from qdrant_client.models import Filter, FieldCondition, Range, MatchValue
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
        description="League name, e.g. 'Premier League', 'La Liga', 'Bundesliga'."
    )


def build_filters(player_filter: PlayerFilter) -> Filter | None:
    """Build a native Qdrant Filter from extracted player criteria."""
    conditions = []

    if player_filter.position:
        conditions.append(
            FieldCondition(key="position", match=MatchValue(value=player_filter.position.lower()))
        )

    if player_filter.min_height:
        num = extract_number(player_filter.min_height)
        if num:
            conditions.append(FieldCondition(key="height", range=Range(gte=num)))

    if player_filter.max_height:
        num = extract_number(player_filter.max_height)
        if num:
            conditions.append(FieldCondition(key="height", range=Range(lte=num)))

    if player_filter.min_age:
        num = extract_number(player_filter.min_age)
        if num:
            conditions.append(FieldCondition(key="age", range=Range(gte=num)))

    if player_filter.max_age:
        num = extract_number(player_filter.max_age)
        if num:
            conditions.append(FieldCondition(key="age", range=Range(lte=num)))

    if player_filter.nationality:
        conditions.append(
            FieldCondition(key="nationality", match=MatchValue(value=player_filter.nationality))
        )

    if player_filter.team:
        conditions.append(
            FieldCondition(key="team", match=MatchValue(value=player_filter.team))
        )

    if player_filter.league:
        conditions.append(
            FieldCondition(key="league", match=MatchValue(value=player_filter.league))
        )

    return Filter(must=conditions) if conditions else None
