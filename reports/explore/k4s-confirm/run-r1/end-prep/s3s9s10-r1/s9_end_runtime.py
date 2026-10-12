#!/usr/bin/env python3
"""S9 (PREREG-K4S END, Q5): 05-only END runtime builder. CANDIDATE: needs Sol review before any use.

No ssh, no host. Reads the 05 clasher repository through git only (ls-tree / cat-file / merge-base / diff, never
the work tree), and reads (never writes) the candidate 05 source trees named on the command line.

Subcommands
  locate       Find the 33 runtime-pin-r2 names that are not in git at --commit, by exact relative-path suffix and
               SHA-256, under the candidate 05 source roots (read-only walk; `games/`, `.git/`, `__pycache__/`
               pruned; symlinks never followed; archives listed, not opened). Prints found/missing for all 33.
  build        Export the git content of --commit (blob-exact, the content of `git archive`; the one tracked
               symlink is dereferenced to a regular file, as in T1's A5 runtime), add the 33 non-git files copied
               byte-exact from located 05 sources, then verify with the FROZEN prepare_bundle.runtime_pins and
               k4s_logic.load_k4s_manifest(74314eda, require_frozen=True) imported from the new tree, and write
               <out>/runtime-manifest.json (runtime_files / measurement_files + canonical SHAs, per-file
               inventory for S10). Built in <out>.partial and renamed only after every check passed.
  verify       Re-hash a built runtime against its manifest (and optionally re-run the frozen checks).
  equivalence  Prove that a runtime built at commit P has the same runtime_files and K4S-pinned bytes as a
               later commit X (e.g. the END-JOB commit), listing every other changed path.

Exit codes: 0 ok; 2 refused (S9 REFUSED: reason); 3 `locate`/`build` found missing pins (STOP for a ruling);
1 unexpected error (still fail closed).
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import end_prep_common as C                                           # noqa: E402

if Path(C.__file__).resolve().parent != HERE:
    raise SystemExit("end_prep_common imported from outside " + str(HERE))

SCHEMA = "clasher.k4s.end-runtime.v1"
LOCATE_SCHEMA = "clasher.k4s.end-runtime-locate.v1"
EQUIV_SCHEMA = "clasher.k4s.end-runtime-equivalence.v1"
BASE_COMMIT = "133f3ae4f414c9b8a3715eb8f44832fc96a6e5db"          # Q5: the END runtime commit is at or after this
RUNTIME_PIN_REL = "reports/explore/s1/receipts/runtime-pin-r2.json"
RUNTIME_PIN_SHA = "f81f36558179458ba74edd3a57f44ad3395f4452a93c64d3102c4f4d5048a80d"
QUALIFIED_REL = "reports/explore/s1/receipts/qualified-source-binding.json"
QUALIFIED_SHA = "56b67dd430636c90462156f3790f3a03df40410a77ffbd3d2d4c0b11acc0dce6"
K4S_MANIFEST_REL = "reports/explore/k4s-confirm/mac/K4S-MAC-MANIFEST.json"
K4S_MANIFEST_SHA = "74314eda04a7100d7ce10141394282b646723d29d0e7bb3883355d1ef1db6357"
K4S_MAC_REL = "reports/explore/k4s-confirm/mac"
E4V3_REL = "reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3"
# The only frozen modules the S9 cross-check imports (prepare_bundle -> receipts, tier_backend; k4s_logic). Their bytes
# are verified with stdlib BEFORE any import: K4S-manifest pins and/or the 42b8986d measurement inventory.
IMPORT_CLOSURE = (E4V3_REL + "/prepare_bundle.py", E4V3_REL + "/tier_backend.py", E4V3_REL + "/receipts.py",
                  K4S_MAC_REL + "/k4s_logic.py")
# Canonical SHA of the 18-file e4v3 measurement inventory (= T1 END-A5 reviewed inventory; b3 DESIGN §E).
MEASUREMENT_SHA = "42b8986d7e7748dd826ddad021ced3573d3ca5bbc21333120f1bf212beef8c25"
# The 33 runtime-pin-r2 names that are not in git (b3 DESIGN §E; recomputed from --commit and required equal).
EXTERNAL = frozenset("""
imitation/__init__.py
imitation/evaluation/legacy_audit.py
imitation/evaluation/runtime_dependencies/derived_d1.py
imitation/evaluation/runtime_dependencies/own_cycle.py
imitation/evaluation/runtime_dependencies/sidecar_observer.py
imitation/evaluation/seed_compat.py
reports/strategy_council_20260928/c56/engine/root-v3/human_deck_catalog.json
reports/strategy_council_20260928/m0/data/roles_v2/training.json
reports/strategy_council_20260928/search-noise-s6/runtime/support/human_deck_catalog.json
reports/strategy_council_20260928/search-noise-s6/runtime/support/selection.json
src/clasher/analysis/loss_review/delay_fixes.py
src/clasher/analysis/loss_review/delay_runtime.py
src/clasher/analysis/loss_review/delay_simulate.py
src/clasher/analysis/loss_review/scheduling.py
src/clasher/analysis/loss_review/search_ab.py
src/clasher/analysis/loss_review/tempo.py
src/clasher/analysis/loss_review/throughput_guard.py
student-source/exit_r3/__init__.py
student-source/exit_r3/network.py
student-source/exit_r3/rows.py
student-source/exit_r3/student.py
student-source/exit_r3/teacher_batch.py
student-source/exit_r3/test_r3.py
student-source/exit_r3/test_round2.py
student-source/exit_r3/train.py
tests/analysis/test_delay_fixes.py
tests/analysis/test_delay_fixes_summary.py
tests/analysis/test_search_ab.py
tests/analysis/test_search_ab_guard.py
tests/analysis/test_tempo.py
tests/analysis/test_tempo_launch.py
tests/analysis/test_throughput_guard.py
tests/test_l1_v4.py
""".split())
T1 = "/mpac/sdicks02/jobs/clasher/t1-20261010-r1"
DEFAULT_SOURCES = (T1 + "/end-a5-0775b704-0108-r1-shipping",
                   T1 + "/end-a5-CANDIDATE-0775b704-0108-r1",
                   "/mpac/sdicks02/k4s-runner/stage")
DEFAULT_PYTHON = "/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python"
PRUNE_DIRS = frozenset(("games", ".git", "__pycache__"))
ARCHIVE_SUFFIXES = (".tar", ".tar.gz", ".tgz", ".zip")
MAX_EXTERNAL_BYTES = 64 * 1024 * 1024
COMMIT = re.compile(r"[0-9a-f]{40}")
SHA = re.compile(r"[0-9a-f]{64}")
CHUNK = 1 << 20


Refusal, require = C.Refusal, C.require


class Missing(Refusal):
    """At least one of the 33 pins was not found on 05 by SHA: STOP for a ruling, never substitute."""


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def canonical(value):
    """receipts.canonical / k4s_logic.canonical (sort_keys, compact separators, no NaN)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    """O_NOFOLLOW, regular files only (end_prep_common)."""
    return C.sha_file(path)


