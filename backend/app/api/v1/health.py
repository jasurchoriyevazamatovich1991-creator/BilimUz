"""
Health check endpoint. Verifies the database is actually reachable, not
just that the process is alive — a process can be "up" while its DB
connection pool is exhausted or Postgres is unreachable, and a load
balancer needs to know the difference.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.schemas import success_response
from app.db.session import get_db

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
def health_check(db: Session = Depends(get_db)):
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unreachable"

    overall = "ok" if db_status == "ok" else "degraded"
    return success_response(
        {"status": overall, "database": db_status},
        "Service health.",
    )
