"""r2 git boundary (ruling P2-4; Sol S2-R3-F1, S4-R3-F1, S4-R3-F3; D1, D2). Each indirection control has a POSITIVE
control (raw git with the same static state or inherited environment really substitutes bytes / runs code on this
host's git) and the helper assertion (the helper returns exactly the true bytes, refuses before git runs, or runs no
code). Two-phase controls prove a refusal-worthy entry anywhere aborts before the first object read (instrumented
counter + a stdin-logging git wrapper). Synthetic repositories only; nothing outside pytest's tmp_path."""
import hashlib
import os
import subprocess

import pytest

from conftest import CANARY_BYTES, HOST, make_file, ok, policy, refusal, role, si

GIT = "/usr/bin/git"
TRUE = b'{"ok": true}\n'
AUTHOR = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
E4_PATHS = sorted(si.E4_COMPLETE_JSON)


def raw(cwd, *args, env=None, check=True, stdin=None):
    """Raw git for FIXTURES and POSITIVE CONTROLS only (never the code under test)."""
    full = dict(si.GIT_ENV, HOME=cwd, **AUTHOR) if env is None else env
    proc = subprocess.run([GIT, "-C", cwd] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=full,
                          input=stdin)
    if check and proc.returncode != 0:
        raise AssertionError("fixture git %r failed: %r" % (args, proc.stderr))
    return proc


def make_repo(path, files, symlinks=()):
    os.makedirs(path)
    raw(path, "init", "-q")
    for rel, data in files.items():
        make_file(os.path.join(path, rel), data)
    for rel, text in symlinks:
        os.makedirs(os.path.dirname(os.path.join(path, rel)) or path, exist_ok=True)
        os.symlink(text, os.path.join(path, rel))
    raw(path, "add", "-A")
    raw(path, "commit", "-q", "-m", "synthetic")
    return path, raw(path, "rev-parse", "HEAD").stdout.decode().strip()


@pytest.fixture
def pair(base):
    repo, head = make_repo(os.path.join(base, "allowed"), {"allowed.json": TRUE, "src/m.py": b"x = 1\n"})
    foreign, fhead = make_repo(os.path.join(base, "foreign"), {"allowed.json": CANARY_BYTES,
                                                              "g/g.json": CANARY_BYTES})
    canary_oid = raw(foreign, "rev-parse", "HEAD:allowed.json").stdout.decode().strip()
    return {"repo": repo, "head": head, "foreign": foreign, "canary_oid": canary_oid,
            "true_oid": raw(repo, "rev-parse", "HEAD:allowed.json").stdout.decode().strip()}


def show_policy(repo):
    return policy([role("repo", repo, patterns=("**",), exemptions=("E1", "E4"))])


def bare_env(home):
    """An ordinary user environment WITHOUT this layer's protections (positive controls only)."""
    return {"PATH": "/usr/bin:/bin", "HOME": home, "LC_ALL": "C"}


def helper_reads_true_bytes(pr, canary_in_repo=False):
    """Every content path of the helper returns exactly the true bytes, never the canary."""
    p = show_policy(pr["repo"])
    ok(si.git_show_file(p, "repo", pr["repo"], pr["head"], "allowed.json") == TRUE)
    plan = si.git_plan(p, "repo", pr["repo"], pr["head"])
    ok(plan.read("allowed.json") == TRUE)
    ok(sorted(e["path"] for e in plan.files) == ["allowed.json", "src/m.py"])
    ok(si._git_object(pr["repo"], pr["true_oid"], "blob", len(TRUE), "allowed.json") == TRUE)
    if not canary_in_repo:                                           # a foreign object id is never reachable
        refusal("git", si._git_object, pr["repo"], pr["canary_oid"], "blob", len(CANARY_BYTES), "foreign object")
    listed = si.git_run(pr["repo"], ["ls-files", "-z"]).stdout.split(b"\x00")
    ok(sorted(x for x in listed if x) == [b"allowed.json", b"src/m.py"], listed)


# ---------------------------------------------------------------- inherited environment (S2-R3-F1 / S4-R3-F1)
def test_inherited_git_dir_redirect(pair, monkeypatch):
    hostile = {"GIT_DIR": pair["foreign"] + "/.git"}
    got = raw(pair["repo"], "show", "HEAD:allowed.json", env=dict(os.environ, **hostile)).stdout
    ok(got == CANARY_BYTES, "positive control: inherited GIT_DIR substitutes the foreign bytes")
    for key, value in hostile.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("GIT_WORK_TREE", pair["foreign"])
    helper_reads_true_bytes(pair)


def test_inherited_object_directory_redirect(pair, monkeypatch):
    proc = raw(pair["repo"], "show", "HEAD:allowed.json", check=False,
               env=dict(os.environ, GIT_OBJECT_DIRECTORY=pair["foreign"] + "/.git/objects"))
    ok(proc.stdout != TRUE, "positive control: GIT_OBJECT_DIRECTORY redirects the object store")
    monkeypatch.setenv("GIT_OBJECT_DIRECTORY", pair["foreign"] + "/.git/objects")
    helper_reads_true_bytes(pair)


