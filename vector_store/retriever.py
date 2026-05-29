from qdrant_client import QdrantClient
from qdrant_client.models import Filter
from sentence_transformers import SentenceTransformer
import os
from dotenv import load_dotenv

load_dotenv()

_embed_model = None


def get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _embed_model


def qdrant_retriever(query_string: str, filters: Filter | None = None, top_k: int = 5) -> list[str]:
    """
    Encode the query and retrieve the top-k matching player texts from Qdrant.
    Returns a list of player text strings.
    """
    model = get_embed_model()
    query_vector = model.encode(query_string).tolist()

    client = QdrantClient(url=os.getenv("QDRANT_URL"))

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
