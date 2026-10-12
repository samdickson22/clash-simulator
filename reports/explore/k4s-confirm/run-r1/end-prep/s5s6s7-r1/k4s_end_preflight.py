"""K4S END on-host PREFLIGHT (S5 candidate, RC-2). Non-claiming, non-timing. Never launches games.

Runs on 127x03/127x04 from the final runtime export, the final bundle (a per-preflight variant whose only
difference from the attempt bundle is ``reference_load_profile.guard.job``) and the preflight's OWN fresh guard job.
First, with the stdlib only and before any runtime module is imported: ``git cat-file -e`` of both frozen seed
commits in the guard job's repo/ (coordinator 15:41Z Q3), and the K4S manifest SHA plus the SHA of every END source
the import chain loads against that manifest (k4s_logic.END_MEASUREMENT_FILES). Then it executes, in
end_reference.reference() order, every piece of the END producer that the 05 dry run cannot reach, EXCEPT the claim
and the measurement:

  end_reference.py:285-291  e4v3 path, end_background, evidence_spec, frozen_helpers (K4S manifest + helper pins)
  end_reference.py:292-294  tier_backend.validate_bundle via frozen_identity (bundle, native, corpus, K4S/SD1 pins,
                            executing END sources)
  end_reference.py:297-304  FrozenHooks.host, k4s_reporting_profile (committed evidence, plan, slot_layout with the
                            live nice == 10, host_reporting), validate_physical_cpus, reference-slot affinity
  end_reference.py:305      end_job: ONLY with --end-job-sha256 (read-only git reads); skipped by default because
                            RC-2 runs before the END-JOB is committed
  -- NEVER --               end_reference.py:307-311 pool_context, producer_claim, K4SStore(REFERENCE_SCOPE);
                            end_reference.py:390 measure(); run_attempt / end-complete.json / end-raw.json
  end_reference.py:326-328  backend(a) (native + models + pickles) and check_corpus
  end_reference.py:329-365  validate_topology, frozen fleet_reference.reference_monitor (T1 ReportingGuard), admission
  end_reference.py:366-374  K4SFleetBackground spawn to readiness; slot affinity/nice read back
  end_reference.py:375-387  hold: by default the END warm-up loop verbatim (reference-slot k4s_work, results
                            discarded, 50-state guarded blocks) for --hold-seconds; --no-reference-work holds the
                            background load with --block-seconds guarded idle blocks instead
  end_reference.py:392-406  monitor stop, frozen validate_census / validate_admission / validate_blocks,
                            compare_mhz (informational unless reference work ran), post-run bundle/native/source pins
  end_reference.py:252-279  frozen cleanup_steps

The checkpoint/guarded closures (end_reference.py:338-362) live inside reference() after the claim and cannot be
imported, so they are copied here line for line (only the variable scope differs).

Output: one fresh directory sealed with scope K4S-END-PREFLIGHT (never K4S-END-REFERENCE; the pool cannot read it),
holding capacity.jsonl, guard-admission.json, guard-blocks.jsonl, guard-sources/ and preflight-result.json
(health-only: checks with UTC stamps, cumulative/windowed system-bus %, per-core MHz, sshd-process counts).
It never writes under --attempt-parent, --repository (the registry lives there) or the runtime/bundle.

  nice -n 10 python -B k4s_end_preflight.py run --bundle B --runtime-root R --native N --corpus C \
      --corpus-inventory CI --k4s-manifest-sha256 S --sd1-manifest-sha256 S --end-evidence E \
      --end-evidence-sha256 S --repository REPO --attempt-parent AP --compare-bundle ATTEMPT_BUNDLE \
      --hold-seconds 960 --out NEW_DIR
  python3 -I k4s_end_preflight.py verify-received --receive RECEIVE_DIR     (05 only)
"""
import argparse
import hashlib
import subprocess
import json
import os
import socket
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

SCHEMA = "clasher.k4s.end-preflight.v1"
SCOPE = "K4S-END-PREFLIGHT"
STUDY_REL = "reports/explore/k4s-confirm"
REGISTRY_REL = STUDY_REL + "/end/registry"
HOSTS = ("127x03", "127x04")
MIN_SAMPLES = 60
MIN_HOLD_SECONDS = {"127x03": 60, "127x04": 900}          # RC-2: >= 15 min loaded on 04
BUS_BANDS_PERCENT = (0.3, 0.7)                            # review §3: <=0.3 proceed, >=0.7 coordinator re-rules
WINDOWS_SECONDS = (1, 10, 30, 60, 300)
BLOCK_SECONDS_RANGE = (1, 300)
GUARD_SIDE_FILES = ("allowlist-occurrences.jsonl", "op2-confirmations.jsonl", "ssh-family-occurrences.jsonl",
                    "parent-source-seed-admission.json")    # fleet_reference.py:219
HOLD_PHASE = "preflight-hold"
RECEIVE_BASE = Path("/mpac/sdicks02/k4s-runner/run-r1/preflight-received")
MANIFEST_REL = STUDY_REL + "/mac/K4S-MAC-MANIFEST.json"
END_SOURCES = (STUDY_REL + "/end_reference.py", STUDY_REL + "/end_pool.py", STUDY_REL + "/end_background.py",
               STUDY_REL + "/end_evidence.py", STUDY_REL + "/mac/k4s_backend.py", STUDY_REL + "/mac/k4s_logic.py")
