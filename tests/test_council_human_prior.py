"""Recipe v7r4h: PPO from the declared human-imitation checkpoint (human prior).

Config, argv, trainer-argument and validator checks only: no gameplay fitting,
tiny synthetic checkpoints written to tmp_path.
"""

import copy
import hashlib
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from clasher.rl.council_pilot import (
    HUMAN_PRIOR_ADMISSION_STATUS,
    CouncilPilotConfig,
    anchor_checkpoint_path,
    build_council_model_config,
    critic_warmup_updates_for_arm,
    evaluation_commands,
    is_continuation,
    is_human_prior,
    load_pilot_config,
    opponent_initialization_paths_for_seed,
    training_command,
    training_recipe,
    validate_council_human_prior,
    validate_council_trainer_args,
)
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import parse_args

CONFIG = Path("configs/council-pilot-local.toml")
RECON = "5158a4ac7d003795b9557d61c590d0dc386587d4dfb391b8f75dd327711f950b"
V7R4H = {
    "entropy_coef": 0.0,
    "action_type_entropy_coef": 0.0,
    "location_entropy_coef": 0.0,
    "conditional_slot_entropy_coef": 0.003,
    "initial_opponent_policies": ("scripted",),
    "gae_lambda": 0.95,
    "critic_warmup_updates": 60,
    "anchor_policy_kl_coef": 0.05,
    "phase_order": ("nominal", "nominal-league"),
}
SEEDS = (2901, 2902, 2903)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _human(tmp_path, **extra):
    fields = V7R4H | {
        "human_prior_checkpoint_path": str(tmp_path / "human-bc-natural-seed2903.pt"),
        "human_prior_checkpoint_sha256": "a" * 64,
        "human_prior_recon_manifest_sha256": RECON,
    }
    base = load_pilot_config(CONFIG)
    return CouncilPilotConfig.model_validate(base.model_dump() | fields | extra)


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
        initialization=init or Path(config.human_prior_checkpoint_path),
    )


def _value(command, flag):
    return command[command.index(flag) + 1]


def _parsed(monkeypatch, command):
    monkeypatch.setattr(sys, "argv", ["trainer", *command[4:]])
    return parse_args()


# ---------------------------------------------------------------- config


def test_human_prior_config_declares_the_fixed_recipe(tmp_path):
    config = _human(tmp_path)
    recipe = training_recipe(config)
    assert recipe["anchor_policy_kl_coef"] == 0.05
    assert recipe["critic_warmup_updates"] == 60 and recipe["gae_lambda"] == 0.95
    assert recipe["level_randomization_after"] is None and recipe["continuation"] is None
    assert recipe["human_prior"] == {
        "arm_slot": "scripted",
        "checkpoint": config.human_prior_checkpoint_path,
        "checkpoint_sha256": "a" * 64,
        "recon_manifest_sha256": RECON,
        "initialization": "human_replay_imitation",
        "anchor": "human-prior checkpoint",
        "admission_status": HUMAN_PRIOR_ADMISSION_STATUS,
    }
    assert "not a Tier A admitted" in HUMAN_PRIOR_ADMISSION_STATUS
    assert all(is_human_prior(config, seed, "scripted") for seed in SEEDS)
    assert not any(is_human_prior(config, seed, "scratch") for seed in SEEDS)
    assert not any(is_continuation(config, s, a) for s in SEEDS for a in config.arms)
    assert critic_warmup_updates_for_arm(config, "scripted") == 60
    assert critic_warmup_updates_for_arm(config, "scratch") == 0


@pytest.mark.parametrize(
    "change,match",
    [
        ({"human_prior_recon_manifest_sha256": None}, "together"),
        ({"human_prior_checkpoint_sha256": None}, "together"),
        ({"critic_warmup_updates": 20}, "60-update critic warm-up"),
        ({"anchor_policy_kl_coef": 0.01}, "0.05 policy-KL anchor"),
        ({"anchor_policy_kl_coef": 0.0}, "0.05 policy-KL anchor"),
        ({"anchor_policy_kl_coef": 0.1}, "anchor_policy_kl_coef"),
        ({"initial_opponent_policies": ("scripted", "random_control")}, "no random control"),
        ({"human_prior_checkpoint_path": "relative/human.pt"}, "absolute"),
        ({"human_prior_checkpoint_sha256": "xyz"}, "SHA-256"),
    ],
)
def test_human_prior_config_refuses_other_recipes(tmp_path, change, match):
    with pytest.raises(ValueError, match=match):
        _human(tmp_path, **change)


