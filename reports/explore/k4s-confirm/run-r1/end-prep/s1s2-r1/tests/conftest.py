"""Offline fixtures for S1/S2. No ssh, no host access: S1 runs against a fake `ssh` shim on PATH that serves a
temporary directory tree; S2 runs against a synthetic git repository plus the frozen code exported (git show) from
the real clasher repository."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
S1 = HERE.parent / "s1_copy_end_sources.py"
S2 = HERE.parent / "s2_end_evidence.py"
CLASHER = Path(os.environ.get("CLASHER_REPO", "/mpac/sdicks02/repos/clasher"))
STUDY = "reports/explore/k4s-confirm"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def py(script, *args, env=None, cwd=None):
    """Run a script as a subprocess, propagating -O so the checks are exercised under python -O as well."""
    flags = ["-I"] + (["-O"] * sys.flags.optimize)
    return subprocess.run([sys.executable, *flags, str(script), *map(str, args)], capture_output=True, text=True,
                          env=env, cwd=cwd)


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout


def frozen_commit():
    return git(CLASHER, "rev-parse", "origin/main").decode().strip()


def blob(rel, commit=None):
    return git(CLASHER, "show", f"{commit or frozen_commit()}:{rel}")


# ---------------------------------------------------------------- frozen code root (S2)

@pytest.fixture(scope="session")
def code_root(tmp_path_factory):
    """The K4S manifest's closure (manifest + every pinned file) exported from origin/main."""
    root = tmp_path_factory.mktemp("code-root")
    commit = frozen_commit()
    manifest_rel = STUDY + "/mac/K4S-MAC-MANIFEST.json"
    manifest = json.loads(blob(manifest_rel, commit))
    names = {manifest_rel, *manifest["k4s_files"], *manifest["end_files"], *manifest["reused_readonly"],
             *manifest["k4s_kernel"]["files"], STUDY + "/DELTA-MANIFEST.json"}
    for rel in names:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob(rel, commit))
    return root


# ---------------------------------------------------------------- synthetic S2 repository

CPUS = list(range(1, 56))


def plan_doc():
    host = dict(physical_cpus=CPUS, supervisor_cpu=61, copy_cpu=62, census_cpu=63)
    return dict(study="PREREG-K4S", compute=dict(hosts={"127x03": host, "127x04": host, "127x01": host}, nice=10,
                                                 scheduler="SCHED_OTHER", slot_width=5, slots=11, console_slots=8,
                                                 smt=False, forbidden_hosts=["127x05"]))


def descriptor(pop, i, host, **extra):
    return dict(id=f"{pop}-{i:04d}", population=pop, host=host, cell=i % 5, index=i, **extra)


def clock_rows(host, n=5, inflight=11, drop_mhz=None):
    census, mhz = [], []
    for t in range(n):
        stamp = f"2026-10-11T20:00:{t:02d}Z"
        census.append(dict(utc=stamp, host=host, phase="reporting", inflight=inflight if t else 3))
        if t != drop_mhz:
            mhz.append(dict(utc=stamp, slots=11, physical_core_mhz=[dict(cpu=c, mhz=3000.0 + c) for c in CPUS]))
    return ("".join(json.dumps(r) + "\n" for r in mhz).encode(), "".join(json.dumps(r) + "\n" for r in census).encode())


