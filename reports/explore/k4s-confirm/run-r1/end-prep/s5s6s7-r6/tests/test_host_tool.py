"""k4s_end_host_tool.py: names-only registry listing, safe_input registry snapshot (RC-5), frozen-reader clone
checks and git environment, the pinned bootstrap loader and the safe_input CLI passthrough. All synthetic."""
import json
import os
import subprocess
from pathlib import Path

import pytest

import helpers as H
from helpers import ok, raises, refused

SI, TOOL = H.load_layers()
REG = "reports/explore/k4s-confirm/end/registry"


@pytest.fixture
def host(monkeypatch):
    monkeypatch.setattr(os, "uname", H.fake_uname("127x03"))
    return "127x03"


def claim(repo, round_index, host, index, payload=None):
    path = Path(repo) / REG / ("round-%02d" % round_index) / host / ("attempt-%02d.json" % index)
    return H.write(path, H.canonical(payload or dict(host=host, attempt=index, round=round_index)) + "\n")


def repo_with_study(tmp):
    repo = Path(tmp) / "repository"
    H.git_repo(repo, files={"reports/explore/k4s-confirm/README": b"study\n"})
    return repo


# ---------------------------------------------------------------- registry listing

def test_registry_listing_absent_and_present(tmp_path, host):
    repo = repo_with_study(tmp_path)
    got = TOOL.registry_listing(SI, host, str(repo))
    ok(got == dict(end_exists=False, exists=False, claims={}))
    claim(repo, 0, host, 0)
    claim(repo, 0, host, 1)
    claim(repo, 1, "127x04", 0)
    got = TOOL.registry_listing(SI, host, str(repo))
    ok(got["exists"] and got["claims"] == {"round-00/127x03": ["attempt-00.json", "attempt-01.json"],
                                            "round-01/127x04": ["attempt-00.json"]}, got)


@pytest.mark.parametrize("rel", ["round-00/127x03/notes.txt", "round-00/127x03/attempt-1.json",
                                 "round-0/127x03/attempt-00.json", "round-00/127x05/attempt-00.json",
                                 "stray.json", "round-00/127x03/end-raw.json"])
def test_registry_unexpected_names_refuse_before_stat(tmp_path, host, rel):
    repo = repo_with_study(tmp_path)
    H.write(repo / REG / rel, b"{}\n")
    raises(TOOL.HostRefusal, TOOL.registry_listing, SI, host, str(repo), match="unexpected name")


def test_registry_hard_linked_claim_refuses_and_canary_untouched(tmp_path, host):
    """Sol S6-F1 class on the host side: a claim hard-linked to an outcome canary is never listed or copied."""
    repo = repo_with_study(tmp_path)
    canary = H.canary(tmp_path / "outcome-canary.bin")
    target = repo / REG / "round-00" / host / "attempt-00.json"
    target.parent.mkdir(parents=True)
    os.link(canary, target)
    raises(TOOL.HostRefusal, TOOL.registry_listing, SI, host, str(repo), match="single-link")
    job = tmp_path / "job"
    job.mkdir()
    raises(TOOL.HostRefusal, TOOL.registry_snapshot, SI, host, str(repo), 0, str(job))
    ok(not (job / "registry").exists() and not (job / "registry-listing.json").exists())
    ok(H.canary_intact(canary))


