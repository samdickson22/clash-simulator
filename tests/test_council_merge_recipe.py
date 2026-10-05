"""Merge-plan items 5 and 6: critic warm-up and target-KL guard.

Synthetic optimizer checks only: tiny models, 100-tick rollouts, no gameplay
fitting and no retained weights.
"""

import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
import torch

from clasher.rl.council_pilot import (
    build_council_model_config,
    critic_warmup_updates_for_arm,
    load_pilot_config,
    training_command,
    validate_council_trainer_args,
)
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import (
    collect_rollout,
    compute_gae,
    critic_parameter_names,
    parse_args,
    ppo_update,
)

CONFIG = Path("configs/council-pilot-local.toml")


def _parsed(monkeypatch, tmp_path, arm):
    config = load_pilot_config(CONFIG)
    command = training_command(
        config,
        config_path=CONFIG,
        admission=tmp_path / "receipt.json",
        seed=config.seeds[0],
        arm=arm,
        phase="nominal",
        pool_path=tmp_path / "pool.json",
        initialization=tmp_path / "initial.pt",
    )
    monkeypatch.setattr(sys, "argv", ["trainer", *command[4:]])
    return config, parse_args()


def _builder(config):
    return StructuredObservationBuilder(
        decks_path=config.training_decks_path,
        max_entities=128,
        card_semantics_version=4,
        public_history_slots=4,
        public_seen_card_slots=8,
        public_entity_levels=True,
        public_hand_levels=True,
        canonical_lane_globals=True,
    )


def test_pilot_records_fixed_warmup_and_kl_values_per_arm(monkeypatch, tmp_path):
    config = load_pilot_config(CONFIG)
    assert config.critic_warmup_updates == 20
    assert config.target_kl == 0.02
    assert "critic_warmup_updates = 20" in CONFIG.read_text()
    assert "target_kl = 0.02" in CONFIG.read_text()
    assert critic_warmup_updates_for_arm(config, "scripted") == 20
    assert critic_warmup_updates_for_arm(config, "scratch") == 0
    for field, value in (("critic_warmup_updates", 5), ("target_kl", 0.0)):
        with pytest.raises(ValueError):
            type(config).model_validate(config.model_dump() | {field: value})
    monkeypatch.setenv("CLASHER_ROOT", str(Path(config.gamedata_path).parent))
    builder = _builder(config)
    model_config = build_council_model_config(builder)
    for arm, warmup in (("scripted", 20), ("scratch", 0)):
        config, args = _parsed(monkeypatch, tmp_path, arm)
        assert args.council_arm == arm
        assert args.critic_warmup_updates == warmup
        assert args.target_kl == 0.02
        validate_council_trainer_args(config, args, model_config, builder)
        # The scratch arm cannot borrow the warm-up and the scripted arm
        # cannot drop it; neither may silently disable the KL guard.
        for name, bad in (
            ("critic_warmup_updates", 20 - warmup),
            ("target_kl", 0.0),
            ("council_arm", None),
        ):
            original = getattr(args, name)
            setattr(args, name, bad)
            with pytest.raises(ValueError):
                validate_council_trainer_args(config, args, model_config, builder)
            setattr(args, name, original)


@pytest.fixture(scope="module")
def rollout_fixture():
    torch.manual_seed(505)
    np.random.seed(505)
    torch.set_num_threads(1)
    builder = StructuredObservationBuilder(
        decks_path="decks.json",
        max_entities=32,
        public_entity_levels=True,
        public_hand_levels=True,
        card_semantics_version=4,
    )
    env = SelfPlayBattleEnv(
        seed=505, decision_interval_ticks=5, max_ticks=100, public_contract_version=4
    )
    env._structured_obs_builder = builder
    env.reset()
    model = ClasherPolicy(
        PolicyConfig(
            num_tokens=builder.spec.num_tokens,
            max_entities=32,
            public_contract_version=4,
            public_observation_confidence=True,
            public_token_names=builder.token_names,
            card_semantics_version=4,
            d_model=32,
            num_heads=4,
            actor_layers=1,
            critic_layers=1,
            memory_size=48,
        ),
        builder.card_stat_features,
    ).eval()
    rollout, *_ = collect_rollout(
        envs=[env],
        builder=builder,
        model=model,
        device=torch.device("cpu"),
        rollout_steps=8,
        recurrent_state=model.initial_state(2),
        previous_actions=np.full(2, env.action_space.no_op_action, dtype=np.int64),
        previous_rewards=np.zeros(2, dtype=np.float32),
        episode_starts=np.ones(2, dtype=np.bool_),
        quiet_engine=True,
    )
    # Synthetic returns with a nonzero target so the value loss has gradient.
    rollout.rewards[:] = np.linspace(-1, 1, rollout.rewards.size).reshape(
        rollout.rewards.shape
    )
    return model, rollout


def _update(model, rollout, *, lr=1e-3, target_kl=0.0, critic_only=False, epochs=2):
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=lr, eps=1e-5, weight_decay=1e-5
    )
    advantages, returns = compute_gae(rollout, gamma=1.0, gae_lambda=0.95)
    np.random.seed(7)
    stats = ppo_update(
        model=model,
        optimizer=optimizer,
        rollout=rollout,
        advantages=advantages,
        returns=returns,
        device=torch.device("cpu"),
        epochs=epochs,
        sequence_batch_size=1,
        clip_ratio=0.2,
        value_coef=0.5,
        entropy_coef=0.01,
        hand_aux_coef=0.02,
        elixir_aux_coef=0.05,
        target_kl=target_kl,
        critic_only=critic_only,
    )
    return stats, optimizer


