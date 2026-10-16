"""Frozen-policy adapters for Tier B roots: actors, scalar root bank, native prefix.

* ``PolicyActor`` steps a frozen recurrent checkpoint one public packet at a
  time, masked by ``PublicActionMaskBuilder``, sampling at temperature one
  from a seeded generator. It records its inputs so a capture can be audited
  by recomputation before any outcome is opened.
* ``generate_tier_b_root_bank`` samples one root request per scalar policy
  game (self-play or scripted evaluation opponent), stratified by deck, phase
  and seat. Scalar games only locate policy-reachable eligible states; they
  never observe branch outcomes.
* ``collect_tier_b_prefix`` drives the existing native prefix collector with
  the frozen policy (and the declared opponent) and the Tier B root rule.
  After the root, branch continuations use the unchanged frozen scripted
  reacting controllers of the Tier A executor.

Native packets are built with the reference vocabulary. A vocabulary bridge
maps them to the checkpoint vocabulary; channels the native adapter does not
measure (opponent history and seen cards) stay missing with zero confidence.
"""

from __future__ import annotations

import json
import random
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

import numpy as np
import torch

from .public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from .public_observation import (
    ConfidenceAwareActorObservation,
    project_council_public_observation,
)
from .public_policy_contract import PublicPolicySequence
from .public_scripted_opponent import SUPPORTED_CARDS, PublicScriptedOpponent
from .readiness_execution import canonical_sha, file_sha, packet_sha
from .readiness_root_bank import DECKS, RootSelection
from .readiness_tier_b import (
    DEFAULT_PHASE_ALLOCATION,
    PHASE_WINDOWS,
    PROBE_KINDS,
    WAIT_ACTION,
    BlockKind,
    OpponentKind,
    Phase,
    PolicyRootRecord,
    ProbeKind,
    RejectedDraw,
    ScalarPreview,
    TierBRootBank,
    TierBRootRequest,
    policy_candidates,
    policy_root_record,
    representative_allocation,
)
from .readiness_tier_b_probes import probe_matches
from .structured_obs import StructuredObservationBuilder

DEFAULT_DECK_TABLE: dict[str, tuple[str, ...]] = {
    "hog_cycle": DECKS[0],
    "giant_beatdown": DECKS[1],
    "hog_control": DECKS[2],
    "giant_control": DECKS[3],
}
DEFAULT_OPPONENTS: tuple[OpponentKind, ...] = (
    "policy",
    "script:balanced",
    "script:pressure",
    "script:defense",
)


@dataclass
class FrozenPolicy:
    model: Any
    builder: StructuredObservationBuilder
    checkpoint_path: Path
    checkpoint_sha256: str
    policy_contract_sha256: str
    device: torch.device = field(default_factory=lambda: torch.device("cpu"))


def load_frozen_policy(
    checkpoint_path: Path, *, decks_path: str | Path, device: str = "cpu"
) -> FrozenPolicy:
    """Load a frozen v4 public-contract checkpoint without modifying it."""
    from .eval import load_policy_checkpoint

    loaded = load_policy_checkpoint(
        checkpoint_path, device=torch.device(device), decks_path=decks_path
    )
    config = loaded.model.config
    if config.public_contract_version < 4 or not config.public_observation_confidence:
        raise ValueError("Tier B requires a confidence-aware public-v4 checkpoint")
    if not set(loaded.builder.card_vocab) <= SUPPORTED_CARDS:
        raise ValueError("policy builder vocabulary exceeds the admitted card scope")
    for parameter in loaded.model.parameters():
        parameter.requires_grad_(False)
    return FrozenPolicy(
        model=loaded.model,
        builder=loaded.builder,
        checkpoint_path=Path(checkpoint_path).resolve(),
        checkpoint_sha256=file_sha(Path(checkpoint_path)),
        policy_contract_sha256=canonical_sha(config.to_dict()),
        device=torch.device(device),
    )


