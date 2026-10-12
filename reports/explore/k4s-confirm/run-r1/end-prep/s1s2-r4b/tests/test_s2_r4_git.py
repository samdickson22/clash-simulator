"""S2 r4 regression controls for SOL-REVIEW-END-S2S4-r3 S2-R3-F1 (static git indirection) and the safe_input r2
adoption, each through a FULL S2 entrypoint (build / validate / diagnose-clock) on a synthetic repository.

Every attack is paired with a POSITIVE CONTROL showing that raw `git -C <repo> show` (inherited environment,
replacement objects honoured) really returns the synthetic outcome canary in that fixture. The S2 run must then
return the true bytes (its outputs carry the pinned SHAs and never the canary) or refuse before git runs; validate's
frozen reader runs only inside frozen_git_env() on a checkout without refs/replace/."""
import json
import os
import subprocess
from pathlib import Path

import pytest

from conftest import (S2, S2_ENV, STUDY, audit_events, audited, git, git_call, make_repo, pins_args, py,
                      s1_manifest_doc, sha, synthetic_files, write_s1_manifest)
from test_s2 import EVIDENCE, built, commit_evidence, result_of, validate_args

COMPLETION = STUDY + "/run-r1/completion-v2/REPORTING-COMPLETION.json"
CANARY = b'{"OUTCOME-CANARY": "synthetic sealed outcome bytes; must never reach S2"}\n'
MARK = b"OUTCOME-CANARY"


def raw_show(repo, spec, env=None):
    """The positive control: plain git with the inherited (or given) environment."""
    return subprocess.run(["git", "-C", str(repo), "show", spec], capture_output=True, env=env).stdout


def blob_oid(repo, spec):
    return git(repo, "rev-parse", spec).decode().strip()


def plant_canary_blob(repo):
    """A synthetic outcome canary committed under the outcome namespace (an ordinary blob in the object store)."""
    path = repo / "games" / "outcome.json"
    path.parent.mkdir()
    path.write_bytes(CANARY)
    git(repo, "add", "games/outcome.json")
    git(repo, "commit", "-q", "-m", "canary")
    return blob_oid(repo, "HEAD:games/outcome.json")


def foreign_repo(base, files):
    """A second repository whose completion path holds the canary (target of GIT_DIR / object redirection)."""
    other = dict(files)
    other[COMPLETION] = CANARY
    root = base / "foreign"
    make_repo(root, other)
    return root


def build_args(repo, commit, files, out, s1_dir):
    return ["build", "--repository", repo, "--commit", commit, "--out", out, *pins_args(files),
            *write_s1_manifest(s1_dir, s1_manifest_doc(files))]


def no_canary_anywhere(*paths):
    for path in paths:
        if Path(path).exists():
            assert MARK not in Path(path).read_bytes(), path


def frozen_git_ran(events, repo):
    return [e for e in events if e["event"] == "subprocess.Popen" and git_call(e["argv"], repo)[0] == "frozen"]


# ---------------------------------------------------------------- replacement refs (Sol's reproduction)

def test_replace_ref_build_reads_the_true_completion(synthetic, tmp_path):
    repo, commit, files = synthetic()
    canary = plant_canary_blob(repo)
    git(repo, "replace", blob_oid(repo, f"{commit}:{COMPLETION}"), canary)
    assert raw_show(repo, f"{commit}:{COMPLETION}") == CANARY                         # positive control: live
    out = py(S2, *build_args(repo, commit, files, repo / EVIDENCE, tmp_path / "s1"))
    assert out.returncode == 0, out.stderr                                              # true bytes: pinned SHA held
    doc = json.loads((repo / EVIDENCE).read_text())
    assert doc["completion"]["sha256"] == sha(files[COMPLETION]) != sha(CANARY)
    assert MARK.decode() not in out.stdout + out.stderr
    no_canary_anywhere(repo / EVIDENCE)


def test_replace_ref_validate_refuses_before_the_frozen_reader(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic)
    canary = plant_canary_blob(repo)
    git(repo, "replace", blob_oid(repo, f"{commit}:{COMPLETION}"), canary)
    assert raw_show(repo, f"{commit}:{COMPLETION}") == CANARY
    log = tmp_path / "audit.jsonl"
    done = audited(log, S2, *validate_args(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root))
    r = result_of(tmp_path / "r.json")
    assert done.returncode == 2 and r["ok"] is False and "refs/replace/" in r["error"], r
    assert frozen_git_ran(audit_events(log), repo) == []                                # the frozen reader never ran
    no_canary_anywhere(tmp_path / "r.json")


