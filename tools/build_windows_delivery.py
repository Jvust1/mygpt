"""Build exact source; deliver only after actual Windows executable checks pass."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
NAME='mygpt'
OUT=ROOT/'delivery';EVIDENCE=OUT/'evidence'
OUT.mkdir(exist_ok=True);EVIDENCE.mkdir(exist_ok=True)

def run(args,**kwargs):
    subprocess.run(args,check=True,cwd=ROOT,**kwargs)

args=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--windowed',
      '--name',NAME,'--exclude-module','playwright','--exclude-module','pytest','--exclude-module','mcp.cli',
      '--paths','brain','--collect-submodules','mygpt_brain','--collect-all','pydantic_ai',
      '--collect-submodules','mcp.client','--collect-submodules','mcp.server','--collect-data','mcp',
      '--recursive-copy-metadata','pydantic-ai-slim','--recursive-copy-metadata','mcp',
      '--add-data','desktop_ui:desktop_ui','--add-data','host:host','--add-data','companion:companion',
      '--add-data','brain/pyproject.toml:brain','desktop.py']
run(args)
package=ROOT/'dist'/NAME
removed=[]
for p in sorted(package.rglob('*')):
    if p.is_file() and p.suffix.lower() in {'.ttf','.otf','.woff','.woff2','.eot','.ttc'}:
        removed.append(p.relative_to(package).as_posix());p.unlink()
for p in package.rglob('*.css'):
    text=p.read_text(encoding='utf-8',errors='strict')
    text=re.sub(r'@font-face\s*\{[^}]*\}', '', text)
    p.write_text(text,encoding='utf-8')
(EVIDENCE/'font-exclusion.json').write_text(json.dumps({'font_binaries_distributed':0,'excluded_count':len(removed)},indent=2),encoding='utf-8')
exe=package/(NAME+'.exe')
with tempfile.TemporaryDirectory(prefix=NAME+'-native-') as temp:
    smoke=EVIDENCE/'native-smoke.json'
    run([str(exe),'--self-test',str(smoke),'--data-dir',str(Path(temp)/'controller')],timeout=150)
    assert json.loads(smoke.read_text(encoding='utf-8'))['ok']
run([sys.executable,'tools/desktop_browser_test.py',str(exe),str(EVIDENCE)],timeout=240)
run(['git','diff','--exit-code'])
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
shutil.copy2(ROOT/'docs/DESKTOP_DELIVERY.md',package/'使用说明.md')
(package/'SOURCE_COMMIT.txt').write_text(commit+'\n',encoding='utf-8')
manifest={'app':NAME,'version':'2026.09.25-rc1','source_commit':commit,
          'built_on':sys.platform,'python':sys.version,'native_executable_smoke':True,
          'actual_user_device_tested':False,'live_model_quality_accepted':False,'files':[]}
for p in sorted(package.rglob('*')):
    if p.is_file():manifest['files'].append({'path':p.relative_to(package).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(package/'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
portable=OUT/(NAME+'-Windows-Portable.zip')
with zipfile.ZipFile(portable,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(package.rglob('*')):
        if p.is_file():z.write(p,NAME+'/'+p.relative_to(package).as_posix())
run(['git','archive','--format=zip','HEAD','-o',str(OUT/(NAME+'-Source-and-Tests.zip'))])
with zipfile.ZipFile(OUT/(NAME+'-Verification.zip'),'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(EVIDENCE.rglob('*')):
        if p.is_file():z.write(p,p.relative_to(EVIDENCE).as_posix())
(OUT/'release.json').write_text(json.dumps({k:v for k,v in manifest.items() if k!='files'},indent=2),encoding='utf-8')
(OUT/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(OUT.glob('*.zip'))),encoding='utf-8')
print(json.dumps({'app':NAME,'status':'BUILT_NATIVE_SMOKE_AND_BROWSER_PASS','commit':commit,'package_bytes':portable.stat().st_size}))
