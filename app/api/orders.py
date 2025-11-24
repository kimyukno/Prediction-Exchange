from __future__ import annotations

from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app import models
from app.schemas.orders import OrderCreate, OrderResponse, TradeOut
from app.matching import MatchingEngine

router = APIRouter(prefix="/orders", tags=["orders"])

# Single in-memory matching engine instance for the whole app
engine = MatchingEngine()


@router.post("/", response_model=OrderResponse)
def create_order(
    order_in: OrderCreate,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    """
    Place a new order in a given market.

    Flow:
    1. Validate input (e.g. limit orders need a price).
    2. Ensure market exists.
    3. Create an Order row in the DB.
    4. Pass the order to the matching engine -> get list of trades.
    5. Persist trades in the DB and update this order's remaining quantity.
    6. Return the order id + list of trades created by this submission.
    """

    # 1) Basic validation: LIMIT orders must have a price
    if order_in.type == order_in.type.LIMIT and order_in.price is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LIMIT orders must have a price.",
        )

    # 2) Ensure market exists
    market = db.query(models.Market).filter(models.Market.id == order_in.market_id).first()
    if market is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Market {order_in.market_id} not found.",
        )

    # 3) Create DB order (persistent representation)
    # NOTE: If your field names differ, tweak here accordingly.
    db_order = models.Order(
        market_id=order_in.market_id,
        user_id=current_user.id,
        side=order_in.side.value,   # store "BUY"/"SELL"
        type=order_in.type.value,   # store "LIMIT"/"MARKET"
        price=order_in.price,
        quantity=order_in.quantity,
        remaining=order_in.quantity,   # make sure your model has this column
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)

    # 4) Call matching engine (in-memory)
    trades = engine.submit_order(
        order_id=str(db_order.id),
        market_id=str(db_order.market_id),
        user_id=str(current_user.id),
        side=order_in.side,
        order_type=order_in.type,
        price=order_in.price,
        quantity=order_in.quantity,
    )

    # 5) Persist trades in DB and update this order's remaining quantity
    db_trades: List[models.Trade] = []
    filled_quantity = Decimal("0")

    for t in trades:
        # t.buy_order_id and t.sell_order_id are strings; cast to int
        db_trade = models.Trade(
            market_id=int(t.market_id),
            buy_order_id=int(t.buy_order_id),
            sell_order_id=int(t.sell_order_id),
            price=t.price,
            quantity=t.quantity,
        )
        db.add(db_trade)
        db_trades.append(db_trade)

        # If this order is either the buyer or seller, accumulate its filled qty
        if t.buy_order_id == str(db_order.id) or t.sell_order_id == str(db_order.id):
            filled_quantity += t.quantity

    db.commit()
    for db_trade in db_trades:
        db.refresh(db_trade)

    # Update remaining quantity on the DB order
    db_order.remaining = db_order.quantity - filled_quantity
    db.commit()
    db.refresh(db_order)

    # 6) Build response model
    trades_out: List[TradeOut] = [
        TradeOut(
            id=str(tr.id),
            market_id=str(tr.market_id),
            buy_order_id=str(tr.buy_order_id),
            sell_order_id=str(tr.sell_order_id),
            price=tr.price,
            quantity=tr.quantity,
            executed_at=tr.executed_at,
        )
        for tr in db_trades
    ]

    return OrderResponse(
        order_id=str(db_order.id),
        trades=trades_out,
    )
