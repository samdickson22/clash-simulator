"""X4S-4 I/O gate (exploration, NEVER ADOPTABLE). r3 after Sol script review r2 (R2-F1, R2-F3, R2-F4, R2-F6).

The ONE module through which every X4S-4 read, write, subprocess and signal goes. Stdlib only, Python 3.8+, Linux.

Vendored from the K4S shared layer safe_input r1 (reports/explore/k4s-confirm/run-r1/end-prep/safe-input-r1/safe_input.py,
blob c7e3fce7681410483c8064c882bae3b26772e62c, SHA-256 5a42036c...0bebedb; commit 4c9439de): check_abs/check_rel,
open_dirs/open_root (component-wise O_DIRECTORY|O_NOFOLLOW walk with dev/ino re-check), open_leaf (descriptor gate:
regular, st_nlink == 1, cap, same dev/ino after open), read_exact (exact size; growth/shrink refuse), loads_strict
(duplicate keys and NaN/Infinity refuse), exclusive creation + linkat no-clobber publication, and run_checked
(explicit absolute argv, exact environment, bounded output, group watchdog, rc checked before stdout is used). Its
K4S name policy (which forbids a `games` component) is NOT vendored: X4S-4 uses its own declared roots below.

X4S-4 additions:
  * Write confinement: absolute canonical paths strictly below the job root (an allowed first-level role) or, for two
    exact names, below the report directory. Every component is opened with O_NOFOLLOW from a canonically opened
    root; nothing writes through an existing inode: new files are O_CREAT|O_EXCL; replacement is an exclusive temp
    file + renameat over a final that must be absent or a regular single-link file; appends open O_APPEND|O_NOFOLLOW
    and refuse a hard-linked or non-regular target before writing; removal is fd-based and never follows a link.
  * Reads: the parent directory is opened canonically and the leaf passes the descriptor gate (no symlink, no hard
    link, no special file) before any byte is read.
  * Processes: owned process groups are recorded as (pgid, leader starttime); signals go to individual verified PIDs
    of that group (never a pattern, never a bare group signal), re-checking each PID's starttime just before kill.
    (/proc pseudo-files - stat, meminfo, pressure, smaps_rollup - are kernel interfaces read directly by
    x4s4io/studytree/supervise; they are not filesystem data and cannot be aliased.)
    r4 (Sol R3-F8): there is NO group-level signal anywhere - run_checked's watchdog/limit kill of the short helper it
    started in a new session also enumerates that session's verified members and signals each PID individually.
  * Git: scrubbed exact environment, --no-replace-objects, GIT_NO_REPLACE_OBJECTS, a null graft file, no hooks, no
    optional locks; committed bytes are obtained by walking commit -> tree -> blob objects whose bytes are each
    hashed against their object id (replace refs and indirection cannot substitute content).
Every check is an explicit raise of Refusal (never an assert), so all hold under -O/-OO.

Accepted residuals (as K4S r1, disclosed): an in-place same-size rewrite by another local actor during a read is not
detected unless an expected SHA is given; a rename_tree destination appearing between its absence check and the
rename is not detected (no RENAME_NOREPLACE in the 3.8 stdlib); a PID reused between its starttime check and kill.
"""
import errno, hashlib, json, os, re, secrets, signal, stat, subprocess, threading, time

JOB = '/mpac/sdicks02/jobs/clasher/x4s4-onpolicy'
REPORT_ROOT = '/mpac/sdicks02/repos/clasher/reports/explore/x4s4'
REPO = '/mpac/sdicks02/repos/clasher'
ROLES = ('collect', 'games', 'data', 'receipts', 'analysis', 'qual', 'calibration', 'driver', 'fits', 'logs', 'smoke',
         'attempts', 'cache', 'inputs', 'fit')
JOB_FILES = ('STOP', 'FIT.STOP', 'REPORTING.GO', 'HARD-STOP-UTC.txt', 'RUNTIME-INVENTORY.json')
RT_ROLE = re.compile(r'rt-(R3a|R3a-rep|R5|R5-rep|R5W)')
REPORT_NAMES = ('RESULTS.md', 'seed-audit.json', 'seed-sources.json')
CHUNK = 1 << 20
LINGER_GRACE = 5
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
LEAF_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOCTTY | os.O_CLOEXEC
MAX_READ = 64 << 30


class Refusal(Exception):
    """Fail-closed refusal. `code` is a stable class; `reason` is human text."""
    def __init__(self, code, reason):
        Exception.__init__(self, code+': '+reason)
        self.code, self.reason = code, reason


def refuse(code, reason): raise Refusal(code, reason)
def require(cond, code, reason):
    if not cond: refuse(code, reason)


# ---------------------------------------------------------------- vendored path primitives (safe_input r1)
def _bad_text(text): return '\\' in text or any(ord(c) < 32 or ord(c) == 127 for c in text)


def check_abs(path):
    path = str(path)
    if not path.startswith('/') or path.startswith('//') or path == '/' or path.endswith('/') or _bad_text(path):
        refuse('path', 'not a usable absolute path: %r' % (path,))
    parts = path[1:].split('/')
    if any(p in ('', '.', '..') for p in parts): refuse('path', "empty, '.' or '..' component: %r" % (path,))
    return parts


def check_rel(rel):
    if not isinstance(rel, str) or rel == '' or rel.startswith('/') or rel.endswith('/') or _bad_text(rel):
        refuse('path', 'not a usable relative path: %r' % (rel,))
    parts = rel.split('/')
    if any(p in ('', '.', '..') for p in parts): refuse('path', "empty, '.' or '..' component: %r" % (rel,))
    return parts


