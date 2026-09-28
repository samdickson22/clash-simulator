"""Eight isolated complete-game workers, with ordered audited publication."""

import argparse
import fcntl
import json
import os
import signal
import subprocess
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

import psutil
from parallel_engine import initialize
from parallel_io import publish_json
from parallel_protocol import (
    BASE_PLAN,
    WORKERS,
    build_plan,
    cases_for,
    source_fingerprint,
    validate_plan,
)
from probe_worker import sha

from scripts.hog26_scalar_openings import digest

ROOT = Path(__file__).resolve().parents[2]
MONITOR = Path("/Users/sam/Library/Application Support/ClasherMonitor")
LIMIT = 18 * 1024**3


def status(mode, **fields):
    fields.update(updated_at=time.time(), pid=os.getpid(), fitting_allowed=False)
    if mode == "collect":
        path = MONITOR / "comparison-status.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(fields, indent=2) + "\n")
        temporary.replace(path)
    print(json.dumps(fields), flush=True)


def main():
    def stop(signum, _frame):
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("preflight", "collect"), required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--attempt", type=int, default=1)
    args = parser.parse_args()
    if args.attempt < 1:
        raise ValueError("positive log attempt required")
    os.chdir(ROOT)
    if args.mode == "collect":
        shared_lock = (MONITOR / "comparison.lock").open("a")
        fcntl.flock(shared_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    name = "hog26_training_expansion_parallel_preflight_20260913" if args.mode == "preflight" else "hog26_training_expansion_parallel_seed1280101_20260913"
    output = ROOT / "datasets/derived" / name
    if (output / "complete.json").exists() or output.exists() != args.resume:
        raise ValueError("existing parallel output requires matching partial resume, never overwrite")
    original = json.loads((ROOT / BASE_PLAN).read_text())
    engine = initialize(ROOT, original["source_authority"]["contract"]["canonical_names"])
    resource_paths = {"checkpoint": ROOT / "checkpoints/hog26_direct_constant_event_seed1263001/candidate.pt",
                      "card_data": Path(engine.builder.loader.data_file)}

    def authority_now():
        return source_fingerprint(ROOT, resource_paths=resource_paths, vocabulary_sha256=engine.vocabulary.sha256,
                                  card_definitions=engine.builder.loader.load_card_definitions())

    authority = authority_now()
    pin = None
    if args.mode == "collect":
        plan_path = ROOT / "reports/hog26_training_expansion_parallel_frozen_plan_20260913.json"
        plan = json.loads(plan_path.read_text())
        pin = json.loads((ROOT / "reports/hog26_training_expansion_parallel_preflight_pin_20260913.json").read_text())
        validate_plan(plan, authority, preflight=pin)
        if not plan["frozen"] or not plan["collection_allowed"]:
            raise ValueError("parallel collection not authorized by preflight")
    else:
        plan = build_plan(authority=authority)
    _, cases = cases_for(plan, args.mode)
    output.mkdir(parents=True, exist_ok=args.resume)
    lease = (output / ".collector.lock").open("a")
    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    run_plan = output / "run_plan.json"
    publish_json(run_plan, plan)
    log_directory = output / "worker_logs"
    log_directory.mkdir(exist_ok=True)
    environment = dict(os.environ, OMP_NUM_THREADS="1",
                       PYTHONPATH="experiments/hog26_parallel_expansion:experiments/hog26_parallel_collection_probe:experiments/hog26_training_expansion:experiments/hog26_scalar_pilot:src:.")
    cancelled = threading.Event()
    launch_lock = threading.Lock()

    def run_case(index):
        with (log_directory / f"attempt{args.attempt}-case{index:04d}.log").open("x") as log:
            with launch_lock:
                if cancelled.is_set():
                    raise RuntimeError("parallel launch cancelled")
                child = subprocess.Popen(["/Users/sam/Desktop/code/clasher/.venv/bin/python", "-u",
                                          "experiments/hog26_parallel_expansion/collect_worker.py", "--plan", str(run_plan),
                                          "--mode", args.mode, "--case", str(index), "--output", str(output)],
                                         env=environment, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            code = child.wait()
        if code != 0:
            raise RuntimeError(f"parallel case {index} failed with exit {code}")
        receipt = json.loads((output / f"receipt-{index:04d}.json").read_text())
        if receipt["case"] != index or receipt["record"]["path"] != cases[index]["name"]:
            raise ValueError("parallel worker receipt identity differs")
        if sha(output / receipt["record"]["path"]) != receipt["record"]["sha256"]:
            raise ValueError("parallel archive differs from worker receipt")
        return receipt

    status(args.mode, stage="parallel-expansion-" + args.mode, output=str(output), workers=WORKERS,
           expected_games=len(cases), source_authority_sha256=digest(authority), memory_limit_bytes=LIMIT)
    peak, receipts, next_case = 0, {}, 0
    pool = ThreadPoolExecutor(max_workers=WORKERS)
    pending = set()
    try:
        while next_case < len(cases) or pending:
            while len(pending) < WORKERS and next_case < len(cases):
                pending.add(pool.submit(run_case, next_case))
                next_case += 1
            done, pending = wait(pending, timeout=1, return_when=FIRST_COMPLETED)
            process = psutil.Process()
            try:
                peak = max(peak, process.memory_info().rss + sum(c.memory_info().rss for c in process.children(recursive=True)))
            except psutil.NoSuchProcess:
                pass
            if peak > LIMIT:
                raise MemoryError("parallel expansion exceeded combined 18 GiB RSS")
            for future in done:
                receipt = future.result()
                if receipt["case"] in receipts:
                    raise ValueError("duplicate parallel case receipt")
                receipts[receipt["case"]] = receipt
                print(json.dumps({"completed_games": len(receipts), "case": receipt["case"], **receipt["record"]}), flush=True)
    except BaseException as error:
        with launch_lock:
            cancelled.set()
            children = psutil.Process().children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        status(args.mode, stage="parallel-expansion-failed", operation=args.mode, reason=f"{type(error).__name__}: {error}",
               output=str(output), peak_rss_bytes=peak, completed_games=len(receipts))
        raise
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
    validate_plan(plan, authority_now(), preflight=pin)
    results = [receipts[index]["record"] for index in range(len(cases))]
    if {p.name for p in output.glob("game-*.npz")} != {case["name"] for case in cases}:
        raise ValueError("parallel final game inventory differs")
    parity = sum(bool(receipt["preflight_parity_fields"]) for receipt in receipts.values())
    if args.mode == "preflight" and parity != 12:
        raise ValueError("parallel preflight did not prove every reference array")
    publish_json(output / "complete.json", {"status": "complete-audited", "mode": args.mode,
                 "source_authority_sha256": digest(authority), "plan_sha256": digest(plan),
                 "games": results, "game_count": len(results), "rows": sum(row["rows"] for row in results),
                 "parallel_workers": WORKERS, "parity_verified_games": parity, "fitting_allowed": False})
    status(args.mode, stage="parallel-expansion-" + args.mode + "-complete-awaiting-review",
           output=str(output), game_count=len(results), peak_rss_bytes=peak)


if __name__ == "__main__":
    main()
