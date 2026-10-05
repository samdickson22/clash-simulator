"""Behaviour cloning on human-replay shards with the council pilot policy.

The loss is the scripted warm start's: cross-entropy on the masked joint
action log-probabilities (``fit_imitation_corpus(imitation_objective="exact")``),
AdamW, gradient clip 0.5, 128-step sequences. The corpus is far larger than a
scripted warm-start corpus, so it is streamed shard by shard and each episode is
unrolled in order with its recurrent state carried between chunks (truncated
backpropagation) instead of replaying the full episode prefix before every chunk.

Research artifact (strategy amendment 2026-10-01); checkpoints written here are
not Tier A admitted pilot arms and say so in their metadata. The privileged
critic receives no target and stays at its initial weights.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

import numpy as np
import torch
from torch import nn

from .common import BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES
from .human_replay_demonstrations import (
    LABEL_SOURCE,
    NO_OP_ACTION,
    PROVENANCE,
    HumanReplayShard,
    load_human_replay_shard,
)
from .imitation import CORPUS_SCHEMA_VERSION, CorpusMetadata, _checkpoint_payload, _sequence_batch_inputs
from .model import ClasherPolicy, PolicyConfig
from .reward_model import OBJECTIVE_V1

FIT_SCHEMA = "clasher.human-replay-bc.v1"


@dataclass(frozen=True)
class HumanReplayFitConfig:
    seed: int
    variant: str
    learning_rate: float = 1e-4
    sequence_length: int = 128
    sequences_per_step: int = 1
    streams: int = 8
    epochs: int = 1
    pool_parts: int = 4
    # Weight of a supervised wait row that is not within ``near_play_rows``
    # decision steps before a play. 1.0 is the scripted warm start's handling.
    wait_row_weight: float = 1.0
    near_play_rows: int = 4
    # Keep only perspectives whose recorded result is a win (filtered BC).
    winners_only: bool = False
    # Stop after this many pools in total (None = every pool of every epoch).
    max_pools: int | None = None
    gradient_clip: float = 0.5

    def __post_init__(self) -> None:
        if self.sequence_length < 2 or self.sequences_per_step < 1 or self.streams < self.sequences_per_step:
            raise ValueError("invalid sequence or stream counts")
        if not 0.0 < self.wait_row_weight <= 1.0 or self.near_play_rows < 0:
            raise ValueError("wait rows may only be down-weighted")
        if self.epochs < 1 or self.pool_parts < 1 or self.learning_rate <= 0:
            raise ValueError("invalid fit schedule")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def supervision_weights(labels: np.ndarray, valid: np.ndarray, *, wait_row_weight: float, near_play_rows: int) -> np.ndarray:
    """Per-row loss weights for one episode.

    Plays and the ``near_play_rows`` steps before each play keep weight one;
    other waits get ``wait_row_weight``. Unsupervised rows get zero.
    """
    weights = np.ones(len(labels), dtype=np.float32)
    if wait_row_weight != 1.0:
        plays = np.flatnonzero(labels < NO_OP_ACTION)
        near = np.zeros(len(labels) + 1, dtype=np.int64)
        np.add.at(near, np.maximum(plays - near_play_rows, 0), 1)
        np.add.at(near, plays + 1, -1)
        protected = np.cumsum(near[:-1]) > 0
        weights[~protected] = wait_row_weight
    weights[~np.asarray(valid, dtype=np.bool_)] = 0.0
    return weights


class _SelectedRowsTileDecoder(nn.Module):
    """Run the tile decoder only on rows whose loss reads location logits.

    A wait row's joint cross-entropy does not depend on its location logits
    (each slot's masked tile distribution sums to one), so its gradient through
    the decoder is zero. Skipped rows pass the undecoded tile queries through.
    """

    def __init__(self, inner: nn.Module) -> None:
        super().__init__()
        self._inner = (inner,)  # tuple: keep the real decoder out of this module's registry
        self.rows: torch.Tensor | None = None

    def forward(self, queries, context, valid):
        if self.rows is None:
            return self._inner[0](queries, context, valid)
        output = queries.clone()
        if self.rows.numel():
            output[self.rows] = self._inner[0](queries[self.rows], context[self.rows], valid[self.rows])
        return output


@contextmanager
def selected_tile_rows(model: ClasherPolicy):
    """Temporarily route the model's tile decoder through a row selector."""
    inner = model._modules.get("tile_decoder")
    if inner is None:
        yield None
        return
    selector = _SelectedRowsTileDecoder(inner)
    model._modules["tile_decoder"] = selector
    try:
        yield selector
    finally:
        model._modules["tile_decoder"] = inner


def episode_arrays(shard: HumanReplayShard, summary: dict[str, Any]) -> dict[str, np.ndarray]:
    """One perspective's rows in the scripted-demonstration format, trimmed to its entity width."""
    begin, count = int(summary["row_offset"]), int(summary["rows"])
    rows = np.arange(begin, begin + count)
    width = max(1, int(shard.compact["entity_counts"][rows].max()))
    arrays = shard.arrays(rows, entity_width=width)
    if not arrays["episode_starts"][0] or arrays["episode_starts"][1:].any():
        raise ValueError("a perspective must be one episode")
    return arrays


def _pad_chunks(chunks: list[dict[str, np.ndarray]], length: int) -> dict[str, np.ndarray]:
    """Stack chunks to [batch * length, ...] with a shared entity width.

    A short final chunk repeats its last row; the caller gives those rows zero weight.
    """
    width = max(chunk["entity_ids"].shape[1] for chunk in chunks)
    merged: dict[str, list[np.ndarray]] = {}
    for chunk in chunks:
        rows = len(chunk["expert_actions"])
        index = np.minimum(np.arange(length), rows - 1)
        for name, values in chunk.items():
            values = values[index]
            if name.startswith("entity_") and values.shape[1] < width:
                padded = np.zeros((length, width, *values.shape[2:]), dtype=values.dtype)
                padded[:, :values.shape[1]] = values
                values = padded
            merged.setdefault(name, []).append(values)
    return {name: np.concatenate(values) for name, values in merged.items()}


def _slice(arrays: dict[str, np.ndarray], begin: int, end: int) -> dict[str, np.ndarray]:
    return {name: values[begin:end] for name, values in arrays.items()}


def _masked_log_softmax(logits: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    return torch.log_softmax(logits.masked_fill(~mask, -1e9), dim=-1)


class HeadMetrics:
    """Validation sums for the three policy factors: when, card and tile."""

    def __init__(self) -> None:
        self.sums: dict[str, float] = {}

    def add(self, name: str, value) -> None:
        self.sums[name] = self.sums.get(name, 0.0) + float(value)

    @torch.no_grad()
    def update(self, output, action_mask: torch.Tensor, labels: torch.Tensor, supervised: torch.Tensor) -> None:
        mask = action_mask[supervised]
        target = labels[supervised]
        type_logits = output.action_type_logits[supervised]
        location_logits = output.location_logits[supervised]
        joint = output.joint_logits[supervised]
        rows = torch.arange(len(target), device=target.device)
        placement = mask[:, :NO_OP_ACTION].reshape(-1, NUM_HAND_SLOTS, NUM_TILES)
        slot_legal = placement.any(dim=-1)
        type_mask = torch.cat([slot_legal, mask[:, NO_OP_ACTION:]], dim=-1)
        type_logp = _masked_log_softmax(type_logits, type_mask)
        wait_logp = type_logp[:, NUM_HAND_SLOTS]
        play_logp = torch.log1p(-wait_logp.exp().clamp(max=1 - 1e-7))
        is_play = target < NO_OP_ACTION
        self.add("rows", len(target))
        self.add("joint_loss", -joint[rows, target].sum())
        self.add("joint_correct", (joint.argmax(dim=-1) == target).sum())
        self.add("play_rows", is_play.sum())
        # When: rows where at least one card could be played.
        playable = slot_legal.any(dim=-1)
        self.add("when_rows", playable.sum())
        self.add("when_loss", -torch.where(is_play, play_logp, wait_logp)[playable].sum())
        predicted_play = wait_logp.exp() < 0.5
        self.add("when_correct", (predicted_play == is_play)[playable].sum())
        self.add("when_wait_rows", (playable & ~is_play).sum())
        self.add("wait_probability_on_wait_rows", wait_logp.exp()[playable & ~is_play].sum())
        self.add("wait_probability_on_play_rows", wait_logp.exp()[is_play].sum())
        self.add("play_recall", predicted_play[is_play].sum())
        self.add("predicted_plays", predicted_play[playable].sum())
        if not bool(is_play.any()):
            return
        slot = target[is_play] // NUM_TILES
        tile = target[is_play] % NUM_TILES
        play_rows = torch.arange(len(slot), device=target.device)
        # Card: the slot given that a card is played.
        card_logp = type_logp[is_play][:, :NUM_HAND_SLOTS] - play_logp[is_play].unsqueeze(-1)
        self.add("card_loss", -card_logp[play_rows, slot].sum())
        card_choice = type_logp[is_play][:, :NUM_HAND_SLOTS].argmax(dim=-1)
        self.add("card_correct", (card_choice == slot).sum())
        multiple = slot_legal[is_play].sum(dim=-1) > 1
        self.add("card_choice_rows", multiple.sum())
        self.add("card_choice_correct", ((card_choice == slot) & multiple).sum())
        # Tile: the location given the recorded slot.
        tile_logp = _masked_log_softmax(location_logits[is_play][play_rows, slot], placement[is_play][play_rows, slot])
        self.add("tile_loss", -tile_logp[play_rows, tile].sum())
        top = tile_logp.topk(5, dim=-1).indices
        self.add("tile_top1", (top[:, 0] == tile).sum())
        self.add("tile_top5", (top == tile.unsqueeze(-1)).any(dim=-1).sum())
        dx = (top[:, 0] % BOARD_WIDTH - tile % BOARD_WIDTH).abs()
        dy = (top[:, 0] // BOARD_WIDTH - tile // BOARD_WIDTH).abs()
        self.add("tile_within_1", ((dx <= 1) & (dy <= 1)).sum())
        self.add("tile_distance", torch.sqrt((dx * dx + dy * dy).float()).sum())

    def result(self) -> dict[str, float]:
        sums = self.sums
        rows, plays = max(1.0, sums.get("rows", 0.0)), max(1.0, sums.get("play_rows", 0.0))
        when = max(1.0, sums.get("when_rows", 0.0))
        return {
            "rows": sums.get("rows", 0.0), "play_rows": sums.get("play_rows", 0.0),
            "joint_loss": sums.get("joint_loss", 0.0) / rows,
            "joint_accuracy": sums.get("joint_correct", 0.0) / rows,
            "when_rows": sums.get("when_rows", 0.0),
            "when_loss": sums.get("when_loss", 0.0) / when,
            "when_accuracy": sums.get("when_correct", 0.0) / when,
            "wait_probability_when_playable_and_human_waited": sums.get("wait_probability_on_wait_rows", 0.0)
            / max(1.0, sums.get("when_wait_rows", 0.0)),
            "wait_probability_when_human_played": sums.get("wait_probability_on_play_rows", 0.0) / plays,
            "play_recall_at_half": sums.get("play_recall", 0.0) / plays,
            "play_precision_at_half": sums.get("play_recall", 0.0) / max(1.0, sums.get("predicted_plays", 0.0)),
            "card_loss": sums.get("card_loss", 0.0) / plays,
            "card_accuracy": sums.get("card_correct", 0.0) / plays,
            "card_choice_rows": sums.get("card_choice_rows", 0.0),
            "card_choice_accuracy": sums.get("card_choice_correct", 0.0) / max(1.0, sums.get("card_choice_rows", 0.0)),
            "tile_loss": sums.get("tile_loss", 0.0) / plays,
            "tile_top1_accuracy": sums.get("tile_top1", 0.0) / plays,
            "tile_top5_accuracy": sums.get("tile_top5", 0.0) / plays,
            "tile_within_1_accuracy": sums.get("tile_within_1", 0.0) / plays,
            "tile_mean_distance": sums.get("tile_distance", 0.0) / plays,
        }


def _episode_stream(parts: Sequence[Path], *, keep: Callable[[dict[str, Any]], bool], rng: np.random.Generator | None) -> Iterator[tuple[dict[str, Any], dict[str, np.ndarray]]]:
    """Yield (summary, arrays) for the kept perspectives of the given shard parts."""
    selected: list[tuple[HumanReplayShard, dict[str, Any]]] = []
    for path in parts:
        shard = load_human_replay_shard(path)
        selected.extend((shard, summary) for summary in shard.header["perspectives"] if keep(summary))
    order = np.arange(len(selected)) if rng is None else rng.permutation(len(selected))
    for index in order:
        shard, summary = selected[int(index)]
        yield summary, episode_arrays(shard, summary)


def _run_streams(
    model: ClasherPolicy,
    episodes: Iterator[tuple[dict[str, Any], dict[str, np.ndarray]]],
    *,
    streams: int,
    sequences_per_step: int,
    sequence_length: int,
    device: torch.device,
    step: Callable[[Any, dict[str, np.ndarray], torch.Tensor, torch.Tensor], None],
    weights_for: Callable[[dict[str, Any], dict[str, np.ndarray]], np.ndarray],
    select_play_rows: bool,
) -> int:
    """Unroll episodes in order on parallel streams; ``step`` consumes each batch.

    Returns the number of real (unpadded) rows processed.
    """
    active: list[dict[str, Any] | None] = [None] * streams
    exhausted = False
    cursor = 0
    processed = 0
    with selected_tile_rows(model) as selector:
        while True:
            chosen: list[int] = []
            for offset in range(streams):
                index = (cursor + offset) % streams
                if active[index] is None and not exhausted:
                    try:
                        summary, arrays = next(episodes)
                    except StopIteration:
                        exhausted = True
                    else:
                        active[index] = {"arrays": arrays, "position": 0, "state": None,
                                         "weights": weights_for(summary, arrays)}
                if active[index] is not None:
                    chosen.append(index)
                    if len(chosen) == sequences_per_step:
                        break
            if not chosen:
                break
            cursor = (chosen[-1] + 1) % streams
            chunks, weights, lengths = [], [], []
            for index in chosen:
                stream = active[index]
                begin = stream["position"]
                end = min(begin + sequence_length, len(stream["weights"]))
                chunks.append(_slice(stream["arrays"], begin, end))
                row_weights = np.zeros(sequence_length, dtype=np.float32)
                row_weights[:end - begin] = stream["weights"][begin:end]
                weights.append(row_weights)
                lengths.append(end - begin)
            batch = _pad_chunks(chunks, sequence_length)
            count = len(chosen)
            inputs = _sequence_batch_inputs(batch, np.arange(count * sequence_length).reshape(count, sequence_length),
                                            device, trim_entity_padding=False, reset_memory=False)
            initial = model.initial_state(count, device=device)
            state = tuple(torch.stack([initial[part][row] if active[index]["state"] is None else active[index]["state"][part]
                                       for row, index in enumerate(chosen)]) for part in (0, 1))
            weight_tensor = torch.as_tensor(np.concatenate(weights), device=device)
            labels = torch.as_tensor(batch["expert_actions"], dtype=torch.long, device=device)
            if selector is not None:
                selector.rows = (torch.nonzero((labels < NO_OP_ACTION) & (weight_tensor > 0)).flatten()
                                 if select_play_rows else None)
            output = model(inputs, state)
            step(output, batch, labels, weight_tensor)
            for row, index in enumerate(chosen):
                stream = active[index]
                stream["position"] += lengths[row]
                processed += lengths[row]
                if stream["position"] >= len(stream["weights"]):
                    active[index] = None
                else:
                    stream["state"] = tuple(output.next_state[part][row].detach() for part in (0, 1))
    return processed


@torch.no_grad()
def evaluate_human_replay(
    model: ClasherPolicy,
    parts: Sequence[Path],
    *,
    keep: Callable[[dict[str, Any]], bool],
    device: torch.device,
    sequence_length: int = 128,
    streams: int = 8,
    maximum_perspectives: int | None = None,
) -> dict[str, float]:
    """Per-head metrics on whole episodes in order, with the real recurrent state."""
    was_training = model.training
    model.eval()
    metrics = HeadMetrics()
    remaining = [maximum_perspectives]

    def limited():
        for item in _episode_stream(parts, keep=keep, rng=None):
            if remaining[0] is not None:
                if remaining[0] <= 0:
                    return
                remaining[0] -= 1
            metrics.add("perspectives", 1)
            yield item

    def step(output, batch, labels, weights):
        flat = type("Flat", (), {name: getattr(output, name).reshape(-1, *getattr(output, name).shape[2:])
                                for name in ("joint_logits", "action_type_logits", "location_logits")})
        mask = torch.as_tensor(batch["action_masks"], dtype=torch.bool, device=labels.device)
        metrics.update(flat, mask, labels, weights > 0)

    try:
        _run_streams(model, limited(), streams=streams, sequences_per_step=streams, sequence_length=sequence_length,
                     device=device, step=step, select_play_rows=False,
                     weights_for=lambda summary, arrays: arrays["expert_action_supervision_valid"].astype(np.float32))
    finally:
        model.train(was_training)
    return metrics.result() | {"perspectives": metrics.sums.get("perspectives", 0.0)}


def _atomic_torch_save(payload: dict[str, Any], path: Path) -> None:
    temporary = path.with_name(path.name + ".tmp")
    torch.save(payload, temporary)
    os.replace(temporary, path)


def fit_human_replay(
    *,
    parts: Sequence[Path],
    output_checkpoint: Path,
    model_config: PolicyConfig,
    card_stat_features: np.ndarray,
    config: HumanReplayFitConfig,
    device: torch.device,
    initial_checkpoint: Path | None = None,
    checkpoint_metadata: dict[str, Any] | None = None,
    validation_perspectives: int | None = 200,
    log: Callable[[dict[str, Any]], None] = lambda record: print(json.dumps(record), flush=True),
) -> dict[str, Any]:
    """Fit the pilot policy to human-replay shards; resumable at pool boundaries.

    ``<output>.state.pt`` holds the model, optimizer and position after every
    pool. Rerunning with the same arguments continues from it; the final
    checkpoint is written once every pool is done.
    """
    parts = [Path(path) for path in sorted(parts)]
    if not parts:
        raise ValueError("no shard parts")
    if output_checkpoint.exists():
        raise FileExistsError("human-replay checkpoint already exists")
    header = load_human_replay_shard(parts[0]).header
    token_names = tuple(header["token_names"])
    if tuple(model_config.public_token_names) != token_names or model_config.public_contract_version != 4:
        raise ValueError("model config does not match the shard public contract")
    if model_config.max_entities != header["max_entities"]:
        raise ValueError("model entity capacity differs from the shards")
    torch.manual_seed(config.seed)
    np.random.seed(config.seed)
    model = ClasherPolicy(model_config, card_stat_features).to(device)
    initial_sha = None
    if initial_checkpoint is not None:
        payload = torch.load(initial_checkpoint, map_location=device, weights_only=False)
        if tuple(payload["token_names"]) != token_names:
            raise ValueError("initial checkpoint vocabulary does not match the shards")
        model.load_state_dict(payload["model_state_dict"])
        initial_sha = file_sha256(initial_checkpoint)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate)
    parameters = list(model.parameters())
    plan = {"schema": FIT_SCHEMA, "config": asdict(config), "parts": [path.name for path in parts],
            "initial_checkpoint_sha256": initial_sha, "token_names": list(token_names)}
    state_path = output_checkpoint.with_name(output_checkpoint.name + ".state.pt")
    progress = {"pools_done": 0, "steps": 0, "rows": 0, "weighted_rows": 0.0, "elapsed_seconds": 0.0, "history": []}
    if state_path.exists():
        saved = torch.load(state_path, map_location=device, weights_only=False)
        if saved["plan"] != plan:
            raise ValueError("resume state was written under a different fit plan")
        model.load_state_dict(saved["model_state_dict"])
        optimizer.load_state_dict(saved["optimizer_state_dict"])
        progress = saved["progress"]
        log({"event": "resumed", "pools_done": progress["pools_done"], "rows": progress["rows"]})

    def train_keep(summary: dict[str, Any]) -> bool:
        return summary["fit_split"] == 0 and (not config.winners_only or summary["recorded_result"] == 1)

    def validation_keep(summary: dict[str, Any]) -> bool:
        return summary["fit_split"] == 1

    pools: list[tuple[int, int, list[Path]]] = []
    for epoch in range(config.epochs):
        order = np.random.default_rng([config.seed, epoch]).permutation(len(parts))
        for index in range(0, len(parts), config.pool_parts):
            pools.append((epoch, index // config.pool_parts, [parts[int(i)] for i in order[index:index + config.pool_parts]]))
    if config.max_pools is not None:
        pools = pools[:config.max_pools]
    window = {"loss": 0.0, "weight": 0.0}

    def train_step(output, batch, labels, weights):
        logits = output.joint_logits.reshape(-1, output.joint_logits.shape[-1])
        supervised = weights > 0
        if not bool(supervised.any()):
            return
        targets = labels.masked_fill(~supervised, NO_OP_ACTION)
        per_row = nn.functional.cross_entropy(logits, targets, reduction="none")
        selected = weights[supervised]
        loss = (per_row[supervised] * selected).sum() / selected.sum().clamp_min(1e-12)
        if not bool(torch.isfinite(loss)):
            raise FloatingPointError("non-finite human-replay imitation loss")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        norm = nn.utils.clip_grad_norm_(parameters, config.gradient_clip)
        if not bool(torch.isfinite(norm)):
            raise FloatingPointError("non-finite human-replay imitation gradient")
        optimizer.step()
        progress["steps"] += 1
        progress["weighted_rows"] += float(selected.sum())
        window["loss"] += float(loss.detach()) * float(selected.sum())
        window["weight"] += float(selected.sum())

    model.train()
    for position, (epoch, pool_index, pool_parts) in enumerate(pools):
        if position < progress["pools_done"]:
            continue
        started = time.monotonic()
        window.update(loss=0.0, weight=0.0)
        rng = np.random.default_rng([config.seed, epoch, pool_index, 1])
        rows = _run_streams(
            model, _episode_stream(pool_parts, keep=train_keep, rng=rng), streams=config.streams,
            sequences_per_step=config.sequences_per_step, sequence_length=config.sequence_length, device=device,
            step=train_step, select_play_rows=True,
            weights_for=lambda summary, arrays: supervision_weights(
                arrays["expert_actions"], arrays["expert_action_supervision_valid"],
                wait_row_weight=config.wait_row_weight, near_play_rows=config.near_play_rows))
        progress["rows"] += rows
        progress["pools_done"] = position + 1
        progress["elapsed_seconds"] += time.monotonic() - started
        record = {"event": "pool", "epoch": epoch, "pool": pool_index, "pools_done": position + 1, "pools": len(pools),
                  "rows": progress["rows"], "steps": progress["steps"],
                  "train_loss": window["loss"] / max(1e-12, window["weight"]),
                  "rows_per_second": rows / max(1e-9, time.monotonic() - started),
                  "elapsed_seconds": round(progress["elapsed_seconds"], 1)}
        progress["history"].append(record)
        _atomic_torch_save({"plan": plan, "model_state_dict": model.state_dict(),
                            "optimizer_state_dict": optimizer.state_dict(), "progress": progress}, state_path)
        log(record)

    validation = evaluate_human_replay(model, parts, keep=validation_keep, device=device,
                                       sequence_length=config.sequence_length,
                                       maximum_perspectives=validation_perspectives)
    log({"event": "validation", **validation})
    metadata = CorpusMetadata(
        schema_version=CORPUS_SCHEMA_VERSION, created_at=datetime.now(timezone.utc).isoformat(), seed=config.seed,
        decisions=progress["rows"], samples=progress["rows"], decision_interval=int(header["decision_interval"]),
        max_ticks=int(header["max_ticks"]), planner_depth=0, planner_simulations=0, planner_action_samples=0,
        max_entities=int(header["max_entities"]), token_names=token_names, reward_profile=OBJECTIVE_V1,
        label_source=LABEL_SOURCE, label_strategy="recorded-human", public_contract_version=4,
        public_history_slots=4, public_seen_card_slots=8,
        provenance=json.dumps({"role": "training", "provenance": PROVENANCE}, sort_keys=True),
    )
    payload = _checkpoint_payload(
        model=model, metadata=metadata, corpus_path=parts[0].parent,
        metrics={f"validation_{name}": value for name, value in validation.items()}, seed=config.seed,
        split_seed=config.seed, trained=True, initial_checkpoint=initial_checkpoint, imitation_objective="exact",
        trim_entity_padding=True, canonical_lane_globals=True,
    )
    payload.update(checkpoint_metadata or {})
    payload["provenance"] = PROVENANCE
    payload["human_replay_fit"] = plan | {
        "rows": progress["rows"], "steps": progress["steps"], "weighted_rows": progress["weighted_rows"],
        "elapsed_seconds": progress["elapsed_seconds"], "history": progress["history"],
        "recurrence": "carried-state truncated backpropagation over ordered episode chunks",
        "critic": "untrained (no value target on this fit path)",
        "validation": validation,
    }
    output_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    _atomic_torch_save(payload, output_checkpoint)
    return {"checkpoint": str(output_checkpoint), "checkpoint_sha256": file_sha256(output_checkpoint),
            "rows": progress["rows"], "steps": progress["steps"], "validation": validation,
            "history": progress["history"]}
