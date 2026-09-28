"""Human fine-tune gate for a simulator-pretrained mechanics slot probe."""

from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn

from clasher.paths import resolve_path
from scripts.fit_mechanics_slot_probe import (
    MechanicsSlotScorer,
    SlotExamples,
    _card_weights,
    _split_episodes,
    evaluate,
    extract_examples,
)


def _snapshot(model: nn.Module) -> dict[str, torch.Tensor]:
    return {name: value.detach().clone() for name, value in model.state_dict().items()}


def _safe_epoch_score(
    *,
    human_validation: dict[str, float],
    guard_metrics: dict[str, dict[str, float]],
    guard_baselines: dict[str, dict[str, float]],
    max_guard_regression: float,
) -> tuple[float, float] | None:
    safe = all(
        guard_metrics[name]["accuracy"]
        >= baseline["accuracy"] - max_guard_regression
        for name, baseline in guard_baselines.items()
    )
    if not safe:
        return None
    return human_validation["accuracy"], -human_validation["loss"]


def _promotion_decision(
    *,
    control_metrics: dict[str, dict[str, float]],
    candidate_metrics: dict[str, dict[str, float]],
    min_human_validation_gain: float,
    max_simulator_regression: float,
) -> bool:
    if min_human_validation_gain < 0.0:
        raise ValueError("min_human_validation_gain must be non-negative")
    if max_simulator_regression < 0.0:
        raise ValueError("max_simulator_regression must be non-negative")
    human_gain = (
        candidate_metrics["human_validation"]["accuracy"]
        - control_metrics["human_validation"]["accuracy"]
    )
    return (
        human_gain >= min_human_validation_gain
        and candidate_metrics["simulator_validation"]["accuracy"]
        >= control_metrics["simulator_validation"]["accuracy"]
        - max_simulator_regression
        and candidate_metrics["simulator_heldout"]["accuracy"]
        >= control_metrics["simulator_heldout"]["accuracy"]
        - max_simulator_regression
    )


