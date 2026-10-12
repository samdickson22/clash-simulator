#!/usr/bin/env python3
"""S1b (PREREG-K4S END, Q2): exact-path reader for the guard admissions. A delta beside S1; S1 is unchanged.

CANDIDATE: requires Sol review and a coordinator GO before any live run. Runs FROM 127x05 and reads 127x03 and
127x04 read-only over ssh. Never run inside an END timing window or a preflight (RC-2) measurement on any host.

What it reads: exactly the files the frozen K4S code wrote into each host's latest K4S job
(Q2: k4s-confirm-replacement-r4; cross-checked against the committed run-r1/rounds/history.json):
    127x03  /mpac/sdicks02/jobs/clasher/k4s-confirm-replacement-r4/system-bus-admission.json
            /mpac/sdicks02/jobs/clasher/k4s-confirm-replacement-r4/idle-services.json
    127x04  /mpac/sdicks02/jobs-k4s/k4s-confirm-replacement-r4/system-bus-admission.json
The names come from the frozen code: supervise.py:34 -> host_audit.admission(j) -> system_bus.pin(j, ...) writes
j/'system-bus-admission.json' (system_bus.py:9-13), and run-r1/tools/round.sh `finalize` runs idle_services.py
--job $J on 03, which writes j/'idle-services.json' (idle_services.py:60-67), with J = <root>/<namespace>.
Nothing else is named: no glob, no listing, no recursion. The one other probe is an lstat of the literal next-job
path <root>/k4s-confirm-replacement-r5 (must be absent, so r4 is still the latest).

One login per host (2 in total). The remote side is a small stdlib python3 program (python3.8-compatible, run with
-I -S under nice -n 19) that, for each literal path, opens EVERY component from / with O_NOFOLLOW (a symlinked
directory or leaf is refused, never followed), fstat()s the opened descriptor and refuses a non-regular file or a
size outside (0, 1 MiB] BEFORE reading, then reads exactly that many bytes (growth refuses) and prints one JSON
header line followed by the bytes. Locally: the ssh output is bounded, the header names exactly the expected paths,
every piece's SHA is recomputed and must equal the header, then the JSON content / host / pinned identity
(constants re-read from the committed r4 host admissions) are checked. Nothing but a refusal receipt is written
unless both hosts passed.

Output: <dest>/<host>/<name> (0444) + <dest>/s1b-admissions-manifest.json. On a live run <dest> is created FIRST
(confined: permitted root, no symlinked ancestor, must not exist) so that every later refusal, including the
window/commit checks, leaves <dest>/S1B-REFUSAL.json. --dry-run prints the planned ssh argv; it writes nothing.
"""
import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import end_prep_common as C                                           # noqa: E402

if Path(C.__file__).resolve().parent != HERE:
    raise SystemExit("end_prep_common imported from outside " + str(HERE))

Refusal, require, sha_bytes = C.Refusal, C.require, C.sha_bytes
SCHEMA = "clasher.k4s.end-admissions-copy.v1"
STUDY = "reports/explore/k4s-confirm"
HISTORY = STUDY + "/run-r1/rounds/history.json"
HOSTS = ("127x03", "127x04")
NAMESPACE = "k4s-confirm-replacement-r4"
NEXT_NAMESPACE = "k4s-confirm-replacement-r5"
JOB_ROOTS = {"127x03": "/mpac/sdicks02/jobs/clasher", "127x04": "/mpac/sdicks02/jobs-k4s"}
BUS_NAME, IDLE_NAME = "system-bus-admission.json", "idle-services.json"
NAMES = {"127x03": (BUS_NAME, IDLE_NAME), "127x04": (BUS_NAME,)}
MAX_BYTES = 1024 * 1024
HEADER_MAX = 64 * 1024
# t1/system_bus.py:5 KEYS; identities from the committed r4 host admissions (14:04Z), process rows uid 103.
BUS_KEYS = ("pid", "start_ticks", "exe", "cmdline_sha256", "uid")
DBUS_CMDLINE_SHA = "f481db6887b1454cde723322eee10a57f08a0789ab8db6f16d41ac2ad3329749"
BUS_IDENTITY = {
    "127x03": dict(pid=2049, start_ticks=1273, exe="/usr/bin/dbus-daemon", cmdline_sha256=DBUS_CMDLINE_SHA, uid=103),
    "127x04": dict(pid=2005, start_ticks=1032, exe="/usr/bin/dbus-daemon", cmdline_sha256=DBUS_CMDLINE_SHA, uid=103),
}
# idle_services.py:7 identity keys; perception v4 validation-cache service on 03 (round.sh finalize check).
IDLE_KEYS = ("pid", "ppid", "pgid", "start_ticks", "cmdline_sha256", "uid")
IDLE_IDENTITY = dict(pid=2180947, ppid=2180946, pgid=2180934, start_ticks=139691386,
                     cmdline_sha256="16152ceb7942621141a2d8d91189affdeacde28ad1a9059ffbadde5e9bde799a", uid=3822945)
