"""Scalable exact differential verification for the PyTorch simulator.

The Python simulator is always the oracle.  This module deliberately checks
more than the mutable battle object: policy masks, both observation formats,
reward outputs, outcomes, and all RNG state are compared at every decision.
It also reports how many requested ticks were actually executed by tensor
kernels, so a fail-closed Python fallback cannot be presented as PyTorch
parity evidence.

The module is executable without project-script installation::

    python -m clasher.torch_sim.differential episode --seeds 1:8
    python -m clasher.torch_sim.differential manifest --cards-per-owner 1 --shards 8 --shard 0
    python -m clasher.torch_sim.differential crowded --seeds 1,2,3 --ticks 400
"""

from __future__ import annotations

import argparse
import json
import random
from collections import deque
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from itertools import islice
from pathlib import Path
from typing import Any, Protocol, TypeVar, cast

import numpy as np

from clasher.arena import Position
from clasher.battle import STANDARD_MATCH_TICKS, BattleState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.deck_pool import load_deck_pool, unique_cards_from_decks
from clasher.rl.obs_cv import CvObservationBuilder
from clasher.rl.reward_model import objective_potential_p0
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.structured_obs import StructuredObservationBuilder

from .diagnostics import StateDivergence, TorchParityError, battle_snapshot
from .executor import SimulatorBackend, TorchBattleExecutor

_T = TypeVar("_T")


def _qualified_type(value: Any) -> str:
    return f"{type(value).__module__}.{type(value).__qualname__}"


def _mismatch(path: str, expected: Any, actual: Any) -> StateDivergence:
    return StateDivergence(
        path=path,
        expected=expected,
        actual=actual,
        expected_type=_qualified_type(expected),
        actual_type=_qualified_type(actual),
    )


def exact_first_divergence(
    expected: Any,
    actual: Any,
    *,
    path: str = "verification",
) -> StateDivergence | None:
    """Find the first exact value, shape, dtype, or scalar-kind mismatch.

    Unlike a digest-only comparison, this routine identifies the first array
    element that changed.  Unlike ``numpy.array_equal`` alone, it treats dtype
    and Python/NumPy scalar kinds as contract-bearing state.
    """

    if type(expected) is not type(actual):
        return _mismatch(path, expected, actual)

    if isinstance(expected, np.ndarray):
        actual_array = cast(np.ndarray, actual)
        if expected.dtype != actual_array.dtype:
            return _mismatch(f"{path}.dtype", expected.dtype, actual_array.dtype)
        if expected.shape != actual_array.shape:
            return _mismatch(f"{path}.shape", expected.shape, actual_array.shape)
        if expected.size == 0:
            return None
        equal = np.equal(expected, actual_array)
        if np.issubdtype(expected.dtype, np.inexact):
            equal = equal | (np.isnan(expected) & np.isnan(actual_array))
        if bool(np.all(equal)):
            return None
        flat_index = int(np.flatnonzero(~equal.reshape(-1))[0])
        array_index = tuple(
            int(part) for part in np.unravel_index(flat_index, expected.shape)
        )
        return _mismatch(
            f"{path}{''.join(f'[{part}]' for part in array_index)}",
            expected[array_index],
            actual_array[array_index],
        )

    if isinstance(expected, np.generic):
        if bool(expected != actual):
            return _mismatch(path, expected, actual)
        return None

    if is_dataclass(expected) and not isinstance(expected, type):
        for field in fields(expected):
            mismatch = exact_first_divergence(
                getattr(expected, field.name),
                getattr(actual, field.name),
                path=f"{path}.{field.name}",
            )
            if mismatch is not None:
                return mismatch
        return None

    if isinstance(expected, Mapping):
        actual_mapping = cast(Mapping[Any, Any], actual)
        expected_keys = tuple(expected)
        actual_keys = tuple(actual_mapping)
        if expected_keys != actual_keys:
            return _mismatch(f"{path}.keys", expected_keys, actual_keys)
        for key in expected_keys:
            mismatch = exact_first_divergence(
                expected[key], actual_mapping[key], path=f"{path}[{key!r}]"
            )
            if mismatch is not None:
                return mismatch
        return None

    if isinstance(expected, (tuple, list, deque)):
        actual_sequence = cast(Sequence[Any], actual)
        if len(expected) != len(actual_sequence):
            return _mismatch(f"{path}.length", len(expected), len(actual_sequence))
        for index, (left, right) in enumerate(zip(expected, actual_sequence)):
            mismatch = exact_first_divergence(left, right, path=f"{path}[{index}]")
            if mismatch is not None:
                return mismatch
        return None

    if expected != actual:
        return _mismatch(path, expected, actual)
    return None


