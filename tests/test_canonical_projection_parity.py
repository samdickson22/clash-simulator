from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
import torch
from torch import Tensor, nn

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.common import BOARD_HEIGHT, BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.live_inference_contract import PublicVisionFrame, VisionEntity
from clasher.rl.model import PolicyConfig
from clasher.rl.public_action_mask import PublicActionMaskBuilder
from clasher.rl.structured_live_adapter import StructuredLiveInferenceAdapter
from clasher.rl.structured_obs import (
    ACTOR_GLOBAL_SIZE,
    ENTITY_FEATURE_SIZE,
    StructuredObservationBuilder,
)
from clasher.rl.train_recurrent import _canonical_lane_globals_for_run
from scripts.audit_tv_royale_youtube_portrait import (
    ACTOR_PROJECTION_SCHEMA,
    NEUTRAL_SNAPSHOT_SCHEMA,
    project_neutral_snapshot,
)

CARD_NAMES = ("Knight", "Tower", "KingTower", "Arrows", "Fireball")
CORNER_CENTERS = ((0.5, 0.5), (17.5, 0.5), (0.5, 31.5), (17.5, 31.5))


class _DummyActorEncoder(nn.Module):
    def __init__(self, card_stat_features: np.ndarray) -> None:
        super().__init__()
        self.register_buffer(
            "card_stat_features",
            torch.as_tensor(card_stat_features, dtype=torch.float32),
        )


class _DummyPolicy(nn.Module):
    def __init__(self, builder: StructuredObservationBuilder) -> None:
        super().__init__()
        self.anchor = nn.Parameter(torch.zeros(()))
        self.actor_encoder = _DummyActorEncoder(builder.card_stat_features)
        self.config = SimpleNamespace(
            actor_observation_domain="causal-frame-v1",
            public_observation_confidence=True,
            entity_feature_size=ENTITY_FEATURE_SIZE,
            actor_global_size=ACTOR_GLOBAL_SIZE,
            public_history_slots=0,
            public_seen_card_slots=0,
            num_tokens=len(builder.token_names),
            max_entities=64,
            canonical_perspective=True,
            canonical_lane_globals=True,
            structured_deterministic_resource_enabled=False,
        )

    def initial_state(
        self, batch_size: int, *, device: torch.device | str | None = None
    ) -> tuple[Tensor, Tensor]:
        target = torch.device("cpu" if device is None else device)
        state = torch.zeros((batch_size, 1), dtype=torch.float32, device=target)
        return state, state.clone()


@dataclass(frozen=True)
class _ProjectionFixture:
    builder: StructuredObservationBuilder
    action_space: DiscreteTileActionSpace
    adapters: tuple[StructuredLiveInferenceAdapter, StructuredLiveInferenceAdapter]


@pytest.fixture(scope="module")
def projection() -> _ProjectionFixture:
    builder = StructuredObservationBuilder(
        card_vocab=CARD_NAMES,
        max_entities=64,
        canonical_perspective=True,
        canonical_lane_globals=True,
    )
    model = _DummyPolicy(builder)
    mask_builder = PublicActionMaskBuilder(builder)
    adapters = tuple(
        StructuredLiveInferenceAdapter(
            model=model,
            token_names=list(builder.token_names),
            public_action_mask_builder=mask_builder,
            actor_id=actor_id,
            deterministic=True,
            device="cpu",
        )
        for actor_id in (0, 1)
    )
    return _ProjectionFixture(
        builder=builder,
        action_space=DiscreteTileActionSpace(canonical_perspective=True),
        adapters=(adapters[0], adapters[1]),
    )


def _expected_position(x: float, y: float, actor_id: int) -> tuple[float, float]:
    if actor_id == 1:
        return BOARD_WIDTH - x, BOARD_HEIGHT - y
    return x, y


def _expected_vector(x: float, y: float, actor_id: int) -> tuple[float, float]:
    if actor_id == 1:
        return -x, -y
    return x, y


def _complete_private_hud(actor_id: int) -> dict[str, object]:
    return {
        "hand": ["Knight", "Arrows", "Fireball", "Knight"],
        "hand_confidence": [1.0, 1.0, 1.0, 1.0],
        "next_card": "Knight",
        "next_card_confidence": 1.0,
        "elixir": 3.0 + actor_id,
        "elixir_confidence": 1.0,
    }


def _neutral_snapshot(entities: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema": NEUTRAL_SNAPSHOT_SCHEMA,
        "match_id": "canonical-gate-a17",
        "snapshot_id": "asymmetric-state",
        "split_group_id": "canonical-gate-a17",
        "timestamp_ms": 12_345,
        "public": {
            "coordinate_frame": "absolute_world",
            "clock_seconds": 123.0,
            "entities": entities,
        },
        "players_private": {
            "0": _complete_private_hud(0),
            "1": _complete_private_hud(1),
        },
        "offline_evidence": {"source": "deterministic_test_fixture"},
    }