def test_inherited_alternate_object_directories(pair, monkeypatch):
    env = dict(os.environ, GIT_ALTERNATE_OBJECT_DIRECTORIES=pair["foreign"] + "/.git/objects")
    ok(raw(pair["repo"], "cat-file", "blob", pair["canary_oid"], env=env).stdout == CANARY_BYTES,
       "positive control: inherited alternates make the foreign canary object readable")
    monkeypatch.setenv("GIT_ALTERNATE_OBJECT_DIRECTORIES", pair["foreign"] + "/.git/objects")
    helper_reads_true_bytes(pair)


def test_inherited_index_file(pair, monkeypatch):
    env = dict(os.environ, GIT_INDEX_FILE=pair["foreign"] + "/.git/index")
    ok(b"g/g.json" in raw(pair["repo"], "ls-files", env=env).stdout, "positive control: foreign index used")
    monkeypatch.setenv("GIT_INDEX_FILE", pair["foreign"] + "/.git/index")
    helper_reads_true_bytes(pair)


def hook_dir(base, marker):
    path = os.path.join(base, "hooks-" + marker)
    os.makedirs(path)
    for name in ("post-checkout", "pre-commit", "post-commit", "reference-transaction", "fsmonitor"):
        make_file(os.path.join(path, name), b"#!/bin/sh\ntouch %s/MARKER-%s\nexit 0\n" % (base.encode(),
                                                                                          marker.encode()), 0o755)
    return path


def markers(base):
    return sorted(n for n in os.listdir(base) if n.startswith("MARKER-"))


