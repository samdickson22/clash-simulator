"""Run one immutable job and persist its terminal receipt even if its supervisor exits."""

import argparse
import fcntl
import subprocess
import time
from pathlib import Path

from clasher.rl.calibration_jobs import JobSpec, atomic_json, process_identity


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--job", type=Path, required=True)
    p.add_argument("--native-lock", type=Path, required=True)
    args = p.parse_args()
    spec = JobSpec.model_validate_json((args.job / "request.json").read_bytes())
    if (args.job / "complete.json").exists() or (args.job / "running.json").exists():
        raise ValueError("job already started; do not replay it")
    args.native_lock.parent.mkdir(parents=True, exist_ok=True)
    with (
        (args.job / "runner.lock").open("a") as own_lock,
        args.native_lock.open("a") as native_lock,
    ):
        fcntl.flock(own_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if spec.native:
            fcntl.flock(native_lock, fcntl.LOCK_EX)
        started = time.monotonic()
        with (args.job / "output.log").open("xb") as output:
            child = subprocess.Popen(
                spec.command, cwd=spec.cwd, stdout=output, stderr=subprocess.STDOUT
            )
            atomic_json(
                args.job / "running.json",
                {"pid": child.pid, "identity": process_identity(child.pid)},
            )
            code = child.wait()
        atomic_json(
            args.job / "complete.json",
            {
                "request": spec.model_dump(mode="json"),
                "exit_code": code,
                "elapsed_seconds": time.monotonic() - started,
            },
        )


if __name__ == "__main__":
    main()