@dataclass(frozen=True)
class CoverageRequirement:
    """Minimum real tensor execution required for a verification claim."""

    min_tensor_ticks: int = 1
    min_tensor_fraction: float = 0.0
    max_unsupported_fallbacks: int | None = None
    reject_fallback_only: bool = True

    def __post_init__(self) -> None:
        if self.min_tensor_ticks < 0:
            raise ValueError("min_tensor_ticks must be non-negative")
        if not 0.0 <= self.min_tensor_fraction <= 1.0:
            raise ValueError("min_tensor_fraction must be in [0, 1]")
        if (
            self.max_unsupported_fallbacks is not None
            and self.max_unsupported_fallbacks < 0
        ):
            raise ValueError("max_unsupported_fallbacks must be non-negative")


@dataclass(frozen=True)
class CoverageEvidence:
    executed_ticks: int
    tensor_ticks: int
    python_ticks: int
    unsupported_fallbacks: int
    shadow_checks: int
    shadow_mismatches: int
    tensor_fraction: float
    fallback_only: bool
    accepted: bool
    rejection_reasons: tuple[str, ...]


def evaluate_coverage(
    *,
    executed_ticks: int,
    metrics: Mapping[str, float],
    requirement: CoverageRequirement,
) -> CoverageEvidence:
    """Convert executor counters into auditable tensor coverage evidence."""

    tensor_ticks = int(metrics.get("tensor_ticks", 0.0))
    python_ticks = int(metrics.get("python_ticks", 0.0))
    fallbacks = int(metrics.get("unsupported_fallbacks", 0.0))
    shadow_checks = int(metrics.get("shadow_checks", 0.0))
    shadow_mismatches = int(metrics.get("shadow_mismatches", 0.0))
    fraction = tensor_ticks / max(1, executed_ticks)
    fallback_only = executed_ticks > 0 and tensor_ticks == 0
    reasons: list[str] = []
    if requirement.reject_fallback_only and fallback_only:
        reasons.append("all requested ticks used the Python fallback")
    if tensor_ticks < requirement.min_tensor_ticks:
        reasons.append(
            f"tensor ticks {tensor_ticks} < required {requirement.min_tensor_ticks}"
        )
    if fraction < requirement.min_tensor_fraction:
        reasons.append(
            f"tensor fraction {fraction:.6f} < required "
            f"{requirement.min_tensor_fraction:.6f}"
        )
    if (
        requirement.max_unsupported_fallbacks is not None
        and fallbacks > requirement.max_unsupported_fallbacks
    ):
        reasons.append(
            f"unsupported fallbacks {fallbacks} > allowed "
            f"{requirement.max_unsupported_fallbacks}"
        )
    if shadow_mismatches:
        reasons.append(f"executor reported {shadow_mismatches} shadow mismatches")
    return CoverageEvidence(
        executed_ticks=executed_ticks,
        tensor_ticks=tensor_ticks,
        python_ticks=python_ticks,
        unsupported_fallbacks=fallbacks,
        shadow_checks=shadow_checks,
        shadow_mismatches=shadow_mismatches,
        tensor_fraction=fraction,
        fallback_only=fallback_only,
        accepted=not reasons,
        rejection_reasons=tuple(reasons),
    )


@dataclass(frozen=True)
class ActionRecord:
    decision: int
    tick: int
    player0: int
    player1: int


@dataclass(frozen=True)
class DifferentialDivergence:
    seed: int
    episode: int
    decision: int
    tick: int
    phase: str
    actions: tuple[tuple[int, int], ...]
    mismatch: StateDivergence

    def __str__(self) -> str:
        action_text = ", ".join(
            f"p{player}={action}" for player, action in self.actions
        )
        return (
            f"seed={self.seed} episode={self.episode} decision={self.decision} "
            f"tick={self.tick} phase={self.phase} actions=[{action_text}]: "
            f"{self.mismatch}"
        )