def finetune(
    *,
    model: MechanicsSlotScorer,
    human_training: SlotExamples,
    human_validation: SlotExamples,
    seed: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    guard_examples: dict[str, SlotExamples],
    max_guard_regression: float,
) -> tuple[dict[str, torch.Tensor], list[dict[str, float]], int]:
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    training_indices = np.arange(human_training.target.shape[0], dtype=np.int64)
    weights = _card_weights(human_training, training_indices)
    rng = np.random.default_rng(seed)
    initial = evaluate(model, human_validation)
    guard_baselines = {
        name: evaluate(model, examples) for name, examples in guard_examples.items()
    }
    best_score = _safe_epoch_score(
        human_validation=initial,
        guard_metrics=guard_baselines,
        guard_baselines=guard_baselines,
        max_guard_regression=max_guard_regression,
    )
    assert best_score is not None
    best_state = _snapshot(model)
    best_epoch = 0
    history = [
        {
            "epoch": 0.0,
            **initial,
            **{
                f"{name}_accuracy": metrics["accuracy"]
                for name, metrics in guard_baselines.items()
            },
            "safe": 1.0,
        }
    ]
    for epoch in range(1, epochs + 1):
        model.train()
        shuffled = training_indices.copy()
        rng.shuffle(shuffled)
        for start in range(0, len(shuffled), batch_size):
            batch = shuffled[start : start + batch_size]
            logits = model(
                human_training.state[batch], human_training.cards[batch]
            ).masked_fill(
                ~human_training.legal[batch], -1e9
            )
            losses = nn.functional.cross_entropy(
                logits,
                human_training.target[batch],
                reduction="none",
            )
            loss = (losses * weights[batch]).mean()
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        metrics = evaluate(model, human_validation)
        guard_metrics = {
            name: evaluate(model, examples)
            for name, examples in guard_examples.items()
        }
        score = _safe_epoch_score(
            human_validation=metrics,
            guard_metrics=guard_metrics,
            guard_baselines=guard_baselines,
            max_guard_regression=max_guard_regression,
        )
        history.append(
            {
                "epoch": float(epoch),
                **metrics,
                **{
                    f"{name}_accuracy": current["accuracy"]
                    for name, current in guard_metrics.items()
                },
                "safe": float(score is not None),
            }
        )
        if score is not None and score > best_score:
            best_score = score
            best_state = _snapshot(model)
            best_epoch = epoch
    model.load_state_dict(best_state)
    return best_state, history, best_epoch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe-checkpoint", required=True, type=Path)
    parser.add_argument("--validation-corpus", required=True, type=Path)
    parser.add_argument("--heldout-corpus", required=True, type=Path)
    parser.add_argument("--human-corpus", required=True, type=Path)
    parser.add_argument("--human-sidecar", required=True, type=Path)
    parser.add_argument("--human-validation-corpus", type=Path)
    parser.add_argument("--human-validation-sidecar", type=Path)
    parser.add_argument("--simulator-checkpoint", required=True, type=Path)
    parser.add_argument("--public-checkpoint", required=True, type=Path)
    parser.add_argument("--decks-path", default="decks.json", type=Path)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--validation-fraction", type=float, default=0.25)
    parser.add_argument("--min-human-validation-gain", type=float, default=0.01)
    parser.add_argument("--max-simulator-regression", type=float, default=0.01)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    probe_path = resolve_path(args.probe_checkpoint, must_exist=True)
    probe = torch.load(probe_path, map_location="cpu", weights_only=False)
    semantics_version = int(probe["semantics_version"])
    hidden_size = int(probe["hidden_size"])
    paths = {
        name: resolve_path(path, must_exist=True)
        for name, path in (
            ("validation", args.validation_corpus),
            ("heldout", args.heldout_corpus),
            ("human", args.human_corpus),
        )
    }
    decks_path = resolve_path(args.decks_path, must_exist=True)
    simulator_checkpoint = resolve_path(args.simulator_checkpoint, must_exist=True)
    public_checkpoint = resolve_path(args.public_checkpoint, must_exist=True)
    human_sidecar = resolve_path(args.human_sidecar, must_exist=True)
    if (args.human_validation_corpus is None) != (
        args.human_validation_sidecar is None
    ):
        raise ValueError(
            "human validation corpus and sidecar must be supplied together"
        )
    simulator_validation, token_names = extract_examples(
        corpus_path=paths["validation"],
        checkpoint_path=simulator_checkpoint,
        decks_path=decks_path,
        semantics_version=semantics_version,
    )
    simulator_heldout, heldout_tokens = extract_examples(
        corpus_path=paths["heldout"],
        checkpoint_path=simulator_checkpoint,
        decks_path=decks_path,
        semantics_version=semantics_version,
    )
    human, human_tokens = extract_examples(
        corpus_path=paths["human"],
        checkpoint_path=public_checkpoint,
        decks_path=decks_path,
        semantics_version=semantics_version,
        public_sidecar=human_sidecar,
    )
    if tuple(probe["token_names"]) != token_names:
        raise ValueError("probe/simulator token vocabulary mismatch")
    if heldout_tokens != token_names or human_tokens != token_names:
        raise ValueError("evaluation token vocabularies differ")
    model = MechanicsSlotScorer(
        state_size=human.state.shape[-1],
        card_size=human.cards.shape[-1],
        hidden_size=hidden_size,
    )
    model.load_state_dict(probe["state_dict"])
    validation_source: dict[str, Any]
    if args.human_validation_corpus is not None:
        validation_corpus = resolve_path(
            args.human_validation_corpus, must_exist=True
        )
        validation_sidecar = resolve_path(
            args.human_validation_sidecar, must_exist=True
        )
        human_training = human
        human_validation, validation_tokens = extract_examples(
            corpus_path=validation_corpus,
            checkpoint_path=public_checkpoint,
            decks_path=decks_path,
            semantics_version=semantics_version,
            public_sidecar=validation_sidecar,
        )
        if validation_tokens != token_names:
            raise ValueError("human validation token vocabulary differs")
        validation_source = {
            "mode": "external_replay_disjoint",
            "corpus": str(validation_corpus),
            "sidecar": str(validation_sidecar),
        }
    else:
        training_indices, validation_indices = _split_episodes(
            human,
            seed=args.seed,
            validation_fraction=args.validation_fraction,
        )
        human_training = human.select(training_indices)
        human_validation = human.select(validation_indices)
        validation_source = {
            "mode": "internal_episode_split",
            "validation_fraction": args.validation_fraction,
        }
    control_metrics = {
        "human_train": evaluate(model, human_training),
        "human_validation": evaluate(model, human_validation),
        "human_full": evaluate(model, human),
        "simulator_validation": evaluate(model, simulator_validation),
        "simulator_heldout": evaluate(model, simulator_heldout),
    }
    best_state, history, selected_epoch = finetune(
        model=model,
        human_training=human_training,
        human_validation=human_validation,
        seed=args.seed,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        guard_examples={
            "simulator_validation": simulator_validation,
            "simulator_heldout": simulator_heldout,
        },
        max_guard_regression=args.max_simulator_regression,
    )
    candidate_metrics = {
        "human_train": evaluate(model, human_training),
        "human_validation": evaluate(model, human_validation),
        "human_full": evaluate(model, human),
        "simulator_validation": evaluate(model, simulator_validation),
        "simulator_heldout": evaluate(model, simulator_heldout),
    }
    promoted = _promotion_decision(
        control_metrics=control_metrics,
        candidate_metrics=candidate_metrics,
        min_human_validation_gain=args.min_human_validation_gain,
        max_simulator_regression=args.max_simulator_regression,
    )
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "source_probe": str(probe_path),
        "semantics_version": semantics_version,
        "hidden_size": hidden_size,
        "state_dict": best_state,
        "token_names": token_names,
        "control_metrics": control_metrics,
        "candidate_metrics": candidate_metrics,
        "selected_epoch": selected_epoch,
        "human_validation_source": validation_source,
        "min_human_validation_gain": args.min_human_validation_gain,
        "max_simulator_regression": args.max_simulator_regression,
        "promoted": promoted,
        "history": history,
    }
    torch.save(payload, output)
    report: dict[str, Any] = {
        key: value for key, value in payload.items() if key not in {"state_dict", "token_names"}
    }
    report["checkpoint"] = str(output)
    output.with_suffix(".json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
