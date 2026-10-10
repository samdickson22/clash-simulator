"""Use T1's SHA-pinned reporting guard and OP-1 rules without SSH or controls."""
import importlib
import json
import os
import sys
import time
from pathlib import Path
from receipts import sha


class FleetTechnicalError(RuntimeError):
    def __init__(self, cause, detail):
        self.cause = cause
        super().__init__(detail)


def owned_tree(rows, roots, known):
    """PID reuse never earns ownership; descendants include spawn helpers."""
    live = {r["pid"]: r for r in rows}
    for pid in roots:
        if pid in live:
            known.setdefault(pid, live[pid]["start_ticks"])
    owned = {pid for pid, start in known.items() if pid in live and live[pid]["start_ticks"] == start}
    changed = True
    while changed:
        changed = False
        for row in rows:
            if row["ppid"] in owned and row["pid"] not in owned:
                if row["pid"] in known and known[row["pid"]] != row["start_ticks"]:
                    continue
                known[row["pid"]] = row["start_ticks"]
                owned.add(row["pid"]); changed = True
    return owned


def validity_reason(foreign, active, console, console_cpu, dt, overloaded, memory, op1=False):
    overloaded = overloaded+dt if console["positive"] and console_cpu/dt > 1 else 0.
    jobs = [r for r in foreign if not (console["positive"] and r.get("tty", 0))]
    busy = [r for r in active if not (console["positive"] and r.get("tty", 0))]
    reason = ("memory_floor" if memory < 24*2**30 else
              "console_over_one_core_60s" if overloaded > 60 else
              "foreign_compute" if jobs else "foreign_active" if busy else
              "op1_interference" if op1 else None)
    return reason, overloaded


class ReportingGuard:
    def __init__(self, bundle, manifest, owned):
        bundle = Path(bundle)
        profile = manifest["reference_load_profile"]
        cfg = profile["guard"]
        freeze = json.loads((bundle/cfg["freeze"]).read_text())
        if cfg["freeze"] not in manifest["files"]:
            raise ValueError("Guard freeze must be SHA-pinned")
        root = bundle/cfg["root"]
        for name in ("common.py", "host_audit.py", "idle_services.py", "system_bus.py", "ssh_transport.py"):
            relative = str((root/name).relative_to(bundle))
            expected = freeze["files"]["reports/explore/t1/"+name]
            if manifest["files"].get(relative) != expected or sha(root/name) != expected:
                raise ValueError("Reporting guard is not the frozen OP-1 source: "+name)
        sys.path.insert(0, str(root))
        # This runs in the fresh census process, before any research-module imports.
        if any(name in sys.modules for name in ("common", "host_audit", "system_bus", "idle_services", "ssh_transport")):
            raise ValueError("Reporting guard import collision")
        self.audit = importlib.import_module("host_audit")
        self.bus = importlib.import_module("system_bus")
        self.idle = importlib.import_module("idle_services")
        plan = json.loads((bundle/profile["plan"]).read_text())
        # Point all guard imports at the single pinned reporting/smoke plan.
        for module in (self.audit, self.idle):
            module.plan = lambda: plan
        self.job = Path(cfg["job"])
        self.admissions = {name: (bundle/source, manifest["files"][source]) for name, source in cfg["admissions"].items()}
        if "system-bus-admission.json" not in self.admissions:
            raise ValueError("Existing exact system-bus admission required; no refresh")
        for name in ("idle-services.json", "owned-copier-admission.json"):
            if (self.job/name).exists() and name not in self.admissions:
                raise ValueError("Every existing guard admission must be pinned")
        self.owned = owned; self.known = {}; self.current_owned = set()
        self.audit.own_process = lambda job, row: row["pid"] in self.current_owned
        self.previous = None; self.last = time.monotonic(); self.origin = self.last
        self.overloaded = 0.; self.bus_meter = None; self.idle_meters = None
        self.check_admissions()

    def check_admissions(self):
        for name, (source, expected) in self.admissions.items():
            if sha(source) != expected or sha(self.job/name) != expected:
                raise ValueError("Reporting guard admission identity changed: "+name)

    def __call__(self, row):
        self.check_admissions()
        now = time.monotonic(); dt = max(now-self.last, .001)
        current = self.audit.processes()
        roots = {p for p in self.owned if p > 0} | {os.getpid()}
        self.current_owned = owned_tree(current, roots, self.known)
        if self.bus_meter is None:
            self.bus_meter = self.bus.begin(self.job, current)
            self.idle_meters = self.idle.begin(self.job, current)
        after, foreign, active, cpu = self.audit.census(self.job, self.previous)
        self.bus.update(self.bus_meter, after); self.idle.update(self.idle_meters, after)
        elapsed = max(now-self.origin, .001)
        bus = self.bus.finish(self.bus_meter, elapsed)
        idle = self.idle.finish(self.idle_meters, elapsed)
        console = self.audit.console(); available = self.audit.memory()
        reason, self.overloaded = validity_reason(foreign, active, console, cpu, dt, self.overloaded,
            available, bus["interfered"] or bus["retired"] or idle["interfered"])
        self.previous, self.last = after, now
        row["reporting_guard"] = dict(passes=reason is None, reason=reason, console=console,
            console_over_one_core_seconds=self.overloaded, memavailable_bytes=available,
            foreign_compute=foreign, foreign_active=active, system_bus=bus, idle_services=idle,
            owned_pid_start_ticks={str(pid): self.known[pid] for pid in sorted(self.current_owned)})
        return reason


def validate_census(rows):
    if len(rows) < 2 or any("reporting_guard" not in row for row in rows):
        raise FleetTechnicalError("validity_census", "Missing reference reporting guard observations")
    failures = [row["reporting_guard"] for row in rows if row["reporting_guard"]["passes"] is not True]
    if failures:
        raise FleetTechnicalError("validity_census", "Reference reporting guard failed: "+str(failures[0]["reason"]))
    return dict(passes=True, observations=len(rows), rules="frozen T1 reporting + OP-1", final=False)


def classify_attempt(directory, manifest):
    """Only structured, sealed evidence grants a technical repeat candidate."""
    directory = Path(directory)
    if manifest["status"] == "complete":
        return dict(passes=True, technical_repeat_candidate=False, exactness_failure=False)
    failure = json.loads((directory/"failure.json").read_text())
    error = failure.get("error", "").lower()
    exact = any(word in error for word in ("exactness", "rng", "root digest", "zero-budget", "zero native budget", "native score", "posterior", "sampled opponent"))
    typed = failure.get("fleet_technical_cause")
    for name in ("exactness-tiers.json", "belief-exactness.json"):
        p = directory/name
        if p.exists():
            value = json.loads(p.read_text())
            if value.get("passes") is not True:
                exact = True
            for row in value.get("records", []):
                differences = row.get("max_relative_difference", 0)
                if isinstance(differences, dict):
                    exact = exact or any(v != 0 for v in differences.values())
                else:
                    exact = exact or differences != 0 or row.get("exact") is not True
    allowed = typed in ("crash", "host_loss", "mhz_gate", "validity_census")
    if typed == "mhz_gate":
        p = directory/"reporting-mhz-comparison.json"
        allowed = p.is_file() and json.loads(p.read_text())["passes"] is False
    if typed == "validity_census":
        p = directory/"capacity.jsonl"
        rows = [json.loads(s) for s in p.read_text().splitlines()] if p.exists() else []
        allowed = any(r.get("reporting_guard", {}).get("passes") is False for r in rows)
    return dict(passes=False, technical_repeat_candidate=allowed and not exact,
                exactness_failure=exact, cause=typed, final=False)
