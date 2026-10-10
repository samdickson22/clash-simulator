"""Synthetic committed receipts test all pre-release routes; no game data."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
import release_reference as R
from barrier import COORDINATOR, outcome_release
from common import sha, write


@pytest.fixture
def packet(tmp_path):
    from test_reference_packet import make_packet
    return make_packet(tmp_path)


@pytest.mark.parametrize('reason', ['committed_mac_summary', 'fourteen_day_escape'])
def test_complete_committed_checked_packet_opens_either_route(packet, reason):
    repo, release, _ = packet;release['reason']=reason
    write(repo / 'release.json', release)
    assert outcome_release(repo, repo / 'release.json') == release


@pytest.mark.parametrize('reason', ['committed_mac_summary', 'fourteen_day_escape'])
@pytest.mark.parametrize('missing', ['pool_manifest', 'pool_check', 'registration_manifest'])
def test_no_route_bypasses_missing_amendment_artifact(packet, reason, missing):
    repo, release, _ = packet;release['reason']=reason
    del release['amendment_1_prerelease'][missing];write(repo / 'release.json', release)
    with pytest.raises((KeyError, ValueError)):outcome_release(repo, repo / 'release.json')


def test_uncommitted_registration_modification_is_denied(packet):
    repo, release, _ = packet
    (repo / 'packet/registration.json').write_text('{}')
    with pytest.raises(ValueError, match='committed SHA'):R.prerequisites(repo, release)


@pytest.mark.parametrize('change,match', [('host', 'counted host'), ('smoke', 'Smoke'), ('phase', 'counted phase')])
def test_population_and_smoke_mismatches_deny(packet, change, match):
    repo, release, recommit = packet;p=release['amendment_1_prerelease']
    if change=='host':
        x=json.loads((repo / 'descriptor.json').read_text());x['hosts'].pop()
        p['descriptor']=recommit('descriptor.json', x)
    else:
        x=json.loads((repo / 'end.json').read_text())
        if change=='smoke':x['kind']='unpoolable-smoke'
        else:x['phases'].pop()
        p['end_evidence']=recommit('end.json', x)
    with pytest.raises(ValueError, match=match):R.prerequisites(repo, release)


def test_changed_original_source_input_denies_even_with_intact_packet(packet):
    repo, release, _ = packet
    (repo / 'attempts/127x03/r0/speed-reference-raw.jsonl').write_text('{"changed":true}')
    with pytest.raises(ValueError, match='input pin mismatch'):R.prerequisites(repo, release)


@pytest.mark.parametrize('ratio', [.95, 1.05])
def test_signed_five_percent_bound_is_inclusive(ratio):R.within_five_percent(ratio)


@pytest.mark.parametrize('ratio', [.9499999, 1.0500001, float('nan'), float('inf'), True])
def test_invalid_signed_ratio_denies(ratio):
    with pytest.raises(ValueError):R.within_five_percent(ratio)


def test_symlink_and_path_traversal_cannot_substitute_commit(packet, tmp_path):
    repo, release, _ = packet
    for name in ('../completion.json', '/completion.json'):
        bad=dict(release['amendment_1_prerelease']['completion'], path=name)
        with pytest.raises(ValueError):R.committed(repo, bad)
    outside=tmp_path.parent / (tmp_path.name + '-outside.json');outside.write_text('{}')
    path=repo / 'completion.json';path.unlink();path.symlink_to(outside)
    with pytest.raises(ValueError, match='symlink'):R.committed(repo, release['amendment_1_prerelease']['completion'])


def test_recheck_output_difference_produces_no_check_receipt(tmp_path, monkeypatch):
    import check_reference as C
    pool=tmp_path / 'pool';pool.mkdir()
    for name in R.POOL_FILES:write(pool / name, {})
    write(pool / 'receipt-manifest.json', dict(scope='FLEET-POOL', status='complete',
        files={n:sha(pool / n) for n in R.POOL_FILES}))
    monkeypatch.setattr(C, 'pool_inputs', lambda *args:{'/synthetic':'a'*64})
    descriptor=tmp_path / 'descriptor.json';write(descriptor, {})
    def different(command, **kwargs):
        target=Path(command[-1]);target.mkdir()
        write(target / 'receipt-manifest.json', dict(scope='FLEET-POOL', status='complete', files={'different':'b'*64}))
    real_utc=C.utc();monkeypatch.setattr(C,'utc',lambda:real_utc)
    monkeypatch.setattr(C.subprocess, 'run', different)
    output=tmp_path / 'check.json'
    with pytest.raises(ValueError, match='differ'):C.check(descriptor, pool, tmp_path, output)
    assert not output.exists()


def replace_sealed(packet, key, root, name, mutate):
    repo, release, recommit=packet
    value=json.loads((repo / root / name).read_text());mutate(value)
    write(repo / root / name, value)
    seal=json.loads((repo / root / 'receipt-manifest.json').read_text())
    seal['files'][name]=sha(repo / root / name)
    release['amendment_1_prerelease'][key]=recommit(root + '/receipt-manifest.json', seal)
    return repo, release


@pytest.mark.parametrize('name,mutate,match', [
    ('fleet_reference.json', lambda v:v.update(excluded_hosts=['127x08']), 'exclusion'),
    ('fleet_reference.json', lambda v:v.update(repeats=2), 'profile'),
    ('fleet_reference.json', lambda v:v['host_receipts']['127x03'].update(reference_to_reporting_mean=1.051), 'five percent'),
    ('pool-complete.json', lambda v:v.update(outcome_access=True), 'completion'),
    ('pooling.json', lambda v:v['attempts']['127x03'][-1].update(passes=False), 'classification')])
def test_committed_but_invalid_pool_cannot_open(packet, name, mutate, match):
    repo, release=replace_sealed(packet, 'pool_manifest', 'pool', name, mutate)
    with pytest.raises(ValueError, match=match):R.prerequisites(repo, release)


@pytest.mark.parametrize('mutate,match', [
    (lambda v:v.update(pooled_reference_manifest_sha256='0'*64), 'lineage'),
    (lambda v:v.update(deadline_replay_semantics='resume'), 'replay'),
    (lambda v:v['sets']['speed']['K4'].pop(), '300-state'),
    (lambda v:v['source_receipts']['127x03'].clear(), 'reference attempt')])
def test_committed_but_invalid_registration_cannot_open(packet, mutate, match):
    repo, release=replace_sealed(packet, 'registration_manifest', 'packet', 'registration.json', mutate)
    with pytest.raises(ValueError, match=match):R.prerequisites(repo, release)


@pytest.mark.parametrize('mutate,match', [
    (lambda v:v.update(passes=False), 'recheck'),
    (lambda v:v.update(checked_at_utc='2026-10-10T00:59:59Z'), 'window'),
    (lambda v:v['input_files'].clear(), 'incomplete')])
def test_committed_invalid_pool_check_cannot_open(packet, mutate, match):
    repo, release, recommit=packet
    check=json.loads((repo / 'pool-check.json').read_text());mutate(check)
    release['amendment_1_prerelease']['pool_check']=recommit('pool-check.json', check)
    with pytest.raises(ValueError, match=match):R.prerequisites(repo, release)


@pytest.mark.parametrize('reason', ['committed_mac_summary', 'fourteen_day_escape'])
def test_committed_check_receipt_cannot_replace_barrier_reexecution(packet, monkeypatch, reason):
    import check_reference as C
    repo, release, _=packet;release['reason']=reason;calls=[]
    def failed(*args):
        calls.append(args);raise ValueError('Actual reexecution failed')
    monkeypatch.setattr(C,'check',failed);write(repo/'release.json',release)
    with pytest.raises(ValueError,match='Actual reexecution failed'):outcome_release(repo,repo/'release.json')
    assert len(calls)==1 and calls[0][0]==repo/'descriptor.json'


def test_omitted_failed_attempt_directory_denies_release(packet):
    repo, release, _=packet
    shutil.copytree(repo/'attempts/127x03/r0',repo/'attempts/127x03/failed-r0')
    with pytest.raises(ValueError,match='omitted.*original reference attempt'):R.prerequisites(repo,release)


def test_reference_attempt_root_cannot_hide_symlinked_attempt(packet):
    repo, release, _=packet
    (repo/'attempts/127x03/hidden').symlink_to(repo/'attempts/127x03/r0',target_is_directory=True)
    with pytest.raises(ValueError,match='only original attempt directories'):R.prerequisites(repo,release)


@pytest.mark.parametrize('field',['blind_ledger','counted_inventory'])
def test_final_committed_end_must_bind_completion_inventory_shas(packet,field):
    repo, release, recommit=packet
    end=json.loads((repo/'end.json').read_text());end[field]['sha256']='0'*64
    release['amendment_1_prerelease']['end_evidence']=recommit('end.json',end)
    with pytest.raises(ValueError,match='Completion differs from END '+field):R.prerequisites(repo,release)


def test_measurement_code_must_equal_committed_final_e4_source(packet):
    repo, release, _=packet
    e4=repo/'reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3'
    (e4/'fleet_end.py').write_text('# changed after commitment\n')
    with pytest.raises(ValueError,match='committed SHA'):R.prerequisites(repo,release)


def test_registration_ids_must_equal_checked_reference_keys(packet):
    repo, release=replace_sealed(packet,'registration_manifest','packet','registration.json',
                                lambda v:v['sets']['speed']['K4'].__setitem__(0,'wrong-state'))
    with pytest.raises(ValueError,match='speed IDs differ'):R.prerequisites(repo,release)


def test_registration_corpus_receipt_must_equal_measured_pin(packet):
    repo, release, recommit=packet
    write(repo/'packet/corpus.json',dict(changed=True))
    seal=json.loads((repo/'packet/receipt-manifest.json').read_text());seal['files']['corpus.json']=sha(repo/'packet/corpus.json')
    release['amendment_1_prerelease']['registration_manifest']=recommit('packet/receipt-manifest.json',seal)
    with pytest.raises(ValueError,match='corpus receipt differs'):R.prerequisites(repo,release)


def test_real_e4_recheck_success_ignores_inherited_pythonpath(packet,monkeypatch):
    import check_reference as C
    repo, release, _=packet;e4=repo/'reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3'
    shadow=repo/'hostile-pythonpath';shadow.mkdir();(shadow/'json.py').write_text('raise RuntimeError("shadowed")\n')
    monkeypatch.setenv('PYTHONPATH',str(shadow));output=repo/'second-real-check.json'
    result=C.check(repo/'descriptor.json',repo/'pool',e4,output)
    assert result['passes'] is True and result['output_files']==json.loads((repo/'pool/receipt-manifest.json').read_text())['files']
    assert result['input_files']==R.pool_inputs(repo/'descriptor.json',e4)
    assert '-I' in C.pool_command(e4,repo/'descriptor.json',repo/'unused')
    assert not (repo/'second-real-check.json.diagnostics/failure-health.json').exists()


def test_checker_retains_failure_health_stderr_and_e4_failure(tmp_path,monkeypatch):
    import check_reference as C
    pool=tmp_path/'pool';pool.mkdir()
    for name in R.POOL_FILES:write(pool/name,{})
    write(pool/'receipt-manifest.json',dict(scope='FLEET-POOL',status='complete',files={n:sha(pool/n) for n in R.POOL_FILES}))
    descriptor=tmp_path/'descriptor.json';write(descriptor,{})
    monkeypatch.setattr(C,'pool_inputs',lambda *args:{'/synthetic':'a'*64})
    def fail(command,**kwargs):
        target=Path(command[-1]);target.mkdir();write(target/'failure.json',dict(error='synthetic reference-only failure'))
        kwargs['stderr'].write('synthetic health diagnostic\n')
        raise subprocess.CalledProcessError(7,command)
    real_utc=C.utc();monkeypatch.setattr(C,'utc',lambda:real_utc)
    monkeypatch.setattr(C.subprocess,'run',fail);output=tmp_path/'check.json'
    with pytest.raises(subprocess.CalledProcessError):C.check(descriptor,pool,tmp_path,output)
    assert not output.exists();diagnostics=tmp_path/'check.json.diagnostics'
    assert json.loads((diagnostics/'failure-health.json').read_text())['returncode']==7
    assert json.loads((diagnostics/'e4-failure.json').read_text())['error']=='synthetic reference-only failure'
    assert (diagnostics/'stderr.txt').read_text()=='synthetic health diagnostic\n'
