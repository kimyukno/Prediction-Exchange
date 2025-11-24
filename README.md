# Mini Prediction-Market Exchange (Kalshi-style)

This repository contains a **mini prediction-market exchange backend** built with **FastAPI** and **PostgreSQL**.  
It is designed as a serious portfolio project for **quant developer / quant researcher / quant analyst** roles.

The goal is to replicate the core mechanics of a Kalshi-style event exchange:

- Binary YES/NO markets on real-world events
- Central limit order books for each market
- Price–time priority matching and partial fills
- Persistent trades, orders, and user positions

---

## High-level Architecture

The backend is split into two main layers:

### 🔹 M1 – Matching Engine (Pure Python)

Located under `app/matching/`:

- **OrderBook** with price–time priority:
  - BUY: highest price first, FIFO within price
  - SELL: lowest price first, FIFO within price
- **MatchingEngine** that manages one `OrderBook` per market
- Works entirely in memory, independent of FastAPI/sqlalchemy
- Designed so it can be tested in isolation via unit tests

### 🔹 M2 – API & Persistence (FastAPI + Postgres)

Located under `app/`:

- `app/main.py` – FastAPI application entrypoint
- `app/api/` – HTTP endpoints for:
  - user accounts & auth
  - creating/listing markets
  - placing/cancelling orders
- `app/models.py` – SQLAlchemy models (User, Market, Order, Trade)
- `app/db.py` – database engine/session factory
- `migrations/` – Alembic migrations to manage schema

The API layer translates incoming HTTP requests into:

1. DB entities (users, markets, orders)
2. Calls to the **matching engine** to generate trades
3. Persistent trade/position updates

---

## Project Structure

```text
app/
  api/           # FastAPI route handlers (accounts, markets, orders, users)
  core/          # configuration & settings
  matching/      # pure matching engine (order book, trades, engine)
  schemas/       # Pydantic schemas for request/response models
  db.py          # SQLAlchemy session + engine
  main.py        # FastAPI app factory / ASGI entrypoint
  models.py      # SQLAlchemy ORM models

migrations/
  env.py, script.py.mako, versions/...

Exchange_User_Guide.pdf
  # High-level user manual describing how to interact with the exchange.

requirements.txt
  # Python dependencies

README.md
  # This file
