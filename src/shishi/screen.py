"""End-of-day research screener. No order execution; missing factors stay missing."""
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import Counter
import json, sys, time, argparse, math, hashlib
import pandas as pd
from intraday import select_session,snapshot_time,intraday_technical,elapsed_minutes

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'vendor'))
from api_client import _get
from runtime import CONFIG,OUTPUT,FROZEN
HERE=Path(__file__).parent
C=json.loads(CONFIG.read_text())
TZ=ZoneInfo('Asia/Shanghai')

def technical(bars, cfg=C):
    df=pd.DataFrame(bars).sort_values('date_ms')
    if len(df)<61 or df.date_ms.duplicated().any(): return None, ['历史不足61日或日期重复']
    cols=['open_price','high_price','low_price','close_price','volume','turnover']
    if df[cols].tail(61).isna().any().any() or (df[['close_price','volume','turnover']].tail(61)<=0).any().any(): return None,['历史关键值缺失或无成交']
    today=df.iloc[-1]; prev=df.iloc[:-1]
    high20=prev.high_price.tail(20).max(); low60=prev.low_price.tail(60).min()
    spread=today.high_price-today.low_price
    m={'gain':(today.close_price/prev.iloc[-1].close_price-1)*100,
       'daily_volume_multiple':today.volume/prev.volume.tail(5).mean(),
       'turnover_multiple':today.turnover/prev.turnover.tail(20).mean(),
       'avg20_turnover':prev.turnover.tail(20).mean(),
       'low60_distance_pct':(today.close_price/low60-1)*100,
       'breakout_ratio':today.close_price/high20,
       'return5_pct':(today.close_price/df.iloc[-6].close_price-1)*100,
       'return20_pct':(today.close_price/df.iloc[-21].close_price-1)*100,
       'close_location':(today.close_price-today.low_price)/spread if spread>0 else 0,
       'bar_date':datetime.fromtimestamp(int(today.date_ms)/1000,TZ).strftime('%Y-%m-%d')}
    rules=[(cfg['gain_min_pct']<=m['gain']<=cfg['gain_max_pct'],f"日涨幅不在{cfg['gain_min_pct']:g}%～{cfg['gain_max_pct']:g}%"),
      (m['daily_volume_multiple']>=cfg['min_daily_volume_multiple'],'日量未明显放大'),
      (m['turnover_multiple']>=cfg['min_turnover_multiple'],'成交额未明显放大'),
      (m['avg20_turnover']>=cfg['min_avg20_turnover_cny'],'20日平均成交额不足'),
      (m['low60_distance_pct']<=cfg['max_distance_from_low60_pct'],'远离60日低点'),
      (cfg['min_close_to_prior_high20']<=m['breakout_ratio']<=cfg['max_close_to_prior_high20'],'未接近20日高点或偏离过大'),
      (m['return5_pct']<=cfg['max_return5_pct'],'5日累计涨幅过大'),
      (m['return20_pct']<=cfg['max_return20_pct'],'20日累计涨幅过大'),
      (m['close_location']>=cfg['min_close_location'],'收盘回落明显')]
    ratio=today.get('volume_ratio')
    if ratio is not None:
        rules.append((ratio>=cfg.get('min_volume_ratio',0),'量比低于下限'))
    elif cfg.get('missing_is_failure',False):
        rules.append((False,'量比数据缺失'))
    return m,[reason for ok,reason in rules if not ok]

def profit_yoy(income, latest):
    previous=next((r for r in income if r.get('fiscal_year')==latest.get('fiscal_year',0)-1 and r.get('fiscal_period')==latest.get('fiscal_period')),None)
    if previous is None: return None
    current=latest.get('net_profit'); base=previous.get('net_profit')
    if current is None or base is None or base<=0: return None
    return (current/base-1)*100

