#!/usr/bin/env python3
"""S2 (PREREG-K4S END, RC-4b): END evidence builder + offline validator. 127x05 only; no ssh, no host access.

CANDIDATE: requires Sol review before use.

build    Writes the ``clasher.k4s.end-evidence.v1`` document (kind ``counted-reporting``) for the frozen
         ``end_evidence.end_evidence``. Every artifact item is {path, sha256, commit, repository_path}: ``commit``
         is the single --commit that holds every artifact, ``repository_path`` the repo path, ``path`` that path
         relative to the evidence file's directory (default evidence location
         ``reports/explore/k4s-confirm/end-evidence.json``, OUTSIDE the strict ``end/`` namespace). Bytes and
         SHAs come from ``git show <commit>:<repository_path>`` only (never from the work tree). Pinned inputs
         (defaults = the records of run r1): plan 38064dcd, completion-v2 3794d953, counted inventory 22c41cb7,
         blind ledger 649272bd; per phase launch/supervisor_exit from run-r1/phase-meta (exit SHA == the
         completion's supervisor_exits), mhz/census from end-sources/<host>/<phase>/ (the committed S1 copy;
         optionally cross-checked against the S1 copy manifest). Refuses to overwrite.

validate Runs, against a repository checkout whose HEAD contains --commit (and whose work tree holds the
         artifacts next to the evidence), the FROZEN code imported from --code-root (default: that checkout):
         K4S manifest 74314eda verification (k4s_logic.load_k4s_manifest, require_frozen) and
         end_pool.frozen_helpers (e4v3 pins), then end_evidence.end_evidence(); then per counted host the frozen
         fleet_profile.slot_layout(profile, plan, host, plan nice) and fleet_end.host_reporting(evidence,
         profile, plan), plus the reporting-side preconditions of fleet_profile.compare_mhz (every occupied
         physical core present, finite > 0 MHz). Writes one JSON result; exit 0 only if every check passed.

         Offline limits: slot_layout is called with host = the counted host and nice = the plan's nice, so its
         live host/priority gate is NOT exercised here (it runs on host, pre-claim); the profile is the declared
         S4 reference_load_profile (default: slot 0, 11 slots, console_rule false, warmup 300 s, perception
         none) unless --profile-json gives the bundle's.
"""
import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

EVIDENCE_SCHEMA = "clasher.k4s.end-evidence.v1"
RESULT_SCHEMA = "clasher.k4s.end-evidence-validation.v1"
STUDY = "reports/explore/k4s-confirm"
END_DIR = STUDY + "/end"
EVIDENCE_REL = STUDY + "/end-evidence.json"
PLAN = STUDY + "/plan.json"
COMPLETION = STUDY + "/run-r1/completion-v2/REPORTING-COMPLETION.json"
INVENTORY = STUDY + "/run-r1/completion-v2/counted-inventory.json"
LEDGER = STUDY + "/run-r1/ledger/blind-ledger-final.json"
PHASE_META = STUDY + "/run-r1/phase-meta/{host}-{phase}/{name}"
SOURCES = STUDY + "/end-sources/{host}/{phase}/{name}"
K4S_MANIFEST = STUDY + "/mac/K4S-MAC-MANIFEST.json"
DEFAULTS = dict(plan="38064dcdeff96fb006f6e261c246a458f423d97cc53278c3921888241c8d22cf",
                completion="3794d953efb2c8af47a09ccb086cc0441f1c0dd9ea7a4f46e331315972c6e891",
                counted_inventory="22c41cb7624ca04d111b08af9273af074d016efd439a7b0f7f8cccb103aa0f7e",
                blind_ledger="649272bdae066e49a524bd46e0155cdaf99f6d1b543e78014d357e1eb18a4f08",
                k4s_manifest="74314eda04a7100d7ce10141394282b646723d29d0e7bb3883355d1ef1db6357")
DEFAULT_HOSTS = ("127x03", "127x04")
DEFAULT_BLOCKS, DEFAULT_LOSSES = 3900, 99
TOP_FIELDS = frozenset(("schema", "kind", "plan", "completion", "blind_ledger", "counted_inventory", "phases"))
ITEM_FIELDS = frozenset(("path", "sha256", "commit", "repository_path"))
PHASE_FIELDS = frozenset(("host", "phase", "launch", "supervisor_exit", "mhz", "census"))
PHASE_FILES = (("launch", PHASE_META, "launch.json"), ("supervisor_exit", PHASE_META, "supervisor-exit.json"),
               ("mhz", SOURCES, "mhz.jsonl"), ("census", SOURCES, "census.jsonl"))
