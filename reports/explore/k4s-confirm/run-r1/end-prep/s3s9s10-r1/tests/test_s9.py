"""S9: locate on REAL 05 bytes (read only), one REAL build of origin/main, every refusal path."""
import json
import os
import shutil
from pathlib import Path

import pytest

from conftest import CLASHER, S9, commit_files, head, make_writable_copy, py

REAL_SOURCES = [s for s in S9.DEFAULT_SOURCES if Path(s).is_dir()]


def test_locate_real_05_sources_finds_all_33():
    if not REAL_SOURCES:
        pytest.skip("real 05 sources absent")
    result = py("s9_end_runtime.py", "locate", "--repository", CLASHER, "--commit", head())
    assert result.returncode == 0, result.stdout + result.stderr
    assert "locate: 33/33 found; missing 0" in result.stdout
    assert result.stdout.count("\nFOUND ") + result.stdout.startswith("FOUND ") == 33


def fake_sources(tmp_path, drop=(), wrong=(), in_games=(), link=()):
    """A source tree holding the 33 externals (copied from the real T1 candidate runtime) with variations."""
    pins = json.loads(S9.show(CLASHER, head(), S9.RUNTIME_PIN_REL))["files"]
    real = Path(S9.DEFAULT_SOURCES[1]) / "runtime"
    src = tmp_path / "src"
    for name in sorted(S9.EXTERNAL):
        if name in drop:
            continue
        target = src / ("games/x/" if name in in_games else "nested/") / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if name in link:
            target.symlink_to(real / name)
            continue
        data = (real / name).read_bytes()
        target.write_bytes(data + b"#" if name in wrong else data)
        assert S9.sha_bytes(data) == pins[name]
    (src / "overlay.tar").write_bytes(b"not opened")
    return src


@pytest.mark.parametrize("variant", ["drop", "wrong", "in_games", "link"])
def test_locate_missing_is_reported_and_exit_3(tmp_path, variant):
    if not REAL_SOURCES:
        pytest.skip("real 05 sources absent")
    name = "student-source/exit_r3/train.py"
    src = fake_sources(tmp_path, **{variant: (name,)})
    out = tmp_path / "locate.json"
    result = py("s9_end_runtime.py", "locate", "--repository", CLASHER, "--commit", head(), "--source", src,
                "--json", out)
    assert result.returncode == 3
    assert f"MISSING  947f8147e44c  {name}" in result.stdout and "STOP" in result.stdout
    doc = json.loads(out.read_text())
    assert doc["missing"] == [name] and doc["found"] == 32 and doc["archives_not_searched"] == [str(src / "overlay.tar")]
    if variant == "wrong":
        assert [c["matches"] for c in doc["files"][[f["path"] for f in doc["files"]].index(name)]["candidates"]] == [False]


def test_build_refuses_missing_pin_and_leaves_nothing(tmp_path):
    out = tmp_path / "rt"
    (tmp_path / "empty").mkdir()
    result = py("s9_end_runtime.py", "build", "--repository", CLASHER, "--commit", head(), "--out", out,
                "--source", tmp_path / "empty")
    assert result.returncode == 3 and "S9 STOP (missing pins)" in result.stderr
    assert not out.exists() and not Path(str(out) + ".partial").exists()


def test_build_refuses_commit_before_133f3ae4(tmp_path):
    before = S9.git(CLASHER, "rev-parse", S9.BASE_COMMIT + "^").strip()
    result = py("s9_end_runtime.py", "build", "--repository", CLASHER, "--commit", before, "--out", tmp_path / "rt")
    assert result.returncode == 2 and "133f3ae4" in result.stderr


@pytest.mark.parametrize("commit", ["origin/main", "abc", "0" * 40])
def test_build_refuses_bad_commit(tmp_path, commit):
    result = py("s9_end_runtime.py", "build", "--repository", CLASHER, "--commit", commit, "--out", tmp_path / "rt")
    assert result.returncode == 2


def test_build_refuses_existing_out(tmp_path):
    (tmp_path / "rt.partial").mkdir()
    result = py("s9_end_runtime.py", "build", "--repository", CLASHER, "--commit", head(), "--out", tmp_path / "rt")
    assert result.returncode == 2 and "must not exist" in result.stderr


def test_real_build_manifest(runtime_build):
    manifest = json.loads((runtime_build / "runtime-manifest.json").read_text())
    root = runtime_build / "runtime"
    assert manifest["commit"] == head() and manifest["k4s_manifest_sha256"] == S9.K4S_MANIFEST_SHA
    assert manifest["measurement_files_sha256"] == S9.MEASUREMENT_SHA
    assert manifest["frozen_runtime_files_equal"] is True and manifest["frozen_check"]["optimize"] == 0
    assert manifest["frozen_check"]["prepare_bundle"].endswith("/e4v3/prepare_bundle.py")
    assert S9.canonical_sha(manifest["runtime_files"]) == manifest["runtime_files_sha256"]
    assert len(manifest["externals"]) == 33 and all(e["source_path"].startswith("/mpac/sdicks02/") for e in manifest["externals"])
    assert manifest["dereferenced_symlinks"] == [dict(path="visualize_battle.py", target="examples/visualize_battle.py",
                                                      sha256=S9.sha_file(root / "examples/visualize_battle.py"))]
    tracked = int(S9.git(CLASHER, "ls-tree", "-r", head()).count("\n"))
    assert manifest["inventory_files"] == tracked + 33
    assert not any(os.lstat(root / p).st_mode & 0o222 for p in list(manifest["inventory"]["files"])[:200])
    for entry in manifest["externals"]:
        assert S9.sha_file(root / entry["path"]) == entry["sha256"]
    assert {r["path"] for r in manifest["tracked_pin_sha_differs_from_git"]} >= {"engine-rs/src/scripts.rs"}


