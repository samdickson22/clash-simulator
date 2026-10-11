"""PREREG-K4S: mechanical T1 -> K4S path rebinding, and its proof.

The K4S runner is T1's frozen reporting runtime (ef4c073a) plus eight reviewed deltas
(PREREG-K4S r3 section 4.1). Every other T1 file is copied either byte-identical or with
only the path substitutions below, so the OP-1..OP-7 guard code is T1's reviewed code.

  python3 reports/explore/k4s-confirm/rebind.py apply FILE...   # rebind copied T1 bytes in place
  python3 reports/explore/k4s-confirm/rebind.py verify         # prove DELTA-MANIFEST classes from git

verify reads T1 bytes with `git show ef4c073a:reports/explore/t1/<name>` and checks:
  identical -> K4S bytes == T1 bytes;
  rebound   -> K4S bytes == rebind(T1 bytes) and != T1 bytes;
  delta     -> recorded T1 base SHA matches git (the diff itself is reviewed separately);
  new       -> no T1 counterpart.
"""
import hashlib, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
T1_COMMIT = 'ef4c073a4c69e85aea0b6f9af9c1118ca8888a59'
T1_DIR = 'reports/explore/t1'
# Order matters. Committed T1 receipts are read by reference, so their prefix is protected.
PROTECT = ('reports/explore/t1/receipts/', '\0T1RECEIPTS\0')
RULES = (
    ('T1_JOB', 'K4S_JOB'),
    ('/mpac/sdicks02/jobs/clasher/t1-20261010-r1', '/mpac/sdicks02/jobs/clasher/k4s-confirm-r1'),
    ('FROZEN-T1.json', 'FROZEN-K4S.json'),
    ('reports/explore/t1', 'reports/explore/k4s-confirm'),
)


def rebind(data: bytes) -> bytes:
    text = data.decode()
    text = text.replace(*PROTECT)
    for old, new in RULES:
        text = text.replace(old, new)
    return text.replace(PROTECT[1], PROTECT[0]).encode()


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def t1_bytes(name):
    return subprocess.run(['git', '-C', str(ROOT), 'show', f'{T1_COMMIT}:{T1_DIR}/{name}'],
                          check=True, capture_output=True).stdout


def verify():
    m = json.loads((HERE/'DELTA-MANIFEST.json').read_text())
    bad = []
    counts = dict(identical=0, rebound=0, delta=0, new=0)
    for name, row in sorted(m['files'].items()):
        cls = row['class']
        mine = (HERE/name).read_bytes()
        if sha(mine) != row['k4s_sha256']:
            bad.append((name, 'k4s sha changed since manifest'))
        if cls == 'new':
            r = subprocess.run(['git', '-C', str(ROOT), 'cat-file', '-e', f'{T1_COMMIT}:{T1_DIR}/{name}'],
                               capture_output=True)
            if r.returncode == 0:
                bad.append((name, 'new file has a T1 counterpart'))
        else:
            base = t1_bytes(name)
            if sha(base) != row['t1_sha256']:
                bad.append((name, 't1 base sha mismatch'))
            if cls == 'identical' and mine != base:
                bad.append((name, 'not identical'))
            if cls == 'rebound' and (mine != rebind(base) or mine == base):
                bad.append((name, 'not a pure rebinding'))
            if cls == 'delta' and (mine == base or mine == rebind(base)):
                bad.append((name, 'declared delta but unchanged'))
        counts[cls] += 1
    print(json.dumps(dict(t1_commit=T1_COMMIT, counts=counts, failures=bad)))
    return not bad


if __name__ == '__main__':
    if sys.argv[1] == 'apply':
        for name in sys.argv[2:]:
            p = HERE/name
            p.write_bytes(rebind(t1_bytes(name)))
    elif sys.argv[1] == 'verify':
        sys.exit(0 if verify() else 1)
    else:
        raise SystemExit(__doc__)
