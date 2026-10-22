"""Validate all six registered arms and report equal-seed paired comparisons."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bot.pretrain_v1 import rl_schedule as S, rl_evaluate as E
from bot.pretrain_v1.compare_arms import estimate


def load_arm(path, size):
    path = Path(path)
    config = json.loads((path/'config.json').read_text())
    S.require(config['size'] == size and config['seed'] in S.SEEDS, 'campaign arm identity')
    banks = S.validate_banks(json.loads(S.pinned(config['banks']).read_text()), config['seed'])
    cases = banks['primary']
    stopped = json.loads((path/'stopped.json').read_text()) if (path/'stopped.json').exists() else None
    if stopped is None:
        final = json.loads((path/'checkpoints/final-manifest.json').read_text())
        completed = json.loads((path/'completed.json').read_text())
        S.require(completed['status'] == 'training_complete' and completed['optimizer_resume_proof']
                  and final['generated'] == final['accepted'] == final['trained'] == 8388608
                  and final['discarded'] == 0 and final['updates'] == 32, 'unequal/incomplete training budget')
    scores, counts = {}, {}
    for phase in ('primary-bc', 'primary-final'):
        directory = path/'evaluation'/phase
        scores[phase] = {i: None for i in range(1600)}
        attempted = 0
        if directory.exists():
            manifest = json.loads((directory/'manifest.json').read_text())
            S.require(manifest['assigned'] == list(range(1600)) and manifest['bank_sha256'] == S.digest(cases),
                      'primary assignment mismatch')
            for index, case in enumerate(cases):
                row_path = directory/f'{index:04d}.json'
                if not row_path.exists():
                    continue
                attempted += 1
                row = json.loads(row_path.read_text())
                scores[phase][index] = E.validate_result(row, case, policy=manifest['policy_sha256'],
                                                        bank=manifest['bank_sha256'], runtime=manifest['runtime_manifest'])
        counts[phase] = dict(assigned=1600, attempted=attempted,
                             valid=sum(v is not None for v in scores[phase].values()))
    return dict(path=str(path), config=config, cases=cases, scores=scores, counts=counts,
                status='stopped' if stopped else 'completed', stopped=stopped)


def contrasts(a, b, *, complete=True):
    import numpy as np
    generator = np.random.Generator(np.random.PCG64(2026102023))
    result = {}
    for label, fa, fb in (('complete_pairs', None, None), ('all_assigned_lower', 0., 1.),
                          ('all_assigned_upper', 1., 0.)):
        diffs = {}
        for seed in S.SEEDS:
            values = []
            S.require(set(a[seed]) == set(b[seed]) == set(range(1600)), 'seed assignment mismatch')
            for index in range(1600):
                x = a[seed][index] if a[seed][index] is not None else fa
                y = b[seed][index] if b[seed][index] is not None else fb
                if x is not None and y is not None:
                    values.append(x-y)
            diffs[seed] = values
        point, ci = estimate(diffs, list(S.SEEDS), generator)
        result[label] = dict(delta=point, ci95=ci, n=sum(len(v) for v in diffs.values()),
                             per_seed_n={str(s): len(v) for s, v in diffs.items()})
    cp, lower = result['complete_pairs'], result['all_assigned_lower']
    result['a_wins_by_registered_rule'] = bool(complete and cp['ci95'] is not None and cp['ci95'][0] > 0
                                             and lower['delta'] > 0)
    result['eligible_equal_budget'] = complete
    return result


def summarize(m_paths, s_paths):
    arms = {}
    for size, paths in (('M', m_paths), ('S100', s_paths)):
        loaded = [load_arm(path, size) for path in paths]
        S.require(len(loaded) == 3 and {a['config']['seed'] for a in loaded} == set(S.SEEDS), 'all three fixed seeds required')
        arms[size] = {a['config']['seed']: a for a in loaded}
    for seed in S.SEEDS:
        m, s = arms['M'][seed], arms['S100'][seed]
        S.require(m['cases'] == s['cases'], 'unpaired primary banks across sizes')
        for key in ('populations', 'evaluation_populations', 'live', 'precision', 'hp1_checkpoint'):
            S.require(m['config'][key] == s['config'][key], 'cross-size frozen input mismatch: '+key)
    result = dict(endpoint='final update32 win; draws are not wins', seeds=list(S.SEEDS), seed_weights=[1/3]*3,
                  arms={size: {str(seed): {k: v for k, v in arm.items() if k in ('path', 'counts', 'status', 'stopped')}
                               for seed, arm in rows.items()} for size, rows in arms.items()}, per_seed={})
    for label, a_size, a_phase, b_size, b_phase in (
        ('M_minus_BC_M', 'M', 'primary-final', 'M', 'primary-bc'),
        ('S100_minus_BC_S100', 'S100', 'primary-final', 'S100', 'primary-bc'),
        ('M_minus_S100', 'M', 'primary-final', 'S100', 'primary-final')):
        a = {seed: arms[a_size][seed]['scores'][a_phase] for seed in S.SEEDS}
        b = {seed: arms[b_size][seed]['scores'][b_phase] for seed in S.SEEDS}
        complete = all(arms[size][seed]['status'] == 'completed' for size in {a_size, b_size} for seed in S.SEEDS)
        result[label] = contrasts(a, b, complete=complete)
        for seed in S.SEEDS:
            per = E.paired_bootstrap(a[seed], b[seed])
            per['eligible_equal_budget'] = all(arms[size][seed]['status'] == 'completed' for size in {a_size, b_size})
            per['a_wins_by_registered_rule'] &= per['eligible_equal_budget']
            result['per_seed'].setdefault(str(seed), {})[label] = per
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--M', nargs=3, required=True)
    p.add_argument('--S100', nargs=3, required=True)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    result = summarize(a.M, a.S100)
    with a.out.open('xb') as out:
        out.write(S.encoded(result)+b'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
