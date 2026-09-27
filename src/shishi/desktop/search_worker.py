import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'vendor'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from api_client import _get
try:
    query=sys.argv[1].strip()
    if not query or len(query)>80:raise ValueError('请输入有效的名称或代码')
    data=_get('/api/meta/tickers/search',{'q':query,'asset_type':'a-share','limit':50})
    print(json.dumps({'items':data.get('item',[]),'query':query},ensure_ascii=False))
except Exception as exc:
    print(json.dumps({'error':str(exc)},ensure_ascii=False));sys.exit(1)