def _classify(error):
    return {errno.ELOOP: 'symlink', errno.ENOTDIR: 'not-dir', errno.ENOENT: 'missing'}.get(error.errno, 'open')


def open_dirs(start_fd, parts, label, create=False, mode=0o755):
    """openat each component with O_DIRECTORY|O_NOFOLLOW (fstatat first, same dev/ino after); with create=True a
    missing component is made with mkdirat. Returns a NEW fd."""
    fd = os.dup(start_fd)
    try:
        for part in parts:
            try:
                st = os.stat(part, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                if not create: refuse('missing', '%s: component %r missing' % (label, part))
                try: os.mkdir(part, mode, dir_fd=fd)
                except FileExistsError: pass
                st = os.stat(part, dir_fd=fd, follow_symlinks=False)
            except OSError as error:
                refuse(_classify(error), '%s: component %r: %s' % (label, part, os.strerror(error.errno)))
            if stat.S_ISLNK(st.st_mode): refuse('symlink', '%s: component %r is a symlink' % (label, part))
            if not stat.S_ISDIR(st.st_mode): refuse('not-dir', '%s: component %r is not a directory' % (label, part))
            try:
                nxt = os.open(part, DIR_FLAGS, dir_fd=fd)
            except OSError as error:
                code = _classify(error)
                try:
                    if stat.S_ISLNK(os.stat(part, dir_fd=fd, follow_symlinks=False).st_mode): code = 'symlink'
                except OSError:
                    pass
                refuse(code, '%s: component %r: %s' % (label, part, os.strerror(error.errno)))
            now = os.fstat(nxt)
            if not stat.S_ISDIR(now.st_mode) or (now.st_dev, now.st_ino) != (st.st_dev, st.st_ino):
                os.close(nxt); refuse('changed', '%s: component %r changed between check and open' % (label, part))
            os.close(fd); fd = nxt
    except BaseException:
        os.close(fd); raise
    return fd


def open_root(root):
    """A canonical root directory: every ancestor lstat'ed (no symlink), realpath == root, then a component-wise
    O_NOFOLLOW walk from '/'. Returns an fd."""
    root = str(root); parts = check_abs(root)
    for i in range(len(parts)):
        prefix = '/'+'/'.join(parts[:i+1])
        try: st = os.lstat(prefix)
        except OSError as error: refuse('root', 'root %s: %s: %s' % (root, prefix, os.strerror(error.errno)))
        if stat.S_ISLNK(st.st_mode): refuse('root', 'root %s: ancestor or root %s is a symlink' % (root, prefix))
        if not stat.S_ISDIR(st.st_mode): refuse('root', 'root %s: %s is not a directory' % (root, prefix))
    if os.path.realpath(root) != root: refuse('root', 'root %s is not canonical' % root)
    top = os.open('/', DIR_FLAGS)
    try: return open_dirs(top, parts, 'root '+root)
    except Refusal as error: refuse('root', error.reason)
    finally: os.close(top)


def open_leaf(dir_fd, name, cap, expected_size, label):
    """Descriptor gate: fstatat (no open) refuses symlink / non-regular / st_nlink != 1 / oversize; then
    O_NOFOLLOW|O_NONBLOCK open and fstat: regular, same dev/ino, st_nlink == 1, size within cap."""
    try: st = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
    except OSError as error: refuse(_classify(error), '%s: %s' % (label, os.strerror(error.errno)))
    if stat.S_ISLNK(st.st_mode): refuse('symlink', '%s: leaf is a symlink' % label)
    if not stat.S_ISREG(st.st_mode): refuse('not-regular', '%s: leaf is not a regular file (mode %o)' % (label, st.st_mode))
    if st.st_nlink != 1: refuse('nlink', '%s: hard-linked leaf (st_nlink %d)' % (label, st.st_nlink))
    if st.st_size > cap or (expected_size is not None and st.st_size != expected_size):
        refuse('size', '%s: size %d (cap %d, expected %r)' % (label, st.st_size, cap, expected_size))
    try: fd = os.open(name, LEAF_FLAGS, dir_fd=dir_fd)
    except OSError as error: refuse(_classify(error), '%s: %s' % (label, os.strerror(error.errno)))
    now = os.fstat(fd); problem = None
    if not stat.S_ISREG(now.st_mode): problem = ('not-regular', 'opened object is not a regular file')
    elif (now.st_dev, now.st_ino) != (st.st_dev, st.st_ino): problem = ('changed', 'leaf changed between check and open')
    elif now.st_nlink != 1: problem = ('nlink', 'hard-linked leaf at open (st_nlink %d)' % now.st_nlink)
    elif now.st_size > cap: problem = ('size', 'size at open %d (cap %d)' % (now.st_size, cap))
    if problem is not None:
        os.close(fd); refuse(problem[0], '%s: %s' % (label, problem[1]))
    return fd, now


def read_exact(fd, size, sink, label):
    left = size
    while left:
        chunk = os.read(fd, min(CHUNK, left))
        if not chunk: refuse('shrink', '%s: file shrank while read' % label)
        sink(chunk); left -= len(chunk)
    if os.read(fd, 1): refuse('growth', '%s: file grew while read' % label)
    if os.fstat(fd).st_size != size: refuse('growth', '%s: size changed while read' % label)


def _no_dups(pairs):
    out = {}
    for k, v in pairs:
        require(k not in out, 'json', 'duplicate key %r' % k); out[k] = v
    return out


def _no_constant(name): refuse('json', 'non-finite constant %s' % name)


def _finite_float(text):
    v = float(text)
    if v != v or v in (float('inf'), float('-inf')): refuse('json', 'non-finite number %s (exponent overflow)' % text[:40])
    return v


def loads_strict(data, label='json', object_pairs_hook=None):
    """Strict UTF-8 JSON: duplicate keys, NaN/Infinity literals and numbers that decode to a non-finite float (e.g.
    1e999) refuse. A projection hook replaces the plain duplicate check with its own (which also refuses duplicates)."""
    try: text = data.decode('utf-8')
    except UnicodeDecodeError: refuse('json', '%s: not UTF-8' % label)
    try: return json.loads(text, object_pairs_hook=object_pairs_hook or _no_dups, parse_constant=_no_constant, parse_float=_finite_float)
    except ValueError as error: refuse('json', '%s: %s' % (label, error))


def dumps(obj, indent=2):
    return (json.dumps(obj, indent=indent, allow_nan=False)+'\n').encode()


# ---------------------------------------------------------------- reads
def _split(path):
    parts = check_abs(path)
    return '/'+'/'.join(parts[:-1]) if len(parts) > 1 else None, parts[-1]


def read_bytes(path, cap=MAX_READ, expected_sha256=None, expected_size=None):
    parent, leaf = _split(path)
    require(parent is not None, 'path', 'no parent: %s' % path)
    pfd = open_root(parent)
    try:
        fd, st = open_leaf(pfd, leaf, cap, expected_size, str(path))
    finally:
        os.close(pfd)
    chunks = []
    try: read_exact(fd, st.st_size, chunks.append, str(path))
    finally: os.close(fd)
    data = b''.join(chunks)
    require(expected_sha256 is None or hashlib.sha256(data).hexdigest() == expected_sha256, 'sha', '%s SHA-256 mismatch' % path)
    return data


def sha256_file(path, cap=MAX_READ):
    parent, leaf = _split(path)
    pfd = open_root(parent)
    try: fd, st = open_leaf(pfd, leaf, cap, None, str(path))
    finally: os.close(pfd)
    h = hashlib.sha256()
    try: read_exact(fd, st.st_size, h.update, str(path))
    finally: os.close(fd)
    return h.hexdigest()


def read_json(path, cap=256 << 20, expected_sha256=None):
    return loads_strict(read_bytes(path, cap, expected_sha256), str(path))


def read_text(path, cap=1 << 20):
    try: return read_bytes(path, cap).decode('utf-8')
    except UnicodeDecodeError: refuse('json', '%s: not UTF-8' % path)


def project_json(path, keep, cap=256 << 20):
    """Parse keeping only the allowlisted keys at every level (outcome fields are never materialized)."""
    keep = frozenset(keep)
    def hook(pairs):
        out, seen = {}, set()
        for k, v in pairs:
            require(k not in seen, 'json', 'duplicate key %r' % k); seen.add(k)   # duplicates refuse even for dropped keys
            if k in keep: out[k] = v
        return out
    return loads_strict(read_bytes(path, cap), str(path), object_pairs_hook=hook)


def lstat(path):
    try: return os.lstat(str(path))
    except FileNotFoundError: return None


def lexists(path): return lstat(path) is not None


def is_real_dir(path):
    """True if path and every ancestor are real directories (no symlink anywhere)."""
    try: os.close(open_root(str(path))); return True
    except Refusal: return False


def listdir(path):
    fd = open_root(str(path))
    try: return sorted(os.listdir(fd))
    finally: os.close(fd)


def stat_leaf(path):
    """fstatat of a regular single-link leaf under a canonical parent (mtime/size identity without reading)."""
    parent, leaf = _split(path)
    pfd = open_root(parent)
    try:
        st = os.stat(leaf, dir_fd=pfd, follow_symlinks=False)
    except OSError as error:
        refuse(_classify(error), '%s: %s' % (path, os.strerror(error.errno)))
    finally:
        os.close(pfd)
    require(stat.S_ISREG(st.st_mode), 'not-regular', '%s is not a regular file' % path)
    require(st.st_nlink == 1, 'nlink', '%s is hard-linked' % path)
    return st


# ---------------------------------------------------------------- write confinement
def _target(path, roles=None, report=False):
    """(root, rel parts) of an allowed write target. roles: allowed first-level names under JOB (None = any ROLES or
    rt-<student>); report=True allows exactly REPORT_ROOT/<REPORT_NAMES>."""
    path = str(path); parts = check_abs(path)
    for root, allowed in ((JOB, None), (REPORT_ROOT, REPORT_NAMES if report else ())):
        rparts = check_abs(root)
        if parts[:len(rparts)] == rparts and len(parts) > len(rparts):
            rel = parts[len(rparts):]
            if root == REPORT_ROOT:
                require(len(rel) == 1 and rel[0] in allowed, 'policy', 'report-root write limited to %s: %s' % (REPORT_NAMES, path))
                return root, rel
            first = rel[0]
            if roles is None:
                ok = first in ROLES or bool(RT_ROLE.fullmatch(first)) or (len(rel) == 1 and first in JOB_FILES)
            else:
                ok = first in roles or (len(rel) == 1 and first in roles)
            require(ok, 'policy', 'role %r not allowed for %s' % (first, path))
            return root, rel
    refuse('policy', 'outside the declared write roots: %s' % path)


def _parent_fd(path, roles, report=False, create=False):
    root, rel = _target(path, roles, report)
    rfd = open_root(root)
    try: pfd = open_dirs(rfd, rel[:-1], str(path), create=create)
    finally: os.close(rfd)
    return pfd, rel[-1]


def check_writable(path, roles=None, report=False, must_not_exist=False):
    """Validate a write target without mutating anything (existing ancestors must be real directories)."""
    root, rel = _target(path, roles, report)
    rfd = open_root(root)
    try:
        fd = rfd
        for i, part in enumerate(rel[:-1]):
            try: st = os.stat(part, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError: break
            require(stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode), 'symlink' if stat.S_ISLNK(st.st_mode) else 'not-dir',
                    '%s: component %r' % (path, part))
            nfd = open_dirs(fd, [part], str(path)); (os.close(fd) if fd != rfd else None); fd = nfd
        else:
            try:
                st = os.stat(rel[-1], dir_fd=fd, follow_symlinks=False)
                require(not stat.S_ISLNK(st.st_mode), 'symlink', '%s is a symlink' % path)
                require(not must_not_exist, 'exists', '%s already exists' % path)
                require(stat.S_ISDIR(st.st_mode) or st.st_nlink == 1, 'nlink', '%s is hard-linked' % path)
            except FileNotFoundError:
                pass
        if fd != rfd: os.close(fd)
    finally:
        os.close(rfd)
    return str(path)


def mkdirs(path, roles=None, mode=0o755):
    """Create a confined directory chain (each component a real directory, made with mkdirat)."""
    root, rel = _target(path, roles)
    rfd = open_root(root)
    try: os.close(open_dirs(rfd, rel, str(path), create=True, mode=mode))
    finally: os.close(rfd)
    return str(path)


def mkdir_excl(path, roles=None, mode=0o755):
    pfd, leaf = _parent_fd(path, roles, create=True)
    try:
        try: os.mkdir(leaf, mode, dir_fd=pfd)
        except FileExistsError: refuse('exists', '%s already exists' % path)
        os.fsync(pfd)
    finally: os.close(pfd)
    return str(path)


def _write_all(fd, data):
    view = memoryview(data)
    while view: view = view[os.write(fd, view):]


def create_excl(path, data, roles=None, mode=0o444, report=False):
    """Exclusive creation (never truncates or replaces); fsync file and directory; fchmod mode."""
    pfd, leaf = _parent_fd(path, roles, report, create=True)
    try:
        try: fd = os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=pfd)
        except FileExistsError: refuse('exists', '%s already exists (never overwritten)' % path)
        try:
            _write_all(fd, data); os.fsync(fd); os.fchmod(fd, mode)
        finally: os.close(fd)
        os.fsync(pfd)
    finally: os.close(pfd)
    return hashlib.sha256(data).hexdigest()


