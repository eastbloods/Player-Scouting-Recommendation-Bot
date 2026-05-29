"""
fix_countries.py
----------------
Fetches real country names from SportMonks API and:
1. Updates the Postgres `country` table with real names
2. Updates Qdrant player payloads with corrected nationality strings

Run: python fix_countries.py
"""
import os
import time
import logging
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from qdrant_client import QdrantClient
from qdrant_client.models import PointIdsList

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

API_TOKEN = os.getenv("SPORTMONK-TOKEN") or os.getenv("SPORTMONKS_TOKEN")
DB_URL    = os.getenv("DATABASE_URL")
QDRANT    = os.getenv("QDRANT_URL")
HEADERS   = {"Authorization": API_TOKEN}
BASE_URL  = "https://api.sportmonks.com/v3/football"


# ── 1. Fetch all countries from SportMonks ────────────────────────────────────
def fetch_all_countries() -> dict[int, str]:
    """Returns {sportmonks_country_id: country_name}"""
    results = {}
    page = 1
    while True:
        resp = requests.get(
            f"{BASE_URL}/countries",
            headers=HEADERS,
            params={"page": page, "per_page": 150}
        )
        resp.raise_for_status()
        data = resp.json()
        countries = data.get("data", [])
        if not countries:
            break
        for c in countries:
            results[c["id"]] = c["name"]
        meta = data.get("pagination", {})
        if not meta.get("has_more", False):
            break
        page += 1
        time.sleep(0.3)
    log.info(f"Fetched {len(results)} countries from SportMonks")
    return results


# ── 2. Update Postgres ────────────────────────────────────────────────────────
def update_postgres(country_map: dict[int, str]) -> dict[int, str]:
    """Updates country names in DB. Returns {db_id: new_name} for changed rows."""
    engine = create_engine(DB_URL)
    updated = {}
    with engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT id, sportmonks_country_id, name FROM country"
        )).fetchall()

        for row in rows:
            db_id, sm_id, old_name = row
            new_name = country_map.get(sm_id)
            if new_name and new_name != old_name:
                conn.execute(text(
                    "UPDATE country SET name = :name WHERE id = :id"
                ), {"name": new_name, "id": db_id})
                updated[db_id] = new_name

    log.info(f"Updated {len(updated)} country names in Postgres")
    return updated


# ── 3. Update Qdrant payloads ─────────────────────────────────────────────────
def update_qdrant_nationalities(engine, updated_countries: dict[int, str]):
    """
    For each changed country, find players with that country_id in Postgres,
    then update their Qdrant nationality payload field.
    """
    client = QdrantClient(url=QDRANT)

    with engine.connect() as conn:
        for db_country_id, new_name in updated_countries.items():
            # Find players with this country
            players = conn.execute(text(
                "SELECT id FROM player WHERE country_id = :cid"
            ), {"cid": db_country_id}).fetchall()

            if not players:
                continue

            player_ids = [p[0] for p in players]
            log.info(f"  Updating {len(player_ids)} players → nationality: {new_name}")

            # Update Qdrant in batches of 500
            for i in range(0, len(player_ids), 500):
                batch = player_ids[i:i+500]
                client.set_payload(
                    collection_name="players",
                    payload={"nationality": new_name},
                    points=batch,
                )

    log.info("Qdrant nationality payloads updated ✅")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("Step 1: Fetching countries from SportMonks...")
    country_map = fetch_all_countries()

    log.info("Step 2: Updating Postgres...")
    engine = create_engine(DB_URL)
    updated = update_postgres(country_map)

    if updated:
        log.info("Step 3: Updating Qdrant payloads...")
        update_qdrant_nationalities(engine, updated)
    else:
        log.info("No country names changed — Qdrant update skipped")

    log.info("Done! 🎉")
