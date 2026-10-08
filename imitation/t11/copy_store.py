"""Lease-supervised receiver; checksum every explicit store/source artifact."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shlex
import signal
import socket
import subprocess
import time

BASE=Path('/mpac/sdicks02/repos/clasher-lease')
HUB=Path('/mpac/sdicks02/repos/clasher')
DATA=HUB/'reports/strategy_council_20260928/imitation/data'
WORK=BASE/'t11-20261008-v1'
child=None


def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()


def run(argv):
    global child
    child=subprocess.Popen([str(x) for x in argv],stdout=subprocess.PIPE,text=True)
    result,_=child.communicate();code=child.returncode;child=None
    if code:raise subprocess.CalledProcessError(code,argv,result)
    return result


def stop(signum,frame):
    if child is not None and child.poll() is None:
        child.terminate()
        try:child.wait(timeout=20)
        except subprocess.TimeoutExpired:child.kill();child.wait()
    raise SystemExit(128+signum)


def lease():
    host=socket.gethostname().split('.')[0];assert host in ('127x16','127x18','127x09','127x15')
    l=json.loads(Path('/mpac/sdicks02/fleet-leases',host+'.json').read_text())
    assert l['project']=='clasher' and l['gpu'] and not l.get('refused') and not l.get('reclaim')
    now=datetime.now(timezone.utc)
    assert datetime.fromisoformat(l['expected_end_utc'].replace('Z','+00:00'))>now
    assert now<datetime.fromisoformat('2026-10-09T04:20:00+00:00')
    return host,l


def sync_files(source,dest,names,label):
    listing=WORK/(label+'-files.txt');listing.write_text('\n'.join(names)+'\n')
    Path(dest).mkdir(parents=True,exist_ok=True)
    run(['rsync','-cr','--partial','--files-from='+str(listing),'127x01:'+str(source)+'/',str(dest)+'/'])


def main():
    started=time.monotonic();host,l=lease();WORK.mkdir(parents=True,exist_ok=True)
    ready=json.loads(run(['ssh','127x01','cat',f'/mpac/sdicks02/jobs/clasher/lease-ready-{host}.json']))
    assert ready['qualified']
    sync_files(DATA/'receipts',WORK/'inputs',['T11-STORE-PASS.json'],'release')
    receipt=json.loads((WORK/'inputs/T11-STORE-PASS.json').read_text());assert receipt['passed'] and receipt['roundtrip_exact']
    target=BASE/'data/v2-store-v1'
    names=['manifest.json','plan.json','mask_table.npy']+[r+'/manifest.json' for r in ('train','dev','eval','eval_ood')]
    sync_files(DATA/'v2-store-v1',target,names,'metadata')
    assert sha(target/'manifest.json')==receipt['store_manifest_sha256']
    manifest=json.loads((target/'manifest.json').read_text());assert manifest['production'] and manifest['roles']==receipt['roles']
    assert sha(target/'plan.json')==manifest['plan_sha256'] and sha(target/'mask_table.npy')==manifest['mask_table_sha256']
    expected={'manifest.json':receipt['store_manifest_sha256'],'plan.json':manifest['plan_sha256'],'mask_table.npy':manifest['mask_table_sha256']}
    for role,h in manifest['role_manifests'].items():
        assert role in ('train','dev','eval','eval_ood') and sha(target/role/'manifest.json')==h
        expected[role+'/manifest.json']=h
        roledata=json.loads((target/role/'manifest.json').read_text())
        for n,v in roledata['arrays'].items():
            assert n and '/' not in n and n not in ('.','..')
            expected[role+'/'+n+'.npy']=v['sha256']
    sync_files(DATA/'v2-store-v1',target,sorted(expected),'store')
    byte_count=0
    for i,(n,h) in enumerate(expected.items()):
        assert sha(target/n)==h,n;byte_count+=(target/n).stat().st_size
        if i%20==0:print(json.dumps({'stage':'checksum','files':i,'of':len(expected)}),flush=True)
    lease()
    sync_files(HUB/'imitation/gate-a-v2',WORK/'source/imitation/gate-a-v2',
               ['PREREG.md','executable-manifest.json','freeze.json'],'prereg')
    freeze=WORK/'source/imitation/gate-a-v2';m=json.loads((freeze/'executable-manifest.json').read_text())
    f=json.loads((freeze/'freeze.json').read_text())
    assert sha(freeze/'executable-manifest.json')==f['manifest_sha256'] and sha(freeze/'PREREG.md')==f['prereg_sha256']
    assert sha(WORK/'inputs/T11-STORE-PASS.json')==m['store_receipt_sha256']
    sync_files(Path('/mpac/sdicks02/jobs/clasher/t11-20261008-v1/source'),WORK/'source',
               sorted(m['files'])+['imitation/model/receipts/throughput-pass.json'],'source')
    assert all(sha(WORK/'source'/n)==h for n,h in m['files'].items())
    sync_files(Path('/mpac/sdicks02/jobs/clasher/t11-20261008-v1/inputs'),WORK/'inputs',['assets.npz','assets.npz.json'],'assets')
    assert sha(WORK/'inputs/assets.npz')==m['assets_sha256']
    lease()
    result=dict(passed=True,host=host,finished_at=datetime.now(timezone.utc).isoformat(),files=len(expected),bytes=byte_count,
                store_manifest_sha256=receipt['store_manifest_sha256'],store_receipt_sha256=sha(WORK/'inputs/T11-STORE-PASS.json'),
                manifest_sha256=f['manifest_sha256'],prereg_sha256=f['prereg_sha256'],all_sha256_equal=True,
                total_wall_seconds=time.monotonic()-started,eval_scored=False)
    (WORK/'copy-receipt.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)


if __name__=='__main__':
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop);main()
