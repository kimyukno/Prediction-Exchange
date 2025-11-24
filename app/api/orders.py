from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import (
    AccountBalance,
    Market,
    MarketStatus,
    Order,
    OrderSide,
    OrderStatus,
    Outcome,
    User,
)

router = APIRouter(prefix="/orders", tags=["orders"])


# ----- Pydantic Schemas ----- #

class OrderCreate(BaseModel):
    user_id: int
    market_id: int
    outcome_id: int
    side: OrderSide
    # price is fraction of 1.0 (e.g. 0.35 = 35 "cents" of payout)
    price: Decimal = Field(gt=Decimal("0"), lt=Decimal("1"))
    quantity: int = Field(gt=0)
    currency: str = Field(default="INR", min_length=1, max_length=10)


class OrderRead(BaseModel):
    id: int
    user_id: int
    market_id: int
    outcome_id: int
    side: OrderSide
    price: Decimal
    quantity: int
    quantity_filled: int
    status: OrderStatus
    is_active: bool

    class Config:
        from_attributes = True


# ----- Internal helpers ----- #

def _get_user_or_404(user_id: int, db: Session) -> User:
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return user


def _get_open_market_or_404(market_id: int, db: Session) -> Market:
    market = db.query(Market).get(market_id)
    if not market:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market not found.",
        )
    if market.status != MarketStatus.OPEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Market is not OPEN (current status: {market.status}).",
        )
    return market


def _get_outcome_or_404(outcome_id: int, market_id: int, db: Session) -> Outcome:
    outcome = (
        db.query(Outcome)
        .filter(
            Outcome.id == outcome_id,
            Outcome.market_id == market_id,
        )
        .first()
    )
    if not outcome:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outcome not found for this market.",
        )
    return outcome


def _get_balance(user_id: int, currency: str, db: Session) -> Optional[AccountBalance]:
    return (
        db.query(AccountBalance)
        .filter(
            AccountBalance.user_id == user_id,
            AccountBalance.currency == currency,
        )
        .with_for_update(nowait=False)
        .first()
    )


# ----- Main endpoint: place order ----- #

@router.post(
    "",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
)
def place_order(
    payload: OrderCreate,
    db: Session = Depends(get_db),
) -> OrderRead:
    """
    Place a new order.

    For now:
    - Only checks basic risk & state.
    - Locks required margin in user's account (available -> locked).
    - Does NOT match orders yet (matching engine will come later).
    """
    # 1) Validate user & market & outcome
    _get_user_or_404(payload.user_id, db)
    market = _get_open_market_or_404(payload.market_id, db)
    _get_outcome_or_404(payload.outcome_id, market.id, db)

    # 2) Risk/margin calculation
    currency = payload.currency.upper()
    price = payload.price
    qty_dec = Decimal(payload.quantity)

    base_payout = Decimal("1.0")  # per contract

    if payload.side == OrderSide.BUY:
        required_funds = price * qty_dec * base_payout
    else:  # SELL
        required_funds = (base_payout - price) * qty_dec

    if required_funds <= Decimal("0"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Required funds computed as non-positive. Check price/quantity.",
        )

    # 3) Check and update account balance
    balance = _get_balance(payload.user_id, currency, db)
    if balance is None:
        # treat as zero balance if row missing
        available = Decimal("0.0")
        locked = Decimal("0.0")
    else:
        available = balance.available or Decimal("0.0")
        locked = balance.locked or Decimal("0.0")

    if available < required_funds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient funds: required {required_funds}, available {available}.",
        )

    # If we reach here, we can lock funds
    if balance is None:
        balance = AccountBalance(
            user_id=payload.user_id,
            currency=currency,
            available=available - required_funds,
            locked=locked + required_funds,
        )
        db.add(balance)
    else:
        balance.available = available - required_funds
        balance.locked = locked + required_funds

    # 4) Create the order
    order = Order(
        user_id=payload.user_id,
        market_id=payload.market_id,
        outcome_id=payload.outcome_id,
        side=payload.side,
        price=price,
        quantity=payload.quantity,
        quantity_filled=0,
        status=OrderStatus.OPEN,
        is_active=True,
    )
    db.add(order)

    # 5) Commit everything atomically
    db.commit()
    db.refresh(order)

    return order


# ----- Read-only helper endpoints ----- #

@router.get("/{order_id}", response_model=OrderRead)
def get_order(order_id: int, db: Session = Depends(get_db)) -> OrderRead:
    """Fetch a single order by ID."""
    order = db.query(Order).get(order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found.",
        )
    return order


@router.get("", response_model=List[OrderRead])
def list_orders(
    user_id: Optional[int] = Query(default=None),
    market_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
) -> list[OrderRead]:
    """
    List orders, optionally filtered by user_id and/or market_id.
    """
    q = db.query(Order)
    if user_id is not None:
        q = q.filter(Order.user_id == user_id)
    if market_id is not None:
        q = q.filter(Order.market_id == market_id)
    q = q.order_by(Order.id)
    return q.all()
