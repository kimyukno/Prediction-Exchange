from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.db import Base
import enum


# ----- ENUMS ----- #

class MarketStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    PAUSED = "PAUSED"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


class OrderSide(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, enum.Enum):
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


# ----- USER ----- #

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    balances = relationship("AccountBalance", back_populates="user")
    orders = relationship("Order", back_populates="user")


# ----- MARKET / OUTCOME ----- #

class Market(Base):
    __tablename__ = "markets"

    id = Column(Integer, primary_key=True)
    slug = Column(String, unique=True, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)

    status = Column(
        Enum(MarketStatus, name="market_status"),
        nullable=False,
        server_default=MarketStatus.DRAFT.value,
    )

    trading_close_at = Column(DateTime(timezone=True), nullable=True)
    settle_at = Column(DateTime(timezone=True), nullable=True)

   # resolved_outcome_id = Column(
   #     Integer,
   #     ForeignKey("outcomes.id", ondelete="SET NULL"),
   #     nullable=True,
   # )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    outcomes = relationship("Outcome", back_populates="market")
    orders = relationship("Order", back_populates="market")
    trades = relationship("Trade", back_populates="market")


class Outcome(Base):
    __tablename__ = "outcomes"

    id = Column(Integer, primary_key=True)
    market_id = Column(
        Integer,
        ForeignKey("markets.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String, nullable=False)
    code = Column(String, nullable=False)
    sort_index = Column(Integer, nullable=False, default=0)

    market = relationship("Market", back_populates="outcomes")

    __table_args__ = (
        UniqueConstraint("market_id", "code", name="uq_market_outcome_code"),
    )


# ----- ACCOUNT BALANCES ----- #

class AccountBalance(Base):
    __tablename__ = "account_balances"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    currency = Column(String, nullable=False, default="INR")
    available = Column(Numeric(18, 4), nullable=False, default=0)
    locked = Column(Numeric(18, 4), nullable=False, default=0)

    user = relationship("User", back_populates="balances")

    __table_args__ = (
        UniqueConstraint("user_id", "currency", name="uq_user_currency"),
    )


# ----- ORDERS & TRADES ----- #

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    market_id = Column(
        Integer,
        ForeignKey("markets.id", ondelete="CASCADE"),
        nullable=False,
    )
    outcome_id = Column(
        Integer,
        ForeignKey("outcomes.id", ondelete="CASCADE"),
        nullable=False,
    )

    side = Column(Enum(OrderSide, name="order_side"), nullable=False)

    price = Column(Numeric(6, 4), nullable=False)
    quantity = Column(Integer, nullable=False)
    quantity_filled = Column(Integer, nullable=False, default=0)

    status = Column(
        Enum(OrderStatus, name="order_status"),
        nullable=False,
        server_default=OrderStatus.OPEN.value,
    )

    is_active = Column(Boolean, nullable=False, server_default="true")

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="orders")
    market = relationship("Market", back_populates="orders")
    outcome = relationship("Outcome")
    buy_trades = relationship(
        "Trade",
        back_populates="buy_order",
        foreign_keys="Trade.buy_order_id",
    )
    sell_trades = relationship(
        "Trade",
        back_populates="sell_order",
        foreign_keys="Trade.sell_order_id",
    )


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    market_id = Column(
        Integer,
        ForeignKey("markets.id", ondelete="CASCADE"),
        nullable=False,
    )
    outcome_id = Column(
        Integer,
        ForeignKey("outcomes.id", ondelete="CASCADE"),
        nullable=False,
    )

    buy_order_id = Column(
        Integer,
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
    )
    sell_order_id = Column(
        Integer,
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
    )

    price = Column(Numeric(6, 4), nullable=False)
    quantity = Column(Integer, nullable=False)

    executed_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    market = relationship("Market", back_populates="trades")
    buy_order = relationship(
        "Order",
        foreign_keys=[buy_order_id],
        back_populates="buy_trades",
    )
    sell_order = relationship(
        "Order",
        foreign_keys=[sell_order_id],
        back_populates="sell_trades",
    )

