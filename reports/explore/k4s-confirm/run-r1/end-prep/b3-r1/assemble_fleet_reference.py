#!/usr/bin/env python3
"""K4S END fleet-reference bundle assembler (CANDIDATE b3-r1; offline; never launches anything, never reads outcomes).

One explicit, SHA-pinned request describes every input by absolute path and expected SHA-256. The assembler checks
everything first, then copies each input into a fresh bundle directory, re-hashes every copy and writes the
`tiers-pins.json` manifest (schema clasher.e4v3.inputs.v1, profile fleet-reference) that the frozen consumers read:
tier_backend.validate_bundle (A3 02e2139f), fleet_validity.ReportingGuard (A5 0775b704), fleet_profile.slot_layout,
end_reference.frozen_identity and end_background.k4s_reporting_profile. Any mismatch raises AssemblyError and
leaves no bundle. Inputs are only read. There are no globs over job or phase directories: evidence artifacts are
taken from the evidence's own relative item paths under one explicit root. The only directory walks are the frozen
prepare_bundle rules for `runtime_files` (runtime tree) and `measurement_files` (e4v3 directory), replicated
exactly (prepare_bundle.py:36-52, :117).

  assemble_fleet_reference.py --request R.json --request-sha256 S --out NEW_BUNDLE_DIR [--dry-run]

--dry-run validates everything (all hashes included) and prints the planned tiers-pins.json bytes to stdout;
it writes nothing. A real run prints nothing on stdout but writes NEW_BUNDLE_DIR/{<inputs>, tiers-pins.json,
tiers-pins.sha256, assembly-receipt.json} and prints a one-line summary to stderr.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path, PurePosixPath

REQUEST_SCHEMA = "clasher.k4s.end-fleet-reference-request.v1"
RECEIPT_SCHEMA = "clasher.k4s.end-fleet-reference-assembly.v1"
BUNDLE_SCHEMA = "clasher.e4v3.inputs.v1"
EVIDENCE_SCHEMA = "clasher.k4s.end-evidence.v1"
STATE_ROWS_SCHEMA = "clasher.e4v3.state-rows.v1"                  # state_rows.py:20
E4V3_REL = "reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3"
S1_RUNTIME_PINS = ("reports/explore/s1/receipts/runtime-pin-r2.json", "reports/explore/s1/receipts/runtime-pin.json")
S1_QUALIFIED = "reports/explore/s1/receipts/qualified-source-binding.json"

# Frozen values (tier_backend.py:18-21; FROZEN-T1.json at aeeb3003; K4S plan.json at 201db04c).
V1_SHA = "d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed"
STUDENT_SHA = "37509a4331bd02ae110b76e1825a2adb23fa78e0e70188e199b6ef90d19ade85"
CALIBRATION_SHA = "e300353346983e888d896b20412d4075496a6f14ef3625cefc7eeadacec5e414"
THRESHOLD = .5005528330802917
FROZEN_T1_SHA256 = "24817e16c3da7b5c9b6e48c56e69144e84678b7d143a146fe2884f446d07d7e4"
K4S_PLAN_SHA256 = "38064dcdeff96fb006f6e261c246a458f423d97cc53278c3921888241c8d22cf"

GUARD_MODULES = ("common", "host_audit", "idle_services", "system_bus", "ssh_transport",      # fleet_validity.py:10-11
                 "perception_confirmation", "owned_supervisor", "ssh_budget", "parent_source_seed")
GUARD_DELTAS = ("operational_delta_op5", "operational_delta_op5_08", "operational_delta_op6")  # fleet_validity.py:61
BUS_KEYS = ("pid", "start_ticks", "exe", "cmdline_sha256", "uid")                             # t1/system_bus.py:5
TIERS = ("K0c", "S", "K2", "K4")                                                               # receipts.py:7
MODEL_NAMES = ("v1.pt", "R3a.pt", "R3a-calibration.json", "states.pkl", "states-rows.json", "states-rows.bin")
ADMISSIONS = ("system-bus-admission.json", "idle-services.json")
# Guard-job namespaces (DESIGN.md §A.4): never T1's, never K4S reporting jobs, never 04 perception paths.
JOB_PARENTS = {"127x03": "/mpac/sdicks02/jobs/clasher", "127x04": "/mpac/sdicks02/jobs-k4s"}
JOB_NAME = re.compile(r"k4s-end-guard-r[1-9][0-9]*(-rd[0-9]{2}-a[0-9]{2})?")
PROFILE = dict(reference_slot=0, console_rule=False, warmup_seconds=300, perception="none")

# Bundle layout (T1 precedent END-A3-manifest-01-f6cebbaa.json; evidence kept in its own subdirectory).
EVIDENCE_DIR = "k4s-end-evidence"
EVIDENCE_NAME = EVIDENCE_DIR + "/end-evidence.json"
GUARD_ROOT, FREEZE_NAME, ADMISSION_DIR, SEED_DIR = "t1-guard", "t1-freeze.json", "guard-admissions", "seed-inputs"
MANIFEST, MANIFEST_SHA, RECEIPT = "tiers-pins.json", "tiers-pins.sha256", "assembly-receipt.json"

SHA256 = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")


class AssemblyError(ValueError):
    """Explicit fail-closed assembly error (never an assert; behaves the same under python -O)."""


def require(condition, message):
    if not condition:
        raise AssemblyError(message)


def canonical(value):
    """receipts.canonical (e4v3 receipts.py:10-11)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def relative(name, label):
    """A safe relative POSIX path: not absolute, no '.', '..' or empty parts."""
    require(isinstance(name, str) and name and "\\" not in name, "Unsafe relative path (" + label + "): " + repr(name))
    path = PurePosixPath(name)
    require(not path.is_absolute() and all(p not in ("", ".", "..") for p in name.split("/")),
            "Unsafe relative path (" + label + "): " + name)
    return str(path)


