import sys,runpy
from pathlib import Path
from runtime import RESOURCES
sys.path[:0]=[str(RESOURCES),str(RESOURCES/'desktop')]
if len(sys.argv)>2 and sys.argv[1]=='--worker':
    name=sys.argv[2]
    if name not in ('screen','quote_worker','search_worker'):raise SystemExit('Unknown worker')
    path=RESOURCES/('screen.py' if name=='screen' else 'desktop/'+name+'.py')
    sys.argv=[str(path),*sys.argv[3:]]
else:
    path=RESOURCES/'desktop/app.py'
runpy.run_path(str(path),run_name='__main__')
