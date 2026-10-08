"""Final source/path audit; run on each lease host under nice."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess

b=Path('/mpac/sdicks02/repos/clasher-lease');root=b/'repo';host=socket.gethostname().split('.')[0]
pins=json.loads((b/'source-sha256.json').read_text())
errors=[];adapted=[]
identity='reports/strategy_council_20260928/fleet/identity.sh'
p16='reports/strategy_council_20260928/c56/engine/tools/p16_identity.py'
for f,h in pins.items():
    p=root/f
    if not p.is_file():errors.append('missing '+f);continue
    data=p.read_bytes()
    if hashlib.sha256(data).hexdigest()==h:continue
    s=data.decode()
    if f==identity:
        s=s.replace(str(root),'/mpac/sdicks02/repos/clasher').replace('[[ -f '+str(b/'jobs/source-verified.json')+' ]]','[[ -f /mpac/sdicks02/jobs/clasher/transfer-ready.json ]]').replace(str(b/'jobs'),'/mpac/sdicks02/jobs/clasher')
    elif f==p16:
        s=s.replace('Path('+repr(str(b/'data/decoded-logic-1e505767/projectiles.csv'))+')','Path.home() / ".cache/clasher-native-reference/decoded-logic-1e505767/projectiles.csv"')
    if hashlib.sha256(s.encode()).hexdigest()!=h:errors.append('unexpected source change '+f)
    else:adapted.append(f)
links=[]
for here,dirs,names in os.walk(b):
    for name in dirs+names:
        p=Path(here)/name
        if p.is_symlink():
            resolved=str(p.resolve())
            if not resolved.startswith(str(b)+'/'):
                links.append({'path':str(p),'target':resolved})
                # Normal OS symlinks are allowed; no shared user or owner dependency.
                if resolved.startswith('/mpac/sdicks02/') or resolved.startswith('/home/'):
                    errors.append('external user path '+str(p)+' -> '+resolved)
versions={}
for name,exe in [('gpu',b/'envs/clasher-gpu/bin/python'),('cpu',root/'.venv/bin/python')]:
    if exe.exists():
        versions[name]=subprocess.check_output([str(exe),'-B','-c','import sys,platform;print(platform.python_version());print(sys.executable)'],text=True).strip()
        if not versions[name].startswith('3.12.13\n'):errors.append(name+' Python version')
catalog=b/'data/decoded-logic-1e505767/projectiles.csv'
if hashlib.sha256(catalog.read_bytes()).hexdigest() != 'c59ef74273b721b861e6a499bc8869a6fc29ad07919884b79ebe859455d6eac5':errors.append('projectile catalog checksum')
# The unchanged P16 checker itself enforces the catalog's declared SHA.
r={'host':host,'status':'pass' if not errors else 'fail','source_files':len(pins),'environment_only_adapted_files':adapted,'external_symlinks':links,'python':versions,'errors':errors}
p=b/'jobs/final-audit.json';p.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));raise SystemExit(bool(errors))
