"""Bounded, lease-supervised serial validation cells; no heldout entry point.

Each cell uses the unchanged full-validation driver and its measured completion
journal. A partial cell stays on disk and never supplies selection evidence.
"""
import argparse
import datetime
import json
import math
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

from lease_lifecycle_v4 import STOP_UTC, offload, supervise
from validation_admission_v4 import read, sha, validate_run


def batch_cells(plan):
    if plan.get('schema')!='clasher.v4.validation-batch.v1':raise ValueError('Explicit replay batch required')
    rows=plan.get('cells',[])
    if not isinstance(rows,list) or not 1<=len(rows)<=9:raise ValueError('One to nine bounded cells required')
    seen=set()
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'epoch','threshold','body_threshold'}:
            raise ValueError('Only registered epoch/event/body options allowed')
        if type(row['epoch']) is not int or not 1<=row['epoch']<=24:
            raise ValueError('Registered epoch required')
        if any(type(row[k]) not in (int,float) or row[k] not in [i/10 for i in range(1,10)]
               for k in ('threshold','body_threshold')):
            raise ValueError('Registered thresholds required')
        key=(row['epoch'],row['threshold'],row['body_threshold'])
        if key in seen:raise ValueError('Duplicate cell refused')
        seen.add(key)
    return rows


def batch_deadline(now, lease_exit, service_deadline=None):
    # Preserve the coordinator's04:30 checkpoint/stop lead even though a replay
    # batch uses a shorter grace than training. No new batch after that point.
    if now>=lease_exit-1800:raise ValueError('Too late for another replay batch')
    end=min(lease_exit-1800+180,now+2700)
    if service_deadline is not None:
        if not math.isfinite(service_deadline):raise ValueError('Finite service deadline required')
        end=min(end,service_deadline-30)
    if now>=end-180:raise ValueError('Cache service lifetime exhausted')
    return end


def worker(a):
    readiness=validate_run(a.run,a.source,a.split,a.phase_state,a.phase_exit)
    plan_sha=sha(a.plan);cells=batch_cells(read(a.plan))
    if a.output.exists():raise ValueError('Fresh batch output required; preserve interrupted work')
    a.output.mkdir()
    manifest=dict(schema='clasher.v4.validation-batch-evidence.v1',readiness=readiness,
        plan_sha256=plan_sha,cells=cells,driver_sha256=sha(Path(__file__).with_name('validation_replay_v4.py')),
        heldout_payloads_opened=False,selection_seal=False)
    (a.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    completed={}
    for row in cells:
        if shutil.disk_usage('/mpac').free<200_000_000_000:raise ValueError('Need200GB free')
        if sha(a.plan)!=plan_sha:raise ValueError('Batch plan changed')
        name=f"epoch-{row['epoch']:02d}-event-{round(row['threshold']*10)}-body-{round(row['body_threshold']*10)}"
        command=[sys.executable,'-B',str(Path(__file__).with_name('validation_replay_v4.py'))]
        for key in ('run','source','split','phase_state','phase_exit','cache_union'):
            command.extend(['--'+key.replace('_','-'),str(getattr(a,key))])
        command.extend(['--output',str(a.output/name)])
        for key,value in row.items():command.extend(['--'+key.replace('_','-'),str(value)])
        print(json.dumps(dict(start_cell=name,time=time.time())),flush=True)
        subprocess.run(command,check=True)
        completed[name]=sha(a.output/name/'complete.json')
        print(json.dumps(dict(completed_cell=name,completion_sha256=completed[name],time=time.time())),flush=True)
    if (sha(a.plan)!=plan_sha or manifest['driver_sha256']!=sha(Path(__file__).with_name('validation_replay_v4.py'))):
        raise ValueError('Batch sources or plan changed')
    (a.output/'complete.json').write_text(json.dumps(dict(cells=completed,
        manifest_sha256=sha(a.output/'manifest.json'),heldout_payloads_opened=False,selection_seal=False),indent=2)+'\n')


def main():
    p=argparse.ArgumentParser()
    for name in ('run','source','split','phase-state','phase-exit','output','plan','cache-union','journal'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--worker',action='store_true')
    p.add_argument('--service-deadline',type=float)
    a=p.parse_args();root=Path('/mpac/sdicks02/repos/clasher-lease')
    if socket.gethostname().split('.')[0]!='127x09' or os.environ.get('CLASHER_LEASE_ROOT')!=str(root):
        raise ValueError('Assigned09 lease wrapper required')
    if any(not q.resolve().is_relative_to(root) for q in (a.run,a.output,a.journal,a.cache_union)):
        raise ValueError('Lease-local runtime paths required')
    if a.worker:
        if os.environ.get('CLASHER_V4_RUN_SUPERVISED')!='1':raise ValueError('Lifecycle supervision required')
        worker(a);return
    batch_cells(read(a.plan))
    # Home services live at most one hour after verification. This batch has a
    # hard45-minute lifetime; on deadline incomplete evidence remains unsealed.
    stop_at=batch_deadline(time.time(),datetime.datetime.fromisoformat(STOP_UTC).timestamp(),a.service_deadline)
    command=[sys.executable,'-B',str(Path(__file__)),*sys.argv[1:],'--worker']
    raise SystemExit(supervise(command,a.journal,stop_at,lambda j:offload(a.run,j,'127x04'),
                              lead=180,grace=120))


if __name__=='__main__':main()