@dataclass(frozen=True)
class VerificationReport:
    seed: int
    backend: str
    decisions: int
    complete_episode: bool
    winner: int | None
    final_tick: int
    parity_passed: bool
    coverage: CoverageEvidence
    divergence: DifferentialDivergence | None
    actions: tuple[ActionRecord, ...]

    @property
    def claim_passed(self) -> bool:
        return self.parity_passed and self.complete_episode and self.coverage.accepted


@dataclass(frozen=True)
class ActionContext:
    seed: int
    decision: int
    tick: int
    masks: Mapping[int, np.ndarray]
    no_op_action: int


class ActionProvider(Protocol):
    def __call__(self, context: ActionContext) -> Mapping[int, int]: ...


@dataclass(frozen=True)
class DifferentialConfig:
    backend: SimulatorBackend | str = SimulatorBackend.PYTORCH_SHADOW
    decks_path: str | Path = "decks.json"
    decision_interval_ticks: int = 8
    max_ticks: int = STANDARD_MATCH_TICKS
    mirror_match: bool = False
    canonical_perspective: bool = True
    compare_structured_observations: bool = True
    device: str = "cpu"
    coverage: CoverageRequirement = CoverageRequirement()

    def __post_init__(self) -> None:
        object.__setattr__(self, "backend", SimulatorBackend(self.backend))
        if self.decision_interval_ticks <= 0:
            raise ValueError("decision_interval_ticks must be positive")
        if self.max_ticks <= 0:
            raise ValueError("max_ticks must be positive")


def _environment_snapshot(
    env: SelfPlayBattleEnv,
    *,
    include_structured: bool,
) -> dict[str, Any]:
    assert env.battle is not None
    masks = tuple(env.get_action_mask(player) for player in (0, 1))
    cv = tuple(env.get_observation(player) for player in (0, 1))
    structured = (
        tuple(env.get_structured_observation(player) for player in (0, 1))
        if include_structured
        else ()
    )
    return {
        "battle": battle_snapshot(env.battle),
        "env_rng_state": env.rng.getstate(),
        "numpy_rng_state": env.np_rng.bit_generator.state,
        "action_masks": masks,
        "cv_observations": cv,
        "structured_observations": structured,
        "objective_potential_p0": objective_potential_p0(env.battle),
        "outcome": (
            env.battle.game_over,
            env.battle.winner,
            env.battle.tick,
            env.battle.get_crown_count(0),
            env.battle.get_crown_count(1),
        ),
    }


def _step_snapshot(step_result: tuple[Any, Any, Any]) -> dict[str, Any]:
    rewards, done, info = step_result
    return {"rewards": rewards, "done": done, "step_info": info}


