"""Throughput limits and the learner-side inference options of the pilot config."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from clasher.rl.council_pilot import (
    CouncilPilotConfig,
    build_council_model_config,
    load_pilot_config,
    training_command,
    validate_council_trainer_args,
)
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import parse_args

CONFIG = Path("configs/council-pilot-local.toml")


def _with(**changes) -> CouncilPilotConfig:
    base = load_pilot_config(CONFIG).model_dump()
    return CouncilPilotConfig.model_validate(base | changes)


def test_strategy_scale_is_allowed_and_bounded():
    config = _with(
        num_envs=64,
        actor_workers=8,
        torch_threads=8,
        smoke_decisions=98_304,
        rollout_inference="learner",
        device="mps",
        inference_device="mps",
    )
    assert config.num_envs * config.rollout_steps == 8192
    for bad in (
        {"num_envs": 65},
        {"num_envs": 64, "actor_workers": 17},
        {"num_envs": 64, "actor_workers": 6},  # unequal partition
        {"torch_threads": 9},
        {"num_envs": 64, "actor_workers": 8},  # 100,000 smoke is not divisible by 64
    ):
        with pytest.raises(ValueError):
            _with(**bad)
    # The learning recipe stays signed.
    for bad in ({"epochs": 3}, {"learning_rate": 3e-4}, {"clip_ratio": 0.1}, {"rollout_steps": 64}):
        with pytest.raises(ValueError):
            _with(**bad)


def test_inference_device_must_be_cpu_or_the_accounted_learner_device():
    with pytest.raises(ValueError, match="accounted learner device"):
        _with(rollout_inference="learner", device="cpu", inference_device="mps")
    with pytest.raises(ValueError, match="per-worker"):
        _with(rollout_inference="worker", device="mps", inference_device="mps")
    assert _with(rollout_inference="learner", device="mps", inference_device="cpu")


def test_learner_inference_command_parses_and_validates(monkeypatch, tmp_path):
    config = _with(
        num_envs=32,
        actor_workers=8,
        torch_threads=4,
        rollout_inference="learner",
        device="mps",
        inference_device="mps",
    )
    command = training_command(
        config,
        config_path=CONFIG,
        admission=tmp_path / "receipt.json",
        seed=config.seeds[0],
        arm="scripted",
        phase="nominal",
        pool_path=tmp_path / "pool.json",
        initialization=tmp_path / "initial.pt",
    )
    assert command[command.index("--rollout-inference") + 1] == "learner"
    assert command[command.index("--actor-device") + 1] == "mps"
    monkeypatch.setattr(sys, "argv", ["trainer", *command[4:]])
    args = parse_args()
    builder = StructuredObservationBuilder(
        decks_path=config.training_decks_path,
        max_entities=128,
        card_semantics_version=4,
        public_history_slots=4,
        public_seen_card_slots=8,
        public_entity_levels=True,
        public_hand_levels=True,
        canonical_lane_globals=True,
    )
    monkeypatch.setenv("CLASHER_ROOT", str(Path(config.gamedata_path).parent))
    validate_council_trainer_args(config, args, build_council_model_config(builder), builder)
    assert args.num_envs == 32 and args.actor_workers == 8 and args.sequence_batch_size == 2
    args.rollout_inference = "worker"
    with pytest.raises(ValueError, match="rollout_inference"):
        validate_council_trainer_args(config, args, build_council_model_config(builder), builder)


def test_default_config_keeps_the_admitted_worker_path(monkeypatch, tmp_path):
    config = load_pilot_config(CONFIG)
    assert config.rollout_inference == "worker" and config.inference_device == "cpu"
    command = training_command(
        config,
        config_path=CONFIG,
        admission=tmp_path / "receipt.json",
        seed=config.seeds[0],
        arm="scratch",
        phase="nominal",
        pool_path=tmp_path / "pool.json",
        initialization=tmp_path / "initial.pt",
    )
    assert command[command.index("--rollout-inference") + 1] == "worker"
    assert command[command.index("--actor-device") + 1] == "cpu"