# end_evidence.JOB_LIKE / FINAL_LIKE / CLAIM_LIKE: the evidence file must never look like an END authority.
AUTHORITY_LIKE = re.compile(r"(END-JOB.*|END-FINAL.*|attempt-.*)\.json", re.IGNORECASE)
SHA = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")


class S2Error(RuntimeError):
    """Fail-closed S2 refusal (never an assert: the checks hold under python -O)."""


def require(condition, message):
    if not condition:
        raise S2Error(message)


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def git(repository, *args):
    result = subprocess.run(["git", "-C", str(repository), *args], capture_output=True)
    require(result.returncode == 0, f"git {' '.join(args[:2])} failed: " + result.stderr.decode(errors="replace")[-300:])
    return result.stdout


def full_commit(repository, commit):
    require(isinstance(commit, str) and COMMIT.fullmatch(commit) is not None, "--commit must be a full 40-hex commit")
    resolved = git(repository, "rev-parse", "--verify", commit + "^{commit}").decode().strip()
    require(resolved == commit, "commit does not resolve to itself: " + commit)
    return commit


def evidence_location(rel):
    p = PurePosixPath(rel)
    require(not p.is_absolute() and ".." not in p.parts and p.as_posix() == rel and rel.endswith(".json"),
            "evidence repository path must be a normalised repo-relative .json path")
    require(rel.startswith(STUDY + "/"), "evidence must lie inside " + STUDY)
    require(not (rel + "/").startswith(END_DIR + "/"), "evidence must lie OUTSIDE the strict END namespace " + END_DIR)
    require(AUTHORITY_LIKE.fullmatch(p.name) is None, "evidence name looks like an END authority/claim: " + p.name)
    return p


def item_for(repository, commit, evidence_dir, rel, expected=None, label=""):
    rel_path = PurePosixPath(rel)
    try:
        path = rel_path.relative_to(evidence_dir)
    except ValueError:
        raise S2Error(f"{label} {rel} does not lie under the evidence directory {evidence_dir}") from None
    require(not (rel + "/").startswith(END_DIR + "/"), f"{label} lies inside the END namespace: {rel}")
    data = git(repository, "show", f"{commit}:{rel}")
    digest = sha_bytes(data)
    require(expected is None or digest == expected, f"{label} SHA {digest} != pinned {expected}: {rel}")
    return dict(path=path.as_posix(), sha256=digest, commit=commit, repository_path=rel), data


# ---------------------------------------------------------------- build

