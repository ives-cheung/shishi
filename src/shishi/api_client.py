import sys
from runtime import FROZEN,RESOURCES,read_key
if not FROZEN:sys.path.insert(0,str(RESOURCES.parents[1]/'vendor'))
import fuyao_client
_original=fuyao_client.resolve_api_key
def app_key():
    key=read_key()
    if key:return key
    raise RuntimeError('请先在「API Key 设置」中填写你自己的同花顺 API Key。')
fuyao_client.resolve_api_key=app_key
_get=fuyao_client._get
