"""Amendment 1 committed health-only evidence; never reads game/outcome bytes."""
import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from receipts import sha, verify_files

AMENDMENT_SHA = "b35bd4e5d8beaf8e89ade092bdf4fc607e067e562f7d9f378fb9c06367df2775"


def relative(name):
    p = Path(name)
    if p.is_absolute() or ".." in p.parts or not p.parts:
        raise ValueError("Evidence path must be relative without traversal")
    return p


def artifact(bundle, manifest, repository, item, committed=True):
    path = relative(item["path"])
    if manifest["files"].get(str(path)) != item["sha256"] or sha(Path(bundle)/path) != item["sha256"]:
        raise ValueError("END evidence pin mismatch: " + str(path))
    data = (Path(bundle)/path).read_bytes()
    if committed:
        commit = item["commit"]
        name = relative(item["repository_path"])
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("END evidence requires a full commit")
        raw = subprocess.check_output(["git", "-C", str(repository), "show", commit+":"+str(name)])
        if raw != data or hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError("END evidence differs from committed T1 bytes")
        subprocess.run(["git", "-C", str(repository), "merge-base", "--is-ancestor", commit, "HEAD"], check=True)
    return data


def utc(value):
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.utcoffset() is None:
        raise ValueError("Evidence timestamps require a timezone")
    return t


def counting(e, completion, phases):
    """Health-only membership, blind losses and logical coverage; no outcomes."""
    ledger, inventory = e["blind_ledger"], e["counted_inventory"]
    if ledger.get("sealed") is not True or inventory.get("outcomes_sealed") is not True:
        raise ValueError("END requires sealed blind ledger and counted inventory")
    if inventory.get("schema") != "clasher.t1.counted-blocks.v1":
        raise ValueError("Unsupported counted-block inventory")
    if set(inventory) != {"schema","outcomes_sealed","blocks"} or not set(ledger) <= {"utc","sealed","events"}:
        raise ValueError("Unknown/non-health counted inventory or ledger fields")
    completed, unsuccessful = {}, {}
    descriptor_fields = {"id", "population", "index", "seed", "cell", "seat", "own_index",
                         "opponent_index", "order", "replaces", "dispatch", "host"}
    def descriptor(d):
        if not {"id","population","host"} <= set(d) or not set(d) <= descriptor_fields:
            raise ValueError("END block descriptor contains unknown/non-health fields")
    for key, values in phases.items():
        exit_ = values["supervisor_exit"]
        seen = set()
        for group in ("completed", "failed", "unstarted"):
            for d in exit_[group]:
                descriptor(d)
                if d["id"] in seen or d["host"] != key[0]:
                    raise ValueError("Raw exit has duplicate/wrong-host block")
                seen.add(d["id"])
                target = completed if group == "completed" else unsuccessful
                target.setdefault(d["id"], []).append((key, d, group))
    losses, replacements = {}, {}
    for event in ledger["events"]:
        if not {"lost","replacement","evidence_sha256"} <= set(event) or not set(event) <= {"utc","lost","replacement","reason","evidence_sha256"}:
            raise ValueError("Unknown/non-health blind ledger event fields")
        lost = event["lost"]; identity = lost["id"]
        descriptor(lost)
        if identity in losses:
            raise ValueError("Duplicate blind ledger loss")
        candidates = completed.get(identity, []) + unsuccessful.get(identity, [])
        if not any(d == lost and group != "unstarted" and
                   phases[key]["exit_sha256"] == event["evidence_sha256"]
                   for key, d, group in candidates):
            raise ValueError("Blind ledger loss lacks verbatim raw exit binding")
        losses[identity] = lost
        replacement = event["replacement"]
        if replacement is not None:
            # Bank descriptors need not have their eventual host/dispatch yet.
            if not set(replacement) <= descriptor_fields:
                raise ValueError("Replacement has unknown/non-health fields")
            rid = replacement["id"]
            if rid in replacements or replacement["population"] != lost["population"] or replacement["cell"] != lost["cell"]:
                raise ValueError("Invalid blind ledger replacement")
            logical = lost.get("replaces") or identity
            if replacement.get("replaces") != logical:
                raise ValueError("Replacement changes logical block")
            replacements[rid] = replacement
    for identity, attempts in unsuccessful.items():
        if any(group == "failed" for _, _, group in attempts) and identity not in losses:
            raise ValueError("Failed block is absent from blind ledger")
    counted, logical, owners = set(), {p: set() for p in ("primary", "guard", "descriptive")}, set()
    for row in inventory["blocks"]:
        if set(row) != {"host", "phase", "descriptor"}:
            raise ValueError("Counted inventory must contain health-only membership rows")
        key = (row["host"], row["phase"]); d = row["descriptor"]; identity = d["id"]
        if identity in counted or identity in losses:
            raise ValueError("Duplicate/lost block counted at END")
        if not any(owner == key and raw == d for owner, raw, _ in completed.get(identity, [])):
            raise ValueError("Counted block lacks exact completed raw exit membership")
        if d.get("replaces"):
            transport_free = lambda value: {k:v for k,v in value.items() if k not in ("host","dispatch")}
            if identity not in replacements or transport_free(d) != transport_free(replacements[identity]):
                raise ValueError("Counted replacement lacks blind ledger binding")
        pop = d["population"]; lid = d.get("replaces") or identity
        if pop not in logical or not re.fullmatch(pop+r"-[0-9]+", lid) or lid in logical[pop]:
            raise ValueError("Invalid/duplicate counted logical block")
        logical[pop].add(lid); counted.add(identity); owners.add(key)
    for pop in ("primary", "guard"):
        count = completion["counted_"+pop+"_blocks"]
        if logical[pop] != {f"{pop}-{i:04d}" for i in range(count)}:
            raise ValueError("Counted inventory lacks complete logical population")
    wanted={(host,phase) for host,values in completion["counted_host_phases"].items() for phase in values}
    if owners != wanted:
        raise ValueError("Counted host/phase inventory differs from completion")
    return dict(blocks=len(counted), losses=len(losses), host_phases=sorted(owners))