def test_human_prior_is_exclusive_and_its_anchor_coefficient_is_reserved(tmp_path):
    with pytest.raises(ValueError, match="mutually exclusive"):
        _human(
            tmp_path,
            continuation_seed=2903,
            continuation_checkpoint_path=str(tmp_path / "c.pt"),
            continuation_checkpoint_sha256="0" * 64,
            continuation_source_config_sha256="1" * 64,
            continuation_source_decisions=1_000_000,
        )
    base = load_pilot_config(CONFIG).model_dump()
    with pytest.raises(ValueError, match="reserved for the human prior"):
        CouncilPilotConfig.model_validate(base | V7R4H)
    # The v7r3 value stays available without a human prior.
    v7r3 = CouncilPilotConfig.model_validate(
        base | V7R4H | {"anchor_policy_kl_coef": 0.01, "gae_lambda": 0.99}
    )
    assert training_recipe(v7r3)["human_prior"] is None


# ---------------------------------------------------------------- argv and pool


def test_human_prior_argv_anchor_warmup_and_pool(tmp_path):
    config = _human(tmp_path)
    human = Path(config.human_prior_checkpoint_path)
    for seed in SEEDS:
        command = _command(config, tmp_path, seed=seed)
        assert _value(command, "--council-arm") == "scripted"
        assert Path(_value(command, "--initialize-policy-from")) == human
        assert Path(_value(command, "--anchor-checkpoint")) == human
        assert anchor_checkpoint_path(config, seed, "scripted") == human
        assert _value(command, "--anchor-policy-kl-coef") == "0.05"
        assert _value(command, "--critic-warmup-updates") == "60"
        assert _value(command, "--gae-lambda") == "0.95"
        assert _value(command, "--target-kl") == "0.02"
        assert _value(command, "--learning-rate") == "0.0001"
        assert "--level-randomization-after" not in command
        warm, control = tmp_path / f"s{seed}" / "scripted.pt", tmp_path / f"s{seed}" / "c.pt"
        assert opponent_initialization_paths_for_seed(
            config, seed=seed, arm="scripted", scripted=warm, scratch=control
        ) == (warm, human)
    league = _command(config, tmp_path, phase="nominal-league")
    assert _value(league, "--total-decisions") == "5000000"
    milestones = {league[i + 1] for i, a in enumerate(league) if a == "--checkpoint-decisions"}
    assert milestones == {"1000000", "2000000", "3000000", "4000000", "5000000"}
    scratch = _command(config, tmp_path, arm="scratch", init=tmp_path / "c.pt")
    assert "--anchor-checkpoint" not in scratch and _value(scratch, "--critic-warmup-updates") == "0"


def test_trainer_args_enforce_the_human_prior_anchor_and_initializer(monkeypatch, tmp_path):
    config = _human(tmp_path)
    monkeypatch.setenv("CLASHER_ROOT", str(Path(config.gamedata_path).parent))
    builder = _builder(config)
    model_config = build_council_model_config(builder)
    for seed in SEEDS:
        validate_council_trainer_args(
            config, _parsed(monkeypatch, _command(config, tmp_path, seed=seed)), model_config, builder
        )
    # A league resume carries no initializer and is accepted.
    resume = _command(config, tmp_path, phase="nominal-league")
    resume[resume.index("--initialize-policy-from") : resume.index("--initialize-policy-from") + 2] = [
        "--resume-from",
        str(tmp_path / "policy_v2_update_000123.pt"),
    ]
    validate_council_trainer_args(config, _parsed(monkeypatch, resume), model_config, builder)
    args = _parsed(monkeypatch, _command(config, tmp_path))
    warm_start = Path(config.output_dir) / "seed-2901" / "initialization" / "scripted.pt"
    for name, bad, match in (
        ("anchor_checkpoint", str(warm_start), "declared human-prior checkpoint"),
        ("anchor_checkpoint", None, "declared human-prior checkpoint"),
        ("anchor_policy_kl_coef", 0.01, "anchor_policy_kl_coef"),
        ("initialize_policy_from", str(warm_start), "start from its declared checkpoint"),
        ("critic_warmup_updates", 0, "critic warm-up"),
        ("critic_warmup_updates", 20, "critic warm-up"),
        ("gae_lambda", 0.99, "gae_lambda"),
    ):
        trial = copy.copy(args)
        setattr(trial, name, bad)
        with pytest.raises(ValueError, match=match):
            validate_council_trainer_args(config, trial, model_config, builder)