def synthetic_files(variant=None):
    """{repo path: bytes} for a consistent synthetic completion (3000/900 counted, 1 loss + replacement)."""
    variant = variant or {}
    phases = {"127x03": ["reporting", "replacement-r1"], "127x04": ["reporting"]}
    exits = {(h, p): dict(utc="2026-10-12T10:00:00Z", host=h, reason="owned_STOP", completed=[], failed=[],
                          unstarted=[]) for h, ps in phases.items() for p in ps}
    rows = []
    for pop, count in (("primary", 3000), ("guard", 900)):
        for i in range(count):
            host = "127x03" if i % 2 == 0 else "127x04"
            d = descriptor(pop, i, host)
            if (pop, i) == ("primary", 2):
                exits[(host, "reporting")]["failed"].append(d)
                continue
            exits[(host, "reporting")]["completed"].append(d)
            rows.append(dict(host=host, phase="reporting", descriptor=d))
    lost = descriptor("primary", 2, "127x03")
    replacement = dict(id="primary-r0002", population="primary", cell=lost["cell"], index=2, replaces="primary-0002")
    placed = dict(replacement, host="127x03", dispatch="replacement-r1")
    exits[("127x03", "replacement-r1")]["completed"].append(placed)
    rows.append(dict(host="127x03", phase="replacement-r1", descriptor=placed))
    exit_bytes = {k: (json.dumps(v, indent=1) + "\n").encode() for k, v in exits.items()}
    ledger = dict(utc="2026-10-12T11:00:00Z", sealed=True,
                  events=[dict(utc="2026-10-12T11:00:00Z", lost=lost, replacement=replacement, reason="failed",
                               evidence_sha256=sha(exit_bytes[("127x03", "reporting")]))])
    inventory = dict(schema="clasher.t1.counted-blocks.v1", outcomes_sealed=True, blocks=rows)
    ledger_b = (json.dumps(ledger, indent=1) + "\n").encode()
    inventory_b = (json.dumps(inventory, indent=1) + "\n").encode()
    completion = dict(schema="clasher.k4s.reporting-completion.v1", study="PREREG-K4S", reporting_complete=True,
                      outcomes_sealed=True, counted_primary_blocks=3000, counted_guard_blocks=900,
                      counted_host_phases=phases, completed_at_utc="2026-10-12T14:45:34Z",
                      blind_ledger_sha256=sha(ledger_b), counted_inventory_sha256=sha(inventory_b),
                      supervisor_exits={f"{h}/{p}": dict(sha256=sha(b)) for (h, p), b in exit_bytes.items()})
    if "completion" in variant:
        variant["completion"](completion)
    files = {STUDY + "/plan.json": (json.dumps(plan_doc(), indent=1) + "\n").encode(),
             STUDY + "/run-r1/completion-v2/REPORTING-COMPLETION.json": (json.dumps(completion, indent=1) + "\n").encode(),
             STUDY + "/run-r1/completion-v2/counted-inventory.json": inventory_b,
             STUDY + "/run-r1/ledger/blind-ledger-final.json": ledger_b}
    for (h, p), data in exit_bytes.items():
        meta = f"{STUDY}/run-r1/phase-meta/{h}-{p}"
        launch = dict(utc="2026-10-11T20:00:00Z", host=h, phase="replacement" if p.startswith("replacement") else "reporting",
                      slots=11)
        files[meta + "/launch.json"] = (json.dumps(launch) + "\n").encode()
        files[meta + "/supervisor-exit.json"] = data
        mhz, census = clock_rows(h, **variant.get("clock", {}).get((h, p), {}))
        if (h, p) not in variant.get("no_sources", ()):
            files[f"{STUDY}/end-sources/{h}/{p}/mhz.jsonl"] = mhz
            files[f"{STUDY}/end-sources/{h}/{p}/census.jsonl"] = census
    return files


def make_repo(root, files):
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q")
    git(root, "symbolic-ref", "HEAD", "refs/heads/main")
    git(root, "config", "user.email", "s2-test@example.invalid")
    git(root, "config", "user.name", "s2 test")
    for rel, data in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "artifacts")
    return git(root, "rev-parse", "HEAD").decode().strip()


def pins_args(files):
    return ["--expect-plan", sha(files[STUDY + "/plan.json"]),
            "--expect-completion", sha(files[STUDY + "/run-r1/completion-v2/REPORTING-COMPLETION.json"]),
            "--expect-counted-inventory", sha(files[STUDY + "/run-r1/completion-v2/counted-inventory.json"]),
            "--expect-blind-ledger", sha(files[STUDY + "/run-r1/ledger/blind-ledger-final.json"])]


@pytest.fixture
def synthetic(tmp_path):
    def make(variant=None, name="repo"):
        files = synthetic_files(variant)
        repo = tmp_path / name
        commit = make_repo(repo, files)
        return repo, commit, files
    return make


# ---------------------------------------------------------------- fake ssh (S1)

