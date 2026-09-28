"""Fit localized guards that preserve a previously retained dense residual.

Unlike a zero-delta guard, each guard stores the complete repair residual from
the requested reference policy at its prototype state.  This matters after a
dense adapter has already been promoted: suppressing the whole dense adapter
would otherwise erase the earlier retained improvement along with the new
regression.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.paths import decks_path as resolve_decks_path
from clasher.rl.eval import LoadedPolicy, load_policy_checkpoint
from clasher.rl.model import ClasherPolicy
from clasher.rl.reward_model import DEFENSE_V2
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import StrategyBot
from clasher.rl.train_recurrent import _stack_step_inputs, maybe_silence_stdio


@dataclass(frozen=True)
class ReplayCase:
    reference: str
    seed: int
    player: int
    strategy: str | None = None
    opponent_reference: str | None = None


@dataclass
class ReplayResult:
    case: ReplayCase
    matched: bool
    tick: int
    decisions: int
    candidate_action: int | None = None
    desired_action: int | None = None
    outcome: str | None = None
    crowns: tuple[int, int] | None = None
    repair_features: torch.Tensor | None = None
    desired_repair: torch.Tensor | None = None

    def summary(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "case": [
                self.case.seed,
                self.case.player,
                self.case.strategy,
                self.case.opponent_reference,
            ],
            "reference": self.case.reference,
            "matched": self.matched,
            "tick": self.tick,
            "decisions": self.decisions,
        }
        if self.matched:
            result.update(outcome=self.outcome, crowns=self.crowns)
        else:
            result.update(
                candidate_action=self.candidate_action,
                desired_action=self.desired_action,
            )
        return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--decks-path", type=Path)
    parser.add_argument("--max-iterations", type=int, default=12)
    parser.add_argument("--torch-threads", type=int, default=2)
    parser.add_argument("--quiet-engine", action="store_true")
    return parser.parse_args()


def _load_spec(path: Path) -> tuple[dict[str, Path], list[ReplayCase]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    references: dict[str, Path] = {}
    cases: list[ReplayCase] = []
    if "include" in payload:
        include_path = (path.parent / payload["include"]).resolve()
        references, cases = _load_spec(include_path)
    references.update(
        {name: Path(value) for name, value in payload.get("references", {}).items()}
    )
    cases.extend(
        ReplayCase(
            reference=str(item["reference"]),
            seed=int(item["seed"]),
            player=int(item["player"]),
            strategy=item.get("strategy"),
            opponent_reference=item.get("opponent_reference"),
        )
        for item in payload.get("cases", [])
    )
    unknown = sorted({case.reference for case in cases} - references.keys())
    unknown.extend(
        sorted(
            {
                case.opponent_reference
                for case in cases
                if case.opponent_reference is not None
            }
            - references.keys()
        )
    )
    if unknown:
        raise ValueError(f"cases use unknown references: {unknown}")
    if any(
        case.strategy is not None and case.opponent_reference is not None
        for case in cases
    ):
        raise ValueError("a case cannot use both strategy and policy opponents")
    return references, cases


def _new_env(decks_path: Path, seed: int) -> SelfPlayBattleEnv:
    return SelfPlayBattleEnv(
        decision_interval_ticks=8,
        max_ticks=6000,
        decks_path=decks_path,
        seed=seed,
        mirror_match=False,
        canonical_perspective=True,
        reward_profile=DEFENSE_V2,
    )


@torch.no_grad()
def _policy_decision(
    policy: LoadedPolicy,
    env: SelfPlayBattleEnv,
    player: int,
    state: tuple[torch.Tensor, torch.Tensor],
    previous_action: int,
    previous_reward: float,
    episode_start: bool,
) -> tuple[int, tuple[torch.Tensor, torch.Tensor], torch.Tensor]:
    assert env.battle is not None
    observation = policy.builder.build(env.battle, player)
    mask = env.get_action_mask(player)[None, :]
    inputs = _stack_step_inputs(
        [observation],
        mask,
        np.asarray([previous_action], dtype=np.int64),
        np.asarray([previous_reward], dtype=np.float32),
        np.asarray([episode_start], dtype=np.bool_),
        torch.device("cpu"),
    )
    action, _, _, next_state, output = policy.model.act(
        inputs,
        state,
        deterministic=True,
    )
    if output.repair_features is None:
        raise RuntimeError("candidate did not expose repair features")
    return (
        int(action[0, 0]),
        next_state,
        output.repair_features[0, 0].detach().cpu().clone(),
    )


@torch.no_grad()
def _effective_repair(model: ClasherPolicy, features: torch.Tensor) -> torch.Tensor:
    inputs = features[None, :]
    dense = model.repair_adapter(inputs) if model.repair_adapter is not None else None
    prototype = model.prototype_repair_adapter
    if prototype is None:
        if dense is None:
            raise RuntimeError("reference has no repair adapter")
        return dense[0].detach().cpu()
    weights = prototype.activation_weights(inputs)
    prototype_delta = prototype(inputs)
    if dense is not None:
        dense = dense * (1.0 - weights.amax(dim=-1, keepdim=True))
        prototype_delta = prototype_delta + dense
    return prototype_delta[0].detach().cpu()


@torch.no_grad()
def _replay(
    candidate: LoadedPolicy,
    reference: LoadedPolicy,
    opponent_policy: LoadedPolicy | None,
    case: ReplayCase,
    decks_path: Path,
    quiet_engine: bool,
) -> ReplayResult:
    env = _new_env(decks_path, case.seed)
    with maybe_silence_stdio(quiet_engine):
        env.reset(seed=case.seed)
    rng = np.random.default_rng(case.seed + 91_117)
    candidate_state = candidate.model.initial_state(1, device=torch.device("cpu"))
    reference_state = reference.model.initial_state(1, device=torch.device("cpu"))
    previous_action = env.action_space.no_op_action
    previous_reward = 0.0
    episode_start = True
    decisions = 0
    opponent = StrategyBot(case.strategy) if case.strategy is not None else None
    other_player = 1 - case.player
    opponent_state = (
        opponent_policy.model.initial_state(1, device=torch.device("cpu"))
        if opponent_policy is not None
        else None
    )
    opponent_previous_action = env.action_space.no_op_action
    opponent_previous_reward = 0.0

    while True:
        candidate_action, candidate_state, candidate_features = _policy_decision(
            candidate,
            env,
            case.player,
            candidate_state,
            previous_action,
            previous_reward,
            episode_start,
        )
        reference_action, reference_state, reference_features = _policy_decision(
            reference,
            env,
            case.player,
            reference_state,
            previous_action,
            previous_reward,
            episode_start,
        )
        decisions += 1
        if candidate_action != reference_action:
            feature_error = float((candidate_features - reference_features).abs().max())
            if feature_error > 1e-6:
                raise RuntimeError(
                    f"base feature mismatch before action divergence: {feature_error}"
                )
            return ReplayResult(
                case=case,
                matched=False,
                tick=int(env.battle.tick),
                decisions=decisions,
                candidate_action=candidate_action,
                desired_action=reference_action,
                repair_features=candidate_features,
                desired_repair=_effective_repair(reference.model, reference_features),
            )

        other_mask = env.get_action_mask(other_player)
        if opponent_policy is not None:
            assert opponent_state is not None
            other_action, opponent_state, _ = _policy_decision(
                opponent_policy,
                env,
                other_player,
                opponent_state,
                opponent_previous_action,
                opponent_previous_reward,
                episode_start,
            )
        elif opponent is None:
            legal = np.flatnonzero(other_mask)
            other_action = (
                int(rng.choice(legal)) if legal.size else env.action_space.no_op_action
            )
        else:
            other_action = opponent.select_action(
                env,
                other_player,
                action_mask=other_mask,
            )
        with maybe_silence_stdio(quiet_engine):
            rewards, done, _ = env.step(
                {case.player: candidate_action, other_player: other_action},
                pre_action_masks={
                    case.player: env.get_action_mask(case.player),
                    other_player: other_mask,
                },
            )
        previous_action = candidate_action
        previous_reward = float(rewards[case.player])
        opponent_previous_action = other_action
        opponent_previous_reward = float(rewards[other_player])
        episode_start = False
        if done:
            assert env.battle is not None
            candidate_crowns = env.battle.get_crown_count(case.player)
            opponent_crowns = env.battle.get_crown_count(other_player)
            if env.battle.winner is None:
                outcome = "draw"
            elif env.battle.winner == case.player:
                outcome = "win"
            else:
                outcome = "loss"
            return ReplayResult(
                case=case,
                matched=True,
                tick=int(env.battle.tick),
                decisions=decisions,
                outcome=outcome,
                crowns=(candidate_crowns, opponent_crowns),
            )


def _expand_with_guards(
    policy: LoadedPolicy,
    failures: list[ReplayResult],
) -> None:
    old_model = policy.model
    old_adapter = old_model.prototype_repair_adapter
    if old_adapter is None:
        raise RuntimeError("candidate requires a prototype repair adapter")
    old_config = old_model.config
    prefix = old_config.repair_prototype_frozen_prefix_count
    count = old_config.repair_prototype_count
    additions = len(failures)
    new_config = replace(
        old_config,
        repair_prototype_count=count + additions,
        repair_prototype_frozen_prefix_count=prefix + additions,
    )
    new_model = ClasherPolicy(new_config, policy.builder.card_stat_features)
    old_state = old_model.state_dict()
    shared_state = {
        name: value
        for name, value in old_state.items()
        if not name.startswith("prototype_repair_adapter.")
    }
    incompatible = new_model.load_state_dict(shared_state, strict=False)
    allowed_missing = {
        "prototype_repair_adapter.prototypes",
        "prototype_repair_adapter.deltas",
        "prototype_repair_adapter.linear_gate_weights",
        "prototype_repair_adapter.linear_gate_bias",
    }
    if (
        incompatible.unexpected_keys
        or set(incompatible.missing_keys) != allowed_missing
    ):
        raise RuntimeError(f"unexpected expansion mismatch: {incompatible}")
    new_adapter = new_model.prototype_repair_adapter
    assert new_adapter is not None
    with torch.no_grad():
        new_adapter.prototypes[:prefix].copy_(old_adapter.prototypes[:prefix])
        new_adapter.deltas[:prefix].copy_(old_adapter.deltas[:prefix])
        for offset, failure in enumerate(failures):
            assert failure.repair_features is not None
            assert failure.desired_repair is not None
            row = prefix + offset
            features = failure.repair_features
            current_prototype = old_adapter(features[None, :])[0].detach().cpu()
            new_adapter.prototypes[row].copy_(features)
            new_adapter.deltas[row].copy_(failure.desired_repair - current_prototype)
        new_adapter.prototypes[prefix + additions :].copy_(
            old_adapter.prototypes[prefix:]
        )
        new_adapter.deltas[prefix + additions :].copy_(old_adapter.deltas[prefix:])
        if old_config.repair_prototype_linear_gate_count:
            new_adapter.linear_gate_weights.copy_(old_adapter.linear_gate_weights)
            new_adapter.linear_gate_bias.copy_(old_adapter.linear_gate_bias)
    new_model.eval()
    policy.model = new_model


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    args = _parse_args()
    torch.set_num_threads(args.torch_threads)
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    reference_paths, cases = _load_spec(args.spec)
    candidate = load_policy_checkpoint(
        args.candidate,
        device=torch.device("cpu"),
        decks_path=decks_path,
    )
    references = {
        name: load_policy_checkpoint(
            path,
            device=torch.device("cpu"),
            decks_path=decks_path,
        )
        for name, path in reference_paths.items()
    }
    source_checkpoint = copy.deepcopy(candidate.checkpoint)
    initial_count = candidate.model.config.repair_prototype_count
    history: list[dict[str, Any]] = []

    for iteration in range(args.max_iterations + 1):
        results = [
            _replay(
                candidate,
                references[case.reference],
                (
                    references[case.opponent_reference]
                    if case.opponent_reference is not None
                    else None
                ),
                case,
                decks_path,
                args.quiet_engine,
            )
            for case in cases
        ]
        failures = [result for result in results if not result.matched]
        record = {
            "iteration": iteration,
            "prototype_count": candidate.model.config.repair_prototype_count,
            "failures": len(failures),
            "results": [result.summary() for result in results],
        }
        history.append(record)
        print(json.dumps(record, sort_keys=True), flush=True)
        if not failures:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            output_state = copy.deepcopy(source_checkpoint)
            # Prototype expansion changes a trainable parameter's shape, so the
            # source Adam moments are not safe to restore.  A future trainer
            # resume must intentionally start fresh optimizer state.
            output_state.pop("optimizer_state_dict", None)
            output_state["model_config"] = candidate.model.config.to_dict()
            output_state["model_state_dict"] = candidate.model.state_dict()
            output_state["residual_preserving_safety_guards"] = {
                "source_checkpoint": str(args.candidate.resolve()),
                "spec": str(args.spec.resolve()),
                "new_guard_count": (
                    candidate.model.config.repair_prototype_count - initial_count
                ),
                "optimizer_state_removed": True,
                "history": history,
            }
            torch.save(output_state, args.output)
            manifest = {
                "checkpoint": str(args.output),
                "sha256": _sha256(args.output),
                "new_guard_count": (
                    candidate.model.config.repair_prototype_count - initial_count
                ),
                "total_prototype_count": candidate.model.config.repair_prototype_count,
                "total_strict_prefix_count": (
                    candidate.model.config.repair_prototype_frozen_prefix_count
                ),
                "iterations": iteration,
                "optimizer_state_removed": True,
                "history": history,
            }
            args.manifest.parent.mkdir(parents=True, exist_ok=True)
            args.manifest.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            summary = {key: manifest[key] for key in manifest if key != "history"}
            print(json.dumps(summary, sort_keys=True))
            return
        if iteration == args.max_iterations:
            raise RuntimeError(f"failed to converge with {len(failures)} divergences")
        _expand_with_guards(candidate, failures)


if __name__ == "__main__":
    main()
