"""S2 END evidence builder + validator + clock diagnosis (r3) on a synthetic committed repository, using the REAL
frozen code (exported from origin/main) through S2's stdlib-only bootstrap."""
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from conftest import (S1_MANIFEST_NAME, S2, S2_ENV, STUDY, audit_events, audited, git, git_call, pins_args,
                      production_env, py, s1_manifest_doc, sha, si_shown_paths, write_s1_manifest)

EVIDENCE = STUDY + "/end-evidence.json"
E4V3 = "reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3"
NOT_ALLOWED = ("games", "complete.json", "hub-blocks")


def load_s2():
    spec = importlib.util.spec_from_file_location("s2_under_test", S2)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def s1_args(tmp, files, doc=None, name="s1"):
    return write_s1_manifest(Path(tmp) / name, doc or s1_manifest_doc(files))


def build(repo, commit, files, *extra, out=None, s1=True):
    args = ["build", "--repository", repo, "--commit", commit, "--out", out or repo / EVIDENCE, *pins_args(files)]
    if s1:
        args += s1_args(repo.parent, files, name=f"s1-build-{len(os.listdir(repo.parent))}")
    return py(S2, *args, *extra)


def commit_evidence(repo):
    git(repo, "add", EVIDENCE)
    git(repo, "commit", "-q", "-m", "evidence")


def validate_args(repo, commit, files, evidence_sha, result, code_root, *extra, s1=None, profile=None):
    s1 = s1 if s1 is not None else s1_args(Path(result).parent, files, name=Path(result).name + ".s1")
    profile = ["--declared-default-profile"] if profile is None else profile
    return ["validate", "--repository", repo, "--commit", commit, "--evidence-sha256", evidence_sha,
            "--result", result, "--expect-blocks", "3900", "--expect-losses", "1", *pins_args(files), *s1,
            "--code-root", code_root, *profile, *extra]


def validate(repo, commit, files, evidence_sha, result, code_root, *extra, s1=None, profile=None):
    return py(S2, *validate_args(repo, commit, files, evidence_sha, result, code_root, *extra, s1=s1, profile=profile))


def built(synthetic, variant=None, name="repo"):
    repo, commit, files = synthetic(variant, name=name)
    out = build(repo, commit, files)
    assert out.returncode == 0, out.stderr
    commit_evidence(repo)
    return repo, commit, files, sha((repo / EVIDENCE).read_bytes())


def result_of(path):
    return json.loads(Path(path).read_text())


def edit_evidence(repo, change):
    doc = json.loads((repo / EVIDENCE).read_text())
    change(doc)
    (repo / EVIDENCE).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    git(repo, "add", EVIDENCE)
    git(repo, "commit", "-q", "-m", "edited evidence")
    return sha((repo / EVIDENCE).read_bytes())


def forbidden_events(events):
    bad = []
    for e in events:
        words = [e.get("path")] if e["event"] != "subprocess.Popen" else e["argv"]
        for w in words:
            if isinstance(w, str) and any(part in NOT_ALLOWED for part in w.replace(":", "/").split("/")):
                bad.append(e)
    return bad


# ---------------------------------------------------------------- happy path and zero-forbidden-read allowlist

def test_build_and_validate_happy_path(synthetic, code_root, tmp_path):
    repo, commit, files, evidence_sha = built(synthetic)
    doc = json.loads((repo / EVIDENCE).read_text())
    assert doc["schema"] == "clasher.k4s.end-evidence.v1" and doc["kind"] == "counted-reporting"
    assert doc["plan"] == dict(path="plan.json", sha256=sha(files[STUDY + "/plan.json"]), commit=commit,
                               repository_path=STUDY + "/plan.json")
    assert [(p["host"], p["phase"]) for p in doc["phases"]] == [("127x03", "reporting"), ("127x03", "replacement-r1"),
                                                                ("127x04", "reporting")]
    assert doc["phases"][0]["mhz"]["path"] == "end-sources/127x03/reporting/mhz.jsonl"
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root)
    assert result.returncode == 0, result.stdout + result.stderr
    r = result_of(tmp_path / "r.json")
    assert r["ok"] is True and r["frozen_manifest_verified"] is True
    assert r["schema"] == "clasher.k4s.end-evidence-validation.TEST-ONLY.v2" and r["test_mode"] is True
    assert r["frozen_bootstrap"]["manifest_sha256"].startswith("74314eda") and r["frozen_bootstrap"]["files_verified"] > 30
    s2 = load_s2()
    manifest = json.loads((code_root / STUDY / "mac/K4S-MAC-MANIFEST.json").read_text())
    for name, (section, rel) in s2.SERVED.items():
        assert r["frozen_module_sha256"][name] == manifest[section][rel] == r["frozen_bootstrap"]["served"][name]
    assert r["optimize"] == sys.flags.optimize                      # the subprocess ran under -O when pytest did
    assert r["membership"] == dict(blocks=3900, losses=1, host_phases=[["127x03", "replacement-r1"],
                                                                       ["127x03", "reporting"],
                                                                       ["127x04", "reporting"]])
    assert r["hosts"]["127x03"]["full_occupancy_rows"] == 8 and r["hosts"]["127x04"]["full_occupancy_rows"] == 4
    assert r["hosts"]["127x03"]["reference_cpus"] == [1, 2, 3, 4, 5] and r["hosts"]["127x03"]["background_slots"] == 10
    assert r["s1_manifest_sha256"] and r["profile_source"] == "declared-default"
    assert r["profile_json_path"] is None and r["profile_json_sha256"] is None
    assert r["s1_manifest_path"] == str(tmp_path / "r.json.s1" / S1_MANIFEST_NAME)


