from __future__ import annotations

import pytest
import torch

from clasher.rl.eval import evaluate, load_policy_checkpoint
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.structured_obs import StructuredObservationBuilder


@pytest.mark.parametrize("version", [3, 4])
def test_checkpoint_loader_preserves_semantics_and_lane_contract(tmp_path, version) -> None:
    builder = StructuredObservationBuilder(
        card_vocab=["Knight", "Archers", "Cannon"],
        max_entities=8,
        card_semantics_version=version,
        canonical_lane_globals=True,
    )
    config = PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=8,
        card_semantics_version=version,
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

    assert loaded.builder.card_semantics_version == version
    assert loaded.builder.canonical_lane_globals is True
    assert loaded.model.config == config
    archer = loaded.builder.token_id("Archers")
    cannon = loaded.builder.token_id("Cannon")
    assert loaded.builder.card_stat_features[archer, 15] == (1 if version == 4 else 0)
    assert loaded.builder.card_stat_features[cannon, -1] == pytest.approx(0.65 if version == 4 else 0)
    torch.testing.assert_close(
        loaded.model.actor_encoder.card_stat_features,
        model.actor_encoder.card_stat_features,
    )


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