def write_json_once(path, obj, roles=None, mode=0o444, report=False):
    return create_excl(path, dumps(obj), roles, mode, report)


def replace_bytes(path, data, roles=None, mode=0o644, report=False):
    """Atomic replacement: exclusive temp in the same directory, fsync, then renameat over the final name. The final,
    if present, must be a regular single-link file (a symlink, hard link or directory refuses); its inode is never
    written, so no other link to it can change."""
    pfd, leaf = _parent_fd(path, roles, report, create=True)
    try:
        try:
            st = os.stat(leaf, dir_fd=pfd, follow_symlinks=False)
            require(not stat.S_ISLNK(st.st_mode), 'symlink', '%s is a symlink' % path)
            require(stat.S_ISREG(st.st_mode), 'not-regular', '%s is not a regular file' % path)
            require(st.st_nlink == 1, 'nlink', '%s is hard-linked (st_nlink %d)' % (path, st.st_nlink))
        except FileNotFoundError:
            pass
        tmp = '.%s.x4s4tmp-%d-%s' % (leaf, os.getpid(), secrets.token_hex(6))
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=pfd)
        try:
            _write_all(fd, data); os.fsync(fd); os.fchmod(fd, mode)
        finally: os.close(fd)
        os.rename(tmp, leaf, src_dir_fd=pfd, dst_dir_fd=pfd)
        os.fsync(pfd)
    finally: os.close(pfd)
    return hashlib.sha256(data).hexdigest()


