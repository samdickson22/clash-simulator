"""Publish the combined Markdown only from final verified metadata on05.

No scientific imports, new reduction, remote launch, or adoption authority.
Run after collect_evaluation.py, independent vacancy publication, and
render_metadata.py. Timer deletion and coordinator notification remain explicit.
"""
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = '<!-- R3-EXTENSION-STATUS -->'


def verified(path):
    data = json.loads(path.read_text())
    assert hashlib.sha256(data['raw'].encode()).hexdigest() == data['sha256']
    assert json.loads(data['raw']) == data['value']
    return data['value']


def validate_final(cost, combined, stage1, descriptive, stage2, vacancies):
    assert cost['final'] and cost['scientific_complete'] and cost['vacancy_complete'], 'Extension still pending'
    assert combined['final'], 'Combined costs still pending'
    for ledger in (cost, combined):
        assert len({m['sha256'] for m in ledger['meters']}) == len(ledger['meters']), 'Duplicate whole-tree meter'
        for key in ('cpu_seconds', 'gpu_wall_seconds'):
            assert abs(sum(m[key] for m in ledger['meters'])-ledger[key]) < 1e-6, 'Cost total mismatch'
    assert set(stage1) == {'R3c', 'R3d', 'R3e'}
    for arm in stage1.values():
        assert arm['stage1_complete'] and len(arm['regret_game_proofs']) == 64
        assert {p['index'] for p in arm['regret_game_proofs']} == set(range(64))
    assert descriptive['paired_seeds'] == 600 and descriptive['never_adoptable']
    assert not descriptive['live_adoption'] and not descriptive['arms']['R3a']['survives']
    assert len(descriptive['block_proofs']) == 600
    if any(arm['survives'] for arm in stage1.values()):
        assert stage2 and stage2['paired_seeds'] == 600 and not stage2['never_adoptable']
        assert not stage2['live_adoption'] and len(stage2['block_proofs']) == 600
        assert set(stage2['arms']) == {'K0'} | {a for a, v in stage1.items() if v['survives']}
    else:
        assert stage2 is None, 'Reporting must not include killed arms'
    assert len(vacancies) == 5
    for receipt in vacancies:
        assert receipt['all_recorded_groups_absent'] and receipt['observer_independently_absent']
        assert not receipt.get('gpu_owned_pids', [])


def main():
    receipts = ROOT/'receipts'
    read = lambda path: json.loads(path.read_text())
    cost = read(receipts/'cost-summary.json')
    combined = read(receipts/'combined-cost-summary.json')
    # Fail before reading absent decisions or writing anything if still pending.
    assert cost['final'], 'Extension still pending; root RESULTS unchanged'
    snapshots = receipts/'evaluation-snapshots'
    stage1 = verified(snapshots/'127x03/stage1-results.json')
    descriptive = verified(snapshots/'127x01/descriptive-results.json')
    stage2_path = snapshots/'127x03/timing03--stage2-results.json'
    stage2 = verified(stage2_path) if stage2_path.exists() else None
    vacancies = [verified(snapshots/host/'EVAL-VACATED.json') for host in
                 ('127x09', '127x16', '127x13', '127x01', '127x03')]
    validate_final(cost, combined, stage1, descriptive, stage2, vacancies)
    report = (ROOT/'RESULTS.md').read_text()
    assert report.startswith('# R3 extended results — complete\n')
    target = ROOT.parent/'RESULTS.md'
    original = target.read_text().split(MARKER, 1)[0]
    original = '\n'.join(line for line in original.splitlines()
                         if not line.startswith('Coordinator-authorized round2 and never-adoptable R3a study are pending'))
    # Make extension-relative evidence links work from the combined report.
    report = re.sub(r'\]\(([^)]+)\)', lambda m: ']('+m[1]+')' if
                    m[1].startswith(('/', '#')) or '://' in m[1] else '](round2/'+m[1]+')', report)
    text = original.rstrip()+'\n\n'+MARKER+'\n\n'+report
    tmp = target.with_suffix('.md.tmp')
    tmp.write_text(text)
    tmp.replace(target)
    receipt = dict(utc=subprocess.check_output(['date', '-u', '+%FT%TZ'], text=True).strip(),
                   scientific_complete=True, vacancy_complete=True, live_adoption=False,
                   root_results_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                   extended_results_sha256=hashlib.sha256((ROOT/'RESULTS.md').read_bytes()).hexdigest(),
                   combined_cost_sha256=hashlib.sha256((receipts/'combined-cost-summary.json').read_bytes()).hexdigest(),
                   cpu_seconds=combined['cpu_seconds'], gpu_wall_seconds=combined['gpu_wall_seconds'],
                   coordinator_notification_pending=True, continuation_deletion_pending=True)
    (receipts/'final-publication.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
