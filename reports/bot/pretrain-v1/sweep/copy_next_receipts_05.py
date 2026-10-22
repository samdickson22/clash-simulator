"""Copy immutable completed 08 receipts to 05. No scientific work or remote writes."""
import argparse
import base64
from contextlib import contextmanager
import ctypes
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import selectors
import subprocess
import tempfile
import time

HERE = Path(__file__).resolve()
CODE = HERE.parents[4]
ROOT = Path('/mpac/sdicks02/scratch/pretrain-v1-dev/followup-20261022')
SOURCE = '/mpac/sdicks02/jobs/clasher/pretrain-v1/followup-20261022'
CONTROLLER = 'bc703a4072634ccccedb90f03e34ef9d3cebad25046bcce3cae14922607b4218'
SIZES = {'S100': 'next-S100', 'M': 'next-M100'}
LIMIT = 2 * 1024 * 1024
spec = importlib.util.spec_from_file_location('receipt_waiter', HERE.with_name('next_eval_expand_05.py'))
W = importlib.util.module_from_spec(spec)
spec.loader.exec_module(W)

# Fixed program, sent on stdin to standard Python. It never imports deployed code.
REMOTE = r'''
import base64, hashlib, json, os, stat
from pathlib import Path
ROOT = Path('/mpac/sdicks02/jobs/clasher/pretrain-v1/followup-20261022')
GO = 'bc703a4072634ccccedb90f03e34ef9d3cebad25046bcce3cae14922607b4218'
def require(ok, why):
    if not ok: raise ValueError(why)
def regular(p):
    for part in (p,) + tuple(p.parents):
        require(not part.is_symlink(), 'source symlink')
    require(stat.S_ISREG(p.stat().st_mode), 'source not regular')
def raw(p):
    regular(p)
    with p.open('rb') as f: b = f.read(262145)
    require(len(b) <= 262144, 'source receipt too large')
    return b
def digest(b): return hashlib.sha256(b).hexdigest()
def sha(p):
    regular(p)
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()
def collect(phase):
    paths = {n: ROOT/phase/n for n in ('run.json', 'summary.json')}
    paths['selection.json'] = ROOT/('select-'+phase)/'selection.json'
    state = ROOT/'allocation-0102'
    meta = {n: state/(n+'-'+phase+'.json') for n in ('claim', 'bundle', 'published')}
    meta['allocation'] = state/'allocation.json'
    try:
        data = {n: raw(p) for n,p in paths.items()}
        mbytes = {n: raw(p) for n,p in meta.items()}
    except FileNotFoundError:
        return dict(status='missing', reason='awaiting atomic source publication')
    parsed = {n: json.loads(b) for n,b in data.items()}
    m = {n: json.loads(b) for n,b in mbytes.items()}
    s = parsed['selection.json']
    require(s['file'] in ('anchor.pt', 'PROVISIONAL-not-admitted.pt') and type(s['smoke']) is bool
            and type(s['admitted']) is bool and type(s['eligible']) is int, 'malformed selection')
    if s['smoke'] or not s['admitted'] or s['eligible'] <= 0 or s['selection']['eligible'] is not True:
        return dict(status='missing', reason='selection not admitted full-DEV eligible')
    require(s['file'] == 'anchor.pt', 'admitted provisional selection')
    hashes = {str(paths[n].relative_to(ROOT)): digest(b) for n,b in data.items()}
    anchor = ROOT/('select-'+phase)/'anchor.pt'
    hashes[str(anchor.relative_to(ROOT))] = sha(anchor)
    require(hashes[str(anchor.relative_to(ROOT))] == s['sha256'], 'anchor hash mismatch')
    require(all(x['controller_sha256'] == GO for x in m.values()), 'controller changed')
    require(m['published']['phase'] == m['claim']['phase'] == phase, 'phase changed')
    require(m['allocation']['phases'] == {'next-M100':'127x01','next-S100':'127x02'}
            and m['claim']['host'] == m['allocation']['phases'][phase]
            and m['claim']['allocation_sha256'] == digest(mbytes['allocation']), 'claim changed')
    require(m['bundle']['files'] == m['published']['files'], 'published bundle changed')
    require(all(m['published']['files'].get(n) == h for n,h in hashes.items()), 'published bytes changed')
    return dict(status='ready', files={n: dict(base64=base64.b64encode(b).decode('ascii'), sha256=digest(b))
                for n,b in data.items()}, binding=dict(source=str(ROOT/phase), selected=str(anchor.parent),
                files=hashes, receipts={n:digest(b) for n,b in mbytes.items()}, controller_sha256=GO))
try:
    result = {s: collect(p) for s,p in [('S100','next-S100'),('M','next-M100')]}
except Exception as e:
    result = dict(error=type(e).__name__+': '+str(e))
print(json.dumps(result, separators=(',',':')))
'''


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


