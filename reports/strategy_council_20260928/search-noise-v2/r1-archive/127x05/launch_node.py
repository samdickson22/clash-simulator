"""Detached node supervisor with fork-shared immutable runtime and prior arrays."""
import bootstrap
from bootstrap import HERE,ROOT
import argparse,json,socket,subprocess,os,time,resource,multiprocessing,traceback
from pathlib import Path
from evaluate import verify,write,Resources
from derived_public_state import DerivedPublicState
import worker as runner
JOBS=Path('/mpac/sdicks02/jobs/clasher')

def child(index,total,label,resources,pilot=False,max_tick=1200):
    started=time.time()
    with (JOBS/f'{label}.log').open('a',buffering=1) as stream:
        os.dup2(stream.fileno(),1);os.dup2(stream.fileno(),2)
        code=0
        try:
            argv=['--index',str(index),'--workers',str(total)]
            if pilot:
                argv+=['--pilot']
                if max_tick:argv+=['--max-tick',str(max_tick)]
            runner.main(argv,resources)
        except BaseException:
            traceback.print_exc();code=1
        usage=resource.getrusage(resource.RUSAGE_SELF)
        print(f'User time (seconds): {usage.ru_utime}',flush=True)
        print(f'System time (seconds): {usage.ru_stime}',flush=True)
        print(f'Maximum resident set size (kbytes): {usage.ru_maxrss}',flush=True)
        print(f'Elapsed seconds: {time.time()-started}',flush=True)
        tmp=JOBS/f'{label}.exit.tmp';tmp.write_text(str(code)+'\n');tmp.replace(JOBS/f'{label}.exit')
    raise SystemExit(code)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',default='r1');ap.add_argument('--fork-pilot',action='store_true');ap.add_argument('--full-pilot',action='store_true');args=ap.parse_args()
    host=socket.gethostname().split('.')[0];assert host in ('127x02','127x07','127x08')
    if host!='127x02':assert (JOBS/'smoke-p16-linux-20261007.exit').read_text().strip()=='0'
    pilot=args.fork_pilot or args.full_pilot
    if pilot:
        workers=[dict(index=(36 if args.full_pilot else 25)+i,host=host) for i in range(18 if args.full_pilot else 4)];total=len(workers)
    else:
        manifest=json.loads((HERE/'evaluation-manifest.json').read_text());verify(manifest)
        execution=json.loads((HERE/'execution.json').read_text());total=len(execution['workers'])
        workers=[w for w in execution['workers'] if w['host']==host]
    assert len(workers)<=(48 if host=='127x02' else 100)
    who=subprocess.check_output(['who'],text=True)
    # Fixed partitions can run in smaller waves without changing any game inputs.
    concurrency=min(len(workers),4 if who.strip() else len(workers))
    r=Resources();prior=json.loads((HERE/'runtime/support/human_deck_catalog.json').read_text())
    r.initial_belief=DerivedPublicState(prior,r.costs)
    context=multiprocessing.get_context('fork');pending=list(workers);active=[];failed=[]
    launched=[dict(index=w['index'],label=f's1-{"fullpilot" if args.full_pilot else "forkpilot" if args.fork_pilot else "confirm"}-{w["index"]}-{args.attempt}',host=host) for w in workers]
    labels={w['index']:w['label'] for w in launched}
    if not pilot:write(HERE/f'launch-{host}-{args.attempt}.json',dict(workers=launched,launched_at=time.time(),who=who,concurrency=concurrency))
    while pending or active:
        while pending and len(active)<concurrency:
            w=pending.pop(0);i=w['index'];label=labels[i]
            receipt=JOBS/f'{label}.exit'
            if receipt.exists():
                if receipt.read_text().strip()!='0':failed.append(i)
                continue
            process=context.Process(target=child,args=(i,total,label,r,pilot,None if args.full_pilot else 1200));process.start()
            (JOBS/f'{label}.pid').write_text(str(process.pid)+'\n');active.append((i,process))
        for i,process in list(active):
            if not process.is_alive():
                process.join();active.remove((i,process))
                if process.exitcode:
                    failed.append(i)
                    receipt=JOBS/f'{labels[i]}.exit'
                    if not receipt.exists():
                        code=process.exitcode if process.exitcode>0 else 128-process.exitcode
                        tmp=receipt.with_suffix('.exit.tmp');tmp.write_text(str(code)+'\n');tmp.replace(receipt)
        if active:time.sleep(1)
    if failed:raise RuntimeError(f'failed partitions: {failed}')

if __name__=='__main__':main()
