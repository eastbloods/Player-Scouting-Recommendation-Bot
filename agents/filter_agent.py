from pydantic import BaseModel, Field
from typing import Optional
from qdrant_client.models import Filter, FieldCondition, Range, MatchValue, MinShould
import re

# ── Position resolution ──────────────────────────────────────────────────────
# Broad positions stored in Qdrant payload["position"]
BROAD_POSITIONS = {"defender", "attacker", "midfielder", "goalkeeper"}

# Sub-position keywords → Qdrant detailed_position codes (SportMonks actual codes)
# Note: SportMonks has a typo — 'midfield' is stored as 'midfied'
WING_CODES = ["left-wing", "right-wing"]  # wing maps to both

DETAILED_MAP = {
    # Attackers
    "wing": "__wing__",            # special: OR(left-wing, right-wing)
    "winger": "__wing__",          # alias kept for backward compat
    "left wing": "left-wing",
    "right wing": "right-wing",
    "left winger": "left-wing",
    "right winger": "right-wing",
    "kanat": "__wing__",
    "kanat oyuncusu": "__wing__",
    "striker": "centre-forward",
    "centre forward": "centre-forward",
    "center forward": "centre-forward",
    "centre-forward": "centre-forward",
    "forvet": "centre-forward",
    "santrafor": "centre-forward",
    "9": "centre-forward",
    "false nine": "centre-forward",
    "second striker": "secondary_striker",
    # Midfielders (SportMonks stores 'midfied' not 'midfield' — known typo)
    "attacking midfielder": "attacking-midfied",
    "attacking mid": "attacking-midfied",
    "10": "attacking-midfied",
    "number 10": "attacking-midfied",
    "playmaker": "attacking-midfied",
    "offensive midfielder": "attacking-midfied",
    "central midfielder": "central-midfied",
    "box to box": "central-midfied",
    "8": "central-midfied",
    "defensive midfielder": "defensive-midfied",
    "holding midfielder": "defensive-midfied",
    "defensive mid": "defensive-midfied",
    "6": "defensive-midfied",
    "kante type": "defensive-midfied",
    "holder": "defensive-midfied",
    "orta saha": "central-midfied",
    "defansif orta saha": "defensive-midfied",
    "left midfield": "left-midfield",
    "right midfield": "right-midfield",
    # Defenders
    "centre-back": "centre-back",
    "center-back": "centre-back",
    "central defender": "centre-back",
    "stoper": "centre-back",
    "cb": "centre-back",
    "left-back": "left-back",
    "left back": "left-back",
    "sol bek": "left-back",
    "right-back": "right-back",
    "right back": "right-back",
    "sağ bek": "right-back",
    "full back": "right-back",
    "full-back": "right-back",
    # Goalkeeper
    "keeper": "goalkeeper",
    "kaleci": "goalkeeper",
    "gk": "goalkeeper",
    "goal keeper": "goalkeeper",
}


def _resolve_position(raw: str) -> tuple[str | None, str | None]:
    """
    Returns (broad_position, detailed_position_code).
    '__wing__' is a special value meaning OR(left-wing, right-wing).
    """
    if not raw:
        return None, None
    lower = raw.lower().strip()
    if lower in DETAILED_MAP:
        return None, DETAILED_MAP[lower]
    if lower in BROAD_POSITIONS:
        return lower, None
    # partial match on known keywords
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
            "or specific (wing/striker/centre-back/right-back/defensive midfielder/"
            "attacking midfielder/central midfielder/etc.). "
            "Turkish: forvet/kanat/santrafor → attacker/wing, stoper/bek → defender, "
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
    must_conditions = []
    should_conditions = []

    if player_filter.position:
        broad, detailed = _resolve_position(player_filter.position)
        if detailed == "__wing__":
            # OR filter: left-wing or right-wing
            should_conditions.extend([
                FieldCondition(key="detailed_position", match=MatchValue(value="left-wing")),
                FieldCondition(key="detailed_position", match=MatchValue(value="right-wing")),
            ])
        elif detailed:
            must_conditions.append(
                FieldCondition(key="detailed_position", match=MatchValue(value=detailed))
            )
        elif broad:
            must_conditions.append(
                FieldCondition(key="position", match=MatchValue(value=broad))
            )

    for attr, op in [("min_age", "gte"), ("max_age", "lte")]:
        val = getattr(player_filter, attr)
        if val:
            num = extract_number(val)
            if num:
                must_conditions.append(
                    FieldCondition(key="age", range=Range(**{op: num}))
                )

    for attr, op in [("min_height", "gte"), ("max_height", "lte")]:
        val = getattr(player_filter, attr)
        if val:
            num = extract_number(val)
            if num:
                must_conditions.append(
                    FieldCondition(key="height", range=Range(**{op: num}))
                )

    if not must_conditions and not should_conditions:
        return None

    if should_conditions and must_conditions:
        # must + OR(should) — use MinShould to enforce at least 1
        return Filter(
            must=must_conditions,
            min_should=MinShould(conditions=should_conditions, min_count=1)
        )
    elif should_conditions:
        # pure OR, no must
        return Filter(should=should_conditions)
    else:
        return Filter(must=must_conditions)
