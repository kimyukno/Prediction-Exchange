from fastapi import Depends, FastAPI
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api import users, accounts, markets, orders
from app.core.config import settings
from app.db import Base, engine  # Base/engine kept for future migrations/tools


app = FastAPI(title="Mini Prediction Exchange")


class HealthResponse(BaseModel):
    status: str
    environment: str
    database_url_present: bool
    redis_url_present: bool
    db_connection_ok: bool


@app.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """Basic healthcheck endpoint with DB connectivity."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return HealthResponse(
        status="ok",
        environment=settings.app_env,
        database_url_present=bool(settings.database_url),
        redis_url_present=bool(settings.redis_url),
        db_connection_ok=db_ok,
    )


# Include routers
app.include_router(users.router)
app.include_router(accounts.router)
app.include_router(markets.router)
app.include_router(orders.router)