def _pad(array: np.ndarray, length: int, name: str, mask: np.ndarray | None = None) -> np.ndarray:
    if array.shape[0] > length:
        if mask is not None and mask[length:].any():
            raise ValueError(f"{name}: visible rows exceed the policy capacity")
        if mask is None and np.any(array[length:]):
            raise ValueError(f"{name}: known values exceed the policy slot count")
        return array[:length].copy()
    pad = [(0, length - array.shape[0])] + [(0, 0)] * (array.ndim - 1)
    return np.pad(array, pad)


def remap_packet(
    packet: ConfidenceAwareActorObservation,
    source_token_names: Sequence[str],
    target: StructuredObservationBuilder,
) -> tuple[ConfidenceAwareActorObservation, int]:
    """Map token identities by name and resize slots to the policy contract.

    Returns the projected policy packet and the number of visible identities
    that are absent from the policy vocabulary (mapped to ``<unknown>``).
    Missing channels stay missing; nothing is inferred.
    """
    packet.validate()
    lut = np.ones(len(source_token_names), dtype=np.int64)
    lut[0] = 0
    names = {name: i for i, name in enumerate(target.token_names)}
    for index, name in enumerate(source_token_names[1:], start=1):
        lut[index] = names.get(name, 1)
    obs = packet.observation

    def mapped(ids: np.ndarray) -> np.ndarray:
        return lut[np.asarray(ids, dtype=np.int64)]

    m = target.max_entities
    # Re-sort visible rows by the policy builder's deterministic key:
    # (kind, enemy side, policy token id, rounded y, rounded x).
    visible = np.flatnonzero(obs.entity_mask)
    hidden = np.flatnonzero(~obs.entity_mask)
    target_ids = lut[np.asarray(obs.entity_ids, dtype=np.int64)]
    features = obs.entity_features

    def key(row: int) -> tuple[int, int, int, float, float]:
        return (
            int(np.argmax(features[row, 4:9])),
            int(features[row, 3] > 0.5),
            int(target_ids[row]),
            round(float(features[row, 1]), 5),
            round(float(features[row, 0]), 5),
        )

    order = np.asarray(sorted(visible.tolist(), key=key) + hidden.tolist(), dtype=np.int64)
    obs = replace(
        obs,
        entity_ids=obs.entity_ids[order],
        entity_features=obs.entity_features[order],
        entity_mask=obs.entity_mask[order],
        entity_levels=None if obs.entity_levels is None else obs.entity_levels[order],
        entity_level_confidence=None
        if obs.entity_level_confidence is None
        else obs.entity_level_confidence[order],
    )
    packet = replace(
        packet,
        observation=obs,
        entity_id_confidence=packet.entity_id_confidence[order],
        entity_feature_confidence=packet.entity_feature_confidence[order],
    )
    mask = obs.entity_mask
    unmapped = int(np.sum((mapped(obs.entity_ids) == 1) & (obs.entity_ids > 1) & mask))
    unmapped += int(np.sum((mapped(obs.hand_ids) == 1) & (obs.hand_ids > 1)))
    hist, seen = target.public_history_slots, target.public_seen_card_slots
    payload = replace(
        obs,
        entity_ids=_pad(mapped(obs.entity_ids), m, "entity ids", mask),
        entity_features=_pad(obs.entity_features, m, "entity features", mask),
        entity_mask=_pad(mask, m, "entity mask", mask),
        hand_ids=mapped(obs.hand_ids),
        opponent_history_ids=_pad(mapped(obs.opponent_history_ids), hist, "history"),
        opponent_history_ages=_pad(obs.opponent_history_ages, hist, "history ages"),
        opponent_seen_card_ids=_pad(mapped(obs.opponent_seen_card_ids), seen, "seen"),
        entity_levels=None
        if obs.entity_levels is None
        else _pad(obs.entity_levels, m, "entity levels", mask),
        entity_level_confidence=None
        if obs.entity_level_confidence is None
        else _pad(obs.entity_level_confidence, m, "level confidence", mask),
    )
    result = replace(
        packet,
        observation=payload,
        entity_id_confidence=_pad(packet.entity_id_confidence, m, "id confidence", mask),
        entity_feature_confidence=_pad(
            packet.entity_feature_confidence, m, "feature confidence", mask
        ),
        opponent_history_confidence=_pad(
            packet.opponent_history_confidence, hist, "history confidence"
        ),
        opponent_seen_card_confidence=_pad(
            packet.opponent_seen_card_confidence, seen, "seen confidence"
        ),
    )
    return project_council_public_observation(result), unmapped