def replace_json(path, obj, roles=None, mode=0o644, report=False):
    return replace_bytes(path, dumps(obj), roles, mode, report)


def open_append(path, roles=None):
    """An O_APPEND fd on a regular single-link file (created if absent); a symlink or hard link refuses before any
    byte is written. The caller owns the fd (e.g. a child's log)."""
    pfd, leaf = _parent_fd(path, roles, create=True)
    try:
        pre = None
        try:                                                    # R3-F7: classify the leaf BEFORE any open attempt
            pre = os.stat(leaf, dir_fd=pfd, follow_symlinks=False)
            require(not stat.S_ISLNK(pre.st_mode), 'symlink', '%s is a symlink' % path)
            require(stat.S_ISREG(pre.st_mode), 'not-regular', '%s is not a regular file (mode %o)' % (path, pre.st_mode))
            require(pre.st_nlink == 1, 'nlink', '%s is hard-linked' % path)
        except FileNotFoundError:
            pass
        flags = os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOCTTY | os.O_CLOEXEC
        try: fd = os.open(leaf, flags if pre is not None else flags | os.O_CREAT | os.O_EXCL, 0o644, dir_fd=pfd)
        except OSError as error: refuse(_classify(error), '%s: %s' % (path, os.strerror(error.errno)))
    finally: os.close(pfd)
    st = os.fstat(fd)
    problem = None
    if not stat.S_ISREG(st.st_mode): problem = ('not-regular', 'opened object is not a regular file')
    elif st.st_nlink != 1: problem = ('nlink', 'hard-linked at open')
    elif pre is not None and (st.st_dev, st.st_ino) != (pre.st_dev, pre.st_ino): problem = ('changed', 'leaf changed between check and open')
    if problem:
        os.close(fd); refuse(problem[0], '%s: %s' % (path, problem[1]))
    import fcntl
    fcntl.fcntl(fd, fcntl.F_SETFL, fcntl.fcntl(fd, fcntl.F_GETFL) & ~os.O_NONBLOCK)
    return fd


