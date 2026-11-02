"""Strict MCP market-data adapter. Configure exact tool names and schemas in .env.

Provider response normalization is intentionally explicit: map documented provider
fields here rather than guessing. No synthetic candles or prices are generated.
"""
import json, os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import Any

INDIA_TZ = ZoneInfo('Asia/Kolkata')

def _parse_timestamp(value):
    if isinstance(value,(int,float)): return datetime.fromtimestamp(value,tz=timezone.utc)
    parsed=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    return parsed.replace(tzinfo=INDIA_TZ) if parsed.tzinfo is None else parsed


def _json_env(name: str, default: Any):
    try: return json.loads(os.getenv(name, json.dumps(default)))
    except json.JSONDecodeError as exc: raise RuntimeError(f'{name} must be valid JSON') from exc


def _configured(name: str) -> str:
    value = os.getenv(name, '').strip()
    if not value: raise RuntimeError(f'{name} is not configured; inspect your MCP server tools first')
    return value


async def call_provider(tool_env: str, args_env: str, substitutions: dict | None = None):
    """Call one configured MCP stdio tool and return raw structured content.

    This uses the official MCP Python client. The server is started per request in
    this starter; production should use a supervised persistent MCP session/cache.
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    command = _configured('MCP_COMMAND')
    argv = _json_env('MCP_ARGS_JSON', [])
    if not isinstance(argv, list) or not all(isinstance(x, str) for x in argv):
        raise RuntimeError('MCP_ARGS_JSON must be a JSON array of strings')
    tool = _configured(tool_env)
    args = _json_env(args_env, {})
    if not isinstance(args, dict): raise RuntimeError(f'{args_env} must be a JSON object')
    for key, value in (substitutions or {}).items():
        args = {k: (v.replace('{'+key+'}', str(value)) if isinstance(v, str) else v) for k,v in args.items()}
    params = StdioServerParameters(command=command, args=argv)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, args)
            if getattr(result, 'isError', False): raise RuntimeError(f'MCP tool {tool} returned an error')
            structured = getattr(result, 'structuredContent', None)
            if structured is not None: return structured
            texts = [getattr(c, 'text', '') for c in getattr(result, 'content', []) if getattr(c, 'text', None)]
            if len(texts) == 1:
                try: return json.loads(texts[0])
                except json.JSONDecodeError: return {'text': texts[0]}
            return {'content': texts}


async def get_universe():
    raw = await call_provider('MCP_UNIVERSE_TOOL', 'MCP_UNIVERSE_ARGS_JSON')
    # Expected normalized contract: {"symbols":["RELIANCE", ...]}.
    if not isinstance(raw, dict) or not isinstance(raw.get('symbols'), list):
        raise RuntimeError('Map your provider universe response to {"symbols": [...]} in market.py')
    return sorted({str(s).upper().replace('.NS','') for s in raw['symbols'] if isinstance(s,str)})


async def get_quote(symbol: str):
    raw = await call_provider('MCP_QUOTE_TOOL','MCP_QUOTE_ARGS_JSON', {'symbol':symbol})
    # Expected normalized contract: {symbol, price, timestamp}.
    if not isinstance(raw,dict) or not isinstance(raw.get('price'),(int,float)) or not raw.get('timestamp'):
        raise RuntimeError('Map provider quote fields to {symbol, price, timestamp} in market.py')
    try:
        stamp=_parse_timestamp(raw['timestamp'])
        age=datetime.now(timezone.utc)-stamp.astimezone(timezone.utc)
        if age>timedelta(minutes=3) or age<timedelta(seconds=-60): raise RuntimeError('Provider quote is stale or future-dated; paper trade blocked')
    except (ValueError, TypeError, OverflowError) as exc:
        raise RuntimeError('Provider quote timestamp is invalid; paper trade blocked') from exc
    return {'symbol':symbol,'price':float(raw['price']),'timestamp':str(raw['timestamp']),'source':'MCP'}


async def get_candles(symbol: str, interval: str, limit: int=100):
    raw = await call_provider('MCP_CANDLES_TOOL','MCP_CANDLES_ARGS_JSON', {'symbol':symbol,'interval':interval,'limit':limit})
    # Expected normalized contract: {candles:[{time,open,high,low,close,volume}, ...]}.
    rows = raw.get('candles') if isinstance(raw,dict) else None
    if not isinstance(rows,list): raise RuntimeError('Map provider candles to {candles:[{time,open,high,low,close,volume}]} in market.py')
    out=[]
    for row in rows:
        if not isinstance(row,dict) or not all(k in row for k in ('time','open','high','low','close','volume')): continue
        out.append({k:row[k] for k in ('time','open','high','low','close','volume')})
    return out[-limit:]
