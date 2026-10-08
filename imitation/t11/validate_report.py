"""Synthetic report plumbing only. No store, model or held-out data access."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import tempfile
from types import SimpleNamespace
from imitation.t11.report import RUNS, ROLES, sha, render


def main():
    assert socket.gethostname() == '127x01'
    p = argparse.ArgumentParser(); p.add_argument('--output', required=True); a = p.parse_args()
    root = Path(tempfile.mkdtemp(prefix='t11-report-synthetic-', dir='/mpac/sdicks02/jobs/clasher'))
    def write(name, value):
        path = root/name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value)); return path
    manifest = write('manifest.json', {'store_manifest_sha256': 'synthetic-store'})
    prereg = write('PREREG.md', 'synthetic registration')
    write('freeze.json', {'manifest_sha256': sha(manifest), 'prereg_sha256': sha(prereg)})
    report = write('v1.md', 'synthetic v1 report')
    selection = {'manifest_sha256': sha(manifest), 'primary': RUNS[0], 'runs': {}}
    roots = []
    for i, run in enumerate(RUNS):
        r = root/run; r.mkdir(); roots.append(run+'='+str(r))
        complete = write(run+'/complete.json', dict(stopped_by_signal=False, epoch=6, bad_epochs=0, step=10, rows=81920))
        segments = write(run+'/segments.jsonl', dict(status='complete', wall_seconds=60, cpu_seconds=30))
        train = r/'train.jsonl'
        train.write_text(json.dumps(dict(event='step', rows_per_second_including_loader=1234))+'\n'+json.dumps(dict(event='dev', step=10, ema_joint_nll=.2+i/10))+'\n')
        ckpt = r/'best-dev-step-00000010.pt'; ckpt.write_bytes(b'synthetic checkpoint; no model')
        selection['runs'][run] = dict(seed=2026100821+i, step=10, dev_joint_nll=.2+i/10,
            checkpoint_sha256=sha(ckpt), complete_sha256=sha(complete), segments_sha256=sha(segments), train_log_sha256=sha(train))
    sel = write('selection.json', selection)
    release = dict(manifest_sha256=sha(manifest), selection_sha256=sha(sel), primary=RUNS[0],
                   v1_report=str(report), v1_report_sha256=sha(report), runs={})
    for run in RUNS:
        release['runs'][run] = dict(calibration=dict(role='dev', selection_sha256=sha(sel), checkpoint_sha256=selection['runs'][run]['checkpoint_sha256'], temperatures=[1, 2, 3]))
    rel = write('release.json', release); stats = []; analyses = []
    for run in RUNS:
        for role in ROLES:
            checkpoint = selection['runs'][run]['checkpoint_sha256']
            stat = write(run+'/'+role+'-complete.json', dict(run=run, role=role, release_sha256=sha(rel), T11_manifest=sha(manifest), checkpoint_sha256=checkpoint, rows=1, batches={'synthetic.npz': 'synthetic'}))
            stats.append(str(stat)); passed = run == RUNS[1]
            metric = dict(value=.1 if role == 'eval' else .2, n=1, ci95=[.05, .25])
            cohort = dict(perspectives=1, stored_rows=1, applicable_gate_pass=passed,
                          before={'metrics': {'joint_nll': metric}}, after={'metrics': {'joint_nll': metric}},
                          gates=dict(A1=dict(pass_=passed, details={'joint_nll': dict(value=-.1, ci95=[-.2, -.05])}),
                          A2=dict(applicable=False, pass_=None), A3=dict(pass_=True, passing_cards=1, assessed_cards=1, scoped_cards=1, cards={'1': dict(n=1, significantly_worse=False)}),
                          A4=dict(pass_=True, ece=.005)))
            analyses.append(str(write(run+'/'+role+'-analysis.json', dict(run=run, role=role, manifest_sha256=sha(manifest), checkpoint_sha256=checkpoint, statistics_complete_sha256=sha(stat), both_cohorts_pass=passed, cohorts={'c56': cohort, 's122': cohort}))))
    args = SimpleNamespace(manifest=str(manifest), selection=str(sel), release=str(rel), statistics=stats, analyses=analyses, runs=roots)
    rendered = render(args)
    assert 'V2 eval gate: **FAIL**' in rendered and 'N/A (empty slice)' in rendered
    assert '| main-2026100822 | eval | c56 | PASS' in rendered
    assert '| joint_nll | -0.1 | [-0.2, -0.05] |' in rendered
    assert '| c56 | joint_nll | 0.1 |' in rendered
    (root/'synthetic-result.md').write_text(rendered)
    report.write_text('changed synthetic report')
    try:
        render(args)
    except AssertionError:
        pass
    else:
        raise AssertionError('changed v1 report admitted')
    result = dict(passed=True, at=datetime.now(timezone.utc).isoformat(), synthetic_only=True,
                  checks=['failed primary retained despite passing secondary', 'N/A remains N/A', 'paired values and CIs unchanged', 'descriptive OOD gap', 'changed v1 hash rejected'],
                  renderer_sha256=sha(Path(__file__).with_name('report.py')), fixture=str(root))
    with Path(a.output).open('x') as f:
        json.dump(result, f, indent=2); f.write('\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
