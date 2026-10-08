"""Re-score exact eligible v2 P16 perspectives with unchanged T3 scorer.

Embargo applies; this entry point is CPU-only on the hub. It does not fit.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing as mp
from pathlib import Path
import socket
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
IM=ROOT/'reports/strategy_council_20260928/imitation'
sys.path.insert(0,str(IM))
from baselines import p16_partition,Metrics
from replay_sidecars import sha,write


def main():
    p=argparse.ArgumentParser();p.add_argument('--store',type=Path,required=True);p.add_argument('--release',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--workers',type=int,default=4);a=p.parse_args();assert socket.gethostname()=='127x01' and 1<=a.workers<=8
    release=json.loads(a.release.read_text());m=json.loads(a.manifest.read_text())
    assert release['manifest_sha256']==sha(a.manifest)
    assert sha(release['v1_report'])==release['v1_report_sha256']
    assert sha(a.store/'manifest.json')==m['store_manifest_sha256']
    assert set(release['runs'])=={'main-2026100821','main-2026100822'}
    for name,h in m['p16_sources'].items():assert sha(ROOT/name)==h,name
    assert sha(IM.parent/'human-prior-p16/checkpoints/human-bc-natural-seed2903.pt')==m['p16_checkpoint_sha256']
    a.out.mkdir(parents=True,exist_ok=True)
    for role in ('eval','eval_ood'):
        path=a.out/f'p16-{role}.json'
        if path.exists():
            assert json.loads(path.read_text())['release_sha256']==sha(a.release);continue
        rolemeta=json.loads((a.store/role/'manifest.json').read_text())
        scoped=[x for x in rolemeta['perspectives'] if x['p16']]
        assert all(x['corpus']=='c56' for x in scoped)
        identities=sorted(x['identity'] for x in scoped);metrics=Metrics();n=0;checkpoint=None;upgrade=None;start=time.monotonic()
        if scoped:
            with ProcessPoolExecutor(a.workers,mp_context=mp.get_context('spawn')) as pool:
                for partial,count,digest,adaptation in pool.map(p16_partition,[(a.store,role,'cpu',i,a.workers) for i in range(a.workers)]):
                    for k,v in partial.sums.items():metrics.sums[k]+=v
                    for k in ('distances','prob','truth','playable'):getattr(metrics,k).extend(getattr(partial,k))
                    if checkpoint is not None:assert checkpoint==digest and upgrade==adaptation
                    checkpoint=digest;upgrade=adaptation;n+=count
        assert n==len(scoped)
        write(path,dict(role=role,corpus='c56',perspectives=n,identities=identities,
                        identity_sha256=hashlib.sha256(json.dumps(identities,separators=(',',':')).encode()).hexdigest(),
                        metrics=metrics.result() if n else None,checkpoint_sha256=checkpoint,upgrade=upgrade,
                        store_manifest_sha256=m['store_manifest_sha256'],release_sha256=sha(a.release),
                        sources=m['p16_sources'],workers=a.workers,wall_seconds=time.monotonic()-start))


if __name__=='__main__':main()