SEED_COMMITS = ("b2f9e25e1002d43cc910a4bb476716cc4cd32623",   # FROZEN-T1 parent_source_seeds (03; 08 join)
                "ce042b9775f80cb495c327b14a4712730ae95c85")   # coordinator 15:41Z Q3: git cat-file -e first


class PreflightRefusal(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PreflightRefusal(message)


def iso(t=None):
    t = time.time() if t is None else t
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".%03dZ" % int((t % 1) * 1000)


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# ---------------------------------------------------------------- check ledger

class Checks:
    """Ordered check records; every check has UTC start/finish, a source citation and pass/error."""

    def __init__(self, clock=time.time):
        self.rows, self.clock = [], clock

    def begin(self, name, source):
        row = dict(name=name, source=source, started_utc=iso(self.clock()), passed=None)
        self.rows.append(row)
        return row

    def end(self, row, **detail):
        row.update(passed=True, finished_utc=iso(self.clock()), **detail)

    def skip(self, name, source, reason):
        self.rows.append(dict(name=name, source=source, started_utc=iso(self.clock()), passed=None,
                              skipped=True, reason=reason))

    def fail_open(self, error):
        for row in self.rows:
            if row["passed"] is None and not row.get("skipped"):
                row.update(passed=False, finished_utc=iso(self.clock()),
                           error="".join(traceback.format_exception_only(type(error), error)).strip())

    def __call__(self, name, source):
        checks = self

        class Scope:
            def __enter__(self):
                self.row = checks.begin(name, source)
                return self.row

            def __exit__(self, kind, error, tb):
                if kind is None:
                    checks.end(self.row)
                return False
        return Scope()

    def all_passed(self):
        return bool(self.rows) and all(r["passed"] is True or r.get("skipped") for r in self.rows)


# ---------------------------------------------------------------- stdlib store (no runtime import needed)

def canonical(value):                                       # = k4s_logic.canonical (k4s_logic.py:106-107)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class Store:
    """Exclusive-creation files in one fresh directory, sealed even on failure. Same file semantics and seal
    format as k4s_logic.K4SStore (k4s_logic.py:1140-1167), but stdlib-only so the result is sealed even when
    the pre-import checks refuse."""

    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=False, exist_ok=False)

    def write(self, name, value):
        with (self.directory / name).open("x") as stream:
            stream.write(canonical(dict(scope=SCOPE, **value)) + "\n")

    def seal(self, status):
        files = {str(p.relative_to(self.directory)): sha_file(p)
                 for p in sorted(self.directory.rglob("*")) if p.is_file()}
        self.write("receipt-manifest.json", dict(status=status, files=files))
        with (self.directory / "receipt-manifest.sha256").open("x") as stream:
            stream.write(sha_file(self.directory / "receipt-manifest.json") + "  receipt-manifest.json\n")


# ---------------------------------------------------------------- pre-import checks (stdlib only)

def guard_repo_commits(bundle, commits=None):
    """Ruling Q3: the guard job's repo/ is a git clone holding both frozen seed commits (parent_source_seed.py:62-69
    runs git show there at admission, after the claim). Reads the guard job from the bundle manifest as JSON."""
    commits = SEED_COMMITS if commits is None else commits
    manifest = json.loads((Path(bundle) / "tiers-pins.json").read_text())
    repo = Path(manifest["reference_load_profile"]["guard"]["job"]) / "repo"
    require((repo / ".git").exists(), "Guard job repo/ is not a git checkout: " + str(repo))
    found = {}
    for commit in commits:
        done = subprocess.run(["git", "-C", str(repo), "cat-file", "-e", commit + "^{commit}"],
                              stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
        found[commit] = done.returncode == 0
    require(all(found.values()), "Guard job repo/ lacks a frozen seed commit: " +
            ",".join(c for c, ok in found.items() if not ok))
    return dict(repo=str(repo), commits=found)


def bootstrap(runtime_root, k4s_manifest_sha256):
    """Before any runtime module is imported: the K4S manifest bytes = the pinned SHA, and every END source that
    the import chain or the executing-source check loads (k4s_logic.END_MEASUREMENT_FILES) = its manifest pin."""
    runtime = Path(runtime_root).resolve()
    raw = (runtime / MANIFEST_REL).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == k4s_manifest_sha256, "K4S manifest SHA mismatch (pre-import)")
    manifest = json.loads(raw)
    require(manifest.get("schema") == "clasher.k4s.mac-manifest.v1", "Unexpected K4S manifest schema")
    pins = {}
    for rel in END_SOURCES:
        pin = (manifest.get("end_files") or {}).get(rel) or (manifest.get("k4s_files") or {}).get(rel)
        path = runtime / rel
        require(isinstance(pin, str) and len(pin) == 64, "K4S manifest lacks a pin for " + rel)
        require(path.is_file() and not path.is_symlink() and runtime in path.resolve().parents,
                "END source missing, linked or outside the runtime: " + rel)
        require(sha_file(path) == pin, "END source differs from its K4S manifest pin (pre-import): " + rel)
        pins[rel] = pin
    return dict(k4s_manifest_sha256=k4s_manifest_sha256, sources=pins)


# ---------------------------------------------------------------- pure argument / host checks