def build(a):
    repository = Path(a.repository)
    commit = full_commit(repository, a.commit)
    location = evidence_location(a.evidence_repository_path)
    out = Path(a.out)
    require(not out.exists() and not out.is_symlink(), "refusing to overwrite " + str(out))
    edir = location.parent
    pins = {k: getattr(a, "expect_" + k) for k in ("plan", "completion", "counted_inventory", "blind_ledger")}
    doc = dict(schema=EVIDENCE_SCHEMA, kind="counted-reporting")
    for key, rel in (("plan", PLAN), ("completion", COMPLETION), ("counted_inventory", INVENTORY), ("blind_ledger", LEDGER)):
        doc[key], data = item_for(repository, commit, edir, rel, pins[key], key)
        if key == "plan":
            require(json.loads(data).get("study") == "PREREG-K4S", "plan is not the PREREG-K4S plan")
        if key == "completion":
            completion = json.loads(data)
    require(completion.get("counted_inventory_sha256") == doc["counted_inventory"]["sha256"]
            and completion.get("blind_ledger_sha256") == doc["blind_ledger"]["sha256"],
            "completion does not bind the pinned inventory/ledger")
    counted = completion.get("counted_host_phases")
    require(isinstance(counted, dict) and counted, "completion lacks counted_host_phases")
    require(sorted(counted) == sorted(a.expect_hosts), f"counted hosts {sorted(counted)} != {sorted(a.expect_hosts)}")
    s1 = s1_meta = None
    if a.s1_manifest:
        copied = json.loads(Path(a.s1_manifest).read_text())
        s1 = {(f["host"], f["phase"], f["name"]): f for f in copied["files"]}
        s1_meta = {(m["host"], m["phase"], m["name"]): m for m in copied["meta"]}
    phases = []
    for host in sorted(counted):
        for phase in counted[host]:
            entry = dict(host=host, phase=phase)
            for field, pattern, name in PHASE_FILES:
                rel = pattern.format(host=host, phase=phase, name=name)
                entry[field], data = item_for(repository, commit, edir, rel, None, f"{host}/{phase} {field}")
                if field == "supervisor_exit":
                    bound = completion.get("supervisor_exits", {}).get(f"{host}/{phase}", {}).get("sha256")
                    require(bound == entry[field]["sha256"], f"supervisor exit SHA not bound by the completion: {rel}")
                if s1_meta is not None and field in ("launch", "supervisor_exit"):
                    row = s1_meta.get((host, phase, name))
                    require(row is not None and row["remote_sha256"] == row["committed_sha256"] == entry[field]["sha256"]
                            and row["committed_repository_path"] == rel,
                            f"phase-meta differs from the on-host file recorded by S1: {rel}")
                if s1 is not None and field in ("mhz", "census"):
                    row = s1.get((host, phase, name))
                    require(row is not None and row["local_sha256"] == row["remote_sha256_before"]
                            == entry[field]["sha256"] and row["local_size"] == len(data),
                            f"committed source differs from the S1 copy manifest: {rel}")
                require(len(data) > 0, "empty artifact: " + rel)
            phases.append(entry)
    doc["phases"] = phases
    data = (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode()
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "xb") as stream:
        stream.write(data)
    summary = dict(status="built", evidence=str(out), evidence_repository_path=location.as_posix(),
                   sha256=sha_bytes(data), commit=commit, phases=len(phases), utc=utc())
    print(json.dumps(summary, indent=1))
    return summary


# ---------------------------------------------------------------- validate

def structure(doc, commit, edir):
    """Stricter than the frozen reader: exact key sets, one commit, path == repository_path relative to the file."""
    require(isinstance(doc, dict) and set(doc) == TOP_FIELDS, "evidence top-level keys differ from the S2 layout")
    require(doc["schema"] == EVIDENCE_SCHEMA and doc["kind"] == "counted-reporting", "wrong evidence schema/kind")
    items = [doc[k] for k in ("plan", "completion", "blind_ledger", "counted_inventory")]
    require(isinstance(doc["phases"], list) and doc["phases"], "evidence lacks phases")
    for entry in doc["phases"]:
        require(isinstance(entry, dict) and set(entry) == PHASE_FIELDS, "phase entry keys differ from the S2 layout")
        items += [entry[f] for f in ("launch", "supervisor_exit", "mhz", "census")]
    for item in items:
        require(isinstance(item, dict) and set(item) == ITEM_FIELDS, "artifact item keys differ")
        require(SHA.fullmatch(str(item["sha256"])) and item["commit"] == commit,
                "artifact item SHA malformed or commit differs from --commit: " + str(item.get("repository_path")))
        require((edir / item["path"]).as_posix() == item["repository_path"]
                and not item["repository_path"].startswith(END_DIR + "/"),
                "artifact path is not its repository path relative to the evidence: " + str(item["path"]))
    return items


def frozen_modules(code_root, manifest_sha256, check_manifest):
    """Import the frozen K4S END modules (and e4v3 helpers) from code_root; refuse any other copy."""
    study = Path(code_root).resolve() / STUDY
    for name in ("end_evidence", "end_pool", "k4s_logic", "fleet_end", "fleet_profile", "fleet_validity", "receipts"):
        require(name not in sys.modules, "frozen module already imported from elsewhere: " + name)
    sys.path[:0] = [str(study / "mac"), str(study)]
    import k4s_logic as L
    import end_evidence as E
    import end_pool as P
    for module, where in ((L, study / "mac"), (E, study), (P, study)):
        require(Path(module.__file__).resolve().parent == where, "wrong frozen module imported: " + module.__name__)
    if check_manifest:
        manifest = L.load_k4s_manifest(Path(code_root) / K4S_MANIFEST, manifest_sha256, Path(code_root),
                                       require_frozen=True)
        fleet_end, fleet_profile, _ = P.frozen_helpers(manifest, Path(code_root))
    else:
        directory = str(Path(code_root).resolve() / L.E4V3_REL)
        sys.path.insert(0, directory)
        import fleet_end
        import fleet_profile
        for module in (fleet_end, fleet_profile):
            require(str(Path(module.__file__).resolve().parent) == directory, "wrong e4v3 helper imported")
    return E, fleet_end, fleet_profile


