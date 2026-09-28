"""Probe mechanics-only conditional card choice on disjoint deck splits."""

from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn

from clasher.paths import resolve_path
from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.imitation import (
    _sequence_batch_inputs,
    load_corpus,
    load_public_observation_sidecar,
)
from clasher.rl.structured_obs import StructuredObservationBuilder


@dataclass(frozen=True)
class SlotExamples:
    state: torch.Tensor
    cards: torch.Tensor
    legal: torch.Tensor
    target: torch.Tensor
    target_card: torch.Tensor
    episode: np.ndarray
    base_logits: torch.Tensor

    def select(self, indices: np.ndarray) -> SlotExamples:
        tensor_indices = torch.as_tensor(indices, dtype=torch.long)
        return SlotExamples(
            state=self.state[tensor_indices],
            cards=self.cards[tensor_indices],
            legal=self.legal[tensor_indices],
            target=self.target[tensor_indices],
            target_card=self.target_card[tensor_indices],
            episode=self.episode[indices],
            base_logits=self.base_logits[tensor_indices],
        )


class MechanicsSlotScorer(nn.Module):
    def __init__(self, state_size: int, card_size: int, hidden_size: int) -> None:
        super().__init__()
        self.state_query: nn.Module
        if hidden_size <= 0:
            self.state_query = nn.Linear(state_size, card_size, bias=False)
            self.card_encoder: nn.Module = nn.Identity()
            self.output_size = card_size
        else:
            self.state_query = nn.Sequential(
                nn.Linear(state_size, hidden_size),
                nn.GELU(),
                nn.Linear(hidden_size, hidden_size, bias=False),
            )
            self.card_encoder = nn.Sequential(
                nn.Linear(card_size, hidden_size),
                nn.GELU(),
                nn.Linear(hidden_size, hidden_size, bias=False),
            )
            self.output_size = hidden_size

    def forward(self, state: torch.Tensor, cards: torch.Tensor) -> torch.Tensor:
        query = self.state_query(state)
        keys = self.card_encoder(cards)
        return torch.einsum("bd,bsd->bs", query, keys) / math.sqrt(
            self.output_size
        )


def _slot_legal_masks(action_masks: np.ndarray) -> np.ndarray:
    return np.asarray(
        action_masks[:, : NUM_HAND_SLOTS * NUM_TILES]
        .reshape(-1, NUM_HAND_SLOTS, NUM_TILES)
        .any(axis=-1),
        dtype=np.bool_,
    )


def extract_examples(
    *,
    corpus_path: Path,
    checkpoint_path: Path,
    decks_path: Path,
    semantics_version: int,
    public_sidecar: Path | None = None,
) -> tuple[SlotExamples, tuple[str, ...]]:
    metadata, arrays = load_corpus(corpus_path)
    if public_sidecar is not None:
        arrays = load_public_observation_sidecar(
            public_sidecar,
            base_arrays=arrays,
        )
    loaded = load_policy_checkpoint(
        checkpoint_path,
        device=torch.device("cpu"),
        decks_path=decks_path,
    )
    if tuple(loaded.builder.token_names) != tuple(metadata.token_names):
        raise ValueError("checkpoint/corpus token vocabulary mismatch")
    semantic_builder = StructuredObservationBuilder(
        decks_path=decks_path,
        max_entities=metadata.max_entities,
        token_names=metadata.token_names,
        card_semantics_version=semantics_version,
    )
    card_features = torch.as_tensor(
        semantic_builder.card_stat_features,
        dtype=torch.float32,
    )
    placement_limit = NUM_HAND_SLOTS * NUM_TILES
    expert_actions = arrays["expert_actions"]
    legal_slots = _slot_legal_masks(arrays["action_masks"])
    state_rows: list[torch.Tensor] = []
    card_rows: list[torch.Tensor] = []
    legal_rows: list[torch.Tensor] = []
    target_rows: list[torch.Tensor] = []
    target_card_rows: list[torch.Tensor] = []
    episode_rows: list[np.ndarray] = []
    base_logit_rows: list[torch.Tensor] = []
    loaded.model.eval()
    with torch.no_grad():
        for episode_id in np.unique(arrays["episode_ids"]):
            indices = np.flatnonzero(arrays["episode_ids"] == episode_id)
            if indices.size == 0 or np.any(np.diff(indices) != 1):
                raise ValueError("corpus episodes must be contiguous")
            inputs = _sequence_batch_inputs(
                arrays,
                indices[None, :],
                torch.device("cpu"),
                trim_entity_padding=True,
            )
            output = loaded.model(inputs)
            selected = expert_actions[indices] < placement_limit
            if not selected.any():
                continue
            selected_indices = indices[selected]
            hand_ids = torch.as_tensor(
                arrays["hand_ids"][selected_indices, :NUM_HAND_SLOTS],
                dtype=torch.long,
            )
            targets = torch.as_tensor(
                expert_actions[selected_indices] // NUM_TILES,
                dtype=torch.long,
            )
            state_rows.append(output.repair_features[0, selected].cpu())
            card_rows.append(card_features[hand_ids])
            legal_rows.append(
                torch.as_tensor(legal_slots[selected_indices], dtype=torch.bool)
            )
            target_rows.append(targets)
            target_card_rows.append(hand_ids.gather(1, targets[:, None]).squeeze(1))
            episode_rows.append(
                np.full(len(selected_indices), int(episode_id), dtype=np.int64)
            )
            base_logit_rows.append(
                output.action_type_logits[0, selected, :NUM_HAND_SLOTS].cpu()
            )
    if not state_rows:
        raise ValueError("corpus has no placement examples")
    return (
        SlotExamples(
            state=torch.cat(state_rows),
            cards=torch.cat(card_rows),
            legal=torch.cat(legal_rows),
            target=torch.cat(target_rows),
            target_card=torch.cat(target_card_rows),
            episode=np.concatenate(episode_rows),
            base_logits=torch.cat(base_logit_rows),
        ),
        tuple(metadata.token_names),
    )


