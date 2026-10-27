from qdrant_client import QdrantClient
from qdrant_client.models import Filter
from sentence_transformers import SentenceTransformer
import os
import threading
from dotenv import load_dotenv

load_dotenv()

_embed_model: SentenceTransformer | None = None
_qdrant_client: QdrantClient | None = None
_lock = threading.Lock()


def get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        with _lock:
            if _embed_model is None:
                _embed_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _embed_model


def get_qdrant_client() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        with _lock:
            if _qdrant_client is None:
                _qdrant_client = QdrantClient(url=os.getenv("QDRANT_URL"))
    return _qdrant_client


def qdrant_retriever(query_string: str, filters: Filter | None = None, top_k: int = 5) -> list[str]:
    """
    Encode the query and retrieve the top-k matching player texts from Qdrant.
    Returns a list of player text strings.
    """
    model = get_embed_model()
    query_vector = model.encode(query_string).tolist()

    client = get_qdrant_client()

    results = client.query_points(
        collection_name="players",
        query=query_vector,
        query_filter=filters,
        limit=top_k,
        with_payload=True,
    ).points

    texts = []
    for r in results:
        text = r.payload.get("text", "")
        print(f"[{r.score:.3f}] {text[:100]}")
        texts.append(text)

    return texts
