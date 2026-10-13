"""HR-1 / GO 9a1613fc: read-only inventory of J (path, type, size, mtime, sha256 for regular files <= 64 MiB). No writes in J."""
import hashlib, json, os, stat, sys
J, out = sys.argv[1], sys.argv[2]
LIM = 64 << 20
with open(out, 'x') as o:
    for d, ds, fs in os.walk(J):
        ds.sort(); fs.sort()
        for n in ds + fs:
            p = os.path.join(d, n); s = os.lstat(p); rel = os.path.relpath(p, J)
            rec = dict(p=rel, t='d' if stat.S_ISDIR(s.st_mode) else 'l' if stat.S_ISLNK(s.st_mode) else 'f' if stat.S_ISREG(s.st_mode) else 'o',
                       size=s.st_size, mtime=s.st_mtime, mode=oct(s.st_mode & 0o7777))
            if rec['t'] == 'l': rec['link'] = os.readlink(p)
            if rec['t'] == 'f' and s.st_size <= LIM:
                h = hashlib.sha256()
                with open(p, 'rb') as f:
                    for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
                rec['sha256'] = h.hexdigest()
            o.write(json.dumps(rec, sort_keys=True) + '\n')
