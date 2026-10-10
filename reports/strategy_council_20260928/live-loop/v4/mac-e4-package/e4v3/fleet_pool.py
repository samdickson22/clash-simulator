"""Mechanical draft fleet pooling. Reads sealed timing receipts, never outcomes."""
import json
import math
from pathlib import Path
from receipts import TIERS, assert_exact, decision_rates, quantiles, sha, verify_files
from tier_backend import NATIVE_SHA,V1_SHA,STUDENT_SHA,CALIBRATION_SHA


def geometric(values):
    if not values or any(not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError("Invalid host speed ratio")
    return math.exp(sum(math.log(v) for v in values)/len(values))


def pool_rows(hosts, min_states=300):
    """Pool RAW host × repeat observations, not medians of per-host medians."""
    if not hosts:
        raise ValueError("No fleet host receipts")
    expected=None
    walls={}
    deadlines={}
    for host,data in hosts.items():
        cells={}
        for row in data["speed"]:
            key=(row["tier"],row["id"])
            if row["tier"] not in TIERS or type(row["repeat"]) is not int or row["repeat"] not in range(3):
                raise ValueError("Unknown tier/repeat")
            cell=cells.setdefault(key,{})
            value=row["wall_seconds"]
            if row["repeat"] in cell or not math.isfinite(value) or value <= 0:
                raise ValueError("Duplicate/invalid fleet timing")
            cell[row["repeat"]]=value
        if any(set(v) != {0,1,2} for v in cells.values()):
            raise ValueError("Every fleet state needs exactly three raw repeats")
        keys=set(cells)
        if any(sum(t == tier for t,_ in keys) != min_states for tier in TIERS):
            raise ValueError("Fleet requires the complete fixed own-tier state sets")
        if expected is None:expected=keys
        if keys != expected:raise ValueError("Fleet host state sets differ")
        walls[host]={key:list(v.values()) for key,v in cells.items()}
        seen=set()
        for row in data["deadlines"]:
            key=(row["tier"],row["id"])
            identity=(key,row["cell"],row["repeat"])
            if type(row["repeat"]) is not int or key not in keys or row["cell"] not in ("1.0","0.8") or row["repeat"] not in range(3) or identity in seen:
                raise ValueError("Duplicate/unknown deadline reference state/cell/repeat")
            if row["deadline_seconds"] != {"1.0":.2,"0.8":.16}[row["cell"]]:
                raise ValueError("Deadline reference budget differs")
            if any(type(row[k]) is not bool for k in ("cutoff","fallback","no_complete_play","over_200_ms","cut_return_over_208_ms")) or not math.isfinite(row["wall_seconds"]) or row["wall_seconds"] <= 0:
                raise ValueError("Invalid deadline timing/count flags")
            seen.add(identity)
        if len(seen) != len(keys)*6:
            raise ValueError("Deadline references require both budgets × three repeats for every state")
        deadlines[host]=data["deadlines"]
    initial={key:quantiles(sum([w[key] for w in walls.values()],[]))["p50"] for key in expected}
    relative={host:geometric([initial[key]/quantiles(w[key])["p50"] for key in sorted(expected)]) for host,w in walls.items()}
    included=[h for h,r in relative.items() if abs(r-1) <= .05]
    excluded=[h for h in walls if h not in included]
    if not included:raise ValueError("All hosts fall outside ±5% of initial pooled median")
    pooled={key:quantiles(sum([walls[h][key] for h in included],[]))["p50"] for key in expected}
    final={h:geometric([pooled[key]/quantiles(walls[h][key])["p50"] for key in sorted(expected)]) for h in included}
    if any(abs(v-1) > .05 for v in final.values()):
        raise ValueError("Retained host exceeds ±5% after pooling; requires review, no silent iteration")
    rates={tier:{} for tier in TIERS}
    for tier in TIERS:
        for cell in ("1.0","0.8"):
            rows=[r for h in included for r in deadlines[h] if r["tier"] == tier and r["cell"] == cell]
            rates[tier][cell]=decision_rates(rows)
            rates[tier][cell]["counts"]={k:sum(bool(r[k]) for r in rows) for k in ("cutoff","fallback","no_complete_play")}
            rates[tier][cell]["states"]={identity:decision_rates([r for r in rows if r["id"]==identity]) for t,identity in sorted(expected) if t==tier}
    return dict(included=included,excluded=excluded,initial_host_ratios=relative,retained_host_ratios=final,
        walls={t:{identity:pooled[(t,identity)] for tier,identity in sorted(expected) if tier==t} for t in TIERS},
        deadlines=rates,rule="one-pass exclusion against raw all-host×repeat per-state median; pooled wall / host median")


def read_lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def run(args,store):
    if sha(args.pool_input) != args.pool_input_sha256:
        raise ValueError("Pooling descriptor SHA mismatch")
    request=json.loads(args.pool_input.read_text())
    if request["schema"] != "clasher.e4v3.fleet-pool.v1" or not request["hosts"]:
        raise ValueError("Unsupported pooling input")
    hosts={};identities={};source_pins={};common=None
    for entry in request["hosts"]:
        directory=Path(entry["directory"])
        seal=directory/"receipt-manifest.json"
        if sha(seal) != entry["manifest_sha256"]:
            raise ValueError("Host receipt SHA mismatch")
        receipt=json.loads(seal.read_text())
        if receipt["status"] != "complete":raise ValueError("Cannot pool failed/incomplete host")
        verify_files(directory,receipt["files"])
        identity=json.loads((directory/"fleet-identity.json").read_text())
        host=identity["host"]
        assert_exact(identity["specification"],json.loads((Path(__file__).parent/"spec-pins.json").read_text()),"pool frozen specification")
        verify_files(Path(__file__).parent,identity["measurement_files"])
        if identity["native_sha256"] != NATIVE_SHA or any(identity["input_files"].get(name) != expected for name,expected in (("v1.pt",V1_SHA),("R3a.pt",STUDENT_SHA),("R3a-calibration.json",CALIBRATION_SHA))):
            raise ValueError("Unqualified fleet native/policy/calibration")
        native=json.loads((directory/"exactness-tiers.json").read_text())
        belief=json.loads((directory/"belief-exactness.json").read_text())
        if native["passes"] is not True or native["states"] != 125 or len(native["records"]) != 125 or len({r["id"] for r in native["records"]}) != 125 or any(r["workers_equal"] is not True or r["zero_budget_immutable"] is not True or set(r["max_relative_difference"]) != {"K0c","K1","K2","K4"} or any(not math.isfinite(v) or not 0 <= v <= 1e-12 for v in r["max_relative_difference"].values()) for r in native["records"]):
            raise ValueError("Native golden125 mismatch drops ALL tiers/hosts")
        if belief["passes"] is not True or belief["histories"] != 125 or belief["posterior_weights_cumulative_ledger_samples_rng_exact"] is not True or len(belief["records"]) != 250 or len({(r["id"],r["deadline_on"]) for r in belief["records"]}) != 250 or {r["id"] for r in belief["records"]} != {r["id"] for r in native["records"]} or any(type(r["deadline_on"]) is not bool or r["exact"] is not True for r in belief["records"]):
            raise ValueError("Belief/posterior/RNG exactness mismatch drops ALL tiers/hosts")
        if host in hosts:raise ValueError("Duplicate host")
        complete=json.loads((directory/"fleet-complete.json").read_text())
        clocks=json.loads((directory/"reporting-mhz-comparison.json").read_text())
        if complete["repeats"] != 3 or complete["completed"] is not True or complete["reporting_load_profile"] is not True or complete["outcome_access"] is not False or complete["live_actions"] is not False or clocks["passes"] is not True:
            raise ValueError("Unqualified host repeat/clock receipt")
        binding=dict(sets=identity["sets"]["speed"],specification=identity["specification"],
            states_sha256=identity["input_files"]["states.pkl"],native_sha256=identity["native_sha256"],
            runtime_files=identity["runtime_files"],measurement_files=identity["measurement_files"],
            deadline_replay_semantics=identity["deadline_replay_semantics"],nice=identity["nice"],
            reporting_plan_sha256=identity["reporting_plan_sha256"],corpus_receipt_sha256=identity["corpus_receipt_sha256"])
        if common is None:common=binding
        assert_exact(binding,common,"cross-host corpus/runtime/load plan")
        hosts[host]=dict(speed=read_lines(directory/"speed-reference-raw.jsonl"),
            deadlines=read_lines(directory/"deadline-reference-raw.jsonl"),
            results=json.loads((directory/"speed-reference.json").read_text()))
        identities[host]=identity;source_pins[host]=entry
    result=pool_rows(hosts)
    refs={t:{} for t in TIERS}
    for tier in TIERS:
        for identity,wall in result["walls"][tier].items():
            first=hosts[result["included"][0]]["results"][tier][identity]
            for host in hosts:
                value=hosts[host]["results"][tier][identity]
                assert_exact(value["result"],first["result"],"cross-host complete decision")
                assert_exact(value["forward"],first["forward"],"cross-host forward")
            refs[tier][identity]=dict(result=first["result"],forward=first["forward"],wall_seconds=wall)
    store.write("speed-reference.json",refs)
    store.write("deadline-reference.json",result["deadlines"])
    store.write("pooling.json",dict(**result,source_receipts=source_pins,descriptor_sha256=sha(args.pool_input),
        final=False,outcome_access=False,reporting_end_amendment_pending_review=True))
    provenance=dict(hosts=result["included"],excluded_hosts=result["excluded"],nice=common["nice"],repeats=3,
        reporting_load_profile=True,physical_cores=True,pooling="raw-host-times-repeat-v1",
        host_receipts={h:dict(manifest_sha256=source_pins[h]["manifest_sha256"],
            relative_to_pooled_median=result["retained_host_ratios"][h]) for h in result["included"]})
    store.write("fleet_reference.json",provenance)
    store.write("pool-complete.json",dict(completed=True,final=False,live_actions=False,outcome_access=False))
    # Verify again before completion, preserving originals as SHA-bound sources.
    for entry in source_pins.values():
        directory=Path(entry["directory"]);seal=directory/"receipt-manifest.json"
        if sha(seal) != entry["manifest_sha256"]:raise ValueError("Host seal changed during pooling")
        verify_files(directory,json.loads(seal.read_text())["files"])