def test_replace_ref_diagnose_reads_the_true_sources(synthetic, tmp_path):
    repo, commit, files = synthetic(dict(clock={("127x04", "reporting"): dict(drop_mhz=4)}))
    canary = plant_canary_blob(repo)
    census = f"{STUDY}/end-sources/127x04/reporting/census.jsonl"
    git(repo, "replace", blob_oid(repo, f"{commit}:{census}"), canary)
    assert raw_show(repo, f"{commit}:{census}") == CANARY
    pins = ["--expect-completion", sha(files[COMPLETION])]
    done = py(S2, "diagnose-clock", "--test-mode", "--repository", repo, "--commit", commit, *pins,
              "--result", tmp_path / "d.json")
    assert done.returncode == 3, done.stdout + done.stderr                              # the real (dropped-mhz) join
    d = result_of(tmp_path / "d.json")
    assert d["phases"]["127x04/reporting"]["census_sha256"] == sha(files[census]) != sha(CANARY)
    no_canary_anywhere(tmp_path / "d.json")


def test_checkout_show_unit_true_bytes_under_replace(synthetic, tmp_path, monkeypatch):
    """Direct helper call (as in Sol's probe): S2's Checkout.show returns the original blob, raw git the canary."""
    repo, commit, files = synthetic()
    canary = plant_canary_blob(repo)
    git(repo, "replace", blob_oid(repo, f"{commit}:{COMPLETION}"), canary)
    monkeypatch.setenv("K4S_S2_TEST_MODE", "SYNTHETIC-NOT-FOR-PRODUCTION")
    s2 = __import__("test_s2").load_s2()
    gated = s2.gate_paths([("--repository", str(repo), lambda p: True, "dir", None)])
    checkout = s2.Checkout(gated.policy, gated.role("--repository"), str(repo))
    assert checkout.show(commit, COMPLETION, None, "unit") == files[COMPLETION]
    with pytest.raises(s2.S2Error, match="refs/replace"):
        checkout.no_replace_refs()


# ---------------------------------------------------------------- inherited repository / object / config indirection

def hostile_env(name, repo, foreign, tmp_path):
    env = dict(os.environ, **S2_ENV)
    if name == "GIT_DIR":
        env["GIT_DIR"] = str(foreign / ".git")
    elif name == "GIT_OBJECT_DIRECTORY":
        env["GIT_OBJECT_DIRECTORY"] = str(foreign / ".git" / "objects")
    elif name == "GIT_ALTERNATE_OBJECT_DIRECTORIES":
        env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = str(foreign / ".git" / "objects")
    elif name == "GIT_INDEX_FILE":
        env["GIT_INDEX_FILE"] = str(foreign / ".git" / "index")
    elif name == "GIT_CONFIG_PARAMETERS":
        env["GIT_CONFIG_PARAMETERS"] = "'core.hookspath'='%s'" % (tmp_path / "hooks")
    elif name == "GIT_CONFIG_COUNT":
        env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="core.fsmonitor", GIT_CONFIG_VALUE_0="/bin/false")
    elif name == "GIT_REPLACE_REF_BASE":
        env["GIT_REPLACE_REF_BASE"] = "refs/heads/"
    elif name == "HOME":
        home = tmp_path / "home"
        home.mkdir()
        (home / ".gitconfig").write_text("[core]\n\tfsmonitor = /bin/false\n")
        env["HOME"] = str(home)
    return env


ENV_ATTACKS = ("GIT_DIR", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_INDEX_FILE",
               "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT", "GIT_REPLACE_REF_BASE", "HOME")


def test_inherited_git_dir_redirects_raw_git(synthetic, tmp_path):
    """Positive control for the GIT_DIR probe: raw `git -C <allowed repo>` serves the foreign repository's bytes."""
    repo, commit, files = synthetic()
    foreign = foreign_repo(tmp_path, files)
    env = hostile_env("GIT_DIR", repo, foreign, tmp_path)
    assert raw_show(repo, f"HEAD:{COMPLETION}", env=env) == CANARY