def score_pool(pool, cfg):
    df=pd.DataFrame(pool)
    if df.empty:return df
    components={'gain':'gain','turnover':'turnover_multiple','breakout20':'breakout_ratio','sector_strength':'sector_gain'}
    raw=pd.Series(0.0,index=df.index);available=pd.Series(0.0,index=df.index)
    for key,col in components.items():
        values=pd.to_numeric(df[col],errors='coerce');valid=values.notna() & values.map(lambda x:math.isfinite(x) if pd.notna(x) else False)
        score=values.where(valid).rank(method='average',pct=True)*cfg['weights'][key]
        df['score_'+key]=score;raw+=score.fillna(0);available+=valid.astype(float)*cfg['weights'][key]
    valid=df['fraction'].notna()
    df['score_sector_rank']=(1-df['fraction'])*cfg['weights']['sector_rank'];raw+=df['score_sector_rank'].fillna(0);available+=valid.astype(float)*cfg['weights']['sector_rank']
    df['score_raw']=raw;df['available_weight']=available;df['coverage_pct']=available/sum(cfg['weights'].values())*100
    df['score_observed']=raw/available*100 if cfg.get('normalize_available_weights') else raw
    df['score_available_max']=100 if cfg.get('normalize_available_weights') else available
    df=df[available>0]
    if cfg.get('missing_is_failure',True):df=df[available==sum(cfg['weights'].values())]
    return df

