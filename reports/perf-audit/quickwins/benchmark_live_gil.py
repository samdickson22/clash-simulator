"""Read-only corrected live qualification replay, serial versus four roots.

Run in a fresh CPU-only process per binary. The qualification tree is never
written; --output must be a new path. Scores use the existing RustPlanner.score
and its unchanged S6 dependency, with a nonbinding 120-second deadline.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import time

import numpy as np
import torch
import clasher_core
from clasher.live.decision import RustPlanner
from clasher.live.loading import module
from clasher.live.runtime import quantiles


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def score_hash(scores):
    return hashlib.sha256(json.dumps(scores, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def trainer_rows(path, count=5):
    with path.open("rb") as source:
        source.seek(max(0, path.stat().st_size-65536))
        lines = source.read().splitlines()
    rows = []
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("event") == "step" and "rows_per_second_step" in row:
            rows.append(dict(step=row["step"], rows_per_second_step=row["rows_per_second_step"]))
        if len(rows) == count:
            break
    if len(rows) != count:
        raise ValueError("missing trainer interval throughput")
    return list(reversed(rows))


def main(args):
    if args.output.exists() or args.output.with_suffix(".samples.jsonl").exists():
        raise ValueError("fresh output and samples path required")
    if platform.node() not in ("127x04", "127x08") or os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise ValueError("approved CPU-only host required")
    if os.getpriority(os.PRIO_PROCESS, 0) < 10:
        raise ValueError("nice >=10 required")
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    original_binary = args.qualification/"engine-rs/clasher_core.abi3.so"
    protected_before = sha(original_binary)
    input_path = args.qualification/"reports/strategy_council_20260928/live-loop/v4/perf-fixes/mac-search-inputs.json.gz"
    qualifier_path = input_path.with_name("qualify.py")
    qualifier = module("quickwin_live_qualification_reference", qualifier_path)
    fixture = json.loads(gzip.decompress(input_path.read_bytes()))
    reference = json.loads(args.reference.read_text())
    assert fixture["split"] == "train" and not fixture["unmatched"]
    assert sha(input_path) == reference["input_sha256"]
    expected = {(r["match"], r["sequence"]): r for r in reference["score_exactness"]["receipts"]}
    selected = fixture["inputs"][::max(1, len(fixture["inputs"])//args.decisions)][:args.decisions]
    assert {(r["match"], r["sequence"]) for r in selected} == set(expected)
    before = trainer_rows(args.trainer_log) if args.trainer_log else []
    baseline_rate = statistics.median(r["rows_per_second_step"] for r in before) if before else None
    result = dict(schema="clasher.native-gil.corrected-live.v1", label=args.label,
                  host=platform.node(), python=sys.version, torch=torch.__version__,
                  nice=os.getpriority(os.PRIO_PROCESS, 0), affinity=sorted(os.sched_getaffinity(0)),
                  native_path=clasher_core.__file__, native_sha256=sha(clasher_core.__file__),
                  qualification_path=str(args.qualification), input_sha256=sha(input_path),
                  reference_sha256=sha(args.reference), qualifier_sha256=sha(qualifier_path),
                  pythonhashseed=os.environ.get("PYTHONHASHSEED"),
                  driver_sha256=sha(__file__), split="train", heldout_opened=False,
                  flags=dict(public_tower_model=True, cache_root_config=True, hoist_opponent_moves=True),
                  repeats=args.repeats, workers=4, trainer_before=before, samples=[],
                  startup_excluded=True, root_construction_included=True,
                  qualification_timing_scope="root construction plus full-list four-root scoring",
                  full_decision_timing_scope="public parse, packet, candidates, roots, scores, reduction",
                  live_sources={str(p.relative_to(args.qualification)): sha(p)
                                for p in sorted((args.qualification/"src/clasher/live").glob("*.py"))})
    planner = RustPlanner(dict(seed=6108, **result["flags"]))
    result["config_sha256"] = score_hash(planner.resources.config)
    result["templates_sha256"] = score_hash(sorted(planner.resources.templates.items()))
    reference_mismatches = {}
    samples_path = args.output.with_suffix(".samples.jsonl")
    try:
        # Establish that the selected corrected roots exercise real simulation.
        root_checks = []
        for row in selected:
            planner.cores[0].rng = np.random.default_rng(6108)
            info, _ = qualifier.info_for(planner, planner.packets, row)
            rng = np.random.default_rng(6108)
            for index, hypothesis in enumerate(row["roots"]):
                root = planner.resources.root(info, hypothesis, rng)
                snapshot = json.loads(root.snapshot())
                root.step(1)
                terminal = json.loads(root.snapshot())["game_over"]
                assert not terminal, (row["match"], row["sequence"], index)
                assert {e["owner"] for e in snapshot["entities"] if e["king"]} == {0, 1}
                root_checks.append(dict(match=row["match"], sequence=row["sequence"], root=index,
                                        after_one_tick_terminal=False))
        result["nonterminal_checks"] = root_checks

        def run(row, parallel):
            started = time.perf_counter()
            planner.cores[0].rng = np.random.default_rng(6108)
            info, _ = qualifier.info_for(planner, planner.packets, row)
            candidates, _ = planner.cores[0].candidates(info.packet)
            assert len(candidates) == expected[(row["match"], row["sequence"])]["candidates"]
            assert len(candidates) >= 2
            planner.delay_ticks = row["recorded_delay_ticks"]
            for core in planner.cores:
                core.command_delay = planner.delay_ticks
            roots_started = time.perf_counter()
            roots = [planner.resources.root(info, hypothesis, np_rng)
                     for hypothesis in row["roots"]]
            roots_done = time.perf_counter()
            root_digests = [root.digest() for root in roots]
            deadline = time.monotonic()+120.
            if parallel:
                futures = [pool.submit(planner.score, core, root, info, candidates, deadline)
                           for core, root in zip(planner.cores, roots)]
                scores = [f.result() for f in futures]
            else:
                scores = [planner.score(core, root, info, candidates, deadline)
                          for core, root in zip(planner.cores, roots)]
            scored = time.perf_counter()
            assert all(all(v is not None for v in values) for values in scores)
            previous = expected[(row["match"], row["sequence"])]["optimized"]
            if scores != previous:
                reference_mismatches[(row["match"], row["sequence"])] = dict(
                    match=row["match"], sequence=row["sequence"], candidates=list(map(int, candidates)),
                    previous_scores=previous, replay_scores=scores)
            reduced = [sum(values)/4 for values in zip(*scores)]
            best = 0
            for i in range(1, len(candidates)):
                if reduced[i] > reduced[best]+1e-9:
                    best = i
            done = time.perf_counter()
            return dict(match=row["match"], sequence=row["sequence"], parallel=parallel,
                        candidates=list(map(int, candidates)), root_count=4,
                        root_digests=root_digests,
                        full_decision_ms=(done-started)*1000,
                        qualification_decision_ms=(scored-roots_started)*1000,
                        root_construction_ms=(roots_done-roots_started)*1000,
                        scoring_ms=(scored-roots_done)*1000,
                        scores=scores, scores_sha256=score_hash(scores), action=int(candidates[best]))

        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="gil-live-root") as pool:
            # Warm both schedules on the first real decision; discard timings.
            for parallel in (False, True):
                np_rng = np.random.default_rng(6108)
                run(selected[0], parallel)
            with samples_path.open("x") as output:
                for repeat in range(args.repeats):
                    for index, row in enumerate(selected):
                        pair = []
                        for parallel in ((False, True) if (repeat+index)%2 else (True, False)):
                            np_rng = np.random.default_rng(6108)
                            sample = run(row, parallel)
                            sample["repeat"] = repeat
                            pair.append(sample)
                            result["samples"].append(sample)
                            output.write(json.dumps(sample, allow_nan=False)+"\n")
                            output.flush()
                        assert pair[0]["scores"] == pair[1]["scores"]
                        assert pair[0]["candidates"] == pair[1]["candidates"]
                        assert pair[0]["action"] == pair[1]["action"]
                        assert pair[0]["root_digests"] == pair[1]["root_digests"]
                        if args.trainer_log:
                            latest = trainer_rows(args.trainer_log, 3)
                            rate = statistics.median(r["rows_per_second_step"] for r in latest)
                            if rate < baseline_rate*.95:
                                result["trainer_protection_stop"] = dict(rate=rate, baseline_rate=baseline_rate, latest=latest)
                                raise RuntimeError("trainer interval median dropped >5%; stopped own benchmark")
                        print(json.dumps(dict(label=args.label, repeat=repeat, match=row["match"], sequence=row["sequence"],
                                              ms={"parallel" if s["parallel"] else "serial": round(s["qualification_decision_ms"], 2)
                                                  for s in pair})), flush=True)
        result["decision_ms"] = {
            mode: {field: quantiles([r[field] for r in result["samples"] if r["parallel"] == parallel])
                   for field in ("full_decision_ms", "qualification_decision_ms", "scoring_ms", "root_construction_ms")}
            for mode, parallel in (("serial", False), ("four_threads", True))}
        result["exactness"] = dict(unique_decisions=len(selected), nonterminal_roots=len(root_checks),
                                    reference_matches=not reference_mismatches,
                                    reference_mismatches=list(reference_mismatches.values()),
                                    serial_parallel_mismatches=0,
                                    candidate_root_scores=sum(len(r["candidates"])*4 for r in result["samples"]))
        after = trainer_rows(args.trainer_log) if args.trainer_log else []
        result["trainer_after"] = after
        if before:
            result["trainer_interval_median_before"] = baseline_rate
            result["trainer_interval_median_after"] = statistics.median(r["rows_per_second_step"] for r in after)
        assert sha(original_binary) == protected_before
        assert sha(input_path) == result["input_sha256"]
        assert all(sha(args.qualification/path) == value for path, value in result["live_sources"].items())
        result["protected_binary_sha256"] = protected_before
        result["qualification_sources_unchanged"] = True
        result["samples_sha256"] = sha(samples_path)
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
        print("RESULT "+json.dumps(result["decision_ms"]), flush=True)
    except Exception:
        args.output.with_suffix(".failure.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
        raise
    finally:
        planner.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--qualification", type=Path, required=True)
    p.add_argument("--reference", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--label", required=True)
    p.add_argument("--decisions", type=int, default=16)
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--trainer-log", type=Path)
    main(p.parse_args())
