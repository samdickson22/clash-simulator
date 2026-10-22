"""In-process exact-quota barrier. No actors, transport, engine, or launch entry point.

See reports/bot/pretrain-v1/RL-COORDINATOR-CONTRACT.md for caller obligations.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import threading
import time
from typing import Callable, Mapping

import numpy as np

from . import featurize as F
from . import rl_learner as L
from . import stream_actor as A


class CoordinatorError(ValueError):
    """Permanent seed stop. Never retry or replace generated data."""


def require(ok, message):
    if not ok:
        raise CoordinatorError(message)


def integer(n):
    return isinstance(n, (int, np.integer)) and not isinstance(n, (bool, np.bool_))


def text(s):
    return isinstance(s, str) and 0 < len(s) <= 256


def encoded(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(obj):
    return hashlib.sha256(encoded(obj)).hexdigest()


@dataclass(frozen=True)
class Publication:
    """Caller-audited public game context, outside the unchanged actor Chunk API.

    sequence is per actor across all updates; game_sequence increments per game.
    engine_tick is the actual engine tick at publication, including terminal close.
    completed is mandatory exactly when the actual producer reports terminal.
    """
    sequence: int
    game_id: str
    game_sequence: int
    engine_tick: int
    terminal: bool
    completed: L.PlayRate | None = None


@dataclass(frozen=True)
class _Context:
    """Only scalar validation results survive publication-map closure."""
    seed: int
    generated_steps: int
    boundary_declined_steps: int
    terminal: bool
    first_tick: int
    last_tick: int
    first_old_value: float
    bootstrap: float
    opponent_id: str
    terminal_reward: float


@dataclass(frozen=True)
class CoordinatorConfig:
    wait_seconds: float = 60.
    test_only: bool = False

    def __post_init__(self):
        require(type(self.test_only) is bool, 'test_only must be boolean')
        require(type(self.wait_seconds) in (float, int) and math.isfinite(self.wait_seconds)
                and self.wait_seconds > 0, 'positive finite wait bound required')


def queue_capacity(steps):
    """Conservative admission bound, including worst-case one-row game chunks.

    Actual receipt sizes are also enforced. Queue disk is reserved for a whole
    update; backpressure at the version barrier never waits for impossible space.
    """
    require(integer(steps) and steps > 0, 'positive step count required')
    row = (F.MAX_ENT*(F.E_COLS*2+1) + F.MAX_EV*(F.V_COLS*2+1)
           + F.MAX_REV*(F.R_COLS*2+1) + 6*F.T_COLS*2 + 5*F.H_COLS*2
           + F.G_COLS*4 + len(F.LAGS)*F.L_COLS*2 + 4+6 + 8+8*3+2+2)
    # Bounded runtime/scalars, 19 NPY headers, manifest entries and JSON overhead.
    return int(steps), int(steps)*(row+131072)


def close_maps(chunk):
    for a in [*chunk.features.values(), *(getattr(chunk, k) for k in
                ('action', 'old_logp', 'old_value', 'reward', 'terminated', 'actor', 'dt'))]:
        if isinstance(a, np.memmap):
            a._mmap.close()


def durable_json(path, obj):
    path = Path(path)
    temporary = path.with_name(path.name+'.tmp')
    with open(temporary, 'xb') as out:
        out.write(encoded(obj))
        out.flush()
        os.fsync(out.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class Coordinator:
    def __init__(self, learner, queue: A.AtomicChunkQueue, *, quotas: Mapping[str, int],
                 checkpoint_dir, config=CoordinatorConfig(), stop_notifier: Callable[[str], None]):
        require(isinstance(queue, A.AtomicChunkQueue), 'actual AtomicChunkQueue required')
        require(isinstance(config, CoordinatorConfig), 'coordinator config required')
        require(config.test_only == learner.config.test_only, 'production rejects test-only learner')
        require(config.test_only or (learner.config.steps_per_update, learner.config.updates)
                == (262144, 32), 'production budget must be exactly 262144 x 32')
        require(callable(stop_notifier), 'cooperative stop notifier required')
        quotas = dict(quotas)
        require(quotas and all(text(k) and integer(v) and v > 0 for k, v in quotas.items()),
                'freeze positive actor quotas')
        require(sum(quotas.values()) == learner.config.steps_per_update, 'quotas must sum to exact update')
        require(learner.version == learner.generated_steps == learner.trained_steps == 0
                and learner.halted_reason is None, 'fresh learner only; engine resume is not qualified')
        require(queue.runtime_manifest == learner.runtime_manifest
                and queue.provenance_sha256 == learner.provenance_sha256, 'queue runtime mismatch')
        require(len(encoded(learner.runtime_manifest)) <= 98304,
                'serialized runtime manifest exceeds admitted 96 KiB bound')
        chunks, size = queue_capacity(learner.config.steps_per_update)
        require(queue.max_chunks >= chunks and queue.max_bytes >= size, 'queue cap cannot hold conservative full update')
        require(not any(p.is_dir() for p in queue.root.iterdir()), 'fresh empty queue required')
        self.learner, self.queue, self.config = learner, queue, config
        self.quotas = {k: int(v) for k, v in sorted(quotas.items())}
        self.updates, self.steps = learner.config.updates, learner.config.steps_per_update
        self.budgets = {k: v*self.updates for k, v in self.quotas.items()}
        self.model_cfg = json.loads(encoded(learner.model.cfg))  # Includes drop and vocabulary sizes.
        self.runtime = dict(learner.runtime_manifest)
        self.anchor = learner.anchor_sha256
        self.provenance = learner.provenance_sha256
        self.version, self.policy = 0, learner.policy_sha256
        self.stop_notifier, self.stop_event = stop_notifier, threading.Event()
        self.condition = threading.Condition(threading.RLock())
        self.reason = None
        self.active = False
        self._inflight = set()
        self._receipts, self._names, self._contents = [], set(), set()
        self._rates, self.games = [], []
        self._previous_checkpoint = None
        self._permit_states = None
        self.actors = {k: dict(generated=0, observed=0, accepted=0, trained=0, sequence=0,
                              reported_until=0, unpublished_reported=0,
                              reported_ranges=[],
                              update_rows=0, boundary_declined=0, completed=0,
                              chain='0'*64, last=None) for k in self.quotas}
        self._game_ids = {k: set() for k in self.quotas}
        self._attempt_sequences = {k: set() for k in self.quotas}
        self.path = Path(checkpoint_dir)
        self.path.mkdir(parents=True, exist_ok=True)
        require(not any(self.path.iterdir()), 'fresh checkpoint directory required; resume denied')
        self._checkpoint([])
        self.worker = threading.Thread(target=self._run, name='outcome-ppo-coordinator', daemon=True)
        self.worker.start()

    def _live(self):
        require(self.reason is None, f'seed halted: {self.reason}')

    def _known(self, actor_id, chunk, boundary, publication):
        """Charge positive malformed/duplicate attempts before validating their contract."""
        declared = getattr(chunk, 'generated_steps', 0)
        action = getattr(chunk, 'action', None)
        n = len(action) if isinstance(action, np.ndarray) and action.ndim else 0
        cumulative = getattr(boundary, 'generated_steps', 0)
        positive = max([0, n, int(declared) if integer(declared) and declared > 0 else 0])
        if actor_id in self.actors:
            a = self.actors[actor_id]
            delta = max(0, int(cumulative)-a['observed']) if integer(cumulative) else 0
            sequence = getattr(publication, 'sequence', None)
            sequenced = integer(sequence) and 0 <= sequence < self.budgets[actor_id]
            novel = sequenced and sequence not in self._attempt_sequences[actor_id]
            covered = 0
            if novel and integer(cumulative) and cumulative >= 0:
                # A first callback may arrive AFTER shutdown already reported its
                # rows. Only those previously funded rows are exempt; a replay
                # of the same sequence is still a new positive duplicate attempt.
                lo, hi = max(0, int(cumulative)-positive), int(cumulative)
                remaining = []
                for start, end in a['reported_ranges']:
                    left, right = max(start, lo), min(end, hi)
                    if left < right:
                        covered += right-left
                        if start < left:
                            remaining.append([start, left])
                        if right < end:
                            remaining.append([right, end])
                    else:
                        remaining.append([start, end])
                a['reported_ranges'] = remaining
            a['unpublished_reported'] -= covered
            a['generated'] += max(positive, delta)-covered
            if sequenced:
                self._attempt_sequences[actor_id].add(int(sequence))
            if integer(cumulative):
                a['observed'] = max(a['observed'], int(cumulative))
        else:
            self._unknown_generated = getattr(self, '_unknown_generated', 0)+positive

    def _sync_halt(self):
        if self.reason is not None and not self.active:
            known = sum(a['generated'] for a in self.actors.values())+getattr(self, '_unknown_generated', 0)
            extra = max(0, known-self.learner.generated_steps)
            self.learner.halt(self.reason[:256], generated_steps=extra)

    def _abort(self, reason):
        if self.reason is None:
            self.reason = str(reason)[:256] or 'coordinator aborted'
            self.stop_event.set()
            # Contract: nonblocking notifier; exceptions cannot suppress stop/halt.
            try:
                self.stop_notifier(self.reason)
            except Exception:
                pass
        self._sync_halt()
        self.condition.notify_all()

    def abort(self, reason, *, generated_counts=None):
        """Stop all actors; report authoritative cumulative counts, never deltas.

        May be called again after cooperative shutdown to report pending failed
        attempts. Learner.halt receives only counts not already charged there.
        """
        with self.condition:
            try:
                if generated_counts is not None:
                    require(isinstance(generated_counts, Mapping), 'stop report must be a mapping')
                    errors = []
                    for key, count in generated_counts.items():
                        if key not in self.actors or not integer(count) or count < 0:
                            errors.append('unknown actor or invalid stop count')
                            continue
                        a = self.actors[key]
                        # Authoritative counters describe physical generation.
                        # Positive duplicate charges are additional attempts and
                        # must never be absorbed into this coverage frontier.
                        additional = max(0, int(count)-a['observed'])
                        if additional:
                            a['reported_ranges'].append([a['observed'], int(count)])
                        a['unpublished_reported'] += additional
                        a['reported_until'] = max(a['reported_until'], int(count))
                        a['generated'] += additional
                        a['observed'] = max(a['observed'], int(count))
                    require(not errors, 'invalid stop report: '+', '.join(errors))
            finally:
                # A malformed report cannot turn a requested stop into a live seed.
                self._abort(reason)

    def publish(self, actor_id, chunk, boundary: A.Boundary, publication: Publication):
        """Bind a callback actor ID independently of untrusted chunk metadata.

        Ordinary flushes return the current version. A quota flush waits on the
        condition for the sole update worker and its durable checkpoint. Final
        budget flushes return immediately; finalize must await the last update.
        """
        entered = False
        mapped = None
        try:
            with self.condition:
                self._known(actor_id, chunk, boundary, publication)
                self._live()
                require(actor_id in self.actors, 'unregistered actor')
                require(actor_id not in self._inflight, 'concurrent/duplicate actor publication')
                self._inflight.add(actor_id)
                entered = True
                require(not self.active, 'publication while learner consumes barrier')
                require(self.version < self.updates, 'generation after final budget')
                require(isinstance(boundary, A.Boundary) and isinstance(publication, Publication), 'explicit boundary/game context required')
                require(chunk.actor_id == actor_id, 'callback actor differs from chunk')
                require(self.actors[actor_id]['update_rows'] < self.quotas[actor_id], 'actor already at barrier')
                old_version, old_policy = self.version, self.policy
            # Filesystem operations must not hold the barrier lock: a stalled
            # writer, load or fsync cannot prevent another thread from aborting.
            receipt = self.queue.write(chunk)
            mapped = self.queue.load(receipt, expected_version=old_version, expected_policy_sha256=old_policy)
            _, maxbytes = queue_capacity(receipt.rows)
            require(receipt.bytes <= maxbytes, 'receipt exceeds admitted conservative bound')
            L.validate_chunk(L.Chunk(**vars(mapped)), config=self.learner.config, version=old_version,
                             anchor_sha256=self.anchor, policy_sha256=old_policy,
                             provenance_sha256=self.provenance, model_cfg=self.model_cfg)
            context = _Context(mapped.seed, mapped.generated_steps, mapped.boundary_declined_steps,
                               bool(mapped.terminated[-1]), int(mapped.features['glob'][0, F.G_TICK]),
                               int(mapped.features['glob'][-1, F.G_TICK]), float(mapped.old_value[0]),
                               float(mapped.bootstrap), mapped.opponent_id, float(mapped.reward[-1]))
            close_maps(mapped)
            mapped = None
            with self.condition:
                self._live()
                require(self.version == old_version and not self.active, 'publication crossed version barrier')
                require(receipt.name not in self._names and receipt.manifest_sha256 not in self._contents, 'duplicate queue receipt/content')
                self._validate_context(actor_id, context, boundary, publication)
                a = self.actors[actor_id]
                self._names.add(receipt.name)
                self._contents.add(receipt.manifest_sha256)
                binding = dict(actor_id=actor_id, receipt=asdict(receipt), boundary=asdict(boundary),
                               publication=asdict(publication), previous=a['chain'])
                a['chain'] = digest(binding)
                binding['sha256'] = a['chain']
                self._receipts.append(binding)
                a['accepted'] += receipt.rows
                a['update_rows'] += receipt.rows
                a['sequence'] += 1
            with self.condition:
                self.condition.notify_all()
                self._live()
                if boundary.reason != 'quota':
                    return A.PolicyUpdate(old_version, old_policy)
                deadline = time.monotonic()+self.config.wait_seconds
                while self.version == old_version and self.reason is None:
                    remaining = deadline-time.monotonic()
                    require(remaining > 0, 'quota barrier timeout')
                    self.condition.wait(remaining)
                self._live()
                return A.PolicyUpdate(self.version, self.policy,
                                      {k: v.clone() for k, v in self._permit_states.items()}, self.quotas[actor_id])
        except BaseException as exc:
            with self.condition:
                self._abort(f'{type(exc).__name__}: {exc}')
            raise
        finally:
            if mapped is not None:
                close_maps(mapped)
            if entered:
                with self.condition:
                    self._inflight.discard(actor_id)

    def _validate_context(self, key, c, b, p):
        a, n = self.actors[key], c.generated_steps
        require(c.seed == self.learner.config.seed, 'seed mismatch')
        require(all(integer(v) for v in (b.generated_steps, b.remaining_budget, b.remaining_quota,
                                         b.boundary_declined_steps, p.sequence, p.game_sequence, p.engine_tick)), 'integer context required')
        require(type(b.terminal) is bool and type(b.unfinished) is bool and type(p.terminal) is bool, 'boolean terminal context required')
        total, quota = a['accepted']+n, a['update_rows']+n
        require(a['generated'] == b.generated_steps == total <= self.budgets[key], 'generated/discard/duplicate ledger mismatch')
        require(b.remaining_budget == self.budgets[key]-total and b.remaining_quota == self.quotas[key]-quota >= 0, 'boundary quota/budget mismatch')
        require(b.boundary_declined_steps == a['boundary_declined']+c.boundary_declined_steps, 'cumulative boundary-decline mismatch')
        terminal = c.terminal
        require(b.terminal == p.terminal == terminal, 'producer terminal context mismatch')
        expected_reason = ('budget' if total == self.budgets[key] else 'quota' if quota == self.quotas[key]
                           else 'terminal' if terminal else 'chunk')
        require(b.reason == expected_reason, 'boundary reason/discard mismatch')
        require(b.unfinished == (b.reason == 'budget' and not terminal), 'unfinished budget metadata mismatch')
        require(p.sequence == a['sequence'] and text(p.game_id) and p.game_sequence >= 0, 'publication sequence/game identity mismatch')
        first, last = c.first_tick, c.last_tick
        previous = a['last']
        if previous is None or previous['terminal']:
            require(first == 90 and p.game_id not in self._game_ids[key], 'completed-game replay or missing initial polls')
            require(p.game_sequence == (0 if previous is None else previous['game_sequence']+1), 'game sequence mismatch')
            self._game_ids[key].add(p.game_id)
        else:
            require(not previous['declined'], 'poll after nonterminal boundary decline')
            require(p.game_id == previous['game_id'] and p.game_sequence == previous['game_sequence']
                    and c.opponent_id == previous['opponent_id'] and first == previous['tick']+F.POLL,
                    'cross-update game continuity/replay mismatch')
            if previous['version'] == self.version:
                require(abs(previous['bootstrap']-c.first_old_value) <= 2e-6, 'continuing bootstrap mismatch')
        require((last <= p.engine_tick < last+F.POLL) if terminal else p.engine_tick == last+F.POLL,
                'actual engine terminal/bootstrap tick mismatch')
        require((p.completed is not None) == terminal, 'completed game requires audited play-rate metadata; unfinished is not completed')
        if terminal:
            rate = p.completed
            require(isinstance(rate, L.PlayRate) and rate.game_id == p.game_id
                    and integer(rate.accepted_plays) and rate.accepted_plays >= 0
                    and type(rate.seconds) in (int, float) and math.isfinite(rate.seconds) and rate.seconds > 0,
                    'invalid completed-game metadata')
            require(15 <= 300*rate.accepted_plays/rate.seconds <= 80, 'play-rate collapse')
            self._rates.append(L.PlayRate(digest([key, p.game_id]), rate.accepted_plays, rate.seconds))
            self.games.append(dict(actor_id=key, game_id=p.game_id, game_sequence=p.game_sequence,
                                   accepted_plays=rate.accepted_plays, seconds=rate.seconds,
                                   terminal_reward=c.terminal_reward, engine_tick=p.engine_tick))
            a['completed'] += 1
        a['boundary_declined'] = b.boundary_declined_steps
        a['last'] = dict(game_id=p.game_id, game_sequence=p.game_sequence, tick=last, terminal=terminal,
                         bootstrap=float(c.bootstrap), version=self.version, declined=bool(c.boundary_declined_steps),
                         opponent_id=c.opponent_id)

    def _snapshot(self, receipts):
        actors = {k: dict(a, discarded=max(0, a['generated']-a['accepted']),
                          games_sha256=digest([g for g in self.games if g['actor_id'] == k]))
                  for k, a in self.actors.items()}
        return dict(schema=1, test_only=self.config.test_only, version=self.learner.version,
                    config=asdict(self.config), learner_config=self.learner.config.record(), quotas=self.quotas,
                    budgets=self.budgets, anchor_sha256=self.anchor, model_cfg=self.model_cfg,
                    model_cfg_sha256=digest(self.model_cfg), feature_hash=self.learner.feature_hash,
                    policy_sha256=self.learner.policy_sha256, runtime_manifest=self.runtime,
                    provenance_sha256=self.provenance, actors=actors, games=self.games,
                    receipts=receipts, previous_checkpoint_sha256=self._previous_checkpoint,
                    engine_resume_qualified=False)

    def _checkpoint(self, receipts):
        version = self.learner.version
        path = self.path/f'update-{version:02d}.pt'
        self.learner.save_checkpoint(path)
        with self.condition:
            state = json.loads(encoded(self._snapshot(receipts)))
        state['learner_checkpoint'] = dict(file=path.name, sha256=L.file_sha256(path))
        durable_json(self.path/f'update-{version:02d}.json', state)
        self._previous_checkpoint = digest(state)

    def _run(self):
        while True:
            with self.condition:
                ready = self.condition.wait_for(lambda: self.reason is not None or all(
                    a['update_rows'] == self.quotas[k] for k, a in self.actors.items()),
                    timeout=self.config.wait_seconds)
                if not ready:
                    self._abort('update collection timeout/incomplete budget')
                if self.reason is not None:
                    self._sync_halt()
                    return
                self.active = True
                receipts = list(self._receipts)
            mapped = []
            try:
                for binding in receipts:
                    mapped.append(self.queue.load(A.Receipt(**binding['receipt']), expected_version=self.version,
                                                  expected_policy_sha256=self.policy))
                require(sum(c.generated_steps for c in mapped) == self.steps, 'lost/partial exact quota')
                self.learner.update([L.Chunk(**vars(c)) for c in mapped], play_rates=list(self._rates))
                require(self.learner.version == self.version+1 and self.learner.trained_steps == (self.version+1)*self.steps,
                        'learner update counters mismatch')
                # No learner array view may outlive these maps. update has returned.
                for c in mapped:
                    close_maps(c)
                mapped.clear()
                with self.condition:
                    for key, a in self.actors.items():
                        a['trained'] += self.quotas[key]
                self._checkpoint(receipts)
                require(self.learner.halted_reason is None, self.learner.halted_reason)
                with self.condition:
                    self._live()
                for binding in receipts:
                    self.queue.acknowledge(A.Receipt(**binding['receipt']))
                states = {k: v.detach().cpu().clone() for k, v in self.learner.model.state_dict().items()}
                with self.condition:
                    self._live()
                    self._permit_states = states
                    self.version, self.policy = self.learner.version, self.learner.policy_sha256
                    for a in self.actors.values():
                        a['update_rows'] = 0
                    self._receipts.clear()
                    self._rates.clear()
                    self.active = False
                    self.condition.notify_all()
                    if self.version == self.updates:
                        return
            except BaseException as exc:
                # Exception traceback may still own views, but there is no further
                # computation on them after update raised. Never retry optimizer.
                for c in mapped:
                    close_maps(c)
                with self.condition:
                    self.active = False
                    self._abort(f'{type(exc).__name__}: {exc}')
                return

    def finalize(self):
        deadline = time.monotonic()+self.config.wait_seconds
        with self.condition:
            try:
                while self.version < self.updates and self.reason is None:
                    remaining = deadline-time.monotonic()
                    require(remaining > 0, 'finalization timeout/incomplete budget')
                    self.condition.wait(remaining)
                self._live()
                total = self.steps*self.updates
                require(all(a['generated'] == a['accepted'] == a['trained'] == self.budgets[k]
                            for k, a in self.actors.items()), 'incomplete actor final ledger')
                require(self.learner.generated_steps == self.learner.trained_steps == total, 'incomplete learner final ledger')
                require(self.games, 'play-rate gate unassessed: no completed-game metadata')
                manifest = self._snapshot([])
                manifest.update(generated=total, accepted=total, trained=total, discarded=0, updates=self.version,
                                completed_games=len(self.games), unfinished_games=sum(
                                    a['last'] is not None and not a['last']['terminal'] for a in self.actors.values()),
                                games_sha256=digest(self.games), checkpoint_sha256=self._previous_checkpoint)
                durable_json(self.path/'final-manifest.json', manifest)
                return manifest
            except BaseException as exc:
                self._abort(f'{type(exc).__name__}: {exc}')
                raise

    def join(self, timeout=None):
        """Bounded cleanup; an in-flight optimizer cannot be forcibly cancelled."""
        self.worker.join(self.config.wait_seconds if timeout is None else timeout)
        return not self.worker.is_alive()
