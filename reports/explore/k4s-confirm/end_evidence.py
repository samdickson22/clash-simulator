"""PREREG-K4S END evidence (r3 §4.5; delta 8): committed health-only inputs, sealed receipts, attempt registry.

Never reads game or outcome bytes. K4S-owned; the frozen TIERS e4v3 helpers are used read only
(``fleet_end.artifact``/``utc``/``relative`` for committed bytes). Three parts:

1. ``end_evidence``: ``clasher.k4s.end-evidence.v1`` (3000 primary / 900 guard counted blocks). Every artifact is
   byte-equal to its committed blob in an ancestor of HEAD. Phase names, launch phase identity and supervisor
   exits are checked as in frozen ``fleet_end.evidence``; ``counting`` is a port of frozen ``fleet_end.counting``
   (verbatim completed-exit membership, ledger loss/replacement bindings to the exit SHA, counted lost blocks
   rejected, health-only allow-lists). The only change: the descriptor allow-list adds the registered K4S
   descriptor fields ``rotation``, ``subsample`` and ``replacement_k`` (K4S-SPEC §3; schedule.py).
2. ``SealedReceipt``: an END receipt directory read only through its verified seal. The directory must hold
   exactly the sealed inventory (plus the seal and its sidecar), so frozen helpers that open files directly
   (``fleet_validity.classify_attempt``) only ever see verified bytes. Every consumed file is recorded.
3. The END job authority (r3 §4.5; PC1 "all original attempt roots"). PREREG-K4S has exactly one reporting
   completion, so there is exactly one END job, at FIXED repository paths (module constants; never derived from the
   evidence, the completion's repository path or a pool descriptor):
   - ``END_JOB_PATH`` (``clasher.k4s.end-job.v1``): added in exactly one commit before the first attempt and never
     modified, deleted or re-added; binds the completion, END evidence, plan, counted hosts and frozen K4S manifest.
     Any other END-JOB-like (or END-FINAL-like) path name anywhere under ``STUDY_DIR`` is refused, so a copied
     completion with repackaged evidence can never gain a second authority.
   - ``end_reference.py`` requires it, then claims ``REGISTRY_ROOT/round-RR/<host>/attempt-NN.json``
     (``clasher.k4s.end-attempt-claim.v2``, bound to the job and evidence; exclusive creation, before the receipt
     directory exists) only while round RR is open.
   - ``END_DIR/END-FINAL-round-RR.json`` (``clasher.k4s.end-finalization.v1``), committed after the last attempt of
     the round, lists every claim of every round so far and every earlier (nonconforming) pool round, whose sealed
     pool is committed at ``POOLS_ROOT/round-RR`` and whose original attempt receipt directories are committed at
     ``RECEIPTS_ROOT/round-RR/<host>/<receipt directory>/``. Every round's finalization is checked by the same
     ``finalization`` (latest and earlier alike). An earlier round is never trusted from its seal status: the pool
     (end_pool.validate_prior_round) and the producer of a later round (``producer_registry`` ->
     end_pool.predecessors) copy its committed pool and receipts (``committed_round``) and re-validate and recompute
     it with the pool's own code path; it must be a ratio-only nonconforming pool equal to the committed one.
   - Health-only read boundary: the authority enumerates committed path NAMES only (``git ls-tree --name-only``,
     tree metadata) and opens blobs only inside the registered END namespace ``END_DIR``, whose layout is strict:
     claims exist only under ``REGISTRY_ROOT``; any other attempt-claim-named file is refused; a committed receipt
     copy (``RECEIPTS_ROOT/round-RR/<host>/<receipt directory>/attempt-claim.json``) must be the registry's claim.
     Every admissible JSON document is parsed from its complete bytes (any serialization; malformed is refused).
"""
import json
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE / "mac"), str(HERE)]      # explicit: `python -I` omits the script directory
import k4s_logic as L  # noqa: E402

EVIDENCE_SCHEMA = "clasher.k4s.end-evidence.v1"
REGISTRY_SCHEMA = "clasher.k4s.end-attempt-claim.v2"
COUNTED_BLOCKS = dict(primary=3000, guard=900)        # K4S completion (barrier.py / verifier)
# Frozen fleet_end.counting allow-list + the registered K4S descriptor fields (and nothing else).
FROZEN_DESCRIPTOR_FIELDS = frozenset(("id", "population", "index", "seed", "cell", "seat", "own_index",
                                      "opponent_index", "order", "replaces", "dispatch", "host"))
K4S_DESCRIPTOR_FIELDS = frozenset(("rotation", "subsample", "replacement_k"))
DESCRIPTOR_FIELDS = FROZEN_DESCRIPTOR_FIELDS | K4S_DESCRIPTOR_FIELDS
INVENTORY_FIELDS = frozenset(("schema", "outcomes_sealed", "blocks"))
LEDGER_FIELDS = frozenset(("utc", "sealed", "events"))
EVENT_FIELDS = frozenset(("utc", "lost", "replacement", "reason", "evidence_sha256"))
PHASE = re.compile(r"replacement-r[1-9][0-9]*")