IDLE_SERVICE_NAME = "v4-validation-cache-renewed-20261010-03r1"
FORBIDDEN_PREFIXES = {"127x03": (), "127x04": ("/mpac/sdicks02/jobs/",)}
SSH_OPTIONS = ("-T", "-o", "BatchMode=yes", "-o", "ControlMaster=no", "-o", "ControlPath=none",
               "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=15",
               "-o", "ServerAliveCountMax=4", "-o", "ClearAllForwardings=yes", "-o", "RequestTTY=no")
SAFE_PATH = re.compile(r"/mpac/sdicks02/[A-Za-z0-9._/-]+")
SHA = re.compile(r"[0-9a-f]{64}")
REMOTE_PYTHON = "/usr/bin/python3"
# The remote reader (python3.8-compatible; argv: cap, probe path, file paths). Exits nonzero on any refusal.
READER = r'''
import hashlib, json, os, stat, sys
cap = int(sys.argv[1]); probe = sys.argv[2]; paths = sys.argv[3:]
F = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
def parent(path):
    parts = path.split("/")[1:]
    fd = os.open("/", F | os.O_DIRECTORY)
    for name in parts[:-1]:
        try:
            nfd = os.open(name, F | os.O_DIRECTORY, dir_fd=fd)
        finally:
            os.close(fd)
        fd = nfd
    return fd, parts[-1]
def lexists(path):
    try:
        fd, name = parent(path)
    except OSError as e:
        raise SystemExit("REFUSE " + str(e.strerror) + " (probe ancestor): " + path)
    try:
        os.stat(name, dir_fd=fd, follow_symlinks=False)
        return True
    except FileNotFoundError:
        return False
    finally:
        os.close(fd)
head = {"next": "present" if lexists(probe) else "absent", "files": []}
blobs = []
for path in paths:
    try:
        fd, name = parent(path)
        try:
            leaf = os.open(name, F | os.O_NONBLOCK, dir_fd=fd)
        finally:
            os.close(fd)
    except OSError as e:                     # missing, or a symlinked leaf/ancestor (ELOOP / ENOTDIR): never followed
        raise SystemExit("REFUSE " + str(e.strerror) + ": " + path)
    try:
        st = os.fstat(leaf)
        if not stat.S_ISREG(st.st_mode):
            raise SystemExit("REFUSE not a regular file: " + path)
        if not 0 < st.st_size <= cap:
            raise SystemExit("REFUSE size outside (0, cap]: " + path)
        data = b""
        while len(data) < st.st_size:
            chunk = os.read(leaf, st.st_size - len(data))
            if not chunk:
                raise SystemExit("REFUSE shrank while reading: " + path)
            data += chunk
        if os.read(leaf, 1):
            raise SystemExit("REFUSE grew while reading: " + path)
    finally:
        os.close(leaf)
    head["files"].append({"path": path, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    blobs.append(data)
sys.stdout.buffer.write(json.dumps(head, sort_keys=True).encode() + b"\n" + b"".join(blobs))
'''


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------- admission content (shared with S3)

