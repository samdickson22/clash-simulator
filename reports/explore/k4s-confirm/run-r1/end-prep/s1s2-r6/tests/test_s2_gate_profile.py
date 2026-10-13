"""S2 r3 controls for Sol r2 S2-R2-F1 (the shared outcome/strict-END location gate on EVERY explicit input) and
S2-R2-F2 (strict profile contents, no default fallback).

Every location control runs a FULL CLI entrypoint (build, validate, diagnose-clock in repository and in S1-dest mode)
under tests/audit_run.py: audit-hook opens/listdirs/subprocesses, wrapped os.stat/os.lstat, and the (dev, ino) of
everything actually opened. Canary files carry VALID input bytes (so only the location can refuse them) and the
supplied SHA matches. Each control asserts the refusal AND zero events naming the canary location AND that no canary
inode is ever opened (hard-link aliases included) or stat-ed through anything but the operator-named alias itself."""
import argparse
import builtins
import contextlib
import json
import os
import shutil
from pathlib import Path

import pytest

from conftest import (S1_MANIFEST_NAME, S2, STUDY, audit_events, audited, make_repo, pins_args, py, s1_manifest_doc,
                      sha, synthetic_files)

EVIDENCE = STUDY + "/end-evidence.json"
HOSTS = ("127x03", "127x04")


def load_s2():
    import importlib.util
    spec = importlib.util.spec_from_file_location("s2_gate_under_test", S2)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S2M = load_s2()


def profile_doc(**changes):
    doc = {h: dict(host=h, reference_slot=0, slot_count=11, console_rule=False, warmup_seconds=300, perception="none",
                   plan="plan.json", end_evidence="end-evidence.json",
                   guard=dict(root="/mpac/sdicks02/jobs-k4s-guard", job="g-01")) for h in HOSTS}
    for host, change in changes.items():
        change(doc[host]) if callable(change) else doc.__setitem__(host, change)
    return doc