def test_registry_symlinked_end_dir_refuses(tmp_path, host):
    repo = repo_with_study(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    claim(elsewhere, 0, host, 0)
    os.symlink(elsewhere / "reports/explore/k4s-confirm/end", repo / "reports/explore/k4s-confirm/end")
    raises(TOOL.HostRefusal, TOOL.registry_listing, SI, host, str(repo), match="not a real directory")


def test_registry_snapshot_copies_through_safe_input(tmp_path, host):
    repo = repo_with_study(tmp_path)
    a = claim(repo, 0, host, 0)
    b = claim(repo, 0, host, 1)
    claim(repo, 1, host, 0)
    job = tmp_path / "job"
    job.mkdir()
    doc = TOOL.registry_snapshot(SI, host, str(repo), 0, str(job))
    ok([c["name"] for c in doc["claims"]] == ["attempt-00.json", "attempt-01.json"])
    ok(doc["claims"][0]["sha256"] == H.sha(a) and doc["claims"][1]["sha256"] == H.sha(b))
    ok(H.sha(job / "registry" / "attempt-00.json") == H.sha(a) and H.nlink(job / "registry" / "attempt-00.json") == 1)
    ok(json.loads((job / "registry-listing.json").read_text()) == doc)
    ok(doc["other_rounds"] == {"round-01/127x03": ["attempt-00.json"]})
    # exclusive: a second snapshot into the same job refuses (nothing replaced)
    refused(SI, "exists", TOOL.registry_snapshot, SI, host, str(repo), 0, str(job))


def test_registry_snapshot_no_claims(tmp_path, host):
    repo = repo_with_study(tmp_path)
    job = tmp_path / "job"
    job.mkdir()
    doc = TOOL.registry_snapshot(SI, host, str(repo), 0, str(job))
    ok(doc["claims"] == [] and doc["registry_exists"] is False and not (job / "registry").exists())


# ---------------------------------------------------------------- frozen-reader ruling: clone roles (F2)

def shallow_clone(tmp, source, name="shallow"):
    """A depth-1 clone (file protocol) of `source`: the shape S3 builds for the Q3 guard repo."""
    target = Path(tmp) / name
    H.run(["/usr/bin/git", "clone", "-q", "--depth=1", "--no-local", "file://" + str(source), str(target)],
          env=dict({k: v for k, v in os.environ.items() if not k.startswith("GIT_")}, **H.GIT_ENV), check=True)
    return target


def test_verify_clone_role_is_explicit(tmp_path, host):
    repo = repo_with_study(tmp_path)
    raises(TypeError, TOOL.verify_clone, SI, host, str(repo))
    raises(TypeError, TOOL.seed_commits, SI, str(repo), ())
    raises(TOOL.HostRefusal, TOOL.verify_clone, SI, host, str(repo), role="guard", match="unknown clone role")
    raises(TOOL.HostRefusal, TOOL.seed_commits, SI, str(repo), (), role="repository", match="guard-repo role only")


def test_verify_clone_plain_clone_passes(tmp_path, host):
    repo = repo_with_study(tmp_path)
    got = TOOL.verify_clone(SI, host, str(repo), role="repository")
    ok(got["replace_refs"] == 0 and all(h.endswith(".sample") for h in got["hooks"]) and got["role"] == "repository")
    ok(got["promisor"] is False and "shallow_commits" not in got)


def test_shallow_refused_for_repository_role_allowed_for_guard_role(tmp_path, host):
    """F2: the --repository (evidence/END-JOB) clone stays full; only the guard role declares shallow."""
    source = repo_with_study(tmp_path)
    H.git(source, "commit", "-q", "--allow-empty", "-m", "second")
    shallow = shallow_clone(tmp_path, source)
    ok((shallow / ".git/shallow").is_file())
    error = refused(SI, "indirection", TOOL.verify_clone, SI, host, str(shallow), role="repository")
    ok("shallow not declared" in str(error), error)
    got = TOOL.verify_clone(SI, host, str(shallow), role="guard-repo")
    head = H.git(shallow, "rev-parse", "HEAD").stdout.strip()
    ok(got["role"] == "guard-repo" and got["shallow_commits"] == [head], got)
    ok(TOOL.seed_commits(SI, str(shallow), (head,), role="guard-repo") == {head: True})


def test_guard_role_requires_the_shallow_q3_shape(tmp_path, host):
    repo = repo_with_study(tmp_path)                  # a full clone is not the S3 Q3 guard repository
    raises(TOOL.HostRefusal, TOOL.verify_clone, SI, host, str(repo), role="guard-repo", match="shallow Q3")


@pytest.mark.parametrize("role", ["repository", "guard-repo"])
@pytest.mark.parametrize("mutate", ["alternates", "http-alternates", "grafts", "filter", "include", "hookspath",
                                    "hook", "replace", "promisor-remote", "partialclone", "promisor-pack",
                                    "commondir"])
def test_verify_clone_indirections_refuse_in_both_roles(tmp_path, host, role, mutate):
    """Every indirection refusal is kept for the guard role too: only shallow is declared."""
    source = repo_with_study(tmp_path)
    H.git(source, "commit", "-q", "--allow-empty", "-m", "second")
    repo = shallow_clone(tmp_path, source) if role == "guard-repo" else source
    head = H.git(repo, "rev-parse", "HEAD").stdout.strip()
    if mutate == "alternates":
        H.write(repo / ".git/objects/info/alternates", str(tmp_path) + "\n")
    elif mutate == "http-alternates":
        H.write(repo / ".git/objects/info/http-alternates", "http://x/\n")
    elif mutate == "grafts":
        H.write(repo / ".git/info/grafts", head + "\n")
    elif mutate == "filter":
        H.git(repo, "config", "filter.x.smudge", "cat")
    elif mutate == "include":
        H.git(repo, "config", "include.path", str(tmp_path / "elsewhere"))
    elif mutate == "hookspath":
        H.git(repo, "config", "core.hooksPath", str(tmp_path))
    elif mutate == "hook":
        H.write(repo / ".git/hooks/post-checkout", "#!/bin/sh\n", 0o755)
    elif mutate == "replace":
        H.git(repo, "replace", "-f", head, head)
    elif mutate == "promisor-remote":
        H.git(repo, "config", "remote.origin.promisor", "true")
    elif mutate == "partialclone":
        H.git(repo, "config", "extensions.partialClone", "origin")
    elif mutate == "promisor-pack":
        H.write(repo / ".git/objects/pack/pack-0000000000000000000000000000000000000000.promisor", b"")
    else:
        H.write(repo / ".git/commondir", "..\n")
    error = raises((SI.Refusal, TOOL.HostRefusal), TOOL.verify_clone, SI, host, str(repo), role=role)
    ok(error.code in ("indirection", "allowlist"), error)


@pytest.mark.parametrize("case", ["junk", "unknown-commit", "empty", "hard-link", "symlink"])
def test_guard_role_shallow_file_gates(tmp_path, host, case):
    source = repo_with_study(tmp_path)
    H.git(source, "commit", "-q", "--allow-empty", "-m", "second")
    repo = shallow_clone(tmp_path, source)
    shallow = repo / ".git/shallow"
    if case == "junk":
        H.write(shallow, "not-an-oid\n")
    elif case == "unknown-commit":
        H.write(shallow, "1" * 40 + "\n")
    elif case == "empty":
        H.write(shallow, "")
    elif case == "hard-link":
        canary = H.canary(tmp_path / "outcome-canary.bin")
        os.unlink(shallow)
        os.link(canary, shallow)
    else:
        target = H.write(tmp_path / "elsewhere-shallow", shallow.read_bytes())
        os.unlink(shallow)
        os.symlink(target, shallow)
    raises((SI.Refusal, TOOL.HostRefusal), TOOL.verify_clone, SI, host, str(repo), role="guard-repo")
    if case == "hard-link":
        ok(H.canary_intact(tmp_path / "outcome-canary.bin"))


def test_seed_commits(tmp_path, host):
    repo = tmp_path / "repo"
    commits = H.git_repo(repo, commits=2)
    ok(TOOL.seed_commits(SI, str(repo), commits, role="guard-repo") == {c: True for c in commits})
    refused(SI, "subprocess", TOOL.seed_commits, SI, str(repo), ("0" * 40,), role="guard-repo")


def test_seed_commits_guard_role_still_refuses_grafts(tmp_path, host):
    repo = tmp_path / "repo"
    commits = H.git_repo(repo, commits=2)
    H.write(repo / ".git/info/grafts", commits[1] + "\n")
    refused(SI, "indirection", TOOL.seed_commits, SI, str(repo), commits, role="guard-repo")


# ---------------------------------------------------------------- frozen-reader ruling: git environment (F3)

def test_frozen_git_env_scrubs_and_sets():
    env = TOOL.frozen_git_env(SI, {"PATH": "/x", "HOME": "/h", "GIT_DIR": "/evil", "GIT_REPLACE_REF_BASE": "r/",
                                   "GIT_CONFIG_PARAMETERS": "'core.hookspath=/evil'", "OMP_NUM_THREADS": "1",
                                   "GIT_CONFIG": "/evil", "GIT_CONFIG_GLOBAL": "/evil"})
    ok(env["PATH"] == "/x" and env["HOME"] == "/h" and env["OMP_NUM_THREADS"] == "1")
    ok("GIT_DIR" not in env and "GIT_REPLACE_REF_BASE" not in env and "GIT_CONFIG" not in env)
    ok(env["GIT_NO_REPLACE_OBJECTS"] == "1" and env["GIT_CONFIG_NOSYSTEM"] == "1" and env["GIT_OPTIONAL_LOCKS"] == "0")
    ok(env["GIT_CONFIG_PARAMETERS"] == TOOL.GIT_CONFIG_PARAMETERS and env["GIT_CONFIG_GLOBAL"] == "/dev/null")
    ok({k for k in env if k.startswith("GIT_")} == {k for k in SI.GIT_FIXED_ENV if k.startswith("GIT_")}
       | {"GIT_CONFIG_PARAMETERS"})


@pytest.mark.parametrize("key,value,needle", [
    ("XDG_CONFIG_HOME", "xdg", "relative"), ("XDG_CONFIG_HOME", "./xdg", "relative"),
    ("XDG_CONFIG_HOME", "", "empty"), ("XDG_CONFIG_HOME", "//tmp/x", "normalized"),
    ("XDG_CONFIG_HOME", "/tmp/x/", "normalized"), ("XDG_CONFIG_HOME", "/tmp/./x", "normalized"),
    ("XDG_CONFIG_HOME", "/tmp/a/../x", "normalized"), ("HOME", "home", "relative"), ("HOME", "", "empty"),
    ("HOME", "/", "normalized"), ("HOME", "///h", "normalized"), ("HOME", "/h/", "normalized"),
    ("HOME", "/h/../x", "normalized"), ("HOME", None, "not set")])
def test_frozen_env_refuses_relative_empty_or_non_normalized(key, value, needle):
    """F3: these values are refused, never silently rewritten (HOME's leading '//' is the one canonicalization)."""
    inherited = {"PATH": "/x", "HOME": "/h"}
    if value is None:
        inherited.pop(key)
    else:
        inherited[key] = value
    raises(TOOL.HostRefusal, TOOL.frozen_git_env, SI, inherited, match=needle)
    raises(TOOL.HostRefusal, TOOL.frozen_env_checked, SI, "127x03", inherited, match=needle)


def test_frozen_env_refuses_symlinked_home_or_xdg(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    os.symlink(real, tmp_path / "alias")
    for key in ("HOME", "XDG_CONFIG_HOME"):
        inherited = {"HOME": str(real), key: str(tmp_path / "alias")}
        raises(TOOL.HostRefusal, TOOL.frozen_git_env, SI, inherited, match="canonical")


def test_home_leading_double_slash_is_installed_canonical(tmp_path):
    """The fleet passwd home is //home/sdicks02: HOME=//x executes as HOME=/x, and the checked path derives from the
    executed value (no divergence)."""
    home = tmp_path / "home"
    home.mkdir()
    H.write(home / ".gitconfig", "[user]\n\tname = t\n")
    env, record = TOOL.frozen_env_checked(SI, "127x03", {"HOME": "/" + str(home), "PATH": "/x"})
    ok(env["HOME"] == str(home) and record["global_config_checked"] == [str(home) + "/.gitconfig"], record)
    ok(record["config_files"] == [str(home) + "/.config/git/config", str(home) + "/.gitconfig"])


def test_git_config_files_requires_nosystem():
    env = TOOL.frozen_git_env(SI, {"HOME": "/h"})
    ok(TOOL.git_config_files(SI, env) == ("/h/.config/git/config", "/h/.gitconfig"))
    env = dict(env, XDG_CONFIG_HOME="/x")
    ok(TOOL.git_config_files(SI, env) == ("/x/git/config", "/h/.gitconfig"))
    raises(TOOL.HostRefusal, TOOL.git_config_files, SI, dict(env, GIT_CONFIG_NOSYSTEM="0"), match="NOSYSTEM")
    raises(TOOL.HostRefusal, TOOL.git_config_files, SI, {k: v for k, v in env.items() if k != "GIT_CONFIG_NOSYSTEM"},
           match="NOSYSTEM")


def test_frozen_env_disables_replace_and_hooks_for_raw_git(tmp_path, host):
    """Positive control on this host's git: with the frozen env, a raw `git show` ignores replace refs and the repo
    hooksPath (GIT_CONFIG_PARAMETERS overrides it)."""
    repo = repo_with_study(tmp_path)
    head = H.git(repo, "rev-parse", "HEAD").stdout.strip()
    canary_repo = tmp_path / "canary-src"
    H.git_repo(canary_repo, files={"reports/explore/k4s-confirm/README": b"CANARY\n"})
    H.git(repo, "fetch", "-q", str(canary_repo), "HEAD")
    fake = H.git(repo, "rev-parse", "FETCH_HEAD").stdout.strip()
    H.git(repo, "replace", "-f", head, fake)
    raw = H.git(repo, "show", head + ":reports/explore/k4s-confirm/README").stdout
    ok(raw == "CANARY\n", "control: replace refs substitute bytes for raw git")
    (tmp_path / "home").mkdir()
    env, _ = TOOL.frozen_env_checked(SI, host, dict(os.environ, HOME=str(tmp_path / "home"), **H.GIT_ENV))
    out = subprocess.run(["/usr/bin/git", "-C", str(repo), "show", head + ":reports/explore/k4s-confirm/README"],
                         capture_output=True, text=True, env=env).stdout
    ok(out == "study\n", out)
    H.git(repo, "config", "core.hooksPath", str(tmp_path / "evil-hooks"))
    got = subprocess.run(["/usr/bin/git", "-C", str(repo), "config", "--get", "core.hooksPath"], capture_output=True,
                         text=True, env=env).stdout.strip()
    ok(got == "/dev/null", got)


def test_global_git_config_checked(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    env = TOOL.frozen_git_env(SI, {"HOME": str(home)})
    ok(TOOL.check_global_git_config(SI, "127x03", env) == [])
    H.write(home / ".gitconfig", "[user]\n\tname = t\n[core]\n\texcludesfile = x\n")
    ok(TOOL.check_global_git_config(SI, "127x03", env) == [str(home) + "/.gitconfig"])
    H.write(home / ".config/git/config", '[filter "lfs"]\n\tsmudge = git-lfs smudge\n')
    refused(SI, "indirection", TOOL.check_global_git_config, SI, "127x03", env)
    os.unlink(home / ".config/git/config")
    os.symlink(tmp_path / "nowhere", home / ".config/git/config")
    raises(SI.Refusal, TOOL.check_global_git_config, SI, "127x03", env)
    os.unlink(home / ".config/git/config")
    canary = H.canary(tmp_path / "outcome-canary.bin")
    os.link(canary, home / ".config/git/config")                      # hard-linked config: descriptor gate (nlink)
    raises(SI.Refusal, TOOL.check_global_git_config, SI, "127x03", env)
    ok(H.canary_intact(canary))


def test_config_paths_pass_the_name_gate(tmp_path):
    """F3: the role/name gate applies to config paths (an XDG dir inside an outcome-named tree refuses by name)."""
    xdg = tmp_path / "games" / "xdg"
    H.write(xdg / "git/config", "[user]\n\tname = t\n")
    env = TOOL.frozen_git_env(SI, {"HOME": str(tmp_path), "XDG_CONFIG_HOME": str(xdg)})
    refused(SI, "name", TOOL.check_global_git_config, SI, "127x03", env)


def sentinel_repo(tmp_path):
    repo = repo_with_study(tmp_path)
    H.git(repo, "config", "sentinel.repo", "1")
    return repo


def origins(env, repo):
    out = subprocess.run(["/usr/bin/git", "-C", str(repo), "config", "--list", "--show-origin"], capture_output=True,
                         text=True, env=env, check=True).stdout
    return {line.split("\t", 1)[0] for line in out.splitlines()}


@pytest.mark.parametrize("xdg", [False, True])
def test_installed_git_reads_only_the_checked_config_files(tmp_path, xdg):
    """Enumeration check against the INSTALLED git: with the executed env, every file origin git reports is the
    repository config or one of the checked files; /etc/gitconfig is never read (GIT_CONFIG_NOSYSTEM=1); with
    XDG_CONFIG_HOME set, $HOME/.config/git/config is not read (and not needed)."""
    home = tmp_path / "home"
    H.write(home / ".gitconfig", "[sentinel]\n\tglobal = 1\n")
    H.write(home / ".config/git/config", "[sentinel]\n\thomexdg = 1\n")
    inherited = {"HOME": "/" + str(home), "PATH": "/usr/bin:/bin"}
    if xdg:
        H.write(tmp_path / "xdg/git/config", "[sentinel]\n\txdg = 1\n")
        inherited["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    repo = sentinel_repo(tmp_path)
    env, record = TOOL.frozen_env_checked(SI, "127x03", inherited)
    seen = origins(env, repo)
    files = {o[len("file:"):] for o in seen if o.startswith("file:")}
    ok(all(o.startswith("file:") or o == "command line:" for o in seen), seen)
    ok(files - {".git/config", str(repo / ".git/config")} == set(record["global_config_checked"]), (files, record))
    ok(set(record["config_files"]) >= set(record["global_config_checked"]) and "/etc/gitconfig" not in files)
    ok((str(home) + "/.config/git/config" in files) is (not xdg), files)


@pytest.mark.parametrize("variant", ["relative", "absolute"])
def test_sol_probe_relative_xdg_include_with_git_C(tmp_path, variant):
    """Sol END-FULL-F3 probe: repo/xdg/git/config includes repo/games/synthetic-config (a config canary). Control:
    raw git with the r2-style env (relative XDG kept) and `git -C repo` reads the canary. r3: the relative value is
    refused before anything runs; given absolutely, the include is seen by the static check and refused."""
    repo = repo_with_study(tmp_path)
    H.write(repo / "games/synthetic-config", "[synthetic]\n\tcanary = SYNTHETIC-CONFIG-CANARY\n")
    H.write(repo / "xdg/git/config", "[include]\n\tpath = %s\n" % (repo / "games/synthetic-config"))
    home = tmp_path / "home"
    home.mkdir()
    r2_env = {k: v for k, v in dict(os.environ, HOME=str(home)).items() if not k.startswith("GIT_")}
    r2_env.update({k: v for k, v in SI.GIT_FIXED_ENV.items() if k.startswith("GIT_")}, XDG_CONFIG_HOME="xdg",
                  GIT_CONFIG_PARAMETERS=TOOL.GIT_CONFIG_PARAMETERS)
    leak = subprocess.run(["/usr/bin/git", "-C", str(repo), "config", "--get", "synthetic.canary"],
                          capture_output=True, text=True, env=r2_env, cwd=str(tmp_path)).stdout.strip()
    ok(leak == "SYNTHETIC-CONFIG-CANARY", "control: git 2.25 resolves a relative XDG against -C: %r" % leak)
    inherited = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME="xdg" if variant == "relative" else str(repo / "xdg"))
    if variant == "relative":
        raises(TOOL.HostRefusal, TOOL.frozen_env_checked, SI, "127x03", inherited, match="relative")
    else:
        refused(SI, "indirection", TOOL.frozen_env_checked, SI, "127x03", inherited)


def test_frozen_exec_executes_the_identical_checked_env(tmp_path, host, monkeypatch):
    """F3 single source of truth: frozen-exec execs the very env object frozen_env_checked returned, and the
    checked config paths are derived from that object."""
    repo = repo_with_study(tmp_path)
    home = tmp_path / "home"
    H.write(home / ".gitconfig", "[user]\n\tname = t\n")
    seen = {}
    original = TOOL.frozen_env_checked

    def spy(si, host_, inherited):
        env, record = original(si, host_, inherited)
        seen.update(env=env, record=record, git_files=si and TOOL.git_config_files(si, env))
        return env, record

    class Exec(BaseException):
        pass

    def fake_exec(path, argv, env):
        seen.update(exec_env=env, argv=argv)
        raise Exec()
    monkeypatch.setattr(TOOL, "frozen_env_checked", spy)
    monkeypatch.setattr(os, "execvpe", fake_exec)
    monkeypatch.setenv("HOME", "/" + str(home))
    monkeypatch.setenv("GIT_DIR", "/inherited/evil")
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    raises(Exec, TOOL.main, ["frozen-exec", "--", "/bin/true", "--repository", str(repo)])
    ok(seen["exec_env"] is seen["env"], "frozen-exec must exec the checked env object itself")
    ok(seen["exec_env"]["HOME"] == str(home) and "GIT_DIR" not in seen["exec_env"])
    ok(list(seen["git_files"]) == seen["record"]["config_files"]
       and seen["record"]["global_config_checked"] == [str(home) + "/.gitconfig"], seen["record"])


def test_frozen_exec_cli_refuses_relative_xdg_before_running(tmp_path):
    """The Sol probe through the wrapper's own entry point (frozen-exec CLI): rc 3, the command never runs."""
    repo = repo_with_study(tmp_path)
    H.write(repo / "games/synthetic-config", "[synthetic]\n\tcanary = SYNTHETIC-CONFIG-CANARY\n")
    H.write(repo / "xdg/git/config", "[include]\n\tpath = %s\n" % (repo / "games/synthetic-config"))
    marker = tmp_path / "RAN"
    (tmp_path / "home").mkdir()
    for xdg, needle in (("xdg", b"relative"), (str(repo / "xdg"), b"indirection")):
        done = run_cli(tmp_path, ["frozen-exec", "--", "/bin/sh", "-c", "touch %s" % marker, "x", "--repository",
                                  str(repo)], extra_env=dict(XDG_CONFIG_HOME=xdg, HOME=str(tmp_path / "home")))
        ok(done.returncode == 3 and needle in done.stderr and not marker.exists(), done.stderr)
    done = run_cli(tmp_path, ["frozen-exec", "--", "/bin/sh", "-c", "touch %s" % marker, "x", "--repository",
                              str(repo)], extra_env=dict(HOME=str(tmp_path / "home")))
    ok(done.returncode == 0 and marker.exists(), done.stderr)


# ---------------------------------------------------------------- pinned loader and CLI

def test_safe_input_bootstrap_refuses_aliases_and_drift(tmp_path):
    """r3 (END-FULL-F1): the host tool loads safe_input only through the canonical bootstrap r1 (refusal convention:
    HostRefusal("bootstrap", ...)); the alias/size/SHA matrix is in test_f1_bootstrap.py (conformance kit)."""
    tools = tmp_path / "tools"
    H.copy_tools(tools)
    si = TOOL.load_safe_input(str(tools / "safe_input.py"))
    ok(si.__k4s_bootstrap__[1:] == (str(tools / "safe_input.py"), TOOL.SAFE_INPUT_SHA256, TOOL.SAFE_INPUT_SIZE))
    os.symlink(tools / "safe_input.py", tmp_path / "link.py")
    raises(TOOL.HostRefusal, TOOL.load_safe_input, str(tmp_path / "link.py"), match="single-link regular")
    os.symlink(tools, tmp_path / "alias")
    raises(TOOL.HostRefusal, TOOL.load_safe_input, str(tmp_path / "alias" / "safe_input.py"), match="ancestor")
    os.link(tools / "safe_input.py", tmp_path / "hard.py")
    raises(TOOL.HostRefusal, TOOL.load_safe_input, str(tools / "safe_input.py"), match="single-link")
    os.unlink(tmp_path / "hard.py")
    os.chmod(tools / "safe_input.py", 0o644)
    data = (tools / "safe_input.py").read_bytes()
    (tools / "safe_input.py").write_bytes(data[:-1] + (b"#" if data[-1:] != b"#" else b" "))
    error = raises(TOOL.HostRefusal, TOOL.load_safe_input, str(tools / "safe_input.py"), match="SHA-256")
    ok(error.code == "bootstrap")
    raises(TOOL.HostRefusal, TOOL.load_safe_input, str(tools) + "/./safe_input.py", match="normalized")


def run_cli(tmp, argv, stdin=b"", host="127x03", extra_env=None):
    tools = Path(tmp) / "tools"
    if not tools.exists():
        H.copy_tools(tools)
    env = dict(H.shim_env(tmp), FAKE_HOST=host)
    env.pop("XDG_CONFIG_HOME", None)
    env.update(extra_env or {})
    return subprocess.run([str(H.fake_python(tmp)), "-I", "-S", str(tools / "k4s_end_host_tool.py")] + argv,
                          input=stdin, capture_output=True, env=env)


def test_cli_create_excl_never_truncates_a_hard_linked_argv_nul(tmp_path):
    """Sol S6-F2 probe at the CLI the wrappers use: a pre-existing argv.nul hard-linked to a canary is refused and
    the foreign inode keeps its bytes."""
    job = tmp_path / "job"
    job.mkdir()
    canary = H.canary(tmp_path / "keep-me")
    os.link(canary, job / "argv.nul")
    done = run_cli(tmp_path, ["si", "--", "create-excl", "--host", "127x03", "--root", str(job), "--rel", "argv.nul",
                              "--max-size", "65536"], stdin=b"a\0b\0")
    ok(done.returncode == 3 and b"exists" in done.stderr, done.stderr)
    ok(H.canary_intact(canary))
    fresh = run_cli(tmp_path, ["si", "--", "create-excl", "--host", "127x03", "--root", str(job), "--rel", "new.nul",
                               "--max-size", "65536"], stdin=b"a\0b\0")
    ok(fresh.returncode == 0 and (job / "new.nul").read_bytes() == b"a\0b\0", fresh.stderr)


def test_cli_symlinked_job_root_refuses(tmp_path):
    real = tmp_path / "foreign"
    real.mkdir()
    os.symlink(real, tmp_path / "job")
    done = run_cli(tmp_path, ["si", "--", "create-excl", "--host", "127x03", "--root", str(tmp_path / "job"),
                              "--rel", "argv.nul", "--max-size", "64"], stdin=b"x")
    ok(done.returncode == 3 and not list(real.iterdir()), done.stderr)


def test_cli_wrong_node_and_tampered_layer_refuse(tmp_path):
    job = tmp_path / "job"
    job.mkdir()
    argv = ["si", "--", "create-excl", "--host", "127x03", "--root", str(job), "--rel", "a", "--max-size", "8"]
    ok(run_cli(tmp_path, argv, b"x", host="127x05").returncode == 3)
    tools = tmp_path / "tools"
    os.chmod(tools / "safe_input.py", 0o644)
    with open(tools / "safe_input.py", "ab") as stream:
        stream.write(b"\n")
    done = run_cli(tmp_path, argv, b"x")
    ok(done.returncode == 3 and b"bootstrap" in done.stderr and not (job / "a").exists(), done.stderr)


# ---------------------------------------------------------------- F6: executable PATH shims

def test_shims_are_executable_on_disk():
    ok(H.require_executable_shims() == ("hostname", "nice", "rsync", "taskset", "timeout"))
    for name in H.SHIM_NAMES:
        ok(os.stat(H.SHIMS / name).st_mode & 0o777 == 0o755, name)


def test_non_executable_shim_fails_loudly(monkeypatch, tmp_path):
    """A 0644 copy of the shims (the committed-mode failure Sol reproduced) is refused, never silently bypassed."""
    import shutil
    shims = tmp_path / "shims"
    shutil.copytree(H.SHIMS, shims)
    os.chmod(shims / "hostname", 0o644)
    monkeypatch.setattr(H, "SHIMS", shims)
    raises(RuntimeError, H.require_executable_shims, match="hostname (mode 644)")
    raises(RuntimeError, H.shim_env, tmp_path, match="not executable")
    os.unlink(shims / "rsync")
    raises(RuntimeError, H.require_executable_shims, match="rsync (missing)")
