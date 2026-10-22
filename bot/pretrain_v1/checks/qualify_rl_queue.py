"""Synthetic host queue/mmap admission. No engine, GPU, learner update or games.

Use 262144 rows for full registered-update storage exposure. This measures the
host coordinator's storage/mapping path; it does not qualify 32 real actors or
the six-hour soak. All synthetic rows remain explicitly test-only artifacts.
"""
import argparse
from dataclasses import asdict
import gc
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def run(out, rows=262144, chunk_rows=128):
    import numpy as np
    import torch
    from bot.pretrain_v1 import rl_driver as D, rl_coordinator as C, rl_learner as L, stream_actor as A
    D.guard()
    torch.set_num_threads(1)
    C.require(not torch.cuda.is_initialized(), 'CPU-only qualification')
    C.require(type(rows) is int and 0 < rows <= 262144 and rows % chunk_rows == 0, 'bounded divisible rows')
    C.require(chunk_rows == 128, 'production transport chunk width is 128')
    out = Path(out)
    out.mkdir()
    runtime = dict(native_sha256=L.NATIVE_SHA256, gamedata_sha256=L.GAMEDATA_SHA256,
                   actor_source_sha256='f'*64, test_only='synthetic-host-queue-admission')
    chunks, capacity = C.queue_capacity(rows)
    C.require(shutil.disk_usage(out).free > capacity+2**30, 'reserve full conservative queue capacity')
    queue = A.AtomicChunkQueue(out/'queue', max_chunks=chunks, max_bytes=capacity, runtime_manifest=runtime)
    descriptors = D.ensure_fd_capacity((rows//chunk_rows)*(len(A._FEATURES)+len(A._VECTORS))+256)
    widths = dict(ent=256, ev=32, rev=16)
    receipts, mapped = [], []
    started = time.monotonic()
    fd_before = len(list(Path('/proc/self/fd').iterdir()))
    result = dict(status='failed', test_only=True, rows=rows, chunk_rows=chunk_rows, widths=widths,
                  source_sha256=D.source_digest(), engine_games=0, experiment_generated_steps=0,
                  optimizer_steps=0, cuda_initialized=False)
    result['descriptor_admission'] = descriptors
    try:
        for start in range(0, rows, chunk_rows):
            D.guard()
            features = {key: np.zeros((chunk_rows, *(widths[key] if n is None else n for n in tail)), dtype=dtype)
                        for key, (dtype, tail) in A._FEATURES.items() if key not in ('ent_mask', 'ev_mask', 'rev_mask')}
            for key, width in widths.items():
                features[key+'_mask'] = np.zeros((chunk_rows, width), bool)
            # Storage labels are synthetic and have no network/engine claim.
            chunk = A.Chunk(features=features, action=np.full(chunk_rows, 2304, np.int64),
                old_logp=np.zeros(chunk_rows, np.float64), old_value=np.zeros(chunk_rows, np.float64),
                reward=np.zeros(chunk_rows, np.float64), terminated=np.zeros(chunk_rows, bool),
                actor=np.zeros(chunk_rows, bool), dt=np.full(chunk_rows, 5, np.int16), bootstrap=0., version=0,
                actor_id=f'actor-{(start//chunk_rows)%32:02d}', seed=L.SEEDS[0], anchor_sha256='a'*64,
                policy_sha256='b'*64, generated_steps=chunk_rows, provenance_sha256=queue.provenance_sha256,
                opponent_id='synthetic-no-game')
            receipts.append(queue.write(chunk))
        result['write_seconds'] = time.monotonic()-started
        for receipt in receipts:
            D.guard()
            mapped.append(queue.load(receipt, expected_version=0, expected_policy_sha256='b'*64))
        result['simultaneous_chunks'] = len(mapped)
        result['fd_mapped'] = len(list(Path('/proc/self/fd').iterdir()))
        arrays = [m.features for m in mapped]
        offsets = np.arange(0, rows+1, chunk_rows)
        checksum = 0.
        for start in range(0, rows, 128):
            D.guard()
            batch, legal = L.Learner._batch(SimpleNamespace(device=torch.device('cpu')), arrays, offsets,
                                           np.arange(start, start+128))
            checksum += sum(float(t.sum()) for t in batch.values())+float(legal.sum())
        result.update(read_seconds=time.monotonic()-started-result['write_seconds'], checksum=checksum,
            peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            actual_queue_bytes=sum(r.bytes for r in receipts), admitted_queue_bytes=capacity)
        for m in mapped:
            C.close_maps(m)
        mapped.clear()
        del arrays, batch, legal
        gc.collect()
        for receipt in receipts:
            D.guard()
            queue.acknowledge(receipt)
        result['fd_after'] = len(list(Path('/proc/self/fd').iterdir()))
        C.require(result['fd_after'] <= fd_before+1, 'mapped descriptor leak')
        C.require(not any(p.is_dir() for p in queue.root.iterdir()), 'queue not drained')
        result.update(status='pass', wall_seconds=time.monotonic()-started,
                      full_registered_row_exposure=rows == 262144)
        return result
    except BaseException as ex:
        result['error'] = repr(ex)
        raise
    finally:
        for m in mapped:
            C.close_maps(m)
        C.durable_json(out/'result.json', result)
        C.durable_json(out/'receipts.json', [asdict(r) for r in receipts])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--rows', type=int, default=262144)
    a = p.parse_args()
    print(json.dumps(run(a.out, a.rows), indent=2))


if __name__ == '__main__':
    main()
