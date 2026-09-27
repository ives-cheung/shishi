"""Intraday calculations; snapshots are observations, not completed daily bars."""
from datetime import datetime
from zoneinfo import ZoneInfo
import math
TZ=ZoneInfo('Asia/Shanghai')

def elapsed_minutes(at):
    minute=at.hour*60+at.minute+at.second/60
    return max(0,min(120,minute-570))+max(0,min(120,minute-780))

def select_session(calendar, now, mode):
    days=sorted({r['date'].replace('-','') for r in calendar if r['date'].replace('-','')<=now.strftime('%Y%m%d')})
    today=now.strftime('%Y%m%d')
    if mode=='intraday':
        if today not in days:raise ValueError('今天不是交易日，请使用盘后模式查看最近交易日。')
        if not 575<=now.hour*60+now.minute<=900:raise ValueError('盘中模式在交易日 09:35–15:00 可用；开盘前及收盘后请使用盘后模式。')
        prior=[d for d in days if d<today]
        if not prior:raise ValueError('交易日历缺少前一交易日')
        return today,prior[-1]
    if today in days and now.hour<16:raise ValueError('当日盘后数据尚未完成，请使用盘中模式；盘后模式于16点后运行。')
    if not days:raise ValueError('没有可用交易日')
    return days[-1],days[-1]

def snapshot_time(stamp,now):
    if not isinstance(stamp,(int,float)):raise ValueError('行情缺少数据时间，不能进行盘中筛选')
    at=datetime.fromtimestamp(stamp/1000,TZ)
    if at.date()!=now.date() or elapsed_minutes(at)<5 or at>now:raise ValueError('行情尚未更新到本交易日，或开盘数据不足5分钟')
    if elapsed_minutes(now)-elapsed_minutes(at)>10:raise ValueError('行情延迟超过10个交易分钟，请稍后刷新')
    return at

def intraday_technical(bars,quote,at,prior_date,cfg,technical):
    rows=sorted((dict(b) for b in bars if datetime.fromtimestamp(b['date_ms']/1000,TZ).strftime('%Y%m%d')<=prior_date),key=lambda b:b['date_ms'])
    if len(rows)<60:return None,['历史不足60日']
    if datetime.fromtimestamp(rows[-1]['date_ms']/1000,TZ).strftime('%Y%m%d')!=prior_date:return None,['日线未更新至前一交易日']
    keys=['last_price','prev_price','open_price','high_price','low_price','volume','turnover','price_change_ratio_pct']
    if any(not isinstance(quote.get(k),(int,float)) or not math.isfinite(quote[k]) for k in keys):return None,['盘中关键行情缺失']
    if any(quote[k]<=0 for k in keys if k!='price_change_ratio_pct'):return None,['盘中无有效成交']
    if not quote['low_price']<=quote['last_price']<=quote['high_price']:return None,['盘中价格范围异常']
    if abs((quote['last_price']/quote['prev_price']-1)*100-quote['price_change_ratio_pct'])>.15:return None,['盘中涨幅与前收盘不一致']
    # Rebase forward-adjusted history onto snapshot previous close, so prices share a scale.
    scale=quote['prev_price']/rows[-1]['close_price']
    for row in rows:
        for key in ['open_price','high_price','low_price','close_price']:row[key]*=scale
    fraction=elapsed_minutes(at)/240
    synthetic={'date_ms':int(at.timestamp()*1000),'open_price':quote['open_price'],'high_price':quote['high_price'],'low_price':quote['low_price'],'close_price':quote['last_price'],'volume':quote['volume']/fraction,'turnover':quote['turnover']/fraction}
    m,reasons=technical(rows+[synthetic],cfg)
    if m:
        m.update(gain=quote['price_change_ratio_pct'],elapsed_trading_minutes=elapsed_minutes(at),amount_progress_fraction=fraction,observed_turnover=quote['turnover'],history_price_scale=scale,quote_observed_at=at.isoformat())
        reasons=[r.replace('收盘回落明显','盘中价格回落明显') for r in reasons]
    return m,reasons
