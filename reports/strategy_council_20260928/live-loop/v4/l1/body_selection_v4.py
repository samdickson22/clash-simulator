"""Recompute nine full-validation body cells for one epoch; propose, never seal.

Epoch/event selection must subsequently use a consistent body configuration.
This tool cannot select the epoch, certify calibration or authorize heldout.
"""
import argparse
from fractions import Fraction
import json
from pathlib import Path
from types import SimpleNamespace

from body_scoring_v4 import POLICY
from selection_guard_v4 import _sha
from validation_admission_v4 import read, sha, validate_run
from validation_body_score_v4 import score_run


COUNT_KEYS = ('truth','predictions','matched','ignored_predictions',
              'eligible_frames','unscorable_frames')


def checked_counts(row):
    if (any(type(row.get(k)) is not int or row[k] < 0 for k in COUNT_KEYS)
            or row['matched'] > min(row['truth'],row['predictions'])
            or (not row['eligible_frames'] and any(row[k] for k in ('truth','predictions','matched')))):
        raise ValueError('Invalid body counts')
    nt,npred,matched=(row[k] for k in ('truth','predictions','matched'))
    expected=dict(missed=nt-matched,false_positive=npred-matched,
        recall=matched/nt if nt else None,precision=matched/npred if npred else None,
        f1=2*matched/(nt+npred) if nt+npred else None,
        phantom_rate=(npred-matched)/npred if npred else None,
        drop_rate=(nt-matched)/nt if nt else None)
    if any(row.get(k)!=value or isinstance(row.get(k),bool) for k,value in expected.items()):
        raise ValueError('Reported body metrics differ from counts')
    return {k:row[k] for k in COUNT_KEYS}


def rank_body_grid(cells):
    """Pure ranking requires caller authentication; JSON claims are not proof."""
    cells=list(cells)
    if len(cells)!=9:raise ValueError('Nine registered body thresholds required')
    reference=cells[0];readiness=reference['readiness'];epoch=reference['epoch']
    if (type(epoch) is not int or not 1<=epoch<=24
            or readiness.get('validated') is not True or readiness.get('steps')!=9600
            or readiness.get('epochs')!=24
            or any(readiness.get(k) is not False for k in
                   ('selection_seal','heldout_opening_authorized','heldout_payloads_opened'))):
        raise ValueError('Complete formal fit required')
    for key in ('fit_manifest_sha256','completion_sha256','admission_sha256'):
        if not _sha(readiness.get(key)):raise ValueError('Formal fit pin missing')
    checkpoints=readiness.get('checkpoint_sha256',{})
    if set(checkpoints)!={str(i) for i in range(1,25)} or not all(_sha(v) for v in checkpoints.values()):
        raise ValueError('All formal checkpoint pins required')
    receipts=readiness['validation_receipt_sha256']
    if not receipts or readiness.get('validation_matches')!=len(receipts) or not all(_sha(v) for v in receipts.values()):
        raise ValueError('Complete validation population required')
    sources=reference['sources'];truth_files=reference['truth_payloads']
    names={'validation_body_score_v4.py','body_scoring_v4.py','labels_v4.py',
           'validation_score_v4.py','validation_replay_v4.py','gamedata.json','body-catalog.json'}
    if (len(sources)!=len(names) or {Path(n).name for n in sources}!=names
            or not all(_sha(v) for v in sources.values()) or set(truth_files)!=set(receipts)
            or any(set(files)!={'frames.jsonl','objects.jsonl.gz','rich-objects.jsonl.gz'}
                   or not all(_sha(v) for v in files.values()) for files in truth_files.values())):
        raise ValueError('Complete scorer/cleaner/truth pins required')
    thresholds=reference['event_thresholds']
    if (not isinstance(thresholds,dict) or 'default' not in thresholds
            or any(not isinstance(k,str) or not k for k in thresholds)
            or any(type(v) not in (int,float) or v not in [i/10 for i in range(1,10)] for v in thresholds.values())):
        raise ValueError('Registered event configuration required')
    grid={};replays=set();population=None
    for cell in cells:
        t=cell['body_threshold']
        if type(t) not in (int,float) or t not in [i/10 for i in range(1,10)] or t in grid:
            raise ValueError('Invalid or duplicate body threshold')
        if (cell.get('schema')!='clasher.v4.validation-body-score.v1'
                or cell.get('epoch')!=epoch or type(cell.get('epoch')) is not int
                or cell.get('readiness')!=readiness or cell.get('validation_receipts')!=receipts
                or cell.get('sources')!=sources or cell.get('truth_payloads')!=truth_files
                or cell.get('policy')!=POLICY or cell.get('event_thresholds')!=thresholds
                or any(cell.get(k) is not False for k in
                       ('selection_seal','heldout_opening_authorized','heldout_payloads_opened'))):
            raise ValueError('Mixed configuration, policy, provenance or population')
        replay=cell.get('replay_manifest_sha256')
        if not _sha(replay) or replay in replays or not _sha(cell.get('replay_completion_sha256')):
            raise ValueError('Distinct authenticated replay evidence required')
        replays.add(replay)
        if set(cell['per_match'])!=set(receipts):raise ValueError('Incomplete match counts')
        counts={ep:checked_counts(row) for ep,row in cell['per_match'].items()}
        micro=checked_counts(cell['micro'])
        if micro!={k:sum(row[k] for row in counts.values()) for k in COUNT_KEYS}:
            raise ValueError('Micro totals differ from per-match counts')
        current={ep:tuple(row[k] for k in ('truth','eligible_frames','unscorable_frames'))
                 for ep,row in counts.items()}
        if population is not None and current!=population:
            raise ValueError('Truth or scorable-frame coverage changed across thresholds')
        population=current
        if not micro['truth']:raise ValueError('No scorable positive body truth; selection blocked')
        grid[t]=cell
    def rank(cell):
        count=cell['micro'];nt,npred,matched=(count[k] for k in ('truth','predictions','matched'))
        return Fraction(2*matched,nt+npred),Fraction(matched,npred) if npred else Fraction(0),cell['body_threshold']
    candidate=max(grid.values(),key=rank)
    return dict(schema='clasher.v4.body-grid-ranking.v1',epoch=epoch,
        body_threshold=candidate['body_threshold'],micro=candidate['micro'],
        replay_manifest_sha256=candidate['replay_manifest_sha256'],
        checkpoint_sha256=checkpoints[str(epoch)],readiness=readiness,policy=POLICY,
        event_thresholds=thresholds,rule='body micro F1, then precision, then higher threshold',
        selection_seal=False,heldout_opening_authorized=False,heldout_payloads_opened=False)


