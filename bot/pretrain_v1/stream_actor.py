"""Bounded synchronous actor and local atomic NPY queue, with no launch entry point.

Integration contract:
* Use sim_ours.bind_matches as for the readiness player. Each instance owns one
  acting seat, continuing across games until its generated-step budget expires.
* publish(chunk, boundary) runs synchronously while the engine clock is stopped.
  It must persist/consume the chunk, release it, and return PolicyUpdate. Ordinary
  chunk/game flushes acknowledge the same version. At quota boundaries it must
  return the next version and weights before another action is sampled. This is
  a zero-lag barrier; distributed scheduling and fixed 262144-step aggregation
  belong to the coordinator. Never retain every published chunk in a callback.
* Catch BudgetComplete outside play_match. Its unfinished flag has no outcome.
  Every attempted Session step is charged immediately, including later discarded
  data. Exceptions poison this actor; never retry or top up its consumed budget.
* Nominal 3600/6000 frontend declines are counted boundary_declined NOOP
  transitions, value only, using features from copied Session history. Production
  Session sampling/history/RNG remain unchanged. Only actual engine close gives
  the boundary row a terminal reward. Another poll before real termination is
  a contract failure. Parent must register this accounting clarification.
* A nonterminal close without another public poll discards the pending row. It
  publishes earlier completed rows with that row's old value as bootstrap. A
  true game end closes the pending row with actual b.winner, even in finally.
* Chunk arrays have exactly model.collate's keys/dtypes/shapes, with leading N.
  Ragged axes are padded to this chunk's maxima, as collate does. Vector dtypes
  are action int64, logp/value/reward float64, terminated/actor bool, dt int16.
  generated_steps is per-chunk N. Actor.generated_steps also includes discarded
  rows and failed attempts, and is the authoritative consumed-budget counter.
* The queue is a local filesystem transport. Receipts pin the manifest digest,
  runtime manifest and policy version. Readers mmap immutable .npy files. Owners
  acknowledge only after consumption and must close mapped arrays first.

Not qualified for leased jobs: live-engine continuation, command queues, opponent
state and engine RNG are NOT checkpointed. There is no engine pickle guarantee.
Reclaim/recycle needs a reviewed checkpoint/replay protocol before RL launch.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
from dataclasses import dataclass, fields
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
from typing import Mapping
import uuid

import numpy as np
import torch

from . import featurize as F
from .model import collate
from .policy import Session
from .policy_trace import PolicyTrace
from .sim_ours import OursFrames, new_builder, record_from_line


class StreamError(ValueError):
    """Stop this actor/seed. The caller must not generate replacement data."""


def _require(ok, message):
    if not ok:
        raise StreamError(message)


def _integer(x):
    return isinstance(x, (int, np.integer)) and not isinstance(x, (bool, np.bool_))


def _sha(x):
    return isinstance(x, str) and re.fullmatch('[0-9a-f]{64}', x) is not None


def _json(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def manifest_sha256(manifest):
    return hashlib.sha256(_json(dict(manifest))).hexdigest()


def policy_sha256(model):
    """Same canonical identity as the learner; anchor SHA identifies its source file."""
    h = hashlib.sha256()
    h.update(manifest_sha256(dict(cfg=model.cfg, feature_hash=F.feature_hash())).encode())
    for name, tensor in sorted(model.state_dict().items()):
        a = tensor.detach().cpu().contiguous().numpy()
        h.update(json.dumps([name, str(a.dtype), list(a.shape)], separators=(',', ':')).encode())
        h.update(a.tobytes())
    return h.hexdigest()


@dataclass(frozen=True)
class Chunk:
    features: Mapping[str, np.ndarray]
    action: np.ndarray
    old_logp: np.ndarray
    old_value: np.ndarray
    reward: np.ndarray
    terminated: np.ndarray
    actor: np.ndarray
    dt: np.ndarray
    bootstrap: float
    version: int
    actor_id: str
    seed: int
    anchor_sha256: str
    policy_sha256: str
    generated_steps: int
    provenance_sha256: str
    opponent_id: str
    boundary_declined_steps: int = 0


_FEATURES = dict(ent=('int16', (None, F.E_COLS)), ent_mask=('bool', (None,)),
                 ev=('int16', (None, F.V_COLS)), ev_mask=('bool', (None,)),
                 rev=('int16', (None, F.R_COLS)), rev_mask=('bool', (None,)),
                 tow=('int16', (6, F.T_COLS)), hand=('int16', (5, F.H_COLS)),
                 glob=('int32', (F.G_COLS,)), lag=('int16', (len(F.LAGS), F.L_COLS)),
                 slot_ok=('bool', (4,)), alive=('bool', (6,)))
_VECTORS = dict(action='int64', old_logp='float64', old_value='float64', reward='float64',
                terminated='bool', actor='bool', dt='int16')
_CAPS = dict(ent=F.MAX_ENT, ev=F.MAX_EV, rev=F.MAX_REV)


def validate_chunk(c):
    _require(isinstance(c.features, Mapping) and set(c.features) == set(_FEATURES), 'feature keys mismatch')
    _require(isinstance(c.action, np.ndarray) and c.action.ndim == 1, 'action must be a CPU numpy vector')
    n = len(c.action)
    _require(0 < n <= 2000, 'chunk must contain 1..2000 rows')
    for key, (dtype, tail) in _FEATURES.items():
        a = c.features[key]
        _require(isinstance(a, np.ndarray) and a.dtype == np.dtype(dtype), f'{key} dtype mismatch')
        _require(a.ndim == len(tail)+1 and a.shape[0] == n, f'{key} shape mismatch')
        _require(all(want is None or got == want for got, want in zip(a.shape[1:], tail)), f'{key} shape mismatch')
    for key, cap in _CAPS.items():
        _require(1 <= c.features[key].shape[1] <= cap, f'{key} cap exceeded')
        _require(c.features[key+'_mask'].shape == c.features[key].shape[:2], f'{key} mask shape mismatch')
    for key, dtype in _VECTORS.items():
        a = getattr(c, key)
        _require(isinstance(a, np.ndarray) and a.dtype == np.dtype(dtype) and a.shape == (n,), f'{key} dtype/shape mismatch')
        _require(bool(np.isfinite(a).all()), f'{key} nonfinite')
    _require(bool(((0 <= c.action) & (c.action <= F.NOOP)).all()), 'invalid action')
    _require(bool((c.dt == F.POLL).all()), 'non-five-tick transition')
    _require(bool((c.old_logp <= 0).all()) and bool((np.abs(c.old_value) <= 1).all()), 'invalid likelihood/value')
    _require(bool((c.old_logp[~c.actor] == 0).all()) and bool((c.action[~c.actor] == F.NOOP).all()), 'forced row has policy action')
    _require(_integer(c.boundary_declined_steps) and c.boundary_declined_steps in (0, 1), 'invalid boundary-declined count')
    expected_actor = c.features['slot_ok'].any(axis=1).copy()
    if c.boundary_declined_steps:
        _require(int(c.features['glob'][-1, F.G_TICK]) in (3600, 6000), 'boundary-declined row outside nominal deadline')
        expected_actor[-1] = False
    _require(bool(np.array_equal(c.actor, expected_actor)), 'actor mask differs from public legal slots/boundary decline')
    _require(bool(np.isin(c.reward, [-1., 0., 1.]).all()) and bool((c.reward[~c.terminated] == 0).all()), 'nonterminal or shaped reward')
    _require(not c.terminated[:-1].any(), 'a chunk may not cross games')
    _require(np.isfinite(c.bootstrap) and abs(c.bootstrap) <= 1 and (not c.terminated[-1] or c.bootstrap == 0), 'invalid bootstrap')
    _require(_integer(c.version) and c.version >= 0 and _integer(c.seed), 'invalid version/seed')
    _require(_integer(c.generated_steps) and c.generated_steps == n, 'generated_steps must equal this chunk length')
    _require(all(_sha(getattr(c, k)) for k in ('anchor_sha256', 'policy_sha256', 'provenance_sha256')), 'invalid SHA256 pin')
    _require(all(isinstance(getattr(c, k), str) and getattr(c, k) for k in ('actor_id', 'opponent_id')), 'missing actor/opponent identity')
    return n


@dataclass(frozen=True)
class PolicyUpdate:
    version: int
    policy_sha256: str
    # Same-version acknowledgements omit weights. New versions replace the model
    # strictly in place so Session's causal history and RNG are preserved.
    state_dict: Mapping | None = None
    quota_steps: int | None = None


@dataclass(frozen=True)
class Boundary:
    reason: str                      # chunk | terminal | quota | budget | unfinished
    generated_steps: int              # cumulative consumed budget, including discarded attempts
    remaining_budget: int
    remaining_quota: int
    terminal: bool
    unfinished: bool
    boundary_declined_steps: int = 0   # cumulative explicit value-only deadline rows


class BudgetComplete(RuntimeError):
    def __init__(self, generated_steps, unfinished):
        self.generated_steps, self.unfinished = generated_steps, unfinished
        super().__init__(f'actor budget exhausted after {generated_steps} generated steps; unfinished={unfinished}')


@dataclass
class _Row:
    features: dict
    action: int
    old_logp: float
    old_value: float
    actor: bool
    reward: float = 0.
    terminated: bool = False
    boundary_declined: bool = False


class StreamingPolicyOursPlayer:
    deadline_seconds = None

    def __init__(self, model, publish, *, actor_id, seed, anchor_sha256, provenance_sha256,
                 opponent_id, budget_steps, quota_steps, chunk_rows=512, version=0,
                 expected_policy_sha256=None, name='pretrain-v1-stream'):
        _require(not model.training and next(model.parameters()).device.type == 'cpu', 'actor requires an eval-mode CPU model')
        _require(all(_integer(x) and x > 0 for x in (budget_steps, quota_steps, chunk_rows)), 'invalid actor budget/chunk bound')
        _require(chunk_rows <= 2000 and _integer(version) and version >= 0 and _integer(seed), 'invalid version/seed/chunk bound')
        _require(_sha(anchor_sha256) and _sha(provenance_sha256), 'invalid anchor/runtime pin')
        _require(isinstance(actor_id, str) and actor_id and isinstance(opponent_id, str) and opponent_id, 'actor/opponent required')
        self.model = PolicyTrace(model)
        self.policy_sha256 = policy_sha256(model)
        _require(expected_policy_sha256 is None or expected_policy_sha256 == self.policy_sha256, 'policy digest mismatch')
        self.publish, self.name = publish, name
        self.actor_id, self.seed = actor_id, int(seed)
        self.anchor_sha256, self.provenance_sha256 = anchor_sha256, provenance_sha256
        self.opponent_id, self.version = opponent_id, int(version)
        self.budget_steps, self.remaining_quota = int(budget_steps), int(quota_steps)
        self.chunk_rows = int(chunk_rows)
        self.generated_steps = self.published_steps = self.discarded_steps = 0
        self.completed_games = self.unfinished_games = self.boundary_declined_steps = 0
        self.counts = {}
        self.battle = self.session = self.frames = None
        self.shadow_builder = self.shadow_hist = None
        self.pending = None
        self.rows = []
        self.failed = self.exhausted = False

    def bind_ours(self, battle):
        _require(self.battle is None and self.session is None, 'previous battle still active')
        _require(not self.failed and not self.exhausted, 'actor stopped')
        self.battle = battle

    def start(self, ctx):
        _require(self.battle is not None and self.session is None, 'actor not bound or already started')
        _require(ctx.command_delay == 27, 'unregistered command delay')
        self.seat = int(ctx.seat)
        self.last_public_tick = self.boundary_declined_tick = None
        self.frames = OursFrames(self.battle, self.seat, ctx.own_order, ctx.seed)
        session_seed = (int(ctx.seed) ^ (0x9E3779B97F4A7C15*(ctx.seat+1))) % (1 << 63)
        self.session = Session(self.model, session_seed)
        self.shadow_builder, self.shadow_hist = new_builder(ctx.own_order), F.History()

    @torch.inference_mode()
    def _lookahead(self, record, extras):
        # No gate/tile decode and no sampling. The actual Session has not seen
        # this poll; it must observe it once, after any synchronous weight update.
        feat = F.observe(record, extras, copy.deepcopy(self.session.hist))
        cls, _ = self.model.original.trunk(collate([feat]))
        p = torch.softmax(self.model.original.value(cls)[0], -1)
        value = float(p[2]-p[0])
        _require(np.isfinite(value), 'nonfinite bootstrap')
        return feat, value

    def _bootstrap(self, record, extras):
        return self._lookahead(record, extras)[1]

    def _chunk(self, bootstrap):
        rows = self.rows
        c = Chunk(features={k: t.numpy() for k, t in collate([r.features for r in rows]).items()},
                  action=np.array([r.action for r in rows], np.int64),
                  old_logp=np.array([r.old_logp for r in rows], np.float64),
                  old_value=np.array([r.old_value for r in rows], np.float64),
                  reward=np.array([r.reward for r in rows], np.float64),
                  terminated=np.array([r.terminated for r in rows], bool),
                  actor=np.array([r.actor for r in rows], bool), dt=np.full(len(rows), F.POLL, np.int16),
                  bootstrap=bootstrap, version=self.version, actor_id=self.actor_id, seed=self.seed,
                  anchor_sha256=self.anchor_sha256, policy_sha256=self.policy_sha256,
                  generated_steps=len(rows), provenance_sha256=self.provenance_sha256, opponent_id=self.opponent_id,
                  boundary_declined_steps=sum(r.boundary_declined for r in rows))
        validate_chunk(c)
        for a in [*c.features.values(), *(getattr(c, k) for k in _VECTORS)]:
            a.flags.writeable = False
        return c

    def _flush(self, bootstrap, reason, *, terminal=False, unfinished=False):
        if not self.rows:
            return
        c = self._chunk(bootstrap)
        # Detach and release the completed raw feature buffer before callback.
        self.rows.clear()
        boundary = Boundary(reason, self.generated_steps, self.budget_steps-self.generated_steps,
                            self.remaining_quota, terminal, unfinished, self.boundary_declined_steps)
        update = self.publish(c, boundary)
        self.published_steps += c.generated_steps
        del c
        if reason in ('budget', 'unfinished'):
            return
        _require(isinstance(update, PolicyUpdate), 'publication needs an explicit version acknowledgement')
        _require(_integer(update.version) and _sha(update.policy_sha256), 'invalid policy acknowledgement')
        if reason == 'quota':
            _require(update.version == self.version+1 and update.state_dict is not None,
                     'quota barrier requires next-version weights')
            _require(_integer(update.quota_steps) and update.quota_steps > 0, 'new quota required at version barrier')
            _require(not self.model.original.training, 'policy must stay in evaluation mode')
            self.model.original.load_state_dict(update.state_dict, strict=True)
            digest = policy_sha256(self.model.original)
            _require(digest == update.policy_sha256, 'updated policy digest mismatch')
            self.version, self.policy_sha256 = int(update.version), digest
            self.remaining_quota = int(update.quota_steps)
        else:
            _require(update.version == self.version and update.policy_sha256 == self.policy_sha256
                     and update.state_dict is None and update.quota_steps is None,
                     'weights/quotas may change only at the zero-lag quota barrier')
        _require(not self.model.original.training and policy_sha256(self.model.original) == self.policy_sha256,
                 'callback mutated policy outside its acknowledged update')

    def _reason(self, terminal=False):
        if self.generated_steps == self.budget_steps:
            return 'budget'
        if self.remaining_quota == 0:
            return 'quota'
        if terminal:
            return 'terminal'
        if len(self.rows) == self.chunk_rows:
            return 'chunk'
        return None

    def act(self, view):
        from bot.players.base import Decision, WAIT
        _require(not self.failed and not self.exhausted and self.session is not None, 'actor stopped/not started')
        try:
            _require(not self.battle.game_over, 'terminal battle must close before another poll')
            _require(self.boundary_declined_tick is None,
                     'boundary-declined poll must reach actual terminal before another five-tick poll')
            (record, extras), line = self.frames.record()
            tick = record['tick']
            expected = 90 if self.last_public_tick is None else self.last_public_tick+F.POLL
            _require(tick == expected and view.tick == tick and view.seat == self.seat, 'poll must start at 90 then advance by five ticks')
            self.last_public_tick = tick
            declined = self.frames.builder.decided(tick)
            _require(not declined or tick in (3600, 6000), 'public decline outside nominal terminal deadline')
            if self.pending is not None:
                self.rows.append(self.pending)
                self.pending = None
                reason = self._reason()
                if reason is not None:
                    self._flush(self._bootstrap(record, extras), reason, unfinished=reason == 'budget')
                    if reason == 'budget':
                        self.exhausted = True
                        raise BudgetComplete(self.generated_steps, True)
            _require(self.generated_steps < self.budget_steps and self.remaining_quota > 0, 'no action permitted beyond quota/budget')
            self.model.clear()
            # Charge before inference. A failing call is consumed, never retried.
            self.generated_steps += 1
            self.remaining_quota -= 1
            if declined:
                # Preserve the R26 WAIT and untouched production Session. Only
                # critic/accounting state advances, on copied causal history.
                feat, value = self._lookahead(record, extras)
                shadow, why = record_from_line(line, self.shadow_builder)
                _require(shadow is not None, f'shadow record refused: {why}')
                shadow_feat = F.observe(shadow[0], shadow[1], copy.deepcopy(self.shadow_hist))
                _require(F.feature_bytes(feat) == F.feature_bytes(shadow_feat), 'boundary logged record replay differs from critic features')
                self.pending = _Row(feat, F.NOOP, 0., value, False, boundary_declined=True)
                self.boundary_declined_tick = tick
                self.boundary_declined_steps += 1
                self.counts['boundary_declined'] = self.counts.get('boundary_declined', 0)+1
                return Decision(WAIT, 0, dict(status='boundary_declined', value=value, p_wait=1., p_wait5=1., logp=0.))
            decision = self.session.step(record, extras)
            logp = self.model.log_probability(decision)
            _require(np.isfinite(decision.value), 'nonfinite actor value')
            shadow, why = record_from_line(line, self.shadow_builder)
            _require(shadow is not None, f'shadow record refused: {why}')
            feat = F.observe(shadow[0], shadow[1], self.shadow_hist)
            _require(F.feature_bytes(feat) == F.feature_bytes(self.session.last_feat), 'logged record replay differs from actor features')
            if decision.status == 'play':
                _require(view.can_act, 'engine channel and public record channel disagree')
                self.session.accepted(decision)
                self.shadow_hist.submit(decision.tick, decision.slot, decision.card, decision.tile)
            self.pending = _Row(self.session.last_feat, int(decision.action), logp, decision.value,
                                decision.status != 'forced')
            self.counts[decision.status] = self.counts.get(decision.status, 0)+1
            return Decision(int(decision.action), 0, dict(status=decision.status, value=decision.value,
                                                       p_wait=decision.p_wait, p_wait5=decision.p_wait5, logp=logp))
        except BudgetComplete:
            raise
        except BaseException:
            self.failed = True
            raise

    def close(self):
        if self.session is None:
            return
        try:
            if self.failed:
                self.discarded_steps = self.generated_steps-self.published_steps
                return
            if self.battle.game_over:
                winner = self.battle.winner
                _require(winner is None or (type(winner) is int and winner in (0, 1)), 'invalid true terminal winner')
                if self.pending is not None:
                    self.pending.reward = 0. if winner is None else (1. if winner == self.seat else -1.)
                    self.pending.terminated = True
                    self.rows.append(self.pending)
                    self.pending = None
                self.completed_games += 1
                reason = self._reason(terminal=True)
                self._flush(0., reason, terminal=True)
                if reason == 'budget':
                    self.exhausted = True
            else:
                self.unfinished_games += 1
                if self.pending is not None:
                    # There was no next public poll. Do not invent its reward or
                    # mark the last generated action complete.
                    bootstrap = self.pending.old_value
                    self.discarded_steps += 1
                    self.failed = True  # No continuation/top-up after an uncompleted transition.
                    self.pending = None
                    self._flush(bootstrap, 'unfinished', unfinished=True)
                _require(not self.rows, 'unfinished rows lack an observed next state')
        except BaseException:
            self.failed = True
            raise
        finally:
            self.rows.clear()
            self.pending = None
            self.model.clear()
            self.session = self.frames = self.battle = None
            self.shadow_builder = self.shadow_hist = None


@dataclass(frozen=True)
class Receipt:
    name: str
    manifest_sha256: str
    bytes: int
    rows: int
    version: int
    generated_steps: int


class QueueFull(StreamError):
    pass


def _file_sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as src:
        for block in iter(lambda: src.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def _fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _npy_parts(a):
    a = np.ascontiguousarray(a)
    buf = io.BytesIO()
    np.lib.format.write_array_header_1_0(buf, dict(descr=np.lib.format.dtype_to_descr(a.dtype),
                                                  fortran_order=False, shape=a.shape))
    return buf.getvalue(), memoryview(a).cast('B')


class AtomicChunkQueue:
    """Local multi-writer queue, capped by actual bytes and shard count.

    Writers hold flock through preflight/write/rename. Abandoned .partial dirs
    consume capacity and are invisible to readers; reclaim only with an external
    ownership protocol. This component never reclaims a live writer's files.
    Runtime manifest must pin assembler, native, gamedata and actor source; its
    exact admission/schema is the coordinator's responsibility.
    """
    def __init__(self, root, *, max_bytes, max_chunks, runtime_manifest):
        _require(_integer(max_bytes) and max_bytes > 0 and _integer(max_chunks) and max_chunks > 0,
                 'queue caps must be positive integers')
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_bytes, self.max_chunks = int(max_bytes), int(max_chunks)
        # Canonical copy isolates caller mutation; no credentials in manifests.
        self.runtime_manifest = json.loads(_json(dict(runtime_manifest)))
        self.provenance_sha256 = manifest_sha256(self.runtime_manifest)

    @contextmanager
    def _lock(self):
        with open(self.root/'.writer.lock', 'a+b') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _usage(self):
        dirs = [p for p in self.root.iterdir() if p.is_dir()]
        return len(dirs), sum(p.stat().st_size for d in dirs for p in d.rglob('*') if p.is_file())

    def write(self, c):
        n = validate_chunk(c)
        _require(c.provenance_sha256 == self.provenance_sha256, 'chunk runtime manifest mismatch')
        # Freeze the bounded input so a caller cannot change bytes between digest
        # calculation and publication. No object or compressed pickle payloads.
        arrays = {f'f_{k}': np.array(v, copy=True, order='C') for k, v in c.features.items()}
        arrays.update({k: np.array(getattr(c, k), copy=True, order='C') for k in _VECTORS})
        entries, parts = {}, {}
        for key, a in arrays.items():
            header, raw = _npy_parts(a)
            digest = hashlib.sha256(header)
            digest.update(raw)
            entries[key] = dict(file=key+'.npy', dtype=str(a.dtype), shape=list(a.shape),
                                bytes=len(header)+len(raw), sha256=digest.hexdigest())
            parts[key] = header, raw
        scalars = {f.name: getattr(c, f.name) for f in fields(c) if f.name != 'features' and f.name not in _VECTORS}
        manifest = dict(schema=1, chunk=scalars, runtime_manifest=self.runtime_manifest, arrays=entries)
        encoded = _json(manifest)
        total = len(encoded)+sum(e['bytes'] for e in entries.values())
        name = 'chunk-'+uuid.uuid4().hex
        receipt = Receipt(name, hashlib.sha256(encoded).hexdigest(), total, n, c.version, c.generated_steps)
        with self._lock():
            count, used = self._usage()
            if count >= self.max_chunks or used+total > self.max_bytes:
                raise QueueFull('queue capacity exhausted; no replacement transitions may be generated')
            stage = self.root/('.partial-'+uuid.uuid4().hex)
            stage.mkdir()
            try:
                for key, (header, raw) in parts.items():
                    with open(stage/entries[key]['file'], 'xb') as out:
                        out.write(header)
                        out.write(raw)
                        out.flush()
                        os.fsync(out.fileno())
                with open(stage/'manifest.json', 'xb') as out:
                    out.write(encoded)
                    out.flush()
                    os.fsync(out.fileno())
                _fsync_dir(stage)
                os.rename(stage, self.root/name)
                _fsync_dir(self.root)
            except BaseException:
                shutil.rmtree(stage, ignore_errors=True)
                raise
        return receipt

    def load(self, receipt, *, expected_version, expected_policy_sha256=None):
        _require(re.fullmatch('chunk-[0-9a-f]{32}', receipt.name) is not None, 'invalid receipt path')
        path = self.root/receipt.name
        encoded = (path/'manifest.json').read_bytes()
        _require(hashlib.sha256(encoded).hexdigest() == receipt.manifest_sha256, 'manifest digest mismatch')
        m = json.loads(encoded)
        _require(m['schema'] == 1 and m['runtime_manifest'] == self.runtime_manifest, 'manifest schema/runtime mismatch')
        meta = m['chunk']
        _require(meta['version'] == expected_version == receipt.version, 'manifest policy version mismatch')
        _require(meta['provenance_sha256'] == self.provenance_sha256, 'manifest provenance mismatch')
        _require(expected_policy_sha256 is None or meta['policy_sha256'] == expected_policy_sha256, 'manifest policy digest mismatch')
        _require(set(m['arrays']) == {*(f'f_{k}' for k in _FEATURES), *_VECTORS}, 'manifest arrays mismatch')
        arrays, total = {}, len(encoded)
        for key, e in m['arrays'].items():
            _require(e['file'] == key+'.npy', 'manifest array path mismatch')
            p = path/e['file']
            _require(p.stat().st_size == e['bytes'] and _file_sha(p) == e['sha256'], 'array size/digest mismatch')
            a = np.load(p, mmap_mode='r', allow_pickle=False)
            _require(list(a.shape) == e['shape'] and str(a.dtype) == e['dtype'], 'array header mismatch')
            arrays[key] = a
            total += e['bytes']
        _require(total == receipt.bytes <= self.max_bytes, 'receipt byte count mismatch')
        c = Chunk(features={k: arrays['f_'+k] for k in _FEATURES},
                  **{k: arrays[k] for k in _VECTORS}, **meta)
        n = validate_chunk(c)
        _require(n == receipt.rows and c.generated_steps == receipt.generated_steps, 'receipt row count mismatch')
        return c

    def acknowledge(self, receipt):
        # Validation precedes deletion. The consumer must release its mmaps first.
        with self._lock():
            c = self.load(receipt, expected_version=receipt.version)
            del c
            shutil.rmtree(self.root/receipt.name)
            _fsync_dir(self.root)
