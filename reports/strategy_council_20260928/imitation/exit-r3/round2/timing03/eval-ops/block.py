"""Complete same-seed paired rotated block; never retain a partial block."""
import argparse,json,os,signal,subprocess,sys,time
from pathlib import Path
from admission import allowed,context,sha
from protocol import BASES,order,stage,arm_list
from journal import record
from imitation.exit_r1.rows import write_json
def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--lane',required=True);p.add_argument('--index',type=int,required=True);p.add_argument('--smoke',action='store_true');a=p.parse_args();j=Path(a.job)
    assert allowed(j) and len(os.sched_getaffinity(0))==1
    arms=arm_list(a.lane,json.loads((j/'stage1-results.json').read_text()) if a.lane=='stage2' else None);assert len(arms)>1
    record(j,'block',lane=a.lane,index=a.index,smoke=a.smoke)
    folder=j/stage(a.lane,a.smoke);(folder/'blocks').mkdir(parents=True,exist_ok=True);(folder/'logs').mkdir(exist_ok=True)
    identity=folder/'blocks'/f'{a.index:04d}-attempt-{os.getpid()}.json';archive=folder/'abandoned'/f'{a.index:04d}-before-{os.getpid()}'
    for arm in arms:
        old=folder/'cases'/f'fallback-{arm}-{a.index:04d}.json'
        if old.exists():archive.mkdir(parents=True,exist_ok=True);old.rename(archive/old.name)
    v=dict(parent_pid=os.getpid(),context=context(),lane=a.lane,index=a.index,smoke=a.smoke,arms=arms,arm_order=order(arms,a.index),cases=[],complete=False,evaluation_freeze_sha256=sha(j/'evaluation-freeze.json'));write_json(identity,v)
    stopping=False;child=None
    def stop(*args):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:
        for arm in v['arm_order']:
            assert not stopping and allowed(j)
            cmd=[sys.executable,'-B',str(j/'eval-ops/game.py'),'--job',str(j),'--lane',a.lane,'--arm',arm,'--index',str(a.index),'--block',str(identity)]
            if a.smoke:cmd+=['--smoke']
            with (folder/'logs'/f'{arm}-{a.index:04d}-attempt-{os.getpid()}.log').open('w') as log:
                child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
                while child.poll() is None:
                    if stopping or not allowed(j):raise InterruptedError('admission changed; abandon entire paired block')
                    time.sleep(2)
                assert child.returncode==0,'case failed; manual review required';child=None
            case=folder/'cases'/f'fallback-{arm}-{a.index:04d}.json';r=json.loads(case.read_text())
            assert r['terminal'] and r['seed']==BASES[a.lane][int(a.smoke)]+a.index
            v['cases'].append(dict(arm=arm,sha256=sha(case)));write_json(identity,v)
    finally:
        if child is not None:
            child.terminate()
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.kill();child.wait()
    v['complete']=True;write_json(identity,v);write_json(folder/'blocks'/f'{a.index:04d}.json',v)
if __name__=='__main__':main()
