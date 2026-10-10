"""Metadata-only, two-session final vacancy and atomic S1 CPU release."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--job', type=Path, required=True)
    ap.add_argument('--mode', choices=('prepare', 'publish'), required=True)
    ap.add_argument('--publication-commit', required=True)
    a = ap.parse_args()
    j = a.job
    sys.path.insert(0, str(j / 'repo/reports/explore/s1'))
    from host_audit import main as audit_main, processes, release_gate, utc
    from supervise import runtime_guard

    assert os.uname().nodename == '127x01'
    assert subprocess.check_output(['who'], text=True) == ''
    assert not (j / 'S1-CPU-RELEASE.json').exists()
    audit = j / ('host-audit-release-' + a.mode + '.json')
    original_argv = sys.argv
    sys.argv = ['host_audit.py', '--job', str(j), '--out', str(audit), '--final']
    try:
        audit_main()
    finally:
        sys.argv = original_argv
    census = json.loads(audit.read_text())
    assert not census['foreign_compute'] and not census['foreign_active']
    assert not census['own_compute']
    prepared = j / 'S1-CPU-RELEASE.prepared.json'
    if a.mode == 'prepare':
        pin = runtime_guard(j)
        assert (j / 'ANALYSIS-COMPLETE').exists()
        paths = set(j.glob('*pid.json')) | set(j.glob('meters/*.json'))
        paths |= set(j.glob('*/launch.json')) | set(j.glob('attempts/*/launch.json'))
        paths |= set(j.glob('attempts/**/*pid.json'))
        paths |= set(j.glob('attempts/*/failure.json'))
        groups, pids, inventory = set(), set(), {}
        for p in sorted(paths):
            r = json.loads(p.read_text())
            inventory[str(p.relative_to(j))] = sha(p)
            for k, v in r.items():
                if isinstance(v, int) and not isinstance(v, bool) and k.endswith('pgid'):
                    groups.add(v)
                elif isinstance(v, int) and not isinstance(v, bool) and k.endswith('pid'):
                    pids.add(v)
        assert {3372782, 3372820, 3392665, 3392678, 3422967,
                3422984, 4055560, 4058693} <= groups
        rows = processes()
        assert not [r for r in rows if r['pgid'] in groups or r['pid'] in pids]
        assert json.loads((j / 'statistics-verification.json').read_text())
        result = dict(
            prepared_at_utc=utc(), host='127x01', publication_commit=a.publication_commit,
            preparer_pid=os.getpid(), all_recorded_pgids=sorted(groups),
            all_recorded_pids=sorted(pids), inventory_sha256=inventory,
            runtime_pin_sha256=sha(j / 'runtime-pin.json'),
            source_files_verified=len(pin['files']),
            results_sha256=sha(j / 'results.json'),
            first_vacancy_census_path=str(audit), first_vacancy_census_sha256=sha(audit),
            r3_release_evidence_sha256=release_gate(j)['evidence_sha256'],
        )
        prepared.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({'prepared_path': str(prepared), 'prepared_sha256': sha(prepared),
                          'recorded_pgids': len(groups), 'recorded_pids': len(pids)}))
    else:
        r = json.loads(prepared.read_text())
        assert r['publication_commit'] == a.publication_commit
        for path, expected in r['inventory_sha256'].items():
            assert sha(j / path) == expected, path
        assert sha(j / 'runtime-pin.json') == r['runtime_pin_sha256']
        assert sha(j / 'results.json') == r['results_sha256']
        rows = processes()
        assert not [p for p in rows if p['pgid'] in r['all_recorded_pgids']
                    or p['pid'] in r['all_recorded_pids']
                    or p['pid'] == r['preparer_pid']]
        release_gate(j)
        r.update(
            released_at_utc=utc(), released=True, reporting_complete=True,
            analysis_complete=True, no_further_s1_cpu_calls_on01=True,
            all_recorded_groups_and_pids_absent=True, scoring_pools_drained=True,
            who='', foreign_compute_count=0, foreign_active_count=0, own_compute_count=0,
            physical_cores=list(range(40)), r3a_original_status='NEVER-ADOPTABLE',
            prepared_sha256=sha(prepared),
            second_vacancy_census_path=str(audit), second_vacancy_census_sha256=sha(audit),
            independent_second_session_checked_first_observer_absent=True,
            claims='Historical launch claims retained; no active S1 scoring pool or process.',
        )
        temp = j / 'S1-CPU-RELEASE.json.tmp'
        target = j / 'S1-CPU-RELEASE.json'
        temp.write_text(json.dumps(r, indent=2) + '\n')
        os.replace(temp, target)
        print(json.dumps({'release_path': str(target), 'release_sha256': sha(target),
                          'release': r}))


if __name__ == '__main__':
    main()