def refusals(host, nice, sched_other, optimized, hold_seconds, min_samples, block_seconds):
    """Reasons to refuse before anything is imported or written (empty list = proceed)."""
    out = []
    if host not in HOSTS:
        out.append("preflight runs only on 127x03/127x04")
    if nice != 10 or not sched_other:
        out.append("preflight must inherit the pinned nice 10 / SCHED_OTHER (fleet_profile.py:13)")
    if optimized:
        out.append("preflight refuses optimized Python (-O)")
    if host in MIN_HOLD_SECONDS and hold_seconds < MIN_HOLD_SECONDS[host]:
        out.append("hold below the RC-2 minimum for " + host)
    if min_samples < MIN_SAMPLES:
        out.append("fewer than 60 guard samples requested")
    if not BLOCK_SECONDS_RANGE[0] <= block_seconds <= BLOCK_SECONDS_RANGE[1]:
        out.append("block seconds outside [1, 300]")
    return out


def isolated(out, forbidden):
    """The preflight directory is fresh and neither inside nor above any forbidden root."""
    out = Path(out).resolve()
    require(not out.exists(), "Preflight output already exists")
    for root in forbidden:
        root = Path(root).resolve()
        require(out != root and root not in out.parents and out not in root.parents,
                "Preflight output overlaps a forbidden root: " + str(root))
    return str(out)


def names_listing(path):
    """Names-only listing (sorted relative paths, no file is opened) and its SHA."""
    path = Path(path)
    if not path.exists():
        return dict(exists=False, entries=0, sha256=None)
    names = sorted(p.relative_to(path).as_posix() + ("/" if p.is_dir() else "") for p in path.rglob("*"))
    return dict(exists=True, entries=len(names), sha256=hashlib.sha256("\0".join(names).encode()).hexdigest())


def bundle_parity(preflight_manifest, attempt_manifest):
    """Per-attempt bundles differ only in reference_load_profile.guard.job (T1 A5 pattern; RC-3)."""
    def strip(m):
        m = json.loads(json.dumps(m))
        job = m["reference_load_profile"]["guard"].pop("job")
        return m, job
    a, job_a = strip(preflight_manifest)
    b, job_b = strip(attempt_manifest)
    require(a == b, "Preflight bundle differs from the attempt bundle beyond guard.job")
    require(job_a != job_b, "Preflight must use its own guard job, not the attempt's")
    return dict(identical_except_guard_job=True, preflight_guard_job=job_a, attempt_guard_job=job_b)


def fresh_guard_job(job, host):
    """No guard side-file or STOP exists yet in the preflight's own guard job (fleet_reference.py:217-226)."""
    job = Path(job)
    require(job.is_dir(), "Guard job missing")
    present = [n for n in GUARD_SIDE_FILES + ("STOP", "STOP-" + host) if (job / n).exists()]
    require(not present, "Guard job is not fresh: " + ",".join(present))
    return dict(guard_job=str(job), fresh=True)


# ---------------------------------------------------------------- health-only summaries