class PolicyActor:
    """One seat of a frozen recurrent policy with seeded stochastic sampling."""

    def __init__(
        self,
        policy: FrozenPolicy,
        *,
        seed: int,
        source_token_names: Sequence[str] | None = None,
    ):
        self.policy = policy
        self.source_token_names = (
            None if source_token_names is None else tuple(source_token_names)
        )
        self.masks = PublicActionMaskBuilder(policy.builder)
        self.state = policy.model.initial_state(1, device=policy.device)
        self.previous = WAIT_ACTION
        self.start = True
        self.generator = torch.Generator().manual_seed(int(seed))
        self.seed = int(seed)
        self._cached: tuple[object, tuple[np.ndarray, np.ndarray, Any]] | None = None
        self.sequences: list[PublicPolicySequence] = []
        self.step_masks: list[np.ndarray] = []
        self.previous_actions: list[int] = []
        self.starts: list[bool] = []
        self.actions: list[int] = []
        self.unmapped_identities = 0

    def policy_packet(
        self, packet: ConfidenceAwareActorObservation
    ) -> ConfidenceAwareActorObservation:
        if self.source_token_names is None:
            return project_council_public_observation(packet)
        result, unmapped = remap_packet(
            packet, self.source_token_names, self.policy.builder
        )
        self.unmapped_identities += unmapped
        return result

    @torch.no_grad()
    def step_sequence(
        self,
        sequence: PublicPolicySequence,
        mask: np.ndarray,
        *,
        previous: int | None = None,
        start: bool | None = None,
    ) -> np.ndarray:
        previous = self.previous if previous is None else previous
        start = self.start if start is None else start
        inputs = sequence.policy_inputs(
            action_mask=np.asarray(mask, dtype=np.bool_)[None],
            previous_actions=np.asarray([previous], dtype=np.int64),
            previous_rewards=np.zeros(1, dtype=np.float32),
            episode_starts=np.asarray([start]),
            device=self.policy.device,
        )
        output = self.policy.model(inputs, self.state)
        self.state = output.next_state
        self.start = False
        self.sequences.append(sequence)
        self.step_masks.append(np.asarray(mask, dtype=np.bool_))
        self.previous_actions.append(int(previous))
        self.starts.append(bool(start))
        return output.joint_logits[0, 0].double().cpu().numpy()

    def distribution(
        self, packet: ConfidenceAwareActorObservation
    ) -> tuple[np.ndarray, np.ndarray, ConfidenceAwareActorObservation]:
        """Advance recurrent state once per packet; repeated calls are cached."""
        if self._cached is not None and self._cached[0] is packet:
            return self._cached[1]
        if self._cached is not None:
            raise ValueError("previous packet was observed without an action")
        view = self.policy_packet(packet)
        mask = self.masks.build(PublicActionMaskInput.from_confidence_observation(view))
        sequence = PublicPolicySequence.from_observations(self.policy.builder, [view])
        log_probs = self.step_sequence(sequence, mask)
        self._cached = (packet, (log_probs, mask, view))
        return log_probs, mask, view

    def sample(self, log_probs: np.ndarray, mask: np.ndarray) -> int:
        legal = np.flatnonzero(mask)
        probs = np.exp(log_probs[legal] - log_probs[legal].max())
        index = torch.multinomial(
            torch.as_tensor(probs / probs.sum(), dtype=torch.float64),
            1,
            generator=self.generator,
        )
        return int(legal[int(index.item())])

    def select_action(self, packet: ConfidenceAwareActorObservation) -> int:
        log_probs, mask, _ = self.distribution(packet)
        action = self.sample(log_probs, mask)
        self.previous = action
        self.actions.append(action)
        self._cached = None
        return action

    def save_trace(self, directory: Path, prefix: str = "policy-trace") -> dict[str, str]:
        """Persist the exact policy inputs for recomputation audits."""
        if not self.sequences:
            raise ValueError("no policy steps to save")
        arrays = {
            name: np.concatenate([s.arrays[name] for s in self.sequences])
            for name in self.sequences[0].arrays
        }
        sequence_path = directory / f"{prefix}-public.npz"
        PublicPolicySequence(self.policy.builder.token_names, arrays).save(sequence_path)
        controls_path = directory / f"{prefix}-controls.npz"
        with controls_path.open("xb") as stream:
            np.savez_compressed(
                stream,
                action_masks=np.asarray(self.step_masks, dtype=np.bool_),
                previous_actions=np.asarray(self.previous_actions, dtype=np.int64),
                episode_starts=np.asarray(self.starts, dtype=np.bool_),
                sampled_actions=np.asarray(self.actions, dtype=np.int64),
                seed=np.asarray(self.seed, dtype=np.int64),
            )
        return {
            sequence_path.name: file_sha(sequence_path),
            controls_path.name: file_sha(controls_path),
        }


