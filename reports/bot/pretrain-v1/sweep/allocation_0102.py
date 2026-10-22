"""Review-gated transfer of the legacy 08 queue. No workload runs by default.

Handoff reserves the exact exclusive intents the immutable legacy owner must
create before launch. Its M50 trainer and selection continue untouched. The
owner completes M25 and refuses next-S100 at the next snapshot boundary. Claims on 08 precede local launch.
An interrupted claim needs inspection. No control operation sends a signal.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve()
INPUTS = HERE.parent.parent / 'host01-02'
DEPLOY = Path('/mpac/sdicks02/repos/pretrain-v1-allocation-0102-20261022')
REMOTE_SCRIPT = DEPLOY / 'sweep/allocation_0102.py'
OUT = Path('/mpac/sdicks02/jobs/clasher/pretrain-v1/followup-20261022')
STATE = OUT / 'allocation-0102'
OLD = OUT.parent / 'bc-sweep'
PYTHON = '/mpac/sdicks02/repos/clasher-bot-gpu/venv/bin/python'
SOURCE = Path('/mpac/sdicks02/repos/pretrain-v1-host01-input-93baf3a5b')
LEGACY = Path('/mpac/sdicks02/repos/pretrain-v1-followup-93baf3a5b')
DATA = Path('/mpac/sdicks02/datasets/pretrain-v1')
STORE_NAME = 'f-ce6e509ee43a-b-1005dbb4'
NEXT = 'snapshot-20261022-b083'
PHASES = {'next-M100': '127x01', 'next-S100': '127x02'}
PEAKS = {'M': {'train': 26.0234375, 'select': 5.349609375},
         'S': {'train': 18.06640625, 'select': 3.103515625}}
PIDS = {1327095: 245175313, 1327129: 245175332, 1327130: 245175333}
OWNER, GUARD, TRAINER = PIDS


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def exclusive(path, value):
    """Durable create-only intent. A torn write blocks rather than relaunches."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        json.dump(value, f, sort_keys=True, indent=1)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def host():
    return os.uname().nodename.split('.')[0]


def reviewed(go):
    require(sha(INPUTS / 'source-inputs.json') == 'e7f2f2cbeb692551815d5a9f9537b99f4b7be9991de1fe66d4f0a323b9fb7433', 'source inventory changed')
    require(sha(INPUTS / 'dataset-inputs.json') == '0095c4feada89c74dfb0dafad8e593ed40195e046a3db7ba5dc346183dc59b6f', 'dataset inventory changed')
    require(go == sha(HERE), 'GO must name this exact controller SHA256')


def proc(pid):
    p = Path('/proc') / str(pid)
    try:
        fields = (p / 'stat').read_text().rsplit(')', 1)[1].split()
        return dict(state=fields[0], ppid=int(fields[1]), start_ticks=int(fields[19]),
                    command=(p / 'cmdline').read_bytes().decode().split('\0')[:-1])
    except FileNotFoundError:
        return None


def alive(pid):
    p = proc(pid)
    return p is not None and p['state'] not in ('Z', 'X')


def exact(pid):
    p = proc(pid)
    require(p is not None and p['start_ticks'] == PIDS[pid], f'PID identity changed: {pid}')
    return p


def checked_files(root, expected):
    require(bool(expected), 'empty input inventory')
    for name, digest in expected.items():
        p = root / name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'unsafe relative path')
        require(p.resolve().is_relative_to(root.resolve()), 'path escaped root')
        require(p.is_file() and sha(p) == digest, f'input hash mismatch: {p}')


def verify_inputs(which):
    require(which in ('127x01', '127x02', '127x08'), 'unauthorized host')
    source = LEGACY if which == '127x08' else SOURCE
    checked_files(source, read(INPUTS / 'source-inputs.json')['files'])
    files = read(INPUTS / 'dataset-inputs.json')['files']
    if which == '127x02':
        files = {k: v for k, v in files.items() if k.startswith(NEXT + '/')}
    checked_files(DATA, files)
    for folder in ({NEXT} if which == '127x02' else {NEXT, STORE_NAME}):
        actual = {str(p.relative_to(DATA)) for p in (DATA / folder).rglob('*') if p.is_file()}
        require(actual == {k for k in files if k.startswith(folder + '/')}, 'unlisted dataset file')
    ready = read(DATA / NEXT / 'STORE-READY.json')
    require(ready['batches'] == 83 and ready['rows'] == 8143577 and ready['matches'] == 41328,
            'larger snapshot counts changed')
    require(ready['manifest_sha256'] == 'f52562891584db3dffef6c45ced1106a41b712456e67a1cd87ccc084b23dc59a',
            'larger snapshot manifest changed')
    checked_files(DATA / NEXT, ready['files'])
    return dict(host=which, source_revision=read(INPUTS / 'source-inputs.json')['revision'],
                source_inventory_sha256=sha(INPUTS / 'source-inputs.json'),
                dataset_inventory_sha256=sha(INPUTS / 'dataset-inputs.json'),
                dataset_files=len(files), source_files=len(read(INPUTS / 'source-inputs.json')['files']),
                ready_sha256=sha(DATA / NEXT / 'STORE-READY.json'), verified=time.time())


