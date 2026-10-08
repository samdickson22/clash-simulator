"""Coordinator-authorized store release, independent of continuing P16 scoring."""
from collections import Counter
import datetime as dt
import json
from pathlib import Path
import sys
import time

from finish_data import HERE, DATA, STORE, BASELINES, OPS, mirror, write
from verify_artifacts import sha


def publish():
    target = DATA/'receipts/T3-PASS.json'
    assert not target.exists(), 'Do not overwrite a published certificate'
    manifest = json.loads((STORE/'manifest.json').read_text())
    prereg = json.loads((BASELINES/'prereg.json').read_text())
    assert manifest['passed'] and manifest['roundtrip_exact']
    assert manifest['roundtrip_perspectives'] == 805
    assert sha(STORE/'manifest.json') == prereg['store_manifest']
    assert sha(HERE/'baselines.py') == prereg['recipe']
    assert sha(HERE/'p16_upgrade.py') == prereg['upgrade_adapter']
    roles_path = HERE.parent/'c56/data/roles/c56_roles_v1.json'
    assert sha(roles_path) == manifest['role_file_sha256']
    roles = json.loads(roles_path.read_text())
    assert sha(STORE/'plan.json') == manifest['plan_sha256']
    plan = json.loads((STORE/'plan.json').read_text())
    actual = Counter(); rows = Counter(); seen = set(); checked = 0
    for unit in plan['units']:
        receipt = json.loads((STORE/'units'/f"{unit['key']}.json").read_text())
        assert receipt['complete']
        checked += receipt['roundtrip_perspectives']
        for item in unit['perspectives']:
            identity = item['identity']; role = item['role']
            assert identity not in seen and roles['roles'][identity] == role
            seen.add(identity); actual[role] += 1; rows[role] += item['rows']
    assert checked == 805
    assert seen == {k for k,v in roles['roles'].items() if v in manifest['roles']}
    for role, counts in manifest['roles'].items():
        assert actual[role] == roles['counts'][role] == counts['perspectives']
        assert rows[role] == counts['rows']
        assert sha(STORE/role/'manifest.json') == manifest['role_manifests'][role]
    complete = json.loads((BASELINES/'frequency-complete.json').read_text())
    assert complete['passed']
    metrics = {'frequency-complete': complete, 'prereg': prereg}
    hashes = {n:sha(BASELINES/n) for n in ('prereg.json','frequency-complete.json','frequency-counts.npz')}
    for role in ('dev','eval','eval_ood'):
        name = f'frequency-{role}.json'
        value = json.loads((BASELINES/name).read_text())
        assert value['perspectives'] == actual[role]
        assert value['count_sha256'] == hashes['frequency-counts.npz']
        assert 0 < value['metrics']['rows'] <= rows[role]
        hashes[name] = sha(BASELINES/name); metrics[name[:-5]] = value
    result = dict(passed=True, published_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        decision='Coordinator: store and frequency baselines release training; P16 is gate A2 only',
        store=str(STORE), store_manifest_sha256=sha(STORE/'manifest.json'),
        roles=manifest['roles'], role_file_sha256=manifest['role_file_sha256'],
        roundtrip_perspectives=checked, roundtrip_exact=True, role_counts_equal=True,
        baselines=metrics, baseline_file_sha256=hashes, copies=[], copies_status='pending',
        copies_receipt=str(DATA/'receipts/T3-COPIES.json'), p16_baseline='pending',
        p16_label='imitation-data-finish-v1', p16_pid=3449355,
        p16_expected_completion_utc='2026-10-08T08:30:00Z',
        p16_expected_completion_note='Estimate from completed 648-perspective dev; eval has 705, OOD zero. Not a deadline.',
        p16_receipt=str(DATA/'receipts/T3-P16-BASELINE.json'))
    write(target,result)
    print(json.dumps(dict(published=str(target),sha256=sha(target),utc=result['published_utc'])),flush=True)


def copies():
    assert json.loads((DATA/'receipts/T3-PASS.json').read_text())['passed']
    done = []
    for host in ('127x04','127x08'):
        done.append(mirror(STORE,host,'store'))
        write(DATA/'receipts/T3-COPIES.json',dict(passed=len(done)==2,copies=done,
              certificate_sha256=sha(DATA/'receipts/T3-PASS.json')))


def p16():
    deadline = dt.datetime(2026,10,9,3,30,tzinfo=dt.timezone.utc)
    while not (BASELINES/'p16-complete.json').exists():
        assert dt.datetime.now(dt.timezone.utc) < deadline, 'P16 deadline reached'
        time.sleep(30)
    complete = json.loads((BASELINES/'p16-complete.json').read_text()); assert complete['passed']
    scores = {}
    for role, count in (('dev',648),('eval',705),('eval_ood',0)):
        value = json.loads((BASELINES/f'p16-bc-{role}.json').read_text())
        assert value['perspectives'] == count
        scores[role] = value
    write(DATA/'receipts/T3-P16-BASELINE.json',dict(passed=True,scores=scores,timing=complete,
          published_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
          files={p.name:sha(p) for p in BASELINES.glob('p16*.json')}))


if __name__ == '__main__':
    {'publish':publish,'copies':copies,'p16':p16}[sys.argv[1]]()
