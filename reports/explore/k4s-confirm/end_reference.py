"""PREREG-K4S END reference cells (r3 §4.5 (a)-(c); K4S-SPEC §8). Delta 8. Never launches games.

Runs after the committed reporting-completion receipt, on every host with counted blocks, in reference
slot 0 while every other reporting slot runs the frozen TIERS corpus loop (reporting load profile) through the
K4S-owned background adapter (end_background.K4SFleetBackground: the frozen FleetBackground lifecycle and work loop,
with K4S evidence instead of the frozen 2400/600 TIERS END reader). One run claims the next entry of the END attempt
registry (end_evidence.producer_claim) and writes one sealed per-host receipt directory (scope K4S-END-REFERENCE)
that end_pool.py pools. The registry is not a caller choice: the single committed, append-only END-JOB at the fixed
end_evidence.END_JOB_PATH (end_evidence.end_job) binds the completion, END evidence, plan, counted hosts and frozen
K4S manifest, and claims go only under the fixed end_evidence.REGISTRY_ROOT; the END-JOB must exist before the first
claim, and a round can be claimed only while no finalization record for it (or a later round) is committed. A
later round (r3 §4.5 re-run) can be claimed only after every earlier round's committed pool and original attempt
receipts re-validate and recompute, by end_pool's own code path, as a ratio-only nonconforming pool.

Before the backend is constructed or any pickle is executed (frozen_identity):
  - the TIERS fleet-reference bundle, runtime and measurement pins via the frozen
    tier_backend.validate_bundle (profile fleet-reference); the qualified native SHA;
  - the frozen K4S Mac manifest: kernel (sdefault.py) and scorer (anchor_x.py) = its pins = DELTA-MANIFEST, the
    scorer's normal form = the bundle's TIERS scorer pin, the SD1 manifest (k4s_logic.check_sd1_manifest, nested
    schema, every inference source) = its pin with the bundle's R3a bytes, the T1 K4 corpus SHA, and every END
    measurement source (k4s_logic.END_MEASUREMENT_FILES) = its pin, including the bytes actually executing.
Common pins (k4s_logic.END_FROZEN_PIN_KEYS + END_SHARED_PIN_KEYS) go into end-identity.json and end-raw.json as
"pins"; this host's own bundle manifest SHA and profile host go in "host_pins" (they differ per host by design).

Work units come from TIERS's frozen replay backend through the K4S read-only subclass (mac/k4s_backend.py):
  (a) no-deadline K4 (TierBackend.work 'K4') and K4S (k4s_work), 3 passes over the corpus;
  (b) K4S deadline mode at 200/180/160/140/120 ms with the 1/c poll charge (sleep (1/c - 1) x the pure SD1
      poll span inside the timer), 3 passes; per state: cutoff, no-complete-play, fallback;
  (c) the pure SD1 and v1 poll spans (call to return) on every corpus state.
No-deadline exactness: the K4S result must equal the K4 result on every state (r3 §2.3: K4S == K4).
Each 50-state work block is checkpointed by the frozen T1 reporting guard (TIERS fleet_reference
reference_monitor, 1 Hz census incl. per-processor MHz), the slot masks/priority come from the pinned
reporting plan (frozen fleet_profile.slot_layout), and the 1 Hz MHz is compared with the committed
full-occupancy reporting rows (frozen fleet_end.host_reporting + fleet_profile.compare_mhz).

Failure/cleanup (run_attempt): a failure writes failure.json (typed fleet_technical_cause only for the frozen
FleetTechnicalError); cleanup (monitor stopped first, then joined/terminated, pipes closed, backend closed) always
runs; a cleanup exception writes cleanup-failure.json and, if nothing failed before, a typed "crash" failure.json.
end-complete.json (cleanup_succeeded = true) is written only after cleanup succeeded; the seal is "complete" only then.

  nice -n 10 end_reference.py --bundle B --runtime-root R --native N --corpus K4-states.pkl \
      --k4s-manifest-sha256 S --sd1-manifest-sha256 S --end-evidence E.json --end-evidence-sha256 S \
      --end-job-sha256 S [--round R] --out NEW_DIR
"""
import argparse
import json
import os
import sys
import time
import traceback
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE / "mac"), str(HERE)]      # explicit: `python -I` omits the script directory
import k4s_logic as L  # noqa: E402
import end_pool as P  # noqa: E402
import end_evidence as E  # noqa: E402