# ---------------------------------------------------------------- validator


@pytest.fixture
def human_case(monkeypatch, tmp_path):
    from clasher.rl.council_opponents import (
        CouncilOpponentPool,
        OpponentCheckpoint,
        policy_contract_sha256,
    )
    from clasher.rl.model import ClasherPolicy

    probe = _human(tmp_path)
    monkeypatch.setenv("CLASHER_ROOT", str(Path(probe.gamedata_path).parent))
    builder = _builder(probe)
    model_config = build_council_model_config(builder)
    torch.manual_seed(2903)
    model = ClasherPolicy(model_config, builder.card_stat_features)
    payload = {
        "format_version": 2,
        "model_type": "entity_spatial_recurrent",
        "model_config": model_config.to_dict(),
        "token_names": builder.token_names,
        "model_state_dict": model.state_dict(),
        "args": {"initialization": "human_replay_imitation", "seed": 2903},
        "imitation": {"trained": True, "initial_checkpoint": None},
        "update": 0,
        "total_transitions": 0,
        "gamedata_sha256": probe.gamedata_sha256,
        "training_decks_sha256": probe.training_decks_sha256,
        "human_replay_recon_manifest_sha256": RECON,
        "provenance": "human-prior research artifact; not a Tier A admitted pilot arm",
    }
    checkpoint = Path(probe.human_prior_checkpoint_path)
    torch.save(payload, checkpoint)
    config = _human(tmp_path, human_prior_checkpoint_sha256=_sha(checkpoint))
    warm = tmp_path / "scripted.pt"
    warm.write_bytes(b"warm start stand-in")
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

    publish([warm, checkpoint])
    args = SimpleNamespace(
        seed=2901,
        council_arm="scripted",
        council_admission=tmp_path / "receipt.json",
        council_opponent_pool=pool_path,
        preflight_no_update=False,
    )

    def check(cfg=config, data=payload, path=checkpoint, **overrides):
        return validate_council_human_prior(
            cfg,
            data,
            initialization_path=path,
            args=SimpleNamespace(**(vars(args) | overrides)),
            builder=builder,
        )

    return SimpleNamespace(
        config=config, payload=payload, checkpoint=checkpoint, check=check,
        publish=publish, warm=warm, tmp_path=tmp_path,
    )


def test_human_prior_validator_accepts_the_declared_checkpoint(human_case):
    from clasher.rl.council_pilot import state_dict_sha256

    for seed in SEEDS:
        record = human_case.check(seed=seed)
        assert record["sha256"] == human_case.config.human_prior_checkpoint_sha256
        assert record["state_sha256"] == state_dict_sha256(human_case.payload["model_state_dict"])
        assert record["initialization"] == "human_prior" and record["arm"] == "scripted"
        assert record["admission_status"] == HUMAN_PRIOR_ADMISSION_STATUS
        assert "not a Tier A admitted" in record["provenance"]
        assert record["weights_only"] and record["optimizer_reset"] and record["update_reset"]
        assert record["checkpoint_optimizer_state_present"] is False