def _vision_frame(
    *, actor_id: int, entities: tuple[VisionEntity, ...]
) -> PublicVisionFrame:
    hud = _complete_private_hud(actor_id)
    return PublicVisionFrame(
        episode_id="canonical-gate-a17",
        frame_id=f"actor-{actor_id}",
        timestamp_ms=12_345,
        visible_clock_seconds=123.0,
        clock_confidence=1.0,
        own_elixir=float(hud["elixir"]),
        own_elixir_confidence=1.0,
        own_hand=tuple(str(card) for card in hud["hand"]),
        own_hand_confidence=(1.0, 1.0, 1.0, 1.0),
        own_next_card=str(hud["next_card"]),
        own_next_card_confidence=1.0,
        entities=entities,
        play_events=(),
    )


def _simulator_entity(
    *,
    card: str,
    kind: int,
    player_id: int,
    position: tuple[float, float],
    facing: tuple[int, int],
) -> Any:
    return SimpleNamespace(
        card_stats=SimpleNamespace(name=card, collision_radius=0.5),
        position=Position(*position),
        player_id=player_id,
        entity_kind=kind,
        hitpoints=73.0,
        max_hitpoints=100.0,
        mechanics=(),
        battle_state=None,
        native_facing_units=lambda: facing,
    )


def test_neutral_projection_stays_absolute_until_actor_adapter() -> None:
    entities = [
        {
            "track_id": "corner",
            "card": "Knight",
            "kind": "troop",
            "player_id": 1,
            "x_tiles": 0.5,
            "y_tiles": 31.5,
        }
    ]
    snapshot = _neutral_snapshot(entities)

    for actor_id in (0, 1):
        actor = project_neutral_snapshot(snapshot, actor_id=actor_id)
        assert actor["schema"] == ACTOR_PROJECTION_SCHEMA
        assert actor["actor_id"] == actor_id
        assert actor["public"]["coordinate_frame"] == "absolute_world"
        assert actor["public"]["entities"] == entities
        assert "players_private" not in actor
        assert "offline_evidence" not in actor


@pytest.mark.parametrize("domain", ("causal-frame-v1", "causal-vision-v1"))
def test_fresh_causal_run_enables_canonical_lane_globals(domain: str) -> None:
    assert _canonical_lane_globals_for_run(
        actor_observation_domain=domain,
        resume_config=None,
    )


def test_fresh_exact_simulator_run_retains_legacy_lane_frame() -> None:
    assert not _canonical_lane_globals_for_run(
        actor_observation_domain="simulator-exact",
        resume_config=None,
    )


@pytest.mark.parametrize("resume_value", (False, True))
def test_resumed_run_preserves_checkpoint_lane_contract(resume_value: bool) -> None:
    resume = PolicyConfig(
        num_tokens=8,
        max_entities=16,
        canonical_lane_globals=resume_value,
    )
    assert (
        _canonical_lane_globals_for_run(
            actor_observation_domain="causal-frame-v1",
            resume_config=resume,
        )
        is resume_value
    )


def test_all_tiles_and_slots_round_trip_in_both_actor_views(
    projection: _ProjectionFixture,
) -> None:
    checked = 0
    for actor_id in (0, 1):
        adapter = projection.adapters[actor_id]
        for world_y in range(BOARD_HEIGHT):
            for world_x in range(BOARD_WIDTH):
                center = (world_x + 0.5, world_y + 0.5)
                expected_center = _expected_position(*center, actor_id)
                assert (
                    projection.builder._canonical_position(*center, actor_id)
                    == expected_center
                )
                assert adapter._canonical_position(*center) == expected_center

                for slot in range(NUM_HAND_SLOTS):
                    action = projection.action_space.encode_action(
                        slot=slot,
                        world_x=world_x,
                        world_y=world_y,
                        player_id=actor_id,
                    )
                    decoded = projection.action_space.decode_action(
                        action, player_id=actor_id
                    )
                    assert decoded.slot == slot
                    assert decoded.position is not None
                    assert decoded.position.x == world_x + 0.5
                    assert decoded.position.y == world_y + 0.5
                    expected_tile = (
                        world_y * BOARD_WIDTH + world_x
                        if actor_id == 0
                        else (BOARD_HEIGHT - 1 - world_y) * BOARD_WIDTH
                        + (BOARD_WIDTH - 1 - world_x)
                    )
                    assert action == slot * NUM_TILES + expected_tile
                    checked += 1

    assert checked == 2 * NUM_HAND_SLOTS * NUM_TILES


