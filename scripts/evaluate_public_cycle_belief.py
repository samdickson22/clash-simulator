"""Measure whether persistent seen-card memory improves public cycle belief."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch
from torch import Tensor, nn
from torch.utils.data import DataLoader, TensorDataset

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES  # type: ignore[import-untyped]


@dataclass(frozen=True)
class BeliefMetrics:
    samples: int
    mean_history_plays: float
    mean_seen_cards: float
    binary_cross_entropy: float
    top4_recall: float
    exact_hand_accuracy: float


def build_public_cycle_examples(
    corpus: dict[str, np.ndarray],
    *,
    recent_slots: int = 4,
    seen_slots: int = 8,
) -> dict[str, np.ndarray]:
    """Build online-only history features and hidden-hand targets by episode."""
    required = {
        "hand_ids",
        "expert_actions",
        "episode_ids",
        "source_frames",
    }
    missing = required.difference(corpus)
    if missing:
        raise ValueError(f"cycle corpus lacks arrays: {sorted(missing)}")
    hand_ids = np.asarray(corpus["hand_ids"], dtype=np.int64)
    actions = np.asarray(corpus["expert_actions"], dtype=np.int64)
    episode_ids = np.asarray(corpus["episode_ids"], dtype=np.int64)
    frames = np.asarray(corpus["source_frames"], dtype=np.int64)
    if hand_ids.ndim != 2 or hand_ids.shape[1] < NUM_HAND_SLOTS:
        raise ValueError("cycle corpus hand_ids must contain four hand slots")
    sample_count = hand_ids.shape[0]
    if any(array.shape[0] != sample_count for array in (actions, episode_ids, frames)):
        raise ValueError("cycle corpus arrays have inconsistent sample counts")

    recent_ids = np.zeros((sample_count, recent_slots), dtype=np.int64)
    recent_ages = np.zeros((sample_count, recent_slots), dtype=np.float32)
    seen_ids = np.zeros((sample_count, seen_slots), dtype=np.int64)
    history_counts = np.zeros((sample_count,), dtype=np.float32)
    targets = np.zeros((sample_count, int(hand_ids.max(initial=0)) + 1), dtype=np.float32)

    histories: dict[int, list[tuple[int, int]]] = {}
    seen: dict[int, list[int]] = {}
    for index in range(sample_count):
        episode = int(episode_ids[index])
        history = histories.setdefault(episode, [])
        discovered = seen.setdefault(episode, [])
        current_frame = int(frames[index])
        for slot, (play_frame, card_id) in enumerate(reversed(history[-recent_slots:])):
            recent_ids[index, slot] = card_id
            recent_ages[index, slot] = min(1.0, max(0.0, (current_frame - play_frame) / 3600.0))
        seen_ids[index, : min(seen_slots, len(discovered))] = discovered[:seen_slots]
        history_counts[index] = min(1.0, len(history) / 16.0)
        for card_id in hand_ids[index, :NUM_HAND_SLOTS]:
            if card_id > 0:
                targets[index, int(card_id)] = 1.0

        action = int(actions[index])
        if 0 <= action < NUM_HAND_SLOTS * NUM_TILES:
            card_id = int(hand_ids[index, action // NUM_TILES])
            if card_id > 0:
                history.append((current_frame, card_id))
                if card_id not in discovered and len(discovered) < seen_slots:
                    discovered.append(card_id)
    return {
        "recent_ids": recent_ids,
        "recent_ages": recent_ages,
        "seen_ids": seen_ids,
        "history_counts": history_counts,
        "targets": targets,
    }


class PublicCycleBelief(nn.Module):
    def __init__(self, num_tokens: int, *, use_seen_deck: bool, width: int = 64) -> None:
        super().__init__()
        self.use_seen_deck = use_seen_deck
        self.card_embedding = nn.Embedding(num_tokens, width, padding_idx=0)
        self.recent_slot_embedding = nn.Embedding(4, width)
        self.recent_age_projection = nn.Linear(1, width)
        input_width = width + 1 + (width if use_seen_deck else 0)
        self.head = nn.Sequential(
            nn.Linear(input_width, 2 * width),
            nn.GELU(),
            nn.Linear(2 * width, num_tokens),
        )

    @staticmethod
    def _masked_mean(tokens: Tensor, ids: Tensor) -> Tensor:
        valid = ids.ne(0).unsqueeze(-1)
        result: Tensor = (tokens * valid).sum(dim=1) / valid.sum(dim=1).clamp_min(1)
        return result

    def forward(
        self,
        recent_ids: Tensor,
        recent_ages: Tensor,
        seen_ids: Tensor,
        history_counts: Tensor,
    ) -> Tensor:
        slots = torch.arange(4, device=recent_ids.device).view(1, 4)
        recent = (
            self.card_embedding(recent_ids)
            + self.recent_slot_embedding(slots)
            + self.recent_age_projection(recent_ages.unsqueeze(-1))
        )
        features = [self._masked_mean(recent, recent_ids), history_counts.unsqueeze(-1)]
        if self.use_seen_deck:
            features.append(self._masked_mean(self.card_embedding(seen_ids), seen_ids))
        logits: Tensor = self.head(torch.cat(features, dim=-1))
        return logits


def _load_examples(path: Path) -> tuple[dict[str, np.ndarray], int]:
    with np.load(path, allow_pickle=False) as corpus:
        arrays = {name: np.asarray(corpus[name]) for name in corpus.files if name != "metadata_json"}
        metadata = json.loads(str(corpus["metadata_json"]))
    examples = build_public_cycle_examples(arrays)
    return examples, len(metadata["token_names"])


def _tensor_dataset(examples: dict[str, np.ndarray], num_tokens: int) -> TensorDataset:
    targets = examples["targets"]
    if targets.shape[1] < num_tokens:
        targets = np.pad(targets, ((0, 0), (0, num_tokens - targets.shape[1])))
    return TensorDataset(
        torch.from_numpy(examples["recent_ids"]),
        torch.from_numpy(examples["recent_ages"]),
        torch.from_numpy(examples["seen_ids"]),
        torch.from_numpy(examples["history_counts"]),
        torch.from_numpy(targets[:, :num_tokens]),
    )


@torch.no_grad()
def evaluate(
    model: PublicCycleBelief,
    dataset: TensorDataset,
    *,
    device: torch.device,
    batch_size: int,
) -> BeliefMetrics:
    model.eval()
    losses = 0.0
    recall = 0.0
    exact = 0.0
    history_total = 0.0
    seen_total = 0.0
    samples = 0
    for recent_ids, recent_ages, seen_ids, history_counts, targets in DataLoader(
        dataset, batch_size=batch_size, shuffle=False
    ):
        recent_ids = recent_ids.to(device)
        recent_ages = recent_ages.to(device)
        seen_ids = seen_ids.to(device)
        history_counts = history_counts.to(device)
        targets = targets.to(device)
        logits = model(recent_ids, recent_ages, seen_ids, history_counts)
        loss = nn.functional.binary_cross_entropy_with_logits(logits, targets)
        batch = targets.shape[0]
        losses += float(loss) * batch
        predicted = logits.topk(NUM_HAND_SLOTS, dim=-1).indices
        predicted_mask = torch.zeros_like(targets).scatter_(-1, predicted, 1.0)
        overlap = (predicted_mask * targets).sum(dim=-1)
        target_count = targets.sum(dim=-1).clamp_min(1.0)
        recall += float((overlap / target_count).sum())
        exact += float((predicted_mask == targets).all(dim=-1).sum())
        history_total += float(history_counts.sum()) * 16.0
        seen_total += float(seen_ids.ne(0).sum())
        samples += batch
    return BeliefMetrics(
        samples=samples,
        mean_history_plays=history_total / samples,
        mean_seen_cards=seen_total / samples,
        binary_cross_entropy=losses / samples,
        top4_recall=recall / samples,
        exact_hand_accuracy=exact / samples,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--split-root",
        type=Path,
        default=Path("datasets/derived/tv_royale_raw_cascade_2000_split_seed1045801"),
    )
    parser.add_argument("--seed", type=int, default=1048801)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device(args.device)

    split_examples: dict[str, dict[str, np.ndarray]] = {}
    num_tokens = 0
    for split in ("train", "validation", "archetype_test", "chronology_test"):
        examples, split_tokens = _load_examples(args.split_root / f"{split}.npz")
        split_examples[split] = examples
        if num_tokens and split_tokens != num_tokens:
            raise ValueError("cycle splits have inconsistent token vocabularies")
        num_tokens = split_tokens
    train_dataset = _tensor_dataset(split_examples["train"], num_tokens)
    positive_weight = torch.full((num_tokens,), (num_tokens - 4.0) / 4.0, device=device)
    positive_weight[0] = 0.0

    reports: dict[str, object] = {}
    for name, use_seen in (("recent4", False), ("recent4_seen8", True)):
        torch.manual_seed(args.seed)
        model = PublicCycleBelief(num_tokens, use_seen_deck=use_seen).to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)
        loader = DataLoader(
            train_dataset,
            batch_size=args.batch_size,
            shuffle=True,
            generator=torch.Generator().manual_seed(args.seed),
        )
        model.train()
        for _ in range(args.epochs):
            for recent_ids, recent_ages, seen_ids, history_counts, targets in loader:
                recent_ids = recent_ids.to(device)
                recent_ages = recent_ages.to(device)
                seen_ids = seen_ids.to(device)
                history_counts = history_counts.to(device)
                targets = targets.to(device)
                optimizer.zero_grad(set_to_none=True)
                logits = model(recent_ids, recent_ages, seen_ids, history_counts)
                loss = nn.functional.binary_cross_entropy_with_logits(
                    logits, targets, pos_weight=positive_weight
                )
                loss.backward()
                optimizer.step()
        reports[name] = {
            split: asdict(
                evaluate(
                    model,
                    _tensor_dataset(examples, num_tokens),
                    device=device,
                    batch_size=args.batch_size,
                )
            )
            for split, examples in split_examples.items()
        }

    payload = {
        "schema_version": 1,
        "seed": args.seed,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "num_tokens": num_tokens,
        "models": reports,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
