"""PREREG-K4S END pooling (r3 §4.5; delta 8): sealed per-host END receipts -> clasher.k4s.mac-fleet-reference.v1.

Never reads game or outcome bytes: only timing, census, MHz and health-only END evidence.

Pooling rules (r3 §4.5; frozen TIERS e4v3/fleet_pool.py conventions):
- population: the 300 frozen T1 K4 corpus states (inventory 81f2483e), K4S no-deadline work unit;
- per-state pooled value = median over every counted host x repeat (raw-host-times-repeat);
- host ratio = geometric mean over states of (pooled per-state median) / (host per-state median of its 3
  repeats), the frozen fleet_pool.py statistic and direction; every host must lie in [0.95, 1.05]
  inclusive (nearest doubles; NOT the frozen float form abs(r-1) <= .05, which rejects both endpoint
  doubles) or the pool fails closed. Counted hosts can never be excluded;
- deadline cells carry integer counts over every host x state x repeat in the canonical naming
  (k4s_logic.deadline_cell_record: rate = key, count = key + "_count").
Identity: common pins (k4s_logic.END_FROZEN_PIN_KEYS = the frozen K4S manifest's kernel/scorer/SD1/corpus/native,
its own SHA and every END measurement source; END_SHARED_PIN_KEYS = bundle runtime/measurement/model pins) must be
equal on every host and the frozen ones equal to the descriptor's frozen K4S manifest. Each host's own bundle
manifest (it names that host) is a per-host receipt (END_HOST_PIN_KEYS), validated per host and retained.
Provenance (r3 §4.5, A1.1-A1.3): committed reporting completion, counted-host set and the ported frozen
membership/loss/replacement reconciliation (end_evidence.py); the committed END attempt registry defines every
original attempt per host (exact membership and order); every attempt is read only through its verified seal and
classified by the frozen fleet_validity.classify_attempt after its failure/completion receipts are reconciled;
slot 0 / every background slot / priority from the pinned plan (frozen fleet_profile.slot_layout), the frozen
reporting guard validators, and the 1 Hz reference MHz against full-occupancy reporting rows (frozen
fleet_end.host_reporting + fleet_profile.compare_mhz) with the signed ratio retained. reporting_load_profile is true
only when every one of these checks passed. Every consumed file is recorded (pool-inputs.json); the re-check
requires them all to be in its before/after input inventory.

  end_pool.py pool --pool-input D.json --pool-input-sha256 S --output NEW_POOL_DIR
  end_pool.py recheck --pool-input D.json --pool-input-sha256 S --pool NEW_POOL_DIR --checked-by WHO \
      --output end-recheck.json            # independent re-execution (T1 check_reference.py pattern)
"""
import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE / "mac"), str(HERE)]      # explicit: `python -I` omits the script directory
import k4s_logic as L  # noqa: E402
import end_evidence as E  # noqa: E402

RAW_SCHEMA = "clasher.k4s.end-reference-raw.v3"
EVIDENCE_SCHEMA = E.EVIDENCE_SCHEMA
POOL_INPUT_SCHEMA = "clasher.k4s.end-pool-input.v2"
POOL_SCOPE = "K4S-END-POOL"
REFERENCE_SCOPE = "K4S-END-REFERENCE"
TIMING_KEYS = ("k4_wall", "k4s_wall", "sd1_poll", "v1_poll")
REPEATS = (0, 1, 2)
BLOCK = 50
COUNTED_BLOCKS = E.COUNTED_BLOCKS
FROZEN_HELPERS = ("fleet_end.py", "fleet_profile.py", "fleet_validity.py", "fleet_pool.py", "fleet_reference.py",
                  "receipts.py", "tier_backend.py", "replay_load.py", "telemetry.py", "corpus_contract.py")
# Every receipt a passing attempt must seal (all consumed below); a passing seal may hold no failure evidence.
COMPLETE_REQUIRED = ("attempt-claim.json", "end-identity.json", "reporting-full-occupancy-mhz.json",
                     "slot-evidence.json", "guard-admission.json", "capacity.jsonl", "guard-blocks.jsonl",
                     "reference-warmup.json", "reporting-mhz-comparison.json", "end-raw.json", "end-complete.json")