def append_bytes(path, data, roles=None):
    fd = open_append(path, roles)
    try: _write_all(fd, data); os.fsync(fd)
    finally: os.close(fd)


def append_json_line(path, obj, roles=None):
    append_bytes(path, (json.dumps(obj, allow_nan=False)+'\n').encode(), roles)


def _remove_at(dfd, name):
    st = os.stat(name, dir_fd=dfd, follow_symlinks=False)
    if stat.S_ISDIR(st.st_mode):
        sub = os.open(name, DIR_FLAGS, dir_fd=dfd)
        try:
            now = os.fstat(sub)
            require((now.st_dev, now.st_ino) == (st.st_dev, st.st_ino), 'changed', 'directory %s changed' % name)
            for entry in os.listdir(sub): _remove_at(sub, entry)
        finally: os.close(sub)
        os.rmdir(name, dir_fd=dfd)
    else:
        os.unlink(name, dir_fd=dfd)                          # a symlink is removed as a link, never followed


def remove_tree(path, roles=None):
    """fd-based removal of a confined file or tree; links are removed, never followed."""
    pfd, leaf = _parent_fd(path, roles)
    try:
        try: _remove_at(pfd, leaf)
        except FileNotFoundError: pass
        os.fsync(pfd)
    finally: os.close(pfd)


def rename_path(src, dst, roles=None):
    """Rename within the job; the destination must be absent (a residual race is disclosed above)."""
    sfd, sleaf = _parent_fd(src, roles)
    try:
        dfd, dleaf = _parent_fd(dst, roles, create=True)
        try:
            require(lstat(dst) is None, 'exists', '%s already exists (never replaced)' % dst)
            st = os.stat(sleaf, dir_fd=sfd, follow_symlinks=False)
            require(not stat.S_ISLNK(st.st_mode), 'symlink', '%s is a symlink' % src)
            os.rename(sleaf, dleaf, src_dir_fd=sfd, dst_dir_fd=dfd)
            os.fsync(dfd); os.fsync(sfd)
        finally: os.close(dfd)
    finally: os.close(sfd)


def copy_file(src, dst, roles=None, mode=0o444, expected_sha256=None):
    data = read_bytes(src, MAX_READ, expected_sha256)
    return create_excl(dst, data, roles, mode)


def copy_tree_fresh(src, dst, roles=None):
    """Copy a source tree into a NEW confined destination. Source: canonical root, regular single-link files and
    directories; symlinks are recreated as symlinks with the same text (never followed); special files refuse."""
    require(lstat(dst) is None, 'exists', '%s already exists' % dst)
    sroot = open_root(str(src))
    mkdir_excl(dst, roles)
    droot = open_root(str(dst))
    def walk(sfd, dfd, label):
        for name in sorted(os.listdir(sfd)):
            st = os.stat(name, dir_fd=sfd, follow_symlinks=False)
            if stat.S_ISLNK(st.st_mode):
                os.symlink(os.readlink(name, dir_fd=sfd), name, dir_fd=dfd)
            elif stat.S_ISDIR(st.st_mode):
                os.mkdir(name, 0o755, dir_fd=dfd)
                s2 = open_dirs(sfd, [name], label); d2 = open_dirs(dfd, [name], label)
                try: walk(s2, d2, label+'/'+name)
                finally: os.close(s2); os.close(d2)
            elif stat.S_ISREG(st.st_mode):
                fd, fst = open_leaf(sfd, name, MAX_READ, None, label+'/'+name)
                try:
                    out = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=dfd)
                    try:
                        read_exact(fd, fst.st_size, lambda c: _write_all(out, c), label+'/'+name)
                        os.fchmod(out, stat.S_IMODE(fst.st_mode))
                    finally: os.close(out)
                finally: os.close(fd)
            else:
                refuse('not-regular', '%s/%s is a special file' % (label, name))
    try: walk(sroot, droot, str(src))
    finally: os.close(sroot); os.close(droot)


def chmod_readonly(path):
    parent, leaf = _split(path)
    pfd = open_root(parent)
    try:
        fd, st = open_leaf(pfd, leaf, MAX_READ, None, str(path))
    finally: os.close(pfd)
    try: os.fchmod(fd, stat.S_IMODE(st.st_mode) & ~0o222)
    finally: os.close(fd)


def create_stop(job=None):
    """Create <job>/STOP (exclusive; an existing entry of any kind already means STOP)."""
    path = (job or JOB)+'/STOP'
    if lexists(path): return path
    try: create_excl(path, b'', roles=('STOP',), mode=0o644)
    except Refusal as r:
        if r.code != 'exists': raise
    return path


