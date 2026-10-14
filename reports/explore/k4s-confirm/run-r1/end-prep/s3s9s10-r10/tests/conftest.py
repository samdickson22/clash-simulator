"""Offline fixtures for the S1b / S3 / S9 / S10 r3 candidates (r3: the synthetic world itself lives in
fixture_guard_job.py, shared with the END-FULL-F2 guard-job fixture CLI; s10_stage_host is imported first, as the top
of the END-FULL-F1 pin chain). Fully SYNTHETIC: no real repository, T1 tree, admission,
receipt or host is read. Everything is written under one tempfile directory in /tmp (neutral names, removed at the end).

* World: a synthetic origin repository (branch main) with the production paths of the pin lists, the K4S manifest,
  e4v3, the E1 link, FROZEN-T1, the T1 modules, seed/join receipts and history.json; synthetic frozen modules that
  implement the frozen rules; the full clone is created by the candidate's own `S9 prepare-clone` (file:// origin).
  Module constants that bind real production bytes (pins, commits, REPO_FULL, Q5_SOURCE, ...) are patched for the
  whole session to the synthetic values; ORIG keeps the production values for the constant tests.
* Fake hosts: a fake ssh that runs the remote words in a user+mount+UTS namespace (`unshare -Urmu`) whose
  /mpac/sdicks02 is a bind mount of FAKE/<host> and whose hostname is the host: the shipped safe_input programs run
  unmodified, including their node-name check; the real /mpac/sdicks02 is invisible to them.
"""
import hashlib  # noqa: F401
import json
import os
import shutil  # noqa: F401
import stat  # noqa: F401
import subprocess
import sys
import tempfile

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
# r3: the synthetic world lives in fixture_guard_job.py (stdlib only), shared with the F2 guard-job fixture CLI.
from fixture_guard_job import *  # noqa: E402,F401,F403
from fixture_guard_job import (C, CANARY, HOSTS, ORIG, S1B, S3, S9, World, _patch, _world, admissions,  # noqa: E402
                               make_file, ok, read, restore, rmtree, sha, si)
from fixture_guard_job import S10, S11  # noqa: E402,F401


# ---------------------------------------------------------------- fake ssh (namespaced fake hosts)

SHIM = r'''#!/usr/bin/python3 -IS
# Fake ssh for the S1b/S10 r2 tests only: hygiene options required; the remote words run under /bin/sh in a
# user+mount+UTS namespace whose /mpac/sdicks02 is a bind mount of ROOT/<host> and whose hostname is <host>.
import os, subprocess, sys
LOG, ROOT, MODE, FAILAT = @LOG@, @ROOT@, @MODE@, @FAILAT@
argv = sys.argv[1:]
with open(LOG, "a") as stream:
    stream.write(" ".join(argv).replace("\n", "~") + "\n")
with open(LOG) as stream:
    n = sum(1 for _ in stream)
words = " " + " ".join(argv) + " "
for need in ("BatchMode=yes", "ControlMaster=no", "ControlPath=none", "StrictHostKeyChecking=yes"):
    if " " + need + " " not in words:
        sys.stderr.write("shim: missing %s\n" % need)
        sys.exit(255)
i = argv.index("--")
host, command = argv[i + 1], " ".join(argv[i + 2:])
if FAILAT is not None and n == FAILAT:
    sys.stdin.buffer.read()
    sys.stderr.write("shim: connection refused\n")
    sys.exit(255)
inner = 'mount --bind "$1" /mpac/sdicks02 && hostname "$2" && cd / && exec /bin/sh -c "$3"'
done = subprocess.run(["/usr/bin/unshare", "-Urmu", "/bin/sh", "-c", inner, "shim", ROOT + "/" + host, host, command],
                      env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"}, stdout=subprocess.PIPE)
out = done.stdout
if MODE == "junk" and n == (FAILAT or n):
    out += b"junk"
elif MODE == "flip" and b'"content_b64":"' in out:
    k = out.index(b'"content_b64":"') + len(b'"content_b64":"') + 4
    out = out[:k] + (b"A" if out[k:k + 1] != b"A" else b"B") + out[k + 1:]
sys.stdout.buffer.write(out)
sys.exit(done.returncode)
'''


