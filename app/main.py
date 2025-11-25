from fastapi import FastAPI

from app.api import users, accounts, markets, orders
from app.db import engine
from app.models import Base

app = FastAPI()


@app.on_event("startup")
def on_startup() -> None:
    """
    Ensure all database tables are created on startup.

    This is mainly for local development with SQLite.
    It will create any missing tables defined in app.models.Base.metadata.
    """
    Base.metadata.create_all(bind=engine)


# Routers
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
app.include_router(markets.router, prefix="/markets", tags=["markets"])
app.include_router(orders.router, prefix="/orders", tags=["orders"])
