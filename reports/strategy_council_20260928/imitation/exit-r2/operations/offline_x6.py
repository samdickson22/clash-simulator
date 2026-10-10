"""R1 heldout diagnostics and exact X stage1 decision; home CPU only."""
import argparse
from experiment_x6 import load_experiment
import json
import os
from pathlib import Path
import resource
import socket
import time
import torch
import numpy as np
from imitation.exit_r1 import screen
from imitation.exit_r1.student import TeacherStore
from imitation.exit_r1.rows import sha,write_json
from supplement import teacher

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--arm',required=True)
    p.add_argument('--checkpoint',required=True);a=p.parse_args();j=Path(a.job)
    assert socket.gethostname().split('.')[0] in ('127x01','127x03')
    screen.execution_guard(str(j/'REPORTING.STOP'))
    torch.set_num_threads(1);start=time.monotonic()
    audit=json.loads((j/'seed-audit.json').read_text());assert audit['passed']
    frozen=load_experiment(j)
    assert sha(j/'heldout-corpus/manifest.json')==frozen['heldout_manifest_sha256']
    assert sha(j/'inputs/assets.npz')==frozen['assets_sha256']
    checkpoint=Path(a.checkpoint);ck=torch.load(checkpoint,map_location='cpu',weights_only=True)
    assert ck['state']['step']==frozen['arms'][a.arm]['steps']
    assert ck['args']['seed']==2026101001 and ck['args']['play_weight']==1
    del ck
    store=TeacherStore(j/'heldout-corpus',j/'inputs/assets.npz')
    assert set(map(int,np.unique(store.arrays['perspective_ids'])))=={
        4503601207370496+i for i in range(64)}
    policy=screen.load_student(checkpoint)
    root=teacher(policy,store,True);poll=teacher(policy,store,False)
    m={k:v['value'] for k,v in root['metrics'].items()};reasons=[]
    if m['play_recall']<.60:reasons.append('play recall <0.60')
    if m['top8_action_recall']<.50:reasons.append('top-8 recall <0.50')
    if m['hard_action_agreement']<.704:reasons.append('root hard agreement <0.704')
    if m['student_wait_rate']>1.5*m['teacher_wait_rate']:reasons.append('student WAIT >1.5 times teacher')
    usage=resource.getrusage(resource.RUSAGE_SELF)
    result=dict(arm=a.arm,stage=1,checkpoint_sha256=sha(checkpoint),
        heldout_manifest_sha256=sha(j/'heldout-corpus/manifest.json'),
        freeze_sha256=sha(j/'freeze.json'),teacher=root,all_poll_rows=poll,
        all_WAIT_hard_agreement=m['teacher_wait_rate'],survives=not reasons,kill_reasons=reasons,
        cpu_seconds=usage.ru_utime+usage.ru_stime,wall_seconds=time.monotonic()-start,
        lane='exploration; no multiplicity adjustment')
    write_json(j/'offline'/f'{a.arm}.json',result)
    print(json.dumps(dict(arm=a.arm,survives=not reasons,kill_reasons=reasons,metrics=m)),flush=True)

if __name__=='__main__':main()