def test_validate_reads_only_the_allowlist(synthetic, code_root, tmp_path):
    """Audit hook: every absolute open is stdlib, a verified code-root file, an exact role path, the evidence, the
    result or the S1 receipt; every git show names an exact role path; nothing under games/complete.json/end/."""
    repo, commit, files, evidence_sha = built(synthetic)
    log = tmp_path / "audit.jsonl"
    result = audited(log, S2, *validate_args(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root))
    assert result.returncode == 0, result.stdout + result.stderr
    events = audit_events(log)
    s2 = load_s2()
    roles = {STUDY + "/plan.json", STUDY + "/run-r1/completion-v2/REPORTING-COMPLETION.json",
             STUDY + "/run-r1/completion-v2/counted-inventory.json", STUDY + "/run-r1/ledger/blind-ledger-final.json"}
    for h, p in (("127x03", "reporting"), ("127x03", "replacement-r1"), ("127x04", "reporting")):
        roles |= {f"{STUDY}/run-r1/phase-meta/{h}-{p}/launch.json", f"{STUDY}/run-r1/phase-meta/{h}-{p}/supervisor-exit.json",
                  f"{STUDY}/end-sources/{h}/{p}/mhz.jsonl", f"{STUDY}/end-sources/{h}/{p}/census.jsonl"}
    code_files = {str(p) for p in code_root.rglob("*") if p.is_file()}
    allowed = {str(repo / r) for r in roles} | {str(repo / EVIDENCE), str(tmp_path / "r.json"),
                                                 str(tmp_path / "r.json.s1" / S1_MANIFEST_NAME), str(S2),
                                                 str(S2.parent / "safe_input.py"),            # r4: pinned layer
                                                 str(repo / ".git")} | code_files     # r4: declared git dir (preflight)
    stdlib = s2.stdlib_dirs()
    interpreter = {sys.prefix, sys.base_prefix, os.path.realpath(sys.prefix), os.path.realpath(sys.base_prefix), *stdlib}
    components = {part for path in allowed | {str(code_root), str(repo)} for part in path.split("/")} | {"/"}
    components |= {".git", "objects", "config", "info"}       # r4: safe_input's static git preflight (no-follow)
    for e in events:
        if e["event"] == "open" and isinstance(e["path"], str):
            path = e["path"]
            if path.startswith("/"):
                real = os.path.realpath(path)
                tempfile_probe = __import__("re").fullmatch(r"/tmp/[a-z0-9_]{8}", path) is not None   # r4: mkdtemp's
                assert path in allowed or any(real.startswith(d + "/") for d in stdlib) or path in ("/", "/dev/null", "/dev/urandom") \
                    or tempfile_probe, path                  # tempdir probe before si.git_run's fresh empty HOME
            else:
                assert path in components, path                     # no-follow component walk (dir_fd opens)
        if e["event"] == "subprocess.Popen":                  # r4: safe_input git_run, or the frozen reader's git
            kind, args = git_call(e["argv"], repo)
            assert kind is not None, e["argv"]
            if kind == "si":
                assert args[0] in ("rev-parse", "merge-base", "cat-file", "ls-tree", "for-each-ref"), args
                if args[0] == "ls-tree":
                    assert args[-3:-1] == [commit, "--"] and args[-1] in roles | {EVIDENCE}, args
                if args[0] == "for-each-ref":
                    assert args == ["for-each-ref", "--format=%(refname)", "refs/replace/"], args
            else:
                assert args[0] in ("merge-base", "show"), args
                if args[0] == "show":
                    assert args[1].split(":", 1)[0] == commit and args[1].split(":", 1)[1] in roles, args
        if e["event"] in ("os.listdir", "os.scandir"):          # import-system directory caches only
            assert str(e["path"]).startswith(str(code_root) + "/") or \
                any(os.path.realpath(str(e["path"])).startswith(d) for d in stdlib), e
        if e["event"] == "stat" and isinstance(e["path"], str) and e["path"].startswith("/") and not e["dir_fd"]:
            path = "/" + e["path"].lstrip("/")                   # lstat walk: only allowed paths and their ancestors;
            assert any(a == path or a.startswith(path + "/") for a in allowed) \
                or any(path == d or path.startswith(d + "/") or d.startswith(path + "/") for d in interpreter), path
    assert forbidden_events(events) == []


