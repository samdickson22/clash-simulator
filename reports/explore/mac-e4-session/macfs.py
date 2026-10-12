"""Confined, exclusive filesystem primitives for Mac staging (run ON the Mac by stage_phase_b.sh, via python3 -I -c).

All paths are RELATIVE to the operator staging root ROOT (argv[1]); every component is checked to be a real
(non-symlink) entry resolving inside ROOT. Operations (argv[2]):
  state REL               -> prints absent|file|dir (exit 0; absent also when an intermediate dir is missing)
                             or fails (exit 2) on symlink/outside/bad/other
  mkdir REL               -> os.mkdir (fails if it exists); parent must be a confined dir
  write REL               -> copy stdin to a NEW file: O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW; parent confined dir
  rename SRC DST          -> atomic renamex_np(SRC, DST, RENAME_EXCL): fails if DST exists; never merges/nests
Any failure exits non-zero; nothing is ever replaced or followed through a symlink.
"""
import ctypes
import ctypes.util
import os
import stat
import sys

RENAME_EXCL = 0x00000004


def fail(message):
    sys.stderr.write("macfs: " + message + "\n")
    sys.exit(2)


def resolve(root, rel, allow_missing_leaf=True):
    if rel == ".":
        return root, "dir"
    parts = rel.split("/")
    if rel.startswith("/") or any(p in ("", ".", "..") for p in parts):
        fail("bad relative path " + repr(rel))
    path = root
    for index, part in enumerate(parts):
        path = os.path.join(path, part)
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            # A missing leaf, or (for allow_missing_leaf callers such as `state`) a missing intermediate
            # directory, means the requested path is absent; checked components so far were real dirs.
            if allow_missing_leaf:
                return os.path.join(root, rel), "absent"
            fail("missing component " + repr(path))
        if stat.S_ISLNK(info.st_mode):
            fail("symlink " + repr(path))
        if index < len(parts) - 1 and not stat.S_ISDIR(info.st_mode):
            fail("non-directory component " + repr(path))
    if not (os.path.realpath(path) + "/").startswith(root + "/"):
        fail("outside root " + repr(path))
    mode = os.lstat(path).st_mode
    return path, "dir" if stat.S_ISDIR(mode) else "file" if stat.S_ISREG(mode) else "other"


def parent_dir(root, rel):
    parent = os.path.dirname(rel) or "."
    path, kind = resolve(root, parent, allow_missing_leaf=False)
    if kind != "dir":
        fail("parent is not a directory " + repr(parent))


def main():
    root = os.path.realpath(sys.argv[1])
    if os.path.islink(sys.argv[1].rstrip("/")) or not os.path.isdir(root):
        fail("bad root")
    op, args = sys.argv[2], sys.argv[3:]
    if op == "state":
        path, kind = resolve(root, args[0])
        if kind == "other":
            fail("unsupported file type " + repr(path))
        print(kind)
    elif op == "mkdir":
        parent_dir(root, args[0])
        path, kind = resolve(root, args[0])
        if kind != "absent":
            fail("exists " + repr(path))
        os.mkdir(path)
        if resolve(root, args[0])[1] != "dir":
            fail("mkdir check")
    elif op == "write":
        parent_dir(root, args[0])
        path, kind = resolve(root, args[0])
        if kind != "absent":
            fail("exists " + repr(path))
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        with os.fdopen(fd, "wb") as stream:
            while True:
                block = sys.stdin.buffer.read(1 << 20)
                if not block:
                    break
                stream.write(block)
            stream.flush()
            os.fsync(stream.fileno())
    elif op == "rename":
        source, kind = resolve(root, args[0], allow_missing_leaf=False)
        if kind not in ("file", "dir"):
            fail("bad source " + repr(source))
        parent_dir(root, args[1])
        target, kind = resolve(root, args[1])
        if kind != "absent":
            fail("destination exists " + repr(target))
        libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
        function = libc.renamex_np
        function.argtypes, function.restype = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint), ctypes.c_int
        if function(os.fsencode(source), os.fsencode(target), RENAME_EXCL) != 0:
            error = ctypes.get_errno()
            fail("renamex_np: " + os.strerror(error))
        if resolve(root, args[1])[1] == "absent" or resolve(root, args[0])[1] != "absent":
            fail("rename check")
    else:
        fail("unknown op " + repr(op))


main()
