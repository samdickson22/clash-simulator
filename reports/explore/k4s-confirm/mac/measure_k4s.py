#!/usr/bin/env python3
"""PREREG-K4S Mac threshold measurement (r3 §1.4; CONFORMANCE-r2 N2/F-8). Replay only.

A separate script from TIERS's frozen ``measure_tiers.py``, which it never edits. It
imports TIERS's e4v3 helpers read-only, after checking their SHA-256 against
K4S-MAC-MANIFEST.json, and writes only to its own fresh output directory.

Order: it refuses to start unless a sealed TIERS session receipt (path + receipt-manifest
SHA) shows TIERS's complete §7 list on this Mac (or a §7.2 exactness termination), or
standalone mode is explicitly flagged with a coordinator authorization file. The reused
TIERS inputs (K4's 1.0-cell feasibility, the §7.2 verdict with 1/2/4-worker equality) are
read from those receipts, never re-measured.

Exit 0 means the session completed, not that any gate passed. A refusal (exit 3) is not
a session and consumes no repeat. There is no live-input, actuator, client, emulator or
network option.
"""
import argparse
import json
import os
import platform
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import k4s_logic as L  # noqa: E402  (stdlib only)

STEPS = ("K0 preconditions", "K1 corpus exactness + SD1 agreement (unloaded)", "K2 replay load + warm-up",
         "K3 loaded K4S speed + poll span", "K4 deadline mode at 200 ms", "K5 packet decisions, default GC",
         "K6 packet decisions, gc.freeze()", "K7 reduce + seal")


# ---------------------------------------------------------------- measurement loops (backend injected)

class Measurements:
    """K1-K6. Everything that touches torch/native goes through ``backend``; tests use fakes."""

    def __init__(self, backend, store, limits, corpus_ids, fleet_states, *, sample=None, check_load=None,
                 window=None):
        self.backend, self.store, self.limits = backend, store, limits
        self.ids = list(corpus_ids)
        self.fleet = fleet_states
        self.sample = sample or (lambda phase: None)
        self.check_load = check_load or (lambda: None)
        self.window = window
        self.speed_rows, self.poll_rows, self.spans = [], [], []
        self.active_seconds = 0.
        self.exactness_class = "EXACT"

    def corpus_exactness(self, score_exactness):
        """No-deadline K4S (== K4) actions/candidates/scores vs the fleet END (a) result."""
        records = []
        for identity in self.ids[:self.limits["speed"]]:
            row = self.backend.k4s_rows[identity]
            try:
                result, timing = self.backend.k4s_work(row)
                difference = score_exactness(result, self.fleet[identity]["result"], "k4s-corpus/" + identity)
            except ValueError as error:
                if not any(word in str(error) for word in L.TIERS_GATE_FAILURE_WORDS):
                    raise
                records.append(dict(id=identity, exact=False, error=str(error)))
                self.store.append("k4s-corpus-exactness.jsonl", records[-1])
                return dict(passes=False, states=len(records), failed_state=identity, error=str(error))
            if difference:
                self.exactness_class = "ARM64-NEAR-EXACT"
            records.append(dict(id=identity, exact=difference == 0, max_relative_difference=difference))
            self.store.append("k4s-corpus-exactness.jsonl", records[-1])
            self.store.append("k4s-speed-unloaded.jsonl", dict(id=identity, fleet_wall_seconds=self.fleet[identity]["k4s_wall_seconds"],
                                                                **{k: timing[k] for k in ("wall_seconds", "poll_seconds", "cold_poll")}))
            self.sample("K1")
        return dict(passes=True, states=len(records), exactness_class=self.exactness_class)

    def sd1_agreement(self, agreement_ids, references, threshold, agreement_fn):
        comparisons = []
        for identity in agreement_ids[:self.limits["agreement"]]:
            reference = json.loads(L.canonical(references[identity]))
            reference["ranks"] = {int(k): v for k, v in reference["ranks"].items()}
            actual, elapsed = self.backend.infer(identity, "cpu")
            comparison = agreement_fn(reference, actual, threshold)
            comparisons.append(comparison)
            self.store.append("k4s-sd1-agreement.jsonl", dict(id=identity, device="cpu", ms=elapsed * 1000, **comparison))
        return L.sd1_agreement_gate(comparisons)

    def loaded_speed(self):
        """>= limits.speed states and >= speed_seconds, in 50-state blocks, under load."""
        minimum = min(self.limits["speed"], len(self.ids))
        count, block = 0, 0
        while count < minimum or self.active_seconds < self.limits["speed_seconds"]:
            batch = (self.ids[count % len(self.ids):] + self.ids)[:min(50, minimum)]
            start = time.monotonic()
            for identity in batch:
                self.check_load()
                result, timing = self.backend.k4s_work(self.backend.k4s_rows[identity])
                row = dict(id=identity, block=block, fleet_wall_seconds=self.fleet[identity]["k4s_wall_seconds"],
                           wall_seconds=timing["wall_seconds"], poll_seconds=timing["poll_seconds"],
                           cold=timing["cold_poll"], end=time.monotonic())
                self.store.append("k4s-speed-loaded.jsonl", row)
                self.speed_rows.append(row)
                self.poll_rows.append(dict(id=identity, poll_seconds=timing["poll_seconds"], cold=timing["cold_poll"]))
                count += 1
                self.sample("K3")
            end = time.monotonic()
            self.active_seconds += end - start
            if self.window is not None:
                self.spans.append(self.window(start, end))
            block += 1
        return dict(samples=count, blocks=block, active_seconds=self.active_seconds)

    def deadline_corpus(self):
        rows = []
        for identity in self.ids[:self.limits["speed"]]:
            row = self.backend.k4s_rows[identity]
            self.backend.prepare_work(row)
            entered = time.monotonic()
            _, timing = self.backend.k4s_work(row, deadline=.2, packet_entry=entered)
            record = dict(id=identity, deadline_seconds=.2, **{k: v for k, v in timing.items() if k != "coarse_order"})
            rows.append(record)
            self.store.append("k4s-deadline-corpus.jsonl", record)
            self.sample("K4")
        return L.k4s_deadline_rates(rows)


