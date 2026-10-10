"""Meter the frozen X fit with loader6 and owned/leased resource guards."""
import datetime
import json
import os
from pathlib import Path
import resource
import signal
import socket
import sys
import time
import hashlib
import numpy as np
import torch
from imitation.exit_r1 import train
from imitation.t5.resources import release_pages
from imitation.exit_r1 import teacher_batch

out = Path(sys.argv[sys.argv.index('--output')+1])
started = time.monotonic()
log = None
original_eligible, original_human = train.eligible, train.human_batch
original_teacher, original_step = teacher_batch.combined_batch, train.step
def eligible(store, *args):
    global log
    if log is None:
        # The frozen trainer first requires a fresh output directory.
        log = (out/'timing.jsonl').open('a', buffering=1)
        (out/'runtime.json').write_text(json.dumps(runtime, indent=2)+'\n')
    result = original_eligible(store, *args)
    release_pages(store)
    return result
def human(store, ix):
    result = original_human(store, ix)
    release_pages(store)
    return result
def teacher(shards, ends, ix):
    result = original_teacher(shards, ends, ix)
    for store in shards: release_pages(store)
    return result
steps = 0
cursor_start=0
if '--resume' in sys.argv:
    cursor_start=int(torch.load(sys.argv[sys.argv.index('--resume')+1],map_location='cpu',weights_only=True)['state']['step'])
qualification_stop=int(os.environ.get('EXIT_QUALIFICATION_STOP_AFTER','0'))
microbatch=int(sys.argv[sys.argv.index('--microbatch')+1])
def step(*args, **kwargs):
    global steps
    begin = time.monotonic()
    result = original_step(*args, **kwargs)
    torch.cuda.synchronize()
    steps += 1
    available = int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines()
                         if s.startswith('MemAvailable:')))*1024
    pss = int(next(s.split()[1] for s in Path('/proc/self/smaps_rollup').read_text().splitlines()
                   if s.startswith('Pss:')))*1024
    free, total = torch.cuda.mem_get_info()
    log.write(json.dumps(dict(step=cursor_start+steps, optimizer_seconds=time.monotonic()-begin,
        elapsed_seconds=time.monotonic()-started, pss_bytes=pss,
        mem_available_bytes=available, gpu_free_bytes=free))+'\n')
    leased=socket.gethostname().split('.')[0] in ('127x09','127x13','127x14','127x15','127x16')
    if available < 24*2**30 or leased and (free < 8*2**30 or pss > 46_000_000_000):
        signal.raise_signal(signal.SIGTERM)
    if qualification_stop and steps>=qualification_stop:
        signal.raise_signal(signal.SIGTERM)
    return result
train.eligible, train.human_batch = eligible, human
teacher_batch.combined_batch, train.step = teacher, step
runtime = dict(host=socket.gethostname(), pid=os.getpid(),
    started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    numpy=np.__version__, torch=torch.__version__, python=sys.version,
    cuda_allocator_config=os.environ.get('PYTORCH_CUDA_ALLOC_CONF'),
    effective_human_microbatch=microbatch,
    nice=os.getpriority(os.PRIO_PROCESS,0), affinity=sorted(os.sched_getaffinity(0)),
    instrumentation='T5 read-only mmap MADV_DONTNEED after copied batches; synchronized step timing')
prefetch=None
if os.environ.get('EXIT_LOADER_WORKERS')=='6':
    from loader_prefetch import Prefetch
    amendment=Path(os.environ['EXIT_LOADER_AMENDMENT'])
    assert hashlib.sha256(amendment.read_bytes()).hexdigest()==os.environ['EXIT_LOADER_AMENDMENT_SHA256']
    spec=json.loads(amendment.read_text())
    assert spec['actual_loader_workers']==6 and spec['prefetch_factor']==4 and not spec['mmap_random_advice']
    assert spec['loader_adapter_sha256']==hashlib.sha256(Path(__file__).with_name('loader_prefetch.py').read_bytes()).hexdigest()
    prefetch=Prefetch(train,teacher_batch,int(sys.argv[sys.argv.index('--steps')+1]))
    runtime.update(actual_loader_workers=6,scientific_loader_workers=1,prefetch_factor=4,
        mmap_random_advice=False,operational_amendment_sha256=os.environ['EXIT_LOADER_AMENDMENT_SHA256'])
status = 'failed'
try:
    train.main()
    status = 'returned'
finally:
    if prefetch is not None:prefetch.close()
    out.mkdir(parents=True, exist_ok=True)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    child_usage=resource.getrusage(resource.RUSAGE_CHILDREN)
    (out/'segment.json').write_text(json.dumps(dict(**runtime,status=status,
        ended_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        wall_seconds=time.monotonic()-started,
        cpu_seconds=usage.ru_utime+usage.ru_stime+child_usage.ru_utime+child_usage.ru_stime,
        parent_cpu_seconds=usage.ru_utime+usage.ru_stime,
        loader_cpu_seconds=child_usage.ru_utime+child_usage.ru_stime,
        optimizer_steps=steps,cursor_start=cursor_start,
        peak_loader_tree_pss_bytes=prefetch.peak_pss if prefetch is not None else 0,
        min_loader_mem_available_bytes=prefetch.minimum_available if prefetch is not None else 0,
        resource_stop=prefetch.resource_stop if prefetch is not None else None),indent=2)+'\n')
