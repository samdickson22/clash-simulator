#!/usr/bin/env python3
"""No-fit launch preflight of the real council pilot command path.

For each requested seed and arm this runs the exact ``training_command`` argv
that ``run_council_pilot.py --execute`` would launch, as a child of a real
``LocalPilotBudget``, with ``--preflight-no-update`` appended. The trainer goes
through startup, council validation, weights-only initialization, worker and
environment creation, one (short) rollout collection, GAE, and the scheduled
critic warm-up and/or PPO loss/backward paths, then exits before any
``optimizer.step()``. It writes no checkpoint and must report bit-identical
weights before and after.

Everything lives in a temporary directory: a copy of the pilot TOML whose
output, source-pin and admission paths point there (and whose environment count
may be reduced), a freshly frozen source-pin file, a placeholder admission file
that explicitly is not a receipt, and synthetic initialization checkpoints. The
initializers are written through the real imitation checkpoint writer with a
typed BudgetSnapshot from the temporary ledger. They are seeded random weights
(the scripted stand-in is a deterministic perturbation), never fitted to any
data: this checks software plumbing, not gameplay fitting or playing strength.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise TypeError(f"unsupported TOML value {value!r}")


def _write_preflight_config(
    real_config: Path, directory: Path, *, num_envs: int, actor_workers: int
) -> Path:
    raw = tomllib.loads(real_config.read_text())
    raw.update(
        output_dir=str(directory / "runs"),
        source_pins_path=str(directory / "source-pins.json"),
        nominal_admission_path=str(directory / "admissions" / "nominal.json"),
        mixed_level_admission_path=str(directory / "admissions" / "levels-10-12.json"),
        num_envs=num_envs,
        actor_workers=actor_workers,
    )
    path = directory / "council-pilot-preflight.toml"
    lines = [
        "# Launch-preflight copy of the pilot config. Never an admitted run config.",
        *(f"{key} = {_toml_value(value)}" for key, value in raw.items()),
    ]
    path.write_text("\n".join(lines) + "\n")
    return path


def _freeze_source_pins(config) -> None:
    # Same file set and format as run_council_pilot.py --freeze-source.
    root = Path(config.source_root)
    paths = sorted((root / "src/clasher").rglob("*.py"))
    paths += [
        root / "scripts/run_council_pilot.py",
        root / "scripts/run_council_warmstart.py",
        root / "scripts/evaluate_council_pilot.py",
    ]
    destination = Path(config.source_pins_path)
    with destination.open("x") as stream:
        json.dump({str(path): _sha(path) for path in paths}, stream, indent=2)
        stream.write("\n")


def write_initialization_fixture(config_path: Path, seed: int, directory: Path) -> dict:
    """Budget-owned child: write both arms' synthetic initializers for one seed."""
    import torch

    from clasher.rl.council_budget import (
        BudgetSnapshot,
        budget_snapshot,
        require_owned_budget,
    )
    from clasher.rl.council_pilot import (
        build_council_model_config,
        load_pilot_config,
        state_dict_sha256,
    )
    from clasher.rl.imitation import (
        CORPUS_SCHEMA_VERSION,
        CorpusMetadata,
        _checkpoint_payload,
    )
    from clasher.rl.model import ClasherPolicy
    from clasher.rl.public_scripted_opponent import SUPPORTED_CARDS
    from clasher.rl.structured_obs import StructuredObservationBuilder

    config = load_pilot_config(config_path)
    ledger = Path(config.output_dir) / "resource-budget.json"
    require_owned_budget(ledger)
    torch.set_num_threads(config.torch_threads)
    # Identical builder to council_warmstart.run_script_warmstart.
    builder = StructuredObservationBuilder(
        decks_path=Path(config.training_decks_path),
        card_vocab=sorted(SUPPORTED_CARDS),
        max_entities=128,
        canonical_perspective=True,
        canonical_lane_globals=True,
        public_history_slots=4,
        public_seen_card_slots=8,
        card_semantics_version=4,
        public_entity_levels=True,
        public_hand_levels=True,
    )
    model_config = build_council_model_config(builder)
    torch.manual_seed(seed)
    control = ClasherPolicy(model_config, builder.card_stat_features).eval()
    scripted = ClasherPolicy(model_config, builder.card_stat_features).eval()
    scripted.load_state_dict(control.state_dict())
    generator = torch.Generator().manual_seed(seed + 1)
    with torch.no_grad():
        # Stand-in for fitted weights without any data or optimizer: a fixed
        # seeded perturbation of parameters only (semantic buffers unchanged).
        for parameter in scripted.parameters():
            parameter.add_(
                1e-3 * torch.randn(parameter.shape, generator=generator)
            )
    directory.mkdir(parents=True, exist_ok=True)
    plan = directory / "synthetic-preflight-plan.json"
    plan.write_text(
        json.dumps(
            {
                "schema": "clasher.council-launch-preflight-fixture.v1",
                "seed": seed,
                "synthetic": True,
                "fitted": False,
                "note": "seeded random weights for a no-update launch preflight",
            },
            indent=2,
        )
        + "\n"
    )
    admission = Path(config.nominal_admission_path)
    metadata = CorpusMetadata(
        schema_version=CORPUS_SCHEMA_VERSION,
        created_at=datetime.now(timezone.utc).isoformat(),
        seed=seed,
        decisions=0,
        samples=0,
        decision_interval=5,
        max_ticks=6001,
        planner_depth=0,
        planner_simulations=0,
        planner_action_samples=0,
        max_entities=128,
        token_names=builder.token_names,
        label_source="public-script",
        public_contract_version=4,
        public_history_slots=4,
        public_seen_card_slots=8,
        provenance=json.dumps({"synthetic_launch_preflight": True}),
    )
    checkpoint_metadata = {
        "gamedata_sha256": config.gamedata_sha256,
        "resource_budget": budget_snapshot(ledger),
        "strategy_sha256": config.strategy_sha256,
        "source_pins_sha256": _sha(Path(config.source_pins_path)),
        "training_decks_sha256": config.training_decks_sha256,
        "admission_sha256": _sha(admission),
        "warmstart_plan_sha256": _sha(plan),
    }
    BudgetSnapshot.model_validate(checkpoint_metadata["resource_budget"])
    outputs = {}
    for name, model, trained in (
        ("scripted.pt", scripted, True),
        ("scripted-random-control.pt", control, False),
    ):
        payload = _checkpoint_payload(
            model=model,
            metadata=metadata,
            corpus_path=plan,
            metrics={},
            seed=seed,
            split_seed=seed,
            trained=trained,
            trim_entity_padding=True,
            canonical_lane_globals=True,
        ) | checkpoint_metadata
        path = directory / name
        with path.open("xb") as stream:
            torch.save(payload, stream)
        outputs[name] = {
            "path": str(path),
            "sha256": _sha(path),
            "state_sha256": state_dict_sha256(model.state_dict()),
        }
    (directory / "fixture.json").write_text(json.dumps(outputs, indent=2) + "\n")
    return outputs


