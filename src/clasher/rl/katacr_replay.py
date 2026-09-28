from __future__ import annotations

import ast
import json
import lzma
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from clasher.arena import TileGrid
from clasher.paths import resolve_path

from .common import BOARD_HEIGHT, BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES
from .imitation import CorpusMetadata
from .oracle_corpus import atomic_save_npz, atomic_write_json, file_sha256
from .reward_model import DEFENSE_V2
from .structured_obs import (
    ACTOR_GLOBAL_SIZE,
    ENTITY_FEATURE_SIZE,
    StructuredObservationBuilder,
)

KATACR_REPLAY_REPOSITORY = "https://github.com/wty-yy/Clash-Royale-Replay-Dataset"
KATACR_SOURCE_REPOSITORY = "https://github.com/wty-yy/KataCR"
KATACR_SOURCE_REVISION = "36ceb9fcfbd117c2ce3d97eacee435c1898eb7b8"
KATACR_REPLAY_REVISION = "ce86e10bedcf97762c3d207633f035cd12be8936"

_SKIPPED_VISUAL_CLASSES = {
    "bar",
    "bar-level",
    "clock",
    "dagger-duchess-tower-bar",
    "elixir",
    "emote",
    "king-tower-bar",
    "selected",
    "skeleton-king-bar",
    "text",
    "tower-bar",
}
_UNIT_ALIASES = {
    "cannoneer-tower": "Tower",
    "dagger-duchess-tower": "Tower",
    "golem-big": "Golem",
    "golem-mid": "Golemite",
    "golem-small": "Golemite",
    "hog": "RoyalHog",
    "king-tower": "KingTower",
    "queen-tower": "Tower",
    "skeleton-evolution": "Skeleton",
    "the-log": "LogProjectileRolling",
}
_CARD_ALIASES = {
    "ice-spirit-evolution": "IceSpirit",
    "skeletons-evolution": "Skeletons",
    "the-log": "Log",
}


@dataclass(frozen=True)
class KataCRImportStats:
    source_files: int
    episodes: int
    samples: int
    placement_samples: int
    forced_noop_samples: int
    unknown_entity_rows: int
    skipped_visual_rows: int
    evolution_hand_rows: int
    recovered_action_hand_rows: int
    dropped_unrecoverable_placement_rows: int
    truncated: bool


