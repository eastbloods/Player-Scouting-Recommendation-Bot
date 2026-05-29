import requests
import os
import time
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("SPORTMONK-TOKEN")
BASE = "https://api.sportmonks.com/v3/football"
CORE = "https://api.sportmonks.com/v3/core"


def _get(url: str, params: dict) -> dict:
    """Single GET with API key injected."""
    params["api_token"] = API_KEY
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


def _paginated_get(url: str, params: dict) -> list:
    """Fetch all pages from a paginated endpoint."""
    results = []
    page = 1
    while True:
        params["page"] = page
        params["per_page"] = 50
        data = _get(url, params.copy())
        batch = data.get("data", [])
        results.extend(batch)
        if not data.get("pagination", {}).get("has_more", False):
            break
        page += 1
        time.sleep(0.3)
    return results


def get_all_leagues() -> list:
    """Return all available leagues."""
    return _paginated_get(f"{BASE}/leagues", {})


def get_league_current_season(league_id: int) -> dict | None:
    """Return current season info for a league."""
    data = _get(f"{BASE}/leagues/{league_id}", {"include": "currentSeason"})
    return data.get("data", {}).get("currentseason")


def get_teams_for_season(season_id: int) -> list:
    """Return all teams playing in a given season."""
    return _paginated_get(f"{BASE}/teams/seasons/{season_id}", {})


def get_squad_with_stats(team_id: int) -> list:
    """Return squad members with full career statistics details."""
    data = _get(
        f"{BASE}/squads/teams/{team_id}",
        {"include": "player;position;detailedPosition;player.statistics.details"}
    )
    return data.get("data", [])


def get_type_map() -> dict[int, str]:
    """Return a mapping of type_id → developer_name for all SportMonks types."""
    types = _paginated_get(f"{CORE}/types", {})
    return {t["id"]: t["developer_name"] for t in types}
