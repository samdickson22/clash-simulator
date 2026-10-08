"""Resume only validation after an authenticated complete T6 epoch24 fit."""
import argparse
import datetime
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import sys

from formal_guard import admit
from lease_lifecycle_v4 import STOP_UTC,offload,supervise
from validation_admission_v4 import read,sha


def validate_completed_fit(run,dataset,admission):
    if read(run/'admission.json')!=admission:raise ValueError('Completed run admission changed')
    model=run/'run/model';complete=read(model/'complete.json');meta=read(model/'manifest.json')
    if (complete.get('epochs')!=24 or complete.get('sha256')!=sha(model/'last.pt')
            or meta.get('seed')!=6107 or meta.get('device')!='cuda'
            or meta.get('heldout_pixels_or_labels_opened') is not False
            or meta.get('dataset_manifest_sha256')!=sha(dataset/'manifest.json')):
        raise ValueError('Unchanged complete formal T6 fit required')
    rows=[json.loads(line) for line in (model/'training.jsonl').read_text().splitlines()]
    if len(rows)!=24 or any(type(r.get('epoch')) is not int or r['epoch']!=i
                           or type(r.get('loss')) not in (int,float) or not math.isfinite(r['loss'])
                           for i,r in enumerate(rows,1)):
        raise ValueError('All24 completed training epochs required')
    inventory=read(dataset/'inventory.json')
    if any(r['split'] not in ('train','validation') for r in inventory):raise ValueError('Heldout dataset refused')
    expected={}
    for path,digest in admission['receipts'].items():
        p=Path(path)
        if sha(p)!=digest:raise ValueError('Admission receipt changed')
        row=read(p)
        if row['split'] in ('train','validation'):expected[row['episode']]=digest
    if len(inventory)!=len(expected) or {r['episode']:r['receipt_sha256'] for r in inventory}!=expected:
        raise ValueError('Prepared full population changed')
    train=[r['episode'] for r in inventory if r['split']=='train']
    if len(meta['training_episodes'])!=len(train) or set(meta['training_episodes'])!=set(train):
        raise ValueError('Full formal training population required')
    return complete['sha256']


def main():
    p=argparse.ArgumentParser()
    for name in ('run','dataset','phase-state','phase-exit','journal'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();root=Path('/mpac/sdicks02/repos/clasher-lease');code=Path(__file__).parent
    if socket.gethostname().split('.')[0]!='127x15' or os.environ.get('CLASHER_LEASE_ROOT')!=str(root):
        raise ValueError('15 lease wrapper required')
    if a.journal.exists() or any(not q.resolve().is_relative_to(root) for q in (a.run,a.dataset,a.journal)):
        raise ValueError('Fresh journal and lease-local paths required')
    admission=admit(a.phase_state,a.phase_exit,root/'data/v4-matches',code.parent/'split.json',code)
    checkpoint=validate_completed_fit(a.run,a.dataset,admission)
    free=subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True)
    if int(free.splitlines()[0])<16384:raise ValueError('Need16GiB free before validation')
    incomplete=a.run/'run/validation-inference'
    if incomplete.exists() and not (incomplete/'complete.json').exists():
        archive=incomplete.with_name('validation-inference-failed-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        incomplete.rename(archive)
    command=[sys.executable,'-B',str(code/'run_t6_shake.py'),'--dataset',str(a.dataset),
             '--output',str(a.run/'run'),'--epochs','24','--steps','400']
    status=supervise(command,a.journal,datetime.datetime.fromisoformat(STOP_UTC).timestamp(),
                     lambda j:offload(a.run,j,'127x04'))
    if sha(a.run/'run/model/last.pt')!=checkpoint:raise ValueError('Validation changed fitted weights')
    raise SystemExit(status)


if __name__=='__main__':main()
