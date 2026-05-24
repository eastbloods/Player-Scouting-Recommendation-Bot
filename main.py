from database.crud import upsert_country, upsert_league, upsert_team, upsert_player
from database.database import SessionLocal
from api.parser import parse_country, parse_league, parse_team, parse_squad
from database.models import Country, League, Team, Player
from database.embedder import build_player_text, upsert_vectors
from fastapi import FastAPI
from routers import search

app = FastAPI()
# session = SessionLocal()
#
# countries = parse_country()
# leagues = parse_league()
# teams = parse_team()
#
#
# def ingest_countries():
#     for country in countries:
#         upsert_country(session, country)
#
#
# def ingest_leagues():
#     for league in leagues:
#         query = session.query(Country).filter(Country.sportmonks_country_id == league["sportmonks_country_id"])
#         league["country_id"] = query.first().id
#         league.pop("sportmonks_country_id")
#         upsert_league(session, league)
#
#
# def ingest_teams():
#     team_id_list = []
#     for team in teams:
#         team_id_list.append(team["sportmonks_team_id"])
#         league_query = session.query(League).filter(League.sportmonks_league_id == team["sportmonks_league_id"])
#         country_query = session.query(Country).filter(Country.sportmonks_country_id == team["sportmonks_country_id"])
#         team["league_id"] = league_query.first().id
#         team["country_id"] = country_query.first().id
#         team.pop("sportmonks_league_id")
#         team.pop("sportmonks_country_id")
#         upsert_team(session, team)
#     return team_id_list
#
#
# def ingest_players():
#     team_ids = ingest_teams()
#     for team_id in team_ids:
#         for player in parse_squad(team_id):
#             team_query = session.query(Team).filter(Team.sportmonks_team_id == player["sportmonks_team_id"])
#             player["team_id"] = team_query.first().id
#             if player["sportmonks_country_id"]:
#                 country_query = session.query(Country).filter(
#                     Country.sportmonks_country_id == player["sportmonks_country_id"])
#                 player["country_id"] = country_query.first().id
#             else:
#                 player["country_id"] = None
#             player.pop("sportmonks_team_id")
#             player.pop("sportmonks_country_id")
#             upsert_player(session, player)
#
#
# ingest_countries()
# ingest_leagues()
# ingest_players()
#
# players = session.query(Player, Team, League, Country
#                         ).join(Team, Player.team_id == Team.id
#                                ).join(League, Team.league_id == League.id
#                                       ).join(Country, Player.country_id == Country.id).all()
#
#
# embedded_text = build_player_text(players)
# upsert_vectors(embedded_text)

app.include_router(search.router)