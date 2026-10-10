import argparse,json,os,resource,subprocess,time
from pathlib import Path
import numpy as np
from regret_admission import allowed,frozen,validate_seal
from admission import sha
from journal import record
from imitation.exit_r1.rows import write_json
def regret(j):
    from metrics import intervals
    allrows=[];proof=[]
    for i in range(64):
        p=j/'regret/games'/f'{i:04d}.json';r=json.loads(p.read_text());data=p.with_suffix('.jsonl');assert r['complete'] and r['command_exact'] and r['jsonl_sha256']==sha(data);validate_seal(j,p,r)
        for arm,want in r['proposals_sha256'].items():assert sha(j/'offline'/f'{arm}-proposals.npz')==want
        rows=[json.loads(l) for l in data.read_text().splitlines()];assert len(rows)==r['roots'] and all(v['seed']==4503601207370496+i for v in rows)
        allrows.extend(rows);proof.append(dict(index=i,sha256=sha(p),jsonl_sha256=sha(data)))
    assert len(allrows)==8088 and len({r['row'] for r in allrows})==8088
    games=np.array([r['seed'] for r in allrows]);plays=np.array([r['teacher_play'] for r in allrows]);out={}
    for arm in ('R3c','R3d','R3e'):
        positive=np.array([r[arm]['positive_regret'] for r in allrows]);signed=np.array([r[arm]['signed_regret'] for r in allrows]);m=dict(mean_positive=intervals(games,positive,np.ones(len(games))),mean_signed=intervals(games,signed,np.ones(len(games))),mean_positive_on_teacher_plays=intervals(games,positive*plays,plays.astype(float)),percentiles={str(p):float(np.quantile(positive,p)) for p in (.5,.9,.95,.99,1.)})
        p=j/'offline'/f'{arm}.json';r=json.loads(p.read_text());r.update(regret=m,stage1_complete=True)
        if m['mean_positive']['value']>.01:r['kill_reasons'].append('mean positive W-score regret >.010')
        r['survives']=not r['kill_reasons'];r['regret_game_proofs']=proof;r['regret_definition']='Best fully completed score among recorded W candidates versus best of legal studenttop8+WAIT/WAIT10, all on the same fresh reconstructed root; all64 command-exact replayed games.'
        write_json(p,r);out[arm]=r
    write_json(j/'stage1-results.json',out)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);a=p.parse_args();j=Path(a.job)
    assert allowed(j) and os.sched_getaffinity(0)=={58};frozen(j);assert not (j/'stage1-results.json').exists(),'reduction already sealed'
    record(j,'stage1_reducer');t=time.monotonic();status='failed'
    try:regret(j);status='complete'
    finally:
        u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN);write_json(j/f'stage1-reduction-meter-{os.getpid()}.json',dict(status=status,pid=os.getpid(),pgid=os.getpgrp(),parent_cpu_seconds=u.ru_utime+u.ru_stime,children_cpu_seconds=v.ru_utime+v.ru_stime,wall_seconds=time.monotonic()-t))
