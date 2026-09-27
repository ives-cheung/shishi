"""Bounded single-stock read, credentials are loaded by the official client."""
import sys,json,re
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'vendor'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from api_client import _get
if sys.argv[1]=='--snapshot':
    codes=sys.argv[2].split(',')
    if not codes or not all(re.fullmatch(r'\d{6}\.(SH|SZ|BJ)',c) for c in codes):raise ValueError('Invalid stock codes')
    try:
        rows=[];stamp=None
        for start in range(0,len(codes),50):
            response=_get('/api/a-share/prices/snapshot',{'thscodes':','.join(codes[start:start+50])});rows.extend(response.get('item',[]));stamp=response.get('timestamp')
        print(json.dumps({'item':rows,'timestamp':stamp},ensure_ascii=False,allow_nan=False))
    except Exception as exc:
        print(json.dumps({'error':str(exc)},ensure_ascii=False));sys.exit(1)
    sys.exit(0)
code=sys.argv[1]
if not re.fullmatch(r'\d{6}\.(SH|SZ|BJ)',code):raise ValueError('Invalid stock code')
now=datetime.now(ZoneInfo('Asia/Shanghai'))
try:
    history=_get('/api/a-share/prices/historical',{'thscode':code,'interval':'1d','start':int((now-timedelta(days=365)).timestamp()*1000),'end':int(now.timestamp()*1000),'adjust':'forward'})
    quote=_get('/api/a-share/prices/snapshot',{'thscodes':code})
    print(json.dumps({'code':code,'history':history,'quote':quote,'fetched_at':now.isoformat()},ensure_ascii=False,allow_nan=False))
except Exception as exc:
    print(json.dumps({'error':str(exc)},ensure_ascii=False));sys.exit(1)
