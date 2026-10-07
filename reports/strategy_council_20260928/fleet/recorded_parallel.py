"""Replay the unchanged eight-game identity gate in independent, resumable shards.

Every game uses broad_identity's original oq_lib.play_game and exact row comparison.
After merging, identity.sh invokes the original broad_identity checker on all rows.
"""
from concurrent.futures import ProcessPoolExecutor
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
ES = ROOT / 'reports/strategy_council_20260928/engine-speed'
OUT = Path('/mpac/sdicks02/jobs/clasher')
sys.path.insert(0, str(ES))
import broad_identity as authority

BASELINE = ES / 'recorded_identity_baseline_admitted.json'
DRIVER = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def replay(index):
    baseline = json.loads(BASELINE.read_text())
    provenance = authority.provenance()
    assert baseline['provenance']['data_sha256'] == provenance['data_sha256']
    assert baseline['count'] == 8 and baseline['suite'] == 'recorded'
    expected_row = baseline['results'][str(index)]
    receipt = OUT / f'recorded-linux-20261007-game{index}.json'
    if receipt.exists():
        saved = json.loads(receipt.read_text())
        assert saved['provenance'] == provenance and saved['driver'] == DRIVER
        assert saved['row'] == expected_row and saved['ok']
        return saved
    sys.path.insert(0, str(authority.OQ))
    import oq_lib
    path = ROOT / expected_row['recording']
    rec = json.loads(path.read_text())
    start = time.perf_counter()
    cpu = time.process_time()
    with contextlib.redirect_stdout(io.StringIO()):
        ctx = oq_lib.Context()
        result = oq_lib.play_game(ctx, rec['spec'])
    row = dict(recording=str(path.relative_to(ROOT)),
               recording_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
               spec=rec['spec'], expected={k: rec[k] for k in authority.FIELDS},
               actual={k: result[k] for k in authority.FIELDS})
    out = dict(index=index, provenance=provenance, driver=DRIVER, row=row,
               wall_seconds=time.perf_counter()-start,
               cpu_seconds=time.process_time()-cpu,
               ok=row['actual'] == row['expected'] and row == expected_row)
    temp = receipt.with_suffix('.tmp')
    temp.write_text(json.dumps(out, indent=2)+'\n')
    temp.replace(receipt)
    print(json.dumps({k: out[k] for k in ('index', 'ok', 'wall_seconds', 'cpu_seconds')}), flush=True)
    assert out['ok'], f'recorded game {index} mismatch; preserved {receipt}'
    return out


if __name__ == '__main__':
    assert (OUT / 'transfer-ready.json').exists()
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(replay, range(8)))
    provenance = authority.provenance()
    assert all(row['provenance'] == provenance for row in rows)
    output = dict(suite='recorded', count=8, provenance=provenance,
                  results={str(row['index']): row['row'] for row in rows}, mismatches=[])
    path = OUT / 'recorded_linux-20261007.json'
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(output, indent=2)+'\n')
    temp.replace(path)
    print(json.dumps(dict(checked=8, mismatches=[], workers=4,
                          wall_seconds=time.perf_counter()-start,
                          sum_game_cpu_seconds=sum(row['cpu_seconds'] for row in rows))), flush=True)
