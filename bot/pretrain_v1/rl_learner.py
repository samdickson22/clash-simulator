"""Bounded, synchronous outcome-PPO component. No actors, queue, launch CLI or signals.

The host owns chunk publication and lifetime. See RL-LEARNER-CONTRACT.md before
integrating; input mappings, including read-only memmaps, are never written.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import tempfile
from typing import Mapping, Sequence

import numpy as np
import torch

from . import featurize as F
from . import rl_math
from .model import NEG, PolicyV1, tiles_ok_np

SEEDS = (2026102101, 2026102102, 2026102103)
NATIVE_SHA256 = '358cf506031bde59519fbb7ec59f07d3823112311b8d3192dbebd7a8871ef144'
GAMEDATA_SHA256 = 'ccd2a5f18f49e23ad316d8ffecd32278fe9994fcdc74936c7410223b2faef756'


class ContractError(ValueError):
    """The seed must stop; the host must not retry with replacement data."""


def _require(condition, message):
    if not condition:
        raise ContractError(message)


def _sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def _integer(value):
    return isinstance(value, (int, np.integer)) and not isinstance(value, (bool, np.bool_))


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def manifest_sha256(manifest):
    return hashlib.sha256(json.dumps(dict(manifest), sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def policy_sha256(model, feature_hash):
    """Canonical model-state identity, distinct from the selected anchor's file SHA."""
    h = hashlib.sha256()
    h.update(manifest_sha256(dict(cfg=model.cfg, feature_hash=feature_hash)).encode())
    for name, tensor in sorted(model.state_dict().items()):
        a = tensor.detach().cpu().contiguous().numpy()
        h.update(json.dumps([name, str(a.dtype), list(a.shape)], separators=(',', ':')).encode())
        h.update(a.tobytes())
    return h.hexdigest()


@dataclass(frozen=True)
class LearnerConfig:
    seed: int
    size: str
    microbatch: int = 128
    steps_per_update: int = 262144
    updates: int = 32
    batch_size: int = 2048
    test_only: bool = False
    precision: str = 'float32'

    def __post_init__(self):
        _require(_integer(self.seed) and self.seed in SEEDS, 'unregistered seed')
        _require(self.size in ('S100', 'M'), 'only S100 and M are registered')
        _require(type(self.test_only) is bool, 'test_only must be boolean')
        _require(self.precision in ('float32', 'float64'), 'unsupported precision')
        _require(self.precision == 'float32' or self.test_only, 'float64 is qualification-only; test_only required')
        _require(all(_integer(n) and n > 0 for n in
                     (self.microbatch, self.steps_per_update, self.updates, self.batch_size)), 'invalid batch/budget')
        _require(self.steps_per_update % self.batch_size == 0 and self.batch_size % self.microbatch == 0,
                 'budget/batch/microbatch must divide exactly')
        if not self.test_only:
            _require((self.steps_per_update, self.updates, self.batch_size) == (262144, 32, 2048),
                     'registered budget is exactly 262144 x 32, effective batch 2048')
            _require(self.microbatch in (128, 256), 'registered microbatch must be 128 or 256')

    def record(self):
        fields = asdict(self)
        fields.pop('precision')  # Preserve the existing FP32 config/checkpoint record.
        return dict(fields, gamma=1., gae_lambda=.95, epochs=2, warmup_updates=3,
                    learning_rate=1e-5, weight_decay=0., clip=.2, value_coefficient=.5,
                    entropy_coefficient=.001, kl_coefficient=.05, gradient_clip=1.,
                    accumulation_steps=self.batch_size//self.microbatch,
                    optimizer_steps_per_update=2*self.steps_per_update//self.batch_size,
                    policy_lag=0, logp_atol=2e-6, dtype=self.precision, model_mode='eval')


@dataclass(frozen=True)
class Chunk:
    features: Mapping[str, np.ndarray | torch.Tensor]
    action: np.ndarray | torch.Tensor
    old_logp: np.ndarray | torch.Tensor
    old_value: np.ndarray | torch.Tensor
    reward: np.ndarray | torch.Tensor
    terminated: np.ndarray | torch.Tensor
    actor: np.ndarray | torch.Tensor
    dt: np.ndarray | torch.Tensor
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


@dataclass(frozen=True)
class PlayRate:
    """One parent-audited completed game. Duration is simulated game time, not CPU/wall time."""
    game_id: str
    accepted_plays: int
    seconds: float


