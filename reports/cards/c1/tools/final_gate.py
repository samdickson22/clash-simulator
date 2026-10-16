"""One-use, fail-closed C1 host driver. Requires independent approval BEFORE execution.

No native/engine imports. Admission/result validators live in final_gate_contract.py.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import socket
import stat
import subprocess
import sys

spec = importlib.util.spec_from_file_location('contract', Path(__file__).with_name('final_gate_contract.py'))
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
MIN_ENV = dict(PATH='/usr/bin:/bin', LANG='C.UTF-8', LC_ALL='C.UTF-8', PYTHONHASHSEED='0',
               PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1', OMP_NUM_THREADS='1',
               OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', RAYON_NUM_THREADS='1', CUDA_VISIBLE_DEVICES='')
TRUSTED_REPOS = {'/mpac/sdicks02/repos/clasher-cards-c1', '/mpac/sdicks02/repos/clasher-cards',
                 '/mpac/sdicks02/repos/clasher', '/mpac/sdicks02/repos/clasher-bot'}


def utc():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def directory(path, private=False):
    s = path.lstat()
    C.require(stat.S_ISDIR(s.st_mode) and s.st_uid == os.getuid() and path.resolve() == path,
              'directory must be owned, real, canonical: ' + str(path))
    C.require(not private or stat.S_IMODE(s.st_mode) == 0o700, 'run/output must be mode 0700')


def new_file(parent, name):
    C.relative(name); C.require('/' not in name, 'output basename required')
    directory(parent, private=True)
    d = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        return os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=d)
    finally:
        os.close(d)


def write_json(parent, name, value):
    with os.fdopen(new_file(parent, name), 'w') as f:
        json.dump(value, f, sort_keys=True, indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())


def git(repo, *args):
    C.require(str(repo) in TRUSTED_REPOS and repo.resolve() == repo, 'untrusted Git repository')
    env = dict(MIN_ENV, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null', GIT_NO_REPLACE_OBJECTS='1')
    return subprocess.check_output(['/usr/bin/git', '--no-replace-objects', '-C', str(repo), *args], env=env)


def archive_files(repo, commit, prefix=''):
    raw = git(repo, 'cat-file', 'commit', commit)
    C.require(hashlib.sha1(b'commit ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == commit,
              'Git commit object authentication failed')
    result = {}
    for entry in git(repo, 'ls-tree', '-r', '-z', commit, '--', prefix).split(b'\0'):
        if not entry:
            continue
        meta, name = entry.split(b'\t', 1)
        mode, kind, oid = meta.decode().split()
        C.require(mode in ('100644', '100755') and kind == 'blob', 'archive symlink/submodule rejected')
        name = name.decode(); C.relative(name)
        if prefix:
            C.require(name.startswith(prefix + '/'), 'archive prefix mismatch')
            name = name[len(prefix) + 1:]
        data = git(repo, 'cat-file', 'blob', oid)
        C.require(hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == oid,
                  'Git blob authentication failed')
        result[name] = C.sha(data)
    C.require(result, 'empty authenticated archive')
    return result


def check_original(run, initial):
    for name, data in initial.items():
        C.require(C.read_regular(run / name) == data, 'original validated control replaced: ' + name)
    manifest = C.decode(initial['manifest.json'])
    C.validate_manifest(manifest, C.inventory(run / 'inputs'))


def preflight(run, requested):
    # The persistent claim already exists. Stage must be frozen before admission; never rebase its hashes.
    initial = {name: C.read_regular(run / name) for name in ('ready.json', 'manifest.json')}
    ready, manifest = (C.decode(initial[name]) for name in ('ready.json', 'manifest.json'))
    fields = {'schema', 'integrated_commit', 'b2_accepted_commit', 'tools_commit', 'bot_commit',
              'native_sha256', 'source_repo', 'bot_repo', 'manifest_sha256', 'receipts'}
    C.require(set(ready) == fields, 'readiness fields differ')
    C.require(tuple(ready[k] for k in ('integrated_commit', 'native_sha256', 'b2_accepted_commit', 'tools_commit'))
              == requested, 'command/readiness identity mismatch')
    C.require(C.sha(initial['manifest.json']) == ready['manifest_sha256'], 'wrong manifest digest')
    C.validate_manifest(manifest, C.inventory(run / 'inputs'))
    C.require(all((run / name).stat().st_mode & 0o222 == 0 for name in initial), 'controls must be frozen')
    capsule = run / 'inputs'
    C.require(capsule.stat().st_mode & 0o222 == 0, 'capsule root must be frozen')
    C.check_derived_runtime(manifest)
    repo = Path(ready['source_repo']); source, native_sha, b2, tools_commit = requested
    C.require(C.content_map(manifest, 'engine') == archive_files(repo, source, 'engine-cards'),
              'engine files differ from authenticated integrated commit')
    git(repo, 'merge-base', '--is-ancestor', b2, source)
    bot_commit = C.digest(ready['bot_commit'], 40)
    C.require(C.content_map(manifest, 'bot') == archive_files(Path(ready['bot_repo']), bot_commit),
              'complete bot archive/transitive reports differ from authenticated commit')
    code_hashes = C.content_map(manifest, 'tools')
    C.require(set(code_hashes) == set(C.TOOL_FILES), 'missing/unexpected executable tools')
    archived_tools = archive_files(repo, tools_commit, 'reports/cards/c1/tools')
    C.require(all(archived_tools.get(k) == v for k, v in code_hashes.items()), 'tool commit differs')
    # Also bind the driver actually executing, rather than merely an unused copy in the manifest.
    for name in ('final_gate.py', 'final_gate_contract.py', 'final_gate.sh'):
        C.require(C.file_sha(Path(__file__).with_name(name)) == code_hashes[name], 'running driver differs')
    receipts = {}
    for role, reference in ready['receipts'].items():
        C.require(set(reference) == {'path', 'sha256'}, 'invalid receipt reference')
        path = C.relative(reference['path'])
        C.require(path.startswith('evidence/') and manifest.get(path, {}).get('sha256') == reference['sha256'],
                  'receipt outside bound evidence inventory')
        receipts[role] = C.decode(C.read_regular(capsule / path))
    C.check_receipts(ready, receipts, manifest, code_hashes)
    for role, expected in (('native', native_sha), ('pinned-native', C.PIN)):
        C.require(C.content_map(manifest, role) == {'clasher_core.abi3.so': expected}, 'native role differs')
        with (capsule / role / 'clasher_core.abi3.so').open('rb') as f:
            C.require(f.read(4) == b'\x7fELF', 'native is not ELF')
    platform = receipts['platform']
    for role in ('r1', 'fixtures', 'roots'):
        expected = C.sha(json.dumps(C.content_map(manifest, role), sort_keys=True).encode())
        C.require(platform.get(role + '_inventory_sha256') == expected, 'unbound baseline/data inventory: ' + role)
    C.require(platform.get('verdict') == 'APPROVED' and platform.get('dependency_closure') == 'materialized-no-symlinks',
              'owner has not approved the full dependency/platform inventory')
    python = capsule / 'python/bin/python3.12'
    C.require(C.file_sha(python) == C.file_sha(Path(sys.executable).resolve()) and sys.version.split()[0] == '3.12.12',
              'unreviewed interpreter binary/version')
    for p in ('python/lib/python3.12/os.py', 'python/lib/python3.12/site-packages/torch/__init__.py',
              'python/lib/python3.12/site-packages/numpy/__init__.py'):
        C.require(p in manifest, 'incomplete Python dependency closure: ' + p)
    fixtures = C.fixture_expectations(capsule / 'fixtures')
    roots, sample = C.root_expectations(capsule / 'roots')
    check_original(run, initial)
    return initial, fixtures, roots, sample


class Children:
    def __init__(self, output):
        self.output, self.live, self.rows = output, {}, []

    def start(self, label, command, env):
        with os.fdopen(new_file(self.output, label + '.log'), 'wb') as log:
            p = subprocess.Popen(command, env=env, cwd=self.output, stdin=subprocess.DEVNULL,
                                 stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        self.live[label] = (p, command, utc())

    def wait(self, phase, labels):
        rows = []
        for label in labels:
            p, command, started = self.live[label]
            code = p.wait()  # Every PID individually, including shutdown failure and negative signal status.
            rows.append(dict(label=label, pid=p.pid, pgid=p.pid, exit_code=code, command=command,
                             started_utc=started, ended_utc=utc()))
            del self.live[label]
        self.rows.extend(rows)
        write_json(self.output, phase + '-exits.json', rows)
        C.statuses_ok(rows, labels)

    def stop(self):
        for p, _, _ in self.live.values():
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for label, (p, command, started) in list(self.live.items()):
            try:
                code = p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL); code = p.wait()
            self.rows.append(dict(label=label, pid=p.pid, pgid=p.pid, exit_code=code,
                                  command=command, started_utc=started, ended_utc=utc()))
            del self.live[label]
        write_json(self.output, 'all-child-exits.json', self.rows)


def jsonlines(path):
    return [C.decode(line) for line in C.read_regular(path).splitlines()]


def run_gate(run, requested):
    initial, fixtures, roots, sample = preflight(run, requested)
    output, capsule = run / 'output', run / 'inputs'
    env = dict(MIN_ENV, LD_LIBRARY_PATH=str(capsule / 'python/lib'))
    write_json(output, 'validated-baseline.json', dict(controls={k: C.sha(v) for k, v in initial.items()},
               requested=requested, fixture_ids=sorted(fixtures), root_sample=sample, environment=env,
               per_arm=dict(CLASHER_BOT_RUNTIME_PINS='r1', CLASHER_EVAL_RUNTIME_ROOT='derived per arm',
                            CLASHER_ROOT='inputs/{r1,total-runtime}', CLASHER_BOT_RUNTIME='inputs/{r1,total-runtime}',
                            CLASHER_DELAY_NATIVE_DIR='inputs/{pinned-native,native}')))
    gate = output / 'gate'; gate.mkdir(mode=0o700)
    # All helper output files are exclusively reserved in a private directory before workers start.
    for tag in ('pinned', 'total'):
        for name in [f'fixtures-{tag}.jsonl'] + [f'roots-{tag}-{i}.jsonl' for i in range(4)]:
            os.close(new_file(gate, name))
    gate.chmod(0o500)
    children = Children(output)
    def command(tag, helper, *args):
        return ['/usr/bin/nice', '-n', '15', str(capsule / 'python/bin/python3.12'), '-I', '-S', '-B',
                str(capsule / 'tools/gate_worker.py'), str(capsule), tag, helper, *map(str, args)]
    try:
        check_original(run, initial)
        for tag in ('pinned', 'total'):
            children.start('fixtures-' + tag, command(tag, 'gate_fixtures.py', '--out',
                           gate / f'fixtures-{tag}.jsonl', '--workers', '3'), env)
        children.wait('fixtures', ['fixtures-pinned', 'fixtures-total'])
        for tag in ('pinned', 'total'):
            first = C.read_regular(output / ('fixtures-' + tag + '.log')).splitlines()[0]
            role = 'pinned-native' if tag == 'pinned' else 'native'
            C.require(C.decode(first) == dict(native=str(capsule / role / 'clasher_core.abi3.so'), fixtures=577),
                      'fixture helper imported the wrong native or fixture set')
            C.audit_fixtures(jsonlines(gate / f'fixtures-{tag}.jsonl'), fixtures)
        C.require(C.read_regular(gate / 'fixtures-pinned.jsonl') == C.read_regular(gate / 'fixtures-total.jsonl'),
                  'fixture bodies differ')
        check_original(run, initial)
        labels = []
        for tag in ('pinned', 'total'):
            for i in range(4):
                label = f'roots-{tag}-{i}'; labels.append(label)
                children.start(label, command(tag, 'gate_roots.py', '--roots', capsule / 'roots', '--sample', '300',
                               '--shard', f'{i}/4', '--out', gate / (label + '.jsonl')), env)
        children.wait('roots', labels)
        for i in range(4):
            for tag, role, native_sha in (('pinned', 'pinned-native', C.PIN), ('total', 'native', requested[1])):
                records = jsonlines(gate / f'roots-{tag}-{i}.jsonl')
                C.audit_root_shard(records[0], records[1:], roots, sample, i,
                                   str(capsule / role / 'clasher_core.abi3.so'), native_sha,
                                   str(capsule / ('r1' if tag == 'pinned' else 'total-runtime')))
            a = C.read_regular(gate / f'roots-pinned-{i}.jsonl').splitlines()[1:]
            b = C.read_regular(gate / f'roots-total-{i}.jsonl').splitlines()[1:]
            C.require(a == b, 'root bodies differ')
        check_original(run, initial)
        children.start('compare', command('pinned', 'gate_compare.py', gate), env)
        children.wait('comparator', ['compare'])
        summary = C.decode(C.read_regular(output / 'compare.log'))
        C.require(summary['fixtures']['identical_records'] == 577 and summary['roots']['identical_records'] == 600,
                  'comparator summary differs')
        check_original(run, initial)
        return dict(verdict='PASS', controls={k: C.sha(v) for k, v in initial.items()},
                    source_commit=requested[0], native_sha256=requested[1], b2_commit=requested[2],
                    tools_commit=requested[3], ended_utc=utc(), child_statuses=children.rows)
    finally:
        children.stop()


def interrupted(signum, frame):
    raise InterruptedError('received signal ' + str(signum))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run', type=Path); ap.add_argument('source'); ap.add_argument('native')
    ap.add_argument('b2'); ap.add_argument('tools')
    a = ap.parse_args()
    requested = (C.digest(a.source, 40), C.digest(a.native), C.digest(a.b2, 40), C.digest(a.tools, 40))
    C.require(socket.gethostname().split('.')[0] == '127x04', 'restricted to 127x04')
    run = a.run
    C.require(re.fullmatch('/mpac/sdicks02/jobs/clasher/cards/c1/final-' + a.source[:12] + r'(-r[1-9][0-9]*)?', str(run)),
              'invalid one-use bundle path')
    directory(run, private=True)
    C.require({p.name for p in run.iterdir()} == {'ready.json', 'manifest.json', 'inputs'},
              'bundle must contain only fresh inputs and controls (no prior output, PASS or dangling links)')
    directory(run / 'inputs')
    (run / '.gate-started').mkdir(mode=0o700)  # Claim BEFORE any control validation; never delete it.
    (run / 'output').mkdir(mode=0o700)
    output = run / 'output'
    try:
        write_json(output, 'launch.json', dict(pid=os.getpid(), ppid=os.getppid(), pgid=os.getpgrp(),
                                             started_utc=utc(), requested=requested, argv=sys.argv))
        lease = Path('/mpac/sdicks02/jobs/clasher/bot-cpu-claims') / ('lease-' + str(os.getppid()))
        slots, pgid = C.read_regular(lease).decode().split()
        C.require((slots, pgid) == ('8', str(os.getpgrp())), 'requires direct cpu_job.sh 8 lease')
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(sig, interrupted)
        result = run_gate(run, requested)
        write_json(output, '.PASS.tmp', result)
        # Atomic no-clobber publication, no redirection through an existing success path.
        os.link(output / '.PASS.tmp', output / 'PASS.json', follow_symlinks=False)
        (output / '.PASS.tmp').unlink()
        return 0
    except BaseException as ex:
        # Includes a signal between the link syscall and its return: never rely on a later flag assignment.
        try:
            (output / 'PASS.json').unlink()
        except FileNotFoundError:
            pass
        write_json(output, 'FAIL.json', dict(verdict='FAIL', error=repr(ex), ended_utc=utc()))
        return 1


if __name__ == '__main__':
    sys.exit(main())
