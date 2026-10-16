"""Paired pilot report; bootstrap 20,000 case resamples with NumPy seed 0.

Scores use clean terminal rows; failure counts cover every row. Deltas are arm minus baseline;
damage taken is positive HP lost. CPU/game includes both players and simulation,
while CPU/decision uses our seat's measured decision timing.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
from itertools import zip_longest
import json
import math
from pathlib import Path
import statistics

import numpy as np

from .run import REPO, identity_problems, parity_checks, row_issues, select_cases


def bootstrap(values):
    """Percentile CI of the paired mean; chunk draws to bound temporary memory."""
    values = np.asarray(values, dtype=float)
    if not len(values):
        return None
    rng = np.random.default_rng(0)
    means = np.empty(20_000)
    chunk = max(1, min(1000, 1_000_000 // len(values)))
    for start in range(0, len(means), chunk):
        count = min(chunk, len(means)-start)
        means[start:start+count] = values[rng.integers(len(values), size=(count, len(values)))].mean(axis=1)
    return np.percentile(means, [2.5, 97.5]).tolist()


def tower_hp(kind, level):
    """Client ladder curve: truncate the running integer percentage each level."""
    base, growth = (2400, 7) if kind == 'king' else (1400, 8)
    pct = 100
    for lv in range(2, int(level)+1):
        pct = pct * (100 + (growth if lv <= 9 else 10)) // 100
    return base * pct // 100


def side(value, seat):
    return value[seat] if isinstance(value, list) else value[str(seat)]


def damage(row, seat):
    if 'towers' not in row:
        return None
    hp = side(row['towers'], seat)
    if 'initial_towers' in row:
        maxima = side(row['initial_towers'], seat)
    else:
        level = row['profile']['towers'][seat]
        # RoyaleSim tower_hp is [king, left princess, right princess].
        maxima = [tower_hp(k, level) for k in ('king', 'princess', 'princess')]
    return sum(max(0, mx-h) for mx, h in zip(maxima, hp))


def mean(values):
    values = [v for v in values if v is not None]
    return statistics.mean(values) if values else None


def metrics(rows):
    timings = [side(r['timing'], r['seat']) for r in rows if 'timing' in r]
    decisions = sum(t['decisions'] for t in timings)
    outcomes = Counter('win' if r['score'] == 1 else 'draw' if r['score'] == .5 else 'loss' for r in rows)
    return dict(games=len(rows), mean_score=mean([r['score'] for r in rows]),
                wdl=[outcomes[k] for k in ('win', 'draw', 'loss')],
                damage_dealt=mean([damage(r, 1-r['seat']) for r in rows]),
                damage_taken=mean([damage(r, r['seat']) for r in rows]),
                crowns_for=mean([side(r['crowns'], r['seat']) for r in rows if 'crowns' in r]),
                crowns_against=mean([side(r['crowns'], 1-r['seat']) for r in rows if 'crowns' in r]),
                cpu_seconds_per_game=mean([r.get('cpu_seconds') for r in rows]),
                process_cpu_seconds_per_game=mean([r.get('process_cpu_seconds') for r in rows]),
                own_cpu_seconds_per_game=mean([t['cpu'] for t in timings]),
                cpu_seconds_per_decision=sum(t['cpu'] for t in timings)/decisions if decisions else None,
                decisions=decisions, wall_seconds_per_game=mean([r.get('wall_seconds') for r in rows]))


def first_difference(a, b):
    """First differing command, including a trailing command in either log."""
    for x, y in zip_longest(a, b):
        if x != y:
            return min(p[0] for p in (x, y) if p is not None)
    return None


def paired(pairs):
    deltas = [a['score']-b['score'] for a, b in pairs]
    sd = statistics.stdev(deltas) if len(deltas) > 1 else None
    hashes = [(a, b) for a, b in pairs if a.get('command_sha256') and b.get('command_sha256')]
    changed = [(a, b) for a, b in hashes if a['command_sha256'] != b['command_sha256']]
    ticks = [first_difference(a.get('play_log', []), b.get('play_log', [])) for a, b in changed]
    ticks = [t for t in ticks if t is not None]
    am, bm = metrics([a for a, _ in pairs]), metrics([b for _, b in pairs])
    delta_metrics = {k: am[k]-bm[k] if am[k] is not None and bm[k] is not None else None for k in
                     ('damage_dealt', 'damage_taken', 'crowns_for', 'crowns_against', 'cpu_seconds_per_game')}
    return dict(pairs=len(pairs), mean_delta_score=mean(deltas), ci95=bootstrap(deltas),
                delta_score_sd=sd, delta_score_variance=sd**2 if sd is not None else None,
                power_n_delta_005=math.ceil(((1.96+.84)*sd/.05)**2) if sd is not None else None,
                identical_commands=sum(a['command_sha256'] == b['command_sha256'] for a, b in hashes),
                command_pairs=len(hashes), identical_command_share=(len(hashes)-len(changed))/len(hashes) if hashes else None,
                differing_commands=len(changed), own_log_differences=len(ticks),
                first_difference_tick_median=statistics.median(ticks) if ticks else None,
                delta_metrics=delta_metrics)


def expected_run(directory):
    """Recover registered jobs from immutable launch receipts and their bank."""
    launches = sorted((p for p in directory.glob('launch-*.json')
                       if p.stem.removeprefix('launch-').isdigit()),
                      key=lambda p: int(p.stem.removeprefix('launch-')))
    if not launches and (directory / 'launch.json').exists():
        launches = [directory / 'launch.json']
    expected, cases, identities, problems = set(), {}, [], []
    gate, completion = False, None
    for path in launches:
        launch = json.loads(path.read_text())
        args = launch['args']
        gate |= args.get('all11_gate', False)
        problems += [f'{path.name}: {p}' for p in identity_problems(launch.get('identity'))]
        if 'identity' in launch:
            identities.append(launch['identity'])
        bank_path = Path(launch.get('bank_path', args['bank']))
        if not bank_path.is_absolute():
            bank_path = REPO / bank_path
        try:
            raw = bank_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != launch['bank_sha256']:
                raise ValueError('bank digest differs from launch')
            selected = select_cases(json.loads(raw), int(args['start']), int(args['count']))
            cases.update({c['index']: c for c in selected})
            registered = {(a, c['index']) for c in selected for a in args['arms'].split(',')}
            if 'expected' in launch and registered != {(j['arm'], j['index']) for j in launch['expected']}:
                raise ValueError('expected jobs differ from launch bank/range')
            expected.update(registered)
        except (OSError, ValueError, KeyError) as exc:
            problems.append(f'{path.name}: {exc}')
            expected.update((j['arm'], j['index']) for j in launch.get('expected', []))
        result_path = path.with_name(f'{path.stem}-result.json')
        completion = json.loads(result_path.read_text()) if result_path.exists() else None
    if identities and any(i != identities[0] for i in identities[1:]):
        problems.append('launch identities differ')
    identity = identities[-1] if identities and isinstance(identities[-1], dict) else None
    return dict(expected=expected, cases=cases, identity=identity,
                known=bool(launches), problems=problems, all11_gate=gate, completion=completion)


def summarize(directory, baseline='A'):
    directory = Path(directory)
    registered = expected_run(directory)
    expected = registered['expected']
    by, counts = defaultdict(dict), defaultdict(Counter)
    seen, raw_rows, duplicates, mismatches = set(), [], [], []
    for path in sorted((Path(directory) / 'rows').glob('*.json')):
        row = json.loads(path.read_text())
        arm = row['arm']
        key = arm, row['index']
        raw_rows.append(row)
        issues = row_issues(row)
        counts[arm].update(issues)
        if key in seen:
            duplicates.append(dict(arm=arm, index=row['index'], file=path.name))
        seen.add(key)
        identity = registered['identity']
        changed = [k for k, v in (identity or {}).items() if k not in row or row[k] != v]
        case = registered['cases'].get(row['index'])
        if case:
            changed += [k for k in ('seed', 'seat', 'opponent', 'decks', 'profile', 'view') if row.get(k) != case[k]]
        if changed:
            mismatches.append(dict(arm=arm, index=row['index'], fields=changed))
        if not any(issues.values()) and not changed:
            by[arm][row['index']] = row
    arms = {}
    all_arms = set(by) | set(counts) | {a for a, _ in expected}
    clean = {(a, i) for a, rows in by.items() for i in rows}
    for arm in sorted(all_arms, key=lambda a: (a != baseline, a)):
        rows = list(by[arm].values())
        entry = dict(metrics(rows), **counts[arm])
        for name in ('errors', 'native_failures', 'rejections', 'missing_diagnostics', 'child_failures', 'controller_prior_failures', 'nonterminal'):
            entry.setdefault(name, 0)
        entry['expected_games'] = sum(a == arm for a, _ in expected) if registered['known'] else None
        entry['missing_indices'] = sorted(i for a, i in expected - seen if a == arm)
        entry['incomplete_indices'] = sorted(i for a, i in expected - clean if a == arm)
        entry['opponents'] = {o: metrics([r for r in rows if r['opponent'] == o]) for o in ('R3a', 'v1')}
        if arm != baseline:
            pairs = [(by[arm][i], by[baseline][i]) for i in sorted(set(by[arm]) & set(by[baseline]))]
            for a, b in pairs:
                if any(a.get(k) != b.get(k) for k in ('seed', 'seat', 'opponent', 'decks', 'profile', 'view')):
                    raise ValueError(f'case mismatch: {arm}/{a["index"]} vs {baseline}')
            entry['paired'] = paired(pairs)
            indices = {i for a, i in expected if a == arm and (baseline, i) in expected}
            entry['paired']['expected_pairs'] = len(indices) if registered['known'] else None
            entry['paired']['missing_indices'] = sorted(i for i in indices if (arm, i) not in clean or (baseline, i) not in clean)
            entry['paired']['opponents'] = {o: paired([(a, b) for a, b in pairs if a['opponent'] == o])
                                            for o in ('R3a', 'v1')}
        arms[arm] = entry
    checks = parity_checks(raw_rows, sorted({i for _, i in expected})) if registered['all11_gate'] else None
    completion = registered['completion']
    coverage = dict(known=registered['known'], expected_rows=len(expected) if registered['known'] else None,
        observed_rows=len(raw_rows), missing_rows=[dict(arm=a, index=i) for a, i in sorted(expected-seen)],
        incomplete_rows=[dict(arm=a, index=i) for a, i in sorted(expected-clean)],
        unexpected_rows=[dict(arm=a, index=i) for a, i in sorted(seen-expected)] if registered['known'] else [],
        duplicate_rows=duplicates, identity_mismatches=mismatches, problems=registered['problems'],
        parent_exit_code=completion.get('exit_code') if completion else None)
    quality = (registered['known'] and bool(expected) and not any(coverage[k] for k in
        ('missing_rows', 'incomplete_rows', 'unexpected_rows', 'duplicate_rows', 'identity_mismatches', 'problems'))
        and completion is not None and completion['exit_code'] == 0
        and all(not any(row_issues(r).values()) for r in raw_rows)
        and (checks is None or all(checks.values())))
    return dict(baseline=baseline, bootstrap=dict(resamples=20_000, seed=0, interval='percentile 95%'),
                arms=arms, coverage=coverage, quality_ok=quality, all11_checks=checks)


def fmt(value):
    return '—' if value is None else f'{value:.3f}'


def markdown(report):
    c = report['coverage']
    lines = [f"Recorded evidence: {'complete and clean' if report['quality_ok'] else 'incomplete, invalid, or unregistered'}; "
             f"rows {c['observed_rows']}/{c['expected_rows'] if c['known'] else 'unknown'}; "
             f"missing {len(c['missing_rows'])}, incomplete {len(c['incomplete_rows'])}; parent exit {c['parent_exit_code']}.", '',
             '| arm | games | errors | score | W/D/L | damage dealt/taken | crowns for/against | CPU s/game | CPU s/decision | wall s/game |',
             '|---|---:|---:|---:|---|---|---|---:|---:|---:|']
    for arm, s in report['arms'].items():
        lines.append(f"| {arm} | {s['games']} | {s['errors']} | {fmt(s['mean_score'])} | {'/'.join(map(str, s['wdl']))} | "
                     f"{fmt(s['damage_dealt'])}/{fmt(s['damage_taken'])} | {fmt(s['crowns_for'])}/{fmt(s['crowns_against'])} | "
                     f"{fmt(s['cpu_seconds_per_game'])} | {fmt(s['cpu_seconds_per_decision'])} | {fmt(s['wall_seconds_per_game'])} |")
    for arm, s in report['arms'].items():
        lines += ['', f"{arm}: native failures={s['native_failures']}, rejected deployments={s['rejections']}, "
                  f"child failures={s['child_failures']}, nonterminal={s['nonterminal']}; "
                  f"missing diagnostics={s['missing_diagnostics']}; "
                  f"controller prior failures={s['controller_prior_failures']}; "
                  f"missing indices={s['missing_indices']}, incomplete indices={s['incomplete_indices']}."]
        if 'paired' in s:
            p = s['paired']
            lines += [f"Pairs vs {report['baseline']}: {p['pairs']}/{p['expected_pairs'] if p['expected_pairs'] is not None else 'unknown'}; "
                      f"missing paired indices={p['missing_indices']}."]
    if report['all11_checks'] is not None:
        lines += ['', 'All11 evidence checks (no general pilot-readiness claim): ' + '; '.join(
            f'{name}={value}' for name, value in report['all11_checks'].items()) + '.']
    if c['problems'] or c['identity_mismatches'] or c['duplicate_rows'] or c['unexpected_rows']:
        lines += ['', 'Coverage/provenance details: ' + json.dumps({k: c[k] for k in
            ('problems', 'identity_mismatches', 'duplicate_rows', 'unexpected_rows')}, sort_keys=True)]
    lines += ['', f"Paired Δ = arm − {report['baseline']}; 95% percentile bootstrap, 20,000 resamples, NumPy seed 0.", '',
              '| arm / opponent | pairs | Δscore [95% CI] | SD(Δ) | identical commands | first differing own tick (median) |',
              '|---|---:|---|---:|---:|---:|']
    for arm, s in report['arms'].items():
        if 'paired' not in s:
            continue
        for label, p in [('all', s['paired']), *s['paired']['opponents'].items()]:
            ci = f"[{fmt(p['ci95'][0])}, {fmt(p['ci95'][1])}]" if p['ci95'] else '—'
            lines.append(f"| {arm} / {label} | {p['pairs']} | {fmt(p['mean_delta_score'])} {ci} | {fmt(p['delta_score_sd'])} | "
                         f"{fmt(p['identical_command_share'])} | {fmt(p['first_difference_tick_median'])} |")
        p = s['paired']
        lines += ['', f"{arm}: n = {p['power_n_delta_005'] if p['power_n_delta_005'] is not None else 'unavailable'} paired cases "
                  'for 80% power, α=0.05 two-sided, Δ=0.05: ceil(((1.96+0.84) SD / 0.05)²).',
                  f"Paired Δ damage dealt/taken: {fmt(p['delta_metrics']['damage_dealt'])}/{fmt(p['delta_metrics']['damage_taken'])}; "
                  f"Δ crowns for/against: {fmt(p['delta_metrics']['crowns_for'])}/{fmt(p['delta_metrics']['crowns_against'])}."]
    lines += ['', 'CPU/game is match process CPU (both seats and simulation); CPU/decision is our seat’s total decision CPU / decisions. '
              'Wall/game is each child’s elapsed time; runtime initialization is excluded. '
              'A differing full command hash can have identical own play logs; those pairs have no own divergence tick. '
              'Power uses observed sample SD; zero observed SD gives a zero plug-in estimate, not evidence of adequate power.']
    for arm, s in report['arms'].items():
        lines += ['', f"{arm} opponent scores: " + '; '.join(
            f"{o} n={v['games']}, score={fmt(v['mean_score'])}, W/D/L={'/'.join(map(str, v['wdl']))}"
            for o, v in s['opponents'].items()) + '.']
    return '\n'.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('directory', type=Path)
    ap.add_argument('--baseline', default='A')
    args = ap.parse_args(argv)
    report = summarize(args.directory, args.baseline)
    from .run import write_json
    write_json(args.directory / 'report.json', report)
    print(markdown(report))
    return int(not report['quality_ok'])


if __name__ == '__main__':
    raise SystemExit(main())