def no_outcome_path(path, label):
    """Defensive: no input may come from a games/ directory or be a block complete.json (as named or resolved)."""
    for candidate in (Path(path), Path(path).resolve()):
        require("games" not in candidate.parts and candidate.name != "complete.json",
                "Outcome-bearing path refused (" + label + ")")


def absolute(value, label, kind):
    require(isinstance(value, str) and value.startswith("/"), label + " must be an absolute path")
    path = Path(value)
    require(path.is_dir() if kind == "dir" else path.is_file(), label + " is not an existing " + kind + ": " + value)
    no_outcome_path(path, label)
    return path


def is_sha(value):
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def pinned_source(entry, label, expected=None):
    """{source, sha256} -> (path, sha); the file's SHA must equal the request's and, if given, the frozen value."""
    require(isinstance(entry, dict) and set(entry) == {"source", "sha256"}, "Input entry must be {source, sha256}: " + label)
    require(is_sha(entry["sha256"]), "Input SHA is not a SHA-256: " + label)
    require(expected is None or entry["sha256"] == expected, "Input SHA differs from the frozen value: " + label)
    path = absolute(entry["source"], label, "file")
    require(sha_file(path) == entry["sha256"], "Pin mismatch: " + label)
    return path, entry["sha256"]


def pinned_json(entry, label, expected=None):
    """Hash and parse the same bytes (no read-after-check gap for small JSON inputs)."""
    require(isinstance(entry, dict) and set(entry) == {"source", "sha256"}, "Input entry must be {source, sha256}: " + label)
    require(is_sha(entry["sha256"]), "Input SHA is not a SHA-256: " + label)
    require(expected is None or entry["sha256"] == expected, "Input SHA differs from the frozen value: " + label)
    path = absolute(entry["source"], label, "file")
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == entry["sha256"], "Pin mismatch: " + label)
    try:
        return path, entry["sha256"], json.loads(raw)
    except ValueError:
        raise AssemblyError("Not JSON: " + label) from None


# ---------------------------------------------------------------- frozen inventory rules (prepare_bundle.py)

def measurement_files(e4v3):
    """prepare_bundle.py:117, verbatim rule."""
    return {p.name: sha_file(p) for p in sorted(e4v3.iterdir()) if p.suffix in (".py", ".sh") or p.name == "spec-pins.json"}


def runtime_files(root):
    """prepare_bundle.runtime_pins (prepare_bundle.py:36-52), same rule; AssemblyError instead of ValueError."""
    source = root / S1_RUNTIME_PINS[0]
    if not source.is_file():
        source = root / S1_RUNTIME_PINS[1]
    require(source.is_file(), "Runtime lacks the S1 runtime pin")
    names = set(json.loads(source.read_text())["files"])
    names.update(str(p.relative_to(root)) for p in root.rglob("*.py"))
    missing = sorted(name for name in names if not (root / name).is_file())
    require(not missing, "Incomplete frozen runtime: " + repr(missing[:8]))
    result = {name: sha_file(root / name) for name in sorted(names)}
    qualified = json.loads((root / S1_QUALIFIED).read_text())
    for name, expected in qualified["qualified_source_files"].items():
        require(result.get(name) == expected, "Not the qualified S1 tier source: " + name)
    return result


