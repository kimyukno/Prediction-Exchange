from __future__ import annotations

from decimal import Decimal
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.schemas.orders import OrderCreate, OrderResponse, TradeOut, OrderOut
from app.api import deps
from app import models
from app.schemas.orders import OrderCreate, OrderResponse, TradeOut
from app.matching import MatchingEngine

# NOTE: main.py already includes this router under /orders,
# which is why the final path in docs can look like /orders/orders/ or /orders/orders/orders/.
router = APIRouter(prefix="/orders", tags=["orders"])

# Single in-memory matching engine instance (placeholder for now)
engine = MatchingEngine()


@router.post("/orders/", response_model=OrderResponse)
def create_order(
    order_in: OrderCreate,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
) -> OrderResponse:
    """
    Place a new order in a given market.

    - Validates LIMIT vs MARKET (LIMIT must have a price).
    - Looks up market by slug (market_id string).
    - Looks up outcome by code ('YES'/'NO') for that market.
    - Creates an Order row in the DB.
    - Returns order_id and (for now) an empty trades list.
    """

    # --- 1) Normalise order type to a simple string: "LIMIT" / "MARKET" ---
    raw_type = order_in.type
    if isinstance(raw_type, str):
        order_type_str = raw_type.upper()
    else:
        # Enum case: use .value if present, else str(...)
        order_type_str = (
            raw_type.value.upper()
            if hasattr(raw_type, "value")
            else str(raw_type).upper()
        )

    # LIMIT orders must have a price
    if order_type_str == "LIMIT" and order_in.price is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LIMIT orders must have a price.",
        )

    # --- 2) Ensure market exists (by slug) and is OPEN ---
    market = (
        db.query(models.Market)
        .filter(models.Market.slug == order_in.market_id)
        .first()
    )
    if market is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Market {order_in.market_id} not found.",
        )

    if market.status != models.MarketStatus.OPEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Market {order_in.market_id} is not OPEN.",
        )

    # --- 3) Ensure outcome exists for this market (by code: 'YES' / 'NO') ---
    outcome = (
        db.query(models.Outcome)
        .filter(models.Outcome.market_id == market.id)
        .filter(models.Outcome.code == order_in.outcome_id)
        .first()
    )
    if outcome is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Outcome {order_in.outcome_id} not found "
                f"for market {order_in.market_id}."
            ),
        )

    # --- 4) Build DB Order object ---
    # SQLite driver doesn't like Decimal, so we cast to float/int before persisting.
    price_value: float
    if order_in.price is not None:
        price_value = float(order_in.price)
    else:
        # MARKET order with no explicit limit price; store 0.0 for now.
        price_value = 0.0

    quantity_value = int(order_in.quantity)

    db_order = models.Order(
        user_id=current_user.id,
        market_id=market.id,
        outcome_id=outcome.id,
        side=order_in.side,             # "BUY" / "SELL" (Enum or str, model handles it)
        price=price_value,              # float → NUMERIC column in SQLite
        quantity=quantity_value,        # int → INTEGER column
        quantity_filled=0,
        order_type=order_type_str,      # "LIMIT" / "MARKET" as plain string
        status=models.OrderStatus.OPEN,
        is_active=True,
    )

    db.add(db_order)
    db.commit()
    db.refresh(db_order)

    # --- 5) Matching engine hook (no-op for now) ---
    trades_out: List[TradeOut] = []

    return OrderResponse(
        order_id=str(db_order.id),
        trades=trades_out,
    )

@router.get("/", response_model=List[OrderOut])
def list_my_orders(
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    """
    List all orders for the current user, with market slug and outcome code.
    """
    rows = (
        db.query(models.Order, models.Market.slug, models.Outcome.code)
        .join(models.Market, models.Order.market_id == models.Market.id)
        .join(models.Outcome, models.Order.outcome_id == models.Outcome.id)
        .filter(models.Order.user_id == current_user.id)
        .order_by(models.Order.created_at.desc())
        .all()
    )

    orders: List[OrderOut] = []
    for order, market_slug, outcome_code in rows:
        orders.append(
            OrderOut(
                id=order.id,
                market_slug=market_slug,
                outcome_code=outcome_code,
                side=OrderSide(order.side),
                type=OrderType(order.order_type),
                price=order.price,
                quantity=order.quantity,
                quantity_filled=order.quantity_filled,
                status=order.status,
                is_active=order.is_active,
                created_at=order.created_at,
            )
        )

    return orders
