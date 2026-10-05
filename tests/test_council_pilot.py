"""No-fit configuration, curriculum and execution-boundary contracts."""

import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from clasher.rl.council_pilot import (
    CouncilPilotConfig,
    build_council_model_config,
    evaluation_commands,
    load_pilot_config,
    training_command,
    validate_council_trainer_args,
)
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import parse_args, planned_rollout_steps

CONFIG = Path("configs/council-pilot-local.toml")


def test_validated_local_recipe_covers_all_six_mandatory_runs():
    config = load_pilot_config(CONFIG)
    assert len(config.seeds) * len(config.arms) == 6
    assert config.decisions_per_seed == 5_000_000
    assert config.num_envs * config.rollout_steps == 512
    assert config.evaluation_games_per_style * len(config.evaluation_styles) * 2 >= 512
    bad = config.model_dump() | {"actor_layers": 2}
    with pytest.raises(ValueError):
        CouncilPilotConfig.model_validate(bad)
    bad = config.model_dump() | {"num_envs": 4.0}
    with pytest.raises(ValueError):
        CouncilPilotConfig.model_validate(bad)


def test_exact_milestones_do_not_overshoot_or_count_opponent_seat():
    total = 0
    chunks = []
    while total < 5_000_000:
        steps = planned_rollout_steps(
            total_decisions=total,
            target_decisions=5_000_000,
            checkpoint_decisions=(1_000_000, 5_000_000),
            agents=4,
            rollout_steps=128,
        )
        total += 4 * steps
        if steps != 128:
            chunks.append((total, steps))
    assert total == 5_000_000
    assert (1_000_000, 16) in chunks
    assert (
        planned_rollout_steps(
            total_decisions=total,
            target_decisions=total,
            checkpoint_decisions=(),
            agents=4,
            rollout_steps=128,
        )
        == 0
    )
    with pytest.raises(ValueError, match="divisible"):
        planned_rollout_steps(
            total_decisions=0,
            target_decisions=5,
            checkpoint_decisions=(),
            agents=4,
            rollout_steps=128,
        )


def test_mixed_levels_start_only_at_episode_reset_and_restore_nominal():
    env = SelfPlayBattleEnv(
        public_contract_version=4,
        level_randomization_after=1_000_000,
        mixed_level_probability=1.0,
        seed=1,
    )
    env.reset()
    assert not env.episode_mixed_levels
    assert all(
        player.tower_level == 11 and not player.card_levels
        for player in env.battle.players
    )
    env.set_learner_decisions(1_000_000)
    assert all(
        player.tower_level == 11 and not player.card_levels
        for player in env.battle.players
    )
    env.reset()
    assert env.episode_mixed_levels
    assert all(
        set(player.card_levels.values()) <= {10, 11, 12}
        for player in env.battle.players
    )
    assert any(
        set(player.card_levels.values()) != {11} for player in env.battle.players
    )
    for seat in (0, 1):
        observation = env.get_structured_observation(seat)
        player = env.battle.players[seat]
        np.testing.assert_array_equal(
            observation.hand_levels,
            [
                player.card_level(name) if name else 0
                for name in [*player.hand, player.get_next_card()]
            ],
        )
    env.mixed_level_probability = 0
    env.reset()
    assert all(
        player.tower_level == 11 and not player.card_levels
        for player in env.battle.players
    )
    with pytest.raises(ValueError, match="backwards"):
        env.set_learner_decisions(1)


def test_runner_arguments_parse_to_the_full_council_model(monkeypatch, tmp_path):
    config = load_pilot_config(CONFIG)
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
    model_config = build_council_model_config(builder)
    monkeypatch.setenv("CLASHER_ROOT", str(Path(config.gamedata_path).parent))
    validate_council_trainer_args(config, args, model_config, builder)
    assert args.total_decisions == 1_000_000 and args.target_kl == 0.02
    assert args.council_arm == "scratch" and args.critic_warmup_updates == 0
    assert args.checkpoint_decisions == [1_000_000, 5_000_000]
    assert not args.lr_anneal and args.actor_workers == 2
    with pytest.raises(ValueError, match="model"):
        validate_council_trainer_args(
            config, args, replace(model_config, actor_layers=2), builder
        )