def test_critic_warmup_keeps_actor_bit_identical_and_moves_critic(rollout_fixture):
    base, rollout = rollout_fixture
    model = deepcopy(base)
    critic = critic_parameter_names(model)
    assert critic and all(
        name.startswith(("critic_encoder.", "value_head.")) for name in critic
    )
    before = {name: value.detach().clone() for name, value in model.named_parameters()}
    buffers = {name: value.clone() for name, value in model.named_buffers()}
    optimizer = None
    for _ in range(3):  # several warm-up updates, as the pilot runs 20
        stats, optimizer = _update(model, rollout, critic_only=True)
        assert stats["critic_warmup"] == 1.0
        assert stats["optimizer_steps"] == 4
    after = dict(model.named_parameters())
    actor = [name for name in before if name not in critic]
    assert actor
    for name in actor:
        assert torch.equal(before[name], after[name].detach()), name
    for name, value in model.named_buffers():
        assert torch.equal(buffers[name], value), name
    assert any(not torch.equal(before[name], after[name].detach()) for name in critic)
    # AdamW never saw an actor gradient, so no actor optimizer state exists.
    tracked = {id(parameter) for parameter in optimizer.state}
    for name, parameter in model.named_parameters():
        assert (id(parameter) in tracked) == (name in critic), name
    # Normal PPO afterwards does move the actor.
    stats, _ = _update(model, rollout, critic_only=False)
    assert stats["critic_warmup"] == 0.0
    assert any(
        not torch.equal(before[name], model.get_parameter(name).detach())
        for name in actor
    )


def test_scratch_path_is_unchanged_by_the_warmup_option(rollout_fixture):
    base, rollout = rollout_fixture
    default, explicit = deepcopy(base), deepcopy(base)
    optimizer = torch.optim.AdamW(default.parameters(), lr=1e-3, eps=1e-5, weight_decay=1e-5)
    advantages, returns = compute_gae(rollout, gamma=1.0, gae_lambda=0.95)
    np.random.seed(7)
    ppo_update(
        model=default, optimizer=optimizer, rollout=rollout, advantages=advantages,
        returns=returns, device=torch.device("cpu"), epochs=2, sequence_batch_size=1,
        clip_ratio=0.2, value_coef=0.5, entropy_coef=0.01, hand_aux_coef=0.02,
        elixir_aux_coef=0.05, target_kl=0.0,
    )
    _update(explicit, rollout, critic_only=False)
    for (name, a), (_, b) in zip(default.named_parameters(), explicit.named_parameters()):
        assert torch.equal(a, b), name


def test_target_kl_guard_stops_epochs_early(rollout_fixture):
    base, rollout = rollout_fixture
    pilot_target = load_pilot_config(CONFIG).target_kl
    # A deliberately large synthetic step makes the second minibatch's
    # approximate KL exceed the recorded 0.02 guard.
    guarded, _ = _update(deepcopy(base), rollout, lr=0.05, target_kl=pilot_target)
    unguarded, _ = _update(deepcopy(base), rollout, lr=0.05, target_kl=0.0)
    assert unguarded["optimizer_steps"] == 4 and unguarded["kl_early_stop"] == 0.0
    assert guarded["kl_early_stop"] == 1.0
    assert 1 <= guarded["optimizer_steps"] < 4
    # A tiny step stays inside the guard and runs every minibatch.
    gentle, _ = _update(deepcopy(base), rollout, lr=1e-7, target_kl=pilot_target)
    assert gentle["kl_early_stop"] == 0.0 and gentle["optimizer_steps"] == 4
    # During critic warm-up the actor is frozen, so the guard cannot fire.
    warm, _ = _update(deepcopy(base), rollout, lr=0.05, target_kl=pilot_target, critic_only=True)
    assert warm["kl_early_stop"] == 0.0 and warm["optimizer_steps"] == 4


def test_warmup_requires_an_initialized_actor(monkeypatch):
    from clasher.rl import train_recurrent

    monkeypatch.setattr(
        sys, "argv", ["trainer", "--critic-warmup-updates", "20", "--updates", "1"]
    )
    with pytest.raises(ValueError, match="initialized actor"):
        train_recurrent.main()


@pytest.mark.parametrize("critic_only", [True, False])
def test_preflight_no_step_update_leaves_weights_and_optimizer_untouched(
    rollout_fixture, critic_only
):
    from clasher.rl.council_pilot import state_dict_sha256

    base, rollout = rollout_fixture
    model = deepcopy(base)
    before = state_dict_sha256(model.state_dict())
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.05, eps=1e-5, weight_decay=1e-5)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("optimizer.step() called during preflight")

    optimizer.step = forbidden
    advantages, returns = compute_gae(rollout, gamma=1.0, gae_lambda=0.95)
    stats = ppo_update(
        model=model, optimizer=optimizer, rollout=rollout, advantages=advantages,
        returns=returns, device=torch.device("cpu"), epochs=2, sequence_batch_size=1,
        clip_ratio=0.2, value_coef=0.5, entropy_coef=0.01, hand_aux_coef=0.02,
        elixir_aux_coef=0.05, target_kl=0.02, critic_only=critic_only,
        apply_optimizer_step=False,
    )
    assert stats["optimizer_steps"] == 0.0 and stats["evaluated_minibatches"] == 4
    assert stats["critic_warmup"] == float(critic_only)
    assert np.isfinite(stats["loss"]) and stats["grad_norm"] > 0
    assert state_dict_sha256(model.state_dict()) == before
    assert not optimizer.state
    assert all(parameter.grad is None for parameter in model.parameters())
