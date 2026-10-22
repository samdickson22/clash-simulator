"""Terminal-boundary actor object recycling, with no launch or learner/engine-resume API.

The coordinator and its queue stay live. A capture can replace one idle actor
object exactly once. A process handoff requires the original worker to be dead
and a durable one-use claim. It cannot resume an engine, replay publications, or restore a learner.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import time
import threading
import socket
import uuid
import weakref

from . import stream_actor as A
from . import lease_supervisor as S

_TRANSFER_LOCK = threading.RLock()


class WorkerError(ValueError):
    """Halt the seed and report final generated counters. Never top up data."""


def require(ok, message):
    if not ok:
        raise WorkerError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def durable_json(path, value):
    """Publish one audit record; caller supplies an admitted private directory."""
    path = Path(path)
    directory = S.directory(os.fspath(path.parent))
    temporary = '.'+path.name+'.'+uuid.uuid4().hex
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=directory)
        with os.fdopen(fd, 'wb') as out:
            out.write(encoded(value))
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path.name, src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
    finally:
        try:
            os.unlink(temporary, dir_fd=directory)
        except FileNotFoundError:
            pass
        os.close(directory)


_COUNTERS = ('generated_steps', 'published_steps', 'discarded_steps', 'completed_games',
             'unfinished_games', 'boundary_declined_steps')
_DRIVER_KEYS = {'publication_sequence', 'next_game_sequence', 'seed', 'actor_id',
                'schedule_sha256', 'runtime_provenance_sha256'}


def _driver(state, actor):
    require(isinstance(state, dict) and set(state) == _DRIVER_KEYS, 'exact driver checkpoint context required')
    require(all(A._integer(state[k]) and state[k] >= 0 for k in
                ('publication_sequence', 'next_game_sequence')), 'invalid driver sequence')
    require(state['seed'] == actor.seed and type(state['seed']) is int
            and state['actor_id'] == actor.actor_id, 'driver actor/seed mismatch')
    require(A._sha(state['schedule_sha256']) and state['runtime_provenance_sha256'] == actor.provenance_sha256,
            'driver schedule/runtime pin mismatch')
    require(state['next_game_sequence'] == actor.completed_games, 'driver completed-game count mismatch')
    require(actor.completed_games <= state['publication_sequence'] <= actor.generated_steps,
            'driver publication count outside generated/completed bounds')
    return json.loads(encoded(state))


def _idle(actor):
    require(isinstance(actor, A.StreamingPolicyOursPlayer), 'actual streaming actor required')
    require(not actor.failed and not getattr(actor, '_lifecycle_retired', False), 'failed or retired actor')
    require(all(getattr(actor, k) is None for k in
                ('battle', 'session', 'frames', 'shadow_builder', 'shadow_hist', 'pending'))
            and not actor.rows, 'checkpoint requires closed game and no pending rows')
    require(actor.completed_games > getattr(actor, '_lifecycle_completed_floor', 0) and actor.unfinished_games == actor.discarded_steps == 0,
            'checkpoint requires true completed games without discarded data')
    require(actor.generated_steps == actor.published_steps, 'unacknowledged actor publication')
    require(all(A._integer(getattr(actor, k)) and getattr(actor, k) >= 0 for k in _COUNTERS),
            'invalid actor counters')
    require(actor.generated_steps <= actor.budget_steps and actor.remaining_quota >= 0,
            'invalid remaining actor budget/quota')
    require(not actor.model.original.training, 'actor policy left evaluation mode')
    require(A.policy_sha256(actor.model.original) == actor.policy_sha256, 'actor policy changed outside acknowledgement')


def process_identity():
    return dict(host=socket.gethostname(), boot=S.boot_id(), pid=os.getpid(),
                start=S.proc_stat(os.getpid())[4])


def _state(actor, driver_state):
    _idle(actor)
    return dict(schema=1, resume_kind='terminal-actor-only-live-coordinator',
                source_process=process_identity(),
                engine_resume_qualified=False, process_resume_qualified=False,
                actor_id=actor.actor_id, seed=actor.seed, name=actor.name,
                anchor_sha256=actor.anchor_sha256, provenance_sha256=actor.provenance_sha256,
                opponent_id=actor.opponent_id, budget_steps=actor.budget_steps,
                remaining_quota=actor.remaining_quota, chunk_rows=actor.chunk_rows,
                version=actor.version, policy_sha256=actor.policy_sha256,
                model_cfg=json.loads(encoded(actor.model.original.cfg)),
                counters={k: int(getattr(actor, k)) for k in _COUNTERS},
                counts=dict(actor.counts), exhausted=actor.exhausted,
                driver_state=_driver(driver_state, actor))


class ActorCheckpoint:
    def __init__(self, actor, state):
        self._source = weakref.ref(actor)
        self._bytes = encoded(state)
        self._used = False

    @classmethod
    def capture(cls, actor, driver_state):
        with _TRANSFER_LOCK:
            return cls(actor, _state(actor, driver_state))

    @property
    def record(self):
        return json.loads(self._bytes)

    @property
    def sha256(self):
        return hashlib.sha256(self._bytes).hexdigest()

    def write(self, path):
        """Audit only. An on-disk record never grants a continuation permit."""
        durable_json(path, dict(checkpoint=self.record, sha256=self.sha256))

    def restore(self, model, publish, *, driver_state):
        """Consume the original idle object, preserving its exact lifetime budget.

        The caller retains the live coordinator and passes the same callback and
        unchanged driver cursor. Publication callbacks already returned, but the
        coordinator may still own queue files until its next quota update. This
        function never consumes, acknowledges, replays or unlinks those files.
        """
        with _TRANSFER_LOCK:
            return self._restore_live(model, publish, driver_state=driver_state)

    def _restore_live(self, model, publish, *, driver_state):
        require(not self._used, 'actor checkpoint already consumed')
        source = self._source()
        require(source is not None, 'original live actor required; disk/process resume denied')
        state = self.record
        require(publish is source.publish, 'retain the original live coordinator callback')
        require(_state(source, driver_state) == state, 'source actor or driver advanced since capture')
        replacement = _replacement(state, model, publish, driver_state)
        # Poison every other outstanding capture of this same source as well.
        source._lifecycle_retired = True
        source.failed = True
        self._used = True
        return replacement

    @classmethod
    def restore_record(cls, record, model, publish, *, expected_sha256, driver_state, claim_directory):
        """Restore only after the old process died; caller keeps coordinator live.

        The parent must receive and retain this exact digest before reaping the
        original process. A claim survives failure and disallows any retry of the
        same handoff. A process/learner crash is a stopped seed, never run resume.
        """
        require(A._sha(expected_sha256) and hashlib.sha256(encoded(record)).hexdigest() == expected_sha256,
                'checkpoint digest mismatch')
        require(isinstance(record, dict) and record.get('schema') == 1
                and record.get('resume_kind') == 'terminal-actor-only-live-coordinator'
                and record.get('engine_resume_qualified') is False
                and record.get('process_resume_qualified') is False, 'unsupported checkpoint kind')
        identity = record.get('source_process')
        require(isinstance(identity, dict) and set(identity) == {'host', 'boot', 'pid', 'start'},
                'missing original process identity')
        require(identity['host'] == socket.gethostname() and identity['boot'] == S.boot_id(),
                'cross-host or cross-boot continuation denied')
        require(all(type(identity[k]) is int and identity[k] > 0 for k in ('pid', 'start')),
                'invalid original process identity')
        require(not S.alive(identity['pid'], identity['start']), 'original actor process is still live')
        # Validate all model/counter/cursor data before consuming the claim.
        replacement = _replacement(record, model, publish, driver_state)
        claim = Path(claim_directory)/('handoff-'+expected_sha256+'.claim')
        directory = S.directory(os.fspath(claim.parent))
        try:
            try:
                fd = os.open(claim.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
            except FileExistsError as ex:
                raise WorkerError('actor handoff already claimed; retry denied') from ex
            with os.fdopen(fd, 'wb') as out:
                out.write(encoded(dict(checkpoint_sha256=expected_sha256, claimant=process_identity())))
                out.flush()
                os.fsync(out.fileno())
            os.fsync(directory)
        finally:
            os.close(directory)
        return replacement


def _replacement(state, model, publish, driver_state):
    try:
        counters = state['counters']
        require(isinstance(counters, dict) and set(counters) == set(_COUNTERS)
                and all(type(v) is int and v >= 0 for v in counters.values()), 'invalid checkpoint counters')
        require(0 < counters['completed_games'] <= counters['generated_steps']
                and counters['boundary_declined_steps'] <= counters['completed_games'] and counters['unfinished_games'] == counters['discarded_steps'] == 0
                and counters['generated_steps'] == counters['published_steps'], 'checkpoint has unfinished/unpublished data')
        require(state['exhausted'] is False and type(state['budget_steps']) is int
                and type(state['remaining_quota']) is int and state['remaining_quota'] > 0
                and counters['generated_steps'] < state['budget_steps'], 'actor lifetime budget exhausted')
        require(isinstance(state['counts'], dict) and all(isinstance(k, str) and type(v) is int and v >= 0
                for k, v in state['counts'].items()) and sum(state['counts'].values()) == counters['generated_steps'],
                'checkpoint sampled-step counters mismatch')
        require(state['driver_state'] == driver_state and set(driver_state) == _DRIVER_KEYS,
                'driver checkpoint cursor mismatch')
        require(json.loads(encoded(model.cfg)) == state['model_cfg'], 'replacement model config mismatch')
        replacement = A.StreamingPolicyOursPlayer(model, publish,
            actor_id=state['actor_id'], seed=state['seed'], name=state['name'],
            anchor_sha256=state['anchor_sha256'], provenance_sha256=state['provenance_sha256'],
            opponent_id=state['opponent_id'], budget_steps=state['budget_steps'],
            quota_steps=state['remaining_quota'], chunk_rows=state['chunk_rows'],
            version=state['version'], expected_policy_sha256=state['policy_sha256'])
        for key, value in counters.items():
            setattr(replacement, key, value)
        replacement.counts = dict(state['counts'])
        replacement._lifecycle_completed_floor = replacement.completed_games
        _driver(driver_state, replacement)
        return replacement
    except (KeyError, TypeError, AttributeError) as ex:
        raise WorkerError('malformed actor checkpoint') from ex


@dataclass(frozen=True)
class WorkerBoundary:
    event: str
    actor_id: str
    game_id: str
    game_sequence: int
    seed: int
    policy_version: int
    policy_sha256: str
    generated_steps: int
    published_steps: int
    discarded_steps: int
    engine_tick: int
    terminal: bool
    pending_rows: int
    publication_sequence: int
    remaining_quota: int
    remaining_budget: int
    engine_resume_qualified: bool = False


@dataclass(frozen=True)
class LifecycleDecision:
    action: str  # continue | recycle_due | drain
    safe_boundary: bool
    reason: str | None


def rss_bytes():
    with open('/proc/self/status') as source:
        for line in source:
            if line.startswith('VmRSS:'):
                return int(line.split()[1])*1024
    raise WorkerError('worker RSS unavailable')


class ActorLifecycle:
    """Observe driver boundaries. The caller owns stopping and OS processes.

    A due recycle remains due until actual process replacement. Replacing just
    an actor object never resets the process clock or completed-game count.
    Hooks are synchronous and cannot interrupt a blocked engine or callback.
    """
    def __init__(self, *, actor_id, monotonic=time.monotonic, read_rss=rss_bytes,
                 recycle_seconds=1200., recycle_games=50, rss_cap_bytes=2 << 30,
                 lease=None):
        require(isinstance(actor_id, str) and actor_id, 'actor identity required')
        require(type(recycle_seconds) in (int, float) and math.isfinite(recycle_seconds)
                and 0 < recycle_seconds <= 1200, 'recycle time must be at most 1200s')
        require(type(recycle_games) is int and 0 < recycle_games <= 50, 'recycle cap must be at most 50 games')
        require(type(rss_cap_bytes) is int and 0 < rss_cap_bytes <= 2 << 30, 'RSS cap must be at most 2 GiB')
        self.actor_id, self.clock, self.read_rss = actor_id, monotonic, read_rss
        self.started, self.games = self.clock(), 0
        self.recycle_seconds, self.recycle_games, self.rss_cap_bytes = recycle_seconds, recycle_games, rss_cap_bytes
        self.lease = lease
        self.last = None
        self._active_game = None
        self._game_generated_start = None
        self._completed = set()
        self._stop_reason = None
        self.retirement_request = None
        self.last_clock = self.started

    def request_stop(self, reason):
        require(isinstance(reason, str) and reason, 'stop reason required')
        self._stop_reason = self._stop_reason or reason

    def on_boundary(self, record):
        require(isinstance(record, WorkerBoundary), 'immutable worker boundary required')
        r = record
        require(r.actor_id == self.actor_id and r.event in
                ('game_start', 'publication', 'game_complete', 'budget_complete'), 'unknown actor/event')
        require(r.engine_resume_qualified is False and type(r.terminal) is bool, 'unqualified engine resume or terminal context')
        require(all(A._integer(getattr(r, k)) and getattr(r, k) >= 0 for k in
            ('game_sequence', 'policy_version', 'generated_steps', 'published_steps', 'discarded_steps',
             'engine_tick', 'pending_rows', 'publication_sequence', 'remaining_quota', 'remaining_budget')),
            'invalid boundary counter')
        require(A._integer(r.seed) and isinstance(r.game_id, str) and r.game_id and A._sha(r.policy_sha256),
                'missing game/seed/policy identity')
        require(r.published_steps <= r.generated_steps and r.discarded_steps == 0,
                'discarded or overpublished actor data')
        if self.last is not None:
            p = self.last
            require(r.seed == p.seed and r.generated_steps >= p.generated_steps
                    and r.published_steps >= p.published_steps and r.publication_sequence >= p.publication_sequence,
                    'worker counters/seed regressed')
            require(r.generated_steps+r.remaining_budget == p.generated_steps+p.remaining_budget,
                    'worker lifetime budget changed')
            require(r.policy_version in (p.policy_version, p.policy_version+1), 'policy version skipped/regressed')
            require(r.policy_version != p.policy_version or r.policy_sha256 == p.policy_sha256,
                    'same-version policy changed')
        identity = (r.game_id, r.game_sequence)
        if r.event == 'game_start':
            self.check()
            require(self.retirement_request is None and self._stop_reason is None,
                    'new game forbidden after retirement or stop request')
            require(self._active_game is None and not any(gid == r.game_id for gid, _ in self._completed) and not r.terminal,
                    'active or replayed game start')
            require(r.pending_rows == 0, 'new game has pending rows')
            if self.last is not None:
                require(r.game_sequence == self.last.game_sequence+1, 'game sequence skipped/regressed')
            self._active_game = identity
            self._game_generated_start = r.generated_steps
        elif r.event == 'budget_complete' and self._active_game is None:
            require(identity in self._completed and r.remaining_budget == 0 and r.terminal,
                    'final budget must belong to the just-completed game')
        else:
            require(identity == self._active_game, 'publication/close outside active game')
        safe = r.event == 'game_complete'
        if safe:
            require(r.terminal and r.pending_rows == 0 and r.generated_steps == r.published_steps
                    and r.generated_steps > self._game_generated_start,
                    'game completion is not a safe terminal boundary')
            self.games += 1
            self._completed.add(identity)
            self._active_game = None
        self.last = r
        return self.check(safe_boundary=safe)

    def check(self, *, safe_boundary=False):
        """Call before public polls as well as after blocking acknowledgements.

        A retirement request finishes the active real game. RSS/read failures
        raise immediately; the driver aborts the seed with its authoritative
        generated count. Only on_boundary may certify a terminal boundary.
        """
        require(type(safe_boundary) is bool, 'boolean boundary required')
        require(not safe_boundary or (self.last is not None and self.last.event == 'game_complete'
                and self._active_game is None), 'uncertified safe boundary')
        rss = self.read_rss()
        require(type(rss) is int and 0 < rss <= self.rss_cap_bytes, 'worker RSS cap breached or unobservable')
        current = self.clock()
        require(type(current) in (float, int) and math.isfinite(current) and current >= self.last_clock,
                'worker monotonic clock regressed or invalid')
        self.last_clock = current
        if self.lease is not None:
            reason = self.lease.poll()
            if reason:
                self.request_stop(reason)
        if self._stop_reason:
            return LifecycleDecision('drain', safe_boundary, self._stop_reason)
        due = current-self.started >= self.recycle_seconds or self.games >= self.recycle_games
        if due and self.retirement_request is None:
            self.retirement_request = dict(monotonic=current, reason='process recycle bound reached',
                                           completed_games=self.games, source_process=process_identity())
        return LifecycleDecision('recycle_due' if self.retirement_request is not None else 'continue',
                                 safe_boundary, self.retirement_request['reason'] if self.retirement_request else None)