class FakeHosts(object):
    def __init__(self, base, fail_at=None, mode=None):
        self.base = base
        self.root = os.path.join(base, "hosts")
        self.log = os.path.join(base, "ssh.log")
        self.ssh = os.path.join(base, "ssh")
        for host in HOSTS:
            for parent in ("jobs/clasher", "jobs-k4s"):
                os.makedirs(os.path.join(self.root, host, parent), exist_ok=True)
        os.makedirs(os.path.join(self.root, "127x04", "jobs", "perception-never-touch"), exist_ok=True)
        self.write_shim(fail_at, mode)

        # r4 (U4): the declared END interpreter of the fake hosts (session-patched S10.HOST_PYTHON): a symlink to the
        # system python3, whose version the session patches into S10.HOST_PYTHON_VERSION.
        for host in HOSTS:
            fakebin = os.path.join(self.root, host, "fakebin")
            os.makedirs(fakebin, exist_ok=True)
            if not os.path.lexists(os.path.join(fakebin, "python3")):
                os.symlink("/usr/bin/python3", os.path.join(fakebin, "python3"))
            # r5 (U4): the declared END interpreter is a VENV python (S10 pins its prefix, base, pyvenv.cfg and
            # site-packages): a real venv layout on the system python3 (bin/python -> /usr/bin/python3, pyvenv.cfg
            # home = /usr/bin) whose site-packages holds stand-ins for the END third-party imports.
            venv = os.path.join(self.root, host, "fakevenv")
            if not os.path.lexists(venv):
                os.makedirs(os.path.join(venv, "bin"))
                os.symlink("/usr/bin/python3", os.path.join(venv, "bin", "python"))
                make_file(os.path.join(venv, "pyvenv.cfg"), ("home = /usr/bin\ninclude-system-site-packages = false\n"
                                                             "version = %s\n" % SYSTEM_PYTHON3_VERSION).encode())
                sp = os.path.join(venv, "lib", "python%s" % ".".join(SYSTEM_PYTHON3_VERSION.split(".")[:2]),
                                  "site-packages")
                for name in FAKE_VENV_IMPORTS:
                    make_file(os.path.join(sp, name + ".py"), b"__version__ = '0.0+k4s-fake'\n")

    def write_shim(self, fail_at=None, mode=None):
        text = (SHIM.replace("@LOG@", repr(self.log)).replace("@ROOT@", repr(self.root))
                .replace("@MODE@", repr(mode)).replace("@FAILAT@", repr(fail_at)))
        with open(self.ssh, "w") as stream:
            stream.write(text)
        os.chmod(self.ssh, 0o755)

    def path(self, host, remote):
        ok(remote.startswith("/mpac/sdicks02/"), remote)
        return os.path.join(self.root, host, remote[len("/mpac/sdicks02/"):])

    def logins(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log) as stream:
            return [line.rstrip("\n") for line in stream]

    def tool(self, host, name, script):
        """A fake host tool at /mpac/sdicks02/fakebin/<name> (inside the namespace)."""
        path = make_file(os.path.join(self.root, host, "fakebin", name), script.encode(), 0o755)
        return "/mpac/sdicks02/fakebin/" + name, path


@pytest.fixture(scope="session")
def world():
    work = os.path.realpath(tempfile.mkdtemp(prefix="k4s-r2t-", dir="/tmp"))
    try:
        w = _world(work)
    except BaseException:
        restore()
        rmtree(work)
        raise
    yield w
    restore()
    rmtree(w.work)


@pytest.fixture
def tmpdir_(world):
    """A fresh neutral-named directory inside the session work dir (never a test-name path)."""
    path = tempfile.mkdtemp(prefix="t-", dir=world.work)
    yield path
    rmtree(path)


@pytest.fixture
def repo_copy(world, tmpdir_, monkeypatch):
    """r4: a private byte copy of the session full clone, installed as S9.REPO_FULL (and S3's) for one test."""
    path = os.path.join(tmpdir_, "repo-full-copy")
    shutil.copytree(world.repo_full, path, symlinks=True)
    monkeypatch.setattr(S9, "REPO_FULL", path)
    monkeypatch.setattr(S3, "REPO_FULL", path)
    return path


@pytest.fixture
def hosts(world):
    base = tempfile.mkdtemp(prefix="fh-", dir=world.work)
    fake = FakeHosts(base)
    for host in HOSTS:
        job = fake.path(host, "%s/%s" % (S1B.JOB_ROOTS[host], S1B.NAMESPACE))
        for name, data in admissions(host).items():
            make_file(os.path.join(job, name), data)
    old = (S1B.SSH_BINARY, S10.SSH_BINARY, dict(S10.REMOTE_TOOLS))
    S1B.SSH_BINARY = S10.SSH_BINARY = fake.ssh
    yield fake
    S1B.SSH_BINARY, S10.SSH_BINARY = old[0], old[1]                   # (S11 sends its session through S10.ssh_script_argv)
    S10.REMOTE_TOOLS.clear()
    S10.REMOTE_TOOLS.update(old[2])
    rmtree(base)


