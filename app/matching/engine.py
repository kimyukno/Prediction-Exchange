from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Optional

from .enums import Side, OrderType
from .models import Order, Trade
from .orderbook import OrderBook
from .exceptions import OrderNotFound


class MatchingEngine:
    """
    Matching engine that manages one OrderBook per market.
    Stateless with respect to the database – just in-memory logic.
    """

    def __init__(self) -> None:
        self._books: Dict[str, OrderBook] = {}

    def get_or_create_book(self, market_id: str) -> OrderBook:
        if market_id not in self._books:
            self._books[market_id] = OrderBook(market_id=market_id)
        return self._books[market_id]

    def submit_order(
        self,
        *,
        order_id: str,
        market_id: str,
        user_id: str,
        side: Side,
        order_type: OrderType,
        price: Optional[Decimal],
        quantity: Decimal,
    ) -> List[Trade]:
        """
        Create an Order object and pass it to the corresponding book.

        Returns:
            List of trades created by this submission.
        """
        order = Order(
            id=order_id,
            market_id=market_id,
            user_id=user_id,
            side=side,
            type=order_type,
            price=price,
            quantity=quantity,
            remaining=quantity,
        )

        book = self.get_or_create_book(market_id)
        trades, _residual = book.add_order(order)

        return trades

    def cancel_order(self, market_id: str, order_id: str) -> None:
        book = self._books.get(market_id)
        if not book:
            raise OrderNotFound(f"Market {market_id} has no orderbook")
        book.cancel_order(order_id)