CELLS = tuple((Fraction(cell), budget) for cell, budget in L.BUDGET_MS.items())
K4_CORPUS_SHA256 = L.T1_K4_CORPUS_SHA
KERNEL_REL = "reports/explore/k4s-confirm/sdefault.py"
SCORER_REL = "reports/explore/k4s-confirm/anchor_x.py"
MEASUREMENT_FILES = L.END_MEASUREMENT_FILES
MODEL_FILES = ("v1.pt", "R3a.pt", "R3a-calibration.json", "states.pkl")


def charge_scale(cell):
    """Exact 1/c as a rational string, e.g. 10/9 for c = 0.9 (k4s_logic.charge_scale_text)."""
    s = 1/Fraction(cell)
    return str(s.numerator) if s.denominator == 1 else f'{s.numerator}/{s.denominator}'


class Timed:
    """Delegating policy wrapper: records the pure poll span and optionally charges (scale-1) x span inside it."""
    def __init__(self, inner, sleep=time.sleep, clock=time.monotonic):
        self.inner, self.sleep, self.clock = inner, sleep, clock
        self.scale = Fraction(1); self.last_poll = None; self.last_sleep = 0.

    def sample(self, *args, **kwargs):
        t = self.clock(); out = self.inner.sample(*args, **kwargs); self.last_poll = self.clock()-t
        extra = float(self.scale-1)*self.last_poll; self.last_sleep = 0.
        if extra > 0:
            t = self.clock(); self.sleep(extra); self.last_sleep = self.clock()-t
        return out

    def __getattr__(self, name):
        return getattr(self.inner, name)


# ---------------------------------------------------------------- frozen identity (before any backend/pickle)

def frozen_identity(a, validate_bundle, native_sha256, digest=L.sha):
    """Every bundle/native/runtime/kernel/scorer/SD1/corpus/source pin, checked before backend construction.

    Returns (bundle manifest, common pins, host pins). ``digest`` hashes the native and corpus binaries only
    (offline tests substitute stand-ins for those two large artifacts; every other pin is hashed for real)."""
    manifest = validate_bundle(a.bundle, Path(a.runtime_root), dry_run=True, require_references=False)
    P.require(manifest.get("profile") == "fleet-reference", "END requires the reviewed fleet-reference bundle profile")
    P.require(digest(a.native) == native_sha256 == L.NATIVE_PROVENANCE_SHA, "Unqualified native for the END reference")
    P.require(a.corpus_sha256 == L.T1_K4_CORPUS_SHA and digest(a.corpus) == a.corpus_sha256, "K4S END corpus SHA mismatch")
    pins = k4s_pins(a, manifest)
    executing_sources(pins["measurement_files"])
    pins.update(shared_bundle_pins(manifest))
    host_pins = dict(bundle_manifest_sha256=L.sha(Path(a.bundle) / "tiers-pins.json"),
                     bundle_profile_host=manifest["reference_load_profile"]["host"])
    return manifest, pins, host_pins


def shared_bundle_pins(manifest):
    """Bundle pins that must be equal on every counted host (the per-host profile is excluded)."""
    models = {name: manifest["files"].get(name) for name in MODEL_FILES}
    P.require(all(L.is_sha256(v) for v in models.values()), "Bundle lacks a pinned model/state file")
    return dict(bundle_runtime_files_sha256=L.sha_bytes(L.canonical(manifest["runtime_files"]).encode()),
                bundle_measurement_files_sha256=L.sha_bytes(L.canonical(manifest["measurement_files"]).encode()),
                bundle_model_files=models)