# ---------------------------------------------------------------- build

def test_build_refuses_evidence_inside_end_namespace(synthetic):
    repo, commit, files = synthetic()
    out = build(repo, commit, files, "--evidence-repository-path", STUDY + "/end/end-evidence.json",
                out=repo / "x.json")
    assert out.returncode == 2 and "OUTSIDE the strict END namespace" in out.stderr


def test_build_refuses_authority_like_name(synthetic):
    repo, commit, files = synthetic()
    out = build(repo, commit, files, "--evidence-repository-path", STUDY + "/END-JOB-evidence.json",
                out=repo / "x.json")
    # r4: the shared safe_input family denylist (END-claim family end-job) names it
    assert out.returncode == 2 and "END claim name family end-job: component 'END-JOB-evidence.json'" in out.stderr


def test_build_refuses_wrong_pinned_completion(synthetic, tmp_path):
    repo, commit, files = synthetic()
    out = py(S2, "build", "--repository", repo, "--commit", commit, "--out", repo / EVIDENCE, "--test-mode",
             *s1_args(tmp_path, files))                                                   # real-run pins
    assert out.returncode == 2 and "completion SHA != pinned completion" in out.stderr and not (repo / EVIDENCE).exists()


def test_build_refuses_uncommitted_sources(synthetic, tmp_path):
    repo, commit, files = synthetic(dict(no_sources={("127x04", "reporting")}))
    out = build(repo, commit, files, s1=False)
    # r4: safe_input git_show_file (tree metadata first) refuses the untracked path before any object read
    assert out.returncode == 2 and "safe_input refused [missing]" in out.stderr and "end-sources/127x04/reporting" in out.stderr


def test_build_refuses_unbound_supervisor_exit(synthetic):
    def unbind(completion):
        completion["supervisor_exits"]["127x04/reporting"]["sha256"] = "0" * 64
    repo, commit, files = synthetic(dict(completion=unbind))
    out = build(repo, commit, files)
    assert out.returncode == 2 and "not bound by the completion" in out.stderr


def test_build_refuses_overwrite_and_planted_symlink(synthetic, tmp_path):
    repo, commit, files = synthetic()
    (repo / EVIDENCE).write_text("{}")
    out = build(repo, commit, files)
    assert out.returncode == 2 and "--out: safe_input refused [exists]" in out.stderr     # r4: si.check_absent
    victim = tmp_path / "victim.json"
    victim.write_text("keep")
    os.symlink(victim, tmp_path / "planted.json")
    out = build(repo, commit, files, out=tmp_path / "planted.json")
    # r4: a planted symlink is an existing name (si.check_absent never follows it); the victim is untouched
    assert out.returncode == 2 and "--out: safe_input refused [exists]" in out.stderr and victim.read_text() == "keep"


def test_build_s1_manifest_cross_check(synthetic, tmp_path):
    repo, commit, files = synthetic()
    doc = s1_manifest_doc(files)
    out = py(S2, "build", "--repository", repo, "--commit", commit, "--out", tmp_path / "e1.json", *pins_args(files),
             *s1_args(tmp_path, files, doc, "good.json"))
    assert out.returncode == 0, out.stderr
    bad = s1_manifest_doc(files)
    bad["files"][0]["local_sha256"] = bad["files"][0]["remote_sha256_before"] = bad["files"][0]["remote_sha256_after"] = "f" * 64
    out = py(S2, "build", "--repository", repo, "--commit", commit, "--out", tmp_path / "e2.json", *pins_args(files),
             *s1_args(tmp_path, files, bad, "bad.json"))
    assert out.returncode == 2 and "S1 copy manifest" in out.stderr


def test_build_refuses_s1_launch_meta_mismatch(synthetic, tmp_path):
    repo, commit, files = synthetic()
    bad = s1_manifest_doc(files)
    row = next(m for m in bad["meta"] if m["name"] == "launch.json")
    row["remote_sha256"] = row["committed_sha256"] = "e" * 64
    out = py(S2, "build", "--repository", repo, "--commit", commit, "--out", tmp_path / "e.json", *pins_args(files),
             *s1_args(tmp_path, files, bad, "bad.json"))
    assert out.returncode == 2 and "phase-meta differs from the on-host file recorded by S1" in out.stderr


# ---------------------------------------------------------------- production / test separation