class PacketDecisions:
    """K5/K6: 200 ms K4S decisions on TIERS's sealed replay packets with the GC trace."""

    def __init__(self, backend, store, schedule, trace, wait_until, sample):
        self.backend, self.store, self.schedule = backend, store, schedule
        self.trace, self.wait_until, self.sample = trace, wait_until, sample
        self.polls = []

    def run(self, variant):
        import gc
        from gc_window import WINDOW
        from telemetry import rss
        before, thresholds = rss(), gc.get_threshold()
        if variant == "freeze":
            gc.collect()
            gc.freeze()
        origin = time.monotonic() + .1
        self.backend.activate("K4S")
        for index, packet in enumerate(self.schedule):
            row = self.backend.by_id[packet["id"]]
            self.backend.prepare_work(row)
            due = origin + packet["offset_seconds"]
            self.trace.context = dict(variant=variant, tier="K4S", scheduled_poll_deadline=due,
                                      decision_deadline=due + .2, opportunity=packet["opportunity"])
            self.wait_until(due, "K5" if variant == "default" else "K6")
            entered = time.monotonic()
            self.trace.context["decision_deadline"] = entered + .2
            poll = dict(poll_id=f"{variant}/K4S/{index}", tier="K4S", variant=variant,
                        opportunity=packet["opportunity"], scheduled=due, entered=entered,
                        poll_delay_seconds=max(0., entered - due))
            self.polls.append(poll)
            next_due = origin + self.schedule[index + 1]["offset_seconds"] if index + 1 < len(self.schedule) else None
            with WINDOW:
                result, timing = self.backend.k4s_work(row, deadline=.2, packet_entry=entered)
                self.trace.context["scheduled_poll_deadline"] = next_due
                self.trace.context["decision_deadline"] = next_due + .2 if next_due is not None else None
            self.store.append("k4s-decisions.jsonl" if variant == "default" else "k4s-gc-freeze.jsonl",
                              dict(id=packet["id"], **poll, **{k: v for k, v in timing.items() if k != "coarse_order"},
                                   action=result["action"], return_time=time.monotonic(), **rss()))
            self.sample("K5" if variant == "default" else "K6")
        if variant == "freeze":
            self.store.write("k4s-gc-freeze-rss.json", dict(before=before, after=rss(), thresholds=list(thresholds),
                                                             permanent_generation_count=gc.get_freeze_count(),
                                                             freeze_called_once_after_warmup=True))
            gc.unfreeze()
            if gc.get_threshold() != thresholds:
                raise ValueError("GC thresholds changed during freeze variant")


def gate_inputs(*, gate0, speed, poll, perception, gc_result, mac_deadline, fleet_deadline):
    return dict(gate0=gate0, r_k4s=speed["r"], p10_k4s=speed["p10"], r_inf=poll["r_inf"],
                poll_p99_seconds=poll["p99_seconds"],
                perception=dict(fps=perception["fps"], processed_fraction=perception["processed_fraction"]),
                gc=dict(passes=gc_result["passes"]),
                mac_deadline={k: mac_deadline[k] for k in GATE6_KEYS},
                fleet_deadline={c: {k: v[k] for k in GATE6_KEYS} for c, v in fleet_deadline.items()})


GATE6_KEYS = ("n", "cutoff", "cutoff_count", "no_complete_play", "no_complete_play_count")


