"""Recipe v7r3 and the declared continuation (pilot/v7r3-proposal).

Config, argv and validation checks only: no gameplay fitting, tiny synthetic
checkpoints written to tmp_path.
"""

import hashlib
import sys
from pathlib import Path

import pytest
import torch

from clasher.rl.council_pilot import (
    CouncilPilotConfig,
    anchor_checkpoint_path,
    build_council_model_config,
    load_pilot_config,
    opponent_initialization_paths_for_seed,
    training_command,
    training_recipe,
    validate_council_continuation,
    validate_council_trainer_args,
)
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import parse_args

CONFIG = Path("configs/council-pilot-local.toml")
FACTORIZED = {
    "entropy_coef": 0.0,
    "action_type_entropy_coef": 0.0,
    "location_entropy_coef": 0.0,
    "conditional_slot_entropy_coef": 0.003,
    "initial_opponent_policies": ("scripted",),
}
V7R3 = {
    "gae_lambda": 0.99,
    "critic_warmup_updates": 60,
    "anchor_policy_kl_coef": 0.01,
    "phase_order": ("nominal", "nominal-league"),
}


def _config(**extra):
    base = load_pilot_config(CONFIG)
    return CouncilPilotConfig.model_validate(base.model_dump() | FACTORIZED | extra)


def _continuation(tmp_path, **extra):
    checkpoint = tmp_path / "continuation.pt"
    fields = {
        "continuation_seed": 2903,
        "continuation_checkpoint_path": str(checkpoint),
        "continuation_checkpoint_sha256": "0" * 64,
        "continuation_source_config_sha256": "1" * 64,
        "continuation_source_decisions": 1_000_000,
        "critic_warmup_updates": 0,
        "phase_order": ("nominal", "nominal-league"),
    }
    return _config(**(fields | extra))


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


def _command(config, tmp_path, *, seed=2901, arm="scripted", phase="nominal", init=None):
    return training_command(
        config,
        config_path=CONFIG,
        admission=tmp_path / "receipt.json",
        seed=seed,
        arm=arm,
        phase=phase,
        pool_path=tmp_path / "pool.json",
        initialization=init or tmp_path / "initial.pt",
    )


def _value(command, flag):
    return command[command.index(flag) + 1]


def test_v7r3_values_are_declared_literals():
    config = _config(**V7R3)
    assert training_recipe(config)["gae_lambda"] == 0.99
    assert training_recipe(config)["level_randomization_after"] is None
    for field, bad in (
        ("gae_lambda", 0.97),
        ("critic_warmup_updates", 40),
        ("anchor_policy_kl_coef", 0.05),
        ("phase_order", ("nominal",)),
        ("phase_order", ("nominal-league", "nominal")),
    ):
        with pytest.raises(ValueError):
            _config(**(V7R3 | {field: bad}))
    with pytest.raises(ValueError, match="reserved for continuation"):
        _config(critic_warmup_updates=0)


def test_v7r3_argv_carries_lambda_anchor_and_nominal_league(monkeypatch, tmp_path):
    config = _config(**V7R3)
    scripted = _command(config, tmp_path)
    assert _value(scripted, "--gae-lambda") == "0.99"
    assert _value(scripted, "--critic-warmup-updates") == "60"
    anchor = Path(config.output_dir) / "seed-2901" / "initialization" / "scripted.pt"
    assert Path(_value(scripted, "--anchor-checkpoint")) == anchor
    assert anchor_checkpoint_path(config, 2901, "scripted") == anchor
    assert _value(scripted, "--anchor-policy-kl-coef") == "0.01"
    assert "--level-randomization-after" not in scripted
    league = _command(config, tmp_path, phase="nominal-league")
    assert _value(league, "--total-decisions") == "5000000"
    milestones = [league[i + 1] for i, a in enumerate(league) if a == "--checkpoint-decisions"]
    assert {"1000000", "2000000", "3000000", "4000000", "5000000"} <= set(milestones)
    with pytest.raises(ValueError, match="undeclared"):
        _command(config, tmp_path, phase="mixed-league")
    scratch = _command(config, tmp_path, arm="scratch")
    assert "--anchor-checkpoint" not in scratch and "--anchor-policy-kl-coef" not in scratch
    assert _value(scratch, "--critic-warmup-updates") == "0"
    # Mixed-level configs keep the one-million level switch.
    mixed = _command(_config(), tmp_path)
    assert _value(mixed, "--level-randomization-after") == "1000000"
    assert _value(mixed, "--gae-lambda") == "0.95"