@pytest.mark.parametrize("attack", ENV_ATTACKS)
def test_inherited_git_environment_build(synthetic, tmp_path, attack):
    repo, commit, files = synthetic()
    foreign = foreign_repo(tmp_path, files)
    env = hostile_env(attack, repo, foreign, tmp_path)
    done = py(S2, *build_args(repo, commit, files, repo / EVIDENCE, tmp_path / "s1"), env=env)
    assert done.returncode == 0, done.stderr                                            # declared repo, true bytes
    assert json.loads((repo / EVIDENCE).read_text())["completion"]["sha256"] == sha(files[COMPLETION])
    no_canary_anywhere(repo / EVIDENCE)


@pytest.mark.parametrize("attack", ENV_ATTACKS)
def test_inherited_git_environment_validate_frozen_reader_scrubbed(synthetic, tmp_path, code_root, attack):
    """The frozen reader's own `git -C` runs inside frozen_git_env (os.environ = the P2-4 set): a hostile inherited
    environment can neither redirect it nor make it fail; validation passes on the true bytes."""
    repo, commit, files, evidence_sha = built(synthetic)
    foreign = foreign_repo(tmp_path, files)
    env = hostile_env(attack, repo, foreign, tmp_path)
    done = py(S2, *validate_args(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root), env=env)
    r = result_of(tmp_path / "r.json")
    assert done.returncode == 0 and r["ok"] is True, r
    assert r["completion_sha256"] == sha(files[COMPLETION]) and r["frozen_git_env"].startswith("P2-4")


def test_frozen_git_env_is_exact_and_restored(synthetic, monkeypatch, tmp_path):
    repo, commit, files = synthetic()
    monkeypatch.setenv("K4S_S2_TEST_MODE", "SYNTHETIC-NOT-FOR-PRODUCTION")
    monkeypatch.setenv("GIT_DIR", "/nonexistent")
    s2 = __import__("test_s2").load_s2()
    gated = s2.gate_paths([("--repository", str(repo), lambda p: True, "dir", None)])
    checkout = s2.Checkout(gated.policy, gated.role("--repository"), str(repo))
    before = dict(os.environ)
    with s2.frozen_git_env(checkout):
        inside = dict(os.environ)
        assert raw_show(repo, f"{commit}:{COMPLETION}") == files[COMPLETION]
    assert dict(os.environ) == before
    extra = {"HOME", "XDG_CONFIG_HOME", "GIT_DIR", "GIT_WORK_TREE"}
    assert set(inside) == set(s2.si.GIT_FIXED_ENV) | extra
    assert {k: inside[k] for k in s2.si.GIT_FIXED_ENV} == s2.si.GIT_FIXED_ENV
    assert inside["GIT_NO_REPLACE_OBJECTS"] == "1" and inside["GIT_DIR"] == str(repo / ".git")
    assert not os.path.exists(inside["HOME"])                                           # fresh, empty, removed


# ---------------------------------------------------------------- static repository indirection (refused before git)

@pytest.mark.parametrize("kind", ["alternates", "grafts", "hooks-config", "fsmonitor-config", "filter-config",
                                  "include-config", "gitfile"])
def test_static_repository_indirection_refused_before_git_runs(synthetic, tmp_path, kind):
    repo, commit, files = synthetic()
    foreign = foreign_repo(tmp_path, files)
    gitdir = repo / ".git"
    if kind == "alternates":
        (gitdir / "objects" / "info").mkdir(exist_ok=True)
        (gitdir / "objects" / "info" / "alternates").write_text(str(foreign / ".git" / "objects") + "\n")
    elif kind == "grafts":
        (gitdir / "info").mkdir(exist_ok=True)
        (gitdir / "info" / "grafts").write_text(commit + "\n")
    elif kind == "hooks-config":
        git(repo, "config", "core.hooksPath", str(tmp_path / "hooks"))
    elif kind == "fsmonitor-config":
        git(repo, "config", "core.fsmonitor", "/bin/false")
    elif kind == "filter-config":
        git(repo, "config", "filter.x.smudge", "cat")
    elif kind == "include-config":
        git(repo, "config", "include.path", str(tmp_path / "other.cfg"))
    else:                                                       # .git is a gitfile pointing at the foreign repo
        os.rename(gitdir, tmp_path / "moved.git")
        (repo / ".git").write_text(f"gitdir: {foreign / '.git'}\n")
    log = tmp_path / "audit.jsonl"
    done = audited(log, S2, *build_args(repo, commit, files, repo / EVIDENCE, tmp_path / "s1"))
    assert done.returncode == 2 and "safe_input refused [" in done.stderr, done.stderr
    assert ("[indirection]" in done.stderr) or ("[root]" in done.stderr and kind == "gitfile"), done.stderr
    assert not any(e["event"] == "subprocess.Popen" for e in audit_events(log))       # no git process at all
    assert not (repo / EVIDENCE).exists()


