# NSE Paper Trader

A local-first intraday **paper-trading** dashboard for NSE equities. React + TypeScript frontend, FastAPI backend, SQLite journal, and FinStack MCP market data.

> **Paper trading only.** This project cannot place real broker orders. Strategy signals are experimental, not investment advice.

## Features
- Virtual ₹50,000 account, tracked by Indian calendar date.
- Long-only simulated buy/sell, cash checks, mandatory stop, risk cap, daily loss guard and open-position cap.
- Scanner ranks up to 50 Nifty 50 symbols and displays the top 10 using transparent 5-minute/15-minute rules.
- 5-minute candlestick chart and EMA 9/21, VWAP, RSI 14 and ATR analysis.
- SQLite trade journal and daily account snapshot.
- Missing or stale candles block analysis and paper entries; no synthetic prices or candles.

## Market data: FinStack MCP

The backend starts the open-source [FinStack MCP](https://github.com/finstacklabs/finstack-mcp) server locally over stdio. It configures these tools:

- `sensex_components(index_name="nifty50")` for the Nifty 50 universe.
- `nse_quote(symbol)` for quotes.
- `nse_historical(symbol, period="5d", interval="5m"|"15m")` for OHLCV history.

The free data path relies primarily on Yahoo Finance and public sources. It is **not a guaranteed real-time exchange feed** and may be delayed, cached, rate-limited or unavailable. FinStack's upstream historical cache defaults to 24 hours; this app launches it through `app.finstack_launcher`, which reduces in-memory quote/history cache TTLs to 60 seconds. This does not make the underlying source real-time. The app rejects intraday candles older than 15 minutes (5m) or 40 minutes (15m).

## Run locally

### Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

### Frontend
In a second terminal:
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173.

## Strategy and risk defaults
- Primary timeframe: 5-minute; confirmation: 15-minute.
- EMA 9/21, VWAP, RSI 14 and ATR are used for explainable scoring.
- BUY requires all four bullish checks; otherwise WAIT.
- Max risk/trade ₹250; daily realized loss limit ₹1,000; max 3 open positions; no leverage or shorts.
- The backend validates a recent quote before paper fills. The free quote timestamp is provider retrieval time, not a verified exchange tick timestamp.

## Important limitations
This is a prototype, not a validated trading system. Verify data licensing and latency, provider reliability, candle timezone/completion semantics, NSE symbol eligibility and risk logic. FinStack MCP and its upstream data sources can change independently. The app never places broker orders and does not promise profitability.
