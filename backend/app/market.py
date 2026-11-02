"""FinStack MCP adapter for NSE market data.

FinStack's free data path uses Yahoo Finance and public sources. It is not a
licensed exchange tick feed. All data is normalized here and stale candles are
rejected before the strategy can produce a tradable setup.
"""
import json
import os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import Any

INDIA_TZ = ZoneInfo("Asia/Kolkata")
SOURCE = "FinStack MCP (free Yahoo Finance/public data)"


def _parse_timestamp(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.replace(tzinfo=INDIA_TZ) if parsed.tzinfo is None else parsed


def _json_env(name: str, default: Any):
    try:
        return json.loads(os.getenv(name, json.dumps(default)))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{name} must be valid JSON") from exc


def _configured(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is not configured")
    return value


async def call_provider(tool_env: str, args_env: str, substitutions: dict | None = None):
    """Start the configured MCP stdio server, call one tool, and decode its result."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    command = _configured("MCP_COMMAND")
    argv = _json_env("MCP_ARGS_JSON", [])
    if not isinstance(argv, list) or not all(isinstance(x, str) for x in argv):
        raise RuntimeError("MCP_ARGS_JSON must be a JSON array of strings")
    tool = _configured(tool_env)
    args = _json_env(args_env, {})
    if not isinstance(args, dict):
        raise RuntimeError(f"{args_env} must be a JSON object")
    for key, value in (substitutions or {}).items():
        args = {
            k: (v.replace("{" + key + "}", str(value)) if isinstance(v, str) else v)
            for k, v in args.items()
        }

    params = StdioServerParameters(command=command, args=argv)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, args)
            if getattr(result, "isError", False):
                raise RuntimeError(f"FinStack MCP tool {tool} returned an error")
            structured = getattr(result, "structuredContent", None)
            if structured is not None:
                return structured
            texts = [
                getattr(c, "text", "")
                for c in getattr(result, "content", [])
                if getattr(c, "text", None)
            ]
            if len(texts) == 1:
                try:
                    return json.loads(texts[0])
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"FinStack MCP tool {tool} did not return JSON") from exc
            raise RuntimeError(f"FinStack MCP tool {tool} returned no usable result")


async def get_universe():
    raw = await call_provider("MCP_UNIVERSE_TOOL", "MCP_UNIVERSE_ARGS_JSON")
    components = raw.get("components") if isinstance(raw, dict) else None
    if not isinstance(components, list):
        raise RuntimeError("FinStack universe response is missing its components array")
    symbols = {
        str(item["symbol"]).upper().replace(".NS", "")
        for item in components
        if isinstance(item, dict) and isinstance(item.get("symbol"), str)
    }
    if not symbols:
        raise RuntimeError("FinStack returned an empty NSE universe")
    return sorted(symbols)


async def get_quote(symbol: str):
    raw = await call_provider("MCP_QUOTE_TOOL", "MCP_QUOTE_ARGS_JSON", {"symbol": symbol})
    if not isinstance(raw, dict) or raw.get("error"):
        detail = raw.get("message", "invalid quote response") if isinstance(raw, dict) else "invalid quote response"
        raise RuntimeError(f"FinStack quote unavailable for {symbol}: {detail}")
    price, timestamp = raw.get("price"), raw.get("timestamp")
    if not isinstance(price, (int, float)) or price <= 0 or not timestamp:
        raise RuntimeError("FinStack quote must contain a positive price and timestamp")
    try:
        stamp = _parse_timestamp(timestamp)
        age = datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)
        if age > timedelta(minutes=3) or age < timedelta(seconds=-60):
            raise RuntimeError("FinStack quote response is stale or future-dated; paper trade blocked")
    except (ValueError, TypeError, OverflowError) as exc:
        raise RuntimeError("FinStack quote timestamp is invalid; paper trade blocked") from exc
    return {
        "symbol": symbol,
        "price": float(price),
        "timestamp": stamp.isoformat(),
        "timestamp_kind": "provider_retrieval_time",
        "source": SOURCE,
        "delay_notice": "Free source; exchange-level real-time status is not guaranteed.",
    }


async def get_candles(symbol: str, interval: str, limit: int = 100):
    if interval not in ("5m", "15m"):
        raise ValueError("Only 5m and 15m candles are supported")
    raw = await call_provider(
        "MCP_CANDLES_TOOL", "MCP_CANDLES_ARGS_JSON",
        {"symbol": symbol, "interval": interval, "limit": limit},
    )
    if not isinstance(raw, dict) or raw.get("error"):
        detail = raw.get("message", "invalid history response") if isinstance(raw, dict) else "invalid history response"
        raise RuntimeError(f"FinStack history unavailable for {symbol}: {detail}")
    rows = raw.get("data")
    if not isinstance(rows, list):
        raise RuntimeError("FinStack history response is missing its data array")

    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        stamp = row.get("date") or row.get("time")
        if stamp is None or not all(k in row for k in ("open", "high", "low", "close", "volume")):
            continue
        try:
            parsed = _parse_timestamp(stamp)
            candle = {
                "time": parsed.isoformat(),
                "open": float(row["open"]), "high": float(row["high"]),
                "low": float(row["low"]), "close": float(row["close"]),
                "volume": float(row["volume"]),
            }
        except (ValueError, TypeError, OverflowError):
            continue
        if candle["close"] <= 0 or candle["high"] < candle["low"]:
            continue
        out.append(candle)

    out.sort(key=lambda item: item["time"])
    out = out[-limit:]
    if not out:
        raise RuntimeError(f"FinStack returned no usable {interval} candles for {symbol}")

    # Candle timestamps denote opening time. Never analyze stale intraday history.
    max_age = timedelta(minutes=15 if interval == "5m" else 40)
    latest = _parse_timestamp(out[-1]["time"])
    age = datetime.now(timezone.utc) - latest.astimezone(timezone.utc)
    if age > max_age or age < timedelta(seconds=-60):
        raise RuntimeError(
            f"FinStack {interval} candles are stale (latest candle {latest.isoformat()}); "
            "analysis and paper entries are blocked."
        )
    return out
