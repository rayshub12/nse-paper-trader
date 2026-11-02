from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from .paper import book
from .market import get_universe,get_quote,get_candles
from .strategy import analyze

app=FastAPI(title='NSE Paper Trader API',version='0.1.0')
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])

class BuyRequest(BaseModel): symbol:str; qty:int=Field(gt=0); price:float=Field(gt=0); stop_loss:float=Field(gt=0)
class SellRequest(BaseModel): symbol:str; price:float=Field(gt=0)

@app.on_event('startup')
async def startup(): await book.init()
@app.get('/api/health')
async def health(): return {'ok':True,'time':datetime.now(timezone.utc).isoformat()}
@app.get('/api/account')
async def account(): return await book.snapshot()
@app.get('/api/universe')
async def universe():
    try: return {'symbols':await get_universe()}
    except Exception as e: raise HTTPException(503,str(e))
@app.get('/api/quote/{symbol}')
async def quote(symbol:str):
    try: return await get_quote(symbol.upper())
    except Exception as e: raise HTTPException(503,str(e))
@app.get('/api/analysis/{symbol}')
async def analysis(symbol:str):
    try:
        five=await get_candles(symbol.upper(),'5m',100); fifteen=await get_candles(symbol.upper(),'15m',100)
        return {'analysis':analyze(symbol.upper(),five,fifteen),'candles':five,'source':'MCP'}
    except Exception as e: raise HTTPException(503,str(e))
@app.post('/api/paper/buy')
async def buy(body:BuyRequest):
    try:
        quote=await get_quote(body.symbol.upper())
        if abs(quote['price']-body.price)/quote['price']>0.005: raise ValueError('Displayed price is stale by more than 0.5%; refresh quote.')
        return await book.buy(body.symbol,body.qty,quote['price'],body.stop_loss)
    except Exception as e: raise HTTPException(400,str(e))
@app.post('/api/paper/sell')
async def sell(body:SellRequest):
    try:
        quote=await get_quote(body.symbol.upper())
        if abs(quote['price']-body.price)/quote['price']>0.005: raise ValueError('Displayed price is stale by more than 0.5%; refresh quote.')
        return await book.sell(body.symbol,quote['price'])
    except Exception as e: raise HTTPException(400,str(e))
