import sys
from dataclasses import replace

import pytest
import torch

from clasher.battle import BattleState
from clasher.rl import train_recurrent
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.parallel_rollout import (
    ActorWorkerConfig,
    OpponentSpec,
    build_policy_observation_builder,
    load_checkpoint_opponent,
    opponent_spec_for_worker,
)
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import restore_optimizer_state


def _config(mode: str, pool: tuple[OpponentSpec, ...]) -> ActorWorkerConfig:
    return ActorWorkerConfig(
        decks_path="decks.json",
        token_names=(),
        model_config={},
        decision_interval=8,
        max_ticks=9090,
        mirror_match=False,
        opponent_mode=mode,
        opponent_pool=pool,
        engine_fast_path="on",
        quiet_engine=True,
        base_seed=23,
        torch_threads=1,
    )


def test_league_opponents_are_distributed_round_robin_across_workers():
    pool = (
        OpponentSpec(kind="random"),
        OpponentSpec(kind="strategy", strategy="reactive-defense"),
        OpponentSpec(kind="checkpoint", checkpoint="update800.pt"),
        OpponentSpec(kind="checkpoint", checkpoint="update1300.pt"),
    )
    config = _config("league", pool)

    assigned = tuple(opponent_spec_for_worker(config, worker) for worker in range(12))

    assert assigned == pool * 3


def test_selfplay_has_no_stationary_opponent_spec():
    assert opponent_spec_for_worker(_config("selfplay", ()), 0) is None


def test_stationary_mode_requires_an_opponent_pool():
    with pytest.raises(ValueError, match="requires a pool"):
        opponent_spec_for_worker(_config("league", ()), 0)


def test_opponent_spec_rejects_inconsistent_payloads():
    with pytest.raises(ValueError, match="random opponent cannot"):
        OpponentSpec(kind="random", checkpoint="not-used.pt")
    with pytest.raises(ValueError, match="requires a path"):
        OpponentSpec(kind="checkpoint")
    with pytest.raises(ValueError, match="known strategy"):
        OpponentSpec(kind="strategy", strategy="omniscient-cheater")


def test_checkpoint_opponent_may_use_a_different_compatible_architecture(tmp_path):
    builder = StructuredObservationBuilder(
        decks_path="decks.json", max_entities=16
    )
    learner_config = PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=16,
        d_model=32,
        num_heads=4,
        actor_layers=1,
        critic_layers=1,
        memory_size=48,
    )
    opponent_config = replace(
        learner_config,
        repair_stage_sizes=(8,),
        repair_stage_prototype_counts=(0,),
    )
    opponent = ClasherPolicy(opponent_config, builder.card_stat_features)
    checkpoint = tmp_path / "opponent.pt"
    torch.save(
        {
            "format_version": 2,
            "model_config": opponent_config.to_dict(),
            "token_names": builder.token_names,
            "model_state_dict": opponent.state_dict(),
        },
        checkpoint,
    )

    loaded = load_checkpoint_opponent(
        checkpoint,
        device=torch.device("cpu"),
        builder=builder,
        learner_config=learner_config,
        token_names=builder.token_names,
    )

    assert loaded.config == opponent_config
    assert not loaded.training


def test_parallel_policy_builder_preserves_public_belief_slot_schema():
    base = StructuredObservationBuilder(decks_path="decks.json", max_entities=16)
    config = PolicyConfig(
        num_tokens=base.spec.num_tokens,
        max_entities=16,
        public_history_slots=4,
        public_seen_card_slots=8,
        d_model=32,
        num_heads=4,
        actor_layers=1,
        critic_layers=1,
        memory_size=48,
    )

    builder = build_policy_observation_builder(
        config,
        decks_path="decks.json",
        token_names=base.token_names,
    )

    assert builder.spec.public_history_slots == 4
    assert builder.spec.public_seen_card_slots == 8
    observation = builder.build_actor(BattleState(), 0)
    assert observation.opponent_history_ids.shape == (4,)
    assert observation.opponent_seen_card_ids.shape == (8,)


