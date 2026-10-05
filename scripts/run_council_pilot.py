#!/usr/bin/env python3
"""Prepare or execute the locally admitted, source-pinned council pilot."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--admission", type=Path)
    parser.add_argument(
        "--phase",
        choices=("smoke", "nominal", "mixed-league", "nominal-league"),
        default="nominal",
    )
    parser.add_argument("--seed", type=int)
    parser.add_argument("--arm", choices=("scripted", "scratch"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--freeze-source", action="store_true")
    args = parser.parse_args()
    from clasher.rl.council_pilot import (
        admission_path_for_phase,
        critic_warmup_updates_for_arm,
        evaluation_commands,
        file_sha256,
        load_pilot_config,
        entropy_recipe,
        is_continuation,
        is_human_prior,
        load_source_pins,
        opponent_initialization_paths_for_seed,
        pilot_environment,
        publish_initial_pool,
        require_pilot_admission,
        training_command,
        training_recipe,
    )

    config = load_pilot_config(args.config)
    from clasher.rl.council_evaluation import (
        build_protocol,
        cell_for_command,
        freeze_protocol,
        load_protocol,
        record_completion,
        result_binding,
        validated_completion,
    )

    if args.freeze_source:
        freeze_protocol(config)
    league_phase = args.phase in ("mixed-league", "nominal-league")
    if league_phase and args.phase != config.phase_order[-1]:
        raise ValueError("league phase differs from the configured phase order")
    # The nominal league never randomizes levels, so its slot is the nominal
    # (Tier A) receipt; admission_path_for_phase only knows the mixed schedule.
    declared_admission = (
        Path(config.nominal_admission_path)
        if args.phase == "nominal-league"
        else admission_path_for_phase(config, args.phase)
    )
    if (
        args.admission is not None
        and args.admission.resolve() != declared_admission.resolve()
    ):
        raise ValueError("admission path differs from the declared phase slot")
    args.admission = declared_admission
    if args.freeze_source:
        if args.execute:
            raise ValueError("source freezing and gameplay execution must be separate")
        root = Path(config.source_root)
        paths = sorted((root / "src/clasher").rglob("*.py"))
        paths += [
            root / "scripts/run_council_pilot.py",
            root / "scripts/run_council_warmstart.py",
            root / "scripts/evaluate_council_pilot.py",
        ]
        destination = Path(config.source_pins_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise FileExistsError(
                "source freeze already exists; choose a new config revision"
            )
        destination.write_text(
            json.dumps({str(path): file_sha256(path) for path in paths}, indent=2)
            + "\n"
        )
    seeds = config.seeds if args.seed is None else (args.seed,)
    arms = config.arms if args.arm is None else (args.arm,)
    if not set(seeds).issubset(config.seeds) or not set(arms).issubset(config.arms):
        raise ValueError("undeclared arm/seed")
    plan = {
        "status": "requires-admission",
        "source_freeze_present": Path(config.source_pins_path).exists(),
        "strategy_sha256": config.strategy_sha256,
        "gamedata_sha256": config.gamedata_sha256,
        "phase": args.phase,
        "admission_path": str(args.admission),
        "runs": [
            {
                "seed": seed,
                "arm": arm,
                "total_pilot_decisions": config.decisions_per_seed,
            }
            for seed in seeds
            for arm in arms
        ],
        "local_batch": {
            "workers": config.actor_workers,
            "environments": config.num_envs,
            "chunk": 128,
            "retained_learner_decisions_per_full_batch": config.num_envs * 128,
            "sequence_minibatch": config.sequence_batch_size,
            "recurrent_reconstruction": "exact full episode prefix",
        },
        "critic_warmup_updates": {
            arm: critic_warmup_updates_for_arm(config, arm) for arm in config.arms
        },
        "target_kl": config.target_kl,
        "training_recipe": training_recipe(config),
        "promotion": "requires fixed paired evaluation plus Tier B; this runner never promotes automatically",
    }
    print(json.dumps(plan, indent=2), flush=True)
    if not args.execute:
        return
    levels = (10, 11, 12) if args.phase == "mixed-league" else (11,)
    evaluation_protocol = load_protocol(Path(config.evaluation_protocol_path))
    if evaluation_protocol != build_protocol(config):
        raise ValueError(
            "evaluation protocol differs from the prospective pilot configuration"
        )
    require_pilot_admission(config, args.admission, levels=levels)
    environment = pilot_environment(config)
    cwd = Path(config.gamedata_path).parent
    from clasher.rl.council_budget import LocalPilotBudget
    from clasher.rl.train_recurrent import find_latest_checkpoint

    with LocalPilotBudget(
        Path(config.output_dir),
        config_sha256=file_sha256(args.config),
        cpu_core_hour_ceiling=config.cpu_core_hour_ceiling,
        accelerator_hour_ceiling=config.accelerator_hour_ceiling,
    ) as budget:
        for seed in seeds:
            initialization_dir = (
                Path(config.output_dir) / f"seed-{seed}" / "initialization"
            )
            scripted = initialization_dir / "scripted.pt"
            scratch = initialization_dir / "scripted-random-control.pt"
            result_path = initialization_dir / "scripted-demonstrations" / "result.json"
            if result_path.exists():
                warmstart_result = json.loads(result_path.read_text())
                scratch = Path(warmstart_result["control_checkpoint"])
                if (
                    file_sha256(scripted) != warmstart_result["checkpoint_sha256"]
                    or file_sha256(scratch)
                    != warmstart_result["control_checkpoint_sha256"]
                ):
                    raise ValueError(
                        "warm-start initialization changed after its result receipt"
                    )
            if not scripted.exists() or not scratch.exists():
                initialization_dir.mkdir(parents=True, exist_ok=True)
                require_pilot_admission(config, args.admission, levels=(11,))
                command = [
                    str(Path(config.source_root) / ".venv/bin/python"),
                    "-B",
                    str(Path(config.source_root) / "scripts/run_council_warmstart.py"),
                    "--config",
                    str(args.config.resolve()),
                    "--admission",
                    str(args.admission.resolve()),
                    "--seed",
                    str(seed),
                    "--output",
                    str(scripted),
                    "--decisions",
                    str(config.warmstart_decisions),
                    "--device",
                    config.device,
                ]
                if (initialization_dir / "scripted-demonstrations").exists():
                    command.append("--resume")
                with (initialization_dir / "warmstart.log").open("a") as log:
                    budget.run(
                        command,
                        cwd=cwd,
                        env=environment,
                        log=log,
                        cpu_cores=config.torch_threads,
                        accelerator=config.device == "mps",
                    )
                warmstart_result = json.loads(result_path.read_text())
                scratch = Path(warmstart_result["control_checkpoint"])
            for arm in arms:
                require_pilot_admission(config, args.admission, levels=levels)
                directory = Path(config.output_dir) / f"seed-{seed}" / arm
                directory.mkdir(parents=True, exist_ok=True)
                resume = find_latest_checkpoint(directory)
                if (
                    league_phase
                    and not (directory / "policy_decisions_001000000.pt").exists()
                ):
                    raise ValueError(
                        "league phase requires the retained one-million-decision checkpoint"
                    )
                pool = directory / "opponents" / "pool.json"
                publish_initial_pool(
                    config,
                    pool_path=pool,
                    initialization_paths=opponent_initialization_paths_for_seed(
                        config, seed=seed, arm=arm, scripted=scripted, scratch=scratch
                    ),
                )
                if league_phase:
                    from clasher.rl.council_pilot import retain_league_checkpoint

                    retain_league_checkpoint(
                        pool, directory / "policy_decisions_001000000.pt", 1_000_000
                    )
                initialization = scripted if arm == "scripted" else scratch
                if is_continuation(config, seed, arm):
                    initialization = Path(config.continuation_checkpoint_path)
                    if file_sha256(initialization) != config.continuation_checkpoint_sha256:
                        raise ValueError("continuation checkpoint differs from its declaration")
                if is_human_prior(config, seed, arm):
                    initialization = Path(config.human_prior_checkpoint_path)
                    if file_sha256(initialization) != config.human_prior_checkpoint_sha256:
                        raise ValueError("human-prior checkpoint differs from its declaration")
                command = training_command(
                    config,
                    config_path=args.config,
                    admission=args.admission,
                    seed=seed,
                    arm=arm,
                    phase=args.phase,
                    pool_path=pool,
                    initialization=initialization,
                    resume=resume,
                )
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                launch = {
                    "config_sha256": file_sha256(args.config),
                    "admission_sha256": file_sha256(args.admission),
                    "source_pins": load_source_pins(config),
                    "seed": seed,
                    "arm": arm,
                    "phase": args.phase,
                    "initialization_sha256": file_sha256(initialization),
                    "critic_warmup_updates": critic_warmup_updates_for_arm(
                        config, arm
                    ),
                    "target_kl": config.target_kl,
                    "entropy_recipe": entropy_recipe(config),
                    "entropy_coefficients": {
                        "entropy_coef": config.entropy_coef,
                        "action_type_entropy_coef": config.action_type_entropy_coef,
                        "location_entropy_coef": config.location_entropy_coef,
                        "conditional_slot_entropy_coef": (
                            config.conditional_slot_entropy_coef
                        ),
                    },
                    "initial_opponent_policies": list(
                        config.initial_opponent_policies
                    ),
                    "training_recipe": training_recipe(config),
                    "initializer_kind": "continuation"
                    if is_continuation(config, seed, arm)
                    else "human_prior"
                    if is_human_prior(config, seed, arm)
                    else "warm_start"
                    if arm == "scripted"
                    else "random_control",
                    "admission_status": (
                        training_recipe(config)["human_prior"]["admission_status"]
                        if is_human_prior(config, seed, arm)
                        else None
                    ),
                    "pool_sha256": file_sha256(pool),
                    "argv": command,
                }
                (directory / f"launch-{stamp}.json").write_text(
                    json.dumps(launch, indent=2) + "\n"
                )
                with (directory / f"train-{stamp}.log").open("x") as log:
                    budget.run(
                        command,
                        cwd=cwd,
                        env=environment,
                        log=log,
                        cpu_cores=config.actor_workers * config.actor_threads
                        + config.torch_threads,
                        accelerator=config.device == "mps",
                    )
                if args.phase != "smoke":
                    final = args.phase == "mixed-league"
                    checkpoint = directory / (
                        "policy_decisions_001000000.pt"
                        if args.phase == "nominal"
                        else "policy_decisions_005000000.pt"
                    )
                    eval_dir = directory / (
                        "final-evaluation"
                        if final
                        else "league-evaluation"
                        if args.phase == "nominal-league"
                        else "diagnostic-evaluation"
                    )
                    eval_dir.mkdir(exist_ok=True)
                    # The nominal league reuses the diagnostic cells (development
                    # holdout and hog26, nominal levels) for its final checkpoint;
                    # the mixed-level final matrix needs the level admission.
                    candidates = (
                        (checkpoint,)
                        if args.phase == "nominal-league"
                        else (initialization, checkpoint)
                    )
                    # (candidate, output dir, policy role, final cells?)
                    plan_cells = []
                    for candidate in candidates:
                        # A continuation starts from an earlier pilot's milestone
                        # whose file name equals this run's own milestone
                        # (policy_decisions_001000000.pt), and evaluation outputs
                        # are named by checkpoint stem. Its cells go to their own
                        # directory so the two never share a completion record.
                        # The human prior's start cells likewise get their own.
                        candidate_dir = eval_dir
                        if candidate == initialization and is_continuation(
                            config, seed, arm
                        ):
                            candidate_dir = eval_dir / "continuation-start"
                            candidate_dir.mkdir(exist_ok=True)
                        if candidate == initialization and is_human_prior(
                            config, seed, arm
                        ):
                            candidate_dir = eval_dir / "human-prior-start"
                            candidate_dir.mkdir(exist_ok=True)
                        plan_cells.append(
                            (
                                candidate,
                                candidate_dir,
                                "initialization"
                                if candidate == initialization
                                else "candidate",
                                final,
                            )
                        )
                    if args.phase == "nominal-league":
                        # Retained league milestones 2M/3M/4M get the same
                        # diagnostic cells as 1M and 5M (development holdout +
                        # hog26, nominal, 32 games x 3 styles), each in its own
                        # directory, so a holdout drop during the league is seen.
                        for milestone in (2_000_000, 3_000_000, 4_000_000):
                            milestone_checkpoint = (
                                directory / f"policy_decisions_{milestone:09d}.pt"
                            )
                            if not milestone_checkpoint.exists():
                                raise ValueError(
                                    f"retained league milestone missing: {milestone_checkpoint}"
                                )
                            milestone_dir = (
                                directory
                                / "milestone-evaluation"
                                / f"decisions_{milestone:09d}"
                            )
                            milestone_dir.mkdir(parents=True, exist_ok=True)
                            plan_cells.append(
                                (milestone_checkpoint, milestone_dir, "candidate", False)
                            )
                    for candidate, candidate_dir, policy_role, cell_final in plan_cells:
                        # eval.py records the evaluated checkpoint's own training
                        # seed; the human prior was fitted once (seed 2903) and
                        # starts every seed's run, so its cells bind that seed.
                        binding_seed = seed
                        if candidate == initialization and is_human_prior(
                            config, seed, arm
                        ):
                            import torch

                            binding_seed = int(
                                torch.load(
                                    candidate, map_location="cpu", weights_only=False
                                )["args"]["seed"]
                            )
                        for eval_command in evaluation_commands(
                            config,
                            checkpoint=candidate,
                            output=candidate_dir,
                            final=cell_final,
                        ):
                            cell = cell_for_command(
                                evaluation_protocol, eval_command, final=cell_final
                            )
                            summary_path = Path(
                                eval_command[eval_command.index("--json-out") + 1]
                            )
                            games_path = Path(
                                eval_command[eval_command.index("--games-json-out") + 1]
                            )
                            binding = result_binding(
                                evaluation_protocol,
                                cell,
                                checkpoint=candidate,
                                seed=binding_seed,
                                arm=arm,
                                policy_role=policy_role,
                            )
                            if validated_completion(
                                evaluation_protocol,
                                cell,
                                summary_path=summary_path,
                                games_path=games_path,
                                binding=binding,
                            ):
                                continue
                            require_pilot_admission(
                                config, args.admission, levels=levels
                            )
                            budget.run(
                                eval_command,
                                cwd=cwd,
                                env=environment,
                                log=None,
                                cpu_cores=config.torch_threads,
                                accelerator=config.device == "mps",
                            )
                            record_completion(
                                evaluation_protocol,
                                cell,
                                summary_path=summary_path,
                                games_path=games_path,
                                binding=binding,
                            )
                    if final:
                        scorer = [
                            str(Path(config.source_root) / ".venv/bin/python"),
                            "-B",
                            str(
                                Path(config.source_root)
                                / "scripts/evaluate_council_pilot.py"
                            ),
                            "--protocol",
                            config.evaluation_protocol_path,
                            "--evaluation-dir",
                            str(eval_dir),
                            "--seed",
                            str(seed),
                            "--arm",
                            arm,
                            "--output",
                            str(directory / "strength-report.json"),
                        ]
                        budget.run(
                            scorer, cwd=cwd, env=environment, log=None, cpu_cores=1
                        )
        if args.phase == "mixed-league":
            for arm in arms:
                reports = [
                    Path(config.output_dir)
                    / f"seed-{seed}"
                    / arm
                    / "strength-report.json"
                    for seed in config.seeds
                ]
                if all(path.exists() for path in reports):
                    scorer = [
                        str(Path(config.source_root) / ".venv/bin/python"),
                        "-B",
                        str(
                            Path(config.source_root)
                            / "scripts/evaluate_council_pilot.py"
                        ),
                        "--protocol",
                        config.evaluation_protocol_path,
                        "--arm",
                        arm,
                        "--output",
                        str(Path(config.output_dir) / f"{arm}-recipe-strength.json"),
                    ]
                    for path in reports:
                        scorer.extend(["--seed-report", str(path)])
                    budget.run(scorer, cwd=cwd, env=environment, log=None, cpu_cores=1)


if __name__ == "__main__":
    main()
