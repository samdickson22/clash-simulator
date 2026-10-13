"""S4 r6 regression controls for INTEGRATION-AUDIT-r1 B1 (S4-REFUSAL-b3r5-runtime-pin-files-shape.md) and L4.

B1: the pinned runtime-pin-r2.json (S1_RUNTIME_PIN_SHA256) holds "files" as a dict {name: sha256} (1557 entries). The
frozen rule S4 mirrors, prepare_bundle.runtime_pins (prepare_bundle.py:42), is names = set(json.loads(...)["files"]):
the dict's keys (a list's items would give the same set), and it never reads the per-file SHAs. So S4 takes the keys
(or a list's items), refuses every other shape, and never compares the per-file SHAs (17 of the 1557 differ from the
runtime bytes at P'; S9's runtime-manifest records them as tracked_pin_sha_differs_from_git).

Real bytes (read-only, 05 only; skipped elsewhere): the pinned file from the S9 runtime copy and from `git cat-file` at
the S9 build commit of repo-full; the real S9 runtime through RuntimeInventory.members() against the frozen
prepare_bundle.runtime_pins run on the same tree and against S9's own runtime-manifest.

L4: the bundle receipt (and the stderr summary) carry the assembler's own SHA-256 as `assembler_sha256`.
Checks use ok() (an explicit raise), never a bare assert, so they keep their force under python -O."""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from test_assemble_fleet_reference import (A, E4V3_REL, EXCEPTION, World, fsha, ok, put, refused,  # noqa: F401
                                           world)
from test_s4_r4_git import e5_bytes, synthetic_e5

HERE = Path(__file__).resolve().parent
S9_ROOT = Path("/mpac/sdicks02/k4s-runner/run-r1/end-staging/runtime-98566c032d0b")
S9_RUNTIME = S9_ROOT / "runtime"
S9_MANIFEST = S9_ROOT / "runtime-manifest.json"
REPO_FULL = Path("/mpac/sdicks02/k4s-runner/run-r1/end-prep/repo-full")      # absolute: also from scratch copies
REAL_PIN_ENTRIES = 1557                       # S4-REFUSAL-b3r5 / INTEGRATION-AUDIT-r1 B1
SHAPE_REFUSAL = r"S1 runtime pin lacks a files dict \(or list\) of names"

real_bytes = pytest.mark.skipif(not (S9_MANIFEST.is_file() and (REPO_FULL / ".git").is_dir()),
                                reason="the S9 runtime and repo-full exist only on 127x05")


def s9_manifest():
    return json.loads(S9_MANIFEST.read_bytes())


def git_blob(commit, rel):
    """Read-only `git cat-file blob <commit>:<rel>` on repo-full: no replace objects, no system/global config."""
    env = dict(PATH="/usr/bin:/bin", HOME="/nonexistent", GIT_NO_REPLACE_OBJECTS="1", GIT_CONFIG_NOSYSTEM="1",
               GIT_CONFIG_GLOBAL="/dev/null", GIT_OPTIONAL_LOCKS="0")
    return subprocess.run(["git", "--git-dir=" + str(REPO_FULL / ".git"), "--no-replace-objects", "cat-file", "blob",
                           commit + ":" + rel], check=True, capture_output=True, env=env).stdout


def real_pin_bytes():
    raw = (S9_RUNTIME / A.S1_RUNTIME_PINS[0]).read_bytes()
    ok(hashlib.sha256(raw).hexdigest() == A.S1_RUNTIME_PIN_SHA256 == A.PRODUCTION_PINS["s1_runtime_pin_sha256"],
       "the S9 runtime copy is not the pinned runtime-pin-r2")
    return raw


def set_pin(world, files, recompute=True):
    """Write the runtime pin with this "files" value, pin its SHA and (if it is a valid shape) re-pin the request."""
    path = put(world.runtime / A.S1_RUNTIME_PINS[0], files if isinstance(files, bytes) else {"files": files})
    world.pin(lambda p: p.update(s1_runtime_pin_sha256=fsha(path)))
    if recompute:
        world.request["runtime_files_sha256"] = A.canonical_sha(A.runtime_files(world.runtime, world.pins))
    return path


def manifest_of(out):
    return json.loads((out / "tiers-pins.json").read_bytes())


