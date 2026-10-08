"""Synthetic recomputation/provenance checks; run only on a fleet worker."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import verify_event_selection_v4 as verifier
import validation_select_v4 as selection
from test_selection_matrix_v4 import fixtures


def main(root):
    checks=0
    def check(v):
        nonlocal checks
        assert v;checks+=1
    def rejects(fn):
        nonlocal checks
        try:fn()
        except ValueError:checks+=1
        else:raise AssertionError('Invalid verification accepted')
    def refuse(*args):raise ValueError('Incomplete producer')
    with patch.object(verifier,'validate_run',refuse):
        rejects(lambda:verifier.verify_run(SimpleNamespace(run=None,source=None,split=None,phase_state=None,phase_exit=None)))
    root.mkdir();scores=fixtures();readiness=deepcopy(scores[0]['readiness'])
    for row in scores:
        count=deepcopy(row['point']['opponent'])
        row['point'].update(all_sides=count,per_card_side=[dict(card='Knight',side=0,**count)])
    lookup={f"replay-{r['epoch']}-{round(r['threshold']*10)}":r for r in scores};calls=[]
    def score(args):calls.append(args.replay.name);return deepcopy(lookup[args.replay.name])
    grid=root/'grid.json'
    grid.write_text(json.dumps(dict(schema='clasher.v4.validation-grid-input.v1',cells=[
        dict(epoch=r['epoch'],threshold=r['threshold'],replay=f"replay-{r['epoch']}-{round(r['threshold']*10)}") for r in scores])))
    def args(name):return SimpleNamespace(run=None,source=None,split=None,phase_state=None,phase_exit=None,
        grid=grid,selection=root/'original',output=root/name)
    with patch.object(verifier,'validate_run',return_value=readiness),patch.object(selection,'validate_run',return_value=readiness),patch.object(selection,'score_run',score):
        selection.select_run(args('original'));calls.clear()
        result=verifier.verify_run(args('verified'))
        check(len(calls)==216 and len(set(calls))==216)
        check(result['epoch']==1 and result['event_thresholds']=={'default':.9,'Knight':.9})
        check(result['event_selection_verified'] is True and result['body_selection_verified'] is False)
        check(result['selection_seal'] is False and result['heldout_opening_authorized'] is False)
        done=json.loads((root/'verified/complete.json').read_text())
        check(done['verification_sha256']==verifier.sha(root/'verified/event-selection-verified.json'))
        rejects(lambda:verifier.verify_run(args('verified')))
        original=root/'original';proposal_path=original/'event-selection-proposal.json';done_path=original/'complete.json'
        proposal_bytes=proposal_path.read_bytes();done_bytes=done_path.read_bytes()
        proposal=json.loads(proposal_bytes)
        def change_proposal(value):
            proposal_path.write_text(json.dumps(value))
            complete=json.loads(done_bytes);complete['proposal_sha256']=verifier.sha(proposal_path)
            done_path.write_text(json.dumps(complete))
        bad=deepcopy(proposal);bad['card_thresholds']['thresholds']['Knight']=.1;change_proposal(bad)
        calls.clear();rejects(lambda:verifier.verify_run(args('forged-map')))
        check(len(calls)==216 and (root/'forged-map/recomputed-selection/complete.json').exists())
        check(not (root/'forged-map/event-selection-verified.json').exists())
        proposal_path.write_bytes(proposal_bytes);done_path.write_bytes(done_bytes)
        for key,value in [('heldout_opening_authorized',True),('selection_seal',True),('scores_sha256',{})]:
            bad=deepcopy(proposal);bad[key]=value;change_proposal(bad)
            rejects(lambda:verifier.verify_run(args('bad-metadata')))
        proposal_path.write_bytes(proposal_bytes);done_path.write_bytes(done_bytes)
        path=original/'epoch-01-threshold-1.json';saved=path.read_bytes();path.write_bytes(saved+b'\n')
        rejects(lambda:verifier.verify_run(args('score-tamper')));path.write_bytes(saved)
        saved_grid=grid.read_bytes();grid.write_bytes(saved_grid+b'\n')
        rejects(lambda:verifier.verify_run(args('grid-changed')));grid.write_bytes(saved_grid)
        # Saved evidence can be internally intact while actual replay scores change.
        row=lookup['replay-1-1'];saved=deepcopy(row);row['point']['opponent']['matched']=4
        row['point']['per_match']['a']['0']['matched']=4
        row['point']['all_sides']['matched']=4;row['point']['per_card_side'][0]['matched']=4
        rejects(lambda:verifier.verify_run(args('actual-score-changed')))
        check(not (root/'actual-score-changed/event-selection-verified.json').exists())
        row.clear();row.update(saved)
    print(json.dumps(dict(checks=checks,passed=True,synthetic_only=True,heldout_payloads_opened=False)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    main(p.parse_args().output)