class Args(object):
    def __init__(self, **kw):
        self.__dict__.update(kw)


def s1b_args(world, dest, **kw):
    base = dict(repository=world.repo_full, commit=world.P, dest=dest, outside_end_window="TEST GO ref",
                dry_run=False)
    base.update(kw)
    return Args(**base)


@pytest.fixture(scope="session")
def s1b_out(world):
    """One real S1b run against fake hosts (session): the admissions + manifest S3 consumes."""
    base = tempfile.mkdtemp(prefix="s1b-", dir=world.work)
    fake = FakeHosts(base)
    for host in HOSTS:
        job = fake.path(host, "%s/%s" % (S1B.JOB_ROOTS[host], S1B.NAMESPACE))
        for name, data in admissions(host).items():
            make_file(os.path.join(job, name), data)
    old = S1B.SSH_BINARY
    S1B.SSH_BINARY = fake.ssh
    try:
        dest = os.path.join(base, "dest")
        S1B.run(s1b_args(world, dest), log=lambda *a: None)
    finally:
        S1B.SSH_BINARY = old
    manifest = os.path.join(dest, "s1b-admissions-manifest.json")
    return dict(dest=dest, manifest=manifest, sha=sha(read(manifest)), logins=fake.logins())


def s3_args(world, s1b, out, host="127x03", round_="00", attempt="00", preflight=None, **kw):
    base = dict(host=host, round=None if preflight else round_, attempt=None if preflight else attempt,
                preflight=preflight, commit=world.P, s1b_manifest=s1b["manifest"], s1b_manifest_sha256=s1b["sha"],
                out=out, python=world.python)
    base.update(kw)
    return Args(**base)


@pytest.fixture(scope="session")
def guard03(world, s1b_out):
    out = os.path.join(tempfile.mkdtemp(prefix="g03-", dir=world.work), "guard")
    manifest = S3.build(s3_args(world, s1b_out, out), log=lambda *a: None)
    return dict(out=out, job=manifest["job_name"], sha=manifest["_sha256"], manifest=manifest)


@pytest.fixture(scope="session")
def runtime(world):
    out = os.path.join(tempfile.mkdtemp(prefix="rt-", dir=world.work), "runtime-P")
    manifest = S9.build(Args(commit=world.P, out=out, python=world.python), log=lambda *a: None)
    return dict(out=out, sha=manifest["_sha256"], manifest=manifest)


PRODUCTION_FILES = {"v1.pt": b"synthetic v1 model\n", "R3a.pt": b"synthetic R3a model\n",
                    "R3a-calibration.json": b'{"calibration": 1}\n', "states.pkl": b"synthetic states\n",
                    "states-rows.json": b'{"rows": 1}\n', "states-rows.bin": b"\x00\x01rows"}


def make_bundle(world, parent, name, host, runtime_manifest, guard=None, synthetic=False, receipt_overrides=None,
                manifest_overrides=None, freeze_bytes=None):
    """A synthetic S4-shaped fleet-reference bundle (schema/profile/receipt as S4 r3b writes them)."""
    root = os.path.join(parent, name)
    files = dict(PRODUCTION_FILES)
    guard_job = (guard["manifest"]["target_job"] if guard else S3.GUARD_PARENTS[host] + "/k4s-end-guard-r1-rd00-a00")
    adm_map = {}
    for n in S3.END_ADMISSIONS[host]:                                   # r4 IR-03
        rel = "t1-guard/guard-admissions/" + n
        files[rel] = admissions(host)[n]
        adm_map[n] = rel
    files["t1-guard/t1-freeze.json"] = freeze_bytes or world.files[S3.FREEZE_REL]
    seed_map = {}
    for b in S3.BINDINGS:
        rel = "t1-guard/seed-inputs/" + b["path"]
        files[rel] = world.git(world.origin, "show", b["commit"] + ":" + b["path"])
        seed_map[b["path"]] = rel
    for rel, data in files.items():
        make_file(os.path.join(root, rel), data, 0o444)
    manifest = dict(schema=S10.BUNDLE_SCHEMA, final=False, profile="fleet-reference",
                    files={rel: sha(data) for rel, data in files.items()},
                    runtime_files=runtime_manifest["runtime_files"],
                    measurement_files=runtime_manifest["measurement_files"],
                    reference_load_profile=dict(host=host, guard=dict(root="t1-guard", job=guard_job,
                                                                      freeze="t1-guard/t1-freeze.json",
                                                                      admissions=adm_map, seed_inputs=seed_map)))
    if synthetic:
        manifest["k4s_s4_synthetic"] = "SYNTHETIC-TEST-ONLY"
    manifest.update(manifest_overrides or {})
    raw = (C.canonical(manifest) + "\n").encode()
    make_file(os.path.join(root, "tiers-pins.json"), raw, 0o444)
    make_file(os.path.join(root, "tiers-pins.sha256"), ("%s  tiers-pins.json\n" % sha(raw)).encode(), 0o444)
    receipt = dict(schema=S10.ASSEMBLY_SCHEMA, manifest_sha256=sha(raw), host=host, guard_job=guard_job,
                   production_pins=not synthetic, final=False, outcomes_read=False, live_actions=False,
                   status="SYNTHETIC-TEST-ONLY" if synthetic else "CANDIDATE", assembler_sha256=SYNTHETIC_S4_SHA256)
    receipt.update(receipt_overrides or {})
    rraw = (C.canonical(receipt) + "\n").encode()
    make_file(os.path.join(root, "assembly-receipt.json"), rraw, 0o444)
    return dict(dir=root, tiers=sha(raw), receipt=sha(rraw), name=name)


