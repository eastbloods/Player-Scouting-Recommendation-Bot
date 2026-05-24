from fastapi import APIRouter, Depends, HTTPException, Request
from agents.search_agent import search_augmentation
from schemas import SearchPlayerResponse, SearchPlayerRequest

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/", response_model=SearchPlayerResponse)
def search_query(request: SearchPlayerRequest):
    response = search_augmentation(request.text)
    return {"text": f"{response}"}
