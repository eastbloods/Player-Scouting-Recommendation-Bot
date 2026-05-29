"""
Full data ingestion pipeline.

Flow:
  1. Fetch type map from SportMonks core API
  2. Fetch all available leagues → filter to domestic, category <= 3
  3. For each league: get current season ID
  4. For each season: get teams
  5. For each team: get squad + full stats (single API call)
  6. Parse player profile + current season stats
  7. Upsert to PostgreSQL + Qdrant

Run: python -m ingest
"""
import time
import json
import logging
from api.sportmonks import (
    get_all_leagues,
    get_league_current_season,
    get_teams_for_season,
    get_squad_with_stats,
    get_type_map,
)
from api.parser import parse_player
from database.database import SessionLocal
from database.models import Country, League, Team, Player
from database.embedder import create_collection, build_and_upsert

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# --- Filters ---
SKIP_KEYWORDS = ["Women", "Frauen", "Féminin", "Damall", "NWSL", "U21", "U19", "Youth",
                 "Friendly", "Concacaf League", "Canadian Soccer"]
SKIP_IDS = {576, 1740, 2328, 1203, 1204, 1205, 983, 1479}   # specific leagues to exclude


def _should_include(league: dict) -> bool:
    if league["id"] in SKIP_IDS:
        return False
    if league["sub_type"] != "domestic":
        return False
    if league["category"] > 3:
        return False
    name = league.get("name", "")
    if any(kw.lower() in name.lower() for kw in SKIP_KEYWORDS):
        return False
    return True


def _upsert_country(session, sportmonks_id: int, name: str) -> Country:
    obj = session.query(Country).filter_by(sportmonks_country_id=sportmonks_id).first()
    if not obj:
        obj = Country(name=name, continent_id=0, sportmonks_country_id=sportmonks_id)
        session.add(obj)
        session.flush()
    return obj


def _upsert_league(session, league_raw: dict) -> League:
    obj = session.query(League).filter_by(sportmonks_league_id=league_raw["id"]).first()
    if not obj:
        # Country for league
        country = _upsert_country(session, league_raw["country_id"], f"country_{league_raw['country_id']}")
        obj = League(
            name=league_raw["name"],
            sportmonks_league_id=league_raw["id"],
            country_id=country.id,
        )
        session.add(obj)
        session.flush()
    return obj


def _upsert_team(session, team_raw: dict, league_id: int) -> Team:
    obj = session.query(Team).filter_by(sportmonks_team_id=team_raw["id"]).first()
    if not obj:
        country = _upsert_country(session, team_raw.get("country_id", 0), f"country_{team_raw.get('country_id', 0)}")
        obj = Team(
            name=team_raw["name"],
            sportmonks_team_id=team_raw["id"],
            league_id=league_id,
            country_id=country.id,
        )
        session.add(obj)
        session.flush()
    return obj


def _upsert_player(session, parsed: dict, team_id: int) -> Player | None:
    obj = session.query(Player).filter_by(sportmonks_player_id=parsed["sportmonks_player_id"]).first()
    if obj:
        # Update stats for existing player
        obj.age = parsed["age"]
        obj.team_id = team_id
    else:
        # Resolve nationality country
        country_id = None
        if parsed.get("sportmonks_country_id"):
            c = session.query(Country).filter_by(
                sportmonks_country_id=parsed["sportmonks_country_id"]
            ).first()
            country_id = c.id if c else None

        obj = Player(
            fullname=parsed["fullname"],
            name=parsed["name"],
            surname=parsed["surname"],
            age=parsed["age"],
            height=parsed["height"],
            weight=parsed["weight"],
            position_name=parsed["position_name"],
            detailed_position=parsed["detailed_position"],
            sportmonks_player_id=parsed["sportmonks_player_id"],
            country_id=country_id,
            team_id=team_id,
        )
        session.add(obj)
        session.flush()
    return obj


RAW_DATA_FILE = "raw_players_data.jsonl"


