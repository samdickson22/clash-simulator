#!/usr/bin/env python3
"""D0–D9 replay measurements. No live-input, actuator, or client CLI exists."""
import argparse
import gc
import json
import multiprocessing as mp
import os
from pathlib import Path
import platform
import sys
import time
import traceback

from receipts import (TIERS, ReceiptStore, agreement, agreement_gate, assert_exact,
                      choose_backend, decision_rates, deadline_equivalence, feasible, gc_summary, perception_window,
                      quantiles, sha, speed_summary, score_exactness, belief_exactness, census_average, forward_exception)
from telemetry import Census, cpu_counters, idle_delta, identity, rss, validate_topology
from tier_backend import NATIVE_SHA, TierBackend, validate_bundle

MAC_LIMITS = dict(golden=125, agreement=2000, unloaded=100, speed=300,
                  warmup_seconds=300, capacity_seconds=180, speed_seconds=300,
                  forwards=2000, decisions=1000)
DRY_LIMITS = dict(golden=125, agreement=32, unloaded=16, speed=32,
                  warmup_seconds=2, capacity_seconds=3, speed_seconds=2,
                  forwards=32, decisions=32)


def admit_platform(dry_run, authorized, system=None, machine=None, host=None, nice=None):
    system = platform.system() if system is None else system
    machine = platform.machine() if machine is None else machine
    host = platform.node() if host is None else host
    nice = os.getpriority(os.PRIO_PROCESS, 0) if nice is None else nice
    if dry_run:
        if system != "Linux" or host not in ("127x03", "127x05"):
            raise ValueError("Linux dry runs are restricted to 127x03/127x05")
        if host == "127x03" and nice != 19:
            raise ValueError("127x03 requires nice 19")
        if host == "127x05" and nice != 19:
            raise ValueError("127x05 requires nice 19")
    elif not authorized or system != "Darwin" or machine != "arm64" or nice != 10:
        raise ValueError("Mac session requires --sam-authorized-replay, Darwin/arm64, nice 10")


def validate_counts(manifest, limits, dry_run):
    sets = manifest["sets"]
    for name, count in (("golden", limits["golden"]), ("agreement", limits["agreement"]),
                        ("packets", limits["decisions"])):
        ids = sets[name]
        if len(ids) < count or len(set(ids)) != len(ids):
            raise ValueError("Insufficient/duplicate sealed " + name + " states")
    for tier in TIERS:
        ids = sets["speed"][tier]
        if len(ids) < limits["speed"] or len(set(ids)) != len(ids):
            raise ValueError("Insufficient/duplicate speed corpus: " + tier)
    schedule = manifest["packet_schedule"]
    if [p["id"] for p in schedule] != sets["packets"] or any(
        b["offset_seconds"] <= a["offset_seconds"] for a, b in zip(schedule, schedule[1:])):
        raise ValueError("Packet schedule must match sealed ordered replay packets")
    if not dry_run:
        provenance = manifest["fleet_reference"]
        if provenance["nice"] != 10 or provenance["repeats"] != 3 or provenance.get("pooling") != "raw-host-times-repeat-v1" or not provenance["reporting_load_profile"]:
            raise ValueError("Mac requires three-repeat reporting-load fleet reference")
        hosts = provenance["hosts"]
        if not hosts or len(set(hosts)) != len(hosts):
            raise ValueError("Wrong registered reporting hosts")
        if set(provenance["host_receipts"]) != set(hosts) or any(
            abs(r["relative_to_pooled_median"]-1) > .05 for r in provenance["host_receipts"].values()):
            raise ValueError("Unqualified reporting-host speed")
        if provenance.get("amendment_1") is not True or provenance.get("excluded_hosts") or any(
            not math.isfinite(r["reference_to_reporting_mean"]) or abs(r["reference_to_reporting_mean"]-1) > .05
            for r in provenance["host_receipts"].values()):
            raise ValueError("Mac requires all counted END hosts and signed full-occupancy MHz ratios")
        if not provenance.get("physical_cores") or manifest["load"]["config"]["device"] != "mps":
            raise ValueError("Missing registered fleet core or MPS perception configuration")


class GCTrace:
    def __init__(self):
        self.events, self.starts = [], {}
        self.context = dict(variant="default", tier=None, scheduled_poll_deadline=None,
                            decision_deadline=None, opportunity=False)

    def callback(self, phase, info):
        now, generation = time.monotonic(), info["generation"]
        if phase == "start":
            self.starts[generation] = (now, dict(self.context))
        else:
            start, context = self.starts.pop(generation)
            self.events.append(dict(start=start, end=now, generation=generation,
                                    pid=os.getpid(), **context))

    def __enter__(self):
        gc.callbacks.append(self.callback)
        return self

    def __exit__(self, *unused):
        gc.callbacks.remove(self.callback)


