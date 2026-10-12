"""X4S-3 (exploration, NEVER ADOPTABLE): write <job>/data/G-UNION-VERIFIED.json, the gate for the
R4-D/R4-DC fits, only if both sealed G receipts passed and the union is exactly the declared
8,804,755 roots (r1 6,009,681 + G-01 149,385 + G-08 2,645,689). Local only; raises on any mismatch."""
import hashlib, json, os, stat, subprocess
from pathlib import Path

J = Path('/mpac/sdicks02/jobs/clasher/x4s3-student-scale-20261012')
R1 = Path('/mpac/sdicks02/jobs/clasher/exit-r1-student-screen-20261009-r1/corpus/manifest.json')
R1_SHA = '1c8e1f4969bab3d2416fb5b19d50b105ed5f35bb05df7b33caaa4c9edf5c737b'
EXPECT = dict(r1=6009681, g01=149385, g08=2645689)


class Fail(Exception):
    pass


def check(c, m):
    if not c: raise Fail(m)


def main():
    out = J/'data'/'G-UNION-VERIFIED.json'
    check(not os.path.lexists(out), 'gate already exists')
    check(hashlib.sha256(R1.read_bytes()).hexdigest() == R1_SHA, 'r1 manifest SHA')
    shards = {}
    for mode in ('g01', 'g08'):
        r = json.loads((J/'data'/mode/'VERIFY-RECEIPT.json').read_text())
        check(r['passed'] is True and r['sealed'] is True and r['mode'] == mode and r['eligible_roots'] == EXPECT[mode], f'{mode} receipt')
        for s in r['shards']:
            d = J/'data'/mode/s['name']
            for p in d.rglob('*'):
                st = os.lstat(p)
                check(not stat.S_ISLNK(st.st_mode) and (stat.S_ISDIR(st.st_mode) or not st.st_mode & 0o222), f'{p} writable or link')
        shards[mode] = [s['name'] for s in r['shards']]
    check(shards['g01'] == ['batch-00000', 'batch-00001'] and shards['g08'] == [f'batch-{i:05d}' for i in range(11)], 'shard lists')
    gate = dict(utc=subprocess.check_output(['date', '-u', '+%FT%TZ'], text=True).strip(), label='X4S-3 exploration, NEVER ADOPTABLE',
                r1_manifest_sha256=R1_SHA, roots=dict(EXPECT, union=sum(EXPECT.values())), shards=shards,
                receipts={m: hashlib.sha256((J/'data'/m/'VERIFY-RECEIPT.json').read_bytes()).hexdigest() for m in ('g01', 'g08')})
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    with os.fdopen(fd, 'w') as f: f.write(json.dumps(gate, indent=2)+'\n')
    print(json.dumps(gate))


if __name__ == '__main__':
    main()
