from __future__ import annotations

import copy
from collections import deque
from typing import ClassVar

import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.obs_cv import CvObservationBuilder
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.torch_sim.observations import TensorObservationProjector
from clasher.torch_sim.resident_engine import TensorResidentEngine
from clasher.torch_sim.resident_outputs import ResidentOutputProjector
from clasher.torch_sim.state import TensorBattleState


class _TypedBuilder:
    max_entities = 16
    canonical_perspective = True
    canonical_lane_globals = True
    _uses_typed_tokens = True

    _TOKENS: ClassVar[dict[tuple[str, str], int]] = {
        ("card_action", "Knight"): 10,
        ("card_action", "Knight_EV1"): 11,
        ("card_action", "Knight_hero"): 12,
        ("troop_body", "Knight"): 20,
        ("troop_body", "Knight_EV1"): 21,
        ("troop_body", "Knight_hero"): 22,
        ("tower", "Tower"): 30,
        ("tower", "KingTower"): 31,
    }

    def token_id(self, name: str | None, *, namespace: str | None = None) -> int:
        if not name:
            return 1
        return self._TOKENS.get((namespace or "card_action", str(name)), 1)


def _deployed_knight() -> tuple[BattleState, object]:
    battle = BattleState()
    battle.players[0].elixir = 10.0
    battle.players[0].hand = ["Knight", None, None, None]
    battle.players[0].deck = ["Knight"]
    battle.players[0].cycle_queue = deque()
    assert battle.deploy_card(0, "Knight", Position(9.0, 10.0))
    knight = max(battle.entities.values(), key=lambda entity: entity.id)
    return battle, knight


def test_canonical_lane_globals_swap_actor_one_tower_lanes_only_when_enabled() -> None:
    battle = BattleState()
    battle.players[0].left_tower_hp *= 0.25
    battle.players[0].right_tower_hp *= 0.75
    battle.players[1].left_tower_hp *= 0.40
    battle.players[1].right_tower_hp *= 0.80
    state = TensorBattleState.from_battles([battle], max_entities=16)

    legacy_builder = StructuredObservationBuilder(card_vocab=[], max_entities=16)
    legacy = TensorObservationProjector(
        state.clone(),
        [battle],
        structured_builder=legacy_builder,
        cv_builder=CvObservationBuilder(card_vocab=[]),
    ).project_structured()

    canonical_builder = StructuredObservationBuilder(card_vocab=[], max_entities=16)
    canonical_builder.canonical_lane_globals = True
    canonical = TensorObservationProjector(
        state.clone(),
        [battle],
        structured_builder=canonical_builder,
        cv_builder=CvObservationBuilder(card_vocab=[]),
    ).project_structured()

    assert torch.equal(legacy.global_features[0, 0], canonical.global_features[0, 0])
    assert torch.equal(
        legacy.global_features[0, 1, [9, 8, 12, 11]],
        canonical.global_features[0, 1, [8, 9, 11, 12]],
    )
    assert torch.equal(
        legacy.critic_global_features[0, 1, [9, 8, 12, 11]],
        canonical.critic_global_features[0, 1, [8, 9, 11, 12]],
    )


def test_typed_projection_preserves_variant_and_body_namespaces_fail_closed() -> None:
    battle, knight = _deployed_knight()
    knight.card_stats = copy.copy(knight.card_stats)
    knight.card_stats.name = "Knight_EV1"
    battle.players[0].hand = [
        "Knight_EV1",
        "Knight_hero",
        "Knight_EV999",
        "Knight_unknown_hero",
    ]
    battle.players[0].cycle_queue = deque(["Knight"])
    state = TensorBattleState.from_battles([battle], max_entities=16)
    projected = TensorObservationProjector(
        state,
        [battle],
        structured_builder=_TypedBuilder(),  # type: ignore[arg-type]
        cv_builder=CvObservationBuilder(card_vocab=["Knight"]),
    ).project_structured()

    actor_ids = projected.entity_ids[0, 0][projected.entity_mask[0, 0]]
    assert 21 in actor_ids.tolist()
    assert 11 == projected.hand_ids[0, 0, 0].item()
    assert 12 == projected.hand_ids[0, 0, 1].item()
    assert 1 == projected.hand_ids[0, 0, 2].item()
    assert 1 == projected.hand_ids[0, 0, 3].item()
    assert 10 == projected.hand_ids[0, 0, 4].item()
    assert 30 in actor_ids.tolist()
    assert 31 in actor_ids.tolist()


def test_resident_refresh_keeps_typed_entity_body_token() -> None:
    battle, _ = _deployed_knight()
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=16, max_objects=16
    )
    outputs = ResidentOutputProjector.from_engine(
        engine,
        [battle],
        structured_builder=_TypedBuilder(),  # type: ignore[arg-type]
        cv_builder=CvObservationBuilder(card_vocab=["Knight"]),
        max_entities=16,
    )

    projected = outputs.project_public_structured()
    actor_ids = projected.entity_ids[0, 0][projected.entity_mask[0, 0]]
    assert 20 in actor_ids.tolist()
    assert 10 not in actor_ids.tolist()
