"""Read our supervisor's generation stop notification. Never open an owner lease.

The R37 watcher alone enforces owner-lease cadence, persisted grace and exact
process signals. This adapter adds cooperative draining to actor jobs. Call poll
at public polls and after blocking publication acknowledgements. A hung worker
still depends on the external watcher for its hard deadline.
"""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import time

from . import lease_supervisor as S


class LeaseAdapterError(ValueError):
    """Stop the seed; notification identity or the job environment is invalid."""


def require(ok, message):
    if not ok:
        raise LeaseAdapterError(message)


def utc(value):
    return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).timestamp()


def _notification_json(raw):
    def integer(text):
        # Match the supervisor's integer bound, including on Python 3.8.
        require(len(text) <= 1024, 'notification integer too long')
        return int(text)

    def number(text):
        value = float(text)
        require(math.isfinite(value), 'nonfinite notification number')
        return value

    # Validate numeric tokens even in unused fields or shadowed duplicate keys.
    return json.loads(raw, parse_int=integer, parse_float=number, parse_constant=number)


class LeaseStopAdapter:
    def __init__(self, *, stop_file, token, stop_by_utc, boot=None, wall_time=time.time):
        self.path = os.path.abspath(os.fspath(stop_file))
        self.name = Path(self.path).stem
        require(self.path.endswith('.stop') and S.valid_name(self.name), 'invalid lease stop file name')
        require(S.under(self.path, (S.STATE_ROOT+'/',)), 'stop file outside our lease state')
        require(isinstance(token, str) and re.fullmatch('[0-9a-f]{32}', token) is not None,
                'invalid inherited lease token')
        self.token, self.boot, self.clock = token, boot or S.boot_id(), wall_time
        self.stop_by = utc(stop_by_utc)
        self.reason = None

    @classmethod
    def from_environment(cls, env=None):
        env = os.environ if env is None else env
        keys = ('CLASHER_LEASE_STOP_FILE', 'CLASHER_LEASE_JOB', 'CLASHER_LEASE_STOP_BY_UTC')
        values = [env.get(k) for k in keys]
        if all(v is None for v in values):
            return None  # own hosts never depend on leased capacity
        require(all(isinstance(v, str) and v for v in values), 'partial inherited lease environment')
        return cls(stop_file=values[0], token=values[1], stop_by_utc=values[2])

    def poll(self):
        if self.reason is not None:
            return self.reason
        if self.clock() >= self.stop_by:
            self.reason = 'lease scheduled stop bound'
            return self.reason
        try:
            with S.safe_open(self.path, 'rb') as source:
                raw = source.read(65537)
        except FileNotFoundError:
            return None
        except OSError as ex:
            raise LeaseAdapterError('own stop notification unreadable') from ex
        try:
            require(len(raw) <= 65536, 'own stop notification exceeds bound')
            record = _notification_json(raw)
            require(isinstance(record, dict), 'own stop notification is not an object')
            require(record.get('name') == self.name and record.get('token') == self.token
                    and record.get('boot') == self.boot, 'own stop notification generation mismatch')
            require(isinstance(record.get('reason'), str) and record['reason'], 'missing stop reason')
            utc(record['utc'])
        except (ValueError, TypeError, KeyError, RecursionError, OverflowError) as ex:
            raise LeaseAdapterError('invalid own stop notification') from ex
        self.reason = record['reason']
        return self.reason