class DifferentialHarness:
    """Lockstep Python-oracle versus candidate-backend verifier."""

    def __init__(self, config: DifferentialConfig = DifferentialConfig()) -> None:
        self.config = config

    def _make_env(self, *, seed: int, backend: SimulatorBackend) -> SelfPlayBattleEnv:
        env = SelfPlayBattleEnv(
            decision_interval_ticks=self.config.decision_interval_ticks,
            max_ticks=self.config.max_ticks,
            decks_path=self.config.decks_path,
            seed=seed,
            mirror_match=self.config.mirror_match,
            canonical_perspective=self.config.canonical_perspective,
            engine_fast_path="off",
            simulation_backend=backend.value,
            # Route Python through the ordinary tick loop too, so coverage and
            # state comparisons use identical decision boundaries.
            idle_fast_forward=False,
        )
        env.reset(seed=seed)
        if backend is not SimulatorBackend.PYTHON:
            env._simulator = TorchBattleExecutor(backend, device=self.config.device)
        return env

    @staticmethod
    def _divergence(
        *,
        seed: int,
        decision: int,
        tick: int,
        phase: str,
        actions: Mapping[int, int] | None,
        mismatch: StateDivergence,
    ) -> DifferentialDivergence:
        return DifferentialDivergence(
            seed=seed,
            episode=0,
            decision=decision,
            tick=tick,
            phase=phase,
            actions=tuple(sorted((actions or {}).items())),
            mismatch=mismatch,
        )

    def run_episode(
        self,
        seed: int,
        *,
        action_provider: ActionProvider | None = None,
        max_decisions: int | None = None,
    ) -> VerificationReport:
        """Run one complete seeded episode, returning first-divergence detail."""

        oracle = self._make_env(seed=seed, backend=SimulatorBackend.PYTHON)
        candidate = self._make_env(
            seed=seed, backend=cast(SimulatorBackend, self.config.backend)
        )
        action_rng = np.random.default_rng(seed + 1_000_003)
        trace: list[ActionRecord] = []
        divergence: DifferentialDivergence | None = None
        decisions = 0
        executed_ticks = 0
        done = False

        def random_actions(context: ActionContext) -> Mapping[int, int]:
            result: dict[int, int] = {}
            for player_id in (0, 1):
                legal = np.flatnonzero(context.masks[player_id])
                result[player_id] = (
                    int(action_rng.choice(legal))
                    if legal.size
                    else context.no_op_action
                )
            return result

        select_actions = action_provider or random_actions

        while not done:
            assert oracle.battle is not None
            assert candidate.battle is not None
            tick = oracle.battle.tick
            before_oracle = _environment_snapshot(
                oracle,
                include_structured=self.config.compare_structured_observations,
            )
            before_candidate = _environment_snapshot(
                candidate,
                include_structured=self.config.compare_structured_observations,
            )
            mismatch = exact_first_divergence(
                before_oracle, before_candidate, path="pre_step"
            )
            if mismatch is not None:
                divergence = self._divergence(
                    seed=seed,
                    decision=decisions,
                    tick=tick,
                    phase="pre_step",
                    actions=None,
                    mismatch=mismatch,
                )
                break

            masks = cast(tuple[np.ndarray, np.ndarray], before_oracle["action_masks"])
            context = ActionContext(
                seed=seed,
                decision=decisions,
                tick=tick,
                masks={0: masks[0], 1: masks[1]},
                no_op_action=oracle.action_space.no_op_action,
            )
            chosen = dict(select_actions(context))
            actions = {
                0: int(chosen.get(0, oracle.action_space.no_op_action)),
                1: int(chosen.get(1, oracle.action_space.no_op_action)),
            }
            trace.append(
                ActionRecord(
                    decision=decisions,
                    tick=tick,
                    player0=actions[0],
                    player1=actions[1],
                )
            )

            oracle_result = oracle.step(
                actions,
                pre_action_masks={0: masks[0], 1: masks[1]},
            )
            try:
                candidate_result = candidate.step(
                    actions,
                    pre_action_masks={0: masks[0].copy(), 1: masks[1].copy()},
                )
            except TorchParityError as exc:
                decisions += 1
                executed_ticks += int(oracle_result[2].ticks_advanced)
                divergence = self._divergence(
                    seed=seed,
                    decision=decisions - 1,
                    tick=tick,
                    phase="tensor_shadow",
                    actions=actions,
                    mismatch=exc.divergence,
                )
                break
            decisions += 1
            executed_ticks += int(oracle_result[2].ticks_advanced)

            mismatch = exact_first_divergence(
                _step_snapshot(oracle_result),
                _step_snapshot(candidate_result),
                path="step_result",
            )
            if mismatch is None:
                mismatch = exact_first_divergence(
                    _environment_snapshot(
                        oracle,
                        include_structured=self.config.compare_structured_observations,
                    ),
                    _environment_snapshot(
                        candidate,
                        include_structured=self.config.compare_structured_observations,
                    ),
                    path="post_step",
                )
            if mismatch is not None:
                divergence = self._divergence(
                    seed=seed,
                    decision=decisions - 1,
                    tick=tick,
                    phase="post_step",
                    actions=actions,
                    mismatch=mismatch,
                )
                break

            done = bool(oracle_result[1])
            if max_decisions is not None and decisions >= max_decisions and not done:
                break

        metrics = candidate.simulator_backend_metrics()
        coverage = evaluate_coverage(
            executed_ticks=executed_ticks,
            metrics=metrics,
            requirement=self.config.coverage,
        )
        assert oracle.battle is not None
        return VerificationReport(
            seed=seed,
            backend=cast(SimulatorBackend, self.config.backend).value,
            decisions=decisions,
            complete_episode=done and divergence is None,
            winner=oracle.battle.winner,
            final_tick=oracle.battle.tick,
            parity_passed=divergence is None,
            coverage=coverage,
            divergence=divergence,
            actions=tuple(trace),
        )

    def run_seeds(
        self,
        seeds: Sequence[int],
        *,
        action_provider: ActionProvider | None = None,
        max_decisions: int | None = None,
    ) -> tuple[VerificationReport, ...]:
        return tuple(
            self.run_episode(
                seed,
                action_provider=action_provider,
                max_decisions=max_decisions,
            )
            for seed in seeds
        )


