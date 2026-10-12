"""X4S-3 (exploration, NEVER ADOPTABLE): local-only verification and sealing of copied
G shards against the six-million concat manifest 7e21f90a. r2 (Sol review r1 P1-P4, P6).

Modes are fixed: g08 = 127x08 batch-00000..00010 (2,645,689 roots) in <job>/data/g08;
g01 = 127x01 batch-00000..00001 (149,385 roots) in <job>/data/g01. Root, receipt path,
host, shard list, source paths and total are bound by the mode; the total is derived from
the pinned manifest items and must equal the mode constant.

Rules (R3 verify_g): eligible root = teacher_root & wait_kind==0 & supervision valid; each
eligible root has a non-empty candidate slice with a valid WAIT (2304) and finite scores on
valid candidates. Inventory is exact and link-free: the root holds only the expected real
shard directories plus named operational receipts; each shard holds exactly its seal's files
plus its own top-level manifest.json, only directories that are ancestors of those files, no
links, no special files, no multiply-linked files. Every check is an explicit raise (valid
under python -O). On success all verified corpus files lose every write bit (mandatory) and
this is re-checked before passed=true. The receipt <root>/VERIFY-RECEIPT.json is created with
O_EXCL|O_NOFOLLOW and must not exist beforehand.
"""
import argparse, hashlib, json, os, stat, subprocess, sys, time
from pathlib import Path, PurePosixPath
import numpy as np

JOB = Path('/mpac/sdicks02/jobs/clasher/x4s3-student-scale-20261012')
CONCAT = '7e21f90a14f96fbd462dc29f0e109e80775eded5cf27bdc91417714a4e8268d2'
R1 = '1c8e1f4969bab3d2416fb5b19d50b105ed5f35bb05df7b33caaa4c9edf5c737b'
PACKED = '/mpac/sdicks02/jobs/clasher/exit-g-topup-20261010/packed'
MODES = {
    'g08': dict(host='127x08', shards=[f'batch-{i:05d}' for i in range(11)], roots=2645689,
                receipts={'source-stat.txt', 'pull-start-utc.txt', 'pull-end-utc.txt'}),
    'g01': dict(host='127x01', shards=['batch-00000', 'batch-00001'], roots=149385,
                receipts={'copy-start-utc.txt', 'copy-end-utc.txt'}),
}
RECEIPT = 'VERIFY-RECEIPT.json'
SCHEMA = 'clasher.exit-r1.teacher-v6.v1'


class ValidationError(Exception):
    pass


def check(cond, msg):
    if not cond:
        raise ValidationError(msg)


def real_dir_chain(path):
    """Every component of the absolute path must exist as a real directory (lstat)."""
    check(path.is_absolute(), f'not absolute: {path}')
    cur = Path('/')
    for part in path.parts[1:]:
        cur = cur/part
        try:
            st = os.lstat(cur)
        except FileNotFoundError:
            raise ValidationError(f'missing: {cur}')
        check(stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode), f'not a real directory: {cur}')