class EvidenceError(ValueError):
    """Explicit fail-closed END evidence error (never an assert)."""


def require(condition, message):
    if not condition:
        raise EvidenceError(message)


def registered_phase(name):
    return name == "reporting" or PHASE.fullmatch(name) is not None


# ---------------------------------------------------------------- 1. committed END evidence

def counting(ledger, inventory, completion, phases):
    """Port of frozen fleet_end.counting (health-only membership, blind losses, logical coverage)."""
    require(ledger.get("sealed") is True and inventory.get("outcomes_sealed") is True,
            "END requires the sealed blind ledger and counted inventory")
    require(inventory.get("schema") == "clasher.t1.counted-blocks.v1", "Unsupported counted-block inventory")
    require(set(inventory) == INVENTORY_FIELDS and set(ledger) <= LEDGER_FIELDS,
            "Unknown/non-health counted inventory or ledger fields")

    def descriptor(d):
        require(isinstance(d, dict) and {"id", "population", "host"} <= set(d) and set(d) <= DESCRIPTOR_FIELDS,
                "END block descriptor contains unknown/non-health fields")
    completed, unsuccessful = {}, {}
    for key, values in phases.items():
        exit_ = values["supervisor_exit"]
        seen = set()
        for group in ("completed", "failed", "unstarted"):
            require(isinstance(exit_.get(group), list), "Raw supervisor exit lacks its " + group + " list")
            for d in exit_[group]:
                descriptor(d)
                require(d["id"] not in seen and d["host"] == key[0], "Raw exit has duplicate/wrong-host block")
                seen.add(d["id"])
                target = completed if group == "completed" else unsuccessful
                target.setdefault(d["id"], []).append((key, d, group))
    events = ledger.get("events")
    require(isinstance(events, list), "Blind ledger lacks its events")
    losses, replacements = {}, {}
    for event in events:
        require(isinstance(event, dict) and {"lost", "replacement", "evidence_sha256"} <= set(event)
                and set(event) <= EVENT_FIELDS, "Unknown/non-health blind ledger event fields")
        lost = event["lost"]
        descriptor(lost)
        identity = lost["id"]
        require(identity not in losses, "Duplicate blind ledger loss")
        candidates = completed.get(identity, []) + unsuccessful.get(identity, [])
        require(any(d == lost and group != "unstarted" and phases[key]["exit_sha256"] == event["evidence_sha256"]
                    for key, d, group in candidates), "Blind ledger loss lacks verbatim raw exit binding")
        losses[identity] = lost
        replacement = event["replacement"]
        if replacement is not None:
            # Bank descriptors need not have their eventual host/dispatch yet.
            require(isinstance(replacement, dict) and set(replacement) <= DESCRIPTOR_FIELDS and "id" in replacement,
                    "Replacement has unknown/non-health fields")
            rid = replacement["id"]
            require(rid not in replacements and replacement.get("population") == lost["population"]
                    and replacement.get("cell") == lost.get("cell"), "Invalid blind ledger replacement")
            require(replacement.get("replaces") == (lost.get("replaces") or identity), "Replacement changes logical block")
            replacements[rid] = replacement
    for identity, attempts in unsuccessful.items():
        require(not any(group == "failed" for _, _, group in attempts) or identity in losses,
                "Failed block is absent from blind ledger")
    counted, logical, owners = set(), {p: set() for p in COUNTED_BLOCKS}, set()
    blocks = inventory["blocks"]
    require(isinstance(blocks, list), "Counted inventory lacks its blocks")
    for row in blocks:
        require(isinstance(row, dict) and set(row) == {"host", "phase", "descriptor"},
                "Counted inventory must contain health-only membership rows")
        key, d = (row["host"], row["phase"]), row["descriptor"]
        descriptor(d)
        identity = d["id"]
        require(identity not in counted and identity not in losses, "Duplicate/lost block counted at END")
        require(any(owner == key and raw == d for owner, raw, _ in completed.get(identity, [])),
                "Counted block lacks exact completed raw exit membership")
        if d.get("replaces"):
            def transport_free(value):
                return {k: v for k, v in value.items() if k not in ("host", "dispatch")}
            require(identity in replacements and transport_free(d) == transport_free(replacements[identity]),
                    "Counted replacement lacks blind ledger binding")
        population, lid = d["population"], d.get("replaces") or identity
        require(population in logical and re.fullmatch(population + r"-[0-9]+", lid) and lid not in logical[population],
                "Invalid/duplicate counted logical block")
        logical[population].add(lid)
        counted.add(identity)
        owners.add(key)
    for population, count in COUNTED_BLOCKS.items():
        require(logical[population] == {f"{population}-{i:04d}" for i in range(count)},
                "Counted inventory lacks the complete logical " + population + " population")
    wanted = {(h, p) for h, values in completion["counted_host_phases"].items() for p in values}
    require(owners == wanted, "Counted host/phase inventory differs from the completion receipt")
    return dict(blocks=len(counted), losses=len(losses), host_phases=sorted(owners))