@pytest.mark.parametrize(
    ("card", "kind_name", "kind_index"),
    (
        ("Knight", "troop", 0),
        ("Tower", "building", 1),
        ("Arrows", "projectile", 2),
        ("Fireball", "area_effect", 3),
    ),
)
@pytest.mark.parametrize("player_id", (0, 1))
@pytest.mark.parametrize("position", CORNER_CENTERS)
def test_entities_project_consistently_at_every_corner_for_both_teams(
    projection: _ProjectionFixture,
    card: str,
    kind_name: str,
    kind_index: int,
    player_id: int,
    position: tuple[float, float],
) -> None:
    vision = VisionEntity(
        track_id=f"{kind_name}-{player_id}-{position}",
        card=card,
        kind=kind_name,
        player_id=player_id,
        x_tiles=position[0],
        y_tiles=position[1],
        confidence=1.0,
        hp_fraction=0.73,
        hp_confidence=1.0,
    )
    simulator = _simulator_entity(
        card=card,
        kind=kind_index,
        player_id=player_id,
        position=position,
        facing=(700, -300),
    )

    for actor_id in (0, 1):
        _, simulator_row = projection.builder._entity_row(simulator, actor_id)
        live_ids, live_rows, live_mask, _, _, _, _, diagnostics = projection.adapters[
            actor_id
        ]._entity_rows(_vision_frame(actor_id=actor_id, entities=(vision,)))
        assert np.count_nonzero(live_mask) == 1
        assert live_ids[0] == projection.builder.token_id(card)
        assert live_rows[0, 0:10] == pytest.approx(simulator_row[0:10])
        assert diagnostics["motion_channels"] == "zero_current_frame_only"
        assert live_rows[0, 27:29].tolist() == [0.0, 0.0]


@pytest.mark.parametrize(
    "world_vector",
    ((1_000, 0), (0, 1_000), (700, -300), (-400, 900), (-800, -600)),
)
def test_facing_vectors_use_the_same_half_turn_as_positions(
    projection: _ProjectionFixture, world_vector: tuple[int, int]
) -> None:
    entity = _simulator_entity(
        card="Knight",
        kind=0,
        player_id=0,
        position=(4.25, 9.75),
        facing=world_vector,
    )
    magnitude = max(1.0, float(np.hypot(*world_vector)))

    for actor_id in (0, 1):
        expected = _expected_vector(*world_vector, actor_id)
        assert projection.builder._canonical_vector(*world_vector, actor_id) == expected
        _, row = projection.builder._entity_row(entity, actor_id)
        assert row[27] == pytest.approx(expected[0] / magnitude)
        assert row[28] == pytest.approx(expected[1] / magnitude)


def test_asymmetric_six_tower_globals_match_live_actor_projection(
    projection: _ProjectionFixture,
) -> None:
    battle = BattleState()
    fractions = {
        (0, "left"): 0.91,
        (0, "right"): 0.72,
        (0, "king"): 0.83,
        (1, "left"): 0.64,
        (1, "right"): 0.45,
        (1, "king"): 0.56,
    }
    for player_id in (0, 1):
        player = battle.players[player_id]
        for slot in ("left", "right", "king"):
            starting = battle._starting_tower_hps[player_id][slot]
            setattr(player, f"{slot}_tower_hp", starting * fractions[player_id, slot])

    towers: list[VisionEntity] = []
    tower_rows: list[dict[str, object]] = []
    slots_seen = {
        (0, "left"): 0,
        (0, "right"): 0,
        (0, "king"): 0,
        (1, "left"): 0,
        (1, "right"): 0,
        (1, "king"): 0,
    }
    for entity_id, entity in battle.entities.items():
        card = str(entity.card_stats.name)
        if card == "KingTower":
            slot = "king"
        else:
            slot = "left" if entity.position.x < BOARD_WIDTH / 2 else "right"
        key = (int(entity.player_id), slot)
        slots_seen[key] += 1
        row = VisionEntity(
            track_id=f"tower-{entity_id}",
            card=card,
            kind="building",
            player_id=int(entity.player_id),
            x_tiles=float(entity.position.x),
            y_tiles=float(entity.position.y),
            confidence=1.0,
            hp_fraction=fractions[key],
            hp_confidence=1.0,
        )
        towers.append(row)
        tower_rows.append(
            {
                "track_id": row.track_id,
                "card": row.card,
                "kind": row.kind,
                "player_id": row.player_id,
                "x_tiles": row.x_tiles,
                "y_tiles": row.y_tiles,
                "hp_fraction": row.hp_fraction,
            }
        )
    assert set(slots_seen.values()) == {1}

    neutral = _neutral_snapshot(tower_rows)
    for actor_id in (0, 1):
        actor = project_neutral_snapshot(neutral, actor_id=actor_id)
        assert actor["public"]["entities"] == tower_rows
        simulator_globals = projection.builder._actor_globals(battle, actor_id)
        live_globals, live_confidence, diagnostics = projection.adapters[
            actor_id
        ]._globals(_vision_frame(actor_id=actor_id, entities=tuple(towers)))
        assert live_globals[8:14] == pytest.approx(simulator_globals[8:14])
        assert live_confidence[8:14].tolist() == [1.0] * 6
        assert diagnostics["observed_tower_global_indices"] == list(range(8, 14))

    assert projection.builder._actor_globals(battle, 0)[8:14] == pytest.approx(
        [0.91, 0.72, 0.83, 0.64, 0.45, 0.56]
    )
    assert projection.builder._actor_globals(battle, 1)[8:14] == pytest.approx(
        [0.45, 0.64, 0.56, 0.72, 0.91, 0.83]
    )
