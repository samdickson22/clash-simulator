"""Derive all reference slots from the SHA-pinned reporting plan, never host guesses."""
import json
import math
import os
import platform
from pathlib import Path


def slot_layout(profile, plan, host, nice):
    compute=plan["compute"]
    if host not in compute["hosts"] or host in compute.get("forbidden_hosts",()):
        raise ValueError("Host absent/forbidden in pinned reporting plan")
    if profile["host"] != host or nice != compute["nice"] or compute["scheduler"] != "SCHED_OTHER":
        raise ValueError("Reference must inherit the pinned reporting host/priority/scheduler")
    if type(profile["console_rule"]) is not bool:
        raise ValueError("Console rule must be an explicit Boolean")
    count=compute["console_slots"] if profile["console_rule"] else compute["slots"]
    if profile["slot_count"] != count or compute["slot_width"] != 5 or compute["smt"]:
        raise ValueError("Reference must occupy every pinned five-physical-core reporting slot")
    cpus=compute["hosts"][host]["physical_cpus"][:count*5]
    if len(cpus) != count*5 or len(set(cpus)) != len(cpus):
        raise ValueError("Incomplete/disjoint reporting masks")
    slots=[cpus[i:i+5] for i in range(0,len(cpus),5)]
    index=profile["reference_slot"]
    if type(index) is not int or not 0 <= index < count or count < 2:
        raise ValueError("Invalid reference slot")
    if not math.isfinite(profile["warmup_seconds"]) or profile["warmup_seconds"] < 300 or profile["perception"] != "none":
        raise ValueError("Fleet uses >=300s all-slot corpus warmup without perception")
    return slots[index],[slot for i,slot in enumerate(slots) if i != index],compute["hosts"][host]["census_cpu"]


def pinned_profile(bundle, manifest):
    profile=manifest["reference_load_profile"]
    for key in ("plan","reporting_mhz","reporting_end"):
        if profile[key] not in manifest["files"]:
            raise ValueError("Reporting profile source must be SHA-pinned: "+key)
    plan=json.loads((Path(bundle)/profile["plan"]).read_text())
    host=platform.node()
    if platform.system() != "Linux" or os.sched_getscheduler(0) != os.SCHED_OTHER:
        raise ValueError("Fleet requires the pinned Linux SCHED_OTHER reporting profile")
    layout=slot_layout(profile,plan,host,os.getpriority(os.PRIO_PROCESS,0))
    end=json.loads((Path(bundle)/profile["reporting_end"]).read_text())
    if end.get("host") != host or end.get("reporting_complete") is not True or end.get("outcomes_sealed") is not True:
        raise ValueError("Fleet references run at reporting END with outcomes sealed")
    return profile,plan,layout


def compare_mhz(reporting, reference, cpus, slots):
    """Equal-weight 1Hz physical-core census; keep distributions and raw sources."""
    from receipts import quantiles
    report=[]
    for row in reporting:
        if row["slots"] != slots:
            continue
        clocks={v["cpu"]:v["mhz"] for v in row["physical_core_mhz"]}
        if not set(cpus) <= set(clocks):
            raise ValueError("Reporting MHz is missing occupied physical cores")
        report.append(sum(clocks[c] for c in cpus)/len(cpus))
    measured=[sum(row["cpu_clock_mhz"][c] for c in cpus)/len(cpus) for row in reference
        if row["phase"] in ("reference-speed","reference-deadlines")]
    if len(report) < 2 or len(measured) < 2 or any(not math.isfinite(v) or v <= 0 for v in report+measured):
        raise ValueError("Missing/invalid independent reporting or reference MHz census")
    ratio=sum(measured)/len(measured)/(sum(report)/len(report))
    return dict(reporting=quantiles(report),reference=quantiles(measured),reference_to_reporting_mean=ratio,
        absolute_relative_difference=abs(ratio-1),passes=abs(ratio-1) <= .05,
        rule="draft <=5% mean physical-core MHz difference; independent review required")