def evidence_items(obj):
    """Every committed artifact item of one evidence document (top-level and per phase)."""
    items = [obj[k] for k in ("plan", "completion", "blind_ledger", "counted_inventory")]
    items += [entry[f] for entry in obj["phases"] for f in ("launch", "supervisor_exit", "mhz", "census")]
    return items


def end_evidence(path, expected_sha256, repository, fleet_end):
    """clasher.k4s.end-evidence.v1 by path + SHA; artifacts relative to the file, committed (blob + ancestry)."""
    path = Path(path)
    require(L.is_sha256(expected_sha256) and path.is_file(), "END evidence SHA mismatch")
    raw = path.read_bytes()
    require(L.sha_bytes(raw) == expected_sha256, "END evidence SHA mismatch")
    obj = json.loads(raw)
    require(isinstance(obj, dict) and obj.get("schema") == EVIDENCE_SCHEMA and obj.get("kind") == "counted-reporting",
            "Unsupported K4S END evidence")
    inventory = dict(files={})
    for item in evidence_items(obj):
        name = str(fleet_end.relative(item["path"]))
        require(inventory["files"].setdefault(name, item["sha256"]) == item["sha256"], "Conflicting END evidence pin: " + name)

    def artifact(item):
        return fleet_end.artifact(path.parent, inventory, repository, item, True)
    plan = json.loads(artifact(obj["plan"]))
    require(plan.get("study") == "PREREG-K4S", "END plan is not the K4S reporting plan")
    completion = json.loads(artifact(obj["completion"]))
    require(completion.get("reporting_complete") is True and completion.get("outcomes_sealed") is True,
            "END requires committed reporting completion with sealed outcomes")
    for population, count in COUNTED_BLOCKS.items():
        require(completion.get("counted_" + population + "_blocks") == count,
                "Completion lacks the full counted " + population + " population")
    expected = completion.get("counted_host_phases")
    compute = plan["compute"]
    allowed = set(compute["hosts"]) - set(compute.get("forbidden_hosts", []))
    require(isinstance(expected, dict) and expected and set(expected) <= allowed,
            "Counted host set differs from the pinned K4S plan")
    wanted = set()
    for host, names in expected.items():
        require(isinstance(names, list) and names and len(set(names)) == len(names),
                "Every counted host requires unique counted phases")
        for name in names:
            require(registered_phase(name), "Unregistered counted phase")
            wanted.add((host, name))
    phases = {}
    for entry in obj["phases"]:
        key = (entry["host"], entry["phase"])
        require(key[0] in allowed and key not in phases and registered_phase(key[1]), "Duplicate/unknown END host phase")
        values = {}
        for field in ("launch", "supervisor_exit", "mhz", "census"):
            data = artifact(entry[field])
            values[field] = [json.loads(s) for s in data.splitlines() if s.strip()] if field in ("mhz", "census") \
                else json.loads(data)
        launch, exit_ = values["launch"], values["supervisor_exit"]
        launch_phase = "replacement" if key[1].startswith("replacement-") else "reporting"
        require(launch.get("host") == key[0] and launch.get("phase") == launch_phase and exit_.get("host") == key[0],
                "END phase host/launch mismatch")
        require(fleet_end.utc(exit_["utc"]) <= fleet_end.utc(completion["completed_at_utc"]),
                "Completion precedes a supervisor exit")
        values["exit_sha256"] = entry["supervisor_exit"]["sha256"]
        phases[key] = values
    require(wanted <= set(phases), "Missing counted reporting/replacement phase evidence")
    counts = {}
    for field in ("blind_ledger", "counted_inventory"):
        require(completion.get(field + "_sha256") == obj[field]["sha256"], "Completion does not bind END " + field)
        counts[field] = json.loads(artifact(obj[field]))
    membership = counting(counts["blind_ledger"], counts["counted_inventory"], completion, phases)
    return dict(kind=obj["kind"], inventory=obj, completion=completion, phases=phases, plan=plan,
                plan_sha256=obj["plan"]["sha256"], completion_sha256=obj["completion"]["sha256"],
                counted_hosts=sorted(expected), membership=membership, sha256=expected_sha256,
                files={str(path.parent / name): digest for name, digest in inventory["files"].items()})


# ---------------------------------------------------------------- 2. sealed END receipts

SEAL_FILES = ("receipt-manifest.json", "receipt-manifest.sha256")


