"""FSC offline tests (05, stdlib): prefix rule, outcome labels, per-game checks on real X4S2 phase-E games."""
import json, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import reduce as R

CFG = json.loads((HERE/'plan-fsc-04.json').read_text())
SHAS = {R.sha(HERE/'plan-fsc.json'), R.sha(HERE/'plan-fsc-04.json')}


def fake_phase(root, name, host):
    p = root/name; p.mkdir()
    (p/'schedule.json').write_text(json.dumps(dict(native_sha256=R.NATIVE, config_sha256=sorted(SHAS)[0], cases=[])))
    (p/'launch.json').write_text(json.dumps(dict(host=host)))
    return p


def run(phases_rows, host='127x03'):
    """phases_rows: list of (complete indices, interrupted indices) per phase."""
    with tempfile.TemporaryDirectory() as t:
        phases, table = [], {}
        for n, (done, broken) in enumerate(phases_rows):
            p = fake_phase(Path(t), f'rep{n}', host); phases.append(p)
            table[p.name] = ({('X', i): {'K4-200': {}, 'K4S-200': {}} for i in done},
                             [dict(index=i) for i in broken], {host: 1} if done else {}, {p.name: len(done)})
        old_load, old_check = R.X.load_x4s2, R.check_more
        R.X.load_x4s2 = lambda ph, cfg, rng, pops: table[ph[0].name]
        R.check_more = lambda rows, cfg, arms_of: None
        try:
            return R.load_host(host, phases, CFG, SHAS)
        finally:
            R.X.load_x4s2, R.check_more = old_load, old_check


def test_prefix():
    kept, info = run([(list(range(10))+[11, 12], [10])])
    assert sorted(i for _, i in kept) == list(range(10)) and info['first_incomplete_index'] == 10
    assert info['complete_beyond_prefix_dropped'] == 2
    # A block retired by an intermediate (yield) STOP is skipped inside the prefix; the final phase's is not.
    kept, info = run([(list(range(5)), [5]), (list(range(6, 9)), [9])])
    assert sorted(i for _, i in kept) == [0, 1, 2, 3, 4, 6, 7, 8] and info['yield_retired_skipped'] == [5]
    assert info['first_incomplete_index'] == 9
    # 03 order continues from 2399 to the top-up segment at 3900.
    kept, info = run([(list(range(2400))+[3900, 3901], [])])
    assert len(kept) == 2402 and info['first_incomplete_index'] == 3902


def test_outcome():
    assert R.outcome(dict(ci95_pp=[-1.0, 0.9])) == 'always-on supported'
    assert R.outcome(dict(ci95_pp=[0.1, 0.9])).startswith('always-on supported (small positive cost')
    assert R.outcome(dict(ci95_pp=[0.2, 2.4])) == 'speed gate needed'
    assert R.outcome(dict(ci95_pp=[-0.5, 2.0])) == 'unresolved'


def test_game_checks():
    # Real X4S2 phase-E games (K4-180 / K4S-180, published results) exercise the per-game metadata checks.
    phase = R.X4S2_E[0]
    i = next(int(p.name[1:5]) for p in sorted((phase/'blocks').glob('X*.json')))
    games = {arm: json.loads((phase/'games'/f'sim-X{i:04d}-d27-{arm}.json').read_text()) for arm in ('K4-180', 'K4S-180')}
    R.check_more({('X', i): games}, CFG, {i: ['K4-180', 'K4S-180']})
    bad = json.loads(json.dumps(games)); bad['K4S-180']['metadata']['checkpoint_sha256'] = R.POLICY
    try:
        R.check_more({('X', i): bad}, CFG, {i: ['K4-180', 'K4S-180']})
    except AssertionError:
        pass
    else:
        raise AssertionError('wrong checkpoint accepted')


if __name__ == '__main__':
    for name, f in list(globals().items()):
        if name.startswith('test_'):
            f(); print('ok', name)
