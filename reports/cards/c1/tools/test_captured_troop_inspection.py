"""Pure JSON inspector controls; fixtures are explicitly synthetic, not captured roots."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile

from inspect_captured_troop import CASES, CONTRACT, inspect, observation


def sample(case, seat):
    lead, identity, first = CASES[case]
    actor = dict(id=identity, **{'class': 'Troop'}, entity_kind=0, x=9, y=10.5, alive=True,
                 target=10, stats=dict(name=case, ordinary=True))
    target = dict(actor, id=10, target=None)
    state = dict(tick=100, entities=[actor, target], config=dict(cards={}, spirit_areas={}))
    before = dict(python=copy.deepcopy(state), native=copy.deepcopy(state))
    after = copy.deepcopy(before)
    for arm in after:
        after[arm]['tick'] += 1
    return dict(case=case, lead=lead, seat=seat, contract=CONTRACT, source_sha256='0'*64,
                initial_root=copy.deepcopy(before), result=dict(first=first, cast=dict(python=True)),
                first_context=dict(relative_tick=first, before=before, after=after,
                                   differences=[dict(field='synthetic-control-only', python=False, native=True)],
                                   digest_equal=True))


def reject(callback):
    try:
        callback()
    except ValueError:
        return
    raise AssertionError('invalid evidence shape accepted')


def main():
    rows = [sample(case, seat) for case in CASES for seat in (0, 1)]
    for row in rows:
        out = observation(row)
        assert out['differences'] == row['first_context']['differences']
        assert out['initial']['python']['actor']['fields']['clock'] == '<absent>'
        assert out['evidence_kind'] == 'captured-boundary-observations-not-causal-proof'
    dragon = observation(rows[2])
    assert dragon['zero_displacement_at_before_boundary'] == dict(python=True, native=True)
    moved = copy.deepcopy(rows[2])
    moved['first_context']['before']['native']['entities'][1]['x'] += .001
    assert observation(moved)['zero_displacement_at_before_boundary']['native'] is False
    for mutate in (
        lambda r: r.update(lead=999),
        lambda r: r.update(seat=True),
        lambda r: r.update(error='explicit failed capture'),
        lambda r: r['first_context']['before']['native'].update(tick=99),
        lambda r: r['first_context']['after']['python'].update(tick=102),
        lambda r: r['first_context']['before'].pop('python'),
        lambda r: r['first_context']['before']['python']['entities'].append(copy.deepcopy(r['first_context']['before']['python']['entities'][0])),
    ):
        bad = copy.deepcopy(rows[0]); mutate(bad)
        reject(lambda: observation(bad))
    with tempfile.TemporaryDirectory(prefix='c1-json-inspection-') as temp:
        path = Path(temp)/'synthetic.json'
        def write(data):
            raw = json.dumps(data).encode(); path.write_bytes(raw)
            return hashlib.sha256(raw).hexdigest()
        data = dict(contract=CONTRACT, collection_status='COMPLETE', status='PREFLIGHT_FAIL', legacy=rows)
        sha = write(data)
        out = inspect(path, sha)
        assert out['engine_acceptance'] == 'NOT_EVALUATED' and out['original_status'] == 'PREFLIGHT_FAIL'
        reject(lambda: inspect(path, 'f'*64))
        data['legacy'].pop(); sha = write(data)
        reject(lambda: inspect(path, sha))
        data['legacy'] = rows; data['collection_status'] = 'INVALID'; sha = write(data)
        reject(lambda: inspect(path, sha))
    print('PASS: six synthetic shapes, retained FAIL/absence, coincidence control, seven malformed roots, hash/denominator/collection negatives; no actual capture or native test')


if __name__ == '__main__':
    main()