def default_profile(host, warmup):
    return dict(host=host, reference_slot=0, slot_count=11, console_rule=False, warmup_seconds=warmup,
                perception="none")


def validate(a):
    started = utc()
    repository = Path(a.repository)
    commit = full_commit(repository, a.commit)
    git(repository, "merge-base", "--is-ancestor", commit, "HEAD")
    location = evidence_location(a.evidence_repository_path)
    evidence = Path(a.evidence) if a.evidence else repository / location
    raw = evidence.read_bytes()
    require(SHA.fullmatch(a.evidence_sha256 or "") and sha_bytes(raw) == a.evidence_sha256, "evidence SHA mismatch")
    doc = json.loads(raw)
    structure(doc, commit, location.parent)
    E, fleet_end, fleet_profile = frozen_modules(a.code_root or repository, a.expect_k4s_manifest, not a.no_manifest_check)
    ev = E.end_evidence(evidence, a.evidence_sha256, repository, fleet_end)
    require(ev["completion_sha256"] == a.expect_completion and ev["plan_sha256"] == a.expect_plan,
            "evidence binds a completion/plan other than the record")
    require(doc["counted_inventory"]["sha256"] == a.expect_counted_inventory
            and doc["blind_ledger"]["sha256"] == a.expect_blind_ledger, "evidence binds another inventory/ledger")
    require(ev["counted_hosts"] == sorted(a.expect_hosts), f"counted hosts {ev['counted_hosts']} != {a.expect_hosts}")
    membership = ev["membership"]
    require(membership["blocks"] == a.expect_blocks and membership["losses"] == a.expect_losses,
            f"membership {membership['blocks']}/{membership['losses']} != expected {a.expect_blocks}/{a.expect_losses}")
    wanted = {(h, p) for h, ps in ev["completion"]["counted_host_phases"].items() for p in ps}
    require(set(ev["phases"]) == wanted, "evidence phases differ from the completion's counted host phases")
    for key, values in ev["phases"].items():
        bound = ev["completion"]["supervisor_exits"].get(f"{key[0]}/{key[1]}", {}).get("sha256")
        require(bound == values["exit_sha256"], f"supervisor exit not bound by the completion: {key}")
    profiles = json.loads(Path(a.profile_json).read_text()) if a.profile_json else {}
    plan = ev["plan"]
    hosts = {}
    for host in ev["counted_hosts"]:
        profile = profiles.get(host, default_profile(host, a.warmup_seconds))
        search, background, census_cpu = fleet_profile.slot_layout(profile, plan, host, plan["compute"]["nice"])
        rows = fleet_end.host_reporting(ev, profile, plan)
        cpus = search + sum(background, [])
        for row in rows:                                   # reporting half of frozen fleet_profile.compare_mhz
            require(row["slots"] == profile["slot_count"] and row.get("inflight") == profile["slot_count"],
                    "non full-occupancy reporting row selected")
            clocks = {v["cpu"]: v["mhz"] for v in row["physical_core_mhz"]}
            require(set(cpus) <= set(clocks), f"reporting MHz row lacks an occupied physical core: {host} {row['utc']}")
            require(all(isinstance(clocks[c], (int, float)) and math.isfinite(clocks[c]) and clocks[c] > 0 for c in cpus),
                    f"non-finite/non-positive reporting MHz: {host} {row['utc']}")
        per_phase = {}
        for row in rows:
            per_phase[row["phase"]] = per_phase.get(row["phase"], 0) + 1
        hosts[host] = dict(profile=profile, reference_cpus=search, background_slots=len(background),
                           census_cpu=census_cpu, full_occupancy_rows=len(rows), full_occupancy_rows_by_phase=per_phase,
                           census_rows_by_phase={p: len(v["census"]) for (h, p), v in ev["phases"].items() if h == host})
    if a.s1_manifest:
        s1 = {(f["host"], f["phase"], f["name"]): f for f in json.loads(Path(a.s1_manifest).read_text())["files"]}
        for entry in doc["phases"]:
            for field, name in (("mhz", "mhz.jsonl"), ("census", "census.jsonl")):
                row = s1.get((entry["host"], entry["phase"], name))
                require(row is not None and row["local_sha256"] == entry[field]["sha256"],
                        f"evidence source differs from the S1 copy manifest: {entry['host']}/{entry['phase']}/{name}")
    return dict(schema=RESULT_SCHEMA, ok=True, started_utc=started, finished_utc=utc(), evidence=str(evidence),
                evidence_sha256=a.evidence_sha256, commit=commit,
                repository_head=git(repository, "rev-parse", "HEAD").decode().strip(),
                code_root=str(a.code_root or repository), frozen_manifest_verified=not a.no_manifest_check,
                end_evidence_py_sha256=sha_bytes(Path(E.__file__).read_bytes()),
                fleet_end_py_sha256=sha_bytes(Path(fleet_end.__file__).read_bytes()),
                fleet_profile_py_sha256=sha_bytes(Path(fleet_profile.__file__).read_bytes()),
                python=sys.version.split()[0], optimize=sys.flags.optimize,
                kind=ev["kind"], counted_hosts=ev["counted_hosts"], membership=membership,
                plan_sha256=ev["plan_sha256"], completion_sha256=ev["completion_sha256"], hosts=hosts,
                slot_layout_offline_note="host/nice supplied offline (plan nice); live gate runs on host pre-claim",
                s1_manifest_checked=bool(a.s1_manifest))