# ---------------------------------------------------------------- planning (all checks; no writes)

def plan_bundle(request):
    """Every check, in order. Returns (copies {bundle name: (source, sha)}, manifest)."""
    require(isinstance(request, dict) and request.get("schema") == REQUEST_SCHEMA, "Unsupported request schema")
    keys = {"schema", "host", "runtime_root", "runtime_files_sha256", "measurement_files_sha256", "topology", "sets",
            "models", "end_evidence", "guard"}
    require(set(request) == keys, "Request keys differ from the schema: " + repr(sorted(set(request) ^ keys)))
    host = request["host"]
    require(host in JOB_PARENTS, "Host is not a K4S END host: " + repr(host))
    copies = {}

    def add(name, source, digest):
        name = relative(name, "bundle name")
        require(name not in copies and name not in (MANIFEST, MANIFEST_SHA, RECEIPT), "Bundle name collision: " + name)
        copies[name] = (source, digest)
        return name

    # 1. runtime + e4v3 (the e4v3 that end_reference imports is ROOT/E4V3_REL of the runtime tree)
    root = absolute(request["runtime_root"], "runtime_root", "dir")
    e4v3 = root / E4V3_REL
    require(e4v3.is_dir(), "Runtime lacks the e4v3 directory")
    measured = measurement_files(e4v3)
    require(is_sha(request["measurement_files_sha256"]) and canonical_sha(measured) == request["measurement_files_sha256"],
            "measurement_files differ from the request (computed " + canonical_sha(measured) + ")")
    try:
        specification = json.loads((e4v3 / "spec-pins.json").read_bytes())
    except (OSError, ValueError):
        raise AssemblyError("e4v3 spec-pins.json unreadable") from None
    runtime = runtime_files(root)
    require(is_sha(request["runtime_files_sha256"]) and canonical_sha(runtime) == request["runtime_files_sha256"],
            "runtime_files differ from the request (computed " + canonical_sha(runtime) + ")")

    # 2. models and state rows (tier_backend.py:459-461, :466-468; state_rows.py:27-58 index checks, no pickle)
    models = request["models"]
    require(isinstance(models, dict) and set(models) == set(MODEL_NAMES), "Model inputs must be exactly " + repr(MODEL_NAMES))
    frozen = {"v1.pt": V1_SHA, "R3a.pt": STUDENT_SHA, "R3a-calibration.json": CALIBRATION_SHA}
    model_pins = {}
    for name in MODEL_NAMES:
        if name == "states-rows.json":
            continue
        path, digest = pinned_source(models[name], "model " + name, frozen.get(name))
        model_pins[name] = digest
        add(name, path, digest)
    path, digest, index = pinned_json(models["states-rows.json"], "model states-rows.json")
    add("states-rows.json", path, digest)
    try:
        require(index["schema"] == STATE_ROWS_SCHEMA, "Unsupported state index")
        require(index["source"]["file"] == "states.pkl" and index["source"]["sha256"] == model_pins["states.pkl"]
                and index["source"].get("verified") is True, "State index is not derived from the pinned states.pkl")
        require(index["container"]["file"] == "states-rows.bin" and index["container"]["sha256"] == model_pins["states-rows.bin"],
                "State index names a different container")
        ids = [entry["id"] for entry in index["rows"]]
        require(len(ids) == index["source"]["rows"] and len(set(ids)) == len(ids), "State index rows differ/duplicate")
        require(os.path.getsize(copies["states-rows.bin"][0]) == index["container"]["bytes"],
                "State container size differs from its index")
    except (KeyError, TypeError, AttributeError):
        raise AssemblyError("Malformed state index") from None

    # 3. sets (TierBackend._load_inputs: golden + speed[, agreement, packets]; corpus_loop: speed[TIERS])
    _, _, sets = pinned_json(request["sets"], "sets")
    require(isinstance(sets, dict) and {"golden", "speed"} <= set(sets) <= {"golden", "speed", "agreement", "packets"},
            "sets must hold golden and speed (optional agreement, packets) only")
    require(isinstance(sets["speed"], dict) and set(sets["speed"]) == set(TIERS), "sets.speed must be exactly " + repr(TIERS))
    loaded = [sets["speed"][t] for t in TIERS] + [sets[k] for k in ("agreement", "packets") if k in sets]
    known = set(ids)
    for values in [sets["golden"]] + loaded:
        require(isinstance(values, list) and values and all(isinstance(v, str) for v in values)
                and len(set(values)) == len(values), "Every set must be a non-empty list of unique string IDs")
    for values in loaded:          # looked up by ID (backend.by_id / inputs); golden is only subtracted (tier_backend:147)
        require(set(values) <= known, "A set names a state absent from the pinned state index")

    # 4. topology (telemetry.validate_topology on the host; here only its Linux shape)
    topology = request["topology"]
    require(isinstance(topology, dict) and set(topology) == {"P", "E", "label"} and topology["E"] == []
            and isinstance(topology["label"], str) and topology["label"], "Topology must be {P, E: [], label}")
    p = topology["P"]
    require(isinstance(p, list) and p and all(type(c) is int and c >= 0 for c in p) and len(set(p)) == len(p),
            "Topology P must be unique non-negative logical CPU IDs")

    # 5. END evidence + every artifact at its own relative path (end_evidence.end_evidence; fleet_end.artifact)
    evidence = request["end_evidence"]
    require(isinstance(evidence, dict) and set(evidence) == {"source", "sha256", "artifacts_root"},
            "end_evidence must be {source, sha256, artifacts_root}")
    path, evidence_sha, document = pinned_json(dict(source=evidence["source"], sha256=evidence["sha256"]), "END evidence")
    add(EVIDENCE_NAME, path, evidence_sha)
    artifacts = absolute(evidence["artifacts_root"], "artifacts_root", "dir").resolve()
    require(isinstance(document, dict) and document.get("schema") == EVIDENCE_SCHEMA
            and document.get("kind") == "counted-reporting", "Unsupported K4S END evidence")
    try:
        items = [document[k] for k in ("plan", "completion", "blind_ledger", "counted_inventory")]
        phases = document["phases"]
        require(isinstance(phases, list) and phases, "END evidence has no phases")
        items += [entry[f] for entry in phases for f in ("launch", "supervisor_exit", "mhz", "census")]
        phase_hosts = {entry["host"] for entry in phases}
    except (KeyError, TypeError, AttributeError):
        raise AssemblyError("Malformed END evidence") from None
    seen = {}
    for item in items:
        require(isinstance(item, dict) and {"path", "sha256", "commit", "repository_path"} <= set(item),
                "END evidence item lacks path/sha256/commit/repository_path")
        name = relative(item["path"], "evidence item")
        relative(item["repository_path"], "evidence repository_path")
        require(is_sha(item["sha256"]) and isinstance(item["commit"], str) and COMMIT.fullmatch(item["commit"]),
                "END evidence item needs a SHA-256 and a full commit: " + name)
        if name in seen:
            require(seen[name] == item["sha256"], "Conflicting END evidence pin: " + name)
            continue
        seen[name] = item["sha256"]
        source = (artifacts / name).resolve()
        require(artifacts in source.parents and source.is_file(), "END evidence artifact missing under artifacts_root: " + name)
        no_outcome_path(source, "evidence artifact")
        require(sha_file(source) == item["sha256"], "Pin mismatch: END evidence artifact " + name)
        add(EVIDENCE_DIR + "/" + name, source, item["sha256"])
    plan_item = document["plan"]
    require(plan_item["sha256"] == K4S_PLAN_SHA256, "END evidence plan is not the frozen K4S plan")
    plan_name = EVIDENCE_DIR + "/" + relative(plan_item["path"], "plan")
    raw = copies[plan_name][0].read_bytes()
    require(hashlib.sha256(raw).hexdigest() == K4S_PLAN_SHA256, "Pin mismatch: K4S plan")
    try:
        plan = json.loads(raw)
        compute, study = plan["compute"], plan.get("study")
        hosts, forbidden = compute["hosts"], compute.get("forbidden_hosts", ())
        slot_count = compute["slots"]                       # console_rule false -> compute.slots (fleet_profile.py:17)
        idle_hosts = compute.get("idle_service_exception", {}).get("hosts", [])
    except (KeyError, TypeError, AttributeError, ValueError):     # no require() inside: AssemblyError is a ValueError
        raise AssemblyError("Malformed K4S plan") from None
    require(study == "PREREG-K4S", "Plan is not the K4S reporting plan")
    require(type(slot_count) is int and slot_count >= 2, "Plan compute.slots must be an integer >= 2")
    require(host in hosts and host not in forbidden, "Host absent/forbidden in plan")
    require(host in phase_hosts, "END evidence has no counted phase on this host")

    # 6. guard (fleet_validity.ReportingGuard.__init__ checks, mirrored; the frozen code re-checks on the host)
    guard = request["guard"]
    require(isinstance(guard, dict) and set(guard) == {"job", "freeze", "modules", "admissions", "seed_inputs"},
            "guard must be {job, freeze, modules, admissions, seed_inputs}")
    job = guard["job"]
    require(isinstance(job, str) and os.path.normpath(job) == job and os.path.dirname(job) == JOB_PARENTS[host]
            and JOB_NAME.fullmatch(os.path.basename(job)) is not None,
            "Guard job must be " + JOB_PARENTS[host] + "/k4s-end-guard-r<N>[-rd<RR>-a<NN>] on " + host)
    path, digest, freeze = pinned_json(guard["freeze"], "guard freeze", FROZEN_T1_SHA256)
    add(FREEZE_NAME, path, digest)
    for delta in GUARD_DELTAS:
        require(isinstance(freeze.get(delta), dict) and freeze[delta].get("verdict") == "CONFIRM",
                "Guard freeze lacks a CONFIRM " + delta)
    frozen_files = freeze.get("files")
    require(isinstance(frozen_files, dict), "Guard freeze lacks files")
    modules = guard["modules"]
    require(isinstance(modules, dict) and set(modules) == {m + ".py" for m in GUARD_MODULES},
            "Guard modules must be exactly the nine frozen T1 guard modules")
    for name in sorted(modules):
        expected = frozen_files.get("reports/explore/t1/" + name)
        require(is_sha(expected), "Guard module is not in the freeze: " + name)
        path, digest = pinned_source(modules[name], "guard module " + name, expected)
        add(GUARD_ROOT + "/" + name, path, digest)
    admissions = guard["admissions"]
    require(isinstance(admissions, dict) and "system-bus-admission.json" in admissions and set(admissions) <= set(ADMISSIONS),
            "Admissions: system-bus-admission.json required; only " + repr(ADMISSIONS) + " allowed")
    require("idle-services.json" not in admissions or host in idle_hosts, "Idle-service admission on a host without the exception")
    admission_map = {}
    for name in sorted(admissions):
        path, digest, value = pinned_json(admissions[name], "admission " + name)
        require(isinstance(value, dict) and value.get("host") == host, "Admission is for a different host: " + name)
        if name == "system-bus-admission.json":
            identity = value.get("identity")
            require(isinstance(identity, dict) and set(identity) == set(BUS_KEYS) and identity["uid"] == 103,
                    "System-bus admission identity malformed")
        else:
            services = value.get("services")
            require(isinstance(services, list) and services and all(
                isinstance(s, dict) and {"name", "service", "wrapper_trio"} <= set(s) for s in services),
                "Idle-service admission malformed")
        admission_map[name] = add(ADMISSION_DIR + "/" + name, path, digest)
    seeds = guard["seed_inputs"]
    require(isinstance(seeds, dict), "seed_inputs must be a map")
    required, parsed = {}, {}

    def binding(b, label):
        require(isinstance(b, dict) and is_sha(b.get("sha256")), "Malformed frozen seed binding: " + label)
        name = relative(b.get("path"), "seed path")
        require(frozen_files.get(name) == b["sha256"], "Unpinned/unsafe OP-5 seed dependency: " + name)
        require(required.setdefault(name, b["sha256"]) == b["sha256"], "Conflicting seed binding: " + name)
        require(name in seeds, "Missing pinned OP-5 seed/join input: " + name)
        path, digest, value = pinned_json(seeds[name], "seed " + name, b["sha256"])
        parsed[name] = (path, digest)
        return value
    bindings = freeze.get("parent_source_seeds", [])
    require(isinstance(bindings, list), "Malformed parent_source_seeds")
    for b in bindings:
        receipt = binding(b, "parent source")
        if isinstance(receipt, dict) and receipt.get("host") == "127x08":       # fleet_validity.py:105-106
            join = receipt.get("source_join")
            require(isinstance(join, dict), "08 seed lacks its source_join")
            for side in ("server", "client"):
                binding(join.get(side), "08 join " + side)
    require(set(seeds) == set(required), "OP-5 seed input map differs from frozen seed/join dependencies")
    seed_map = {name: add(SEED_DIR + "/" + name, *parsed[name]) for name in sorted(parsed)}

    # 7. manifest (key order irrelevant: written canonically)
    files = {name: digest for name, (_, digest) in copies.items()}
    profile = dict(PROFILE, host=host, slot_count=slot_count, plan=plan_name, end_evidence=EVIDENCE_NAME,
                   guard=dict(root=GUARD_ROOT, job=job, freeze=FREEZE_NAME, admissions=admission_map, seed_inputs=seed_map))
    manifest = dict(schema=BUNDLE_SCHEMA, final=False, profile="fleet-reference", threshold=THRESHOLD,
                    specification=specification, files=files, runtime_files=runtime, measurement_files=measured,
                    topology=topology, sets=sets, reference_load_profile=profile)
    return copies, manifest