def git_blob_id(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def safe_rel(name, label="path"):
    require(isinstance(name, str) and name and not name.startswith("/") and "\\" not in name
            and "\n" not in name and all(p not in ("", ".", "..") for p in name.split("/")),
            "unsafe " + label + ": " + repr(name))
    return name


# ---------------------------------------------------------------- git (read only)

def git(repository, *args, text=True):
    result = subprocess.run(["git", "-C", str(repository), *args], capture_output=True, text=text)
    require(result.returncode == 0, "git " + " ".join(args[:3]) + " failed: "
            + (result.stderr if text else result.stderr.decode(errors="replace"))[-300:])
    return result.stdout


def resolve_commit(repository, commit):
    require(COMMIT.fullmatch(commit or "") is not None, "commit must be a full 40-hex SHA: " + repr(commit))
    out = subprocess.run(["git", "-C", str(repository), "rev-parse", "--verify", "-q", commit + "^{commit}"],
                         capture_output=True, text=True)
    require(out.returncode == 0 and out.stdout.strip() == commit, "commit not in repository: " + commit)
    return commit


def is_ancestor(repository, older, newer):
    result = subprocess.run(["git", "-C", str(repository), "merge-base", "--is-ancestor", older, newer],
                            capture_output=True)
    require(result.returncode in (0, 1), "git merge-base failed")
    return result.returncode == 0


def show(repository, commit, rel):
    result = subprocess.run(["git", "-C", str(repository), "show", commit + ":" + rel], capture_output=True)
    require(result.returncode == 0, "not committed at " + commit + ": " + rel)
    return result.stdout


def ls_tree(repository, commit):
    """[(mode, type, oid, path)] of every tracked entry at commit."""
    raw = git(repository, "ls-tree", "-r", "-z", "--full-tree", commit, text=False)
    entries = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        meta, _, path = record.partition(b"\t")
        mode, kind, oid = meta.decode().split()
        entries.append((mode, kind, oid, safe_rel(path.decode(), "tracked path")))
    return entries


def commit_pins(repository, commit):
    """runtime-pin-r2 / qualified binding / K4S manifest at commit, each SHA-checked; the 33 external names."""
    resolve_commit(repository, commit)
    require(is_ancestor(repository, BASE_COMMIT, commit), "commit is not at or after 133f3ae4 (Q5): " + commit)
    raw = show(repository, commit, RUNTIME_PIN_REL)
    require(sha_bytes(raw) == RUNTIME_PIN_SHA, "runtime-pin-r2.json at the commit is not f81f3655")
    require(sha_bytes(show(repository, commit, QUALIFIED_REL)) == QUALIFIED_SHA,
            "qualified-source-binding.json at the commit is not 56b67dd4")
    require(sha_bytes(show(repository, commit, K4S_MANIFEST_REL)) == K4S_MANIFEST_SHA,
            "K4S-MAC-MANIFEST.json at the commit is not 74314eda")
    pins = json.loads(raw)["files"]
    require(isinstance(pins, dict) and all(SHA.fullmatch(v or "") for v in pins.values()), "malformed runtime pin")
    entries = ls_tree(repository, commit)
    tracked = {path for _, _, _, path in entries}
    external = {name for name in pins if name not in tracked}
    require(external == EXTERNAL, "the non-git runtime-pin names at this commit differ from the 33 of record: "
            + repr(sorted(external ^ EXTERNAL)[:6]))
    return pins, entries


# ---------------------------------------------------------------- locate (read-only walk of 05 sources)

def locate(pins, sources, log=print):
    want = {name: pins[name] for name in sorted(EXTERNAL)}
    found = {name: [] for name in want}
    archives, unreadable = [], []
    for source in sources:
        root = Path(source)
        require(root.is_absolute() and os.path.normpath(source) == source, "source must be absolute: " + source)
        if not root.is_dir() or os.path.realpath(source) != source:          # no symlinked root or ancestor
            unreadable.append(source)
            continue
        for directory, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = sorted(d for d in dirnames if d not in PRUNE_DIRS and not d.endswith(".partial"))
            for filename in sorted(filenames):
                path = os.path.join(directory, filename)
                if filename.endswith(ARCHIVE_SUFFIXES):
                    archives.append(path)
                    continue
                rel = os.path.relpath(path, root)
                for name in want:
                    if (rel == name or rel.endswith("/" + name)) and not os.path.islink(path):
                        info = os.lstat(path)
                        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_EXTERNAL_BYTES:
                            continue
                        digest = sha_file(path)                  # O_NOFOLLOW: a swapped-in link refuses
                        found[name].append(dict(source_path=path, size=info.st_size, sha256=digest,
                                                matches=digest == want[name]))
    files, missing = [], []
    for name, expected in want.items():
        good = [f for f in found[name] if f["matches"]]
        files.append(dict(path=name, expected_sha256=expected, candidates=found[name],
                          chosen=good[0]["source_path"] if good else None))
        if not good:
            missing.append(name)
    return dict(schema=LOCATE_SCHEMA, utc=utc(), sources=list(sources), archives_not_searched=sorted(archives),
                unreadable_sources=unreadable, wanted=len(want), found=len(want) - len(missing),
                missing=missing, ok=not missing, files=files)


def print_locate(result, log=print):
    for row in result["files"]:
        if row["chosen"]:
            log(f"FOUND    {row['expected_sha256'][:12]}  {row['path']}  <-  {row['chosen']}")
        else:
            seen = ",".join(c["sha256"][:12] for c in row["candidates"]) or "none"
            log(f"MISSING  {row['expected_sha256'][:12]}  {row['path']}  (same-name candidates with other SHA: {seen})")
    log(f"locate: {result['found']}/{result['wanted']} found; missing {len(result['missing'])}")
    if result["missing"]:
        log("!!! MISSING PINS: STOP for a coordinator ruling; never substitute bytes !!!")


# ---------------------------------------------------------------- frozen inventory rules

def measurement_files(e4v3):
    """prepare_bundle.py:117 rule."""
    return {p.name: sha_file(p) for p in sorted(Path(e4v3).iterdir())
            if p.suffix in (".py", ".sh") or p.name == "spec-pins.json"}


def runtime_files(root):
    """prepare_bundle.runtime_pins (prepare_bundle.py:36-52), same rule; Refusal instead of ValueError."""
    root = Path(root)
    source = root / RUNTIME_PIN_REL
    require(source.is_file(), "runtime lacks " + RUNTIME_PIN_REL)
    names = set(json.loads(C.read_bounded(source, 64 << 20))["files"])
    names.update(str(p.relative_to(root)) for p in root.rglob("*.py"))
    for n in names:
        safe_rel(n, "runtime name")                                   # no absolute / .. / empty component
    missing = sorted(n for n in names if not (root / n).is_file())
    require(not missing, "Incomplete frozen runtime: " + repr(missing[:8]))
    result = {n: sha_file(root / n) for n in sorted(names)}
    qualified = json.loads(C.read_bounded(root / QUALIFIED_REL, 16 << 20))
    for n, expected in qualified["qualified_source_files"].items():
        require(result.get(n) == expected, "Not the qualified S1 tier source: " + n)
    return result


def verify_closure(root):
    """Stdlib-only, BEFORE importing anything from the runtime: the K4S manifest bytes are 74314eda, every file it
    pins matches, the e4v3 measurement inventory is 42b8986d, and every module of IMPORT_CLOSURE is covered."""
    raw = C.read_bounded(Path(root) / K4S_MANIFEST_REL, 4 << 20)
    require(sha_bytes(raw) == K4S_MANIFEST_SHA, "runtime K4S manifest is not 74314eda")
    manifest = json.loads(raw)
    pins = {}
    for key in ("k4s_files", "end_files", "reused_readonly"):
        pins.update(manifest[key])
    pins.update(manifest["k4s_kernel"]["files"])
    for name, expected in sorted(pins.items()):
        require(sha_file(Path(root) / safe_rel(name, "pinned name")) == expected, "K4S-pinned file differs: " + name)
    measurement = measurement_files(Path(root) / E4V3_REL)
    require(canonical_sha(measurement) == MEASUREMENT_SHA, "e4v3 measurement inventory is not 42b8986d")
    for name in IMPORT_CLOSURE:
        covered = name in pins or (name.startswith(E4V3_REL + "/") and name.rsplit("/", 1)[1] in measurement)
        require(covered, "import closure module is not covered by a verified pin: " + name)
    return dict(k4s_pins_verified=len(pins), measurement_files_sha256=canonical_sha(measurement),
                import_closure=list(IMPORT_CLOSURE))


FROZEN_SNIPPET = r"""
import json, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
e4v3 = root / sys.argv[2]; mac = root / sys.argv[3]
sys.path.insert(0, str(e4v3)); sys.path.insert(0, str(mac))
import prepare_bundle, k4s_logic
closure = {str(root / n) for n in json.loads(sys.argv[6])}
loaded = {str(Path(m.__file__).resolve()) for m in list(sys.modules.values()) if getattr(m, "__file__", None)
          and str(Path(m.__file__).resolve()).startswith(str(root) + "/")}
if not loaded <= closure or str((e4v3 / "prepare_bundle.py").resolve()) not in loaded:
    raise SystemExit("runtime modules imported outside the verified closure: " + repr(sorted(loaded - closure)))
runtime = prepare_bundle.runtime_pins(root)
manifest = k4s_logic.load_k4s_manifest(root / sys.argv[4], sys.argv[5], root, require_frozen=True)
print(json.dumps(dict(runtime_files=runtime, prepare_bundle=str(Path(prepare_bundle.__file__).resolve()),
                      k4s_logic=str(Path(k4s_logic.__file__).resolve()), python=sys.version.split()[0],
                      optimize=sys.flags.optimize, k4s_manifest_schema=manifest["schema"],
                      k4s_reused_readonly=len(manifest["reused_readonly"]))))
"""


def frozen_check(root, python):
    """Cross-check with the FROZEN prepare_bundle.runtime_pins and k4s_logic.load_k4s_manifest, imported from the
    runtime itself, ONLY after verify_closure() verified their bytes with stdlib (the frozen code is never the
    verifier of its own identity)."""
    closure = verify_closure(root)
    # Never -O: run the frozen code as the hosts do.
    argv = [python, "-I", "-B", "-c", FROZEN_SNIPPET, str(Path(root).resolve()), E4V3_REL, K4S_MAC_REL,
            K4S_MANIFEST_REL, K4S_MANIFEST_SHA, json.dumps(IMPORT_CLOSURE)]
    result = subprocess.run(argv, capture_output=True, text=True, cwd="/", timeout=1800)
    require(result.returncode == 0, "frozen runtime check refused: " + result.stderr.strip()[-600:])
    return dict(json.loads(result.stdout), stdlib_verified=closure)


# ---------------------------------------------------------------- export / build

def export_commit(repository, entries, dest):
    """Blob-exact export of every tracked entry (the content `git archive` would write; there are no
    .gitattributes in the tree, and each written file's git blob id is re-checked). Symlinks are dereferenced
    afterwards to a regular copy of their in-tree target (T1 A5 precedent); submodules are refused."""
    blobs = [e for e in entries if e[1] == "blob"]
    require(len(blobs) == len(entries), "tree holds a non-blob entry (submodule?)")
    links = []
    batch = subprocess.Popen(["git", "-C", str(repository), "cat-file", "--batch"], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE)
    try:
        for mode, _, oid, path in blobs:
            batch.stdin.write(oid.encode() + b"\n")
            batch.stdin.flush()
            header = batch.stdout.readline().split()
            require(len(header) == 3 and header[0].decode() == oid and header[1] == b"blob", "cat-file: " + oid)
            data = batch.stdout.read(int(header[2]))
            require(batch.stdout.read(1) == b"\n" and git_blob_id(data) == oid, "blob read mismatch: " + path)
            if mode == "120000":
                links.append((path, data.decode()))
                continue
            require(mode in ("100644", "100755"), "unsupported tracked mode " + mode + ": " + path)
            target = dest / path
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "xb") as out:
                out.write(data)
            os.chmod(target, 0o755 if mode == "100755" else 0o644)
    finally:
        batch.stdin.close()
        batch.wait()
    require(batch.returncode == 0, "git cat-file --batch failed")
    dereferenced = []
    for path, link in links:
        resolved = os.path.normpath(os.path.join(os.path.dirname(path), link))
        require(not os.path.isabs(link) and not resolved.startswith("../") and resolved != "..",
                "tracked symlink escapes the tree: " + path + " -> " + link)
        source = dest / resolved
        require(source.is_file() and not source.is_symlink(), "tracked symlink target is not a tracked file: " + path)
        shutil.copyfile(source, dest / path)
        os.chmod(dest / path, 0o644)
        dereferenced.append(dict(path=path, target=link, sha256=sha_file(dest / path)))
    return dereferenced


