"""Recompute the complete formal validation grid and propose event thresholds.

No heldout payload path or selection seal. Body threshold fitting, replay with
the combined event map, calibration and final sealing remain required.
Interrupted outputs are retained; restart with a fresh output directory.
"""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from validation_admission_v4 import read, sha, validate_run
from validation_score_v4 import score_run
from selection_matrix_v4 import rank_validation_grid
from card_thresholds_v4 import select_card_thresholds


def select_run(args):
    # Authentic producer completion/full formal fitting precede even grid reads.
    readiness = validate_run(args.run, args.source, args.split, args.phase_state, args.phase_exit)
    plan = read(args.grid)
    entries = plan['cells']
    expected = {(epoch, i/10) for epoch in range(1,25) for i in range(1,10)}
    if plan.get('schema') != 'clasher.v4.validation-grid-input.v1' or len(entries) != len(expected):
        raise ValueError('Explicit complete 24x9 replay grid required')
    paths, grid = set(), {}
    for cell in entries:
        epoch, threshold = cell['epoch'], cell['threshold']
        if (type(epoch) is not int or type(threshold) not in (int,float)
                or (epoch,threshold) not in expected or (epoch,threshold) in grid):
            raise ValueError('Invalid or repeated registered cell')
        name = cell['replay']
        if not isinstance(name,str) or not name:
            raise ValueError('Replay directory required')
        path = Path(name)
        if not path.is_absolute():path = args.grid.parent/path
        path = path.resolve()
        if path in paths:
            raise ValueError('One distinct completed replay per grid cell required')
        paths.add(path); grid[epoch,threshold] = path
    if args.output.exists():
        raise ValueError('Fresh selection output required; retain interrupted evidence')
    args.output.mkdir()
    def put(name,value):
        with (args.output/name).open('x') as f:
            json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
    code = Path(__file__).parent
    source_names = ('validation_select_v4.py','validation_admission_v4.py','validation_score_v4.py',
                    'selection_matrix_v4.py','card_thresholds_v4.py','scoring_v4.py','execution_clock_v4.py')
    manifest = dict(schema='clasher.v4.validation-selection-input.v1', readiness=readiness,
        grid_sha256=sha(args.grid), cells=[dict(epoch=e,threshold=t,replay=str(grid[e,t])) for e,t in sorted(grid)],
        sources={name:sha(code/name) for name in source_names}, heldout_payloads_opened=False,selection_seal=False)
    put('manifest.json',manifest)
    scores, score_files = [], {}
    for epoch,threshold in sorted(grid):
        cell_args = SimpleNamespace(run=args.run,source=args.source,split=args.split,
            phase_state=args.phase_state,phase_exit=args.phase_exit,replay=grid[epoch,threshold])
        # Never trust a precomputed metrics JSON: recompute authenticated files.
        result = score_run(cell_args)
        if (result['readiness'] != readiness or result['epoch'] != epoch or result['threshold'] != threshold):
            raise ValueError('Replay differs from declared grid or original full admission')
        name = f'epoch-{epoch:02d}-threshold-{round(threshold*10)}.json'
        put(name,result);score_files[name] = sha(args.output/name);scores.append(result)
    ranking = rank_validation_grid(scores)
    candidate = ranking['candidate']
    thresholds = select_card_thresholds([r for r in scores if r['epoch']==candidate['epoch']],
                                       global_threshold=candidate['threshold'])
    # Refuse source/grid mutations during a long recomputation.
    if manifest['grid_sha256'] != sha(args.grid) or any(sha(code/n)!=v for n,v in manifest['sources'].items()):
        raise ValueError('Selection inputs changed during scoring')
    proposal = dict(schema='clasher.v4.event-selection-proposal.v1', ranking=ranking,
        body_threshold=ranking['body_threshold'],
        card_thresholds=thresholds, checkpoint_sha256=readiness['checkpoint_sha256'][str(candidate['epoch'])],
        manifest_sha256=sha(args.output/'manifest.json'), scores_sha256=score_files,
        heldout_payloads_opened=False,heldout_opening_authorized=False,selection_seal=False,
        pending=['body thresholds','combined-threshold replay','isotonic calibration','selection freeze'])
    put('event-selection-proposal.json',proposal)
    put('complete.json',dict(proposal_sha256=sha(args.output/'event-selection-proposal.json'),
        cells=len(scores),heldout_payloads_opened=False,heldout_opening_authorized=False,selection_seal=False))
    return proposal


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    for name in ('run','source','split','phase-state','phase-exit','grid','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    select_run(parser.parse_args())