class SealedReceipt:
    """One receipt directory by path + receipt-manifest SHA, read only through its verified seal."""

    def __init__(self, directory, manifest_sha256, *, scope, label, consumed=None):
        self.directory, self.label = Path(directory), label
        self.consumed = {} if consumed is None else consumed
        seal = self._read("receipt-manifest.json")
        require(L.is_sha256(manifest_sha256) and L.sha_bytes(seal) == manifest_sha256, label + " receipt SHA mismatch")
        sidecar = self._read("receipt-manifest.sha256")
        require(sidecar == (manifest_sha256 + "  receipt-manifest.json\n").encode(), label + " seal sidecar mismatch")
        self.manifest = document(seal, label + " seal")
        self.sha256 = manifest_sha256
        require(self.manifest.get("scope") == scope, label + " has an unexpected scope")
        files = self.manifest.get("files")
        require(isinstance(files, dict) and files and all(L.is_sha256(v) for v in files.values()),
                label + " has an empty/malformed seal")
        self.files, self.status = files, self.manifest.get("status")
        on_disk = {p.relative_to(self.directory).as_posix() for p in self.directory.rglob("*") if p.is_file()}
        require(on_disk == set(files) | set(SEAL_FILES),
                label + " directory differs from its sealed inventory (unsealed or missing files)")
        for name in sorted(files):
            self.bytes(name)

    def _read(self, name):
        path = self.directory / name
        require(path.is_file() and not path.is_symlink(), self.label + " lacks " + name)
        data = path.read_bytes()
        self.consumed[str(path.resolve())] = L.sha_bytes(data)
        return data

    def bytes(self, name):
        require(name in self.files, self.label + " seal does not include " + name)
        data = self._read(name)
        require(L.sha_bytes(data) == self.files[name], self.label + " pin mismatch: " + name)
        return data

    def json(self, name):
        return document(self.bytes(name), self.label + " " + name)

    def lines(self, name):
        return [json.loads(s) for s in self.bytes(name).decode().splitlines() if s.strip()]

    def has(self, name):
        return name in self.files


# ---------------------------------------------------------------- 3. END job authority, attempt registry, finalization

JOB_SCHEMA = "clasher.k4s.end-job.v1"
FINAL_SCHEMA = "clasher.k4s.end-finalization.v1"
REFERENCE_SCOPE = "K4S-END-REFERENCE"
# The fixed, registered health-only END namespace (repository-relative; one END job for the study).
STUDY_DIR = "reports/explore/k4s-confirm"
END_DIR = STUDY_DIR + "/end"
END_JOB_PATH = END_DIR + "/END-JOB.json"
REGISTRY_ROOT = END_DIR + "/registry"
POOLS_ROOT = END_DIR + "/pools"
RECEIPTS_ROOT = END_DIR + "/receipts"
FINAL = re.compile(r"END-FINAL-round-([0-9]{2})\.json")
FINAL_AT = re.compile(re.escape(END_DIR) + r"/END-FINAL-round-[0-9]{2}\.json")
ROUND = re.compile(r"round-([0-9]{2})")
ATTEMPT = re.compile(r"attempt-([0-9]{2})\.json")
JOB_LIKE = re.compile(r"END-JOB.*\.json", re.IGNORECASE)
FINAL_LIKE = re.compile(r"END-FINAL.*\.json", re.IGNORECASE)
CLAIM_LIKE = re.compile(r"attempt-.*\.json", re.IGNORECASE)
RECEIPT_COPY = "attempt-claim.json"
# Health-only allow-lists (exact key sets): no outcome or game field can enter these documents.
JOB_FIELDS = frozenset(("schema", "study", "end_evidence_sha256", "completion_sha256", "plan_sha256",
                        "k4s_manifest_sha256", "counted_hosts", "declared_utc", "declared_by"))
CLAIM_FIELDS = frozenset(("schema", "job_sha256", "end_evidence_sha256", "round", "host", "attempt",
                          "receipt_directory", "launched_utc", "pid", "nonce"))
RECEIPT_COPY_FIELDS = frozenset(("scope", "claim", "claim_sha256"))
FINAL_FIELDS = frozenset(("schema", "job_sha256", "round", "claims", "prior_rounds", "finalized_utc", "finalized_by"))
PRIOR_FIELDS = frozenset(("round", "pool_repository_path", "pool_manifest_sha256"))


def _git(repository, *args, check=True):
    result = subprocess.run(["git", "-C", str(repository), *args], capture_output=True)
    require(result.returncode == 0 or not check, "git " + args[0] + " failed: " + result.stderr.decode()[-200:])
    return result


def document(data, label):
    """One admissible JSON document parsed from its COMPLETE bytes (compact, indented, any whitespace)."""
    try:
        value = json.loads(data)
    except ValueError:                                      # includes JSONDecodeError and UnicodeDecodeError
        raise EvidenceError(label + " is not one well-formed JSON document") from None
    require(isinstance(value, dict), label + " is not a JSON object")
    return value


def repo_relative(name, label):
    rel = Path(name or "")
    require(isinstance(name, str) and rel.parts and not rel.is_absolute() and ".." not in rel.parts
            and rel.as_posix() == name, label + " must be a normalised repo-relative path")
    return rel.as_posix()


def tree_names(repository, directory, rev="HEAD"):
    """Committed path NAMES under ``directory`` at ``rev``: tree metadata only, no blob is opened."""
    listing = _git(repository, "ls-tree", "-r", "-z", "--name-only", rev, "--", directory + "/").stdout.decode()
    return [n for n in listing.split("\0") if n]


def namespace_blob(repository, rel, label, rev="HEAD"):
    """The only blob reader of the authority: refuses any path outside the registered END namespace."""
    require(rel.startswith(END_DIR + "/"), label + " lies outside the health-only END namespace: " + rel)
    result = _git(repository, "show", rev + ":" + rel, check=False)
    require(result.returncode == 0, label + " is not committed at " + rev + ": " + rel)
    return result.stdout


