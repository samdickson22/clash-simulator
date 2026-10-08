"""Auditable adapter around the unchanged, throughput-qualified T4 train.main.

Extension points are explicit: policy factory, store provenance, row-index
annotation, GRU role binding, and interruptible dev. Optimizer, sampling, loss,
microbatch accumulation, EMA, scheduler, checkpoint/RNG and loop are T4's.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import signal
import sys
import threading
import time
from imitation.model import train as qualified
from imitation.model import runner
from imitation.model.batching import batch_loader as qualified_loader
from imitation.model.store import PackedStore
from .guards import frozen, qualification, role_guard
from .variants import create_policy


class DevInterrupted(Exception):
    pass


def indexed_loader(store, batch_size, indices=None, **kwargs):
    for b, y in qualified_loader(store, batch_size, indices, **kwargs):
        b['row_index'] = y['index']
        yield b, y


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--variant', choices=('main', 'noD1', 'gru'), required=True)
    parser.add_argument('--freeze', type=Path)
    parser.add_argument('--stop-at')
    extension, remaining = parser.parse_known_args()
    root = Path(__file__).resolve().parents[2]
    receipt, receipt_hash = qualification(root)
    synthetic = '--synthetic-smoke' in remaining
    if synthetic:
        manifest = None
        pins = {'T4_code': receipt['code_sha256'], 'T4_throughput': receipt_hash}
    else:
        if extension.freeze is None:
            raise ValueError('freeze is required before any fitted run')
        manifest, pins = frozen(root, extension.freeze)
        # No unregistered recipe flags, including an accidentally stale microbatch.
        options = dict(zip(remaining[::2], remaining[1::2]))
        for key, expected in (('--microbatch', receipt['microbatch']), ('--batch-size', 8192),
                              ('--workers', receipt['workers']), ('--epochs', 12),
                              ('--warmup', 2000), ('--patience', 3), ('--tile-width', 64)):
            if str(options.get(key)) != str(expected):
                raise ValueError('explicit registered option required: '+key)
        if any(k in remaining for k in ('--max-steps', '--subset-fraction', '--epoch-fraction', '--overfit-rows')):
            raise ValueError('partial/extra fitting forbidden')
        seed = int(options['--seed'])
        if seed not in ([2026100801, 2026100802, 2026100803] if extension.variant == 'main' else [2026100801]):
            raise ValueError('unregistered run seed')
    pins['T5_variant'] = extension.variant
    stores = {}
    stopping = threading.Event()

    class TrainingStore(PackedStore):
        def __init__(self, directory, role, assets=None):
            if manifest is not None:
                role_guard(directory, role, manifest)
            super().__init__(directory, role, assets)
            self.hashes.update(pins)
            stores[role] = self

    def factory(config, descriptors, tiles, costs):
        model = create_policy(extension.variant, config, descriptors, tiles, costs)
        if extension.variant == 'gru':
            model.bind_store(stores['train'])
        return model

    original_dev = runner.dev_joint_nll

    def guarded_loader(*args, **kwargs):
        for b, y in indexed_loader(*args, **kwargs):
            if stopping.is_set():
                raise DevInterrupted('SIGTERM/deadline during dev; pre-dev checkpoint retained')
            yield b, y

    def dev(model, ema, store, *args, **kwargs):
        if extension.variant == 'gru':
            model.bind_store(store)
        try:
            return original_dev(model, ema, store, *args, **kwargs)
        finally:
            if extension.variant == 'gru':
                model.bind_store(stores['train'])

    original_signal = signal.signal

    def install(signum, handler):
        if signum in (signal.SIGTERM, signal.SIGINT) and callable(handler):
            def receive(sig, frame):
                stopping.set()
                handler(sig, frame)
            return original_signal(signum, receive)
        return original_signal(signum, handler)

    # This is deliberate in-process dependency injection, never source rewriting.
    qualified.PackedStore = TrainingStore
    qualified.SetPolicy = factory
    qualified.batch_loader = indexed_loader
    runner.batch_loader = guarded_loader
    runner.dev_joint_nll = dev
    signal.signal = install
    timer = None
    if extension.stop_at:
        delay = (datetime.fromisoformat(extension.stop_at.replace('Z', '+00:00'))-datetime.now(timezone.utc)).total_seconds()
        if delay <= 0:
            raise ValueError('planned stop deadline already reached')
        timer = threading.Timer(delay, lambda: os.kill(os.getpid(), signal.SIGTERM))
        timer.daemon = True
        timer.start()
    output = Path(remaining[remaining.index('--output')+1])
    sys.argv = [sys.argv[0], *remaining]
    started = datetime.now(timezone.utc).isoformat()
    before = time.monotonic()
    exit_status = 'failed'
    try:
        qualified.main()
        exit_status = 'checkpointed' if stopping.is_set() else 'complete'
    except DevInterrupted:
        exit_status = 'checkpointed_during_dev'
    finally:
        signal.signal = original_signal
        if timer:
            timer.cancel()
        if output.exists():
            own, child = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
            record = {'started_at': started, 'ended_at': datetime.now(timezone.utc).isoformat(),
                      'pid': os.getpid(), 'status': exit_status, 'pins': pins,
                      'wall_seconds': time.monotonic()-before,
                      'cpu_seconds': own.ru_utime+own.ru_stime+child.ru_utime+child.ru_stime,
                      'peak_self_rss_kib': own.ru_maxrss, 'stop_at': extension.stop_at}
            with (output/'segments.jsonl').open('a') as f:
                f.write(json.dumps(record)+'\n')


if __name__ == '__main__':
    main()
