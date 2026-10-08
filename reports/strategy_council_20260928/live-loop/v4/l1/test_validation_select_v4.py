"""Synthetic file-backed orchestration, with admission/scoring boundaries mocked."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import validation_select_v4 as selection
from test_selection_matrix_v4 import fixtures


def main(root):
    checks=0
    def check(value):
        nonlocal checks
        assert value;checks+=1
    def rejected(args):
        nonlocal checks
        try: selection.select_run(args)
        except ValueError: checks+=1
        else: raise AssertionError('Invalid selection accepted')
    def reject_admission(*args):raise ValueError('Producer not complete')
    selection.validate_run=reject_admission
    rejected(SimpleNamespace(run=None,source=None,split=None,phase_state=None,phase_exit=None))
    root.mkdir()
    scores=fixtures()
    for row in scores:
        c=deepcopy(row['point']['opponent'])
        row['point'].update(all_sides=c,per_card_side=[dict(card='Knight',side=0,**c)])
    evidence=deepcopy(scores[0]['readiness'])
    selection.validate_run=lambda *args:deepcopy(evidence)
    lookup={f"replay-{row['epoch']}-{round(row['threshold']*10)}":row for row in scores}
    calls=[]
    def score(args):
        calls.append(args.replay.name)
        return deepcopy(lookup[args.replay.name])
    selection.score_run=score
    plan=dict(schema='clasher.v4.validation-grid-input.v1',cells=[dict(epoch=r['epoch'],threshold=r['threshold'],
        replay=f"replay-{r['epoch']}-{round(r['threshold']*10)}") for r in scores])
    grid=root/'grid.json'
    def args(label):return SimpleNamespace(run=None,source=None,split=None,phase_state=None,phase_exit=None,grid=grid,output=root/label)
    def put(value):grid.write_text(json.dumps(value))
    put(plan)
    result=selection.select_run(args('good'))
    check(len(calls)==216 and len(result['scores_sha256'])==216)
    check(result['ranking']['candidate']['epoch']==1 and result['card_thresholds']['thresholds']=={'default':.9,'Knight':.9})
    check(result['selection_seal'] is False and result['heldout_opening_authorized'] is False)
    check(result['body_threshold']==.5 and result['card_thresholds']['body_threshold']==.5)
    check(selection.read(root/'good/complete.json')['proposal_sha256']==selection.sha(root/'good/event-selection-proposal.json'))
    rejected(args('good'))  # No overwrite, including completed proposals.
    bad=deepcopy(plan);bad['cells'].pop();put(bad);rejected(args('missing'))
    bad=deepcopy(plan);bad['cells'][-1]=deepcopy(bad['cells'][0]);put(bad);rejected(args('duplicate-cell'))
    bad=deepcopy(plan);bad['cells'][-1]['replay']=bad['cells'][0]['replay'];put(bad);rejected(args('duplicate-path'))
    put(plan)
    first=lookup['replay-1-1'];saved=deepcopy(first)
    first['epoch']=2;rejected(args('wrong-epoch'));first.clear();first.update(deepcopy(saved))
    first['readiness']['fit_manifest_sha256']='0'*64;rejected(args('mixed-fit'));first.clear();first.update(deepcopy(saved))
    first['sources']['scoring_v4.py']='0'*64;rejected(args('mixed-scorer'));first.clear();first.update(deepcopy(saved))
    first['body_threshold']=.7;rejected(args('mixed-body'));first.clear();first.update(deepcopy(saved))
    # A failed recomputation leaves evidence but never completion or a proposal.
    check((root/'mixed-fit/manifest.json').exists() and not (root/'mixed-fit/complete.json').exists())
    check(not (root/'mixed-scorer/event-selection-proposal.json').exists())
    print(json.dumps(dict(checks=checks,passed=True,synthetic_only=True,heldout_payloads_opened=False)),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output)
