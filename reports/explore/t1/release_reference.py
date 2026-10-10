"""Amendment 1 prerequisites, checked before any reporting outcome is read."""
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from common import sha

AMENDMENT_SHA = 'b35bd4e5d8beaf8e89ade092bdf4fc607e067e562f7d9f378fb9c06367df2775'
AMENDMENT_PATH = 'reports/strategy_council_20260928/live-loop/v4/PREREG-SEARCH-TIERS-AMENDMENT-1-20261010.md'
TIERS = {'K0c', 'S', 'K2', 'K4'}
POOL_FILES = {'fleet-policy-agreement.json', 'speed-reference.json', 'deadline-reference.json',
              'pooling.json', 'fleet_reference.json', 'pool-complete.json'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def relative(name):
    require(isinstance(name, str) and bool(name), 'Missing relative artifact path')
    p = Path(name)
    require(not p.is_absolute() and '..' not in p.parts and bool(p.parts), 'Artifact path escapes its root')
    return p


def stamp(value):
    t = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(t.utcoffset() is not None, 'Timestamp requires a timezone')
    return t.astimezone(timezone.utc)


def beneath(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def committed(repo, binding):
    repo = Path(repo).resolve()
    name = relative(binding['path'])
    require(re.fullmatch('[0-9a-f]{40}', binding['commit']) is not None, 'Full commit required')
    require(re.fullmatch('[0-9a-f]{64}', binding['sha256']) is not None, 'Full SHA required')
    path = (repo / name).resolve()
    require(beneath(path, repo), 'Artifact symlink escapes repository')
    raw = subprocess.check_output(['git', '-C', str(repo), 'show', binding['commit'] + ':' + str(name)])
    subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', binding['commit'], 'HEAD'], check=True)
    require(hashlib.sha256(raw).hexdigest() == binding['sha256'] and path.read_bytes() == raw,
            'Artifact differs from its committed SHA: ' + str(name))
    return raw


def obj(repo, binding):
    return json.loads(committed(repo, binding))


def sealed(repo, binding, scope):
    manifest = obj(repo, binding)
    require(manifest['scope'] == scope and manifest['status'] == 'complete', 'Incomplete/wrong-scope seal')
    root = relative(binding['path']).parent
    files = manifest['files']
    require(isinstance(files, dict) and bool(files), 'Empty sealed inventory')
    for name, digest in files.items():
        committed(repo, dict(path=str(root / relative(name)), commit=binding['commit'], sha256=digest))
    return manifest, Path(repo) / root


def within_five_percent(value):
    require(type(value) in (int, float), 'Invalid signed ratio')
    d = Decimal(str(value))
    require(d.is_finite() and abs(d - 1) <= Decimal('0.05'), 'Reference ratio outside inclusive five percent')


def pool_inputs(descriptor_path, measurement_root):
    """SHA inventory of the exact health/reference inputs read by E4 pooling."""
    descriptor_path = Path(descriptor_path).resolve()
    request = json.loads(descriptor_path.read_text())
    files = {str(descriptor_path): sha(descriptor_path)}
    def include(path, digest):
        path = Path(path).resolve()
        require(sha(path) == digest, 'Reference input pin mismatch: ' + str(path))
        require(str(path) not in files or files[str(path)] == digest, 'Conflicting input pins')
        files[str(path)] = digest
    def inventory(root, manifest):
        root = Path(root).resolve()
        for name, digest in manifest['files'].items():
            path = (root / relative(name)).resolve()
            require(beneath(path, root), 'Reference input escapes source bundle')
            include(path, digest)
    context = request['context']
    bundle = Path(context['bundle']).resolve()
    seal = bundle / 'tiers-pins.json'
    include(seal, context['manifest_sha256'])
    inventory(bundle, json.loads(seal.read_text()))
    for host in request['hosts']:
        for entry in host['attempts']:
            root = Path(entry['directory']).resolve()
            seal = root / 'receipt-manifest.json'
            include(seal, entry['manifest_sha256'])
            inventory(root, json.loads(seal.read_text()))
            identity = json.loads((root / 'fleet-identity.json').read_text())
            for name, digest in identity['measurement_files'].items():
                include(Path(measurement_root) / relative(name), digest)
    return files


def prerequisites(repo, release):
    """Both release routes require the same committed, checked END reference."""
    p = release['amendment_1_prerelease']
    require(p['schema'] == 'clasher.t1.amendment1-prerelease.v1', 'Unsupported pre-release evidence')
    require(p['amendment']['path'] == AMENDMENT_PATH and p['amendment']['sha256'] == AMENDMENT_SHA,
            'Wrong frozen Amendment 1')
    committed(repo, p['amendment'])
    completion = obj(repo, p['completion'])
    require(completion['reporting_complete'] is True and completion['outcomes_sealed'] is True,
            'Reporting must be complete and sealed')
    require(type(completion['counted_primary_blocks']) is int and completion['counted_primary_blocks'] == 2400
            and type(completion['counted_guard_blocks']) is int and completion['counted_guard_blocks'] == 600,
            'Incomplete counted population')
    phases = completion['counted_host_phases']
    require(isinstance(phases, dict) and bool(phases) and set(phases) <= {'127x01', '127x03', '127x08'},
            'Unknown/empty counted host population')
    for names in phases.values():
        require(isinstance(names, list) and len(set(names)) == len(names) and 'reporting' in names
                and all(n == 'reporting' or re.fullmatch('replacement-r[1-9][0-9]*', n) for n in names),
                'Invalid counted phase inventory')
    hosts = set(phases)
    end = obj(repo, p['end_evidence'])
    require(end['schema'] == 'clasher.e4v3.end-evidence.v1' and end['kind'] == 'counted-reporting',
            'Smoke evidence cannot open outcomes')
    require(end['completion']['repository_path'] == p['completion']['path']
            and end['completion']['commit'] == p['completion']['commit']
            and end['completion']['sha256'] == p['completion']['sha256'], 'Different END completion')
    wanted = {(h, n) for h, names in phases.items() for n in names}
    require(len(end['phases']) == len(wanted) and {(x['host'], x['phase']) for x in end['phases']} == wanted,
            'END omits a counted phase')
    descriptor = obj(repo, p['descriptor'])
    require(descriptor['schema'] == 'clasher.e4v3.fleet-pool.v2', 'All-attempt v2 descriptor required')
    entries = descriptor['hosts']
    require(len(entries) == len(hosts) and {e['host'] for e in entries} == hosts, 'Pool omits a counted host')
    require(all(1 <= len(e['attempts']) <= 2 for e in entries), 'Invalid reference attempt inventory')
    manifest, pool = sealed(repo, p['pool_manifest'], 'FLEET-POOL')
    require(POOL_FILES <= set(manifest['files']), 'Missing pooled outputs')
    complete = json.loads((pool / 'pool-complete.json').read_text())
    require(complete['scope'] == 'FLEET-POOL' and complete['completed'] is True
            and complete['outcome_access'] is False and complete['live_actions'] is False, 'Invalid pool completion')
    fleet = json.loads((pool / 'fleet_reference.json').read_text())
    pooling = json.loads((pool / 'pooling.json').read_text())
    require(fleet['amendment_1'] is True and pooling['amendment_1'] is True
            and fleet['excluded_hosts'] == [] and pooling['excluded'] == [], 'Counted host exclusion forbidden')
    require(len(fleet['hosts']) == len(hosts) and set(fleet['hosts']) == hosts
            and len(pooling['included']) == len(hosts) and set(pooling['included']) == hosts,
            'Pooled host population differs')
    require(fleet['nice'] == 10 and fleet['repeats'] == 3 and fleet['physical_cores'] is True
            and fleet['reporting_load_profile'] is True and fleet['pooling'] == 'raw-host-times-repeat-v1',
            'Wrong reference load/repeats/core profile')
    require(fleet['end_evidence_sha256'] == pooling['end_evidence_sha256'] == p['end_evidence']['sha256']
            and pooling['descriptor_sha256'] == p['descriptor']['sha256'], 'Pool lineage mismatch')
    require(set(fleet['host_receipts']) == hosts and set(pooling['attempts']) == hosts, 'Missing host evidence')
    for entry in entries:
        host = entry['host']
        actual = pooling['attempts'][host]
        require(len(actual) == len(entry['attempts']) and all(
            a['directory'] == b['directory'] and a['manifest_sha256'] == b['manifest_sha256']
            for a, b in zip(actual, entry['attempts'])), 'Lost/changed reference attempt')
        require(actual[-1]['passes'] is True and all(a['passes'] is False and a['technical_repeat_candidate'] is True
                for a in actual[:-1]), 'Invalid repeat classification')
        require(fleet['host_receipts'][host]['manifest_sha256'] == actual[-1]['manifest_sha256'], 'Wrong passing source')
        for key in ('relative_to_pooled_median', 'reference_to_reporting_mean'):
            within_five_percent(fleet['host_receipts'][host][key])
    check = obj(repo, p['pool_check'])
    require(check['schema'] == 'clasher.t1.pool-check.v1' and check['passes'] is True
            and check['outcome_access'] is False and check['pool_manifest_sha256'] == p['pool_manifest']['sha256']
            and check['descriptor_sha256'] == p['descriptor']['sha256'], 'Missing/mismatched pool recheck')
    require(check['output_files'] == manifest['files'], 'Pool check covers different outputs')
    require(stamp(completion['completed_at_utc']) <= stamp(check['checked_at_utc']) <= stamp(release['authorized_at_utc']),
            'Pool check is outside the post-completion release window')
    require(check['checker_sha256'] == sha(Path(__file__).with_name('check_reference.py')), 'Different pool checker')
    checker_name = 'reports/explore/t1/check_reference.py'
    committed(repo, dict(path=checker_name, commit=p['pool_check']['commit'], sha256=check['checker_sha256']))
    measurement_root = Path(repo) / 'reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3'
    require(check['input_files'] == pool_inputs(Path(repo) / p['descriptor']['path'], measurement_root),
            'Checked reference inputs changed or incomplete')
    registration_seal, packet = sealed(repo, p['registration_manifest'], 'T1-REGISTRATION')
    registered = registration_seal['files']
    require({'registration.json', 'golden.json', 'belief-reference.json', 'student-reference.json',
             'speed-reference.json', 'deadline-reference.json'} <= set(registered), 'Incomplete registration packet')
    registration = json.loads((packet / 'registration.json').read_text())
    require(registration['fleet_reference'] == fleet
            and registration['pooled_reference_manifest_sha256'] == p['pool_manifest']['sha256']
            and registration['pool_check_sha256'] == p['pool_check']['sha256'], 'Registration lineage mismatch')
    require(registration['deadline_replay_semantics'] == 'committed-copy', 'Wrong deadline replay contract')
    require(str(relative(registration['corpus_receipt'])) in registered, 'Unsealed corpus receipt')
    speed = registration['sets']['speed']
    require(set(speed) == TIERS and all(len(ids) == 300 and len(set(ids)) == 300 for ids in speed.values()),
            'Registration lacks fixed own-tier 300-state corpora')
    for name in ('speed-reference.json', 'deadline-reference.json'):
        require(registered[name] == manifest['files'][name], 'Registration reference differs from checked pool')
    sources = registration['source_receipts']
    require(set(sources) == hosts, 'Registration source host population differs')
    for entry in entries:
        archived = sources[entry['host']]
        require(len(archived) == len(entry['attempts']), 'Registration omitted a reference attempt')
        for source, attempt in zip(archived, entry['attempts']):
            name = relative(source['path'])
            require(source['manifest_sha256'] == attempt['manifest_sha256'] == registered.get(str(name)),
                    'Registration source seal differs')
            original = json.loads((packet / name).read_text())
            require(original['scope'] == 'FLEET-REFERENCE' and bool(original['files']), 'Wrong source receipt scope')
            for filename, digest in original['files'].items():
                require(registered.get(str(name.parent / relative(filename))) == digest, 'Unsealed original source receipt')
    return completion
