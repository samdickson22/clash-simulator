"""Use T1's SHA-pinned OP-1 through OP-4 guard without SSH or controls."""
import importlib
import json
import os
import sys
import time
from pathlib import Path
from receipts import sha

GUARD_MODULES = ("common", "host_audit", "idle_services", "system_bus", "ssh_transport",
                 "perception_confirmation", "owned_supervisor", "ssh_budget")
GUARD_RULES = "frozen-t1-op1-op2-op3-op4-v1"


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
              "console_user" if console["positive"] else
              "foreign_compute" if jobs else "foreign_active" if busy else
              "op1_interference" if op1 else None)
    return reason, overloaded


class ReportingGuard:
    def __init__(self, bundle, manifest, owned):
        bundle = Path(bundle)
        profile = manifest["reference_load_profile"]
        cfg = profile["guard"]
        freeze = json.loads((bundle/cfg["freeze"]).read_text())
        if manifest["files"].get(cfg["freeze"]) != sha(bundle/cfg["freeze"]):
            raise ValueError("Guard freeze must be SHA-pinned")
        root = bundle/cfg["root"]
        for module in GUARD_MODULES:
            name = module+".py"
            relative = str((root/name).relative_to(bundle))
            expected = freeze["files"]["reports/explore/t1/"+name]
            if manifest["files"].get(relative) != expected or sha(root/name) != expected:
                raise ValueError("Reporting guard is not the frozen final T1 source: "+name)
        sys.path.insert(0, str(root))
        # This runs in the fresh census process, before any research-module imports.
        if any(name in sys.modules for name in GUARD_MODULES):
            raise ValueError("Reporting guard import collision")
        self.audit = importlib.import_module("host_audit")
        self.bus = importlib.import_module("system_bus")
        self.idle = importlib.import_module("idle_services")
        self.confirmation = importlib.import_module("perception_confirmation")
        self.supervisor = importlib.import_module("owned_supervisor")
        self.ssh = importlib.import_module("ssh_budget")
        plan = json.loads((bundle/profile["plan"]).read_text())
        # Point all guard imports at the single pinned reporting/smoke plan.
        for module in (importlib.import_module("common"), self.audit, self.idle, self.confirmation):
            module.plan = lambda: plan
        self.job = Path(cfg["job"])
        self.admissions = {name: (bundle/source, manifest["files"][source]) for name, source in cfg["admissions"].items()}
        if "system-bus-admission.json" not in self.admissions:
            raise ValueError("Existing exact system-bus admission required; no refresh")
        for name in ("idle-services.json", "owned-copier-admission.json", "owned-supervisor-admission.json"):
            if (self.job/name).exists() and name not in self.admissions:
                raise ValueError("Every existing guard admission must be pinned")
        self.owned = owned; self.known = {}; self.current_owned = set()
        self.known_identity = {}
        self.audit.own_process = lambda job, row: (row["pid"] in self.current_owned and
            tuple(row[k] for k in self.supervisor.KEYS) == self.known_identity.get(row["pid"]))
        self.previous = None; self.last = time.monotonic(); self.origin = self.last
        self.overloaded = 0.; self.bus_meter = None; self.idle_meters = None
        self.blocks = {}; self.latest = None
        self.sample_previous = None; self.sample_last = self.last
        self.ssh_sample = dict(cpu_ticks=0,seconds=0.,core_fraction=0.,stop=False)
        self.check_admissions()

    def check_admissions(self):
        for name, (source, expected) in self.admissions.items():
            if sha(source) != expected or sha(self.job/name) != expected:
                raise ValueError("Reporting guard admission identity changed: "+name)

    def __call__(self, row, budget_sample=True):
        self.check_admissions()
        current = self.audit.processes()
        if self.sample_previous is None:
            self.sample_previous = current; self.sample_last = time.monotonic()
        roots = {p for p in self.owned if p > 0} | {os.getpid()}
        self.current_owned = owned_tree(current, roots, self.known)
        # Use the frozen OP-3 identity fields for the explicitly supplied E4
        # tree. A stale T1 job/argv predicate never grants unrelated ownership.
        for r in current:
            if r["pid"] in self.current_owned:
                identity = tuple(r[k] for k in self.supervisor.KEYS)
                old = self.known_identity.setdefault(r["pid"], identity)
                if old != identity:self.current_owned.remove(r["pid"])
        if self.bus_meter is None:
            self.bus_meter = self.bus.begin(self.job, current)
            self.idle_meters = self.idle.begin(self.job, current)
        after, foreign, active, cpu = self.audit.census(self.job, self.previous, block_ids=list(self.blocks))
        # Confirmation can take two seconds; T1 measures the interval AFTER it.
        now = time.monotonic(); dt = max(now-self.last, .001)
        # Extra block checkpoints must not turn T1's one-second burst budget
        # into tiny artificial windows. They update block meters but preserve
        # the independent 1 Hz sample's previous rows and timestamp.
        if budget_sample:
            self.ssh_sample = self.ssh.sample(self.sample_previous, after, max(now-self.sample_last,.001))
            self.sample_previous, self.sample_last = after, now
        ssh_sample = self.ssh_sample
        self.bus.update(self.bus_meter, after); self.idle.update(self.idle_meters, after)
        elapsed = max(now-self.origin, .001)
        bus = self.bus.finish(self.bus_meter, elapsed)
        idle = self.idle.finish(self.idle_meters, elapsed)
        console = self.audit.console(); available = self.audit.memory()
        block_results = {}
        for identity, block in self.blocks.items():
            self.ssh.update(block["ssh_meter"], after)
            self.bus.update(block["bus_meter"], after); self.idle.update(block["idle_meter"], after)
            seconds = max(now-block["started"], .001)
            block_results[identity] = self.ssh.finish(block["ssh_meter"], seconds)
        jobs = [r for r in foreign if not (console["positive"] and r.get("tty", 0))]
        busy = [r for r in active if not (console["positive"] and r.get("tty", 0))]
        reason = ("owned_STOP" if (self.job/"STOP").exists() or (self.job/("STOP-"+os.uname().nodename)).exists()
                  else "memory_floor" if available < 24*2**30 else
                  self.ssh.stop_reason(console,jobs,busy,ssh_sample,list(block_results.values())))
        if reason is None and (bus["interfered"] or bus["retired"] or idle["interfered"]):
            reason = "op1_interference"
        self.previous, self.last = after, now
        row["reporting_guard"] = dict(passes=reason is None, reason=reason, rules=GUARD_RULES, console=console,
            console_over_one_core_seconds=self.overloaded, memavailable_bytes=available,
            foreign_compute=foreign, foreign_active=active, system_bus=bus, idle_services=idle,
            ssh_family_sample=ssh_sample, ssh_family_blocks=block_results,
            ssh_sample_scope="independent-1Hz" if budget_sample else "block-checkpoint-last-1Hz",
            owned_pid_start_ticks={str(pid): self.known[pid] for pid in sorted(self.current_owned)})
        self.latest = row["reporting_guard"]
        return reason

    def begin_block(self, identity):
        if self.blocks:raise ValueError("Reference guard blocks must be serial and disjoint")
        reason = self({},budget_sample=False)
        if reason:return reason
        self.blocks[identity] = dict(started=time.monotonic(), ssh_meter=self.ssh.begin(self.previous),
            bus_meter=self.bus.begin(self.job,self.previous),idle_meter=self.idle.begin(self.job,self.previous))
        return None

    def end_block(self, identity):
        if identity not in self.blocks:raise ValueError("Unknown reference guard block")
        reason = self({},budget_sample=False);block = self.blocks.pop(identity)
        seconds = max(time.monotonic()-block["started"], .001)
        ssh = self.ssh.finish(block["ssh_meter"], seconds)
        bus = self.bus.finish(block["bus_meter"], seconds)
        idle = self.idle.finish(block["idle_meter"], seconds)
        # T1 flags >0.5% without stopping at that boundary. A flagged reference
        # cannot qualify; retain it and fail the attempt, never remove a block.
        if reason is None:
            if ssh["interfered"]:reason = "ssh_family_interference"
            elif bus["interfered"] or bus["retired"] or idle["interfered"]:reason = "op1_interference"
        self.latest.update(passes=reason is None,reason=reason,
            completed_block=dict(id=identity,seconds=seconds,ssh_family=ssh,system_bus=bus,idle_services=idle))
        return reason


