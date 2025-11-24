from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db
from app.models import Market, Outcome, MarketStatus

router = APIRouter(prefix="/markets", tags=["markets"])


# ----- Pydantic Schemas ----- #

class OutcomeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=10)


class OutcomeRead(BaseModel):
    id: int
    name: str
    code: str
    sort_index: int

    class Config:
        from_attributes = True


class MarketCreate(BaseModel):
    slug: str = Field(min_length=3, max_length=100)
    title: str = Field(min_length=3, max_length=200)
    description: Optional[str] = None
    trading_close_at: Optional[datetime] = None
    settle_at: Optional[datetime] = None
    outcomes: List[OutcomeCreate]


class MarketRead(BaseModel):
    id: int
    slug: str
    title: str
    description: Optional[str]
    status: MarketStatus
    trading_close_at: Optional[datetime]
    settle_at: Optional[datetime]
    outcomes: List[OutcomeRead]

    class Config:
        from_attributes = True


# ----- Helpers ----- #

def _get_market_or_404(market_id: int, db: Session) -> Market:
    market = (
        db.query(Market)
        .options(joinedload(Market.outcomes))
        .filter(Market.id == market_id)
        .first()
    )
    if not market:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market not found.",
        )
    return market


# ----- Endpoints ----- #

@router.post(
    "",
    response_model=MarketRead,
    status_code=status.HTTP_201_CREATED,
)
def create_market(
    payload: MarketCreate,
    db: Session = Depends(get_db),
) -> MarketRead:
    """
    Create a new market with its outcomes.

    For now we require the client to pass outcomes explicitly
    (e.g. YES/NO, or multiple choices).
    """
    existing = db.query(Market).filter(Market.slug == payload.slug).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Market with this slug already exists.",
        )

    if not payload.outcomes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one outcome is required.",
        )

    market = Market(
        slug=payload.slug,
        title=payload.title,
        description=payload.description,
        trading_close_at=payload.trading_close_at,
        settle_at=payload.settle_at,
        status=MarketStatus.DRAFT,
    )
    db.add(market)
    db.flush()  # assign market.id

    for idx, outcome_data in enumerate(payload.outcomes):
        outcome = Outcome(
            market_id=market.id,
            name=outcome_data.name,
            code=outcome_data.code.upper(),
            sort_index=idx,
        )
        db.add(outcome)

    db.commit()
    db.refresh(market)
    # reload with outcomes
    market = _get_market_or_404(market.id, db)
    return market


@router.get("", response_model=List[MarketRead])
def list_markets(db: Session = Depends(get_db)) -> list[MarketRead]:
    """
    List all markets with their outcomes.
    """
    markets = (
        db.query(Market)
        .options(joinedload(Market.outcomes))
        .order_by(Market.id)
        .all()
    )
    return markets


@router.get("/{market_id}", response_model=MarketRead)
def get_market(market_id: int, db: Session = Depends(get_db)) -> MarketRead:
    """Get a single market by ID, with outcomes."""
    market = _get_market_or_404(market_id, db)
    return market


@router.post("/{market_id}/open", response_model=MarketRead)
def open_market(market_id: int, db: Session = Depends(get_db)) -> MarketRead:
    """
    Transition market from DRAFT to OPEN (trading allowed).

    Very basic lifecycle for now:
    - Only DRAFT -> OPEN is allowed.
    """
    market = _get_market_or_404(market_id, db)

    if market.status != MarketStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can only open markets in DRAFT status (current: {market.status}).",
        )

    market.status = MarketStatus.OPEN
    db.commit()
    db.refresh(market)
    return market