def head_blob(repository, rel, label):
    return namespace_blob(repository, rel, label)


def immutable(repository, rel, label):
    """The path was added in exactly one commit reachable from HEAD and never modified, deleted or re-added.
    Returns that commit."""
    touched = _git(repository, "log", "--format=%H", "--full-history", "--no-renames", "HEAD",
                   "--", rel).stdout.decode().split()
    require(len(touched) == 1, label + " is not append-only (rewritten, deleted or re-added): " + rel)
    added = _git(repository, "log", "--format=%H", "--full-history", "--no-renames", "--diff-filter=A", "HEAD",
                 "--", rel).stdout.decode().split()
    require(added == touched, label + " was not added by its only commit: " + rel)
    return touched[0]


def ancestor(repository, older, newer):
    return _git(repository, "merge-base", "--is-ancestor", older, newer, check=False).returncode == 0


def job_path():
    """The single END-JOB location (fixed; never derived from the completion/evidence location)."""
    return END_JOB_PATH


def final_path(round_):
    return f"{END_DIR}/END-FINAL-round-{round_:02d}.json"


def pool_path(round_):
    return f"{POOLS_ROOT}/round-{round_:02d}"


def declarations(repository):
    """Exactly one END job: no END-JOB-like or END-FINAL-like path name under the study directory except the fixed
    ones (names only)."""
    for rel in tree_names(repository, STUDY_DIR):
        base = rel.rsplit("/", 1)[-1]
        require(not JOB_LIKE.fullmatch(base) or rel == END_JOB_PATH,
                "END-JOB-like declaration outside the fixed END-JOB location (one END job per study): " + rel)
        require(not FINAL_LIKE.fullmatch(base) or FINAL_AT.fullmatch(rel),
                "END finalization-like record outside the fixed END namespace: " + rel)


def namespace(repository):
    """Strict layout of the committed END namespace, by path NAME only. Claims exist only under REGISTRY_ROOT
    (layout checked by registry_at); any other attempt-claim-named file is refused, except a receipt copy at its
    registered place. Returns the receipt copies [(path, round, host, receipt directory)]."""
    copies = []
    for rel in tree_names(repository, END_DIR):
        if rel == END_JOB_PATH or FINAL_AT.fullmatch(rel) or rel.startswith(REGISTRY_ROOT + "/"):
            continue
        parts, base = rel[len(END_DIR) + 1:].split("/"), rel.rsplit("/", 1)[-1]
        receipt = parts[0] == "receipts" and len(parts) == 5 and ROUND.fullmatch(parts[1]) is not None
        require(not CLAIM_LIKE.fullmatch(base) or (receipt and base == RECEIPT_COPY),
                "END attempt claim outside the registry root (claims exist only under " + REGISTRY_ROOT + "): " + rel)
        require(receipt or (parts[0] == "pools" and len(parts) == 3 and ROUND.fullmatch(parts[1]) is not None),
                "Unregistered path in the END namespace: " + rel)
        if receipt and base == RECEIPT_COPY:
            copies.append((rel, int(parts[1][6:]), parts[2], parts[3]))
    return copies


def end_job(repository, evidence, job_sha256, k4s_manifest_sha256):
    """The committed, append-only END job declaration at the fixed END_JOB_PATH, bound to this completion and END
    evidence. Required by the producer before any claim and by the pool."""
    rel = job_path()
    data = head_blob(repository, rel, "END-JOB declaration")
    require(L.is_sha256(job_sha256) and L.sha_bytes(data) == job_sha256, "END-JOB SHA mismatch: " + rel)
    commit = immutable(repository, rel, "END-JOB declaration")
    job = document(data, "END-JOB declaration")
    require(set(job) == JOB_FIELDS and job["schema"] == JOB_SCHEMA and job["study"] == "PREREG-K4S",
            "Malformed END-JOB declaration (health-only exact fields)")
    require(job["end_evidence_sha256"] == evidence["sha256"] and job["completion_sha256"] == evidence["completion_sha256"]
            and job["plan_sha256"] == evidence["plan_sha256"] and job["counted_hosts"] == evidence["counted_hosts"],
            "END-JOB is not bound to this committed completion/END evidence")
    require(job["k4s_manifest_sha256"] == k4s_manifest_sha256, "END-JOB names a different frozen K4S manifest")
    require(isinstance(job["declared_by"], str) and job["declared_by"]
            and isinstance(job["declared_utc"], str) and job["declared_utc"], "END-JOB lacks its declaration stamp")
    declarations(repository)
    return dict(job, sha256=job_sha256, repository_path=rel, registry_root=REGISTRY_ROOT, commit=commit)


def finals_at_head(repository):
    """Committed finalization rounds at their fixed location at HEAD (names only)."""
    names = [n.rsplit("/", 1)[-1] for n in tree_names(repository, END_DIR) if FINAL_AT.fullmatch(n)]
    return sorted(int(m.group(1)) for m in map(FINAL.fullmatch, names) if m)