def test_verify_ok_and_detects_tamper(runtime_build, tmp_path):
    assert py("s9_end_runtime.py", "verify", "--out", runtime_build, "--frozen").returncode == 0
    copy = make_writable_copy(runtime_build, tmp_path / "copy")
    (copy / "runtime/reports/explore/s1/anchor.py").write_bytes(b"# tampered\n")
    result = py("s9_end_runtime.py", "verify", "--out", copy)
    assert result.returncode == 2 and "inventory" in result.stderr


def test_frozen_runtime_pins_refuses_incomplete_runtime(runtime_build, tmp_path):
    copy = make_writable_copy(runtime_build / "runtime", tmp_path / "rt")
    (copy / "student-source/exit_r3/train.py").unlink()
    with pytest.raises(S9.Refusal, match="Incomplete frozen runtime"):
        S9.frozen_check(copy, S9.DEFAULT_PYTHON if os.path.exists(S9.DEFAULT_PYTHON) else "python3")
    with pytest.raises(S9.Refusal, match="Incomplete frozen runtime"):
        S9.runtime_files(copy)


def test_frozen_manifest_check_refuses_changed_pinned_file(runtime_build, tmp_path):
    copy = make_writable_copy(runtime_build / "runtime", tmp_path / "rt")
    target = copy / S9.E4V3_REL / "fleet_validity.py"
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(S9.Refusal, match="K4S-pinned file differs"):
        S9.frozen_check(copy, S9.DEFAULT_PYTHON if os.path.exists(S9.DEFAULT_PYTHON) else "python3")


def test_equivalence(scratch):
    repo, base = scratch["repo"], scratch["base"]
    data_only = commit_files(repo, base, {"reports/explore/k4s-confirm/end/END-JOB.json": b"{}\n"}, "endjob")
    ok = py("s9_end_runtime.py", "equivalence", "--repository", repo, "--runtime-commit", base,
            "--end-job-commit", data_only)
    assert ok.returncode == 0 and '"runtime_files_and_k4s_pins_equal": true' in ok.stdout
    for name, files in (("py", {"reports/explore/k4s-confirm/new_module.py": b"x = 1\n"}),
                        ("md", {"reports/explore/k4s-confirm/mac/K4S-MAC-PROCEDURE.md": b"changed\n"}),
                        ("pin", {"decks.json": b"[]\n"})):
        child = commit_files(repo, data_only, files, name)
        bad = py("s9_end_runtime.py", "equivalence", "--repository", repo, "--runtime-commit", base,
                 "--end-job-commit", child)
        assert bad.returncode == 2 and "runtime-relevant" in bad.stderr, name
    reverse = py("s9_end_runtime.py", "equivalence", "--repository", repo, "--runtime-commit", data_only,
                 "--end-job-commit", base)
    assert reverse.returncode == 2 and "ancestor" in reverse.stderr


def test_export_refuses_escaping_symlink(tmp_path):
    with pytest.raises(S9.Refusal):
        S9.safe_rel("../x")
    with pytest.raises(S9.Refusal):
        S9.safe_rel("/abs")



@pytest.mark.parametrize("module,needle", [(S9.K4S_MAC_REL + "/k4s_logic.py", "K4S-pinned file differs"),
                                           (S9.E4V3_REL + "/prepare_bundle.py", "42b8986d")])
def test_closure_verified_before_any_import(runtime_build, tmp_path, module, needle):
    """A tampered verifier (no-op verify_pinned + a canary write) is refused by stdlib BEFORE it can execute."""
    copy = make_writable_copy(runtime_build / "runtime", tmp_path / "rt")
    canary = tmp_path / "canary"
    target = copy / module
    target.write_bytes(target.read_bytes() + f"\nopen({str(canary)!r}, 'w').write('ran')\n"
                       "verify_pinned = lambda *a, **k: None\nruntime_pins = lambda root: {}\n".encode())
    with pytest.raises(S9.Refusal, match=needle):
        S9.frozen_check(copy, S9.DEFAULT_PYTHON if os.path.exists(S9.DEFAULT_PYTHON) else "python3")
    assert not canary.exists()


def test_build_out_must_be_permitted(foreign_dir):
    for out in (foreign_dir / "rt", "relative/out"):
        result = py("s9_end_runtime.py", "build", "--repository", CLASHER, "--commit", head(), "--out", out)
        assert result.returncode == 2 and "--out" in result.stderr
    assert os.listdir(foreign_dir) == [] and not os.path.exists("relative")


def test_build_out_with_symlinked_ancestor(tmp_path):
    (tmp_path / "real").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "real")
    result = py("s9_end_runtime.py", "build", "--repository", CLASHER, "--commit", head(), "--out",
                tmp_path / "link" / "rt")
    assert result.returncode == 2 and "symlinked ancestor" in result.stderr and os.listdir(tmp_path / "real") == []


def test_locate_refuses_symlinked_source_root(tmp_path):
    (tmp_path / "real").mkdir()
    (tmp_path / "alias").symlink_to(tmp_path / "real")
    result = py("s9_end_runtime.py", "locate", "--repository", CLASHER, "--commit", head(), "--source",
                tmp_path / "alias", "--json", tmp_path / "l.json")
    doc = json.loads((tmp_path / "l.json").read_text())
    assert result.returncode == 3 and doc["unreadable_sources"] == [str(tmp_path / "alias")] and doc["found"] == 0
