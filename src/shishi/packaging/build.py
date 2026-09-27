"""Run with the build venv on the target macOS architecture."""
from pathlib import Path
import subprocess,sys,json
base=Path(__file__).resolve().parents[1];repo=base.parents[1]
stage=base/'packaging/stage';stage.mkdir(parents=True,exist_ok=True)
# Public defaults only; never package personal state, credentials, caches or reports.
config=json.loads((base/'config.json').read_text())
config.update(fundamental_mode='soft_risk',normalize_available_weights=True,missing_is_failure=False)
(stage/'config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2))
args=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--windowed','--name','拾势','--osx-bundle-identifier','com.shishi.stockresearch','--icon',str(base/'desktop/assets/Shishi.icns'),'--distpath',str(repo/'dist/shishi-portable'),'--workpath',str(repo/'build/shishi-portable'),'--specpath',str(stage),'--paths',str(base),'--paths',str(repo/'vendor'),'--hidden-import','marketdb.credentials','--paths',str(base/'desktop'),'--paths',str(repo/'vendor'),'--add-data',str(base/'packaging/licenses')+':licenses','--collect-all','qtawesome','--hidden-import','app','--hidden-import','intraday','--hidden-import','api_client','--hidden-import','pandas','--hidden-import','watchlist','--hidden-import','market_search','--exclude-module','pyarrow','--exclude-module','matplotlib','--exclude-module','scipy','--exclude-module','duckdb']
for name in ['screen.py','desktop/app.py','desktop/search_worker.py','desktop/quote_worker.py']:
    src=base/name;args+=['--add-data',str(src)+':stock-screen/'+str(Path(name).parent)]
args+=['--add-data',str(stage/'config.json')+':stock-screen','--add-data',str(base/'desktop/assets')+':stock-screen/desktop/assets',str(base/'launcher.py')]
subprocess.run(args,check=True)
import plistlib
bundle=repo/'dist/shishi-portable/拾势.app'
plist=bundle/'Contents/Info.plist'
info=plistlib.loads(plist.read_bytes());info.update(LSMinimumSystemVersion='13.0',CFBundleShortVersionString='1.0.0',CFBundleVersion='1',NSHighResolutionCapable=True)
plist.write_bytes(plistlib.dumps(info))
subprocess.run(['codesign','--force','--deep','--sign','-',str(bundle)],check=True)
