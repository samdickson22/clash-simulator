"""Freeze 240 sealed batches, build only new shards, verify and publish a separate 08 store."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import interim_pins as pins

CODE = Path(__file__).resolve().parents[4]
SRC = Path('/mpac/sdicks02/datasets/native-redrive-20261021')
OLD = Path('/mpac/sdicks02/datasets/pretrain-v1/snapshot-20261022-b083/f-ce6e509ee43a-b-1005dbb4')
ROOT = Path('/mpac/sdicks02/datasets/pretrain-v1/05/interim-20261022-b240')
ART = Path('/mpac/sdicks02/jobs/clasher/pretrain-v1/interim-20261022-b240')
JOBS = '/mpac/sdicks02/scratch/native-redrive-full-20261021/jobs'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    pins.verify(CODE)
    assert os.uname().nodename.split('.')[0] == '127x05'
    ROOT.mkdir(parents=True, exist_ok=True); ART.mkdir(parents=True, exist_ok=True)
    lock = (ROOT/'build.lock').open('a'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    (ROOT/'owner.json').write_text(json.dumps(dict(pid=os.getpid(), started=time.time(), code=str(CODE)))+'\n')
    frozen = ROOT/'input.json'
    assert sha(frozen) == '2422eb7321982a60b14f5152d3a4338f456294d1cd249b6cbb973de834c765c2'
    inputs = json.loads(frozen.read_text())
    assert len(inputs) == 240
    jobs_pin = ROOT/'jobs-input.json'
    assert sha(jobs_pin) == '2b0cebed9a2988690dc1fd6545c1dd43e745d1e5896b3af2f4f9c175ed5291e9'
    jobs_input = json.loads(jobs_pin.read_text())
    for shard, digest in jobs_input.items():
        assert sha(Path(JOBS)/(shard+'.jsonl.gz')) == digest
    reused = json.loads((OLD.parent/'input.json').read_text())
    assert len(reused) == 83 and all(inputs.get(b) == h for b, h in reused.items())
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
        old_ready = json.loads((OLD.parent/'STORE-READY.json').read_text())
        assert sha(OLD/'MANIFEST.jsonl') == old_ready['manifest_sha256']
        for name, digest in old_ready['files'].items():
            assert sha(OLD.parent/name) == digest, name
        assert {p.name for p in (OLD/'shards').iterdir()} <= set(inputs)
        # Only immutable shards share inodes. The growing manifest is a separate ordinary copy.
        shutil.copytree(OLD/'shards', store/'shards', copy_function=os.link)
        shutil.copy2(OLD/'MANIFEST.jsonl', store/'MANIFEST.jsonl')
    pins.verify(CODE)
    assert pins.host_ok(60, 60), 'build admission needs >=60 GiB and load <60'
    subprocess.run([sys.executable, '-B', '-m', 'bot.pretrain_v1.dataset', 'build', '--src', str(source),
                    '--jobs', JOBS, '--out', str(ROOT), '--workers', '24'], cwd=CODE, check=True)
    manifest = [json.loads(l) for l in (store/'MANIFEST.jsonl').read_text().splitlines()]
    assert len(manifest) == len({r['batch'] for r in manifest}) == 240
    assert {r['batch'] for r in manifest} == set(inputs)
    assert not any(json.loads((store/'shards'/r['batch']/'meta.json').read_text())['stats'].get(k, 0) for r in manifest for k in
                   ['match_missing_file', 'match_sha_mismatch', 'match_no_job', 'persp_exception'])
    assert {p.name for p in (store/'shards').iterdir() if p.is_dir() and not p.name.startswith('.')} == set(inputs)
    files = {str(p.relative_to(ROOT)): sha(p) for p in store.rglob('*') if p.is_file()}
    for p in (store/'shards').glob('*/meta.json'):
        d = json.loads(p.read_text())
        assert all(sha(p.parent/f'{n}.npy') == digest for n, digest in d['files'].items())
    ready = dict(store_name=store.name, batches=240, rows=sum(r['rows'] for r in manifest),
                 matches=sum(r['matches'] for r in manifest), manifest_sha256=sha(store/'MANIFEST.jsonl'),
                 input_sha256=sha(frozen), jobs_input_sha256=sha(jobs_pin), files=files)
    (ROOT/'built.json').write_text(json.dumps(ready, indent=1)+'\n')
    # The ready gate is written remotely only after every transferred file has matched its frozen digest.
    subprocess.run(['timeout', '60', 'ssh', '-o', 'BatchMode=yes', '127x08', 'mkdir', '-p', str(ROOT)], check=True)
    subprocess.run(['timeout', '3600', 'rsync', '-a', str(store), '127x08:'+str(ROOT)+'/'], check=True)
    verifier = """import hashlib,json,pathlib,sys,os
root=pathlib.Path(sys.argv[1]); d=json.load(sys.stdin)
store=root/d['store_name']
expected={json.loads(l)['batch'] for l in (store/'MANIFEST.jsonl').read_text().splitlines()}
assert {p.name for p in (store/'shards').iterdir() if p.is_dir() and not p.name.startswith('.')} == expected, 'unexpected remote shards'
for n,h in d['files'].items():
 assert hashlib.sha256((root/n).read_bytes()).hexdigest()==h, n
p=root/'STORE-READY.json'; raw=json.dumps(d,sort_keys=True)+'\\n'
if p.exists(): assert json.loads(p.read_text())==d, 'another snapshot is already ready'
else:
 tmp=p.with_name(p.name+'.tmp-'+str(os.getpid()))
 with tmp.open('x') as f: f.write(raw)
 try: os.link(tmp,p)
 except FileExistsError: assert json.loads(p.read_text())==d, 'another snapshot is already ready'
 finally: tmp.unlink()
print('READY',d['batches'],d['matches'],d['rows'])
"""
    import shlex
    cmd = '/mpac/sdicks02/repos/clasher-bot-gpu/venv/bin/python -B -c '+shlex.quote(verifier)+' '+shlex.quote(str(ROOT))
    subprocess.run(['timeout', '300', 'ssh', '-o', 'BatchMode=yes', '127x08', cmd],
                   input=json.dumps(ready), text=True, check=True)
    tmp = ROOT/f'.STORE-READY-{os.getpid()}.tmp'
    tmp.write_text(json.dumps(ready, indent=1)+'\n')
    try:
        os.link(tmp, ROOT/'STORE-READY.json')
    except FileExistsError:
        assert json.loads((ROOT/'STORE-READY.json').read_text()) == ready
    finally:
        tmp.unlink()
    print('NEXT SNAPSHOT READY', ready['matches'], ready['rows'], flush=True)


if __name__ == '__main__':
    main()