def assert_pending():
    for name in ('next-S100', 'next-M100'):
        require(not (OUT / ('intent-' + name + '.json')).exists(), f'legacy already owns {name}')
        require(not (OUT / name).exists(), f'legacy phase directory exists: {name}')


def validate_legacy():
    require(host() == '127x08', 'handoff runs only on 08')
    require(read(OUT / 'launch.json') == dict(pid=OWNER, revision='93baf3a5bcff9670a0b8ddbcf437638172e84fbd'),
            'legacy launch changed')
    require(exact(OWNER)['command'] == [PYTHON, '-B', '-u', str(LEGACY / 'reports/bot/pretrain-v1/sweep/followup_08.py')],
            'legacy owner command changed')
    active = read(OUT / 'active.json')
    require(active['name'] == 'M50' and active['guard_pid'] == GUARD, 'legacy advanced past M50')
    require(exact(GUARD)['ppid'] == OWNER and exact(TRAINER)['ppid'] == GUARD, 'M50 process tree changed')
    require(exact(TRAINER)['command'] == active['command'], 'trainer command changed')
    require(exact(GUARD)['command'] == ['bash', str(LEGACY / 'bot/pretrain_v1/run_guarded.sh'),
                                      str(OUT / 'M50.log'), '--'] + active['command'], 'guard command changed')
    require(alive(GUARD) and alive(TRAINER), 'M50 is no longer active; review a new boundary')
    assert_pending()
    return active


def handoff(go):
    reviewed(go)
    validate_legacy()
    checked_files(LEGACY, read(INPUTS / 'source-inputs.json')['files'])
    with locked(STATE / 'handoff.lock'):
        require(not (STATE / 'allocation.json').exists(), 'allocation already exists')
        validate_legacy()
        # The immutable owner uses open('x') BEFORE admission or spawn. Each
        # reservation competes atomically with that exact legacy intent. If it
        # already won, this operation fails and no allocation is published.
        reservations = {}
        for phase in ('next-S100', 'next-M100'):
            path = OUT / f'intent-{phase}.json'
            exclusive(path, dict(reserved_by='allocation-0102', phase=phase,
                                 host=PHASES[phase], controller_sha256=go))
            reservations[path.name] = sha(path)
        receipt = dict(schema='pv1.allocation.0102.v1', controller_sha256=go, phases=PHASES,
                       mechanism='legacy-exclusive-prelaunch-intents', reservations=reservations,
                       legacy_owner_pid=OWNER, legacy_owner_start=PIDS[OWNER], created=time.time(),
                       source_inventory_sha256=sha(INPUTS / 'source-inputs.json'),
                       dataset_inventory_sha256=sha(INPUTS / 'dataset-inputs.json'))
        exclusive(STATE / 'allocation.json', receipt)
        return receipt


def allocation(go):
    reviewed(go)
    a = read(STATE / 'allocation.json')
    require(a['controller_sha256'] == go and a['phases'] == PHASES and
            a['mechanism'] == 'legacy-exclusive-prelaunch-intents', 'allocation identity mismatch')
    require(a['source_inventory_sha256'] == sha(INPUTS / 'source-inputs.json') and
            a['dataset_inventory_sha256'] == sha(INPUTS / 'dataset-inputs.json'), 'inventory changed')
    require(set(a['reservations']) == {f'intent-{p}.json' for p in PHASES}, 'missing reservation')
    checked_files(OUT, a['reservations'])
    checked_files(LEGACY, read(INPUTS / 'source-inputs.json')['files'])
    return a


def claim(phase, requester, go):
    require(host() == '127x08', 'claims live on 08')
    allocation(go)
    require(phase in PHASES, 'phase is not allocated')
    require(PHASES[phase] == requester, 'wrong phase host')
    value = dict(phase=phase, host=requester, controller_sha256=go, allocation_sha256=sha(STATE / 'allocation.json'))
    with locked(STATE / 'claims.lock'):
        completed = STATE / f'published-{phase}.json'
        if completed.exists():
            require(read(STATE / f'claim-{phase}.json') == value, 'completed claim changed')
            receipt = read(completed)
            require(receipt['controller_sha256'] == go, 'completed phase identity changed')
            checked_files(OUT, receipt['files'])
            return dict(value, completed=True)
        exclusive(STATE / f'claim-{phase}.json', value)
    return dict(value, completed=False)


