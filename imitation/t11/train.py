"""V2-only guards and mixed sampling around unchanged qualified T4 trainer."""
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
from imitation.model import train as qualified, runner
from imitation.model.store import PackedStore
from imitation.t5.guards import qualification, sha, role_guard
from imitation.t5.resources import install as install_bounded_loader
from .sampling import epoch_indices, train_loader


class DevInterrupted(Exception):
    pass


def frozen(root, path):
    path = Path(path); m = json.loads(path.read_text())
    receipt, receipt_hash = qualification(root)
    assert m['qualified_code_sha256'] == receipt['code_sha256']
    assert m['throughput_receipt_sha256'] == receipt_hash
    for name,digest in m['files'].items():
        assert sha(root/name) == digest, name
    seal = json.loads((path.parent/'freeze.json').read_text())
    assert seal['manifest_sha256'] == sha(path)
    assert seal['prereg_sha256'] == sha(path.parent/'PREREG.md')
    return m, {'T11_manifest':sha(path), 'T11_prereg':seal['prereg_sha256'],
               'T4_code':receipt['code_sha256'],'T4_throughput':receipt_hash,
               'T5_bounded_loader':sha(root/'imitation/t5/resources.py')}


def main():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument('--freeze',type=Path,required=True); p.add_argument('--stop-at')
    ext,remaining = p.parse_known_args()
    root = Path(__file__).resolve().parents[2]; manifest,pins = frozen(root,ext.freeze)
    opts = dict(zip(remaining[::2],remaining[1::2]))
    for key,expected in {'--microbatch':7168,'--batch-size':8192,'--workers':1,'--epochs':6,
                         '--warmup':2000,'--patience':3,'--tile-width':64,'--checkpoint-every':1000}.items():
        assert str(opts.get(key)) == str(expected), key
    assert int(opts['--seed']) in (2026100821,2026100822)
    assert not any(k in remaining for k in ('--max-steps','--subset-fraction','--epoch-fraction','--overfit-rows','--synthetic-smoke'))
    receipt = json.loads(Path(opts['--qualification']).read_text())
    assert receipt['schema'] == 'clasher.imitation.t11-store-pass.v1' and receipt['passed']
    assert sha(opts['--qualification']) == manifest['store_receipt_sha256']
    assert sha(opts['--assets']) == manifest['assets_sha256']
    stop = threading.Event()

    class TrainingStore(PackedStore):
        def __init__(self,directory,role,assets=None):
            role_guard(directory,role,manifest)
            super().__init__(directory,role,assets)
            rm = json.loads((self.root.parent/'manifest.json').read_text())
            assert rm['production'] and rm['version']=='v2'
            self.hashes.update(pins)

    original_signal = signal.signal
    def install_signal(signum,handler):
        if signum in (signal.SIGTERM,signal.SIGINT) and callable(handler):
            def receive(sig,frame): stop.set(); handler(sig,frame)
            return original_signal(signum,receive)
        return original_signal(signum,handler)

    original_dev_loader = runner.batch_loader
    def dev_loader(*args,**kwargs):
        for b,y in original_dev_loader(*args,**kwargs):
            if stop.is_set(): raise DevInterrupted()
            yield b,y

    install_bounded_loader()
    qualified.PackedStore = TrainingStore
    qualified.epoch_indices = epoch_indices
    qualified.batch_loader = train_loader
    runner.batch_loader = dev_loader
    signal.signal = install_signal
    timer = None
    if ext.stop_at:
        delay = (datetime.fromisoformat(ext.stop_at.replace('Z','+00:00'))-datetime.now(timezone.utc)).total_seconds()
        assert delay > 0, 'stop deadline already reached'
        timer = threading.Timer(delay,lambda:os.kill(os.getpid(),signal.SIGTERM)); timer.daemon=True; timer.start()
    if socket_host_leased() and ext.stop_at != '2026-10-09T04:20:00Z':
        raise ValueError('leased run requires the predeclared early stop')
    output = Path(opts['--output']); sys.argv = [sys.argv[0],*remaining]
    started = datetime.now(timezone.utc).isoformat(); before = time.monotonic(); status='failed'
    try:
        qualified.main(); status='checkpointed' if stop.is_set() else 'complete'
    except DevInterrupted:
        status='checkpointed_during_dev'
    finally:
        signal.signal = original_signal
        if timer: timer.cancel()
        if output.exists():
            own,child=resource.getrusage(resource.RUSAGE_SELF),resource.getrusage(resource.RUSAGE_CHILDREN)
            with (output/'segments.jsonl').open('a') as f:
                f.write(json.dumps(dict(started_at=started,ended_at=datetime.now(timezone.utc).isoformat(),pid=os.getpid(),
                      status=status,pins=pins,wall_seconds=time.monotonic()-before,
                      cpu_seconds=own.ru_utime+own.ru_stime+child.ru_utime+child.ru_stime,stop_at=ext.stop_at))+'\n')


def socket_host_leased():
    import socket
    host=socket.gethostname().split('.')[0]
    if host not in ('127x01','127x04','127x08','127x09','127x15','127x16','127x18'):
        raise ValueError('host outside T11 allocation')
    return host in ('127x09','127x15','127x16','127x18')


if __name__ == '__main__': main()
