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
    repo = tmp_path
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.DEVNULL).decode().strip()
    def commit():
        names = [str(p.relative_to(repo)) for p in repo.rglob('*') if p.is_file() and '.git' not in p.parts]
        git('add', '--', *names)
        git('commit', '-qm', 'Synthetic health/reference evidence')
        return git('rev-parse', 'HEAD')
    def binding(name, revision):
        return dict(path=name, commit=revision, sha256=sha(repo / name))
    def seal(root, scope):
        files = {str(p.relative_to(repo / root)): sha(p) for p in (repo / root).rglob('*') if p.is_file()}
        write(repo / root / 'receipt-manifest.json', dict(scope=scope, status='complete', files=files))
    git('init', '-q');git('config', 'user.name', 'Synthetic Test');git('config', 'user.email', 'test@example.invalid')
    amendment = repo / R.AMENDMENT_PATH
    amendment.parent.mkdir(parents=True)
    source_root = Path(__file__).resolve().parents[3]
    shutil.copyfile(source_root / R.AMENDMENT_PATH, amendment)
    checker = repo / 'reports/explore/t1/check_reference.py'
    checker.parent.mkdir(parents=True)
    shutil.copyfile(Path(__file__).with_name('check_reference.py'), checker)
    hosts = ['127x01', '127x03', '127x08']
    completion = dict(reporting_complete=True, outcomes_sealed=True, counted_primary_blocks=2400,
                      counted_guard_blocks=600, completed_at_utc='2026-10-10T12:00:00Z',
                      counted_host_phases={h:['reporting'] for h in hosts})
    write(repo / 'completion.json', completion)
    first = commit()
    end = dict(schema='clasher.e4v3.end-evidence.v1', kind='counted-reporting',
               completion=dict(repository_path='completion.json', commit=first, sha256=sha(repo / 'completion.json')),
               phases=[dict(host=h, phase='reporting') for h in hosts])
    write(repo / 'end.json', end)
    measurement = repo / 'reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3'
    measurement.mkdir(parents=True)
    (measurement / 'measure_tiers.py').write_text('# synthetic measurement pin\n')
    write(repo / 'bundle' / 'tiers-pins.json', dict(files={}))
    entries = []
    for host in hosts:
        root = 'original/' + host
        write(repo / root / 'fleet-identity.json', dict(host=host, measurement_files={
            'measure_tiers.py':sha(measurement / 'measure_tiers.py')}))
        (repo / root / 'reference-raw.jsonl').write_text('{"synthetic":true}\n')
        seal(root, 'FLEET-REFERENCE')
        entries.append(dict(host=host, attempts=[dict(directory=str(repo / root),
            manifest_sha256=sha(repo / root / 'receipt-manifest.json'))]))
    descriptor = dict(schema='clasher.e4v3.fleet-pool.v2', hosts=entries,
                      context=dict(bundle=str(repo / 'bundle'), manifest_sha256=sha(repo / 'bundle' / 'tiers-pins.json')))
    write(repo / 'descriptor.json', descriptor)
    fleet = dict(scope='FLEET-POOL', amendment_1=True, hosts=hosts, excluded_hosts=[], nice=10, repeats=3,
                 physical_cores=True, reporting_load_profile=True, pooling='raw-host-times-repeat-v1',
                 end_evidence_sha256=sha(repo / 'end.json'), host_receipts={e['host']:dict(
                     manifest_sha256=e['attempts'][0]['manifest_sha256'], relative_to_pooled_median=1.,
                     reference_to_reporting_mean=1.) for e in entries})
    pooling = dict(scope='FLEET-POOL', amendment_1=True, excluded=[], included=hosts,
                   end_evidence_sha256=sha(repo / 'end.json'), descriptor_sha256=sha(repo / 'descriptor.json'),
                   attempts={e['host']:[dict(**e['attempts'][0], passes=True, technical_repeat_candidate=False)] for e in entries})
    for name, value in [('fleet_reference.json', fleet), ('pooling.json', pooling),
                        ('pool-complete.json', dict(scope='FLEET-POOL', completed=True, outcome_access=False, live_actions=False)),
                        ('speed-reference.json', {}), ('deadline-reference.json', {}), ('fleet-policy-agreement.json', {})]:
        write(repo / 'pool' / name, value)
    seal('pool', 'FLEET-POOL')
    manifest = json.loads((repo / 'pool' / 'receipt-manifest.json').read_text())
    check = dict(schema='clasher.t1.pool-check.v1', passes=True, checked_at_utc='2026-10-10T13:00:00Z',
                 outcome_access=False, checker_sha256=sha(checker), output_files=manifest['files'],
                 pool_manifest_sha256=sha(repo / 'pool' / 'receipt-manifest.json'), descriptor_sha256=sha(repo / 'descriptor.json'),
                 input_files=R.pool_inputs(repo / 'descriptor.json', measurement))
    write(repo / 'pool-check.json', check)
    registration = dict(fleet_reference=fleet, pooled_reference_manifest_sha256=check['pool_manifest_sha256'],
                        pool_check_sha256=sha(repo / 'pool-check.json'), deadline_replay_semantics='committed-copy',
                        corpus_receipt='corpus.json', sets=dict(speed={t:[f'{t}-{i}' for i in range(300)] for t in R.TIERS}),
                        source_receipts={})
    for name in ('speed-reference.json', 'deadline-reference.json'):
        (repo / 'packet').mkdir(exist_ok=True)
        shutil.copyfile(repo / 'pool' / name, repo / 'packet' / name)
    for name in ('golden.json', 'belief-reference.json', 'student-reference.json', 'corpus.json'):
        write(repo / 'packet' / name, dict(synthetic=True))
    for entry in entries:
        host = entry['host'];shutil.copytree(repo / 'original' / host, repo / 'packet' / 'sources' / host)
        registration['source_receipts'][host]=[dict(path=f'sources/{host}/receipt-manifest.json',
            manifest_sha256=entry['attempts'][0]['manifest_sha256'])]
    write(repo / 'packet' / 'registration.json', registration)
    seal('packet', 'T1-REGISTRATION')
    write(repo / 'summary.json', dict(synthetic=True))
    final = commit()
    prerelease = dict(schema='clasher.t1.amendment1-prerelease.v1', amendment=binding(R.AMENDMENT_PATH, first),
                      completion=binding('completion.json', first), end_evidence=binding('end.json', final),
                      descriptor=binding('descriptor.json', final), pool_manifest=binding('pool/receipt-manifest.json', final),
                      registration_manifest=binding('packet/receipt-manifest.json', final), pool_check=binding('pool-check.json', final))
    release = dict(coordinator_thread=COORDINATOR, authorized_at_utc='2026-10-24T12:00:00Z',
                   authorization_message_id='synthetic-only', reason='committed_mac_summary',
                   amendment_1_prerelease=prerelease, mac_summary_path='summary.json', commit=final,
                   mac_summary_sha256=sha(repo / 'summary.json'), reporting_completion_path='completion.json',
                   reporting_completion_sha256=prerelease['completion']['sha256'], completion_commit=first)
    def recommit(name, value):
        write(repo / name, value);return binding(name, commit())
    return repo, release, recommit


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
    (repo / 'original/127x03/reference-raw.jsonl').write_text('{"changed":true}')
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
    (lambda v:v.update(checked_at_utc='2026-10-10T11:59:59Z'), 'window'),
    (lambda v:v['input_files'].clear(), 'incomplete')])
def test_committed_invalid_pool_check_cannot_open(packet, mutate, match):
    repo, release, recommit=packet
    check=json.loads((repo / 'pool-check.json').read_text());mutate(check)
    release['amendment_1_prerelease']['pool_check']=recommit('pool-check.json', check)
    with pytest.raises(ValueError, match=match):R.prerequisites(repo, release)
