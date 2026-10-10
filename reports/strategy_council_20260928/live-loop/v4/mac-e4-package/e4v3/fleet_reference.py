"""Loaded Linux reference using the identical TierBackend.work decision loop.

Called only by measure_tiers.py --fleet-reference; never launches games.
"""
import json
import multiprocessing as mp
import os
from pathlib import Path
import platform
import time

from receipts import TIERS, assert_exact, decision_rates, quantiles, sha
from replay_load import FleetBackground
from telemetry import cpu_counters, monitor_worker, validate_physical_cpus, validate_topology
from tier_backend import NATIVE_SHA, TierBackend, validate_bundle
from fleet_profile import pinned_profile, compare_mhz
from fleet_end import evidence,host_reporting
from fleet_validity import FleetTechnicalError,validate_census

from corpus_contract import REQUIRED_ROW, validate_row, validate_capture_receipt


def run(args, store):
    if sha(args.native) != NATIVE_SHA:
        raise ValueError("Wrong qualified fleet native")
    if args.background_cpus or args.load_cpu is not None:
        raise ValueError("Fleet masks come exclusively from the pinned reporting plan; no perception CPU")
    manifest = validate_bundle(args.bundle,args.runtime_root,dry_run=True,require_references=False)
    if manifest["profile"] != "fleet-reference":
        raise ValueError("Fleet reference mode requires reviewed fleet-reference inputs")
    if any(name not in manifest["files"] for name in ("golden.json","belief-reference.json")):
        raise ValueError("Fleet native/belief exactness references must be SHA-pinned")
    profile,plan,(search,background_masks,census_cpu)=pinned_profile(args.bundle,manifest)
    end=evidence(args.bundle,manifest,plan)
    reporting=host_reporting(end,profile,plan)
    if args.search_cpus and args.search_cpus != search:
        raise ValueError("Reference CPU mask differs from pinned reporting slot")
    args.search_cpus=search
    validate_physical_cpus(search+sum(background_masks,[])+[census_cpu])
    os.sched_setaffinity(0,set(search))
    backend = TierBackend(args.bundle,args.runtime_root,args.native)
    backend.search_cpus = args.search_cpus
    context = mp.get_context("spawn")
    stop, phase = context.Event(), context.Array("c",64)
    owned = context.Array("i",[os.getpid()]+[0]*(len(background_masks)+1))
    clusters = validate_topology(manifest["topology"],cpu_counters(),darwin=False)
    monitor = context.Process(target=reference_monitor,args=(stop,phase,owned,clusters,store.directory/"capacity.jsonl",census_cpu,args.bundle,manifest))
    def check_monitor():
        if not monitor.is_alive():
            path=store.directory/"capacity.jsonl"
            rows=[json.loads(s) for s in path.read_text().splitlines()] if path.exists() else []
            if any(row.get("reporting_guard",{}).get("passes") is False for row in rows):
                raise FleetTechnicalError("validity_census","Reference reporting guard failed")
            raise FleetTechnicalError("crash","Reference telemetry failed")
    refs = {tier:{} for tier in TIERS}
    deadlines = {tier:{"1.0":[],"0.8":[]} for tier in TIERS}
    trace=None
    try:
        for tier in TIERS:
            ids = manifest["sets"]["speed"][tier]
            if len(ids) != 300 or len(ids) != len(set(ids)):
                raise ValueError("Fleet reference needs >=300 unique states PER tier")
            for identity in ids:
                validate_row(backend.by_id[identity],tier)
        capture=validate_capture_receipt(args.bundle,manifest,backend)
        store.write("corpus-capture.json",capture)
        store.write("fleet-identity.json",dict(host=platform.node(),nice=plan["compute"]["nice"],native_sha256=sha(args.native),
            manifest_sha256=sha(args.bundle/"tiers-pins.json"),specification=manifest["specification"],
            load_profile=profile,search_cpus=args.search_cpus,background_masks=background_masks,
            reporting_plan_sha256=sha(args.bundle/profile["plan"]),
            end_evidence_sha256=end["sha256"],end_kind=end["kind"],
            counted_hosts=end["counted_hosts"],
            corpus_receipt_sha256=sha(args.bundle/manifest["corpus_receipt"]),
            input_files=manifest["files"],sets=manifest["sets"],runtime_files=manifest["runtime_files"],
            measurement_files=manifest["measurement_files"],deadline_replay_semantics=manifest["deadline_replay_semantics"],
            utc=time.time(),final=False,live_actions=False))
        store.write("end-evidence.json",end["inventory"])
        store.write("reporting-full-occupancy-mhz.json",dict(rows=reporting))
        from measure_tiers import Session
        from types import SimpleNamespace
        if len(manifest["sets"]["golden"]) != 125:
            raise ValueError("Fleet reference needs qualified golden125 and belief reference inputs")
        Session.exactness(SimpleNamespace(args=args,store=store,manifest=manifest,backend=backend,exactness_class="EXACT"))
        from measure_tiers import GCTrace
        trace=GCTrace();trace.__enter__()
        trace.context.update(variant="fleet-reference")
        phase.value = b"reference-warmup"
        monitor.start(); owned[-1]=monitor.pid
        background_load=FleetBackground(args.bundle,args.runtime_root,args.native,background_masks)
        background_load.check_external=check_monitor
        with background_load as background:
            for index,worker in enumerate(background.workers,1): owned[index]=worker.pid
            if profile["warmup_seconds"] < 300:
                raise ValueError("Reporting reference thermal warmup must be >=300 seconds")
            warmed={tier:0 for tier in TIERS};lap=0;warm_start=time.monotonic()
            until=warm_start+profile["warmup_seconds"]
            # Warm the reference slot as well as every background slot; an idle
            # reference core would begin its timed work at a different clock.
            while time.monotonic()<until:
                order=TIERS[lap%4:]+TIERS[:lap%4]
                for offset in range(0,300,50):
                    for tier in order:
                        for identity in manifest["sets"]["speed"][tier][offset:offset+50]:
                            if time.monotonic()>=until:break
                            background.check();check_monitor()
                            trace.context.update(tier=tier,id=identity,opportunity=True,decision_deadline=None)
                            backend.work(backend.by_id[identity],tier);warmed[tier]+=1
                lap+=1
            store.write("reference-warmup.json",dict(seconds=time.monotonic()-warm_start,
                reference_slot_work=warmed,all_background_slots=len(background_masks),all_slots_active=True))
            for repeat in range(3):
                order=TIERS[repeat%4:]+TIERS[:repeat%4]
                phase.value=b"reference-speed"
                for offset in range(0,max(len(manifest["sets"]["speed"][t]) for t in TIERS),50):
                    for tier in order:
                        for identity in manifest["sets"]["speed"][tier][offset:offset+50]:
                            background.check()
                            check_monitor()
                            trace.context.update(tier=tier,id=identity,opportunity=True,decision_deadline=None)
                            result,timing=backend.work(backend.by_id[identity],tier)
                            ref=refs[tier].setdefault(identity,dict(result=result,forward=timing["forward"],walls=[]))
                            assert_exact(result,ref["result"],"fleet repeated full decision")
                            assert_exact(timing["forward"],ref["forward"],"fleet repeated forward")
                            ref["walls"].append(timing["wall_seconds"])
                            store.append("speed-reference-raw.jsonl",dict(repeat=repeat,tier=tier,id=identity,**{k:v for k,v in timing.items() if k != "forward"}))
                phase.value=b"reference-deadlines"
                for tier in order:
                    for cell,budget in (("1.0",.2),("0.8",.16)):
                        for identity in manifest["sets"]["speed"][tier]:
                            trace.context.update(tier=tier,id=identity,opportunity=False,decision_deadline=None)
                            background.check();check_monitor();backend.activate(tier);backend.prepare_work(backend.by_id[identity])
                            entered=time.monotonic()
                            trace.context.update(opportunity=True,decision_deadline=entered+budget)
                            _,timing=backend.work(backend.by_id[identity],tier,deadline=budget,packet_entry=entered)
                            row=dict(repeat=repeat,tier=tier,id=identity,cell=cell,deadline_seconds=budget,**{k:v for k,v in timing.items() if k != "forward"})
                            deadlines[tier][cell].append(row);store.append("deadline-reference-raw.jsonl",row)
                print("Fleet full-pipeline loaded repeat "+str(repeat+1)+"/3",flush=True)
        stop.set();monitor.join(10)
        if monitor.is_alive():
            raise FleetTechnicalError("crash","Reference census did not stop before sealing")
        if monitor.exitcode != 0:
            check_monitor()
        for tier in TIERS:
            for ref in refs[tier].values():ref["wall_seconds"]=quantiles(ref.pop("walls"))["p50"]
        store.write("speed-reference.json",refs)
        store.write("deadline-reference.json",{t:{c:decision_rates(v) for c,v in cells.items()} for t,cells in deadlines.items()})
        census=[json.loads(line) for line in (store.directory/"capacity.jsonl").read_text().splitlines()]
        store.write("reference-validity.json",validate_census(census))
        clocks=compare_mhz(reporting,census,search+sum(background_masks,[]),profile["slot_count"])
        store.write("reporting-mhz-comparison.json",clocks)
        if not clocks["passes"]:
            raise FleetTechnicalError("mhz_gate","Reference/reporting MHz differs by >5%; reference fails closed")
        source=args.bundle/profile["plan"]
        (store.directory/"source-plan.json").write_bytes(source.read_bytes())
        # Preserve every committed completion/phase source, not a selected projection.
        artifacts=[end["inventory"]["completion"]]+[entry[key] for entry in end["inventory"]["phases"] for key in ("launch","supervisor_exit","mhz","census")]
        for item in artifacts:
            target=store.directory/"end-sources"/item["path"];target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():target.write_bytes((args.bundle/item["path"]).read_bytes())
        validate_bundle(args.bundle,args.runtime_root,dry_run=True,require_references=False)
        store.write("fleet-complete.json",dict(completed=True,final=False,repeats=3,reporting_load_profile=True,
            outcome_access=False,live_actions=False,host=platform.node(),utc=time.time(),
            poolable=end["kind"]=="counted-reporting",exactness_class="EXACT"))
    finally:
        stop.set()
        try:
            if monitor.pid:
                monitor.join(10)
                if monitor.is_alive():monitor.terminate();monitor.join(10)
                # Preserve the primary exception (especially exactness), never replace it
                # with a generic cleanup crash that could earn a technical repeat.
                if monitor.exitcode != 0 and __import__("sys").exc_info()[0] is None:check_monitor()
        finally:
            try:
                if trace is not None:
                    trace.__exit__()
                    store.write("gc-events.json",dict(events=trace.events,
                        deadline_basis="actual packet entry plus 200/160ms; no synthetic poll cadence"))
            finally:
                backend.close()


def reference_monitor(stop,phase,owned,clusters,output,cpu,bundle,manifest):
    os.sched_setaffinity(0,{cpu})
    from fleet_validity import ReportingGuard
    monitor_worker(stop,phase,owned,clusters,output,ReportingGuard(bundle,manifest,owned))