# ---------------------------------------------------------------- linked worktree (declared git dir / common dir)

def test_linked_worktree_checkout_needs_declared_git_dirs(synthetic, tmp_path, code_root):
    repo, commit, files, evidence_sha = built(synthetic)
    head = git(repo, "rev-parse", "HEAD").decode().strip()
    wt = Path(os.path.realpath(tmp_path)) / "k4s-s2-wt"
    git(repo, "worktree", "add", "-q", "--detach", str(wt), head)
    name = os.path.basename(git(wt, "rev-parse", "--git-dir").decode().strip())
    args = validate_args(wt, commit, files, evidence_sha, tmp_path / "r1.json", code_root)
    done = py(S2, *args)
    r = result_of(tmp_path / "r1.json")
    # undeclared: <wt>/.git is a gitfile, not the git directory si requires -> refused before git runs
    assert done.returncode == 2 and r["ok"] is False and "safe_input refused [root]" in r["error"] and ".git is not a directory" in r["error"], r
    declared = ["--git-dir", str(repo / ".git" / "worktrees" / name), "--git-common-dir", str(repo / ".git")]
    args = validate_args(wt, commit, files, evidence_sha, tmp_path / "r2.json", code_root, *declared)
    done = py(S2, *args)
    r = result_of(tmp_path / "r2.json")
    assert done.returncode == 0 and r["ok"] is True, r
    wrong = ["--git-dir", str(repo / ".git" / "worktrees" / name), "--git-common-dir", str(tmp_path / "other")]
    (tmp_path / "other").mkdir()
    done = py(S2, *validate_args(wt, commit, files, evidence_sha, tmp_path / "r3.json", code_root, *wrong))
    assert done.returncode == 2 and "commondir" in result_of(tmp_path / "r3.json")["error"]


def test_worktree_git_dirs_production_rule():
    s2 = __import__("test_s2").load_s2()
    roots = s2.Roots(False) if "K4S_S2_TEST_ROOT" not in os.environ else None
    if roots is None:
        saved = os.environ.pop("K4S_S2_TEST_ROOT")
        try:
            roots = s2.Roots(False)
        finally:
            os.environ["K4S_S2_TEST_ROOT"] = saved
    main = "/mpac/sdicks02/repos/clasher"
    assert roots.worktree_git_dirs(main, None, None) == (None, None)
    good = roots.worktree_git_dirs("/tmp/k4s-s2-x", main + "/.git/worktrees/k4s-s2-x", main + "/.git")
    assert good == (main + "/.git/worktrees/k4s-s2-x", main + "/.git")
    for checkout, gd, cd in (("/tmp/k4s-s2-x", main + "/.git/worktrees/k4s-s2-x", None),
                             (main, main + "/.git/worktrees/a", main + "/.git"),
                             ("/tmp/k4s-s2-x", "/tmp/other/.git", main + "/.git"),
                             ("/tmp/k4s-s2-x", main + "/.git/worktrees/games", main + "/.git")):
        with pytest.raises(s2.S2Error):
            roots.worktree_git_dirs(checkout, gd, cd)


# ---------------------------------------------------------------- shared family denylist: case variants, every input

@pytest.mark.parametrize("rel", ["GAMES/profile.json", "x/Games.tmp/profile.json", "x/COMPLETE.json",
                                 "x/End-Raw-copy.JSON", "x/Hub_Blocks/p.json", "x/END-final.json", "x/ATTEMPT-01.json",
                                 "x/Interference.Json", "x/HUB-ACK.json", "x/end_job.json"])
