"""Validate/rank a complete formal validation grid; no I/O or selection seal.

Callers must recompute each cell through validation_score_v4.score_run. A JSON
declaration, even with internally consistent hashes, is not authenticated evidence.
This helper proposes a global-threshold/epoch candidate only. Per-card and body
thresholds, final replay, calibration and the sealed selection remain separate.
"""
from selection_guard_v4 import _sha
from scoring_v4 import select_epoch, select_threshold


def counts(row):
    values = tuple(row[k] for k in ('truth', 'predictions', 'matched'))
    if any(type(v) is not int or v < 0 for v in values) or values[2] > min(values[:2]):
        raise ValueError('Invalid cell counts')
    return values


def rank_validation_grid(cells, body_rankings=None):
    cells = list(cells)
    if len(cells) != 24*9:
        raise ValueError('All 24 epochs and nine registered thresholds required')
    reference = cells[0]
    body_threshold=reference.get('body_threshold')
    if type(body_threshold) not in (int,float) or body_threshold not in [i/10 for i in range(1,10)]:
        raise ValueError('Explicit registered body threshold required')
    readiness = reference['readiness']
    if (readiness.get('validated') is not True or readiness.get('steps') != 9600
            or readiness.get('epochs') != 24 or readiness.get('selection_seal') is not False
            or readiness.get('heldout_opening_authorized') is not False
            or readiness.get('heldout_payloads_opened') is not False):
        raise ValueError('Full formal fit evidence required')
    for key in ('fit_manifest_sha256', 'completion_sha256', 'admission_sha256'):
        if not _sha(readiness.get(key)):
            raise ValueError('Incomplete formal run provenance')
    checkpoints = readiness.get('checkpoint_sha256', {})
    if set(checkpoints) != {str(i) for i in range(1, 25)} or not all(_sha(v) for v in checkpoints.values()):
        raise ValueError('Complete formal checkpoint set required')
    # Caller must recompute these rankings from all nine authenticated body
    # replays per epoch. Body configuration may vary between epochs, never
    # between event-threshold cells belonging to the same epoch.
    if body_rankings is not None:
        if set(body_rankings) != {str(i) for i in range(1,25)}:
            raise ValueError('All 24 authenticated body rankings required')
        for e, ranking in body_rankings.items():
            t = ranking.get('body_threshold')
            if (ranking.get('schema') != 'clasher.v4.body-grid-ranking.v1'
                    or type(ranking.get('epoch')) is not int or ranking['epoch'] != int(e)
                    or ranking.get('readiness') != readiness
                    or ranking.get('checkpoint_sha256') != checkpoints[e]
                    or ranking.get('event_thresholds') != {'default': .5}
                    or type(t) not in (int,float) or t not in [i/10 for i in range(1,10)]
                    or any(ranking.get(k) is not False for k in
                           ('selection_seal','heldout_opening_authorized','heldout_payloads_opened'))):
                raise ValueError('Body ranking differs from full fit or registered configuration')
    receipts = readiness['validation_receipt_sha256']
    if not receipts or not all(_sha(v) for v in receipts.values()):
        raise ValueError('Full validation receipt population required')
    if readiness.get('validation_matches') != len(receipts):
        raise ValueError('Validation population size differs')
    sources, truth_files = reference['sources'], reference['truth_payloads']
    if (set(sources) != {'validation_score_v4.py', 'execution_clock_v4.py', 'scoring_v4.py'}
            or not all(_sha(v) for v in sources.values()) or set(truth_files) != set(receipts)
            or any(set(files) != {'frames.jsonl', 'events.jsonl'} or not all(_sha(v) for v in files.values())
                   for files in truth_files.values())):
        raise ValueError('Incomplete scorer/truth provenance')
    grid, seen_replays, population = {}, set(), None
    for cell in cells:
        epoch, threshold = cell['epoch'], cell['threshold']
        if (type(epoch) is not int or not 1 <= epoch <= 24
                or type(threshold) not in (float, int) or threshold not in [i/10 for i in range(1, 10)]):
            raise ValueError('Unregistered epoch/threshold')
        if (cell.get('schema') != 'clasher.v4.validation-score.v1'
                or cell.get('replay_mode')!='grid' or cell.get('event_thresholds')!={'default':threshold}
                or cell.get('heldout_payloads_opened') is not False
                or cell.get('selection_seal') is not False or cell.get('readiness') != readiness
                or cell.get('validation_receipts') != receipts or cell.get('sources') != sources
                or type(cell.get('body_threshold')) not in (int,float)
                or cell['body_threshold'] != (body_rankings[str(epoch)]['body_threshold']
                                             if body_rankings is not None else body_threshold)
                or cell.get('truth_payloads') != truth_files):
            raise ValueError('Mixed fit, validation population, or scorer sources')
        identity = epoch, threshold
        if identity in grid:
            raise ValueError('Duplicate validation grid cell')
        replay = cell.get('replay_manifest_sha256')
        if not _sha(replay) or replay in seen_replays or not _sha(cell.get('replay_completion_sha256')):
            raise ValueError('Missing or reused replay evidence')
        seen_replays.add(replay)
        score = cell['point']
        if score.get('timing') != 'point' or set(score['per_match']) != set(receipts):
            raise ValueError('Point scoring and complete episode counts required')
        totals = [0, 0, 0]
        truth_counts = {}
        for ep, sides in score['per_match'].items():
            if set(sides) != {'0', '1'}:
                raise ValueError('Both native seats required')
            own, opponent = counts(sides['1']), counts(sides['0'])
            totals = [a+b for a,b in zip(totals, opponent)]
            truth_counts[ep] = (opponent[0], own[0])
        if counts(score['opponent']) != tuple(totals):
            raise ValueError('Opponent totals differ from episode counts')
        if population is not None and truth_counts != population:
            raise ValueError('Per-match truth denominators changed across grid')
        population = truth_counts
        grid[identity] = dict(epoch=epoch, threshold=threshold, opponent=score['opponent'],
                             replay_manifest_sha256=replay)
    candidates = [select_threshold([grid[epoch, i/10] for i in range(1, 10)]) for epoch in range(1, 25)]
    candidate = select_epoch(candidates)
    if body_rankings is not None:
        body_threshold = body_rankings[str(candidate['epoch'])]['body_threshold']
    return dict(schema='clasher.v4.validation-grid.v1', candidate=candidate,
                body_threshold=body_threshold,
                epoch_candidates=candidates, cells=len(grid), readiness=readiness,
                validation_receipts=receipts, sources=sources, truth_payloads=truth_files,
                rule='best global threshold per epoch; opponent F1 then precision; threshold ties higher, epoch ties earlier',
                selection_seal=False, heldout_opening_authorized=False,
                scope='pure candidate ranking; caller must authenticate every replay; per-card/body/calibration pending')