def registry_at(repository, rev, root=REGISTRY_ROOT):
    """{round: {host: [attempt names]}} at ``rev``; strict layout <root>/round-RR/<host>/attempt-NN.json."""
    out = {}
    for line in tree_names(repository, root, rev):
        parts = Path(line[len(root) + 1:]).parts
        require(line.startswith(root + "/") and len(parts) == 3 and ROUND.fullmatch(parts[0])
                and ATTEMPT.fullmatch(parts[2]), "Unexpected END attempt registry entry: " + line)
        out.setdefault(int(parts[0][6:]), {}).setdefault(parts[1], []).append(parts[2])
    require(sorted(out) == list(range(len(out))), "END attempt registry rounds are not contiguous from round-00")
    for round_, hosts in out.items():
        for host, names in hosts.items():
            require(sorted(names) == [f"attempt-{i:02d}.json" for i in range(len(names))],
                    f"END attempt registry is not contiguous: round-{round_:02d}/{host}")
    return out


def registry_append_only(repository, root=REGISTRY_ROOT):
    """No claim under the registry root was ever deleted, modified or type-changed in the history of HEAD."""
    changed = _git(repository, "log", "--format=", "--name-only", "--no-renames", "--diff-filter=DMT", "HEAD",
                   "--", root + "/").stdout.decode().split()
    require(not changed, "END attempt registry is not append-only (claim deleted/modified): " + ",".join(changed[:3]))


def claim_path(round_, host, name):
    return f"{REGISTRY_ROOT}/round-{round_:02d}/{host}/{name}"


def producer_registry(repository, job, round_, host, context=None):
    """Producer-side authority check before a claim: the END namespace is well-formed; this host is counted; the
    round is open (no committed finalization for it or a later round); a later round needs the committed
    finalizations of every earlier round AND every earlier round re-validated as a ratio-only nonconforming pool by the
    pool's own code path (end_pool.predecessors; ``context`` = end_pool.pool_context of the frozen shared inputs).
    Returns (claim directory under REGISTRY_ROOT, committed claim names for this host/round)."""
    require(host in job["counted_hosts"], "This host has no counted blocks in the END job: " + host)
    require(type(round_) is int and 0 <= round_ <= 99, "END round must be an integer 0-99")
    namespace(repository)
    finals = finals_at_head(repository)
    require(not any(r >= round_ for r in finals), f"END round {round_:02d} is already finalized; no further attempts")
    require(round_ == 0 or round_ - 1 in finals, f"END round {round_:02d} requires the committed finalization of "
                                                 f"round {round_ - 1:02d} (r3 §4.5 re-run)")
    require(finals == list(range(round_)), "END finalizations at HEAD must be exactly the earlier rounds")
    committed = registry_at(repository, "HEAD")
    require(round_ == len(committed) or round_ == len(committed) - 1, "END round skips a registry round")
    if round_:
        require(context is not None, f"END round {round_:02d} requires the validated nonconforming pool of every "
                                     f"earlier round (r3 §4.5 re-run): no pool context given")
        import end_pool                                     # lazy: end_pool imports this module
        end_pool.predecessors(repository, job, round_, context)
    names = committed.get(round_, {}).get(host, [])
    return Path(repository) / REGISTRY_ROOT / f"round-{round_:02d}" / host, names


