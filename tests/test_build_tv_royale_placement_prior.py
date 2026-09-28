import importlib.util
from pathlib import Path

import torch

from clasher.rl.common import BOARD_WIDTH, NUM_TILES
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.structured_obs import StructuredObservationBuilder


def _load_script():
    path = Path("scripts/build_tv_royale_placement_prior.py")
    spec = importlib.util.spec_from_file_location(
        "build_tv_royale_placement_prior", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prior_filters_incompatible_labels_and_mirrors_locations() -> None:
    module = _load_script()
    builder = StructuredObservationBuilder(
        card_vocab=["Knight", "Fireball", "Miner"], max_entities=8
    )
    rows = [
        {"card": "knight", "x": "100", "y": "500", "source_shard": "1"},
        {"card": "fireball", "x": "100", "y": "500", "source_shard": "1"},
        {"card": "miner", "x": "100", "y": "500", "source_shard": "1"},
        {"card": "knight", "x": "100", "y": "200", "source_shard": "1"},
        {"card": "knight", "x": "100", "y": "500", "source_shard": "0"},
    ]

    logits, metadata = module.build_prior_logits(
        rows,
        builder=builder,
        enabled_cards=("Knight", "Fireball", "Miner"),
    )

    knight = builder.token_id("Knight")
    tile = module.source_pixel_to_canonical_tile(100, 500)
    mirror = (tile // BOARD_WIDTH) * BOARD_WIDTH + (
        BOARD_WIDTH - 1 - tile % BOARD_WIDTH
    )
    assert logits.shape == (builder.spec.num_tokens, NUM_TILES)
    assert logits[knight, tile] == logits[knight, mirror]
    assert torch.count_nonzero(logits[builder.token_id("Fireball")]).item() == 0
    assert torch.count_nonzero(logits[builder.token_id("Miner")]).item() == 0
    assert metadata["accepted_samples"] == 1
    assert metadata["skipped"] == {
        "coordinate_schema": 1,
        "global_deploy_ambiguous_seat": 1,
        "opponent_side": 1,
        "spell": 1,
    }


def test_augment_checkpoint_adds_only_scaled_prior() -> None:
    module = _load_script()
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=8)
    config = PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=8,
        d_model=32,
        num_heads=4,
        actor_layers=1,
        critic_layers=1,
        memory_size=48,
    )
    model = ClasherPolicy(config, builder.card_stat_features)
    payload = {
        "format_version": 2,
        "model_config": config.to_dict(),
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": {"state": {}},
        "token_names": builder.token_names,
    }
    prior = torch.zeros((config.num_tokens, NUM_TILES))
    prior[builder.token_id("Knight"), 12] = 2.0

    augmented = module.augment_checkpoint(
        payload,
        builder=builder,
        prior_logits=prior,
        scale=0.25,
    )

    assert augmented["model_config"]["placement_prior_enabled"] is True
    assert "optimizer_state_dict" not in augmented
    assert augmented["model_state_dict"]["placement_prior.weight"][
        builder.token_id("Knight"), 12
    ] == torch.tensor(0.5)
