from __future__ import annotations

import pytest
import torch

from clasher.rl.eval import evaluate, load_policy_checkpoint
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.structured_obs import StructuredObservationBuilder


def test_checkpoint_loader_preserves_semantics_and_lane_contract(tmp_path) -> None:
    builder = StructuredObservationBuilder(
        card_vocab=["Knight"],
        max_entities=8,
        card_semantics_version=3,
        canonical_lane_globals=True,
    )
    config = PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=8,
        card_semantics_version=3,
        canonical_lane_globals=True,
        d_model=16,
        num_heads=4,
        actor_layers=1,
        critic_layers=1,
        memory_size=16,
    )
    model = ClasherPolicy(config, builder.card_stat_features)
    path = tmp_path / "policy.pt"
    torch.save(
        {
            "format_version": 2,
            "model_config": config.to_dict(),
            "model_state_dict": model.state_dict(),
            "token_names": builder.token_names,
        },
        path,
    )

    loaded = load_policy_checkpoint(
        path, device=torch.device("cpu"), decks_path="decks.json"
    )

    assert loaded.builder.card_semantics_version == 3
    assert loaded.builder.canonical_lane_globals is True
    assert loaded.model.config == config


def test_evaluation_opponent_contract_fails_before_runtime() -> None:
    with pytest.raises(ValueError, match="strategy opponent mode"):
        evaluate(
            candidate=None,  # type: ignore[arg-type]
            decks_path=None,  # type: ignore[arg-type]
            games=2,
            seed=1,
            decision_interval=8,
            max_ticks=1,
            opponent_mode="strategy",
            opponent=None,
            deterministic=True,
            quiet_engine=True,
            device=torch.device("cpu"),
        )
