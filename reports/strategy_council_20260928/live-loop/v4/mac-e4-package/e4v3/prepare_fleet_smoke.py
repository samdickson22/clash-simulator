#!/usr/bin/env python3
"""Stage A6 offline from T1's approved END bundle; never starts a measurement.

The coordinator assigned 127x01 at END, outside reporting. All copied input
bytes remain source-pinned; only the plan/evidence labels are smoke-specific.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import time
import traceback

from fleet_end import evidence, host_reporting
from fleet_profile import slot_layout
from receipts import TIERS, ReceiptStore, canonical, sha, verify_files


def prepare(source, expected, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    store = ReceiptStore(output, "A6-OFFLINE-STAGING-DRAFT")
    status = "failed"
    try:
        if sha(source/"tiers-pins.json") != expected:
            raise ValueError("A6 source manifest SHA mismatch")
        manifest = json.loads((source/"tiers-pins.json").read_text())
        verify_files(source, manifest["files"])
        verify_files(Path(__file__).parent, manifest["measurement_files"])
        if manifest["profile"] != "fleet-reference" or manifest["reference_load_profile"]["host"] != "127x01":
            raise ValueError("A6 requires T1's reviewed 127x01 fleet-reference bundle")
        if len(set(manifest["sets"]["golden"])) != 125 or len(manifest["sets"]["golden"]) != 125:
            raise ValueError("A6 retains the separate exactness golden125")
        for tier in TIERS:
            ids = manifest["sets"]["speed"][tier]
            if len(ids) != 300 or len(set(ids)) != 300:
                raise ValueError("A6 requires reviewed own-tier300 sets")
        profile = manifest["reference_load_profile"]
        plan = json.loads((source/profile["plan"]).read_text())
        end = evidence(source, manifest, plan)
        if end["kind"] != "counted-reporting":
            raise ValueError("A6 source must bind the committed reporting END")
        report = host_reporting(end, profile, plan)
        if plan["compute"]["nice"] != 10:
            raise ValueError("Scheduled T1 A6 inherits reporting nice10")
        slot_layout(profile,plan,"127x01",10)
        bundle = output/"bundle"; bundle.mkdir()
        for name in manifest["files"]:
            target = bundle/name; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source/name, target)
        verify_files(bundle, manifest["files"])
        smoke = copy.deepcopy(manifest)
        def write(name, obj, lines=False):
            target = bundle/name; target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("x") as stream:
                if lines:
                    for row in obj:stream.write(canonical(row)+"\n")
                else:stream.write(canonical(obj)+"\n")
            smoke["files"][name] = sha(target)
            return dict(path=name,sha256=sha(target),synthetic=True)
        plan = copy.deepcopy(plan)
        plan["profile"] = "e4v3-unpoolable-smoke"
        plan["a6_schedule"] = dict(host="127x01",phase="T1-END-before-production-references",
            window_owner="T1",projected_window_utc="2026-10-11T02:00Z/2026-10-11T06:00Z",
            actual_window_assignment_required=True,source_manifest_sha256=expected)
        write("_a6/plan.json",plan)
        completion = copy.deepcopy(end["completion"])
        blocks=[dict(row,phase="reporting") for row in end["counted_inventory"]["blocks"] if row["host"]=="127x01"]
        # This derived inventory is solely for an unpoolable smoke. Retain all
        # original committed ledger/inventory/exit bytes above, without edits.
        ledger=write("_a6/blind-ledger.json",dict(sealed=True,events=[]))
        smoke_blocks=[]
        for row in blocks:
            d=copy.deepcopy(row["descriptor"])
            d["id"]=d.get("replaces") or d["id"];d["replaces"]=None
            smoke_blocks.append(dict(row,descriptor=d))
        completion.update(counted_host_phases={"127x01":["reporting"]},synthetic=True,
            blind_ledger_sha256=ledger["sha256"],
            purpose="A6 only; production END source retained and SHA-bound")
        # Host01's logical IDs can be sparse. Smoke-only normalization keeps
        # coverage mechanical while explicitly disclosing synthetic identities.
        for pop in ("primary","guard"):
            rows_pop=[r for r in smoke_blocks if r["descriptor"]["population"]==pop]
            for i,row in enumerate(rows_pop):row["descriptor"]["id"]=f"{pop}-{i:04d}"
            completion["counted_"+pop+"_blocks"]=len(rows_pop)
        counted=write("_a6/counted-inventory.json",dict(schema="clasher.t1.counted-blocks.v1",
            outcomes_sealed=True,blocks=smoke_blocks))
        completion["counted_inventory_sha256"]=counted["sha256"]
        complete = write("_a6/completion.json",completion)
        launch = write("_a6/launch.json",dict(host="127x01",phase="reporting",slots=profile["slot_count"],synthetic=True))
        exit_ = write("_a6/supervisor-exit.json",dict(host="127x01",reason=None,completed=[r["descriptor"] for r in smoke_blocks],failed=[],unstarted=[],
            utc=completion["completed_at_utc"],synthetic=True))
        # Baseline numbers are fixed BEFORE measurement from approved reporting.
        # They are never derived from the smoke result to force a passing gate.
        rows = [dict(row,utc="a6-baseline-"+str(i),synthetic=True,
                     source_phase=row["phase"],source_utc=row["utc"]) for i,row in enumerate(report)]
        mhz = write("_a6/reporting-mhz.jsonl",rows,True)
        census = write("_a6/reporting-census.jsonl",[dict(host="127x01",utc=row["utc"],
            inflight=profile["slot_count"],reason=None,synthetic=True) for row in rows],True)
        inventory = dict(schema="clasher.e4v3.end-evidence.v1",kind="unpoolable-smoke",
            repository=end["inventory"]["repository"],completion=complete,blind_ledger=ledger,counted_inventory=counted,
            phases=[dict(host="127x01",phase="reporting",launch=launch,supervisor_exit=exit_,mhz=mhz,census=census)],
            source_end_evidence_sha256=end["sha256"],source_manifest_sha256=expected)
        write("_a6/end-evidence.json",inventory)
        smoke["reference_load_profile"].update(plan="_a6/plan.json",end_evidence="_a6/end-evidence.json")
        smoke["final"] = False
        smoke["a6_smoke"] = dict(unpoolable=True,host="127x01",source_manifest_sha256=expected,
            source_end_evidence_sha256=end["sha256"],baseline="approved full-occupancy reporting clocks, synthetic join labels",
            actual_window_assignment_required=True)
        with (bundle/"tiers-pins.json").open("x") as stream:stream.write(canonical(smoke)+"\n")
        with (bundle/"tiers-pins.sha256").open("x") as stream:stream.write(sha(bundle/"tiers-pins.json")+"  tiers-pins.json\n")
        verify_files(source,manifest["files"])
        if sha(source/"tiers-pins.json") != expected:
            raise ValueError("A6 source changed during staging")
        verify_files(bundle,smoke["files"])
        staged = evidence(bundle,smoke,plan)
        host_reporting(staged,smoke["reference_load_profile"],plan)
        store.write("staging.json",dict(source_bundle=str(source),source_manifest_sha256=expected,
            bundle=str(bundle),manifest_sha256=sha(bundle/"tiers-pins.json"),
            original_inputs_unchanged=True,unpoolable=True,host="127x01",nice=10,
            warmup_seconds=profile["warmup_seconds"],slot_count=profile["slot_count"],
            measurement_started=False,outcome_access=False,live_actions=False,
            actual_window_assignment_required=True,review_pending=True,final=False,utc=time.time()))
        status = "complete"
        return sha(bundle/"tiers-pins.json")
    except BaseException:
        store.write("failure.json",dict(error=traceback.format_exc(),fail_closed=True,final=False,measurement_started=False))
        raise
    finally:
        store.seal(status)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-bundle",type=Path,required=True)
    parser.add_argument("--source-manifest-sha256",required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    print("A6 smoke bundle manifest SHA: "+prepare(args.source_bundle,args.source_manifest_sha256,args.output))


if __name__=="__main__":main()