# Exact collate dtypes. Ragged axes are checked separately before allocating anything.
_FEATURES = dict(ent=(np.dtype('int16'), (None, F.E_COLS)), ent_mask=(np.dtype('bool'), (None,)),
                 ev=(np.dtype('int16'), (None, F.V_COLS)), ev_mask=(np.dtype('bool'), (None,)),
                 rev=(np.dtype('int16'), (None, F.R_COLS)), rev_mask=(np.dtype('bool'), (None,)),
                 tow=(np.dtype('int16'), (6, F.T_COLS)), hand=(np.dtype('int16'), (5, F.H_COLS)),
                 glob=(np.dtype('int32'), (F.G_COLS,)), lag=(np.dtype('int16'), (len(F.LAGS), F.L_COLS)),
                 slot_ok=(np.dtype('bool'), (4,)), alive=(np.dtype('bool'), (6,)))
_CAPS = dict(ent=F.MAX_ENT, ev=F.MAX_EV, rev=F.MAX_REV)


def _array(value):
    if isinstance(value, torch.Tensor):
        _require(value.device.type == 'cpu' and not value.requires_grad and value.layout == torch.strided,
                 'chunk tensors must be detached, dense CPU tensors')
        try:
            return value.detach().numpy()
        except (TypeError, RuntimeError) as exc:
            raise ContractError('unsupported tensor dtype') from exc
    _require(isinstance(value, np.ndarray), 'chunk fields must be numpy arrays or CPU tensors')
    _require(value.dtype.kind in 'biuf', 'object/string/complex arrays are forbidden')
    return value


def _finite(*values):
    for value in values:
        _require(bool(torch.isfinite(value).all()), 'nonfinite tensor')


def _vector(value, n, kind, label):
    a = _array(value)
    _require(a.shape == (n,), f'{label}: expected vector of length N')
    if kind == 'float':
        _require(a.dtype in (np.dtype('float32'), np.dtype('float64')), f'{label}: float32/64 required')
        _require(bool(np.isfinite(a).all()), f'{label}: nonfinite')
    elif kind == 'int':
        _require(a.dtype in (np.dtype('int16'), np.dtype('int32'), np.dtype('int64')), f'{label}: signed integer required')
    else:
        _require(a.dtype == np.dtype('bool'), f'{label}: bool required')
    return a


def _text(value):
    return isinstance(value, str) and 0 < len(value) <= 256


