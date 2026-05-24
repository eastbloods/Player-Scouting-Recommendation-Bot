from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, func
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from typing import Optional

Base = declarative_base()


class Country(Base):
    __tablename__ = "country"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    continent_id: Mapped[int]
    sportmonks_country_id: Mapped[int] = mapped_column(unique=True)


class League(Base):
    __tablename__ = "league"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    country_id: Mapped[int] = mapped_column(ForeignKey("country.id"))
    sportmonks_league_id: Mapped[int] = mapped_column(unique=True)

    country = relationship("Country", backref="country_league")


class Team(Base):
    __tablename__ = "team"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    league_id: Mapped[int] = mapped_column(ForeignKey("league.id"))
    country_id: Mapped[int] = mapped_column(ForeignKey("country.id"))
    sportmonks_team_id: Mapped[int] = mapped_column(unique=True)

    country = relationship("Country", backref="country_team")
    league = relationship("League", backref="league_team")


class Player(Base):
    __tablename__ = "player"
    id: Mapped[int] = mapped_column(primary_key=True)
    fullname: Mapped[Optional[str]]
    name: Mapped[str]
    surname: Mapped[str]
    age: Mapped[int]
    height: Mapped[int]
    weight: Mapped[int]
    position_name: Mapped[str]
    detailed_position: Mapped[str]
    sportmonks_player_id: Mapped[int] = mapped_column(unique=True)
    country_id: Mapped[int] = mapped_column(ForeignKey("country.id"), nullable=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"))
    create_date: Mapped[datetime] = mapped_column(insert_default=func.now())

    team = relationship("Team", backref="team_player")
    country = relationship("Country", backref="country_player")
