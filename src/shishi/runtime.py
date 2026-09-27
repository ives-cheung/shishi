"""Bundle resources are read-only; personal state stays outside the application."""
import sys,os,json,shutil
from pathlib import Path
FROZEN=getattr(sys,'frozen',False)
RESOURCES=Path(sys._MEIPASS)/'stock-screen' if FROZEN else Path(__file__).resolve().parent
DATA=Path.home()/'Library/Application Support/shishi'
DATA.mkdir(parents=True,exist_ok=True)
CONFIG=DATA/'config.json' if FROZEN else RESOURCES/'config.json'
if not CONFIG.exists():shutil.copy2(RESOURCES/'config.json',CONFIG)
OUTPUT=DATA/'results' if FROZEN else RESOURCES.parents[1]/'out/stock-screen'
KEYFILE=DATA/'api-key.json'
def read_key():
    if not KEYFILE.exists():return ''
    return json.loads(KEYFILE.read_text()).get('api_key','').strip()
def save_key(key):
    tmp=KEYFILE.with_suffix('.tmp')
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as f:json.dump({'api_key':key.strip()},f)
    os.chmod(tmp,0o600);tmp.replace(KEYFILE)
def worker_args(name,args):
    return [sys.executable, '--worker',name,*args] if FROZEN else [sys.executable,str(RESOURCES/('screen.py' if name=='screen' else 'desktop/'+name+'.py')),*args]