def summarize(ctx, *, inputs, mapping, extra, provisional):
    """The k4s-mac-summary.json body: every gate input, the mapping, c_M and status labels."""
    tiers = ctx["tiers"]
    final = L.final_cell(tiers, mapping, ctx["c_star"])
    status = ("DESCRIPTIVE-ONLY (no TIERS inputs; no cell)" if tiers.get("descriptive_only")
              else "DRY-RUN (not Mac evidence)" if ctx["dry_run"] else provisional["label"])
    return dict(status=status, dry_run=ctx["dry_run"], mode=ctx["mode"], provisional=provisional["provisional"],
                provisional_label=provisional["label"], load=ctx.get("load"), labels=ctx.get("labels", []),
                study="PREREG-K4S", prereg_sha256=ctx.get("prereg_sha256"),
                k4s_manifest_sha256=ctx["k4s_manifest_sha256"], tiers_inputs=tiers,
                reused_from_tiers=dict(c_M_1_0="TIERS feasibility.K4 (cell 1.0) from receipts, never re-measured",
                                       gate0="TIERS §7.2 exactness incl. 1/2/4-worker equality from receipts"),
                binding=ctx.get("binding"), gate_inputs=inputs, cell_mapping=mapping, **final,
                kill=L.kill_flags(inputs, tiers), measurements=extra, final=False, mac_qualified=False,
                formal_E4_qualified=False, live_actions=False,
                tiers_untouched="K4S wrote nothing under any TIERS path and never adds to TIERS's minimum")


# ---------------------------------------------------------------- preconditions

def admit_platform(args, system=None, machine=None, host=None):
    system = platform.system() if system is None else system
    machine = platform.machine() if machine is None else machine
    host = platform.node() if host is None else host
    if args.linux_dry_run:
        if args.sam_authorized_replay or system != "Linux" or host not in ("127x03", "127x05"):
            raise L.PreconditionRefusal("Linux dry runs are restricted to 127x03/127x05 without Mac authorization")
    elif not args.sam_authorized_replay or system != "Darwin" or machine != "arm64":
        raise L.PreconditionRefusal("Mac session requires --sam-authorized-replay on Darwin/arm64")


def parse_pairs(paths, shas, label):
    paths, shas = list(paths or []), list(shas or [])
    if len(paths) != len(shas):
        raise L.PreconditionRefusal(label + ": every path needs exactly one SHA-256 argument")
    return list(zip(paths, shas))


def preconditions(args, store, *, environ=None, nice=None, now=None, classify=None, identity=None):
    """K0. Every check runs before any measurement; any failure is a refusal, not a session."""
    environ = os.environ if environ is None else environ
    dry = bool(args.linux_dry_run)
    limits = L.DRY_LIMITS if dry else L.MAC_LIMITS
    admit_platform(args)
    L.check_priority_and_threads(L.getpriority() if nice is None else nice, environ, dry_run=dry)
    runtime = Path(args.runtime_root)
    manifest = L.load_k4s_manifest(args.k4s_manifest, args.k4s_manifest_sha256, runtime, require_frozen=not dry)
    if args.c_star not in ("0.9", "0.8"):
        raise L.PreconditionRefusal("--c-star must be the recorded c* (0.9 or 0.8)")
    if not dry and args.k4s_release_state not in ("sealed", "released"):
        raise L.PreconditionRefusal("Mac session requires --k4s-release-state sealed|released")
    released = args.k4s_release_state == "released"
    review = None
    if args.independent_review:
        if L.sha(args.independent_review) != args.independent_review_sha256:
            raise L.PreconditionRefusal("Independent review receipt SHA mismatch")
        review = json.loads(Path(args.independent_review).read_text())
    priors = []
    for path, digest in parse_pairs(args.prior_classification, args.prior_classification_sha256, "prior classification"):
        if L.sha(path) != digest:
            raise L.PreconditionRefusal("Prior classification SHA mismatch")
        priors.append(dict(json.loads(Path(path).read_text().splitlines()[0]), receipt_sha256=digest))
    repeat = L.check_repeat_admission(priors, released=released, review=review)

    pairs = parse_pairs(args.tiers_receipts, args.tiers_receipt_sha256, "TIERS receipts")
    authorization = None
    if args.standalone:
        authorization = L.check_standalone_authorization(args.coordinator_authorization,
                                                         args.coordinator_authorization_sha256, [s for _, s in pairs])
    elif not pairs:
        raise L.PreconditionRefusal("No TIERS session-completion receipt: K4S runs only after TIERS's complete §7 "
                                    "list (or with --standalone and a coordinator authorization file)")
    if classify is None:
        sys.path.insert(0, str(runtime / L.E4V3_REL))
        from classify_failure import classify as classify  # noqa: PLW0127 (TIERS classifier, read only)
    sessions = [L.read_tiers_session(p, s, require_mac=not dry, classify=classify) for p, s in pairs]
    ctx = dict(dry_run=dry, limits=limits, manifest=manifest, k4s_manifest_sha256=args.k4s_manifest_sha256,
               c_star=args.c_star, repeat=repeat, released=released, authorization=authorization,
               mode="standalone" if args.standalone else "in-session", sessions=sessions,
               prereg_sha256=manifest.get("prereg", {}).get("sha256"))
    if authorization is not None and authorization["descriptive_only"]:
        ctx["tiers"] = dict(gate0=dict(passes=False, parts=dict(tiers_inputs_unavailable=False)),
                            exactness_failure_kind=None, k4_cell_1_0=False, sessions=[], descriptive_only=True)
    else:
        ctx["tiers"] = L.tiers_inputs(sessions, limits["golden"])
    if sessions and not args.standalone:
        L.check_in_session(sessions[0], args.coordinator_lock, L.now_utc() if now is None else now,
                           require_lock=not dry)
    if not dry and sessions:
        current = identity() if identity is not None else __import__("telemetry").identity()
        for session in sessions:
            same = L.same_mac(session["identity"], current)
            if not same["passes"]:
                raise L.PreconditionRefusal("TIERS receipts come from a different Mac: " + ",".join(same["mismatches"]))
    ctx["measure"] = not any(s["state"] == "exactness-terminated" for s in sessions)
    store.write("k4s-preconditions.json", dict(mode=ctx["mode"], repeat=repeat, released=released,
                tiers=ctx["tiers"], authorization=authorization, k4s_manifest_sha256=args.k4s_manifest_sha256,
                c_star=args.c_star, measure=ctx["measure"]))
    return ctx