def test_test_only_options_refused_in_production(synthetic, tmp_path):
    repo, commit, files = synthetic()
    env = production_env()
    args = [a for a in pins_args(files) if a != "--test-mode"]
    out = py(S2, "build", "--repository", repo, "--commit", commit, "--out", tmp_path / "e.json", *args, env=env)
    assert out.returncode == 2 and "TEST-ONLY option" in out.stderr
    out = py(S2, "build", "--repository", repo, "--commit", commit, "--out", tmp_path / "e.json", *pins_args(files),
             env=env)                                            # --test-mode without the environment marker
    assert out.returncode == 2 and "BOTH --test-mode" in out.stderr
    out = py(S2, "build", "--repository", repo, "--commit", commit, "--out", tmp_path / "e.json", *args,
             env=dict(env, K4S_S2_TEST_MODE="SYNTHETIC-NOT-FOR-PRODUCTION"))
    assert out.returncode == 2 and "BOTH --test-mode" in out.stderr        # marker without --test-mode
    wrong = dict(env, K4S_S2_TEST_MODE="1")
    out = py(S2, "build", "--repository", repo, "--commit", commit, "--out", tmp_path / "e.json", *pins_args(files),
             env=wrong)
    assert out.returncode == 2 and "not the synthetic test marker" in out.stderr
    assert not (tmp_path / "e.json").exists()


def test_no_manifest_check_is_test_only_and_recorded(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic)
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root, "--no-manifest-check")
    r = result_of(tmp_path / "r.json")
    assert result.returncode == 0 and r["ok"] is True and r["frozen_manifest_verified"] is False
    assert r["schema"].endswith("TEST-ONLY.v2") and r["test_mode"] is True
    result = py(S2, "validate", "--repository", repo, "--commit", commit, "--evidence-sha256", evidence_sha,
                "--result", tmp_path / "p.json", "--code-root", code_root, "--no-manifest-check",
                "--declared-default-profile", env=production_env())
    assert result.returncode == 2 and "TEST-ONLY option" in result.stderr and not (tmp_path / "p.json").exists()


def test_production_confines_result_and_refuses_test_root_setting(synthetic, tmp_path, code_root):
    """A production run can neither write outside its fixed roots nor inherit the test root."""
    repo, commit, files, evidence_sha = built(synthetic)
    args = ["validate", "--repository", repo, "--commit", commit, "--evidence-sha256", evidence_sha,
            "--result", tmp_path / "p.json", "--code-root", code_root, "--declared-default-profile"]
    result = py(S2, *args, env=production_env())
    assert result.returncode == 2 and "--result: outside its allowed root" in result.stderr
    result = py(S2, *args, env=dict(production_env(), K4S_S2_TEST_ROOT=str(tmp_path)))
    assert result.returncode == 2 and "K4S_S2_TEST_ROOT is a TEST-ONLY setting" in result.stderr
    assert not (tmp_path / "p.json").exists()


def test_production_requires_s1_receipt(tmp_path, monkeypatch):
    s2 = load_s2()
    monkeypatch.delenv("K4S_S2_TEST_ROOT")
    a = s2_namespace(s2, "validate", s1_manifest=None)
    with pytest.raises(s2.S2Error, match="--s1-manifest and --s1-manifest-sha256 are required"):
        s2.validate(a, s2.Mode(a), {})
    b = s2_namespace(s2, "build", s1_manifest=None)
    with pytest.raises(s2.S2Error, match="--s1-manifest and --s1-manifest-sha256 are required"):
        s2.build(b, s2.Mode(b))


def s2_namespace(s2, command, **overrides):
    """Production-mode argparse namespace for direct calls (every path below is never touched: refusals come first)."""
    base = dict(command=command, test_mode=False, repository="/mpac/sdicks02/repos/clasher", commit="0" * 40,
                code_root=None, out="/mpac/sdicks02/repos/clasher/" + EVIDENCE, s1_manifest=None,
                s1_manifest_sha256=None, profile_json=None, profile_json_sha256=None, declared_default_profile=False,
                evidence_sha256="0" * 64, result=None, s1_dest=None)
    for name in s2.TEST_ONLY_OPTIONS + ("no_manifest_check",):
        base[name] = None
    base.update(overrides)
    return __import__("argparse").Namespace(**base)


def test_load_s1_production_refuses_test_receipt(tmp_path):
    s2 = load_s2()
    mode = type("M", (), dict(testing=False))()
    files = {STUDY + "/end-sources/127x03/reporting/mhz.jsonl": b"m", STUDY + "/end-sources/127x03/reporting/census.jsonl": b"c",
             STUDY + "/run-r1/phase-meta/127x03-reporting/launch.json": b"l",
             STUDY + "/run-r1/phase-meta/127x03-reporting/supervisor-exit.json": b"x"}
    # r4: load_s1 reads only an open si-gated descriptor produced by gate_paths
    gate = lambda path: s2.gate_paths([("--s1-manifest", str(path), lambda p: True, "file", None)])["--s1-manifest"]
    args = write_s1_manifest(tmp_path / "s1", s1_manifest_doc(files))
    with pytest.raises(s2.S2Error, match="schema/status"):
        s2.load_s1(gate(args[1]), args[3], mode, [("127x03", "reporting")])
    args = write_s1_manifest(tmp_path / "s1p", s1_manifest_doc(files, schema="clasher.k4s.end-sources-copy.v2"))
    assert s2.load_s1(gate(args[1]), args[3], mode, [("127x03", "reporting")])["schema"] == "clasher.k4s.end-sources-copy.v2"
    with pytest.raises(s2.S2Error, match="SHA"):
        s2.load_s1(gate(args[1]), "0" * 64, mode, [("127x03", "reporting")])