def k4s_pins(a, manifest):
    """Frozen common pins (k4s_logic.end_frozen_pins of the frozen K4S manifest) after checking kernel/scorer
    against the manifest and DELTA-MANIFEST, the scorer normal form against the bundle's TIERS scorer pin, SD1
    (nested schema, every inference source) against the bundle's R3a bytes, and every END source file."""
    runtime = Path(a.runtime_root)
    k4s = L.load_k4s_manifest(a.k4s_manifest, a.k4s_manifest_sha256, runtime, require_frozen=True)
    delta = json.loads((HERE / "DELTA-MANIFEST.json").read_text())
    pins = P.expected_pins_from(k4s, a.k4s_manifest_sha256, a.kernel, a.scorer)
    for rel, key in ((a.kernel, "kernel_sha256"), (a.scorer, "scorer_sha256")):
        actual = L.sha(runtime / rel)
        P.require(actual == pins[key] == delta["files"].get(Path(rel).name, {}).get("k4s_sha256"),
                  "K4S kernel/scorer differs from the K4S manifest / DELTA-MANIFEST: " + rel)
    normal = L.sha_bytes(L.scorer_normal_form((runtime / a.scorer).read_bytes()))
    P.require(normal == manifest["runtime_files"].get(L.TIERS_SCORER_REL), "K4S scorer is not the TIERS-qualified scorer")
    P.require(a.sd1_manifest_sha256 == pins["sd1_manifest_sha256"], "SD1 manifest differs from the K4S manifest's")
    L.check_sd1_manifest(a.sd1_manifest, a.sd1_manifest_sha256, runtime, manifest["files"].get("R3a.pt"),
                         manifest["files"].get("R3a-calibration.json"))
    for rel, digest in pins["measurement_files"].items():
        P.require(L.sha(runtime / rel) == digest, "END measurement source differs from its K4S-manifest pin: " + rel)
    return pins


def executing_sources(measurement_files):
    """The END code actually executing in this interpreter is byte-equal to the frozen source pins."""
    import end_background
    import k4s_backend
    modules = {"reports/explore/k4s-confirm/end_reference.py": Path(__file__),
               "reports/explore/k4s-confirm/end_pool.py": Path(P.__file__),
               "reports/explore/k4s-confirm/end_background.py": Path(end_background.__file__),
               "reports/explore/k4s-confirm/end_evidence.py": Path(E.__file__),
               L.MAC_REL + "/k4s_backend.py": Path(k4s_backend.__file__), L.MAC_REL + "/k4s_logic.py": Path(L.__file__)}
    P.require(set(modules) == set(measurement_files), "END measurement-source inventory differs from the executing set")
    for rel, path in modules.items():
        P.require(L.sha(path) == measurement_files[rel], "Executing END source differs from its frozen pin: " + rel)
    return True


def backend(a):
    from k4s_backend import backend_class
    runtime = Path(a.runtime_root)
    be = backend_class()(a.bundle, runtime, a.native, a.corpus, a.corpus_sha256, runtime / a.kernel, runtime / a.scorer)
    be.search_cpus = a.cores
    be.sd1 = Timed(be.sd1); be.v1 = Timed(be.v1)
    return be


# ---------------------------------------------------------------- measurement loop (fake-backend testable)

def measure(be, ids, guarded, set_phase, check, repeats=3, clock=time.monotonic):
    """(a)-(c) in guarded 50-state work blocks: speed-{r}-{offset}, deadline-{r}-{cell}-{offset}."""
    states = {i: dict(k4_wall=[], k4s_wall=[], sd1_poll=[], v1_poll=[]) for i in ids}
    deadline = {cell: dict(budget_ms=budget, charge_scale=L.charge_scale_text(cell), rows=[])
                for cell, budget in L.BUDGET_MS.items()}
    for repeat in range(repeats):
        set_phase("reference-speed")
        for offset in range(0, len(ids), P.BLOCK):
            with guarded(f"speed-{repeat}-{offset}"):
                for identity in ids[offset:offset + P.BLOCK]:
                    check()
                    row, s = be.k4s_rows[identity], states[identity]
                    be.sd1.scale = Fraction(1)
                    k4_result, k4_t = be.work(row, 'K4'); s['v1_poll'].append(be.v1.last_poll); s['k4_wall'].append(k4_t['wall_seconds'])
                    k4s_result, k4s_t = be.k4s_work(row); s['sd1_poll'].append(be.sd1.last_poll); s['k4s_wall'].append(k4s_t['wall_seconds'])
                    if k4s_result != k4_result:
                        raise ValueError('Exactness mismatch: no-deadline K4S != K4 on state ' + identity)
                    if s.setdefault('result', k4s_result) != k4s_result:
                        raise ValueError('Exactness mismatch: repeated no-deadline K4S result on state ' + identity)
        set_phase("reference-deadlines")
        for cell, budget in L.BUDGET_MS.items():
            for offset in range(0, len(ids), P.BLOCK):
                with guarded(f"deadline-{repeat}-{cell}-{offset}"):
                    for identity in ids[offset:offset + P.BLOCK]:
                        check()
                        row = be.k4s_rows[identity]
                        be.sd1.scale = 1/Fraction(cell)
                        be.prepare_work(row)
                        entered = clock()
                        _, t = be.k4s_work(row, deadline=budget/1000, packet_entry=entered)
                        deadline[cell]['rows'].append(dict(
                            id=identity, repeat=repeat, cutoff=bool(t['cutoff']), no_complete_play=bool(t['no_complete_play']),
                            fallback=bool(t['fallback']), wall_seconds=t['wall_seconds'], poll_seconds=be.sd1.last_poll,
                            scale_sleep_seconds=be.sd1.last_sleep))
                be.sd1.scale = Fraction(1)
    return states, deadline


