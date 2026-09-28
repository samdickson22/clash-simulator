from __future__ import annotations

from pathlib import Path

import torch

from clasher.rl.checkpoint_upgrade import (
    scale_semantic_v3_adapter,
    upgrade_v1_checkpoint_to_semantic_v3,
)
from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.structured_obs import StructuredObservationBuilder


def _write_v1_checkpoint(path: Path) -> None:
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=8)
    config = PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=builder.max_entities,
        d_model=16,
        num_heads=2,
        actor_layers=1,
        critic_layers=1,
        memory_size=16,
    )
    model = ClasherPolicy(config, builder.card_stat_features)
    torch.save(
        {
            "format_version": 2,
            "model_config": config.to_dict(),
            "token_names": builder.token_names,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": {"must": "be dropped"},
        },
        path,
    )


def test_upgrade_adds_only_zero_preserving_semantic_v3_state(tmp_path: Path) -> None:
    source = tmp_path / "source.pt"
    output = tmp_path / "upgraded.pt"
    _write_v1_checkpoint(source)

    report = upgrade_v1_checkpoint_to_semantic_v3(
        source_path=source,
        output_path=output,
        decks_path=Path("decks.json"),
        seed=123,
    )

    payload = torch.load(output, map_location="cpu", weights_only=False)
    assert payload["model_config"]["card_semantics_version"] == 3
    assert "optimizer_state_dict" not in payload
    assert report["target_parameters"] > report["source_parameters"]
    assert report["missing_keys_initialized"]
    loaded = load_policy_checkpoint(
        output,
        device=torch.device("cpu"),
        decks_path="decks.json",
    )
    for encoder in (loaded.model.actor_encoder, loaded.model.critic_encoder):
        assert encoder.semantic_card_projection is not None
        torch.testing.assert_close(
            encoder.semantic_card_projection[-1].weight,
            torch.zeros_like(encoder.semantic_card_projection[-1].weight),
        )
        torch.testing.assert_close(
            encoder.semantic_card_projection[-1].bias,
            torch.zeros_like(encoder.semantic_card_projection[-1].bias),
        )


def test_semantic_adapter_scaling_changes_only_final_residual_layers(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.pt"
    upgraded = tmp_path / "upgraded.pt"
    trained = tmp_path / "trained.pt"
    scaled = tmp_path / "scaled.pt"
    _write_v1_checkpoint(source)
    upgrade_v1_checkpoint_to_semantic_v3(
        source_path=source,
        output_path=upgraded,
        decks_path=Path("decks.json"),
        seed=123,
    )
    payload = torch.load(upgraded, map_location="cpu", weights_only=False)
    for encoder in ("actor_encoder", "critic_encoder"):
        for suffix in ("weight", "bias"):
            key = f"{encoder}.semantic_card_projection.2.{suffix}"
            payload["model_state_dict"][key].fill_(2.0)
    torch.save(payload, trained)

    report = scale_semantic_v3_adapter(
        source_path=trained,
        output_path=scaled,
        alpha=0.25,
    )

    result = torch.load(scaled, map_location="cpu", weights_only=False)
    assert len(report["scaled_keys"]) == 4
    for key, value in result["model_state_dict"].items():
        if key in report["scaled_keys"]:
            torch.testing.assert_close(value, torch.full_like(value, 0.5))
        else:
            torch.testing.assert_close(value, payload["model_state_dict"][key])
