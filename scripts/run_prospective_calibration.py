"""Sequential prospective collection and evaluation with durable one-attempt jobs."""

from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
import sys
import time
from pathlib import Path

from clasher.rl.calibration_artifacts import artifact_digest
from clasher.rl.calibration_collection import (
    FrozenCollectionProtocol,
    collection_sources,
    verify_protocol_documents,
)
from clasher.rl.calibration_families import register_family
from clasher.rl.calibration_jobs import (
    JobSpec,
    atomic_json,
    job_status,
    process_identity,
)


def run_job(directory, spec, native_lock):
    if not directory.exists():
        directory.mkdir(parents=True)
        atomic_json(directory / "request.json", spec.model_dump(mode="json"))
        log = (directory / "runner.log").open("xb")
        child = subprocess.Popen(
            [
                sys.executable,
                "scripts/run_calibration_job.py",
                "--job",
                str(directory),
                "--native-lock",
                str(native_lock),
            ],
            cwd=spec.cwd,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        log.close()
        atomic_json(
            directory / "launch.json",
            {"pid": child.pid, "identity": process_identity(child.pid)},
        )
    else:
        child = None
    while True:
        state, code = job_status(directory, spec)
        if state == "complete":
            if child is not None:
                child.wait()
            return code
        if state == "unresolved":
            if child is not None and child.poll() is None:
                time.sleep(1)
                continue
            raise RuntimeError(
                f"Job has no verified live process or terminal receipt: {directory}; inspect before continuing"
            )
        time.sleep(2)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("protocol", "registry", "campaign", "gamedata", "catalog", "adb"):
        p.add_argument("--" + name, type=Path, required=True)
    args = p.parse_args()
    for name in ("protocol", "registry", "campaign", "gamedata", "catalog", "adb"):
        setattr(args, name, getattr(args, name).resolve())
    workspace = Path.cwd()
    protocol = FrozenCollectionProtocol.model_validate_json(args.protocol.read_bytes())
    sha = artifact_digest(args.protocol)
    verify_protocol_documents(protocol, args.protocol.parent)
    expected = {
        str(path.relative_to(workspace)): artifact_digest(path)
        for path in collection_sources(workspace)
    }
    if expected != protocol.source_files:
        raise ValueError("campaign producer differs from frozen protocol")
    if (
        artifact_digest(args.gamedata) != protocol.ruleset_sha256
        or artifact_digest(args.catalog) != protocol.catalog_sha256
    ):
        raise ValueError("campaign ruleset/catalog differs")
    manifest = json.loads(
        (args.protocol.parent / protocol.family_manifest_path).read_text()
    )
    args.campaign.mkdir(parents=True, exist_ok=True)
    with (args.campaign / "supervisor.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        identity = args.campaign / "protocol-sha256.txt"
        if identity.exists():
            if identity.read_text().strip() != sha:
                raise ValueError("campaign belongs to another protocol")
        else:
            identity.write_text(sha + "\n")
        evaluation_job = args.campaign / "jobs/evaluation"
        if evaluation_job.exists():
            saved = JobSpec.model_validate_json(
                (evaluation_job / "request.json").read_bytes()
            )
            if saved.protocol_sha256 != sha or saved.cwd != str(workspace):
                raise ValueError("saved evaluation job belongs to another campaign")
            code = run_job(
                evaluation_job,
                saved,
                Path.home() / ".cache/clasher-native-reference/native-acceptance.lock",
            )
            atomic_json(
                args.campaign / "complete.json",
                {
                    "protocol_sha256": sha,
                    "evaluation_exit_code": code,
                    "configurations": sum(len(v) for v in protocol.families.values()),
                },
            )
            if code:
                raise SystemExit(code)
            return
        for family in manifest["families"]:
            register_family(
                args.registry,
                [c["config"] for c in family["configurations"]],
                family_id=family["family_id"],
                role="acceptance",
                protocol_sha256=sha,
            )
        index = {}
        native_lock = (
            Path.home() / ".cache/clasher-native-reference/native-acceptance.lock"
        )

        def job(name, command, native=False):
            spec = JobSpec(
                command=(sys.executable, *command),
                cwd=str(workspace),
                native=native,
                protocol_sha256=sha,
            )
            code = run_job(args.campaign / "jobs" / name, spec, native_lock)
            if code and name != "evaluation":
                atomic_json(args.campaign / "execution-index.json", index)
                atomic_json(
                    args.campaign / "failure.json",
                    {
                        "protocol_sha256": sha,
                        "job": name,
                        "exit_code": code,
                        "configurations_started": len(index),
                    },
                )
                raise SystemExit(code)
            return code

        for family in manifest["families"]:
            for item in family["configurations"]:
                config_sha = item["root_id"].split(":", 1)[1]
                root = args.campaign / config_sha
                root.mkdir(exist_ok=True)
                plan = root / "input-plan.json"
                input_plan = {"config": item["config"], "decks": item["decks"]}
                if plan.exists():
                    if json.loads(plan.read_text()) != input_plan:
                        raise ValueError("saved input plan changed")
                else:
                    atomic_json(plan, input_plan)
                capture = root / "capture"
                branches = root / "branch-protocol.json"
                index[config_sha] = {"capture": str(capture), "branches": []}
                common = [
                    "--gamedata",
                    str(args.gamedata),
                    "--catalog",
                    str(args.catalog),
                    "--catalog-sha256",
                    protocol.catalog_sha256,
                    "--adb",
                    str(args.adb),
                    "--registry",
                    str(args.registry),
                    "--family-id",
                    family["family_id"],
                    "--batched-native-levels",
                ]
                code = job(
                    config_sha + "-capture",
                    [
                        "scripts/collect_native_public_game.py",
                        "--plan",
                        str(plan),
                        "--seed",
                        str(item["config"]["rndSeed"]),
                        "--output",
                        str(capture),
                        "--acceptance-protocol",
                        str(args.protocol),
                        "--public-opponent-seat",
                        str(protocol.public_opponent_seat),
                        "--public-opponent-style",
                        protocol.public_opponent_style,
                        *common,
                    ],
                    native=True,
                )
                if code == 0:
                    code = job(
                        config_sha + "-prepare",
                        [
                            "scripts/prepare_prospective_branch.py",
                            "--capture",
                            str(capture),
                            "--collection-protocol",
                            str(args.protocol),
                            "--registry",
                            str(args.registry),
                            "--family-id",
                            family["family_id"],
                            "--catalog",
                            str(args.catalog),
                            "--output",
                            str(branches),
                        ],
                    )
                    if code == 0:
                        for engine in ("native", "scalar"):
                            output = root / ("branches-" + engine)
                            index[config_sha]["branches"].append(
                                {"path": str(output), "engines": [engine]}
                            )
                            job(
                                config_sha + "-" + engine,
                                [
                                    "scripts/compare_reacting_public_branches.py",
                                    "--capture",
                                    str(capture),
                                    "--protocol",
                                    str(branches),
                                    "--collection-protocol",
                                    str(args.protocol),
                                    "--output",
                                    str(output),
                                    "--engine",
                                    engine,
                                    *common,
                                ],
                                native=engine == "native",
                            )
                atomic_json(args.campaign / "execution-index.json", index)
                print(
                    "Finished configuration",
                    len(index),
                    "of",
                    sum(len(v) for v in protocol.families.values()),
                    flush=True,
                )
        code = job(
            "evaluation",
            [
                "scripts/evaluate_prospective_calibration.py",
                "--protocol",
                str(args.protocol),
                "--registry",
                str(args.registry),
                "--index",
                str(args.campaign / "execution-index.json"),
                "--catalog",
                str(args.catalog),
                "--output",
                str(args.campaign / "evaluation.json"),
            ],
        )
        atomic_json(
            args.campaign / "complete.json",
            {
                "protocol_sha256": sha,
                "evaluation_exit_code": code,
                "configurations": len(index),
            },
        )
        if code:
            raise SystemExit(code)


if __name__ == "__main__":
    main()
