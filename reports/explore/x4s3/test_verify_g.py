"""Fixture tests for verify_g.py r3 (X4S-3, exploration). Run with and without -O:
    python test_verify_g.py && python -O test_verify_g.py
Synthetic trees only, under a fresh temporary directory. Module constants JOB, PACKED,
CONCAT and MODES['g08'] are pointed at the fixture; verification code is unchanged.
"""
import hashlib, json, os, shutil, signal, socket, stat, sys, tempfile, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_g as V

ORIG_CONCAT = V.CONCAT
SHARDS = ['batch-00000', 'batch-00001']


def h(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def make_shard(d, roots=3, bad_wait=False):
    (d/'train').mkdir(parents=True)
    n = roots+1
    arrays = dict(teacher_root=np.r_[np.ones(roots, bool), False], teacher_wait_kind=np.zeros(n, np.int8),
                  expert_action_supervision_valid=np.ones(n, bool), root_offsets=np.arange(0, 2*(n+1), 2, dtype=np.int64),
                  root_valid=np.ones(2*n, bool), root_actions=np.tile([5 if bad_wait else 2304, 7], n).astype(np.int16),
                  root_scores=np.zeros(2*n, np.float32))
    for k, v in arrays.items(): np.save(d/'train'/f'{k}.npy', v)
    (d/'mask_table.npy').write_bytes(b'mask'); (d/'sources.json').write_text('{}')
    files = {str(p.relative_to(d)): h(p) for p in sorted(d.rglob('*')) if p.is_file()}
    (d/'manifest.json').write_text(json.dumps(dict(schema=V.SCHEMA, complete=True, files=files)))
    return roots


def fixture(tmp, **kw):
    job = tmp/'job'; root = job/'data'/'g08'; root.mkdir(parents=True)
    packed = '/fixture/exit-g-topup/packed'
    items = []
    for s in SHARDS:
        r = make_shard(root/s, bad_wait=kw.get('bad_wait', False))
        items.append(dict(host='127x08', path=f'{packed}/{s}', manifest_sha256=h(root/s/'manifest.json'), root_decisions=r, source_host='127x08'))
    if kw.get('no_08'): items = []
    concat = tmp/'concat.json'
    concat.write_text(json.dumps(dict(complete=kw.get('complete', True), parent_r1_manifest_sha256=V.R1, shards=items)))
    for n in ('pull-start-utc.txt', 'pull-end-utc.txt', 'source-stat.txt'): (root/n).write_text('x\n')
    V.JOB, V.PACKED = job, packed
    V.CONCAT = ORIG_CONCAT if kw.get('genuine_pin') else h(concat)
    V.MODES['g08'] = dict(V.MODES['g08'], shards=SHARDS, roots=3*len(SHARDS))
    return job, root, concat


class Hang(Exception):
    pass


def alarm(*_):
    raise Hang('verification blocked > 10 s')


def run_case(name, mutate=None, expect=False, want=None, **kw):
    tmp = Path(tempfile.mkdtemp(prefix='x4s3-vg-'))
    outside = tmp/'outside.npy'; outside.write_bytes(b'outside'); outside.chmod(0o644)
    victims = [outside]; socks = []
    try:
        job, root, concat = fixture(tmp, **kw)
        if mutate:
            extra = mutate(root, tmp, outside)
            if isinstance(extra, list): victims += [x for x in extra if isinstance(x, Path)]; socks += [x for x in extra if not isinstance(x, Path)]
        t0 = time.monotonic(); signal.signal(signal.SIGALRM, alarm); signal.alarm(10)
        try:
            rc = V.main(['--mode', 'g08', '--concat', str(concat)])
        except Exception as e:  # receipt could not be written (confinement failure) or a hang
            rc, raised = 'raised', repr(e)
        else:
            raised = None
        finally:
            signal.alarm(0)
        seconds = round(time.monotonic()-t0, 3)
        rec_path = root/V.RECEIPT
        rec = json.loads(rec_path.read_text()) if rec_path.is_file() and not rec_path.is_symlink() and not kw.get('pre_receipt') else None
        passed = bool(rec and rec['passed'])
        outside_writable = all(v.stat().st_mode & 0o200 for v in victims)
        error = (rec or {}).get('error') or raised
        ok = (passed == expect) and outside_writable and (rc == 0) == expect and seconds < 10 and 'Hang' not in str(error)
        if want is not None:
            ok = ok and want in str(error)
        if expect:
            data = [p for p in root.rglob('*') if p.is_file() and p.name != V.RECEIPT and p.parent != root]
            ok = ok and rec['sealed'] and all(not (p.stat().st_mode & 0o222) for p in data)
        print(json.dumps(dict(case=name, ok=ok, rc=rc, passed=passed, error=error, want=want, seconds=seconds,
                              victims_still_writable=outside_writable, optimize=sys.flags.optimize)))
        return ok
    finally:
        for sk in socks: sk.close()
        for p in tmp.rglob('*'):
            if not p.is_symlink(): p.chmod(0o755 if p.is_dir() else 0o644)
        shutil.rmtree(tmp)


def symlink_file(root, tmp, outside):
    p = root/'batch-00000'/'mask_table.npy'
    outside.write_bytes(p.read_bytes()); p.unlink(); p.symlink_to(outside)


def hardlink_file(root, tmp, outside):
    os.link(root/'batch-00000'/'sources.json', tmp/'hl'); (tmp/'hl').chmod(0o644)
    return [tmp/'hl']  # the linked inode itself must keep its write bit


def fifo_at(rel):
    def m(root, tmp, outside):
        p = root/rel; p.unlink() if p.exists() else None; os.mkfifo(p)
    return m


def socket_at(rel):
    def m(root, tmp, outside):
        p = root/rel; p.unlink() if p.exists() else None
        sk = socket.socket(socket.AF_UNIX); sk.bind(str(p)); return [sk]
    return m


def fifo_concat(root, tmp, outside):
    c = tmp/'concat.json'; c.unlink(); os.mkfifo(c)


def symlink_ancestor(root, tmp, outside):
    data = root.parent; real = tmp/'real-data'; data.rename(real); data.symlink_to(real)


def main():
    cases = [
        ('valid', None, True, None, {}),
        ('wrong_concat_pin', None, False, 'concat manifest SHA', dict(genuine_pin=True)),
        ('concat_incomplete', None, False, 'not complete', dict(complete=False)),
        ('empty_selection', None, False, 'empty selection', dict(no_08=True)),
        ('extra_root_file', lambda r, t, o: (r/'stray.txt').write_text('x'), False, 'unexpected root entries', {}),
        ('unlisted_train_manifest', lambda r, t, o: (r/'batch-00000'/'train'/'manifest.json').write_text('{}'), False, 'file inventory differs', {}),
        ('dangling_symlink', lambda r, t, o: (r/'batch-00001'/'dangling').symlink_to(t/'nope'), False, 'symlink', {}),
        ('extra_empty_dir', lambda r, t, o: (r/'batch-00001'/'empty').mkdir(), False, 'unexpected directories', {}),
        ('extra_root_dir', lambda r, t, o: (r/'batch-00002').mkdir(), False, 'root directories != expected shards', {}),
        ('symlinked_listed_file', symlink_file, False, 'symlink', {}),
        ('hardlinked_file', hardlink_file, False, 'multiply-linked', {}),
        ('symlink_ancestor', symlink_ancestor, False, 'not a real directory', {}),
        ('missing_file', lambda r, t, o: (r/'batch-00000'/'sources.json').unlink(), False, 'file inventory differs', {}),
        ('data_sha_mismatch', lambda r, t, o: (r/'batch-00000'/'sources.json').write_text('{"x":1}'), False, 'sources.json SHA', {}),
        ('fifo_in_shard', fifo_at('batch-00000/fifo'), False, 'special file', {}),
        ('invalid_wait', None, False, 'without valid WAIT', dict(bad_wait=True)),
        ('receipt_preexists', lambda r, t, o: (r/V.RECEIPT).write_text('{}'), False, 'File exists', dict(pre_receipt=True)),
        ('fifo_root_other_name', fifo_at('stray.fifo'), False, 'special root entries', {}),
        ('socket_root_other_name', socket_at('stray.sock'), False, 'special root entries', {}),
        ('fifo_shard_manifest', fifo_at('batch-00000/manifest.json'), False, 'not a single-link regular file', {}),
        ('fifo_concat', fifo_concat, False, 'not a single-link regular file', {}),
        ('hardlinked_receipt', lambda r, t, o: (os.link(r/'pull-start-utc.txt', t/'hl-receipt'), (t/'hl-receipt').chmod(0o644), [t/'hl-receipt'])[-1], False, 'is not a single-link regular file', {}),
    ]
    for n in sorted(V.MODES['g08']['receipts']):
        cases += [(f'fifo_receipt_{n}', fifo_at(n), False, 'special root entries', {}),
                  (f'socket_receipt_{n}', socket_at(n), False, 'special root entries', {})]
    results = [run_case(n, m, e, w, **kw) for n, m, e, w, kw in cases]
    print(json.dumps(dict(all_ok=all(results), cases=len(results), optimize=sys.flags.optimize)))
    return 0 if all(results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
