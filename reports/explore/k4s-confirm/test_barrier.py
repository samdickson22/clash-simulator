"""PREREG-K4S release-barrier tests (replaces T1 test_barrier.py; r3 §4.5)."""
import json, subprocess
import pytest
from barrier import outcome_release, reporting_release, COORDINATOR
from common import write, sha


def git(root, *args): return subprocess.check_output(['git', '-C', str(root), *args]).decode().strip()


def repo_with_items(tmp_path, ratio_unavailable=False, tiers='tiers_summary'):
    git(tmp_path, 'init', '-q'); git(tmp_path, 'config', 'user.name', 'Synthetic'); git(tmp_path, 'config', 'user.email', 't@example.invalid')
    items = {}
    names = ['completion', 'production_checks', 'verifier_receipt', 'mac_procedure_manifest', tiers]
    names += ['ratio_unavailable_declaration'] if ratio_unavailable else ['end_reference', 'end_recheck']
    for n in names:
        body = dict(reporting_complete=True, outcomes_sealed=True, counted_primary_blocks=3000, counted_guard_blocks=900) if n == 'completion' else dict(item=n)
        write(tmp_path/f'{n}.json', body); items[n] = dict(path=f'{n}.json', sha256=sha(tmp_path/f'{n}.json'))
    git(tmp_path, 'add', '.'); git(tmp_path, 'commit', '-qm', 'synthetic release items')
    receipt = dict(coordinator_thread=COORDINATOR, authorized_at_utc='2026-10-13T00:00:00Z', authorization_message_id='synthetic',
                   study='PREREG-K4S', commit=git(tmp_path, 'rev-parse', 'HEAD'), items=items)
    return receipt


@pytest.mark.parametrize('ratio_unavailable,tiers', [(False, 'tiers_summary'), (True, 'tiers_release')])
def test_complete_release_opens(tmp_path, ratio_unavailable, tiers):
    receipt = repo_with_items(tmp_path, ratio_unavailable, tiers); release = tmp_path/'release.json'; write(release, receipt)
    assert outcome_release(tmp_path, release) == receipt


@pytest.mark.parametrize('drop', ['completion', 'production_checks', 'verifier_receipt', 'mac_procedure_manifest', 'tiers_summary', 'end_recheck'])
def test_any_missing_item_denies(tmp_path, drop):
    receipt = repo_with_items(tmp_path); del receipt['items'][drop]; release = tmp_path/'release.json'; write(release, receipt)
    with pytest.raises((AssertionError, KeyError)): outcome_release(tmp_path, release)


def test_tampered_item_and_wrong_coordinator_deny(tmp_path):
    receipt = repo_with_items(tmp_path); release = tmp_path/'release.json'
    bad = json.loads(json.dumps(receipt)); bad['items']['verifier_receipt']['sha256'] = '0'*64; write(release, bad)
    with pytest.raises(AssertionError): outcome_release(tmp_path, release)
    bad = dict(receipt, coordinator_thread='someone-else'); write(release, bad)
    with pytest.raises(AssertionError): outcome_release(tmp_path, release)
    write(tmp_path/'completion.json', dict(reporting_complete=True, outcomes_sealed=False, counted_primary_blocks=3000, counted_guard_blocks=900))
    write(release, receipt)
    with pytest.raises(AssertionError): outcome_release(tmp_path, release)  # working-tree bytes differ from the commit


def test_missing_explicit_freeze_denies_reporting(tmp_path):
    m = tmp_path/'manifest.json'; a = tmp_path/'authorization.json'; write(m, dict(status='FROZEN')); write(a, dict(coordinator_thread=COORDINATOR, r3_explicitly_frozen=False))
    with pytest.raises(AssertionError): reporting_release(tmp_path, m, a)