def raw_record(host, pins, host_pins, states, deadline):
    return dict(schema=P.RAW_SCHEMA, host=host, corpus_sha256=pins["corpus_sha256"], repeats=3, pins=pins,
                host_pins=host_pins, states=states, deadline=deadline)


# ---------------------------------------------------------------- attempt lifecycle (failure, cleanup, completion)

def run_attempt(store, body, cleanup, completion, technical=()):
    """body(); cleanup() always; end-complete.json only after a clean body AND a clean cleanup.

    A body failure writes failure.json (``fleet_technical_cause`` only for ``technical`` errors) and is re-raised
    after cleanup. A cleanup exception always writes cleanup-failure.json; if the body had succeeded it also
    writes a typed "crash" failure.json and becomes the raised error, so the seal is "failed", never "complete".
    """
    primary = None
    try:
        body()
    except BaseException as error:
        primary = error
        record = dict(error=traceback.format_exc(), utc=time.time(), fail_closed=True)
        if isinstance(error, technical):
            record["fleet_technical_cause"] = error.cause
        store.write("failure.json", record)
    try:
        cleanup()
    except BaseException as error:
        store.write("cleanup-failure.json", dict(error=traceback.format_exc(), utc=time.time(), fail_closed=True,
                                                 primary_failure=primary is not None))
        if primary is None:
            store.write("failure.json", dict(error=traceback.format_exc(), fleet_technical_cause="crash", cleanup=True,
                                             utc=time.time(), fail_closed=True))
            primary = error
    status = "failed"
    try:
        if primary is None:
            store.write("end-complete.json", dict(completion, cleanup_succeeded=True))
            status = "complete"
    finally:
        store.seal(status)
    if primary is not None:
        raise primary
    return status


def cleanup_steps(state, join_seconds=10):
    """Stop the monitor first (prompt on failure paths), join/terminate it, close both pipe ends, close the
    backend. Every step runs; the first error is raised after all of them."""
    errors = []

    def attempt(step):
        try:
            step()
        except BaseException as error:  # keep going; report the first
            errors.append(error)
    if state.stop is not None:
        attempt(state.stop.set)
    monitor = state.monitor
    if monitor is not None and monitor.pid:
        def stop_monitor():
            monitor.join(join_seconds)
            if monitor.is_alive():
                monitor.terminate()
                monitor.join(join_seconds)
                raise RuntimeError("Reference census process had to be terminated")
        attempt(stop_monitor)
    for end in (state.channel, state.monitor_channel):
        if end is not None:
            attempt(end.close)
    if state.backend is not None:
        attempt(state.backend.close)
    if errors:
        raise errors[0]


# ---------------------------------------------------------------- one host's reference (Linux fleet host only)

