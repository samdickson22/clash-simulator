"""Exercise the production opt-in constructor and four-root reduction on CPU."""
import argparse
import gzip
import json
import os
from pathlib import Path
import time

import torch
from clasher.live.contracts import Snapshot
from clasher.live.decision import RustPlanner
from qualify import public


def main(a):
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '' or a.output.exists():
        raise ValueError('CPU-only smoke requires a fresh output')
    torch.set_num_threads(1)
    fixture = json.loads(gzip.decompress(a.inputs.read_bytes()))
    assert fixture['split'] == 'train'
    row = next(r for r in fixture['inputs'] if 'empty' in r['own']['hand'])
    config = dict(seed=6108, public_tower_model=True, cache_root_config=True, hoist_opponent_moves=True)
    planner = RustPlanner(config)
    try:
        now = time.monotonic()
        snapshot = Snapshot(row['public']['episode_id'], row['sequence'], now, now, now,
            row['tick'], public(row), row['own'], tuple(row['roots']), row['opponent'],
            row['revision'], None, 0, 0)
        before = json.dumps(row['own'], sort_keys=True)
        action, diagnostic = planner.decide(snapshot, time.monotonic()+30.)
        assert diagnostic['completed'] == diagnostic['candidates']
        assert action in diagnostic['candidate_ids']
        assert json.dumps(row['own'], sort_keys=True) == before
        result = dict(schema='clasher.live-perf.flagged-planner-smoke.v1', flags=config,
            match=row['match'], sequence=row['sequence'], action=action, diagnostic=diagnostic,
            own_input_unchanged=True, heldout_opened=False)
        a.output.write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result), flush=True)
    finally:
        planner.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--inputs', type=Path, default=Path(__file__).with_name('mac-search-inputs.json.gz'))
    p.add_argument('--output', type=Path, required=True)
    main(p.parse_args())
