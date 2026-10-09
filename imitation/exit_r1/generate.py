"""Bounded detached home-host generation with stop-file and memory-floor control."""
import argparse
import json
import multiprocessing as mp
import os
from pathlib import Path
import queue
import signal
import socket
import time
from .rows import write_json,sha


def available():
    return int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                    if line.startswith('MemAvailable:')))*1024


def worker(number,opts,reports):
    from .emitter import initialize,run_game
    os.sched_setaffinity(0,{opts['cores'][number%len(opts['cores'])]})
    initialize(opts['checkpoint'])
    i=number
    while not Path(opts['stop']).exists():
        index=opts['offset']+i
        directory=Path(opts['out'])/f'game-{index:09d}'
        if directory.exists():
            raise ValueError('refuse to overwrite or duplicate a game: '+str(directory))
        opponent=('W','v1','baseline','script')[index%4]
        receipt=run_game(opts['seed']+index,index,directory,opponent,opts['stop'])
        if receipt is None:break
        reports.put({k:receipt[k] for k in ('rows','root_decisions','cpu_seconds','wall_seconds','plays','seed')})
        i+=opts['workers']


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out',required=True);p.add_argument('--stop',required=True)
    p.add_argument('--checkpoint',required=True);p.add_argument('--workers',type=int,required=True)
    p.add_argument('--offset',type=int,default=0);p.add_argument('--seed',type=int,default=4503599727370496)
    p.add_argument('--target-roots',type=int,default=4000000)
    p.add_argument('--cores',type=int,nargs='+')
    p.add_argument('--park-receipt',help='04 release receipt explicitly supplied by coordinator')
    a=p.parse_args();host=socket.gethostname().split('.')[0]
    allowed=set(range(62,128) if host=='127x03' else range(30,128) if host=='127x04' else range(126))
    a.cores=a.cores or sorted(allowed)
    if not set(a.cores)<=allowed:raise ValueError('core overlap with E1 allocation')
    cap={'127x03':48,'127x04':96,'127x08':96}.get(host,0)
    if not 1<=a.workers<=cap-2:raise ValueError('workers plus supervisor/tracker exceed host allocation')
    if host=='127x04' and (not a.park_receipt or not Path(a.park_receipt).is_file()):
        raise ValueError('04 requires explicit parked/release evidence')
    if host=='127x04' and json.loads(Path(a.park_receipt).read_text()).get('status')!='PARKED_EXACT_CHECKPOINT_BACKED_UP_04_RELEASED':
        raise ValueError('04 parked/release receipt does not release the host')
    if os.getpriority(os.PRIO_PROCESS,0)<(19 if host=='127x08' else 10):raise ValueError('nice floor')
    if os.sched_getscheduler(0)!=os.SCHED_IDLE:raise ValueError('SCHED_IDLE required')
    if available()<24*2**30:raise ValueError('MemAvailable below 24 GiB')
    if Path(a.stop).exists():raise ValueError('stop file already exists')
    out=Path(a.out).resolve()
    if not out.is_relative_to('/mpac/sdicks02') or out.exists():raise ValueError('fresh /mpac output required')
    out.mkdir(parents=True)
    source=Path(__file__).resolve().parents[2]
    pins={str(f.relative_to(source)):sha(f) for f in source.rglob('*')
          if f.is_file() and f.suffix in ('.py','.sh','.json','.so') and '__pycache__' not in f.parts}
    write_json(out/'launch.json',dict(host=host,pid=os.getpid(),options=vars(a),source_sha256=pins,
        checkpoint_sha256=sha(a.checkpoint),park_receipt_sha256=sha(a.park_receipt) if a.park_receipt else None,
        native_sha256={f.name:sha(f) for f in Path(os.environ['CLASHER_DELAY_NATIVE_DIR']).glob('*.so')},
        nice=os.getpriority(os.PRIO_PROCESS,0),scheduler=os.sched_getscheduler(0),max_processes=a.workers+2,
        stop_file=a.stop,memory_floor_bytes=24*2**30))
    context=mp.get_context('spawn');reports=context.Queue()
    processes=[];start=time.monotonic();reason='target'
    totals=dict(games=0,rows=0,root_decisions=0,cpu_seconds=0.,plays=0)
    def stop(sig=None,frame=None):
        nonlocal reason
        reason='signal' if sig else reason
        Path(a.stop).touch()
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,stop)
    opts=vars(a).copy()
    try:
        for n in range(a.workers):
            process=context.Process(target=worker,args=(n,opts,reports))
            process.start();processes.append(process)
        last=0
        with (out/'completed.jsonl').open('a',buffering=1) as log:
            while any(v.is_alive() for v in processes):
                try:
                    r=reports.get(timeout=1)
                    totals['games']+=1
                    for k in ('rows','root_decisions','cpu_seconds','plays'):totals[k]+=r[k]
                    log.write(json.dumps(r)+'\n')
                except queue.Empty:pass
                if available()<24*2**30:reason='memory_floor';stop()
                if any(v.exitcode not in (None,0) for v in processes):reason='worker_failure';stop()
                if totals['root_decisions']>=a.target_roots:reason='target';stop()
                if Path(a.stop).exists() and reason=='target' and totals['root_decisions']<a.target_roots:
                    reason='stop_file'
                now=time.monotonic()
                if now-last>=15:
                    elapsed=now-start
                    root_rate=totals['root_decisions']/elapsed
                    status=dict(**totals,host=host,elapsed_seconds=elapsed,root_decisions_per_second=root_rate,
                        emitted_rows_per_second=totals['rows']/elapsed,
                        roots_per_cpu_second=totals['root_decisions']/max(1.,totals['cpu_seconds']),
                        eta_seconds=(a.target_roots-totals['root_decisions'])/root_rate if root_rate else None,
                        active=sum(v.is_alive() for v in processes),mem_available=available(),stop=Path(a.stop).exists())
                    write_json(out/'progress.json',status);print(json.dumps(status),flush=True);last=now
        for process in processes:process.join(timeout=1)
        while True:
            try:
                r=reports.get_nowait()
            except queue.Empty:break
            totals['games']+=1
            for k in ('rows','root_decisions','cpu_seconds','plays'):totals[k]+=r[k]
        write_json(out/'exit.json',dict(reason=reason,elapsed_seconds=time.monotonic()-start,
            totals=totals,children=[dict(pid=v.pid,exitcode=v.exitcode,alive=v.is_alive()) for v in processes],
            fully_vacated=all(not v.is_alive() for v in processes)))
    finally:
        # Only PIDs created by this supervisor; never a broad process match.
        stop()
        for process in processes:
            if process.is_alive():process.terminate()
        for process in processes:
            process.join(timeout=5)
            if process.is_alive():process.kill();process.join(timeout=5)


if __name__=='__main__':main()