# ---------------------------------------------------------------- frozen-code bootstrap (S2-F1)

def tampered_code(code_root, tmp_path, rel, suffix):
    copy = tmp_path / "code"
    shutil.copytree(code_root, copy)
    path = copy / rel
    path.write_text(path.read_text() + suffix)
    return copy


def test_pre_import_canary_never_executes(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic)
    canary = tmp_path / "CANARY-EXECUTED"
    code = tampered_code(code_root, tmp_path, STUDY + "/end_evidence.py",
                         f"\nopen({str(canary)!r}, 'w').write('executed')\n")
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", code)
    r = result_of(tmp_path / "r.json")
    assert result.returncode == 2 and r["ok"] is False and "Pin mismatch" in r["error"]
    assert not canary.exists()


def test_modified_verifier_cannot_fake_verification(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic)
    code = tampered_code(code_root, tmp_path, STUDY + "/mac/k4s_logic.py",
                         "\nverify_pinned = lambda *args, **kwargs: None\n")
    helper = code / E4V3 / "fleet_end.py"
    helper.write_text(helper.read_text() + "\n# tampered\n")
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", code)
    r = result_of(tmp_path / "r.json")
    assert result.returncode == 2 and r["ok"] is False and "Pin mismatch (K4S Mac files)" in r["error"]
    assert "frozen_manifest_verified" not in r


def test_validate_refuses_modified_frozen_helper(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic)
    code = tampered_code(code_root, tmp_path, E4V3 + "/fleet_end.py", "\n# tampered\n")
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", code)
    assert result.returncode == 2 and "Pin mismatch (reused read-only TIERS files)" in result_of(tmp_path / "r.json")["error"]


def test_validate_refuses_modified_manifest(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic)
    code = tampered_code(code_root, tmp_path, STUDY + "/mac/K4S-MAC-MANIFEST.json", " ")
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", code)
    assert result.returncode == 2 and "K4S manifest SHA != approved" in result_of(tmp_path / "r.json")["error"]


def test_validate_refuses_symlinked_frozen_module(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic)
    copy = tmp_path / "code"
    shutil.copytree(code_root, copy)
    module = copy / E4V3 / "receipts.py"
    elsewhere = tmp_path / "receipts-elsewhere.py"
    shutil.copyfile(module, elsewhere)                          # identical bytes, but reached through a symlink
    module.unlink()
    os.symlink(elsewhere, module)
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", copy)
    r = result_of(tmp_path / "r.json")
    assert result.returncode == 2 and "receipts.py" in r["error"] and "safe_input refused [symlink]" in r["error"]


def test_validate_refuses_code_root_without_frozen_code(synthetic, tmp_path):
    repo, commit, files, evidence_sha = built(synthetic)
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", repo)
    assert result.returncode == 2 and result_of(tmp_path / "r.json")["ok"] is False


def test_closure_finder_refuses_non_stdlib_imports(tmp_path):
    s2 = load_s2()
    finder = s2.ClosureFinder({})
    assert finder.find_spec("json") is not None or "json" in sys.modules
    import email
    assert finder.find_spec("email.message", email.__path__) is not None
    (tmp_path / "planted_module.py").write_text("raise SystemExit('executed')\n")
    sys.path.insert(0, str(tmp_path))
    try:
        with pytest.raises(ImportError, match="outside the verified frozen closure"):
            finder.find_spec("planted_module")
        with pytest.raises(ImportError):
            finder.find_spec("pytest")                          # site-packages are not part of the closure
    finally:
        sys.path.remove(str(tmp_path))


# ---------------------------------------------------------------- exact roles and zero forbidden reads (S2-F2)

GAMES = STUDY + "/games/synthetic-clock.jsonl"


def test_outcome_dir_item_refused_before_any_read(synthetic, tmp_path, code_root):
    # r4 rename: pytest names tmp_path after the test, and a 'games' token there is itself refused by the family gate
    """Reviewer reproduction: valid synthetic MHz committed under games/ and named by one mhz item."""
    mhz, _ = __import__("conftest").clock_rows("127x03")
    repo, commit, files = synthetic(dict(extra_files={GAMES: mhz}))
    assert build(repo, commit, files).returncode == 0
    commit_evidence(repo)

    def redirect(doc):
        doc["phases"][0]["mhz"].update(path="games/synthetic-clock.jsonl", repository_path=GAMES, sha256=sha(mhz))
    evidence_sha = edit_evidence(repo, redirect)
    log = tmp_path / "audit.jsonl"
    result = audited(log, S2, *validate_args(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root))
    r = result_of(tmp_path / "r.json")
    assert result.returncode == 2 and r["ok"] is False and "repository_path" in r["error"] and "games" in r["error"]
    assert forbidden_events(audit_events(log)) == []


