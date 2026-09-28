"""Fit a small permutation-invariant card-choice policy on public replay state."""

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
from clasher.rl.imitation import load_corpus, load_public_observation_sidecar
from clasher.rl.oracle_corpus import file_sha256
from clasher.rl.structured_obs import StructuredObservationBuilder


@dataclass(frozen=True)
class PublicSlotExamples:
    entity_ids: torch.Tensor
    entity_features: torch.Tensor
    entity_mask: torch.Tensor
    entity_id_confidence: torch.Tensor
    entity_feature_confidence: torch.Tensor
    hand_ids: torch.Tensor
    hand_confidence: torch.Tensor
    global_features: torch.Tensor
    global_confidence: torch.Tensor
    legal: torch.Tensor
    target: torch.Tensor
    target_card: torch.Tensor
    episode: np.ndarray

    def select(self, indices: np.ndarray) -> PublicSlotExamples:
        selected = torch.as_tensor(indices, dtype=torch.long)
        return PublicSlotExamples(
            entity_ids=self.entity_ids[selected],
            entity_features=self.entity_features[selected],
            entity_mask=self.entity_mask[selected],
            entity_id_confidence=self.entity_id_confidence[selected],
            entity_feature_confidence=self.entity_feature_confidence[selected],
            hand_ids=self.hand_ids[selected],
            hand_confidence=self.hand_confidence[selected],
            global_features=self.global_features[selected],
            global_confidence=self.global_confidence[selected],
            legal=self.legal[selected],
            target=self.target[selected],
            target_card=self.target_card[selected],
            episode=self.episode[indices],
        )

    def __len__(self) -> int:
        return int(self.target.shape[0])


class PublicReactiveSlotScorer(nn.Module):
    """React to the full public board while scoring hand cards equivariantly."""

    card_stats: torch.Tensor
    identity: nn.Embedding
    entity_encoder: nn.Sequential
    global_encoder: nn.Sequential
    context_encoder: nn.Sequential
    card_scorer: nn.Sequential

    def __init__(
        self,
        *,
        num_tokens: int,
        card_stats: torch.Tensor,
        entity_feature_size: int,
        global_feature_size: int,
        identity_size: int = 16,
        hidden_size: int = 64,
    ) -> None:
        super().__init__()
        if card_stats.ndim != 2 or card_stats.shape[0] != num_tokens:
            raise ValueError("card stat table must match the token vocabulary")
        self.identity_size = int(identity_size)
        self.hidden_size = int(hidden_size)
        self.card_size = int(card_stats.shape[1])
        self.register_buffer("card_stats", card_stats.detach().float().clone())
        self.identity = nn.Embedding(num_tokens, identity_size, padding_idx=0)
        nn.init.zeros_(self.identity.weight)
        entity_input = (
            2 * entity_feature_size + self.card_size + identity_size + 1
        )
        self.entity_encoder = nn.Sequential(
            nn.Linear(entity_input, hidden_size),
            nn.GELU(),
            nn.Linear(hidden_size, hidden_size),
            nn.GELU(),
        )
        self.global_encoder = nn.Sequential(
            nn.Linear(2 * global_feature_size, hidden_size),
            nn.GELU(),
            nn.Linear(hidden_size, hidden_size),
            nn.GELU(),
        )
        self.context_encoder = nn.Sequential(
            nn.Linear(3 * hidden_size, hidden_size),
            nn.GELU(),
        )
        candidate_size = identity_size + self.card_size + 1
        self.card_scorer = nn.Sequential(
            nn.Linear(hidden_size + candidate_size, hidden_size),
            nn.GELU(),
            nn.Linear(hidden_size, 1),
        )

    def forward(self, examples: PublicSlotExamples) -> torch.Tensor:
        entity_confidence = examples.entity_feature_confidence
        identity_confidence = examples.entity_id_confidence.unsqueeze(-1)
        entity_dynamic = examples.entity_features * entity_confidence
        entity_static = self.card_stats[examples.entity_ids] * identity_confidence
        entity_identity = self.identity(examples.entity_ids) * identity_confidence
        entity_input = torch.cat(
            (
                entity_dynamic,
                entity_confidence,
                entity_static,
                entity_identity,
                identity_confidence,
            ),
            dim=-1,
        )
        encoded = self.entity_encoder(entity_input)
        mask = examples.entity_mask.unsqueeze(-1)
        encoded = encoded * mask
        count = mask.sum(dim=1).clamp_min(1)
        entity_mean = encoded.sum(dim=1) / count
        entity_max = encoded.masked_fill(~mask, -torch.inf).max(dim=1).values
        no_entities = ~examples.entity_mask.any(dim=1)
        entity_max = torch.where(no_entities[:, None], 0.0, entity_max)

        global_input = torch.cat(
            (
                examples.global_features * examples.global_confidence,
                examples.global_confidence,
            ),
            dim=-1,
        )
        global_context = self.global_encoder(global_input)
        context = self.context_encoder(
            torch.cat((entity_mean, entity_max, global_context), dim=-1)
        )

        hand_confidence = examples.hand_confidence.unsqueeze(-1)
        candidate = torch.cat(
            (
                self.identity(examples.hand_ids) * hand_confidence,
                self.card_stats[examples.hand_ids] * hand_confidence,
                hand_confidence,
            ),
            dim=-1,
        )
        expanded_context = context[:, None, :].expand(-1, NUM_HAND_SLOTS, -1)
        scores = self.card_scorer(torch.cat((expanded_context, candidate), dim=-1))
        assert isinstance(scores, torch.Tensor)
        return scores.squeeze(-1)