def validate_census(rows):
    if len(rows) < 2 or any("reporting_guard" not in row for row in rows):
        raise FleetTechnicalError("validity_census", "Missing reference reporting guard observations")
    failures = [row["reporting_guard"] for row in rows if row["reporting_guard"]["passes"] is not True]
    if failures:
        raise FleetTechnicalError("validity_census", "Reference reporting guard failed: "+str(failures[0]["reason"]))
    if any(row["reporting_guard"].get("rules") != GUARD_RULES or
           "ssh_family_sample" not in row["reporting_guard"] for row in rows):
        raise FleetTechnicalError("validity_census", "Missing frozen OP-4 budget evidence")
    for row in rows:
        g=row["reporting_guard"]
        if g["ssh_family_sample"]["stop"] or any(b["stop"] for b in g.get("ssh_family_blocks",{}).values()) or g.get("console",{}).get("positive"):
            raise FleetTechnicalError("validity_census", "Contradictory passing reference guard")
    return dict(passes=True, observations=len(rows), rules=GUARD_RULES, final=False)


def validate_admission(row):
    guard=row["reporting_guard"]
    if guard.get("passes") is not True or guard.get("rules") != GUARD_RULES:
        raise FleetTechnicalError("validity_census", "Reference host admission failed")
    if guard["console"]["positive"] or guard["memavailable_bytes"] < 24*2**30 or guard["foreign_compute"] or guard["foreign_active"] or guard["ssh_family_sample"]["stop"]:
        raise FleetTechnicalError("validity_census", "Contradictory reference host admission")
    return dict(passes=True,rules=GUARD_RULES)


