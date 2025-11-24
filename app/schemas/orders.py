from __future__ import annotations

from decimal import Decimal
from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel, Field

from app.matching.enums import Side, OrderType


class OrderCreate(BaseModel):
    market_id: str
    side: Side
    type: OrderType = Field(default=OrderType.LIMIT)
    price: Optional[Decimal] = None  # required for LIMIT, ignored for MARKET
    quantity: Decimal


class TradeOut(BaseModel):
    id: str
    market_id: str
    buy_order_id: str
    sell_order_id: str
    price: Decimal
    quantity: Decimal
    executed_at: datetime


class OrderResponse(BaseModel):
    order_id: str
    trades: List[TradeOut]
