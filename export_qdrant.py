"""
Export all players from Qdrant to a local JSON file.
This preserves current data for future re-embedding without API calls.
"""
from qdrant_client import QdrantClient
import json, os
from dotenv import load_dotenv

load_dotenv()
client = QdrantClient(url=os.getenv("QDRANT_URL"))

all_points = []
offset = None

while True:
    result, next_offset = client.scroll(
        collection_name="players",
        limit=500,
        offset=offset,
        with_payload=True,
        with_vectors=False
    )
    all_points.extend([{"id": p.id, "payload": p.payload} for p in result])
    print(f"  Exported: {len(all_points)}", end="\r")
    offset = next_offset
    if offset is None:
        break

output_file = "raw_players_export.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(all_points, f, ensure_ascii=False)

print(f"\nDone: {len(all_points)} players → {output_file}")
