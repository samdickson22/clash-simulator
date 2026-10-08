"""Synthetic complete-grid and provenance rejection tests; no real data."""
from copy import deepcopy
from hashlib import sha256
import json
from selection_matrix_v4 import rank_validation_grid


def digest(value):
    return sha256(str(value).encode()).hexdigest()


def fixtures():
    receipts = {'a': digest('a'), 'b': digest('b')}
    readiness = dict(validated=True, steps=9600, epochs=24, selection_seal=False,
        heldout_opening_authorized=False, heldout_payloads_opened=False,
        fit_manifest_sha256=digest('fit'), completion_sha256=digest('fit-done'),
        admission_sha256=digest('admission'), validation_receipt_sha256=receipts,
        validation_matches=2, checkpoint_sha256={str(i):digest(i) for i in range(1, 25)})
    count = dict(truth=10, predictions=10, matched=5)
    empty = dict(truth=0, predictions=0, matched=0)
    return [dict(schema='clasher.v4.validation-score.v1', epoch=e, threshold=t/10,body_threshold=.5,
        replay_mode='grid',event_thresholds={'default':t/10},
        readiness=deepcopy(readiness), heldout_payloads_opened=False, selection_seal=False,
        validation_receipts=deepcopy(receipts),
        sources={name:digest(name) for name in ('validation_score_v4.py', 'execution_clock_v4.py', 'scoring_v4.py')},
        truth_payloads={ep:{name:digest(ep+name) for name in ('frames.jsonl','events.jsonl')} for ep in receipts},
        replay_manifest_sha256=digest((e,t)), replay_completion_sha256=digest(('done',e,t)),
        point=dict(timing='point', opponent=deepcopy(count), per_match={
            'a':{'0':deepcopy(count),'1':deepcopy(empty)},
            'b':{'0':deepcopy(empty),'1':deepcopy(empty)}})) for e in range(1,25) for t in range(1,10)]


def main():
    checks = 0
    def check(value):
        nonlocal checks
        assert value
        checks += 1
    def reject(cells):
        nonlocal checks
        try: rank_validation_grid(cells)
        except (ValueError, KeyError): checks += 1
        else: raise AssertionError('Invalid matrix accepted')
    grid = fixtures()
    chosen = rank_validation_grid(grid)
    check(chosen['body_threshold']==.5)
    check(chosen['candidate']['epoch'] == 1 and chosen['candidate']['threshold'] == .9)
    check(len(chosen['epoch_candidates']) == 24 and chosen['selection_seal'] is False
          and chosen['heldout_opening_authorized'] is False)
    cell = grid[11*9+2]
    better_precision = dict(truth=10,predictions=6,matched=4)  # Same exact F1, higher precision.
    cell['point']['opponent'] = deepcopy(better_precision)
    cell['point']['per_match']['a']['0'] = deepcopy(better_precision)
    chosen = rank_validation_grid(grid)
    check(chosen['candidate']['epoch'] == 12 and chosen['candidate']['threshold'] == .3)
    check(rank_validation_grid(list(reversed(grid))) == chosen)
    reject(grid[:-1])
    bad=deepcopy(grid);bad[-1]=deepcopy(bad[0]);reject(bad)
    for path, value in [
        (['epoch'],True), (['threshold'],.55), (['schema'],'pilot'),
        (['replay_mode'],'combined'), (['event_thresholds'],{'default':.1,'Knight':.8}),
        (['body_threshold'],.7), (['body_threshold'],None), (['body_threshold'],True),
        (['heldout_payloads_opened'],True), (['selection_seal'],True),
        (['readiness','fit_manifest_sha256'],digest('different-fit')),
        (['readiness','checkpoint_sha256','12'],digest('different-weights')),
        (['sources','scoring_v4.py'],digest('different-scorer')),
        (['truth_payloads','a','events.jsonl'],digest('different-truth')),
        (['validation_receipts','a'],digest('different-receipt')),
        (['replay_manifest_sha256'],grid[0]['replay_manifest_sha256']),
        (['replay_completion_sha256'],'bad'), (['point','timing'],'conservative'),
        (['point','per_match','a','0','matched'],True),
        (['point','per_match','a','0','predictions'],3),
        (['point','opponent','matched'],4),
        (['point','per_match','b','1','truth'],1)]:
        bad=deepcopy(grid);row=bad[1]
        for k in path[:-1]:row=row[k]
        row[path[-1]]=value;reject(bad)
    # Uniformly false metadata is still refused, even when every cell agrees.
    for field,value in [('steps',400),('validated',False),('validation_matches',1),('admission_sha256','bad')]:
        bad=deepcopy(grid)
        for row in bad:row['readiness'][field]=value
        reject(bad)
    bad=deepcopy(grid)
    for row in bad:row['body_threshold']=.55
    reject(bad)
    bad=deepcopy(grid)
    for row in bad:del row['point']['per_match']['b']
    reject(bad)
    print(json.dumps(dict(checks=checks,passed=True,synthetic_only=True,heldout_payloads_opened=False)),flush=True)


if __name__ == '__main__':main()
