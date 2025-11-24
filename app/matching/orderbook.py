from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Tuple, Dict, Optional

from .enums import Side, OrderType
from .models import Order, Trade
from .exceptions import OrderNotFound


@dataclass
class OrderBook:
    """
    Simple price-time priority order book for a single market.

    - BUYs are sorted by price DESC, then time ASC.
    - SELLs are sorted by price ASC, then time ASC.
    """
    market_id: str
    buys: List[Order] = field(default_factory=list)
    sells: List[Order] = field(default_factory=list)
    _orders_by_id: Dict[str, Order] = field(default_factory=dict)

    # ---------- Public API ----------

    def add_order(self, order: Order) -> Tuple[List[Trade], Optional[Order]]:
        """
        Add an order to the book and perform matching.

        Returns:
            trades: list of generated trades
            residual_order: the order if partially/un-filled and resting on the book,
                            or None if fully filled.
        """
        trades: List[Trade] = []

        if order.side == Side.BUY:
            trades = self._match_buy(order)
        else:
            trades = self._match_sell(order)

        residual_order: Optional[Order] = None
        if order.remaining > Decimal("0"):
            # Rest on the book
            self._add_to_book(order)
            residual_order = order
            self._orders_by_id[order.id] = order

        return trades, residual_order

    def cancel_order(self, order_id: str) -> None:
        """
        Remove an order from the book.
        Raises OrderNotFound if not present.
        """
        order = self._orders_by_id.pop(order_id, None)
        if order is None:
            raise OrderNotFound(f"Order {order_id} not found in orderbook")

        book_side = self.buys if order.side == Side.BUY else self.sells
        for idx, existing in enumerate(book_side):
            if existing.id == order.id:
                del book_side[idx]
                break

    def get_best_bid(self) -> Optional[Order]:
        return self.buys[0] if self.buys else None

    def get_best_ask(self) -> Optional[Order]:
        return self.sells[0] if self.sells else None

    # ---------- Internal helpers ----------

    def _match_buy(self, incoming: Order) -> List[Trade]:
        trades: List[Trade] = []

        # BUY matches against best asks (lowest price)
        i = 0
        while incoming.remaining > 0 and i < len(self.sells):
            best_ask = self.sells[i]

            # Price check for LIMIT. MARKET always crosses.
            if incoming.type == OrderType.LIMIT and best_ask.price is not None:
                if incoming.price is None or best_ask.price > incoming.price:
                    break

            trade_qty = min(incoming.remaining, best_ask.remaining)
            trade_price = best_ask.price or incoming.price  # should not be None here

            trades.append(
                Trade(
                    id=f"t-{incoming.id}-{best_ask.id}-{len(trades)+1}",
                    market_id=incoming.market_id,
                    buy_order_id=incoming.id,
                    sell_order_id=best_ask.id,
                    price=trade_price,
                    quantity=trade_qty,
                )
            )

            incoming.remaining -= trade_qty
            best_ask.remaining -= trade_qty

            if best_ask.remaining <= 0:
                # Remove fully filled ask
                del self.sells[i]
                self._orders_by_id.pop(best_ask.id, None)
            else:
                i += 1

        return trades

    def _match_sell(self, incoming: Order) -> List[Trade]:
        trades: List[Trade] = []

        # SELL matches against best bids (highest price)
        i = 0
        while incoming.remaining > 0 and i < len(self.buys):
            best_bid = self.buys[i]

            if incoming.type == OrderType.LIMIT and best_bid.price is not None:
                if incoming.price is None or best_bid.price < incoming.price:
                    break

            trade_qty = min(incoming.remaining, best_bid.remaining)
            trade_price = best_bid.price or incoming.price

            trades.append(
                Trade(
                    id=f"t-{best_bid.id}-{incoming.id}-{len(trades)+1}",
                    market_id=incoming.market_id,
                    buy_order_id=best_bid.id,
                    sell_order_id=incoming.id,
                    price=trade_price,
                    quantity=trade_qty,
                )
            )

            incoming.remaining -= trade_qty
            best_bid.remaining -= trade_qty

            if best_bid.remaining <= 0:
                del self.buys[i]
                self._orders_by_id.pop(best_bid.id, None)
            else:
                i += 1

        return trades

    def _add_to_book(self, order: Order) -> None:
        """
        Insert order into the appropriate side while keeping book sorted.
        """
        book_side = self.buys if order.side == Side.BUY else self.sells

        if order.side == Side.BUY:
            # Sort by price DESC, time ASC
            key = lambda o: (-(o.price or Decimal("0")), o.created_at)
        else:
            # Sort by price ASC, time ASC
            key = lambda o: ((o.price or Decimal("0")), o.created_at)

        book_side.append(order)
        book_side.sort(key=key)