def stage_inputs(args, ctx, store):
    """Pins that need TIERS's bundle: load rule, scorer/native binding, SD1, corpus, fleet reference."""
    dry = ctx["dry_run"]
    runtime = Path(args.runtime_root)
    if not args.k4s_kernel_rel or not args.k4s_scorer:
        raise L.PreconditionRefusal("--k4s-kernel-rel and --k4s-scorer are required")
    for name in ("tiers_bundle", "native", "corpus", "corpus_inventory", "fleet_reference"):
        if getattr(args, name) is None:
            raise L.PreconditionRefusal("--" + name.replace("_", "-") + " is required")
    sys.path.insert(0, str(runtime / L.E4V3_REL))
    if dry:
        # TIERS's dry-run CPU profile: 05 one search CPU, 03 five; separate replay and background CPUs.
        width = 1 if platform.node() == "127x05" else 5
        cpus = args.search_cpus or []
        if len(set(cpus)) != width or len(cpus) != width or args.load_cpu is None or args.load_cpu in cpus \
                or not args.background_cpus or len(args.background_cpus) != width:
            raise L.PreconditionRefusal("Linux dry run requires TIERS's host-specific physical CPU profile")
        from telemetry import validate_physical_cpus
        validate_physical_cpus(cpus + [args.load_cpu] + args.background_cpus)
        os.sched_setaffinity(0, set(cpus))
    elif args.search_cpus or args.load_cpu is not None or args.background_cpus:
        raise L.PreconditionRefusal("Mac uses inherited QoS; Linux affinity options cannot change Mac scheduling")
    import tier_backend
    from receipts import sha
    if tier_backend.NATIVE_SHA != L.NATIVE_PROVENANCE_SHA or tier_backend.THRESHOLD != L.SD1_THRESHOLD:
        raise L.PreconditionRefusal("TIERS backend constants differ from K4S's frozen identities")
    bundle_sha = sha(Path(args.tiers_bundle) / "tiers-pins.json")
    for session in ctx["sessions"]:
        if session["identity"].get("manifest_sha256") != bundle_sha:
            raise L.PreconditionRefusal("TIERS bundle is not the one the TIERS session measured")
    if bundle_sha != args.tiers_manifest_sha256:
        raise L.PreconditionRefusal("TIERS bundle manifest SHA differs from the argument")
    bundle = tier_backend.validate_bundle(args.tiers_bundle, runtime, dry_run=dry)
    identity = ctx["sessions"][0]["identity"] if ctx["sessions"] else dict(load_label=bundle["load"]["label"])
    ctx["load"] = L.select_load(bundle, identity, dry_run=dry)
    ctx["labels"] = list(ctx["load"]["labels"])
    build = ctx["sessions"][0]["build"] if ctx["sessions"] else None
    ctx["binding"] = L.bind_scorer_and_native(
        tiers_runtime_files=bundle["runtime_files"], runtime_root=runtime, k4s_scorer_rel=args.k4s_scorer,
        native_sha256=sha(args.native), tiers_build=build, tiers_pins_sha256=bundle_sha, dry_run=dry)
    if not ctx["binding"]["passes"] and not ctx["tiers"].get("descriptive_only"):
        raise L.PreconditionRefusal("R5 binding failed: " + "; ".join(ctx["binding"]["reasons"]))
    kernel_pins = ctx["manifest"]["k4s_kernel"].get("files", {})
    for rel, path in ((args.k4s_kernel_rel, args.k4s_kernel_rel), (args.k4s_scorer, args.k4s_scorer)):
        if not dry and kernel_pins.get(rel) != sha(runtime / path):
            raise L.PreconditionRefusal("K4S kernel file is not the manifest-pinned one: " + rel)
    if args.sd1_manifest:
        L.check_sd1_manifest(args.sd1_manifest, args.sd1_manifest_sha256, runtime,
                             bundle["files"].get("R3a.pt"), bundle["files"].get("R3a-calibration.json"))
        if not dry and ctx["manifest"]["sd1_manifest"]["sha256"] != args.sd1_manifest_sha256:
            raise L.PreconditionRefusal("SD1 manifest differs from the K4S manifest's")
    elif not dry:
        raise L.PreconditionRefusal("Mac session requires the frozen SD1 manifest")
    inventory = json.loads(Path(args.corpus_inventory).read_text())
    if sha(args.corpus_inventory) != args.corpus_inventory_sha256:
        raise L.PreconditionRefusal("T1 corpus inventory SHA mismatch")
    publication = None
    if args.corpus_publication:
        if sha(args.corpus_publication) != args.corpus_publication_sha256:
            raise L.PreconditionRefusal("T1 corpus publication SHA mismatch")
        publication = json.loads(Path(args.corpus_publication).read_text())
    if not dry and args.corpus_sha256 != L.T1_K4_CORPUS_SHA:
        raise L.PreconditionRefusal("Mac session requires the frozen T1 K4 speed corpus")
    ids = L.check_corpus(sha(args.corpus), args.corpus_sha256, inventory, publication, None)
    reference = json.loads(Path(args.fleet_reference).read_text())
    if sha(args.fleet_reference) != args.fleet_reference_sha256:
        raise L.PreconditionRefusal("Fleet END reference SHA mismatch")
    ctx["fleet"] = L.check_fleet_reference(reference, args.corpus_sha256, ids, dry_run=dry)
    ctx["fleet_states"] = reference["states"]
    ctx["corpus_ids"] = ids
    ctx["bundle"] = bundle
    store.write("k4s-staging.json", dict(load=ctx["load"], binding=ctx["binding"], tiers_manifest_sha256=bundle_sha,
                corpus_sha256=args.corpus_sha256, fleet_reference_sha256=args.fleet_reference_sha256,
                sd1_manifest_sha256=args.sd1_manifest_sha256, fleet_deadline=ctx["fleet"]["cells"]))
    return ctx


