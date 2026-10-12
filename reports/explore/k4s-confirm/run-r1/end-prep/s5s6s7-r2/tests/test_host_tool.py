"""k4s_end_host_tool.py: names-only registry listing, safe_input registry snapshot (RC-5), frozen-reader clone
checks and git environment, the pinned bootstrap loader and the safe_input CLI passthrough. All synthetic."""
import json
import os
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


# ---------------------------------------------------------------- frozen-reader ruling

def test_verify_clone_plain_clone_passes(tmp_path, host):
    repo = repo_with_study(tmp_path)
    got = TOOL.verify_clone(SI, host, str(repo))
    ok(got["replace_refs"] == 0 and all(h.endswith(".sample") for h in got["hooks"]))


def test_verify_clone_replace_ref_refuses(tmp_path, host):
    repo = repo_with_study(tmp_path)
    head = H.git(repo, "rev-parse", "HEAD").stdout.strip()
    H.git(repo, "commit", "-q", "--allow-empty", "-m", "other")
    other = H.git(repo, "rev-parse", "HEAD").stdout.strip()
    H.git(repo, "replace", head, other)
    error = raises((SI.Refusal, TOOL.HostRefusal), TOOL.verify_clone, SI, host, str(repo))
    ok(error.code == "indirection", error)


@pytest.mark.parametrize("mutate", ["alternates", "grafts", "filter", "hookspath", "hook"])
def test_verify_clone_indirections_refuse(tmp_path, host, mutate):
    repo = repo_with_study(tmp_path)
    if mutate == "alternates":
        H.write(repo / ".git/objects/info/alternates", str(tmp_path) + "\n")
    elif mutate == "grafts":
        H.write(repo / ".git/info/grafts", "")
    elif mutate == "filter":
        H.git(repo, "config", "filter.x.smudge", "cat")
    elif mutate == "hookspath":
        H.git(repo, "config", "core.hooksPath", str(tmp_path))
    else:
        H.write(repo / ".git/hooks/post-checkout", "#!/bin/sh\n", 0o755)
    error = raises(SI.Refusal, TOOL.verify_clone, SI, host, str(repo))
    ok(error.code in ("indirection", "allowlist"), error)


def test_seed_commits(tmp_path, host):
    repo = tmp_path / "repo"
    commits = H.git_repo(repo, commits=2)
    ok(TOOL.seed_commits(SI, str(repo), commits) == {c: True for c in commits})
    refused(SI, "subprocess", TOOL.seed_commits, SI, str(repo), ("0" * 40,))


def test_frozen_git_env_scrubs_and_sets():
    env = TOOL.frozen_git_env(SI, {"PATH": "/x", "HOME": "/h", "GIT_DIR": "/evil", "GIT_REPLACE_REF_BASE": "r/",
                                   "GIT_CONFIG_PARAMETERS": "'core.hookspath=/evil'", "OMP_NUM_THREADS": "1"})
    ok(env["PATH"] == "/x" and env["HOME"] == "/h" and env["OMP_NUM_THREADS"] == "1")
    ok("GIT_DIR" not in env and "GIT_REPLACE_REF_BASE" not in env)
    ok(env["GIT_NO_REPLACE_OBJECTS"] == "1" and env["GIT_CONFIG_NOSYSTEM"] == "1" and env["GIT_OPTIONAL_LOCKS"] == "0")
    ok(env["GIT_CONFIG_PARAMETERS"] == TOOL.GIT_CONFIG_PARAMETERS)
    ok({k for k in env if k.startswith("GIT_")} == {k for k in SI.GIT_FIXED_ENV if k.startswith("GIT_")}
       | {"GIT_CONFIG_PARAMETERS"})


def test_frozen_env_disables_replace_and_hooks_for_raw_git(tmp_path, host):
    """Positive control on this host's git: with the frozen env, a raw `git show` ignores replace refs and the repo
    hooksPath (GIT_CONFIG_PARAMETERS overrides it)."""
    repo = repo_with_study(tmp_path)
    head = H.git(repo, "rev-parse", "HEAD").stdout.strip()
    H.write(tmp_path / "canary-src/README", b"CANARY\n")
    canary_repo = tmp_path / "canary-src"
    H.git_repo(canary_repo, files={"reports/explore/k4s-confirm/README": b"CANARY\n"})
    H.git(repo, "fetch", "-q", str(canary_repo), "HEAD")
    fake = H.git(repo, "rev-parse", "FETCH_HEAD").stdout.strip()
    H.git(repo, "replace", "-f", head, fake)
    raw = H.git(repo, "show", head + ":reports/explore/k4s-confirm/README").stdout
    ok(raw == "CANARY\n", "control: replace refs substitute bytes for raw git")
    env = TOOL.frozen_git_env(SI, dict(os.environ, **H.GIT_ENV))
    import subprocess
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
    ok(TOOL.check_global_git_config(SI, {"HOME": str(home)}) == [])
    H.write(home / ".gitconfig", "[user]\n\tname = t\n[core]\n\texcludesfile = x\n")
    ok(TOOL.check_global_git_config(SI, {"HOME": "/" + str(home)}) == [str(home) + "/.gitconfig"])
    H.write(home / ".config/git/config", '[filter "lfs"]\n\tsmudge = git-lfs smudge\n')
    refused(SI, "indirection", TOOL.check_global_git_config, SI, {"HOME": str(home)})
    os.unlink(home / ".config/git/config")
    os.symlink(tmp_path / "nowhere", home / ".config/git/config")
    raises(SI.Refusal, TOOL.check_global_git_config, SI, {"HOME": str(home)})


# ---------------------------------------------------------------- pinned loader and CLI

def test_read_pinned_refuses_aliases_and_drift(tmp_path):
    real = H.write(tmp_path / "real.py", b"x = 1\n")
    digest = H.sha(real)
    ok(TOOL.read_pinned(str(real), digest) == b"x = 1\n")
    raises(TOOL.HostRefusal, TOOL.read_pinned, str(real), "0" * 64, match="SHA-256")
    link = tmp_path / "link.py"
    os.symlink(real, link)
    raises(TOOL.HostRefusal, TOOL.read_pinned, str(link), digest, match="canonical")
    hard = tmp_path / "hard.py"
    os.link(real, hard)
    raises(TOOL.HostRefusal, TOOL.read_pinned, str(real), digest, match="single-link")


def run_cli(tmp, argv, stdin=b"", host="127x03"):
    import subprocess
    tools = Path(tmp) / "tools"
    if not tools.exists():
        H.copy_tools(tools)
    return subprocess.run([str(H.fake_python(tmp)), "-I", "-S", str(tools / "k4s_end_host_tool.py")] + argv,
                          input=stdin, capture_output=True, env=dict(H.shim_env(tmp), FAKE_HOST=host))


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