@pytest.mark.parametrize("rel", [STUDY + "/end/registry/round-00/127x03/attempt-00.json",
                                 STUDY + "/run-r1/phase-meta/127x03-reporting/complete.json",
                                 STUDY + "/end-sources/127x03/replacement-r1/mhz.jsonl",
                                 STUDY + "/../k4s-confirm/end-sources/127x03/reporting/mhz.jsonl"])
def test_wrong_role_paths_refused_before_any_read(synthetic, tmp_path, code_root, rel):
    repo, commit, files, _ = built(synthetic)

    def redirect(doc):
        doc["phases"][0]["mhz"].update(repository_path=rel, path=rel[len(STUDY) + 1:])
    evidence_sha = edit_evidence(repo, redirect)
    log = tmp_path / "audit.jsonl"
    result = audited(log, S2, *validate_args(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root))
    r = result_of(tmp_path / "r.json")
    assert result.returncode == 2 and r["ok"] is False and "repository_path" in r["error"]
    events = audit_events(log)
    assert forbidden_events(events) == []
    assert not any(e["event"] == "open" and isinstance(e["path"], str) and e["path"].endswith(rel.split("/")[-1])
                   and e["path"].startswith(str(repo)) and "mhz" not in rel for e in events)


def test_worktree_leaf_symlink_refused_without_following(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic)
    leaf = repo / STUDY / "end-sources/127x03/reporting/mhz.jsonl"
    canary = repo / STUDY / "games" / "canary.jsonl"
    canary.parent.mkdir()
    canary.write_bytes(leaf.read_bytes())
    os.chmod(canary, 0)                                          # if it were followed: EACCES, not the lstat refusal
    leaf.unlink()
    os.symlink(canary, leaf)
    log = tmp_path / "audit.jsonl"
    result = audited(log, S2, *validate_args(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root))
    r = result_of(tmp_path / "r.json")
    assert result.returncode == 2 and "safe_input refused [symlink]" in r["error"] and "mhz.jsonl" in r["error"]
    events = audit_events(log)
    assert forbidden_events(events) == []
    assert not any(e["event"] == "open" and e["path"] == str(leaf) for e in events)     # frozen reader never ran


def test_worktree_ancestor_symlink_refused(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic)
    host_dir = repo / STUDY / "end-sources/127x04"
    copy = tmp_path / "copy-127x04"
    shutil.copytree(host_dir, copy)
    shutil.rmtree(host_dir)
    os.symlink(copy, host_dir)
    log = tmp_path / "audit.jsonl"
    result = audited(log, S2, *validate_args(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root))
    r = result_of(tmp_path / "r.json")
    assert result.returncode == 2 and "component '127x04'" in r["error"]
    assert not any(e["event"] == "open" and isinstance(e["path"], str) and e["path"].startswith(str(host_dir))
                   for e in audit_events(log))


def test_evidence_file_symlink_refused(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic)
    moved = tmp_path / "evidence-copy.json"
    shutil.copyfile(repo / EVIDENCE, moved)
    (repo / EVIDENCE).unlink()
    os.symlink(moved, repo / EVIDENCE)
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root)
    assert result.returncode == 2 and "safe_input refused [symlink]" in result_of(tmp_path / "r.json")["error"]


def test_result_symlink_never_followed(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic)
    victim = tmp_path / "victim.json"
    victim.write_text("keep")
    os.symlink(victim, tmp_path / "r.json")
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root)
    # r4: si.check_absent: the symlink is an existing name, never followed; the victim is untouched
    assert result.returncode == 2 and "--result: safe_input refused [exists]" in result.stderr and victim.read_text() == "keep"


# ---------------------------------------------------------------- r1 validate refusals (unchanged expectations)

def test_validate_refuses_evidence_sha_mismatch(synthetic, tmp_path, code_root):
    repo, commit, files, _ = built(synthetic)
    result = validate(repo, commit, files, "a" * 64, tmp_path / "r.json", code_root)
    assert result.returncode == 2 and result_of(tmp_path / "r.json")["error"] == "evidence SHA mismatch"


def test_validate_refuses_worktree_artifact_differing_from_commit(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic)
    path = repo / STUDY / "end-sources/127x04/reporting/census.jsonl"
    path.write_bytes(path.read_bytes() + b"\n")
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root)
    r = result_of(tmp_path / "r.json")
    # r4 (stricter): refused by S2's own si work-tree hash, before the frozen reader's "END evidence pin mismatch"
    assert result.returncode == 2 and r["ok"] is False and "work-tree pin mismatch" in r["error"]


def test_validate_refuses_commit_not_ancestor(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic)
    git(repo, "checkout", "-q", "--orphan", "other")
    git(repo, "commit", "-q", "-m", "orphan copy")
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root)
    assert result.returncode == 2 and "merge-base" in result_of(tmp_path / "r.json")["error"]


