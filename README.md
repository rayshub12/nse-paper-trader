# NSE Paper Trader

A local-first intraday **paper-trading** dashboard for NSE equities. React + TypeScript frontend, FastAPI backend, SQLite journal, and an MCP market-data adapter.

> **Paper trading only.** This project has no broker integration and cannot place real orders. Strategy signals are experimental, not investment advice.

## Features in this starter
- Virtual ₹50,000 account, tracked by Indian calendar date.
- Long-only simulated buy/sell, cash checks, mandatory stop, risk cap, daily loss guard and open-position cap.
- Scanner ranks up to 60 symbols and displays the top 10 by transparent 5-minute/15-minute rule score.
- 5-minute candlestick chart and deterministic EMA 9/21, VWAP, RSI 14 and ATR explanation.
- SQLite trade journal and daily account snapshot.
- Stale/missing data blocks trading; no synthetic prices or candles.

## Project structure
- `backend/app/main.py`: FastAPI endpoints.
- `backend/app/market.py`: MCP stdio adapter and explicit response normalization contract.
- `backend/app/strategy.py`: indicator and setup rules.
- `backend/app/paper.py`: SQLite paper ledger and risk controls.
- `frontend/src/App.tsx`: React dashboard.
- `frontend/src/style.css`: responsive dark terminal UI.

## Run locally

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
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

## Connect an NSE data MCP server
An example open-source provider to evaluate is [afthabvp/indian-market-mcp](https://github.com/afthabvp/indian-market-mcp). Review its current README, license, data terms, cache/latency and exposed tool schemas before use. Public exchange data may be delayed; do not assume tick-level real-time data.

1. Inspect the MCP server tools and their exact input schemas with an MCP inspector.
2. Set `MCP_COMMAND` and `MCP_ARGS_JSON` in `backend/.env`.
3. Set `MCP_UNIVERSE_TOOL`, `MCP_QUOTE_TOOL`, `MCP_CANDLES_TOOL` to exact tool names.
4. Set each corresponding `*_ARGS_JSON` to the exact JSON input shape required by that tool. Candle args can contain string placeholders `{symbol}`, `{interval}`, and `{limit}`.
5. Map the provider's documented response to the strict normalized structures in `backend/app/market.py`:
   - Universe: `{"symbols":["RELIANCE", "INFY"]}`
   - Quote: `{"price": 1234.5, "timestamp": "2026-01-01T10:00:00+05:30"}`
   - Candles: `{"candles":[{"time":"2026-01-01T10:00:00+05:30","open":1,"high":2,"low":0.5,"close":1.5,"volume":1000}]}`

The normalizer intentionally does not guess provider field names. Until the exact provider schema is mapped and validated, the UI reports market data unavailable and disables trading. Keep provider credentials on the backend; never put them in Vite/frontend environment variables.

## Strategy and risk defaults
- Primary timeframe: 5-minute; confirmation: 15-minute.
- EMA 9/21, VWAP, RSI 14 and ATR are used for explainable scoring.
- BUY requires all four bullish checks; otherwise WAIT.
- Max risk/trade ₹250; daily realized loss limit ₹1,000; max 3 open positions; no leverage or shorts.
- The backend validates a fresh quote before paper fills. This starter uses the provider quote as a simplified simulated fill; it does not model all exchange fees, taxes, spread, slippage, partial fills or market impact.

## Important limitations before live use
This is a prototype, not a validated trading system. Verify data licensing and latency, provider reliability, candle timezone/completion semantics, NSE symbol universe eligibility and all risk logic. The current MCP adapter starts a stdio server for each tool call; production should use a supervised persistent session, caching, rate limits, retries and monitoring. The strategy does not promise profitability.
