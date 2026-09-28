"""Pretrain a behavior-neutral public opponent cycle/deck belief module."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import Tensor, nn
from torch.utils.data import DataLoader, TensorDataset

from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.common import NUM_HAND_SLOTS
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import _stack_step_inputs
from scripts.evaluate_public_cycle_belief import (
    BeliefMetrics,
    build_public_cycle_examples,
)

TRAINABLE_BELIEF_PREFIXES = (
    "public_history_slot_embedding.",
    "public_history_age_projection.",
    "public_seen_card_slot_embedding.",
    "public_belief_encoder.",
    "public_belief_hand_head.",
)
ADDED_BELIEF_PREFIXES = TRAINABLE_BELIEF_PREFIXES + (
    "public_history_projection.",
    "public_belief_card_query.",
    "public_belief_timing_head.",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_cycle_dataset(
    path: Path,
) -> tuple[TensorDataset, tuple[str, ...], dict[str, np.ndarray]]:
    with np.load(path, allow_pickle=False) as corpus:
        arrays = {
            name: np.asarray(corpus[name])
            for name in corpus.files
            if name != "metadata_json"
        }
        metadata = json.loads(str(corpus["metadata_json"]))
    token_names = tuple(str(name) for name in metadata["token_names"])
    examples = build_public_cycle_examples(arrays)
    targets = examples["targets"]
    if targets.shape[1] < len(token_names):
        targets = np.pad(
            targets,
            ((0, 0), (0, len(token_names) - targets.shape[1])),
        )
    dataset = TensorDataset(
        torch.from_numpy(examples["recent_ids"]),
        torch.from_numpy(examples["recent_ages"]),
        torch.from_numpy(examples["seen_ids"]),
        torch.from_numpy(targets[:, : len(token_names)]),
    )
    return dataset, token_names, examples


def build_upgraded_policy(
    payload: dict[str, Any],
    *,
    seed: int,
    history_slots: int = 4,
    seen_slots: int = 8,
) -> tuple[ClasherPolicy, StructuredObservationBuilder, list[str]]:
    if int(payload.get("format_version", 0)) != 2:
        raise ValueError("source checkpoint is not a V2 recurrent policy")
    source_config = PolicyConfig.from_dict(payload["model_config"])
    if source_config.public_history_slots not in (0, history_slots):
        raise ValueError("source checkpoint has an incompatible public-history width")
    if source_config.public_seen_card_slots not in (0, seen_slots):
        raise ValueError("source checkpoint has an incompatible seen-card width")
    target_config = replace(
        source_config,
        public_history_slots=history_slots,
        public_seen_card_slots=seen_slots,
    )
    builder = StructuredObservationBuilder(
        token_names=payload["token_names"],
        max_entities=target_config.max_entities,
        card_semantics_version=target_config.card_semantics_version,
        public_history_slots=history_slots,
        public_seen_card_slots=seen_slots,
    )
    torch.manual_seed(seed)
    model = ClasherPolicy(target_config, builder.card_stat_features)
    incompatible = model.load_state_dict(payload["model_state_dict"], strict=False)
    if incompatible.unexpected_keys:
        raise ValueError(
            f"unexpected source parameters: {sorted(incompatible.unexpected_keys)!r}"
        )
    missing = sorted(incompatible.missing_keys)
    if not missing or not all(key.startswith(ADDED_BELIEF_PREFIXES) for key in missing):
        raise ValueError(f"unexpected added belief parameters: {missing!r}")
    source_state = payload["model_state_dict"]
    target_state = model.state_dict()
    for name, value in source_state.items():
        if name not in target_state or not torch.equal(value.cpu(), target_state[name].cpu()):
            raise ValueError(f"shared source parameter changed during upgrade: {name}")
    history_output = model.public_history_projection
    belief_head = model.public_belief_hand_head
    belief_card_query = model.public_belief_card_query
    belief_timing_head = model.public_belief_timing_head
    assert history_output is not None
    assert belief_head is not None
    assert belief_card_query is not None
    assert belief_timing_head is not None
    history_output_layer = history_output[-1]
    if not isinstance(history_output_layer, nn.Linear):
        raise TypeError("public-history output projection must end in a linear layer")
    for tensor in (
        history_output_layer.weight,
        history_output_layer.bias,
        belief_head.weight,
        belief_head.bias,
        belief_card_query.weight,
        belief_card_query.bias,
        belief_timing_head.weight,
        belief_timing_head.bias,
    ):
        if torch.count_nonzero(tensor).item() != 0:
            raise ValueError("new policy-facing belief outputs must initialize to zero")
    return model, builder, missing


def configure_belief_trainable(model: ClasherPolicy) -> list[str]:
    trainable_names: list[str] = []
    for name, parameter in model.named_parameters():
        trainable = name.startswith(TRAINABLE_BELIEF_PREFIXES)
        parameter.requires_grad_(trainable)
        if trainable:
            trainable_names.append(name)
    if not trainable_names:
        raise ValueError("belief model exposes no trainable parameters")
    if any(name.startswith("public_history_projection.") for name in trainable_names):
        raise ValueError("policy-facing belief projection must remain frozen")
    return trainable_names


def belief_logits(
    model: ClasherPolicy,
    recent_ids: Tensor,
    recent_ages: Tensor,
    seen_ids: Tensor,
) -> Tensor:
    belief = model.encode_public_belief(recent_ids, recent_ages, seen_ids)
    assert model.public_belief_hand_head is not None
    result: Tensor = model.public_belief_hand_head(belief)
    return result


@torch.no_grad()
def evaluate_belief(
    model: ClasherPolicy,
    dataset: TensorDataset,
    *,
    device: torch.device,
    batch_size: int,
    use_seen_cards: bool,
) -> BeliefMetrics:
    model.eval()
    loss_total = recall_total = exact_total = 0.0
    history_total = seen_total = 0.0
    samples = 0
    for recent_ids, recent_ages, seen_ids, targets in DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
    ):
        recent_ids = recent_ids.to(device)
        recent_ages = recent_ages.to(device)
        seen_ids = seen_ids.to(device)
        targets = targets.to(device)
        if not use_seen_cards:
            seen_ids = torch.zeros_like(seen_ids)
        logits = belief_logits(model, recent_ids, recent_ages, seen_ids)
        loss = nn.functional.binary_cross_entropy_with_logits(logits, targets)
        batch = targets.shape[0]
        loss_total += float(loss) * batch
        ranked_logits = logits.clone()
        ranked_logits[:, 0] = -torch.inf
        predicted = ranked_logits.topk(NUM_HAND_SLOTS, dim=-1).indices
        predicted_mask = torch.zeros_like(targets).scatter_(-1, predicted, 1.0)
        overlap = (predicted_mask * targets).sum(dim=-1)
        recall_total += float((overlap / targets.sum(dim=-1).clamp_min(1.0)).sum())
        exact_total += float((predicted_mask == targets).all(dim=-1).sum())
        history_total += float(recent_ids.ne(0).sum())
        seen_total += float(seen_ids.ne(0).sum())
        samples += batch
    return BeliefMetrics(
        samples=samples,
        mean_history_plays=history_total / samples,
        mean_seen_cards=seen_total / samples,
        binary_cross_entropy=loss_total / samples,
        top4_recall=recall_total / samples,
        exact_hand_accuracy=exact_total / samples,
    )


def train_belief_model(
    model: ClasherPolicy,
    train_dataset: TensorDataset,
    validation_dataset: TensorDataset,
    *,
    device: torch.device,
    seed: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    use_seen_cards: bool,
) -> tuple[dict[str, Tensor], list[dict[str, Any]], int]:
    trainable_names = configure_belief_trainable(model)
    model.to(device)
    optimizer = torch.optim.AdamW(
        [parameter for parameter in model.parameters() if parameter.requires_grad],
        lr=learning_rate,
    )
    positive_weight = torch.full(
        (model.config.num_tokens,),
        (model.config.num_tokens - NUM_HAND_SLOTS) / NUM_HAND_SLOTS,
        device=device,
    )
    positive_weight[0] = 0.0
    loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        generator=torch.Generator().manual_seed(seed),
    )
    best_epoch = 0
    best_recall = -1.0
    best_state: dict[str, Tensor] = {}
    rows: list[dict[str, Any]] = []
    for epoch in range(1, epochs + 1):
        model.train()
        loss_total = 0.0
        samples = 0
        for recent_ids, recent_ages, seen_ids, targets in loader:
            recent_ids = recent_ids.to(device)
            recent_ages = recent_ages.to(device)
            seen_ids = seen_ids.to(device)
            targets = targets.to(device)
            if not use_seen_cards:
                seen_ids = torch.zeros_like(seen_ids)
            optimizer.zero_grad(set_to_none=True)
            logits = belief_logits(model, recent_ids, recent_ages, seen_ids)
            loss = nn.functional.binary_cross_entropy_with_logits(
                logits,
                targets,
                pos_weight=positive_weight,
            )
            loss.backward()
            optimizer.step()
            loss_total += float(loss.detach()) * targets.shape[0]
            samples += targets.shape[0]
        validation = evaluate_belief(
            model,
            validation_dataset,
            device=device,
            batch_size=batch_size,
            use_seen_cards=use_seen_cards,
        )
        rows.append(
            {
                "epoch": epoch,
                "weighted_train_loss": loss_total / samples,
                "validation": asdict(validation),
            }
        )
        if validation.top4_recall > best_recall:
            best_epoch = epoch
            best_recall = validation.top4_recall
            best_state = {
                name: parameter.detach().cpu().clone()
                for name, parameter in model.state_dict().items()
            }
    if not best_state:
        raise RuntimeError("belief training did not produce a checkpoint")
    model.load_state_dict(best_state)
    if set(trainable_names) != {
        name for name, parameter in model.named_parameters() if parameter.requires_grad
    }:
        raise RuntimeError("belief trainable scope changed during training")
    return best_state, rows, best_epoch


@torch.no_grad()
def verify_policy_equivalence(
    source_payload: dict[str, Any],
    target_model: ClasherPolicy,
    target_builder: StructuredObservationBuilder,
) -> dict[str, Any]:
    source_config = PolicyConfig.from_dict(source_payload["model_config"])
    source_builder = StructuredObservationBuilder(
        token_names=source_payload["token_names"],
        max_entities=source_config.max_entities,
        card_semantics_version=source_config.card_semantics_version,
        public_history_slots=source_config.public_history_slots,
        public_seen_card_slots=source_config.public_seen_card_slots,
    )
    source_model = ClasherPolicy(source_config, source_builder.card_stat_features)
    source_model.load_state_dict(source_payload["model_state_dict"])
    source_model.eval()
    target_model = target_model.cpu().eval()
    battle = BattleState(fast_path=True)
    battle.tick = 500
    battle.public_card_play_history[1] = [
        (20, "Giant"),
        (70, "Archer"),
        (120, "Zap"),
        (180, "MiniP.E.K.K.A"),
        (240, "Fireball"),
        (300, "Musketeer"),
        (360, "Knight"),
        (430, "HogRider"),
    ]
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    action_mask = action_space.legal_action_mask(battle, 0)[None, :]
    source_state = source_model.initial_state(1, device=torch.device("cpu"))
    target_state = target_model.initial_state(1, device=torch.device("cpu"))
    digest = hashlib.sha256()
    max_joint_difference = 0.0
    max_value_difference = 0.0
    for step in range(12):
        previous_action = np.asarray(
            [action_space.no_op_action if step == 0 else step % action_space.no_op_action],
            dtype=np.int64,
        )
        common = (
            action_mask,
            previous_action,
            np.asarray([0.0], dtype=np.float32),
            np.asarray([step == 0], dtype=np.bool_),
            torch.device("cpu"),
        )
        source_inputs = _stack_step_inputs([source_builder.build(battle, 0)], *common)
        target_inputs = _stack_step_inputs([target_builder.build(battle, 0)], *common)
        source_output = source_model(source_inputs, source_state)
        target_output = target_model(target_inputs, target_state)
        joint_difference = float(
            (source_output.joint_logits - target_output.joint_logits).abs().max()
        )
        value_difference = float((source_output.values - target_output.values).abs().max())
        max_joint_difference = max(max_joint_difference, joint_difference)
        max_value_difference = max(max_value_difference, value_difference)
        if not torch.equal(source_output.joint_logits, target_output.joint_logits):
            raise ValueError(f"policy logits changed at equivalence step {step}")
        if not torch.equal(source_output.values, target_output.values):
            raise ValueError(f"policy values changed at equivalence step {step}")
        for source_tensor, target_tensor in zip(
            source_output.next_state,
            target_output.next_state,
            strict=True,
        ):
            if not torch.equal(source_tensor, target_tensor):
                raise ValueError(f"recurrent state changed at equivalence step {step}")
        digest.update(source_output.joint_logits.numpy().tobytes())
        digest.update(source_output.values.numpy().tobytes())
        source_state = source_output.next_state
        target_state = target_output.next_state
    return {
        "steps": 12,
        "bit_exact": True,
        "max_joint_logit_abs_difference": max_joint_difference,
        "max_value_abs_difference": max_value_difference,
        "source_output_sha256": digest.hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-checkpoint",
        type=Path,
        default=Path(
            "checkpoints/tv_raw1000_spatial_value_rl_seed1044801/"
            "policy_v2_update_000040.pt"
        ),
    )
    parser.add_argument(
        "--split-root",
        type=Path,
        default=Path("datasets/derived/tv_royale_raw_cascade_2000_split_seed1045801"),
    )
    parser.add_argument("--seed", type=int, default=1048803)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    parser.add_argument("--output-checkpoint", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device(args.device)
    payload = torch.load(args.source_checkpoint, map_location="cpu", weights_only=False)
    datasets: dict[str, TensorDataset] = {}
    token_names: tuple[str, ...] | None = None
    example_counts: dict[str, int] = {}
    for split in ("train", "validation", "archetype_test", "chronology_test"):
        dataset, split_tokens, examples = load_cycle_dataset(
            args.split_root / f"{split}.npz"
        )
        if token_names is not None and split_tokens != token_names:
            raise ValueError("cycle splits have inconsistent token vocabularies")
        token_names = split_tokens
        datasets[split] = dataset
        example_counts[split] = int(examples["targets"].shape[0])
    if token_names != tuple(payload["token_names"]):
        raise ValueError("cycle corpus vocabulary does not match source checkpoint")

    results: dict[str, Any] = {}
    selected_model: ClasherPolicy | None = None
    selected_builder: StructuredObservationBuilder | None = None
    selected_missing: list[str] = []
    selected_trainable: list[str] = []
    for name, use_seen_cards in (("recent4", False), ("recent4_seen8", True)):
        model, builder, missing = build_upgraded_policy(payload, seed=args.seed)
        trainable_names = configure_belief_trainable(model)
        _, epochs, best_epoch = train_belief_model(
            model,
            datasets["train"],
            datasets["validation"],
            device=device,
            seed=args.seed,
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            use_seen_cards=use_seen_cards,
        )
        metrics = {
            split: asdict(
                evaluate_belief(
                    model,
                    datasets[split],
                    device=device,
                    batch_size=args.batch_size,
                    use_seen_cards=use_seen_cards,
                )
            )
            for split in ("train", "validation", "archetype_test", "chronology_test")
        }
        results[name] = {
            "best_epoch_selected_on_validation": best_epoch,
            "epochs": epochs,
            "metrics": metrics,
        }
        if use_seen_cards:
            selected_model = model
            selected_builder = builder
            selected_missing = missing
            selected_trainable = trainable_names

    assert selected_model is not None
    assert selected_builder is not None
    equivalence = verify_policy_equivalence(payload, selected_model, selected_builder)
    output_payload = dict(payload)
    output_payload.pop("optimizer_state_dict", None)
    output_payload["model_config"] = selected_model.config.to_dict()
    output_payload["model_state_dict"] = {
        name: tensor.detach().cpu()
        for name, tensor in selected_model.state_dict().items()
    }
    output_args = dict(payload.get("args") or {})
    output_args["public_cycle_belief_pretrain"] = {
        "source_checkpoint": str(args.source_checkpoint.resolve()),
        "split_root": str(args.split_root.resolve()),
        "seed": args.seed,
        "epochs": args.epochs,
        "best_epoch_selected_on_validation": results["recent4_seen8"][
            "best_epoch_selected_on_validation"
        ],
        "history_slots": 4,
        "seen_slots": 8,
        "policy_projection_frozen_zero": True,
        "trainable_parameter_names": selected_trainable,
    }
    output_payload["args"] = output_args
    args.output_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output_checkpoint.with_suffix(args.output_checkpoint.suffix + ".tmp")
    torch.save(output_payload, temporary)
    temporary.replace(args.output_checkpoint)

    recent = results["recent4"]["metrics"]
    seen = results["recent4_seen8"]["metrics"]
    improvements = {
        split: {
            "top4_recall_absolute": (
                seen[split]["top4_recall"] - recent[split]["top4_recall"]
            ),
            "top4_recall_relative": (
                seen[split]["top4_recall"] / recent[split]["top4_recall"] - 1.0
                if recent[split]["top4_recall"] > 0.0
                else None
            ),
        }
        for split in recent
    }
    report = {
        "schema_version": 1,
        "source_checkpoint": str(args.source_checkpoint.resolve()),
        "output_checkpoint": str(args.output_checkpoint.resolve()),
        "output_checkpoint_sha256": _sha256(args.output_checkpoint),
        "split_root": str(args.split_root.resolve()),
        "seed": args.seed,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "device": args.device,
        "example_counts": example_counts,
        "added_parameter_names": selected_missing,
        "trainable_parameter_names": selected_trainable,
        "trainable_parameter_count": sum(
            parameter.numel()
            for parameter in selected_model.parameters()
            if parameter.requires_grad
        ),
        "policy_equivalence": equivalence,
        "models": results,
        "seen_card_improvements": improvements,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