# ---------------------------------------------------------------- session (Mac / Linux dry run)

class Session:
    def __init__(self, args, store, ctx):
        import multiprocessing as mp
        from telemetry import cpu_counters, validate_topology
        self.args, self.store, self.ctx = args, store, ctx
        self.limits = ctx["limits"]
        self.backend = self.worker = self.stop = self.background = self.monitor = None
        self.clusters = validate_topology(ctx["bundle"]["topology"], cpu_counters(), darwin=not ctx["dry_run"])
        context = mp.get_context("spawn")
        self.monitor_stop, self.phase = context.Event(), context.Array("c", 64)
        self.owned_pids = context.Array("i", [os.getpid(), 0, 0, 0, 0])

    def check_load(self):
        if self.monitor is not None and not self.monitor.is_alive():
            raise RuntimeError("1 Hz telemetry process failed")
        if self.background is not None:
            self.background.check()
        if self.worker is not None and (not self.worker.is_alive() or self.stop.is_set()):
            raise RuntimeError("Paced perception process stopped during measurement")

    def sample(self, phase):
        self.phase.value = phase.encode()[:63]
        self.check_load()

    def wait_until(self, deadline, phase):
        while time.monotonic() < deadline:
            self.sample(phase)
            time.sleep(min(.1, max(0., deadline - time.monotonic())))
        self.check_load()

    def load_rows(self):
        path = self.store.directory / "perception-replay.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.endswith("}")]

    def window(self, start, end):
        from receipts import perception_window
        return perception_window(self.load_rows(), start, end, self.ctx["bundle"]["load"]["target_fps"])

    def start_load(self):
        import multiprocessing as mp
        args = self.args
        output = self.store.directory / "perception-replay.jsonl"
        if self.ctx["dry_run"]:
            from replay_load import LinuxBackground
            self.background = LinuxBackground(args.tiers_bundle, args.runtime_root, args.native, output,
                                              args.load_cpu, args.background_cpus)
            self.background.__enter__()
            for index, worker in enumerate(self.background.workers, 1):
                self.owned_pids[index] = worker.pid
        else:
            from replay_load import load_worker
            context = mp.get_context("spawn")
            ready, self.stop = context.Event(), context.Event()
            self.worker = context.Process(target=load_worker, args=(args.tiers_bundle, args.runtime_root,
                                          args.native, False, ready, self.stop, output, None))
            self.worker.start()
            self.owned_pids[1] = self.worker.pid
            start = time.monotonic()
            while not ready.wait(.25):
                self.check_load()
                if time.monotonic() - start > 120:
                    raise RuntimeError("Replay worker did not become ready in 120s")
        self.wait_until(time.monotonic() + self.limits["warmup_seconds"], "K2-warmup")

    def stop_load(self):
        if self.background is not None:
            self.background.close()
            self.background = None
        if self.worker is not None:
            self.stop.set()
            self.worker.join(10)
            if self.worker.is_alive():
                self.worker.terminate()
                self.worker.join(10)
                raise RuntimeError("Replay load did not stop cleanly")
            if self.worker.exitcode != 0:
                raise RuntimeError("Replay worker failed")
            self.worker = None

    def stop_monitor(self):
        if self.monitor is not None:
            self.monitor_stop.set()
            self.monitor.join(10)
            if self.monitor.is_alive():
                self.monitor.terminate()
                self.monitor.join(10)
                raise RuntimeError("Telemetry did not stop cleanly")
            if self.monitor.exitcode != 0:
                raise RuntimeError("Telemetry process failed")
            self.monitor = None

    def pre_session_census(self):
        from receipts import census_average
        start = time.monotonic()
        self.wait_until(start + self.limits["census_seconds"], "K0-census")
        rows = [json.loads(line) for line in (self.store.directory / "capacity.jsonl").read_text().splitlines()
                if line.endswith("}")]
        selected = [r for r in rows if r["phase"] == "K0-census"]
        foreign = {pid: v for pid, v in census_average(selected).items() if v > .2}
        passes = not foreign and len(selected) >= self.limits["census_seconds"] - 2
        self.store.write("k4s-pre-session-census.json", dict(samples=len(selected), foreign_over_point_two_core=foreign,
                                                             passes=passes))
        if not passes:
            raise L.PreconditionRefusal("Exclusive Mac 5-minute quiescence census failed (delay, not a repeat)")

    def run(self):
        import multiprocessing as mp
        import measure_tiers  # read-only reuse of GCTrace
        from receipts import agreement, gc_summary, score_exactness, sha
        from telemetry import command, identity, monitor_worker
        from k4s_backend import backend_class
        args, ctx = self.args, self.ctx
        native_sha = sha(args.native)
        start_table = command(["ps", "-A", "-o", "pid=,comm="])
        self.store.write("k4s-identity.json", dict(**identity(), limits=self.limits, dry_run=ctx["dry_run"],
                         emulator_process_table=start_table, load=ctx["load"], steps=list(STEPS)))
        self.phase.value = b"K0"
        self.monitor = mp.get_context("spawn").Process(target=monitor_worker, args=(
            self.monitor_stop, self.phase, self.owned_pids, self.clusters, self.store.directory / "capacity.jsonl"))
        self.monitor.start()
        self.owned_pids[3] = self.monitor.pid
        if not ctx["dry_run"]:
            self.pre_session_census()
        trace = measure_tiers.GCTrace()
        extra = {}
        with trace:
            self.backend = backend_class()(args.tiers_bundle, args.runtime_root, args.native, args.corpus,
                                           args.corpus_sha256, Path(args.runtime_root) / args.k4s_kernel_rel,
                                           Path(args.runtime_root) / args.k4s_scorer)
            self.backend.search_cpus = args.search_cpus if ctx["dry_run"] else None
            L.check_corpus(args.corpus_sha256, args.corpus_sha256,
                           json.loads(Path(args.corpus_inventory).read_text()), None, list(self.backend.k4s_rows))
            self.store.write("k4s-runtime-versions.json", dict(torch=self.backend.torch.__version__,
                             torch_threads=self.backend.torch.get_num_threads(), sd1_threshold=self.backend.threshold))
            m = Measurements(self.backend, self.store, self.limits, ctx["corpus_ids"], ctx["fleet_states"],
                             sample=self.sample, check_load=self.check_load, window=self.window)
            exact = m.corpus_exactness(score_exactness)
            student_refs = json.loads((Path(args.tiers_bundle) / "student-reference.json").read_text())
            agreement_k4s = m.sd1_agreement(ctx["bundle"]["sets"]["agreement"], student_refs, L.SD1_THRESHOLD, agreement)
            tiers_cpu = [((s["student_agreement"] or {}).get("backends") or {}).get("cpu", {}).get("passes")
                         for s in ctx["sessions"] if s["state"] == "complete"]
            gate0 = dict(ctx["tiers"]["gate0"])
            gate0["parts"] = dict(gate0["parts"], k4s_corpus_exactness=exact["passes"],
                                  sd1_agreement_k4s=agreement_k4s["passes"],
                                  sd1_agreement_tiers_cpu=all(v is True for v in tiers_cpu) if tiers_cpu else True,
                                  r5_binding=ctx["binding"]["passes"])
            gate0["passes"] = all(v is True for v in gate0["parts"].values())
            extra.update(corpus_exactness=exact, sd1_agreement=agreement_k4s)
            inputs = mapping = None
            descriptive = bool(ctx["tiers"].get("descriptive_only"))
            if gate0["passes"] or (descriptive and exact["passes"] and agreement_k4s["passes"]):
                self.start_load()
                extra["loaded_speed"] = m.loaded_speed()
                speed = L.k4s_speed_summary(m.speed_rows, None if ctx["dry_run"] else ctx["corpus_ids"])
                poll = L.poll_summary(m.poll_rows, ctx["fleet_states"], None if ctx["dry_run"] else ctx["corpus_ids"])
                perception = L.perception_aggregate(m.spans, m.active_seconds)
                rates = m.deadline_corpus()
                decisions = PacketDecisions(self.backend, self.store, ctx["bundle"]["packet_schedule"][:self.limits["decisions"]],
                                            trace, self.wait_until, self.sample)
                decisions.run("default")
                default_gc = gc_summary([e for e in trace.events if e["variant"] == "default"],
                                        [p for p in decisions.polls if p["variant"] == "default"])
                probe = gate_inputs(gate0=gate0, speed=speed, poll=poll, perception=perception,
                                    gc_result=dict(passes=True), mac_deadline=rates, fleet_deadline=ctx["fleet"]["cells"])
                eligible_for_freeze = any(all(v for k, v in g.items() if k not in ("5_gc", "6_deadline", "passes"))
                                          for g in L.gate_table(probe).values())
                freeze_gc = None
                if eligible_for_freeze:
                    decisions.run("freeze")
                    freeze_gc = gc_summary([e for e in trace.events if e["variant"] == "freeze"],
                                           [p for p in decisions.polls if p["variant"] == "freeze"])
                gc_result = freeze_gc if freeze_gc is not None and freeze_gc["passes"] else default_gc
                inputs = gate_inputs(gate0=gate0, speed=speed, poll=poll, perception=perception, gc_result=gc_result,
                                     mac_deadline=rates, fleet_deadline=ctx["fleet"]["cells"])
                mapping = L.map_cell(inputs)
                extra.update(speed={k: v for k, v in speed.items()}, poll=poll, perception=perception,
                             deadline_200ms=rates, default_gc=default_gc, freeze_gc=freeze_gc,
                             freeze_variant_run=eligible_for_freeze)
            else:
                mapping = dict(cells=None, provisional_cell=None, gate6_trail=[], c_M_k4s=None, mac_infeasible=True,
                               reason="gate 0 failed; no K4S cell can pass")
                inputs = dict(gate0=gate0, r_k4s=None, p10_k4s=None, r_inf=None, poll_p99_seconds=None,
                              perception=None, gc=None, mac_deadline=None, fleet_deadline=ctx["fleet"]["cells"])
        self.stop_load()
        self.stop_monitor()
        for event in trace.events:
            self.store.append("k4s-gc-trace.jsonl", event)
        capacities = [json.loads(line) for line in (self.store.directory / "capacity.jsonl").read_text().splitlines()
                      if line.endswith("}")]
        extra["technical_failure_candidates"] = dict(
            foreign_over_one_core_over_60_seconds=any(p["foreign_over_one_core_seconds"] > 60
                                                       for r in capacities for p in r["processes"]),
            sampling_gaps=any(r.get("sample_gap_over_3_seconds") for r in capacities))
        end_table = command(["ps", "-A", "-o", "pid=,comm="])
        provisional = L.provisional_status(L.emulator_present(start_table["stdout"]),
                                           L.emulator_present(end_table["stdout"]), False)
        body = summarize(ctx, inputs=inputs, mapping=mapping, extra=extra, provisional=provisional)
        self.store.write("k4s-mac-summary.json", body)
        import tier_backend
        tier_backend.validate_bundle(args.tiers_bundle, args.runtime_root, dry_run=ctx["dry_run"])
        if sha(args.native) != native_sha:
            raise ValueError("Native changed during measurement")
        self.store.write("k4s-complete.json", dict(completed=True, utc=time.time(), final=False, live_actions=False,
                                                    exit_zero_means="session completed, not gate pass"))

    def close(self):
        try:
            self.stop_load()
        finally:
            self.stop_monitor()
            if self.backend is not None:
                self.backend.close()


