"""One complete same-seed rotating block; incomplete attempts entirely replayed."""
import argparse,json,os,signal,subprocess,sys,time
from pathlib import Path
from exit_r3.rows import sha,write_json
from admission import allowed,context

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--index',type=int,required=True);p.add_argument('--arms',nargs='+',required=True);p.add_argument('--smoke',action='store_true');a=p.parse_args();j=Path(a.job)
    assert allowed(j) and len(context()['affinity'])==1
    stage=j/('stage3-sdefault-smoke' if a.smoke else 'stage3-sdefault');blocks=stage/'blocks';blocks.mkdir(parents=True,exist_ok=True);(stage/'logs').mkdir(exist_ok=True)
    identity=blocks/f'{a.index:04d}-attempt-{os.getpid()}.json';order=a.arms[a.index%len(a.arms):]+a.arms[:a.index%len(a.arms)]
    archive=stage/'abandoned'/f'{a.index:04d}-before-{os.getpid()}'
    for arm in a.arms:
        for path in (stage/'cases'/f'sdefault-{arm}-{a.index:04d}.json',stage/'k-raw'/arm/'games'/f'sim-{a.index:04d}-d27-{arm}.json'):
            if path.exists():archive.mkdir(parents=True,exist_ok=True);path.rename(archive/f'{arm}-{path.name}')
    r=dict(parent_pid=os.getpid(),context=context(),index=a.index,smoke=a.smoke,arms=a.arms,arm_order=order,cases=[],complete=False,evaluation_freeze_sha256=sha(j/'evaluation-freeze.json'),utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip());write_json(identity,r)
    stopping=False;child=None
    def stop(*_):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:
        for arm in order:
            assert not stopping and allowed(j)
            command=[sys.executable,'-B',str(j/'eval-ops/game.py'),'--job',str(j),'--arm',arm,'--index',str(a.index),'--block',str(identity)]
            if a.smoke:command.append('--smoke')
            with (stage/'logs'/f'{arm}-{a.index:04d}-attempt-{os.getpid()}.log').open('w') as log:
                child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
                while child.poll() is None:
                    if stopping or not allowed(j):raise InterruptedError('admission changed; abandon complete block')
                    time.sleep(2)
                assert child.returncode==0,'case failure';child=None
            case=stage/'cases'/f'sdefault-{arm}-{a.index:04d}.json';record=json.loads(case.read_text());assert record['terminal'] and record['seed']==(4503601917370496 if a.smoke else 4503601907370496)+a.index
            r['cases'].append(dict(arm=arm,sha256=sha(case)));write_json(identity,r)
    finally:
        if child is not None:
            child.terminate()
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait()
    r['complete']=True;write_json(identity,r);write_json(blocks/f'{a.index:04d}.json',r)
if __name__=='__main__':main()