def test_validate_refuses_extra_top_level_key(synthetic, tmp_path, code_root):
    repo, commit, files, _ = built(synthetic)
    doc = json.loads((repo / EVIDENCE).read_text())
    doc["note"] = "extra"
    (repo / EVIDENCE).write_text(json.dumps(doc))
    result = validate(repo, commit, files, sha((repo / EVIDENCE).read_bytes()), tmp_path / "r.json", code_root)
    assert result.returncode == 2 and "top-level keys" in result_of(tmp_path / "r.json")["error"]


def test_validate_refuses_wrong_membership_expectation(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic)
    args = validate_args(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root)
    args[args.index("--expect-losses") + 1] = "99"
    result = py(S2, *args)
    assert result.returncode == 2 and "membership" in result_of(tmp_path / "r.json")["error"]


def test_validate_refuses_result_overwrite(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic)
    (tmp_path / "r.json").write_text("{}")
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root)
    assert result.returncode == 2 and "--result: safe_input refused [exists]" in result.stderr       # r4
    assert (tmp_path / "r.json").read_text() == "{}"


# ---------------------------------------------------------------- S1 receipt cross-checks in validate (S2-F3)

def test_validate_refuses_s1_launch_meta_mismatch_with_correct_telemetry(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic)
    for name in ("launch.json", "supervisor-exit.json"):
        bad = s1_manifest_doc(files)
        row = next(m for m in bad["meta"] if m["name"] == name and m["host"] == "127x04")
        row["remote_sha256"] = row["committed_sha256"] = "e" * 64
        result_path = tmp_path / f"r-{name}.json"
        result = validate(repo, commit, files, evidence_sha, result_path, code_root,
                          s1=s1_args(tmp_path, files, bad, f"bad-{name}"))
        r = result_of(result_path)
        assert result.returncode == 2 and "phase-meta differs from the on-host file recorded by S1" in r["error"]


def test_validate_refuses_s1_source_mismatch(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic)
    bad = s1_manifest_doc(files)
    row = bad["files"][3]
    row["local_sha256"] = row["remote_sha256_before"] = row["remote_sha256_after"] = "d" * 64
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root,
                      s1=s1_args(tmp_path, files, bad, "bad.json"))
    assert result.returncode == 2 and "differs from the S1 copy manifest" in result_of(tmp_path / "r.json")["error"]


# ---------------------------------------------------------------- MHz / census join (S2-F3) + diagnosis

def failing(synthetic, tmp_path, code_root, clock, name="repo"):
    repo, commit, files, evidence_sha = built(synthetic, dict(clock=clock), name=name)
    result = validate(repo, commit, files, evidence_sha, tmp_path / f"r-{name}.json", code_root)
    assert result.returncode == 2
    return result_of(tmp_path / f"r-{name}.json")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 0.0, -1.0])
def test_nonfinite_or_nonpositive_full_occupancy_mhz_refused(synthetic, tmp_path, code_root, value):
    r = failing(synthetic, tmp_path, code_root, {("127x04", "reporting"): dict(mhz={2: value})})
    assert "non-finite/non-positive reporting MHz: 127x04 2026-10-11T20:00:02Z" in r["error"]


def test_missing_occupied_core_refused(synthetic, tmp_path, code_root):
    r = failing(synthetic, tmp_path, code_root, {("127x03", "reporting"): dict(missing_core=4)})
    assert "lacks an occupied physical core: 127x03 2026-10-11T20:00:04Z" in r["error"]


def test_nonfinite_mhz_outside_full_occupancy_is_not_selected(synthetic, tmp_path, code_root):
    """Row 0 (inflight 3) is never a full-occupancy row: the frozen join does not select it, so its NaN is not
    part of the reporting MHz census (same as frozen compare_mhz)."""
    repo, commit, files, evidence_sha = built(synthetic, dict(clock={("127x04", "reporting"): dict(mhz={0: float("nan")})}))
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root)
    assert result.returncode == 0, result.stdout
    assert result_of(tmp_path / "r.json")["hosts"]["127x04"]["full_occupancy_rows"] == 4


def test_full_occupancy_selection_counts(synthetic, tmp_path, code_root):
    clock = {("127x04", "reporting"): dict(n=6, inflight=[3, 11, 10, 11, 0, 11])}
    repo, commit, files, evidence_sha = built(synthetic, dict(clock=clock))
    result = validate(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root)
    assert result.returncode == 0, result.stdout
    r = result_of(tmp_path / "r.json")
    assert r["hosts"]["127x04"]["full_occupancy_rows"] == 3 and r["hosts"]["127x04"]["census_rows_by_phase"] == {"reporting": 6}


def test_insufficient_full_occupancy_refused(synthetic, tmp_path, code_root):
    r = failing(synthetic, tmp_path, code_root, {("127x04", "reporting"): dict(inflight=10)})
    assert "Insufficient full-occupancy" in r["error"]
    assert r["clock_diagnosis"]["127x04/reporting"]["full_occupancy_rows"] == 0
    assert r["clock_diagnosis"]["127x04/reporting"]["frozen_join_would_pass"] is True


