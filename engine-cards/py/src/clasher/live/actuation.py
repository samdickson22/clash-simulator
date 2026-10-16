"""P4: sole owner of the unchanged T2 state machine and persistent input."""
from dataclasses import asdict
import time
from .contracts import Feedback
from .loading import V4, actuator_module, module
from .timing import backend_timing


class MockInput:
    def __init__(self, delay=.02):
        self.delay = delay
        self.taps = []

    def play(self, slot, x, y, delay=.02):
        start = time.monotonic()
        time.sleep(self.delay)
        self.taps.append((slot, x, y))
        return (time.monotonic()-start)*1000

    def close(self):
        pass


class Actuation:
    def __init__(self, channel, backend='offline-renderer-grpc', timing_path=None):
        self.api = actuator_module()
        self.backend, timing_path, _, self.delay_ticks = backend_timing(
            dict(backend=backend, timing_path=timing_path))
        self.machine = self.api.Actuator(backend=backend, timing_path=timing_path)
        self.channel = channel
        self.command = None
        self.highest_id = -1
        self.revision = 0
        self.last_hud = None
        self.fence = -float('inf')

    def pending(self):
        p = self.machine.pending
        if p is None:
            return None
        return dict(command_id=self.command.command_id, backend=self.backend,
                    command_delay_ticks=self.delay_ticks,
                    card=p.card, cost=p.cost, slot=p.slot, tile=p.tile,
                    submitted_at=p.submitted_at, attempts=p.attempts,
                    before_elixir=p.before.elixir, before_hand=p.before.hand,
                    next_card=p.before.next_card,
                    rollback_at=(p.submitted_at if p.attempts == 1 else p.retry_at)+self.machine.verify_seconds+.2)

    def feedback(self, state, hud, detail, now):
        self.revision += 1
        c = self.command
        return Feedback(c.command_id, now, self.revision, state, c.card, c.cost,
                        hud, self.pending(), detail)

    def submit(self, command, hud, now):
        # IDs are never recycled within a run. A queued duplicate is consumed
        # without disturbing the currently outstanding reservation.
        if command.command_id <= self.highest_id:
            return None, {'state': 'blocked', 'reason': 'duplicate command'}
        self.highest_id = command.command_id
        if self.machine.pending:
            return None, {'state': 'blocked', 'reason': 'pending'}
        self.command = command
        reason = ('expired command' if now > command.expires_at else
                  'old ledger revision' if command.revision != self.revision else
                  'pre-terminal decision' if command.produced_at <= self.fence else
                  'missing HUD' if hud is None else None)
        result = ({'state': 'blocked', 'reason': reason} if reason else
                  self.machine.submit(command.card, command.cost, command.tile, hud, now))
        if result['state'] == 'tap':
            self.last_hud = hud
            # Reservation exists BEFORE transport; timeout is ambiguous and
            # must leave it pending for pixel verification, never immediate retry.
            return self.feedback('submitted', hud, result, now), result
        return self.feedback('blocked', hud, result, now), result

    def execute(self, request):
        if request['state'] != 'tap':
            return None
        start = time.monotonic()
        try:
            self.channel.play(request['slot'], *request['tile'], delay=.020)
            return dict(transport_ms=(time.monotonic()-start)*1000, ambiguous=False)
        except Exception as error:
            return dict(transport_ms=(time.monotonic()-start)*1000,
                        ambiguous=True, error=f'{type(error).__name__}: {error}')

    def observe(self, hud, now):
        if hud is not None and (self.last_hud is None or hud.produced_at > self.last_hud.produced_at):
            self.last_hud = hud
        if self.machine.pending is None or self.last_hud is None:
            return None, None
        result = self.machine.observe(self.last_hud, now)
        if result['state'] in ('accepted', 'failed'):
            # Wall-time fence rejects decisions made during the outstanding
            # interval, even after P2 has received the terminal result.
            self.fence = now
            return self.feedback(result['state'], self.last_hud, result, now), result
        if result['state'] == 'tap':
            return self.feedback('retry', self.last_hud, result, now), result
        return None, result


def input_channel(config):
    if config['kind'] == 'mock':
        return MockInput(config.get('tap_seconds', .02))
    return module('clasher_live_input', V4/'input_channel.py').GrpcInput(
        config['port'], config['proto_dir'], config['discovery'])