# ---------------------------------------------------------------- subprocess (vendored run_checked)
class RunResult(object):
    __slots__ = ('argv', 'rc', 'stdout', 'stderr')
    def __init__(self, argv, rc, stdout, stderr): self.argv, self.rc, self.stdout, self.stderr = argv, rc, stdout, stderr


def _argv_ok(argv):
    require(isinstance(argv, (list, tuple)) and argv and all(isinstance(a, str) and '\x00' not in a for a in argv),
            'subprocess', 'argv must be a non-empty list of strings')
    require(argv[0].startswith('/') and os.path.normpath(argv[0]) == argv[0], 'subprocess', 'argv[0] must be absolute: %r' % argv[0])


def run_checked(argv, timeout, stdout_limit, stderr_limit=1 << 16, env=None, env_allow=(), stdin_bytes=None, cwd=None, ok_rcs=(0,)):
    """Explicit argv, exact environment, bounded output, group watchdog; rc must be in ok_rcs before stdout is used."""
    _argv_ok(argv)
    require(isinstance(timeout, (int, float)) and timeout > 0, 'subprocess', 'timeout required')
    full_env = {k: os.environ[k] for k in env_allow if k in os.environ}
    full_env.update(env or {})
    try:
        proc = subprocess.Popen(list(argv), stdin=subprocess.PIPE if stdin_bytes is not None else subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=full_env, cwd=cwd,
                                start_new_session=True, close_fds=True, shell=False)
    except OSError as error:
        refuse('subprocess', 'cannot start %s: %s' % (argv[0], error))
    state = {'out': b'', 'err': b'', 'over': None, 'timed_out': False, 'stdin_error': None}
    lead = proc_stat(proc.pid)
    helper_start = lead['starttime'] if lead else None
    def kill():                                          # R3-F8: verified individual PIDs of the helper's own session
        if helper_start is not None: signal_owned(proc.pid, helper_start, signal.SIGKILL)
    def drain(stream, key, limit):
        chunks, total = [], 0
        while True:
            data = stream.read1(65536) if hasattr(stream, 'read1') else stream.read(65536)
            if not data: break
            total += len(data)
            if total > limit:
                if state['over'] is None: state['over'] = key; kill()
                continue
            chunks.append(data)
        state[key] = b''.join(chunks)
    def feed():
        try: proc.stdin.write(stdin_bytes)
        except (BrokenPipeError, OSError) as error: state['stdin_error'] = error
        finally:
            try: proc.stdin.close()
            except (BrokenPipeError, OSError): pass
    def expire(): state['timed_out'] = True; kill()
    threads = [threading.Thread(target=drain, args=(proc.stdout, 'out', stdout_limit)),
               threading.Thread(target=drain, args=(proc.stderr, 'err', stderr_limit))]
    if stdin_bytes is not None: threads.append(threading.Thread(target=feed))
    for t in threads: t.daemon = True; t.start()
    watchdog = threading.Timer(timeout, expire); watchdog.daemon = True; watchdog.start()
    try:
        proc.wait()
        for t in threads: t.join(LINGER_GRACE)
        lingering = any(t.is_alive() for t in threads)
        if lingering:
            kill()
            for t in threads: t.join(5)
    finally:
        watchdog.cancel()
    tail = state['err'][-400:].decode('utf-8', 'replace')
    require(not state['timed_out'], 'subprocess', '%s timed out after %ss: %s' % (argv[0], timeout, tail))
    require(state['over'] is None, 'subprocess', '%s: %s exceeded its bound' % (argv[0], state['over']))
    require(not lingering, 'subprocess', '%s: a descendant kept the output pipes open' % argv[0])
    require(proc.returncode in ok_rcs, 'subprocess', '%s exited %s (stdout discarded): %s' % (argv[0], proc.returncode, tail))
    require(state['stdin_error'] is None, 'subprocess', '%s: stdin feed failed' % argv[0])
    return RunResult(tuple(argv), proc.returncode, state['out'], state['err'])


def spawn(argv, log_path, env, roles=('logs',), cwd=None):
    """Start a detached owned child (own session) with stdout/stderr appended to a confined log; returns
    dict(pid, pgid, starttime). argv[0] must be absolute; the environment is exactly `env`."""
    _argv_ok(argv)
    fd = open_append(log_path, roles)
    try:
        proc = subprocess.Popen(list(argv), stdout=fd, stderr=fd, stdin=subprocess.DEVNULL, env=dict(env), cwd=cwd,
                                start_new_session=True, close_fds=True, shell=False)
    finally:
        os.close(fd)
    st = proc_stat(proc.pid)
    return dict(pid=proc.pid, pgid=proc.pid, starttime=None if st is None else st['starttime'], popen=proc)


# ---------------------------------------------------------------- owned processes (PID-only signalling)
def proc_stat(pid):
    try:
        with open('/proc/%d/stat' % int(pid), 'rb') as f: raw = f.read()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None
    try:
        rest = raw.rsplit(b')', 1)[1].split()
        return dict(state=rest[0].decode(), ppid=int(rest[1]), pgid=int(rest[2]), sid=int(rest[3]),
                    utime=int(rest[11]), stime=int(rest[12]), starttime=int(rest[19]))
    except (IndexError, ValueError):
        return None


def all_pids():
    return [int(n) for n in os.listdir('/proc') if n.isdigit()]


