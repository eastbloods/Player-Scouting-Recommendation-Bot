from fastapi import APIRouter, Request
from agents.search_agent import search_augmentation
from schemas import SearchPlayerResponse, SearchPlayerRequest
from limiter import limiter

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/", response_model=SearchPlayerResponse)
@limiter.limit("5/minute")
def search_query(request: Request, body: SearchPlayerRequest):
    """
    Search players by natural language query + optional UI filters.
    UI filters (position, age, height, nationality, league, team_country) are applied
    directly as hard Qdrant filters, bypassing LLM extraction when set.
    Rate limited to 5 requests per minute per IP.
    """
    response = search_augmentation(
        content=body.text,
        ui_position=body.position,
        ui_min_age=body.min_age,
        ui_max_age=body.max_age,
        ui_min_height=body.min_height,
        ui_max_height=body.max_height,
        ui_nationality=body.nationality,
        ui_league=body.league,
        ui_team_country=body.team_country,
        ui_team=body.team,
    )
    return {"text": response}
