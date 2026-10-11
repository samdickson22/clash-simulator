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
3. The END attempt registry: ``end_reference.py`` claims ``<registry>/<host>/attempt-NN.json`` (exclusive
   creation, before its receipt directory exists). The committed registry, not the pool descriptor, defines the
   complete ordered set of original attempts per host.
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
REGISTRY_SCHEMA = "clasher.k4s.end-attempt-claim.v1"
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
        self.manifest = json.loads(seal.decode().splitlines()[0])
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
        return json.loads(self.bytes(name).decode().splitlines()[0])

    def lines(self, name):
        return [json.loads(s) for s in self.bytes(name).decode().splitlines() if s.strip()]

    def has(self, name):
        return name in self.files


# ---------------------------------------------------------------- 3. END attempt registry

ATTEMPT = re.compile(r"attempt-([0-9]{2})\.json")


def claim_attempt(registry, host, out, *, now=None):
    """Exclusive claim <registry>/<host>/attempt-NN.json before the receipt directory exists.

    Returns (claim, claim_sha256). NN counts every earlier claim on this host, so an attempt can never
    be launched without leaving a registry entry, and the pool descriptor cannot omit one."""
    directory = Path(registry) / host
    directory.mkdir(parents=True, exist_ok=True)
    names = sorted(p.name for p in directory.iterdir())
    require(all(ATTEMPT.fullmatch(n) for n in names) and names == [f"attempt-{i:02d}.json" for i in range(len(names))],
            "END attempt registry is not a contiguous claim sequence: " + host)
    claim = dict(schema=REGISTRY_SCHEMA, host=host, attempt=len(names), receipt_directory=Path(out).name,
                 launched_utc=time.time() if now is None else now, pid=os.getpid(), nonce=secrets.token_hex(16))
    data = (L.canonical(claim) + "\n").encode()
    with (directory / f"attempt-{len(names):02d}.json").open("xb") as stream:
        stream.write(data)
    return claim, L.sha_bytes(data)


def committed_registry(repository, commit, repository_path):
    """The committed attempt registry: {host: [(claim, sha256), ...]} in attempt order (git blobs only)."""
    require(isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit), "Attempt registry needs a full commit")
    rel = Path(repository_path or "")
    require(rel.parts and not rel.is_absolute() and ".." not in rel.parts, "Attempt registry path must be repo-relative")
    ancestry = subprocess.run(["git", "-C", str(repository), "merge-base", "--is-ancestor", commit, "HEAD"],
                              capture_output=True)
    require(ancestry.returncode == 0, "Attempt registry commit is not an ancestor of HEAD")
    listing = subprocess.run(["git", "-C", str(repository), "ls-tree", "-r", "--name-only", commit, "--",
                              rel.as_posix() + "/"], capture_output=True, text=True)
    require(listing.returncode == 0 and listing.stdout.strip(), "Attempt registry is not in the commit")
    registry = {}
    for line in listing.stdout.splitlines():
        parts = Path(line[len(rel.as_posix()) + 1:]).parts
        require(len(parts) == 2 and ATTEMPT.fullmatch(parts[1]), "Unexpected attempt registry entry: " + line)
        registry.setdefault(parts[0], []).append(parts[1])
    out = {}
    for host, names in registry.items():
        require(sorted(names) == [f"attempt-{i:02d}.json" for i in range(len(names))],
                "Attempt registry is not contiguous: " + host)
        entries = []
        for index, name in enumerate(sorted(names)):
            data = L.git_bytes(repository, commit, rel.as_posix() + "/" + host + "/" + name)
            claim = json.loads(data)
            require(claim.get("schema") == REGISTRY_SCHEMA and claim.get("host") == host and claim.get("attempt") == index,
                    "Malformed attempt claim: " + host + "/" + name)
            entries.append((claim, L.sha_bytes(data)))
        out[host] = entries
    return out
