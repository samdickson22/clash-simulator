"""Synthetic worker orchestration: no real model, cache or receipt payloads."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import validation_batch_v4 as batch


def main(root):
    root.mkdir();checks=0
    def check(value):
        nonlocal checks
        assert value;checks+=1
    def refuse(fn):
        nonlocal checks
        try:fn()
        except (ValueError,RuntimeError,FileNotFoundError):checks+=1
        else:raise AssertionError('Invalid batch accepted')
    plan=root/'plan.json'
    value=dict(schema='clasher.v4.validation-batch.v1',cells=[dict(epoch=1,threshold=.5,body_threshold=.1)])
    plan.write_text(json.dumps(value));calls=[]
    def args(name):return SimpleNamespace(run=root/'run',source=root/'source',split=root/'split',
        phase_state=root/'state',phase_exit=root/'exit',cache_union=root/'private-runtime',
        plan=plan,output=root/name)
    with patch.object(batch,'validate_run',side_effect=ValueError('Producer incomplete')):
        refuse(lambda:batch.worker(args('premature')))
        check(not (root/'premature').exists())
    def child(command,check):
        calls.append(command)
        out=Path(command[command.index('--output')+1]);out.mkdir()
        (out/'complete.json').write_text('{}')
    with patch.object(batch,'validate_run',return_value={'validated':True}), \
         patch.object(batch.shutil,'disk_usage',return_value=SimpleNamespace(free=300_000_000_000)), \
         patch.object(batch.subprocess,'run',side_effect=child):
        batch.worker(args('ok'))
        check(len(calls)==1 and calls[0][calls[0].index('--epoch')+1]=='1')
        check(calls[0][calls[0].index('--body-threshold')+1]=='0.1')
        done=batch.read(root/'ok/complete.json')
        check(done['heldout_payloads_opened'] is False and done['selection_seal'] is False)
        check(set(done['cells'])=={'epoch-01-event-5-body-1'})
        refuse(lambda:batch.worker(args('ok')))
        with patch.object(batch.subprocess,'run',side_effect=RuntimeError('Failed cell')):
            refuse(lambda:batch.worker(args('failed')))
        check((root/'failed/manifest.json').exists() and not (root/'failed/complete.json').exists())
        def changed(command,check):
            child(command,check);plan.write_text(plan.read_text()+'\n')
        with patch.object(batch.subprocess,'run',side_effect=changed):
            refuse(lambda:batch.worker(args('changed-plan')))
        check(not (root/'changed-plan/complete.json').exists())
        with patch.object(batch.shutil,'disk_usage',return_value=SimpleNamespace(free=199_999_999_999)):
            refuse(lambda:batch.worker(args('disk-reserve')))
        check(not (root/'disk-reserve/complete.json').exists())
    print(json.dumps(dict(checks=checks,passed=True,synthetic_only=True,heldout_payloads_opened=False)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
