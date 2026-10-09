"""Resource and timing instrumentation around the frozen trainer; no recipe edits."""
import datetime
import json
import os
from pathlib import Path
import resource
import signal
import socket
import sys
import time
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
    log.write(json.dumps(dict(step=steps, optimizer_seconds=time.monotonic()-begin,
        elapsed_seconds=time.monotonic()-started, pss_bytes=pss,
        mem_available_bytes=available, gpu_free_bytes=free))+'\n')
    if available < 24*2**30 or free < 8*2**30 or pss > 46_000_000_000:
        signal.raise_signal(signal.SIGTERM)
    return result
train.eligible, train.human_batch = eligible, human
teacher_batch.combined_batch, train.step = teacher, step
runtime = dict(host=socket.gethostname(), pid=os.getpid(),
    started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    numpy=np.__version__, torch=torch.__version__, python=sys.version,
    nice=os.getpriority(os.PRIO_PROCESS,0), affinity=sorted(os.sched_getaffinity(0)),
    instrumentation='T5 read-only mmap MADV_DONTNEED after copied batches; synchronized step timing')
status = 'failed'
try:
    train.main()
    status = 'returned'
finally:
    out.mkdir(parents=True, exist_ok=True)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    (out/'segment.json').write_text(json.dumps(dict(**runtime,status=status,
        ended_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        wall_seconds=time.monotonic()-started,
        cpu_seconds=usage.ru_utime+usage.ru_stime, optimizer_steps=steps),indent=2)+'\n')
