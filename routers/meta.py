from fastapi import APIRouter
from database.database import SessionLocal
from database.models import League, Country

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/leagues")
def get_leagues():
    """Returns all league names sorted alphabetically for UI dropdown."""
    db: Session = SessionLocal()
    try:
        leagues = db.query(League.name).order_by(League.name).all()
        return {"leagues": sorted(set(r[0] for r in leagues if r[0]))}
    finally:
        db.close()


@router.get("/nationalities")
def get_nationalities():
    """Returns all country names sorted alphabetically for UI dropdown."""
    db: Session = SessionLocal()
    try:
        countries = db.query(Country.name).order_by(Country.name).all()
        return {"nationalities": sorted(set(
            r[0] for r in countries
            if r[0] and not r[0].startswith("country_")
        ))}
    finally:
        db.close()
