from qdrant_client import QdrantClient
import os
from dotenv import load_dotenv
load_dotenv()
client = QdrantClient(url=os.getenv("QDRANT_URL"))
if client.collection_exists("players"):
    client.delete_collection("players")
    print("Silindi.")
else:
    print("Zaten boş.")