# ---------------------------------------------------------------- writing (only after every check passed)

def manifest_bytes(manifest):
    return (canonical(manifest) + "\n").encode()


def check_out(out, request):
    """A new absolute directory whose parent exists, outside the runtime and evidence trees (inputs stay unchanged)."""
    out = Path(out)
    require(out.is_absolute() and not out.exists() and out.parent.is_dir(), "--out must be a new absolute directory")
    require(not (out.parent / (out.name + ".partial")).exists(), "A previous partial bundle exists: " + str(out))
    for tree in (Path(request["runtime_root"]), Path(request["end_evidence"]["artifacts_root"])):
        require(tree.resolve() not in out.resolve().parents and tree.resolve() != out.resolve(),
                "--out must not be inside an input tree: " + str(tree))
    return out


def write_bundle(copies, manifest, out, request, request_sha):
    out = check_out(out, request)
    stage = out.parent / (out.name + ".partial")
    stage.mkdir(exist_ok=False)
    try:
        for name, (source, digest) in sorted(copies.items()):
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            require(sha_file(target) == digest, "Copy differs from its pin: " + name)
            os.chmod(target, 0o444)
        data = manifest_bytes(manifest)
        digest = hashlib.sha256(data).hexdigest()
        (stage / MANIFEST).write_bytes(data)
        (stage / MANIFEST_SHA).write_text(digest + "  " + MANIFEST + "\n")
        receipt = dict(schema=RECEIPT_SCHEMA, request_sha256=request_sha, manifest_sha256=digest,
                       files=len(manifest["files"]), host=request["host"], guard_job=request["guard"]["job"],
                       assembler_sha256=sha_file(Path(__file__)), final=False, outcomes_read=False,
                       live_actions=False, status="CANDIDATE")
        (stage / RECEIPT).write_text(canonical(receipt) + "\n")
        for name in (MANIFEST, MANIFEST_SHA, RECEIPT):
            os.chmod(stage / name, 0o444)
        require(not out.exists(), "--out appeared during assembly")
        os.rename(stage, out)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return digest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--request", type=Path, required=True)
    ap.add_argument("--request-sha256", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    raw = a.request.read_bytes()
    require(is_sha(a.request_sha256) and hashlib.sha256(raw).hexdigest() == a.request_sha256, "Request SHA mismatch")
    try:
        request = json.loads(raw)
    except ValueError:
        raise AssemblyError("Request is not JSON") from None
    copies, manifest = plan_bundle(request)
    check_out(a.out, request)
    if a.dry_run:
        sys.stdout.buffer.write(manifest_bytes(manifest))
        sys.stdout.flush()
        print(canonical(dict(dry_run=True, manifest_sha256=hashlib.sha256(manifest_bytes(manifest)).hexdigest(),
                             files=len(manifest["files"]), written=False)), file=sys.stderr)
        return 0
    digest = write_bundle(copies, manifest, a.out, request, a.request_sha256)
    print(canonical(dict(dry_run=False, manifest_sha256=digest, files=len(manifest["files"]), out=str(a.out))),
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssemblyError as error:
        print("ASSEMBLY REFUSED: " + str(error), file=sys.stderr)
        raise SystemExit(2)