def quantiles(values):
    if not values:
        return None
    s = sorted(values)
    return dict(n=len(s), min=s[0], p50=s[(len(s) - 1) // 2], max=s[-1], mean=sum(s) / len(s))


def bus_series(rows):
    """(monotonic timestamp, cumulative bus ticks, phase) from the frozen guard's per-sample system_bus."""
    out = []
    for r in rows:
        bus = (r.get("reporting_guard") or {}).get("system_bus") or {}
        if "cpu_ticks" in bus and "timestamp" in r:
            out.append((r["timestamp"], bus["cpu_ticks"], r.get("phase")))
    return out


def window_max(series, hz, seconds):
    """Max bus % of one core over the shortest windows spanning >= seconds; flagged with the frozen integer rule
    ticks*100 > hz*elapsed (system_bus.py:30)."""
    best, flagged, count, i = None, 0, 0, -1
    for j in range(len(series)):
        while i + 1 < j and series[j][0] - series[i + 1][0] >= seconds:
            i += 1
        if i < 0 or series[j][0] - series[i][0] < seconds:
            continue
        dt, ticks = series[j][0] - series[i][0], series[j][1] - series[i][1]
        percent = 100. * ticks / hz / dt
        count += 1
        flagged += ticks * 100 > hz * dt
        best = percent if best is None else max(best, percent)
    return dict(window_seconds=seconds, windows=count, max_percent=best, flagged_over_1_percent=flagged)


def cumulative(series, hz):
    if len(series) < 2:
        return None
    dt, ticks = series[-1][0] - series[0][0], series[-1][1] - series[0][1]
    return dict(seconds=dt, cpu_ticks=ticks, percent=100. * ticks / hz / dt if dt > 0 else None)


def band(percent):
    if percent is None:
        return "unavailable"
    low, high = BUS_BANDS_PERCENT
    return ("proceed (<=0.3%)" if percent <= low else "coordinator re-rules (>=0.7%)" if percent >= high
            else "between 0.3% and 0.7%: coordinator judgement")


def bus_summary(rows, hz, loaded_phase=HOLD_PHASE):
    series = bus_series(rows)
    loaded = [s for s in series if s[2] == loaded_phase]
    last = ((rows[-1].get("reporting_guard") or {}).get("system_bus") or {}) if rows else {}
    total = cumulative(series, hz)
    hold = cumulative(loaded, hz)
    return dict(hz=hz, samples=len(series), loaded_samples=len(loaded),
                guard_cumulative_core_fraction_last=last.get("core_fraction"),
                guard_interfered_last=last.get("interfered"), guard_retired_last=last.get("retired"),
                cumulative_all=total, cumulative_loaded=hold,
                windows_all=[window_max(series, hz, w) for w in WINDOWS_SECONDS],
                windows_loaded=[window_max(loaded, hz, w) for w in WINDOWS_SECONDS],
                loaded_band=band(hold and hold["percent"]))


def block_summary(blocks):
    done = [b["reporting_guard"]["completed_block"] for b in blocks
            if b.get("event") == "end" and "completed_block" in (b.get("reporting_guard") or {})]
    bus = [100. * d["system_bus"]["core_fraction"] for d in done if "system_bus" in d]
    return dict(completed=len(done), seconds=quantiles([d["seconds"] for d in done]),
                bus_percent=quantiles(bus),
                flagged_bus=sum(bool(d.get("system_bus", {}).get("interfered")) for d in done),
                flagged_idle=sum(bool(d.get("idle_services", {}).get("interfered")) for d in done),
                flagged_ssh=sum(bool(d.get("ssh_family", {}).get("interfered")) for d in done))


def mhz_summary(rows, cpus, loaded_phase=HOLD_PHASE):
    loaded = [r for r in rows if r.get("phase") == loaded_phase and "cpu_clock_mhz_by_processor" in r]
    means, per_core = [], {str(c): [] for c in cpus}
    for r in loaded:
        clocks = r["cpu_clock_mhz_by_processor"]
        values = [clocks[str(c)] for c in cpus if str(c) in clocks]
        if len(values) == len(cpus):
            means.append(sum(values) / len(values))
        for c in cpus:
            if str(c) in clocks:
                per_core[str(c)].append(clocks[str(c)])
    return dict(occupied_cpus=len(cpus), loaded_samples=len(loaded), occupied_mean_mhz=quantiles(means),
                per_core={c: quantiles(v) for c, v in per_core.items()})


def sshd_summary(rows, loaded_phase=HOLD_PHASE):
    """sshd process count per 1 Hz census row (names only); a rise during the hold means a login."""
    counts = [(r.get("phase"), sum(p.get("name") == "sshd" for p in r.get("processes", []))) for r in rows]
    loaded = [c for phase, c in counts if phase == loaded_phase]
    return dict(all=quantiles([c for _, c in counts]), loaded=quantiles(loaded),
                loaded_first=loaded[0] if loaded else None,
                login_detected_during_hold=bool(loaded) and max(loaded) > loaded[0])


def guard_reasons(rows):
    return sorted({(r.get("reporting_guard") or {}).get("reason") for r in rows} - {None})


def read_lines(path):
    """Complete JSON lines only: a line the live monitor has not finished writing (no newline yet) is skipped."""
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(s) for s in path.read_text().split("\n")[:-1] if s.strip()]


# ---------------------------------------------------------------- frozen modules (imported from the runtime)

class Frozen:
    """The frozen END modules from the runtime export, imported in end_reference.reference() order."""

    def __init__(self, runtime_root):
        here = Path(runtime_root).resolve() / STUDY_REL
        sys.path[:0] = [str(here / "mac"), str(here)]
        import end_reference as ER                       # module import only: k4s_logic, end_pool, end_evidence
        require(Path(ER.__file__).resolve() == here / "end_reference.py", "end_reference not from the runtime")
        sys.path.insert(0, str(ER.ROOT / ER.L.E4V3_REL))  # end_reference.py:285-286
        import end_background as G                        # end_reference.py:288
        for module in (ER, G, ER.L, ER.P, ER.E):           # the very files bootstrap() verified, not shadows/pycs
            require(Path(module.__file__).resolve() in [Path(runtime_root).resolve() / rel for rel in END_SOURCES],
                    "Imported END module is not the verified runtime source: " + module.__name__)
        self.ER, self.G, self.L, self.P, self.E = ER, G, ER.L, ER.P, ER.E

    def bundle_tools(self):                                # end_reference.py:292-293 (after frozen_helpers)
        from tier_backend import NATIVE_SHA, validate_bundle
        from fleet_validity import FleetTechnicalError
        return SimpleNamespace(NATIVE_SHA=NATIVE_SHA, validate_bundle=validate_bundle,
                               FleetTechnicalError=FleetTechnicalError)

    def guard_tools(self):                                 # end_reference.py:295-296 (after frozen_identity)
        from fleet_reference import reference_monitor
        from telemetry import cpu_counters, validate_physical_cpus, validate_topology
        return SimpleNamespace(reference_monitor=reference_monitor, cpu_counters=cpu_counters,
                               validate_physical_cpus=validate_physical_cpus, validate_topology=validate_topology)


def frozen_namespace(a, F):
    """The argparse namespace end_reference.main() would build, with the frozen defaults (end_reference.py:416-437)."""
    ER = F.ER
    return SimpleNamespace(
        bundle=Path(a.bundle), runtime_root=Path(a.runtime_root), native=Path(a.native), corpus=Path(a.corpus),
        corpus_sha256=ER.K4_CORPUS_SHA256, corpus_inventory=Path(a.corpus_inventory), kernel=ER.KERNEL_REL,
        scorer=ER.SCORER_REL, k4s_manifest=ER.HERE / "mac" / F.L.MANIFEST_NAME,
        k4s_manifest_sha256=a.k4s_manifest_sha256, sd1_manifest=ER.HERE / "SD1-MANIFEST.json",
        sd1_manifest_sha256=a.sd1_manifest_sha256, end_evidence=Path(a.end_evidence),
        end_evidence_sha256=a.end_evidence_sha256, repository=Path(a.repository), end_job_sha256=a.end_job_sha256,
        round=0, out=None)


# ---------------------------------------------------------------- the preflight body

def preflight(a, store, checks, F, result, clock=time.monotonic, sleep=time.sleep):
    """Everything of end_reference.reference() except the claim and measure(); fills ``result``."""
    import multiprocessing as mp
    r = frozen_namespace(a, F)
    state = SimpleNamespace(stop=mp.get_context("spawn").Event(), monitor=None, channel=None, monitor_channel=None,
                            backend=None)
    repo_registry = Path(a.repository) / REGISTRY_REL
    result["before"] = dict(registry=names_listing(repo_registry), attempt_parent=names_listing(a.attempt_parent))
    primary = None
    try:
        with checks("frozen_helpers", "end_reference.py:289-291; end_background.py:58-67; end_pool.py:204-217"):
            spec = F.G.evidence_spec(r.end_evidence, r.end_evidence_sha256, r.repository, r.k4s_manifest,
                                     r.k4s_manifest_sha256)
            _, (fleet_end, fleet_profile, fleet_validity) = F.G.frozen_helpers(spec, r.runtime_root)
        with checks("frozen_identity", "end_reference.py:96-110,292-294; tier_backend.py:450-469"):
            T = F.bundle_tools()
            manifest, pins, host_pins = F.ER.frozen_identity(r, T.validate_bundle, T.NATIVE_SHA)
        W = F.guard_tools()
        profile = manifest["reference_load_profile"]
        if a.compare_bundle:
            with checks("bundle_parity", "RC-3; T1 END-A5 per-attempt bundles differ only in guard.job") as row:
                attempt_manifest = json.loads((Path(a.compare_bundle) / "tiers-pins.json").read_text())
                row.update(bundle_parity(manifest, attempt_manifest))
        else:
            checks.skip("bundle_parity", "RC-3", "no --compare-bundle given")
        with checks("guard_job_fresh", "RC-3; fleet_validity.py:86,112-114") as row:
            guard_job = Path(profile["guard"]["job"]).resolve()
            require(guard_job not in store.directory.resolve().parents, "Preflight output inside the guard job")
            row.update(fresh_guard_job(guard_job, socket.gethostname()))
            result["guard_job"] = str(guard_job)
        with checks("reporting_profile", "end_reference.py:297-301; end_background.py:70-87; "
                                         "fleet_profile.py:9-29; fleet_end.host_reporting") as row:
            host_identity = F.G.FrozenHooks().host()
            profile, plan, (search, background_masks, census_cpu), evidence, reporting = \
                F.G.k4s_reporting_profile(r.bundle, manifest, spec, host_identity, fleet_end, fleet_profile)
            host = host_identity["node"]
            require(host_pins["bundle_profile_host"] == host, "Bundle reference profile names a different host")
            row.update(host=host, nice=host_identity["nice"], search_cpus=search, background_slots=len(background_masks),
                       census_cpu=census_cpu, reporting_rows=len(reporting), end_evidence_sha256=evidence["sha256"])
            result["occupied_cpus"] = search + sum(background_masks, [])
        with checks("physical_cpus", "end_reference.py:302-304; telemetry.py:74-88"):
            W.validate_physical_cpus(search + sum(background_masks, []) + [census_cpu])
            os.sched_setaffinity(0, set(search))
            r.cores = search
        if a.end_job_sha256:
            with checks("end_job_read_only", "end_reference.py:305; end_evidence.py:415-432 (git reads only)"):
                F.E.end_job(r.repository, evidence, r.end_job_sha256, r.k4s_manifest_sha256)
        else:
            checks.skip("end_job_read_only", "end_reference.py:305", "RC-2 runs before the END-JOB is committed")
        # NEVER end_reference.py:307-311 (pool_context, producer_claim, K4SStore(REFERENCE_SCOPE)).
        with checks("backend_and_corpus", "end_reference.py:159-165,326-328") as row:
            be = state.backend = F.ER.backend(r)
            ids = F.L.check_corpus(r.corpus_sha256, r.corpus_sha256, json.loads(Path(r.corpus_inventory).read_text()),
                                   None, list(be.k4s_rows))
            row.update(corpus_states=len(ids))
        context = mp.get_context("spawn")
        stop, phase = state.stop, context.Array("c", 64)
        owned = context.Array("i", [os.getpid()] + [0] * (len(background_masks) + 1))
        channel, monitor_channel = state.channel, state.monitor_channel = context.Pipe()
        with checks("topology", "end_reference.py:333; telemetry.py:60-71"):
            clusters = W.validate_topology(manifest["topology"], W.cpu_counters(), darwin=False)
        monitor = state.monitor = context.Process(target=W.reference_monitor, args=(
            stop, phase, owned, clusters, store.directory / "capacity.jsonl", census_cpu, r.bundle, manifest,
            monitor_channel))

        def check_monitor():                                  # end_reference.py:338-340
            if not monitor.is_alive():
                raise T.FleetTechnicalError("crash", "Reference telemetry/guard process stopped")

        def checkpoint(event, identity):                      # end_reference.py:342-353
            channel.send(dict(event=event, id=identity, phase=phase.value.decode()))
            limit = clock() + 60
            while not channel.poll(.1):
                check_monitor()
                if clock() > limit:
                    raise T.FleetTechnicalError("crash", "Reference guard checkpoint timed out")
            reply = channel.recv()
            if reply["event"] != event or reply["id"] != identity:
                raise T.FleetTechnicalError("crash", "Reference guard checkpoint identity mismatch")
            if reply["reason"]:
                raise T.FleetTechnicalError("validity_census", reply["reason"])

        class guarded:                                         # end_reference.py:355-359
            def __init__(self, identity):
                self.identity = identity

            def __enter__(self):
                checkpoint("begin", self.identity)

            def __exit__(self, kind, error, tb):
                if kind is None:
                    checkpoint("end", self.identity)
                return False

        def set_phase(name):                                   # end_reference.py:361-362
            phase.value = name.encode()
        with checks("guard_admission", "end_reference.py:363-365; fleet_reference.py:235-256; "
                                       "fleet_validity.py:53-203") as row:
            set_phase("reference-warmup")
            monitor.start(); owned[-1] = monitor.pid
            checkpoint("admit", "preflight-admission")
            admission = json.loads((store.directory / "guard-admission.json").read_text())
            row.update(admission_utc=iso(admission["utc"]))
            result["admission_epoch"] = admission["utc"]
        ready = checks.begin("background_ready", "end_reference.py:366-374; end_background.py:132-157; "
                                                 "replay_load.py:131-145")
        load = F.G.K4SFleetBackground(r.bundle, r.runtime_root, r.native, background_masks, spec)
        load.check_external = check_monitor
        with load as background:
            for index, worker in enumerate(background.workers, 1):
                owned[index] = worker.pid
            slots = dict(reference_affinity=sorted(os.sched_getaffinity(0)),
                         reference_nice=os.getpriority(os.PRIO_PROCESS, 0),
                         background_affinity=[sorted(os.sched_getaffinity(w.pid)) for w in background.workers],
                         background_nice=[os.getpriority(os.PRIO_PROCESS, w.pid) for w in background.workers])
            result["slot_evidence"] = slots
            require(slots["reference_nice"] == 10 and set(slots["background_nice"]) == {10},
                    "Slot priority read back differs from nice 10")
            require(slots["background_affinity"] == [sorted(m) for m in background_masks],
                    "Background affinity read back differs from the pinned masks")
            checks.end(ready, workers=len(background.workers))
            hold = checks.begin("loaded_hold", "end_reference.py:375-387 (warm-up loop; never measure())")
            set_phase(HOLD_PHASE)
            start = clock()
            until = start + a.hold_seconds
            result["hold_started_utc"] = iso()
            warmed, lap = 0, 0
            if a.reference_work:
                while clock() < until:                         # end_reference.py:377-387 verbatim
                    for offset in range(0, len(ids), F.P.BLOCK):
                        if clock() >= until:
                            break
                        with guarded(f"warm-{lap}-{offset}"):
                            for identity in ids[offset:offset + F.P.BLOCK]:
                                if clock() >= until:
                                    break
                                background.check(); check_monitor()
                                be.k4s_work(be.k4s_rows[identity]); warmed += 1
                    lap += 1
            else:
                while clock() < until:
                    with guarded(f"hold-{lap}"):
                        block_end = min(until, clock() + a.block_seconds)
                        while clock() < block_end:
                            background.check(); check_monitor()
                            sleep(max(0., min(1., block_end - clock())))
                    lap += 1
            rows = read_lines(store.directory / "capacity.jsonl")
            admitted = [x for x in rows if x.get("utc", 0) >= result["admission_epoch"]]
            limit = clock() + 30
            while len(admitted) < a.min_samples and clock() < limit:  # bounded top-up to the sample minimum
                background.check(); check_monitor(); sleep(1.)
                rows = read_lines(store.directory / "capacity.jsonl")
                admitted = [x for x in rows if x.get("utc", 0) >= result["admission_epoch"]]
            require(len(admitted) >= a.min_samples, "Fewer than the required 1 Hz guard samples after admission")
            checks.end(hold, seconds=clock() - start, reference_slot_work=warmed, laps=lap,
                       samples_after_admission=len(admitted))
            result["hold_finished_utc"] = iso()
        with checks("monitor_stop", "end_reference.py:392-394"):
            stop.set(); monitor.join(10)
            if monitor.is_alive() or monitor.exitcode != 0:
                raise T.FleetTechnicalError("crash", "Reference census did not stop cleanly before sealing")
        with checks("frozen_guard_validators", "end_reference.py:395-399; fleet_validity.py:230-283"):
            census = F.P.read_lines(store.directory / "capacity.jsonl")
            fleet_validity.validate_census(census)
            fleet_validity.validate_admission(json.loads((store.directory / "guard-admission.json").read_text()))
            fleet_validity.validate_blocks(F.P.read_lines(store.directory / "guard-blocks.jsonl"),
                                           require_measurement=False)
        source = "end_reference.py:400-403; fleet_profile.py:48-68 (hold rows relabelled reference-speed)"
        with checks("mhz_comparison", source) as row:
            relabelled = [dict(x, phase="reference-speed") if x.get("phase") == HOLD_PHASE else x for x in census]
            clocks = fleet_profile.compare_mhz(reporting, relabelled, search + sum(background_masks, []),
                                               profile["slot_count"])
            row.update(gate=bool(a.reference_work), passes=clocks["passes"],
                       absolute_relative_difference=clocks["absolute_relative_difference"])
            result["mhz_comparison"] = clocks
            require(clocks["passes"] or not a.reference_work, "Preflight/reporting MHz differs by >5%")
        with checks("post_pins", "end_reference.py:404-406"):
            T.validate_bundle(r.bundle, r.runtime_root, dry_run=True, require_references=False)
            require(F.L.sha(r.native) == pins["native_sha256"], "Native changed during the preflight")
            F.ER.executing_sources(pins["measurement_files"])
    except BaseException as error:
        primary = error
        raise
    finally:
        cleanup = checks.begin("cleanup", "end_reference.py:252-279 (frozen cleanup_steps)")
        try:
            F.ER.cleanup_steps(state)
            checks.end(cleanup)
        except BaseException as error:                        # a primary failure is never replaced by cleanup
            cleanup.update(passed=False, finished_utc=iso(), error=traceback.format_exc()[-2000:])
            if primary is None:
                raise
        finally:
            result["after"] = dict(registry=names_listing(repo_registry),
                                   attempt_parent=names_listing(a.attempt_parent))
    return result


def summaries(store_dir, result, hz):
    rows = read_lines(Path(store_dir) / "capacity.jsonl")
    blocks = read_lines(Path(store_dir) / "guard-blocks.jsonl")
    cpus = result.get("occupied_cpus") or []
    return dict(samples=len(rows), bus=bus_summary(rows, hz), blocks=block_summary(blocks),
                mhz=mhz_summary(rows, cpus), sshd=sshd_summary(rows), guard_reasons=guard_reasons(rows + blocks))


def copy_guard_sources(job, directory):
    """Raw health-only guard outputs of the preflight's own guard job (fleet_reference.py:217-226)."""
    copied = []
    for name in GUARD_SIDE_FILES:
        source = Path(job) / name
        if source.is_file():
            target = Path(directory) / "guard-sources" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            copied.append(name)
    return copied


def verdict(checks, result, host):
    """Overall pass: every check passed, no claim/attempt-parent change, and on 04 no login during the hold."""
    unchanged = "before" in result and result.get("before") == result.get("after")
    ok = checks.all_passed() and unchanged
    if host == "127x04":
        ok = ok and result.get("summaries", {}).get("sshd", {}).get("login_detected_during_hold") is False
    return dict(passed=bool(ok), registry_and_attempt_parent_unchanged=unchanged)


def run(a, frozen_factory=Frozen, hostinfo=None):
    hostinfo = hostinfo or dict(host=socket.gethostname(), nice=os.getpriority(os.PRIO_PROCESS, 0),
                                sched_other=os.sched_getscheduler(0) == os.SCHED_OTHER,
                                optimized=bool(sys.flags.optimize))
    reasons = refusals(hostinfo["host"], hostinfo["nice"], hostinfo["sched_other"], hostinfo["optimized"],
                       a.hold_seconds, a.min_samples, a.block_seconds)
    if reasons:
        raise PreflightRefusal("; ".join(reasons))
    isolated(a.out, [a.attempt_parent, a.repository, a.runtime_root, a.bundle] +
             ([a.compare_bundle] if a.compare_bundle else []))
    store = Store(a.out)
    checks = Checks()
    result = dict(schema=SCHEMA, host=hostinfo["host"], started_utc=iso(), claim=False, measure_called=False,
                  timing=False, outcome_access=False, live_actions=False, games=False,
                  reference_work=bool(a.reference_work), hold_seconds=a.hold_seconds, block_seconds=a.block_seconds,
                  min_samples=a.min_samples, python=sys.version.split()[0], nice=hostinfo["nice"],
                  inputs=dict(bundle=str(a.bundle), runtime_root=str(a.runtime_root), native=str(a.native),
                              corpus=str(a.corpus), corpus_inventory=str(a.corpus_inventory),
                              end_evidence=str(a.end_evidence), end_evidence_sha256=a.end_evidence_sha256,
                              k4s_manifest_sha256=a.k4s_manifest_sha256, sd1_manifest_sha256=a.sd1_manifest_sha256,
                              repository=str(a.repository), attempt_parent=str(a.attempt_parent),
                              compare_bundle=str(a.compare_bundle) if a.compare_bundle else None,
                              end_job_sha256=a.end_job_sha256))
    error = None
    try:
        with checks("guard_repo_commits", "coordinator 2026-10-12 15:41Z Q3; t1/parent_source_seed.py:62-69") as row:
            row.update(guard_repo_commits(a.bundle))
        with checks("pre_import_pins", "Sol END-PKG1 r1 (verify before import); k4s_logic.py:831-833") as row:
            row.update(bootstrap(a.runtime_root, a.k4s_manifest_sha256))
        with checks("frozen_import", "end_reference.py:56-61,285-288 (module imports only)"):
            F = frozen_factory(a.runtime_root)
        preflight(a, store, checks, F, result)
    except BaseException as caught:                     # recorded; the seal is "failed"
        error = caught
        checks.fail_open(caught)
        result["error"] = traceback.format_exc()
    result["checks"] = checks.rows
    try:
        result["summaries"] = summaries(store.directory, result, os.sysconf("SC_CLK_TCK"))
    except Exception:                                    # health summaries never prevent the sealed result
        result["summaries"] = {}
        result["summaries_error"] = traceback.format_exc()[-2000:]
    if result.get("guard_job"):
        result["guard_sources"] = copy_guard_sources(result["guard_job"], store.directory)
    result.update(verdict(checks, result, hostinfo["host"]))
    result["finished_utc"] = iso()
    result.pop("admission_epoch", None)
    store.write("preflight-result.json", result)
    store.seal("passed" if result["passed"] else "failed")
    if error is not None and not isinstance(error, Exception):
        raise error
    return 0 if result["passed"] else 1


# ---------------------------------------------------------------- 05: received preflight check (local files only)

def verify_received(root):
    """Seal, transfer and no-claim checks of one pushed preflight; returns the health-only summary."""
    root = Path(root)
    require(root.is_absolute() and root == root.resolve(), "Noncanonical receive path")
    require(root.parent.name in HOSTS and root.parent.parent == RECEIVE_BASE, "Wrong preflight receive namespace")
    require(not (root / "PUSH-FAILED.json").exists() and not (root / "PUSH-FAILED.json").is_symlink(),
            "PUSH-FAILED present")
    for name in ("exit.json", "TRANSFER-COMPLETE.json", "argv.nul", "detach.json", "detach.log"):
        require((root / name).is_file() and not (root / name).is_symlink(), "Missing " + name)
    exit_ = json.loads((root / "exit.json").read_text())
    marker = json.loads((root / "TRANSFER-COMPLETE.json").read_text())
    require(marker["transfer_complete"] is True and marker["host"] == exit_["host"] == root.parent.name
            and marker["attempt"] == exit_["attempt"] == root.name, "Transfer/exit mismatch")
    require(marker["measurement_exit_code"] == exit_["exit_code"], "Transfer/exit code mismatch")
    require(exit_["registry_listing_before"] == exit_["registry_listing_after"], "Registry root changed")
    require(exit_["attempts_listing_before"] == exit_["attempts_listing_after"], "Attempt parent changed")
    data = root / "preflight"
    require(exit_["measurement_exists"] is True and data.is_dir() and not data.is_symlink(), "No preflight directory")
    seal, stamp = data / "receipt-manifest.json", data / "receipt-manifest.sha256"
    require(stamp.read_text().split() == [sha_file(seal), "receipt-manifest.json"], "Seal SHA mismatch")
    manifest = json.loads(seal.read_text())
    require(manifest["scope"] == SCOPE and manifest["status"] in ("passed", "failed"), "Unexpected seal")
    files = manifest["files"]
    for name, digest in files.items():
        rel = Path(name)
        require(not rel.is_absolute() and ".." not in rel.parts and str(rel) == name, "Unsafe sealed name")
        require((data / rel).is_file() and not (data / rel).is_symlink(), "Missing sealed file " + name)
        require(sha_file(data / rel) == digest, "File SHA mismatch: " + name)
    entries = list(data.rglob("*"))
    require(not any(p.is_symlink() for p in entries), "Symlink in preflight")
    require({str(p.relative_to(data)) for p in entries if p.is_file()} ==
            set(files) | {"receipt-manifest.json", "receipt-manifest.sha256"}, "Extra/missing files")
    result = json.loads((data / "preflight-result.json").read_text())
    require((exit_["exit_code"] == 0) == (manifest["status"] == "passed") == (result["passed"] is True),
            "Exit/status/result mismatch")
    require(result["claim"] is False and result["measure_called"] is False and result["host"] == root.parent.name,
            "Preflight result identity mismatch")
    return dict(utc=iso(), host=root.parent.name, attempt=root.name, status=manifest["status"],
                passed=result["passed"], receipt_manifest_sha256=sha_file(seal),
                failed_checks=[c["name"] for c in result["checks"] if c["passed"] is False],
                skipped_checks=[c["name"] for c in result["checks"] if c.get("skipped")],
                bus=result["summaries"]["bus"]["cumulative_loaded"],
                bus_band=result["summaries"]["bus"]["loaded_band"],
                login_detected_during_hold=result["summaries"]["sshd"]["login_detected_during_hold"],
                registry_and_attempt_parent_unchanged=result["registry_and_attempt_parent_unchanged"])


def parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 allow_abbrev=False)
    sub = ap.add_subparsers(dest="command", required=True)
    run_ = sub.add_parser("run", allow_abbrev=False)
    for name in ("--bundle", "--runtime-root", "--native", "--corpus", "--corpus-inventory", "--end-evidence",
                 "--repository", "--attempt-parent", "--out"):
        run_.add_argument(name, type=Path, required=True)
    for name in ("--k4s-manifest-sha256", "--sd1-manifest-sha256", "--end-evidence-sha256"):
        run_.add_argument(name, required=True)
    run_.add_argument("--compare-bundle", type=Path, help="the attempt bundle (parity except guard.job)")
    run_.add_argument("--end-job-sha256", help="only once the END-JOB is committed (read-only end_job check)")
    run_.add_argument("--hold-seconds", type=float, required=True)
    run_.add_argument("--block-seconds", type=float, default=30.)
    run_.add_argument("--min-samples", type=int, default=MIN_SAMPLES)
    run_.add_argument("--no-reference-work", dest="reference_work", action="store_false")
    check = sub.add_parser("verify-received", allow_abbrev=False)
    check.add_argument("--receive", type=Path, required=True)
    return ap


def main(argv=None):
    a = parser().parse_args(argv)
    if a.command == "verify-received":
        require(socket.gethostname() == "127x05" and not sys.flags.optimize, "verify-received runs on 05, not -O")
        summary = verify_received(a.receive)
        with (a.receive / "PREFLIGHT-VERIFIED.json").open("x") as stream:
            stream.write(json.dumps(summary, sort_keys=True) + "\n")
        print(json.dumps(summary, sort_keys=True))
        return 0 if summary["passed"] else 2
    return run(a)


if __name__ == "__main__":
    raise SystemExit(main())
