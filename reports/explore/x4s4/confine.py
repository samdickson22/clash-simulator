"""X4S-4 write confinement (Sol r1 F10; exploration, NEVER ADOPTABLE). Stdlib only.

Every X4S-4 writer validates its output path BEFORE creating, replacing, renaming, chmod-ing or deleting
anything: the path must be absolute, contain no '.'/'..' components, lie strictly below one of the allowed
roots (default: the canonical job root), start with an allowed role directory, and every existing component
from '/' down to the path must be a real directory (lstat; no symlink anywhere), with the path itself, if
it exists, not a symlink. Read-only inputs (frozen r1 corpus, held-out slice, repo sources) are never passed
through this module.
"""
import os, stat
from pathlib import Path, PurePosixPath

JOB = Path('/mpac/sdicks02/jobs/clasher/x4s4-onpolicy')
REPORT_ROOT = Path('/mpac/sdicks02/repos/clasher/reports/explore/x4s4')   # RESULTS.md / results.json (05 checkout)
ROLES = ('collect', 'games', 'data', 'receipts', 'analysis', 'qual', 'calibration', 'driver', 'fits', 'logs', 'smoke', 'attempts')


class ConfinementError(Exception):
    pass


def _fail(msg):
    raise ConfinementError(msg)


def writable(path, roles=ROLES, roots=None, must_not_exist=False):
    """Return Path(path) if it is an allowed write target; raise ConfinementError otherwise."""
    roots = [JOB] if roots is None else list(roots)
    p = PurePosixPath(str(path))
    if not p.is_absolute(): _fail(f'not absolute: {path}')
    if any(part in ('.', '..') for part in p.parts) or str(p) != os.path.normpath(str(p)): _fail(f'non-canonical path: {path}')
    root = next((Path(r) for r in roots if PurePosixPath(str(r)) in p.parents), None)
    if root is None: _fail(f'outside the allowed roots {list(map(str, roots))}: {path}')
    rel = p.relative_to(PurePosixPath(str(root)))
    if roles is not None and rel.parts[0] not in roles: _fail(f'role {rel.parts[0]!r} not allowed for {path}')
    cur = Path('/')
    for part in p.parts[1:-1]:
        cur = cur/part
        try: st = os.lstat(cur)
        except FileNotFoundError: break             # below here nothing exists yet; mkdir creates real dirs
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode): _fail(f'not a real directory: {cur}')
    try:
        st = os.lstat(str(p))
        if stat.S_ISLNK(st.st_mode): _fail(f'symlink target: {path}')
        if must_not_exist: _fail(f'already exists: {path}')
    except FileNotFoundError:
        pass
    return Path(str(p))


def mkdirs(path, **kw):
    """Create a confined directory chain (each new component is a real directory)."""
    p = writable(path, **kw)
    cur = Path('/')
    for part in p.parts[1:]:
        cur = cur/part
        try:
            st = os.lstat(cur)
            if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode): _fail(f'not a real directory: {cur}')
        except FileNotFoundError:
            os.mkdir(cur)
    return p