def select_run(args):
    readiness=validate_run(args.run,args.source,args.split,args.phase_state,args.phase_exit)
    plan=read(args.grid);epoch=plan.get('epoch');entries=plan.get('cells',[])
    if (plan.get('schema')!='clasher.v4.body-grid-input.v1' or type(epoch) is not int
            or not 1<=epoch<=24 or len(entries)!=9):
        raise ValueError('Explicit complete single-epoch body grid required')
    grid={};paths=set()
    for cell in entries:
        t=cell['body_threshold'];name=cell['replay']
        if (type(t) not in (int,float) or t not in [i/10 for i in range(1,10)] or t in grid
                or not isinstance(name,str) or not name):raise ValueError('Invalid body-grid cell')
        path=Path(name)
        if not path.is_absolute():path=args.grid.parent/path
        path=path.resolve()
        if path in paths:raise ValueError('Distinct body replays required')
        paths.add(path);grid[t]=path
    if args.output.exists():raise ValueError('Fresh output required; retain failed attempts')
    args.output.mkdir()
    def put(name,value):
        with (args.output/name).open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
    pins={p.name:sha(p) for p in (Path(__file__),Path(__file__).with_name('validation_body_score_v4.py'))}
    manifest=dict(schema='clasher.v4.body-selection-input.v1',readiness=readiness,epoch=epoch,
        grid_sha256=sha(args.grid),sources=pins,selection_seal=False,heldout_payloads_opened=False)
    put('manifest.json',manifest)
    scores=[];files={}
    for t,path in sorted(grid.items()):
        score=score_run(SimpleNamespace(run=args.run,source=args.source,split=args.split,
            phase_state=args.phase_state,phase_exit=args.phase_exit,replay=path))
        if score['epoch']!=epoch or score['body_threshold']!=t or score['readiness']!=readiness:
            raise ValueError('Authenticated replay differs from declared body grid')
        name=f'body-threshold-{round(t*10)}.json';put(name,score);files[name]=sha(args.output/name);scores.append(score)
    ranking=rank_body_grid(scores)
    if sha(args.grid)!=manifest['grid_sha256'] or any(sha(Path(__file__).with_name(n))!=v for n,v in pins.items()):
        raise ValueError('Body selection inputs changed')
    proposal=dict(schema='clasher.v4.body-selection-proposal.v1',ranking=ranking,
        scores_sha256=files,manifest_sha256=sha(args.output/'manifest.json'),
        selection_seal=False,heldout_opening_authorized=False,heldout_payloads_opened=False,
        pending=['verify body proposal by recomputation','consistent event/epoch selection',
                 'final calibration verification','selection seal'])
    put('body-selection-proposal.json',proposal)
    put('complete.json',dict(proposal_sha256=sha(args.output/'body-selection-proposal.json'),cells=9,
        selection_seal=False,heldout_opening_authorized=False,heldout_payloads_opened=False))
    return proposal


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ('run','source','split','phase-state','phase-exit','grid','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    select_run(parser.parse_args())
