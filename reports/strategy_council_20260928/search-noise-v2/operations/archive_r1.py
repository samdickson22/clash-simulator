"""Preserve the surviving r1 study without opening outcome fields."""
from pathlib import Path
import hashlib, json, shutil, socket, time
root = Path('/mpac/sdicks02/repos/clasher')
study = root/'reports/strategy_council_20260928/search-noise-v2'
host = socket.gethostname().split('.')[0]
assert host in ('127x01','127x04','127x07','127x08','127x05')
expected = '253aba47a826e6dbb2d951114d0f7596b0d45bd3eee294d65e6c032c0513c849'
manifest = study/'evaluation-manifest.json'
assert hashlib.sha256(manifest.read_bytes()).hexdigest() == expected
archive = study/'r1-archive'/host
assert not archive.exists(), 'archive already exists; inspect rather than overwrite'
archive.mkdir(parents=True)
move_names = {'runtime','evaluation-manifest.json','preflight.json','source-copies.json',
              'source-copies-linux.json','replay-tests','confirmation','collected-status',
              'interrupted','monitor.json','RESULTS.md','result.json','frozen-files.txt'}
moved=[];copied=[]
for path in list(study.iterdir()):
    name=path.name
    if name=='r1-archive': continue
    move = name in move_names or name.startswith(('pilot-','worker-','launch-'))
    if move:
        shutil.move(str(path),str(archive/name));moved.append(name)
    elif path.is_file() and path.suffix in ('.py','.md','.json','.txt'):
        shutil.copy2(path,archive/name);copied.append(name)
    elif name=='operations':
        shutil.copytree(path,archive/name);copied.append(name)
jobs = Path('/mpac/sdicks02/jobs/clasher')
if host != '127x05':
    for path in jobs.glob('s1-*'):
        if path.is_file() and path.suffix in ('.log','.exit','.pid'):
            target=archive/'jobs'/path.name;target.parent.mkdir(exist_ok=True)
            shutil.copy2(path,target)
receipt=dict(host=host,utc=time.time(),r1_manifest=expected,moved=moved,copied=copied,
             confirmation_outcomes_inspected=False)
(study/'operations').mkdir(exist_ok=True)
(study/'operations'/f'r1-archive-{host}.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
