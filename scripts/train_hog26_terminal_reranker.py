#!/usr/bin/env python3
"""Train a frozen-policy action reranker from terminal counterfactual probes."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from numpy.typing import NDArray
from torch import Tensor
from torch.nn import functional as F

from clasher.rl.common import NUM_HAND_SLOTS
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.terminal_action_reranker import (
    TerminalActionReranker,
    candidate_action_features,
    guarded_reranker_actions,
)
from scripts.distill_hog26_playgate import sequence_inputs
from scripts.train_hog26_factorized_counterfactual import (
    ROOT_POLICY_INPUT_KEYS,
    file_sha256,
)

PROBE_SCHEMA = "clasher.simple-counterfactual-teacher-probe.v4"
REPORT_SCHEMA = "clasher.hog26.terminal-action-reranker.v1"
THRESHOLDS = (0.0, 0.025, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5)


@dataclass(frozen=True)
class RootExamples:
    names: tuple[str, ...]
    strategies: tuple[str, ...]
    warmups: Tensor
    state_features: Tensor
    action_features: Tensor
    actions: Tensor
    outcomes: Tensor
    returns: Tensor
    parent_indices: Tensor
    fingerprints: frozenset[str]

    @property
    def roots(self) -> int:
        return len(self.names)

    @property
    def candidates(self) -> int:
        return int(self.actions.shape[1])


def _load_policy(payload: dict[str, Any], device: torch.device) -> ClasherPolicy:
    config = PolicyConfig.from_dict(payload["model_config"])
    state = payload["model_state_dict"]
    card_stats = torch.as_tensor(state["actor_encoder.card_stat_features"])
    semantic = state.get("actor_encoder.semantic_card_features")
    if semantic is not None:
        card_stats = torch.cat([card_stats, torch.as_tensor(semantic)], dim=-1)
    model = ClasherPolicy(config, card_stats).to(device)
    model.load_state_dict(state, strict=True)
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    return model


def _exact_confidence_arrays(arrays: dict[str, np.ndarray]) -> None:
    arrays["entity_id_confidence"] = arrays["entity_mask"].astype(np.float32)
    arrays["entity_feature_confidence"] = np.broadcast_to(
        arrays["entity_mask"][..., None], arrays["entity_features"].shape
    ).astype(np.float32, copy=True)
    arrays["hand_id_confidence"] = np.ones(arrays["hand_ids"].shape, np.float32)
    arrays["global_feature_confidence"] = np.ones(
        arrays["global_features"].shape, np.float32
    )


def _root_fingerprint(arrays: dict[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    for key in ROOT_POLICY_INPUT_KEYS:
        value = np.ascontiguousarray(arrays[key][-1])
        digest.update(key.encode())
        digest.update(value.dtype.str.encode())
        digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
        digest.update(value.tobytes())
    return digest.hexdigest()


@torch.no_grad()
def load_probe_examples(
    root: Path,
    *,
    checkpoint_sha256: str,
    model: ClasherPolicy,
    card_features: Tensor,
    policy_device: torch.device,
) -> RootExamples:
    paths = sorted(root.glob("*.json"))
    if not paths:
        raise ValueError(f"probe root contains no JSON files: {root}")
    names: list[str] = []
    strategies: list[str] = []
    warmups: list[int] = []
    states: list[Tensor] = []
    descriptors: list[Tensor] = []
    actions_out: list[Tensor] = []
    outcomes_out: list[Tensor] = []
    returns_out: list[Tensor] = []
    parents: list[int] = []
    fingerprints: set[str] = set()
    expected_candidates: int | None = None
    for path in paths:
        payload = json.loads(path.read_text())
        if payload.get("schema") != PROBE_SCHEMA:
            raise ValueError(f"probe is not terminal-outcome v4: {path}")
        if payload.get("checkpoint_sha256") != checkpoint_sha256:
            raise ValueError(f"probe checkpoint differs from retained parent: {path}")
        rows = payload.get("rows")
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"probe has no candidates: {path}")
        if not bool(payload.get("stop_when_all_terminal")) or not all(
            bool(row.get("terminal")) for row in rows
        ):
            raise ValueError(f"probe candidates are not all terminal: {path}")
        state_path = path.with_suffix(".npz")
        with np.load(state_path, allow_pickle=False) as archive:
            arrays = {
                name: archive[name].copy()
                for name in archive.files
                if name != "metadata_json"
            }
        _exact_confidence_arrays(arrays)
        fingerprint = _root_fingerprint(arrays)
        if fingerprint in fingerprints:
            raise ValueError(f"probe root policy input is duplicated: {path}")
        fingerprints.add(fingerprint)
        input_rows: NDArray[np.int64] = np.arange(
            arrays["entity_ids"].shape[0], dtype=np.int64
        )
        inputs = sequence_inputs(arrays, input_rows, policy_device)
        output = model(inputs, model.initial_state(1, device=policy_device))
        if output.repair_features is None:
            raise ValueError("retained policy emitted no frozen state features")
        root_state = output.repair_features[0, -1]
        hazard = (
            torch.zeros((), device=policy_device)
            if output.play_hazard_logits is None
            else output.play_hazard_logits[0, -1]
        )
        root_state = torch.cat(
            [root_state, output.values[0, -1, None], hazard.reshape(1)], dim=0
        )
        candidate_actions = torch.as_tensor(
            [int(row["action"]) for row in rows],
            dtype=torch.long,
            device=policy_device,
        )
        if not bool(inputs.action_mask[0, -1, candidate_actions].all()):
            raise ValueError(f"probe contains an illegal candidate: {path}")
        parent_matches = torch.nonzero(
            candidate_actions == int(payload["parent_action"]), as_tuple=False
        ).flatten()
        if parent_matches.numel() != 1:
            raise ValueError(f"probe must contain parent action exactly once: {path}")
        desc = candidate_action_features(
            candidate_actions,
            inputs.hand_ids[0, -1, :NUM_HAND_SLOTS],
            output.joint_logits[0, -1],
            card_features,
        )
        candidate_count = len(rows)
        if expected_candidates is None:
            expected_candidates = candidate_count
        elif candidate_count != expected_candidates:
            raise ValueError("probe candidate count changed within a split")
        names.append(path.stem)
        strategies.append(str(payload["opponent_strategy"]))
        warmups.append(int(payload["warmup_steps"]))
        states.append(root_state.float().cpu())
        descriptors.append(desc.float().cpu())
        actions_out.append(candidate_actions.cpu())
        outcomes_out.append(
            torch.tensor(
                [int(row["terminal_outcome"]) for row in rows], dtype=torch.float32
            )
        )
        returns_out.append(
            torch.tensor([float(row["discounted_reward_return"]) for row in rows])
        )
        parents.append(int(parent_matches.item()))
    return RootExamples(
        names=tuple(names),
        strategies=tuple(strategies),
        warmups=torch.tensor(warmups, dtype=torch.long),
        state_features=torch.stack(states),
        action_features=torch.stack(descriptors),
        actions=torch.stack(actions_out),
        outcomes=torch.stack(outcomes_out),
        returns=torch.stack(returns_out),
        parent_indices=torch.tensor(parents, dtype=torch.long),
        fingerprints=frozenset(fingerprints),
    )


def _root_loss(
    outcome_logits: Tensor,
    tie_scores: Tensor,
    outcomes: Tensor,
    returns: Tensor,
) -> tuple[Tensor, dict[str, float]]:
    targets = (outcomes + 1.0) * 0.5
    classification = F.binary_cross_entropy_with_logits(outcome_logits, targets)
    true_diff = outcomes.unsqueeze(-1) - outcomes.unsqueeze(-2)
    predicted_diff = outcome_logits.unsqueeze(-1) - outcome_logits.unsqueeze(-2)
    outcome_pairs = true_diff > 0
    outcome_rank = (
        F.softplus(-predicted_diff[outcome_pairs]).mean()
        if bool(outcome_pairs.any())
        else outcome_logits.sum() * 0.0
    )
    reward_diff = returns.unsqueeze(-1) - returns.unsqueeze(-2)
    tie_diff = tie_scores.unsqueeze(-1) - tie_scores.unsqueeze(-2)
    tie_pairs = (true_diff == 0) & (reward_diff > 1e-9)
    tie_rank = (
        F.softplus(-tie_diff[tie_pairs]).mean()
        if bool(tie_pairs.any())
        else tie_scores.sum() * 0.0
    )
    loss = classification + outcome_rank + 0.25 * tie_rank
    return loss, {
        "classification": float(classification.detach()),
        "outcome_rank": float(outcome_rank.detach()),
        "tie_rank": float(tie_rank.detach()),
    }


@torch.no_grad()
def evaluate_reranker(
    model: TerminalActionReranker,
    examples: RootExamples,
    *,
    device: torch.device,
) -> dict[str, Any]:
    model.eval()
    state = examples.state_features.to(device)
    actions = examples.action_features.to(device)
    expanded = state[:, None, :].expand(-1, examples.candidates, -1)
    outcome_logits, tie_scores = model(expanded, actions)
    probabilities = outcome_logits.sigmoid().cpu()
    parent = examples.parent_indices
    rows = torch.arange(examples.roots)
    correctable = examples.outcomes.max(dim=1).values > examples.outcomes[rows, parent]
    curves: list[dict[str, Any]] = []
    for threshold in THRESHOLDS:
        selected, _improvement = guarded_reranker_actions(
            outcome_logits.cpu(),
            tie_scores.cpu(),
            parent,
            probability_margin=threshold,
        )
        selected_outcome = examples.outcomes[rows, selected]
        parent_outcome = examples.outcomes[rows, parent]
        selected_return = examples.returns[rows, selected]
        parent_return = examples.returns[rows, parent]
        curves.append(
            {
                "threshold": threshold,
                "overrides": int((selected != parent).sum()),
                "improved_outcomes": int((selected_outcome > parent_outcome).sum()),
                "equal_outcomes": int((selected_outcome == parent_outcome).sum()),
                "worse_outcomes": int((selected_outcome < parent_outcome).sum()),
                "correctable_roots": int(correctable.sum()),
                "correctable_captured": int(
                    ((selected_outcome > parent_outcome) & correctable).sum()
                ),
                "best_outcome_accuracy": float(
                    (selected_outcome == examples.outcomes.max(dim=1).values)
                    .float()
                    .mean()
                ),
                "mean_dense_return_delta": float(
                    (selected_return - parent_return).mean()
                ),
            }
        )
    labels = ((examples.outcomes + 1.0) * 0.5).reshape(-1)
    bce = F.binary_cross_entropy(probabilities.reshape(-1), labels)
    return {
        "roots": examples.roots,
        "candidates": examples.candidates,
        "outcome_bce": float(bce),
        "parent_best_outcome_accuracy": float(
            (examples.outcomes[rows, parent] == examples.outcomes.max(dim=1).values)
            .float()
            .mean()
        ),
        "threshold_curve": curves,
    }


@torch.no_grad()
def fixed_threshold_root_details(
    model: TerminalActionReranker,
    examples: RootExamples,
    *,
    device: torch.device,
    threshold: float,
) -> list[dict[str, Any]]:
    """Return auditable per-root choices at one already-frozen threshold."""

    model.eval()
    state = examples.state_features.to(device)
    action_features = examples.action_features.to(device)
    expanded = state[:, None, :].expand(-1, examples.candidates, -1)
    outcome_logits, tie_scores = model(expanded, action_features)
    selected, proposed_margin = guarded_reranker_actions(
        outcome_logits,
        tie_scores,
        examples.parent_indices.to(device),
        probability_margin=threshold,
    )
    selected = selected.cpu()
    proposed_margin = proposed_margin.cpu()
    parent = examples.parent_indices
    details: list[dict[str, Any]] = []
    for index, name in enumerate(examples.names):
        chosen = int(selected[index])
        parent_index = int(parent[index])
        details.append(
            {
                "root": name,
                "strategy": examples.strategies[index],
                "warmup_steps": int(examples.warmups[index]),
                "parent_action": int(examples.actions[index, parent_index]),
                "selected_action": int(examples.actions[index, chosen]),
                "override": chosen != parent_index,
                "proposed_probability_margin": float(proposed_margin[index]),
                "parent_outcome": int(examples.outcomes[index, parent_index]),
                "selected_outcome": int(examples.outcomes[index, chosen]),
                "best_available_outcome": int(examples.outcomes[index].max()),
                "parent_dense_return": float(examples.returns[index, parent_index]),
                "selected_dense_return": float(examples.returns[index, chosen]),
            }
        )
    return details


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--initial-checkpoint", type=Path, required=True)
    parser.add_argument("--train-probes", type=Path, required=True)
    parser.add_argument("--validation-probes", type=Path, required=True)
    parser.add_argument("--output-checkpoint", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--policy-device", choices=("cpu", "mps"), default="cpu")
    parser.add_argument("--train-device", choices=("cpu", "mps"), default="cpu")
    parser.add_argument("--seed", type=int, default=1236001)
    parser.add_argument("--rank", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=500)
    parser.add_argument("--learning-rate", type=float, default=3e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-3)
    args = parser.parse_args()
    if args.output_checkpoint.exists() or args.report.exists():
        raise SystemExit("refusing to overwrite reranker outputs")
    if args.epochs < 1 or args.rank < 1 or args.learning_rate <= 0.0:
        raise ValueError("invalid reranker training settings")
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    torch.set_num_threads(1)
    policy_device = torch.device(args.policy_device)
    train_device = torch.device(args.train_device)
    checkpoint_sha = file_sha256(args.initial_checkpoint)
    payload = torch.load(
        args.initial_checkpoint, map_location=policy_device, weights_only=False
    )
    policy = _load_policy(payload, policy_device)
    state = payload["model_state_dict"]
    card_features = torch.as_tensor(
        state["actor_encoder.card_stat_features"], device=policy_device
    )
    semantic = state.get("actor_encoder.semantic_card_features")
    if semantic is not None:
        card_features = torch.cat(
            [card_features, torch.as_tensor(semantic, device=policy_device)], dim=-1
        )
    started = time.monotonic()
    train = load_probe_examples(
        args.train_probes,
        checkpoint_sha256=checkpoint_sha,
        model=policy,
        card_features=card_features,
        policy_device=policy_device,
    )
    validation = load_probe_examples(
        args.validation_probes,
        checkpoint_sha256=checkpoint_sha,
        model=policy,
        card_features=card_features,
        policy_device=policy_device,
    )
    overlap = train.fingerprints.intersection(validation.fingerprints)
    if overlap:
        raise ValueError(f"train/validation share {len(overlap)} exact root inputs")
    del policy
    if policy_device.type == "mps":
        torch.mps.empty_cache()

    reranker = TerminalActionReranker(
        train.state_features.shape[-1], train.action_features.shape[-1], args.rank
    ).to(train_device)
    optimizer = torch.optim.AdamW(
        reranker.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay
    )
    state_train = train.state_features.to(train_device)
    action_train = train.action_features.to(train_device)
    outcome_train = train.outcomes.to(train_device)
    return_train = train.returns.to(train_device)
    expanded_train = state_train[:, None, :].expand(-1, train.candidates, -1)
    history: list[dict[str, Any]] = []
    best_validation: dict[str, Any] | None = None
    best_state: dict[str, Tensor] | None = None
    best_epoch = 0
    best_score: tuple[float, float, float] = (-1.0, -1.0, -math.inf)
    for epoch in range(1, args.epochs + 1):
        reranker.train()
        outcome_logits, tie_scores = reranker(expanded_train, action_train)
        loss, components = _root_loss(
            outcome_logits, tie_scores, outcome_train, return_train
        )
        if not bool(torch.isfinite(loss)):
            raise FloatingPointError("reranker loss became non-finite")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        gradient = torch.nn.utils.clip_grad_norm_(reranker.parameters(), 1.0)
        optimizer.step()
        if epoch == 1 or epoch % 10 == 0 or epoch == args.epochs:
            metrics = evaluate_reranker(reranker, validation, device=train_device)
            eligible_rows = [
                row
                for row in metrics["threshold_curve"]
                if row["worse_outcomes"] == 0
                and row["improved_outcomes"] >= min(2, row["correctable_roots"])
            ]
            candidate = max(
                eligible_rows,
                key=lambda row: (
                    row["improved_outcomes"],
                    row["best_outcome_accuracy"],
                    row["mean_dense_return_delta"],
                    -row["threshold"],
                ),
                default=None,
            )
            score: tuple[float, float, float] = (
                -1.0 if candidate is None else float(candidate["improved_outcomes"]),
                -1.0 if candidate is None else candidate["best_outcome_accuracy"],
                -math.inf
                if candidate is None
                else candidate["mean_dense_return_delta"],
            )
            row = {
                "epoch": epoch,
                "loss": float(loss.detach()),
                **components,
                "gradient_norm": float(gradient),
                "validation": metrics,
                "eligible_threshold": None if candidate is None else candidate,
            }
            history.append(row)
            print(json.dumps(row), flush=True)
            if candidate is not None and score > best_score:
                best_score = score
                best_epoch = epoch
                best_validation = metrics
                best_state = {
                    name: value.detach().cpu().clone()
                    for name, value in reranker.state_dict().items()
                }
    report = {
        "schema": REPORT_SCHEMA,
        "initial_checkpoint": str(args.initial_checkpoint.resolve()),
        "initial_checkpoint_sha256": checkpoint_sha,
        "train_probe_root": str(args.train_probes.resolve()),
        "validation_probe_root": str(args.validation_probes.resolve()),
        "train_root_count": train.roots,
        "validation_root_count": validation.roots,
        "candidate_count": train.candidates,
        "train_validation_root_overlap": len(overlap),
        "state_feature_size": int(train.state_features.shape[-1]),
        "action_feature_size": int(train.action_features.shape[-1]),
        "rank": args.rank,
        "seed": args.seed,
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "policy_device": str(policy_device),
        "train_device": str(train_device),
        "elapsed_seconds": time.monotonic() - started,
        "selection_contract": (
            "terminal-outcome probability first; bounded dense tie-break; "
            "override only at a fixed probability-margin threshold"
        ),
        "eligibility_contract": (
            "zero held-out worse outcomes and at least two held-out outcome improvements"
        ),
        "best_epoch": best_epoch,
        "best_validation": best_validation,
        "history": history,
        "output_checkpoint": None,
    }
    if best_state is not None and best_validation is not None:
        threshold_rows = [
            row
            for row in best_validation["threshold_curve"]
            if row["worse_outcomes"] == 0
            and row["improved_outcomes"] >= min(2, row["correctable_roots"])
        ]
        selected_threshold = max(
            threshold_rows,
            key=lambda row: (
                row["improved_outcomes"],
                row["best_outcome_accuracy"],
                row["mean_dense_return_delta"],
                -row["threshold"],
            ),
        )["threshold"]
        args.output_checkpoint.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "schema": REPORT_SCHEMA,
                "parent_checkpoint": str(args.initial_checkpoint.resolve()),
                "parent_checkpoint_sha256": checkpoint_sha,
                "state_dict": best_state,
                "state_feature_size": int(train.state_features.shape[-1]),
                "action_feature_size": int(train.action_features.shape[-1]),
                "rank": args.rank,
                "override_probability_margin": selected_threshold,
                "development_only": True,
            },
            args.output_checkpoint,
        )
        report["output_checkpoint"] = str(args.output_checkpoint.resolve())
        report["output_checkpoint_sha256"] = file_sha256(args.output_checkpoint)
        report["override_probability_margin"] = selected_threshold
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