def test_census_row_without_mhz_kill_between_writes(synthetic, tmp_path, code_root):
    """A supervisor killed between the census append and the MHz append: last census row unmatched."""
    r = failing(synthetic, tmp_path, code_root, {("127x04", "reporting"): dict(drop_mhz=4)})
    assert "inventories differ" in r["error"] and "nothing repaired" in r["error"]
    d = r["clock_diagnosis"]["127x04/reporting"]
    assert d["census_without_mhz"] == [dict(utc="2026-10-11T20:00:04Z", line=5, position="last",
                                            previous_joined_utc="2026-10-11T20:00:03Z", next_joined_utc=None)]
    assert d["census_rows"] == 5 and d["mhz_rows"] == 4 and d["first_frozen_rule_violated"] == \
        "Reporting MHz/census inventories differ"
    assert "completed" not in json.dumps(r)                       # health-only projection


def test_broken_clock_join_interior(synthetic, tmp_path, code_root):
    r = failing(synthetic, tmp_path, code_root, {("127x04", "reporting"): dict(drop_mhz=2)})
    assert "differ" in r["error"]
    assert r["clock_diagnosis"]["127x04/reporting"]["census_without_mhz"][0]["position"] == "interior"


def test_duplicate_census_row_refused_and_diagnosed(synthetic, tmp_path, code_root):
    r = failing(synthetic, tmp_path, code_root, {("127x03", "replacement-r1"): dict(duplicate_census=3)})
    assert "Duplicate/wrong host census row" in r["error"]
    d = r["clock_diagnosis"]["127x03/replacement-r1"]
    assert d["census_duplicate_utc"] == [dict(utc="2026-10-11T20:00:03Z", lines=[4, 5])]


def test_mhz_without_census_and_slot_mismatch(synthetic, tmp_path, code_root):
    r = failing(synthetic, tmp_path, code_root, {("127x04", "reporting"): dict(extra_mhz="2026-10-11T20:00:09Z")})
    assert "Missing/duplicate full-occupancy clock join" in r["error"]
    assert r["clock_diagnosis"]["127x04/reporting"]["mhz_without_census"] == [dict(utc="2026-10-11T20:00:09Z", line=6)]
    r2 = failing(synthetic, tmp_path, code_root, {("127x04", "reporting"): dict(slots=10)}, name="repo2")
    assert r2["clock_diagnosis"]["127x04/reporting"]["mhz_slots_mismatch"][0]["slots"] == 10


def diagnose_args(tmp_path, *args):
    return ["diagnose-clock", "--test-mode", *args, "--result", tmp_path / "d.json"]


def test_diagnose_clock_repository_mode(synthetic, tmp_path):
    repo, commit, files = synthetic(dict(clock={("127x04", "reporting"): dict(drop_mhz=4)}))
    log = tmp_path / "audit.jsonl"
    pins = ["--expect-completion", sha(files[STUDY + "/run-r1/completion-v2/REPORTING-COMPLETION.json"])]
    result = audited(log, S2, *diagnose_args(tmp_path, "--repository", repo, "--commit", commit, *pins))
    assert result.returncode == 3, result.stdout + result.stderr
    d = result_of(tmp_path / "d.json")
    assert d["schema"].endswith("TEST-ONLY.v1") and d["clean"] is False and d["repair"].startswith("none")
    assert d["hosts"]["127x04"]["phases_failing_join"] == ["reporting"]
    assert d["phases"]["127x04/reporting"]["census_without_mhz"][0]["position"] == "last"
    assert d["phases"]["127x03/reporting"]["frozen_join_would_pass"] is True
    assert "completed" not in (tmp_path / "d.json").read_text()
    shows = si_shown_paths(audit_events(log), repo)          # r4: safe_input git_show_file
    assert shows[0].endswith("REPORTING-COMPLETION.json")
    assert all(s.endswith(("/mhz.jsonl", "/census.jsonl")) and "/end-sources/" in s for s in shows[1:]) and len(shows) == 7
    assert forbidden_events(audit_events(log)) == []


def test_diagnose_clock_clean_and_s1_dest_mode(synthetic, tmp_path):
    repo, commit, files = synthetic()
    dest = tmp_path / "s1-dest"
    for rel, data in files.items():
        if "/end-sources/" in rel:
            path = dest / rel.split("/end-sources/")[1]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    s1 = s1_args(dest, files, name=".")
    s1[1] = dest / S1_MANIFEST_NAME                                # S1's receipt, in its destination
    result = py(S2, *diagnose_args(tmp_path, "--s1-dest", dest, *s1))
    assert result.returncode == 0, result.stdout + result.stderr
    d = result_of(tmp_path / "d.json")
    assert d["clean"] is True and d["source"] == "s1-dest" and len(d["phases"]) == 3
    (dest / "127x03/reporting/mhz.jsonl").write_bytes(b"{}\n")
    result = py(S2, "diagnose-clock", "--test-mode", "--s1-dest", dest, *s1, "--result", tmp_path / "d2.json")
    assert result.returncode == 2 and "differs from its manifest" in result_of(tmp_path / "d2.json")["error"]
