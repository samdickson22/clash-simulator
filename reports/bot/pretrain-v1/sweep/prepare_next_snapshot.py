"""Freeze 83 sealed batches, build only new shards, verify and publish a separate 08 store."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

CODE = Path(__file__).resolve().parents[4]
SRC = Path('/mpac/sdicks02/datasets/native-redrive-20261021')
OLD = Path('/mpac/sdicks02/datasets/pretrain-v1/f-ce6e509ee43a-b-1005dbb4')
ROOT = OLD.parent/'snapshot-20261022-b083'
ART = Path('/mpac/sdicks02/scratch/pretrain-v1-dev/followup-20261022')
JOBS = '/mpac/sdicks02/scratch/native-redrive-full-20261021/jobs'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    assert os.uname().nodename.split('.')[0] == '127x05'
    ROOT.mkdir(parents=True, exist_ok=True); ART.mkdir(parents=True, exist_ok=True)
    lock = (ROOT/'build.lock').open('a'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    (ROOT/'owner.json').write_text(json.dumps(dict(pid=os.getpid(), started=time.time(), code=str(CODE)))+'\n')
    frozen = ROOT/'input.json'
    if frozen.exists():
        inputs = json.loads(frozen.read_text())
    else:
        acked = [b for b in (SRC/'acked.txt').read_text().split()
                 if (SRC/'receipts'/f'batch-{b}.json').exists()][:83]
        assert len(acked) == len(set(acked)) == 83
        inputs = {b: sha(SRC/'receipts'/f'batch-{b}.json') for b in acked}
        frozen.write_text(json.dumps(inputs, indent=1)+'\n')
    assert len(inputs) == 83
    source = ROOT/'frozen-input'; (source/'receipts').mkdir(parents=True, exist_ok=True)
    for b, digest in inputs.items():
        r = SRC/'receipts'/f'batch-{b}.json'; assert sha(r) == digest
        p = source/'receipts'/r.name
        if not p.exists(): shutil.copy2(r, p)
        assert sha(p) == digest
    (source/'acked.txt').write_text('\n'.join(inputs)+'\n')
    if not (source/'out').exists(): (source/'out').symlink_to(SRC/'out', target_is_directory=True)
    assert sha(CODE/'bot/pretrain_v1/dataset.py').startswith('1005dbb4')
    store = ROOT/OLD.name
    if not store.exists():
        assert {p.name for p in (OLD/'shards').iterdir()} <= set(inputs)
        # Only immutable shards share inodes. The growing manifest is a separate ordinary copy.
        shutil.copytree(OLD/'shards', store/'shards', copy_function=os.link)
        shutil.copy2(OLD/'MANIFEST.jsonl', store/'MANIFEST.jsonl')
    subprocess.run([sys.executable, '-B', '-m', 'bot.pretrain_v1.dataset', 'build', '--src', str(source),
                    '--jobs', JOBS, '--out', str(ROOT), '--workers', '8'], cwd=CODE, check=True)
    manifest = [json.loads(l) for l in (store/'MANIFEST.jsonl').read_text().splitlines()]
    assert len(manifest) == len({r['batch'] for r in manifest}) == 83
    assert {r['batch'] for r in manifest} == set(inputs)
    files = {str(p.relative_to(ROOT)): sha(p) for p in store.rglob('*') if p.is_file()}
    for p in (store/'shards').glob('*/meta.json'):
        d = json.loads(p.read_text())
        assert all(sha(p.parent/f'{n}.npy') == digest for n, digest in d['files'].items())
    ready = dict(store_name=store.name, batches=83, rows=sum(r['rows'] for r in manifest),
                 matches=sum(r['matches'] for r in manifest), manifest_sha256=sha(store/'MANIFEST.jsonl'),
                 input_sha256=sha(frozen), files=files)
    (ROOT/'built.json').write_text(json.dumps(ready, indent=1)+'\n')
    # The ready gate is written remotely only after every transferred file has matched its frozen digest.
    subprocess.run(['timeout', '60', 'ssh', '-o', 'BatchMode=yes', '127x08', 'mkdir', '-p', str(ROOT)], check=True)
    subprocess.run(['timeout', '3600', 'rsync', '-a', str(store), '127x08:'+str(ROOT)+'/'], check=True)
    verifier = """import hashlib,json,pathlib,sys
root=pathlib.Path(sys.argv[1]); d=json.load(sys.stdin)
for n,h in d['files'].items():
 assert hashlib.sha256((root/n).read_bytes()).hexdigest()==h, n
p=root/'STORE-READY.json'; raw=json.dumps(d,sort_keys=True)+'\\n'
if p.exists(): assert json.loads(p.read_text())==d, 'another snapshot is already ready'
else:
 with p.open('x') as f: f.write(raw)
print('READY',d['batches'],d['matches'],d['rows'])
"""
    import shlex
    cmd = '/mpac/sdicks02/repos/clasher-bot-gpu/venv/bin/python -B -c '+shlex.quote(verifier)+' '+shlex.quote(str(ROOT))
    subprocess.run(['timeout', '300', 'ssh', '-o', 'BatchMode=yes', '127x08', cmd],
                   input=json.dumps(ready), text=True, check=True)
    (ROOT/'STORE-READY.json').write_text(json.dumps(ready, indent=1)+'\n')
    print('NEXT SNAPSHOT READY', ready['matches'], ready['rows'], flush=True)


if __name__ == '__main__':
    main()