# ---------------------------------------------------------------- B1 on the REAL pinned bytes

@real_bytes
def test_r6_real_pin_bytes_are_the_pinned_dict_in_runtime_and_git():
    raw = real_pin_bytes()
    commit = s9_manifest()["commit"]
    ok(re.fullmatch("[0-9a-f]{40}", commit) is not None, commit)
    ok(git_blob(commit, A.S1_RUNTIME_PINS[0]) == raw, "git show <S9 commit>:runtime-pin-r2.json != the runtime copy")
    files = json.loads(raw)["files"]
    ok(isinstance(files, dict) and len(files) == REAL_PIN_ENTRIES, "real shape: a dict of %d" % REAL_PIN_ENTRIES)
    ok(all(isinstance(v, str) and re.fullmatch("[0-9a-f]{64}", v) for v in files.values()))


@real_bytes
def test_r6_real_pin_bytes_through_members_in_synthetic_world(world):
    """The real pinned bytes drive the whole assembly (synthetic pins, re-pinned to the real SHA): membership = the
    dict's keys + every *.py, hashed from the bytes on disk; the placeholders' SHAs differ from every listed value."""
    raw = real_pin_bytes()
    keys = set(json.loads(raw)["files"])
    e5 = {name: e5_bytes(name) for name in sorted(keys) if name in A.si.E5_PATHS}
    synthetic_e5(world.mp, e5)                        # E5 stand-ins (real E5 bytes are never read), as add_e5 does
    for name, data in e5.items():
        put(world.runtime / name, data)
        put(world.repo / name, data)
    world.commit()
    for name in sorted(keys):
        if not (world.runtime / name).exists():
            put(world.runtime / name, ("# r6 placeholder " + name + "\n").encode())
    world.pin(lambda p: p.update(measurement_files_sha256=A.canonical_sha(
        A.measurement_files(world.runtime / E4V3_REL, p))))
    world.request["measurement_files_sha256"] = world.pins["measurement_files_sha256"]
    set_pin(world, raw)
    code, out = world.run()
    ok(code == 0)
    runtime = manifest_of(out)["runtime_files"]
    py = {str(p.relative_to(world.runtime)) for p in world.runtime.rglob("*.py")}
    ok(set(runtime) == keys | py, "membership must be the dict keys + every *.py")
    for name in sorted(keys - {EXCEPTION}):
        ok(runtime[name] == fsha(world.runtime / name), name)
    listed = json.loads(raw)["files"]
    placeholders = [n for n in keys if n not in e5 and n != EXCEPTION]
    ok(placeholders and all(runtime[n] != listed[n] for n in placeholders), "the per-file SHAs were not ignored")


@real_bytes
def test_r6_real_runtime_membership_equals_frozen_rule_and_s9():
    """RuntimeInventory.members() on the REAL S9 runtime (production pins, read-only) gives exactly the frozen
    prepare_bundle.runtime_pins result (run on the same tree from its own e4v3) and S9's recorded runtime_files."""
    real_pin_bytes()
    mine = A.runtime_files(str(S9_RUNTIME), A.PRODUCTION_PINS)
    e4v3 = S9_RUNTIME / E4V3_REL
    code = ("import sys,hashlib;from pathlib import Path;sys.path.insert(0,sys.argv[1])\n"
            "import prepare_bundle,receipts\n"
            "r=prepare_bundle.runtime_pins(Path(sys.argv[2]))\n"
            "print(hashlib.sha256(receipts.canonical(r).encode()).hexdigest(),len(r))")
    p = subprocess.run([sys.executable, "-I", "-B", *(["-O"] if sys.flags.optimize else []), "-c", code, str(e4v3),
                        str(S9_RUNTIME)], capture_output=True, text=True, cwd="/")
    ok(p.returncode == 0, p.stderr)
    ok(p.stdout.split() == [A.canonical_sha(mine), str(len(mine))], p.stdout)
    manifest = s9_manifest()
    ok(A.canonical_sha(mine) == manifest["runtime_files_sha256"] and len(mine) == manifest["runtime_files_count"])
    listed = json.loads((S9_RUNTIME / A.S1_RUNTIME_PINS[0]).read_bytes())["files"]
    differing = {n: dict(path=n, git_sha256=mine[n], runtime_pin_r2_sha256=listed[n]) for n in listed
                 if mine[n] != listed[n]}
    recorded = {d["path"]: d for d in manifest["tracked_pin_sha_differs_from_git"]}
    ok(set(listed) <= set(mine) and differing and differing == recorded,
       "comparing the per-file SHAs would refuse the real runtime: %d differ" % len(differing))


