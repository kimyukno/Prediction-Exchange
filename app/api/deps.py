from __future__ import annotations

from typing import Generator

from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app import models


def get_db() -> Generator[Session, None, None]:
    """
    Dependency that provides a database session and closes it afterwards.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    x_user_id: int = Header(..., alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> models.User:
    """
    Simple 'current user' dependency.

    - The client sends a header:  X-User-Id: <user_id>
    - We look up that user in the database.
    - If found, we return it as the current user.
    - If not, we raise 401 Unauthorized.

    This mimics a real exchange pattern where the authenticated identity
    comes from headers (API key / token), not from the request body.
    """
    user = db.query(models.User).filter(models.User.id == x_user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"User with id {x_user_id} not found. Create the user first.",
        )
    return user