def remote(args):
    # All remote values are fixed phase names, hex hashes or absolute paths controlled here.
    import shlex
    cmd = [PYTHON, '-B', str(REMOTE_SCRIPT)] + args
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', '127x08', shlex.join(cmd)],
                            check=True, capture_output=True, text=True, timeout=180)
    return json.loads(result.stdout)


def command(phase, selected=False):
    require(phase in PHASES, 'phase is not allocated')
    source = LEGACY if host() == '127x08' else SOURCE
    store = DATA / (NEXT if phase.startswith('next-') else '') / STORE_NAME
    size = 'S' if phase == 'next-S100' else 'M'
    if selected:
        return [PYTHON, '-B', '-m', 'bot.pretrain_v1.select_bc', '--store', str(store), '--runs', str(OUT / phase),
                '--out', str(OUT / ('select-' + phase)), '--device', 'cuda']
    require(phase in PHASES, 'phase is not allocated')
    spec = importlib.util.spec_from_file_location('base', source / 'reports/bot/pretrain-v1/sweep/sweep_08.py')
    b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
    args = ['--bs', '512', '--patience', '2']
    args += ['--epochs', '8', '--eval-every', '1', '--warmup-steps', '0']
    return [PYTHON, '-B', '-m', 'bot.pretrain_v1.train_bc', '--store', str(store), '--out', str(OUT / phase),
            '--seed', '2026102001', '--device', 'cuda', '--threads', '3'] + b.SIZE_ARGS[size] + args


def host_ok():
    import math
    try:
        avail = next(int(l.split()[1]) / 2**20 for l in Path('/proc/meminfo').read_text().splitlines()
                     if l.startswith('MemAvailable:'))
        load = os.getloadavg()[0]
        return math.isfinite(load) and avail >= 29 and load <= 90
    except (OSError, ValueError, StopIteration):
        return False


def guard(cmd):
    """Only our newly launched child group can be stopped by this guard."""
    require(bool(cmd), 'empty guard command')
    if not host_ok():
        return 75
    p = subprocess.Popen(['nice', '-n', '10'] + cmd, start_new_session=True)
    while p.poll() is None:
        if not host_ok():
            os.killpg(p.pid, signal.SIGTERM)
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL); p.wait()
            return 75
        time.sleep(20)
    return p.returncode