@dataclass(frozen=True)
class InteractionManifest:
    """One exhaustive interaction with one or two cards per opposing owner."""

    ordinal: int
    cards_per_owner: int
    player0_cards: tuple[str, ...]
    player1_cards: tuple[str, ...]

    @property
    def name(self) -> str:
        left = "+".join(self.player0_cards)
        right = "+".join(self.player1_cards)
        return f"{self.cards_per_owner}-card-per-owner:{left}:vs:{right}"


def _combinations_with_replacement(
    values: Sequence[_T], count: int
) -> Iterator[tuple[_T, ...]]:
    if count == 0:
        yield ()
        return
    for index, value in enumerate(values):
        for suffix in _combinations_with_replacement(values[index:], count - 1):
            yield (value, *suffix)


def interaction_manifest_count(card_count: int, cards_per_owner: int) -> int:
    """Return exact manifest cardinality without materializing it."""

    if card_count < 1:
        raise ValueError("card_count must be positive")
    if cards_per_owner not in {1, 2}:
        raise ValueError("cards_per_owner must be 1 or 2")
    owner_loadout_count = (
        card_count if cards_per_owner == 1 else card_count * (card_count + 1) // 2
    )
    return owner_loadout_count * owner_loadout_count


def iter_interaction_manifests(
    card_names: Sequence[str],
    *,
    cards_per_owner: int,
    shard_index: int = 0,
    shard_count: int = 1,
) -> Iterator[InteractionManifest]:
    """Yield the complete deterministic manifest, optionally index-sharded.

    Cards controlled by one owner are combinations with replacement:
    duplicate-card interactions are included, while permutations within one
    side are not redundantly repeated. Player sides remain ordered because
    perspective and deployment territory are behaviorally distinct. Two cards
    per owner is not a true four-controller team 2v2 match.
    """

    if cards_per_owner not in {1, 2}:
        raise ValueError("cards_per_owner must be 1 or 2")
    if shard_count < 1 or not 0 <= shard_index < shard_count:
        raise ValueError("shard_index must be in [0, shard_count)")
    cards = tuple(sorted(set(card_names)))
    if not cards:
        raise ValueError("at least one card is required")
    owner_loadouts = tuple(_combinations_with_replacement(cards, cards_per_owner))
    ordinal = 0
    for player0_cards in owner_loadouts:
        for player1_cards in owner_loadouts:
            if ordinal % shard_count == shard_index:
                yield InteractionManifest(
                    ordinal=ordinal,
                    cards_per_owner=cards_per_owner,
                    player0_cards=player0_cards,
                    player1_cards=player1_cards,
                )
            ordinal += 1


@dataclass(frozen=True)
class FixtureVerificationReport:
    seed: int
    name: str
    backend: str
    requested_ticks: int
    advanced_ticks: int
    parity_passed: bool
    coverage: CoverageEvidence
    divergence: DifferentialDivergence | None

    @property
    def claim_passed(self) -> bool:
        return self.parity_passed and self.coverage.accepted


class BattleExternalSurfaces:
    """Reusable builders for high-volume direct battle-fixture comparisons."""

    def __init__(
        self,
        *,
        decks_path: str | Path = "decks.json",
        compare_structured_observations: bool = True,
    ) -> None:
        self.action_space = DiscreteTileActionSpace(canonical_perspective=True)
        self.cv_builder = CvObservationBuilder(decks_path=decks_path)
        self.structured_builder = (
            StructuredObservationBuilder(decks_path=decks_path)
            if compare_structured_observations
            else None
        )

    def snapshot(self, battle: BattleState) -> dict[str, Any]:
        return {
            "battle": battle_snapshot(battle),
            "action_masks": tuple(
                self.action_space.legal_action_mask(battle, player, fast_path=False)
                for player in (0, 1)
            ),
            "cv_observations": tuple(
                self.cv_builder.build(battle, player) for player in (0, 1)
            ),
            "structured_observations": (
                tuple(
                    self.structured_builder.build(battle, player) for player in (0, 1)
                )
                if self.structured_builder is not None
                else ()
            ),
            "reward_potential": objective_potential_p0(battle),
            "outcome": (
                battle.game_over,
                battle.winner,
                battle.get_crown_count(0),
                battle.get_crown_count(1),
            ),
        }


