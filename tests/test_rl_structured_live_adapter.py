from __future__ import annotations

import base64
import inspect
import json
import subprocess
import sys
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import torch

from clasher.rl.eval import LoadedPolicy, load_policy_checkpoint
from clasher.rl.live_inference_contract import (
    InferenceContractError,
    PublicVisionFrame,
    parse_public_vision_frame,
)
from clasher.rl.model import PolicyInputs
from clasher.rl.public_action_mask import PublicActionMaskBuilder
from clasher.rl.structured_live_adapter import (
    LiveAdapterError,
    LiveCadenceError,
    LivePolicyInputs,
    StructuredLiveInferenceAdapter,
)

CHECKPOINT = Path(
    "checkpoints/fresh_structured_causal_v1_seed1062701/"
    "resource_belief_gated_seed1063602/resource_u10_gate0.pt"
)


@pytest.fixture(scope="module")
def loaded() -> LoadedPolicy:
    if not CHECKPOINT.is_file():
        pytest.skip("accepted structured checkpoint is unavailable")
    return load_policy_checkpoint(
        CHECKPOINT,
        device=torch.device("cpu"),
        decks_path="decks.json",
    )


def _payload(
    *,
    actor_id: int,
    frame_id: str = "f0",
    timestamp_ms: int = 0,
    episode_id: str = "game-1",
) -> dict[str, Any]:
    own_hand = (
        ["Knight", "Archers", "Fireball", "HogRider"]
        if actor_id == 0
        else ["Giant", "Musketeer", "Arrows", "MiniPEKKA"]
    )
    own_next = "Skeletons" if actor_id == 0 else "Bomber"
    return {
        "schema_version": 1,
        "episode_id": episode_id,
        "frame_id": frame_id,
        "timestamp_ms": timestamp_ms,
        "public": {
            "visible_clock_seconds": timestamp_ms / 1000.0,
            "clock_confidence": 0.91,
            "own_elixir": 8.0,
            "own_elixir_confidence": 1.0,
            "own_hand": own_hand,
            "own_hand_confidence": [1.0, 1.0, 1.0, 1.0],
            "own_next_card": own_next,
            "own_next_card_confidence": 1.0,
            "entities": [
                {
                    "track_id": "p0-knight",
                    "card": "Knight",
                    "kind": "troop",
                    "player_id": 0,
                    "x_tiles": 4.0,
                    "y_tiles": 6.0,
                    "confidence": 0.92,
                    "hp_fraction": 0.75,
                    "hp_confidence": 0.81,
                    "statuses": ["slowed"],
                },
                {
                    "track_id": "p1-giant",
                    "card": "Giant",
                    "kind": "troop",
                    "player_id": 1,
                    "x_tiles": 14.0,
                    "y_tiles": 25.0,
                    "confidence": 0.88,
                    "hp_fraction": 0.64,
                    "hp_confidence": 0.76,
                    "statuses": [],
                },
                {
                    "track_id": "p0-left",
                    "card": "Tower",
                    "kind": "building",
                    "player_id": 0,
                    "x_tiles": 4.0,
                    "y_tiles": 3.0,
                    "confidence": 0.96,
                    "hp_fraction": 0.80,
                    "hp_confidence": 0.93,
                    "statuses": [],
                },
                {
                    "track_id": "p1-king",
                    "card": "KingTower",
                    "kind": "building",
                    "player_id": 1,
                    "x_tiles": 9.0,
                    "y_tiles": 29.0,
                    "confidence": 0.97,
                    "hp_fraction": 0.90,
                    "hp_confidence": 0.95,
                    "statuses": [],
                },
            ],
            "play_events": [],
        },
    }


def _frame(**kwargs: Any) -> PublicVisionFrame:
    return parse_public_vision_frame(_payload(**kwargs))