def test_fixed_evaluation_uses_frozen_seeds_stochastic_public_scripts_and_roles(
    tmp_path,
):
    config = load_pilot_config(CONFIG)
    commands = evaluation_commands(
        config, checkpoint=tmp_path / "final.pt", output=tmp_path, final=True
    )
    assert len(commands) == 12
    assert len({command[command.index("--seed") + 1] for command in commands}) == 12
    for command in commands:
        assert "--stochastic" in command
        assert int(command[command.index("--seed") + 1]) >= config.evaluation_seed
        assert command[command.index("--candidate-sampling-decks-path") + 1] in {
            config.acceptance_decks_path,
            config.deployment_decks_path,
        }
        assert command[command.index("--opponent") + 1] == "public-script"
    assert {command[command.index("--level-mode") + 1] for command in commands} == {
        "nominal",
        "mixed",
    }


def test_success_string_is_not_an_admission_receipt(tmp_path):
    import json

    from clasher.rl.council_pilot import file_sha256, require_pilot_admission

    config = load_pilot_config(CONFIG)
    pins = tmp_path / "source.json"
    source = Path(config.source_root) / "src/clasher/battle.py"
    pins.write_text(json.dumps({str(source): file_sha256(source)}))
    config = config.model_copy(
        update={
            "source_pins_path": str(pins),
            "admission_ledger_path": str(tmp_path / "readiness.sqlite"),
        }
    )
    receipt = tmp_path / "admitted.json"
    receipt.write_text('{"status":"passed","public_contract_version":4}')
    with pytest.raises(ValueError):
        require_pilot_admission(config, receipt)
    assert not Path(config.admission_ledger_path).exists()


def test_actual_council_workers_collect_only_learner_seats(tmp_path):
    import json

    import torch

    from clasher.rl.council_opponents import (
        CouncilOpponentPool,
        OpponentCheckpoint,
        policy_contract_sha256,
    )
    from clasher.rl.council_pilot import file_sha256
    from clasher.rl.model import ClasherPolicy, PolicyConfig
    from clasher.rl.parallel_rollout import (
        ActorWorkerConfig,
        OpponentSpec,
        ParallelRolloutCollector,
    )
    from clasher.rl.public_scripted_opponent import SUPPORTED_CARDS

    torch.set_num_threads(1)
    config = load_pilot_config(CONFIG)
    builder = StructuredObservationBuilder(
        card_vocab=sorted(SUPPORTED_CARDS),
        max_entities=32,
        card_semantics_version=4,
        public_history_slots=4,
        public_seen_card_slots=8,
        public_entity_levels=True,
        public_hand_levels=True,
        canonical_lane_globals=True,
    )
    model_config = PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=32,
        public_contract_version=4,
        public_token_names=builder.token_names,
        public_observation_confidence=True,
        card_semantics_version=4,
        canonical_lane_globals=True,
        public_history_slots=4,
        public_seen_card_slots=8,
        d_model=32,
        num_heads=4,
        actor_layers=1,
        critic_layers=1,
        memory_size=48,
    )
    model = ClasherPolicy(model_config, builder.card_stat_features).eval()
    checkpoint = tmp_path / "initial.pt"
    data_sha = file_sha256(builder.loader.data_file)
    torch.save(
        {
            "format_version": 2,
            "model_config": model_config.to_dict(),
            "model_state_dict": model.state_dict(),
            "token_names": builder.token_names,
            "gamedata_sha256": data_sha,
        },
        checkpoint,
    )
    pool = CouncilOpponentPool(
        generation=0,
        phase="initial",
        gamedata_sha256=data_sha,
        policy_contract_sha256=policy_contract_sha256(model_config),
        initial=(
            OpponentCheckpoint(path=str(checkpoint), sha256=file_sha256(checkpoint)),
        ),
    )
    pool_path = tmp_path / "pool.json"
    pool_path.write_text(pool.model_dump_json())
    worker = ActorWorkerConfig(
        decks_path=config.training_decks_path,
        token_names=builder.token_names,
        model_config=model_config.to_dict(),
        decision_interval=5,
        max_ticks=100,
        mirror_match=False,
        opponent_mode="strategy",
        opponent_pool=(OpponentSpec(kind="strategy", strategy="balanced"),),
        engine_fast_path="off",
        quiet_engine=True,
        base_seed=2901,
        torch_threads=1,
        council_opponent_pool=str(pool_path),
    )
    with ParallelRolloutCollector(
        num_workers=2, num_envs=4, config=worker
    ) as collector:
        batch = collector.collect(
            model=model,
            rollout_steps=2,
            policy_version=0,
            learner_decisions=0,
            timeout=30,
        )
    assert batch.actions.shape == (4, 2)
    assert (
        batch.transitions == 8
    )  # Opponent decisions never count as learner experience.
    assignments = []
    for path in tmp_path.glob("worker-*-assignments.jsonl"):
        assignments.extend(json.loads(line) for line in path.read_text().splitlines())
    assert len(assignments) == 4
    assert {record["kind"] for record in assignments} <= {"initial", "script"}
    assert all(record["learner_decisions_at_assignment"] == 0 for record in assignments)