SYNTHETIC_S4_SHA256 = sha(b"synthetic adopted S4 assembler (tests only)\n")
FAKE_HOST_PYTHON = "/mpac/sdicks02/fakevenv/bin/python"                # r5 (U4): a venv python, like the real pin
FAKE_VENV_IMPORTS = ("k4sfake_numpy", "k4sfake_torch", "k4sfake_cv2", "k4sfake_scipy")
SYSTEM_PYTHON3_VERSION = subprocess.run(["/usr/bin/python3", "-I", "-c", "import sys; print('%d.%d.%d' % "
                                         "sys.version_info[:3])"], stdout=subprocess.PIPE).stdout.decode().strip()


@pytest.fixture(scope="session", autouse=True)
def production_pins_patch(world):
    """S10 production identities -> the synthetic bundle bytes (session); ORIG keeps the real ones. r4: the adopted
    S4 SHA, the fake hosts' interpreter (system python3 via a symlink; stdlib imports) and its version."""
    pins = {name: sha(data) for name, data in PRODUCTION_FILES.items()}
    _patch(S10, "PRODUCTION_PINS", pins)
    _patch(S10, "ADOPTED_S4_SHA256", SYNTHETIC_S4_SHA256)
    _patch(S10, "HOST_PYTHON", FAKE_HOST_PYTHON)
    _patch(S10, "HOST_PYTHON_VERSION", SYSTEM_PYTHON3_VERSION)
    _patch(S10, "HOST_PYTHON_IMPORTS", FAKE_VENV_IMPORTS)
    _patch(S10, "HOST_PYTHON_PREFIX", "/mpac/sdicks02/fakevenv")
    _patch(S10, "HOST_PYTHON_BASE_PREFIX", "/usr")
    _patch(S10, "HOST_PYTHON_REALPATH", os.path.realpath("/usr/bin/python3"))
    _patch(S10, "HOST_PYTHON_INFO", ("/mpac/sdicks02/fakebin/no-such-python",))
    _patch(S11, "REQUIRED_ANCESTOR", world.base_commit)               # r4: the synthetic stand-in of 022ec7bf
    yield


def s10_args(**kw):
    base = dict(host="127x03", runtime=None, runtime_manifest_for_checks=None, runtime_manifest_sha256=None,
                bundle=None, guard_job=None, guard_job_name=None, guard_manifest_sha256=None, create_base=False,
                record=None, outside_end_window="TEST A2 GO", dry_run=False, print_layout=False, declare_roots=False,
                tools_source=None, end_inputs=False)
    base.update(kw)
    return Args(**base)


def run_py(script, *args, optimize=None):
    """Run a candidate as a subprocess (-I -B; -O when pytest runs under -O), cwd /tmp."""
    flags = ["-I", "-B"] + (["-O"] * (sys.flags.optimize if optimize is None else optimize))
    return subprocess.run([sys.executable] + flags + [os.path.join(ROOT, script)] + [str(a) for a in args],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd="/tmp")


def canary_file(directory, name="canary.json"):
    return make_file(os.path.join(directory, name), CANARY, 0o644)
