#!/usr/bin/env python3
"""S1 (PREREG-K4S END, B2 / RC-4a): exact-path copier for the reporting mhz.jsonl / census.jsonl sources.

CANDIDATE: requires Sol review and a coordinator GO before any live run. Runs FROM 127x05 and reads 127x03 and
127x04 read-only over ssh. Never run inside an END timing window (first quiet read .. attempt exit + C-d), on
any host.

For each of the 10 counted (host, phase) pairs the phase directory is a FIXED literal:
    127x03: /mpac/sdicks02/jobs/clasher/<namespace>/<phase>/
    127x04: /mpac/sdicks02/jobs-k4s/<namespace>/<phase>/
with <namespace> from the committed run-r1/rounds/history.json (cross-checked against the constant table). On 04
nothing under /mpac/sdicks02/jobs/ (the perception storage) is ever named.

Within each phase directory exactly four names are ever named, by full literal path (no glob, no recursion, no
listing, no other name): launch.json, supervisor-exit.json, mhz.jsonl, census.jsonl.

Order (fail closed; any error refuses and stops; nothing is copied unless every check on BOTH hosts passed):
  1. login P (one per host): LC_ALL=C stat -c '%F|%s|%n' and sha256sum of the 4 files of all 5 phases.
     Local checks, in order, per phase: launch.json and supervisor-exit.json SHA == the committed phase-meta SHA
     (computed from `git show <commit>:<phase-meta path>`, == the constant table, and for the exit == the
     completion-v2 supervisor_exits SHA); all 4 are regular files (no symlink); mhz/census 0 < size <= 95 MiB.
  2. login C (one per host): `cat -- <10 exact paths>` streamed to one local temp file, split by the login-P sizes;
     total length and every piece's SHA must equal login P.
  3. login V (one per host): the same stat + sha256sum again; every size and SHA must be unchanged and the
     mhz/census SHA must equal the local copy.
Logins: 3 per host, 6 in total (P03, P04, C03, V03, C04, V04), each with ControlMaster=no, ControlPath=none,
BatchMode=yes, StrictHostKeyChecking=yes; every remote command runs under `nice -n 19`.

Output: <dest>/<host>/<phase>/{mhz.jsonl,census.jsonl} (dest must not exist) and <dest>/s1-copy-manifest.json
(on-host + local SHA-256 and sizes). A refusal writes <dest>/S1-REFUSAL.json (if dest was created) and exits 2.
--dry-run prints the planned ssh argv and the expected SHAs; it makes no ssh call and writes nothing.
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

SCHEMA = "clasher.k4s.end-sources-copy.v1"
STUDY = "reports/explore/k4s-confirm"
HISTORY = STUDY + "/run-r1/rounds/history.json"
COMPLETION = STUDY + "/run-r1/completion-v2/REPORTING-COMPLETION.json"
COMPLETION_SHA256 = "3794d953efb2c8af47a09ccb086cc0441f1c0dd9ea7a4f46e331315972c6e891"
MAX_BYTES = 95 * 1024 * 1024
HOSTS = ("127x03", "127x04")
JOB_ROOTS = {"127x03": "/mpac/sdicks02/jobs/clasher", "127x04": "/mpac/sdicks02/jobs-k4s"}
# Never named on that host (04 holds the perception storage under /mpac/sdicks02/jobs/).
FORBIDDEN_PREFIXES = {"127x03": (), "127x04": ("/mpac/sdicks02/jobs/",)}
PHASES = (("reporting", "k4s-confirm-reporting-r1"),
          ("replacement-r1", "k4s-confirm-replacement-r1"),
          ("replacement-r2", "k4s-confirm-replacement-r2"),
          ("replacement-r3", "k4s-confirm-replacement-r3"),
          ("replacement-r4", "k4s-confirm-replacement-r4"))
META = ("launch.json", "supervisor-exit.json")
SOURCES = ("mhz.jsonl", "census.jsonl")
NAMES = META + SOURCES
# Committed phase-meta SHA-256 (run-r1/phase-meta/<host>-<phase>/{launch.json, supervisor-exit.json}).
EXPECTED = {
    ("127x03", "reporting"): ("116f1ed5f998649ba950fbde08846b47b052294acbbb6432b4a04b2a324e0159",
                              "88debddf7bf33c1b0bc2f14002339c87072be956398d90bfb727c2d0c36a1033"),
    ("127x03", "replacement-r1"): ("b864703e102d9dea314e1b332ee1415518f90153a0a633a9c2b1b0ac0ca1a70b",
                                   "bffde5d4008b2a47fc867e690f18d6ae087fd09e58464816f9a2fa60dddb5efa"),
    ("127x03", "replacement-r2"): ("1d917968d9875f89c2024ba173fb1a16fcdaf8b7a5f6a5504fe3bc7b6b9df299",
                                   "834fc2475b5a071d1564076b77403d83b983dbdf2026f4ccccf7df84012c3e3f"),
    ("127x03", "replacement-r3"): ("6c49a6679c1c654879a071c44a86cda952fb40bc1722af43e3b2c22914b13efb",
                                   "cccb86839ef970ae6e9bda6a8bb3b10451aa73baad8ac0978750f7c654688616"),
    ("127x03", "replacement-r4"): ("e8f72fb483e73b5bcbb78b4aa129e5b31c61b4e2f0c45fec67d6b9637f65f2e6",
                                   "c9066d63cd1aa73de74d2214498dc7543d2d863282d3593887aec2f65642027c"),
    ("127x04", "reporting"): ("7cd6b140551d8f1d66858d98b3cf2d74b14339e7d334e6b4fc3650a3fa383c48",
                              "c0a935f6cd1ecf022bf197dc3e88604769491bb461973bcd3c106e393aa71084"),
    ("127x04", "replacement-r1"): ("420f7ec1076885ddb0c0211a39bcfa0d0ced72b9c9c3856c382eef1f4f727f0e",
                                   "c11ae500e34504872095ba1d2b50d836546923c14641684d6ab97f635e4114b2"),
    ("127x04", "replacement-r2"): ("ea88e4d5c11590390875bfc8c044f5027950349e70bdd3f5b3eef82f3683cf32",
                                   "37aafa6a128757e80082d0fbad6a1e518de88a277e342538cb2f33dbbdfc8e8b"),
    ("127x04", "replacement-r3"): ("9cd6bc37da5638dbc95a065cfd47ad467980d9b348bef2d7a711f8f9a7b4264e",
                                   "91475244cc702e33dbf0a4fd20635dcb5b2fa435b21361094263723fc4cd414c"),
    ("127x04", "replacement-r4"): ("38730d445b2a8095cbad8b393f709fbf5e0a79eb0267d6eb69c9875c2ee6c69a",
                                   "21269aa00b3340f8b75a02de5526c5f20d525d3af27a2b1c0ac6d56f8fc47cb9"),
}
SSH_OPTIONS = ("-T", "-o", "BatchMode=yes", "-o", "ControlMaster=no", "-o", "ControlPath=none",
               "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=15",
               "-o", "ServerAliveCountMax=4", "-o", "ClearAllForwardings=yes", "-o", "RequestTTY=no")
SAFE_PATH = re.compile(r"/mpac/sdicks02/[A-Za-z0-9._/-]+")
SHA = re.compile(r"[0-9a-f]{64}")
CHUNK = 1 << 20


class Refusal(RuntimeError):
    """Fail-closed refusal (never an assert: the checks hold under python -O)."""


def require(condition, message):
    if not condition:
        raise Refusal(message)


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- committed expectations (local git, read only)

def git_blob(repository, commit, rel):
    result = subprocess.run(["git", "-C", str(repository), "show", f"{commit}:{rel}"], capture_output=True)
    require(result.returncode == 0, f"not committed at {commit}: {rel}")
    return result.stdout


def phase_dir(host, namespace, phase):
    path = f"{JOB_ROOTS[host]}/{namespace}/{phase}"
    require(SAFE_PATH.fullmatch(path) is not None and ".." not in path.split("/"), "unsafe phase path: " + path)
    require(not any(path.startswith(p) for p in FORBIDDEN_PREFIXES[host]), f"forbidden path on {host}: {path}")
    return path


def expectations(repository, commit):
    """The plan of record from committed bytes: namespaces, phase-meta SHAs (== constants == completion exits)."""
    require(re.fullmatch(r"[0-9a-f]{40}", commit) is not None, "--commit must be a full 40-hex commit")
    resolved = subprocess.run(["git", "-C", str(repository), "rev-parse", "--verify", commit + "^{commit}"],
                              capture_output=True, text=True)
    require(resolved.returncode == 0 and resolved.stdout.strip() == commit, "commit not in repository: " + commit)
    history = json.loads(git_blob(repository, commit, HISTORY))
    namespaces = {row["phase"]: row["namespace"] for row in history}
    require(len(namespaces) == len(history) == len(PHASES) and namespaces == dict(PHASES),
            "committed rounds/history.json differs from the copier's phase -> namespace table")
    raw = git_blob(repository, commit, COMPLETION)
    require(sha_bytes(raw) == COMPLETION_SHA256, "completion-v2 SHA differs from the completion of record")
    completion = json.loads(raw)
    require(completion.get("counted_host_phases") == {h: [p for p, _ in PHASES] for h in HOSTS},
            "completion counted_host_phases differs from the copier's 10 host/phase pairs")
    plan = []
    for host in HOSTS:
        for phase, namespace in PHASES:
            meta = f"{STUDY}/run-r1/phase-meta/{host}-{phase}"
            launch = sha_bytes(git_blob(repository, commit, meta + "/launch.json"))
            exit_ = sha_bytes(git_blob(repository, commit, meta + "/supervisor-exit.json"))
            require((launch, exit_) == EXPECTED[(host, phase)], f"committed phase-meta SHA differs from the table: {meta}")
            require(completion["supervisor_exits"][f"{host}/{phase}"]["sha256"] == exit_,
                    f"completion supervisor_exits SHA differs from phase-meta: {host}/{phase}")
            directory = phase_dir(host, namespace, phase)
            plan.append(dict(host=host, phase=phase, namespace=namespace, directory=directory,
                             committed={"launch.json": dict(sha256=launch, repository_path=meta + "/launch.json"),
                                        "supervisor-exit.json": dict(sha256=exit_,
                                                                     repository_path=meta + "/supervisor-exit.json")}))
    return plan


# ---------------------------------------------------------------- remote commands (exact literal paths only)

def host_paths(plan, host, names):
    out = []
    for entry in plan:
        if entry["host"] == host:
            for name in names:
                path = entry["directory"] + "/" + name
                require(SAFE_PATH.fullmatch(path) is not None, "unsafe path: " + path)
                out.append((entry, name, path))
    return out


def inspect_command(paths):
    quoted = " ".join(shlex.quote(p) for _, _, p in paths)
    return ("set -eu; LC_ALL=C; export LC_ALL; "
            f"nice -n 19 stat -c '%F|%s|%n' -- {quoted}; nice -n 19 sha256sum -- {quoted}")


def copy_command(paths):
    return "set -eu; exec nice -n 19 cat -- " + " ".join(shlex.quote(p) for _, _, p in paths)


def ssh_argv(ssh, host, command):
    require(host in HOSTS, "unknown host: " + host)
    return [ssh, *SSH_OPTIONS, "--", host, command]


class Session:
    def __init__(self, ssh, log):
        self.ssh, self.log, self.logins = ssh, log, []

    def run(self, host, command, label, *, stdout=None, timeout=900):
        argv = ssh_argv(self.ssh, host, command)
        self.logins.append(dict(label=label, host=host, started_utc=utc(), argv=argv))
        self.log(f"[{utc()}] ssh {label} {host}")
        try:
            result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=stdout or subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise Refusal(f"ssh {label} {host} timed out after {timeout}s") from None
        self.logins[-1].update(finished_utc=utc(), returncode=result.returncode)
        require(result.returncode == 0, f"ssh {label} {host} failed rc={result.returncode}: "
                + result.stderr.decode(errors="replace")[-400:])
        return result


def parse_inspection(stdout, paths, label):
    lines = stdout.decode().splitlines()
    n = len(paths)
    require(len(lines) == 2 * n, f"{label}: unexpected stat/sha256sum output ({len(lines)} lines, want {2 * n})")
    out = {}
    for (entry, name, path), stat_line, sha_line in zip(paths, lines[:n], lines[n:]):
        kind, size, shown = (stat_line.split("|", 2) + ["", ""])[:3]
        require(shown == path and kind == "regular file" and size.isdigit(),
                f"{label}: {path} is not a regular file (stat: {stat_line!r})")
        digest, _, shown = sha_line.partition("  ")
        require(shown == path and SHA.fullmatch(digest) is not None, f"{label}: bad sha256sum line {sha_line!r}")
        out[path] = dict(entry=entry, name=name, size=int(size), sha256=digest)
    return out


def check_inspection(found, label):
    """Step 1 then step 2, per phase, in order."""
    for path, row in found.items():
        if row["name"] in META:
            want = row["entry"]["committed"][row["name"]]["sha256"]
            require(row["sha256"] == want, f"{label}: REFUSE on-host {path} SHA {row['sha256']} != committed {want}")
    for path, row in found.items():
        if row["name"] in SOURCES:
            require(row["size"] <= MAX_BYTES, f"{label}: REFUSE {path} is {row['size']} bytes > 95 MiB ({MAX_BYTES})")
            require(row["size"] > 0, f"{label}: REFUSE {path} is empty")


# ---------------------------------------------------------------- local writes

def split_stream(stream_path, pieces, dest):
    """Split the cat stream by the login-P sizes; every piece must hash to its login-P SHA."""
    total = sum(row["size"] for _, row in pieces)
    require(stream_path.stat().st_size == total, f"copy stream length {stream_path.stat().st_size} != expected {total}")
    written = []
    with open(stream_path, "rb") as source:
        for path, row in pieces:
            entry = row["entry"]
            local = dest / entry["host"] / entry["phase"] / row["name"]
            local.parent.mkdir(parents=True, exist_ok=True)
            h, left = hashlib.sha256(), row["size"]
            with open(local, "xb") as out:
                while left:
                    chunk = source.read(min(CHUNK, left))
                    require(chunk, "copy stream ended early")
                    h.update(chunk)
                    out.write(chunk)
                    left -= len(chunk)
            require(h.hexdigest() == row["sha256"], f"local copy SHA differs from on-host SHA: {path}")
            require(sha_file(local) == row["sha256"] and local.stat().st_size == row["size"],
                    f"local file re-read differs: {local}")
            written.append((path, local))
    return written


def run(a, log=print):
    started = utc()
    plan = expectations(a.repository, a.commit)
    inspections = {h: host_paths(plan, h, NAMES) for h in HOSTS}
    copies = {h: host_paths(plan, h, SOURCES) for h in HOSTS}
    if a.dry_run:
        log(json.dumps(dict(mode="dry-run", commit=a.commit, logins=6, max_bytes=MAX_BYTES,
                            expected={f"{e['host']}/{e['phase']}": {k: v["sha256"] for k, v in e["committed"].items()}
                                      for e in plan}), indent=1))
        for label, host, command in ([("P", h, inspect_command(inspections[h])) for h in HOSTS]
                                     + [x for h in HOSTS for x in (("C", h, copy_command(copies[h])),
                                                                  ("V", h, inspect_command(inspections[h])))]):
            log(f"# login {label} {host}")
            log(shlex.join(ssh_argv(a.ssh, host, command)))
        return None
    require(a.outside_end_window, "live run requires --outside-end-window '<coordinator GO / window reference>'")
    dest = Path(a.dest)
    require(not dest.exists() and not dest.is_symlink(), "--dest must not exist: " + str(dest))
    ssh = shutil.which(a.ssh)
    require(ssh is not None, "ssh not found: " + a.ssh)
    session = Session(ssh, log)
    try:
        first = {}
        for host in HOSTS:                                    # every check on both hosts before any copy
            result = session.run(host, inspect_command(inspections[host]), "P")
            first[host] = parse_inspection(result.stdout, inspections[host], f"P {host}")
            check_inspection(first[host], f"P {host}")
        dest.mkdir(parents=True)
        files = []
        for host in HOSTS:
            stream = dest / f".s1-stream-{host}.partial"
            with open(stream, "xb") as out:
                session.run(host, copy_command(copies[host]), "C", stdout=out, timeout=3600)
            pieces = [(p, first[host][p]) for _, _, p in copies[host]]
            written = split_stream(stream, pieces, dest)
            stream.unlink()
            result = session.run(host, inspect_command(inspections[host]), "V")
            again = parse_inspection(result.stdout, inspections[host], f"V {host}")
            for path, row in first[host].items():
                require((again[path]["size"], again[path]["sha256"]) == (row["size"], row["sha256"]),
                        f"V {host}: on-host file changed during the copy: {path}")
            for path, local in written:
                row = first[host][path]
                files.append(dict(host=host, phase=row["entry"]["phase"], name=row["name"], remote_path=path,
                                  remote_size=row["size"], remote_sha256_before=row["sha256"],
                                  remote_sha256_after=again[path]["sha256"],
                                  local_path=local.relative_to(dest).as_posix(), local_size=local.stat().st_size,
                                  local_sha256=sha_file(local)))
        meta = [dict(host=r["entry"]["host"], phase=r["entry"]["phase"], name=r["name"], remote_path=p,
                     remote_size=r["size"], remote_sha256=r["sha256"],
                     committed_sha256=r["entry"]["committed"][r["name"]]["sha256"],
                     committed_repository_path=r["entry"]["committed"][r["name"]]["repository_path"])
                for host in HOSTS for p, r in first[host].items() if r["name"] in META]
        on_disk = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
        require(on_disk == sorted(f["local_path"] for f in files) and len(files) == 2 * len(plan),
                "destination holds unexpected files: " + ",".join(on_disk[:5]))
        manifest = dict(schema=SCHEMA, status="copied", started_utc=started, finished_utc=utc(),
                        outside_end_window=a.outside_end_window, repository_commit=a.commit,
                        script_sha256=sha_file(Path(__file__).resolve()), ssh=ssh, ssh_logins=len(session.logins),
                        logins=session.logins, max_bytes=MAX_BYTES, files=files, meta=meta)
        with open(dest / "s1-copy-manifest.json", "x") as out:
            out.write(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
        log(f"S1 OK: {len(files)} files, {len(session.logins)} ssh logins, manifest "
            f"{sha_file(dest / 's1-copy-manifest.json')}")
        return manifest
    except Exception as error:
        if dest.is_dir():
            with open(dest / "S1-REFUSAL.json", "w") as out:
                out.write(json.dumps(dict(schema=SCHEMA, status="refused", error=str(error), utc=utc(),
                                          logins=session.logins), indent=1) + "\n")
        raise


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repository", type=Path, required=True, help="local clasher checkout (read with git show only)")
    ap.add_argument("--commit", required=True, help="full commit holding phase-meta, history.json and completion-v2")
    ap.add_argument("--dest", type=Path, help="new local staging root (must not exist)")
    ap.add_argument("--ssh", default="ssh")
    ap.add_argument("--outside-end-window", default="", help="required for a live run: GO/window reference")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if not a.dry_run and a.dest is None:
        ap.error("--dest is required unless --dry-run")
    try:
        run(a)
    except Refusal as error:
        print("S1 REFUSED: " + str(error), file=sys.stderr)
        return 2
    except Exception as error:                                # fail closed on anything unexpected
        print(f"S1 FAILED: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
