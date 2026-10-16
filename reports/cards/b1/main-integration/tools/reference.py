"""Single-process RoyaleSim16.402 reference probes; exclusive run-local output.

Use the same scratch stat overlay for original and combined Python sources.
The per-card comparator reports partial fidelity honestly; regression acceptance
requires unchanged measured B1 observables versus its accepted original source.
"""
import importlib.util
import json
from pathlib import Path
import sys

tools = Path(__file__).resolve().parent
sys.path.insert(0, str(tools/'b1'))
import scenarios


def require(ok, detail):
    if not ok:
        raise RuntimeError(detail)


if sys.argv[1] == 'probe':
    pool = {r['name']: r for r in json.loads((tools/'b1/pool.json').read_text())}
    pool.update({r['name']: r for r in json.loads((tools/'batchA/pool.json').read_text())})
    cards = ('RoyalRecruits', 'ThreeMusketeers', 'GiantSkeleton', 'SkeletonBalloon', 'Hunter',
             'MiniSparkys', 'RoyalGiant', 'BattleHealer', 'GoblinGiant', 'GiantBuffer',
             'Tombstone', 'BarbarianHut', 'Witch')
    count = 0
    with open(sys.argv[2], 'x') as out:
        for name in cards:
            card = pool[name]
            for scenario in scenarios.scenarios(card):
                row = scenarios.paired((card, scenario, '160402'))
                out.write(json.dumps(row)+'\n'); out.flush()
                count += 1
                require(all('error' not in row[k] for k in ('ours', 'rsim')), row)
                require(all(d[-1] for k in ('ours', 'rsim') for d in row[k]['deployments']),
                        ('reference deployment refused', name, scenario))
                print(name, scenario, row['elapsed_s'], flush=True)
    require(count == 39, ('reference coverage', count))
elif sys.argv[1] == 'compare':
    spec = importlib.util.spec_from_file_location('summary', tools/'summarize.py')
    summary = importlib.util.module_from_spec(spec); spec.loader.exec_module(summary)
    def rows(path):
        return {(r['card'], r['scenario']): r for r in map(json.loads, Path(path).read_text().splitlines())}
    before, after = rows(sys.argv[2]), rows(sys.argv[3])
    require(before.keys() == after.keys() and len(after) == 39, 'reference key mismatch')
    results = []
    changed_b1 = []
    for key, row in after.items():
        verdict, differences = summary.compare(row)
        old_verdict, old_differences = summary.compare(before[key])
        def observable(x):
            return {k: v for k, v in x.items() if k not in ('r1_battle_sha256', 'source')}
        unchanged = observable(row['ours']) == observable(before[key]['ours'])
        require(observable(row['rsim']) == observable(before[key]['rsim']), ('reference changed', key))
        require(verdict != 'HARNESS-GAP', (key, differences))
        if key[0] not in ('Tombstone', 'BarbarianHut', 'Witch') and not unchanged:
            changed_b1.append(key)
        results.append(dict(card=key[0], scenario=key[1], before=old_verdict, after=verdict,
                            before_differences=len(old_differences), differences=len(differences),
                            ours_unchanged=unchanged, details=differences))
    report = dict(total=len(results), b1_regressions=changed_b1, results=results,
                  note='Partial reference fidelity is reported; no all-card or Rune Giant enchantment certification.')
    with open(sys.argv[4], 'x') as f:
        json.dump(report, f, indent=2)
    require(not changed_b1, ('B1 measured observables changed; inspect before accepting', changed_b1))
else:
    raise SystemExit('probe OUT.jsonl | compare BEFORE.jsonl AFTER.jsonl OUT.json')