def open_regular(path):
    """Open without following a final symlink; require a single-link regular file."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as e:
        raise ValidationError(f'cannot open without following links: {path}: {e!r}')
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        os.close(fd)
        raise ValidationError(f'not a single-link regular file: {path}')
    return fd


def sha(path):
    fd = open_regular(path)
    h = hashlib.sha256()
    with os.fdopen(fd, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def scan(top):
    """Link-free walk: (regular-file relpaths, directory relpaths). Rejects links and specials."""
    files, dirs, stack = set(), set(), ['']
    while stack:
        rel = stack.pop()
        with os.scandir(top/rel if rel else top) as it:
            for e in it:
                r = f'{rel}/{e.name}' if rel else e.name
                if e.is_symlink():
                    raise ValidationError(f'symlink: {top/r}')
                if e.is_dir(follow_symlinks=False):
                    dirs.add(r); stack.append(r)
                elif e.is_file(follow_symlinks=False):
                    st = e.stat(follow_symlinks=False)
                    check(st.st_nlink == 1, f'multiply-linked file: {top/r}')
                    files.add(r)
                else:
                    raise ValidationError(f'special file: {top/r}')
    return files, dirs


def safe_key(k):
    p = PurePosixPath(k)
    check(isinstance(k, str) and k and not p.is_absolute() and '..' not in p.parts and '.' not in p.parts
          and str(p) == k, f'unsafe seal key: {k!r}')


def verify(mode, concat_path, root, result):
    m_spec = MODES[mode]
    real_dir_chain(root)
    check(sha(concat_path) == CONCAT, 'concat manifest SHA')
    m = json.loads(Path(concat_path).read_text())
    check(m.get('complete') is True and m.get('parent_r1_manifest_sha256') == R1, 'concat manifest not complete / wrong parent')
    items = [s for s in m['shards'] if s['host'] == m_spec['host']]
    check(len(items) > 0, 'empty selection')
    names = [Path(s['path']).name for s in items]
    check(names == m_spec['shards'], f'shard list {names}')
    check(all(s['path'] == f"{PACKED}/{Path(s['path']).name}" and s['source_host'] == m_spec['host'] for s in items), 'source paths')
    total = sum(int(s['root_decisions']) for s in items)
    check(total == m_spec['roots'], f'manifest total {total} != {m_spec["roots"]}')
    # Root inventory: exact shard dirs plus named receipts (receipt file itself must not pre-exist).
    entries = {}
    with os.scandir(root) as it:
        for e in it:
            check(not e.is_symlink(), f'symlink at root: {e.name}')
            entries[e.name] = 'dir' if e.is_dir(follow_symlinks=False) else 'file' if e.is_file(follow_symlinks=False) else 'special'
    check(RECEIPT not in entries, 'receipt already exists')
    check(sorted(n for n, t in entries.items() if t == 'dir') == m_spec['shards'], 'root directories != expected shards')
    extra = {n for n, t in entries.items() if t != 'dir'} - m_spec['receipts']
    check(not extra, f'unexpected root entries: {sorted(extra)}')
    for n in m_spec['receipts'] & set(entries):
        check(os.lstat(root/n).st_nlink == 1, f'multiply-linked receipt {n}')
    roots, corpus_files = 0, []
    for item in items:
        d = root/Path(item['path']).name
        check(sha(d/'manifest.json') == item['manifest_sha256'], f'{d.name} manifest SHA')
        seal = json.loads((d/'manifest.json').read_text())
        check(seal.get('complete') is True and seal.get('schema') == SCHEMA, f'{d.name} seal')
        keys = set(seal['files'])
        for k in keys: safe_key(k)
        check('manifest.json' not in keys, f'{d.name} seal lists manifest.json')
        files, dirs = scan(d)
        check(files - {'manifest.json'} == keys and 'manifest.json' in files, f'{d.name} file inventory differs from seal')
        needed = {str(PurePosixPath(k).parents[i]) for k in keys for i in range(len(PurePosixPath(k).parents)-1)}
        check(dirs == needed, f'{d.name} unexpected directories {sorted(dirs - needed)}')
        for name, digest in seal['files'].items():
            check(sha(d/name) == digest, f'{d.name}/{name} SHA')
        ar = {k: np.load(d/'train'/f'{k}.npy', mmap_mode='r') for k in ('teacher_root', 'teacher_wait_kind',
              'expert_action_supervision_valid', 'root_offsets', 'root_valid', 'root_actions', 'root_scores')}
        ix = np.flatnonzero(ar['teacher_root'].astype(bool) & (ar['teacher_wait_kind'] == 0)
                            & ar['expert_action_supervision_valid'].astype(bool))
        check(len(ix) == int(item['root_decisions']), f'{d.name} eligible {len(ix)} != {item["root_decisions"]}')
        lo, hi = np.asarray(ar['root_offsets'][ix]), np.asarray(ar['root_offsets'][ix+1])
        check(bool((hi > lo).all()), f'{d.name} empty root slice')
        for i0, i1 in zip(lo, hi):
            valid = ar['root_valid'][i0:i1]; actions = ar['root_actions'][i0:i1]
            check(bool(valid.any()) and bool(((actions == 2304) & valid).any()), f'{d.name} root without valid WAIT')
            check(bool(np.isfinite(ar['root_scores'][i0:i1][valid]).all()), f'{d.name} nonfinite valid score')
        roots += len(ix)
        corpus_files += [d/'manifest.json'] + [d/k for k in keys]
        result['shards'].append(dict(name=d.name, manifest_sha256=item['manifest_sha256'], files=len(keys), eligible_roots=int(len(ix))))
    check(roots == m_spec['roots'], f'total eligible {roots}')
    # Mandatory seal: remove every write bit via the opened (link-free) fd, then re-check.
    for p in corpus_files:
        fd = open_regular(p)
        try:
            os.fchmod(fd, stat.S_IMODE(os.fstat(fd).st_mode) & ~0o222)
        finally:
            os.close(fd)
    for p in corpus_files:
        st = os.lstat(p)
        check(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and not (st.st_mode & 0o222), f'still writable: {p}')
    result.update(eligible_roots=roots, sealed_files=len(corpus_files), sealed=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=sorted(MODES), required=True)
    ap.add_argument('--concat', type=Path, required=True)
    a = ap.parse_args(argv)
    root = JOB/'data'/a.mode
    start = time.monotonic()
    result = dict(passed=False, sealed=False, mode=a.mode, host=MODES[a.mode]['host'], root=str(root), shards=[],
                  concat_manifest_sha256=None, label='X4S-3 exploration, NEVER ADOPTABLE', python_optimize=sys.flags.optimize)
    try:
        verify(a.mode, a.concat, root, result)
        result.update(concat_manifest_sha256=CONCAT, passed=True)
    except Exception as e:
        result['error'] = repr(e)
    result.update(utc=subprocess.check_output(['date', '-u', '+%FT%TZ'], text=True).strip(), wall_seconds=time.monotonic()-start)
    body = (json.dumps(result, indent=2)+'\n').encode()
    real_dir_chain(root)
    fd = os.open(root/RECEIPT, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, 'wb') as f:
        f.write(body)
    print(json.dumps(result), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