def test_trainer_args_must_match_the_v7r3_recipe(monkeypatch, tmp_path):
    config = _config(**V7R3)
    monkeypatch.setenv("CLASHER_ROOT", str(Path(config.gamedata_path).parent))
    builder = _builder(config)
    model_config = build_council_model_config(builder)
    for arm in ("scripted", "scratch"):
        monkeypatch.setattr(sys, "argv", ["trainer", *_command(config, tmp_path, arm=arm)[4:]])
        args = parse_args()
        validate_council_trainer_args(config, args, model_config, builder)
    monkeypatch.setattr(sys, "argv", ["trainer", *_command(config, tmp_path)[4:]])
    args = parse_args()
    for name, bad, match in (
        ("gae_lambda", 0.95, "gae_lambda"),
        ("anchor_policy_kl_coef", 0.05, "anchor_policy_kl_coef"),
        ("anchor_checkpoint", str(tmp_path / "other.pt"), "anchor"),
        ("anchor_checkpoint", None, "anchor"),
        ("level_randomization_after", 1_000_000, "level_randomization_after"),
    ):
        original = getattr(args, name)
        setattr(args, name, bad)
        with pytest.raises(ValueError, match=match):
            validate_council_trainer_args(config, args, model_config, builder)
        setattr(args, name, original)


def test_continuation_declaration_is_all_or_nothing(tmp_path):
    config = _continuation(tmp_path)
    assert training_recipe(config)["continuation"]["seed"] == 2903
    with pytest.raises(ValueError, match="together"):
        _config(continuation_seed=2903)
    with pytest.raises(ValueError, match="declared pilot seed"):
        _continuation(tmp_path, continuation_seed=1234)
    with pytest.raises(ValueError, match="anchor"):
        _continuation(tmp_path, anchor_policy_kl_coef=0.01)
    paths = opponent_initialization_paths_for_seed(
        config, seed=2903, arm="scripted", scripted=tmp_path / "s.pt", scratch=tmp_path / "c.pt"
    )
    assert paths == (tmp_path / "s.pt", tmp_path / "continuation.pt")
    other = opponent_initialization_paths_for_seed(
        config, seed=2901, arm="scripted", scripted=tmp_path / "s.pt", scratch=tmp_path / "c.pt"
    )
    assert other == (tmp_path / "s.pt",)


