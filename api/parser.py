from datetime import date, datetime

TIME_FORMAT = "%Y-%m-%d"
TODAY = date.today()

# Stats we care about — maps developer_name → human label
STAT_LABELS = {
    "GOALS": "goals",
    "ASSISTS": "assists",
    "APPEARANCES": "appearances",
    "LINEUPS": "starts",
    "BENCH": "bench",
    "MINUTES_PLAYED": "minutes_played",
    "RATING": "rating",
    "SHOTS_TOTAL": "shots_total",
    "SHOTS_ON_TARGET": "shots_on_target",
    "KEY_PASSES": "key_passes",
    "PASSES": "passes",
    "ACCURATE_PASSES": "accurate_passes",
    "ACCURATE_PASSES_PERCENTAGE": "pass_accuracy_pct",
    "TACKLES": "tackles",
    "INTERCEPTIONS": "interceptions",
    "CLEARANCES": "clearances",
    "AERIALS_WON": "aerials_won",
    "TOTAL_DUELS": "duels_total",
    "DUELS_WON": "duels_won",
    "DRIBBLED_ATTEMPTS": "dribbles_attempted",
    "SUCCESSFUL_DRIBBLES": "dribbles_successful",
    "YELLOWCARDS": "yellow_cards",
    "REDCARDS": "red_cards",
    "CLEANSHEET": "cleansheets",
    "BIG_CHANCES_CREATED": "big_chances_created",
    "BIG_CHANCES_MISSED": "big_chances_missed",
    "TOTAL_CROSSES": "crosses_total",
    "ACCURATE_CROSSES": "crosses_accurate",
    "GOALS_CONCEDED": "goals_conceded",
    "HIT_WOODWORK": "hit_woodwork",
    "LONG_BALLS": "long_balls",
    "THROUGH_BALLS": "through_balls",
    "DISPOSSESSED": "dispossessed",
    "FOULS": "fouls_committed",
    "FOULS_DRAWN": "fouls_drawn",
}


def _extract_stat_value(detail: dict, type_map: dict[int, str]) -> tuple[str, float | None]:
    """Return (label, numeric_value) for a stat detail, or (label, None) if not useful."""
    dev_name = type_map.get(detail["type_id"])
    if not dev_name or dev_name not in STAT_LABELS:
        return dev_name, None
    label = STAT_LABELS[dev_name]
    val = detail.get("value", {})
    # Pick the most meaningful numeric from the value dict
    for key in ("total", "average", "goals", "in"):
        if key in val:
            return label, val[key]
    return label, None


def extract_season_stats(statistics: list, current_season_id: int, type_map: dict[int, str]) -> dict:
    """Extract stats for the given season from a player's full stats history."""
    target = next((s for s in statistics if s["season_id"] == current_season_id), None)
    if not target or not target.get("has_values"):
        return {}
    result = {}
    for detail in target.get("details", []):
        label, value = _extract_stat_value(detail, type_map)
        if label and value is not None:
            result[label] = value
    return result


def parse_player(raw: dict, current_season_id: int, type_map: dict[int, str]) -> dict | None:
    """
    Parse a raw squad entry into a structured player dict.
    Returns None if essential data is missing.
    """
    player = raw.get("player") or {}
    position = raw.get("position") or {}
    detailed = raw.get("detailedposition") or {}

    # Skip if missing core fields
    if not player.get("id") or not player.get("date_of_birth"):
        return None

    try:
        birth_date = datetime.strptime(player["date_of_birth"], TIME_FORMAT).date()
        age = TODAY.year - birth_date.year - (
            (TODAY.month, TODAY.day) < (birth_date.month, birth_date.day)
        )
    except (ValueError, TypeError):
        return None

    stats = extract_season_stats(
        player.get("statistics", []), current_season_id, type_map
    )

    return {
        "sportmonks_player_id": player["id"],
        "sportmonks_team_id": raw.get("team_id"),
        "sportmonks_country_id": player.get("nationality_id") or player.get("country_id"),
        "fullname": player.get("display_name") or player.get("name"),
        "name": player.get("firstname") or "",
        "surname": player.get("lastname") or "",
        "age": age,
        "height": player.get("height") or 0,
        "weight": player.get("weight") or 0,
        "position_name": position.get("code", "unknown"),
        "detailed_position": detailed.get("code", "unknown"),
        "stats": stats,          # dict of stat_label → value
        "season_id": current_season_id,
    }
