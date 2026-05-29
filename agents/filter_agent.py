from pydantic import BaseModel, Field
from typing import Optional
from qdrant_client.models import Filter, FieldCondition, Range, MatchValue
import re

# ── Position resolution ──────────────────────────────────────────────────────
# Broad positions stored in Qdrant payload["position"]
BROAD_POSITIONS = {"defender", "attacker", "midfielder", "goalkeeper"}

# Sub-position keywords → Qdrant detailed_position codes
DETAILED_MAP = {
    # Attackers
    "winger": "winger", "left winger": "winger", "right winger": "winger",
    "kanat": "winger", "kanat oyuncusu": "winger",
    "striker": "centre-forward", "centre forward": "centre-forward",
    "center forward": "centre-forward", "centre-forward": "centre-forward",
    "forvet": "centre-forward", "santrafor": "centre-forward", "9": "centre-forward",
    "false nine": "centre-forward", "second striker": "second-striker",
    # Midfielders
    "attacking midfielder": "attacking-midfield", "attacking mid": "attacking-midfield",
    "10": "attacking-midfield", "number 10": "attacking-midfield", "playmaker": "attacking-midfield",
    "offensive midfielder": "attacking-midfield",
    "central midfielder": "central-midfield", "box to box": "central-midfield",
    "defensive midfielder": "defensive-midfield", "holding midfielder": "defensive-midfield",
    "defensive mid": "defensive-midfield", "6": "defensive-midfield",
    "kante type": "defensive-midfield", "holder": "defensive-midfield",
    "orta saha": "central-midfield", "defansif orta saha": "defensive-midfield",
    "left midfield": "left-midfield", "right midfield": "right-midfield",
    # Defenders
    "centre-back": "centre-back", "center-back": "centre-back",
    "central defender": "centre-back", "stoper": "centre-back", "cb": "centre-back",
    "left-back": "left-back", "left back": "left-back", "sol bek": "left-back",
    "right-back": "right-back", "right back": "right-back", "sağ bek": "right-back",
    "full back": "right-back", "full-back": "right-back",
    # Goalkeeper
    "keeper": "goalkeeper", "kaleci": "goalkeeper", "gk": "goalkeeper",
    "goal keeper": "goalkeeper",
}


def _resolve_position(raw: str) -> tuple[str | None, str | None]:
    """Returns (broad_position, detailed_position_code)."""
    if not raw:
        return None, None
    lower = raw.lower().strip()
    if lower in DETAILED_MAP:
        return None, DETAILED_MAP[lower]
    if lower in BROAD_POSITIONS:
        return lower, None
    # partial match
    for key, val in DETAILED_MAP.items():
        if key in lower:
            return None, val
    return lower, None


def extract_number(value: str) -> int | None:
    match = re.search(r'\d+', value)
    return int(match.group()) if match else None


# ── Schema ───────────────────────────────────────────────────────────────────

class PlayerFilter(BaseModel):
    """
    Extract ONLY the filterable criteria from a football scouting query.
    Nationality, team, league, and playing style go into the semantic query — NOT here.
    """
    position: Optional[str] = Field(
        default=None,
        description=(
            "Player position. Can be broad (defender/attacker/midfielder/goalkeeper) "
            "or specific (winger/striker/centre-back/right-back/defensive midfielder/"
            "attacking midfielder/central midfielder/etc.). "
            "Turkish: forvet/kanat/santrafor → attacker/winger, stoper/bek → defender, "
            "kaleci → goalkeeper, orta saha → midfielder, defansif → defensive midfielder."
        )
    )
    min_age: Optional[str] = Field(
        default=None,
        description="Minimum age as a number. 'experienced'/'veteran' → 30. 'over 28' → 28."
    )
    max_age: Optional[str] = Field(
        default=None,
        description="Maximum age as a number. 'young' → 23. 'youth'/'teenage' → 19. 'under 26' → 26."
    )
    min_height: Optional[str] = Field(
        default=None,
        description="Minimum height in cm. 'tall'/'physical' → 185. 'over 190cm' → 190."
    )
    max_height: Optional[str] = Field(
        default=None,
        description="Maximum height in cm. 'short'/'small' → 175."
    )


# ── Filter builder ────────────────────────────────────────────────────────────

def build_filters(player_filter: PlayerFilter) -> Filter | None:
    conditions = []

    if player_filter.position:
        broad, detailed = _resolve_position(player_filter.position)
        if detailed:
            conditions.append(
                FieldCondition(key="detailed_position", match=MatchValue(value=detailed))
            )
        elif broad:
            conditions.append(
                FieldCondition(key="position", match=MatchValue(value=broad))
            )

    for attr, op in [("min_age", "gte"), ("max_age", "lte")]:
        val = getattr(player_filter, attr)
        if val:
            num = extract_number(val)
            if num:
                conditions.append(
                    FieldCondition(key="age", range=Range(**{op: num}))
                )

    for attr, op in [("min_height", "gte"), ("max_height", "lte")]:
        val = getattr(player_filter, attr)
        if val:
            num = extract_number(val)
            if num:
                conditions.append(
                    FieldCondition(key="height", range=Range(**{op: num}))
                )

    return Filter(must=conditions) if conditions else None