def _new_pt_files(since: float, exclude: Path) -> list[str]:
    found = []
    for base in (ROOT / "checkpoints", ROOT / "reports", ROOT / "datasets", ROOT):
        if not base.exists():
            continue
        iterator = base.rglob("*.pt") if base != ROOT else base.glob("*.pt")
        for path in iterator:
            try:
                if path.stat().st_mtime >= since and exclude not in path.parents:
                    found.append(str(path))
            except FileNotFoundError:
                continue
    return sorted(set(found))


def run_preflight(args) -> dict:
    from clasher.rl.council_budget import LocalPilotBudget
    from clasher.rl.council_pilot import (
        critic_warmup_updates_for_arm,
        is_continuation,
        is_human_prior,
        load_pilot_config,
        opponent_initialization_paths_for_seed,
        pilot_environment,
        publish_initial_pool,
        state_dict_sha256,
        training_command,
    )

    real_config_path = args.config.resolve()
    real = load_pilot_config(real_config_path)
    seeds = tuple(args.seed or real.seeds)
    arms = tuple(args.arm or real.arms)
    if not set(seeds) <= set(real.seeds) or not set(arms) <= set(real.arms):
        raise ValueError("undeclared arm/seed")
    real_output = Path(real.output_dir)
    real_output_existed = real_output.exists()
    started_wall = time.time()
    workdir = Path(tempfile.mkdtemp(prefix="council-launch-preflight-"))
    runs = []
    try:
        (workdir / "admissions").mkdir()
        config_path = _write_preflight_config(
            real_config_path,
            workdir,
            num_envs=args.num_envs,
            actor_workers=args.actor_workers,
        )
        config = load_pilot_config(config_path)
        _freeze_source_pins(config)
        admission = Path(config.nominal_admission_path)
        admission.write_text(
            json.dumps(
                {
                    "schema": "clasher.council-launch-preflight-placeholder.v1",
                    "is_admission_receipt": False,
                    "note": "digest binding target for a no-update preflight only",
                },
                indent=2,
            )
            + "\n"
        )
        environment = pilot_environment(config)
        cwd = Path(config.gamedata_path).parent
        with LocalPilotBudget(
            Path(config.output_dir),
            config_sha256=_sha(config_path),
            cpu_core_hour_ceiling=config.cpu_core_hour_ceiling,
            accelerator_hour_ceiling=config.accelerator_hour_ceiling,
        ) as budget:
            for seed in seeds:
                initialization_dir = Path(config.output_dir) / f"seed-{seed}" / "initialization"
                initialization_dir.mkdir(parents=True)
                fixture_command = [
                    sys.executable,
                    "-B",
                    str(Path(__file__).resolve()),
                    "--write-initialization-fixture",
                    "--config",
                    str(config_path),
                    "--seed",
                    str(seed),
                    "--fixture-dir",
                    str(initialization_dir),
                ]
                with (initialization_dir / "fixture.log").open("x") as log:
                    budget.run(
                        fixture_command, cwd=cwd, env=environment, log=log, cpu_cores=1
                    )
                fixture = json.loads((initialization_dir / "fixture.json").read_text())
                scripted = initialization_dir / "scripted.pt"
                scratch = initialization_dir / "scripted-random-control.pt"
                for arm in arms:
                    directory = Path(config.output_dir) / f"seed-{seed}" / arm
                    directory.mkdir(parents=True)
                    pool = directory / "opponents" / "pool.json"
                    publish_initial_pool(
                        config,
                        pool_path=pool,
                        initialization_paths=opponent_initialization_paths_for_seed(
                            config, seed=seed, arm=arm, scripted=scripted, scratch=scratch
                        ),
                    )
                    initialization = scripted if arm == "scripted" else scratch
                    declared = None
                    if is_continuation(config, seed, arm):
                        declared = Path(config.continuation_checkpoint_path)
                    elif is_human_prior(config, seed, arm):
                        declared = Path(config.human_prior_checkpoint_path)
                    if declared is not None:
                        # The real declared checkpoint (read only): its digest is
                        # bound by the config, so no synthetic stand-in can pass.
                        # (For the human prior it is also the KL anchor.)
                        import torch

                        initialization = declared
                        expected_state = state_dict_sha256(
                            torch.load(
                                initialization, map_location="cpu", weights_only=False
                            )["model_state_dict"]
                        )
                    else:
                        expected_state = fixture[initialization.name]["state_sha256"]
                    before_file = _sha(initialization)
                    command = training_command(
                        config,
                        config_path=config_path,
                        admission=admission,
                        seed=seed,
                        arm=arm,
                        phase="smoke",
                        pool_path=pool,
                        initialization=initialization,
                        resume=None,
                    )
                    report_path = directory / "preflight-report.json"
                    preflight_flags = [
                        "--preflight-no-update",
                        "--preflight-rollout-steps",
                        str(args.rollout_steps),
                        "--preflight-report-json",
                        str(report_path),
                    ]
                    begin = time.monotonic()
                    status = "failed"
                    error = None
                    log_path = directory / "preflight-train.log"
                    try:
                        with log_path.open("x") as log:
                            budget.run(
                                command + preflight_flags,
                                cwd=cwd,
                                env=environment,
                                log=log,
                                cpu_cores=config.actor_workers * config.actor_threads
                                + config.torch_threads,
                            )
                        status = "completed"
                    except subprocess.CalledProcessError as exc:
                        error = f"trainer exited {exc.returncode}"
                    elapsed = time.monotonic() - begin
                    report = (
                        json.loads(report_path.read_text())
                        if report_path.exists()
                        else None
                    )
                    stray_checkpoints = sorted(
                        str(path)
                        for path in Path(config.output_dir).rglob("*.pt")
                        if path.parent != initialization_dir
                    )
                    checks = {
                        "trainer_exit_zero": status == "completed",
                        "report_passed": bool(report and report["status"] == "passed"),
                        "weights_before_equal_initializer": bool(
                            report and report["weights_sha256_before"] == expected_state
                        ),
                        "weights_after_equal_initializer": bool(
                            report and report["weights_sha256_after"] == expected_state
                        ),
                        "optimizer_state_empty": bool(
                            report
                            and report["optimizer_state_entries_before"] == 0
                            and report["optimizer_state_entries_after"] == 0
                        ),
                        "no_checkpoint_written": not stray_checkpoints
                        and bool(report and not report["checkpoints_written"]),
                        "initializer_file_unchanged": _sha(initialization) == before_file,
                    }
                    log_tail = log_path.read_text().splitlines()[-25:]
                    runs.append(
                        {
                            "seed": seed,
                            "arm": arm,
                            "critic_warmup_updates": critic_warmup_updates_for_arm(
                                config, arm
                            ),
                            "status": "passed" if all(checks.values()) else "failed",
                            "error": error,
                            "checks": checks,
                            "wall_seconds": elapsed,
                            "argv_real_pilot": command,
                            "argv_preflight_suffix": preflight_flags,
                            "initializer_kind": "continuation"
                            if is_continuation(config, seed, arm)
                            else "human_prior"
                            if is_human_prior(config, seed, arm)
                            else "synthetic",
                            "initializer_sha256": before_file,
                            "initializer_state_sha256": expected_state,
                            "trainer_report": report,
                            "stray_checkpoints": stray_checkpoints,
                            "log_tail": log_tail,
                        }
                    )
                    print(
                        json.dumps(
                            {
                                "seed": seed,
                                "arm": arm,
                                "status": runs[-1]["status"],
                                "wall_seconds": round(elapsed, 2),
                            }
                        ),
                        flush=True,
                    )
            budget_record = json.loads(budget.path.read_text())
    finally:
        tmp_listing = sorted(
            str(path.relative_to(workdir)) for path in workdir.rglob("*") if path.is_file()
        )
        if not args.keep_tmp:
            shutil.rmtree(workdir, ignore_errors=True)
    outside = _new_pt_files(started_wall, workdir)
    result = {
        "schema": "clasher.council-launch-preflight.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "gameplay_fitting": False,
        "admission": "not checked: no-update preflight (Tier A receipt absent)",
        "real_config": str(real_config_path),
        "real_config_sha256": _sha(real_config_path),
        "preflight_overrides": {
            "num_envs": args.num_envs,
            "actor_workers": args.actor_workers,
            "rollout_steps_cap": args.rollout_steps,
            "phase": "smoke",
            "output_dir": "temporary directory (deleted)"
            if not args.keep_tmp
            else str(workdir),
        },
        "host_environment": {
            "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
            "trainer_OMP_NUM_THREADS": str(real.torch_threads),
            "python": sys.version.split()[0],
        },
        "initializers": "synthetic seeded weights through the real imitation "
        "checkpoint writer with a typed BudgetSnapshot; never fitted",
        "runs": runs,
        "budget_jobs": [
            {key: job[key] for key in ("argv", "cpu_cores", "elapsed_seconds", "status")}
            for job in budget_record["jobs"]
        ],
        "temporary_files": tmp_listing,
        "new_pt_files_outside_tmp": outside,
        "real_output_dir_created": (not real_output_existed) and real_output.exists(),
        "status": "passed"
        if runs
        and all(run["status"] == "passed" for run in runs)
        and not outside
        and not ((not real_output_existed) and real_output.exists())
        else "failed",
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seed", type=int, action="append")
    parser.add_argument("--arm", choices=("scripted", "scratch"), action="append")
    parser.add_argument("--num-envs", type=int, default=2)
    parser.add_argument("--actor-workers", type=int, default=2)
    parser.add_argument("--rollout-steps", type=int, default=4)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--keep-tmp", action="store_true")
    parser.add_argument("--write-initialization-fixture", action="store_true")
    parser.add_argument("--fixture-dir", type=Path)
    args = parser.parse_args()
    if args.write_initialization_fixture:
        if args.fixture_dir is None or not args.seed or len(args.seed) != 1:
            raise ValueError("fixture mode needs one --seed and --fixture-dir")
        print(json.dumps(write_initialization_fixture(args.config, args.seed[0], args.fixture_dir), indent=2))
        return
    if args.output_json is not None and args.output_json.exists():
        raise FileExistsError("refusing to overwrite a preflight record")
    result = run_preflight(args)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        with args.output_json.open("x") as stream:
            stream.write(text)
    print(json.dumps({"status": result["status"], "runs": [
        {k: run[k] for k in ("seed", "arm", "status", "wall_seconds")} for run in result["runs"]
    ]}, indent=2))
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