def evidence(bundle, manifest, plan):
    profile = manifest["reference_load_profile"]
    name = profile["end_evidence"]
    if name not in manifest["files"] or sha(Path(bundle)/name) != manifest["files"][name]:
        raise ValueError("END evidence inventory must be SHA-pinned")
    obj = json.loads((Path(bundle)/name).read_text())
    if obj["schema"] != "clasher.e4v3.end-evidence.v1" or obj["kind"] not in ("counted-reporting", "unpoolable-smoke"):
        raise ValueError("Unsupported END evidence")
    committed = obj["kind"] == "counted-reporting"
    if not committed and plan.get("profile") != "e4v3-unpoolable-smoke":
        raise ValueError("Synthetic END evidence requires a smoke-labelled plan")
    if committed:
        amendment = profile["amendment"]
        if manifest["files"].get(amendment) != AMENDMENT_SHA or sha(Path(bundle)/amendment) != AMENDMENT_SHA:
            raise ValueError("Production END requires signed Amendment 1")
    completion = json.loads(artifact(bundle, manifest, obj["repository"], obj["completion"], committed))
    if completion["reporting_complete"] is not True or completion["outcomes_sealed"] is not True:
        raise ValueError("References require committed reporting completion and sealed outcomes")
    if committed and (completion["counted_primary_blocks"] != 2400 or completion["counted_guard_blocks"] != 600):
        raise ValueError("END completion lacks the full counted block population")
    expected = completion["counted_host_phases"]
    allowed = set(plan["compute"]["hosts"]) - set(plan["compute"].get("forbidden_hosts", []))
    if not expected or not set(expected) <= allowed:
        raise ValueError("Counted host set differs from pinned reporting plan")
    reporting_hosts = set(plan.get("reporting_hosts", sorted(allowed)))
    if committed and set(expected) != reporting_hosts:
        raise ValueError("END host set must equal every pinned reporting host")
    wanted = set()
    for host, phases in expected.items():
        if not phases or len(set(phases)) != len(phases):
            raise ValueError("Every counted host requires unique counted phases")
        for phase in phases:
            if phase != "reporting" and not re.fullmatch(r"replacement-r[1-9][0-9]*", phase):
                raise ValueError("Unregistered counted phase")
            wanted.add((host, phase))
    phases = {}
    for entry in obj["phases"]:
        key = (entry["host"], entry["phase"])
        if key[0] not in allowed or key in phases or (key[1] != "reporting" and not re.fullmatch(r"replacement-r[1-9][0-9]*",key[1])):
            raise ValueError("Duplicate/unknown END host phase")
        values = {}
        for field in ("launch", "supervisor_exit", "mhz", "census"):
            raw = artifact(bundle, manifest, obj["repository"], entry[field], committed)
            values[field] = [json.loads(s) for s in raw.splitlines()] if field in ("mhz", "census") else json.loads(raw)
        launch, exit_ = values["launch"], values["supervisor_exit"]
        if launch["host"] != key[0] or launch["phase"] != ("replacement" if key[1].startswith("replacement-") else "reporting") or exit_["host"] != key[0]:
            raise ValueError("END phase host/launch mismatch")
        if utc(exit_["utc"]) > utc(completion["completed_at_utc"]):
            raise ValueError("Completion precedes a supervisor exit")
        values["exit_sha256"] = entry["supervisor_exit"]["sha256"]
        phases[key] = values
    if not wanted <= set(phases):
        raise ValueError("Missing counted reporting/replacement phase evidence")
    counts = {}
    for field in ("blind_ledger", "counted_inventory"):
        if completion[field+"_sha256"] != obj[field]["sha256"]:
            raise ValueError("Completion does not bind END "+field)
        counts[field] = json.loads(artifact(bundle, manifest, obj["repository"], obj[field], committed))
    checked = counting(counts, completion, phases)
    return dict(kind=obj["kind"], inventory=obj, completion=completion, phases=phases,
                counted_hosts=sorted(expected), counting=checked, **counts, sha256=sha(Path(bundle)/name))


