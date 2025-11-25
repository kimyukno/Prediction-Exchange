from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


# ---------- Enums ----------

class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"


# ---------- Request body for creating an order ----------

class OrderCreate(BaseModel):
    """
    Request body for placing an order.

    Note:
    - `market_id` is actually the **market slug**, e.g. "rain-mumbai-2025-12-01".
    - `outcome_id` is the **outcome code**, e.g. "YES" or "NO".
    """

    market_id: str = Field(
        ...,
        description="Market slug (e.g. 'rain-mumbai-2025-12-01').",
    )
    outcome_id: str = Field(
        ...,
        description="Outcome code for this market (e.g. 'YES' or 'NO').",
    )

    side: OrderSide = Field(
        ...,
        description="Side of the order: BUY or SELL.",
    )

    type: OrderType = Field(
        ...,
        description="Order type: LIMIT or MARKET.",
    )

    # LIMIT orders must provide a price; MARKET orders can leave this null.
    price: Optional[Decimal] = Field(
        None,
        ge=0,
        le=1,
        description="Contract price between 0 and 1 for LIMIT orders.",
    )

    quantity: Decimal = Field(
        ...,
        ge=0,
        description="Number of contracts.",
    )

    currency: str = Field(
        "INR",
        description="Settlement currency (currently only 'INR').",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "market_id": "rain-mumbai-2025-12-01",
                "outcome_id": "YES",
                "side": "BUY",
                "type": "LIMIT",
                "price": 0.55,
                "quantity": 10,
                "currency": "INR",
            }
        }


# ---------- Response models ----------

class TradeOut(BaseModel):
    id: str
    market_id: str
    buy_order_id: str
    sell_order_id: str
    price: Decimal
    quantity: Decimal
    executed_at: Optional[str]

    class Config:
        from_attributes = True  # replaces orm_mode in Pydantic v2


class OrderResponse(BaseModel):
    order_id: str
    trades: List[TradeOut]

    class Config:
        from_attributes = True  # replaces orm_mode in Pydantic v2

class OrderOut(BaseModel):
    """
    Lightweight view of a user's order, with human-friendly IDs.
    """

    id: int
    market_slug: str
    outcome_code: str
    side: OrderSide
    type: OrderType
    price: Decimal
    quantity: int
    quantity_filled: int
    status: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
