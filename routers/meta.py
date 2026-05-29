from fastapi import APIRouter
from qdrant_client import QdrantClient
import os
from dotenv import load_dotenv
from functools import lru_cache

load_dotenv()
router = APIRouter(prefix="/meta", tags=["meta"])


def _get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=os.getenv("QDRANT_URL"))


@lru_cache(maxsize=1)
def _fetch_meta_cached():
    """Scroll through Qdrant once, cache unique leagues + nationalities."""
    client = _get_qdrant_client()
    leagues = set()
    nationalities = set()
    offset = None

    while True:
        result = client.scroll(
            collection_name="players",
            scroll_filter=None,
            limit=1000,
            offset=offset,
            with_payload=["league", "nationality"],
            with_vectors=False,
        )
        points, next_offset = result

        for pt in points:
            lg = pt.payload.get("league")
            nat = pt.payload.get("nationality")
            if lg and isinstance(lg, str) and lg.strip():
                leagues.add(lg.strip())
            if nat and isinstance(nat, str) and nat.strip():
                nationalities.add(nat.strip())

        if next_offset is None:
            break
        offset = next_offset

    return sorted(leagues), sorted(nationalities)


@router.get("/leagues")
def get_leagues():
    """Returns all league names sorted alphabetically from Qdrant."""
    try:
        leagues, _ = _fetch_meta_cached()
        return {"leagues": leagues}
    except Exception as e:
        return {"leagues": [], "error": str(e)}


@router.get("/nationalities")
def get_nationalities():
    """Returns all nationality values sorted alphabetically from Qdrant."""
    try:
        _, nationalities = _fetch_meta_cached()
        return {"nationalities": nationalities}
    except Exception as e:
        return {"nationalities": [], "error": str(e)}


@router.get("/refresh")
def refresh_meta():
    """Force refresh the cached meta (call after re-ingestion)."""
    _fetch_meta_cached.cache_clear()
    leagues, nationalities = _fetch_meta_cached()
    return {"leagues": len(leagues), "nationalities": len(nationalities), "status": "refreshed"}