def run():
    session = SessionLocal()
    create_collection()
    raw_file = open(RAW_DATA_FILE, "w", encoding="utf-8")

    # 1. Type map
    log.info("Fetching type map...")
    type_map = get_type_map()
    log.info(f"  {len(type_map)} types loaded.")

    # 2. Leagues
    log.info("Fetching all leagues...")
    all_leagues = get_all_leagues()
    selected = [l for l in all_leagues if _should_include(l)]
    log.info(f"  {len(selected)} leagues selected out of {len(all_leagues)}.")

    total_players = 0
    failed_leagues = []

    for i, league_raw in enumerate(selected):
        league_name = league_raw["name"]
        league_id_sm = league_raw["id"]
        log.info(f"[{i+1}/{len(selected)}] {league_name} (id:{league_id_sm})")

        # 3. Current season
        try:
            season = get_league_current_season(league_id_sm)
            if not season:
                log.warning(f"  No current season — skipping.")
                continue
            current_season_id = season["id"]
            season_name = season.get("name", "")
            log.info(f"  Season: {season_name} (id:{current_season_id})")
        except Exception as e:
            log.error(f"  Season fetch failed: {e}")
            failed_leagues.append(league_name)
            continue

        # DB: upsert league
        try:
            league_db = _upsert_league(session, league_raw)
            session.commit()
        except Exception as e:
            session.rollback()
            log.error(f"  League upsert failed: {e}")
            continue

        # 4. Teams
        try:
            teams = get_teams_for_season(current_season_id)
            if not teams:
                log.warning(f"  No teams found — skipping.")
                continue
            log.info(f"  {len(teams)} teams.")
        except Exception as e:
            log.error(f"  Teams fetch failed: {e}")
            failed_leagues.append(league_name)
            continue

        for team_raw in teams:
            team_name = team_raw.get("name", "?")
            team_id_sm = team_raw["id"]

            # DB: upsert team
            try:
                team_db = _upsert_team(session, team_raw, league_db.id)
                session.commit()
            except Exception as e:
                session.rollback()
                log.error(f"    Team {team_name} upsert failed: {e}")
                continue

            # 5. Squad + stats
            try:
                squad = get_squad_with_stats(team_id_sm)
                time.sleep(0.3)
            except Exception as e:
                log.error(f"    Squad fetch failed for {team_name}: {e}")
                continue

            if not squad:
                log.warning(f"    {team_name}: empty squad.")
                continue

            team_players = 0
            for raw_player in squad:
                try:
                    parsed = parse_player(raw_player, current_season_id, type_map)
                except Exception as e:
                    log.warning(f"      parse_player error: {e} — skipping.")
                    continue
                if not parsed:
                    continue

                # DB: upsert player
                try:
                    player_db = _upsert_player(session, parsed, team_db.id)
                    session.commit()
                except Exception as e:
                    session.rollback()
                    log.error(f"      Player upsert failed: {e}")
                    continue

                # 6a. Save raw data to JSONL
                try:
                    record = {
                        **parsed,
                        "team_name": team_name,
                        "league_name": league_name,
                    }
                    raw_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                except Exception as e:
                    log.warning(f"      Raw save failed: {e}")

                # 6b. Qdrant embed + upsert
                try:
                    # Resolve country name
                    country_name = "Unknown"
                    if player_db.country_id:
                        c = session.query(Country).filter_by(id=player_db.country_id).first()
                        if c:
                            country_name = c.name

                    build_and_upsert(
                        player=parsed,
                        player_db_id=player_db.id,
                        team_name=team_name,
                        league_name=league_name,
                        country_name=country_name,
                    )
                    team_players += 1
                    total_players += 1
                except Exception as e:
                    log.error(f"      Qdrant upsert failed: {e}")

            log.info(f"    {team_name}: {team_players} players ingested.")

        log.info(f"  League done. Running total: {total_players} players.")
        time.sleep(0.5)  # gentle rate limiting between leagues

    session.close()
    raw_file.close()
    log.info(f"\n{'='*50}")
    log.info(f"INGEST COMPLETE: {total_players} players ingested.")
    log.info(f"Raw data saved → {RAW_DATA_FILE}")
    if failed_leagues:
        log.warning(f"Failed leagues: {failed_leagues}")


if __name__ == "__main__":
    run()