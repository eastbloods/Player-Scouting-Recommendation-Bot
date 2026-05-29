from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient, models
import os
from dotenv import load_dotenv

load_dotenv()

model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
client = QdrantClient(url=os.getenv('QDRANT_URL'))
COLLECTION = "players"


def create_collection():
    if not client.collection_exists(collection_name=COLLECTION):
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
        )
        print(f"Collection '{COLLECTION}' created.")


def _build_text(player: dict, team_name: str, league_name: str, country_name: str) -> str:
    """Build a rich natural-language text for embedding."""
    stats = player.get("stats", {})

    # --- Base profile ---
    lines = [
        f"{player['fullname']} – {player['age']} years old, {player['height']} cm, "
        f"{player['position_name']} ({player['detailed_position']}), "
        f"nationality: {country_name}, "
        f"{team_name}, {league_name}."
    ]

    # --- Season stats (only include if we have real data) ---
    if stats.get("appearances"):
        parts = [f"Season: {int(stats['appearances'])} appearances"]
        if stats.get("starts"):
            parts.append(f"{int(stats['starts'])} starts")
        if stats.get("minutes_played"):
            parts.append(f"{int(stats['minutes_played'])} minutes")
        if stats.get("rating"):
            parts.append(f"avg rating {stats['rating']:.2f}")
        lines.append(", ".join(parts) + ".")

    # --- Attacking ---
    atk = []
    if stats.get("goals") is not None:
        atk.append(f"{int(stats['goals'])} goals")
    if stats.get("assists") is not None:
        atk.append(f"{int(stats['assists'])} assists")
    if stats.get("shots_total"):
        atk.append(f"{int(stats['shots_total'])} shots")
    if stats.get("shots_on_target"):
        atk.append(f"{int(stats['shots_on_target'])} on target")
    if stats.get("big_chances_created"):
        atk.append(f"{int(stats['big_chances_created'])} big chances created")
    if stats.get("hit_woodwork"):
        atk.append(f"hit woodwork {int(stats['hit_woodwork'])} times")
    if atk:
        lines.append("Attacking: " + ", ".join(atk) + ".")

    # --- Passing & Creativity ---
    pas = []
    if stats.get("passes"):
        pas.append(f"{int(stats['passes'])} passes")
    if stats.get("pass_accuracy_pct"):
        pas.append(f"{stats['pass_accuracy_pct']:.1f}% accuracy")
    if stats.get("key_passes"):
        pas.append(f"{int(stats['key_passes'])} key passes")
    if stats.get("through_balls"):
        pas.append(f"{int(stats['through_balls'])} through balls")
    if stats.get("crosses_total"):
        pas.append(f"{int(stats['crosses_total'])} crosses")
    if stats.get("crosses_accurate"):
        pas.append(f"{int(stats['crosses_accurate'])} accurate")
    if pas:
        lines.append("Passing: " + ", ".join(pas) + ".")

    # --- Defending ---
    dfn = []
    if stats.get("tackles"):
        dfn.append(f"{int(stats['tackles'])} tackles")
    if stats.get("interceptions"):
        dfn.append(f"{int(stats['interceptions'])} interceptions")
    if stats.get("clearances"):
        dfn.append(f"{int(stats['clearances'])} clearances")
    if stats.get("aerials_won"):
        dfn.append(f"{int(stats['aerials_won'])} aerials won")
    if stats.get("cleansheets"):
        dfn.append(f"{int(stats['cleansheets'])} clean sheets")
    if stats.get("goals_conceded") is not None:
        dfn.append(f"{int(stats['goals_conceded'])} goals conceded")
    if dfn:
        lines.append("Defending: " + ", ".join(dfn) + ".")

    # --- Physical / Duels ---
    phy = []
    if stats.get("duels_total") and stats.get("duels_won"):
        pct = round(stats["duels_won"] / stats["duels_total"] * 100)
        phy.append(f"{int(stats['duels_won'])}/{int(stats['duels_total'])} duels won ({pct}%)")
    if stats.get("dribbles_attempted") and stats.get("dribbles_successful"):
        phy.append(f"{int(stats['dribbles_successful'])}/{int(stats['dribbles_attempted'])} dribbles")
    if phy:
        lines.append("Physical: " + ", ".join(phy) + ".")

    # --- Discipline ---
    disc = []
    if stats.get("yellow_cards"):
        disc.append(f"{int(stats['yellow_cards'])} yellow cards")
    if stats.get("red_cards"):
        disc.append(f"{int(stats['red_cards'])} red cards")
    if disc:
        lines.append("Discipline: " + ", ".join(disc) + ".")

    return " ".join(lines)


def build_and_upsert(player: dict, player_db_id: int,
                     team_name: str, league_name: str, country_name: str):
    """Build embedding text, encode, and upsert a single player to Qdrant."""
    text = _build_text(player, team_name, league_name, country_name)
    vector = model.encode(text).tolist()

    stats = player.get("stats", {})
    payload = {
        "text": text,
        "age": player["age"],
        "height": player["height"],
        "position": player["position_name"],
        "detailed_position": player["detailed_position"],
        "nationality": country_name,
        "team": team_name,
        "league": league_name,
        # Key stats as metadata (for future filter support)
        "goals": int(stats.get("goals") or 0),
        "assists": int(stats.get("assists") or 0),
        "appearances": int(stats.get("appearances") or 0),
        "rating": float(stats.get("rating") or 0.0),
    }

    client.upsert(
        collection_name=COLLECTION,
        points=[models.PointStruct(id=player_db_id, vector=vector, payload=payload)]
    )