def review_allowed(q,cfg):
    if cfg.get('missing_is_failure',True) and q['financial_missing']:return False
    return cfg.get('fundamental_mode','hard_filter')=='soft_risk' or not q['financial_flags']

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--refresh',action='store_true'); parser.add_argument('--mode',choices=['eod','intraday'],default='eod'); args=parser.parse_args()
    now=datetime.now(TZ); out=(OUTPUT if FROZEN else ROOT/'out/stock-screen')/(now.strftime('%Y%m%d')+('-intraday' if args.mode=='intraday' else '')); out.mkdir(parents=True,exist_ok=True)
    cache=out/'raw'; cache.mkdir(exist_ok=True); manifest=[]; errors=[]
    def fetch(name,path,params):
        f=cache/(name+'_'+hashlib.sha256(json.dumps(params,sort_keys=True).encode()).hexdigest()[:10]+'.json')
        live=args.mode=='intraday' and ('snapshot' in path or name=='calendar')
        if f.exists() and not (args.refresh and args.mode=='eod') and not live: d=json.loads(f.read_text())
        else:
            d=_get(path,params); f.write_text(json.dumps(d,ensure_ascii=False)); time.sleep(.08)
        manifest.append({'file':str(f),'endpoint':path,'params':params,'timestamp':d.get('timestamp')})
        return d
    calendar=fetch('calendar','/api/a-share/calendar/trading-days',{})['item']
    asof,prior_date=select_session(calendar,now,args.mode)
    date=f'{asof[:4]}-{asof[4:6]}-{asof[6:]}'
    symbols=[]; offset=0
    while True:
        page=fetch(f'symbols_{offset}','/api/meta/tickers/list',{'asset_type':'a-share','limit':10000,'offset':offset})['item']; symbols+=page
        if len(page)<10000: break
        offset+=len(page)
    names={r['thscode']:r for r in symbols}; quotes=[]; offset=0
    while True:
        d=fetch(f'quotes_{offset}','/api/a-share/prices/snapshot',{'limit':1000,'offset':offset}); page=d['item']
        if args.mode=='intraday':
            at=snapshot_time(d.get('timestamp'),datetime.now(TZ))
            for q in page:q['_snapshot_ms']=int(at.timestamp()*1000)
        quotes+=page; offset+=len(page)
        if offset>=d['total']: break
        if not page: raise RuntimeError('Incomplete quote pagination')
    if args.mode=='intraday' and quotes and max(q['_snapshot_ms'] for q in quotes)-min(q['_snapshot_ms'] for q in quotes)>300000:
        raise ValueError('全市场分页行情跨越超过5分钟，请重新运行以减少时点偏差')
    assert len({q['thscode'] for q in quotes})==len(quotes),'Duplicate quote keys'
    qm={q['thscode']:q for q in quotes}; candidates=[]; rejected=[]
    for q in quotes:
        code=q['thscode']; name=names.get(code,{}).get('name')
        if not name or 'ST' in name.upper() or '退' in name: continue
        p=q.get('last_price'); gain=q.get('price_change_ratio_pct'); amount=q.get('turnover')
        if p is None or gain is None or amount is None or p<=0: continue
        if not C['gain_min_pct']<=gain<=C['gain_max_pct'] or amount<C['min_turnover_cny']*(elapsed_minutes(datetime.fromtimestamp(q['_snapshot_ms']/1000,TZ))/240 if args.mode=='intraday' else 1): continue
        if C['price_is_hard_filter'] and p>C['preferred_max_price']: continue
        candidates.append({**q,'name':name,'price_preferred':p<=C['preferred_max_price'],'lot100_cost':p*100})
    print(f'Universe={len(quotes)}, snapshot candidates={len(candidates)}, session={date}',flush=True)
    end=datetime.strptime(date,'%Y-%m-%d').replace(tzinfo=TZ,hour=23,minute=59,second=59)
    history_end=datetime.strptime(prior_date,'%Y%m%d').replace(tzinfo=TZ,hour=23,minute=59,second=59)
    if args.mode=='intraday':end=now
    params={'interval':'1d','start':int((history_end-timedelta(days=C['history_calendar_days'])).timestamp()*1000),'end':int(history_end.timestamp()*1000),'adjust':'forward'}
    technical_pass=[]
    for i,q in enumerate(candidates):
        code=q['thscode']
        try:
            bars=fetch('history_'+code,'/api/a-share/prices/historical',{'thscode':code,**params})['item']
            if args.mode=='intraday':
                m,reasons=intraday_technical(bars,q,datetime.fromtimestamp(q['_snapshot_ms']/1000,TZ),prior_date,C,technical)
            else:
                m,reasons=technical(bars)
                if m and m['bar_date']!=date: reasons.append('日线滞后')
                if bars:
                    b=max(bars,key=lambda x:x['date_ms'])
                    for k in ['volume','turnover']:
                        if not b.get(k) or abs(q[k]/b[k]-1)>.01: reasons.append('快照与日线成交不一致'); break
            if reasons: rejected.append({'thscode':code,'stage':'technical','reasons':reasons})
            else: technical_pass.append({**q,**m})
        except Exception as e: errors.append({'thscode':code,'stage':'history','error':str(e)})
        if (i+1)%20==0: print(f'History {i+1}/{len(candidates)}, pass={len(technical_pass)}',flush=True)
    print(f'Technical passes={len(technical_pass)}',flush=True)
    sectors=fetch('industries','/api/a-share-index/catalog/ths-index-list',{'tag':'industry'})['item']
    sq={}
    for i in range(0,len(sectors),50):
        d=fetch(f'sector_quotes_{i}','/api/a-share-index/prices/snapshot',{'thscodes':','.join(x['thscode'] for x in sectors[i:i+50])})
        if args.mode=='intraday':snapshot_time(d.get('timestamp'),datetime.now(TZ))
        sq.update({r['thscode']:r for r in d['item']})
    memberships={q['thscode']:[] for q in technical_pass}
    if technical_pass:
        for i,s in enumerate(sectors):
            try:
                members=fetch('members_'+s['thscode'],'/api/a-share-index/constituents/ths-stock-list',{'thscode':s['thscode']})['item']
                available=[qm[r['thscode']] for r in members if r['thscode'] in qm and qm[r['thscode']].get('price_change_ratio_pct') is not None]
                for r in members:
                    code=r['thscode']
                    if code not in memberships: continue
                    rank=1+sum(a['price_change_ratio_pct']>qm[code]['price_change_ratio_pct'] for a in available)
                    memberships[code].append({'sector':s['name'],'sector_code':s['thscode'],'sector_gain':sq.get(s['thscode'],{}).get('price_change_ratio_pct'),'rank':rank,'members':len(members),'covered':len(available),'fraction':rank/len(available) if available else 1})
            except Exception as e: errors.append({'sector':s['thscode'],'stage':'membership','error':str(e)})
            if (i+1)%50==0: print(f'Sector membership {i+1}/{len(sectors)}',flush=True)
    pool=[]
    for q in technical_pass:
        options=memberships[q['thscode']]
        # Smallest membership = most specific available industry; never cherry-pick best performance.
        if not options:
            if C.get('missing_is_failure',True):rejected.append({'thscode':q['thscode'],'stage':'sector','reasons':['行业归属缺失']});continue
            s={'sector':'未知','sector_code':None,'sector_gain':None,'rank':None,'members':0,'covered':0,'fraction':None}
        else:s=min(options,key=lambda x:(x['members'],x['sector_code']))
        if s['covered']!=s['members']:s['fraction']=None;s['rank']=None
        if ((C.get('missing_is_failure',True) and (s['sector_gain'] is None or s['fraction'] is None)) or (s['sector_gain'] is not None and s['sector_gain']<=C['min_sector_gain_pct']) or (s['fraction'] is not None and s['fraction']>C['max_sector_rank_fraction'])):
            rejected.append({'thscode':q['thscode'],'stage':'sector','reasons':['板块不强/排名不靠前/成分行情不完整']}); continue
        pool.append({**q,**s,'volume_ratio':None,'turnover_rate':None,'catalyst':'未核实'})
    if pool:
        df=score_pool(pool,C)
        # Price is a soft preference: preferred-price candidates first, then observed score.
        df=df.sort_values(['price_preferred','score_observed','thscode'],ascending=[False,False,True]).head(C['top_n'])
        top=json.loads(df.to_json(orient='records',force_ascii=False))
    else: top=[]
    print(f'Initial shortlist={len(top)}; checking financials',flush=True)
    if top:
        try:
            vals=fetch('valuations_'+hashlib.sha256(','.join(q['thscode'] for q in top).encode()).hexdigest()[:12],'/api/a-share/valuations/snapshot',{'thscodes':','.join(q['thscode'] for q in top)})['item']; vm={r['thscode']:r for r in vals}
        except Exception as e:
            vm={};errors.append({'stage':'valuations','error':str(e)})
        for q in top:
            code=q['thscode']; flags=[]; missing=[]
            try:
                income=fetch('income_'+code,'/api/a-share/financials/income-statements',{'thscode':code,'period':'quarterly','limit':8})['item']
                disclosed=[r for r in income if r.get('report_date_ms') and r['report_date_ms']<=int(end.timestamp()*1000)]
                if not disclosed: raise ValueError('没有已披露财报')
                latest=max(disclosed,key=lambda r:r['period_end_ms']); dt=datetime.fromtimestamp(latest['period_end_ms']/1000,TZ); report=f'{dt.year}-{(dt.month-1)//3+1}'
                q['report']=report
                if (end-dt).days>200: missing.append('财报过旧')
                indicators=fetch('indicators_'+code,'/api/a-share/financials/indicators',{'thscode':code,'report':report})
                iv={v['index_id']:float(v['value']) if v.get('value') is not None else None for a in indicators['abilities'] for v in a['indicators']}
                q['profit_yoy_source']='同报告期利润表净利润同比（上年同期为正）'
                iv['net_profit_yoy_growth_ratio']=profit_yoy(disclosed,latest)
                q.update({k:iv.get(k) for k in ['net_profit_yoy_growth_ratio','index_weighted_avg_roe','sale_gross_margin','sale_net_interest_ratio','assets_debt_ratio']})
                for k,v in [(k,q[k]) for k in ['net_profit_yoy_growth_ratio','index_weighted_avg_roe','assets_debt_ratio']]:
                    if v is None or not math.isfinite(v): missing.append(k)
                if q['net_profit_yoy_growth_ratio'] is not None and q['net_profit_yoy_growth_ratio']<C['min_profit_yoy_pct']: flags.append(f"净利润同比低于{C['min_profit_yoy_pct']:g}%")
                if latest.get('parent_holder_net_profit') is None: missing.append('归母净利润')
                elif latest['parent_holder_net_profit']<=0: flags.append('归母净利润非正')
                debt=q['assets_debt_ratio']
                if any(w in q['sector'] for w in ['银行','保险','证券','金融']): missing.append('金融业负债率需专门口径')
                elif debt is not None and debt>C['max_debt_ratio_pct_nonfinancial']: flags.append(f"资产负债率超过{C['max_debt_ratio_pct_nonfinancial']:g}%")
                cash=fetch('cash_'+code,'/api/a-share/financials/cash-flow-statements',{'thscode':code,'period':'quarterly','limit':8})['item']
                cf=next((r.get('act_cash_flow_net') for r in cash if r.get('period_end_ms')==latest['period_end_ms'] and r.get('report_date_ms') and r['report_date_ms']<=int(end.timestamp()*1000)),None)
                q['operating_cashflow']=cf
                if cf is None: missing.append('经营现金流')
                elif cf<0: flags.append('经营现金流为负，需核实季节性')
                v=vm.get(code,{})
                for k,ceiling in [('pe_ttm',C['max_pe_ttm']),('pb_mrq',C['max_pb_mrq'])]:
                    q[k]=v.get(k)
                    if q[k] is None: missing.append(k)
                    elif q[k]<=0 or q[k]>ceiling: flags.append(k+'超出试运行范围')
            except Exception as e: missing.append('财务请求失败'); errors.append({'thscode':code,'stage':'financial','error':str(e)})
            q['financial_flags']=flags; q['financial_missing']=missing
            q['review_status']=('风险提示' if C.get('fundamental_mode')=='soft_risk' else '排雷未通过') if flags else ('数据待补' if missing else '无已识别异常')
    review=[q for q in top if review_allowed(q,C)][:C['display_n']]
    result={'mode':args.mode,'history_asof':prior_date,'intraday_note':'成交额和日量倍数按已交易分钟/240线性折算，仅为时段进度估算；不是真实量比。快照无逐股时间，无法验证每只股票的实时性。' if args.mode=='intraday' else '', 'asof':date,'generated_at':now.isoformat(),'config':C,'counts':{'universe':len(quotes),'snapshot_candidates':len(candidates),'technical_pass':len(technical_pass),'sector_pass':len(pool),'top20':len(top),'review5':len(review),'strict_final':len(review)},'missing_required':[f"量比及其上升趋势（{C['weights']['volume_ratio']:g}%）",f"换手率及其上升趋势（{C['weights']['turnover_rate']:g}%）",'行业催化及纯情绪脉冲判断'],'score_note':('按每只股票可用权重归一化至100分。' if C.get('normalize_available_weights') else '按原始权重计分。')+('缺失指标判失败。' if C.get('missing_is_failure') else '缺失指标不判失败，显示数据覆盖率。'),'top20':top,'review5':review,'strict_final':review,'rejected':rejected,'errors':errors,'source_manifest':manifest}
    result['completed_at']=datetime.now(TZ).isoformat()
    result_tmp=out/'result.json.tmp';result_tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False));result_tmp.replace(out/'result.json')
    lines=[f'# 条件选股试运行 · {date}', '', '来源：同花顺 Financial API。日线前复权；本结果为研究观察名单，非投资建议。', '', result['score_note'],result['intraday_note'],'', '按当前策略输出候选：基本面异常仅作风险提示，缺失评分指标按可用权重处理。', '', '## 筛选数量', '', json.dumps(result['counts'],ensure_ascii=False),'', '## 待复核候选（最多5只）','', '|代码|名称|价格|涨幅%|日量倍数|成交额倍数|行业|行业涨幅%|行业排名|归一化评分|','|---|---|---:|---:|---:|---:|---|---:|---|---:|']
    for q in review: lines.append(f"|{q['thscode']}|{q['name']}|{q['last_price']:.2f}|{q['gain']:.2f}|{q['daily_volume_multiple']:.2f}|{q['turnover_multiple']:.2f}|{q['sector']}|{q['sector_gain'] if q['sector_gain'] is not None else '—'}|{q['rank']}/{q['covered']}|{q['score_observed']:.2f}|")
    lines+=['','## 初筛名单与财务排雷','', '|代码|名称|价格|财务问题|缺失项|','|---|---|---:|---|---|']
    for q in top: lines.append(f"|{q['thscode']}|{q['name']}|{q['last_price']:.2f}|{'；'.join(q['financial_flags']) or '无已识别异常'}|{'；'.join(q['financial_missing']) or '无'}|")
    if not review: lines.append('\n本次没有通过已实现条件及财务排雷的候选，不放宽条件凑数。')
    lines+=['','## 限制','', '价格≤30元为优先项；100股成本仅供预算比较，不保证所有板块最低申报数量均为100股。行业采用成分最少的匹配行业，不挑涨幅最大的板块。行业排名由全市场快照计算。快照没有个股交易日期，以日线日期和成交量/额一致性核对。基本面采用软风险模式，异常仅提示，缺失不判失败。收盘位置和涨幅阈值只能过滤部分脉冲，不能验证催化。', '',f'请求失败数：{len(errors)}。详见 result.json；参数为试运行假设，尚未回测。']
    (out/'REPORT.md').write_text('\n'.join(lines))
    print(json.dumps({'counts':result['counts'],'errors':len(errors),'output':str(out)},ensure_ascii=False),flush=True)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(str(exc),file=sys.stderr);sys.exit(1)
