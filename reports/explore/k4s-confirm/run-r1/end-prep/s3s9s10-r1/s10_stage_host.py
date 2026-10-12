#!/usr/bin/env python3
"""S10 (PREREG-K4S END, A2 staging): ship END inputs from 127x05 to ONE host. CANDIDATE: host-touching; Sol review
and a coordinator A2 GO (+ T1 owner confirmation for the T1 inputs) before any live run. Never run inside an END
timing window or a preflight measurement on any host.

Components (each optional; at least one):
  --runtime S9OUT    S9 runtime tree (re-verified locally)        -> <base>/runtime-<commit12>/
  --inputs           Q6 T1 background inputs from 05 only         -> <base>/t1-background-inputs/
                     (states.pkl 0addf7c0, states-rows.json bcd30777, states-rows.bin 8cc2f611; byte copies)
  --bundle DIR       S4 fleet-reference bundle(s) (repeatable)    -> <base>/bundles/<basename>/
  --guard-job S3OUT  S3 per-attempt guard job (re-verified)       -> its Q4 target (k4s-end-guard-r1-rdRR-aNN)
with <base> = /mpac/sdicks02/jobs/clasher/k4s-confirm-end-r1 (03) or /mpac/sdicks02/jobs-k4s/k4s-confirm-end-r1 (04),
the END bases of the S5/S6/S7 candidates. Every remote path is computed from these constants and checked against
the forbidden namespaces (T1 trees, K4S reporting jobs, repos/clasher-v4-cache, 04's /mpac/sdicks02/jobs/clasher).

Logins: exactly 3, each `ssh -T -o BatchMode=yes -o ControlMaster=no -o ControlPath=none ...`:
  P   inspect: hostname, every target and its .partial absent, parents are directories, free space, git/tar present.
  TV  transfer + verify: one tar stream (05 hashes every byte while streaming and refuses on any difference) is
      extracted under `nice -n 19` into NEW `<target>.partial` directories only (`--keep-old-files`); the same login
      then lists every staged entry and sha256sums every staged file, and for the guard job runs `git cat-file -e`
      for the four binding commits and `git show <c>:<p> | sha256sum` for the four seed files.
  F   finalize (only if 05 found every on-host size/SHA/listing equal to the local manifest): read-only modes
      (runtime/inputs/bundles a-w; guard job: the 3-4 job files and the 4 seed files 0444, directories writable),
      `mv -T` each .partial into place, then re-check hostname, modes, and the guard commits.
Nothing is ever deleted on a host. A refused run leaves `.partial` directories that need a separately authorized
cleanup (the exact paths are printed and recorded). --dry-run runs every local check and prints the three remote
commands; it makes no ssh call and writes nothing.
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import end_prep_common as C                                           # noqa: E402
import s3_guard_job as S3                                             # noqa: E402
import s9_end_runtime as S9                                           # noqa: E402

for _module in (C, S3, S9):
    if Path(_module.__file__).resolve().parent != HERE:
        raise SystemExit("sibling module imported from outside " + str(HERE))

SCHEMA = "clasher.k4s.end-staging.v1"
HOSTS = ("127x03", "127x04")
END_BASES = {"127x03": "/mpac/sdicks02/jobs/clasher/k4s-confirm-end-r1",
             "127x04": "/mpac/sdicks02/jobs-k4s/k4s-confirm-end-r1"}
EXTRACT_ROOT = "/mpac/sdicks02"
FORBIDDEN = {"127x03": ("/mpac/sdicks02/jobs/clasher/t1-", "/mpac/sdicks02/jobs/clasher/k4s-confirm-reporting",
                        "/mpac/sdicks02/jobs/clasher/k4s-confirm-replacement", "/mpac/sdicks02/jobs/clasher/k4s-confirm-r1",
                        "/mpac/sdicks02/repos/"),
             "127x04": ("/mpac/sdicks02/jobs/", "/mpac/sdicks02/jobs-k4s/k4s-confirm-reporting",
                        "/mpac/sdicks02/jobs-k4s/k4s-confirm-replacement", "/mpac/sdicks02/jobs-k4s/k4s-confirm-r1",
                        "/mpac/sdicks02/jobs-k4s/k4s-prep", "/mpac/sdicks02/repos/")}
INPUTS_SOURCE = "/mpac/sdicks02/jobs/clasher/t1-20261010-r1/end-a5-pool-context-20261012-r1/bundle"
INPUTS = {"states.pkl": ("0addf7c0176c358e19f816a1079208eea370a2764d43a44fc9c1993811ead6f1", 11649583550),
          "states-rows.json": ("bcd307770b70394878f7da17a97e4a1baa10f6efd7ea06d6b4240901dc0336e5", 353160),
          "states-rows.bin": ("8cc2f611e867dc3891cdab643365193be685057b802cf73847c7fd6c91d6a1cb", 11651404503)}
BUNDLE_UNPINNED = ("tiers-pins.json", "tiers-pins.sha256", "assembly-receipt.json")
# Production identities every shipped bundle must pin (frozen models; Q6 state bytes).
PRODUCTION_PINS = {"v1.pt": "d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed",
                   "R3a.pt": "37509a4331bd02ae110b76e1825a2adb23fa78e0e70188e199b6ef90d19ade85",
                   "R3a-calibration.json": "e300353346983e888d896b20412d4075496a6f14ef3625cefc7eeadacec5e414",
                   **{name: sha for name, (sha, _) in INPUTS.items()}}
HEADROOM = 50 * 1024 ** 3
SSH_OPTIONS = ("-T", "-o", "BatchMode=yes", "-o", "ControlMaster=no", "-o", "ControlPath=none",
               "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=15",
               "-o", "ServerAliveCountMax=8", "-o", "ClearAllForwardings=yes", "-o", "RequestTTY=no",
               "-o", "Compression=no")
SAFE_PATH = re.compile(r"/mpac/sdicks02/[A-Za-z0-9._/-]+")
SAFE_NAME = re.compile(r"[A-Za-z0-9._-]+")
CHUNK = 1 << 20


Refusal, require = C.Refusal, C.require


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


sha_file = C.sha_file                                                 # O_NOFOLLOW, regular, optional size cap
canonical_sha = S9.canonical_sha


def check_remote(host, path):
    """Every remote path S10 names: absolute, normal, safe characters, inside the declared K4S namespaces only."""
    require(isinstance(path, str) and SAFE_PATH.fullmatch(path) is not None and os.path.normpath(path) == path
            and ".." not in path.split("/"), "unsafe remote path: " + repr(path))
    require(not any(path.startswith(p) for p in FORBIDDEN[host]), f"forbidden remote path on {host}: {path}")
    base, guard_parent = END_BASES[host], S3.GUARD_PARENTS[host]
    ok = path == base or path.startswith(base + "/")
    if not ok and path.startswith(guard_parent + "/"):              # a Q4 guard job (or .partial) or inside one
        first = path[len(guard_parent) + 1:].split("/")[0]
        ok = S3.JOB_NAME.fullmatch(first.removesuffix(".partial")) is not None
    require(ok, f"remote path outside the K4S END namespaces on {host}: {path}")
    return path


def ancestors(path):
    """Every existing-or-created directory above a remote target, from /mpac down (each must be a real dir)."""
    parts = path.split("/")[1:-1]
    return ["/" + "/".join(parts[:i]) for i in range(1, len(parts) + 1)]


def local_root(path, label):
    """A local input root: absolute, normal, an existing directory with no symlinked ancestor."""
    text = str(path)
    require(os.path.isabs(text) and os.path.normpath(text) == text and os.path.isdir(text)
            and os.path.realpath(text) == text, f"{label} must be a real directory path (no symlink): {text}")
    return Path(text)


# ---------------------------------------------------------------- local components (verified before shipping)

class Component:
    def __init__(self, kind, local, remote, entries, extra=None):
        self.kind, self.local, self.remote, self.entries = kind, Path(local), remote, entries
        self.partial = remote + ".partial"
        self.extra = extra or {}
        self.files = {e["path"]: e for e in entries if e["type"] == "f"}
        self.dirs = sorted(e["path"] for e in entries if e["type"] == "d")

    def summary(self):
        return dict(kind=self.kind, local=str(self.local), remote=self.remote, files=len(self.files),
                    dirs=len(self.dirs), bytes=sum(f["size"] for f in self.files.values()),
                    inventory_sha256=canonical_sha(sorted(self.entries, key=lambda e: e["path"])), **self.extra)


def walk_entries(root, allow_exec=True):
    """Every dir/file under root (symlinks and specials refused), with size, SHA and an exec flag."""
    entries = []
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in dirnames + sorted(filenames):
            path = os.path.join(directory, name)
            rel = os.path.relpath(path, root)
            require("\n" not in rel and "\\" not in rel, "unsafe local name: " + repr(rel))
            info = os.lstat(path)
            require(not stat.S_ISLNK(info.st_mode), "symlink in a staged tree: " + path)
            if stat.S_ISDIR(info.st_mode):
                entries.append(dict(path=rel, type="d"))
            else:
                require(stat.S_ISREG(info.st_mode), "non-regular file in a staged tree: " + path)
                entries.append(dict(path=rel, type="f", size=info.st_size, sha256=sha_file(path),
                                    executable=allow_exec and bool(info.st_mode & 0o100)))
    return entries


def runtime_component(host, s9out, log):
    local_root(s9out, "--runtime")
    manifest = S9.verify(argparse.Namespace(out=s9out, frozen=False, python=sys.executable), log)
    root = Path(s9out) / manifest["runtime_dir"]
    entries = [dict(path=d, type="d") for d in manifest["inventory"]["dirs"]]
    entries += [dict(path=p, type="f", size=f["size"], sha256=f["sha256"], executable=f["executable"])
                for p, f in manifest["inventory"]["files"].items()]
    remote = check_remote(host, f"{END_BASES[host]}/runtime-{manifest['commit'][:12]}")
    return Component("runtime", root, remote, entries,
                     dict(commit=manifest["commit"], runtime_files_sha256=manifest["runtime_files_sha256"],
                          measurement_files_sha256=manifest["measurement_files_sha256"],
                          runtime_manifest_sha256=sha_file(Path(s9out) / "runtime-manifest.json"))), manifest


def inputs_component(host, source, log):
    root = local_root(source, "--inputs-source")
    entries = []
    for name, (expected, size) in sorted(INPUTS.items()):
        path = root / name
        log(f"hashing {path} ...")
        require(sha_file(path, size) == expected and os.lstat(path).st_size == size,     # O_NOFOLLOW, bounded
                f"Q6 input SHA/size differs: {name}")
        entries.append(dict(path=name, type="f", size=size, sha256=expected, executable=False))
    remote = check_remote(host, f"{END_BASES[host]}/t1-background-inputs")
    return Component("inputs", root, remote, entries, dict(source=str(root)))


def bundle_component(host, directory, runtime_manifest, guard_manifest):
    directory = local_root(directory, "--bundle")
    name = directory.name
    require(SAFE_NAME.fullmatch(name) is not None and not name.endswith(".partial"), "bad bundle name: " + name)
    raw = C.read_bounded(directory / "tiers-pins.json", 64 << 20)
    manifest = json.loads(raw)
    side = C.read_bounded(directory / "tiers-pins.sha256", 4096).decode()
    require(side == f"{S9.sha_bytes(raw)}  tiers-pins.json\n", "tiers-pins.sha256 does not match tiers-pins.json")
    profile = manifest.get("reference_load_profile", {})
    require(manifest.get("profile") == "fleet-reference" and profile.get("host") == host,
            f"bundle {name} is not a fleet-reference bundle for {host}")
    S3.check_target(host, profile["guard"]["job"])
    entries = walk_entries(directory, allow_exec=False)
    files = {e["path"]: e for e in entries if e["type"] == "f"}
    pinned = manifest["files"]
    require(set(files) == set(pinned) | (set(BUNDLE_UNPINNED) & set(files)) and "tiers-pins.json" in files,
            f"bundle {name} holds unpinned or lacks pinned files: "
            + repr(sorted(set(files) ^ (set(pinned) | set(BUNDLE_UNPINNED)))[:6]))
    for rel, expected in pinned.items():
        require(files[rel]["sha256"] == expected, f"bundle {name}: {rel} differs from its pin")
    for rel, expected in PRODUCTION_PINS.items():
        require(pinned.get(rel) == expected, f"bundle {name}: {rel} is not the production identity {expected[:8]}")
    want = set(S3.S1B.NAMES[host])
    require(set(profile["guard"].get("admissions", {})) == want,
            f"bundle {name}: guard admissions must be exactly {sorted(want)} on {host}")
    checks = dict(guard_job=profile["guard"]["job"], tiers_pins_sha256=S9.sha_bytes(raw))
    if runtime_manifest is not None:
        require(S9.canonical_sha(manifest["runtime_files"]) == runtime_manifest["runtime_files_sha256"]
                and S9.canonical_sha(manifest["measurement_files"]) == runtime_manifest["measurement_files_sha256"],
                f"bundle {name} was not built from the staged runtime (runtime/measurement canonical SHA)")
        checks["runtime_consistent"] = True
    if guard_manifest is not None and profile["guard"]["job"] == guard_manifest["target_job"]:
        guard = profile["guard"]
        pairs = [(guard["freeze"], S3.FROZEN_T1_SHA)]
        pairs += [(guard["admissions"][n], guard_manifest["admissions"][n]["sha256"]) for n in guard["admissions"]]
        require(set(guard["admissions"]) == set(guard_manifest["admissions"]), "bundle/guard-job admission names differ")
        seeds = {b["path"]: b["sha256"] for b in guard_manifest["bindings"]}
        require(set(guard["seed_inputs"]) == set(seeds), "bundle/guard-job seed inputs differ")
        pairs += [(guard["seed_inputs"][p], s) for p, s in seeds.items()]
        for rel, expected in pairs:
            require(pinned.get(rel) == expected, f"bundle {name}: {rel} differs from the guard job's bytes")
        checks["guard_job_bytes_equal"] = True
    remote = check_remote(host, f"{END_BASES[host]}/bundles/{name}")
    return Component("bundle", directory, remote, entries, checks)


def guard_component(host, s3out, log):
    local_root(s3out, "--guard-job")
    manifest = S3.verify(s3out, log)
    require(manifest["host"] == host, "guard job was built for " + manifest["host"])
    remote = check_remote(host, S3.check_target(host, manifest["target_job"]))
    entries = []
    for row in manifest["inventory"]:
        if row["type"] == "d":
            entries.append(dict(path=row["path"], type="d"))
        else:
            entries.append(dict(path=row["path"], type="f", size=row["size"], sha256=row["sha256"],
                                executable=bool(int(row["mode"], 8) & 0o100)))
    read_only = ["FROZEN-T1.json"] + sorted(manifest["admissions"]) + ["repo/" + b["path"] for b in manifest["bindings"]]
    return Component("guard-job", Path(s3out) / manifest["job_name"], remote, entries,
                     dict(read_only=read_only, bindings=manifest["bindings"],
                          guard_manifest_sha256=sha_file(Path(s3out) / "guard-job-manifest.json"))), manifest


# ---------------------------------------------------------------- remote scripts (generated; literal paths only)

def q(path):
    return shlex.quote(path)


def p_script(host, components):
    base = END_BASES[host]
    probes = sorted({c.remote for c in components} | {c.partial for c in components})
    lines = ["set -eu", "export LC_ALL=C", "hostname"]
    lines += [f"if test -e {q(p)} || test -L {q(p)}; then echo 'EXISTS|{p}'; else echo 'ABSENT|{p}'; fi" for p in probes]
    parents = sorted({os.path.dirname(base), *(S3.GUARD_PARENTS[host] for c in components if c.kind == "guard-job")})
    lines += [f"stat -c 'PARENT|%F|%U|%n' -- {q(p)}" for p in parents]
    links = sorted({a for c in components for a in ancestors(c.remote)})
    lines += [f"if test -L {q(a)}; then echo 'LINK|{a}'; fi" for a in links]
    lines += [f"if test -d {q(d)}; then echo 'DIR|present|{d}'; else echo 'DIR|absent|{d}'; fi"
              for d in (base, base + "/bundles")]
    lines += ["df -P -B1 /mpac/sdicks02 | tail -n 1 | awk '{print \"DF|\" $4}'",
              "echo \"GIT|$(git --version)\"", "if command -v tar sha256sum find xargs sort >/dev/null; then echo 'TOOLS|ok'; fi",
              "echo \"WHO|$(who | wc -l)\""]
    return "\n".join(lines)


def tv_script(host, components):
    base = END_BASES[host]
    lines = ["set -euo pipefail", "export LC_ALL=C", "umask 022", f'test "$(hostname)" = {host}']
    # One command per line: under `set -e` a failing test inside an `a && b` list would NOT stop the script.
    lines += [f"test ! -e {q(p)}\ntest ! -L {q(p)}" for c in components for p in (c.remote, c.partial)]
    created = [d for d in (base, base + "/bundles") if any(c.remote.startswith(d + "/") for c in components)]
    for directory in sorted({a for c in components for a in ancestors(c.remote)}):
        if directory in created:
            lines.append(f"test -d {q(directory)} || mkdir -- {q(directory)}")
        lines += [f"test -d {q(directory)}", f"test ! -L {q(directory)}"]     # a real directory, never an alias
    lines.append(f"nice -n 19 tar -x -f - -C {EXTRACT_ROOT} --no-same-owner --keep-old-files")
    for i, c in enumerate(components):
        lines.append(f"echo '@@LIST|{i}'")
        lines.append(f"( cd -- {q(c.partial)} && find . -mindepth 1 -printf '%y|%m|%s|%P\\n' | sort )")
        lines.append(f"echo '@@SHA|{i}'")
        lines.append(f"( cd -- {q(c.partial)} && find . -type f -print0 | sort -z | xargs -0 -r nice -n 19 sha256sum -- )")
        if c.kind == "guard-job":
            lines += git_checks(i, c.partial)
    lines.append("echo '@@END'")
    return "\n".join(lines)


def git_checks(i, job):
    repo = job + "/repo"
    lines = [f"echo '@@GIT|{i}'"]
    for commit in S3.Q3_COMMITS + tuple(b["commit"] for b in S3.JOINS):
        lines.append(f"git -C {q(repo)} cat-file -e {commit}^{{commit}} && echo 'CATFILE|{commit}|0'")
    for b in S3.BINDINGS:
        lines.append(f"printf 'SHOW|%s|' {q(b['path'])}; git -C {q(repo)} show {q(b['commit'] + ':' + b['path'])} | sha256sum")
    return lines


def f_script(host, components):
    lines = ["set -euo pipefail", "export LC_ALL=C", f'test "$(hostname)" = {host}']
    for c in components:
        lines += [f"test -d {q(c.partial)}", f"test ! -L {q(c.partial)}", f"test ! -e {q(c.remote)}"]
    for c in components:
        if c.kind == "guard-job":
            lines.append("chmod 0444 -- " + " ".join(q(c.partial + "/" + p) for p in c.extra["read_only"]))
        else:
            lines.append(f"chmod -R a-w -- {q(c.partial)}")
        lines.append(f"mv -T -- {q(c.partial)} {q(c.remote)}")
        lines += [f"test -d {q(c.remote)}", f"test ! -e {q(c.partial)}", f"stat -c 'FINAL|%F|%a|%n' -- {q(c.remote)}"]
        # An assignment carries the substitution's status (set -e + pipefail); `echo "$(...)"` would hide a failure.
        depth = "-maxdepth 1 -type f " if c.kind == "guard-job" else ""
        lines += [f"n=$(find {q(c.remote)} {depth}-perm /222 | wc -l)", f"echo \"WRITABLE|{c.remote}|$n\""]
        if c.kind == "guard-job":
            lines += [line.replace("'@@GIT|", "'@@FGIT|") for line in git_checks(0, c.remote)]
    lines.append(f'test "$(hostname)" = {host} && echo DONE')
    return "\n".join(lines)


def ssh_argv(ssh, host, script):
    require(host in HOSTS, "unknown host " + host)
    return [ssh, *SSH_OPTIONS, "--", host, "bash -c " + shlex.quote(script)]


# ---------------------------------------------------------------- parsing remote output

def parse_p(host, out, components, need_bytes):
    lines = out.decode().splitlines()
    require(lines and lines[0] == host, f"P: hostname {lines[:1]} != {host}")
    rows = {}
    for line in lines[1:]:
        tag, _, rest = line.partition("|")
        rows.setdefault(tag, []).append(rest)
    present = [r for r in rows.get("EXISTS", [])]
    require(not present, "P: target or .partial already exists on the host: " + ", ".join(present))
    require(not rows.get("LINK"), "P: a target ancestor is a symlink on the host: " + ", ".join(rows.get("LINK", [])))
    for row in rows.get("PARENT", []):
        kind, owner, path = row.split("|", 2)
        require(kind == "directory" and owner == "sdicks02", f"P: {path} is not an sdicks02 directory ({kind}/{owner})")
    free = int(rows["DF"][0])
    require(free >= need_bytes + HEADROOM, f"P: {free} bytes free on /mpac < {need_bytes} + 50 GiB headroom")
    require(rows.get("TOOLS") == ["ok"] and rows.get("GIT", [""])[0].startswith("git version"), "P: tools missing")
    return dict(free_bytes=free, git=rows["GIT"][0], who=rows.get("WHO", ["?"])[0],
                dirs={r.split("|", 1)[1]: r.split("|", 1)[0] for r in rows.get("DIR", [])})


def split_sections(text):
    sections, key = {}, None
    for line in text.splitlines():
        if line.startswith("@@"):
            key = line[2:]
            sections[key] = []
        elif key is not None:
            sections[key].append(line)
    return sections


def check_tv(out, components):
    sections = split_sections(out.decode())
    require("END" in sections, "TV: remote verification did not complete")
    for i, c in enumerate(components):
        listing = {}
        for line in sections.get(f"LIST|{i}", []):
            kind, mode, size, rel = line.split("|", 3)
            listing[rel] = (kind, int(size))
        expected = {e["path"]: ("d" if e["type"] == "d" else "f") for e in c.entries}
        require({k: v[0] for k, v in listing.items()} == expected,
                f"TV {c.kind}: on-host listing differs: " + repr(sorted(set(listing) ^ set(expected))[:6]))
        for rel, f in c.files.items():
            require(listing[rel][1] == f["size"], f"TV {c.kind}: size differs on host: {rel}")
        sums = {}
        for line in sections.get(f"SHA|{i}", []):
            digest, _, rel = line.partition("  ")
            require(rel.startswith("./"), "TV: unexpected sha256sum line " + repr(line))
            sums[rel[2:]] = digest
        require(sums == {rel: f["sha256"] for rel, f in c.files.items()},
                f"TV {c.kind}: on-host SHA differs: "
                + repr(sorted(r for r in set(sums) | set(c.files) if sums.get(r) != c.files.get(r, {}).get("sha256"))[:6]))
        if c.kind == "guard-job":
            check_git(sections.get(f"GIT|{i}", []), "TV")
    return {c.kind + ":" + c.remote: dict(files=len(c.files), on_host_sha_equal=True) for c in components}


def check_git(lines, label):
    want = [f"CATFILE|{c}|0" for c in S3.Q3_COMMITS + tuple(b["commit"] for b in S3.JOINS)]
    want += [f"SHOW|{b['path']}|{b['sha256']}  -" for b in S3.BINDINGS]
    require(lines == want, f"{label}: guard repo git checks differ: {lines!r}")


def check_f(host, out, components):
    text = out.decode()
    lines = text.splitlines()
    require(lines and lines[-1] == "DONE", "F: finalize did not complete")
    for c in components:
        mode = "755" if c.kind == "guard-job" else "555"           # guard job dir stays writable (the guard writes)
        require(f"FINAL|directory|{mode}|{c.remote}" in lines, f"F: {c.remote} not in place with mode {mode}")
        require(f"WRITABLE|{c.remote}|0" in lines, f"F: writable entries remain in {c.remote}")
        if c.kind == "guard-job":
            check_git(split_sections(text).get("FGIT|0", [])[:8], "F")
    return [line for line in lines if line.startswith("FINAL|")]


# ---------------------------------------------------------------- streaming

class HashingReader:
    def __init__(self, path, expected, size):
        fd, _ = C.open_regular(path)                                 # O_NOFOLLOW, regular file only
        self.path, self.stream, self.expected, self.size = str(path), os.fdopen(fd, "rb"), expected, size
        self.digest, self.count = hashlib.sha256(), 0

    def read(self, n=-1):
        n = min(n if n and n > 0 else CHUNK, self.size - self.count + 1)     # never more than size + 1 bytes
        data = self.stream.read(n) if n > 0 else b""
        self.digest.update(data)
        self.count += len(data)
        return data

    def close(self):
        self.stream.close()
        require(self.count == self.size and self.digest.hexdigest() == self.expected,
                "local file changed while streaming: " + self.path)


def write_stream(fileobj, components):
    now = int(time.time())                                            # one mtime for every member
    with tarfile.open(fileobj=fileobj, mode="w|", format=tarfile.PAX_FORMAT) as tar:
        for c in components:
            prefix = os.path.relpath(c.partial, EXTRACT_ROOT)
            require(not prefix.startswith(".."), "component outside the extract root")
            for rel in [""] + c.dirs:
                info = tarfile.TarInfo(prefix + ("/" + rel if rel else ""))
                info.type, info.mode, info.mtime = tarfile.DIRTYPE, 0o755, now
                tar.addfile(info)
            for rel in sorted(c.files):
                f = c.files[rel]
                info = tarfile.TarInfo(prefix + "/" + rel)
                info.size, info.mode, info.mtime = f["size"], 0o755 if f["executable"] else 0o644, now
                reader = HashingReader(c.local / rel, f["sha256"], f["size"])
                try:
                    tar.addfile(info, reader)
                finally:
                    reader.close()


# ---------------------------------------------------------------- run

def plan(a, log):
    host = a.host
    require(host in HOSTS, "--host must be 127x03 or 127x04")
    require(a.runtime or a.inputs or a.bundle or a.guard_job, "nothing to stage")
    components, runtime_manifest, guard_manifest = [], None, None
    if a.runtime:
        component, runtime_manifest = runtime_component(host, a.runtime, log)
        components.append(component)
    elif a.runtime_manifest_for_checks:
        runtime_manifest, _ = S9.load_manifest(a.runtime_manifest_for_checks)
    if a.guard_job:
        guard, guard_manifest = guard_component(host, a.guard_job, log)
    if a.inputs:
        components.append(inputs_component(host, a.inputs_source, log))
    for directory in a.bundle or ():
        components.append(bundle_component(host, directory, runtime_manifest, guard_manifest))
    if a.guard_job:
        components.append(guard)
    remotes = [c.remote for c in components]
    require(len(set(remotes)) == len(remotes), "two components share a remote path")
    for c in components:
        check_remote(host, c.partial)
    return components


def run(a, log=print):
    started = utc()
    if a.dry_run:
        components = plan(a, log)
        need = sum(sum(f["size"] for f in c.files.values()) for c in components)
        log(json.dumps(dict(mode="dry-run", host=a.host, logins=3, bytes=need,
                            components=[c.summary() for c in components]), indent=1))
        for label, make in (("P", p_script), ("TV", tv_script), ("F", f_script)):
            log(f"# login {label} {a.host}" + (" (stdin: tar stream)" if label == "TV" else ""))
            log(shlex.join(ssh_argv(a.ssh, a.host, make(a.host, components))))
        return None
    record = C.confined_new(a.record, "--record")              # first: every later refusal leaves a receipt here
    record.mkdir()
    logins, components = [], []
    try:
        require(a.outside_end_window, "live run requires --outside-end-window '<coordinator A2 GO / window reference>'")
        components = plan(a, log)
        need = sum(sum(f["size"] for f in c.files.values()) for c in components)
        scripts = dict(P=p_script(a.host, components), TV=tv_script(a.host, components), F=f_script(a.host, components))
        ssh = shutil.which(a.ssh)
        require(ssh is not None, "ssh not found: " + a.ssh)
        files = sum(len(c.files) + len(c.dirs) for c in components)

        def login(label, timeout, limit, feed=None):
            argv = ssh_argv(ssh, a.host, scripts[label])
            logins.append(dict(label=label, host=a.host, started_utc=utc(), argv=argv))
            log(f"[{utc()}] ssh {label} {a.host}")
            rc, out, err = C.run_bounded(argv, timeout, limit, feed=feed)
            logins[-1].update(finished_utc=utc(), returncode=rc, stderr_tail=err.decode(errors="replace")[-400:])
            require(rc == 0, f"ssh {label} {a.host} failed rc={rc}: " + err.decode(errors="replace")[-400:])
            return out

        inspect = parse_p(a.host, login("P", 600, 1 << 20), components, need)
        verified = check_tv(login("TV", 6 * 3600, (8 << 20) + 1024 * files,
                                  lambda stdin: write_stream(stdin, components)), components)
        final = check_f(a.host, login("F", 1800, 1 << 20), components)
        manifest = dict(schema=SCHEMA, status="staged", host=a.host, started_utc=started, finished_utc=utc(),
                        outside_end_window=a.outside_end_window, ssh_logins=len(logins), logins=logins,
                        inspect=inspect, components=[c.summary() for c in components], on_host_verified=verified,
                        final=final, script_sha256=sha_file(Path(__file__).resolve()),
                        s3_sha256=sha_file(S3.__file__), s9_sha256=sha_file(S9.__file__),
                        common_sha256=sha_file(C.__file__), inventories={c.remote: c.entries for c in components})
        C.write_new(record / "s10-staging-manifest.json", (json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode())
        log(f"S10 OK: {record / 's10-staging-manifest.json'} sha256 {sha_file(record / 's10-staging-manifest.json')}")
        return manifest
    except BaseException as error:
        C.write_new(record / "S10-REFUSAL.json", (json.dumps(dict(
            schema=SCHEMA, status="refused", error=str(error), utc=utc(), logins=logins,
            leftover_partials_needing_authorized_cleanup=[c.partial for c in components] if logins else []),
            indent=1) + "\n").encode())
        raise


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--host", required=True, choices=HOSTS)
    ap.add_argument("--runtime", help="S9 output directory (ships the runtime)")
    ap.add_argument("--runtime-manifest-for-checks", help="S9 output used only to check bundles (no ship)")
    ap.add_argument("--inputs", action="store_true", help="ship the Q6 T1 background inputs")
    ap.add_argument("--inputs-source", default=INPUTS_SOURCE)
    ap.add_argument("--bundle", action="append", help="S4 bundle directory (repeatable)")
    ap.add_argument("--guard-job", help="S3 output directory")
    ap.add_argument("--record", help="new local directory for the staging manifest (live run)")
    ap.add_argument("--ssh", default="ssh")
    ap.add_argument("--outside-end-window", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if not a.dry_run and not a.record:
        ap.error("--record is required unless --dry-run")
    try:
        run(a)
    except Refusal as error:
        print("S10 REFUSED: " + str(error), file=sys.stderr)
        return 2
    except Exception as error:                                        # fail closed on anything unexpected
        print(f"S10 FAILED: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