def replay_policy_trace(
    policy: FrozenPolicy, directory: Path, prefix: str = "policy-trace"
) -> tuple[np.ndarray, np.ndarray, PublicPolicySequence]:
    """Recompute the recorded trace; verify every sampled prefix action.

    Returns the final-step log-probabilities, mask and one-step sequence.
    """
    sequence = PublicPolicySequence.load(
        directory / f"{prefix}-public.npz", token_names=policy.builder.token_names
    )
    with np.load(directory / f"{prefix}-controls.npz", allow_pickle=False) as data:
        controls = {name: data[name].copy() for name in data.files}
    count = len(controls["action_masks"])
    if count == 0 or len(sequence.arrays["own_last_play_ids"]) != count:
        raise ValueError("policy trace length differs from its controls")
    if len(controls["sampled_actions"]) not in (count - 1, count):
        raise ValueError("policy trace must end at an unacted root or action")
    actor = PolicyActor(policy, seed=int(controls["seed"]))
    log_probs = np.zeros(0)
    step = None
    for index in range(count):
        step = PublicPolicySequence(
            sequence.token_names,
            {name: value[index : index + 1] for name, value in sequence.arrays.items()},
        )
        mask = controls["action_masks"][index]
        log_probs = actor.step_sequence(
            step,
            mask,
            previous=int(controls["previous_actions"][index]),
            start=bool(controls["episode_starts"][index]),
        )
        if index < len(controls["sampled_actions"]):
            action = actor.sample(log_probs, mask)
            if action != int(controls["sampled_actions"][index]):
                raise ValueError("recorded policy action is not reproducible")
            if index + 1 < count and int(controls["previous_actions"][index + 1]) != action:
                raise ValueError("recorded previous action differs from sample")
    assert step is not None
    return log_probs, controls["action_masks"][-1], step


# ---------------------------------------------------------------------------
# Scalar root bank.


@dataclass(frozen=True)
class Slot:
    index: int
    deck_id: str
    phase: Phase
    root_owner: Literal[0, 1]
    opponent: OpponentKind
    probe_kind: ProbeKind | None = None


def representative_slots(
    deck_table: dict[str, tuple[str, ...]],
    phase_allocation: tuple[tuple[Phase, int], ...] = DEFAULT_PHASE_ALLOCATION,
    opponents: tuple[OpponentKind, ...] = DEFAULT_OPPONENTS,
) -> tuple[Slot, ...]:
    cells = representative_allocation(tuple(sorted(deck_table)), phase_allocation)
    return tuple(
        Slot(i, deck, phase, seat, opponents[i % len(opponents)])
        for i, (deck, phase, seat) in enumerate(cells)
    )