def owned_pids(pgid, leader_starttime):
    """Live PIDs of a recorded owned group: process-group id equal to pgid and started no earlier than the recorded
    leader. If a process with pid == pgid exists it must be that leader (same starttime), else the group number was
    reused and nothing is owned."""
    if pgid is None or leader_starttime is None: return []
    lead = proc_stat(pgid)
    if lead is not None and lead['pgid'] == pgid and lead['starttime'] != leader_starttime: return []
    out = []
    for pid in all_pids():
        st = proc_stat(pid)
        if st and st['pgid'] == pgid and st['starttime'] >= leader_starttime and st['state'] != 'Z': out.append(pid)
    return sorted(out)


def group_alive(pgid, leader_starttime):
    return bool(owned_pids(pgid, leader_starttime))


def signal_owned(pgid, leader_starttime, sig, exclude=()):
    """Signal each verified PID of an owned group individually (never a pattern, never a bare group signal);
    each PID's group and starttime are re-read immediately before its kill. Returns the PIDs signalled."""
    sent = []
    for pid in owned_pids(pgid, leader_starttime):
        if pid in exclude: continue
        st = proc_stat(pid)
        if not st or st['pgid'] != pgid or st['starttime'] < leader_starttime: continue
        try: os.kill(pid, sig); sent.append(pid)
        except ProcessLookupError: pass
    return sent


def stop_owned(pgid, leader_starttime, term_grace=45, kill_grace=60, poll=1.0, exclude=()):
    """TERM then KILL the owned PIDs of a group (except `exclude`); returns True once none is left."""
    left = lambda: [p for p in owned_pids(pgid, leader_starttime) if p not in exclude]
    for sig, grace in ((signal.SIGTERM, term_grace), (signal.SIGKILL, kill_grace)):
        signal_owned(pgid, leader_starttime, sig, exclude)
        end = time.monotonic()+grace
        while time.monotonic() < end:
            if not left(): return True
            time.sleep(poll)
    return not left()


def signal_pid(pid, pgid, leader_starttime, sig):
    """Signal one PID only if it is a verified member of the owned group."""
    if pid in owned_pids(pgid, leader_starttime):
        try: os.kill(pid, sig); return True
        except ProcessLookupError: return False
    return False


def own_identity():
    st = proc_stat(os.getpid())
    return dict(pid=os.getpid(), pgid=os.getpgrp(), starttime=None if st is None else st['starttime'])


# ---------------------------------------------------------------- git (self-verifying object walk)
GIT = '/usr/bin/git'
GIT_ENV = {'LC_ALL': 'C', 'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'GIT_CONFIG_NOSYSTEM': '1',
           'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_TERMINAL_PROMPT': '0', 'GIT_OPTIONAL_LOCKS': '0',
           'GIT_LITERAL_PATHSPECS': '1', 'GIT_NO_REPLACE_OBJECTS': '1', 'GIT_GRAFT_FILE': '/nonexistent/x4s4-no-grafts',
           'GIT_ATTR_NOSYSTEM': '1'}
OID = re.compile(r'[0-9a-f]{40}')


def git_checked(repo, args, timeout=300, stdout_limit=64 << 20, git=GIT):
    check_abs(repo); require(os.path.realpath(repo) == repo, 'root', 'repository %s is not canonical' % repo)
    return run_checked([git, '--no-replace-objects', '--no-optional-locks', '-c', 'core.hooksPath=/dev/null',
                        '-c', 'core.fsmonitor=false', '-C', repo]+list(args), timeout, stdout_limit, env=GIT_ENV)


def git_object(repo, oid, kind, git=GIT, cap=256 << 20):
    """Object bytes whose sha1('<kind> <len>\\0'+bytes) equals oid (content cannot be substituted)."""
    require(isinstance(oid, str) and OID.fullmatch(oid) is not None, 'git', 'not a full object id: %r' % (oid,))
    got = git_checked(repo, ['cat-file', '-t', oid], git=git, stdout_limit=64).stdout.strip().decode()
    require(got == kind, 'git', 'object %s is a %s, not a %s' % (oid, got, kind))
    data = git_checked(repo, ['cat-file', kind, oid], git=git, stdout_limit=cap).stdout
    require(hashlib.sha1(b'%s %d\x00' % (kind.encode(), len(data))+data).hexdigest() == oid, 'git',
            '%s %s does not hash to its object id' % (kind, oid))
    return data


def _tree_entries(data):
    out, i = {}, 0
    while i < len(data):
        sp = data.index(b' ', i); nul = data.index(b'\x00', sp)
        mode, name = data[i:sp].decode(), data[sp+1:nul].decode('utf-8')
        out[name] = (mode, data[nul+1:nul+21].hex()); i = nul+21
    return out


def git_committed_blob(repo, commit, relpath, git=GIT):
    """Bytes of relpath at commit by a verified commit -> tree -> blob walk; the leaf must be a regular blob."""
    body = git_object(repo, commit, 'commit', git)
    first = body.split(b'\n', 1)[0].decode()
    require(first.startswith('tree ') and OID.fullmatch(first[5:]) is not None, 'git', 'commit %s has no tree line' % commit)
    oid, parts = first[5:], check_rel(relpath)
    for i, part in enumerate(parts):
        entries = _tree_entries(git_object(repo, oid, 'tree', git))
        require(part in entries, 'missing', '%s not tracked at %s' % (relpath, commit[:12]))
        mode, oid = entries[part]
        if i < len(parts)-1: require(mode == '40000', 'git', '%s: %s is not a tree' % (relpath, part))
        else: require(mode in ('100644', '100755'), 'git', '%s is not a regular blob (mode %s)' % (relpath, mode))
    return git_object(repo, oid, 'blob', git)