SHIM = r'''#!{python}
"""Fake ssh: logs argv, refuses missing hygiene options, serves FAKE_SSH_ROOT/<host>/ as the host's /."""
import json, os, subprocess, sys
argv = sys.argv[1:]
log = os.environ["FAKE_SSH_LOG"]
opts, i = [], 0
while i < len(argv) and argv[i] != "--":
    if argv[i] == "-o":
        opts.append(argv[i + 1]); i += 2
    else:
        opts.append(argv[i]); i += 1
host, command = argv[i + 1], " ".join(argv[i + 2:])
with open(log, "a") as f:
    f.write(json.dumps(dict(argv=sys.argv, host=host, command=command)) + "\n")
for need in ("BatchMode=yes", "ControlMaster=no", "ControlPath=none"):
    if need not in opts:
        sys.stderr.write("shim: missing " + need + "\n"); sys.exit(255)
if os.environ.get("FAKE_SSH_FAIL_HOST") == host:
    sys.stderr.write("shim: connection refused\n"); sys.exit(255)
root = os.path.join(os.environ["FAKE_SSH_ROOT"], host)
rewritten = command.replace("/mpac/sdicks02/", root + "/mpac/sdicks02/")
if " cat -- " in command:
    rc = subprocess.run(["sh", "-c", rewritten]).returncode          # raw byte stream
else:                                                                # names as the host would print them
    done = subprocess.run(["sh", "-c", rewritten], capture_output=True, text=True)
    sys.stdout.write(done.stdout.replace(root + "/mpac/sdicks02/", "/mpac/sdicks02/"))
    sys.stderr.write(done.stderr.replace(root + "/mpac/sdicks02/", "/mpac/sdicks02/"))
    rc = done.returncode
sys.stdout.flush()
if " cat -- " in command:
    if os.environ.get("FAKE_SSH_EXTRA") == host:
        sys.stdout.write("junk"); sys.stdout.flush()
    target = os.environ.get("FAKE_SSH_MUTATE")
    if target and target.startswith(host + ":"):
        with open(root + target.split(":", 1)[1], "ab") as f:
            f.write(b"x")
sys.exit(rc)
'''

ROOTS = {"127x03": "/mpac/sdicks02/jobs/clasher", "127x04": "/mpac/sdicks02/jobs-k4s"}
PHASES = (("reporting", "k4s-confirm-reporting-r1"), ("replacement-r1", "k4s-confirm-replacement-r1"),
          ("replacement-r2", "k4s-confirm-replacement-r2"), ("replacement-r3", "k4s-confirm-replacement-r3"),
          ("replacement-r4", "k4s-confirm-replacement-r4"))


def phase_dir(fake_root, host, phase, namespace):
    return fake_root / host / ROOTS[host].lstrip("/") / namespace / phase


@pytest.fixture
def fake_hosts(tmp_path):
    """Fake 03/04 trees: the REAL committed launch/supervisor-exit bytes (origin/main) + synthetic mhz/census,
    plus decoys (games/, complete.json, look-alike names, 04 perception storage) that S1 must never name."""
    commit = frozen_commit()
    fake_root = tmp_path / "hosts"
    for host in ROOTS:
        for phase, namespace in PHASES:
            d = phase_dir(fake_root, host, phase, namespace)
            d.mkdir(parents=True)
            meta = f"{STUDY}/run-r1/phase-meta/{host}-{phase}"
            (d / "launch.json").write_bytes(blob(meta + "/launch.json", commit))
            (d / "supervisor-exit.json").write_bytes(blob(meta + "/supervisor-exit.json", commit))
            mhz, census = clock_rows(host)
            (d / "mhz.jsonl").write_bytes(mhz + f'{{"tag":"{host}/{phase}/mhz"}}\n'.encode())
            (d / "census.jsonl").write_bytes(census + f'{{"tag":"{host}/{phase}/census"}}\n'.encode())
            (d / "games").mkdir()
            (d / "games" / "decoy.json").write_text("{}")
            (d / "complete.json").write_text("{}")
            (d / "mhz.jsonl.old").write_text("decoy")
            (d / "primary-0001.log").write_text("decoy")
        perception = fake_root / "127x04" / "mpac/sdicks02/jobs/clasher/k4s-confirm-reporting-r1/reporting"
        perception.mkdir(parents=True, exist_ok=True)
        (perception / "mhz.jsonl").write_text("PERCEPTION DECOY")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    shim = bindir / "ssh"
    shim.write_text(SHIM.replace("{python}", sys.executable))
    shim.chmod(0o755)
    log = tmp_path / "ssh-log.jsonl"
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", FAKE_SSH_ROOT=str(fake_root), FAKE_SSH_LOG=str(log))
    return dict(root=fake_root, env=env, log=log, commit=commit, dest=tmp_path / "end-sources", tmp=tmp_path)


def ssh_log(log):
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