def run_step(phase, selected, go):
    source = LEGACY if host() == '127x08' else SOURCE
    spec = importlib.util.spec_from_file_location('base', source / 'reports/bot/pretrain-v1/sweep/sweep_08.py')
    b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
    b.CODE, b.SW = str(source), OUT
    size = 'S' if phase == 'next-S100' else 'M'
    cap = 1.5 * PEAKS[size]['select' if selected else 'train']
    name = ('select-' if selected else '') + phase
    artifact = OUT / name / ('selection.json' if selected else 'summary.json')
    cmd = command(phase, selected)
    # No automatic recovery of a claimed/partial phase, including a surviving orphan guard.
    require(not artifact.parent.exists(), f'partial/existing phase: {name}')
    exclusive(STATE / f'intent-{name}.json', dict(command=cmd, cap_gib=cap, controller_sha256=go, created=time.time()))
    b.admit(cap)  # Reviewed measured caps, 43.5 GiB budget, >=40 GiB admission / load<85.
    env = dict(os.environ, PYTHONPATH=str(source), CUDA_VISIBLE_DEVICES='0', OMP_NUM_THREADS='3',
               PV1_GPU_FRACTION=f'{cap / b.TOTAL:.4f}', PYTHONDONTWRITEBYTECODE='1', PYTHONHASHSEED='0',
               NUMPY_MADVISE_HUGEPAGE='0')
    with (OUT / f'{name}.allocation.log').open('x') as log:
        p = subprocess.Popen([PYTHON, '-B', str(HERE), 'guard', '--'] + cmd, cwd=source, env=env,
                             stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        exclusive(STATE / f'active-{name}.json', dict(guard_pid=p.pid, command=cmd))
        rc = p.wait()
    require(rc == 0 and artifact.is_file(), f'{name} failed ({rc}); inspect, never retry automatically')
    exclusive(STATE / f'completed-{name}.json', dict(command=cmd, cap_gib=cap, artifact_sha256=sha(artifact)))


def tree_hashes(root):
    require(root.is_dir(), 'missing bundle')
    files = {}
    for p in sorted(root.rglob('*')):
        require(not p.is_symlink(), 'symlink in bundle')
        if p.is_file():
            files[str(p.relative_to(root))] = sha(p)
    return files


def validate_bundle(root, phase):
    selected = root / ('select-' + phase)
    d = read(selected / 'selection.json')
    require(d['file'] in ('anchor.pt', 'PROVISIONAL-not-admitted.pt') and d['smoke'] is False,
            'invalid completed selection')
    require(sha(selected / d['file']) == d['sha256'], 'checkpoint hash mismatch')
    require((root / phase / 'run.json').is_file() and (root / phase / 'summary.json').is_file(), 'missing run receipts')
    return d


def publish_dir(src, dest):
    import shutil
    import tempfile
    if dest.exists():
        require(tree_hashes(src) == tree_hashes(dest), f'existing incompatible mirror: {dest.name}')
        return
    with tempfile.TemporaryDirectory(dir=OUT, prefix='.publish-') as tmp:
        incoming = Path(tmp) / dest.name
        shutil.copytree(src, incoming)
        require(tree_hashes(src) == tree_hashes(incoming), 'copy changed')
        for p in incoming.rglob('*'):
            if p.is_file():
                with p.open('rb') as f:
                    os.fsync(f.fileno())
        incoming.rename(dest)
        fd = os.open(OUT, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def publish(phase, go):
    require(host() == '127x08' and phase in PHASES, 'invalid publish')
    allocation(go)
    c = read(STATE / f'claim-{phase}.json')
    require(c['host'] == PHASES[phase] and c['controller_sha256'] == go, 'claim mismatch')
    incoming = STATE / ('incoming-' + phase)
    with locked(STATE / 'publish.lock'):
        validate_bundle(incoming, phase)
        hashes = tree_hashes(incoming)
        manifest = read(STATE / f'bundle-{phase}.json')
        require(hashes == manifest['files'] and manifest['controller_sha256'] == go, 'bundle changed')
        # Publish run receipts before selection.json becomes visible to existing 05/game readers.
        for name in (phase, 'select-' + phase):
            publish_dir(incoming / name, OUT / name)
        completed = STATE / f'published-{phase}.json'
        if completed.exists():
            receipt = read(completed)
            require(receipt['files'] == hashes and receipt['controller_sha256'] == go, 'publication changed')
            return receipt
        receipt = dict(phase=phase, files=hashes, controller_sha256=go, completed=time.time())
        exclusive(completed, receipt)
        return receipt


def mirror(phase, go):
    import tempfile
    import shutil
    with tempfile.TemporaryDirectory(dir=STATE, prefix='bundle-') as tmp:
        root = Path(tmp)
        shutil.copytree(OUT / ('select-' + phase), root / ('select-' + phase))
        (root / phase).mkdir()
        for name in ('run.json', 'summary.json'):
            shutil.copy2(OUT / phase / name, root / phase / name)
        validate_bundle(root, phase)
        manifest = dict(files=tree_hashes(root), controller_sha256=go)
        local_manifest = STATE / f'bundle-{phase}.json'
        exclusive(local_manifest, manifest)
        subprocess.run(['rsync', '-a', str(root) + '/', f'127x08:{STATE}/incoming-{phase}/'], check=True)
        subprocess.run(['scp', '-q', str(local_manifest), f'127x08:{STATE}/bundle-{phase}.json'], check=True)
        return remote(['publish', '--phase', phase, '--review-go', go])


def runner(go):
    reviewed(go)
    which = host()
    require(which in ('127x01', '127x02'), 'host not allocated')
    OUT.mkdir(parents=True, exist_ok=True)
    with locked(STATE / 'runner.lock'):
        verify_inputs(which)
        phases = {'127x01': ['next-M100'], '127x02': ['next-S100']}[which]
        for phase in phases:
            claimed = remote(['claim', '--phase', phase, '--requester', which, '--review-go', go])
            if claimed['completed']:
                continue
            run_step(phase, False, go)
            run_step(phase, True, go)
            mirror(phase, go)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=['verify', 'inspect', 'handoff', 'claim', 'run', 'publish', 'guard'])
    ap.add_argument('--review-go')
    ap.add_argument('--phase', choices=list(PHASES))
    ap.add_argument('--requester', choices=['127x01', '127x02', '127x08'])
    if len(sys.argv) > 1 and sys.argv[1] == 'guard':
        return guard(sys.argv[3:])
    a = ap.parse_args()
    if a.action == 'verify':
        result = verify_inputs(host())
    elif a.action == 'inspect':
        result = dict(host=host(), processes={pid: proc(pid) for pid in PIDS}, controller_sha256=sha(HERE))
    elif a.action == 'handoff':
        result = handoff(a.review_go)
    elif a.action == 'claim':
        result = claim(a.phase, a.requester, a.review_go)
    elif a.action == 'publish':
        result = publish(a.phase, a.review_go)
    else:
        result = runner(a.review_go)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
