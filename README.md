# Mini Prediction-Market Exchange (Kalshi-style)

Backend for a toy prediction-market exchange, built as a serious portfolio project for quant-developer / quant-researcher roles.

The goal is to mimic the core behaviour of a real exchange:

- users with accounts,
- markets with YES/NO contracts,
- a central order book and matching engine,
- orders → trades persisted in a database.

Right now this is a **backend-only** project with an in-memory matching engine and a FastAPI REST interface.

---

## 1. Tech stack

- **Language:** Python 3.12
- **Web framework:** FastAPI + Uvicorn
- **Data models & validation:** Pydantic v2
- **ORM:** SQLAlchemy
- **Migrations:** Alembic
- **Database (dev):** SQLite (`exchange.db` in repo root)  
  > The models are written to be easily portable to Postgres later.
- **Environment config:** `.env` (not committed)

---

## 2. What’s implemented so far

### 2.1 Core domain

- **Users**
  - `users` table with `id`, `email`, `created_at`.
  - `POST /users` to create a user.
  - For now, authentication is stubbed: `get_current_user` simply returns the **first** user in the DB.  
    (This is deliberate so the rest of the system can be built before adding real auth/JWT.)

- **Markets & Outcomes**
  - `markets` table with:
    - `slug` (e.g. `rain-mumbai-2025-12-01`),
    - `title`, `description`,
    - `status` (`DRAFT`, `OPEN`, `SETTLED`, `CANCELLED`),
    - `trading_close_at`, `settle_at`, timestamps.
  - `outcomes` table linked to `markets`:
    - `name` (e.g. `"Yes"` / `"No"`),
    - `code` (e.g. `"YES"` / `"NO"`),
    - `sort_index` for display order.
  - Typical YES/NO market has exactly two outcomes with codes `"YES"` and `"NO"`.
  - Endpoints (via `/markets/...`) to:
    - create markets,
    - list markets,
    - fetch a single market,
    - attach outcomes to a market.
  - Market status is stored but **not yet enforced** in the matching engine (orders can still be submitted to a `DRAFT` market for now).

- **Orders & Trades**
  - `orders` table:
    - `user_id`, `market_id`, `outcome_id`,
    - `side` (`BUY` / `SELL`),
    - `order_type` (`LIMIT` / `MARKET`),
    - `price` (0–1 for yes/no contracts),
    - `quantity`, `quantity_filled`,
    - `status` (`OPEN`, `PARTIALLY_FILLED`, `FILLED`, etc.),
    - `is_active`, `created_at`, `updated_at`.
  - `trades` table:
    - `market_id`,
    - `buy_order_id`, `sell_order_id`,
    - `price`, `quantity`,
    - `executed_at`.

  Matching/booking behaviour:

  - **In-memory matching engine** (`MatchingEngine` in `app/matching.py`)
    - One global engine instance for the whole app.
    - Maintains per-market order books in memory.
    - Currently supports **LIMIT** orders, matched price-time priority.
    - Matching result is a list of trades: `(buy_order_id, sell_order_id, price, quantity)`.

  - **Order placement endpoint** (implemented):
    - `POST /orders/orders`
    - Request body (`OrderCreate` schema):

      ```json
      {
        "market_id": "rain-mumbai-2025-12-01",
        "outcome_id": "YES",
        "side": "BUY",
        "type": "LIMIT",
        "price": 0.55,
        "quantity": 10,
        "currency": "INR"
      }
      ```

    - Behaviour:
      1. Validate input:
         - LIMIT orders must include `price` between `0` and `1`.
      2. Resolve `market_id` as **market slug**, ensure market exists.
      3. Find the requested outcome for that market via `outcome_id` (the outcome **code**, `"YES"` or `"NO"`).
      4. Create a persistent `Order` row in the DB with:
         - `user_id` from the current user,
         - `order_type` stored as `"LIMIT"` or `"MARKET"`,
         - `quantity_filled = 0`, `status = "OPEN"`.
      5. Submit the order to the in-memory `MatchingEngine` → receive a list of trades.
      6. Persist each trade into the `trades` table, and update `quantity_filled` / `status` for the current order.
      7. Return an `OrderResponse` containing:
         - the order id
         - list of trades created because of this submission.

### 2.2 What is **not** implemented yet

These are planned but not wired up yet:

- User authentication / JWT / sessions.
- Wallets / balances:
  - Right now **placing an order does not debit or credit any balance**.  
    Accounting will be added later (locked funds, realised P&L, withdrawals, etc.).
- Order cancellation / amendments.
- Real-time WebSocket feeds.
- Market settlement logic & PnL.

---

## 3. Project structure

Rough layout (only key files):

```text
Prediction-Exchange/
├── app/
│   ├── main.py              # FastAPI app, router includes
│   ├── db.py                # DB engine & SessionLocal (SQLite in dev)
│   ├── models.py            # SQLAlchemy models (User, Market, Outcome, Order, Trade, enums)
│   ├── matching.py          # In-memory MatchingEngine
│   ├── api/
│   │   ├── health.py        # Simple health-check endpoint
│   │   ├── users.py         # POST /users
│   │   ├── markets.py       # Market + outcome endpoints
│   │   └── orders.py        # POST /orders/orders (place order)
│   └── schemas/
│       ├── users.py
│       ├── markets.py
│       └── orders.py        # OrderCreate, OrderResponse, TradeOut
├── migrations/
│   ├── env.py
│   └── versions/
│       └── 896429297bfc_create_core_exchange_tables.py
├── alembic.ini
├── requirements.txt
├── .env                     # local config (ignored by git)
└── Exchange_User_Guide.pdf  # user manual for non-devs
