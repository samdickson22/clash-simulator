"""Deterministic indexed partition, atomic terminal receipts, fail-closed resume."""
import bootstrap
from bootstrap import HERE
import argparse,fcntl,gc,hashlib,json,os,time
from pathlib import Path
from evaluate import game,write,verify,Resources
from cells import CELLS,H2H

def jobs(schedule):
    return [(ep,cell,seat) for ep in schedule['pairs'] for cell in (CELLS if ep['mode']=='scripts' else H2H) for seat in (0,1)]

def main(argv=None, resources=None):
    ap=argparse.ArgumentParser();ap.add_argument('--index',type=int,required=True);ap.add_argument('--workers',type=int,required=True)
    ap.add_argument('--pilot',action='store_true');ap.add_argument('--max-tick',type=int);args=ap.parse_args(argv)
    lock=(HERE/f'worker-{args.index}.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    r=resources or Resources();prior=json.loads((HERE/'runtime/support/human_deck_catalog.json').read_text())
    if not hasattr(r,'initial_belief'):
        from derived_public_state import DerivedPublicState
        r.initial_belief=DerivedPublicState(prior,r.costs)
    if args.pilot:
        deck=['HogRider','Musketeer','IceGolem','IceSpirit','Skeletons','Cannon','Fireball','Log']
        ep=dict(pair=-1,seed=7610800001,noise_seed=7610900001,planning_deck=deck,opponent_deck=deck[::-1],mode='scripts',family='Hog 2.6',style='balanced')
        cell=list(CELLS)[args.index%len(CELLS)]
        row=game(r,prior,ep,args.index%2,cell,max_tick=args.max_tick)
        # Timing pilot intentionally does not retain or print outcomes.
        safe={k:row[k] for k in ('variant','terminal','ticks','elapsed','cpu_seconds','timing','host','perception','action_sha256')}
        write(HERE/f'pilot-{args.index}-{args.max_tick or "full"}.json',safe);print(json.dumps(safe),flush=True);return
    manifest=json.loads((HERE/'evaluation-manifest.json').read_text());verify(manifest)
    sha=hashlib.sha256((HERE/'evaluation-manifest.json').read_bytes()).hexdigest()
    schedule=json.loads((HERE/'schedule.json').read_text());folder=HERE/'confirmation';folder.mkdir(exist_ok=True)
    current=HERE/f'worker-{args.index}-current.json'
    if current.exists():
        previous=json.loads(current.read_text())
        if not (folder/f'{previous["job"]:05d}.json').exists():
            archive=HERE/'interrupted';archive.mkdir(exist_ok=True)
            __import__('shutil').copyfile(current,archive/f'worker-{args.index}-{time.time_ns()}.json')
    for index,(ep,cell,seat) in enumerate(jobs(schedule)):
        if index%args.workers!=args.index:continue
        path=folder/f'{index:05d}.json'
        if path.exists():
            old=json.loads(path.read_text())
            assert old['manifest']==sha and old['terminal'] and old['job']==index
            assert old['seed']==ep['seed'] and old['noise_seed']==ep['noise_seed']
            assert old['variant']==cell and old['seat']==seat and old['mode']==ep['mode']
            continue
        verify(manifest)
        write(HERE/f'worker-{args.index}-current.json',dict(job=index,started=time.time(),pid=os.getpid()))
        row=game(r,prior,ep,seat,cell)
        assert row['terminal']
        row.update(manifest=sha,job=index);write(path,row)
        print(json.dumps(dict(job=index,terminal=True,elapsed=row['elapsed'],cpu_seconds=row['cpu_seconds'])),flush=True)
        gc.collect()
    verify(manifest)
    write(HERE/f'worker-{args.index}-done.json',dict(complete=True,manifest=sha,finished=time.time()))

if __name__=='__main__':main()
