"""Resumable fixed-index game pool. SIGTERM/SIGUSR1 drains all active games.

A route file assigns original job indices exclusively across hosts. Repartition
only after every previous controller and its children have drained. No bank,
seed, match algorithm, completed outcome or planner behavior changes.
"""
import argparse,json,os,signal,sys,time
from pathlib import Path
from types import SimpleNamespace
from bot.deckopt2 import run as h
import clean


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True)
    ap.add_argument('--stage',choices=['screen','validation'],required=True)
    ap.add_argument('--route',type=Path,required=True);ap.add_argument('--label',required=True)
    ap.add_argument('--workers',type=int,required=True)
    args=ap.parse_args();assert 1<=args.workers<=40
    root=args.root;out=root/args.stage;meta=json.loads((root/'manifest.json').read_text())
    data=json.loads((out/'bank.json').read_text());bank_sha=h.sha(out/'bank.json')
    assert data['manifest_sha256']==h.sha(root/'manifest.json'),'manifest differs from registered bank'
    assert meta['source_sha256']==h.source_hashes(),'source changed'
    route=json.loads(args.route.read_text());indices=route['routes'][args.label]
    assert len(indices)==len(set(indices))
    assignments=[i for ids in route['routes'].values() for i in ids]
    assert len(assignments)==len(set(assignments)),'overlapping routes'
    assert route['bank_sha256']==bank_sha
    for name,digest in meta.get('job_source_sha256',{}).items():
        assert h.sha(Path(__file__).with_name(name))==digest,('job helper changed',name)
    from bot.players.runtime import Runtime
    from bot.players.royalesim_vocab import load
    from bot.live.player import load_fast
    rt=Runtime()
    assert meta['pins']==json.loads(json.dumps(rt.pins))
    assert meta['simulator']==h.sim_identity()
    meta=dict(meta,own_levels=data['own_levels'],own_tower=data['own_tower'])
    if 'candidate_plans' in meta:
        import instrument
        instrument.install()
    h.install_compat(rt);vocab=load(rt);rt.STUDENT;load_fast(rt)
    import bot.players.royalesim_match as match
    original_match=match.play_match
    def with_refusals(*a,**kw):
        result=original_match(*a,**kw)
        result['rejected_commands']=[event for event in result.get('command_events',[]) if not event['ok']]
        return result
    match.play_match=with_refusals
    jobs=h.jobs_for(data);assert all(0<=i<len(jobs) for i in indices)
    launch=dict(started_utc=h.utc(),pid=os.getpid(),host=os.uname().nodename,
                label=args.label,workers=args.workers,jobs=len(indices),route_sha256=h.sha(args.route),
                bank_sha256=bank_sha,pool_source_sha256=h.sha(__file__),meta_sha256=h.sha(root/'manifest.json'))
    receipt=out/f'pool-{args.label}-{os.getpid()}.json';h.dump(receipt,launch,exclusive=True)
    active={};stopping=False;errors=[];resumed=completed=0
    def stop(signum,frame):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGUSR1,stop);signal.signal(signal.SIGINT,stop)
    def path(i):return out/'rows'/f'{i:06d}.json'
    def check(i):
        c,n,p=jobs[i];r=json.loads(path(i).read_text())
        assert (r['id'],r['candidate'],r['player'])==(c['id'],n,p)
        assert r['bank_sha256']==bank_sha
        assert not clean.problems(r),r
    def progress():
        h.dump(out/f'active-{args.label}.json',dict(updated_utc=h.utc(),pid=os.getpid(),label=args.label,
            stopping=stopping,active={str(p):i for p,i in active.items()},completed=completed,resumed=resumed,errors=errors))
    def reap():
        nonlocal completed,stopping
        pid,status=os.wait();i=active.pop(pid)
        try:
            assert status==0 and path(i).is_file(),('child exit',i,pid,status)
            check(i);completed+=1
        except Exception as ex:
            errors.append(dict(index=i,pid=pid,error=str(ex)));stopping=True
        progress()
    for i in indices:
        if path(i).is_file():
            check(i);resumed+=1;continue
        while len(active)>=args.workers and not stopping:reap()
        if stopping or (root/f'PAUSE-{args.label}').exists():stopping=True;break
        # A route is exclusive, but recheck after the bounded wait for clarity.
        if path(i).is_file():check(i);resumed+=1;continue
        c,n,p=jobs[i]
        pid=os.fork()
        if pid==0:
            signal.signal(signal.SIGTERM,signal.SIG_DFL);signal.signal(signal.SIGUSR1,signal.SIG_DFL)
            signal.signal(signal.SIGINT,signal.SIG_DFL)
            try:
                current=meta
                if 'candidate_plans' in meta:current=dict(meta,own_levels=meta['candidate_plans'][n]['levels'])
                h.game(rt,vocab,root,args.stage,current,c,n,p,path(i))
            finally:os._exit(0)
        active[pid]=i;progress()
    while active:reap()
    launch.update(finished_utc=h.utc(),completed=completed,resumed=resumed,drained=stopping,errors=errors)
    h.dump(receipt,launch);progress()
    if not stopping and not errors:
        for i in indices:check(i)
        h.dump(out/f'finished-{args.label}.json',launch)
    print(json.dumps({k:launch[k] for k in ('label','completed','resumed','drained','errors','finished_utc')}),flush=True)
    if errors:sys.exit(1)

if __name__=='__main__':main()