def test_inherited_git_config_parameters_and_count(base, pair, monkeypatch):
    hooks = hook_dir(base, "params")
    env = dict(os.environ, GIT_CONFIG_PARAMETERS="'core.hookspath=%s'" % hooks)
    raw(pair["repo"], "checkout", "-q", "--detach", pair["head"], env=env)
    ok(markers(base) == ["MARKER-params"], "positive control: GIT_CONFIG_PARAMETERS hook ran")
    os.unlink(os.path.join(base, "MARKER-params"))
    monkeypatch.setenv("GIT_CONFIG_PARAMETERS", "'core.hookspath=%s' 'core.fsmonitor=%s/fsmonitor'" % (hooks, hooks))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")                  # git >= 2.31 only; scrubbed regardless
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.hooksPath")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", hooks)
    monkeypatch.setenv("GIT_CONFIG", os.path.join(base, "nonexistent-config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.path.join(base, "nonexistent-config"))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.path.join(base, "nonexistent-config"))
    si.git_run(pair["repo"], ["checkout", "-q", "--detach", pair["head"]])
    si.git_run(pair["repo"], ["status", "--porcelain"])
    ok(markers(base) == [], "a hook or fsmonitor ran through the helper")
    helper_reads_true_bytes(pair)


def test_inherited_replace_ref_base_and_home_config(base, pair, monkeypatch):
    canary = raw(pair["repo"], "hash-object", "-w", "--stdin", stdin=CANARY_BYTES).stdout.decode().strip()
    raw(pair["repo"], "update-ref", "refs/hidden/" + pair["true_oid"], canary)
    env = dict(os.environ, GIT_REPLACE_REF_BASE="refs/hidden/")
    ok(raw(pair["repo"], "show", "HEAD:allowed.json", env=env).stdout == CANARY_BYTES,
       "positive control: GIT_REPLACE_REF_BASE substitutes the canary")
    monkeypatch.setenv("GIT_REPLACE_REF_BASE", "refs/hidden/")
    home = os.path.join(base, "home")
    hooks = hook_dir(base, "home")
    make_file(os.path.join(home, ".gitconfig"), b"[core]\n\thooksPath = %s\n\tfsmonitor = %s/fsmonitor\n"
              b"[status]\n\tshowUntrackedFiles = no\n" % (hooks.encode(), hooks.encode()))
    make_file(os.path.join(home, "xdg", "git", "config"), b"[core]\n\thooksPath = %s\n[status]\n"
              b"\tshowUntrackedFiles = no\n" % hooks.encode())
    raw(pair["repo"], "status", env=dict(os.environ, HOME=home))
    ok(markers(base) == ["MARKER-home"], "positive control: ~/.gitconfig fsmonitor ran")
    os.unlink(os.path.join(base, "MARKER-home"))
    monkeypatch.setenv("HOME", home)
    monkeypatch.setenv("XDG_CONFIG_HOME", os.path.join(home, "xdg"))
    si.git_run(pair["repo"], ["status", "--porcelain"])
    si.git_run(pair["repo"], ["checkout", "-q", "--detach", pair["head"]])
    ok(markers(base) == [], "HOME/XDG config reached the helper")
    make_file(os.path.join(pair["repo"], "untracked.txt"), b"u")
    ok(b"untracked.txt" not in raw(pair["repo"], "status", "--porcelain", env=dict(os.environ)).stdout,
       "positive control: ~/.gitconfig / XDG config hides untracked files")
    monkeypatch.delenv("HOME")
    ok(b"untracked.txt" not in raw(pair["repo"], "status", "--porcelain", env=dict(os.environ)).stdout,
       "positive control: XDG config alone hides untracked files")
    monkeypatch.setenv("HOME", home)
    ok(b"?? untracked.txt" in si.git_run(pair["repo"], ["status", "--porcelain"]).stdout, "HOME/XDG config used")
    os.unlink(os.path.join(pair["repo"], "untracked.txt"))
    helper_reads_true_bytes(pair, canary_in_repo=True)


def test_helper_home_is_fresh_and_removed(pair):
    seen = []
    real = si.run_checked

    def spy(argv, *a, **k):
        seen.append(dict(k["env"]))
        return real(argv, *a, **k)
    si.run_checked = spy
    try:
        si.git_run(pair["repo"], ["rev-parse", "HEAD"])
    finally:
        si.run_checked = real
    env = seen[0]
    ok(set(env) == set(si.GIT_FIXED_ENV) | {"HOME", "XDG_CONFIG_HOME"}, sorted(env))
    ok(env["GIT_NO_REPLACE_OBJECTS"] == "1" and env["GIT_OPTIONAL_LOCKS"] == "0" and env["GIT_CONFIG_NOSYSTEM"] == "1")
    ok(not os.path.exists(env["HOME"]), "the per-call HOME was not removed")
    ok(os.path.basename(env["HOME"]).startswith("si-git-home-") and env["XDG_CONFIG_HOME"].startswith(env["HOME"] + "/"))


def test_helper_argv_flags(pair):
    seen = []
    real = si.run_checked

    def spy(argv, *a, **k):
        seen.append(list(argv))
        return real(argv, *a, **k)
    si.run_checked = spy
    runs = si.GIT_COUNTERS["runs"]
    try:
        si.git_run(pair["repo"], ["rev-parse", "HEAD"])
    finally:
        si.run_checked = real
    ok(si.GIT_COUNTERS["runs"] == runs + 1)
    argv = seen[0]
    ok(argv[0] == GIT and "--no-replace-objects" in argv and "core.hooksPath=/dev/null" in argv
       and "protocol.allow=never" in argv and "--git-dir=" + pair["repo"] + "/.git" in argv
       and "--work-tree=" + pair["repo"] in argv and argv[-2:] == ["rev-parse", "HEAD"], argv)


# ---------------------------------------------------------------- static repository state
def test_replace_refs_in_repo(pair):
    canary = raw(pair["repo"], "hash-object", "-w", "--stdin", stdin=CANARY_BYTES).stdout.decode().strip()
    raw(pair["repo"], "replace", pair["true_oid"], canary)
    ok(raw(pair["repo"], "show", "HEAD:allowed.json", env=bare_env(pair["repo"])).stdout == CANARY_BYTES,
       "positive control: a static replace ref substitutes the canary")
    ok(raw(pair["repo"], "cat-file", "--batch", stdin=(pair["true_oid"] + "\n").encode(),
           env=bare_env(pair["repo"])).stdout.endswith(CANARY_BYTES + b"\n"),
       "positive control: even cat-file --batch of the original oid returns the replacement")
    helper_reads_true_bytes(pair, canary_in_repo=True)
    # a replaced COMMIT (tree with g/g.json) does not change the screened plan
    fake_commit = raw(pair["foreign"], "rev-parse", "HEAD").stdout.decode().strip()
    raw(pair["repo"], "fetch", "-q", pair["foreign"], "HEAD")
    raw(pair["repo"], "replace", "-f", pair["head"], fake_commit)
    plan = si.git_plan(show_policy(pair["repo"]), "repo", pair["repo"], pair["head"])
    ok(sorted(e["path"] for e in plan.files) == ["allowed.json", "src/m.py"])


@pytest.mark.parametrize("kind,rel", [("alternates", "objects/info/alternates"),
                                      ("alternates", "objects/info/http-alternates"),
                                      ("grafts", "info/grafts"), ("shallow", "shallow")])
def test_static_indirection_files_refuse_before_git_runs(pair, kind, rel):
    gd = pair["repo"] + "/.git"
    if rel == "info/grafts":
        make_file(os.path.join(pair["repo"], "two"), b"2\n")
        raw(pair["repo"], "add", "-A")
        raw(pair["repo"], "commit", "-q", "-m", "two")
        tip = raw(pair["repo"], "rev-parse", "HEAD").stdout.decode().strip()
        make_file(os.path.join(gd, rel), (tip + "\n").encode())
        count = raw(pair["repo"], "--no-replace-objects", "rev-list", "--count", "HEAD").stdout.strip()
        ok(count == b"1", "positive control: grafts rewrite history even with --no-replace-objects (%r)" % count)
    elif kind == "alternates":
        make_file(os.path.join(gd, rel), (pair["foreign"] + "/.git/objects\n").encode())
        if rel.endswith("/alternates"):
            ok(raw(pair["repo"], "cat-file", "blob", pair["canary_oid"]).stdout == CANARY_BYTES,
               "positive control: an alternates file exposes the foreign canary object")
    else:
        make_file(os.path.join(gd, rel), (pair["head"] + "\n").encode())
    runs = si.GIT_COUNTERS["runs"]
    refusal("indirection", si.git_run, pair["repo"], ["rev-parse", "HEAD"])
    refusal("indirection", si.git_plan, show_policy(pair["repo"]), "repo", pair["repo"], pair["head"])
    refusal("indirection", si.git_show_file, show_policy(pair["repo"]), "repo", pair["repo"], pair["head"],
            "allowed.json")
    ok(si.GIT_COUNTERS["runs"] == runs, "git ran despite a static indirection file")
    declared = si.GitRepo(work_tree=pair["repo"], allow=(kind,))
    si.git_run(declared, ["rev-parse", "HEAD"])                     # explicitly declared: allowed


def test_gitfile_and_symlinked_git_dir_refuse(base, pair):
    gf = os.path.join(base, "gitfile")
    os.makedirs(gf)
    make_file(os.path.join(gf, ".git"), ("gitdir: %s/.git\n" % pair["foreign"]).encode())
    ok(raw(gf, "show", "HEAD:allowed.json").stdout == CANARY_BYTES, "positive control: a gitfile redirects")
    refusal("root", si.git_run, gf, ["rev-parse", "HEAD"])
    sl = os.path.join(base, "symlinked")
    os.makedirs(sl)
    os.symlink(pair["foreign"] + "/.git", os.path.join(sl, ".git"))
    refusal("root", si.git_run, sl, ["rev-parse", "HEAD"])
    objects = pair["repo"] + "/.git/objects"
    os.rename(objects, objects + "-real")
    os.symlink(objects + "-real", objects)
    refusal("symlink", si.git_run, pair["repo"], ["rev-parse", "HEAD"])


def test_linked_worktree_must_be_declared(base, pair):
    wt = os.path.join(base, "wt")
    raw(pair["repo"], "worktree", "add", "-q", "--detach", wt, pair["head"])
    gd = pair["repo"] + "/.git/worktrees/wt"
    refusal("root", si.git_run, wt, ["rev-parse", "HEAD"])           # .git is a file: undeclared
    refusal("indirection", si.git_run, si.GitRepo(work_tree=wt, git_dir=gd), ["rev-parse", "HEAD"])
    refusal("indirection", si.git_run, si.GitRepo(work_tree=wt, git_dir=gd, common_dir=pair["foreign"] + "/.git"),
            ["rev-parse", "HEAD"])
    declared = si.GitRepo(work_tree=wt, git_dir=gd, common_dir=pair["repo"] + "/.git")
    p = policy([role("wt", wt, patterns=("**",))])
    ok(si.git_show_file(p, "wt", declared, pair["head"], "allowed.json") == TRUE)
    make_file(pair["repo"] + "/.git/objects/info/alternates", (pair["foreign"] + "/.git/objects\n").encode())
    refusal("indirection", si.git_run, declared, ["rev-parse", "HEAD"])  # the common dir is checked too
    os.unlink(pair["repo"] + "/.git/objects/info/alternates")
    si.git_run(declared, ["rev-parse", "HEAD"])
    refusal("indirection", si.git_run, si.GitRepo(work_tree=pair["repo"], common_dir=pair["repo"] + "/.git"),
            ["rev-parse", "HEAD"])                                   # common_dir declared but no commondir file


def test_repo_hooks_and_fsmonitor_never_run(base, pair):
    hooks = hook_dir(base, "repo")
    for name in ("post-checkout", "pre-commit", "post-commit"):
        os.link(os.path.join(hooks, name), os.path.join(pair["repo"], ".git", "hooks", name))
    raw(pair["repo"], "config", "core.fsmonitor", hooks + "/fsmonitor")
    raw(pair["repo"], "status")
    ok(markers(base) == ["MARKER-repo"], "positive control: the repository's own fsmonitor ran")
    os.unlink(os.path.join(base, "MARKER-repo"))
    raw(pair["repo"], "config", "--unset", "core.fsmonitor")
    raw(pair["repo"], "checkout", "-q", "--detach", pair["head"])
    ok(markers(base) == ["MARKER-repo"], "positive control: the repository's post-checkout hook ran")
    os.unlink(os.path.join(base, "MARKER-repo"))
    raw(pair["repo"], "config", "core.fsmonitor", hooks + "/fsmonitor")
    refusal("indirection", si.git_run, pair["repo"], ["status", "--porcelain"])   # refused before git runs
    raw(pair["repo"], "config", "--unset", "core.fsmonitor")
    si.git_run(pair["repo"], ["checkout", "-q", "--detach", pair["head"]])
    si.git_run(pair["repo"], ["status", "--porcelain"])
    make_file(os.path.join(pair["repo"], "n.txt"), b"n")
    si.git_run(pair["repo"], ["add", "n.txt"])
    si.git_run(pair["repo"], ["commit", "-q", "-m", "n"], extra_env=AUTHOR)
    ok(markers(base) == [], "a repository hook or fsmonitor ran through the helper")


def test_protocols_subcommands_env_and_init(base, pair):
    clone = os.path.join(base, "fresh")
    os.makedirs(clone)
    fresh = si.GitRepo(work_tree=clone)
    si.git_run(fresh, ["init", "-q"])
    refusal("exists", si.git_run, fresh, ["init", "-q"])
    refusal("subprocess", si.git_run, fresh, ["fetch", "-q", pair["repo"], "HEAD"])     # protocol.allow=never
    si.git_run(si.GitRepo(work_tree=clone, protocols=("file",)), ["fetch", "-q", pair["repo"], "HEAD"])
    refusal("policy", si.GitRepo, work_tree=clone, protocols=("ssh",))
    refusal("policy", si.GitRepo, work_tree=clone, allow=("everything",))
    for args in (["config", "core.hooksPath", "/tmp"], ["-c", "x=y", "status"], ["--git-dir=/x", "status"],
                 ["show", "HEAD"], ["replace", "-l"], [], ["status\x00"]):
        refusal("subprocess", si.git_run, pair["repo"], args)
    refusal("subprocess", si.git_run, pair["repo"], ["rev-parse", "HEAD"], extra_env={"GIT_DIR": "/x"})
    refusal("policy", setattr, fresh, "git_dir", "/x")


# ---------------------------------------------------------------- two-phase: refusal before the first object read
def logged_git(base):
    """A git wrapper that logs argv AND stdin (cat-file --batch object ids arrive on stdin)."""
    log = os.path.join(base, "git.log")
    path = os.path.join(base, "git-logged")
    with open(path, "w") as stream:
        stream.write('#!/bin/sh\necho "ARGV $*" >> %s\n/usr/bin/tee -a %s | %s "$@"\n' % (log, log, GIT))
    os.chmod(path, 0o755)
    return path, log


def log_text(log):
    if not os.path.exists(log):
        return ""
    with open(log) as stream:
        return stream.read()


def e4_files():
    return {p: b"stand-in-" + p.encode() for p in E4_PATHS}


def pin_e4(monkeypatch, repo, files):
    for p, data in files.items():
        if p not in E4_PATHS:
            continue
        monkeypatch.setitem(si.E4_COMPLETE_JSON, p, hashlib.sha256(data).hexdigest())
        oid = raw(repo, "rev-parse", "HEAD:" + p).stdout.decode().strip()
        monkeypatch.setitem(si.E4_GIT_BLOB_OIDS, p, oid)


LATE = [("zz-outcome/complete.json", b"{}", None, "name"),          # S4-R3-F3 reproduction (late unlisted)
        ("zz/games/x.json", b"{}", None, "name"),
        ("zz/x-hub-ack.json", b"{}", None, "name"),
        ("zz/END-FINAL.json", b"{}", None, "name"),
        ("zz/attempt-00.json", b"{}", None, "name"),
        ("zz/interference-r2.json", b"{}", None, "name"),
        ("zz/link.py", None, "src/a.py", "symlink"),
        ("zz/big.bin", b"z" * 4096, None, "size")]


@pytest.mark.parametrize("late", LATE, ids=[x[0] for x in LATE])
def test_refusal_anywhere_aborts_before_first_object_read(base, monkeypatch, late):
    files = e4_files()
    files.update({"aa.py": b"a\n", "src/a.py": b"print(1)\n", "examples/visualize_battle.py": b"vb\n"})
    links = [(si.E1_ALIAS, si.E1_LINK_TEXT)]
    path, data, link, code = late
    if data is not None:
        files[path] = data
    else:
        links.append((path, link))
    repo, head = make_repo(os.path.join(base, "r"), files, links)
    pin_e4(monkeypatch, repo, e4_files())
    wrapper, log = logged_git(base)
    p = policy([role("rt", repo, patterns=("**",), exemptions=("E1", "E4"), max_size=1024)])
    reads = si.GIT_COUNTERS["object_reads"]
    refusal(code, si.git_plan, p, "rt", repo, head, git_binary=wrapper)
    ok(si.GIT_COUNTERS["object_reads"] == reads, "an object was read before the refusal")
    ok("--batch" not in log_text(log), "cat-file --batch ran before the refusal")
    ok("ls-tree" in log_text(log))                                   # the metadata pass did run


@pytest.mark.parametrize("variant", ["wrong-mode", "changed-blob", "late-gitlink"])
def test_e4_identity_refused_in_phase_one(base, monkeypatch, variant):
    files = e4_files()
    files["src/a.py"] = b"1\n"
    repo, head = make_repo(os.path.join(base, "r"), files)
    pin_e4(monkeypatch, repo, files)
    target = E4_PATHS[1]
    if variant == "wrong-mode":
        os.chmod(os.path.join(repo, target), 0o755)
        expected = "exemption"
    elif variant == "changed-blob":
        make_file(os.path.join(repo, target), b"changed bytes\n")    # pinned OID is the original
        expected = "exemption"
    else:
        raw(repo, "update-index", "--add", "--cacheinfo", "160000,%s,zz-sub" % head)
        expected = "not-regular"
    if variant != "late-gitlink":
        raw(repo, "add", "-A")
    raw(repo, "commit", "-q", "-m", "change")
    head = raw(repo, "rev-parse", "HEAD").stdout.decode().strip()
    wrapper, log = logged_git(base)
    p = policy([role("rt", repo, patterns=("**",), exemptions=("E4",))])
    reads = si.GIT_COUNTERS["object_reads"]
    refusal(expected, si.git_plan, p, "rt", repo, head, git_binary=wrapper)
    ok(si.GIT_COUNTERS["object_reads"] == reads and "--batch" not in log_text(log))


def test_e4_hash_only_through_the_plan(base, monkeypatch):
    files = e4_files()
    files["src/a.py"] = b"1\n"
    repo, head = make_repo(os.path.join(base, "r"), files)
    p = policy([role("rt", repo, patterns=("**",), exemptions=("E4",))])
    refusal("exemption", si.git_plan, p, "rt", repo, head)             # real pinned OIDs vs synthetic stand-ins
    pin_e4(monkeypatch, repo, files)
    plan = si.git_plan(p, "rt", repo, head)
    ok(sorted(e["path"] for e in plan.e4) == E4_PATHS and [e["path"] for e in plan.files] == ["src/a.py"])
    got = plan.hash_e4(plan.e4[0])
    ok(set(got) == {"path", "sha256", "size"} and got["sha256"] == si.E4_COMPLETE_JSON[plan.e4[0]["path"]])
    refusal("policy", plan.read, plan.e4[0])                         # never as ordinary bytes
    refusal("policy", plan.read, "imitation/model/receipts/throughput-0935/complete.json")


# ---------------------------------------------------------------- D1: member set from metadata alone
def d1_repo(base):
    files = {"src/a.py": b"a\n", "src/b.py": b"b\n", "notes/tiers-complete.json": CANARY_BYTES,
             "ev/oa1/hub-ack.returned.json": CANARY_BYTES, "g/games/x.json": CANARY_BYTES,
             "examples/visualize_battle.py": b"vb\n"}
    return make_repo(os.path.join(base, "r"), files, [(si.E1_ALIAS, si.E1_LINK_TEXT)])


def test_d1_members_never_read_non_members(base):
    repo, head = d1_repo(base)
    canaries = [raw(repo, "rev-parse", "HEAD:" + p).stdout.decode().strip()
                for p in ("notes/tiers-complete.json", "ev/oa1/hub-ack.returned.json", "g/games/x.json")]
    p = policy([role("rt", repo, patterns=("**",), exemptions=("E1", "E4"))])
    refusal("name", si.git_plan, p, "rt", repo, head)                  # whole tree: the denylist refuses
    wrapper, log = logged_git(base)
    members = ("src/a.py", "src/b.py", si.E1_ALIAS)
    reads = si.GIT_COUNTERS["object_reads"]
    plan = si.git_plan(p, "rt", repo, head, members=members, git_binary=wrapper)
    ok(si.GIT_COUNTERS["object_reads"] == reads)
    ok([e["path"] for e in plan.files] == ["src/a.py", "src/b.py"] and plan.e1["path"] == si.E1_ALIAS)
    out = os.path.join(base, "out")
    os.makedirs(out)
    inv = plan.export(si.Writer(policy([role("w", out, access="write", patterns=("**",))]), "w"))
    ok(sorted(inv) == ["src/a.py", "src/b.py", si.E1_ALIAS])
    text = log_text(log)
    ok(not any(c in text for c in canaries), "a non-member object id was requested")
    ok(si.git_plan(p, "rt", repo, head, members=lambda e: "yes").files == [])   # only an exact True selects
    predicate = si.git_plan(p, "rt", repo, head, members=lambda e: e["path"].startswith("src/"))
    ok([e["path"] for e in predicate.files] == ["src/a.py", "src/b.py"] and predicate.e1 is None)
    refusal("name", si.git_plan, p, "rt", repo, head, members=("src/a.py", "notes/tiers-complete.json"))
    refusal("name", si.git_plan, p, "rt", repo, head, members=lambda e: True)
    refusal("missing", si.git_plan, p, "rt", repo, head, members=("src/a.py", "src/zz.py"))
    refusal("policy", plan.read, "notes/tiers-complete.json")
    refusal("exemption", predicate.e1_check)                         # no E1 entry in this plan


def test_d1_unlisted_complete_json_refuses_even_as_non_member(base):
    repo, head = make_repo(os.path.join(base, "r"), {"src/a.py": b"a\n", "x/complete.json": b"{}"})
    p = policy([role("rt", repo, patterns=("**",), exemptions=("E4",))])
    reads = si.GIT_COUNTERS["object_reads"]
    refusal("name", si.git_plan, p, "rt", repo, head, members=("src/a.py",))   # ruling E4 fail-closed holds
    ok(si.GIT_COUNTERS["object_reads"] == reads)


# ---------------------------------------------------------------- D2: E1 materialised
def test_d2_e1_materialised(base):
    repo, head = make_repo(os.path.join(base, "r"), {"examples/visualize_battle.py": b"print('vb')\n",
                                                     "src/a.py": b"1\n"}, [(si.E1_ALIAS, si.E1_LINK_TEXT)])
    ok(raw(repo, "ls-tree", "HEAD", si.E1_ALIAS).stdout.split()[2].decode() == si.E1_LINK_OID)
    p = policy([role("rt", repo, patterns=("**",), exemptions=("E1",))])
    plan = si.git_plan(p, "rt", repo, head)
    info = plan.e1_check()
    ok(info["target_sha256"] == hashlib.sha256(b"print('vb')\n").hexdigest() and info["link"] == si.E1_LINK_TEXT)
    out = os.path.join(base, "runtime")
    os.makedirs(out)
    inv = plan.export(si.Writer(policy([role("w", out, access="write", patterns=("**",))]), "w"))
    alias = os.path.join(out, si.E1_ALIAS)
    ok(not os.path.islink(alias) and os.stat(alias).st_nlink == 1 and inv[si.E1_ALIAS]["copy_of"] == si.E1_LINK_TEXT)
    shipped = policy([role("rt-shipped", out, patterns=("**",))])
    ok(plan.e1_verify_shipped(shipped, "rt-shipped")["shipped_sha256"] == info["target_sha256"])
    os.chmod(alias, 0o644)
    with open(alias, "r+b") as stream:
        stream.write(b"PRINT")
    refusal("exemption", plan.e1_verify_shipped, shipped, "rt-shipped")    # same size, different bytes
    os.unlink(alias)
    os.symlink(si.E1_LINK_TEXT, alias)
    refusal("symlink", plan.e1_verify_shipped, shipped, "rt-shipped")      # D2: never a symlink in the runtime
    os.unlink(alias)
    os.link(os.path.join(out, si.E1_LINK_TEXT), alias)
    refusal("nlink", plan.e1_verify_shipped, shipped, "rt-shipped")
    refusal("exemption", si.git_export, repo, plan._plan, si.Writer(policy([role("w2", base, access="write",
                                                                                 patterns=("**",))]), "w2"), "symlink")


def test_d2_e1_link_blob_is_verified(base):
    repo, head = make_repo(os.path.join(base, "r"), {"examples/visualize_battle.py": b"vb\n"},
                           [(si.E1_ALIAS, si.E1_LINK_TEXT)])
    p = policy([role("rt", repo, patterns=("**",), exemptions=("E1",))])
    plan = si.git_plan(p, "rt", repo, head)
    link_oid = plan.e1["oid"]
    fake = os.path.join(base, "fake")
    with open(fake, "w") as stream:   # a git that answers the link object with other text of the same length
        stream.write("#!/bin/sh\ncat >/dev/null\nprintf '%s blob 28\\nexamples/visualize_battle.pX\\n'\n" % link_oid)
    os.chmod(fake, 0o755)
    refusal("sha", si.git_e1_check, repo, plan._plan, fake)
    repo2, head2 = make_repo(os.path.join(base, "r2"), {"examples/visualize_battle.py": b"vb\n",
                                                        "examples/other.py": b"o\n"},
                             [(si.E1_ALIAS, "examples/other.py")])
    reads = si.GIT_COUNTERS["object_reads"]
    refusal("exemption", si.git_plan, policy([role("rt", repo2, patterns=("**",), exemptions=("E1",))]), "rt",
            repo2, head2)
    ok(si.GIT_COUNTERS["object_reads"] == reads)
    repo3, head3 = make_repo(os.path.join(base, "r3"), {"src/a.py": b"a\n"}, [(si.E1_ALIAS, si.E1_LINK_TEXT)])
    refusal("exemption", si.git_plan, policy([role("rt", repo3, patterns=("**",), exemptions=("E1",))]), "rt",
            repo3, head3)                                            # target missing


def test_plan_role_must_be_the_repository(base, pair):
    p = policy([role("other", base, patterns=("**",))])
    refusal("root", si.git_plan, p, "other", pair["repo"], pair["head"])
    refusal("subprocess", si.git_plan, show_policy(pair["repo"]), "repo", pair["repo"], "HEAD")
    tree = raw(pair["repo"], "rev-parse", "HEAD^{tree}").stdout.decode().strip()
    refusal("git", si.git_plan, show_policy(pair["repo"]), "repo", pair["repo"], tree)   # a tree id, not a commit


@pytest.mark.parametrize("snippet", ['[filter "x"]\n\tsmudge = %s\n', '[diff "x"]\n\ttextconv = %s\n',
                                     '[merge "x"]\n\tdriver = %s\n', '[include]\n\tpath = %s\n',
                                     '[includeIf "gitdir:/"]\n\tpath = %s\n', '[core]\n\tworktree = %s\n',
                                     '[core]\n\tsshCommand = %s\n', '[core]\n\tpager = %s\n', '[CORE]\n\tFsMonitor = %s\n',
                                     '[core] hooksPath = %s\n', '[core]\n\tattributesFile = %s\n'])
def test_repository_config_indirection_refuses_before_git_runs(base, pair, snippet):
    with open(os.path.join(pair["repo"], ".git", "config"), "a") as stream:
        stream.write(snippet % (base + "/x"))
    runs = si.GIT_COUNTERS["runs"]
    refusal("indirection", si.git_run, pair["repo"], ["rev-parse", "HEAD"])
    refusal("indirection", si.git_plan, show_policy(pair["repo"]), "repo", pair["repo"], pair["head"])
    ok(si.GIT_COUNTERS["runs"] == runs)


def test_repository_filter_driver_positive_control(base, pair):
    hooks = hook_dir(base, "filter")
    make_file(os.path.join(pair["repo"], ".gitattributes"), b"*.json filter=x\n")
    raw(pair["repo"], "add", ".gitattributes")
    raw(pair["repo"], "commit", "-q", "-m", "attrs")
    raw(pair["repo"], "config", "filter.x.smudge", hooks + "/fsmonitor")
    os.unlink(os.path.join(pair["repo"], "allowed.json"))
    raw(pair["repo"], "checkout", "-q", "--", "allowed.json")
    ok(markers(base) == ["MARKER-filter"], "positive control: a repository filter driver ran on checkout")
    os.unlink(os.path.join(base, "MARKER-filter"))
    os.unlink(os.path.join(pair["repo"], "allowed.json"))
    refusal("indirection", si.git_run, pair["repo"], ["checkout", "-q", "--", "allowed.json"])
    ok(markers(base) == [])
    with open(os.path.join(pair["repo"], ".git", "config"), "a") as stream:
        stream.write("[branch \"main\"]\n\tremote = origin\n[credential \"https://x\"]\n\thelper = store\n")
    raw(pair["repo"], "config", "--remove-section", "filter.x")
    si.git_run(pair["repo"], ["checkout", "-q", "--", "allowed.json"])  # ordinary sections pass


def test_more_preflight_controls(base, pair, monkeypatch):
    make_file(os.path.join(pair["repo"], ".git", "config.worktree"), b"[core]\n\tworktree = /elsewhere\n")
    refusal("indirection", si.git_run, pair["repo"], ["rev-parse", "HEAD"])
    os.unlink(os.path.join(pair["repo"], ".git", "config.worktree"))
    os.symlink(pair["repo"], os.path.join(base, "wt-link"))
    refusal("root", si.git_run, si.GitRepo(work_tree=os.path.join(base, "wt-link"), git_dir=pair["repo"] + "/.git"),
            ["rev-parse", "HEAD"])                                   # the declared work tree itself is checked
    writer = os.path.join(base, "git-writes-home")
    with open(writer, "w") as stream:
        stream.write('#!/bin/sh\ntouch "$HOME/planted"\nexec %s "$@"\n' % GIT)
    os.chmod(writer, 0o755)
    import tempfile
    homes = os.path.join(base, "homes")
    os.makedirs(homes)
    monkeypatch.setattr(tempfile, "tempdir", homes)                  # the kept (non-empty) HOME stays in tmp_path
    e = refusal("subprocess", si.git_run, pair["repo"], ["rev-parse", "HEAD"], git_binary=writer)
    kept = os.listdir(homes)
    ok(len(kept) == 1 and kept[0].startswith("si-git-home-") and os.listdir(os.path.join(homes, kept[0])) == ["planted"]
       and "(kept)" in e.reason, (kept, e.reason))


def test_object_read_counter_counts_reads(base, pair):
    before = si.GIT_COUNTERS["object_reads"]
    plan = si.git_plan(show_policy(pair["repo"]), "repo", pair["repo"], pair["head"])
    ok(si.GIT_COUNTERS["object_reads"] == before)
    plan.read("allowed.json")
    plan.read("src/m.py")
    ok(si.GIT_COUNTERS["object_reads"] == before + 2)


def test_e1_target_is_screened_even_as_non_member(base):
    repo, head = make_repo(os.path.join(base, "r"), {"examples/visualize_battle.py": b"vb\n", "src/a.py": b"a\n"},
                           [(si.E1_ALIAS, si.E1_LINK_TEXT)])
    p = policy([role("rt", repo, patterns=("src/*", si.E1_ALIAS), exemptions=("E1",))])
    refusal("allowlist", si.git_plan, p, "rt", repo, head, members=("src/a.py", si.E1_ALIAS))
    repo2, head2 = make_repo(os.path.join(base, "r2"), {"examples/real.py": b"vb\n", "src/a.py": b"a\n"},
                             [(si.E1_ALIAS, si.E1_LINK_TEXT), ("examples/visualize_battle.py", "real.py")])
    p2 = policy([role("rt", repo2, patterns=("**",), exemptions=("E1",))])
    refusal("exemption", si.git_plan, p2, "rt", repo2, head2, members=("src/a.py", si.E1_ALIAS))
    p3 = policy([role("rt", repo, patterns=("**",), exemptions=("E1",))])
    plan = si.git_plan(p3, "rt", repo, head, members=("src/a.py", si.E1_ALIAS))
    ok(plan.e1_check()["target_size"] == 3 and [e["path"] for e in plan.files] == ["src/a.py"])


def test_e4_sha_pin_checked_even_when_oid_matches(base, monkeypatch):
    files = e4_files()
    repo, head = make_repo(os.path.join(base, "r"), files)
    pin_e4(monkeypatch, repo, files)
    monkeypatch.setitem(si.E4_COMPLETE_JSON, E4_PATHS[0], "0" * 64)
    p = policy([role("rt", repo, patterns=("**",), exemptions=("E4",))])
    plan = si.git_plan(p, "rt", repo, head)
    refusal("exemption", plan.hash_e4, [e for e in plan.e4 if e["path"] == E4_PATHS[0]][0])
    out = os.path.join(base, "out")
    os.makedirs(out)
    refusal("exemption", plan.export, si.Writer(policy([role("w", out, access="write", patterns=("**",),
                                                              exemptions=("E4",))]), "w"))