def claim_attempt(directory, out, *, job, round_, host, committed=(), now=None):
    """Exclusive claim REGISTRY_ROOT/round-RR/<host>/attempt-NN.json before the receipt directory exists.

    The claim binds the END job and END evidence. NN counts every earlier claim on this host and round, and the
    committed claims must be a prefix of the local ones (a committed claim can never be dropped locally)."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    names = sorted(p.name for p in directory.iterdir())
    require(all(ATTEMPT.fullmatch(n) for n in names) and names == [f"attempt-{i:02d}.json" for i in range(len(names))],
            "END attempt registry is not a contiguous claim sequence: " + host)
    require(list(committed) == names[:len(committed)], "Local END attempt registry lost a committed claim: " + host)
    claim = dict(schema=REGISTRY_SCHEMA, job_sha256=job["sha256"], end_evidence_sha256=job["end_evidence_sha256"],
                 round=round_, host=host, attempt=len(names), receipt_directory=Path(out).name,
                 launched_utc=time.time() if now is None else now, pid=os.getpid(), nonce=secrets.token_hex(16))
    data = (L.canonical(claim) + "\n").encode()
    with (directory / f"attempt-{len(names):02d}.json").open("xb") as stream:
        stream.write(data)
    return claim, L.sha_bytes(data)


def producer_claim(repository, job, round_, host, out, *, now=None, context=None):
    directory, committed = producer_registry(repository, job, round_, host, context)
    return claim_attempt(directory, out, job=job, round_=round_, host=host, committed=committed, now=now)


def _claims(repository, job, rev, layout):
    out = {}
    for round_, hosts in layout.items():
        for host, names in hosts.items():
            entries = []
            for index, name in enumerate(names):
                rel = claim_path(round_, host, name)
                data = namespace_blob(repository, rel, "END attempt claim", rev)
                claim = document(data, "END attempt claim " + rel)
                require(set(claim) == CLAIM_FIELDS and claim["schema"] == REGISTRY_SCHEMA
                        and claim["job_sha256"] == job["sha256"] and claim["end_evidence_sha256"] == job["end_evidence_sha256"]
                        and claim["round"] == round_ and claim["host"] == host and claim["attempt"] == index,
                        "Malformed/unbound END attempt claim: " + rel)
                entries.append((claim, L.sha_bytes(data), rel))
            out.setdefault(round_, {})[host] = entries
    return out


def _digests(claims):
    return {str(r): {h: [sha for _, sha, _ in v] for h, v in sorted(hosts.items())} for r, hosts in sorted(claims.items())}


def receipt_copies(repository, copies, claims):
    """Every committed receipt copy of a claim (complete bytes parsed) must be the registry's claim for that round,
    host and receipt directory."""
    registered = {sha: (round_, host, claim) for round_, hosts in claims.items() for host, entries in hosts.items()
                  for claim, sha, _ in entries}
    for rel, round_, host, directory in copies:
        copy = document(namespace_blob(repository, rel, "END attempt receipt copy"), "END attempt receipt copy " + rel)
        require(set(copy) == RECEIPT_COPY_FIELDS and copy["scope"] == REFERENCE_SCOPE,
                "Malformed END attempt receipt copy: " + rel)
        entry = registered.get(copy["claim_sha256"])
        require(entry is not None and entry == (round_, host, copy["claim"])
                and copy["claim"]["receipt_directory"] == directory,
                "Committed END attempt receipt whose claim is not in the registry: " + rel)


def materialize(repository, rel, target, label):
    """Copy the committed directory ``rel`` (inside END_DIR, at HEAD) into the fresh local ``target``: names from tree
    metadata, blobs through namespace_blob, every file append-only (added once, never modified). Returns
    {repository path: adding commit}."""
    names = tree_names(repository, rel)
    require(names, label + " is not committed: " + rel)
    commits = {}
    for name in names:
        path = Path(target) / name[len(rel) + 1:]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(namespace_blob(repository, name, label))
        commits[name] = immutable(repository, name, label)
    return commits


def finalization(repository, job, round_, digests, claims, final_sha256=None):
    """Round ``round_``'s committed finalization, checked identically for the latest and for every earlier round:
    fixed path, append-only, health-only fields bound to the END-JOB and round; its claims are exactly the registry's
    claims of rounds 0..round_ at HEAD and at the finalization's own commit; it is later than every launch it lists;
    its prior_rounds name every earlier round's committed pool at the fixed location with the committed seal SHA."""
    rel = final_path(round_)
    data = head_blob(repository, rel, "END finalization record")
    require(final_sha256 is None or (L.is_sha256(final_sha256) and L.sha_bytes(data) == final_sha256),
            "END finalization SHA mismatch: " + rel)
    commit = immutable(repository, rel, "END finalization record")
    final = document(data, "END finalization record")
    require(set(final) == FINAL_FIELDS and final["schema"] == FINAL_SCHEMA
            and final["job_sha256"] == job["sha256"] and final["round"] == round_
            and isinstance(final["finalized_by"], str) and final["finalized_by"],
            "Malformed END finalization record (health-only exact fields) or not bound to the END-JOB/round")
    own = {k: v for k, v in digests.items() if int(k) <= round_}
    require(final["claims"] == own, f"END finalization round {round_:02d} is not the complete claim inventory at HEAD "
                                    "(claims added/omitted after finalization, or an older snapshot)")
    require(_digests(_claims(repository, job, commit, registry_at(repository, commit))) == own,
            "END finalization was committed before every claim it lists")
    for r in range(round_ + 1):
        for entries in claims[r].values():
            for claim, _, path in entries:
                require(isinstance(final["finalized_utc"], (int, float)) and claim["launched_utc"] < final["finalized_utc"],
                        "END finalization precedes an attempt it lists: " + path)
    prior = final["prior_rounds"]
    require(isinstance(prior, list) and [p.get("round") if isinstance(p, dict) else None for p in prior]
            == list(range(round_)), "END finalization must record every earlier pool round")
    for entry in prior:
        r = entry["round"]
        require(set(entry) == PRIOR_FIELDS, "Malformed earlier-round record")
        require(entry["pool_repository_path"] == pool_path(r),
                f"Earlier END pool must be committed at its fixed location {pool_path(r)}")
        seal = head_blob(repository, pool_path(r) + "/receipt-manifest.json", "Earlier END pool")
        require(L.sha_bytes(seal) == entry["pool_manifest_sha256"], f"Earlier END pool seal mismatch: round {r:02d}")
    return dict(final, sha256=L.sha_bytes(data), repository_path=rel, commit=commit)