def check_admission(host, name, data):
    """Structural + identity check of one admission's bytes. Returns a small identity summary."""
    require(host in HOSTS and name in NAMES[host], f"{name} is not an END guard admission for {host}")
    require(0 < len(data) <= MAX_BYTES, f"{host}/{name}: size {len(data)} outside (0, 1 MiB]")
    try:
        doc = json.loads(data)
    except ValueError:
        raise Refusal(f"{host}/{name}: not JSON") from None
    require(isinstance(doc, dict) and doc.get("host") == host, f"{host}/{name}: host field is {doc.get('host')!r}")
    if name == BUS_NAME:
        identity = doc.get("identity")
        require(isinstance(identity, dict) and tuple(sorted(identity)) == tuple(sorted(BUS_KEYS)),
                f"{host}/{name}: identity keys differ from system_bus.KEYS")
        require(identity == BUS_IDENTITY[host], f"{host}/{name}: pinned dbus identity {identity} != {BUS_IDENTITY[host]}")
        return dict(name=name, pid=identity["pid"], start_ticks=identity["start_ticks"], utc=doc.get("utc"))
    services = doc.get("services")
    require(isinstance(services, list) and len(services) == 1 and isinstance(services[0], dict),
            f"{host}/{name}: exactly one idle service expected")
    service = services[0]
    identity = service.get("service")
    require(isinstance(identity, dict) and tuple(sorted(identity)) == tuple(sorted(IDLE_KEYS)),
            f"{host}/{name}: service identity keys differ from idle_services.identity")
    require(identity == IDLE_IDENTITY and service.get("name") == IDLE_SERVICE_NAME,
            f"{host}/{name}: idle service identity/name differs from PID 2180947 of record")
    require(isinstance(service.get("wrapper_trio"), list) and len(service["wrapper_trio"]) == 3,
            f"{host}/{name}: wrapper_trio must hold 3 identities")
    return dict(name=name, pid=identity["pid"], start_ticks=identity["start_ticks"], utc=doc.get("utc"))


def job_dir(host):
    return f"{JOB_ROOTS[host]}/{NAMESPACE}"


def checked(host, path):
    require(SAFE_PATH.fullmatch(path) is not None and ".." not in path.split("/"), "unsafe path: " + path)
    require(not any(path.startswith(p) for p in FORBIDDEN_PREFIXES[host]), f"forbidden path on {host}: {path}")
    return path


def remote_paths(host):
    return [checked(host, f"{job_dir(host)}/{name}") for name in NAMES[host]]


def probe_path(host):
    return checked(host, f"{JOB_ROOTS[host]}/{NEXT_NAMESPACE}")


def committed_latest(repository, commit):
    """The committed rounds/history.json must end at the replacement-r4 namespace (Q2: the latest K4S job)."""
    require(re.fullmatch(r"[0-9a-f]{40}", commit or "") is not None, "--commit must be a full 40-hex commit")
    result = subprocess.run(["git", "-C", str(repository), "show", f"{commit}:{HISTORY}"], capture_output=True)
    require(result.returncode == 0, "rounds/history.json not committed at " + commit)
    history = json.loads(result.stdout)
    require(isinstance(history, list) and history and history[-1].get("namespace") == NAMESPACE
            and sum(row.get("namespace") == NAMESPACE for row in history) == 1,
            "committed history does not end at " + NAMESPACE)
    return sha_bytes(result.stdout)


# ---------------------------------------------------------------- remote command and parsing

def command(host):
    args = [str(MAX_BYTES), probe_path(host)] + remote_paths(host)
    return ("exec nice -n 19 " + REMOTE_PYTHON + " -I -S -c " + shlex.quote(READER) + " "
            + " ".join(shlex.quote(a) for a in args))


def ssh_argv(ssh, host, cmd):
    require(host in HOSTS, "unknown host: " + host)
    return [ssh, *SSH_OPTIONS, "--", host, cmd]


def parse(host, stdout):
    paths = remote_paths(host)
    header, sep, body = stdout.partition(b"\n")
    require(sep and len(header) <= HEADER_MAX, f"{host}: missing reader header")
    try:
        head = json.loads(header)
    except ValueError:
        raise Refusal(f"{host}: unreadable reader header") from None
    require(head.get("next") == "absent", f"{host}: {NEXT_NAMESPACE} exists; r4 is not the latest K4S job (re-rule Q2)")
    files = head.get("files")
    require(isinstance(files, list) and [f.get("path") for f in files] == paths, f"{host}: header names other paths")
    rows, offset = [], 0
    for f in files:
        size, digest = f.get("size"), f.get("sha256")
        require(type(size) is int and 0 < size <= MAX_BYTES and SHA.fullmatch(digest or ""),
                f"{host}: bad header entry for {f.get('path')}")
        data = body[offset:offset + size]
        offset += size
        require(len(data) == size and sha_bytes(data) == digest,
                f"{host}: received bytes of {f['path']} differ from the remote SHA (transport corruption?)")
        rows.append(dict(name=f["path"].rsplit("/", 1)[1], remote_path=f["path"], remote_size=size,
                         remote_sha256=digest, data=data))
    require(offset == len(body), f"{host}: {len(body) - offset} unexpected trailing bytes")
    return rows


