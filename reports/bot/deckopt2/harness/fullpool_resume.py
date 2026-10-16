"""Orchestration-only recovery; original game, models, banks and rows stay frozen."""
import json,os,random,signal,subprocess,traceback
from pathlib import Path
import fullpool_worker as w
import fullpool_clean
fp=w.fp;D=w.DEST

def install():
    amendment=json.loads((D/'resume-manifest.json').read_text())
    assert amendment['bank_sha256']==fp.sha(D/'validation/bank.json')
    assert amendment['original_manifest_sha256']==fp.sha(D/'manifest.json')
    assert all(fp.sha(w.ROOT/name)==digest for name,digest in amendment['helper_sha256'].items())
    assert fp.sha(w.ROOT/'fullpool_worker.py')==amendment['unchanged_game_worker_sha256']
    assert json.loads((D/'vocab-combined.json').read_text())['no_counterpart_units']==['SpearGoblin_Dummy']
    w.work=work

def work(label,wid,meta,bank,rt,strong_rt,vocab):
    stopping=False
    def stop(signum,frame):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGUSR1,stop)
    worker=f'{os.uname().nodename}-{label}-{wid}'
    arms=[(candidate,player) for candidate in bank['candidates'] for player in bank['players']]
    completed=skipped=0
    while not stopping and not (D/f'PAUSE-{label}').exists():
        index=json.loads(w.remote([w.PY,w.ROOT/'fullpool_resume_queue.py','--worker',worker]))['index']
        if index is None:break
        case=bank['cases'][index];order=list(range(len(arms)));random.Random(case['seed']^0xA4A4).shuffle(order)
        block=dict(worker=worker,controller_label=label,worker_pid=os.getpid(),case_index=index,
                   arm_order=[arms[a] for a in order],cpu_slots=1,affinity=sorted(os.sched_getaffinity(0)),resume=True)
        fp.dump(D/f'active-{label}-{wid}.json',dict(utc=fp.utc(),**block))
        for position,arm in enumerate(order):
            candidate,player=arms[arm];output=D/'validation/rows'/f'{index*len(arms)+arm:06d}.json'
            if output.exists():
                row=json.loads(output.read_text())
                saved=json.loads((D/'resume-manifest.json').read_text())['preserved_rows']
                assert output.name in saved and fp.sha(output)==saved[output.name]
                assert row['id']==case['id'] and row['candidate']==candidate and row['player']==player
                assert row['bank_sha256']==fp.sha(D/'validation/bank.json') and row['host']==os.uname().nodename
                assert not fullpool_clean.problems(row),fullpool_clean.problems(row)
                skipped+=1;continue
            w.game(rt,strong_rt,vocab,meta,bank,case,candidate,player,output,dict(block,arm_position=position,game_pid=os.getpid()))
            row=json.loads(output.read_text())
            subprocess.run(['rsync','-a',str(output),f'127x05:{D}/validation/rows/'],check=True)
            if fullpool_clean.problems(row):
                w.remote(['touch',D/'STOP'])
                raise RuntimeError(('unclean game retained',str(output),fullpool_clean.problems(row)))
            completed+=1
        fp.dump(D/f'block-complete-{index:04d}.json',dict(utc=fp.utc(),**block))
    fp.dump(D/f'worker-complete-{label}-{wid}.json',dict(utc=fp.utc(),games=completed,preserved=skipped,stopping=stopping))