def _adapter(loaded: LoadedPolicy, actor_id: int) -> StructuredLiveInferenceAdapter:
    return StructuredLiveInferenceAdapter(
        model=loaded.model,
        token_names=list(loaded.builder.token_names),
        public_action_mask_builder=PublicActionMaskBuilder(loaded.builder),
        actor_id=actor_id,
        deterministic=True,
        device="cpu",
    )


def _direct_inputs(inputs: LivePolicyInputs) -> PolicyInputs:
    return PolicyInputs(
        **{field.name: getattr(inputs, field.name) for field in fields(PolicyInputs)}
    )


def _snapshot_tensor(snapshot: bytes, name: str) -> np.ndarray:
    payload = json.loads(snapshot)
    record = payload[name]
    dtype = np.dtype(record["dtype"])
    return np.frombuffer(base64.b64decode(record["data"]), dtype=dtype).reshape(
        record["shape"]
    )


def test_live_module_import_graph_excludes_battle_and_structured_simulator() -> None:
    script = """
import sys
import clasher.rl.structured_live_adapter
assert 'clasher.battle' not in sys.modules
assert 'clasher.rl.structured_obs' not in sys.modules
from clasher.rl import DiscreteTileActionSpace
assert DiscreteTileActionSpace.__name__ == 'DiscreteTileActionSpace'
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_adapter_canonicalizes_both_actor_perspectives(loaded: LoadedPolicy) -> None:
    lower = _adapter(loaded, 0)
    upper = _adapter(loaded, 1)
    lower.reset("game-1")
    upper.reset("game-1")

    lower_prepared = lower.prepare_current_frame(_frame(actor_id=0))
    upper_prepared = upper.prepare_current_frame(_frame(actor_id=1))
    knight = loaded.builder.token_id("Knight")
    lower_ids = lower_prepared.inputs.entity_ids[0, 0].numpy()
    upper_ids = upper_prepared.inputs.entity_ids[0, 0].numpy()
    lower_row = lower_prepared.inputs.entity_features[0, 0][lower_ids == knight][0]
    upper_row = upper_prepared.inputs.entity_features[0, 0][upper_ids == knight][0]

    assert lower_row[0].item() == pytest.approx(4.0 / 18.0)
    assert lower_row[1].item() == pytest.approx(6.0 / 32.0)
    assert lower_row[2:4].tolist() == [1.0, 0.0]
    assert upper_row[0].item() == pytest.approx(14.0 / 18.0)
    assert upper_row[1].item() == pytest.approx(26.0 / 32.0)
    assert upper_row[2:4].tolist() == [0.0, 1.0]
    assert lower_prepared.diagnostics["canonical_perspective"] is True
    assert upper_prepared.diagnostics["canonical_perspective"] is True


def test_nonzero_public_next_reaches_model_but_not_mask_slot_count(
    loaded: LoadedPolicy,
) -> None:
    adapter = _adapter(loaded, 0)
    adapter.reset("game-1")

    prepared = adapter.prepare_current_frame(_frame(actor_id=0))

    assert int(prepared.inputs.hand_ids[0, 0, 4]) == loaded.builder.token_id(
        "Skeletons"
    )
    assert float(prepared.inputs.hand_id_confidence[0, 0, 4]) == 1.0
    assert prepared.diagnostics["next_card_observed"] is True
    assert prepared.action_mask.shape == (2306,)


def test_mask_is_label_independent_and_cannot_be_injected(
    loaded: LoadedPolicy,
) -> None:
    adapter = _adapter(loaded, 0)
    adapter.reset("game-1")
    frame = _frame(actor_id=0)
    first = adapter.prepare_current_frame(frame)
    external_label_a = 7
    external_label_b = 1800
    assert external_label_a != external_label_b
    second = adapter.prepare_current_frame(frame)

    assert np.array_equal(first.action_mask, second.action_mask)
    assert first.diagnostics["mask_source"].startswith("PublicActionMaskBuilder")
    parameters = inspect.signature(adapter.step).parameters
    assert set(parameters) == {"frame"}

    leaked = _payload(actor_id=0)
    leaked["expert_action"] = external_label_a
    with pytest.raises(InferenceContractError, match="privileged"):
        parse_public_vision_frame(leaked)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("opponent_hand", ["HogRider"]),
        ("exact_opponent_elixir", 8.0),
        ("public_card_play_history", ["HogRider"]),
        ("action_mask", [True, False]),
    ],
)
def test_opponent_private_and_simulator_inputs_fail_before_adapter(
    field: str, value: object
) -> None:
    payload = _payload(actor_id=0)
    public = payload["public"]
    assert isinstance(public, dict)
    public[field] = value
    with pytest.raises(InferenceContractError, match="privileged"):
        parse_public_vision_frame(payload)


def test_direct_dataclass_cannot_bypass_public_frame_validation(
    loaded: LoadedPolicy,
) -> None:
    adapter = _adapter(loaded, 0)
    adapter.reset("game-1")
    frame = _frame(actor_id=0)
    invalid_entity = replace(
        frame.entities[0],
        hp_fraction=0.75,
        hp_confidence=0.0,
    )
    invalid = replace(frame, entities=(invalid_entity, *frame.entities[1:]))

    with pytest.raises(InferenceContractError, match="zero confidence"):
        adapter.step(invalid)


def test_duplicate_dropped_and_gap_frames_do_not_fabricate_recurrent_steps(
    loaded: LoadedPolicy,
) -> None:
    adapter = _adapter(loaded, 0)
    adapter.reset("game-1")
    first = adapter.step(_frame(actor_id=0, frame_id="f0", timestamp_ms=0))
    duplicate = adapter.step(_frame(actor_id=0, frame_id="f0", timestamp_ms=0))
    early = adapter.step(_frame(actor_id=0, frame_id="f1", timestamp_ms=200))
    second = adapter.step(_frame(actor_id=0, frame_id="f2", timestamp_ms=400))

    assert first.disposition == second.disposition == "accepted"
    assert first.state_step == 1
    assert duplicate.disposition == "duplicate_frame"
    assert duplicate.state.sha256 == first.state.sha256
    assert early.disposition == "before_cadence"
    assert early.state_step == 1
    assert second.state_step == 2

    with pytest.raises(LiveCadenceError, match="exceeds safe maximum"):
        adapter.step(_frame(actor_id=0, frame_id="late", timestamp_ms=1300))
    with pytest.raises(LiveAdapterError, match="requires reset"):
        adapter.step(_frame(actor_id=0, frame_id="later", timestamp_ms=1400))
    reset = adapter.reset("game-2")
    assert len(reset.sha256) == 64
    resumed = adapter.step(
        _frame(
            actor_id=0,
            episode_id="game-2",
            frame_id="new-f0",
            timestamp_ms=0,
        )
    )
    assert resumed.state_step == 1
    adapter.step(
        _frame(
            actor_id=0,
            episode_id="game-2",
            frame_id="new-f1",
            timestamp_ms=400,
        )
    )
    with pytest.raises(LiveAdapterError, match="moved backwards"):
        adapter.step(
            _frame(
                actor_id=0,
                episode_id="game-2",
                frame_id="out-of-order",
                timestamp_ms=300,
            )
        )


def test_state_snapshot_restore_is_exact_across_next_decision(
    loaded: LoadedPolicy,
) -> None:
    original = _adapter(loaded, 0)
    original.reset("game-1")
    first = original.step(_frame(actor_id=0, frame_id="f0", timestamp_ms=0))
    restored = _adapter(loaded, 0)
    restored.restore_state(first.state)

    next_frame = _frame(actor_id=0, frame_id="f1", timestamp_ms=400)
    continued = original.step(next_frame)
    replayed = restored.step(next_frame)

    assert continued.action == replayed.action
    assert np.array_equal(continued.action_mask, replayed.action_mask)
    assert continued.state.sha256 == replayed.state.sha256


def test_unsupported_current_cues_are_zero_and_reported(loaded: LoadedPolicy) -> None:
    adapter = _adapter(loaded, 0)
    adapter.reset("game-1")
    prepared = adapter.prepare_current_frame(_frame(actor_id=0))

    visible = prepared.inputs.entity_mask[0, 0]
    features = prepared.inputs.entity_features[0, 0][visible]
    confidence = prepared.inputs.entity_feature_confidence[0, 0][visible]
    assert torch.count_nonzero(features[:, 23]) == 0
    assert torch.count_nonzero(confidence[:, 23]) == 0
    assert torch.count_nonzero(features[:, 27:30]) == 0
    assert torch.count_nonzero(confidence[:, 27:30]) == 0
    knight = loaded.builder.token_id("Knight")
    ids = prepared.inputs.entity_ids[0, 0][visible]
    knight_confidence = confidence[ids == knight][0]
    assert float(knight_confidence[9]) == pytest.approx(0.81)
    assert float(prepared.inputs.global_feature_confidence[0, 0, 8]) == pytest.approx(
        0.93
    )
    assert prepared.diagnostics["ignored_visible_status_count"] == 1
    assert prepared.diagnostics["phase_globals"] == "zero_not_fabricated"


def test_adapter_matches_direct_policy_inputs_on_frozen_synthetic_step(
    loaded: LoadedPolicy,
) -> None:
    adapter = _adapter(loaded, 0)
    adapter.reset("game-1")
    frame = _frame(actor_id=0, frame_id="f0", timestamp_ms=0)
    prepared = adapter.prepare_current_frame(frame)
    direct_state = loaded.model.initial_state(1, device="cpu")

    with torch.no_grad():
        direct_action, _, _, direct_next, _ = loaded.model.act(
            _direct_inputs(prepared.inputs),
            direct_state,
            deterministic=True,
        )
    decision = adapter.step(frame)

    assert decision.action == int(direct_action[0, 0])
    assert np.array_equal(decision.action_mask, prepared.action_mask)
    serialized_hidden = _snapshot_tensor(decision.state.payload, "hidden")
    serialized_cell = _snapshot_tensor(decision.state.payload, "cell")
    assert np.array_equal(serialized_hidden, direct_next[0].detach().numpy())
    assert np.array_equal(serialized_cell, direct_next[1].detach().numpy())


@pytest.fixture
def v4_loaded() -> LoadedPolicy:
    from clasher.rl.model import ClasherPolicy, PolicyConfig
    from clasher.rl.structured_obs import StructuredObservationBuilder
    builder = StructuredObservationBuilder(
        card_vocab=['Knight','Archers','Fireball','HogRider','Skeletons','Giant'],
        max_entities=16, card_semantics_version=4,
        public_entity_levels=True, public_hand_levels=True,
    )
    torch.manual_seed(928)
    config = PolicyConfig(
        num_tokens=builder.spec.num_tokens, max_entities=16, public_contract_version=4,
        public_token_names=builder.token_names, public_observation_confidence=True,
        actor_observation_domain='causal-frame-v1', card_semantics_version=4,
        d_model=16, num_heads=4, actor_layers=1, critic_layers=1, memory_size=24,
    )
    return LoadedPolicy(ClasherPolicy(config,builder.card_stat_features).eval(),builder,{})


def test_v4_live_measured_levels_and_confirmed_play_reach_actor(v4_loaded):
    payload = _payload(actor_id=0)
    public = payload['public']
    public['own_card_levels'] = [10,11,None,12,10]
    public['own_card_level_confidence'] = [1,.8,0,.9,.7]
    public['own_last_play'] = {'card_name':'Knight','elixir_cost':3}
    for index,entity in enumerate(public['entities']):
        entity.update(level=10+index%3,level_confidence=.6+index/10)
    frame = parse_public_vision_frame(payload)
    adapter = _adapter(v4_loaded,0)
    adapter.reset('game-1')
    prepared = adapter.prepare_current_frame(frame)
    inputs = prepared.inputs
    assert inputs.hand_levels[0,0].tolist() == [10,11,0,12,10]
    np.testing.assert_allclose(inputs.hand_level_confidence[0,0],[1,.8,0,.9,.7])
    for entity in frame.entities:
        namespace = 'tower' if entity.card in {'Tower','KingTower'} else 'troop_body'
        token = v4_loaded.builder.token_id(entity.card,namespace=namespace)
        row = inputs.entity_ids[0,0] == token
        assert inputs.entity_levels[0,0][row].tolist() == [entity.level]
        assert inputs.entity_level_confidence[0,0][row].item() == pytest.approx(entity.level_confidence)
    assert inputs.own_last_play_ids.item() == v4_loaded.builder.token_id('Knight')
    assert inputs.own_last_play_features[0,0].tolist() == pytest.approx([1,.3])
    assert prepared.action_mask.sum() == 1 and prepared.action_mask[2304]
    assert prepared.diagnostics['match_lifecycle'] == 'unknown_wait_only'
    direct = _direct_inputs(inputs)
    changed_levels = direct.hand_levels.clone()
    changed_levels[...,0] += 1
    with torch.no_grad():
        original = v4_loaded.model(direct)
        changed = v4_loaded.model(replace(direct,hand_levels=changed_levels))
    assert not torch.equal(original.next_state[0],changed.next_state[0])
    assert not torch.equal(original.action_type_logits,changed.action_type_logits)
    decision = adapter.step(frame)
    assert decision.action == 2304
    np.testing.assert_array_equal(_snapshot_tensor(decision.state.payload,'hidden'),original.next_state[0].numpy())


def test_v4_live_unknown_levels_and_acceptance_stay_unknown(v4_loaded):
    adapter = _adapter(v4_loaded,0)
    adapter.reset('game-1')
    inputs = adapter.prepare_current_frame(_frame(actor_id=0)).inputs
    for name in ('entity_levels','entity_level_confidence','hand_levels','hand_level_confidence',
                 'own_last_play_ids','own_last_play_features'):
        assert getattr(inputs,name) is not None
        assert not getattr(inputs,name).any()
    # A submitted previous action is never proof of acceptance.
    adapter._previous_action = 17
    prepared = adapter.prepare_current_frame(_frame(actor_id=0))
    assert not prepared.inputs.own_last_play_ids.any()
    assert prepared.inputs.previous_actions.item() == 17
    with torch.no_grad():
        assert torch.isfinite(v4_loaded.model(_direct_inputs(prepared.inputs)).values).all()


@pytest.mark.parametrize('mutation', ['fractional','zero-confidence','missing-level','missing-next','short','unconfirmed-cost'])
def test_live_level_and_accepted_play_validation_is_not_bypassable(mutation):
    payload = _payload(actor_id=0)
    public = payload['public']
    if mutation == 'fractional': public['entities'][0].update(level=11.5,level_confidence=1)
    elif mutation == 'zero-confidence': public['entities'][0].update(level=11,level_confidence=0)
    elif mutation == 'missing-level': public['entities'][0]['level_confidence']=1
    elif mutation == 'missing-next':
        public.update(own_next_card=None,own_next_card_confidence=0,own_card_levels=[None,None,None,None,11],own_card_level_confidence=[0,0,0,0,1])
    elif mutation == 'short': public['own_card_levels']=[11]
    else: public['own_last_play']={'card_name':'Knight','elixir_cost':3.5}
    with pytest.raises(InferenceContractError):
        parse_public_vision_frame(payload)


def test_live_v4_rejects_unsupported_accumulated_history(v4_loaded):
    v4_loaded.model.config = replace(v4_loaded.model.config,public_history_slots=4,public_seen_card_slots=8)
    with pytest.raises(ValueError,match='externally accumulated opponent history'):
        _adapter(v4_loaded,0)
