"""Fail closed on fresh HEADLINE-v1 command identity and actual import receipts."""
import hashlib
import json
from pathlib import Path
import sys

J=Path(sys.argv[1]); output=Path(sys.argv[2])
expected={('K4L-R-gs-rw-fc-p2',op,i) for op in ('R3a','v1') for i in range(6)}
helper=hashlib.sha256((J/'public_root.py').read_bytes()).hexdigest()
results={}
for arm,native in [('baseline','681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b'),
                   ('candidate','326ce6f93c4db6a7bd15b667960a2d3ed40a0d48eab3badc9ddd181521996732')]:
    phase='headline-'+arm
    rows={}
    for p in sorted((J/phase).glob('games-*.jsonl')):
        for line in p.read_text().splitlines():
            r=json.loads(line)
            key=(r.get('candidate'),r.get('opponent'),r.get('index'))
            if key in rows or key not in expected or r.get('error') or 'ticks' not in r or len(r.get('command_sha256',''))!=64:
                raise SystemExit('invalid/duplicate headline row '+str(r))
            rows[key]=r
    if set(rows)!=expected:
        raise SystemExit('missing headline cases '+str(expected-set(rows)))
    receipts=[]
    for p in J.glob(phase+'-imports-*.jsonl'):
        receipts += [json.loads(line) for line in p.read_text().splitlines()]
    if not receipts or any(r['helper_sha256']!=helper or r['native_sha256']!=native or r['vocabulary_count']!=360
                           or r['v1_sha256']!='d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed'
                           or r['r3a_sha256']!='37509a4331bd02ae110b76e1825a2adb23fa78e0e70188e199b6ef90d19ade85' for r in receipts):
        raise SystemExit('incorrect/missing actual import receipts '+phase)
    results[arm]=rows
pairs=[]
for key in sorted(expected):
    b,c=results['baseline'][key],results['candidate'][key]
    if b['command_sha256']!=c['command_sha256']:
        raise SystemExit('command mismatch '+str(key))
    pairs.append(dict(candidate=key[0],opponent=key[1],index=key[2],baseline=b['command_sha256'],candidate_sha256=c['command_sha256']))
with output.open('x') as f:
    json.dump(dict(result='PASS',identical=12,successful_arm_rows=24,helper_sha256=helper,pairs=pairs),f,indent=2)
    f.write('\n')
print('K4L HEADLINE PASS:12/12 identical command hashes,24 successful actual arm rows')