def add_externals(dest, pins, located):
    added = []
    for row in located["files"]:
        name, expected = row["path"], row["expected_sha256"]
        require(pins[name] == expected and row["chosen"], "no located source for " + name)
        target = dest / name
        require(not target.exists() and not target.is_symlink(), "external pin collides with a git path: " + name)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = C.read_bounded(row["chosen"], MAX_EXTERNAL_BYTES)      # O_NOFOLLOW, bounded
        require(sha_bytes(data) == expected, "source changed since locate: " + row["chosen"])
        C.write_new(target, data, 0o644)
        require(sha_file(target) == expected, "written external differs: " + name)
        added.append(dict(path=name, sha256=expected, size=len(data), source_path=row["chosen"]))
    return added


def inventory(root):
    """Every entry under root: regular files (size, sha256, exec bit) and directories. Symlinks are refused."""
    files, dirs = {}, []
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for d in dirnames:
            path = os.path.join(directory, d)
            require(not os.path.islink(path), "symlink in runtime tree: " + path)
            dirs.append(safe_rel(os.path.relpath(path, root)))
        for f in sorted(filenames):
            path = os.path.join(directory, f)
            info = os.lstat(path)
            require(stat.S_ISREG(info.st_mode), "non-regular file in runtime tree: " + path)
            files[safe_rel(os.path.relpath(path, root))] = dict(size=info.st_size, sha256=sha_file(path),
                                                                executable=bool(info.st_mode & 0o100))
    return dict(files=files, dirs=sorted(dirs))


