"""Detached dev supervisor; count all user Python processes and respect host cap."""
import bootstrap
from bootstrap import HERE
import argparse,json,multiprocessing,os,resource,socket,subprocess,time,traceback
from pathlib import Path
JOBS=Path('/mpac/sdicks02/jobs/clasher')
def child(index,kind,round_name,r):
    label=f's4-dev-extra-{kind}-{index}-{round_name}'
    with (JOBS/f'{label}.log').open('a',buffering=1) as f:
        os.dup2(f.fileno(),1);os.dup2(f.fileno(),2);code=0
        try:
            if kind=='generate':
                from dev_trace import run
                run(r,index)
            else:
                from dev_replay import run
                run(index,round_name)
        except BaseException:traceback.print_exc();code=1
        usage=resource.getrusage(resource.RUSAGE_SELF)
        print(json.dumps(dict(cpu_seconds=usage.ru_utime+usage.ru_stime)),flush=True)
        (JOBS/f'{label}.exit').write_text(str(code)+'\n')
    raise SystemExit(code)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--kind',choices=['generate','replay'],required=True);ap.add_argument('--round',default='v1');ap.add_argument('--limit',type=int,default=56);ap.add_argument('--concurrency',type=int,default=24);args=ap.parse_args()
    host=socket.gethostname().split('.')[0];assert host in ('127x04','127x08') and os.getpriority(os.PRIO_PROCESS,0)>=10
    r=None
    if args.kind=='generate':
        from fair_player import Resources
        r=Resources()
    pending=[i for i in range(28,args.limit) if i%2==(host=='127x08')];active=[];failed=[];context=multiprocessing.get_context('fork')
    while pending or active:
        who=subprocess.check_output(['who'],text=True);ps=subprocess.check_output(['ps','-u',str(os.getuid()),'-o','comm='],text=True)
        capacity=max(0,min(args.concurrency-len(active),(16 if who.strip() else 96)-sum('python' in x.lower() for x in ps.splitlines())-2))
        for _ in range(min(capacity,len(pending))):
            if failed:break
            i=pending.pop(0);label=f's4-dev-extra-{args.kind}-{i}-{args.round}'
            if (JOBS/f'{label}.exit').exists():
                assert (JOBS/f'{label}.exit').read_text().strip()=='0';continue
            p=context.Process(target=child,args=(i,args.kind,args.round,r));p.start();(JOBS/f'{label}.pid').write_text(str(p.pid));active.append((i,p))
        for i,p in list(active):
            if not p.is_alive():
                p.join();active.remove((i,p))
                if p.exitcode:failed.append(i)
        if failed and not active:break
        if pending or active:time.sleep(3)
    assert not failed,failed
if __name__=='__main__':main()