def write_no_measurement_summary(ctx, store):
    """TIERS ended on a §7.2 exactness failure: gate 0 fails from receipts; nothing to measure."""
    gate0 = ctx["tiers"]["gate0"]
    inputs = dict(gate0=gate0, r_k4s=None, p10_k4s=None, r_inf=None, poll_p99_seconds=None, perception=None,
                  gc=None, mac_deadline=None, fleet_deadline=None)
    mapping = dict(cells=None, provisional_cell=None, gate6_trail=[], c_M_k4s=None, mac_infeasible=True,
                   reason="TIERS §7.2 exactness failure read from receipts")
    body = summarize(ctx, inputs=inputs, mapping=mapping, extra=dict(measured=False),
                     provisional=L.provisional_status(False, False, False))
    store.write("k4s-mac-summary.json", body)
    store.write("k4s-complete.json", dict(completed=True, utc=time.time(), final=False, live_actions=False,
                                          measured=False, exit_zero_means="session completed, not gate pass"))


# ---------------------------------------------------------------- CLI

def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--output", type=Path, required=True, help="fresh K4S-only output directory")
    p.add_argument("--runtime-root", type=Path, default=L.REPO_ROOT)
    p.add_argument("--k4s-manifest", type=Path, default=L.MAC_DIR / L.MANIFEST_NAME)
    p.add_argument("--k4s-manifest-sha256")
    p.add_argument("--sam-authorized-replay", action="store_true")
    p.add_argument("--linux-dry-run", action="store_true")
    p.add_argument("--tiers-receipts", type=Path, action="append", help="TIERS session receipt dir (repeatable)")
    p.add_argument("--tiers-receipt-sha256", action="append", help="its receipt-manifest.json SHA-256")
    p.add_argument("--standalone", action="store_true")
    p.add_argument("--coordinator-authorization", type=Path)
    p.add_argument("--coordinator-authorization-sha256")
    p.add_argument("--coordinator-lock", type=Path)
    p.add_argument("--coordinator-lock-fd", type=int)
    p.add_argument("--k4s-release-state", choices=("sealed", "released"))
    p.add_argument("--independent-review", type=Path)
    p.add_argument("--independent-review-sha256")
    p.add_argument("--prior-classification", type=Path, action="append")
    p.add_argument("--prior-classification-sha256", action="append")
    p.add_argument("--c-star", default="0.9")
    p.add_argument("--tiers-bundle", type=Path)
    p.add_argument("--tiers-manifest-sha256")
    p.add_argument("--native", type=Path)
    p.add_argument("--k4s-kernel-rel", help="repo-relative pinned K4S kernel (full S-default rule)")
    p.add_argument("--k4s-scorer", help="repo-relative scorer module the kernel imports")
    p.add_argument("--sd1-manifest", type=Path)
    p.add_argument("--sd1-manifest-sha256")
    p.add_argument("--corpus", type=Path, help="frozen T1 K4-states.pkl")
    p.add_argument("--corpus-sha256")
    p.add_argument("--corpus-inventory", type=Path, help="T1 corpora.json (81f2483e)")
    p.add_argument("--corpus-inventory-sha256")
    p.add_argument("--corpus-publication", type=Path)
    p.add_argument("--corpus-publication-sha256")
    p.add_argument("--fleet-reference", type=Path, help="pooled fleet END K4S reference (a)-(c)")
    p.add_argument("--fleet-reference-sha256")
    p.add_argument("--search-cpus", type=lambda v: [int(i) for i in v.split(",")], help="Linux dry run only")
    p.add_argument("--load-cpu", type=int, help="Linux dry run only")
    p.add_argument("--background-cpus", type=lambda v: [int(i) for i in v.split(",")], help="Linux dry run only")
    return p