def verify_tree(root, entries, dereferenced, added):
    """Every tracked blob (git blob id), every dereferenced link and external, and nothing else."""
    links = {d["path"] for d in dereferenced}
    expected = {path for _, _, _, path in entries} | {a["path"] for a in added}
    present = set(inventory(root)["files"])
    require(present == expected, "tree differs from git + externals: " + repr(sorted(present ^ expected)[:6]))
    for mode, _, oid, path in entries:
        if path not in links:
            require(git_blob_id((root / path).read_bytes()) == oid, "exported file differs from git: " + path)


def freeze_modes(root):
    for directory, _, filenames in os.walk(root):
        for f in filenames:
            path = os.path.join(directory, f)
            os.chmod(path, os.lstat(path).st_mode & ~0o222)


def build(a, log=print):
    repository, commit = Path(a.repository), a.commit
    out = C.confined_new(a.out, "--out")
    partial = C.confined_new(str(out) + ".partial", "--out .partial")
    started = utc()
    pins, entries = commit_pins(repository, commit)
    located = locate(pins, a.source or DEFAULT_SOURCES)
    print_locate(located, log)
    if located["missing"]:
        raise Missing("33-pin locate incomplete; missing: " + ", ".join(located["missing"]))
    partial.mkdir()
    try:
        return finish_build(a, repository, commit, out, partial, pins, entries, located, started, log)
    except BaseException:
        remove_tree(partial)                                          # our own .partial only; out never existed
        raise


