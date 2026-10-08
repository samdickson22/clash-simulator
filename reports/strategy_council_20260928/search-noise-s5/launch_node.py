"""Fleet-detached fork supervisor; fixed partitions, host-wide caps, immutable receipts."""
import bootstrap
from bootstrap import HERE
import argparse,json,socket,subprocess,os,time,resource,multiprocessing,traceback
from pathlib import Path
from evaluate import verify,write,Resources
from derived_public_state import DerivedPublicState
import worker as runner
JOBS=Path('/mpac/sdicks02/jobs/clasher')

def child(index,total,label,resources):
    started=time.time()
    with (JOBS/f'{label}.log').open('a',buffering=1) as stream:
        os.dup2(stream.fileno(),1);os.dup2(stream.fileno(),2);code=0
        try:runner.main(['--index',str(index),'--workers',str(total)],resources)
        except BaseException:traceback.print_exc();code=1
        usage=resource.getrusage(resource.RUSAGE_SELF)
        print(f'User time (seconds): {usage.ru_utime}',flush=True)
        print(f'System time (seconds): {usage.ru_stime}',flush=True)
        print(f'Maximum resident set size (kbytes): {usage.ru_maxrss}',flush=True)
        print(f'Elapsed seconds: {time.time()-started}',flush=True)
        tmp=JOBS/f'{label}.exit.tmp';tmp.write_text(str(code)+'\n');tmp.replace(JOBS/f'{label}.exit')
    raise SystemExit(code)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',default='r1');ap.add_argument('--concurrency',type=int,default=76);args=ap.parse_args()
    host=socket.gethostname().split('.')[0];assert host in ('127x04','127x08')
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    assert os.environ.get('PYTHONHASHSEED')=='0'
    assert all(os.environ.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','RAYON_NUM_THREADS'))
    manifest=json.loads((HERE/'evaluation-manifest.json').read_text());verify(manifest)
    (HERE/'confirmation').mkdir(exist_ok=True)
    execution=json.loads((HERE/'execution.json').read_text());total=len(execution['workers'])
    workers=[w for w in execution['workers'] if w['host']==host]
    assert 1<=args.concurrency<=76 and len(workers)==76
    who=subprocess.check_output(['who'],text=True)
    console_tool=Path.home()/'.local/bin/fleet-console-users'
    console_users=int(subprocess.check_output([str(console_tool)],text=True))
    r=Resources();prior=json.loads((HERE/'runtime/support/human_deck_catalog.json').read_text());r.initial_belief=DerivedPublicState(prior,r.costs)
    context=multiprocessing.get_context('fork');pending=list(workers);active=[];failed=[]
    launched=[dict(index=w['index'],label=f's5-confirm-{w["index"]}-{args.attempt}',host=host) for w in workers]
    labels={w['index']:w['label'] for w in launched}
    launch_path=HERE/f'launch-{host}-{args.attempt}.json';assert not launch_path.exists()
    write(launch_path,dict(workers=launched,launched_at=time.time(),who=who,console_users=console_users,requested_concurrency=args.concurrency,supervisor_label=f's5-confirm-node-{host}-{args.attempt}'))
    max_observed=0;max_with_console=0;checks=0
    while pending or active:
        who=subprocess.check_output(['who'],text=True)
        # Conservatively count all current user Python processes, including supervisor.
        ps=subprocess.check_output(['ps','-u',str(os.getuid()),'-o','comm='],text=True)
        python_count=sum(any(word in line.lower() for word in ('python','pt_data_worker','ffmpeg','blender','clasher')) for line in ps.splitlines())
        console_users=int(subprocess.check_output([str(console_tool)],text=True))
        cap=16 if console_users else 96
        max_observed=max(max_observed,python_count);checks+=1
        if console_users:max_with_console=max(max_with_console,python_count)
        capacity=max(0,min(args.concurrency-len(active),cap-python_count-2))
        write(HERE/f'capacity-{host}.json',dict(utc=time.time(),who=who,console_users=console_users,python_processes=python_count,cap=cap,active=len(active),pending=len(pending),capacity=capacity,max_observed_processes=max_observed,max_observed_with_console=max_with_console,checks=checks))
        for _ in range(min(capacity,len(pending))):
            if failed:break
            w=pending.pop(0);i=w['index'];label=labels[i];receipt=JOBS/f'{label}.exit'
            if receipt.exists():
                if receipt.read_text().strip()!='0':failed.append(i)
                continue
            process=context.Process(target=child,args=(i,total,label,r));process.start()
            (JOBS/f'{label}.pid').write_text(str(process.pid)+'\n');active.append((i,process))
        for i,process in list(active):
            if not process.is_alive():
                process.join();active.remove((i,process))
                if process.exitcode:
                    failed.append(i);receipt=JOBS/f'{labels[i]}.exit'
                    if not receipt.exists():
                        code=process.exitcode if process.exitcode>0 else 128-process.exitcode
                        tmp=receipt.with_suffix('.exit.tmp');tmp.write_text(str(code)+'\n');tmp.replace(receipt)
        if failed and not active:break
        if pending or active:time.sleep(5)
    if failed:raise RuntimeError(f'failed partitions: {failed}; pending retained: {[w["index"] for w in pending]}')
if __name__=='__main__':main()
