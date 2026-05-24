from sqlalchemy.dialects.postgresql import insert
from database.models import Country, League, Team, Player


def upsert_country(session, country_data: dict):
    stmt = insert(Country).values(country_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["sportmonks_country_id"],
        set_={"name": stmt.excluded.name, "continent_id": stmt.excluded.continent_id}
    )
    session.execute(stmt)
    session.commit()


def upsert_league(session, league_data: dict):
    stmt = insert(League).values(league_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["sportmonks_league_id"],
        set_={"name": stmt.excluded.name}
    )

    session.execute(stmt)
    session.commit()


def upsert_team(session, team_data: dict):
    stmt = insert(Team).values(team_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["sportmonks_team_id"],
        set_={"name": stmt.excluded.name}
    )

    session.execute(stmt)
    session.commit()


def upsert_player(session, player_data: dict):
    stmt = insert(Player).values(player_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["sportmonks_player_id"],
        set_={
            "fullname": stmt.excluded.fullname,
            "name": stmt.excluded.name,
            "surname": stmt.excluded.surname,
            "age": stmt.excluded.age,
            "height": stmt.excluded.height,
            "weight": stmt.excluded.weight,
            "country_id": stmt.excluded.country_id,
            "team_id": stmt.excluded.team_id}
    )

    session.execute(stmt)
    session.commit()