def probe_slots(
    deck_table: dict[str, tuple[str, ...]],
    per_kind: int = 4,
    kinds: tuple[str, ...] = PROBE_KINDS,
    phase: Phase = "middle",
    opponents: tuple[OpponentKind, ...] = DEFAULT_OPPONENTS,
) -> tuple[Slot, ...]:
    decks = sorted(deck_table)
    slots = []
    for kind in kinds:
        for k in range(per_kind):
            i = len(slots)
            slots.append(
                Slot(i, decks[i % len(decks)], phase, k % 2, opponents[i % len(opponents)], kind)  # type: ignore[arg-type]
            )
    return tuple(slots)


def _script(builder: StructuredObservationBuilder, opponent: str) -> PublicScriptedOpponent:
    return PublicScriptedOpponent(builder, style=opponent.split(":", 1)[1])


def sample_scalar_root(
    policy: FrozenPolicy,
    *,
    decks: tuple[tuple[str, ...], tuple[str, ...]],
    root_owner: int,
    opponent: str,
    seed: int,
    policy_seeds: tuple[int, int],
    start_tick: int,
    stop_tick: int,
    probe_kind: str | None = None,
    slot_index: int | None = None,
) -> ScalarPreview | str:
    """Play one scalar policy game to the first eligible owner root in window.

    Returns a preview, or a rejection reason. The game stops at the root; no
    continuation outcome is ever computed here.
    """
    from clasher.battle import STANDARD_MATCH_TICKS

    from .selfplay_env import SelfPlayBattleEnv, resolve_match_horizon

    builder = policy.builder
    env = SelfPlayBattleEnv(
        decision_interval_ticks=5,
        max_ticks=resolve_match_horizon(STANDARD_MATCH_TICKS, 4),
        seed=seed,
        canonical_perspective=True,
        canonical_lane_globals=True,
        public_contract_version=4,
        idle_fast_forward=False,
        tower_levels=(11, 11),
        card_levels=({}, {}),
    )
    env._structured_obs_builder = builder
    env.reset(seed=seed, ordered_decks=decks)
    actors: list[Any] = [None, None]
    actors[root_owner] = PolicyActor(policy, seed=policy_seeds[root_owner])
    other = 1 - root_owner
    actors[other] = (
        PolicyActor(policy, seed=policy_seeds[other])
        if opponent == "policy"
        else _script(builder, opponent)
    )
    masks = PublicActionMaskBuilder(builder)
    while True:
        tick = env.battle.tick
        packets = [
            project_council_public_observation(builder.build_actor(env.battle, s))
            for s in (0, 1)
        ]
        if packets[root_owner].observation.terminal is True:
            return "scalar game ended before an eligible root"
        if start_tick <= tick <= stop_tick:
            log_probs, mask, view = actors[root_owner].distribution(packets[root_owner])
            if probe_kind is None or probe_matches(probe_kind, view, builder.token_names):
                try:
                    candidates, recommendation = policy_candidates(
                        log_probs,
                        mask,
                        view,
                        probe_kind=probe_kind,  # type: ignore[arg-type]
                        token_names=builder.token_names,
                    )
                except ValueError as exc:
                    if not str(exc).startswith("ineligible root:"):
                        raise
                else:
                    return ScalarPreview(
                        scalar_seed=seed,
                        scalar_root_tick=tick,
                        scalar_packet_sha256=packet_sha(view),
                        scalar_candidate_actions=tuple(c.action_id for c in candidates),  # type: ignore[arg-type]
                        scalar_original_recommendation=recommendation.action_id,
                    )
        if tick > stop_tick:
            return "no eligible scalar policy root in the declared window"
        decisions = {s: int(actors[s].select_action(packets[s])) for s in (0, 1)}
        public_masks = {
            s: masks.build(PublicActionMaskInput.from_confidence_observation(packets[s]))
            for s in (0, 1)
        }
        if any(not public_masks[s][decisions[s]] for s in (0, 1)):
            raise ValueError("scalar prefix selected an illegal public action")
        _, done, _ = env.step(decisions, pre_action_masks=public_masks)
        if done:
            return "scalar game ended before an eligible root"


