"""C1 final-gate admission/result contract. Stdlib only; importing this module launches nothing.

The host driver is separate. These validators can be tested with local synthetic records, without
loading a native module, running a gate, or touching remote hosts. See FINAL-GATE-PLAN.md schema v2.
"""
import gzip
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import random
import re
import stat

PIN = '681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b'
ARGS = dict(command_delay=27, opponent_delay=27, horizon=160, interval=10, elixir_weight=1.0)
ROLES = {'engine', 'native', 'pinned-native', 'r1', 'total-runtime', 'bot', 'python',
         'fixtures', 'roots', 'tools', 'evidence'}
GROUPS = {'review-r2': 21, 'snapshot-followup': 2, 'c1-cases': 72, 'first-update': 42,
          'batchA-review': 4, 'c1-scenarios': 36, 'named-replays': 11}
TOOL_FILES = ('final_gate.sh', 'final_gate.py', 'final_gate_contract.py', 'gate_worker.py',
              'gate_fixtures.py', 'gate_roots.py', 'gate_compare.py')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(value, size=64):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{%d}' % size, value), 'invalid hash')
    return value


def integer(value, minimum=0):
    require(type(value) is int and value >= minimum, 'invalid integer')
    return value


def relative(name):
    require(isinstance(name, str) and name and '\\' not in name and all(ord(c) >= 32 and ord(c) != 127 for c in name),
            'invalid manifest name')
    p = PurePosixPath(name)
    require(p.parts and not p.is_absolute() and p.as_posix() == name and all(x not in ('.', '..') for x in p.parts),
            'noncanonical/escaping manifest name')
    return name


def decode(data):
    def unique(pairs):
        out = {}
        for k, v in pairs:
            require(k not in out, 'duplicate JSON key: ' + k)
            out[k] = v
        return out
    return json.loads(data, object_pairs_hook=unique)


