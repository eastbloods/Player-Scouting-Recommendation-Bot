from fastapi import APIRouter
from agents.search_agent import search_augmentation
from agents.filter_agent import build_filters, PlayerFilter
from schemas import SearchPlayerResponse, SearchPlayerRequest

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/", response_model=SearchPlayerResponse)
def search_query(request: SearchPlayerRequest):
    """
    Search players by natural language query + optional UI filters.
    UI filters (position, age, height, nationality, league) are applied
    directly as hard Qdrant filters, bypassing LLM extraction when set.
    """
    response = search_augmentation(
        content=request.text,
        ui_position=request.position,
        ui_min_age=request.min_age,
        ui_max_age=request.max_age,
        ui_min_height=request.min_height,
        ui_max_height=request.max_height,
        ui_nationality=request.nationality,
        ui_league=request.league,
    )
    return {"text": response}
