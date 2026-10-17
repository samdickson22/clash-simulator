"""Check the full-game cold/warm/disk-loaded performance gate.

python reports/cards/levels/tools/perf_compare.py JOB_DIR --out RECEIPT.json
Inputs: cold-{before,after}-caseN.jsonl (two repeats), disk-after-caseN.jsonl,
none-before.jsonl and none-after.jsonl (cases 0,1,2). Outputs compact timings/hashes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def read(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def digest(row):
    r = row['result']
    assert row['failures'] == 0, row
    assert r['terminal'] and row['ticks_limit'] == 6001, (r['ticks'], row['ticks_limit'])
    return {key: r[key] for key in ('command_sha256', 'ticks', 'winner', 'towers', 'plays', 'accepted')}


def brief(row):
    return dict(case=row['case'], wall_seconds=row['wall_seconds'], cpu_seconds=row['result']['cpu_seconds'],
                exports=len(row['exports']), export_seconds=sum(r['seconds'] for r in row['exports']),
                builds=row['builds'], preparation_seconds=row.get('preparation_seconds'),
                max_decision_seconds=max((d['wall'] for d in row['decisions']), default=0.),
                **digest(row))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('job_dir', type=Path)
    ap.add_argument('--out', required=True, type=Path)
    a = ap.parse_args()
    rows = []
    before = read(a.job_dir / 'cold-before-case0.jsonl')
    assert len(before) == 2 and digest(before[0]) == digest(before[1])
    assert len(before[0]['exports']) == 363 and not before[1]['exports']
    for case in range(3):
        pair = read(a.job_dir / f'cold-after-case{case}.jsonl')
        disk = read(a.job_dir / f'disk-after-case{case}.jsonl')
        assert len(pair) == 2 and len(disk) == 1
        cold, warm = pair
        disk = disk[0]
        assert all(r['case'] == case and r['levels'] == 'max' for r in (cold, warm, disk))
        assert digest(cold) == digest(warm) == digest(disk)
        assert len(cold['exports']) == 363 and not warm['exports'] and not disk['exports']
        assert len(cold['builds']) == 3 and not warm['builds'] and not disk['builds']
        if case == 0:
            assert digest(cold) == digest(before[0])
        rows.append(dict(case=case, cold=brief(cold), warm=brief(warm), disk_loaded=brief(disk)))
    none_before = read(a.job_dir / 'none-before.jsonl')
    none_after = read(a.job_dir / 'none-after.jsonl')
    assert len(none_before) == len(none_after) == 3
    none = []
    for case, (old, new) in enumerate(zip(none_before, none_after)):
        assert old['case'] == new['case'] == case and old['levels'] == new['levels'] == 'none'
        assert digest(old) == digest(new) and not old['exports'] and not new['exports']
        none.append(dict(case=case, before=brief(old), after=brief(new)))
    result = dict(status='PASS', l16=rows, baseline_l16=[brief(r) for r in before], levels_none=none)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: L16 cold = warm = disk-loaded on 3 terminal cases; baseline L16 case 0 unchanged; '
          'levels=None unchanged on 3 terminal cases; zero failures')


if __name__ == '__main__':
    main()
