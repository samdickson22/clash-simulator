"""Render already-sealed T11 evidence; no inference, calibration or gate changes."""
import argparse
import hashlib
import json
from pathlib import Path

RUNS = ('main-2026100821', 'main-2026100822')
ROLES = ('eval', 'eval_ood')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def number(value):
    if value is None:
        return 'unassessed'
    return format(value, '.9g')


def interval(value):
    return 'unassessed' if value is None else '['+', '.join(map(number, value))+']'


def verdict(value):
    return {True: 'PASS', False: 'FAIL', None: 'UNASSESSED'}[value]


def render(a):
    manifest = read(a.manifest)
    seal = read(Path(a.manifest).parent/'freeze.json')
    prereg = Path(a.manifest).parent/'PREREG.md'
    assert sha(a.manifest) == seal['manifest_sha256'] and sha(prereg) == seal['prereg_sha256']
    selection, release = read(a.selection), read(a.release)
    assert selection['manifest_sha256'] == release['manifest_sha256'] == sha(a.manifest)
    assert release['selection_sha256'] == sha(a.selection)
    assert set(selection['runs']) == set(release['runs']) == set(RUNS)
    assert sha(release['v1_report']) == release['v1_report_sha256']
    assert selection['primary'] == release['primary']
    assert selection['primary'] == min(RUNS, key=lambda r: (selection['runs'][r]['dev_joint_nll'], selection['runs'][r]['seed']))
    statistics = {}
    for path in a.statistics:
        item = read(path)
        key = (item['run'], item['role'])
        assert key not in statistics
        assert item['release_sha256'] == sha(a.release) and item['T11_manifest'] == sha(a.manifest)
        assert item['checkpoint_sha256'] == selection['runs'][key[0]]['checkpoint_sha256']
        assert item['rows'] > 0 and item['batches']
        statistics[key] = (path, item)
    analyses = {}
    for path in a.analyses:
        item = read(path)
        key = (item['run'], item['role'])
        assert key not in analyses and item['manifest_sha256'] == sha(a.manifest)
        assert item['checkpoint_sha256'] == selection['runs'][key[0]]['checkpoint_sha256']
        assert item['statistics_complete_sha256'] == sha(statistics[key][0])
        assert set(item['cohorts']) == {'c56', 's122'}
        analyses[key] = (path, item)
    expected = {(r, s) for r in RUNS for s in ROLES}
    assert set(analyses) == set(statistics) == expected
    roots = dict(value.split('=', 1) for value in a.runs)
    assert set(roots) == set(RUNS)
    primary = selection['primary']
    lines = ['# T11 v2 offline gate (a)', '',
             f"Primary entrant: **{primary}**, selected only by dev joint NLL. "
             f"V2 eval gate: **{verdict(analyses[primary, 'eval'][1]['both_cohorts_pass'])}**.", '',
             'OOD gates are diagnostic. The secondary seed cannot replace the primary based on these results.', '',
             f"PREREG SHA256: `{sha(prereg)}`. Executable manifest: `{sha(a.manifest)}`.",
             f"V1 published report: `{release['v1_report']}`, SHA256 `{release['v1_report_sha256']}`.",
             f"Selection SHA256: `{sha(a.selection)}`. Held-out release SHA256: `{sha(a.release)}`.", '',
             '## Training and selection', '']
    for run in RUNS:
        root = Path(roots[run]); chosen = selection['runs'][run]
        for filename, key in [('complete.json', 'complete_sha256'), ('train.jsonl', 'train_log_sha256'), ('segments.jsonl', 'segments_sha256')]:
            assert sha(root/filename) == chosen[key]
        complete = read(root/'complete.json')
        assert not complete['stopped_by_signal'] and (complete['epoch'] >= 6 or complete['bad_epochs'] >= 3)
        segments = [json.loads(l) for l in (root/'segments.jsonl').read_text().splitlines()]
        assert segments[-1]['status'] == 'complete'
        curve = []; last = None
        with (root/'train.jsonl').open() as f:
            for line in f:
                record = json.loads(line)
                if record['event'] == 'dev':
                    curve.append(record)
                elif record['event'] == 'step':
                    last = record
        best = min(curve, key=lambda r: (r['ema_joint_nll'], r['step']))
        assert best['step'] == chosen['step'] and best['ema_joint_nll'] == chosen['dev_joint_nll']
        checkpoint = root/f"best-dev-step-{chosen['step']:08d}.pt"
        assert sha(checkpoint) == chosen['checkpoint_sha256']
        calibration = release['runs'][run]['calibration']
        assert calibration['selection_sha256'] == sha(a.selection) and calibration['checkpoint_sha256'] == chosen['checkpoint_sha256']
        assert calibration['role'] == 'dev'
        lines += [f"### {run}", '',
                  f"Selected step {chosen['step']}; dev joint NLL {number(chosen['dev_joint_nll'])}. "
                  f"Checkpoint SHA256 `{chosen['checkpoint_sha256']}`.",
                  f"Completed epochs {complete['epoch']}; bad epochs {complete['bad_epochs']}; steps {complete['step']}; rows {complete['rows']}.",
                  f"Dev temperatures (gate/card/tile): {', '.join(map(number, calibration['temperatures']))}.",
                  f"Recorded trainer wall hours {number(sum(s['wall_seconds'] for s in segments)/3600)}; "
                  f"CPU hours {number(sum(s['cpu_seconds'] for s in segments)/3600)}. "
                  'Wall hours include loading, checkpointing and dev; they are not active GPU compute hours.',
                  f"Final segment cumulative loader-inclusive rows/s: {number(last['rows_per_second_including_loader'])}.", '',
                  '| Dev checkpoint step | EMA joint NLL |', '|---:|---:|']
        lines += [f"| {r['step']} | {number(r['ema_joint_nll'])} |" for r in curve]
        lines.append('')
    lines += ['## Separate cohort gates', '', '| Seed | Split | Corpus | A1 | A2 | A3 | A4 | All applicable |', '|---|---|---|---|---|---|---|---|']
    for run in RUNS:
        for role in ROLES:
            for corpus, c in analyses[run, role][1]['cohorts'].items():
                gates = c['gates']
                statuses = ['N/A (empty slice)' if name == 'A2' and not g['applicable'] else verdict(g['pass_']) for name, g in ((n, gates[n]) for n in ('A1', 'A2', 'A3', 'A4'))]
                lines.append('| '+' | '.join([run, role, corpus, *statuses, verdict(c['applicable_gate_pass'])])+' |')
    for run in RUNS:
        for role in ROLES:
            path, result = analyses[run, role]
            lines += ['', f'## {run}: {role}', '', f"Analysis artifact: `{path}`, SHA256 `{sha(path)}`.",
                      f"Statistics completion SHA256 `{result['statistics_complete_sha256']}`. "
                      'This artifact includes pooled diagnostics, per-card/arena and Battle Healer/Mirror slices, and calibration bins.']
            for corpus, c in result['cohorts'].items():
                g = c['gates']
                lines += ['', f"### {corpus}: {c['perspectives']} perspectives, {c['stored_rows']} stored rows", '',
                          '| Metric | Before calibration | After calibration | 95% CI after |', '|---|---:|---:|---|']
                for name, metric in c['after']['metrics'].items():
                    lines.append(f"| {name} | {number(c['before']['metrics'][name]['value'])} | {number(metric['value'])} | {interval(metric['ci95'])} |")
                lines += ['', '| A1 paired model-minus-frequency | Mean | 95% CI |', '|---|---:|---|']
                for name, metric in g['A1']['details'].items():
                    lines.append(f"| {name} | {number(metric['value'])} | {interval(metric['ci95'])} |")
                lines += ['', 'A2: '+('N/A, empty structural P16 slice.' if not g['A2']['applicable'] else json.dumps(g['A2']['details'], sort_keys=True)),
                          f"A3 passing/assessed/scoped: {g['A3']['passing_cards']}/{g['A3']['assessed_cards']}/{g['A3']['scoped_cards']}.",
                          'A3 significantly worse cards: '+(', '.join(k for k, v in g['A3']['cards'].items() if v['significantly_worse']) or 'none')+'.',
                          'A3 unassessed cards: '+(', '.join(k for k, v in g['A3']['cards'].items() if not v['n']) or 'none')+'.',
                          f"A4 calibrated gate ECE {number(g['A4']['ece'])}; bar ≤0.01."]
            if role == 'eval_ood':
                lines += ['', '| Corpus | Metric | OOD minus eval (descriptive) |', '|---|---|---:|']
                for corpus, c in result['cohorts'].items():
                    for name, metric in c['after']['metrics'].items():
                        reference = analyses[run, 'eval'][1]['cohorts'][corpus]['after']['metrics'][name]['value']
                        gap = None if metric['value'] is None or reference is None else metric['value']-reference
                        lines.append(f'| {corpus} | {name} | {number(gap)} |')
    lines += ['', '## Input provenance', '']
    lines += [f'- {name}: `{value}`.' for name, value in manifest.items() if name.endswith('_sha256')]
    return '\n'.join(lines)+'\n'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'selection', 'release', 'output'):
        p.add_argument('--'+name, required=True)
    p.add_argument('--analyses', nargs=4, required=True)
    p.add_argument('--statistics', nargs=4, required=True, help='Four statistics complete.json files')
    p.add_argument('--runs', nargs=2, required=True, help='RUN=/compute-host/run-directory')
    a = p.parse_args()
    text = render(a)
    with Path(a.output).open('x') as f:
        f.write(text)


if __name__ == '__main__':
    main()