def verify_battle_fixture(
    battle: BattleState,
    *,
    seed: int,
    name: str,
    ticks: int,
    backend: SimulatorBackend | str = SimulatorBackend.PYTORCH_SHADOW,
    device: str = "cpu",
    decks_path: str | Path = "decks.json",
    compare_structured_observations: bool = True,
    coverage_requirement: CoverageRequirement = CoverageRequirement(),
    external_surfaces: BattleExternalSurfaces | None = None,
) -> FixtureVerificationReport:
    """Verify an arbitrary crowded/targeted battle through a tick window."""

    candidate_backend = SimulatorBackend(backend)
    oracle = battle.clone()
    candidate = battle.clone()
    expected_advanced = oracle.step_logic_ticks(ticks)
    executor = TorchBattleExecutor(candidate_backend, device=device)
    actual_advanced = executor.step_logic_ticks(candidate, ticks)
    surfaces = external_surfaces or BattleExternalSurfaces(
        decks_path=decks_path,
        compare_structured_observations=compare_structured_observations,
    )
    mismatch = exact_first_divergence(
        {
            "advanced": expected_advanced,
            "externals": surfaces.snapshot(oracle),
        },
        {
            "advanced": actual_advanced,
            "externals": surfaces.snapshot(candidate),
        },
        path="fixture",
    )
    divergence = (
        None
        if mismatch is None
        else DifferentialDivergence(
            seed=seed,
            episode=0,
            decision=0,
            tick=battle.tick,
            phase="tick_window",
            actions=(),
            mismatch=mismatch,
        )
    )
    coverage = evaluate_coverage(
        executed_ticks=expected_advanced,
        metrics=executor.metrics_dict(),
        requirement=coverage_requirement,
    )
    return FixtureVerificationReport(
        seed=seed,
        name=name,
        backend=candidate_backend.value,
        requested_ticks=max(0, int(ticks)),
        advanced_ticks=expected_advanced,
        parity_passed=mismatch is None,
        coverage=coverage,
        divergence=divergence,
    )


def build_interaction_fixture(
    manifest: InteractionManifest,
    *,
    seed: int,
) -> BattleState:
    """Build a public-action fixture for one exhaustive card manifest."""

    battle = BattleState(rng=random.Random(seed))
    x_positions = (4.0, 14.0)
    y_positions = {0: (14.0, 12.0), 1: (18.0, 20.0)}
    for player_id, cards in (
        (0, manifest.player0_cards),
        (1, manifest.player1_cards),
    ):
        for slot, card_name in enumerate(cards):
            player = battle.players[player_id]
            player.elixir = player.max_elixir
            player.hand = [card_name, None, None, None]
            player.deck = [card_name]
            player.cycle_queue = deque()
            position = Position(x_positions[slot], y_positions[player_id][slot])
            if not battle.deploy_card(player_id, card_name, position):
                raise RuntimeError(
                    f"manifest {manifest.name} could not deploy p{player_id} "
                    f"card {card_name} at {position}"
                )
    return battle


def build_randomized_crowded_fixture(
    *,
    seed: int,
    decks_path: str | Path = "decks.json",
    deployment_rounds: int = 24,
    interdeployment_ticks: int = 1,
) -> BattleState:
    """Create a reproducible high-object-count state through legal actions."""

    if deployment_rounds < 1:
        raise ValueError("deployment_rounds must be positive")
    env = SelfPlayBattleEnv(
        decision_interval_ticks=max(1, interdeployment_ticks),
        max_ticks=STANDARD_MATCH_TICKS,
        decks_path=decks_path,
        seed=seed,
        simulation_backend="python",
        idle_fast_forward=False,
    )
    env.reset(seed=seed)
    assert env.battle is not None
    action_rng = np.random.default_rng(seed + 7_919)
    for _ in range(deployment_rounds):
        actions: dict[int, int] = {}
        for player_id in (0, 1):
            env.battle.players[player_id].elixir = env.battle.players[
                player_id
            ].max_elixir
            mask = env.get_action_mask(player_id).copy()
            mask[env.action_space.no_op_action] = False
            mask[env.action_space.ability_action] = False
            legal = np.flatnonzero(mask)
            actions[player_id] = (
                int(action_rng.choice(legal))
                if legal.size
                else env.action_space.no_op_action
            )
        env.step(actions)
        if env.battle.game_over:
            break
    return env.battle.clone()