def add_pins(ap):
    for key in ("plan", "completion", "counted_inventory", "blind_ledger"):
        ap.add_argument("--expect-" + key.replace("_", "-"), dest="expect_" + key, default=DEFAULTS[key])
    ap.add_argument("--expect-hosts", nargs="+", default=list(DEFAULT_HOSTS))
    ap.add_argument("--evidence-repository-path", default=EVIDENCE_REL)
    ap.add_argument("--s1-manifest", help="S1 s1-copy-manifest.json for a source SHA cross-check")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--repository", required=True)
    b.add_argument("--commit", required=True, help="the one commit containing every artifact")
    b.add_argument("--out", required=True, help="evidence file to write (refuses to overwrite)")
    add_pins(b)
    v = sub.add_parser("validate")
    v.add_argument("--repository", required=True, help="checkout whose HEAD contains --commit (work tree = HEAD)")
    v.add_argument("--commit", required=True)
    v.add_argument("--evidence", help="evidence file (default: <repository>/<evidence-repository-path>)")
    v.add_argument("--evidence-sha256", required=True)
    v.add_argument("--code-root", help="checkout holding the frozen code (default: --repository)")
    v.add_argument("--expect-k4s-manifest", default=DEFAULTS["k4s_manifest"])
    v.add_argument("--no-manifest-check", action="store_true", help="TESTS ONLY: skip the K4S manifest pin check")
    v.add_argument("--expect-blocks", type=int, default=DEFAULT_BLOCKS)
    v.add_argument("--expect-losses", type=int, default=DEFAULT_LOSSES)
    v.add_argument("--warmup-seconds", type=float, default=300.0)
    v.add_argument("--profile-json", help="{host: reference_load_profile} from the S4 bundles")
    v.add_argument("--result", required=True, help="result JSON to write (refuses to overwrite)")
    add_pins(v)
    a = ap.parse_args(argv)
    if a.command == "build":
        try:
            build(a)
        except Exception as error:                        # fail closed
            print(f"S2 BUILD REFUSED: {type(error).__name__}: {error}", file=sys.stderr)
            return 2
        return 0
    result_path = Path(a.result)
    if result_path.exists() or result_path.is_symlink():
        print("S2 VALIDATE REFUSED: result exists: " + str(result_path), file=sys.stderr)
        return 2
    try:
        result = validate(a)
        code = 0
    except Exception as error:                            # fail closed: frozen EvidenceError/ValueError included
        result = dict(schema=RESULT_SCHEMA, ok=False, error_type=type(error).__name__, error=str(error), utc=utc())
        code = 2
    data = json.dumps(result, indent=1, sort_keys=True) + "\n"
    with open(result_path, "x") as stream:
        stream.write(data)
    print(data, end="")
    return code


if __name__ == "__main__":
    sys.exit(main())