def reference(a):
    e4v3 = str(ROOT / L.E4V3_REL)
    sys.path.insert(0, e4v3)
    import multiprocessing as mp
    import end_background as G
    spec = G.evidence_spec(a.end_evidence, a.end_evidence_sha256, a.repository, a.k4s_manifest, a.k4s_manifest_sha256)
    # The frozen K4S manifest and every frozen e4v3 helper pin are verified before any frozen module is imported.
    _, (fleet_end, fleet_profile, fleet_validity) = G.frozen_helpers(spec, a.runtime_root)
    from tier_backend import NATIVE_SHA, validate_bundle
    from fleet_validity import FleetTechnicalError
    manifest, pins, host_pins = frozen_identity(a, validate_bundle, NATIVE_SHA)
    from fleet_reference import reference_monitor
    from telemetry import cpu_counters, validate_physical_cpus, validate_topology
    host_identity = G.FrozenHooks().host()
    profile, plan, (search, background_masks, census_cpu), evidence, reporting = G.k4s_reporting_profile(
        a.bundle, manifest, spec, host_identity, fleet_end, fleet_profile)
    host, nice = host_identity["node"], host_identity["nice"]
    P.require(host_pins["bundle_profile_host"] == host, "Bundle reference profile names a different host")
    validate_physical_cpus(search + sum(background_masks, []) + [census_cpu])
    os.sched_setaffinity(0, set(search))
    a.cores = search
    job = E.end_job(a.repository, evidence, a.end_job_sha256, a.k4s_manifest_sha256)    # before the first claim
    # A later round: every earlier round re-validated by the pool's code path as a ratio-only nonconforming pool.
    context = P.pool_context(P.shared_request(a.k4s_manifest, a.k4s_manifest_sha256, a.corpus_inventory, a.end_evidence,
                                              a.end_evidence_sha256, a.kernel, a.scorer), a.repository) if a.round else None
    claim, claim_sha = E.producer_claim(a.repository, job, a.round, host, a.out,      # before the receipt directory
                                        context=context)
    store = L.K4SStore(a.out, P.REFERENCE_SCOPE)
    state = SimpleNamespace(stop=None, monitor=None, channel=None, monitor_channel=None, backend=None)

    def body():
        store.write("attempt-claim.json", dict(claim=claim, claim_sha256=claim_sha))
        store.write("end-identity.json", dict(
            host=host, utc=time.time(), nice=nice, scheduler="SCHED_OTHER", end_kind=evidence["kind"],
            end_evidence_sha256=evidence["sha256"], counted_hosts=evidence["counted_hosts"],
            plan_sha256=evidence["plan_sha256"], attempt=claim["attempt"], attempt_claim_sha256=claim_sha,
            end_job_sha256=job["sha256"], round=a.round,
            load_profile={k: profile[k] for k in (
                "host", "reference_slot", "slot_count", "console_rule", "warmup_seconds", "perception")},
            search_cpus=search, background_masks=background_masks, census_cpu=census_cpu, pins=pins,
            host_pins=host_pins, final=False, live_actions=False, outcome_access=False))
        store.write("reporting-full-occupancy-mhz.json", dict(rows=reporting))
        be = state.backend = backend(a)       # pickles execute only now, after every pin above matched
        ids = L.check_corpus(a.corpus_sha256, a.corpus_sha256, json.loads(Path(a.corpus_inventory).read_text()), None,
                             list(be.k4s_rows))
        context = mp.get_context("spawn")
        stop, phase = state.stop, context.Array("c", 64)
        owned = context.Array("i", [os.getpid()] + [0] * (len(background_masks) + 1))
        channel, monitor_channel = state.channel, state.monitor_channel = context.Pipe()
        clusters = validate_topology(manifest["topology"], cpu_counters(), darwin=False)
        monitor = state.monitor = context.Process(target=reference_monitor, args=(
            stop, phase, owned, clusters, store.directory / "capacity.jsonl", census_cpu, a.bundle, manifest,
            monitor_channel))

        def check_monitor():
            if not monitor.is_alive():
                raise FleetTechnicalError("crash", "Reference telemetry/guard process stopped")

        def checkpoint(event, identity):
            channel.send(dict(event=event, id=identity, phase=phase.value.decode()))
            limit = time.monotonic() + 60
            while not channel.poll(.1):
                check_monitor()
                if time.monotonic() > limit:
                    raise FleetTechnicalError("crash", "Reference guard checkpoint timed out")
            result = channel.recv()
            if result["event"] != event or result["id"] != identity:
                raise FleetTechnicalError("crash", "Reference guard checkpoint identity mismatch")
            if result["reason"]:
                raise FleetTechnicalError("validity_census", result["reason"])

        @contextmanager
        def guarded(identity):
            checkpoint("begin", identity)
            yield
            checkpoint("end", identity)

        def set_phase(name):
            phase.value = name.encode()
        set_phase("reference-warmup")
        monitor.start(); owned[-1] = monitor.pid
        checkpoint("admit", "reference-admission")
        load = G.K4SFleetBackground(a.bundle, a.runtime_root, a.native, background_masks, spec)
        load.check_external = check_monitor
        with load as background:
            for index, worker in enumerate(background.workers, 1):
                owned[index] = worker.pid
            store.write("slot-evidence.json", dict(
                reference_affinity=sorted(os.sched_getaffinity(0)), reference_nice=os.getpriority(os.PRIO_PROCESS, 0),
                background_affinity=[sorted(os.sched_getaffinity(w.pid)) for w in background.workers],
                background_nice=[os.getpriority(os.PRIO_PROCESS, w.pid) for w in background.workers]))
            warmed, lap, start = 0, 0, time.monotonic()
            until = start + profile["warmup_seconds"]
            while time.monotonic() < until:
                for offset in range(0, len(ids), P.BLOCK):
                    if time.monotonic() >= until:
                        break
                    with guarded(f"warm-{lap}-{offset}"):
                        for identity in ids[offset:offset + P.BLOCK]:
                            if time.monotonic() >= until:
                                break
                            background.check(); check_monitor()
                            be.k4s_work(be.k4s_rows[identity]); warmed += 1
                lap += 1
            store.write("reference-warmup.json", dict(seconds=time.monotonic() - start, reference_slot_work=warmed,
                                                      all_background_slots=len(background_masks), all_slots_active=True))
            states, deadline = measure(be, ids, guarded, set_phase,
                                       lambda: (background.check(), check_monitor()))
        stop.set(); monitor.join(10)
        if monitor.is_alive() or monitor.exitcode != 0:
            raise FleetTechnicalError("crash", "Reference census did not stop cleanly before sealing")
        census = P.read_lines(store.directory / "capacity.jsonl")
        fleet_validity.validate_census(census)
        fleet_validity.validate_admission(json.loads((store.directory / "guard-admission.json").read_text()))
        blocks = P.read_lines(store.directory / "guard-blocks.jsonl")
        fleet_validity.validate_blocks(blocks, require_measurement=False)
        clocks = fleet_profile.compare_mhz(reporting, census, search + sum(background_masks, []), profile["slot_count"])
        store.write("reporting-mhz-comparison.json", clocks)
        if not clocks["passes"]:
            raise FleetTechnicalError("mhz_gate", "Reference/reporting MHz differs by >5%; reference fails closed")
        validate_bundle(a.bundle, a.runtime_root, dry_run=True, require_references=False)
        P.require(L.sha(a.native) == pins["native_sha256"], "Native changed during the END reference")
        executing_sources(pins["measurement_files"])
        store.write("end-raw.json", raw_record(host, pins, host_pins, states, deadline))

    state.stop = mp.get_context("spawn").Event()
    return run_attempt(store, body, lambda: cleanup_steps(state),
                       dict(completed=True, repeats=3, reporting_load_profile=True, poolable=True, outcome_access=False,
                            live_actions=False, host=host, utc=time.time(), final=False),
                       technical=(FleetTechnicalError,))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--bundle', type=Path, required=True); ap.add_argument('--runtime-root', type=Path, required=True)
    ap.add_argument('--native', type=Path, required=True); ap.add_argument('--corpus', type=Path, required=True)
    ap.add_argument('--corpus-sha256', default=K4_CORPUS_SHA256)
    ap.add_argument('--corpus-inventory', type=Path, required=True, help='T1 corpora.json (81f2483e)')
    ap.add_argument('--kernel', default=KERNEL_REL, help='repo-relative K4S kernel under --runtime-root')
    ap.add_argument('--scorer', default=SCORER_REL, help='repo-relative K4S scorer under --runtime-root')
    ap.add_argument('--k4s-manifest', type=Path, default=HERE / 'mac' / L.MANIFEST_NAME)
    ap.add_argument('--k4s-manifest-sha256', required=True)
    ap.add_argument('--sd1-manifest', type=Path, default=HERE / 'SD1-MANIFEST.json')
    ap.add_argument('--sd1-manifest-sha256', required=True)
    ap.add_argument('--end-evidence', type=Path, required=True, help='clasher.k4s.end-evidence.v1 (committed inputs)')
    ap.add_argument('--end-evidence-sha256', required=True)
    ap.add_argument('--repository', type=Path, default=ROOT, help='git checkout holding the evidence commits')
    ap.add_argument('--end-job-sha256', required=True,
                    help='SHA-256 of the committed END-JOB at the fixed end_evidence.END_JOB_PATH')
    ap.add_argument('--round', type=int, default=0, help='END round (0; a re-run under r3 §4.5 needs every earlier '
                                                         'round finalized, its pool and receipts committed, and each '
                                                         're-validated as a ratio-only nonconforming pool)')
    ap.add_argument('--out', type=Path, required=True, help='fresh per-host receipt directory')
    a = ap.parse_args(argv)
    if a.corpus_sha256 != K4_CORPUS_SHA256:
        raise P.PoolError('END requires the frozen T1 K4 speed corpus')
    reference(a)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
