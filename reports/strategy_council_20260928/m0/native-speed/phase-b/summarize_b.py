"""Summarize Phase B harness runs: latency, host CPU and dual-read results.

Usage: .venv/bin/python -B summarize_b.py --output summary-b.json RUN_DIR [RUN_DIR ...]
Fails (exit 1) if any dual read in any run was not identical.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def per_decision(breakdown, decisions):
    rows = {key: round(1000 * value["seconds"] / max(decisions, 1), 2) for key, value in breakdown.items()}
    return dict(sorted(rows.items(), key=lambda item: -item[1]))


def summarize(run):
    jobs = []
    for job in sorted(run.glob("job-*")):
        profile = json.loads((job / "profile.json").read_text()) if (job / "profile.json").exists() else None
        cpu = json.loads((job / "host-cpu.json").read_text()) if (job / "host-cpu.json").exists() else None
        dual = []
        if (job / "dual-read.jsonl").exists():
            dual = [json.loads(line) for line in (job / "dual-read.jsonl").read_text().splitlines()]
        level_rows = [row for row in dual if row["kind"] == "levels"]
        rich_rows = [row for row in dual if row["kind"] == "rich"]
        decisions = profile["decisions"] if profile else 0
        jobs.append({
            "job": job.name,
            "failure": profile.get("failure") if profile else "missing profile",
            "decisions": decisions,
            "seconds_per_decision": profile.get("seconds_per_decision") if profile else None,
            "host_cpu_ms_per_decision": None if not cpu or not decisions
            else round(1000 * cpu["process_cpu_seconds"] / decisions, 2),
            "read_options": cpu.get("read_options") if cpu else None,
            "breakdown_ms_per_decision": per_decision(profile["breakdown"], decisions) if profile else {},
            "dual_levels": {"frames": len(level_rows),
                            "non_identical": sum(not all(o.get("identical") for o in row["others"].values())
                                                 for row in level_rows)},
            "dual_rich": {"frames": len(rich_rows), "non_identical": sum(not row["identical"] for row in rich_rows)},
        })
    return {"run": str(run), "jobs": jobs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("runs", type=Path, nargs="+")
    args = parser.parse_args()
    result = [summarize(run) for run in args.runs]
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    bad = [job["job"] for run in result for job in run["jobs"]
           if job["failure"] or job["dual_levels"]["non_identical"] or job["dual_rich"]["non_identical"]]
    print(json.dumps({"runs": len(result), "failed_or_mismatched": bad}))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