def read_regular(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        s = os.fstat(fd)
        require(stat.S_ISREG(s.st_mode) and s.st_uid == os.getuid() and s.st_nlink == 1,
                'not an owned single-link regular file: ' + str(path))
        require(s.st_size <= 128 * 1024 * 1024, 'oversized control/record file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            return stream.read()
    finally:
        os.close(fd)


def file_sha(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        s = os.fstat(fd)
        require(stat.S_ISREG(s.st_mode) and s.st_uid == os.getuid() and s.st_nlink == 1, 'unsafe input file')
        h = hashlib.sha256()
        while block := os.read(fd, 1 << 20):
            h.update(block)
        return h.hexdigest()
    finally:
        os.close(fd)


def inventory(root, frozen=True):
    """Exact recursive inventory, including empty directories; no external links or special files."""
    root = Path(root)
    result = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in sorted(dirs + files):
            p = Path(directory) / name
            key = p.relative_to(root).as_posix()
            relative(key)
            s = p.lstat()
            require(s.st_uid == os.getuid(), 'foreign input owner: ' + key)
            require(not stat.S_ISLNK(s.st_mode), 'input symlink: ' + key)
            require(not frozen or s.st_mode & 0o222 == 0, 'input is not frozen: ' + key)
            mode = stat.S_IMODE(s.st_mode)
            if stat.S_ISDIR(s.st_mode):
                result[key] = dict(kind='dir', mode=mode)
            else:
                require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'special/hardlinked input: ' + key)
                result[key] = dict(kind='file', mode=mode, size=s.st_size, sha256=file_sha(p))
    return result


def validate_manifest(manifest, observed):
    require(type(manifest) is dict and manifest, 'empty inventory')
    for key, rec in manifest.items():
        relative(key)
        require(key.split('/')[0] in ROLES, 'unexpected role/control/output entry: ' + key)
        require(type(rec) is dict and rec.get('kind') in ('file', 'dir'), 'invalid inventory record')
        expected = {'kind', 'mode'} | ({'size', 'sha256'} if rec['kind'] == 'file' else set())
        require(set(rec) == expected, 'invalid inventory fields')
        integer(rec['mode']); require(rec['mode'] & 0o222 == 0, 'writable manifest input')
        if rec['kind'] == 'file':
            integer(rec['size']); digest(rec['sha256'])
    require(set(key for key in manifest if '/' not in key) == ROLES, 'missing/extra dependency roles')
    require(manifest == observed, 'missing, changed, duplicate, or unexpected input')


def content_map(manifest, prefix):
    prefix += '/'
    return {k[len(prefix):]: v['sha256'] for k, v in manifest.items()
            if k.startswith(prefix) and v['kind'] == 'file'}


def check_derived_runtime(manifest):
    original, total = content_map(manifest, 'r1'), content_map(manifest, 'total-runtime')
    engine = content_map(manifest, 'engine')
    require({'Cargo.toml', 'src/lib.rs', 'py/gamedata.json', 'py/src/clasher/battle.py'} <= set(engine),
            'incomplete engine archive')
    expected = {k: v for k, v in original.items()
                if k != 'gamedata.json' and not k.startswith(('src/', 'engine-rs/'))}
    expected.update({'engine-rs/' + k: v for k, v in engine.items()})
    expected.update({k.removeprefix('py/'): v for k, v in engine.items() if k.startswith('py/src/')})
    expected['gamedata.json'] = engine['py/gamedata.json']
    require(total == expected, 'patched runtime is not the exact baseline plus engine overrides')
    require(all(k in original for k in ('gamedata.json', 'R3a.pt')), 'incomplete r1 runtime')
    require(any(k.startswith('reports/strategy_council_20260928/engine-speed/') for k in original),
            'missing runtime/transitive engine-speed sources')


def check_receipts(ready, receipts, manifest, code_hashes):
    """Typed owner evidence is checked, not inferred from a nonempty map or four booleans.

    Approval authenticity remains the owning lead's authority; hashes do not manufacture approval.
    """
    require(ready.get('schema') == 2, 'readiness schema must be 2')
    source, b2, tools = (digest(ready[k], 40) for k in ('integrated_commit', 'b2_accepted_commit', 'tools_commit'))
    native = digest(ready['native_sha256'])
    require(set(receipts) == {'b2', 'integration', 'build', 'tests', 'launcher_review', 'platform'},
            'missing/extra typed evidence roles')
    for role, r in receipts.items():
        require(r.get('kind') == role, 'wrong evidence kind: ' + role)
        require(all(isinstance(r.get(k), str) and r[k] for k in ('authority', 'evidence_id')),
                'missing owner/evidence identity')
        raw = r.get('raw_evidence')
        require(isinstance(raw, dict) and raw, 'missing raw provenance: ' + role)
        for path, expected in raw.items():
            relative(path)
            require(path.startswith('evidence/raw/') and manifest.get(path, {}).get('sha256') == digest(expected),
                    'missing/changed raw provenance: ' + role)
    require(receipts['b2'].get('verdict') == 'ACCEPTED' and receipts['b2'].get('commit') == b2,
            'B2 not accepted at the declared commit')
    required_b2 = receipts['b2'].get('required_integration_cases')
    require(isinstance(required_b2, list) and required_b2 and len(set(required_b2)) == len(required_b2),
            'B2 integration case inventory missing/duplicate')
    engine_hash = sha(json.dumps(content_map(manifest, 'engine'), sort_keys=True).encode())
    for role in ('integration', 'build', 'tests'):
        r = receipts[role]
        require(r.get('source_commit') == source and r.get('native_sha256') == native,
                'wrong source/native binding: ' + role)
        require(r.get('engine_inventory_sha256') == engine_hash, 'wrong source inventory: ' + role)
        require(r.get('verdict') == 'PASS' and type(r.get('exit_code')) is int and r['exit_code'] == 0,
                'failed evidence: ' + role)
    require(receipts['integration'].get('b2_commit') == b2, 'wrong integration ancestor')
    affected = receipts['integration'].get('required_tests', {})
    require(set(affected) == set(GROUPS) | {'b2-integration'}, 'missing declared affected-case identities')
    for group, cases in affected.items():
        require(isinstance(cases, list) and cases and all(isinstance(c, str) and c for c in cases)
                and len(set(cases)) == len(cases), 'invalid declared affected cases')
        require(len(cases) == GROUPS.get(group, len(required_b2)), 'wrong declared case count')
    require(set(affected['b2-integration']) == set(required_b2), 'wrong declared B2 cases')
    build = receipts['build']
    require(isinstance(build.get('command'), list) and build['command'], 'missing actual build command')
    for k in ('pid', 'pgid'):
        integer(build[k], 1)
    require(build.get('started_utc', '').endswith('Z') and build.get('ended_utc', '').endswith('Z')
            and build['started_utc'] <= build['ended_utc'], 'missing/invalid build times')
    review = receipts['launcher_review']
    require(review.get('verdict') == 'APPROVE' and review.get('reviewed_commit') == tools,
            'launcher review does not approve tools commit')
    require(review.get('code_hashes') == code_hashes and set(code_hashes) == set(TOOL_FILES),
            'reviewed launcher/helper code differs')
    groups = receipts['tests'].get('groups', {})
    require(set(groups) == set(GROUPS) | {'b2-integration'}, 'affected test inventory missing/extra groups')
    for group, rows in groups.items():
        require(isinstance(rows, list) and rows and len({x['case'] for x in rows}) == len(rows),
                'missing/duplicate test identities: ' + group)
        require({x['case'] for x in rows} == set(affected[group]), 'affected-case identities differ')
        if group in GROUPS:
            require(len(rows) == GROUPS[group], 'wrong affected case count: ' + group)
        else:
            require({x['case'] for x in rows} == set(required_b2), 'B2 affected cases differ')
        for row in rows:
            require(row.get('verdict') == 'PASS' and type(row.get('exit_code')) is int and row['exit_code'] == 0,
                    'failed affected case')
            path = relative(row['artifact'])
            require(path.startswith('evidence/raw/'), 'test evidence outside raw evidence')
            require(manifest.get(path, {}).get('sha256') == digest(row['artifact_sha256']),
                    'missing/changed actual test artifact')
    platform = receipts['platform']
    require(platform.get('python_version') == '3.12.12', 'unreviewed Python platform')
    require(platform.get('python_inventory_sha256') == sha(json.dumps(content_map(manifest, 'python'), sort_keys=True).encode()),
            'Python stdlib/site-package closure not bound')
    return source, b2, tools, native


def fixture_expectations(root):
    split_data = decode(read_regular(root / 't1-split.json'))['matches']
    require(len({x['episode'] for x in split_data}) == len(split_data), 'duplicate split IDs')
    for x in split_data:
        relative(x['episode']); require('/' not in x['episode'], 'unsafe fixture ID')
    ids = sorted(x['episode'] for x in split_data if x['split'] in ('train', 'validation')
                 and (root / 't1-trainval' / x['episode']).is_dir())
    require(len(ids) == 577, 'expected frozen 577-fixture collection')
    result = {}
    for ep in ids:
        relative(ep); require('/' not in ep, 'unsafe fixture ID')
        d = root / 't1-trainval' / ep
        require(all((d / name).is_file() for name in ('setup.json', 'events.jsonl', 'objects.jsonl.gz',
                                                     'evaluation-only.jsonl.gz')), 'incomplete fixture input')
        setup = decode(read_regular(d / 'setup.json'))['entry']
        with gzip.open(d / 'objects.jsonl.gz', 'rt') as f:
            end = max(decode(line)['tick'] for line in f)
        start = integer(setup['start_tick'])
        integer(end); require(end >= start, 'fixture ends before start')
        require(setup['split'] == next(x['split'] for x in split_data if x['episode'] == ep), 'fixture split differs')
        events = [decode(line) for line in read_regular(d / 'events.jsonl').splitlines()]
        plays = sum(bool(x.get('accepted')) and x.get('exec_tick') is not None
                    and x.get('kind') != 'champion ability' and x['exec_tick'] - 1 < end for x in events)
        result[ep] = dict(ticks=end - start, plays=plays, split=setup['split'])
    return result


def root_expectations(root):
    rows = []
    for p in sorted(root.glob('roots-*.jsonl.gz')):
        with gzip.open(p, 'rt') as f:
            rows.extend(decode(line) for line in f)
    require(len(rows) >= 300, 'incomplete frozen root collection')
    sample = sorted(random.Random(20261015).sample(range(len(rows)), 300))
    for k in sample:
        r = rows[k]
        h = digest(r['config'])
        require(sha(read_regular(root / ('config-' + h[:16] + '.json'))) == h, 'root config hash mismatch')
    return rows, sample


def statuses_ok(records, expected):
    require(len(records) == len(expected) and {x['label'] for x in records} == set(expected), 'missing child exits')
    require(len({x['label'] for x in records}) == len(records), 'duplicate child exits')
    for r in records:
        integer(r['pid'], 1)
        require(type(r['exit_code']) is int and r['exit_code'] == 0, 'failed/signalled child: ' + r['label'])


def hexfloat(value):
    require(isinstance(value, str), 'missing float.hex value')
    f = float.fromhex(value)
    require(math.isfinite(f) and f.hex() == value, 'invalid/noncanonical float.hex')


def battle_digest(value):
    # lib.rs hex_digest is SHA256, independently of the snapshot checksum.
    digest(value)


def audit_fixtures(rows, expected):
    require(len(rows) == len(expected) == 577 and {r['episode'] for r in rows} == set(expected), 'wrong fixture IDs')
    require(len({r['episode'] for r in rows}) == len(rows), 'duplicate fixture ID')
    for row in rows:
        require(set(row) == {'episode', 'rs', 'rust_only'}, 'unexpected fixture record schema')
        e = expected[row['episode']]
        rs, rust = row['rs'], row['rust_only']
        require(rs.get('episode') == row['episode'] and rs.get('split') == e['split'], 'wrong fixture metadata')
        require(type(rs.get('start_match')) is bool and isinstance(rs.get('action_mismatch'), list)
                and 'first_mismatch' in rs and 'error' not in rs, 'incomplete lockstep record')
        require(rs['fixture_ticks'] == e['ticks'] and 0 <= integer(rs['ticks']) <= e['ticks'], 'wrong lockstep ticks')
        require(rs['first_mismatch'] is None or isinstance(rs['first_mismatch'], dict), 'invalid residual mismatch')
        for mismatch in rs['action_mismatch']:
            require(isinstance(mismatch, list) and len(mismatch) == 6 and type(mismatch[0]) is int
                    and mismatch[1] in (0, 1) and isinstance(mismatch[2], str)
                    and isinstance(mismatch[3], list) and len(mismatch[3]) == 2
                    and all(type(x) is bool for x in mismatch[4:]), 'invalid action residual')
        if rs['first_mismatch'] is not None:
            m = rs['first_mismatch']
            require(set(m) == {'tick', 'rel', 'entities', 'n_entities_diff'}, 'incomplete mismatch detail')
            integer(m['tick']); integer(m['rel']); integer(m['n_entities_diff'])
            require(isinstance(m['entities'], list), 'invalid mismatch entities')
        require(set(rust) == {'ticks', 'chain', 'final', 'accepted', 'plays', 'action_results'}, 'incomplete Rust chain')
        require(rust['ticks'] == e['ticks'] and rust['plays'] == e['plays'], 'wrong chain ticks/actions')
        digest(rust['chain']); digest(rust['final'])
        actions = rust['action_results']
        require(isinstance(actions, list) and len(actions) == e['plays'] and all(type(x) is bool for x in actions),
                'invalid/errored chain actions')
        require(integer(rust['accepted']) == sum(actions), 'wrong accepted-action count')


def audit_root_shard(header, records, all_roots, sample, shard, native_path, native_sha, runtime_root):
    require(header == dict(native=native_path, native_sha256=native_sha, roots_total=len(all_roots),
                           sampled=300, args=ARGS, runtime_root=runtime_root, runtime_pins='r1'), 'wrong root header')
    indices = sample[shard::4]
    expected_keys = {(k, v) for k in indices for v in ('full', 'cut')}
    require(len(records) == len(expected_keys) == 150 and {(r['k'], r['variant']) for r in records} == expected_keys,
            'wrong sample, duplicate root, pairing or shard assignment')
    for r in records:
        required = {'k', 'index', 'tick', 'seat', 'variant', 'digest', 'legal_actions', 'actions',
                    'rollout_e1', 'evaluate', 'parts', 'view', 'mask', 'select', 'step', 'root_snapshot'}
        require(set(r) in (required, required | {'apply'}), 'root record schema differs')
        integer(r['k'])
        source = all_roots[r['k']]
        require(all(type(r[k]) is type(source[k]) and r[k] == source[k] for k in ('index', 'tick', 'seat')),
                'wrong root identity')
        legal = r['legal_actions']
        require(isinstance(legal, list) and legal == sorted(set(legal))
                and all(type(x) is int and 0 <= x < 2304 for x in legal), 'invalid legal-action inventory')
        plays = sorted(random.Random(r['k']).sample(legal, min(4, len(legal))))
        require(r['actions'] == [2304, 2401] + plays, 'wrong deterministic sampled actions')
        require(len(r['rollout_e1']) == len(r['actions']) * 3, 'missing rollout checks')
        for x in r['rollout_e1'] + r['parts'] + [r['evaluate']]:
            hexfloat(x)
        require(len(r['parts']) == 7, 'missing evaluation parts')
        for key in ('view', 'mask'):
            require(len(r[key]) == 2, 'missing seat checks')
            for h in r[key]:
                digest(h)
        require(len(r['select']) == len(r['step']) == 3, 'missing select/step checks')
        battle_digest(r['digest']); digest(r['root_snapshot'])
        for action, d in r['select']:
            require(type(action) is int and 0 <= action <= 2304, 'invalid selection')
            battle_digest(d)
        for d, h in r['step']:
            battle_digest(d); digest(h)
        require(('apply' in r) == bool(plays), 'missing/unexpected apply check')
        if plays:
            require(len(r['apply']) == 3 and r['apply'][0] in ('True', 'False'), 'incomplete apply result')
            battle_digest(r['apply'][1]); digest(r['apply'][2])
