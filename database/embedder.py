from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient, models
import os
from dotenv import load_dotenv

load_dotenv()


model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
client = QdrantClient(url=os.getenv('QDRANT_URL'))


def create_collection():
    if client.collection_exists(collection_name="players"):
        print("Collection already created!")
    else:
        client.create_collection(
            collection_name="players",
            vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
        )


def build_player_text(players):
    players_list = []
    for player, team, league, country in players:
        created_text = f"{player.name} {player.surname}, {player.age} years old, {player.height}cm, {player.position_name}, {player.detailed_position}, {team.name}, {league.name}"
        embedding = model.encode(created_text)
        payload = {
            "text": created_text,
            "height": player.height,
            "position": player.position_name,
            "age": player.age,
            "nationality": country.name,
            "team": team.name,
            "league": league.name,
        }
        player_struct = {"id": player.id, "vector": embedding, "text": created_text, "payload": payload}
        players_list.append(player_struct)
    return players_list


def upsert_vectors(embedded):
    create_collection()
    for vector in embedded:
        client.upsert(
            collection_name="players",
            points=[
                models.PointStruct(
                    id=vector["id"],
                    vector=vector["vector"],
                    payload=vector["payload"],
                )
            ],
        )
