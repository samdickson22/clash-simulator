import hashlib,json,os,shutil,socket,time
from pathlib import Path
HERE=Path('/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/search-noise-v2')
INC=HERE/'operations/incident-seal-overwrite-r2b'
FROZEN=INC/'frozen-r2'
SHA='3ad63c0a7ad1634bac32bf5b031a7a312013497d8863aeaa3b0e2b0e077e5677'
host=socket.gethostname().split('.')[0]
assert host in ('127x01','127x04','127x08')
raw=(FROZEN/'evaluation-manifest.json').read_bytes() if host!='127x08' else (HERE/'evaluation-manifest.json').read_bytes()
assert hashlib.sha256(raw).hexdigest()==SHA
files=json.loads(raw)['files']; assert len(files)==468
expected=dict(files,**{'evaluation-manifest.json':SHA})
backup=INC/f'overwritten-{host}-recovery-{time.time_ns()}'
changes=[]
for rel,want in expected.items():
    dst=HERE/rel
    old=hashlib.sha256(dst.read_bytes()).hexdigest() if dst.exists() else None
    if old==want: continue
    assert host!='127x08', ('intact host drift',rel)
    src=FROZEN/rel; assert hashlib.sha256(src.read_bytes()).hexdigest()==want
    if dst.exists():
        saved=backup/rel; saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dst,saved)
    dst.parent.mkdir(parents=True,exist_ok=True)
    tmp=dst.with_name(dst.name+'.restore-r2e.tmp');shutil.copyfile(src,tmp);os.replace(tmp,dst)
    changes.append(dict(path=rel,before=old,after=want))
audit={rel:hashlib.sha256((HERE/rel).read_bytes()).hexdigest() for rel in expected}
assert audit==expected
out=dict(utc=time.time(),host=host,manifest=SHA,sealed_files_verified=468,manifest_verified=True,changes=changes,backup=str(backup),hashes=audit)
(HERE/f'operations/restoration-audit-{host}-r2e.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k not in ('hashes','changes')},sort_keys=True));print('replaced',len(changes))