def host_reporting(e, profile, plan):
    host = profile["host"]
    if host not in e["counted_hosts"]:
        raise ValueError("Reference host has no counted reporting blocks")
    if profile["reference_slot"] != 0:
        raise ValueError("Amendment 1 registers reference slot zero on every host")
    selected = []
    for (owner, phase), values in e["phases"].items():
        if owner != host:
            continue
        if phase not in e["completion"]["counted_host_phases"][host]:
            continue
        launch = values["launch"]
        if launch["slots"] != profile["slot_count"]:
            raise ValueError("Reference slot count differs from counted reporting launch")
        census = {}
        for row in values["census"]:
            if row["utc"] in census or row["host"] != host:
                raise ValueError("Duplicate/wrong host census row")
            census[row["utc"]] = row
        seen = set()
        for row in values["mhz"]:
            key = row["utc"]
            if key in seen or key not in census or row["slots"] != launch["slots"]:
                raise ValueError("Missing/duplicate full-occupancy clock join")
            seen.add(key)
            c = census[key]
            if c["inflight"] == launch["slots"]:
                selected.append(dict(row, host=host, phase=phase, inflight=c["inflight"]))
        if seen != set(census):
            raise ValueError("Reporting MHz/census inventories differ")
    if len(selected) < 2:
        raise ValueError("Insufficient full-occupancy reporting clock observations")
    return selected


def pool_context(request):
    context = request["context"]
    bundle = Path(context["bundle"])
    if sha(bundle/"tiers-pins.json") != context["manifest_sha256"]:
        raise ValueError("Pool context manifest SHA mismatch")
    manifest = json.loads((bundle/"tiers-pins.json").read_text())
    verify_files(bundle, manifest["files"])
    profile = manifest["reference_load_profile"]
    plan = json.loads((bundle/profile["plan"]).read_text())
    e = evidence(bundle, manifest, plan)
    if e["kind"] != "counted-reporting":
        raise ValueError("A6 smoke receipts cannot be pooled")
    if set(entry["host"] for entry in request["hosts"]) != set(e["counted_hosts"]) or len(request["hosts"]) != len(e["counted_hosts"]):
        raise ValueError("Pool host list must equal ALL counted reporting/replacement hosts")
    return bundle, manifest, plan, e