def test_budget_counts_only_allocated_cores_persists_and_locks(tmp_path):
    import json
    import os

    from clasher.rl.council_budget import LocalPilotBudget, budget_snapshot

    with LocalPilotBudget(tmp_path, config_sha256="a" * 64) as budget:
        with (
            pytest.raises(RuntimeError, match="another coordinator"),
            LocalPilotBudget(tmp_path, config_sha256="a" * 64),
        ):
            pass
        with (tmp_path / "child.log").open("w") as log:
            budget.run(
                [sys.executable, "-B", "-c", "pass"],
                cwd=tmp_path,
                env=os.environ.copy(),
                log=log,
                cpu_cores=2,
            )
    record = json.loads((tmp_path / "resource-budget.json").read_text())
    assert record["jobs"][0]["status"] == "completed"
    assert record["accelerator_hours_used"] == 0
    assert record["cpu_core_hours_used"] == pytest.approx(
        record["jobs"][0]["elapsed_seconds"] * 2 / 3600
    )
    with LocalPilotBudget(tmp_path, config_sha256="a" * 64):
        snapshot = budget_snapshot(tmp_path / "resource-budget.json")
        assert 0 < snapshot["cpu_core_hours_remaining"] < 4608
        assert snapshot["active_job"] is None


def test_budget_timeout_stops_owned_child_and_retains_usage(tmp_path):
    import json
    import os

    from clasher.rl.council_budget import LocalPilotBudget, PilotBudgetExceeded

    with (
        LocalPilotBudget(
            tmp_path, config_sha256="b" * 64, cpu_core_hour_ceiling=0.00001
        ) as budget,
        (tmp_path / "child.log").open("w") as log,
        pytest.raises(PilotBudgetExceeded, match="ceiling"),
    ):
        budget.run(
            [sys.executable, "-B", "-c", "import time; time.sleep(30)"],
            cwd=tmp_path,
            env=os.environ.copy(),
            log=log,
            cpu_cores=1,
        )
    record = json.loads((tmp_path / "resource-budget.json").read_text())
    assert record["active"] is None and record["jobs"][0]["status"] == "compute-ceiling"
    assert record["cpu_core_hours_used"] >= 0.00001


def test_republishing_retained_initial_history_cannot_roll_back_generation(tmp_path):
    from clasher.rl.council_opponents import CouncilOpponentPool, OpponentCheckpoint
    from clasher.rl.council_pilot import file_sha256, retain_league_checkpoint

    checkpoint = tmp_path / "checkpoint.pt"
    checkpoint.write_bytes(b"owned synthetic checkpoint")
    entry = OpponentCheckpoint(path=str(checkpoint), sha256=file_sha256(checkpoint))
    pool = CouncilOpponentPool(
        generation=2_000_000,
        phase="league",
        gamedata_sha256="a" * 64,
        policy_contract_sha256="b" * 64,
        initial=(entry,),
        historical=(entry,),
    )
    path = tmp_path / "pool.json"
    path.write_text(pool.model_dump_json())
    before = path.read_bytes()
    retain_league_checkpoint(path, checkpoint, 1_000_000)
    assert path.read_bytes() == before
    different = tmp_path / "other.pt"
    different.write_bytes(b"new synthetic checkpoint")
    with pytest.raises(ValueError, match="older"):
        retain_league_checkpoint(path, different, 1_000_000)