def _split_episodes(
    examples: SlotExamples,
    *,
    seed: int,
    validation_fraction: float,
) -> tuple[np.ndarray, np.ndarray]:
    episodes = np.unique(examples.episode)
    rng = np.random.default_rng(seed)
    rng.shuffle(episodes)
    count = max(1, round(len(episodes) * validation_fraction))
    validation_episodes = set(episodes[:count].tolist())
    validation = np.asarray(
        [i for i, episode in enumerate(examples.episode) if episode in validation_episodes],
        dtype=np.int64,
    )
    training = np.asarray(
        [i for i, episode in enumerate(examples.episode) if episode not in validation_episodes],
        dtype=np.int64,
    )
    if training.size == 0 or validation.size == 0:
        raise ValueError("episode split produced an empty partition")
    return training, validation


def _card_weights(examples: SlotExamples, indices: np.ndarray) -> torch.Tensor:
    cards = examples.target_card.numpy()
    counts = np.bincount(cards[indices], minlength=int(cards.max()) + 1)
    nonzero = counts[counts > 0]
    reference = float(np.median(nonzero)) if nonzero.size else 1.0
    weights = np.ones_like(cards, dtype=np.float32)
    for index in indices:
        weights[index] = min(4.0, math.sqrt(reference / max(1, counts[cards[index]])))
    weights[indices] /= max(1e-8, float(weights[indices].mean()))
    return torch.as_tensor(weights)


@torch.no_grad()
def evaluate(
    model: MechanicsSlotScorer,
    examples: SlotExamples,
) -> dict[str, float]:
    model.eval()
    logits = model(examples.state, examples.cards).masked_fill(
        ~examples.legal, -torch.inf
    )
    predictions = logits.argmax(dim=-1)
    base_predictions = examples.base_logits.masked_fill(
        ~examples.legal, -torch.inf
    ).argmax(dim=-1)
    return {
        "samples": float(len(examples.target)),
        "loss": float(nn.functional.cross_entropy(logits, examples.target)),
        "accuracy": float((predictions == examples.target).float().mean()),
        "base_accuracy": float((base_predictions == examples.target).float().mean()),
    }


