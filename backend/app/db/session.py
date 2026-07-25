"""
Session factory and the FastAPI dependency that hands one Session per
request to routers/services. Depends on db/database.py's engine — nothing
here constructs its own connection.
"""
from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker

from app.db.database import engine

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency — yields one Session per request, always closed
    afterwards even if the request raises.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