def test_zero_warmup_is_refused_outside_the_continuation_run(monkeypatch, tmp_path):
    config = _continuation(tmp_path)
    monkeypatch.setenv("CLASHER_ROOT", str(Path(config.gamedata_path).parent))
    builder = _builder(config)
    model_config = build_council_model_config(builder)
    command = _command(config, tmp_path, seed=2903, init=tmp_path / "continuation.pt")
    monkeypatch.setattr(sys, "argv", ["trainer", *command[4:]])
    validate_council_trainer_args(config, parse_args(), model_config, builder)
    command = _command(config, tmp_path, seed=2903, init=tmp_path / "elsewhere.pt")
    monkeypatch.setattr(sys, "argv", ["trainer", *command[4:]])
    with pytest.raises(ValueError, match="declared checkpoint"):
        validate_council_trainer_args(config, parse_args(), model_config, builder)
    command = _command(config, tmp_path, seed=2901)
    monkeypatch.setattr(sys, "argv", ["trainer", *command[4:]])
    with pytest.raises(ValueError, match="continuation run may skip"):
        validate_council_trainer_args(config, parse_args(), model_config, builder)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_continuation_validator_binds_the_declared_checkpoint(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from clasher.rl.council_opponents import (
        CouncilOpponentPool,
        OpponentCheckpoint,
        policy_contract_sha256,
    )
    from clasher.rl.model import ClasherPolicy

    base = _continuation(tmp_path)
    monkeypatch.setenv("CLASHER_ROOT", str(Path(base.gamedata_path).parent))
    builder = _builder(base)
    model_config = build_council_model_config(builder)
    model = ClasherPolicy(model_config, builder.card_stat_features)
    receipt = tmp_path / "receipt.json"
    receipt.write_text('{"admission": true}\n')
    payload = {
        "format_version": 2,
        "model_type": "entity_spatial_recurrent",
        "model_config": model_config.to_dict(),
        "token_names": builder.token_names,
        "model_state_dict": model.state_dict(),
        "gamedata_sha256": base.gamedata_sha256,
        "council_config_sha256": "1" * 64,
        "admission_sha256": _sha(receipt),
        "total_transitions": 1_000_000,
        "council_recipe": {"arm": "scripted"},
    }
    checkpoint = tmp_path / "continuation.pt"
    torch.save(payload, checkpoint)
    config = _continuation(tmp_path, continuation_checkpoint_sha256=_sha(checkpoint))
    pool_path = tmp_path / "pool.json"

    def publish(entries):
        pool = CouncilOpponentPool(
            generation=0,
            phase="initial",
            gamedata_sha256=config.gamedata_sha256,
            policy_contract_sha256=policy_contract_sha256(model_config),
            initial=tuple(OpponentCheckpoint(path=str(p), sha256=_sha(p)) for p in entries),
        )
        pool_path.write_text(pool.model_dump_json())

    publish([checkpoint])
    args = SimpleNamespace(
        seed=2903,
        council_arm="scripted",
        council_admission=receipt,
        council_opponent_pool=pool_path,
        preflight_no_update=False,
    )

    def check(cfg=config, data=payload, **overrides):
        return validate_council_continuation(
            cfg,
            data,
            initialization_path=checkpoint,
            args=SimpleNamespace(**(vars(args) | overrides)),
            builder=builder,
        )

    record = check()
    assert record["initialization"] == "continuation" and record["weights_only"]
    for change, match in (
        ({"total_transitions": 999_936}, "decision count"),
        ({"council_config_sha256": "2" * 64}, "undeclared pilot config"),
        ({"council_recipe": {"arm": "scratch"}}, "scripted arm"),
        ({"admission_sha256": "3" * 64}, "different admission"),
        ({"gamedata_sha256": "4" * 64}, "ruleset"),
    ):
        with pytest.raises(ValueError, match=match):
            check(data=payload | change)
    # The preflight binds a placeholder receipt, never the Tier A admission.
    check(data=payload | {"admission_sha256": "3" * 64}, preflight_no_update=True)
    with pytest.raises(ValueError, match="not the declared continuation"):
        check(seed=2901)
    with pytest.raises(ValueError, match="bytes differ"):
        check(cfg=_continuation(tmp_path, continuation_checkpoint_sha256="5" * 64))
    other = tmp_path / "other.pt"
    other.write_bytes(b"x")
    publish([other])
    with pytest.raises(ValueError, match="published initial opponent"):
        check()


def test_anchor_kl_term_pulls_the_council_policy_toward_its_warm_start(monkeypatch):
    """Synthetic optimizer check of the v7r3 anchor on the council actor contract.

    A tiny rollout (2 agents x 8 steps, 100 ticks) from the council model; the
    copy that moved away from its frozen anchor reports a nonzero
    anchor_policy_kl, and an anchored update ends closer to the anchor than the
    same update with coefficient 0. No gameplay fitting, nothing retained.
    """
    from copy import deepcopy

    import numpy as np

    from clasher.rl.model import ClasherPolicy
    from clasher.rl.selfplay_env import SelfPlayBattleEnv
    from clasher.rl.train_recurrent import collect_rollout, compute_gae, ppo_update

    config = _config(**V7R3)
    monkeypatch.setenv("CLASHER_ROOT", str(Path(config.gamedata_path).parent))
    torch.manual_seed(2903)
    np.random.seed(2903)
    torch.set_num_threads(1)
    builder = _builder(config)
    env = SelfPlayBattleEnv(
        seed=2903, decision_interval_ticks=5, max_ticks=100, public_contract_version=4
    )
    env._structured_obs_builder = builder
    env.reset()
    anchor = ClasherPolicy(build_council_model_config(builder), builder.card_stat_features)
    anchor.eval().requires_grad_(False)
    rollout, *_ = collect_rollout(
        envs=[env],
        builder=builder,
        model=anchor,
        device=torch.device("cpu"),
        rollout_steps=8,
        recurrent_state=anchor.initial_state(2),
        previous_actions=np.full(2, env.action_space.no_op_action, dtype=np.int64),
        previous_rewards=np.zeros(2, dtype=np.float32),
        episode_starts=np.ones(2, dtype=np.bool_),
        quiet_engine=True,
    )
    rollout.rewards[:] = np.linspace(-1, 1, rollout.rewards.size).reshape(
        rollout.rewards.shape
    )
    advantages, returns = compute_gae(rollout, gamma=1.0, gae_lambda=config.gae_lambda)

    def update(model, *, coef, lr=1e-3, step=True):
        np.random.seed(7)
        torch.manual_seed(7)
        optimizer = torch.optim.AdamW(model.parameters(), lr=lr, eps=1e-5, weight_decay=1e-5)
        return ppo_update(
            model=model, optimizer=optimizer, rollout=rollout, advantages=advantages,
            returns=returns, device=torch.device("cpu"), epochs=2, sequence_batch_size=1,
            clip_ratio=config.clip_ratio, value_coef=0.5, entropy_coef=config.entropy_coef,
            action_type_entropy_coef=config.action_type_entropy_coef,
            location_entropy_coef=config.location_entropy_coef,
            conditional_slot_entropy_coef=config.conditional_slot_entropy_coef,
            hand_aux_coef=0.02, elixir_aux_coef=0.05, target_kl=0.0,
            anchor_model=anchor, anchor_policy_kl_coef=coef, apply_optimizer_step=step,
        )

    def distance(model):
        # No optimizer step: the metric is the KL(anchor || model) on the rollout.
        return update(deepcopy(model), coef=0.0, step=False)["anchor_policy_kl"]

    start = deepcopy(anchor).requires_grad_(True)
    assert distance(start) < 1e-6
    # Move the policy away from its warm start with unanchored PPO steps.
    moved = deepcopy(start)
    for _ in range(2):
        update(moved, coef=0.0, lr=0.02)
    drift = distance(moved)
    assert drift > 1e-4
    free, anchored = deepcopy(moved), deepcopy(moved)
    stats_free = update(free, coef=0.0)
    stats_anchored = update(anchored, coef=config.anchor_policy_kl_coef)
    assert stats_anchored["anchor_policy_kl"] > 1e-4
    assert stats_anchored["anchor_policy_kl_loss"] > 0.0 == stats_free["anchor_policy_kl_loss"]
    assert distance(anchored) < distance(free)
    assert distance(anchored) < drift


def test_continuation_start_evaluation_never_shares_outputs_with_the_new_milestone(tmp_path):
    """The continuation checkpoint and this run's own 1M milestone have the same
    file name; evaluation outputs are named by checkpoint stem, so the runner
    must keep the continuation start's cells in their own directory."""
    from clasher.rl.council_pilot import evaluation_commands

    start = tmp_path / "earlier-pilot" / "policy_decisions_001000000.pt"
    config = _continuation(tmp_path, continuation_checkpoint_path=str(start))
    milestone = tmp_path / "run" / "policy_decisions_001000000.pt"
    eval_dir = tmp_path / "run" / "diagnostic-evaluation"

    def outputs(checkpoint, output):
        return {
            command[command.index("--json-out") + 1]
            for command in evaluation_commands(
                config, checkpoint=checkpoint, output=output, final=False
            )
        }

    assert outputs(start, eval_dir) == outputs(milestone, eval_dir)  # the collision
    assert not outputs(start, eval_dir / "continuation-start") & outputs(milestone, eval_dir)
    runner = Path("scripts/run_council_pilot.py").read_text()
    assert 'candidate_dir = eval_dir / "continuation-start"' in runner
    assert "output=candidate_dir" in runner and "output=eval_dir" not in runner
