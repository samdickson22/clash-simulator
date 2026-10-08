"""Synthetic full body/event selection and tamper rejection; fleet worker only."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import body_selection_v4 as body
import validation_select_v4 as event
import verify_event_selection_v4 as verifier
from selection_matrix_v4 import rank_validation_grid
from test_body_selection_v4 import fixtures as body_fixtures, metric
from test_selection_matrix_v4 import fixtures as event_fixtures, digest


def main(root):
    checks=0
    def check(value):
        nonlocal checks
        assert value;checks+=1
    def refuses(fn):
        nonlocal checks
        try:fn()
        except (ValueError,KeyError):checks+=1
        else:raise AssertionError('Invalid joint selection accepted')
    root.mkdir()
    events=event_fixtures();ready=events[0]['readiness'];bodies={};rankings={}
    body_map={}
    for epoch in range(1,25):
        chosen=(epoch%9+1)/10
        rows=body_fixtures()
        for row in rows:
            row['epoch']=epoch
            row['replay_manifest_sha256']=digest(('body',epoch,row['body_threshold']))
            if row['body_threshold']==chosen:
                row['micro']=dict(metric(10,10,8),eligible_frames=2)
                row['per_match']['a']=metric(10,10,8)
            bodies[f"body-{epoch}-{round(row['body_threshold']*10)}"]=row
        rankings[str(epoch)]=body.rank_body_grid(rows)
        path=root/f'body-grid-{epoch}.json'
        path.write_text(json.dumps(dict(schema='clasher.v4.body-grid-input.v1',epoch=epoch,
            cells=[dict(body_threshold=r['body_threshold'],replay=f"body-{epoch}-{round(r['body_threshold']*10)}") for r in rows])))
        body_map[str(epoch)]=path.name
    for row in events:
        row['body_threshold']=rankings[str(row['epoch'])]['body_threshold']
        count=deepcopy(row['point']['opponent'])
        row['point'].update(all_sides=count,per_card_side=[dict(card='Knight',side=0,**count)])
    check(rank_validation_grid(events,rankings)['body_threshold']==.2)
    refuses(lambda:rank_validation_grid(events))
    for key,value in [('epoch',True),('checkpoint_sha256',digest('wrong')),
                      ('event_thresholds',{'default':.6}),('body_threshold',True),('selection_seal',True)]:
        bad=deepcopy(rankings);bad['1'][key]=value
        refuses(lambda:rank_validation_grid(events,bad))
    bad=deepcopy(rankings);del bad['24'];refuses(lambda:rank_validation_grid(events,bad))
    bad=deepcopy(events);bad[0]['body_threshold']=.7
    refuses(lambda:rank_validation_grid(bad,rankings))
    grid=root/'grid.json'
    plan=dict(schema='clasher.v4.validation-grid-input.v1',body_grids=body_map,
        cells=[dict(epoch=r['epoch'],threshold=r['threshold'],replay=f"event-{r['epoch']}-{round(r['threshold']*10)}") for r in events])
    grid.write_text(json.dumps(plan))
    lookup={f"event-{r['epoch']}-{round(r['threshold']*10)}":r for r in events}
    calls=[]
    def scorer(table,kind):
        def score(args):calls.append((kind,args.replay.name));return deepcopy(table[args.replay.name])
        return score
    def args(name):return SimpleNamespace(run=None,source=None,split=None,phase_state=None,phase_exit=None,
        grid=grid,output=root/name,selection=root/'original')
    with patch.object(body,'validate_run',return_value=ready),patch.object(event,'validate_run',return_value=ready), \
            patch.object(verifier,'validate_run',return_value=ready), \
            patch.object(body,'score_run',side_effect=scorer(bodies,'body')), \
            patch.object(event,'score_run',side_effect=scorer(lookup,'event')):
        proposal=event.select_run(args('original'))
        check(len(calls)==432 and len(set(calls))==432)
        check(proposal['body_threshold']==.2 and len(proposal['body_selections'])==24)
        calls.clear();result=verifier.verify_run(args('verified'))
        check(len(calls)==432 and result['body_selection_verified'] is True)
        check(result['grid_body_threshold']==.2 and result['event_thresholds']=={'default':.9,'Knight':.9})
        check(result['selection_seal'] is False and result['heldout_opening_authorized'] is False)
        path=root/'original/body-epoch-01/body-threshold-1.json';saved=path.read_bytes()
        path.write_bytes(saved+b'\n');calls.clear()
        refuses(lambda:verifier.verify_run(args('tampered-body')))
        check(not calls);path.write_bytes(saved)
        # Changing actual recomputed body outcomes cannot be hidden by intact JSON hashes.
        changed=bodies['body-1-2'];saved=deepcopy(changed)
        changed['micro']=dict(metric(10,10,4),eligible_frames=2);changed['per_match']['a']=metric(10,10,4)
        refuses(lambda:verifier.verify_run(args('changed-body-score')))
        check(not (root/'changed-body-score/complete.json').exists())
        changed.clear();changed.update(saved)
        bad=deepcopy(plan);bad['body_grids'].pop('24');grid.write_text(json.dumps(bad))
        refuses(lambda:event.select_run(args('missing-body-epoch')))
        grid.write_text(json.dumps(plan))
    print(json.dumps(dict(checks=checks,passed=True,synthetic_only=True,selection_seal=False,
                         heldout_payloads_opened=False)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    main(p.parse_args().output)
