"""Synthetic ranking and file-backed proposal guards; no real fit or labels."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import body_selection_v4 as selection
from body_scoring_v4 import POLICY, summarize
from test_selection_matrix_v4 import fixtures as event_fixtures, digest


def metric(nt=10,npred=10,matched=5):
    return summarize([dict(truth=nt,predictions=npred,matched=matched,ignored_predictions=0,
                           eligible_frames=1,unscorable_frames=0)])


def fixtures():
    readiness=event_fixtures()[0]['readiness']
    names=['validation_body_score_v4.py','body_scoring_v4.py','labels_v4.py',
           'validation_score_v4.py','validation_replay_v4.py','gamedata.json','body-catalog.json']
    return [dict(schema='clasher.v4.validation-body-score.v1',readiness=deepcopy(readiness),epoch=7,
        body_threshold=i/10,event_thresholds={'default':.5},policy=deepcopy(POLICY),
        sources={n:digest(n) for n in names},validation_receipts=readiness['validation_receipt_sha256'],
        truth_payloads={ep:{n:digest(ep+n) for n in ('frames.jsonl','objects.jsonl.gz','rich-objects.jsonl.gz')}
                        for ep in ('a','b')},
        micro=dict(metric(),eligible_frames=2),per_match={'a':metric(),'b':metric(0,0,0)},
        replay_manifest_sha256=digest(('body',i)),replay_completion_sha256=digest(('body-done',i)),
        selection_seal=False,heldout_opening_authorized=False,heldout_payloads_opened=False) for i in range(1,10)]


def main(root):
    checks=0
    def check(ok):
        nonlocal checks
        assert ok
        checks+=1
    def refuses(fn):
        nonlocal checks
        try:fn()
        except (ValueError,KeyError):checks+=1
        else:raise AssertionError('Invalid body grid accepted')
    cells=fixtures()
    result=selection.rank_body_grid(cells)
    check(result['body_threshold']==.9 and result['selection_seal'] is False)
    check(selection.rank_body_grid(list(reversed(cells)))==result)
    cells[2]['micro']=dict(metric(10,6,4),eligible_frames=2)
    cells[2]['per_match']['a']=metric(10,6,4)
    check(selection.rank_body_grid(cells)['body_threshold']==.3)  # Exact equal F1, greater precision.
    cells[1]['micro']=dict(metric(10,10,6),eligible_frames=2)
    cells[1]['per_match']['a']=metric(10,10,6)
    check(selection.rank_body_grid(cells)['body_threshold']==.2)
    refuses(lambda:selection.rank_body_grid(cells[:-1]))
    for path,value in [(['body_threshold'],True),(['body_threshold'],.55),(['epoch'],8),
                       (['event_thresholds','default'],.4),(['policy','radius_tiles'],4),
                       (['selection_seal'],True),(['heldout_opening_authorized'],True),
                       (['sources','labels_v4.py'],digest('changed')),
                       (['truth_payloads','a','objects.jsonl.gz'],digest('changed')),
                       (['readiness','steps'],400),(['micro','matched'],True),
                       (['micro','false_positive'],99),(['micro','eligible_frames'],3),
                       (['per_match','b','truth'],1),
                       (['replay_manifest_sha256'],cells[1]['replay_manifest_sha256']),
                       (['replay_completion_sha256'],'bad')]:
        bad=deepcopy(cells);row=bad[0]
        for k in path[:-1]:row=row[k]
        row[path[-1]]=value
        refuses(lambda:selection.rank_body_grid(bad))
    bad=fixtures()
    for row in bad:
        row['micro']=dict(metric(0,0,0),eligible_frames=2)
        row['per_match']={ep:metric(0,0,0) for ep in ('a','b')}
    refuses(lambda:selection.rank_body_grid(bad))
    bad=fixtures();bad[0]['micro']['eligible_frames']=3;bad[0]['per_match']['a']['eligible_frames']=2
    refuses(lambda:selection.rank_body_grid(bad))
    with patch.object(selection,'validate_run',side_effect=ValueError('Producer incomplete')):
        refuses(lambda:selection.select_run(SimpleNamespace(run=None,source=None,split=None,phase_state=None,phase_exit=None)))
    root.mkdir();grid=root/'grid.json';cells=fixtures();calls=[]
    plan=dict(schema='clasher.v4.body-grid-input.v1',epoch=7,
              cells=[dict(body_threshold=i/10,replay=f'replay-{i}') for i in range(1,10)])
    grid.write_text(json.dumps(plan))
    def scorer(args):
        index=int(args.replay.name.split('-')[-1]);calls.append(index)
        return deepcopy(cells[index-1])
    args=SimpleNamespace(run=None,source=None,split=None,phase_state=None,phase_exit=None,grid=grid,output=root/'selected')
    with patch.object(selection,'validate_run',return_value=cells[0]['readiness']), \
         patch.object(selection,'score_run',side_effect=scorer):
        selected=selection.select_run(args)
        check(calls==list(range(1,10)))
        check(selected['ranking']['body_threshold']==.9 and len(selected['scores_sha256'])==9)
        check(selection.read(args.output/'complete.json')['proposal_sha256']==selection.sha(args.output/'body-selection-proposal.json'))
        refuses(lambda:selection.select_run(args))
        args.output=root/'duplicate';plan['cells'][1]['replay']='replay-1';grid.write_text(json.dumps(plan))
        refuses(lambda:selection.select_run(args))
    print(json.dumps(dict(checks=checks,passed=True,scope='synthetic ranking and mocked admission/replay fixtures',
                         selection_seal=False,heldout_payloads_opened=False)))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output)