FAILURE_FILES = ("failure.json", "cleanup-failure.json")
LOW, HIGH = L.HOST_RATIO_WINDOW
PoolError = E.EvidenceError
require = E.require
end_evidence = E.end_evidence


def positive(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and value > 0


def nonnegative(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and value >= 0


# ---------------------------------------------------------------- timing validation and statistics

def validate_raw(raw, ids):
    """Exact frozen state inventory; 3 finite positive timings per state; each deadline
    (cell, state, repeat 0-2) exactly once with Boolean flags and registered budget/charge."""
    require(isinstance(raw, dict) and raw.get("schema") == RAW_SCHEMA, "Unsupported raw END schema")
    require(raw.get("repeats") == 3, "Raw END must declare exactly 3 repeats")
    host_pins = raw.get("host_pins")
    require(isinstance(host_pins, dict) and set(host_pins) == set(L.END_HOST_PIN_KEYS)
            and L.is_sha256(host_pins["bundle_manifest_sha256"]) and host_pins["bundle_profile_host"] == raw.get("host"),
            "Raw END lacks its own per-host bundle/profile receipt")
    states = raw.get("states")
    require(isinstance(states, dict) and set(states) == set(ids), "Raw END states differ from the frozen inventory")
    for identity in ids:
        row = states[identity]
        require(isinstance(row, dict) and set(row) == set(TIMING_KEYS) | {"result"}, "Raw END state fields: " + identity)
        for key in TIMING_KEYS:
            values = row[key]
            require(isinstance(values, list) and len(values) == 3, "Exactly three " + key + " timings: " + identity)
            require(all(positive(v) for v in values), "Invalid " + key + " timing: " + identity)
        result = row["result"]
        require(isinstance(result, dict) and set(result) == {"action", "candidates", "scores"},
                "Raw END lacks the no-deadline result: " + identity)
    deadline = raw.get("deadline")
    require(isinstance(deadline, dict) and set(deadline) == set(L.BUDGET_MS), "Raw END needs exactly the five cells")
    wanted = set(ids)
    for cell, block in deadline.items():
        require(isinstance(block, dict) and type(block.get("budget_ms")) is int and block["budget_ms"] == L.BUDGET_MS[cell],
                "Unregistered deadline budget: " + cell)
        require(block.get("charge_scale") == L.charge_scale_text(cell), "Unregistered 1/c charge scale: " + cell)
        rows = block.get("rows")
        require(isinstance(rows, list), "Deadline rows missing: " + cell)
        seen = set()
        for row in rows:
            require(isinstance(row, dict) and row.get("id") in wanted, "Unknown deadline state: " + cell)
            require(type(row.get("repeat")) is int and row["repeat"] in REPEATS, "Deadline repeat must be 0-2: " + cell)
            key = (row["id"], row["repeat"])
            require(key not in seen, "Duplicate deadline (cell, state, repeat): " + cell + "/" + row["id"])
            for flag in L.DEADLINE_RATE_KEYS:
                require(type(row.get(flag)) is bool, "Deadline flag must be Boolean: " + flag)
            require(positive(row.get("wall_seconds")) and positive(row.get("poll_seconds"))
                    and nonnegative(row.get("scale_sleep_seconds")), "Invalid deadline timing: " + cell)
            seen.add(key)
        require(len(seen) == 3 * len(ids), "Every (state, repeat) exactly once in cell " + cell)
    return raw


def geometric(values):
    """Identical to the frozen e4v3/fleet_pool.py geometric() (cross-checked by a test)."""
    if not values or any(not math.isfinite(v) or v <= 0 for v in values):
        raise PoolError("Invalid host speed ratio")
    return math.exp(sum(math.log(v) for v in values) / len(values))


def host_ratios(walls):
    """walls: {host: {state: [3 raw repeats]}} -> pooled per-state medians and per-host ratios.

    Frozen TIERS direction: geometric mean over states of pooled / host median (fleet_pool.py
    ``initial[key] / quantiles(w[key])["p50"]``). A host that is slower has a ratio below 1.
    """
    hosts = sorted(walls)
    keys = sorted(walls[hosts[0]])
    pooled = {k: L.quantiles([v for h in hosts for v in walls[h][k]])["p50"] for k in keys}
    return pooled, {h: geometric([pooled[k] / L.quantiles(walls[h][k])["p50"] for k in keys]) for h in hosts}


def within_window(ratio):
    """K4S r3 §4.5 inclusive window (k4s_logic.in_host_ratio_window), not the frozen TIERS float form."""
    return L.in_host_ratio_window(ratio)


def pool(raws, ids):
    """Pure timing pool over validated raw END records (one per counted host)."""
    require(isinstance(raws, list) and raws, "No raw END records")
    hosts = [r.get("host") if isinstance(r, dict) else None for r in raws]
    require(all(isinstance(h, str) and h for h in hosts) and len(set(hosts)) == len(hosts), "One raw END record per host")
    for raw in raws:
        validate_raw(raw, ids)
    by_host = {r["host"]: r for r in raws}
    hosts = sorted(by_host)
    corpus = {r.get("corpus_sha256") for r in raws}
    require(len(corpus) == 1 and L.is_sha256(next(iter(corpus))), "Raw END corpora differ")
    # Common identity only: per-host bundle receipts legitimately differ (each names its own host).
    pins = [L.canonical(r.get("pins")) for r in raws]
    require(isinstance(raws[0].get("pins"), dict) and len(set(pins)) == 1, "Hosts measured different common pins")
    states = {}
    for identity in sorted(ids):
        results = {L.canonical(by_host[h]["states"][identity]["result"]) for h in hosts}
        require(len(results) == 1, "Exactness mismatch: cross-host no-deadline K4S result " + identity)

        def median(key):
            return L.quantiles([v for h in hosts for v in by_host[h]["states"][identity][key]])["p50"]
        states[identity] = dict(k4s_wall_seconds=median("k4s_wall"), sd1_poll_seconds=median("sd1_poll"),
                                k4_wall_seconds=median("k4_wall"), v1_poll_seconds=median("v1_poll"),
                                result=by_host[hosts[0]]["states"][identity]["result"])
    pooled, ratios = host_ratios({h: {i: by_host[h]["states"][i]["k4s_wall"] for i in ids} for h in hosts})
    if any(pooled[i] != states[i]["k4s_wall_seconds"] for i in ids):
        raise PoolError("Pooled wall disagrees with the ratio population")
    deadline = {}
    for cell in L.BUDGET_MS:
        rows = [row for h in hosts for row in by_host[h]["deadline"][cell]["rows"]]
        counts = {key: sum(row[key] for row in rows) for key in L.DEADLINE_RATE_KEYS}
        deadline[cell] = L.deadline_cell_record(cell, len(rows), counts)
    return dict(corpus_sha256=corpus.pop(), repeats=3, hosts=hosts, host_ratio_to_pool=ratios,
                ratio_statistic=L.HOST_RATIO_STATISTIC, ratio_window=[float(LOW), float(HIGH)],
                pool_conforms=all(within_window(v) for v in ratios.values()), pins=raws[0]["pins"],
                states=states, deadline=deadline)


def reference_document(timing, provenance):
    """The Mac contract (K4S-MAC-PROCEDURE.md §3). reporting_load_profile only when evidenced."""
    evidence = provenance.get("reporting_load_profile_evidence", {})
    evidenced = all(evidence.get(k) is True for k in L.REPORTING_EVIDENCE_KEYS)
    return dict(schema=L.FLEET_REFERENCE_SCHEMA, reporting_load_profile=evidenced, provenance=provenance, **timing)


# ---------------------------------------------------------------- frozen helpers (read only)

def frozen_helpers(k4s_manifest, root=ROOT):
    """Import the frozen e4v3 fleet helpers read only, after their K4S-manifest pins match."""
    reused = k4s_manifest["reused_readonly"]
    pins = {L.E4V3_REL + "/" + name: reused.get(L.E4V3_REL + "/" + name) for name in FROZEN_HELPERS}
    L.verify_pinned(root, pins, "frozen e4v3 fleet helpers")
    directory = str(Path(root) / L.E4V3_REL)
    if directory not in sys.path:
        sys.path.insert(0, directory)
    import fleet_end
    import fleet_profile
    import fleet_validity
    for module in (fleet_end, fleet_profile, fleet_validity):
        require(Path(module.__file__).resolve().parent == Path(directory).resolve(), "Wrong e4v3 helper imported")
    return fleet_end, fleet_profile, fleet_validity


def load_json(path):
    text = Path(path).read_text()
    return json.loads(text.splitlines()[0]) if text.count("\n") <= 1 else json.loads(text)


def read_lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


class Consumed(dict):
    """path -> SHA-256 of every local file the pool read (recorded in pool-inputs.json)."""

    def read(self, path):
        path = Path(path)
        data = path.read_bytes()
        self[str(path.resolve())] = L.sha_bytes(data)
        return data


# ---------------------------------------------------------------- per-host receipts

def expected_blocks(ids):
    """Guard block identities end_reference.py checkpoints for every measured work block."""
    blocks = {f"speed-{r}-{o}" for r in REPEATS for o in range(0, len(ids), BLOCK)}
    blocks |= {f"deadline-{r}-{c}-{o}" for r in REPEATS for c in L.BUDGET_MS for o in range(0, len(ids), BLOCK)}
    return blocks


def reconcile(sealed, label):
    """Seal status vs failure/completion receipts (r2 finding 16): a poolable seal is complete with every required
    receipt and no failure or cleanup-failure evidence; a failed seal carries failure.json and no completion."""
    if sealed.status == "complete":
        missing = [n for n in COMPLETE_REQUIRED if not sealed.has(n)]
        require(not missing, label + " complete seal lacks: " + ",".join(missing))
        require(not any(sealed.has(n) for n in FAILURE_FILES), "Contradictory END attempt seal: " + label
                + " is complete but carries failure/cleanup evidence")
        complete = sealed.json("end-complete.json")
        require(complete.get("completed") is True and complete.get("cleanup_succeeded") is True,
                "Contradictory END attempt seal: completion without successful cleanup: " + label)
    elif sealed.status == "failed":
        require(sealed.has("failure.json") and not sealed.has("end-complete.json"),
                "Contradictory END attempt seal: " + label + " failed without failure.json or with a completion")
    else:
        raise PoolError("Unadmissible END attempt status " + str(sealed.status) + ": " + label)
    for name in ("attempt-claim.json", "end-identity.json"):
        require(sealed.has(name), label + " seal lacks " + name)


def classify_attempts(host, attempts, registry, evidence, fleet_validity, consumed):
    """Every original attempt in the committed registry order (exact membership; the descriptor cannot omit or
    add one); at most one repeat; only the last may pass; earlier ones must be mechanically classified technical
    repeat candidates (frozen classify_attempt on a verified, reconciled seal; exactness never earns a repeat)."""
    claims = registry.get(host, [])
    require(isinstance(attempts, list) and len(attempts) == len(claims) and claims,
            "Pool descriptor attempts differ from the committed END attempt registry: " + host)
    require(len(attempts) <= 2, "Each host may have at most one repeat (registry lists " + str(len(attempts)) + "): " + host)
    classified, passing, last = [], None, None
    for index, (entry, (claim, claim_sha)) in enumerate(zip(attempts, claims)):
        label = f"END attempt {host}/{index}"
        sealed = E.SealedReceipt(entry["directory"], entry["manifest_sha256"], scope=REFERENCE_SCOPE, label=label,
                                 consumed=consumed)
        reconcile(sealed, label)
        bound = sealed.json("attempt-claim.json")
        require(bound.get("claim") == claim and bound.get("claim_sha256") == claim_sha
                and claim["receipt_directory"] == Path(entry["directory"]).name,
                "Attempt receipt is not the registry's claim (omitted/reordered attempt): " + label)
        identity = sealed.json("end-identity.json")
        require(identity.get("host") == host and identity.get("end_kind") == "counted-reporting"
                and identity.get("end_evidence_sha256") == evidence["sha256"]
                and identity.get("attempt_claim_sha256") == claim_sha, "Attempt host/committed END binding differs")
        stamp = identity.get("utc")
        require(positive(stamp) and (last is None or stamp > last), "Attempts must be strictly chronological")
        last = stamp
        verdict = fleet_validity.classify_attempt(sealed.directory, sealed.manifest)
        classified.append(dict(manifest_sha256=entry["manifest_sha256"], attempt=index, claim_sha256=claim_sha, **verdict))
        if verdict["passes"]:
            require(index == len(attempts) - 1, "A passing attempt forbids a later attempt")
            passing = sealed
        else:
            require(verdict["technical_repeat_candidate"] is True, "Unrepeatable END failure (exactness never earns a repeat)")
    require(passing is not None, "No passing END attempt: re-run or coordinator ratio-unavailable declaration")
    return passing, classified


def validate_host(host, entry, evidence, ids, expected_frozen, helpers, registry, consumed):
    """One counted host's passing receipt, read only through its verified seal: pins, slots, priority, guard,
    warm-up and MHz."""
    fleet_end, fleet_profile, fleet_validity = helpers
    sealed, attempts = classify_attempts(host, entry["attempts"], registry, evidence, fleet_validity, consumed)
    identity = sealed.json("end-identity.json")
    complete = sealed.json("end-complete.json")
    require(complete.get("completed") is True and complete.get("repeats") == 3 and complete.get("poolable") is True
            and complete.get("reporting_load_profile") is True and complete.get("outcome_access") is False
            and complete.get("live_actions") is False, "Unqualified END completion receipt: " + host)
    require(identity["counted_hosts"] == evidence["counted_hosts"] and identity["plan_sha256"] == evidence["plan_sha256"],
            "END receipt counted-host set / plan differ from the committed evidence")
    try:
        L.check_end_pins(identity.get("pins"), expected_frozen, "END receipt " + host)
    except L.PreconditionRefusal as error:
        raise PoolError(str(error)) from None
    host_pins = identity.get("host_pins")
    require(isinstance(host_pins, dict) and set(host_pins) == set(L.END_HOST_PIN_KEYS)
            and L.is_sha256(host_pins["bundle_manifest_sha256"]) and host_pins["bundle_profile_host"] == host,
            "END receipt lacks its own bundle/profile receipt: " + host)
    plan = evidence["plan"]
    profile = identity["load_profile"]
    require(profile.get("host") == host and profile.get("reference_slot") == 0 and profile.get("perception") == "none",
            "END profile must be reference slot 0 without perception: " + host)
    require(identity["nice"] == plan["compute"]["nice"] and identity["scheduler"] == "SCHED_OTHER",
            "END priority differs from the reporting plan")
    search, background, census_cpu = fleet_profile.slot_layout(profile, plan, host, identity["nice"])
    require(identity["search_cpus"] == search and identity["background_masks"] == background
            and identity["census_cpu"] == census_cpu, "END slot masks differ from the pinned reporting plan")
    slots = sealed.json("slot-evidence.json")
    require(slots.get("reference_affinity") == sorted(search) and slots.get("reference_nice") == identity["nice"],
            "Reference slot affinity/priority read-back differs")
    require([sorted(m) for m in slots.get("background_affinity", [])] == [sorted(m) for m in background]
            and slots.get("background_nice") == [identity["nice"]] * len(background),
            "Every background slot must run under the reporting masks and priority")
    fleet_validity.validate_admission(sealed.json("guard-admission.json"))
    census = sealed.lines("capacity.jsonl")
    fleet_validity.validate_census(census)
    blocks = sealed.lines("guard-blocks.jsonl")
    fleet_validity.validate_blocks(blocks, require_measurement=False)
    completed = {row["id"] for row in blocks if row["event"] == "end"}
    require(expected_blocks(ids) <= completed and any(i.startswith("warm-") for i in completed),
            "Missing measured/warm-up reporting guard blocks: " + host)
    warm = sealed.json("reference-warmup.json")
    require(warm["seconds"] >= profile["warmup_seconds"] >= 300 and warm["all_slots_active"] is True
            and warm["all_background_slots"] == len(background) and type(warm["reference_slot_work"]) is int
            and warm["reference_slot_work"] >= 1, "Reference and every background slot must warm >= 300 s")
    reporting = fleet_end.host_reporting(evidence, profile, plan)
    stored_rows = sealed.json("reporting-full-occupancy-mhz.json").get("rows")
    require(L.canonical(stored_rows) == L.canonical(reporting), "Recorded full-occupancy reporting rows do not recompute")
    clocks = fleet_profile.compare_mhz(reporting, census, search + sum(background, []), profile["slot_count"])
    stored = {k: v for k, v in sealed.json("reporting-mhz-comparison.json").items() if k != "scope"}
    require(L.canonical(stored) == L.canonical(clocks), "Signed reporting MHz comparison does not recompute")
    require(clocks["passes"] is True, "Reference/reporting MHz differs by more than 5%: " + host)
    raw = sealed.json("end-raw.json")
    require(raw.get("host") == host and raw.get("pins") == identity["pins"] and raw.get("host_pins") == host_pins,
            "Raw END record not bound to its identity")
    return raw, dict(manifest_sha256=sealed.sha256, attempts=attempts, search_cpus=search,
                     background_masks=background, nice=identity["nice"], host_pins=host_pins,
                     reference_to_reporting_mean=clocks["reference_to_reporting_mean"],
                     mhz_comparison_passes=True)


def expected_pins_from(k4s_manifest, k4s_manifest_sha256, kernel_rel, scorer_rel):
    try:
        return L.end_frozen_pins(k4s_manifest, k4s_manifest_sha256, kernel_rel, scorer_rel)
    except L.PreconditionRefusal as error:
        raise PoolError(str(error)) from None


def run_pool(descriptor_path, descriptor_sha256, output, repository=ROOT, root=ROOT):
    """Validate every input, pool, and write a sealed K4S-END-POOL directory (deterministic bytes)."""
    consumed = Consumed()
    descriptor_path = Path(descriptor_path)
    raw_descriptor = consumed.read(descriptor_path)
    require(L.sha_bytes(raw_descriptor) == descriptor_sha256, "Pool descriptor SHA mismatch")
    request = json.loads(raw_descriptor)
    require(request.get("schema") == POOL_INPUT_SCHEMA and request.get("hosts") and request.get("pooled_by"),
            "Unsupported pool descriptor")
    manifest_sha = request["k4s_manifest"]["sha256"]
    require(L.sha_bytes(consumed.read(request["k4s_manifest"]["path"])) == manifest_sha, "K4S manifest SHA mismatch")
    k4s_manifest = L.load_k4s_manifest(request["k4s_manifest"]["path"], manifest_sha, root, require_frozen=True)
    helpers = frozen_helpers(k4s_manifest, root)
    inventory_raw = consumed.read(request["corpus_inventory"]["path"])
    require(L.sha_bytes(inventory_raw) == request["corpus_inventory"]["sha256"], "Corpus inventory SHA mismatch")
    ids = L.check_corpus(L.T1_K4_CORPUS_SHA, L.T1_K4_CORPUS_SHA, json.loads(inventory_raw), None, None)
    evidence = E.end_evidence(request["end_evidence"]["path"], request["end_evidence"]["sha256"], repository, helpers[0])
    consumed[str(Path(request["end_evidence"]["path"]).resolve())] = request["end_evidence"]["sha256"]
    consumed.update({str(Path(p).resolve()): d for p, d in evidence["files"].items()})
    hosts = [entry["host"] for entry in request["hosts"]]
    require(sorted(hosts) == evidence["counted_hosts"] and len(set(hosts)) == len(hosts),
            "Pool host list must equal ALL committed counted hosts (no exclusion after counting)")
    registry_ref = request.get("attempt_registry") or {}
    registry = E.committed_registry(repository, registry_ref.get("commit"), registry_ref.get("repository_path"))
    require(set(registry) == set(hosts), "Committed END attempt registry hosts differ from the counted hosts")
    expected = expected_pins_from(k4s_manifest, manifest_sha, request["kernel_rel"], request["scorer_rel"])
    raws, receipts = [], {}
    for entry in sorted(request["hosts"], key=lambda e: e["host"]):
        raw, record = validate_host(entry["host"], entry, evidence, ids, expected, helpers, registry, consumed)
        raws.append(raw)
        receipts[entry["host"]] = record
    timing = pool(raws, ids)
    for host in timing["hosts"]:
        receipts[host]["ratio_to_pool"] = timing["host_ratio_to_pool"][host]
    provenance = dict(
        pool_input_sha256=descriptor_sha256, end_evidence_sha256=evidence["sha256"],
        completion_sha256=evidence["completion_sha256"], plan_sha256=evidence["plan_sha256"],
        counted_hosts=evidence["counted_hosts"], membership=evidence["membership"], host_receipts=receipts,
        attempt_registry=dict(commit=registry_ref["commit"], repository_path=registry_ref["repository_path"],
                              claims={h: [sha for _, sha in v] for h, v in sorted(registry.items())}),
        k4s_manifest_sha256=manifest_sha, pooled_by=request["pooled_by"], pooler_sha256=L.sha(Path(__file__).resolve()),
        population="frozen T1 K4 speed corpus, 300 states (inventory 81f2483e); K4S no-deadline work unit",
        reporting_load_profile_evidence={k: True for k in L.REPORTING_EVIDENCE_KEYS})
    document = reference_document(timing, provenance)
    store = L.K4SStore(output, POOL_SCOPE)
    try:
        store.write("end-reference.json", document)
        store.write("pool-inputs.json", dict(consumed=dict(sorted(consumed.items()))))
        if not document["pool_conforms"]:
            store.write("pool-nonconforming.json", dict(host_ratio_to_pool=timing["host_ratio_to_pool"],
                        rule="r3 §4.5: re-run or coordinator ratio-unavailable declaration; no host exclusion"))
        store.seal("complete" if document["pool_conforms"] else "nonconforming")
    except BaseException:
        store.seal("failed")
        raise
    return document


def input_files(request, descriptor_path, repository=ROOT):
    """Every pooled input by absolute path -> SHA-256: the descriptor, every descriptor-named file, the END
    evidence and each committed artifact it names, and every file in every attempt directory (whole listing,
    sealed or not)."""
    files = {str(Path(descriptor_path).resolve()): L.sha(descriptor_path)}
    for key in ("end_evidence", "corpus_inventory", "k4s_manifest"):
        files[str(Path(request[key]["path"]).resolve())] = L.sha(request[key]["path"])
    evidence_path = Path(request["end_evidence"]["path"])
    for item in E.evidence_items(json.loads(evidence_path.read_bytes())):
        path = (evidence_path.parent / item["path"]).resolve()
        files[str(path)] = L.sha(path) if path.is_file() else None
    for entry in request["hosts"]:
        for attempt in entry["attempts"]:
            directory = Path(attempt["directory"])
            for path in sorted(directory.rglob("*")):
                if path.is_file():
                    files[str(path.resolve())] = L.sha(path)
    return files


def recheck(descriptor_path, descriptor_sha256, pool_dir, checked_by, output, repository=ROOT):
    """Independent re-execution in a fresh interpreter (-I), byte comparison with the sealed pool,
    inputs unchanged before/after and covering every consumed file; emits clasher.k4s.end-recheck.v1."""
    descriptor_path, pool_dir, output = Path(descriptor_path).resolve(), Path(pool_dir).resolve(), Path(output)
    require(not output.exists(), "Re-check receipt already exists")
    require(L.sha(descriptor_path) == descriptor_sha256, "Pool descriptor SHA mismatch")
    request = load_json(descriptor_path)
    require(checked_by and checked_by != request["pooled_by"], "The re-check must be run by someone other than the pooler")
    seal_sha = L.sha(pool_dir / "receipt-manifest.json")
    sealed = E.SealedReceipt(pool_dir, seal_sha, scope=POOL_SCOPE, label="K4S END pool")
    require(sealed.status == "complete" and sealed.has("end-reference.json") and sealed.has("pool-inputs.json"),
            "Pool is not a complete K4S END pool")
    before = input_files(request, descriptor_path, repository)
    consumed = sealed.json("pool-inputs.json")["consumed"]
    missing = sorted(p for p, d in consumed.items() if before.get(p) != d)
    require(not missing, "Re-check input inventory omits/changes consumed pool inputs: " + ",".join(missing[:3]))
    with tempfile.TemporaryDirectory(prefix="k4s-end-recheck-") as scratch:
        target = Path(scratch) / "pool"
        subprocess.run([sys.executable, "-I", "-B", str(Path(__file__).resolve()), "pool", "--pool-input",
                        str(descriptor_path), "--pool-input-sha256", descriptor_sha256, "--output", str(target),
                        "--repository", str(repository)], check=True, stdout=subprocess.DEVNULL,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        repeated = load_json(target / "receipt-manifest.json")
        require(repeated["files"] == sealed.files and repeated["status"] == sealed.status, "Pooled outputs differ on re-check")
        for name, digest in sealed.files.items():
            require(L.sha(target / name) == digest, "Re-checked pooled bytes differ: " + name)
    require(input_files(request, descriptor_path, repository) == before, "Pool inputs changed during the re-check")
    require(L.sha(pool_dir / "receipt-manifest.json") == seal_sha, "Pool seal changed during the re-check")
    document = sealed.json("end-reference.json")
    prov = document["provenance"]
    result = dict(schema=L.END_RECHECK_SCHEMA, passes=True, outcome_access=False, checked_by=checked_by,
                  checked_at_utc=time.time(), reference_sha256=sealed.files["end-reference.json"],
                  pool_manifest_sha256=seal_sha, pool_input_sha256=descriptor_sha256,
                  end_evidence_sha256=prov["end_evidence_sha256"],
                  host_receipts={h: r["manifest_sha256"] for h, r in prov["host_receipts"].items()},
                  attempt_registry_commit=prov["attempt_registry"]["commit"],
                  checker_sha256=L.sha(Path(__file__).resolve()), input_files=before)
    with output.open("x") as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("pool", "recheck"):
        p = sub.add_parser(name)
        p.add_argument("--pool-input", type=Path, required=True)
        p.add_argument("--pool-input-sha256", required=True)
        p.add_argument("--output", type=Path, required=True)
        p.add_argument("--repository", type=Path, default=ROOT)
        if name == "recheck":
            p.add_argument("--pool", type=Path, required=True)
            p.add_argument("--checked-by", required=True)
    args = parser.parse_args(argv)
    if args.command == "pool":
        document = run_pool(args.pool_input, args.pool_input_sha256, args.output, args.repository)
        print(json.dumps(dict(pool_conforms=document["pool_conforms"], ratios=document["host_ratio_to_pool"])))
        if not document["pool_conforms"]:
            raise SystemExit("pool fails closed (r3 §4.5): re-run or coordinator ratio-unavailable declaration")
        return 0
    result = recheck(args.pool_input, args.pool_input_sha256, args.pool, args.checked_by, args.output, args.repository)
    print(json.dumps(dict(passes=result["passes"], reference_sha256=result["reference_sha256"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