def acquire_lock(args, store):
    if args.linux_dry_run:
        return None
    import fcntl
    if args.coordinator_lock is None:
        raise L.PreconditionRefusal("Mac requires the coordinator's exclusive session lock")
    if args.coordinator_lock_fd is None:
        lock = args.coordinator_lock.open("r+")
    else:
        lock = os.fdopen(os.dup(args.coordinator_lock_fd), "r+")
        if (os.fstat(lock.fileno()).st_dev, os.fstat(lock.fileno()).st_ino) != (
                args.coordinator_lock.stat().st_dev, args.coordinator_lock.stat().st_ino):
            raise L.PreconditionRefusal("Inherited coordinator lock descriptor points at a different file")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    store.write("k4s-coordinator-lock.json", dict(path=str(args.coordinator_lock), receipt=lock.read(),
                                                  pid=os.getpid(), held_exclusively=True))
    return lock


def main(argv=None, **hooks):
    args = build_parser().parse_args(argv)
    scope = "K4S-LINUX-DRY-RUN" if args.linux_dry_run else "K4S-MAC-REPLAY"
    forbidden = L.forbidden_roots(args.runtime_root, args.tiers_receipts or (), args.tiers_bundle)
    try:
        store = L.K4SStore(args.output, scope, forbidden)
    except L.PreconditionRefusal as error:
        print("K4S refused before creating any receipt: " + str(error), file=sys.stderr)
        return 3
    status, session, lock, code = "failed", None, None, 0
    try:
        if sum((args.linux_dry_run, args.sam_authorized_replay)) != 1:
            raise L.PreconditionRefusal("Exactly one of --linux-dry-run / --sam-authorized-replay")
        ctx = preconditions(args, store, **hooks)
        lock = acquire_lock(args, store)
        if not ctx["measure"]:
            write_no_measurement_summary(ctx, store)
        else:
            stage_inputs(args, ctx, store)
            session = Session(args, store, ctx)
            session.run()
        status = "complete"
    except L.PreconditionRefusal as error:
        store.write("refusal.json", dict(error=str(error), cause="precondition-refusal", session=False,
                                         repeat_consumed=False, utc=time.time(), live_actions=False))
        status, code = "refused", 3
    except BaseException:
        store.write("failure.json", dict(error=traceback.format_exc(), utc=time.time(), fail_closed=True,
                                         final=False, live_actions=False))
        raise
    finally:
        try:
            if session is not None:
                session.close()
        except BaseException:
            if status == "complete":
                status = "failed"
                store.write("cleanup-failure.json", dict(error=traceback.format_exc(), fail_closed=True))
                raise
        finally:
            store.seal(status)
            if lock is not None:
                lock.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