def test_semantic_v2_learner_can_load_legacy_v1_checkpoint_opponent(tmp_path):
    learner_builder = StructuredObservationBuilder(
        decks_path="decks.json",
        max_entities=16,
        card_semantics_version=2,
    )
    learner_config = PolicyConfig(
        num_tokens=learner_builder.spec.num_tokens,
        max_entities=16,
        card_semantics_version=2,
        d_model=32,
        num_heads=4,
        actor_layers=1,
        critic_layers=1,
        memory_size=48,
    )
    opponent_builder = StructuredObservationBuilder(
        decks_path="decks.json",
        max_entities=16,
        token_names=learner_builder.token_names,
        card_semantics_version=1,
    )
    opponent_config = replace(learner_config, card_semantics_version=1)
    opponent = ClasherPolicy(opponent_config, opponent_builder.card_stat_features)
    checkpoint = tmp_path / "legacy-opponent.pt"
    torch.save(
        {
            "format_version": 2,
            "model_config": opponent_config.to_dict(),
            "token_names": learner_builder.token_names,
            "model_state_dict": opponent.state_dict(),
        },
        checkpoint,
    )

    loaded = load_checkpoint_opponent(
        checkpoint,
        device=torch.device("cpu"),
        builder=learner_builder,
        learner_config=learner_config,
        token_names=learner_builder.token_names,
    )

    assert loaded.config.card_semantics_version == 1
    assert loaded.actor_encoder.card_stat_features.shape[1] == 16


def test_checkpoint_opponent_rejects_incompatible_observation_schema(tmp_path):
    builder = StructuredObservationBuilder(
        decks_path="decks.json", max_entities=16
    )
    learner_config = PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=16,
        d_model=32,
        num_heads=4,
        actor_layers=1,
        critic_layers=1,
        memory_size=48,
    )
    opponent_config = replace(learner_config, actor_global_size=17)
    opponent = ClasherPolicy(opponent_config, builder.card_stat_features)
    checkpoint = tmp_path / "incompatible.pt"
    torch.save(
        {
            "format_version": 2,
            "model_config": opponent_config.to_dict(),
            "token_names": builder.token_names,
            "model_state_dict": opponent.state_dict(),
        },
        checkpoint,
    )

    with pytest.raises(ValueError, match="observation schemas differ"):
        load_checkpoint_opponent(
            checkpoint,
            device=torch.device("cpu"),
            builder=builder,
            learner_config=learner_config,
            token_names=builder.token_names,
        )


def test_resume_restores_optimizer_moments_but_honors_requested_learning_rate():
    source_parameter = torch.nn.Parameter(torch.ones(()))
    source = torch.optim.AdamW([source_parameter], lr=2.5e-4)
    source_parameter.grad = torch.ones_like(source_parameter)
    source.step()

    resumed_parameter = torch.nn.Parameter(torch.ones(()))
    resumed = torch.optim.AdamW([resumed_parameter], lr=2.5e-4)
    restore_optimizer_state(resumed, source.state_dict(), learning_rate=1e-4)

    assert resumed.param_groups[0]["lr"] == pytest.approx(1e-4)
    assert resumed.state[resumed_parameter]["step"].item() == 1


def test_reset_optimizer_flag_is_disabled_by_default_and_can_be_enabled(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["train_recurrent"])
    defaults = train_recurrent.parse_args()
    assert defaults.reset_optimizer is False
    assert defaults.conditional_slot_entropy_coef == 0.0
    assert defaults.causal_spatial_rehearsal_corpus is None
    assert defaults.causal_spatial_rehearsal_coef == 0.0

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "train_recurrent",
            "--reset-optimizer",
            "--conditional-slot-entropy-coef",
            "0.025",
            "--causal-spatial-rehearsal-corpus",
            "spatial.npz",
            "--causal-spatial-rehearsal-public-sidecar",
            "spatial_public.npz",
            "--causal-spatial-rehearsal-coef",
            "0.5",
            "--causal-spatial-rehearsal-card-coef",
            "1.0",
            "--causal-spatial-rehearsal-tile-coef",
            "0.25",
        ],
    )
    configured = train_recurrent.parse_args()
    assert configured.reset_optimizer is True
    assert configured.conditional_slot_entropy_coef == pytest.approx(0.025)
    assert configured.causal_spatial_rehearsal_corpus == "spatial.npz"
    assert configured.causal_spatial_rehearsal_coef == pytest.approx(0.5)
    assert configured.causal_spatial_rehearsal_tile_coef == pytest.approx(0.25)


def test_parallel_worker_config_carries_public_teacher_contract():
    config = _config("random", (OpponentSpec(kind="random"),))
    configured = ActorWorkerConfig(
        **{
            **config.__dict__,
            "learner_teacher_strategy": "balanced",
            "learner_teacher_balanced_config": {"minimum_elixir_to_play": 3.0},
        }
    )
    assert configured.learner_teacher_strategy == "balanced"
    assert configured.learner_teacher_balanced_config == {
        "minimum_elixir_to_play": 3.0
    }