def test_case_variant_profile_names_refused_unread(synthetic, tmp_path, code_root, rel):
    repo, commit, files, evidence_sha = built(synthetic)
    data = json.dumps({h: dict(host=h, reference_slot=0, slot_count=11, console_rule=False, warmup_seconds=300,
                               perception="none") for h in ("127x03", "127x04")}).encode()
    canary = tmp_path / "p" / rel
    canary.parent.mkdir(parents=True, exist_ok=True)
    canary.write_bytes(data)
    log = tmp_path / "audit.jsonl"
    done = audited(log, S2, *validate_args(repo, commit, files, evidence_sha, tmp_path / "r.json", code_root,
                                          profile=["--profile-json", canary, "--profile-json-sha256", sha(data)]))
    r = result_of(tmp_path / "r.json")
    assert done.returncode == 2 and "forbidden location" in r["error"], r
    st = os.lstat(canary)
    assert not any(e["event"] in ("opened", "stat-ok") and (e.get("dev"), e.get("ino")) == (st.st_dev, st.st_ino)
                   for e in audit_events(log))


# ---------------------------------------------------------------- the pinned safe_input loader (before any S2 code)

def copied_package(tmp_path, mutate_layer=None, pin_layer_sha=False, link_layer=False):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    source = S2.read_text()
    layer = (S2.parent / "safe_input.py").read_bytes()
    if mutate_layer:
        layer = mutate_layer(layer)
    (pkg / "safe_input.py").write_bytes(layer)
    if pin_layer_sha:                                   # pin S2 to the mutated layer's SHA (only the fingerprint differs)
        pinned = "806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00"
        assert source.count(pinned) == 1
        source = source.replace(pinned, sha(layer))
    (pkg / "s2_end_evidence.py").write_text(source)
    if link_layer:
        os.link(pkg / "safe_input.py", tmp_path / "layer-alias.py")
    return pkg / "s2_end_evidence.py"


def test_loader_refuses_a_layer_with_other_bytes(tmp_path):
    script = copied_package(tmp_path, mutate_layer=lambda b: b + b"\n# one extra comment line\n")
    done = py(script, "build", "--help")
    assert done.returncode != 0 and "is not the pinned safe_input r3" in done.stderr, done.stderr


def test_loader_refuses_a_changed_constants_fingerprint(tmp_path):
    """Even with S2's SHA pin moved to the edited layer, an edited constant (here one E4 blob OID) refuses."""
    script = copied_package(tmp_path, mutate_layer=lambda b: b.replace(b"7c9502037a75263dcfaaf5ab33666d2b8382a201",
                                                                       b"7c9502037a75263dcfaaf5ab33666d2b8382a200", 1),
                            pin_layer_sha=True)
    done = py(script, "build", "--help")
    assert done.returncode != 0 and "constants fingerprint differs" in done.stderr, done.stderr


def test_loader_refuses_a_hard_linked_layer(tmp_path):
    script = copied_package(tmp_path, link_layer=True)
    done = py(script, "build", "--help")
    assert done.returncode != 0 and "single-link regular file" in done.stderr, done.stderr


def test_loader_control_unchanged_copy_loads(tmp_path):
    done = py(copied_package(tmp_path), "build", "--help")
    assert done.returncode == 0 and "usage" in done.stdout


# ---------------------------------------------------------------- frozen-reader precondition: si reads come first

def test_committed_blob_is_checked_by_si_before_the_frozen_reader(synthetic, tmp_path, code_root):
    """The evidence names census bytes that match the WORK TREE but not the committed blob at --commit: si's
    git_show_file (expected SHA) refuses before the frozen reader's own git show runs."""
    repo, commit, files, _ = built(synthetic)
    rel = STUDY + "/end-sources/127x04/reporting/census.jsonl"
    changed = (repo / rel).read_bytes() + b"\n"
    (repo / rel).write_bytes(changed)                                  # work tree only; --commit keeps the old blob

    def point(doc):
        for entry in doc["phases"]:
            if (entry["host"], entry["phase"]) == ("127x04", "reporting"):
                entry["census"]["sha256"] = sha(changed)
    doc = json.loads((repo / EVIDENCE).read_text())
    point(doc)
    (repo / EVIDENCE).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    git(repo, "add", EVIDENCE)
    git(repo, "commit", "-q", "-m", "evidence names a work-tree-only census")
    s1 = write_s1_manifest(tmp_path / "s1-changed", s1_manifest_doc(dict(files, **{rel: changed})))
    log = tmp_path / "audit.jsonl"
    done = audited(log, S2, *validate_args(repo, commit, files, sha((repo / EVIDENCE).read_bytes()),
                                          tmp_path / "r.json", code_root, s1=s1))
    r = result_of(tmp_path / "r.json")
    assert done.returncode == 2 and "committed blob pin mismatch" in r["error"], r
    assert frozen_git_ran(audit_events(log), repo) == []