Sampler = Callable[..., "ScalarPreview | str"]


def generate_tier_b_root_bank(
    policy: FrozenPolicy,
    *,
    master_seed: int,
    block_kind: BlockKind = "representative",
    deck_table: dict[str, tuple[str, ...]] | None = None,
    slots: tuple[Slot, ...] | None = None,
    window_ticks: int = 300,
    max_draws_per_root: int = 3,
    sampler: Sampler | None = None,
) -> TierBRootBank:
    """Declare root requests from scalar policy games; outcomes are never seen.

    Each slot draws a fresh game seed, the owner's declared deck, an opponent
    deck and a uniform window start inside the slot's phase. Draws without an
    eligible scalar preview are recorded (bounded, never hidden). A slot with
    no eligible draw leaves the bank incomplete and undeclarable.
    """
    if type(master_seed) is not int or master_seed < 0:
        raise ValueError("master seed must be a nonnegative integer")
    table = {k: tuple(sorted(v)) for k, v in (deck_table or DEFAULT_DECK_TABLE).items()}
    if slots is None:
        slots = (
            representative_slots(table)
            if block_kind == "representative"
            else probe_slots(table)
        )
    if block_kind == "targeted_probe" and any(s.probe_kind is None for s in slots):
        raise ValueError("probe banks need a probe kind per slot")
    run = sampler or sample_scalar_root
    source = random.Random(master_seed)
    seen: set[int] = set()
    requests, rejected, failures = [], [], []
    for slot in slots:
        low, high = PHASE_WINDOWS[slot.phase]
        for _draw in range(max_draws_per_root):
            seed = source.getrandbits(32)
            if seed in seen:
                raise ValueError("episode seed collision; declare a new bank")
            seen.add(seed)
            rng = random.Random(seed)
            own = list(table[slot.deck_id])
            other = list(table[rng.choice(sorted(table))])
            rng.shuffle(own)
            rng.shuffle(other)
            decks = (tuple(own), tuple(other)) if slot.root_owner == 0 else (tuple(other), tuple(own))
            start = 5 * rng.randrange(-(-low // 5), (high - 10) // 5)
            stop = min(start + window_ticks, 5 * ((high - 5) // 5))
            if stop <= start:
                stop = start + 5
            policy_seeds = (rng.getrandbits(32), rng.getrandbits(32))
            preview = run(
                policy,
                decks=decks,
                root_owner=slot.root_owner,
                opponent=slot.opponent,
                seed=seed,
                policy_seeds=policy_seeds,
                start_tick=start,
                stop_tick=stop,
                probe_kind=slot.probe_kind,
                slot_index=slot.index,
            )
            if isinstance(preview, str):
                rejected.append(RejectedDraw(slot=slot.index, scalar_seed=seed, reason=preview))
                continue
            key = f"tb{master_seed}-{block_kind[:4]}-{slot.index:02d}"
            requests.append(
                TierBRootRequest(
                    family_id=key,
                    source_episode_id=f"{key}-g{seed:08x}",
                    root_owner=slot.root_owner,
                    episode_seed=seed,
                    decks=decks,
                    deck_id=slot.deck_id,
                    phase=slot.phase,
                    opponent=slot.opponent,
                    policy_seeds=policy_seeds,
                    checkpoint_sha256=policy.checkpoint_sha256,
                    probe_kind=slot.probe_kind,
                    start_tick=start,
                    stop_tick=stop,
                    scalar_preview=preview,
                )
            )
            break
        else:
            failures.append(f"slot {slot.index}: no eligible scalar draw")
    if failures:
        # Surface the incomplete design with every rejection; never declare it.
        raise IncompleteRootBank(tuple(failures), tuple(rejected), tuple(requests))
    return TierBRootBank(
        block_kind=block_kind,
        master_seed=master_seed,
        checkpoint_sha256=policy.checkpoint_sha256,
        policy_contract_sha256=policy.policy_contract_sha256,
        deck_table=table,
        window_ticks=window_ticks,
        max_draws_per_root=max_draws_per_root,
        requests=tuple(requests),
        rejected_draws=tuple(rejected),
    )


class IncompleteRootBank(ValueError):
    def __init__(self, failures: tuple[str, ...], rejected: tuple[RejectedDraw, ...], requests: tuple[TierBRootRequest, ...]):
        super().__init__("incomplete Tier B root bank: " + "; ".join(failures))
        self.failures = failures
        self.rejected = rejected
        self.requests = requests


# ---------------------------------------------------------------------------
# Native prefix capture.


def policy_root_selector(
    request: TierBRootRequest,
    actor: PolicyActor,
    *,
    reference_token_names: Sequence[str],
    policy: FrozenPolicy,
    records: list[PolicyRootRecord],
) -> Callable[[Iterator[tuple[int, ConfidenceAwareActorObservation]]], RootSelection]:
    """First eligible frozen-policy root in the declared window; no replacement."""

    def select(
        packets: Iterator[tuple[int, ConfidenceAwareActorObservation]],
    ) -> RootSelection:
        count, expected = 0, request.start_tick

        def result(status: Any, reason: str, **values: Any) -> RootSelection:
            return RootSelection(
                family_id=request.family_id,
                source_episode_id=request.source_episode_id,
                root_owner=request.root_owner,
                status=status,
                observed_packets=count,
                reason=reason,
                **values,
            )

        for tick, packet in packets:
            if tick != expected:
                return result("missing_packets", f"expected tick {expected}, received {tick}")
            count += 1
            packet.validate()
            if packet.observation.terminal is True:
                return result("terminal_before_root", "episode ended before an eligible root")
            log_probs, mask, view = actor.distribution(packet)
            if request.probe_kind is None or probe_matches(
                request.probe_kind, packet, reference_token_names
            ):
                try:
                    candidates, recommendation = policy_candidates(
                        log_probs,
                        mask,
                        packet,
                        probe_kind=request.probe_kind,
                        token_names=tuple(reference_token_names),
                    )
                except ValueError as exc:
                    if not str(exc).startswith("ineligible root:"):
                        raise
                else:
                    public_sha = packet_sha(packet)
                    records.append(
                        policy_root_record(
                            family_id=request.family_id,
                            checkpoint_sha256=policy.checkpoint_sha256,
                            policy_contract_sha256=policy.policy_contract_sha256,
                            public_packet_sha256=public_sha,
                            policy_packet_sha256=packet_sha(view),
                            root_tick=tick,
                            log_probs=log_probs,
                            mask=mask,
                            candidates=candidates,
                            recommendation=recommendation,
                            probe_kind=request.probe_kind,
                        )
                    )
                    return result(
                        "selected",
                        "first eligible frozen-policy root",
                        root_tick=tick,
                        public_packet_sha256=public_sha,
                        candidates=candidates,
                        original_recommendation=recommendation.action_id,
                    )
            if tick == request.stop_tick:
                return result(
                    "no_eligible_root", "bounded policy root window exhausted; no replacement"
                )
            expected += request.cadence_ticks
        return result("missing_packets", f"missing tick {expected}")

    return select


def collect_tier_b_prefix(
    request: TierBRootRequest,
    config: dict[str, Any],
    *,
    output: Path,
    policy: FrozenPolicy,
    reference_builder: StructuredObservationBuilder,
    **collector: Any,
) -> tuple[dict[str, Any], PolicyRootRecord | None]:
    """Run ``collect_prefix`` with the frozen policy and the Tier B root rule.

    ``collector`` passes the command/read_frame/project/claim/verify_producer
    (and optional source_archive/read_session_scope) dependencies unchanged.
    """
    from .readiness_prefix import collect_prefix

    if request.checkpoint_sha256 != policy.checkpoint_sha256:
        raise ValueError("root request binds a different checkpoint")
    names = reference_builder.token_names
    owner = request.root_owner
    actors: list[Any] = [None, None]
    actors[owner] = PolicyActor(policy, seed=request.policy_seeds[owner], source_token_names=names)
    actors[1 - owner] = (
        PolicyActor(policy, seed=request.policy_seeds[1 - owner], source_token_names=names)
        if request.opponent == "policy"
        else _script(reference_builder, request.opponent)
    )
    records: list[PolicyRootRecord] = []
    result = collect_prefix(
        request,  # type: ignore[arg-type]  # duck-typed request fields
        config,
        output=output,
        role="fresh_acceptance",
        builder=reference_builder,
        prefix_actors=actors,
        root_selector=policy_root_selector(
            request,
            actors[owner],
            reference_token_names=names,
            policy=policy,
            records=records,
        ),
        **collector,
    )
    record = records[0] if result["status"] == "selected" and records else None
    trace: dict[str, str] = {}
    if output.is_dir() and actors[owner].sequences:
        trace = actors[owner].save_trace(output)
    if output.is_dir():
        (output / "policy-root.json").write_text(
            json.dumps(
                {
                    "schema": "readiness-v2-tier-b-policy-root-v1",
                    "status": result["status"],
                    "root_request_sha256": canonical_sha(request.model_dump(mode="json")),
                    "checkpoint_sha256": policy.checkpoint_sha256,
                    "policy_contract_sha256": policy.policy_contract_sha256,
                    "unmapped_visible_identities": actors[owner].unmapped_identities,
                    "record": None if record is None else record.model_dump(mode="json"),
                    "trace_hashes": trace,
                },
                indent=2,
                allow_nan=False,
            )
            + "\n"
        )
    return result, record


def verify_policy_root_capture(policy: FrozenPolicy, directory: Path) -> PolicyRootRecord:
    """Recompute a captured policy root before sealing; any drift fails."""
    payload = json.loads((directory / "policy-root.json").read_text())
    if payload.get("record") is None:
        raise ValueError("capture has no selected policy root")
    record = PolicyRootRecord.model_validate(payload["record"])
    if (
        record.checkpoint_sha256 != policy.checkpoint_sha256
        or payload["checkpoint_sha256"] != policy.checkpoint_sha256
        or record.policy_contract_sha256 != policy.policy_contract_sha256
    ):
        raise ValueError("captured root used a different frozen checkpoint")
    for name, digest in payload["trace_hashes"].items():
        if file_sha(directory / name) != digest:
            raise ValueError(f"policy trace changed: {name}")
    log_probs, mask, step = replay_policy_trace(policy, directory)
    for role, action in record.candidate_actions.items():
        if abs(float(log_probs[action]) - record.candidate_log_probs[role]) > 1e-4:
            raise ValueError("recomputed policy ranking differs from capture")
    # Card identity relations are vocabulary-independent, so the policy packet
    # reproduces the reference packet's role choices.
    arrays = step.arrays
    packet = SimpleNamespace(
        observation=SimpleNamespace(
            hand_ids=arrays["hand_ids"][0],
            entity_ids=arrays["entity_ids"][0],
            entity_features=arrays["entity_features"][0],
            entity_mask=arrays["entity_mask"][0],
        ),
        entity_id_confidence=arrays["entity_id_confidence"][0],
    )
    candidates, recommendation = policy_candidates(
        log_probs,
        mask,
        packet,  # type: ignore[arg-type]
        probe_kind=record.probe_kind,
        token_names=policy.builder.token_names,
    )
    if (
        {c.role: c.action_id for c in candidates} != record.candidate_actions
        or recommendation.action_id != record.original_recommendation
    ):
        raise ValueError("recomputed policy candidates differ from capture")
    return record