def test_phase_admission_slots_do_not_change_recipe_when_receipts_arrive(tmp_path):
    from clasher.rl.council_pilot import admission_path_for_phase

    config = load_pilot_config(CONFIG).model_copy(
        update={
            "nominal_admission_path": str(tmp_path / "nominal.json"),
            "mixed_level_admission_path": str(tmp_path / "mixed.json"),
        }
    )
    before = config.model_dump_json()
    assert admission_path_for_phase(config, "smoke") == tmp_path / "nominal.json"
    assert admission_path_for_phase(config, "nominal") == tmp_path / "nominal.json"
    assert admission_path_for_phase(config, "mixed-league") == tmp_path / "mixed.json"
    # File arrival is not authority; the separate ledger verifier decides that.
    (tmp_path / "nominal.json").write_text("synthetic non-admission fixture")
    (tmp_path / "mixed.json").write_text("synthetic non-admission fixture")
    assert config.model_dump_json() == before


def test_diagnostic_evaluation_never_replays_final_matchup_seeds(tmp_path):
    config = load_pilot_config(CONFIG)

    def matchup_seeds(final):
        seeds = set()
        for command in evaluation_commands(
            config, checkpoint=tmp_path / "c.pt", output=tmp_path, final=final
        ):
            seed = int(command[command.index("--seed") + 1])
            games = int(command[command.index("--games") + 1])
            seeds |= {seed + 1009 * matchup for matchup in range(games // 2)}
        return seeds

    assert not matchup_seeds(True) & matchup_seeds(False)


# --- v7r2 recipe fix (pilot/diagnosis-1M) --------------------------------------

FACTORIZED = {
    "entropy_coef": 0.0,
    "action_type_entropy_coef": 0.0,
    "location_entropy_coef": 0.0,
    "conditional_slot_entropy_coef": 0.003,
}


def _v7r2_config(**extra):
    base = load_pilot_config(CONFIG)
    return CouncilPilotConfig.model_validate(
        base.model_dump() | FACTORIZED | {"initial_opponent_policies": ("scripted",)} | extra
    )


def test_entropy_recipes_are_declared_and_reach_the_trainer(monkeypatch, tmp_path):
    from clasher.rl.council_pilot import entropy_recipe
    from clasher.rl.train_recurrent import entropy_recipe_record

    base = load_pilot_config(CONFIG)
    assert entropy_recipe(base) == "joint-v1"
    config = _v7r2_config()
    assert entropy_recipe(config) == "factorized-v2"
    for bad in ({"conditional_slot_entropy_coef": 0.01}, {"location_entropy_coef": None},
                {"entropy_coef": 0.01}):
        with pytest.raises(ValueError, match="entropy recipe"):
            _v7r2_config(**bad)
    command = training_command(
        config, config_path=CONFIG, admission=tmp_path / "receipt.json",
        seed=2901, arm="scripted", phase="nominal", pool_path=tmp_path / "pool.json",
        initialization=tmp_path / "initial.pt",
    )
    monkeypatch.setattr(sys, "argv", ["trainer", *command[4:]])
    args = parse_args()
    assert (args.entropy_coef, args.action_type_entropy_coef, args.location_entropy_coef,
            args.conditional_slot_entropy_coef) == (0.0, 0.0, 0.0, 0.003)
    record = entropy_recipe_record(args)
    # ppo_update uses the joint term only while both factor overrides are unset.
    assert record["joint_entropy_term_applies"] is False
    assert record["effective_type_coef"] == 0.0 and record["effective_location_coef"] == 0.0
    assert entropy_recipe(args) == "factorized-v2"
    # The joint-v1 command keeps the trainer defaults (no factor overrides).
    joint = training_command(
        base, config_path=CONFIG, admission=tmp_path / "receipt.json", seed=2901,
        arm="scripted", phase="nominal", pool_path=tmp_path / "pool.json",
        initialization=tmp_path / "initial.pt",
    )
    assert "--action-type-entropy-coef" not in joint and "--location-entropy-coef" not in joint
    monkeypatch.setattr(sys, "argv", ["trainer", *joint[4:]])
    assert entropy_recipe_record(parse_args())["joint_entropy_term_applies"] is True


def test_trainer_args_must_carry_the_config_entropy_recipe(monkeypatch, tmp_path):
    config = _v7r2_config()
    monkeypatch.setenv("CLASHER_ROOT", str(Path(config.gamedata_path).parent))
    builder = StructuredObservationBuilder(
        decks_path=config.training_decks_path, max_entities=128, card_semantics_version=4,
        public_history_slots=4, public_seen_card_slots=8, public_entity_levels=True,
        public_hand_levels=True, canonical_lane_globals=True,
    )
    command = training_command(
        config, config_path=CONFIG, admission=tmp_path / "receipt.json", seed=2901,
        arm="scripted", phase="nominal", pool_path=tmp_path / "pool.json",
        initialization=tmp_path / "initial.pt",
    )
    monkeypatch.setattr(sys, "argv", ["trainer", *command[4:]])
    args = parse_args()
    model_config = build_council_model_config(builder)
    validate_council_trainer_args(config, args, model_config, builder)
    for name, bad in (("location_entropy_coef", None), ("entropy_coef", 0.01),
                      ("conditional_slot_entropy_coef", 0.0)):
        original = getattr(args, name)
        setattr(args, name, bad)
        with pytest.raises(ValueError, match=name):
            validate_council_trainer_args(config, args, model_config, builder)
        setattr(args, name, original)


def test_random_control_leaves_the_scripted_pool_but_stays_for_scratch(tmp_path):
    from clasher.rl.council_pilot import opponent_initialization_paths

    scripted, scratch = tmp_path / "scripted.pt", tmp_path / "scripted-random-control.pt"
    base = load_pilot_config(CONFIG)
    config = _v7r2_config()
    for arm in ("scripted", "scratch"):
        assert opponent_initialization_paths(
            base, arm=arm, scripted=scripted, scratch=scratch) == (scripted, scratch)
    assert opponent_initialization_paths(
        config, arm="scripted", scripted=scripted, scratch=scratch) == (scripted,)
    # validate_council_initial_policy requires the arm's initializer in the pool.
    assert opponent_initialization_paths(
        config, arm="scratch", scripted=scripted, scratch=scratch) == (scripted, scratch)
    for bad in (("random_control",), ("scripted", "scripted"), ()):
        with pytest.raises(ValueError):
            _v7r2_config(initial_opponent_policies=bad)


def test_rebind_republishes_identical_weights_under_a_new_pilot(tmp_path, monkeypatch):
    import hashlib
    import json
    import os
    import time

    import torch

    from clasher.rl import council_pilot
    from clasher.rl.council_pilot import (
        rebind_warmstart_initialization,
        state_dict_sha256,
    )

    def sha(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    new_output = tmp_path / "new-runs"
    pins = tmp_path / "pins-v2.json"
    pins.write_text('{"v": 2}\n')
    admission = tmp_path / "admission.json"
    admission.write_text("{}\n")
    text = CONFIG.read_text()
    base = load_pilot_config(CONFIG)
    text = text.replace(f'output_dir = "{base.output_dir}"', f'output_dir = "{new_output}"')
    text = text.replace(f'source_pins_path = "{base.source_pins_path}"', f'source_pins_path = "{pins}"')
    config_path = tmp_path / "pilot.toml"
    config_path.write_text(text)
    config = load_pilot_config(config_path)
    source = tmp_path / "old-runs" / "seed-2901" / "initialization"
    demos = source / "scripted-demonstrations"
    demos.mkdir(parents=True)
    plan = {"schema": "clasher.council-script-warmstart.v1", "seed": 2901}
    (demos / "plan.json").write_text(json.dumps(plan))
    common = {
        "gamedata_sha256": config.gamedata_sha256, "strategy_sha256": config.strategy_sha256,
        "training_decks_sha256": config.training_decks_sha256, "admission_sha256": sha(admission),
        "warmstart_plan_sha256": sha(demos / "plan.json"), "source_pins_sha256": "1" * 64,
        "resource_budget": {"ledger_path": str(tmp_path / "old-runs/resource-budget.json")},
        "format_version": 2, "args": {"initialization": "x"},
    }
    torch.manual_seed(3)
    for name, trained in (("scripted.pt", True), ("scripted-random-control.pt", False)):
        torch.save(common | {"imitation": {"trained": trained, "metrics": {"nan": float("nan")}},
                             "model_state_dict": {"w": torch.randn(3, 2)},
                             "optimizer_state_dict": {"state": {0: {"m": torch.ones(2)}}}},
                   source / name)
    receipt = {"schema": "clasher.council-script-warmstart-result.v1", "plan": plan,
               "checkpoint": str(source / "scripted.pt"),
               "checkpoint_sha256": sha(source / "scripted.pt"),
               "control_checkpoint": str(source / "scripted-random-control.pt"),
               "control_checkpoint_sha256": sha(source / "scripted-random-control.pt"),
               "corpus": {"samples": 1}, "fit": {"epochs": 1}}
    (demos / "result.json").write_text(json.dumps(receipt))
    new_output.mkdir()
    ledger = new_output / "resource-budget.json"
    ledger.write_text(json.dumps({
        "schema": "clasher.local-pilot-budget.v1", "config_sha256": sha(config_path),
        "cpu_core_hour_ceiling": 4608.0, "accelerator_hour_ceiling": 72.0,
        "cpu_core_hours_used": 0.0, "accelerator_hours_used": 0.0,
        "active": {"argv": ["rebind"], "started_at": time.time(), "cpu_cores": 1,
                   "accelerator": False, "pid": os.getpid()},
        "jobs": []}))
    admitted = []
    monkeypatch.setattr(council_pilot, "require_pilot_admission",
                        lambda *args, **kwargs: admitted.append(args))
    result = rebind_warmstart_initialization(
        config_path=config_path, admission_path=admission, seed=2901, source_dir=source)
    assert admitted, "the rebind child must pass the full admission check"
    target = new_output / "seed-2901" / "initialization"
    on_disk = json.loads((target / "scripted-demonstrations" / "result.json").read_text())
    assert on_disk == result and not result["fitted"] and not result["demonstrations_collected"]
    for name in ("scripted.pt", "scripted-random-control.pt"):
        old = torch.load(source / name, weights_only=False)
        new = torch.load(target / name, weights_only=False)
        assert state_dict_sha256(new["model_state_dict"]) == state_dict_sha256(old["model_state_dict"])
        assert new["source_pins_sha256"] == sha(pins)
        assert new["resource_budget"]["ledger_path"] == str(ledger.resolve())
        assert new["resource_budget"]["active_job"]["pid"] == os.getpid()
        assert new["warmstart_rebind"]["source_checkpoint_sha256"] == sha(source / name)
        assert set(new) == set(old) | {"warmstart_rebind"}
        assert result["initializers"][name]["sha256"] == sha(target / name)
    assert result["checkpoint_sha256"] == sha(target / "scripted.pt")
    # Never overwrites, and refuses a source that no longer matches its receipt.
    with pytest.raises(FileExistsError):
        rebind_warmstart_initialization(
            config_path=config_path, admission_path=admission, seed=2901, source_dir=source)
    (target / "scripted.pt").unlink()
    (target / "scripted-random-control.pt").unlink()
    (target / "scripted-demonstrations" / "result.json").unlink()
    with (source / "scripted.pt").open("ab") as stream:
        stream.write(b"tamper")
    with pytest.raises(ValueError, match="differs from its warm-start receipt"):
        rebind_warmstart_initialization(
            config_path=config_path, admission_path=admission, seed=2901, source_dir=source)