def git_is_ancestor(repo, commit, ref='refs/remotes/origin/main', git=GIT):
    """True if commit is reachable from ref, from the commit graph read with replace objects and grafts disabled."""
    tip = git_checked(repo, ['rev-parse', '--verify', '--end-of-options', ref+'^{commit}'], git=git, stdout_limit=128).stdout.strip().decode()
    require(OID.fullmatch(tip) is not None, 'git', 'cannot resolve %s' % ref)
    git_object(repo, commit, 'commit', git)
    graph = git_checked(repo, ['rev-list', '--parents', tip], git=git, stdout_limit=512 << 20).stdout.decode().split('\n')
    return any(line.split(' ', 1)[0] == commit for line in graph if line)


# ---------------------------------------------------------------- sealed game directories (exit_r1.rows.seal layout)
SEAL_SCHEMA = 'clasher.exit-r1.teacher-v6.v1'


def tree_files(path):
    """(files, dirs) relative to a canonical directory; any symlink, special file or hard link refuses."""
    files, dirs = set(), set()
    def walk(fd, rel):
        for name in sorted(os.listdir(fd)):
            st = os.stat(name, dir_fd=fd, follow_symlinks=False)
            r = rel+'/'+name if rel else name
            if stat.S_ISLNK(st.st_mode): refuse('symlink', '%s/%s is a symlink' % (path, r))
            if stat.S_ISDIR(st.st_mode):
                dirs.add(r); sub = open_dirs(fd, [name], str(path))
                try: walk(sub, r)
                finally: os.close(sub)
            elif stat.S_ISREG(st.st_mode):
                require(st.st_nlink == 1, 'nlink', '%s/%s is hard-linked' % (path, r)); files.add(r)
            else:
                refuse('not-regular', '%s/%s is a special file' % (path, r))
    root = open_root(str(path))
    try: walk(root, '')
    finally: os.close(root)
    return files, dirs


def verify_sealed_dir(path, schema=SEAL_SCHEMA):
    """Re-verify a sealed game directory completely: manifest complete + schema, exact file inventory (no extra,
    missing, linked or special file; only the directories the seal needs), every listed file's SHA-256. Returns
    (manifest dict, manifest SHA-256)."""
    raw = read_bytes(str(path)+'/manifest.json', 64 << 20)
    seal = loads_strict(raw, str(path)+'/manifest.json')
    require(seal.get('schema') == schema and seal.get('complete') is True, 'seal', '%s: incomplete or wrong-schema seal' % path)
    keys = set(seal['files'])
    for k in keys: check_rel(k)
    files, dirs = tree_files(path)
    require(files == keys | {'manifest.json'}, 'seal', '%s: inventory differs from seal (%s)' % (path, sorted(files ^ (keys | {'manifest.json'}))[:4]))
    needed = {'/'.join(k.split('/')[:i]) for k in keys for i in range(1, k.count('/')+1)}
    require(dirs == needed, 'seal', '%s: unexpected directories %s' % (path, sorted(dirs - needed)[:4]))
    for k, want in seal['files'].items():
        require(sha256_file(str(path)+'/'+k) == want, 'seal', '%s/%s SHA-256 differs from its seal' % (path, k))
    return seal, hashlib.sha256(raw).hexdigest()


def git_ls_tree(repo, commit, git=GIT):
    """[(mode, type, oid, size, path)] of every entry at commit (ls-tree -r -l -z, replace objects disabled)."""
    require(OID.fullmatch(commit or '') is not None, 'git', 'commit must be a full object id')
    git_object(repo, commit, 'commit', git)
    raw = git_checked(repo, ['ls-tree', '-r', '-l', '-z', '--full-tree', commit], git=git, stdout_limit=1 << 30).stdout
    out = []
    for rec in raw.split(b'\x00'):
        if not rec: continue
        meta, path = rec.split(b'\t', 1)
        mode, kind, oid, size = meta.decode().split()
        out.append((mode, kind, oid, None if size == '-' else int(size), path.decode('utf-8')))
    return out


def git_blobs(repo, oids, git=GIT, total_cap=1 << 31):
    """{oid: bytes} via one `cat-file --batch`; every blob is hashed against its object id."""
    oids = sorted(set(oids))
    for o in oids: require(OID.fullmatch(o) is not None, 'git', 'not a full object id: %r' % o)
    if not oids: return {}
    check_abs(repo); require(os.path.realpath(repo) == repo, 'root', 'repository not canonical')
    raw = run_checked([git, '--no-replace-objects', '--no-optional-locks', '-c', 'core.hooksPath=/dev/null', '-C', repo,
                       'cat-file', '--batch'], 1800, total_cap, env=GIT_ENV, stdin_bytes=('\n'.join(oids)+'\n').encode()).stdout
    out, i = {}, 0
    for o in oids:
        nl = raw.index(b'\n', i); head = raw[i:nl].decode().split(); i = nl+1
        require(len(head) == 3 and head[0] == o and head[1] == 'blob', 'git', 'cat-file --batch header for %s: %r' % (o, head))
        n = int(head[2]); data = raw[i:i+n]; i += n+1
        require(hashlib.sha1(b'blob %d\x00' % n + data).hexdigest() == o, 'git', 'blob %s does not hash to its object id' % o)
        out[o] = data
    return out