def run(a, log=print):
    started = utc()
    if a.dry_run:
        committed_latest(a.repository, a.commit)
        log(json.dumps(dict(mode="dry-run", logins=len(HOSTS), files={h: remote_paths(h) for h in HOSTS},
                            next_probe={h: probe_path(h) for h in HOSTS},
                            expected_identities=dict(bus=BUS_IDENTITY, idle_127x03=IDLE_IDENTITY)), indent=1))
        for host in HOSTS:
            log(f"# login {host}")
            log(shlex.join(ssh_argv(a.ssh, host, command(host))))
        return None
    dest = C.confined_new(a.dest, "--dest")                    # before anything else: receipts need a home
    dest.mkdir()
    logins = []
    try:
        require(a.outside_end_window, "live run requires --outside-end-window '<coordinator GO / window reference>'")
        history_sha = committed_latest(a.repository, a.commit)
        ssh = shutil.which(a.ssh)
        require(ssh is not None, "ssh not found: " + a.ssh)
        results = {}
        for host in HOSTS:                                # every check on both hosts before anything is written
            argv = ssh_argv(ssh, host, command(host))
            logins.append(dict(host=host, started_utc=utc(), argv=argv))
            log(f"[{utc()}] ssh {host}")
            rc, out, err = C.run_bounded(argv, 300, HEADER_MAX + 1 + MAX_BYTES * len(NAMES[host]))
            logins[-1].update(finished_utc=utc(), returncode=rc, stderr_tail=err.decode(errors="replace")[-400:])
            require(rc == 0, f"ssh {host} failed rc={rc}: " + err.decode(errors="replace")[-300:])
            rows = parse(host, out)
            for row in rows:
                row["identity"] = check_admission(host, row["name"], row["data"])
            results[host] = rows
        files = []
        for host in HOSTS:
            (dest / host).mkdir()
            for row in results[host]:
                local = dest / host / row["name"]
                C.write_new(local, row["data"])
                require(C.sha_file(local) == row["remote_sha256"], "local re-read differs: " + str(local))
                files.append(dict(host=host, name=row["name"], remote_path=row["remote_path"],
                                  remote_size=row["remote_size"], remote_sha256=row["remote_sha256"],
                                  local_path=f"{host}/{row['name']}", local_sha256=C.sha_file(local),
                                  identity=row["identity"]))
        manifest = dict(schema=SCHEMA, status="copied", started_utc=started, finished_utc=utc(),
                        outside_end_window=a.outside_end_window, repository_commit=a.commit,
                        history_sha256=history_sha, namespace=NAMESPACE, ssh_logins=len(logins), logins=logins,
                        script_sha256=C.sha_file(Path(__file__).resolve()),
                        common_sha256=C.sha_file(Path(C.__file__).resolve()), files=files)
        C.write_new(dest / "s1b-admissions-manifest.json", (json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode())
    except BaseException as error:
        C.write_new(dest / "S1B-REFUSAL.json", (json.dumps(dict(schema=SCHEMA, status="refused", error=str(error),
                                                                utc=utc(), logins=logins), indent=1) + "\n").encode())
        raise
    for f in files:
        log(f"  {dest / f['local_path']}  sha256 {f['local_sha256']}")
    log(f"S1b OK: {len(files)} files, {len(logins)} logins, manifest {C.sha_file(dest / 's1b-admissions-manifest.json')}")
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repository", type=Path, default=Path("/mpac/sdicks02/repos/clasher"))
    ap.add_argument("--commit", required=True, help="full commit holding run-r1/rounds/history.json")
    ap.add_argument("--dest", help="new local destination (must not exist; permitted root; no symlinked ancestor)")
    ap.add_argument("--ssh", default="ssh")
    ap.add_argument("--outside-end-window", default="", help="required for a live run: GO/window reference")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if not a.dry_run and a.dest is None:
        ap.error("--dest is required unless --dry-run")
    try:
        run(a)
    except Refusal as error:
        print("S1b REFUSED: " + str(error), file=sys.stderr)
        return 2
    except Exception as error:                                # fail closed on anything unexpected
        print(f"S1b FAILED: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
