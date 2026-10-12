#!/usr/bin/env python3
"""Mac operator pre-start check for the TIERS session (coordinator rulings 2026-10-11 22:30:53Z / 22:35Z report).

Run ON THE MAC with the session's Python, from anywhere, as:
    python -B mac_preconditions.py <runtime-root> <bundle-or-staging-dir> <output.json>
It changes nothing. For 300 s it samples, at 1 Hz, the FROZEN telemetry.Census (imported read-only from the
runtime's e4v3) and averages per-PID CPU with the frozen receipts.census_average, exactly as the session's
pre-session census does (foreign PID > 0.2 core fails), except that the first CPU sample is primed rather than
recorded as unknown; the frozen session census still runs and is binding. Invoke with python -B. Before and after the window it reads vm_stat (free,
inactive, purgeable, speculative pages, swapouts), sysctl vm.swapusage and free disk. Thresholds (operator
preconditions, not gates): free+inactive+purgeable >= 6 GiB at both reads; free swap >= 1 GiB at both reads;
0 swapouts during the window; free disk >= 10 GiB. The output JSON is exclusive-created; exit 1 if any fails.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

GIB = 2 ** 30
WINDOW = 300


def vm():
    text = subprocess.check_output(["vm_stat"], text=True)
    page = int(re.search(r"page size of (\d+) bytes", text).group(1))
    values = {m.group(1).strip(): int(m.group(2)) for m in re.finditer(r"^([^:]+):\s+(\d+)\.", text, re.M)}
    swap = subprocess.check_output(["sysctl", "-n", "vm.swapusage"], text=True)
    def mb(key):
        return float(re.search(key + r" = ([\d.]+)M", swap).group(1)) * 2 ** 20
    available = (values["Pages free"] + values["Pages inactive"] + values["Pages purgeable"]) * page
    return dict(page_size=page, pages=values, available_bytes=available,
                swap_total_bytes=mb("total"), swap_used_bytes=mb("used"), swap_free_bytes=mb("free"),
                swapouts=values["Swapouts"], utc=time.time())


def main():
    runtime, staging, output = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    # Confinement (Sol pre-run review r1): the output must be a new, non-symlink file whose real parent lies in
    # the operator-owned staging root, so no symlinked parent can redirect the write.
    root = os.path.realpath(staging)
    parent = os.path.realpath(output.parent)
    if os.path.islink(output) or output.exists() or not (parent == root or parent.startswith(root + "/")):
        raise SystemExit("output must be a new file inside the staging root")
    sys.path.insert(0, str(runtime / "reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3"))
    from telemetry import Census
    from receipts import census_average
    before = vm()
    census, rows = Census(), []
    owned = {os.getpid()}
    census.sample(owned)
    last = start = time.monotonic()
    index = 1
    while time.monotonic() < start + WINDOW:
        time.sleep(max(0., start + index - time.monotonic()))
        now = time.monotonic()
        rows.append(dict(interval_seconds=now - last, processes=census.sample(owned)))
        last, index = now, index + 1
    after = vm()
    names = {str(p["pid"]): p["name"] for r in rows for p in r["processes"]}
    averages = census_average(rows)
    foreign = {pid: dict(name=names.get(pid), cores=v) for pid, v in averages.items() if v > .2}
    top = sorted(((v, pid) for pid, v in averages.items()), reverse=True)[:10]
    disk = shutil.disk_usage(staging)
    checks = dict(
        census_samples_ge_298=len(rows) >= 298,
        census_no_foreign_over_0_2_core=not foreign,
        available_ge_6GiB=min(before["available_bytes"], after["available_bytes"]) >= 6 * GIB,
        swap_free_ge_1GiB=min(before["swap_free_bytes"], after["swap_free_bytes"]) >= 1 * GIB,
        zero_swapouts=after["swapouts"] - before["swapouts"] == 0,
        disk_free_ge_10GiB=disk.free >= 10 * GIB)
    result = dict(schema="clasher.mac-e4-session.preconditions.v1", scope="operator preconditions, not gates; non-counted",
                  window_seconds=WINDOW, census_samples=len(rows), foreign_over_0_2_core=foreign,
                  top_consumers=[dict(pid=pid, name=names.get(pid), cores=v) for v, pid in top],
                  vm_before=before, vm_after=after, swapouts_delta=after["swapouts"] - before["swapouts"],
                  disk_free_bytes=disk.free, checks=checks, passes=all(checks.values()))
    with output.open("x") as stream:
        json.dump(result, stream, indent=1, sort_keys=True)
        stream.write("\n")
    print(json.dumps(dict(passes=result["passes"], checks=checks,
                          top=[(t["name"], round(t["cores"], 3)) for t in result["top_consumers"][:5]])))
    return 0 if result["passes"] else 1


if __name__ == "__main__":
    sys.exit(main())