def rounds_authority(repository, job, through):
    """Rounds 0..``through`` of the one END job, read at HEAD: the strict namespace, the append-only registry, every
    claim bound to the job and launched after it, every round claimed on every counted host, every receipt copy a
    registry claim, and each round's finalization (``finalization``). Later (open) rounds' claims may exist at HEAD;
    they are bound and ordered (``committed_round``) but not part of these rounds."""
    copies = namespace(repository)
    registry_append_only(repository)
    head = registry_at(repository, "HEAD")
    require(all(r in head for r in range(through + 1)), "END attempt registry lacks a finalized round at HEAD")
    every = _claims(repository, job, "HEAD", head)
    commits = {}
    for round_claims in every.values():
        for entries in round_claims.values():
            for claim, _, path in entries:
                commits[path] = immutable(repository, path, "END attempt claim")
                require(ancestor(repository, job["commit"], commits[path]),
                        "END attempt claim predates the committed END-JOB: " + path)
    claims = {r: every[r] for r in range(through + 1)}
    for round_claims in claims.values():
        require(sorted(round_claims) == job["counted_hosts"], "Every END round must claim on every counted host")
    receipt_copies(repository, copies, every)
    digests = _digests(claims)
    return dict(job=job, through=through, every=every, claim_commits=commits, digests=digests,
                rounds={r: dict(round=r, digests={k: v for k, v in digests.items() if int(k) <= r},
                                claims={h: [(c, sha) for c, sha, _ in v] for h, v in claims[r].items()})
                        for r in range(through + 1)})


def round_finals(repository, authority, final_sha256=None):
    """Every round's finalization of an authority (the last one optionally pinned by the caller's SHA)."""
    through = authority["through"]
    claims = {r: authority["every"][r] for r in range(through + 1)}
    for r in range(through + 1):
        authority["rounds"][r]["final"] = finalization(repository, authority["job"], r, authority["digests"], claims,
                                                       final_sha256 if r == through else None)
    return authority


def committed_round(repository, authority, r, target):
    """Earlier round ``r``'s committed pool and every original attempt receipt, copied from HEAD into the fresh local
    ``target`` for re-validation by the pool's own code path (end_pool.validate_prior_round). Every file is
    append-only; the committed receipt directories of each host are exactly its round-r claims' receipt directories
    (none missing, none extra); every pool file was committed before any later round's claim. Returns the local pool
    directory, its seal SHA and {host: [(receipt directory, seal SHA)]} in claim order."""
    target = Path(target)
    label = f"Earlier END pool round {r:02d}"
    pool_commits = materialize(repository, pool_path(r), target / "pool", label)
    later = [commit for path, commit in authority["claim_commits"].items()
             if int(path[len(REGISTRY_ROOT) + len("/round-"):].split("/")[0]) > r]
    require(all(ancestor(repository, made, claimed) for made in pool_commits.values() for claimed in later),
            label + " was committed after a later round's claim (the re-run requires the validated pool first)")
    seal = target / "pool" / "receipt-manifest.json"
    require(seal.is_file(), label + " lacks its seal")
    receipts = {}
    for host, entries in authority["rounds"][r]["claims"].items():
        root = f"{RECEIPTS_ROOT}/round-{r:02d}/{host}"
        wanted = [claim["receipt_directory"] for claim, _ in entries]
        present = {name[len(root) + 1:].split("/")[0] for name in tree_names(repository, root)}
        require(len(set(wanted)) == len(wanted) and present == set(wanted),
                f"Earlier END round {r:02d} original attempt receipts are not committed exactly (missing/extra): {host}")
        receipts[host] = []
        for name in wanted:
            local = target / "receipts" / host / name
            materialize(repository, f"{root}/{name}", local, f"Earlier END round {r:02d} attempt receipt")
            require((local / "receipt-manifest.json").is_file(), f"Earlier END round {r:02d} receipt lacks its seal")
            receipts[host].append((local, L.sha((local / "receipt-manifest.json"))))
    return dict(pool=target / "pool", pool_manifest_sha256=L.sha(seal), receipts=receipts)


def job_registry(repository, evidence, job_sha256, k4s_manifest_sha256, round_, final_sha256):
    """Pool-side authority: the fixed END-JOB, the finalized complete append-only claim inventory for the latest
    finalized ``round_`` and every earlier round, reconciled with the registry at HEAD (never a caller-chosen commit).
    Reads blobs only inside END_DIR. Earlier rounds' pools and receipts are NOT trusted here: end_pool re-validates
    and recomputes each of them (end_pool.validate_prior_round). Returns the authority with every round's claims."""
    job = end_job(repository, evidence, job_sha256, k4s_manifest_sha256)
    require(type(round_) is int and 0 <= round_ <= 99, "END round must be an integer 0-99")
    rel = final_path(round_)
    data = head_blob(repository, rel, "END finalization record")
    require(L.is_sha256(final_sha256) and L.sha_bytes(data) == final_sha256, "END finalization SHA mismatch: " + rel)
    immutable(repository, rel, "END finalization record")
    require(finals_at_head(repository) == list(range(round_ + 1)),
            "END finalizations at HEAD must be exactly rounds 00..%02d (pool the latest finalized round)" % round_)
    require(sorted(registry_at(repository, "HEAD")) == list(range(round_ + 1)),
            "END attempt registry rounds at HEAD differ from the finalized rounds")
    authority = round_finals(repository, rounds_authority(repository, job, round_), final_sha256)
    authority["final"] = authority["rounds"][round_]["final"]
    authority["claims"] = {r: v["claims"] for r, v in authority["rounds"].items()}
    return authority
