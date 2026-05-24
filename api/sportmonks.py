import requests
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('SPORTMONK-TOKEN')


def sportmonks_get_countries():
    url = f"https://cricket.sportmonks.com/api/v2.0/countries?api_token={api_key}&include=leagues,"
    res = requests.get(url)
    return res.json()


def sportmonks_get_leagues():
    url = f"https://api.sportmonks.com/v3/football/leagues?api_token={api_key}&include=country"
    res = requests.get(url)
    return res.json()


def sportmonks_get_teams():
    url = f"https://api.sportmonks.com/v3/football/teams?api_token={api_key}&include=seasons;coaches"
    res = requests.get(url)
    return res.json()


def sportmonks_get_squad(team_id):
    url = f"https://api.sportmonks.com/v3/football/squads/teams/{team_id}?api_token={api_key}&include=position;detailedPosition;player"
    res = requests.get(url)
    return res.json()


def sportmonks_get_players():
    url = f"https://api.sportmonks.com/v3/football/players?api_token={api_key}&include=country;city;nationality;teams;position;detailedPosition;statistics"
    res = requests.get(url)
    return res.json()