# ---------------------------------------------------------------- B1 shapes (synthetic world)

def test_r6_dict_membership_is_the_keys_not_the_values(world):
    put(world.runtime / "data/only-key.json", b"{}\n")
    put(world.runtime / "data/only-value.json", b"[]\n")
    names = ("data/x.json", "src/a.py", EXCEPTION)
    files = {n: fsha(world.runtime / n) for n in names}
    files["data/only-key.json"] = "data/only-value.json"
    set_pin(world, files)
    code, out = world.run()
    runtime = manifest_of(out)["runtime_files"]
    ok(code == 0 and "data/only-key.json" in runtime and "data/only-value.json" not in runtime)


@pytest.mark.parametrize("value", ["f" * 64, None, 7, {"nested": True}])
def test_r6_dict_per_file_shas_are_never_compared(world, value):
    """Frozen prepare_bundle.runtime_pins never reads the per-file SHAs (17 real ones differ), so S4 never does."""
    expected = A.runtime_files(world.runtime, world.pins)
    set_pin(world, {n: value for n in ("data/x.json", "src/a.py", EXCEPTION)})
    code, out = world.run()
    runtime = manifest_of(out)["runtime_files"]
    ok(code == 0 and runtime == expected and runtime["data/x.json"] == fsha(world.runtime / "data/x.json"))


def test_r6_list_form_gives_the_same_set_as_frozen(world):
    """prepare_bundle.py:42 is set(...["files"]): a list of names (duplicates allowed) is the same membership."""
    expected = A.runtime_files(world.runtime, world.pins)
    set_pin(world, ["src/a.py", "data/x.json", EXCEPTION, "src/a.py"])
    code, out = world.run()
    ok(code == 0 and manifest_of(out)["runtime_files"] == expected)


@pytest.mark.parametrize("doc", [
    {"files": "data/x.json"}, {"files": None}, {"files": 5}, {"files": True}, {"other": ["data/x.json"]},
    {"files": ["data/x.json", 3]}, {"files": ["data/x.json", None]}, {"files": [["data/x.json"]]},
    ["data/x.json"], "data/x.json",
], ids=["string", "null", "int", "bool", "no-files", "list-int", "list-null", "list-list", "top-list", "top-string"])
def test_r6_other_files_shapes_refused(world, doc):
    set_pin(world, json.dumps(doc).encode() + b"\n", recompute=False)
    refused(world, SHAPE_REFUSAL)


def test_r6_dict_keys_are_gated_like_list_items(world):
    """An unsafe key refuses as an unsafe name before any read (the f1 tests now use the dict shape throughout)."""
    set_pin(world, {"data/x.json": "0" * 64, "../outside.json": "0" * 64}, recompute=False)
    refused(world, r"Unsafe relative path \(S1 runtime-pin entry\): \.\./outside\.json")
    set_pin(world, {"data/x.json": "0" * 64, "data/missing.json": "0" * 64}, recompute=False)
    refused(world, r"Incomplete frozen runtime: \['data/missing\.json'\]")


# ---------------------------------------------------------------- L4: the assembler's own SHA in the receipt

def test_r6_receipt_and_summary_carry_assembler_sha256(world, capsys):
    own = fsha(HERE / "assemble_fleet_reference.py")
    code, _ = world.run(out=world.tmp / "dry" / "bundle-SYNTHETIC", dry_run=True)
    dry = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    ok(code == 0 and dry["dry_run"] is True and dry["assembler_sha256"] == own, repr(dry))
    code, out = world.run()
    real = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    receipt = json.loads((out / "assembly-receipt.json").read_bytes())
    ok(code == 0 and receipt["assembler_sha256"] == own and real["assembler_sha256"] == own, repr(real))
    ok(receipt["safe_input_sha256"] == fsha(HERE / "safe_input.py") == A.SAFE_INPUT_SHA256)
