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
from replay_load import LinuxBackground
from telemetry import cpu_counters, monitor_worker, validate_physical_cpus, validate_topology
from tier_backend import NATIVE_SHA, TierBackend, validate_bundle

REQUIRED_ROW = ("id", "tier", "seed", "info", "reserved_packet", "d1", "d1_before", "d1_events",
                "policy_rng_state", "candidate_rng_state", "belief_before", "belief_rng_state",
                "opponent", "root_rng_state", "root", "root_digest", "pending", "opponent_elixir",
                "strata", "belief_had_suspended_transaction")


def validate_row(row, tier):
    missing = [name for name in REQUIRED_ROW if name not in row]
    if missing or row.get("tier") != tier:
        raise ValueError("Incomplete/wrong own-tier reference row: " + repr(missing))
    if "builder" in row["d1_before"]:
        raise ValueError("d1_before is a tracker state dictionary excluding builder")
    if getattr(row["belief_before"], "_pending", None) is not None:
        raise ValueError("Use serializable belief_resume instead of a live generator")
    if not {"elixir", "legal_play_count"} <= set(row["strata"]):
        raise ValueError("Missing preregistered strata")


def run(args, store):
    if platform.system() != "Linux" or platform.node() not in ("127x01", "127x03", "127x08"):
        raise ValueError("Fleet references require authorized T1 reporting hosts 01/03/08")
    if os.getpriority(os.PRIO_PROCESS, 0) != 10:
        raise ValueError("T1 reporting-load references require nice 10")
    if sha(args.native) != NATIVE_SHA:
        raise ValueError("Wrong qualified fleet native")
    if not args.search_cpus or len(args.search_cpus) != 5 or not args.background_cpus or len(args.background_cpus) != 5 or args.load_cpu is None:
        raise ValueError("Fleet reference requires five search CPUs, five background CPUs, separate replay CPU")
    validate_physical_cpus(args.search_cpus+args.background_cpus+[args.load_cpu])
    os.sched_setaffinity(0,set(args.search_cpus))
    manifest = validate_bundle(args.bundle,args.runtime_root,dry_run=True,require_references=False)
    if manifest["profile"] != "fleet-reference":
        raise ValueError("Fleet reference mode requires reviewed fleet-reference inputs")
    if any(name not in manifest["files"] for name in ("golden.json","belief-reference.json")):
        raise ValueError("Fleet native/belief exactness references must be SHA-pinned")
    profile = manifest["reference_load_profile"]
    if not profile.get("reporting_load_profile") or profile.get("background_cpus") != args.background_cpus or profile.get("replay_cpu") != args.load_cpu:
        raise ValueError("Load profile must bind the reviewed reporting-equivalent background CPU groups")
    backend = TierBackend(args.bundle,args.runtime_root,args.native)
    backend.search_cpus = args.search_cpus
    context = mp.get_context("spawn")
    stop, phase = context.Event(), context.Array("c",64)
    owned = context.Array("i",[os.getpid(),0,0,0,0])
    clusters = validate_topology(manifest["topology"],cpu_counters(),darwin=False)
    monitor = context.Process(target=monitor_worker,args=(stop,phase,owned,clusters,store.directory/"capacity.jsonl"))
    refs = {tier:{} for tier in TIERS}
    deadlines = {tier:{"1.0":[],"0.8":[]} for tier in TIERS}
    try:
        for tier in TIERS:
            ids = manifest["sets"]["speed"][tier]
            if len(ids) < 300 or len(ids) != len(set(ids)):
                raise ValueError("Fleet reference needs >=300 unique states PER tier")
            for identity in ids:
                validate_row(backend.by_id[identity],tier)
        store.write("fleet-identity.json",dict(host=platform.node(),nice=10,native_sha256=sha(args.native),
            manifest_sha256=sha(args.bundle/"tiers-pins.json"),specification=manifest["specification"],
            load_profile=profile,search_cpus=args.search_cpus,final=False,live_actions=False))
        from measure_tiers import Session
        from types import SimpleNamespace
        if len(manifest["sets"]["golden"]) != 125:
            raise ValueError("Fleet reference needs qualified golden125 and belief reference inputs")
        Session.exactness(SimpleNamespace(args=args,store=store,manifest=manifest,backend=backend,exactness_class="EXACT"))
        phase.value = b"reference-warmup"
        monitor.start(); owned[3]=monitor.pid
        with LinuxBackground(args.bundle,args.runtime_root,args.native,store.directory/"perception-replay.jsonl",
                             args.load_cpu,args.background_cpus,preparing=True) as background:
            for index,worker in enumerate(background.workers,1): owned[index]=worker.pid
            until=time.monotonic()+profile["warmup_seconds"]
            if profile["warmup_seconds"] < 300:
                raise ValueError("Reporting reference thermal warmup must be >=300 seconds")
            while time.monotonic()<until:
                background.check();time.sleep(.1)
            for repeat in range(3):
                order=TIERS[repeat%4:]+TIERS[:repeat%4]
                phase.value=b"reference-speed"
                for offset in range(0,max(len(manifest["sets"]["speed"][t]) for t in TIERS),50):
                    for tier in order:
                        for identity in manifest["sets"]["speed"][tier][offset:offset+50]:
                            background.check()
                            if not monitor.is_alive():raise RuntimeError("Reference telemetry failed")
                            result,timing=backend.work(backend.by_id[identity],tier)
                            ref=refs[tier].setdefault(identity,dict(result=result,forward=timing["forward"],walls=[]))
                            assert_exact(result,ref["result"],"fleet repeated full decision")
                            ref["walls"].append(timing["wall_seconds"])
                            store.append("speed-reference-raw.jsonl",dict(repeat=repeat,tier=tier,id=identity,**{k:v for k,v in timing.items() if k != "forward"}))
                phase.value=b"reference-deadlines"
                for tier in order:
                    for cell,budget in (("1.0",.2),("0.8",.16)):
                        for identity in manifest["sets"]["speed"][tier]:
                            background.check();backend.activate(tier);backend.prepare_work(backend.by_id[identity])
                            entered=time.monotonic()
                            _,timing=backend.work(backend.by_id[identity],tier,deadline=budget,packet_entry=entered)
                            row=dict(repeat=repeat,tier=tier,id=identity,cell=cell,deadline_seconds=budget,**{k:v for k,v in timing.items() if k != "forward"})
                            deadlines[tier][cell].append(row);store.append("deadline-reference-raw.jsonl",row)
                print("Fleet full-pipeline loaded repeat "+str(repeat+1)+"/3",flush=True)
        for tier in TIERS:
            for ref in refs[tier].values():ref["wall_seconds"]=quantiles(ref.pop("walls"))["p50"]
        store.write("speed-reference.json",refs)
        store.write("deadline-reference.json",{t:{c:decision_rates(v) for c,v in cells.items()} for t,cells in deadlines.items()})
        store.write("fleet-complete.json",dict(completed=True,final=False,repeats=3,reporting_load_profile=True,
            outcome_access=False,live_actions=False,host=platform.node(),utc=time.time()))
    finally:
        stop.set()
        if monitor.pid:
            monitor.join(10)
            if monitor.is_alive():monitor.terminate();monitor.join(10)
            if monitor.exitcode != 0:raise RuntimeError("Reference telemetry exited with error")
        backend.close()