def put(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    """One synthetic committed repository with committed evidence, its S1 receipt bytes and a valid profile."""
    base = Path(os.path.realpath(tmp_path_factory.mktemp("gate")))
    files = synthetic_files()
    repo = base / "repo"
    commit = make_repo(repo, files)
    receipt = json.dumps(s1_manifest_doc(files)).encode()
    s1_dir = base / "s1-ok"
    put(s1_dir / S1_MANIFEST_NAME, receipt)
    out = py(S2, "build", "--repository", repo, "--commit", commit, "--out", repo / EVIDENCE, *pins_args(files),
             "--s1-manifest", s1_dir / S1_MANIFEST_NAME, "--s1-manifest-sha256", sha(receipt))
    assert out.returncode == 0, out.stderr
    from conftest import git
    git(repo, "add", EVIDENCE)
    git(repo, "commit", "-q", "-m", "evidence")
    profile = json.dumps(profile_doc()).encode()
    return dict(base=base, repo=repo, commit=commit, files=files, receipt=receipt, s1=s1_dir / S1_MANIFEST_NAME,
                evidence_sha=sha((repo / EVIDENCE).read_bytes()), profile=profile)


def validate_cmd(w, result, code_root, *, s1=None, s1_sha=None, profile=None, profile_sha=None, repository=None,
                 code=None, declared=False):
    args = ["validate", "--repository", repository or w["repo"], "--commit", w["commit"], "--evidence-sha256",
            w["evidence_sha"], "--result", result, "--expect-blocks", "3900", "--expect-losses", "1",
            *pins_args(w["files"]), "--code-root", code or code_root,
            "--s1-manifest", s1 or w["s1"], "--s1-manifest-sha256", s1_sha or sha(w["receipt"])]
    if declared:
        args += ["--declared-default-profile"]
    else:
        args += ["--profile-json", profile, "--profile-json-sha256", profile_sha or sha(w["profile"])]
    return args


def run_audited(tmp_path, args):
    log = tmp_path / f"audit-{len(list(tmp_path.glob('audit-*')))}.jsonl"
    done = audited(log, S2, *args)
    return done, audit_events(log)


def inode(path):
    st = os.lstat(path)
    return st.st_dev, st.st_ino


import sys as _sys

# r4: the interpreter's own installation (sys.prefix chain). An interpreter that lives under a host job root (the e4v3
# venv: /mpac/sdicks02/jobs/clasher/e4v3-venv) is lstat'ed by Python's own start-up, before S2 runs; those events are
# not S2 accesses. Only that exact chain (ancestors and descendants of the prefixes) is exempt, nothing else.
_INTERPRETER = {os.path.realpath(_sys.prefix), _sys.prefix, os.path.realpath(_sys.base_prefix), _sys.base_prefix}


def interpreter_path(path):
    return any(path == d or path.startswith(d + "/") or d.startswith(path + "/") for d in _INTERPRETER)


def violations(events, canary_paths, canary_inodes, alias_paths=()):
    """Events that name a canary location (or any outcome/strict-END location), open a canary inode, or stat a canary
    inode through anything but an operator-named alias (the lstat that detects the alias is unavoidable metadata)."""
    bad = []
    roots = [str(p) for p in canary_paths]
    for e in events:
        names = e["argv"] if e["event"] == "subprocess.Popen" else [e.get("path")]
        for name in names:
            if not isinstance(name, str):
                continue
            norm = "/" + name.lstrip("/") if name.startswith("/") else name
            if e["event"] != "subprocess.Popen" and norm.startswith("/") and interpreter_path(norm) and \
                    not any(norm == r or norm.startswith(r + "/") for r in roots):
                continue
            if any(norm == r or norm.startswith(r + "/") for r in roots) or S2M.forbidden_reason(norm.replace(":", "/")):
                bad.append(e)
        if e["event"] == "opened" and (e["dev"], e["ino"]) in canary_inodes:
            bad.append(e)
        # r4: si's descriptor gate fstatat()s the operator-named alias by its leaf name relative to the gated parent
        # descriptor (dir_fd): the same single metadata look at the alias, never an open
        named = set(map(str, alias_paths)) | {os.path.basename(str(p)) for p in alias_paths if e.get("dir_fd")}
        if e["event"] == "stat-ok" and (e["dev"], e["ino"]) in canary_inodes and e["path"] not in named:
            bad.append(e)
    return bad


def refused(done, result, text):
    if Path(result).exists():
        r = json.loads(Path(result).read_text())
        assert done.returncode == 2 and r["ok"] is False and text in r["error"], r
        return r
    assert done.returncode == 2 and text in done.stderr, done.stderr
    return None


# ---------------------------------------------------------------- positive controls (canary bytes are valid inputs)

def test_valid_profile_and_receipt_accepted_with_recorded_source(world, code_root, tmp_path):
    """Control: the bytes used by every canary below pass when they sit at an allowed location."""
    path = put(tmp_path / "profiles" / "s4-profiles.json", world["profile"])
    done, events = run_audited(tmp_path, validate_cmd(world, tmp_path / "r.json", code_root, profile=path))
    assert done.returncode == 0, done.stdout + done.stderr
    r = json.loads((tmp_path / "r.json").read_text())
    assert r["ok"] is True and r["profile_source"] == "s4-bundles"
    assert r["profile_json_path"] == str(path) and r["profile_json_sha256"] == sha(world["profile"])
    assert r["hosts"]["127x03"]["profile"] == profile_doc()["127x03"]
    assert r["s1_manifest_path"] == str(world["s1"])
    assert violations(events, [], set()) == []


def test_declared_default_recorded(world, code_root, tmp_path):
    done = py(S2, *validate_cmd(world, tmp_path / "r.json", code_root, declared=True))
    r = json.loads((tmp_path / "r.json").read_text())
    assert done.returncode == 0 and r["profile_source"] == "declared-default"
    assert r["profile_json_path"] is None and r["profile_json_sha256"] is None
    assert r["hosts"]["127x04"]["profile"] == dict(host="127x04", reference_slot=0, slot_count=11, console_rule=False,
                                                   warmup_seconds=300.0, perception="none")


# ---------------------------------------------------------------- S2-R2-F1: forbidden locations, full entrypoints

PROFILE_CANARIES = ["reports/explore/k4s-confirm/end/end-raw.json",            # Sol r2 reproduction
                    "games/profile.json", "hub-blocks/profile.json", "complete.json", "x/complete-v2.json",
                    "x/interference.json", "x/end-raw-copy.json", "x/attempt-00.json", "x/END-FINAL-x.json",
                    "end/receipts/round-00/127x03/raw-00/reference-warmup.json",
                    "k4s-confirm-reporting-r1/reporting/profile.json", "t1-20261010-r1/profile.json",
                    "tests/fixtures/native_friendly_completed_15_535_86.json"]   # r4b: an E5 path; S2 grants no E5


@pytest.mark.parametrize("rel", PROFILE_CANARIES)
def test_validate_profile_at_forbidden_location_never_touched(world, code_root, tmp_path, rel):
    canary = put(tmp_path / "zoo" / rel, world["profile"])
    os.chmod(canary, 0)                                     # even a stray open would be EACCES, not a location refusal
    done, events = run_audited(tmp_path, validate_cmd(world, tmp_path / "r.json", code_root, profile=canary))
    refused(done, tmp_path / "r.json", "forbidden location")
    assert violations(events, [canary], {inode(canary)}) == []
    assert not any(e["event"] == "subprocess.Popen" for e in events)     # refused before git / the bootstrap


S1_CANARY_DIRS = ["games", "hub-blocks", "end", "reports/explore/k4s-confirm/end/receipts",
                  "k4s-confirm-reporting-r1/reporting", "t1-20261010-r1"]


@pytest.mark.parametrize("rel", S1_CANARY_DIRS)
def test_validate_s1_receipt_at_forbidden_location_never_touched(world, code_root, tmp_path, rel):
    canary = put(tmp_path / "zoo" / rel / S1_MANIFEST_NAME, world["receipt"])
    done, events = run_audited(tmp_path, validate_cmd(world, tmp_path / "r.json", code_root, s1=canary, declared=True))
    refused(done, tmp_path / "r.json", "forbidden location")
    assert violations(events, [canary], {inode(canary)}) == []


@pytest.mark.parametrize("rel", ["games", "end", "t1-20261010-r1"])
def test_build_s1_receipt_and_out_at_forbidden_location_never_touched(world, tmp_path, rel):
    canary = put(tmp_path / "zoo" / rel / S1_MANIFEST_NAME, world["receipt"])
    args = ["build", "--repository", world["repo"], "--commit", world["commit"], "--out", tmp_path / "e.json",
            *pins_args(world["files"]), "--s1-manifest", canary, "--s1-manifest-sha256", sha(world["receipt"])]
    done, events = run_audited(tmp_path, args)
    assert done.returncode == 2 and "forbidden location" in done.stderr and not (tmp_path / "e.json").exists()
    assert violations(events, [canary], {inode(canary)}) == []
    out_dir = tmp_path / "zoo2" / rel
    out_dir.mkdir(parents=True)
    args = ["build", "--repository", world["repo"], "--commit", world["commit"], "--out", out_dir / "e.json",
            *pins_args(world["files"]), "--s1-manifest", world["s1"], "--s1-manifest-sha256", sha(world["receipt"])]
    done, events = run_audited(tmp_path, args)
    assert done.returncode == 2 and "forbidden location" in done.stderr and os.listdir(out_dir) == []
    assert violations(events, [out_dir], set()) == []


def test_validate_and_diagnose_forbidden_repository_code_root_and_result(world, code_root, tmp_path):
    hidden = tmp_path / "zoo" / "hub-blocks" / "repo"
    shutil.copytree(world["repo"], hidden, symlinks=True)
    done, events = run_audited(tmp_path, validate_cmd(world, tmp_path / "r1.json", code_root, repository=hidden,
                                                      declared=True))
    refused(done, tmp_path / "r1.json", "forbidden location")
    assert violations(events, [hidden], set()) == [] and not any(e["event"] == "subprocess.Popen" for e in events)
    done, events = run_audited(tmp_path, ["diagnose-clock", "--test-mode", "--repository", hidden, "--commit",
                                          world["commit"], "--result", tmp_path / "d1.json"])
    refused(done, tmp_path / "d1.json", "forbidden location")
    assert violations(events, [hidden], set()) == [] and not any(e["event"] == "subprocess.Popen" for e in events)
    code = tmp_path / "zoo" / "games" / "code"
    shutil.copytree(code_root, code)
    done, events = run_audited(tmp_path, validate_cmd(world, tmp_path / "r2.json", code_root, code=code, declared=True))
    refused(done, tmp_path / "r2.json", "forbidden location")
    assert violations(events, [code], set()) == []
    end_dir = tmp_path / "zoo" / "end"
    end_dir.mkdir(parents=True, exist_ok=True)
    for args in (validate_cmd(world, end_dir / "r.json", code_root, declared=True),
                 ["diagnose-clock", "--test-mode", "--repository", world["repo"], "--commit", world["commit"],
                  "--result", end_dir / "d.json"]):
        done, events = run_audited(tmp_path, args)
        assert done.returncode == 2 and "forbidden location" in done.stderr and os.listdir(end_dir) == []
        assert violations(events, [end_dir], set()) == [] and not any(e["event"] == "subprocess.Popen" for e in events)


def s1_dest(world, root):
    """An S1 destination tree (sources + receipt) under `root`."""
    for rel, data in world["files"].items():
        if "/end-sources/" in rel:
            put(root / rel.split("/end-sources/")[1], data)
    put(root / S1_MANIFEST_NAME, world["receipt"])
    return root


@pytest.mark.parametrize("rel", ["games/dest", "end/dest", "k4s-confirm-replacement-r1/dest"])
def test_diagnose_s1_dest_at_forbidden_location_never_touched(world, tmp_path, rel):
    dest = s1_dest(world, tmp_path / "zoo" / rel)
    done, events = run_audited(tmp_path, ["diagnose-clock", "--test-mode", "--s1-dest", dest, "--s1-manifest",
                                          dest / S1_MANIFEST_NAME, "--s1-manifest-sha256", sha(world["receipt"]),
                                          "--result", tmp_path / "d.json"])
    refused(done, tmp_path / "d.json", "forbidden location")
    inodes = {inode(p) for p in dest.rglob("*") if p.is_file()}
    assert violations(events, [dest], inodes) == []


def test_diagnose_s1_receipt_must_be_the_dest_receipt(world, tmp_path):
    dest = s1_dest(world, tmp_path / "dest")
    done = py(S2, "diagnose-clock", "--test-mode", "--s1-dest", dest, "--s1-manifest", world["s1"],
              "--s1-manifest-sha256", sha(world["receipt"]), "--result", tmp_path / "d.json")
    refused(done, tmp_path / "d.json", "must be the receipt S1 wrote in --s1-dest")


def test_outside_allowed_root_never_touched(world, code_root, tmp_path):
    outside = "/var/tmp/k4s-s2-never-created/profile.json"
    done, events = run_audited(tmp_path, validate_cmd(world, tmp_path / "r.json", code_root, profile=outside))
    refused(done, tmp_path / "r.json", "outside its allowed root")
    assert violations(events, [outside, "/var/tmp/k4s-s2-never-created"], set()) == []
    assert not any(isinstance(e.get("path"), str) and e["path"].startswith("/var/tmp") for e in events)


@pytest.mark.parametrize("path", ["relative/profile.json", "{base}/ok/../ok/profile.json", "{base}//ok/profile.json",
                                  "{base}/ok/pro file.json"])
def test_unnormalised_paths_refused_unresolved(world, code_root, tmp_path, path):
    put(tmp_path / "ok" / "profile.json", world["profile"])
    path = path.format(base=tmp_path)
    done, events = run_audited(tmp_path, validate_cmd(world, tmp_path / "r.json", code_root, profile=path))
    refused(done, tmp_path / "r.json", "--profile-json")
    assert not any(e["event"] in ("opened", "stat-ok") and str(e.get("path", "")).endswith("profile.json")
                   for e in events)


def test_profile_and_receipt_name_rules(world, code_root, tmp_path):
    other = put(tmp_path / "s1" / "receipt.json", world["receipt"])
    done = py(S2, *validate_cmd(world, tmp_path / "r1.json", code_root, s1=other, declared=True))
    refused(done, tmp_path / "r1.json", "must be S1's s1-copy-manifest.json")
    text = put(tmp_path / "p" / "profile.txt", world["profile"])
    done = py(S2, *validate_cmd(world, tmp_path / "r2.json", code_root, profile=text))
    refused(done, tmp_path / "r2.json", "must be a .json file")


# ---------------------------------------------------------------- S2-R2-F1: hard-link and symlink canaries

def test_hard_linked_profile_refused_unopened(world, code_root, tmp_path):
    canary = put(tmp_path / "zoo" / "games" / "canary.json", world["profile"])
    alias = tmp_path / "ok" / "profile.json"
    alias.parent.mkdir()
    os.link(canary, alias)
    done, events = run_audited(tmp_path, validate_cmd(world, tmp_path / "r.json", code_root, profile=alias))
    refused(done, tmp_path / "r.json", "safe_input refused [nlink]")  # r4: si descriptor gate
    assert violations(events, [canary], {inode(canary)}, alias_paths=[alias]) == []


@pytest.mark.parametrize("entry", ["validate", "build", "diagnose"])
def test_hard_linked_s1_receipt_refused_unopened_every_entrypoint(world, code_root, tmp_path, entry):
    canary = put(tmp_path / "zoo" / "end" / "canary.json", world["receipt"])
    dest = s1_dest(world, tmp_path / "dest")
    alias = dest / S1_MANIFEST_NAME
    alias.unlink()
    os.link(canary, alias)
    receipt = ["--s1-manifest", alias, "--s1-manifest-sha256", sha(world["receipt"])]
    if entry == "validate":
        args = validate_cmd(world, tmp_path / "r.json", code_root, s1=alias, declared=True)
    elif entry == "build":
        args = ["build", "--repository", world["repo"], "--commit", world["commit"], "--out", tmp_path / "r.json",
                *pins_args(world["files"]), *receipt]
    else:
        args = ["diagnose-clock", "--test-mode", "--s1-dest", dest, *receipt, "--result", tmp_path / "r.json"]
    done, events = run_audited(tmp_path, args)
    if entry == "build":
        assert done.returncode == 2 and "safe_input refused [nlink]" in done.stderr and not (tmp_path / "r.json").exists()
    else:
        refused(done, tmp_path / "r.json", "safe_input refused [nlink]")  # r4: si descriptor gate
    assert violations(events, [canary], {inode(canary)}, alias_paths=[alias]) == []


def test_hard_linked_s1_dest_source_refused_unopened(world, tmp_path):
    canary = put(tmp_path / "zoo" / "games" / "mhz.jsonl", world["files"][STUDY + "/end-sources/127x04/reporting/mhz.jsonl"])
    dest = s1_dest(world, tmp_path / "dest")
    (dest / "127x04/reporting/mhz.jsonl").unlink()
    os.link(canary, dest / "127x04/reporting/mhz.jsonl")
    done, events = run_audited(tmp_path, ["diagnose-clock", "--test-mode", "--s1-dest", dest, "--s1-manifest",
                                          dest / S1_MANIFEST_NAME, "--s1-manifest-sha256", sha(world["receipt"]),
                                          "--result", tmp_path / "d.json"])
    refused(done, tmp_path / "d.json", "safe_input refused [nlink]")  # r4: si descriptor gate
    # the alias is lstat-ed through its parent descriptor (relative name), never opened
    assert violations(events, [canary], {inode(canary)}, alias_paths=["mhz.jsonl"]) == []


def test_hard_linked_worktree_artifact_refused_unopened(world, code_root, tmp_path):
    repo = tmp_path / "repo-copy"
    shutil.copytree(world["repo"], repo, symlinks=True)
    rel = STUDY + "/end-sources/127x03/reporting/census.jsonl"
    canary = put(tmp_path / "zoo" / "hub-blocks" / "census.jsonl", (repo / rel).read_bytes())
    (repo / rel).unlink()
    os.link(canary, repo / rel)
    done, events = run_audited(tmp_path, validate_cmd(world, tmp_path / "r.json", code_root, repository=repo,
                                                      code=code_root, declared=True))
    refused(done, tmp_path / "r.json", "safe_input refused [nlink]")  # r4: si descriptor gate
    assert violations(events, [canary], {inode(canary)}, alias_paths=["census.jsonl"]) == []


@pytest.mark.parametrize("kind", ["leaf", "ancestor"])
def test_symlinked_profile_refused_unresolved(world, code_root, tmp_path, kind):
    canary = put(tmp_path / "zoo" / "games" / "profile.json", world["profile"])
    if kind == "leaf":
        path = tmp_path / "ok" / "profile.json"
        path.parent.mkdir()
        os.symlink(canary, path)
    else:
        os.symlink(canary.parent, tmp_path / "linkdir")
        path = tmp_path / "linkdir" / "profile.json"
    done, events = run_audited(tmp_path, validate_cmd(world, tmp_path / "r.json", code_root, profile=path))
    # r4: si refuses a symlinked leaf ([symlink]) or a symlinked ancestor of the role root ([root]) unresolved
    refused(done, tmp_path / "r.json", "safe_input refused [symlink]" if kind == "leaf" else "safe_input refused [root]")
    assert violations(events, [canary], {inode(canary)}) == []
    if kind == "ancestor":                                  # nothing below the aliased component is ever named
        assert not any(isinstance(e.get("path"), str) and e["path"].startswith(str(path)) for e in events)


@pytest.mark.parametrize("entry", ["validate", "build", "diagnose"])
def test_symlinked_s1_receipt_refused_unresolved_every_entrypoint(world, code_root, tmp_path, entry):
    canary = put(tmp_path / "zoo" / "end" / S1_MANIFEST_NAME, world["receipt"])
    dest = s1_dest(world, tmp_path / "dest")
    alias = dest / S1_MANIFEST_NAME
    alias.unlink()
    os.symlink(canary, alias)
    receipt = ["--s1-manifest", alias, "--s1-manifest-sha256", sha(world["receipt"])]
    if entry == "validate":
        args = validate_cmd(world, tmp_path / "r.json", code_root, s1=alias, declared=True)
    elif entry == "build":
        args = ["build", "--repository", world["repo"], "--commit", world["commit"], "--out", tmp_path / "r.json",
                *pins_args(world["files"]), *receipt]
    else:
        args = ["diagnose-clock", "--test-mode", "--s1-dest", dest, *receipt, "--result", tmp_path / "r.json"]
    done, events = run_audited(tmp_path, args)
    if entry == "build":
        assert done.returncode == 2 and "symlink" in done.stderr and not (tmp_path / "r.json").exists()
    else:
        refused(done, tmp_path / "r.json", "symlink")
    assert violations(events, [canary], {inode(canary)}) == []


def test_symlinked_checkouts_dest_and_result_parent_refused_unresolved(world, code_root, tmp_path):
    os.symlink(world["repo"], tmp_path / "repo-link")
    done, events = run_audited(tmp_path, validate_cmd(world, tmp_path / "r1.json", code_root,
                                                      repository=tmp_path / "repo-link", declared=True))
    refused(done, tmp_path / "r1.json", "symlink")
    assert not any(e["event"] == "subprocess.Popen" for e in events)
    os.symlink(code_root.parent, tmp_path / "code-link")
    done, events = run_audited(tmp_path, validate_cmd(world, tmp_path / "r2.json", code_root, declared=True,
                                                      code=tmp_path / "code-link" / code_root.name))
    refused(done, tmp_path / "r2.json", "symlink")
    dest = s1_dest(world, tmp_path / "zoo" / "games" / "dest")
    os.symlink(dest, tmp_path / "dest-link")
    done, events = run_audited(tmp_path, ["diagnose-clock", "--test-mode", "--s1-dest", tmp_path / "dest-link",
                                          "--s1-manifest", tmp_path / "dest-link" / S1_MANIFEST_NAME,
                                          "--s1-manifest-sha256", sha(world["receipt"]), "--result", tmp_path / "d.json"])
    refused(done, tmp_path / "d.json", "symlink")
    assert violations(events, [dest], {inode(p) for p in dest.rglob("*")}) == []
    target = tmp_path / "zoo" / "end"
    target.mkdir(parents=True, exist_ok=True)
    os.symlink(target, tmp_path / "out-link")
    done, events = run_audited(tmp_path, validate_cmd(world, tmp_path / "out-link" / "r.json", code_root, declared=True))
    assert done.returncode == 2 and "symlink" in done.stderr and os.listdir(target) == []
    assert violations(events, [target], set()) == []


def test_gate_to_open_identity(world, tmp_path, monkeypatch):
    """r4: gate_paths keeps the si-gated descriptor open and read_gated consumes THAT descriptor: a file replaced
    (new inode) after the gate is never read; the gated inode's bytes are, and only with the expected SHA-256."""
    monkeypatch.setenv("K4S_S2_TEST_ROOT", str(Path(os.path.realpath(tmp_path)).parent))
    path = put(tmp_path / "p" / "profile.json", world["profile"])
    roots = S2M.Roots(True)
    gated = S2M.gate_paths([("--profile-json", str(path), roots.prep, "file", S2M.json_name)])
    put(tmp_path / "p" / "new.json", b'{"replaced": true}')
    os.replace(tmp_path / "p" / "new.json", path)
    assert S2M.read_gated(gated["--profile-json"], "profile JSON", sha(world["profile"])) == world["profile"]
    gated = S2M.gate_paths([("--profile-json", str(path), roots.prep, "file", S2M.json_name)])
    with pytest.raises(S2M.S2Error, match="profile JSON SHA mismatch"):
        S2M.read_gated(gated["--profile-json"], "profile JSON", sha(world["profile"]), "profile JSON SHA mismatch")


# ---------------------------------------------------------------- the lexical gate itself: pure, production roots

class Syscall(Exception):
    """A filesystem call reached before the lexical refusal."""


@contextlib.contextmanager
def forbid_syscalls():
    """Any stat/open/listdir inside the block raises Syscall; restored BEFORE pytest reports (it stats files)."""
    names = ("lstat", "stat", "open", "listdir", "scandir")
    saved, saved_open, calls = {n: getattr(os, n) for n in names}, builtins.open, []

    def trap(name):
        def call(*args, **kwargs):
            calls.append((name, args))
            raise Syscall(f"{name}{args} before the lexical refusal")
        return call
    try:
        for name in names:
            setattr(os, name, trap("os." + name))
        builtins.open = trap("open")
        yield calls
    finally:
        for name, function in saved.items():
            setattr(os, name, function)
        builtins.open = saved_open


@pytest.fixture
def no_syscalls(monkeypatch):
    """Production roots (no test root); the tests run the gate inside forbid_syscalls(): it must be pure."""
    monkeypatch.delenv("K4S_S2_TEST_ROOT", raising=False)
    return S2M.Roots(False)


def refused_purely(call, message):
    with forbid_syscalls() as calls:
        with pytest.raises(S2M.S2Error, match=message):
            call()
    assert calls == []


@pytest.mark.parametrize("path,role,message", [
    ("/mpac/sdicks02/jobs/clasher/t1-20261010-r1/x.json", "prep", "forbidden location"),
    ("/mpac/sdicks02/jobs-k4s/k4s-confirm-reporting-r1/reporting/mhz.jsonl", "prep", "forbidden location"),
    ("/mpac/sdicks02/jobs/clasher/e4v3-venv/profile.json", "prep", "host job tree"),
    ("/mpac/sdicks02/jobs-k4s/x.json", "prep", "host job tree"),
    ("/mpac/sdicks02/repos/clasher/reports/explore/k4s-confirm/end/end-raw.json", "prep", "forbidden location"),
    ("/mpac/sdicks02/k4s-runner/run-r1/end-prep/games/s1-copy-manifest.json", "prep", "forbidden location"),
    ("/mpac/sdicks02/k4s-runner/run-r1/end-prep/b2/hub-blocks/p.json", "prep", "forbidden location"),
    ("/mpac/sdicks02/k4s-runner/run-r1/end-prep/b2/interference.json", "prep", "forbidden location"),
    ("/mpac/sdicks02/k4s-runner/run-r1/hub-view/profile.json", "prep", "outside its allowed root"),
    ("/mpac/sdicks02/k4s-runner/run-r1/end-prep", "prep", "outside its allowed root"),
    ("/mpac/sdicks02/k4s-runner/run-r1/end-prep/../hub-view/p.json", "prep", "not an absolute normalised path"),
    ("relative/p.json", "prep", "not an absolute normalised path"),
    ("/tmp/pytest-of-x/p.json", "prep", "outside its allowed root"),
    ("/mpac/sdicks02/repos/other", "checkout", "outside its allowed root"),
    ("/tmp/k4s-s2-check/sub", "checkout", "outside its allowed root"),
    ("/tmp/games", "checkout", "forbidden location"),
    ("/tmp/k4s-s2-t1-x", "checkout", None),
    ("/mpac/sdicks02/repos/clasher", "checkout", None),
    ("/tmp/k4s-s2-check", "checkout", None),
    ("/mpac/sdicks02/k4s-runner/run-r1/end-prep/b2-copy-r1/end-sources/s1-copy-manifest.json", "prep", None),
])
def test_lexical_gate_production_roots(no_syscalls, path, role, message):
    allowed = getattr(no_syscalls, role)
    if message is None:
        with forbid_syscalls() as calls:
            S2M.lexical(path, "--x")
            assert allowed(path)
        assert calls == []
        return
    refused_purely(lambda: S2M.gate_paths([("--x", path, allowed, "file", None)]), message)


def test_every_path_is_lexically_gated_before_any_is_stated(no_syscalls):
    """A valid first path is not lstat-ed before a forbidden second path is refused."""
    refused_purely(lambda: S2M.gate_paths([
        ("--repository", "/mpac/sdicks02/repos/clasher", no_syscalls.checkout, "dir", None),
        ("--profile-json", "/mpac/sdicks02/k4s-runner/run-r1/end-prep/end/p.json", no_syscalls.prep, "file",
         S2M.json_name)]), "forbidden location")


def namespace(command, **overrides):
    base = dict(command=command, test_mode=False, repository="/mpac/sdicks02/repos/clasher", commit="0" * 40,
                code_root=None, out="/mpac/sdicks02/repos/clasher/" + EVIDENCE, s1_manifest=None,
                s1_manifest_sha256=None, profile_json=None, profile_json_sha256=None, declared_default_profile=True,
                evidence_sha256="0" * 64, result=None, s1_dest=None, git_dir=None, git_common_dir=None)
    base.update({name: None for name in S2M.TEST_ONLY_OPTIONS + ("no_manifest_check",)})
    base.update(overrides)
    return argparse.Namespace(**base)


@pytest.mark.parametrize("out", ["/tmp/k4s-s2-build/reports/explore/k4s-confirm/end-evidence.json",
                                 "/mpac/sdicks02/repos/clasher/reports/explore/k4s-confirm/other.json",
                                 "/mpac/sdicks02/k4s-runner/run-r1/end-prep/end-evidence.json"])
def test_production_build_out_is_the_evidence_path_of_the_repository(no_syscalls, out):
    a = namespace("build", out=out, s1_manifest="/mpac/sdicks02/k4s-runner/run-r1/end-prep/b2/" + S1_MANIFEST_NAME)
    refused_purely(lambda: S2M.build(a, S2M.Mode(a)), "--out: outside its allowed root")


def test_production_validate_gates_profile_before_any_access(no_syscalls):
    a = namespace("validate", s1_manifest="/mpac/sdicks02/k4s-runner/run-r1/end-prep/b2/" + S1_MANIFEST_NAME,
                  declared_default_profile=False, profile_json_sha256="0" * 64,
                  profile_json="/mpac/sdicks02/repos/clasher/reports/explore/k4s-confirm/end/end-raw.json")
    refused_purely(lambda: S2M.validate(a, S2M.Mode(a), {}), "forbidden location")


def test_test_root_must_be_below_tmp(monkeypatch):
    for value, message in (("/mpac/sdicks02", "strictly below /tmp/"), ("/tmp/x/games", "forbidden location"),
                           ("tmp/x", "not an absolute")):
        monkeypatch.setenv("K4S_S2_TEST_ROOT", value)
        with pytest.raises(S2M.S2Error, match=message):
            S2M.Roots(True)
    monkeypatch.delenv("K4S_S2_TEST_ROOT")
    with pytest.raises(S2M.S2Error, match="test mode requires K4S_S2_TEST_ROOT"):
        S2M.Roots(True)


# ---------------------------------------------------------------- S2-R2-F2: strict profile contents, no fallback

def drop(key):
    return lambda p: p.pop(key)


def setv(key, value):
    return lambda p: p.__setitem__(key, value)


BAD_PROFILES = {
    "empty-objects": (profile_doc(**{"127x03": {}, "127x04": {}}), "must be a non-empty JSON object"),   # Sol r2
    "null-values": (profile_doc(**{"127x03": None, "127x04": None}), "must be a non-empty JSON object"),  # Sol r2
    "list-value": (profile_doc(**{"127x04": []}), "must be a non-empty JSON object"),
    "string-value": (profile_doc(**{"127x04": "default"}), "must be a non-empty JSON object"),
    "number-value": (profile_doc(**{"127x04": 0}), "must be a non-empty JSON object"),
    "true-value": (profile_doc(**{"127x04": True}), "must be a non-empty JSON object"),
    "missing-host-key": ({"127x03": profile_doc()["127x03"]}, "exactly the counted hosts"),
    "extra-host-key": (dict(profile_doc(), **{"127x05": profile_doc()["127x03"]}), "exactly the counted hosts"),
    "top-level-list": ([profile_doc()["127x03"]], "exactly the counted hosts"),
    "host-mismatch": (profile_doc(**{"127x04": setv("host", "127x03")}), "profile host differs"),
    "host-int": (profile_doc(**{"127x04": setv("host", 4)}), "profile host differs"),
    "unknown-field": (profile_doc(**{"127x03": setv("slots", 11)}), "unknown fields"),
    "slot-1": (profile_doc(**{"127x03": setv("reference_slot", 1)}), "reference_slot must be the integer 0"),
    "slot-bool": (profile_doc(**{"127x03": setv("reference_slot", False)}), "reference_slot must be the integer 0"),
    "slot-float": (profile_doc(**{"127x03": setv("reference_slot", 0.0)}), "reference_slot must be the integer 0"),
    "slot-str": (profile_doc(**{"127x03": setv("reference_slot", "0")}), "reference_slot must be the integer 0"),
    "count-10": (profile_doc(**{"127x04": setv("slot_count", 10)}), "slot_count must be the integer 11"),
    "count-8": (profile_doc(**{"127x04": setv("slot_count", 8)}), "slot_count must be the integer 11"),
    "count-float": (profile_doc(**{"127x04": setv("slot_count", 11.0)}), "slot_count must be the integer 11"),
    "console-true": (profile_doc(**{"127x04": setv("console_rule", True)}), "console_rule must be the Boolean false"),
    "console-int": (profile_doc(**{"127x04": setv("console_rule", 0)}), "console_rule must be the Boolean false"),
    "console-str": (profile_doc(**{"127x04": setv("console_rule", "false")}), "console_rule must be the Boolean false"),
    "warmup-299": (profile_doc(**{"127x03": setv("warmup_seconds", 299.9)}), "warmup_seconds must be a finite number"),
    "warmup-str": (profile_doc(**{"127x03": setv("warmup_seconds", "300")}), "warmup_seconds must be a finite number"),
    "warmup-bool": (profile_doc(**{"127x03": setv("warmup_seconds", True)}), "warmup_seconds must be a finite number"),
    "warmup-null": (profile_doc(**{"127x03": setv("warmup_seconds", None)}), "warmup_seconds must be a finite number"),
    "perception": (profile_doc(**{"127x03": setv("perception", "full")}), 'perception must be "none"'),
    "perception-null": (profile_doc(**{"127x03": setv("perception", None)}), 'perception must be "none"'),
    "extra-plan-int": (profile_doc(**{"127x03": setv("plan", 1)}), "plan must be a non-empty str"),
    "extra-guard-empty": (profile_doc(**{"127x03": setv("guard", {})}), "guard must be a non-empty dict"),
    **{f"missing-{k}": (profile_doc(**{"127x04": drop(k)}), f"lacks ['{k}']")
       for k in ("host", "reference_slot", "slot_count", "console_rule", "warmup_seconds", "perception")},
}


@pytest.mark.parametrize("name", sorted(BAD_PROFILES))
def test_malformed_profile_refused_no_fallback(world, code_root, tmp_path, name):
    doc, message = BAD_PROFILES[name]
    data = json.dumps(doc).encode()
    path = put(tmp_path / "p" / "profile.json", data)
    done = py(S2, *validate_cmd(world, tmp_path / "r.json", code_root, profile=path, profile_sha=sha(data)))
    r = refused(done, tmp_path / "r.json", message)
    assert "profile_source" not in r and "hosts" not in r


@pytest.mark.parametrize("raw,message", [
    (b'{"127x03": {"host": "127x03", "host": "127x03"}}', "[json]: duplicate key"),      # r4: si.loads_strict
    (json.dumps(profile_doc()).replace('"warmup_seconds": 300', '"warmup_seconds": NaN', 1).encode(), "non-finite"),
    (json.dumps(profile_doc()).replace('"warmup_seconds": 300', '"warmup_seconds": Infinity', 1).encode(), "non-finite"),
    (b"{not json", "safe_input refused [json]")])
def test_profile_json_strict_parse(world, code_root, tmp_path, raw, message):
    path = put(tmp_path / "p" / "profile.json", raw)
    done = py(S2, *validate_cmd(world, tmp_path / "r.json", code_root, profile=path, profile_sha=sha(raw)))
    refused(done, tmp_path / "r.json", message)


def test_profile_source_choice_is_exactly_one(world, code_root, tmp_path):
    path = put(tmp_path / "p" / "profile.json", world["profile"])
    both = validate_cmd(world, tmp_path / "r1.json", code_root, profile=path) + ["--declared-default-profile"]
    refused(py(S2, *both), tmp_path / "r1.json", "exactly one of --profile-json")
    neither = [x for x in validate_cmd(world, tmp_path / "r2.json", code_root, declared=True)
               if x != "--declared-default-profile"]
    refused(py(S2, *neither), tmp_path / "r2.json", "exactly one of --profile-json")
    sha_only = neither[:]
    sha_only[sha_only.index("--result") + 1] = tmp_path / "r3.json"
    refused(py(S2, *sha_only, "--declared-default-profile", "--profile-json-sha256", "0" * 64), tmp_path / "r3.json",
            "go together")
    wrong = validate_cmd(world, tmp_path / "r4.json", code_root, profile=path, profile_sha="0" * 64)
    refused(py(S2, *wrong), tmp_path / "r4.json", "profile JSON SHA mismatch")


def test_accepted_warmup_variants_follow_the_frozen_rule(world, code_root, tmp_path):
    """>= 300, finite, int or float (fleet_profile.py:27): 300.0 and 600 pass and are reported as given."""
    doc = profile_doc(**{"127x03": setv("warmup_seconds", 300.0), "127x04": setv("warmup_seconds", 600)})
    for extra in ("plan", "end_evidence", "guard"):
        doc["127x04"].pop(extra)
    data = json.dumps(doc).encode()
    path = put(tmp_path / "p" / "profile.json", data)
    done = py(S2, *validate_cmd(world, tmp_path / "r.json", code_root, profile=path, profile_sha=sha(data)))
    r = json.loads((tmp_path / "r.json").read_text())
    assert done.returncode == 0 and r["ok"] is True, r
    assert r["hosts"]["127x04"]["profile"]["warmup_seconds"] == 600 and r["profile_json_sha256"] == sha(data)


def test_check_profile_never_completes_from_defaults():
    with pytest.raises(S2M.S2Error, match="non-empty JSON object"):
        S2M.check_profile({}, "127x03", "unit")
    with pytest.raises(S2M.S2Error, match="lacks"):
        S2M.check_profile(dict(host="127x03"), "127x03", "unit")
    good = profile_doc()["127x03"]
    assert S2M.check_profile(good, "127x03", "unit") is good


# ---------------------------------------------------------------- every descriptor helper is lexically gated first

ANYWHERE = lambda path: True                                # r4: the r3 descriptor helpers are gone; every access
                                                            # is a gate_paths role, so the gate itself is exercised


@pytest.mark.parametrize("call", [
    lambda: S2M.gate_paths([("--d", "/tmp/k4s-s2-x/games", ANYWHERE, "dir", None)]),
    lambda: S2M.gate_paths([("--d", "/mpac/sdicks02/jobs/clasher/t1-20261010-r1", ANYWHERE, "dir", None)]),
    lambda: S2M.gate_paths([("--f", "/mpac/sdicks02/repos/clasher/reports/explore/k4s-confirm/end/end-raw.json",
                             ANYWHERE, "file", None)]),
    lambda: S2M.gate_paths([("--f", "/mpac/sdicks02/repos/clasher/x/hub-blocks/b.json", ANYWHERE, "file", None)]),
    lambda: S2M.gate_paths([("--f", "/tmp/k4s-s2-x/end/x.json", ANYWHERE, "file", None)]),
    lambda: S2M.gate_paths([("--o", "/mpac/sdicks02/k4s-runner/run-r1/end-prep/b2/complete.json", ANYWHERE, "new",
                             None)]),
    lambda: S2M.gate_paths([("--o", "/mpac/sdicks02/k4s-runner/run-r1/end-prep/games/r.json", ANYWHERE, "new", None)]),
    lambda: S2M.repo_relative("x/END-final-copy.json", "rel"),
    lambda: S2M.repo_relative("x/Attempt-00.JSON", "rel")])
def test_descriptor_helpers_refuse_forbidden_locations_before_any_syscall(no_syscalls, call):
    refused_purely(call, "forbidden location")


# ---------------------------------------------------------------- S1 receipt contents (typed rows, strict JSON)

@pytest.mark.parametrize("change,message", [
    (lambda d: d["files"][0].__setitem__("local_size", "12"), "wrong type"),
    (lambda d: d["meta"][0].__setitem__("host", "../x"), "unsafe host/phase"),
    (lambda d: d["files"][0].pop("remote_sha256_after"), "rows are malformed"),
    (lambda d: d.__setitem__("files", {}), "rows are malformed"),
    (lambda d: d.__setitem__("meta", [None]), "rows are malformed")])
def test_malformed_s1_receipt_rows_refused(world, code_root, tmp_path, change, message):
    doc = json.loads(world["receipt"])
    change(doc)
    data = json.dumps(doc).encode()
    path = put(tmp_path / "s1" / S1_MANIFEST_NAME, data)
    done = py(S2, *validate_cmd(world, tmp_path / "r.json", code_root, s1=path, s1_sha=sha(data), declared=True))
    refused(done, tmp_path / "r.json", message)


def test_s1_receipt_duplicate_key_refused(world, code_root, tmp_path):
    data = world["receipt"].replace(b'"status": "copied"', b'"status": "refused", "status": "copied"', 1)
    assert data != world["receipt"]
    path = put(tmp_path / "s1" / S1_MANIFEST_NAME, data)
    done = py(S2, *validate_cmd(world, tmp_path / "r.json", code_root, s1=path, s1_sha=sha(data), declared=True))
    refused(done, tmp_path / "r.json", "[json]: duplicate key")      # r4: si.loads_strict


def test_load_s1_direct_call_at_end_namespace_refused_purely(world, tmp_path):
    """Sol r2 reproduction 2: unmodified load_s1(testing=False) on a production-schema receipt at the END namespace.
    Even called directly (bypassing gate_paths), the descriptor helpers refuse it before any system call."""
    data = json.dumps(s1_manifest_doc(world["files"], schema="clasher.k4s.end-sources-copy.v2")).encode()
    canary = put(tmp_path / "repo" / STUDY / "end" / "end-raw.json", data)
    gated = (str(canary), os.lstat(canary))                 # the test's lstat, not S2's
    mode = type("M", (), dict(testing=False))()
    pairs = [("127x03", "reporting"), ("127x03", "replacement-r1"), ("127x04", "reporting")]
    refused_purely(lambda: S2M.load_s1(gated, sha(data), mode, pairs), "forbidden location")


@pytest.mark.parametrize("kind", ["profile-wrong-sha", "profile-bad-content", "receipt-wrong-sha", "receipt-bad-schema"])
def test_forbidden_location_refused_before_a_later_sha_or_schema_refusal(world, code_root, tmp_path, kind):
    """The location refusal comes first even when the SHA or the schema would refuse later: never 'SHA mismatch'
    or a schema error, and the canary is never touched."""
    if kind.startswith("profile"):
        data = world["profile"] if kind.endswith("sha") else b'{"127x03": {}, "127x04": null}'
        canary = put(tmp_path / "zoo" / "reports/explore/k4s-confirm/end/end-raw.json", data)
        args = validate_cmd(world, tmp_path / "r.json", code_root, profile=canary,
                            profile_sha="0" * 64 if kind.endswith("sha") else sha(data))
    else:
        data = world["receipt"] if kind.endswith("sha") else b'{"schema": "not-an-s1-receipt"}'
        canary = put(tmp_path / "zoo" / "end" / S1_MANIFEST_NAME, data)
        args = validate_cmd(world, tmp_path / "r.json", code_root, s1=canary, declared=True,
                            s1_sha="0" * 64 if kind.endswith("sha") else sha(data))
    done, events = run_audited(tmp_path, args)
    r = refused(done, tmp_path / "r.json", "forbidden location")
    assert "SHA" not in r["error"] and "schema" not in r["error"]
    assert violations(events, [canary], {inode(canary)}) == []