def _normalized_name(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def load_katacr_unit_names(label_list_path: Path) -> tuple[str, ...]:
    """Read KataCR's detector label order without importing its runtime."""

    module = ast.parse(label_list_path.read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "unit_list"
            for target in node.targets
        ):
            values = ast.literal_eval(node.value)
            if not isinstance(values, list) or not all(
                isinstance(value, str) for value in values
            ):
                break
            return tuple(values)
    raise ValueError(f"could not read unit_list from {label_list_path}")


def load_katacr_card_names(metadata_path: Path) -> dict[int, str | None]:
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    raw = payload.get("idx2card")
    if not isinstance(raw, dict):
        raise TypeError("KataCR classifier metadata has no idx2card mapping")
    result: dict[int, str | None] = {}
    for key, value in raw.items():
        if not isinstance(value, str):
            raise TypeError("KataCR classifier card names must be strings")
        result[int(key)] = None if value == "empty" else value
    return result


class KataCRReplayConverter:
    """Convert KataCR's expert Hog 2.6 traces into Clasher actor corpora.

    KataCR observes the lower player. Clasher's canonical actor orientation is
    obtained with a 180-degree rotation. Health-bar crops are deliberately not
    decoded: detected live entities receive a neutral full-health feature, while
    exact public positions, ownership, hand, elixir, timing, and expert actions
    are retained. No-op video frames are forced-mask context rows so sequence
    imitation advances recurrent state without optimizing a huge no-op majority.
    """

    def __init__(
        self,
        *,
        decks_path: Path,
        unit_names: tuple[str, ...],
        card_names: dict[int, str | None],
        max_entities: int = 128,
    ) -> None:
        self.builder = StructuredObservationBuilder(
            decks_path=decks_path,
            max_entities=max_entities,
        )
        self.unit_names = unit_names
        self.card_names = card_names
        self.max_entities = max_entities
        self.action_count = NUM_HAND_SLOTS * NUM_TILES + 2
        self.noop_action = NUM_HAND_SLOTS * NUM_TILES
        self.ability_action = self.noop_action + 1
        self._token_by_normalized = {
            _normalized_name(name): name
            for name in self.builder.token_names
            if not name.startswith("<")
        }
        self._blocked_tiles = set(TileGrid.BLOCKED_TILES)
        self.unknown_entity_rows = 0
        self.skipped_visual_rows = 0
        self.evolution_hand_rows = 0
        self.recovered_action_hand_rows = 0
        self.dropped_unrecoverable_placement_rows = 0

    def _card_name(self, external_index: Any) -> str | None:
        try:
            raw = self.card_names[int(external_index)]
        except (KeyError, TypeError, ValueError):
            return None
        if raw is None:
            return None
        if raw.endswith("-evolution"):
            self.evolution_hand_rows += 1
        aliased = _CARD_ALIASES.get(raw, raw)
        token_name = self._token_by_normalized.get(_normalized_name(aliased))
        if token_name is None:
            raise ValueError(f"KataCR card {raw!r} is not in the enabled deck vocabulary")
        return token_name

    def _unit_token(self, raw_name: str) -> tuple[int, str] | None:
        if raw_name in _SKIPPED_VISUAL_CLASSES:
            self.skipped_visual_rows += 1
            return None
        aliased = _UNIT_ALIASES.get(raw_name, raw_name)
        if raw_name.endswith("-evolution") and raw_name not in _UNIT_ALIASES:
            aliased = raw_name.removesuffix("-evolution")
        token_name = self._token_by_normalized.get(_normalized_name(aliased))
        if token_name is None:
            self.unknown_entity_rows += 1
            return self.builder.token_id(None), self.builder.UNKNOWN_TOKEN
        return self.builder.token_id(token_name), token_name

    @staticmethod
    def _entity_kind(token_name: str, builder: StructuredObservationBuilder) -> int:
        if token_name in {"Tower", "KingTower"}:
            return 1
        stats = builder.loader.get_card(token_name)
        kind = str(getattr(stats, "card_type", "") or "").lower()
        if kind == "building":
            return 1
        if kind == "spell":
            return 3
        return 0

    def _entities(self, state: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        rows: list[tuple[tuple[Any, ...], int, np.ndarray]] = []
        for item in state.get("unit_infos", ()):
            if not isinstance(item, dict):
                continue
            try:
                raw_name = self.unit_names[int(item["cls"])]
                xy = np.asarray(item["xy"], dtype=np.float32)
                x = float(xy[0])
                y = float(xy[1])
                belonging = int(item["bel"])
            except (IndexError, KeyError, TypeError, ValueError):
                continue
            if not math.isfinite(x) or not math.isfinite(y):
                continue
            mapped = self._unit_token(raw_name)
            if mapped is None:
                continue
            token_id, token_name = mapped
            row = np.zeros((ENTITY_FEATURE_SIZE,), dtype=np.float32)
            canonical_x = float(np.clip(BOARD_WIDTH - x, 0.0, BOARD_WIDTH))
            canonical_y = float(np.clip(BOARD_HEIGHT - y, 0.0, BOARD_HEIGHT))
            row[0] = canonical_x / BOARD_WIDTH
            row[1] = canonical_y / BOARD_HEIGHT
            own = belonging == 0
            row[2] = float(own)
            row[3] = float(not own)
            kind = self._entity_kind(token_name, self.builder)
            row[4 + kind] = 1.0
            row[9] = 1.0
            static = self.builder.card_stat_features[token_id]
            stats = self.builder.loader.get_card(token_name)
            speed = float(getattr(stats, "speed", 0.0) or 0.0)
            row[23] = float(np.clip(math.log1p(abs(speed)) / math.log1p(1000.0), 0.0, 1.0))
            row[24] = static[7]
            row[25] = static[8]
            row[26] = static[12]
            if kind == 0:
                row[28] = 1.0 if own else -1.0
            row[30] = static[6]
            row[31] = float(token_name in {"Tower", "KingTower"})
            sort_key = (
                kind,
                int(not own),
                token_id,
                round(float(row[1]), 5),
                round(float(row[0]), 5),
            )
            rows.append((sort_key, token_id, row))
        rows.sort(key=lambda value: value[0])
        if len(rows) > self.max_entities:
            raise ValueError(
                f"KataCR frame has {len(rows)} entities, exceeding max_entities={self.max_entities}"
            )
        ids = np.zeros((self.max_entities,), dtype=np.int64)
        # Visual detections are substantially noisier than float16 precision.
        # Keeping the external corpus compact cuts a full import by several GB;
        # the fitter promotes these rows to float32 on device.
        features = np.zeros(
            (self.max_entities, ENTITY_FEATURE_SIZE), dtype=np.float16
        )
        mask = np.zeros((self.max_entities,), dtype=np.bool_)
        for index, (_, token_id, row) in enumerate(rows):
            ids[index] = token_id
            features[index] = row
            mask[index] = True
        return ids, features, mask

    def _hand(self, state: dict[str, Any]) -> tuple[np.ndarray, list[str | None]]:
        raw_cards = list(state.get("cards", ()))
        if len(raw_cards) != NUM_HAND_SLOTS + 1:
            raise ValueError("KataCR frame must contain next card plus four hand slots")
        ordered = raw_cards[1:] + raw_cards[:1]
        names = [self._card_name(value) for value in ordered]
        ids = np.asarray(
            [0 if name is None else self.builder.token_id(name) for name in names],
            dtype=np.int64,
        )
        return ids, names

    @staticmethod
    def _globals(state: dict[str, Any]) -> np.ndarray:
        elapsed = max(0.0, float(state.get("time", 0.0) or 0.0))
        try:
            elixir = float(state.get("elixir", 0.0))
        except (TypeError, ValueError):
            elixir = 0.0
        if not math.isfinite(elixir) or elixir < 0.0:
            elixir = 0.0
        progress = float(np.clip(elapsed / 300.0, 0.0, 1.0))
        return np.asarray(
            [
                progress,
                1.0 - progress,
                float(elapsed >= 120.0),
                float(elapsed >= 240.0),
                float(elapsed >= 180.0),
                float(np.clip(elixir / 10.0, 0.0, 1.0)),
                0.0,
                0.0,
                1.0,
                1.0,
                1.0,
                1.0,
                1.0,
                1.0,
                0.0,
                0.0,
                0.0,
                1.0,
            ],
            dtype=np.float32,
        )

    def _placement_tile_mask(self, card_name: str) -> np.ndarray:
        stats = self.builder.loader.get_card(card_name)
        kind = str(getattr(stats, "card_type", "") or "").lower()
        all_board_spell = kind == "spell" and card_name != "Log"
        result = np.zeros((NUM_TILES,), dtype=np.bool_)
        for y in range(BOARD_HEIGHT):
            for x in range(BOARD_WIDTH):
                if (x, y) in self._blocked_tiles:
                    continue
                if all_board_spell or y < 15 or (y < 6 and 6 <= x < 12):
                    result[y * BOARD_WIDTH + x] = True
        return result

    def _action(
        self,
        state: dict[str, Any],
        action: dict[str, Any],
        hand_names: list[str | None],
    ) -> tuple[int, np.ndarray, bool]:
        mask = np.zeros((self.action_count,), dtype=np.bool_)
        mask[self.noop_action] = True
        try:
            external_slot = int(action.get("card_id", 0))
        except (TypeError, ValueError):
            external_slot = 0
        if external_slot == 0:
            return self.noop_action, mask, False

        try:
            elixir = float(state.get("elixir", 0.0))
        except (TypeError, ValueError):
            elixir = 0.0
        for slot, card_name in enumerate(hand_names[:NUM_HAND_SLOTS]):
            if card_name is None:
                continue
            stats = self.builder.loader.get_card(card_name)
            cost = float(getattr(stats, "mana_cost", 0.0) or 0.0)
            if math.isfinite(elixir) and elixir >= 0.0 and cost > elixir:
                continue
            tile_mask = self._placement_tile_mask(card_name)
            start = slot * NUM_TILES
            mask[start : start + NUM_TILES] = tile_mask

        slot = external_slot - 1
        if slot < 0 or slot >= NUM_HAND_SLOTS or hand_names[slot] is None:
            raise ValueError(f"invalid KataCR expert hand slot {external_slot}")
        xy = np.asarray(action.get("xy"), dtype=np.float32)
        if xy.shape != (2,) or not np.all(np.isfinite(xy)):
            raise ValueError("KataCR placement action has no finite xy coordinate")
        canonical_x = int(np.clip(math.floor(BOARD_WIDTH - float(xy[0])), 0, BOARD_WIDTH - 1))
        canonical_y = int(np.clip(math.floor(BOARD_HEIGHT - float(xy[1])), 0, BOARD_HEIGHT - 1))
        expert_action = slot * NUM_TILES + canonical_y * BOARD_WIDTH + canonical_x
        mask[expert_action] = True
        return expert_action, mask, True

    def convert_episode(
        self,
        payload: dict[str, Any],
        *,
        episode_id: int,
    ) -> dict[str, list[np.ndarray | int | float | bool]]:
        states = payload.get("state")
        actions = payload.get("action")
        if not isinstance(states, list) or not isinstance(actions, list):
            raise TypeError("KataCR episode needs state and action lists")
        if len(states) != len(actions) or not states:
            raise ValueError("KataCR episode state/action lengths do not match")
        arrays: dict[str, list[np.ndarray | int | float | bool]] = {
            name: []
            for name in (
                "entity_ids",
                "entity_features",
                "entity_mask",
                "hand_ids",
                "global_features",
                "action_masks",
                "previous_actions",
                "previous_rewards",
                "episode_starts",
                "expert_actions",
                "episode_ids",
            )
        }
        previous_action = self.noop_action
        last_nonempty_hand: list[str | None] = [None] * NUM_HAND_SLOTS
        for index, (state, action) in enumerate(zip(states, actions, strict=True)):
            if not isinstance(state, dict) or not isinstance(action, dict):
                raise TypeError("KataCR state/action rows must be mappings")
            entity_ids, entity_features, entity_mask = self._entities(state)
            hand_ids, hand_names = self._hand(state)
            try:
                action_slot = int(action.get("card_id", 0)) - 1
            except (TypeError, ValueError):
                action_slot = -1
            if (
                0 <= action_slot < NUM_HAND_SLOTS
                and hand_names[action_slot] is None
                and last_nonempty_hand[action_slot] is not None
            ):
                recovered = last_nonempty_hand[action_slot]
                hand_names[action_slot] = recovered
                hand_ids[action_slot] = self.builder.token_id(recovered)
                self.recovered_action_hand_rows += 1
            effective_action = action
            if (
                0 <= action_slot < NUM_HAND_SLOTS
                and hand_names[action_slot] is None
            ):
                # The public video-derived traces occasionally record a play before
                # the classifier has ever observed that occupied hand slot. There is
                # no defensible card label to recover in that case. Preserve the row
                # as recurrent context, but force it to no-op so it contributes no
                # supervised placement loss instead of inventing a target.
                effective_action = {"card_id": 0, "xy": None}
                self.dropped_unrecoverable_placement_rows += 1
            expert_action, action_mask, _ = self._action(
                state, effective_action, hand_names
            )
            arrays["entity_ids"].append(entity_ids)
            arrays["entity_features"].append(entity_features)
            arrays["entity_mask"].append(entity_mask)
            arrays["hand_ids"].append(hand_ids)
            arrays["global_features"].append(self._globals(state))
            arrays["action_masks"].append(action_mask)
            arrays["previous_actions"].append(previous_action)
            arrays["previous_rewards"].append(0.0)
            arrays["episode_starts"].append(index == 0)
            arrays["expert_actions"].append(expert_action)
            arrays["episode_ids"].append(episode_id)
            previous_action = expert_action
            for slot, name in enumerate(hand_names[:NUM_HAND_SLOTS]):
                if name is not None:
                    last_nonempty_hand[slot] = name
        return arrays


def import_katacr_replays(
    *,
    dataset_root: Path,
    katacr_source_root: Path,
    classifier_metadata: Path,
    decks_path: Path,
    output_path: Path,
    manifest_path: Path,
    max_entities: int = 128,
    max_episodes: int | None = None,
    progress: bool = False,
) -> tuple[CorpusMetadata, KataCRImportStats]:
    replay_files = sorted(dataset_root.rglob("*.npy.xz"))
    if max_episodes is not None:
        if max_episodes <= 0:
            raise ValueError("max_episodes must be positive")
        replay_files = replay_files[:max_episodes]
    if not replay_files:
        raise ValueError(f"no .npy.xz replay files found under {dataset_root}")
    unit_names = load_katacr_unit_names(
        katacr_source_root / "katacr/constants/label_list.py"
    )
    card_names = load_katacr_card_names(classifier_metadata)
    converter = KataCRReplayConverter(
        decks_path=decks_path,
        unit_names=unit_names,
        card_names=card_names,
        max_entities=max_entities,
    )
    # Keep one contiguous chunk per episode instead of hundreds of thousands of
    # individual row objects. The final corpus is several GB uncompressed, so
    # this materially lowers importer overhead and peak allocator pressure.
    merged: dict[str, list[np.ndarray]] = {
        name: []
        for name in (
            "entity_ids",
            "entity_features",
            "entity_mask",
            "hand_ids",
            "global_features",
            "action_masks",
            "previous_actions",
            "previous_rewards",
            "episode_starts",
            "expert_actions",
            "episode_ids",
        )
    }
    placements = 0
    samples_seen = 0
    for episode_id, replay_path in enumerate(replay_files):
        with lzma.open(replay_path, "rb") as source:
            payload = np.load(source, allow_pickle=True).item()
        episode = converter.convert_episode(payload, episode_id=episode_id)
        placements += sum(
            int(value) != converter.noop_action
            for value in episode["expert_actions"]
        )
        for name, values in episode.items():
            merged[name].append(np.asarray(values))
        samples_seen += len(episode["expert_actions"])
        if progress and ((episode_id + 1) % 10 == 0 or episode_id + 1 == len(replay_files)):
            print(
                json.dumps(
                    {
                        "imported_episodes": episode_id + 1,
                        "total_episodes": len(replay_files),
                        "samples": samples_seen,
                        "placements": placements,
                    }
                ),
                flush=True,
            )
    arrays = {name: np.concatenate(values, axis=0) for name, values in merged.items()}
    if arrays["global_features"].shape[1] != ACTOR_GLOBAL_SIZE:
        raise AssertionError("KataCR actor global feature width changed")
    samples = int(arrays["expert_actions"].shape[0])
    legal = arrays["action_masks"][np.arange(samples), arrays["expert_actions"]]
    if not np.all(legal):
        raise AssertionError("converted KataCR corpus contains an illegal label")
    metadata = CorpusMetadata(
        schema_version=1,
        created_at=datetime.now(timezone.utc).isoformat(),
        seed=0,
        decisions=samples,
        samples=samples,
        decision_interval=4,
        max_ticks=6000,
        planner_depth=0,
        planner_simulations=0,
        planner_action_samples=0,
        max_entities=max_entities,
        token_names=converter.builder.token_names,
        reward_profile=DEFENSE_V2,
        workers=1,
        behavior_checkpoint=None,
        expert_probability=1.0,
        stable_root_candidates=False,
        behavior_opponent=None,
        label_source="human-replay",
    )
    atomic_save_npz(
        output_path,
        {**arrays, "metadata_json": np.asarray(metadata.to_json())},
    )
    stats = KataCRImportStats(
        source_files=len(replay_files),
        episodes=len(replay_files),
        samples=samples,
        placement_samples=placements,
        forced_noop_samples=samples - placements,
        unknown_entity_rows=converter.unknown_entity_rows,
        skipped_visual_rows=converter.skipped_visual_rows,
        evolution_hand_rows=converter.evolution_hand_rows,
        recovered_action_hand_rows=converter.recovered_action_hand_rows,
        dropped_unrecoverable_placement_rows=(
            converter.dropped_unrecoverable_placement_rows
        ),
        truncated=max_episodes is not None,
    )
    source_group_counts: dict[str, int] = {}
    for replay_path in replay_files:
        relative = replay_path.relative_to(dataset_root)
        group = relative.parts[0] if len(relative.parts) > 1 else "."
        source_group_counts[group] = source_group_counts.get(group, 0) + 1
    atomic_write_json(
        manifest_path,
        {
            "schema_version": 1,
            "created_at": metadata.created_at,
            "dataset_repository": KATACR_REPLAY_REPOSITORY,
            "dataset_revision": KATACR_REPLAY_REVISION,
            "katacr_repository": KATACR_SOURCE_REPOSITORY,
            "katacr_revision": KATACR_SOURCE_REVISION,
            "katacr_source_license": "MIT",
            "dataset_repository_license": None,
            "dataset_root": str(dataset_root),
            "source_group_counts": source_group_counts,
            "katacr_source_root": str(katacr_source_root),
            "classifier_metadata": str(classifier_metadata),
            "classifier_metadata_sha256": file_sha256(classifier_metadata),
            "decks_path": str(decks_path),
            "decks_sha256": file_sha256(decks_path),
            "output": str(output_path),
            "stats": asdict(stats),
            "limitations": [
                "KataCR health-bar image crops are not decoded; live entities use neutral full-health features.",
                "No-op video frames are recurrent context with a forced no-op mask, not supervised negatives.",
                "Evolution hand and unit labels are mapped to their enabled base-card equivalents.",
                "Placement rows whose played card was never observed in that hand slot are retained only as forced-no-op recurrent context, never guessed or supervised.",
                "The public corpus contains expert Hog 2.6 play only; PPO must restore broad deck coverage.",
                "The replay-data repository has no explicit license file at the pinned revision; keep the source data local and do not redistribute it without permission.",
            ],
        },
    )
    return metadata, stats


def default_external_paths() -> tuple[Path, Path, Path]:
    dataset_root = resolve_path("datasets/external/Clash-Royale-Replay-Dataset")
    source_root = resolve_path("datasets/external/KataCR")
    classifier = resolve_path(
        "datasets/external/KataCR-CardClassification/010/config/metadata"
    )
    return dataset_root, source_root, classifier