def validate_chunk(c, *, config: LearnerConfig, version: int, anchor_sha256: str,
                   policy_sha256: str, provenance_sha256: str, model_cfg: Mapping):
    """Validate one chronological chunk without mutation or GPU work.

    Return feature/vector numpy views for the learner. The caller must retain the
    source arrays and must not write them until the update returns. This validates
    structure and legality, not network old-logp parity or a whole-update budget.
    """
    _require(isinstance(c, Chunk), 'Chunk required')
    _require(_integer(c.generated_steps) and 0 < c.generated_steps <= config.steps_per_update,
             'generated_steps out of bounds')
    n = c.generated_steps
    _require(_integer(c.version) and c.version == version, 'version mismatch: exact zero lag required')
    _require(_integer(c.seed) and c.seed == config.seed, 'chunk seed mismatch')
    _require(c.anchor_sha256 == anchor_sha256 and c.policy_sha256 == policy_sha256,
             'chunk anchor/policy hash mismatch')
    _require(c.provenance_sha256 == provenance_sha256, 'chunk runtime/source provenance mismatch')
    _require(_text(c.actor_id) and _text(c.opponent_id), 'bounded actor/opponent identifiers required')
    _require(isinstance(c.features, Mapping) and set(c.features) == set(_FEATURES), 'collate feature keys mismatch')
    b = {}
    for key, (dtype, shape) in _FEATURES.items():
        a = _array(c.features[key])
        _require(a.dtype == dtype and a.ndim == len(shape)+1 and a.shape[0] == n,
                 f'{key}: collate dtype/shape mismatch')
        _require(all(want is None or got == want for got, want in zip(a.shape[1:], shape)),
                 f'{key}: collate shape mismatch')
        b[key] = a
    for key, cap in _CAPS.items():
        mask = b[key+'_mask']
        _require(1 <= b[key].shape[1] <= cap and mask.shape == b[key].shape[:2], f'{key}: ragged bound/mask mismatch')
        _require(not bool((mask[:, 1:] & ~mask[:, :-1]).any()), f'{key}: non-prefix collate mask')
    for key, col in (('ent', F.E_CARD), ('ev', F.V_CARD), ('rev', F.R_CARD), ('hand', F.H_CARD), ('glob', F.G_PEND_CARD)):
        ids = b[key][..., col]
        _require(bool(((ids >= 0) & (ids < model_cfg['n_cards'])).all()), f'{key}: card index out of bounds')
    ids = b['ent'][..., F.E_BODY]
    _require(bool(((ids >= 0) & (ids < model_cfg['n_bodies'])).all()), 'body index out of bounds')
    for key, col in (('ev', F.V_PRESENT), ('rev', F.R_PRESENT)):
        _require(np.array_equal(b[key][..., col], b[key+'_mask']), f'{key}: presence/mask mismatch')
    hand, glob = b['hand'], b['glob']
    _require(bool(((hand[..., F.H_PLACE] >= 0) & (hand[..., F.H_PLACE] <= 4)).all()), 'invalid placement code')
    _require(bool(np.isin(glob[:, F.G_BUSY], [0, 1]).all()), 'invalid busy flag')
    _require(bool(np.isin(hand[..., F.H_AFFORD], [0, 1]).all()), 'invalid affordability flag')
    # The channel and legal-slot flags are part of the observed public feature contract.
    expected = ((hand[:, :4, F.H_CARD] >= 2) & (hand[:, :4, F.H_PLACE] != 0)
                & (hand[:, :4, F.H_AFFORD] == 1) & (glob[:, F.G_BUSY, None] == 0))
    _require(np.array_equal(b['slot_ok'], expected) and np.array_equal(hand[:, :4, F.H_LEGAL], expected),
             'slot legality/busy mask mismatch')
    action = _vector(c.action, n, 'int', 'action')
    dt = _vector(c.dt, n, 'int', 'dt')
    actor = _vector(c.actor, n, 'bool', 'actor')
    terminal = _vector(c.terminated, n, 'bool', 'terminated')
    reward = _vector(c.reward, n, 'float', 'reward')
    old_logp = _vector(c.old_logp, n, 'float', 'old_logp')
    old_value = _vector(c.old_value, n, 'float', 'old_value')
    _require(bool((dt == F.POLL).all()), 'cadence must be five ticks')
    ticks = glob[:, F.G_TICK].astype(np.int64)
    _require(bool(((ticks >= 90) & ((ticks-90) % F.POLL == 0)).all()), 'polls must use five-tick grid from 90')
    _require(bool(((ticks[1:]-ticks[:-1] == F.POLL) | terminal[:-1]).all()), 'chunk is not chronological')
    gaps = glob[:, F.G_GAP]
    _require(int(gaps[0]) == (-1 if ticks[0] == 90 else F.POLL)
             and bool((gaps[1:] == np.where(terminal[:-1], -1, F.POLL)).all()),
             'observed gap violates cadence')
    _require(bool((ticks[1:][terminal[:-1]] == 90).all()), 'terminal reset must restart at tick 90')
    _require(_integer(c.boundary_declined_steps) and c.boundary_declined_steps in (0, 1),
             'boundary_declined_steps must be 0 or 1')
    declined = np.zeros(n, dtype=bool)
    if c.boundary_declined_steps:
        _require(ticks[-1] in (3600, 6000), 'boundary-declined row must end at tick 3600 or 6000')
        declined[-1] = True
    _require(np.array_equal(actor, b['slot_ok'].any(1) & ~declined),
             'actor eligibility must include every eligible poll except the declared boundary row')
    _require(bool(((action >= 0) & (action <= F.NOOP)).all()), 'action out of bounds')
    _require(bool((action[~actor] == F.NOOP).all()) and bool((old_logp[~actor] == 0).all()),
             'forced/busy poll must be certain NOOP')
    _require(bool((old_logp <= 0).all()), 'positive old_logp')
    _require(bool(((reward == 0) | terminal).all()) and bool(np.isin(reward, [-1., 0., 1.]).all()),
             'reward must be terminal-only -1/0/+1')
    _require(bool((np.abs(old_value) <= 1).all()), 'WDL value outside [-1,1]')
    _require(isinstance(c.bootstrap, (float, int, np.floating)) and not isinstance(c.bootstrap, bool)
             and math.isfinite(c.bootstrap) and abs(c.bootstrap) <= 1, 'invalid WDL bootstrap')
    _require(not terminal[-1] or c.bootstrap == 0., 'real terminal tail requires zero bootstrap')
    # Tile geometry is checked in bounded slices, never an update-sized 4x576 allocation.
    for start in range(0, n, config.microbatch):
        end = min(n, start+config.microbatch)
        legal = tiles_ok_np(hand[start:end], b['slot_ok'][start:end], b['alive'][start:end])
        _require(np.array_equal(legal.any(-1), b['slot_ok'][start:end]), 'slot has no legal tiles')
        a = action[start:end]
        play = a != F.NOOP
        slots, tiles = a[play]//F.NTILE, a[play] % F.NTILE
        _require(bool(legal[np.flatnonzero(play), slots, tiles].all()), 'illegal sampled slot/tile')
    return b, dict(action=action, dt=dt, actor=actor, terminated=terminal, reward=reward,
                   old_logp=old_logp, old_value=old_value, boundary_declined=declined)


