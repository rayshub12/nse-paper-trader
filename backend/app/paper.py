import aiosqlite
from datetime import datetime
from zoneinfo import ZoneInfo

INDIA_TZ = ZoneInfo('Asia/Kolkata')
def trading_day(): return datetime.now(INDIA_TZ).date().isoformat()
from .config import settings

class PaperBook:
    def __init__(self): self.db=settings.database_path
    async def init(self):
        async with aiosqlite.connect(self.db) as db:
            await db.executescript('''CREATE TABLE IF NOT EXISTS account(day TEXT PRIMARY KEY,cash REAL NOT NULL,realized REAL NOT NULL DEFAULT 0); CREATE TABLE IF NOT EXISTS trades(id INTEGER PRIMARY KEY AUTOINCREMENT,day TEXT NOT NULL,symbol TEXT NOT NULL,side TEXT NOT NULL,qty INTEGER NOT NULL,price REAL NOT NULL,stop REAL,created_at TEXT NOT NULL,pnl REAL NOT NULL DEFAULT 0);'''); await db.commit()
    async def _account(self,db,day):
        cur=await db.execute('SELECT cash,realized FROM account WHERE day=?',(day,)); row=await cur.fetchone()
        if row is None:
            await db.execute('INSERT INTO account(day,cash,realized) VALUES(?,?,0)',(day,settings.starting_cash)); return [settings.starting_cash,0.0]
        return [float(row[0]),float(row[1])]
    async def snapshot(self):
        day=trading_day()
        async with aiosqlite.connect(self.db) as db:
            cash,realized=await self._account(db,day); await db.commit()
            cur=await db.execute("SELECT b.id,b.symbol,b.qty,b.price,b.stop,b.created_at FROM trades b WHERE b.day=? AND b.side='BUY' AND NOT EXISTS (SELECT 1 FROM trades c WHERE c.day=b.day AND c.symbol=b.symbol AND c.side='CLOSED' AND c.id>b.id)",(day,))
            rows=await cur.fetchall()
            cur=await db.execute('SELECT id,symbol,side,qty,price,stop,created_at,pnl FROM trades WHERE day=? ORDER BY id DESC LIMIT 100',(day,)); trades=await cur.fetchall()
        positions=[{'id':r[0],'symbol':r[1],'qty':r[2],'entry':r[3],'stop_loss':r[4],'created_at':r[5]} for r in rows]
        return {'day':day,'cash':cash,'realized_pnl':realized,'positions':positions,'trades':[dict(id=r[0],symbol=r[1],side=r[2],qty=r[3],price=r[4],stop_loss=r[5],created_at=r[6],pnl=r[7]) for r in trades]}
    async def buy(self,symbol,qty,price,stop):
        if qty<1 or price<=0 or stop<=0 or stop>=price: raise ValueError('Quantity and prices invalid; stop must be below entry.')
        if (price-stop)*qty>settings.max_risk_per_trade: raise ValueError('Trade exceeds max risk per trade.')
        day=date.today().isoformat()
        async with aiosqlite.connect(self.db) as db:
            cash,realized=await self._account(db,day)
            cur=await db.execute("SELECT COUNT(*) FROM trades b WHERE b.day=? AND b.side='BUY' AND NOT EXISTS (SELECT 1 FROM trades c WHERE c.day=b.day AND c.symbol=b.symbol AND c.side='CLOSED' AND c.id>b.id)",(day,)); count=(await cur.fetchone())[0]
            if count>=settings.max_open_positions: raise ValueError('Maximum open positions reached.')
            cur=await db.execute("SELECT 1 FROM trades b WHERE b.day=? AND b.symbol=? AND b.side='BUY' AND NOT EXISTS (SELECT 1 FROM trades c WHERE c.day=b.day AND c.symbol=b.symbol AND c.side='CLOSED' AND c.id>b.id) LIMIT 1",(day,symbol.upper()))
            if await cur.fetchone(): raise ValueError('A paper position for this symbol is already open.')
            if realized<=-settings.daily_loss_limit: raise ValueError('Daily realized loss limit reached.')
            cost=qty*price
            if cost>cash: raise ValueError('Insufficient virtual cash.')
            await db.execute('INSERT INTO trades(day,symbol,side,qty,price,stop,created_at) VALUES(?,?,?,?,?,?,?)',(day,symbol.upper(), 'BUY',qty,price,stop,datetime.now().isoformat()))
            await db.execute('UPDATE account SET cash=? WHERE day=?',(cash-cost,day)); await db.commit()
        return await self.snapshot()
    async def sell(self,symbol,price):
        day=date.today().isoformat(); symbol=symbol.upper()
        async with aiosqlite.connect(self.db) as db:
            cash,realized=await self._account(db,day)
            cur=await db.execute("SELECT b.id,b.qty,b.price FROM trades b WHERE b.day=? AND b.symbol=? AND b.side='BUY' AND NOT EXISTS (SELECT 1 FROM trades c WHERE c.day=b.day AND c.symbol=b.symbol AND c.side='CLOSED' AND c.id>b.id) ORDER BY b.id DESC LIMIT 1",(day,symbol)); row=await cur.fetchone()
            if not row: raise ValueError('No open paper position for this symbol.')
            _,qty,entry=row; pnl=(price-entry)*qty
            await db.execute('INSERT INTO trades(day,symbol,side,qty,price,created_at,pnl) VALUES(?,?,?,?,?,?,?)',(day,symbol,'CLOSED',qty,price,datetime.now().isoformat(),pnl))
            await db.execute('UPDATE account SET cash=?,realized=? WHERE day=?',(cash+qty*price,realized+pnl,day)); await db.commit()
        return await self.snapshot()

book=PaperBook()