def enabled_cards(decks_path: str | Path = "decks.json") -> tuple[str, ...]:
    return tuple(unique_cards_from_decks(load_deck_pool(decks_path)))


def _parse_seeds(value: str) -> tuple[int, ...]:
    seeds: list[int] = []
    for part in value.split(","):
        token = part.strip()
        if not token:
            continue
        if ":" in token:
            start_text, stop_text = token.split(":", 1)
            seeds.extend(range(int(start_text), int(stop_text)))
        else:
            seeds.append(int(token))
    if not seeds:
        raise argparse.ArgumentTypeError("at least one seed is required")
    return tuple(seeds)


def _jsonable(value: Any) -> Any:
    if isinstance(value, StateDivergence):
        return {
            "path": value.path,
            "expected": repr(value.expected),
            "actual": repr(value.actual),
            "expected_type": value.expected_type,
            "actual_type": value.actual_type,
        }
    if is_dataclass(value) and not isinstance(value, type):
        payload = {
            field.name: _jsonable(getattr(value, field.name)) for field in fields(value)
        }
        if isinstance(value, (VerificationReport, FixtureVerificationReport)):
            payload["claim_passed"] = value.claim_passed
        if isinstance(value, InteractionManifest):
            payload["name"] = value.name
        return payload
    if isinstance(value, Mapping):
        return {str(key): _jsonable(child) for key, child in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(child) for child in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return value


def _coverage_from_args(args: argparse.Namespace) -> CoverageRequirement:
    return CoverageRequirement(
        min_tensor_ticks=args.min_tensor_ticks,
        min_tensor_fraction=args.min_tensor_fraction,
        max_unsupported_fallbacks=args.max_unsupported_fallbacks,
        reject_fallback_only=not args.allow_fallback_only,
    )


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--backend",
        choices=[SimulatorBackend.PYTORCH_SHADOW.value, SimulatorBackend.PYTORCH.value],
        default=SimulatorBackend.PYTORCH_SHADOW.value,
    )
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--min-tensor-ticks", type=int, default=1)
    parser.add_argument("--min-tensor-fraction", type=float, default=0.0)
    parser.add_argument("--max-unsupported-fallbacks", type=int)
    parser.add_argument("--allow-fallback-only", action="store_true")
    parser.add_argument("--skip-structured-observations", action="store_true")
    parser.add_argument(
        "--json-out",
        type=Path,
        help="write JSON (manifest mode streams one JSON object per line)",
    )


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    episode = subparsers.add_parser("episode", help="verify seeded full episodes")
    _add_common_arguments(episode)
    episode.add_argument("--seeds", type=_parse_seeds, default=(1,))
    episode.add_argument("--decision-interval", type=int, default=8)
    episode.add_argument("--max-ticks", type=int, default=STANDARD_MATCH_TICKS)
    episode.add_argument("--max-decisions", type=int)
    episode.add_argument("--mirror-match", action="store_true")
    episode.add_argument(
        "--action-policy", choices=("random", "noop"), default="random"
    )

    manifest = subparsers.add_parser(
        "manifest", help="enumerate or verify exhaustive card interactions"
    )
    _add_common_arguments(manifest)
    manifest.add_argument("--cards-per-owner", type=int, choices=(1, 2), required=True)
    manifest.add_argument("--shards", type=int, default=1)
    manifest.add_argument("--shard", type=int, default=0)
    manifest.add_argument("--limit", type=int)
    manifest.add_argument("--ticks", type=int, default=400)
    manifest.add_argument("--seed-base", type=int, default=10_000)
    manifest.add_argument("--list-only", action="store_true")

    crowded = subparsers.add_parser("crowded", help="verify randomized crowded states")
    _add_common_arguments(crowded)
    crowded.add_argument("--seeds", type=_parse_seeds, default=(1,))
    crowded.add_argument("--ticks", type=int, default=400)
    crowded.add_argument("--deployment-rounds", type=int, default=24)
    return parser