def prepare_targets(chunks):
    """CPU float64 GAE per validated chunk, then one eligible-row normalization over the update."""
    advantages, returns, actors = [], [], []
    for c in chunks:
        a, r = rl_math.gae(torch.tensor(_array(c.reward), dtype=torch.float64),
                           torch.tensor(_array(c.old_value), dtype=torch.float64),
                           torch.tensor(_array(c.terminated)), c.bootstrap)
        _finite(a, r)
        advantages.append(a)
        returns.append(r)
        actors.append(torch.tensor(_array(c.actor)))
    advantage = rl_math.normalize_advantages(torch.cat(advantages), torch.cat(actors))
    returns = torch.cat(returns)
    _finite(advantage, returns)
    return advantage.numpy(), returns.numpy()


class Learner:
    def __init__(self, anchor_path, *, anchor_sha256, model_cfg, runtime_manifest,
                 config: LearnerConfig, device='cpu'):
        self.config = config
        _require(isinstance(config, LearnerConfig), 'LearnerConfig required')
        path = Path(anchor_path)
        _require(path.name == 'anchor.pt', 'only selected anchor.pt is admitted')
        _require(_sha(anchor_sha256) and file_sha256(path) == anchor_sha256, 'selected anchor file hash mismatch')
        selection = json.loads(path.with_name('selection.json').read_text())
        _require(selection.get('admitted') is True and selection.get('smoke') is False
                 and selection.get('file') == 'anchor.pt' and selection.get('sha256') == anchor_sha256,
                 'missing admitted selection receipt or wrong anchor hash')
        self.anchor_sha256 = anchor_sha256
        self.selection = copy.deepcopy(selection)
        self.feature_hash = F.feature_hash()
        ck = torch.load(path, map_location='cpu', weights_only=False)
        _require(ck.get('feature_hash') == self.feature_hash, 'anchor feature hash mismatch')
        _require(ck.get('cfg') == dict(model_cfg), 'anchor model configuration mismatch')
        _require(ck.get('admission', {}).get('eligible') is True, 'anchor has no eligible admission')
        self.model = PolicyV1(**model_cfg)
        _require(self.model.cfg == dict(model_cfg), 'incomplete model configuration')
        expected_state = self.model.state_dict()
        _require(set(ck['model']) == set(expected_state) and all(
                 isinstance(ck['model'][k], torch.Tensor) and ck['model'][k].dtype == t.dtype
                 and ck['model'][k].shape == t.shape for k, t in expected_state.items()),
                 'anchor state keys/dtypes/shapes mismatch')
        self.model.load_state_dict(ck['model'], strict=True)
        _require(all(p.dtype == torch.float32 for p in self.model.parameters()), 'float32 model required')
        _require(float(self.model.gate_bias) == ck.get('gate_bias'), 'anchor gate bias mismatch')
        for t in self.model.state_dict().values():
            _finite(t)
        self.runtime_manifest = dict(runtime_manifest)
        _require(0 < len(self.runtime_manifest) <= 128 and all(_text(k) and _text(v)
                 for k, v in self.runtime_manifest.items()), 'invalid bounded runtime manifest')
        _require(self.runtime_manifest.get('native_sha256') == NATIVE_SHA256
                 and self.runtime_manifest.get('gamedata_sha256') == GAMEDATA_SHA256
                 and _sha(self.runtime_manifest.get('actor_source_sha256')), 'runtime/source pins missing or wrong')
        self.provenance_sha256 = manifest_sha256(self.runtime_manifest)
        self.device = torch.device(device)
        if config.precision == 'float64':
            # Explicit test-only conversion of the verified FP32 source anchor.
            # Convert before freezing the human anchor or constructing AdamW.
            self.model.double()
        self.model.to(self.device).eval()
        self.anchor = copy.deepcopy(self.model).eval().requires_grad_(False)
        self._anchor_state_sha256 = policy_sha256(self.anchor, self.feature_hash)
        self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=1e-5, weight_decay=0.)
        # Local shuffling RNG does not change the caller's RNG state.
        self.shuffle_rng = np.random.default_rng(config.seed)
        self.update_index = self.generated_steps = self.trained_steps = self.optimizer_steps = 0
        self.high_kl_streak = 0
        self.halted_reason = None
        self.last_metrics = None
        self.policy_sha256 = policy_sha256(self.model, self.feature_hash)
        self._set_trainable()

    @property
    def version(self):
        return self.update_index

    def _set_trainable(self):
        warmup = self.update_index < 3
        for name, parameter in self.model.named_parameters():
            parameter.requires_grad_(not warmup or name.startswith('value.'))
        self.model.eval()
        self.anchor.eval().requires_grad_(False)

    def _batch(self, arrays, offsets, indices):
        """Copy only this microbatch from host-owned arrays; pad ragged axes locally."""
        group = np.searchsorted(offsets[1:], indices, side='right')
        pieces = [(k, np.flatnonzero(group == k), indices[group == k]-offsets[k]) for k in np.unique(group)]
        result = {}
        for key, (dtype, _) in _FEATURES.items():
            shape = list(arrays[pieces[0][0]][key].shape[1:])
            base = key.removesuffix('_mask')
            if base in _CAPS:
                shape[0] = max(arrays[k][key].shape[1] for k, _, _ in pieces)
            out = np.zeros((len(indices), *shape), dtype=dtype)
            for k, rows, local in pieces:
                source = arrays[k][key]
                if base in _CAPS:
                    out[rows, :source.shape[1]] = source[local]
                else:
                    out[rows] = source[local]
            result[key] = out
        legal = tiles_ok_np(result['hand'], result['slot_ok'], result['alive'])
        return {k: torch.from_numpy(v).to(self.device) for k, v in result.items()}, torch.from_numpy(legal).to(self.device)

    def _forward(self, b, legal, *, anchor=False, declined=None):
        model = self.anchor if anchor else self.model
        model.eval()
        cls, hand = model.trunk(b)
        gate = model.gate_logits(cls, hand, b['slot_ok'])
        tiles = model.tile_logits_all(cls, hand, legal)
        logits = model.value(cls)
        _finite(gate, tiles, logits)
        if declined is not None:
            # The frontend declined this poll before sampling. Its executed distribution
            # is certain NOOP, while the untouched public features still train the critic.
            forced = torch.full_like(gate, NEG)
            forced[:, 0] = 0.
            gate = torch.where(declined[:, None], forced, gate)
        probability = logits.softmax(-1)
        return gate, tiles, probability[:, 2]-probability[:, 0]

    def _tensor(self, value, indices):
        return torch.from_numpy(np.array(value[indices], copy=True)).to(self.device)

    def halt(self, reason: str, *, generated_steps: int = 0):
        """Record an upstream failure and charge newly reported discarded/generated polls.

        This count is additional, never the actor's cumulative count. The host must
        stop generation and call this for lost chunks; there is no replacement path.
        """
        _require(_text(reason) and _integer(generated_steps) and generated_steps >= 0,
                 'halt needs a bounded reason and nonnegative additional step count')
        self.generated_steps += generated_steps
        self.halted_reason = reason if self.halted_reason is None else self.halted_reason
        return dict(halted_reason=self.halted_reason, generated_steps=self.generated_steps,
                    trained_steps=self.trained_steps, update=self.update_index)

    def update(self, chunks: Sequence[Chunk], *, play_rates: Sequence[PlayRate] = ()):
        _require(self.halted_reason is None, f'seed is halted: {self.halted_reason}')
        try:
            return self._update(chunks, play_rates)
        except Exception as exc:
            self.halted_reason = f'{type(exc).__name__}: {exc}'
            raise

    def _update(self, chunks, play_rates):
        _require(self.update_index < self.config.updates, 'registered update budget exhausted')
        _require(isinstance(chunks, (list, tuple)) and 0 < len(chunks) <= self.config.steps_per_update,
                 'bounded complete chunk list required')
        # Charge known generated transitions even when a later contract check kills this seed.
        known_counts = [int(c.generated_steps) for c in chunks
                        if isinstance(c, Chunk) and _integer(c.generated_steps) and c.generated_steps > 0]
        generated = sum(known_counts)
        self.generated_steps += generated
        _require(len(known_counts) == len(chunks), 'invalid generated-step accounting')
        _require(generated == self.config.steps_per_update, 'exact generated-step budget required; no top-up/overshoot')
        _require(self.generated_steps == (self.update_index+1)*self.config.steps_per_update,
                 'generated-step ledger mismatch')
        _require(policy_sha256(self.model, self.feature_hash) == self.policy_sha256, 'learner state changed outside update')
        _require(policy_sha256(self.anchor, self.feature_hash) == self._anchor_state_sha256, 'frozen anchor changed')
        checked = [validate_chunk(c, config=self.config, version=self.version,
                                  anchor_sha256=self.anchor_sha256, policy_sha256=self.policy_sha256,
                                  provenance_sha256=self.provenance_sha256, model_cfg=self.model.cfg) for c in chunks]
        arrays = [b for b, _ in checked]
        vectors = {key: np.concatenate([v[key] for _, v in checked]) for key in checked[0][1]}
        # Validation accepts int16/32/64 on disk; PyTorch advanced indices require int64.
        vectors['action'] = vectors['action'].astype(np.int64, copy=False)
        offsets = np.r_[0, np.cumsum([c.generated_steps for c in chunks])]
        # Chunks for each actor stay in chronological order even when actors interleave.
        intervals = {}
        for c, b in zip(chunks, arrays):
            first = int(b['glob'][0, F.G_TICK])
            previous = intervals.get(c.actor_id)
            if previous is not None:
                tick, terminal, bootstrap = previous
                _require(first == (90 if terminal else tick+F.POLL), 'actor chunks overlap or omit polls')
                if not terminal:
                    _require(abs(bootstrap-float(_array(c.old_value)[0])) <= 2e-6,
                             'continuing actor chunk bootstrap disagrees with next old value')
            intervals[c.actor_id] = (int(b['glob'][-1, F.G_TICK]), bool(_array(c.terminated)[-1]), c.bootstrap)
        _require(isinstance(play_rates, (list, tuple)) and len(play_rates) <= self.config.steps_per_update,
                 'bounded completed-game metadata required')
        rates, game_ids = {}, set()
        for rate in play_rates:
            _require(isinstance(rate, PlayRate) and _text(rate.game_id) and rate.game_id not in game_ids,
                     'invalid/duplicate play-rate game id')
            _require(_integer(rate.accepted_plays) and rate.accepted_plays >= 0
                     and isinstance(rate.seconds, (float, int)) and not isinstance(rate.seconds, bool)
                     and math.isfinite(rate.seconds) and rate.seconds > 0, 'invalid play-rate metadata')
            game_ids.add(rate.game_id)
            rates[rate.game_id] = 300*rate.accepted_plays/rate.seconds
        _require(all(15 <= r <= 80 for r in rates.values()), 'play-rate collapse: outside 15..80 accepted plays/300s')
        n = generated
        # Baseline parity is checked for ALL rows, before any optimizer step in this update.
        logp_error = value_error = 0.
        with torch.no_grad():
            for start in range(0, n, self.config.microbatch):
                ix = np.arange(start, min(n, start+self.config.microbatch))
                b, legal = self._batch(arrays, offsets, ix)
                g, t, value = self._forward(b, legal, declined=self._tensor(vectors['boundary_declined'], ix))
                logp, entropy = rl_math.joint_terms(g, t, self._tensor(vectors['action'], ix), self._tensor(vectors['dt'], ix))
                _finite(logp, entropy, value)
                logp_error = max(logp_error, float((logp.double()-self._tensor(vectors['old_logp'], ix).double()).abs().max()))
                value_error = max(value_error, float((value.double()-self._tensor(vectors['old_value'], ix).double()).abs().max()))
                _require(bool(((logp.double()-self._tensor(vectors['old_logp'], ix).double()).abs() <= 2e-6).all()),
                         'sampled old_logp parity failed before update')
                _require(bool(((value.double()-self._tensor(vectors['old_value'], ix).double()).abs() <= 2e-6).all()),
                         'old_value parity failed before update')
        advantage, returns = prepare_targets(chunks)
        self._set_trainable()
        warmup = self.update_index < 3
        for _ in range(2):
            order = self.shuffle_rng.permutation(n)
            for start in range(0, n, self.config.batch_size):
                minibatch = order[start:start+self.config.batch_size]
                actor_count = int(vectors['actor'][minibatch].sum())
                self.optimizer.zero_grad(set_to_none=True)
                for m in range(0, len(minibatch), self.config.microbatch):
                    ix = minibatch[m:m+self.config.microbatch]
                    b, legal = self._batch(arrays, offsets, ix)
                    g, t, value = self._forward(b, legal, declined=self._tensor(vectors['boundary_declined'], ix))
                    # Warmup needs no policy graph, but still evaluates the same joint distribution.
                    with torch.no_grad():
                        ag, at, _ = self._forward(b, legal, anchor=True, declined=self._tensor(vectors['boundary_declined'], ix))
                    logp, entropy = rl_math.joint_terms(g, t, self._tensor(vectors['action'], ix), self._tensor(vectors['dt'], ix))
                    kl = rl_math.joint_kl(g, t, ag, at)
                    _finite(logp, entropy, kl, value)
                    sums = rl_math.ppo_sums(logp, self._tensor(vectors['old_logp'], ix), self._tensor(advantage, ix),
                                            value, self._tensor(returns, ix), entropy, kl, self._tensor(vectors['actor'], ix))
                    loss = .5*sums['value']/len(minibatch)
                    if not warmup and actor_count:
                        loss = loss+(sums['policy']-.001*sums['entropy']+.05*sums['kl'])/actor_count
                    _finite(loss)
                    loss.backward()
                for p in self.model.parameters():
                    if p.grad is not None:
                        _finite(p.grad)
                norm = torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1., error_if_nonfinite=True)
                _finite(norm)
                self.optimizer.step()
                self.optimizer_steps += 1
                for p in self.model.parameters():
                    _finite(p)
        # Collapse KL is measured on the UPDATED distribution, in nats per all-poll row.
        kls = np.empty(n, dtype=np.float64)
        entropy_sum = 0.
        with torch.no_grad():
            for start in range(0, n, self.config.microbatch):
                ix = np.arange(start, min(n, start+self.config.microbatch))
                b, legal = self._batch(arrays, offsets, ix)
                g, t, _ = self._forward(b, legal, declined=self._tensor(vectors['boundary_declined'], ix))
                ag, at, _ = self._forward(b, legal, anchor=True, declined=self._tensor(vectors['boundary_declined'], ix))
                kl = rl_math.joint_kl(g, t, ag, at)
                _, entropy = rl_math.joint_terms(g, t, self._tensor(vectors['action'], ix), self._tensor(vectors['dt'], ix))
                _finite(kl, entropy)
                entropy_sum += float(entropy[self._tensor(vectors['actor'], ix)].double().sum())
                kls[ix] = kl.cpu().double().numpy()
        self.trained_steps += n
        self.update_index += 1
        mean_kl = float(kls.mean())
        if not warmup:
            self.high_kl_streak = self.high_kl_streak+1 if mean_kl > .5 else 0
            if self.high_kl_streak >= 3:
                self.halted_reason = 'three consecutive PPO updates with mean KL > 0.5 nats/poll'
        self.policy_sha256 = policy_sha256(self.model, self.feature_hash)
        opponents = {}
        for i, c in enumerate(chunks):
            opponents.setdefault(c.opponent_id, []).append(kls[offsets[i]:offsets[i+1]])
        opponent_metrics = {name: dict(mean=float(np.concatenate(parts).mean()),
                                      p95=float(np.quantile(np.concatenate(parts), .95)), polls=sum(map(len, parts)))
                            for name, parts in opponents.items()}
        eligible = int(vectors['actor'].sum())
        self.last_metrics = dict(update=self.update_index, version=self.version, warmup=warmup,
                                 generated_steps=self.generated_steps, trained_steps=self.trained_steps,
                                 optimizer_steps=self.optimizer_steps, polls=n, actor_polls=eligible, forced_polls=n-eligible,
                                 busy_polls=sum(int(b['glob'][:, F.G_BUSY].sum()) for b in arrays),
                                 boundary_declined_steps=int(vectors['boundary_declined'].sum()),
                                 old_logp_max_error=logp_error, old_value_max_error=value_error,
                                 legal_action_checks=n, cadence_checks=n,
                                 mean_entropy=entropy_sum/max(1, eligible),
                                 mean_kl=mean_kl, p95_kl=float(np.quantile(kls, .95)), per_opponent_kl=opponent_metrics,
                                 plays_per_300s=rates, play_rates_reported=bool(rates),
                                 high_kl_streak=self.high_kl_streak, halted_reason=self.halted_reason,
                                 policy_sha256=self.policy_sha256)
        self._set_trainable()
        return copy.deepcopy(self.last_metrics)

    def save_checkpoint(self, path):
        """Atomic boundary checkpoint; no handler is installed. Host calls this after update/stop."""
        _require(policy_sha256(self.anchor, self.feature_hash) == self._anchor_state_sha256, 'frozen anchor changed')
        state = dict(format=1, config=self.config.record(), model_cfg=self.model.cfg,
                     feature_hash=self.feature_hash, anchor_sha256=self.anchor_sha256, selection=self.selection,
                     anchor_state_sha256=self._anchor_state_sha256,
                     runtime_manifest=self.runtime_manifest, provenance_sha256=self.provenance_sha256,
                     model=self.model.state_dict(), anchor=self.anchor.state_dict(), optimizer=self.optimizer.state_dict(),
                     update_index=self.update_index, generated_steps=self.generated_steps, trained_steps=self.trained_steps,
                     optimizer_steps=self.optimizer_steps, high_kl_streak=self.high_kl_streak,
                     halted_reason=self.halted_reason, last_metrics=self.last_metrics,
                     policy_sha256=policy_sha256(self.model, self.feature_hash),
                     shuffle_rng=self.shuffle_rng.bit_generator.state, python_rng=random.getstate(),
                     numpy_rng=np.random.get_state(), torch_rng=torch.get_rng_state(),
                     cuda_rng=torch.cuda.get_rng_state_all() if torch.cuda.is_initialized() else None)
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=destination.name+'.', suffix='.tmp', dir=destination.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                torch.save(state, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
            directory_fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def load_checkpoint(self, path):
        """Restore a trusted local checkpoint into a fresh learner with identical pins/config."""
        try:
            return self._load_checkpoint(path)
        except Exception as exc:
            self.halted_reason = f'{type(exc).__name__}: {exc}'
            raise

    def _load_checkpoint(self, path):
        _require(self.update_index == 0 and self.generated_steps == 0 and self.halted_reason is None,
                 'resume requires a fresh learner')
        state = torch.load(path, map_location='cpu', weights_only=False)
        for key, expected in dict(format=1, config=self.config.record(), model_cfg=self.model.cfg,
                                  feature_hash=self.feature_hash, anchor_sha256=self.anchor_sha256, selection=self.selection,
                                  anchor_state_sha256=self._anchor_state_sha256,
                                  runtime_manifest=self.runtime_manifest, provenance_sha256=self.provenance_sha256).items():
            _require(state.get(key) == expected, f'checkpoint {key} mismatch')
        update = state['update_index']
        _require(_integer(update) and 0 <= update <= self.config.updates, 'checkpoint update out of budget')
        expected_steps = update*2*self.config.steps_per_update//self.config.batch_size
        _require(state['trained_steps'] == update*self.config.steps_per_update
                 and _integer(state['optimizer_steps']) and state['optimizer_steps'] >= expected_steps
                 and (state['halted_reason'] is not None or state['optimizer_steps'] == expected_steps),
                 'checkpoint training counters mismatch')
        _require(_integer(state['generated_steps']) and state['generated_steps'] >= state['trained_steps']
                 and (state['halted_reason'] is not None or state['generated_steps'] == state['trained_steps']),
                 'checkpoint generated ledger mismatch')
        # load_state_dict silently casts. Reject stored dtype/shape mismatches first.
        for key, model in (('model', self.model), ('anchor', self.anchor)):
            expected = model.state_dict()
            actual = state[key]
            _require(set(actual) == set(expected) and all(
                isinstance(actual[k], torch.Tensor) and actual[k].dtype == t.dtype
                and actual[k].shape == t.shape for k, t in expected.items()),
                f'checkpoint {key} keys/dtypes/shapes mismatch')
        self.model.load_state_dict(state['model'], strict=True)
        self.anchor.load_state_dict(state['anchor'], strict=True)
        _require(policy_sha256(self.anchor, self.feature_hash) == self._anchor_state_sha256, 'checkpoint anchor state hash mismatch')
        _require(policy_sha256(self.model, self.feature_hash) == state['policy_sha256'], 'checkpoint policy state hash mismatch')
        for model in (self.model, self.anchor):
            for t in model.state_dict().values():
                _finite(t)
        expected_groups = [{k: v for k, v in group.items() if k != 'params'} for group in self.optimizer.param_groups]
        actual_groups = [{k: v for k, v in group.items() if k != 'params'} for group in state['optimizer']['param_groups']]
        _require(actual_groups == expected_groups, 'checkpoint optimizer configuration mismatch')
        stored_optimizer = state['optimizer']
        parameter_ids = [i for group in stored_optimizer['param_groups'] for i in group['params']]
        parameters = [p for group in self.optimizer.param_groups for p in group['params']]
        _require(len(parameter_ids) == len(parameters) and len(set(parameter_ids)) == len(parameter_ids),
                 'checkpoint optimizer parameter mapping mismatch')
        by_id = dict(zip(parameter_ids, parameters))
        _require(set(stored_optimizer['state']) <= set(by_id), 'checkpoint optimizer unknown parameter')
        for pid, values in stored_optimizer['state'].items():
            _require(set(values) == {'step', 'exp_avg', 'exp_avg_sq'}, 'checkpoint optimizer state keys mismatch')
            p = by_id[pid]
            for key in ('exp_avg', 'exp_avg_sq'):
                value = values[key]
                _require(isinstance(value, torch.Tensor) and value.dtype == p.dtype and value.shape == p.shape,
                         'checkpoint optimizer moment dtype/shape mismatch')
                _finite(value)
            step = values['step']
            _require(isinstance(step, torch.Tensor) and step.ndim == 0 and step.dtype == torch.float32,
                     'checkpoint optimizer step must be a float32 scalar counter')
            _finite(step)
        self.optimizer.load_state_dict(stored_optimizer)
        for values in self.optimizer.state.values():
            for value in values.values():
                if isinstance(value, torch.Tensor):
                    _finite(value)
        for key in ('update_index', 'generated_steps', 'trained_steps', 'optimizer_steps', 'high_kl_streak',
                    'halted_reason', 'last_metrics', 'policy_sha256'):
            setattr(self, key, state[key])
        self.shuffle_rng.bit_generator.state = state['shuffle_rng']
        random.setstate(state['python_rng'])
        np.random.set_state(state['numpy_rng'])
        torch.set_rng_state(state['torch_rng'])
        if state['cuda_rng'] is not None:
            _require(torch.cuda.is_available() and len(state['cuda_rng']) == torch.cuda.device_count(), 'CUDA RNG topology mismatch')
            torch.cuda.set_rng_state_all(state['cuda_rng'])
        self._set_trainable()
        return copy.deepcopy(self.last_metrics)
