from datetime import datetime, timezone
import pandas as pd


def _indicators(rows):
    df=pd.DataFrame(rows)
    if len(df)<25: return None
    for col in ('open','high','low','close','volume'): df[col]=pd.to_numeric(df[col],errors='coerce')
    df=df.dropna()
    if len(df)<25: return None
    df['ema9']=df.close.ewm(span=9,adjust=False).mean()
    df['ema21']=df.close.ewm(span=21,adjust=False).mean()
    delta=df.close.diff(); gain=delta.clip(lower=0).rolling(14).mean(); loss=(-delta.clip(upper=0)).rolling(14).mean()
    rs=gain/loss.replace(0, float('nan')); df['rsi']=100-(100/(1+rs))
    typical=(df.high+df.low+df.close)/3
    df['vwap']=(typical*df.volume).cumsum()/df.volume.cumsum().replace(0,float('nan'))
    tr=pd.concat([df.high-df.low,(df.high-df.close.shift()).abs(),(df.low-df.close.shift()).abs()],axis=1).max(axis=1)
    df['atr']=tr.rolling(14).mean()
    return df


def analyze(symbol, five, fifteen):
    base={'symbol':symbol,'signal':'WAIT','score':0,'entry':None,'stop_loss':None,'target_1':None,'target_2':None,'reasons':[],'status':'insufficient_data'}
    a=_indicators(five); b=_indicators(fifteen)
    if a is None or b is None: base['reasons']=['Need at least 25 valid completed candles on both 5m and 15m timeframes.']; return base
    x=a.iloc[-1]; y=b.iloc[-1]
    if pd.isna(x.atr) or pd.isna(x.rsi) or pd.isna(x.vwap): base['reasons']=['Indicators are not ready.']; return base
    reasons=[]; score=0
    if x.ema9>x.ema21: score+=1; reasons.append('5m EMA 9 is above EMA 21.')
    else: reasons.append('5m EMA trend is not bullish.')
    if x.close>x.vwap: score+=1; reasons.append('Price is above session VWAP.')
    else: reasons.append('Price is below session VWAP.')
    if 50<=x.rsi<=70: score+=1; reasons.append(f'5m RSI is {x.rsi:.1f}, in the momentum zone.')
    else: reasons.append(f'5m RSI is {x.rsi:.1f}; outside the preferred 50–70 zone.')
    if y.ema9>y.ema21: score+=1; reasons.append('15m trend confirms bullish EMA alignment.')
    else: reasons.append('15m trend does not confirm bullish EMA alignment.')
    entry=float(x.close); atr=float(x.atr); stop=entry-1.2*atr
    risk=entry-stop
    signal='BUY' if score>=4 and risk>0 else 'WAIT'
    base.update(signal=signal,score=score,entry=round(entry,2) if signal=='BUY' else None,
      stop_loss=round(stop,2) if signal=='BUY' else None,
      target_1=round(entry+1.5*risk,2) if signal=='BUY' else None,
      target_2=round(entry+2*risk,2) if signal=='BUY' else None,
      reasons=reasons,status='ready')
    return base
