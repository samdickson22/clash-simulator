"""Full inventory of the traced trees (lstat only, no file content): rel, type, size, mode, mtime_ns, ctime_ns,
ino, nlink. Usage: python3 -I inventory.py OUT.json ROOT [ROOT ...]"""
import json
import os
import stat
import sys


def inventory(root):
    out = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs.sort()
        for name in [""] + sorted(dirs) + sorted(files) if directory == root else sorted(dirs) + sorted(files):
            path = os.path.join(directory, name) if name else directory
            st = os.lstat(path)
            kind = "dir" if stat.S_ISDIR(st.st_mode) else "file" if stat.S_ISREG(st.st_mode) else \
                "symlink" if stat.S_ISLNK(st.st_mode) else "other"
            out[os.path.relpath(path, root)] = [kind, st.st_size, oct(st.st_mode), st.st_mtime_ns, st.st_ctime_ns,
                                                st.st_ino, st.st_nlink]
    return out


if __name__ == "__main__":
    result = {root: inventory(root) for root in sys.argv[2:]}
    with open(sys.argv[1], "x") as f:
        json.dump(result, f, sort_keys=True)
    print({root: len(v) for root, v in result.items()})