def digest(b):
    return hashlib.sha256(b).hexdigest()


def safe(path):
    for p in (path,) + tuple(path.parents):
        require(not p.is_symlink(), 'local symlink: '+str(p))


def sync(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextmanager
def locked(path):
    safe(path)
    with path.open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


class TransportError(Exception):
    pass


def fetch():
    """One bounded 08 connection. Only transport failures may be retried."""
    command = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15',
               '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=2', '127x08', 'python3 -B -']
    with tempfile.TemporaryFile() as script:
        script.write(REMOTE.encode()); script.seek(0)
        with subprocess.Popen(command, stdin=script, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as p:
            try:
                with selectors.DefaultSelector() as sel:
                    sel.register(p.stdout, selectors.EVENT_READ)
                    data, deadline = bytearray(), time.monotonic()+90
                    while True:
                        remaining = deadline-time.monotonic()
                        if remaining <= 0 or not sel.select(remaining):
                            raise OSError('08 SSH timeout')
                        b = os.read(p.stdout.fileno(), min(65536, LIMIT+1-len(data)))
                        if not b:
                            break
                        data.extend(b)
                        require(len(data) <= LIMIT, '08 response exceeds 2 MiB')
                if p.wait(timeout=max(0.01, deadline-time.monotonic())):
                    raise OSError('08 SSH failed')
            except BaseException:
                p.kill(); p.wait()
                raise
    return json.loads(data)


def rename_new(source, dest):
    # Linux renameat2 prevents replacing even an empty directory raced into place.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.renameat2(-100, os.fsencode(source), -100, os.fsencode(dest), 1):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(dest))


def publish(root, size, item):
    require(set(item['files']) == {'run.json', 'summary.json', 'selection.json'}, 'unexpected remote files')
    data = {n: base64.b64decode(f['base64'], validate=True) for n,f in item['files'].items()}
    require(all(digest(b) == item['files'][n]['sha256'] for n,b in data.items()), 'transport hash mismatch')
    binding, phase = item['binding'], SIZES[size]
    require(binding['source'] == SOURCE+'/'+phase and binding['selected'] == SOURCE+'/select-'+phase
            and binding['controller_sha256'] == CONTROLLER, 'source binding mismatch')
    for n,b in data.items():
        relative = ('select-'+phase if n == 'selection.json' else phase)+'/'+n
        require(binding['files'][relative] == digest(b), 'source byte binding mismatch')
    selected, run, summary = [json.loads(data[n]) for n in ('selection.json', 'run.json', 'summary.json')]
    require(selected['file'] == 'anchor.pt' and selected['smoke'] is False and selected['admitted'] is True
            and selected['eligible'] > 0 and selected['selection']['eligible'] is True, 'selection not admitted')
    require(binding['files']['select-'+phase+'/anchor.pt'] == selected['sha256'], 'anchor binding mismatch')
    W.validate_run(size, phase, selected, run, summary, W.SNAPSHOT, 8143577)
    manifest = json.dumps(dict(schema='pv1.next-receipt-copy.v1', binding=binding,
                         sha256={n:digest(b) for n,b in data.items()}), sort_keys=True).encode()+b'\n'
    expected = {n:data[n] for n in ('run.json', 'summary.json')}
    expected['copy-receipt.json'] = manifest
    parent = root/'next-run-receipts'
    safe(parent); parent.mkdir(exist_ok=True)
    dest = parent/size
    safe(dest)
    if dest.exists():
        require(dest.is_dir() and {p.name for p in dest.iterdir()} == set(expected), 'existing destination conflict')
        for n,b in expected.items():
            p = dest/n
            safe(p)
            require(p.is_file() and p.read_bytes() == b, 'existing destination bytes/binding conflict')
    else:
        with tempfile.TemporaryDirectory(dir=parent, prefix='.copy-') as tmp:
            incoming = Path(tmp)/size
            incoming.mkdir()
            for n,b in expected.items():
                with (incoming/n).open('xb') as f:
                    f.write(b); f.flush(); os.fsync(f.fileno())
                require((incoming/n).read_bytes() == b, 'local write mismatch')
            sync(incoming)
            rename_new(incoming, dest)
            sync(parent)
    return json.loads(manifest)


def attempt(root):
    try:
        response = fetch()
    except (OSError, subprocess.TimeoutExpired) as e:
        raise TransportError(str(e)) from e
    done, waiting = {}, []
    require('error' not in response, response.get('error', ''))
    require(set(response) == set(SIZES), 'unexpected remote response')
    for size in SIZES:
        item = response[size]
        require(item['status'] in ('missing', 'ready'), 'unknown source status')
        if item['status'] == 'ready':
            done[size] = publish(root, size, item)
        else:
            waiting.append(size+': '+item['reason'])
    return done, waiting


def state(root, value):
    p = root/'next-run-receipts-owner.json'
    safe(p)
    with tempfile.NamedTemporaryFile(dir=root, prefix='.receipt-state-', delete=False) as f:
        tmp = Path(f.name)
        f.write(json.dumps(value, sort_keys=True).encode()+b'\n'); f.flush(); os.fsync(f.fileno())
    tmp.replace(p); sync(root)


def run(revision):
    require(os.uname().nodename.split('.')[0] == '127x05' and os.getpriority(os.PRIO_PROCESS, 0) >= 10,
            'requires 05 and nice >=10')
    safe(ROOT)
    with locked(ROOT/'next-run-receipts-owner.lock'):
        W.verify_review(revision)
        ident = dict(pid=os.getpid(), start=Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19],
                     boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                     script_sha256=digest(HERE.read_bytes()), revision=revision, started=time.time())
        last_failure = None
        state(ROOT, dict(ident, status='starting', wait_reason='first source check', done={}, last_failure=None))
        while True:
            try:
                W.verify_review(revision)
                available = next(int(l.split()[1]) for l in Path('/proc/meminfo').read_text().splitlines()
                                 if l.startswith('MemAvailable:'))
                require(available >= 29*1024**2 and os.getloadavg()[0] <= 90, '05 host guard threshold')
                try:
                    done, waiting = attempt(ROOT)
                except TransportError as e:
                    last_failure = str(e)
                    done, waiting = {}, ['08 transport failure: '+last_failure]
                status = 'done' if len(done) == 2 else 'waiting'
                state(ROOT, dict(ident, status=status, wait_reason=waiting, done=done,
                                 last_failure=last_failure, updated=time.time()))
                print(json.dumps(dict(status=status, wait_reason=waiting, last_failure=last_failure)), flush=True)
                if status == 'done':
                    return
            except Exception as e:
                state(ROOT, dict(ident, status='failed', wait_reason=str(e), last_failure=last_failure, updated=time.time()))
                raise
            time.sleep(60)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reviewed-revision', required=True)
    run(parser.parse_args().reviewed_revision)
