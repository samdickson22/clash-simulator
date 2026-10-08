"""Real TRAIN-only smoke for the exact production P16 scorer and spawn transport."""
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing
import time
from baselines import p16_partition
from replay_sidecars import HERE, write, sha


def main():
    started=time.perf_counter()
    plan=json.loads((HERE/'data/store-smoke-v2/plan.json').read_text())
    unit=plan['units'][0]
    selected=next(p for p in unit['perspectives'] if p['role']=='train' and p['p16'])
    out=HERE/'data/p16-partition-smoke-v1'
    write(out/'plan.json',dict(units=[dict(unit,perspectives=[selected])]))
    with ProcessPoolExecutor(1,mp_context=multiprocessing.get_context('spawn')) as pool:
        metric,count,digest,upgrade=pool.submit(p16_partition,(out,'train','cpu',0,1)).result()
    result=metric.result()
    assert count==1 and 0<result['playable_rows']<=result['rows']<=selected['rows']
    assert result['joint_nll']>=0 and result['play_wait_nll_playable']>=0
    write(HERE/'data/receipts/t3-p16-partition-smoke.json',dict(passed=True,role='train',identity=selected['identity'],
          perspectives=count,rows=result['rows'],playable_rows=result['playable_rows'],checkpoint_sha256=digest,
          upgrade=upgrade,scorer_sha256=sha(HERE/'baselines.py'),wall_seconds=time.perf_counter()-started))


if __name__=='__main__':main()
