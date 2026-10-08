"""P3: event/cadence scheduling and four-root Rust fair search."""
from concurrent.futures import ThreadPoolExecutor
import importlib
import math
import time
from dataclasses import dataclass
from .contracts import Command, DelayContext
from .loading import COUNCIL, ROOT, imports, module, delay_module
from .timing import backend_timing


class Triggers:
    def __init__(self):
        self.last_tick = -10
        self.last_search = -float('inf')
        self.events = self.verified = 0
        self.elixir = -1

    def reason(self, snapshot, now):
        if snapshot.pending or now-self.last_search < .2:
            return None
        reason = ('event' if snapshot.event_serial != self.events else
                  'verification' if snapshot.verification_serial != self.verified else
                  'elixir' if math.floor(snapshot.own['elixir']) != self.elixir else
                  'cadence' if snapshot.tick-self.last_tick >= 10 else None)
        if reason:
            self.last_tick, self.last_search = snapshot.tick, now
            self.events, self.verified = snapshot.event_serial, snapshot.verification_serial
            self.elixir = math.floor(snapshot.own['elixir'])
        return reason


@dataclass(frozen=True)
class DecisionInfo:
    tick: int
    seat: int
    packet: object
    own: dict


class DeadlineReached(Exception):
    pass


class DeadlineNative:
    """Interrupt S6 between bounded native calls, without changing its scorer."""
    def __init__(self, native, deadline):
        self.native, self.deadline = native, deadline

    def __getattr__(self, name):
        method = getattr(self.native, name)
        def call(*args, **kwargs):
            if time.monotonic() >= self.deadline:
                raise DeadlineReached
            return method(*args, **kwargs)
        return call


class RustPlanner:
    def __init__(self, config):
        import numpy as np
        from clasher.rl.c56_rollout_planner import C56SearchConfig
        stage5 = COUNCIL/'engine-speed/stage5'
        # Reconstruct hypothetical roots from public packets and static templates.
        derived = module('clasher_live_derived', stage5/'derived_public_state.py')
        with imports([ROOT/'engine-rs', stage5], {'derived_public_state': derived}):
            resources = module('clasher_live_fair_player', stage5/'fair_player.py').Resources()
        packet = module('clasher_live_packet_builder', COUNCIL/'live-loop/l2/pixel_player.py')
        self.resources = resources
        self.packets = packet.PacketBuilder(resources.builder)
        self.model_hypothesis = packet.model_hypothesis
        self.backend, self.timing_path, self.timing, self.delay_ticks = backend_timing(config)
        self.delay_aware = config.get('delay_aware', True)
        self.cores = [delay_module().DelayAwarePlanner(
                      resources.builder, resources.bots, backend='native',
                      native=resources.native, native_config=resources.config,
                      config=C56SearchConfig(horizon=160, interval=10, threads=1),
                      command_delay=self.delay_ticks, delay_aware=self.delay_aware,
                      seed=config.get('seed', 6108)+i) for i in range(4)]
        self.rng = np.random.default_rng(config.get('seed', 6108))
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='fair-root')
        self.hook = None
        if config.get('delay_hook'):
            name, symbol = config['delay_hook'].split(':')
            self.hook = getattr(importlib.import_module(name), symbol)

    def score(self, core, root, info, candidates, deadline):
        core.info, core.costs = info, self.resources.costs
        if not self.delay_aware or not self.delay_ticks:
            # S6's exact d=0 / flag-off delegation, including native deadline.
            core.score_candidates(root, info.seat, candidates, deadline=deadline)
            return core.last['scores']
        values = [None]*len(candidates)
        native = core.native
        core.native = DeadlineNative(native, deadline)
        try:
            for i, candidate in enumerate(candidates):
                # S6's candidate scores are independent. Finishing all three
                # styles makes this candidate eligible for four-root reduction.
                core.score_candidates(root, info.seat, [candidate])
                if time.monotonic() >= deadline:
                    break
                values[i] = core.last['scores'][0]
        except DeadlineReached:
            pass  # The interrupted candidate contributes no partial score.
        finally:
            core.native = native
        return values

    def decide(self, snapshot, deadline):
        start = time.monotonic()
        base = dict(delay_aware=self.delay_aware, command_delay_ticks=self.delay_ticks,
                    backend=self.backend)
        # P4 feedback is the ONLY live command ledger. In particular do not
        # construct an S6 channel against already-reserved own state, or release
        # its slot at the predicted due tick before pixel verification finishes.
        if snapshot.pending:
            return 2304, dict(base, completed=0, reason='pending',
                              pending_command_id=snapshot.pending.get('command_id'))
        if start >= deadline:
            return 2304, dict(base, completed=0, reason='deadline')
        packet, diagnostic = self.packets.build(snapshot.public, snapshot.tick)
        packet = self.model_hypothesis(packet)
        own = {k: snapshot.own[k] for k in ('hand', 'cycle', 'refill', 'elixir')}
        info = DecisionInfo(snapshot.tick, 1, packet, own)
        candidates, _ = self.cores[0].candidates(packet)
        context = DelayContext(self.backend, self.timing['p50_ms'], self.timing['p99_ms'],
                               self.delay_ticks, None, snapshot.tick, deadline)
        if self.hook:
            action, extra = self.hook(self.resources, info, snapshot.roots, candidates, context)
            if action not in candidates:
                raise ValueError('Delay planner returned a non-public candidate')
            return int(action), dict(diagnostic, **extra, **base)
        if len(candidates) <= 1:
            return int(candidates[0]), dict(diagnostic, **base, completed=0)
        if len(snapshot.roots) != 4:
            raise ValueError('Fair runtime requires four opponent roots')
        roots = [self.resources.root(info, hypothesis, self.rng) for hypothesis in snapshot.roots]
        # Leave 5 ms for result reduction and IPC; native calls are cooperative,
        # not preemptible. Actual overruns are still measured against deadline.
        search_deadline = deadline-.005
        futures = [self.pool.submit(self.score, core, root, info, candidates, search_deadline)
                   for core, root in zip(self.cores, roots)]
        scores = [future.result() for future in futures]
        complete = [(sum(values)/4, i) for i, values in enumerate(zip(*scores))
                    if all(value is not None for value in values)]
        # S6 stable tie handling (epsilon 1e-9); no complete candidate => wait.
        best = None
        for value, i in complete:
            if best is None or value > best[0]+1e-9:
                best = value, i
        action = candidates[best[1]] if best else 2304
        return int(action), dict(diagnostic, **base, completed=len(complete),
                    candidates=len(candidates), candidate_ids=candidates,
                    scores=[value for value, _ in complete],
                    search_ms=(time.monotonic()-start)*1000,
                    deadline_overrun=time.monotonic() > deadline)

    def close(self):
        self.pool.shutdown(wait=True)


class SyntheticPlanner:
    def __init__(self, config):
        pass

    def decide(self, snapshot, deadline):
        return 0, {'synthetic': True, 'completed': 1}

    def close(self):
        pass


def command_for(action, snapshot, command_id, costs, now):
    if action >= 2304:
        return None
    slot, tile = divmod(action, 576)
    card = snapshot.own['hand'][slot]
    if card not in costs:
        return None
    # The public actor's board is rotated to seat 1; touch coordinates are absolute.
    return Command(command_id, snapshot.episode, snapshot.sequence, snapshot.produced_at,
                   now, snapshot.revision, card, costs[card],
                   (18-(tile % 18+.5), 32-(tile//18+.5)), snapshot.produced_at+.4)
