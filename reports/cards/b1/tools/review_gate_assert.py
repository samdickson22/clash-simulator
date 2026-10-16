"""Fail closed on the exact unchanged C56 fixture/root coverage contract."""
import json
import sys

def require(ok, detail):
    if not ok:
        raise SystemExit('C56 gate rejected: '+str(detail))


report = json.load(open(sys.argv[1]))
f, r = report['fixtures'], report['roots']
require(f['pinned'] == f['total'] == f['identical_records'] == f['rust_only_chains_equal'] == 577, f)
require(not f['differing'] and f['rust_only_errors'] == {'pinned': 0, 'total': 0}, f)
require(f['rs_full_parity'] == {'pinned': 429, 'total': 429}, f)
require(r['records'] == {'pinned': 600, 'total': 600} and r['identical_records'] == 600, r)
require(not r['differing'] and r['by_variant'] == {'full': 300, 'cut': 300}, r)
require(r['sampled_roots'] == 300 and r['games'] == 12 and r['select_action_calls'] == 1800, r)
print('C56 PASS: 577 fixtures + 600 full/cut root records')
