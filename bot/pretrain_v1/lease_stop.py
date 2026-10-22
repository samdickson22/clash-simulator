"""Opt-in lease checkpoint and exit. Interrupted seeds are never resumed or admitted."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path
import signal
import socket
import stat
import tempfile


class LeaseStopped(SystemExit):
    pass


def atomic_write(path, writer):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            writer(stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class LeaseStop:
    def __init__(self, out, seed):
        self.out, self.seed = Path(out), seed
        self.signal_requested = False
        self.token = os.environ['CLASHER_LEASE_JOB']
        self.path = Path(os.environ['CLASHER_LEASE_STOP_FILE'])
        host = socket.gethostname().split('.')[0]
        expected = Path('/mpac/sdicks02/jobs/clasher/lease-20261022') / host / 'jobs'
        if self.path.parent != expected or self.path.suffix != '.stop' or not self.token:
            raise RuntimeError('invalid lease generation context')
        self.name = self.path.name[:-5]
        self.boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        self._utc(os.environ['CLASHER_LEASE_STOP_BY_UTC'])
        if any(self.out.iterdir()):
            raise RuntimeError('supplemental seed output already exists; no resume permitted')
        signal.signal(signal.SIGTERM, self._signal)

    @classmethod
    def from_env(cls, out, seed):
        value = os.environ.get('PV1_LEASE_STOP_ONLY')
        if value is None:
            return None
        if value != '1':
            raise RuntimeError('PV1_LEASE_STOP_ONLY must be exactly 1')
        return cls(out, seed)

    def _signal(self, *_):
        self.signal_requested = True

    @staticmethod
    def _utc(value):
        if not isinstance(value, str) or re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', value) is None:
            raise ValueError('invalid notification UTC')
        parsed = dt.datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc)
        return parsed.timestamp()

    def notification(self):
        try:
            fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            if self.signal_requested:
                raise RuntimeError('SIGTERM without own durable lease notification')
            return None
        with os.fdopen(fd, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise RuntimeError('lease notification is not a regular file')
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise RuntimeError('oversized lease notification')
        value = json.loads(raw)
        if not isinstance(value, dict) or any(value.get(k) != v for k, v in
                [('name', self.name), ('token', self.token), ('boot', self.boot)]):
            raise RuntimeError('lease notification generation mismatch')
        if not isinstance(value.get('reason'), str) or not value['reason'].strip():
            raise RuntimeError('invalid lease notification reason')
        if self._utc(value.get('utc')) > dt.datetime.now(dt.timezone.utc).timestamp() + 60:
            raise RuntimeError('future lease notification')
        return value

    def poll(self, model=None, optimizer=None, scheduler=None, *, step=0, epoch=-1,
             consumed_batches=0, phase='initialization', args=None, pool=None, model_state=None):
        notice = self.notification()
        if notice is None:
            return
        progress = dict(schema='clasher.supplemental-bc.lease-exit.v1',
                        status='cancelled-by-lease', finished=False, admitted=False,
                        seed=self.seed, consumed_optimizer_steps=step, epoch=epoch,
                        consumed_batches=consumed_batches, phase=phase,
                        initialization_without_model=model is None, notification=notice,
                        source_commit='40ea0b503d94daba5486cb151f759b233664ba43',
                        args=vars(args) if args is not None else None,
                        model_state_origin='final-training-boundary' if model_state is not None else 'current-safe-boundary',
                        pid=os.getpid(), checkpoint=None,
                        artifacts=sorted(p.name for p in self.out.iterdir() if p.is_file()))
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)
        if model is not None:
            import torch
            target = self.out / 'lease-interrupted-NOT-ADMITTED.pt'
            progress['checkpoint'] = target.name
            progress['artifacts'] = sorted(set(progress['artifacts'] + [target.name, 'lease-exit.json']))
            payload = dict(progress=progress, model=model_state if model_state is not None else model.state_dict(), cfg=model.cfg,
                           optimizer=optimizer.state_dict() if optimizer is not None else None,
                           scheduler=scheduler.state_dict() if scheduler is not None else None)
            atomic_write(target, lambda stream: torch.save(payload, stream))
            progress['checkpoint'] = target.name
        atomic_write(self.out / 'lease-exit.json',
                     lambda stream: stream.write((json.dumps(progress, indent=2) + '\n').encode()))
        print(json.dumps(progress), flush=True)
        raise LeaseStopped(75)