def _slot_legal_masks(action_masks: np.ndarray) -> np.ndarray:
    return np.asarray(
        action_masks[:, : NUM_HAND_SLOTS * NUM_TILES]
        .reshape(-1, NUM_HAND_SLOTS, NUM_TILES)
        .any(axis=-1),
        dtype=np.bool_,
    )


def load_examples(
    *,
    corpus_path: Path,
    public_sidecar: Path,
) -> tuple[PublicSlotExamples, tuple[str, ...]]:
    metadata, arrays = load_corpus(corpus_path)
    arrays = load_public_observation_sidecar(public_sidecar, base_arrays=arrays)
    expert = arrays["expert_actions"]
    selected = np.flatnonzero(expert < NUM_HAND_SLOTS * NUM_TILES)
    if selected.size == 0:
        raise ValueError("corpus has no placement examples")
    targets = np.asarray(expert[selected] // NUM_TILES, dtype=np.int64)
    hand_ids = np.asarray(
        arrays["hand_ids"][selected, :NUM_HAND_SLOTS], dtype=np.int64
    )
    return (
        PublicSlotExamples(
            entity_ids=torch.as_tensor(arrays["entity_ids"][selected], dtype=torch.long),
            entity_features=torch.as_tensor(
                arrays["entity_features"][selected], dtype=torch.float32
            ),
            entity_mask=torch.as_tensor(arrays["entity_mask"][selected], dtype=torch.bool),
            entity_id_confidence=torch.as_tensor(
                arrays["entity_id_confidence"][selected], dtype=torch.float32
            ),
            entity_feature_confidence=torch.as_tensor(
                arrays["entity_feature_confidence"][selected], dtype=torch.float32
            ),
            hand_ids=torch.as_tensor(hand_ids, dtype=torch.long),
            hand_confidence=torch.as_tensor(
                arrays["hand_id_confidence"][selected, :NUM_HAND_SLOTS],
                dtype=torch.float32,
            ),
            global_features=torch.as_tensor(
                arrays["global_features"][selected], dtype=torch.float32
            ),
            global_confidence=torch.as_tensor(
                arrays["global_feature_confidence"][selected], dtype=torch.float32
            ),
            legal=torch.as_tensor(
                _slot_legal_masks(arrays["action_masks"])[selected], dtype=torch.bool
            ),
            target=torch.as_tensor(targets, dtype=torch.long),
            target_card=torch.as_tensor(
                hand_ids[np.arange(len(selected)), targets], dtype=torch.long
            ),
            episode=np.asarray(arrays["episode_ids"][selected], dtype=np.int64),
        ),
        tuple(metadata.token_names),
    )


def _split_episodes(
    examples: PublicSlotExamples,
    *,
    seed: int,
    validation_fraction: float,
) -> tuple[np.ndarray, np.ndarray]:
    episodes = np.unique(examples.episode)
    rng = np.random.default_rng(seed)
    rng.shuffle(episodes)
    validation_count = max(1, round(len(episodes) * validation_fraction))
    validation_episodes = set(episodes[:validation_count].tolist())
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


def _card_weights(examples: PublicSlotExamples, indices: np.ndarray) -> torch.Tensor:
    cards = examples.target_card.numpy()
    counts = np.bincount(cards[indices], minlength=int(cards.max()) + 1)
    nonzero = counts[counts > 0]
    reference = float(np.median(nonzero)) if nonzero.size else 1.0
    result = np.ones(len(examples), dtype=np.float32)
    for index in indices:
        result[index] = min(4.0, math.sqrt(reference / max(1, counts[cards[index]])))
    result[indices] /= max(1e-8, float(result[indices].mean()))
    return torch.as_tensor(result)


@torch.no_grad()
def evaluate(
    model: PublicReactiveSlotScorer,
    examples: PublicSlotExamples,
    *,
    batch_size: int = 256,
) -> dict[str, float]:
    model.eval()
    losses = 0.0
    correct = 0
    for start in range(0, len(examples), batch_size):
        indices = np.arange(start, min(len(examples), start + batch_size))
        batch = examples.select(indices)
        logits = model(batch).masked_fill(~batch.legal, -torch.inf)
        losses += float(nn.functional.cross_entropy(logits, batch.target, reduction="sum"))
        correct += int((logits.argmax(dim=-1) == batch.target).sum())
    return {
        "samples": float(len(examples)),
        "loss": losses / len(examples),
        "accuracy": correct / len(examples),
    }


def fit(
    *,
    model: PublicReactiveSlotScorer,
    examples: PublicSlotExamples,
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
    for epoch in range(1, epochs + 1):
        model.train()
        shuffled = training_indices.copy()
        rng.shuffle(shuffled)
        for start in range(0, len(shuffled), batch_size):
            indices = shuffled[start : start + batch_size]
            batch = examples.select(indices)
            logits = model(batch).masked_fill(~batch.legal, -1e9)
            row_losses = nn.functional.cross_entropy(
                logits, batch.target, reduction="none"
            )
            loss = (row_losses * weights[indices]).mean()
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        train_metrics = evaluate(model, examples.select(training_indices))
        validation_metrics = evaluate(model, examples.select(validation_indices))
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-corpus", required=True, type=Path)
    parser.add_argument("--train-sidecar", required=True, type=Path)
    parser.add_argument("--validation-corpus", required=True, type=Path)
    parser.add_argument("--validation-sidecar", required=True, type=Path)
    parser.add_argument("--heldout-corpus", required=True, type=Path)
    parser.add_argument("--heldout-sidecar", required=True, type=Path)
    parser.add_argument("--chronology-corpus", required=True, type=Path)
    parser.add_argument("--chronology-sidecar", required=True, type=Path)
    parser.add_argument("--decks-path", default="decks.json", type=Path)
    parser.add_argument("--semantics-version", choices=(1, 2, 3), type=int, default=1)
    parser.add_argument("--identity-size", type=int, default=16)
    parser.add_argument("--hidden-size", type=int, default=64)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    corpus_paths = {
        name: resolve_path(getattr(args, f"{name}_corpus"), must_exist=True)
        for name in ("train", "validation", "heldout", "chronology")
    }
    sidecar_paths = {
        name: resolve_path(getattr(args, f"{name}_sidecar"), must_exist=True)
        for name in ("train", "validation", "heldout", "chronology")
    }
    examples: dict[str, PublicSlotExamples] = {}
    token_names: tuple[str, ...] | None = None
    for name in ("train", "validation", "heldout", "chronology"):
        examples[name], current_tokens = load_examples(
            corpus_path=corpus_paths[name], public_sidecar=sidecar_paths[name]
        )
        token_names = token_names or current_tokens
        if current_tokens != token_names:
            raise ValueError("corpus token vocabularies differ")
    assert token_names is not None
    builder = StructuredObservationBuilder(
        decks_path=resolve_path(args.decks_path, must_exist=True),
        token_names=token_names,
        card_semantics_version=args.semantics_version,
    )
    card_stats = torch.as_tensor(builder.card_stat_features, dtype=torch.float32)
    training_indices, internal_validation_indices = _split_episodes(
        examples["train"],
        seed=args.seed,
        validation_fraction=args.validation_fraction,
    )
    torch.manual_seed(args.seed)
    model = PublicReactiveSlotScorer(
        num_tokens=len(token_names),
        card_stats=card_stats,
        entity_feature_size=examples["train"].entity_features.shape[-1],
        global_feature_size=examples["train"].global_features.shape[-1],
        identity_size=args.identity_size,
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
        "validation": evaluate(model, examples["validation"]),
        "heldout_archetypes": evaluate(model, examples["heldout"]),
        "chronology": evaluate(model, examples["chronology"]),
    }
    output = resolve_path(args.output)
    if output.exists() or output.with_suffix(".json").exists():
        raise FileExistsError(f"refusing to overwrite reactive slot probe: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    torch.save(
        {
            "schema_version": 1,
            "architecture": "public-reactive-slot-deepset-v1",
            "semantics_version": args.semantics_version,
            "identity_size": args.identity_size,
            "hidden_size": args.hidden_size,
            "token_names": token_names,
            "state_dict": best_state,
            "metrics": metrics,
            "history": history,
            "sources": {
                name: {
                    "corpus": str(corpus_paths[name]),
                    "corpus_sha256": file_sha256(corpus_paths[name]),
                    "sidecar": str(sidecar_paths[name]),
                    "sidecar_sha256": file_sha256(sidecar_paths[name]),
                }
                for name in corpus_paths
            },
        },
        output,
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "architecture": "public-reactive-slot-deepset-v1",
        "seed": args.seed,
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "identity_size": args.identity_size,
        "hidden_size": args.hidden_size,
        "parameter_count": parameter_count,
        "selected_epoch": int(min(history, key=lambda row: row["validation_loss"])["epoch"]),
        "metrics": metrics,
        "checkpoint": str(output),
        "checkpoint_sha256": file_sha256(output),
    }
    output.with_suffix(".json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