def fit(
    *,
    model: MechanicsSlotScorer,
    examples: SlotExamples,
    training_indices: np.ndarray,
    validation_indices: np.ndarray,
    seed: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
) -> tuple[dict[str, torch.Tensor], list[dict[str, float]]]:
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    weights = _card_weights(examples, training_indices)
    rng = np.random.default_rng(seed)
    best_state: dict[str, torch.Tensor] | None = None
    best_loss = float("inf")
    history: list[dict[str, float]] = []
    train_examples = examples.select(training_indices)
    validation_examples = examples.select(validation_indices)
    for epoch in range(1, epochs + 1):
        model.train()
        shuffled = training_indices.copy()
        rng.shuffle(shuffled)
        for start in range(0, len(shuffled), batch_size):
            batch = shuffled[start : start + batch_size]
            logits = model(examples.state[batch], examples.cards[batch]).masked_fill(
                ~examples.legal[batch], -1e9
            )
            losses = nn.functional.cross_entropy(
                logits,
                examples.target[batch],
                reduction="none",
            )
            loss = (losses * weights[batch]).mean()
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        train_metrics = evaluate(model, train_examples)
        validation_metrics = evaluate(model, validation_examples)
        history.append(
            {
                "epoch": float(epoch),
                "train_loss": train_metrics["loss"],
                "train_accuracy": train_metrics["accuracy"],
                "validation_loss": validation_metrics["loss"],
                "validation_accuracy": validation_metrics["accuracy"],
            }
        )
        if validation_metrics["loss"] < best_loss:
            best_loss = validation_metrics["loss"]
            best_state = {
                name: value.detach().clone() for name, value in model.state_dict().items()
            }
    assert best_state is not None
    model.load_state_dict(best_state)
    return best_state, history


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-corpus", required=True, type=Path)
    parser.add_argument("--validation-corpus", required=True, type=Path)
    parser.add_argument("--heldout-corpus", required=True, type=Path)
    parser.add_argument("--human-corpus", required=True, type=Path)
    parser.add_argument("--human-sidecar", required=True, type=Path)
    parser.add_argument("--simulator-checkpoint", required=True, type=Path)
    parser.add_argument("--public-checkpoint", required=True, type=Path)
    parser.add_argument("--decks-path", default="decks.json", type=Path)
    parser.add_argument("--semantics-version", choices=(1, 2, 3), type=int, required=True)
    parser.add_argument("--hidden-size", type=int, default=0)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = {
        name: resolve_path(path, must_exist=True)
        for name, path in (
            ("train", args.train_corpus),
            ("validation", args.validation_corpus),
            ("heldout", args.heldout_corpus),
            ("human", args.human_corpus),
        )
    }
    simulator_checkpoint = resolve_path(args.simulator_checkpoint, must_exist=True)
    public_checkpoint = resolve_path(args.public_checkpoint, must_exist=True)
    decks_path = resolve_path(args.decks_path, must_exist=True)
    human_sidecar = resolve_path(args.human_sidecar, must_exist=True)
    examples: dict[str, SlotExamples] = {}
    token_names: tuple[str, ...] | None = None
    for name in ("train", "validation", "heldout"):
        examples[name], current_tokens = extract_examples(
            corpus_path=paths[name],
            checkpoint_path=simulator_checkpoint,
            decks_path=decks_path,
            semantics_version=args.semantics_version,
        )
        token_names = token_names or current_tokens
        if current_tokens != token_names:
            raise ValueError("simulator corpus vocabularies differ")
    examples["human"], human_tokens = extract_examples(
        corpus_path=paths["human"],
        checkpoint_path=public_checkpoint,
        decks_path=decks_path,
        semantics_version=args.semantics_version,
        public_sidecar=human_sidecar,
    )
    if human_tokens != token_names:
        raise ValueError("human/simulator vocabularies differ")
    training_indices, internal_validation_indices = _split_episodes(
        examples["train"],
        seed=args.seed,
        validation_fraction=args.validation_fraction,
    )
    torch.manual_seed(args.seed)
    model = MechanicsSlotScorer(
        state_size=examples["train"].state.shape[-1],
        card_size=examples["train"].cards.shape[-1],
        hidden_size=args.hidden_size,
    )
    best_state, history = fit(
        model=model,
        examples=examples["train"],
        training_indices=training_indices,
        validation_indices=internal_validation_indices,
        seed=args.seed,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
    )
    metrics = {
        "train": evaluate(model, examples["train"].select(training_indices)),
        "internal_validation": evaluate(
            model, examples["train"].select(internal_validation_indices)
        ),
        "validation_decks": evaluate(model, examples["validation"]),
        "heldout_archetypes": evaluate(model, examples["heldout"]),
        "human_snapshot": evaluate(model, examples["human"]),
    }
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "schema_version": 1,
            "semantics_version": args.semantics_version,
            "hidden_size": args.hidden_size,
            "state_dict": best_state,
            "token_names": token_names,
            "metrics": metrics,
            "history": history,
        },
        output,
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "semantics_version": args.semantics_version,
        "hidden_size": args.hidden_size,
        "seed": args.seed,
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "training_examples": len(training_indices),
        "internal_validation_examples": len(internal_validation_indices),
        "metrics": metrics,
        "checkpoint": str(output),
    }
    report_path = output.with_suffix(".json")
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