def _write_or_print(payload: Any, path: Path | None) -> None:
    rendered = json.dumps(_jsonable(payload), indent=2, sort_keys=True)
    if path is None:
        print(rendered)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered + "\n", encoding="utf-8")
        print(f"wrote={path.resolve()}")


def _stream_manifest_reports(
    reports: Iterator[InteractionManifest | FixtureVerificationReport],
    path: Path | None,
) -> tuple[int, int]:
    """Emit arbitrarily large manifest shards without retaining them in RAM."""

    output = None
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        output = path.open("w", encoding="utf-8")
    processed = 0
    failed = 0
    try:
        for report in reports:
            line = json.dumps(_jsonable(report), sort_keys=True)
            if output is None:
                print(line)
            else:
                output.write(line + "\n")
            processed += 1
            if (
                isinstance(report, FixtureVerificationReport)
                and not report.claim_passed
            ):
                failed += 1
    finally:
        if output is not None:
            output.close()
    if path is not None:
        print(f"wrote_jsonl={path.resolve()}")
    print(f"processed={processed} failed={failed}")
    return processed, failed


def main(argv: Sequence[str] | None = None) -> int:
    args = _argument_parser().parse_args(argv)
    coverage = _coverage_from_args(args)
    compare_structured = not args.skip_structured_observations

    if args.command == "episode":
        harness = DifferentialHarness(
            DifferentialConfig(
                backend=args.backend,
                decks_path=args.decks_path,
                decision_interval_ticks=args.decision_interval,
                max_ticks=args.max_ticks,
                mirror_match=args.mirror_match,
                compare_structured_observations=compare_structured,
                device=args.device,
                coverage=coverage,
            )
        )
        provider: ActionProvider | None = None
        if args.action_policy == "noop":
            provider = lambda context: {
                0: context.no_op_action,
                1: context.no_op_action,
            }
        reports: tuple[Any, ...] = harness.run_seeds(
            args.seeds,
            action_provider=provider,
            max_decisions=args.max_decisions,
        )
    elif args.command == "manifest":
        cards = enabled_cards(args.decks_path)
        external_surfaces = BattleExternalSurfaces(
            decks_path=args.decks_path,
            compare_structured_observations=compare_structured,
        )
        manifests: Iterator[InteractionManifest] = iter_interaction_manifests(
            cards,
            cards_per_owner=args.cards_per_owner,
            shard_index=args.shard,
            shard_count=args.shards,
        )
        if args.limit is not None:
            manifests = islice(manifests, max(0, args.limit))
        if args.list_only:
            streamed: Iterator[InteractionManifest | FixtureVerificationReport] = (
                manifest for manifest in manifests
            )
        else:
            streamed = (
                verify_battle_fixture(
                    build_interaction_fixture(
                        manifest, seed=args.seed_base + manifest.ordinal
                    ),
                    seed=args.seed_base + manifest.ordinal,
                    name=manifest.name,
                    ticks=args.ticks,
                    backend=args.backend,
                    device=args.device,
                    decks_path=args.decks_path,
                    compare_structured_observations=compare_structured,
                    coverage_requirement=coverage,
                    external_surfaces=external_surfaces,
                )
                for manifest in manifests
            )
        _, failed_count = _stream_manifest_reports(streamed, args.json_out)
        return 1 if failed_count else 0
    else:
        reports = tuple(
            verify_battle_fixture(
                build_randomized_crowded_fixture(
                    seed=seed,
                    decks_path=args.decks_path,
                    deployment_rounds=args.deployment_rounds,
                ),
                seed=seed,
                name=f"crowded:{seed}",
                ticks=args.ticks,
                backend=args.backend,
                device=args.device,
                decks_path=args.decks_path,
                compare_structured_observations=compare_structured,
                coverage_requirement=coverage,
            )
            for seed in args.seeds
        )

    _write_or_print(reports, args.json_out)
    failed = [
        report
        for report in reports
        if hasattr(report, "claim_passed") and not report.claim_passed
    ]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