@pytest.mark.parametrize(
    "change,match",
    [
        ({"args": {"initialization": "public_script_imitation"}}, "human-replay imitation"),
        ({"provenance": None}, "provenance"),
        ({"provenance": "admitted"}, "provenance"),
        ({"gamedata_sha256": "4" * 64}, "ruleset"),
        ({"training_decks_sha256": "5" * 64}, "training-deck"),
        ({"human_replay_recon_manifest_sha256": "6" * 64}, "reconstruction manifest"),
        ({"imitation": {"trained": False}}, "trained imitation"),
        ({"format_version": 1}, "V2"),
        ({"model_type": "other"}, "model type"),
        ({"token_names": ["<pad>"]}, "vocabulary"),
        ({"model_state_dict": {}}, "model state"),
    ],
)
def test_human_prior_validator_refuses_payload_changes(human_case, change, match):
    with pytest.raises((ValueError, TypeError), match=match):
        human_case.check(data=human_case.payload | change)


def test_human_prior_validator_refuses_other_files_runs_and_pools(human_case):
    with pytest.raises(ValueError, match="not the declared human-prior arm"):
        human_case.check(council_arm="scratch")
    with pytest.raises(ValueError, match="not the declared human-prior arm"):
        human_case.check(seed=1234)
    with pytest.raises(ValueError, match="path differs"):
        human_case.check(path=human_case.warm)
    with pytest.raises(ValueError, match="bytes differ"):
        human_case.check(cfg=_human(human_case.tmp_path, human_prior_checkpoint_sha256="7" * 64))
    bad_config = dict(human_case.payload["model_config"]) | {"d_model": 64}
    with pytest.raises(ValueError, match="council actor contract"):
        human_case.check(data=human_case.payload | {"model_config": bad_config})
    human_case.publish([human_case.warm])
    with pytest.raises(ValueError, match="published initial opponent"):
        human_case.check()


def test_trainer_selects_the_human_prior_validator_and_keeps_its_record():
    source = Path("src/clasher/rl/train_recurrent.py").read_text()
    assert "else validate_council_human_prior\n                if is_human_prior(" in source
    assert "resumed human-prior run lost its declared initialization record" in source


# ---------------------------------------------------------------- runner and kit


def test_runner_evaluates_the_human_start_and_every_league_milestone(tmp_path):
    config = _human(tmp_path)
    arm_dir = tmp_path / "run"

    def outputs(checkpoint, output):
        return {
            c[c.index("--json-out") + 1]
            for c in evaluation_commands(config, checkpoint=checkpoint, output=output, final=False)
        }

    dirs = {
        m: arm_dir / "milestone-evaluation" / f"decisions_{m:09d}"
        for m in (2_000_000, 3_000_000, 4_000_000)
    }
    every = [outputs(arm_dir / f"policy_decisions_{m:09d}.pt", d) for m, d in dirs.items()]
    every.append(outputs(arm_dir / "policy_decisions_005000000.pt", arm_dir / "league-evaluation"))
    every.append(outputs(Path(config.human_prior_checkpoint_path), arm_dir / "diagnostic-evaluation" / "human-prior-start"))
    assert all(len(cells) == 6 for cells in every)  # holdout + hog26, nominal, 3 styles
    assert len(set().union(*every)) == 6 * len(every)
    runner = Path("scripts/run_council_pilot.py").read_text()
    assert 'candidate_dir = eval_dir / "human-prior-start"' in runner
    assert '/ "milestone-evaluation"' in runner and "(2_000_000, 3_000_000, 4_000_000)" in runner
    assert "seed=binding_seed" in runner and '"admission_status"' in runner
    preflight = Path("scripts/preflight_council_pilot.py").read_text()
    assert "declared = Path(config.human_prior_checkpoint_path)" in preflight


KIT = Path("reports/strategy_council_20260928/pilot/v7r4h-launch")


@pytest.mark.skipif(not (KIT / "launch.sh").exists(), reason="v7r4h kit not built")
@pytest.mark.parametrize("seed", SEEDS)
def test_kit_launcher_never_launches_the_scratch_arm(seed):
    result = subprocess.run(
        ["bash", str(KIT / "launch.sh"), str(seed), "scratch", "--dry-run"],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 2
    assert "REFUSED" in result.stderr and "scratch" in result.stderr
