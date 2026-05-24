from qdrant_client import QdrantClient
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core import VectorStoreIndex
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import os
from dotenv import load_dotenv

load_dotenv()
_embed_model = None


def get_embed_model():
    global _embed_model
    if _embed_model is None:
        _embed_model = HuggingFaceEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
    return _embed_model


def qdrant_retriever(query_string, filters=None):
    Settings.embed_model = get_embed_model()
    result_stack = []
    client = QdrantClient(url=os.getenv('QDRANT_URL'))
    vector_store = QdrantVectorStore(
        client=client, collection_name="players"
    )
    index = VectorStoreIndex.from_vector_store(vector_store)
    retriever = index.as_retriever(similarity_top_k=5, filters=filters)
    results = retriever.retrieve(query_string)
    for r in results:
        result_stack.append(r.node.text)
        print(r.node.text)
    return result_stack