def remove_tree(path):
    for directory, dirnames, _ in os.walk(path):
        os.chmod(directory, 0o755)
    for directory, _, filenames in os.walk(path):
        for f in filenames:
            if not os.path.islink(os.path.join(directory, f)):       # never chmod through a link
                os.chmod(os.path.join(directory, f), 0o644)
    shutil.rmtree(path)


def finish_build(a, repository, commit, out, partial, pins, entries, located, started, log):
    root = partial / "runtime"
    root.mkdir()
    dereferenced = export_commit(repository, entries, root)
    added = add_externals(root, pins, located)
    verify_tree(root, entries, dereferenced, added)
    local = runtime_files(root)
    frozen = frozen_check(root, a.python)
    require(frozen["runtime_files"] == local, "frozen runtime_pins differs from the S9 re-implementation")
    measurement = measurement_files(root / E4V3_REL)
    require(canonical_sha(measurement) == MEASUREMENT_SHA, "e4v3 measurement inventory is not 42b8986d")
    tracked_mismatch = [dict(path=n, git_sha256=local.get(n), runtime_pin_r2_sha256=pins[n])
                        for n in sorted(pins) if n not in EXTERNAL and local.get(n) != pins[n]]
    freeze_modes(root)
    inv = inventory(root)
    manifest = dict(
        schema=SCHEMA, status="CANDIDATE-built", started_utc=started, finished_utc=utc(), commit=commit,
        tree=git(repository, "rev-parse", commit + "^{tree}").strip(), base_commit=BASE_COMMIT,
        runtime_dir="runtime", k4s_manifest_sha256=K4S_MANIFEST_SHA, runtime_pin_r2_sha256=RUNTIME_PIN_SHA,
        qualified_source_binding_sha256=QUALIFIED_SHA,
        runtime_files=local, runtime_files_count=len(local), runtime_files_sha256=canonical_sha(local),
        measurement_files=measurement, measurement_files_sha256=canonical_sha(measurement),
        externals=added, dereferenced_symlinks=dereferenced, tracked_pin_sha_differs_from_git=tracked_mismatch,
        frozen_check=dict((k, v) for k, v in frozen.items() if k != "runtime_files"),
        frozen_runtime_files_equal=True, locate=dict(sources=located["sources"],
                                                     archives_not_searched=located["archives_not_searched"]),
        inventory=inv, inventory_files=len(inv["files"]),
        inventory_bytes=sum(f["size"] for f in inv["files"].values()), inventory_sha256=canonical_sha(inv),
        script_sha256=sha_file(Path(__file__).resolve()), python=a.python)
    C.write_new(partial / "runtime-manifest.json", (json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode())
    partial.rename(out)
    path = out / "runtime-manifest.json"
    log(f"S9 OK: {path} sha256 {sha_file(path)}")
    log(f"  runtime_files {manifest['runtime_files_count']} canonical {manifest['runtime_files_sha256']}")
    log(f"  measurement_files canonical {manifest['measurement_files_sha256']}; inventory {manifest['inventory_files']}"
        f" files, {manifest['inventory_bytes']} bytes, canonical {manifest['inventory_sha256']}")
    return manifest


def load_manifest(out):
    path = Path(out) / "runtime-manifest.json"
    require(path.is_file() and not path.is_symlink(), "missing runtime-manifest.json in " + str(out))
    manifest = json.loads(C.read_bounded(path, 256 << 20))
    require(manifest.get("schema") == SCHEMA and manifest.get("k4s_manifest_sha256") == K4S_MANIFEST_SHA,
            "not an S9 runtime manifest")
    return manifest, sha_file(path)


def verify(a, log=print):
    manifest, manifest_sha = load_manifest(a.out)
    root = Path(a.out) / manifest["runtime_dir"]
    inv = inventory(root)
    require(inv == manifest["inventory"] and canonical_sha(inv) == manifest["inventory_sha256"],
            "runtime tree differs from its manifest inventory")
    local = runtime_files(root)
    require(local == manifest["runtime_files"] and canonical_sha(local) == manifest["runtime_files_sha256"],
            "runtime_files differ from the manifest")
    measurement = measurement_files(root / E4V3_REL)
    require(canonical_sha(measurement) == manifest["measurement_files_sha256"] == MEASUREMENT_SHA,
            "measurement_files differ")
    if a.frozen:
        require(frozen_check(root, a.python)["runtime_files"] == local, "frozen runtime_pins differs")
    log(f"S9 VERIFY OK: manifest {manifest_sha}; runtime_files {manifest['runtime_files_sha256']}; "
        f"inventory {manifest['inventory_sha256']}{' (frozen re-run)' if a.frozen else ''}")
    return manifest


# ---------------------------------------------------------------- equivalence (P built, X = END-JOB commit)

def equivalence(a, log=print):
    repository = Path(a.repository)
    p, x = resolve_commit(repository, a.runtime_commit), resolve_commit(repository, a.end_job_commit)
    require(is_ancestor(repository, p, x), "runtime commit is not an ancestor of (or equal to) the END-JOB commit")
    pins_p, entries_p = commit_pins(repository, p)
    pins_x, entries_x = commit_pins(repository, x)
    blobs_p = {path: (mode, oid) for mode, _, oid, path in entries_p}
    blobs_x = {path: (mode, oid) for mode, _, oid, path in entries_x}
    names = set(pins_p) | {n for n in blobs_p if n.endswith(".py")} | {n for n in blobs_x if n.endswith(".py")}
    k4s = json.loads(show(repository, x, K4S_MANIFEST_REL))
    pinned = set(k4s["k4s_files"]) | set(k4s["end_files"]) | set(k4s["reused_readonly"]) \
        | set(k4s["k4s_kernel"]["files"]) | {K4S_MANIFEST_REL}
    pinned |= {n for n in blobs_x if n.startswith(E4V3_REL + "/")} | {n for n in blobs_p if n.startswith(E4V3_REL + "/")}
    relevant = sorted(n for n in names | pinned if n not in EXTERNAL and blobs_p.get(n) != blobs_x.get(n))
    changed = sorted(n for n in set(blobs_p) | set(blobs_x) if blobs_p.get(n) != blobs_x.get(n))
    result = dict(schema=EQUIV_SCHEMA, utc=utc(), runtime_commit=p, end_job_commit=x,
                  runtime_relevant_changes=relevant, runtime_files_and_k4s_pins_equal=not relevant,
                  other_changed_paths=[n for n in changed if n not in relevant], changed_paths=len(changed))
    log(json.dumps(result, indent=1))
    require(not relevant, "runtime-relevant paths differ between the runtime commit and the END-JOB commit: "
            + ", ".join(relevant[:6]))
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    lp = sub.add_parser("locate")
    lp.add_argument("--repository", default="/mpac/sdicks02/repos/clasher")
    lp.add_argument("--commit", required=True)
    lp.add_argument("--source", action="append", help="candidate 05 root (repeatable; default: the Q5 three)")
    lp.add_argument("--json", type=Path, help="write the locate result here (new file)")
    bp = sub.add_parser("build")
    bp.add_argument("--repository", default="/mpac/sdicks02/repos/clasher")
    bp.add_argument("--commit", required=True)
    bp.add_argument("--out", required=True)
    bp.add_argument("--source", action="append")
    bp.add_argument("--python", default=DEFAULT_PYTHON if os.path.exists(DEFAULT_PYTHON) else sys.executable)
    vp = sub.add_parser("verify")
    vp.add_argument("--out", required=True)
    vp.add_argument("--frozen", action="store_true")
    vp.add_argument("--python", default=DEFAULT_PYTHON if os.path.exists(DEFAULT_PYTHON) else sys.executable)
    ep = sub.add_parser("equivalence")
    ep.add_argument("--repository", default="/mpac/sdicks02/repos/clasher")
    ep.add_argument("--runtime-commit", required=True)
    ep.add_argument("--end-job-commit", required=True)
    a = ap.parse_args(argv)
    try:
        if a.command == "locate":
            pins, _ = commit_pins(Path(a.repository), a.commit)
            result = locate(pins, a.source or DEFAULT_SOURCES)
            result["commit"] = a.commit
            print_locate(result)
            if a.json:
                C.write_new(C.confined_new(str(a.json), "--json"),
                            (json.dumps(result, indent=1, sort_keys=True) + "\n").encode(), 0o644)
                print(f"locate result: {a.json} sha256 {sha_file(a.json)}")
            return 0 if result["ok"] else 3
        {"build": build, "verify": verify, "equivalence": equivalence}[a.command](a)
    except Missing as error:
        print("S9 STOP (missing pins): " + str(error), file=sys.stderr)
        return 3
    except Refusal as error:
        print("S9 REFUSED: " + str(error), file=sys.stderr)
        return 2
    except Exception as error:                                        # fail closed on anything unexpected
        print(f"S9 FAILED: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