def validate_blocks(rows, require_measurement=True):
    active = set(); completed = set()
    for row in rows:
        identity = row["id"]; guard = row["reporting_guard"]
        if guard.get("passes") is not True or guard.get("rules") != GUARD_RULES:
            raise FleetTechnicalError("validity_census", "Reference work-block guard failed")
        if row["event"] == "begin":
            if active or identity in completed:raise ValueError("Duplicate/overlapping guard block")
            active.add(identity)
        elif row["event"] == "end":
            if identity not in active:raise ValueError("Missing guard block begin")
            result = guard["completed_block"]
            if result["id"] != identity or result["seconds"] <= 0 or result["ssh_family"]["interfered"] or result["ssh_family"]["stop"]:
                raise FleetTechnicalError("validity_census", "Flagged SSH work block cannot qualify")
            active.remove(identity);completed.add(identity)
        else:raise ValueError("Unknown guard block event")
    if active or not completed:raise FleetTechnicalError("validity_census", "Missing completed reference guard blocks")
    if require_measurement:
        expected={f"speed-{repeat}-{tier}-{offset}" for repeat in range(3)
                  for tier in ("K0c","S","K2","K4") for offset in range(0,300,50)}
        expected.update(f"deadline-{repeat}-{tier}-{cell}-{offset}" for repeat in range(3)
                        for tier in ("K0c","S","K2","K4") for cell in ("1.0","0.8") for offset in range(0,300,50))
        if not expected <= completed or not any(i.startswith("warm-") for i in completed):
            raise FleetTechnicalError("validity_census", "Missing measured/warmup work-block guards")
    return dict(passes=True,blocks=len(completed),rules=GUARD_RULES)


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
        p = directory/"guard-blocks.jsonl"
        if p.exists():rows.extend(json.loads(s) for s in p.read_text().splitlines())
        p = directory/"guard-admission.json"
        if p.exists():rows.append(json.loads(p.read_text()))
        allowed = any(r.get("reporting_guard", {}).get("passes") is False for r in rows)
    return dict(passes=False, technical_repeat_candidate=allowed and not exact,
                exactness_failure=exact, cause=typed, final=False)
