from datetime import date, datetime
from api.sportmonks import sportmonks_get_leagues, sportmonks_get_teams, sportmonks_get_countries, sportmonks_get_squad

all_country_data = sportmonks_get_countries()
all_leagues_data = sportmonks_get_leagues()
all_teams_data = sportmonks_get_teams()

time_format = "%Y-%m-%d"
today = date.today()


def parse_country():
    results = []
    for country in all_country_data["data"]:
        results.append({
            "name": country["name"],
            "continent_id": country["continent_id"],
            "sportmonks_country_id": country["id"],
        })
    return results


def parse_league():
    results = []
    for league in all_leagues_data["data"]:
        country = league["country"]
        results.append({
            "name": league['name'],
            "sportmonks_league_id": league['id'],
            "sportmonks_country_id": country["id"],
        })
    return results


def parse_team():
    results = []
    for team in all_teams_data["data"]:
        seasons = team["seasons"]
        if seasons:
            for season in seasons:
                if season["is_current"]:
                    results.append(
                        {
                            "name": team["name"],
                            "sportmonks_team_id": team["id"],
                            "sportmonks_country_id": team["country_id"],
                            "sportmonks_league_id": season["league_id"],
                        }
                    )
                    break
    return results


def parse_squad(team_id):
    all_squad_data = sportmonks_get_squad(team_id)
    results = []
    for player in all_squad_data["data"]:
        player_details = player["player"]
        detailed_position = player["detailedposition"]
        position = player["position"]
        string_date = player_details["date_of_birth"]
        birth_date = datetime.strptime(string_date, time_format)
        results.append({
            "fullname": player_details["display_name"],
            "name": player_details["firstname"],
            "surname": player_details["lastname"],
            "age": today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day)),
            "height": player_details["height"] or 0,
            "weight": player_details["weight"] or 0,
            "position_name": position["code"],
            "detailed_position": detailed_position["code"],
            "sportmonks_country_id": player_details["country_id"],
            "sportmonks_team_id": player["team_id"],
            "sportmonks_player_id": player_details["id"],
        })

    return results