class Session:
    def __init__(self, args, store):
        self.args, self.store = args, store
        self.limits = DRY_LIMITS if args.linux_dry_run else MAC_LIMITS
        self.manifest = validate_bundle(args.bundle, args.runtime_root, dry_run=args.linux_dry_run)
        validate_counts(self.manifest, self.limits, args.linux_dry_run)
        self.backend = None
        self.worker = None
        self.stop = None
        self.speed_rows, self.windows, self.polls = [], {}, []
        self.trace = GCTrace()
        self.exactness_class = "EXACT"
        self.forward_exemptions = {tier: set() for tier in TIERS}
        self.chosen_backend = "cpu"
        self.census = Census()
        self.last_sample = time.monotonic()
        self.last_counters = cpu_counters()
        self.clusters = validate_topology(self.manifest["topology"], self.last_counters,
                                         darwin=not args.linux_dry_run)
        context = mp.get_context("spawn")
        self.monitor_stop, self.phase = context.Event(), context.Array("c", 64)
        self.owned_pids = context.Array("i", [os.getpid(), 0, 0, 0, 0])
        self.monitor = None
        self.background = None

    def sample(self, phase):
        self.phase.value = phase.encode()
        if self.monitor is not None:
            if not self.monitor.is_alive():
                raise RuntimeError("1 Hz telemetry process failed")
            self.check_load()
            return
        now = time.monotonic()
        if now - self.last_sample < 1:
            return
        counters = cpu_counters()
        owned = {os.getpid()}
        if self.worker is not None:
            owned.add(self.worker.pid)
        processes = self.census.sample(owned)
        row = dict(timestamp=now, utc=time.time(), phase=phase, interval_seconds=now-self.last_sample,
                   load_average=os.getloadavg(), processes=processes,
                   **idle_delta(self.last_counters, counters, self.clusters))
        # A >3s sampling gap is retained as possible sleep/stall evidence, not
        # silently removed from timing or treated as a granted repeat session.
        row["sample_gap_over_3_seconds"] = now - self.last_sample > 3
        if not self.args.linux_dry_run:
            from telemetry import command
            row["thermal"] = command(["pmset", "-g", "therm"])
        self.store.append("capacity.jsonl", row)
        self.last_counters, self.last_sample = counters, now
        self.check_load()

    def check_load(self):
        if self.background is not None:
            self.background.check()
        if self.worker is not None and (not self.worker.is_alive() or self.stop.is_set()):
            raise RuntimeError("Paced perception process stopped during measurement")

    def wait_until(self, deadline, phase):
        while time.monotonic() < deadline:
            self.sample(phase)
            time.sleep(min(.1, max(0., deadline-time.monotonic())))
        self.check_load()

    def load_rows(self):
        path = self.store.directory / "perception-replay.jsonl"
        if not path.exists():
            return []
        lines = path.read_text().splitlines()
        # Concurrent writer may have a partial trailing line; no partial frame
        # counts as processed. Final post-join read below requires complete JSON.
        return [json.loads(line) for line in lines if line.endswith("}")]

    def window(self, start, end):
        return perception_window(self.load_rows(), start, end,
                                 self.manifest["load"]["target_fps"])

    def exactness(self):
        refs = json.loads((self.args.bundle / "golden.json").read_text())
        records = []
        for identity_ in self.manifest["sets"]["golden"]:
            row = self.backend.by_id[identity_]
            result = {}
            differences = {}
            for tier in ("K0c", "K1", "K2", "K4"):
                actual = self.backend.golden(row, tier)
                if getattr(self.args,"fleet_reference",False) or getattr(self.args,"linux_dry_run",False):
                    assert_exact(actual,refs[identity_],identity_+"/fleet bit-exact/"+tier)
                difference = score_exactness(actual, refs[identity_], identity_ + "/" + tier)
                if difference:
                    self.exactness_class = "ARM64-NEAR-EXACT"
                differences[tier] = difference
                result[tier] = actual
            assert_exact(result["K1"], result["K2"], identity_ + "/1=2")
            assert_exact(result["K1"], result["K4"], identity_ + "/1=4")
            self.backend.zero_budget(row)
            records.append(dict(id=identity_, score_sha256=__import__("hashlib").sha256(
                json.dumps(result["K1"], sort_keys=True).encode()).hexdigest(),
                workers_equal=True, zero_budget_immutable=True, max_relative_difference=differences))
            if len(records) % 25 == 0:
                print(f"D1 exactness: {len(records)}/125", flush=True)
        self.store.write("exactness-tiers.json", dict(passes=True, states=len(records), records=records))
        refs = json.loads((self.args.bundle / "belief-reference.json").read_text())
        belief_records = []
        for identity_ in self.manifest["sets"]["golden"]:
            for deadline_on in (False, True):
                actual = self.backend.belief_result(self.backend.by_id[identity_], deadline_on)
                difference = belief_exactness(actual, refs[identity_], "belief/posterior/ledger/sampling/RNG/" + identity_)
                if getattr(self.args,"fleet_reference",False) or getattr(self.args,"linux_dry_run",False):
                    assert_exact(actual,refs[identity_],"fleet bit-exact belief/"+identity_)
                if difference:
                    self.exactness_class = "ARM64-NEAR-EXACT"
                belief_records.append(dict(id=identity_, deadline_on=deadline_on, exact=difference == 0,
                    max_relative_difference=difference, history_length=len(self.backend.by_id[identity_]["info"].events)))
            if len(belief_records) % 50 == 0:
                print(f"D1 belief/RNG exactness: {len(belief_records)//2}/125", flush=True)
        self.store.write("belief-exactness.json", dict(passes=True, histories=len(belief_records)//2,
            posterior_weights_cumulative_ledger_samples_rng_exact=True, records=belief_records))

    def student_agreement(self):
        refs = json.loads((self.args.bundle / "student-reference.json").read_text())
        result, records = {}, []
        for device in self.backend.students:
            comparisons = []
            for identity_ in self.manifest["sets"]["agreement"]:
                reference = refs[identity_]
                reference["ranks"] = {int(k): v for k, v in reference["ranks"].items()}
                actual, elapsed = self.backend.infer(identity_, device)
                comparison = agreement(reference, actual, self.manifest["threshold"])
                comparisons.append(comparison)
                records.append(dict(id=identity_, device=device, ms=elapsed*1000, **comparison))
            result[device] = agreement_gate(comparisons)
        if "mps" not in result:
            result["mps"] = dict(passes=False, unavailable=True, reason="MPS unavailable on Linux")
        self.store.write("student-agreement.json", dict(backends=result, records=records))
        return result

    def speed(self, loaded, only=None):
        refs = json.loads((self.args.bundle / "speed-reference.json").read_text())
        minimum = self.limits["speed"] if loaded else self.limits["unloaded"]
        duration = self.limits["speed_seconds"] if loaded else 0
        ids = self.manifest["sets"]["speed"]
        start_all, round_ = time.monotonic(), 0
        tiers = (only,) if only else TIERS
        active_seconds = {tier: 0. for tier in tiers}
        count = {tier: 0 for tier in tiers}
        load_spans = {tier: [] for tier in tiers}
        while any(count[tier] < minimum or active_seconds[tier] < duration for tier in tiers):
            order = (only,) if only else TIERS[round_ % 4:] + TIERS[:round_ % 4]
            for tier in order:
                if count[tier] >= minimum and active_seconds[tier] >= duration:
                    continue
                start = time.monotonic()
                # Registered 50-state blocks; dry runs use their smaller sealed set.
                batch = ids[tier][count[tier] % len(ids[tier]):][:min(50, minimum)]
                for identity_ in batch:
                    self.check_load()
                    actual, timing = self.backend.work(self.backend.by_id[identity_], tier, backend=self.chosen_backend or "cpu")
                    reference = refs[tier][identity_]
                    exempt = False
                    if canonical_result(actual) != canonical_result(reference["result"]):
                        exempt = timing.get("forward") is not None and reference.get("forward") is not None and forward_exception(
                            tier, reference["forward"], timing["forward"], self.manifest["threshold"])
                        if exempt:
                            # Proposal differences change the candidate set. Scores
                            # for every common candidate must still be near-exact.
                            old_scores = dict(zip(reference["result"]["candidates"],reference["result"]["scores"]))
                            from receipts import near_floats
                            for a,v in zip(actual["candidates"],actual["scores"]):
                                if a in old_scores:
                                    near_floats(v,old_scores[a],"speed/common-score")
                            self.forward_exemptions[tier].add(identity_)
                        else:
                            score_exactness(actual, reference["result"], "speed/" + tier + "/" + identity_)
                    row = dict(tier=tier, id=identity_, round=round_, loaded=loaded,
                               fleet_wall_seconds=reference["wall_seconds"],
                               wall_seconds=timing["wall_seconds"], end=time.monotonic(),
                               backend=self.chosen_backend or "cpu", forward_equality_exempt=exempt)
                    self.store.append("speed-loaded.jsonl" if loaded else "speed-unloaded.jsonl", row)
                    if loaded:
                        self.speed_rows.append(row)
                    count[tier] += 1
                    self.sample("D5" if loaded else "D3")
                end = time.monotonic()
                active_seconds[tier] += end-start
                if loaded:
                    load_spans[tier].append(self.window(start, end))
            round_ += 1
        if loaded:
            for tier, spans in load_spans.items():
                processed = sum(s["processed"] for s in spans)
                expected = sum(s["expected"] for s in spans)
                fps = processed / active_seconds[tier]
                self.windows[tier] = dict(processed=processed, expected=expected,
                    fps=fps, processed_fraction=min(1., processed/expected),
                    active_seconds=active_seconds[tier], spans=spans,
                    passes=fps >= 18 and processed/expected >= .95)
        self.store.write(("loaded-windows-"+only+".json" if only else "loaded-windows.json") if loaded else "unloaded-windows.json",
            dict(start=start_all, end=time.monotonic(), active_seconds=active_seconds,
                 samples=count, rotated_rounds=round_, perception=self.windows if loaded else None))

    def start_load(self):
        if self.args.linux_dry_run:
            from replay_load import LinuxBackground
            self.background = LinuxBackground(self.args.bundle, self.args.runtime_root, self.args.native,
                self.store.directory / "perception-replay.jsonl", self.args.load_cpu, self.args.background_cpus)
            self.background.__enter__()
            for index, worker in enumerate(self.background.workers, 1):
                self.owned_pids[index] = worker.pid
        else:
            self.start_mac_load()
        self.wait_until(time.monotonic() + self.limits["warmup_seconds"], "D4-warmup")
        self.wait_until(time.monotonic() + self.limits["capacity_seconds"], "D4-capacity")

    def start_mac_load(self):
        from replay_load import load_worker
        context = mp.get_context("spawn")
        ready, self.stop = context.Event(), context.Event()
        self.worker = context.Process(target=load_worker, args=(self.args.bundle, self.args.runtime_root,
            self.args.native, self.args.linux_dry_run, ready, self.stop,
            self.store.directory / "perception-replay.jsonl", self.args.load_cpu))
        self.worker.start()
        self.owned_pids[1] = self.worker.pid
        start = time.monotonic()
        while not ready.wait(.25):
            self.check_load()
            if time.monotonic() - start > 120:
                raise RuntimeError("Replay worker did not become ready in 120s")

    def forwards(self):
        summaries, perception = {}, {}
        for device in self.backend.students:
            # A fresh spawned interpreter gives a genuine first forward, while
            # the independently spawned perception process remains active.
            context = mp.get_context("spawn")
            output = self.store.directory / ("forward-" + device + ".jsonl")
            worker = context.Process(target=forward_worker, args=(self.args.bundle, self.args.runtime_root,
                self.args.native, self.args.linux_dry_run, device,
                self.manifest["sets"]["agreement"][:self.limits["forwards"]], output,
                self.args.search_cpus))
            start = time.monotonic()
            worker.start()
            self.owned_pids[4] = worker.pid
            try:
                deadline = start + 600
                while worker.is_alive():
                    if time.monotonic() > deadline:
                        raise RuntimeError("Student forward child exceeded 10 minutes")
                    self.sample("D6/" + device)
                    self.check_load()
                    worker.join(.1)
                if worker.exitcode != 0:
                    raise RuntimeError("Student forward child failed: " + device)
            finally:
                if worker.is_alive():
                    worker.terminate()
                    worker.join(10)
                self.owned_pids[4] = 0
            end = time.monotonic()
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            warm = [r["ms"] for r in rows if not r["cold"]]
            summaries[device] = quantiles(warm)
            window = self.window(rows[0]["start"], rows[-1]["end"])
            # Short Linux windows have too few paced frames for a p95. Retain
            # missing evidence; they cannot establish the MPS selection rule.
            perception[device] = window["service_ms"]["p95"] if window["service_ms"] else float("inf")
            for row in rows:
                self.store.append("student-forward.jsonl", row)
            self.store.write("forward-window-" + device + ".json", dict(
                window=window, process_start=start, process_end=end, warm_ms=summaries[device], cold_ms=rows[0]["ms"]))
        return summaries, perception

    def decisions(self, tier, variant):
        from gc_window import WINDOW
        schedule = self.manifest["packet_schedule"][:self.limits["decisions"]]
        before = rss()
        thresholds = gc.get_threshold()
        if variant == "freeze":
            # The tier has already completed loaded speed and default decisions.
            gc.collect()
            gc.freeze()
        origin = time.monotonic() + .1
        self.backend.activate(tier)
        for index, packet in enumerate(schedule):
            identity_ = packet["id"]
            # Loading the previously sealed state happens before packet arrival.
            self.backend.prepare_work(self.backend.by_id[identity_])
            due = origin + packet["offset_seconds"]
            self.trace.context = dict(variant=variant, tier=tier, scheduled_poll_deadline=due,
                                     decision_deadline=due+.2, opportunity=packet["opportunity"])
            self.wait_until(due, "D7" if variant == "default" else "D8")
            entered = time.monotonic()
            self.trace.context["decision_deadline"] = entered+.2
            poll_id = f"{variant}/{tier}/{index}"
            poll = dict(poll_id=poll_id, tier=tier, variant=variant, opportunity=packet["opportunity"],
                        scheduled=due, entered=entered, poll_delay_seconds=max(0., entered-due))
            self.polls.append(poll)
            with WINDOW:
                result, timing = self.backend.work(self.backend.by_id[identity_], tier,
                    deadline=.2, backend=self.chosen_backend or "cpu", packet_entry=entered)
                next_due = origin+schedule[index+1]["offset_seconds"] if index+1 < len(schedule) else None
                self.trace.context["scheduled_poll_deadline"] = next_due
                self.trace.context["decision_deadline"] = next_due+.2 if next_due is not None else None
            self.store.append("decisions-tiers.jsonl" if variant == "default" else "gc-freeze.jsonl",
                dict(id=identity_, **poll, **timing, action=result["action"],
                     return_time=time.monotonic(), **rss()))
            # Maintenance after a return is compared to the NEXT scheduled poll.
            next_due = origin+schedule[index+1]["offset_seconds"] if index+1 < len(schedule) else None
            self.trace.context["scheduled_poll_deadline"] = next_due
            self.trace.context["decision_deadline"] = next_due+.2 if next_due is not None else None
            self.sample("D7" if variant == "default" else "D8")
        if variant == "freeze":
            after = rss()
            self.store.write("gc-freeze-rss-"+tier+".json", dict(tier=tier, before=before, after=after,
                permanent_generation_count=gc.get_freeze_count(), thresholds=list(thresholds),
                freeze_called_once_after_warmup=True))
            gc.unfreeze()
            if gc.get_threshold() != thresholds:
                raise ValueError("GC thresholds changed during freeze variant")

    def run(self):
        self.store.write("tiers-identity.json", dict(**identity(), limits=self.limits,
            specification=self.manifest["specification"],
            manifest_sha256=sha(self.args.bundle / "tiers-pins.json"),
            load_label=self.manifest["load"]["label"], emulator_process_table=__import__("telemetry").command(["ps", "-A", "-o", "pid=,comm="]),
            dry_run=self.args.linux_dry_run, max_owned_processes=5,
            physical_core_configuration=self.args.search_cpus, replay_load_cpu=self.args.load_cpu))
        native_sha = sha(self.args.native)
        build = json.loads((self.args.native.parent / "build-tiers.json").read_text())
        if build["native_sha256"] != native_sha:
            raise ValueError("Native build receipt SHA mismatch")
        if self.args.linux_dry_run:
            if native_sha != NATIVE_SHA:
                raise ValueError("Linux dry run requires frozen provenance native")
        elif build.get("target") != "aarch64-apple-darwin" or build.get("rustflags") != "" or not build.get("locked"):
            raise ValueError("Requires fresh --locked native arm64 build with empty RUSTFLAGS")
        if build["source_manifest_sha256"] != sha(self.args.bundle / "tiers-pins.json"):
            raise ValueError("Native source manifest binding differs")
        self.store.write("build-tiers.json", build)
        from telemetry import monitor_worker
        self.phase.value = b"D0"
        self.monitor = mp.get_context("spawn").Process(target=monitor_worker, args=(self.monitor_stop,
            self.phase, self.owned_pids, self.clusters, self.store.directory / "capacity.jsonl"))
        self.monitor.start()
        self.owned_pids[3] = self.monitor.pid
        if not self.args.linux_dry_run:
            self.pre_session_census()
        with self.trace:
            self.backend = TierBackend(self.args.bundle, self.args.runtime_root, self.args.native)
            self.backend.search_cpus = self.args.search_cpus
            self.store.write("runtime-versions.json",dict(torch=self.backend.torch.__version__,
                numpy=self.backend.np.__version__,torch_threads=self.backend.torch.get_num_threads(),
                torch_interop_threads=self.backend.torch.get_num_interop_threads(),
                environment={k:os.environ.get(k) for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS")}))
            if not self.args.linux_dry_run:
                from corpus_contract import validate_capture_receipt
                self.store.write("corpus-capture.json",validate_capture_receipt(self.args.bundle,self.manifest,self.backend))
                for identity_ in self.manifest["sets"]["packets"]:
                    row = self.backend.by_id[identity_]
                    from corpus_contract import validate_row
                    validate_row(row)
                from fleet_reference import validate_row
                for tier in TIERS:
                    for identity_ in self.manifest["sets"]["speed"][tier]:
                        validate_row(self.backend.by_id[identity_],tier)
                origin = self.manifest["packet_schedule"][0]["timestamp_seconds"]
                for packet in self.manifest["packet_schedule"]:
                    row = self.backend.by_id[packet["id"]]
                    if row["info"].tick != packet["tick"] or packet["offset_seconds"] != packet["timestamp_seconds"]-origin:
                        raise ValueError("Poll schedule does not come from sealed packet timestamps")
            self.exactness()  # Any mismatch terminates the session, before timing.
            agreement_results = self.student_agreement()
            self.speed(False)
            self.start_load()
            self.speed(True)
            speeds = speed_summary(self.speed_rows)
            deadline_results = self.deadline_corpus(speeds)
            forwards, perception = self.forwards()
            self.chosen_backend = choose_backend(agreement_results, forwards, perception)
            if self.chosen_backend == "mps":
                # CPU remains the pre-selection D5/D5b baseline. The admitted
                # backend receives its own complete D5/D5b evidence under load.
                self.store.write("S-cpu-speed-baseline.json", dict(speed=speeds["S"], deadline=deadline_results["S"]))
                self.speed_rows = [r for r in self.speed_rows if r["tier"] != "S"]
                self.forward_exemptions["S"].clear()
                self.speed(True, only="S")
                speeds = speed_summary(self.speed_rows)
                deadline_results.update(self.deadline_corpus(speeds, only="S"))
            for tier in TIERS:
                if tier == "S" and self.chosen_backend is None:
                    self.store.write("S-decisions-skipped.json", dict(reason="No admitted student backend"))
                    continue
                self.decisions(tier, "default")
            default_gc = {tier: gc_summary([e for e in self.trace.events if e["variant"] == "default"],
                [p for p in self.polls if p["tier"] == tier and p["variant"] == "default"]) for tier in TIERS}
            # D8 admission excludes GC, so a default-GC failure cannot prevent
            # the registered freeze variant from being evaluated.
            candidates = [tier for tier in TIERS if feasible(speeds[tier], self.windows[tier], True,
                {"passes": True}, tier != "S" or self.chosen_backend is not None,
                1.)["feasible"] and self.corpus_exact(tier)]
            for tier in candidates:
                self.decisions(tier, "freeze")
            if not candidates:
                self.store.write("gc-freeze-skipped.json", dict(reason="No tier passes non-GC feasibility gates"))
            freeze_gc = {tier: gc_summary([e for e in self.trace.events if e["variant"] == "freeze"],
                [p for p in self.polls if p["variant"] == "freeze" and p["tier"] == tier]) for tier in TIERS}
        self.stop_load()
        self.stop_monitor()
        for event in self.trace.events:
            overlapping = [p for p in self.polls if p["variant"] == event["variant"] and
                           p["tier"] == event["tier"] and event["start"] <= p["scheduled"] < event["end"]]
            self.store.append("gc-trace.jsonl", dict(**event,
                overlapping_poll_ids=[p["poll_id"] for p in overlapping],
                resulting_poll_delay_ms=max((p["poll_delay_seconds"]*1000 for p in overlapping), default=0.)))
        capacities = [json.loads(line) for line in (self.store.directory / "capacity.jsonl").read_text().splitlines()]
        free = {c: quantiles([r["free_"+c] for r in capacities if r["phase"] == "D4-capacity"])
                for c in ("P", "E")}
        self.store.write("tiers-summary.json", dict(dry_run=self.args.linux_dry_run,
            fleet_signed_reference_to_reporting_mean={h:r["reference_to_reporting_mean"] for h,r in self.manifest.get("fleet_reference",{}).get("host_receipts",{}).items() if "reference_to_reporting_mean" in r},
            mac_qualified=False, speed=speeds, exactness_class=self.exactness_class,
            forward_exemptions={t:dict(n=len(ids), fraction=len(ids)/len(self.manifest["sets"]["speed"][t])) for t,ids in self.forward_exemptions.items()},
            r_S=speeds["S"], r_K0c=speeds["K0c"], r_K2=speeds["K2"], r_K4=speeds["K4"], r_1=speeds["S"], r_3=speeds["K2"], r_5=speeds["K4"],
            K0c_independent_ratio=speeds["K0c"], free_capacity=free, chosen_student_backend=self.chosen_backend,
            student_forward_warm_ms=forwards, default_gc=default_gc, freeze_gc=freeze_gc,
            deadline_equivalence=deadline_results,
            feasibility={tier: feasible(speeds[tier], self.windows[tier], self.corpus_exact(tier),
                freeze_gc[tier] if freeze_gc[tier]["passes"] else default_gc[tier],
                tier != "S" or self.chosen_backend is not None, deadline_results[tier]["cell"]) for tier in TIERS},
            technical_failure_candidates=dict(
                foreign_over_one_core_over_60_seconds=any(p["foreign_over_one_core_seconds"] > 60 for r in capacities for p in r["processes"]),
                sampling_gaps=any(r["sample_gap_over_3_seconds"] for r in capacities)),
            deadline_replay_semantics=self.manifest.get("deadline_replay_semantics","legacy smoke without suspended-progress credit"),
            deadline_replay_amendment_1=not self.args.linux_dry_run,
            suspended_transaction_states=sum(r.get("belief_had_suspended_transaction",False) for r in self.backend.rows),
            formal_E4_qualified=False, final=False))
        validate_bundle(self.args.bundle, self.args.runtime_root, dry_run=self.args.linux_dry_run)
        if sha(self.args.native) != native_sha:
            raise ValueError("Native changed during measurement")
        self.store.write("tiers-complete.json", dict(completed=True, utc=time.time(), final=False,
            live_actions=False, mac_qualified=False, exit_zero_means="session completed, not gate pass"))

    def stop_load(self):
        if self.background is not None:
            self.background.close()
            self.background = None
        if self.worker is None:
            return
        self.stop.set()
        self.worker.join(10)
        if self.worker.is_alive():
            self.worker.terminate()
            self.worker.join(10)
            raise RuntimeError("Replay load did not stop cleanly")
        if self.worker.exitcode != 0:
            raise RuntimeError("Replay worker failed")
        self.worker = None

    def close(self):
        try:
            self.stop_load()
        finally:
            self.stop_monitor()
            if self.backend is not None:
                self.backend.close()

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
        start = time.monotonic()
        self.wait_until(start+300, "pre-session-census")
        rows = [json.loads(line) for line in (self.store.directory / "capacity.jsonl").read_text().splitlines() if line.endswith("}")]
        selected = [r for r in rows if r["phase"] == "pre-session-census"]
        averages = census_average(selected)
        foreign = {pid:value for pid,value in averages.items() if value > .2}
        for row in selected:
            self.store.append("presession-census.jsonl", row)
        self.store.write("pre-session-census.json", dict(start=start, end=time.monotonic(),
            samples=len(selected), foreign_over_point_two_core=foreign, passes=not foreign and len(selected) >= 298))
        if foreign or len(selected) < 298:
            raise ValueError("Exclusive Mac 5-minute quiescence census failed")

    def corpus_exact(self, tier):
        return len(self.forward_exemptions[tier])/len(self.manifest["sets"]["speed"][tier]) <= .005

    def deadline_corpus(self, speeds, only=None):
        refs = json.loads((self.args.bundle / "deadline-reference.json").read_text())
        result = {}
        for tier in ((only,) if only else TIERS):
            rows = []
            self.backend.activate(tier)
            for identity_ in self.manifest["sets"]["speed"][tier]:
                self.backend.prepare_work(self.backend.by_id[identity_])
                entered = time.monotonic()
                _, timing = self.backend.work(self.backend.by_id[identity_], tier,
                    deadline=.2, packet_entry=entered, backend=self.chosen_backend or "cpu")
                row = dict(tier=tier, id=identity_, deadline_seconds=.2, **timing)
                rows.append(row)
                self.store.append("deadline-corpus.jsonl", row)
                self.sample("D5b")
            result[tier] = deadline_equivalence(speeds[tier], decision_rates(rows), refs[tier])
        self.store.write("deadline-equivalence"+("-"+only if only else "")+".json", dict(tiers=result))
        return result


def forward_worker(bundle, root, native, dry_run, device, identities, output, search_cpus):
    if search_cpus:
        os.sched_setaffinity(0, set(search_cpus))
    validate_bundle(bundle, root, dry_run=dry_run)
    backend = TierBackend(bundle, root, native)
    try:
        with Path(output).open("x") as stream:
            # Cold observation is separate from every warm quantile.
            for index, identity_ in enumerate([identities[0]] + identities):
                start = time.monotonic()
                _, elapsed = backend.infer(identity_, device)
                end = time.monotonic()
                stream.write(json.dumps(dict(device=device, id=identity_, cold=index == 0,
                    ms=elapsed*1000, start=start, end=end, pid=os.getpid())) + "\n")
                stream.flush()
    finally:
        backend.close()


def canonical_result(value):
    from receipts import canonical
    return canonical(value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--native", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sam-authorized-replay", action="store_true")
    parser.add_argument("--linux-dry-run", action="store_true")
    parser.add_argument("--fleet-reference", action="store_true",
        help="T1-only loaded Linux reference; executes fixed public fixtures, never games")
    parser.add_argument("--search-cpus", type=lambda value: [int(i) for i in value.split(",")])
    parser.add_argument("--load-cpu", type=int)
    parser.add_argument("--background-cpus", type=lambda value: [int(i) for i in value.split(",")])
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--pool-fleet-references",action="store_true")
    parser.add_argument("--pool-input",type=Path)
    parser.add_argument("--pool-input-sha256")
    parser.add_argument("--coordinator-lock", type=Path)
    parser.add_argument("--coordinator-lock-fd", type=int,
        help="Inherited locked descriptor: holds the same lock from pre-staging through measurement")
    args = parser.parse_args(argv)
    # Refusals leave a failure receipt, including authorization/platform/pin gates.
    store = ReceiptStore(args.output, "FLEET-POOL" if args.pool_fleet_references else "FLEET-REFERENCE" if args.fleet_reference else "LINUX-DRY-RUN" if args.linux_dry_run else "MAC-REPLAY")
    session = None
    status = "failed"
    lock = None
    try:
        if any(os.environ.get(k) != "1" for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS")):
            raise ValueError("Measurement requires OMP/OPENBLAS/MKL thread environment pinned to one")
        if sum((args.fleet_reference,args.linux_dry_run,args.sam_authorized_replay,args.pool_fleet_references)) > 1:
            raise ValueError("Measurement modes are mutually exclusive")
        if args.pool_fleet_references:
            if args.pool_input is None or args.pool_input_sha256 is None or any((args.bundle,args.runtime_root,args.native,args.manifest_sha256,args.search_cpus,args.background_cpus,args.load_cpu is not None)):
                raise ValueError("Pooling requires only the approved descriptor SHA and output")
            from fleet_pool import run
            run(args,store)
            status="complete"
            return 0
        if any(v is None for v in (args.bundle,args.runtime_root,args.native,args.manifest_sha256)):
            raise ValueError("Measurement requires bundle/runtime/native/manifest SHA")
        if args.fleet_reference and (args.linux_dry_run or args.sam_authorized_replay):
            raise ValueError("Fleet reference, Linux dry run and authorized Mac modes are exclusive")
        if not args.fleet_reference:
            admit_platform(args.linux_dry_run, args.sam_authorized_replay)
        if sha(args.bundle / "tiers-pins.json") != args.manifest_sha256:
            raise ValueError("Independently approved bundle manifest SHA mismatch")
        if args.fleet_reference:
            from fleet_reference import run
            run(args, store)
            status = "complete"
            return 0
        if args.linux_dry_run:
            width = 1 if platform.node() == "127x05" else 5
            if not args.search_cpus or len(args.search_cpus) != width or len(set(args.search_cpus)) != width or args.load_cpu is None or args.load_cpu in args.search_cpus:
                raise ValueError("Linux dry run requires the host-specific physical CPU profile (05: one search; 03: five) and separate replay CPU")
            os.sched_setaffinity(0, set(args.search_cpus))
            from telemetry import validate_physical_cpus
            validate_physical_cpus(args.search_cpus + [args.load_cpu] + (args.background_cpus or []))
            if not args.background_cpus or len(args.background_cpus) != width:
                raise ValueError("Linux run requires a separate host-specific background corpus slot")
        elif args.search_cpus or args.load_cpu is not None:
            raise ValueError("Mac uses inherited QoS; Linux affinity options cannot change Mac scheduling")
        else:
            import fcntl
            if args.coordinator_lock is None:
                raise ValueError("Mac requires the coordinator's exclusive session lock")
            if args.coordinator_lock_fd is None:
                lock = args.coordinator_lock.open("r+")
            else:
                lock = os.fdopen(os.dup(args.coordinator_lock_fd), "r+")
                if (os.fstat(lock.fileno()).st_dev,os.fstat(lock.fileno()).st_ino) != (args.coordinator_lock.stat().st_dev,args.coordinator_lock.stat().st_ino):
                    raise ValueError("Inherited coordinator lock descriptor points at a different file")
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            store.write("coordinator-lock.json", dict(path=str(args.coordinator_lock),
                receipt=lock.read(), pid=os.getpid(), held_exclusively=True))
        session = Session(args, store)
        store.scope += ":"+session.manifest["load"]["label"]
        session.run()
        status = "complete"
    except BaseException as error:
        store.write("failure.json", dict(error=traceback.format_exc(), utc=time.time(),
            fleet_technical_cause=getattr(error,"cause",None) if args.fleet_reference else None,
            fail_closed=True, final=False, live_actions=False))
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
