"""r5 (Sol integration review r1, finding 2, BLOCKING): git metadata write confinement in S9 refresh-clone and S11
advance/provision. Every case plants a pre-existing alias (symlink, hard link, symlinked directory, stale lock) of a
path in the audited write set to a SYNTHETIC foreign marker outside the repository, runs the real command, and
requires: refusal BEFORE the fetch/checkout, the foreign marker byte-identical (and its directory unchanged), and no
success record. The write-set table itself is tested row by row on the shared guard (S9.GIT_WRITE_GUARD, the same
source the S11 host program runs), and an inotify observation of the exact git commands proves the table covers
every path git touches."""
import json
import os
import shutil
import subprocess

import pytest

from conftest import C, S9, S10, S11, Args, make_file, ok, read, refused, sha, si
import test_r4_s11 as T11
from test_r4_s11 import advanced_clone, ready  # noqa: F401  (fixtures)
from test_r4_s9 import origin_branch, refresh  # noqa: F401  (fixture)

GW = S9._GW
END_REF = S9.END_BRANCH_REF
LOG_REF = ".git/logs/" + END_REF
MARKER = b"SYNTHETIC FOREIGN MARKER (perception-synthetic) - must never change\n"


def tree_state(path):
    """Bytes and identity of every entry under a foreign directory (the 'unchanged' proof)."""
    out = {}
    for d, dirs, files in os.walk(path):
        for n in sorted(dirs + files):
            p = os.path.join(d, n)
            st = os.lstat(p)
            out[os.path.relpath(p, path)] = (st.st_mode, st.st_ino, st.st_nlink, st.st_size, st.st_mtime_ns,
                                              read(p) if os.path.isfile(p) and not os.path.islink(p) else None)
    return out


def plant(repo, rel, kind, foreign, target_prefix=None):
    """Replace repo/rel by an alias into `foreign` (a local directory); `target_prefix` is how a symlink names
    `foreign` (the fake host's namespace path for S11). The foreign copy keeps the original bytes when rel existed,
    so git would happily use it."""
    path = os.path.join(repo, rel)
    name = rel.replace("/", "_")
    target = (target_prefix or foreign) + "/" + name
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if kind == "dir-symlink":
        dst = os.path.join(foreign, name)
        if os.path.isdir(path):
            shutil.copytree(path, dst, symlinks=True)
            shutil.rmtree(path)
        else:
            os.makedirs(dst)
            make_file(os.path.join(dst, "marker"), MARKER)
        os.symlink(target, path)
        return
    if kind == "exists":                                               # a stale lock sibling / forbidden name
        make_file(path, MARKER)
        return
    dst = os.path.join(foreign, name)
    if os.path.lexists(path):
        os.chmod(path, 0o644)
        shutil.copyfile(path, dst)
        os.unlink(path)
    else:
        make_file(dst, MARKER)
    if kind == "symlink":
        os.symlink(target, path)
    elif kind == "hardlink":
        os.link(dst, path)
    else:
        raise ValueError(kind)


# ---------------------------------------------------------------- S9 refresh-clone (05)

# Cases an EARLIER S9 layer already refuses before the fetch (the guard's own refusal of each is proved row by row in
# test_guard_table_*): git cannot even open a repository whose HEAD is a symlink out of .git; verify_clone refuses
# symlinked objects/pack and objects/info; objects_snapshot's confined walk refuses a hard-linked object file.
S9_EARLIER = {(".git/HEAD", "symlink"): "subprocess", (".git/objects/pack", "dir-symlink"): "symlink",
              (".git/objects/info", "dir-symlink"): "indirection", (".git/objects/info/commit-graph", "hardlink"): "nlink"}
S9_CASES = [  # (rel, kind) - Sol's three first, then the rest of the audited write set
    (".git/FETCH_HEAD", "symlink"), (".git/FETCH_HEAD", "hardlink"), (LOG_REF, "symlink"),
    (LOG_REF, "hardlink"), (".git/logs/HEAD", "symlink"), (".git/logs/HEAD", "hardlink"),
    (".git/ORIG_HEAD", "symlink"), (".git/ORIG_HEAD", "hardlink"), (".git/index", "symlink"), (".git/index", "hardlink"),
    (".git/packed-refs", "symlink"), (".git/packed-refs", "hardlink"), (".git/HEAD", "symlink"),
    (".git/" + END_REF, "symlink"), (".git/" + END_REF, "hardlink"), (".git/refs/remotes/origin", "dir-symlink"),
    (".git/logs/refs/remotes/origin", "dir-symlink"), (".git/logs", "dir-symlink"), (".git/refs", "dir-symlink"),
    (".git/index.lock", "exists"), (".git/" + END_REF + ".lock", "exists"), (".git/packed-refs.lock", "exists"),
    (".git/HEAD.lock", "exists"), (".git/objects/pack", "dir-symlink"), (".git/objects/info", "dir-symlink"),
    (".git/gc.pid", "symlink"), (".git/objects/info/commit-graph", "hardlink")]


def s9_case_id(case):
    return "%s-%s" % (case[0].replace(".git/", "").replace("/", "_"), case[1])


@pytest.fixture
def fetch_spy(monkeypatch):
    runs = []
    real = si.run_checked
    monkeypatch.setattr(si, "run_checked", lambda argv, *a, **k: runs.append(list(argv)) or real(argv, *a, **k))
    return runs


def git_writes(runs):
    return [r for r in runs if "fetch" in r or "checkout" in r]


@pytest.mark.parametrize("case", S9_CASES, ids=[s9_case_id(c) for c in S9_CASES])
def test_s9_refresh_refuses_a_write_set_alias_before_the_fetch(world, repo_copy, origin_branch, tmpdir_, fetch_spy,
                                                               case):
    rel, kind = case
    if rel == ".git/" + END_REF:
        make_file(os.path.join(repo_copy, rel), (world.P + "\n").encode())    # a loose copy of the packed ref
    foreign = os.path.join(tmpdir_, "perception-synthetic")
    os.makedirs(foreign)
    plant(repo_copy, rel, kind, foreign)
    state = tree_state(foreign)
    origin_branch(world.X2)
    error = refused(S9_EARLIER.get(case, "git-write"), refresh, tmpdir_, world.X2)
    if case not in S9_EARLIER:
        ok(rel in error.reason, error.reason)
    ok(git_writes(fetch_spy) == [], "a writing git command ran: %r" % git_writes(fetch_spy))
    ok(tree_state(foreign) == state, "the foreign marker changed")
    names = os.listdir(os.path.join(tmpdir_, "rec"))
    ok(len(names) == 1 and names[0].startswith("S9-REFUSAL-"), names)


@pytest.mark.parametrize("kind", ["dir-symlink", "file-symlink", "file-hardlink"])
def test_s9_checkout_refuses_a_work_tree_alias_before_the_checkout(world, repo_copy, origin_branch, tmpdir_,
                                                                   fetch_spy, kind):
    """--checkout writes exactly the paths that differ (HEAD P -> X2: END-JOB.json and its new directory): an alias
    of the END directory or of the END-JOB.json leaf refuses after the fetch and BEFORE the checkout."""
    foreign = os.path.join(tmpdir_, "perception-synthetic")
    os.makedirs(foreign)
    if kind == "dir-symlink":
        plant(repo_copy, si.STRICT_END_DIR, "dir-symlink", foreign)
    else:
        plant(repo_copy, S9.END_JOB_REL, kind.split("-")[1], foreign)
    state = tree_state(foreign)
    origin_branch(world.X2)
    error = refused("git-write", refresh, tmpdir_, world.X2, checkout=True)
    ok(si.STRICT_END_DIR in error.reason, error.reason)
    ok([r for r in fetch_spy if "fetch" in r] and not [r for r in fetch_spy if "checkout" in r], fetch_spy)
    ok(world.git(repo_copy, "rev-parse", "HEAD").decode().strip() == world.P)
    ok(tree_state(foreign) == state, "the foreign marker changed")
    names = os.listdir(os.path.join(tmpdir_, "rec"))
    ok(len(names) == 1 and names[0].startswith("S9-REFUSAL-"), names)


def test_s9_refresh_record_names_the_guard_and_the_config(world, repo_copy, origin_branch, tmpdir_, fetch_spy):
    origin_branch(world.X2)
    result = refresh(tmpdir_, world.X2, base=world.P, checkout=True)
    g = result["git_write_guard"]
    ok(g["release"] == "k4s-git-write-guard-r6" and g["checked"] > 10 and g["config"] == list(S9.GW_CONFIG))
    ok(g["checkout"]["release"] == "k4s-git-write-guard-r6")
    fetch, checkout = [r for r in fetch_spy if "fetch" in r], [r for r in fetch_spy if "checkout" in r]
    ok(len(fetch) == 1 and len(checkout) == 1, fetch_spy)
    for argv in (fetch[0], checkout[0]):
        ok(argv[3:3 + len(S9.GW_CONFIG)] == list(S9.GW_CONFIG), argv)
        ok("core.logAllRefUpdates=false" in argv and "gc.auto=0" in argv and "core.hooksPath=/dev/null" in argv)
    ok("--no-auto-gc" in fetch[0] and fetch[0].index("--no-auto-gc") > fetch[0].index("fetch"))
    ok(checkout[0][-4:] == ["checkout", "-q", "--detach", world.X2])


# ---------------------------------------------------------------- the write-set table, row by row (shared guard)

GENV = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "GIT_CONFIG_NOSYSTEM": "1", "LC_ALL": "C",
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
        "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z"}
HOST_REF = "refs/heads/" + S9.END_BRANCH


def g(cwd, *args):
    done = subprocess.run(["/usr/bin/git"] + list(args), cwd=cwd, env=GENV, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)
    ok(done.returncode == 0, (args, done.stderr[-400:]))
    return done.stdout.decode().strip()


@pytest.fixture(scope="module")
def scratch():
    """A synthetic origin (P: a few files; X = P + END-JOB.json in the new END directory), the complete bundle of P and
    the P..X bundle, and a host-like repository provisioned at P by the host program's own guarded commands."""
    import tempfile
    work = os.path.realpath(tempfile.mkdtemp(prefix="k4s-r5gw-", dir="/tmp"))
    try:
        origin = os.path.join(work, "origin")
        os.makedirs(origin)
        g(origin, "init", "-q", "--template=")
        for i in range(6):
            make_file(os.path.join(origin, S11.STUDY_REL, "f%d.py" % i), b"x = %d\n" % i)
        g(origin, "add", "-A")
        g(origin, "commit", "-q", "-m", "P")
        g(origin, "branch", "-m", S9.END_BRANCH)
        p = g(origin, "rev-parse", "HEAD")
        g(origin, "bundle", "create", os.path.join(work, "full.bundle"), S9.END_BRANCH)
        make_file(os.path.join(origin, S9.END_JOB_REL), b'{"schema": "synthetic"}\n')
        g(origin, "add", "-A")
        g(origin, "commit", "-q", "-m", "X")
        x = g(origin, "rev-parse", "HEAD")
        g(origin, "bundle", "create", os.path.join(work, "adv.bundle"), "%s..%s" % (p, S9.END_BRANCH))
        ns = T11.host_namespace()
        host = os.path.join(work, "host")
        os.makedirs(host)
        si.git_run(si.GitRepo(work_tree=host), ["init", "-q", "--template="])
        plan = ns["gw_plan"](HOST_REF, worktree_only=(".git",))
        ns["_guarded"](si, host, plan, ["fetch"] + list(ns["GW_FETCH_FLAGS"]) + [
            os.path.join(work, "full.bundle"), "%s:%s" % (HOST_REF, HOST_REF)], protocols=("file",))
        ns["_guarded"](si, host, plan, ["checkout", "-q", S9.END_BRANCH])
        ok(g(host, "rev-parse", "HEAD") == p)
        yield dict(work=work, origin=origin, P=p, X=x, host=host, ns=ns, full=os.path.join(work, "full.bundle"),
                   adv=os.path.join(work, "adv.bundle"))
    finally:
        shutil.rmtree(work)


def copy_host(scratch, tmpdir_, name="repo"):
    dst = os.path.join(tmpdir_, name)
    subprocess.run(["/bin/cp", "-a", scratch["host"], dst], check=True)
    return dst


def table_rows():
    rows = []
    for ref in (HOST_REF, END_REF):
        plan = GW["gw_plan"](ref, worktree=[S9.END_JOB_REL])
        rows += [(ref, "file", rel, alias) for rel in plan["files"] for alias in ("symlink", "hardlink")]
        rows += [(ref, "dir", rel, "dir-symlink") for rel in plan["dirs"] + plan["may_dirs"]]
        rows += [(ref, "dir", rel, "missing") for rel in plan["dirs"]]
        rows += [(ref, "absent", rel, alias) for rel in plan["absent"] for alias in ("exists", "symlink")]
        rows += [(ref, "tree", ".git/objects", alias) for alias in ("symlink-inside", "hardlink-inside", "fifo-inside")]
        rows += [(ref, "worktree", S9.END_JOB_REL, alias) for alias in ("symlink", "hardlink")]
        rows += [(ref, "worktree", si.STRICT_END_DIR, "dir-symlink")]
    return rows


TABLE = table_rows()


def gw_refuse(reason):
    return si.Refusal("git-write", reason)


@pytest.mark.parametrize("row", TABLE, ids=["%s:%s:%s" % (r[0].split("/")[1], r[2].replace(".git/", ""), r[3])
                                            for r in TABLE])
def test_guard_table_every_row_refuses_its_alias(scratch, tmpdir_, row):
    """Closing the class: every row of the write-set table (generated from gw_plan itself, so a new row is tested
    automatically) refuses its alias, in BOTH guard copies (S9's executed source and the S11 host program's), with
    the foreign marker unchanged."""
    ref, kind, rel, alias = row
    repo = copy_host(scratch, tmpdir_)
    plan = GW["gw_plan"](ref, worktree=[S9.END_JOB_REL])
    ok(GW["gw_scan"](repo, plan, gw_refuse))                            # healthy first
    foreign = os.path.join(tmpdir_, "perception-synthetic")
    os.makedirs(foreign)
    path = os.path.join(repo, rel)
    if alias == "missing":
        shutil.rmtree(path)
    elif kind == "tree":
        pack = os.path.join(repo, ".git/objects/pack")
        victim = os.path.join(pack, sorted(os.listdir(pack))[0])
        if alias == "symlink-inside":
            os.symlink(os.path.join(foreign, "x"), os.path.join(repo, ".git/objects/ab"))
        elif alias == "hardlink-inside":
            os.link(victim, os.path.join(foreign, "pack-alias"))
        else:
            os.mkfifo(os.path.join(repo, ".git/objects/info/fifo"))
    else:
        plant(repo, rel, alias, foreign)
    state = tree_state(foreign)
    for label, ns in (("s9", GW), ("s11-host", scratch["ns"])):
        with pytest.raises(si.Refusal) as caught:
            ns["gw_scan"](repo, plan, gw_refuse)
        ok(caught.value.code == "git-write", (label, caught.value))
        anchor = ".git/objects" if kind == "tree" else rel.rsplit("/", 1)[0] if alias == "dir-symlink" else rel
        ok(anchor in caught.value.reason or rel in caught.value.reason, (label, caught.value.reason))
    ok(tree_state(foreign) == state)


def test_guard_table_is_complete_and_shared(scratch):
    """The table covers every audited class (README r5) and the host program carries the guard verbatim."""
    plan = GW["gw_plan"](HOST_REF, worktree=[S9.END_JOB_REL])
    for rel in (".git/FETCH_HEAD", ".git/ORIG_HEAD", ".git/HEAD", ".git/index", ".git/packed-refs", ".git/config",
                ".git/logs/HEAD", ".git/" + HOST_REF, ".git/logs/" + HOST_REF, ".git/gc.pid", ".git/gc.log"):
        ok(rel in plan["files"] and rel + ".lock" in plan["absent"], rel)
    for rel in (".git/hooks", ".git/shallow", ".git/objects/info/alternates", ".git/modules", ".git/worktrees"):
        ok(rel in plan["absent"], rel)
    ok(plan["trees"] == [".git/objects"] and plan["worktree"] == [S9.END_JOB_REL])
    remote = GW["gw_plan"](END_REF)
    for rel in (".git/refs/remotes", ".git/refs/remotes/origin", ".git/logs/refs/remotes/origin"):
        ok(rel in remote["may_dirs"], rel)
    text = S11.host_program(si.Policy(C.local_host(), [C.code_role()]))[0].decode()
    ok(text.count(S9.GIT_WRITE_GUARD) == 1 and scratch["ns"]["GW_CONFIG"] == S9.GW_CONFIG)
    for bad in ("refs", "heads/x", "refs/../x", "refs/heads/", "/refs/heads/x"):
        with pytest.raises(ValueError):
            GW["gw_plan"](bad)
    with pytest.raises(si.Refusal):
        GW["gw_scan"](scratch["host"], dict(plan, release="other"), gw_refuse)


@pytest.mark.parametrize("case", ["symlinked-ancestor", "not-normalized", "relative", "bad-rel", "inside-git",
                                  "fresh-root-not-empty"])
def test_guard_root_and_plan_shape(scratch, tmpdir_, case):
    repo = copy_host(scratch, tmpdir_)
    plan = GW["gw_plan"](HOST_REF)
    path = repo
    if case == "symlinked-ancestor":
        os.symlink(tmpdir_, os.path.join(tmpdir_, "alias"))
        path = os.path.join(tmpdir_, "alias", "repo")
    elif case == "not-normalized":
        path = repo + "/../repo"
    elif case == "relative":
        path = "repo"
    elif case == "bad-rel":
        plan = dict(plan, files=plan["files"] + [".git/../outside"])
    elif case == "inside-git":
        plan = dict(plan, worktree=[".git/config"])
    else:
        plan = GW["gw_plan"](HOST_REF, worktree_only=(".git",))
    with pytest.raises(si.Refusal) as caught:
        GW["gw_scan"](path, plan, gw_refuse)
    ok(caught.value.code == "git-write", caught.value)


@pytest.mark.parametrize("case", ["ok", "dir-replaced", "alias-appeared"])
def test_guard_post_detects_a_changed_write_set(scratch, tmpdir_, case):
    """gw_post (after the command; detection only): the write set must still pass and every directory keeps its
    identity."""
    repo = copy_host(scratch, tmpdir_)
    plan = GW["gw_plan"](HOST_REF)
    before = GW["gw_scan"](repo, plan, gw_refuse)
    if case == "dir-replaced":
        heads = os.path.join(repo, ".git/refs/heads")
        os.rename(heads, heads + "-old")
        shutil.copytree(heads + "-old", heads)
    elif case == "alias-appeared":
        os.unlink(os.path.join(repo, ".git/FETCH_HEAD"))
        os.symlink(os.path.join(tmpdir_, "x"), os.path.join(repo, ".git/FETCH_HEAD"))
    if case == "ok":
        ok(GW["gw_post"](repo, plan, before, gw_refuse) == GW["gw_scan"](repo, plan, gw_refuse))
    else:
        with pytest.raises(si.Refusal) as caught:
            GW["gw_post"](repo, plan, before, gw_refuse)
        ok(caught.value.code == "git-write", caught.value)


# ---------------------------------------------------------------- the observed write set (inotify) is covered

def covered(plan, rel):
    if rel in plan["dirs"] or rel in plan["may_dirs"] or rel in plan["files"] or rel in plan["absent"]:
        return True                                                       # absent rows include the transient *.lock
    if any(rel == t or rel.startswith(t + "/") for t in plan["trees"]):
        return True
    if any(rel == w or w.startswith(rel + "/") for w in plan["worktree"]):
        return True                                                       # the checkout's paths and their ancestors
    return plan["worktree_only"] is not None and rel != ".git" and not rel.startswith(".git/")


def observed(root, fn):
    from gw_observe import observe
    return observe(root, fn)[1]


@pytest.mark.parametrize("command", ["provision-fetch", "provision-checkout", "advance-fetch", "advance-checkout",
                                     "s9-fetch", "s9-checkout"])
def test_observed_git_write_set_is_inside_the_plan(scratch, tmpdir_, monkeypatch, command):
    """The audit, as a test: run the EXACT commands (the host program's _git_w argv for S11; S9.fetch_argv /
    checkout_argv for S9) under an inotify + snapshot observer and require every touched path to be a row of the
    plan (or inside .git/objects, or a planned work-tree path). Healthy repositories, so the scan itself passes."""
    ns = scratch["ns"]
    if command.startswith("provision"):
        repo = os.path.join(tmpdir_, "partial")
        os.makedirs(repo)
        si.git_run(si.GitRepo(work_tree=repo), ["init", "-q", "--template="])
        plan = ns["gw_plan"](HOST_REF, worktree_only=(".git",))
        fetch = ["fetch"] + list(ns["GW_FETCH_FLAGS"]) + [scratch["full"], "%s:%s" % (HOST_REF, HOST_REF)]
        if command == "provision-checkout":
            ns["_guarded"](si, repo, plan, fetch, protocols=("file",))
            args, proto = ["checkout", "-q", S9.END_BRANCH], ()
        else:
            args, proto = fetch, ("file",)
        ok(ns["gw_scan"](repo, plan, gw_refuse))
        touched = observed(repo, lambda: ns["_git_w"](si, repo, args, proto))
    elif command.startswith("advance"):
        repo = copy_host(scratch, tmpdir_)
        make_file(os.path.join(repo, ".git/logs/HEAD"), b"")               # a pre-r5 provision left reflogs
        make_file(os.path.join(repo, ".git/logs/" + HOST_REF), b"")
        plan = ns["gw_plan"](HOST_REF, worktree=[S9.END_JOB_REL])
        fetch = ["fetch"] + list(ns["GW_FETCH_FLAGS"]) + [scratch["adv"], HOST_REF]
        if command == "advance-checkout":
            ns["_guarded"](si, repo, plan, fetch, protocols=("file",))
            args, proto = ["checkout", "-q", "-B", S9.END_BRANCH, scratch["X"]], ()
        else:
            args, proto = fetch, ("file",)
        ok(ns["gw_scan"](repo, plan, gw_refuse))
        touched = observed(repo, lambda: ns["_git_w"](si, repo, args, proto))
    else:
        repo = os.path.join(tmpdir_, "full")
        g(scratch["origin"], "update-ref", "refs/heads/" + S9.END_BRANCH, scratch["P"])
        try:
            g(tmpdir_, "clone", "-q", "--no-checkout", "--template=", "file://" + scratch["origin"], repo)
        finally:
            g(scratch["origin"], "update-ref", "refs/heads/" + S9.END_BRANCH, scratch["X"])
        g(repo, "checkout", "-q", "--detach", scratch["P"])
        monkeypatch.setattr(S9, "REPO_FULL", repo)
        monkeypatch.setattr(S9, "ORIGIN_URL", "file://" + scratch["origin"])
        monkeypatch.setattr(S9, "CLONE_PROTOCOL", "file")
        if command == "s9-checkout":
            with C.ScrubbedEnv() as env:
                si.run_checked(S9.fetch_argv(), 600, 1 << 20, env=env, cwd=repo)
            argv = S9.checkout_argv(scratch["X"])
            plan = GW["gw_plan"](END_REF, worktree=S9.changed_paths(si.GitRepo(work_tree=repo), scratch["P"],
                                                                     scratch["X"]))
        else:
            argv = S9.fetch_argv()
            plan = GW["gw_plan"](END_REF)
        ok(GW["gw_scan"](repo, plan, gw_refuse))

        def run_it():
            with C.ScrubbedEnv() as env:
                return si.run_checked(argv, 600, 1 << 20, env=env, cwd=repo)
        touched = observed(repo, run_it)
    ok(touched, "nothing observed")
    if os.environ.get("K4S_R5_SHOW_OBSERVED"):
        print("OBSERVED %s %r" % (command, [t for t in touched if not t.startswith(S11.STUDY_REL + "/f")]))
    outside = [rel for rel in touched if not covered(plan, rel)]
    ok(outside == [], "git touched paths outside the write-set plan: %r" % outside)
    if command.endswith("fetch"):
        ok(".git/FETCH_HEAD" in touched)
    if command.endswith("checkout"):
        ok(".git/index" in touched and ".git/HEAD" in touched)


# ---------------------------------------------------------------- S11 advance on the fake host (one login)

FOREIGN_NS = "/mpac/sdicks02/jobs/perception-synthetic"                # the fake host's unrelated tree (namespace path)
PACKED_HEADER = b"# pack-refs with: peeled fully-peeled sorted \n"
S11_CASES = [  # Sol's three first, then the rest of the audited write set
    (".git/FETCH_HEAD", "symlink"), (".git/FETCH_HEAD", "hardlink"), (".git/logs/HEAD", "symlink"),
    (".git/logs/HEAD", "hardlink"), (".git/logs/" + HOST_REF, "symlink"), (".git/logs/" + HOST_REF, "hardlink"),
    (".git/ORIG_HEAD", "symlink"), (".git/ORIG_HEAD", "hardlink"), (".git/index", "symlink"), (".git/index", "hardlink"),
    (".git/packed-refs", "symlink"), (".git/packed-refs", "hardlink"), (".git/" + HOST_REF, "hardlink"),
    (".git/refs/heads", "dir-symlink"), (".git/logs", "dir-symlink"), (".git/logs/refs/heads", "dir-symlink"),
    (".git/index.lock", "exists"), (".git/" + HOST_REF + ".lock", "exists"), (".git/HEAD.lock", "exists"),
    (".git/packed-refs.lock", "exists"), (".git/objects/pack", "dir-symlink"), (".git/objects/info", "dir-symlink"),
    (".git/objects/pack/<pack>", "hardlink"), (".git/gc.pid", "symlink"), (".git/objects/info/commit-graph", "symlink"),
    (".git/HEAD", "hardlink"), (".git/config", "hardlink")]
# An EARLIER layer refuses these first (before any fetch, which is what matters); the guard's own refusal of each
# row is proved by test_guard_table_every_row_refuses_its_alias. Values: a word of the reported refusal.
# (They stop at the [check] stage: the existing repository verification, before the bundle is even received.)
S11_EARLIER = {(".git/objects/info", "dir-symlink"): '"symlink"', (".git/config", "hardlink"): '"nlink"',
               (".git/objects/pack", "dir-symlink"): '"root"'}


@pytest.mark.parametrize("case", S11_CASES, ids=[s9_case_id(c) for c in S11_CASES])
def test_s11_advance_refuses_a_write_set_alias_before_the_fetch(world, ready, tmpdir_, repo_copy, advanced_clone,
                                                               monkeypatch, case):
    rel, kind = case
    _, repo = T11.provision_at_p(world, ready, tmpdir_, repo_copy, monkeypatch)
    n = len(T11.s11_logins(ready))
    if rel == ".git/objects/pack/<pack>":
        pack = os.path.join(repo, ".git/objects/pack")
        rel = ".git/objects/pack/" + sorted(os.listdir(pack))[0]
    if rel == ".git/packed-refs":
        make_file(os.path.join(repo, rel), PACKED_HEADER)
    foreign = ready.path(T11.HOST, FOREIGN_NS)
    os.makedirs(foreign, exist_ok=True)
    plant(repo, rel, kind, foreign, target_prefix=FOREIGN_NS)
    state = tree_state(foreign)
    a = T11.advance_args(world, tmpdir_, advanced_clone)
    error = refused("remote-refused", T11.run, a)
    if case in S11_EARLIER:
        ok(S11_EARLIER[case] in error.reason and "stages ['@@RC|check|3']" in error.reason, error.reason)
    else:
        ok('"git-write"' in error.reason and rel in error.reason and "'@@RC|receive|0', '@@RC|advance|3'" in
           error.reason, error.reason)
    ok(len(T11.s11_logins(ready)) == n + 1)
    ok(T11.git(repo, "cat-file", "-e", world.X2 + "^{commit}")[0] != 0, "the fetch ran")
    if kind != "dir-symlink":                       # (a namespace-path symlink does not resolve outside the host)
        ok(T11.git(repo, "rev-parse", "HEAD") == (0, world.P), "the work tree moved")
    ok(tree_state(foreign) == state, "the foreign marker changed")
    T11.receipt(a.record)
    ok(not os.path.exists(os.path.join(a.record, "s11-advance.json")))


def test_s11_advance_healthy_records_the_guard(world, ready, tmpdir_, repo_copy, advanced_clone, monkeypatch):
    _, repo = T11.provision_at_p(world, ready, tmpdir_, repo_copy, monkeypatch)
    prov = json.loads(read(os.path.join(tmpdir_, "prov", "s11-provision.json")))
    gp = prov["result"]["git_write_guard"]
    ok(gp["config"] == list(S9.GW_CONFIG) and gp["fetch"]["release"] == gp["checkout"]["release"] ==
       "k4s-git-write-guard-r6")
    ok(not os.path.exists(os.path.join(repo, ".git/logs")))             # r5: no reflog is created any more
    doc = T11.run(T11.advance_args(world, tmpdir_, advanced_clone))
    ga = doc["result"]["git_write_guard"]
    ok(ga["fetch"]["checked"] > 10 and ga["checkout"]["checked"] > ga["fetch"]["checked"] - 5)
    ok(T11.git(repo, "rev-parse", "HEAD") == (0, world.X2))


# ---------------------------------------------------------------- the host program's _main, locally (guards isolated)

def local_main(world, ready, tmpdir_, repo_copy, advanced_clone, monkeypatch, mode):
    """Run the host program's _main for `mode` on THIS machine against the fake host's tree (the namespace paths
    rewritten to their local equivalents; node name = this host). The bundle is placed as the D4 receive would."""
    if mode == "advance":
        T11.provision_at_p(world, ready, tmpdir_, repo_copy, monkeypatch)
        commit, prior, record = world.X2, world.P, advanced_clone
        end_job = dict(oid=T11.git(world.origin, "rev-parse", "%s:%s" % (world.X2, S9.END_JOB_REL))[1],
                       sha256=sha(world.end_job2))
    else:
        commit, prior, end_job = world.P, None, None
    work = os.path.join(tmpdir_, "bundle-src")
    os.makedirs(work)
    with monkeypatch.context() as m:
        if mode == "provision":
            m.setattr(S9, "REPO_FULL", world.repo_full)
        bundle = S11.make_bundle(work, commit, prior)
    p = S11.params(mode, T11.HOST, commit, bundle, prior, end_job)
    local = ready.path(T11.HOST, p["base"])
    p.update(host=os.uname().nodename.split(".")[0], base=local, tools=ready.path(T11.HOST, p["tools"]))
    transfer = os.path.join(local, p["transfer_leaf"])
    os.makedirs(transfer)
    shutil.copyfile(bundle["path"], os.path.join(transfer, p["bundle_name"]))
    os.chmod(os.path.join(transfer, p["bundle_name"]), 0o444)
    return p, local


def test_s11_host_checkout_guard_isolated_from_the_clean_check(world, ready, tmpdir_, repo_copy, advanced_clone,
                                                                monkeypatch, capfd):
    """The advance checkout guard on its own: _verify (whose clean-status check would see an untracked alias first)
    is stubbed, an alias of the END directory is planted, and the host program's _main must fetch (the .git write
    set is healthy) and then refuse BEFORE the checkout, foreign tree unchanged."""
    import base64
    p, local = local_main(world, ready, tmpdir_, repo_copy, advanced_clone, monkeypatch, "advance")
    repo = os.path.join(local, "repository")
    foreign = os.path.join(tmpdir_, "perception-synthetic")
    os.makedirs(foreign)
    plant(repo, si.STRICT_END_DIR, "dir-symlink", foreign)
    state = tree_state(foreign)
    ns = T11.host_namespace()
    ns["_verify"] = lambda si_, tool, p_, path, commit: dict(head=commit)
    saved = {m: os.sys.modules.get(m) for m in ("safe_input", "k4s_end_host_tool")}
    try:
        with pytest.raises(ns["_Refused"]) as caught:
            ns["_main"](["x", "advance", base64.b64encode(C.canonical(p).encode()).decode()])
    finally:
        for m, v in saved.items():
            if v is None:
                os.sys.modules.pop(m, None)
            else:
                os.sys.modules[m] = v
    ok(caught.value.code == "git-write" and si.STRICT_END_DIR in caught.value.reason, caught.value)
    ok(T11.git(repo, "cat-file", "-e", world.X2 + "^{commit}")[0] == 0)  # the fetch ran (healthy .git)
    ok(T11.git(repo, "rev-parse", "HEAD") == (0, world.P))             # the checkout did not
    ok(tree_state(foreign) == state)


@pytest.mark.parametrize("case", ["extra-path", "fresh-root-not-empty"])
def test_s11_host_main_other_checkout_guards(world, ready, tmpdir_, repo_copy, advanced_clone, monkeypatch, case):
    """advance: the checkout's path set must be exactly END-JOB.json (else refuse before the checkout);
    provision: the fresh work-tree root must hold only .git before the fetch."""
    import base64
    mode = "advance" if case == "extra-path" else "provision"
    p, local = local_main(world, ready, tmpdir_, repo_copy, advanced_clone, monkeypatch, mode)
    ns = T11.host_namespace()
    ns["_verify"] = lambda si_, tool, p_, path, commit: dict(head=commit)
    if case == "extra-path":
        p["end_job_rel"] = S9.END_JOB_REL + ".other"
        ns["_end_job"] = lambda *a: {}
    else:
        real = ns["_git"]

        def init_then_litter(si_, path, args, **kw):
            out = real(si_, path, args, **kw)
            if args[0] == "init":
                make_file(os.path.join(path, "stray"), b"x")
            return out
        ns["_git"] = init_then_litter
    saved = {m: os.sys.modules.get(m) for m in ("safe_input", "k4s_end_host_tool")}
    try:
        with pytest.raises(ns["_Refused"]) as caught:
            ns["_main"](["x", mode, base64.b64encode(C.canonical(p).encode()).decode()])
    finally:
        for m, v in saved.items():
            if v is None:
                os.sys.modules.pop(m, None)
            else:
                os.sys.modules[m] = v
    if case == "extra-path":
        ok(caught.value.code == "check" and "would write" in caught.value.reason, caught.value)
        ok(T11.git(os.path.join(local, "repository"), "rev-parse", "HEAD") == (0, world.P))
    else:
        ok(caught.value.code == "git-write" and "work tree root" in caught.value.reason, caught.value)
        ok(not os.path.exists(os.path.join(local, "repository.partial", ".git", "FETCH_HEAD")))


def test_s11_host_git_w_argv(scratch, tmpdir_, monkeypatch):
    """The host's writing git commands: si.git_run's flags and environment + GW_CONFIG; only fetch/checkout."""
    ns = scratch["ns"]
    seen = []
    real = si.run_checked
    monkeypatch.setattr(si, "run_checked", lambda argv, *a, **k: seen.append((list(argv), dict(k))) or real(argv, *a, **k))
    repo = copy_host(scratch, tmpdir_)
    ns["_git_w"](si, repo, ["checkout", "-q", S9.END_BRANCH])
    argv, kw = seen[-1]
    n = len(si.GIT_GLOBAL_ARGS)
    ok(argv[0] == si.GIT_BINARY and argv[1:1 + n] == list(si.GIT_GLOBAL_ARGS))
    ok(argv[1 + n:1 + n + len(S9.GW_CONFIG)] == list(S9.GW_CONFIG))
    ok(argv[-5:] == ["--git-dir=" + repo + "/.git", "--work-tree=" + repo, "checkout", "-q", S9.END_BRANCH])
    env = kw["env"]
    ok({k: v for k, v in env.items() if k not in ("HOME", "XDG_CONFIG_HOME")} == si.GIT_FIXED_ENV)
    ok(not os.path.exists(env["HOME"]))
    with pytest.raises(ns["_Refused"]):
        ns["_git_w"](si, repo, ["status"])
    make_file(os.path.join(repo, ".git/shallow"), (scratch["P"] + "\n").encode())
    with pytest.raises(si.Refusal):                                       # si's static preflight still runs
        ns["_git_w"](si, repo, ["checkout", "-q", S9.END_BRANCH])


# ---------------------------------------------------------------- detection after the command; descriptor identity

def test_s9_post_fetch_detection(world, repo_copy, origin_branch, tmpdir_, monkeypatch):
    """gw_after (detection only): a write-set alias that appears DURING the fetch (fault injection) is reported as a
    refusal, so no success record is written."""
    origin_branch(world.X2)
    real = si.run_checked

    def fetch_then_alias(argv, *a, **k):
        result = real(argv, *a, **k)
        if "fetch" in argv:
            os.unlink(os.path.join(repo_copy, ".git/FETCH_HEAD"))
            os.symlink(os.path.join(tmpdir_, "elsewhere"), os.path.join(repo_copy, ".git/FETCH_HEAD"))
        return result
    monkeypatch.setattr(si, "run_checked", fetch_then_alias)
    error = refused("git-write", refresh, tmpdir_, world.X2)
    ok(".git/FETCH_HEAD" in error.reason, error.reason)
    ok([n for n in os.listdir(os.path.join(tmpdir_, "rec")) if n.startswith("S9-REFUSAL-")]
       and "s9-refresh-clone.json" not in os.listdir(os.path.join(tmpdir_, "rec")))


@pytest.mark.parametrize("when", ["after-checkout", "dir-swapped"])
def test_s11_host_guarded_post_check_detects(scratch, tmpdir_, when):
    """The host's _guarded: gw_post after the command (fault injection: the command plants an alias / replaces a
    write-set directory) refuses."""
    ns = dict(scratch["ns"])
    repo = copy_host(scratch, tmpdir_)
    real = ns["_git_w"]

    def command_then_damage(si_, path, args, protocols=()):
        out = real(si_, path, args, protocols)
        if when == "after-checkout":
            os.symlink(os.path.join(tmpdir_, "elsewhere"), os.path.join(path, ".git/ORIG_HEAD"))
        else:
            heads = os.path.join(path, ".git/refs/heads")
            os.rename(heads, heads + "-old")
            shutil.copytree(heads + "-old", heads)
        return out
    ns["_git_w"] = command_then_damage
    guarded = scratch["ns"]["_guarded"]
    run_guarded = type(guarded)(guarded.__code__, ns, None, guarded.__defaults__)   # same function, patched globals
    with pytest.raises(ns["_Refused"]) as caught:
        run_guarded(si, repo, ns["gw_plan"](HOST_REF), ["checkout", "-q", S9.END_BRANCH])
    ok(caught.value.code == "git-write", caught.value)


def test_guard_descriptor_must_be_the_inspected_directory(scratch, tmpdir_, monkeypatch):
    """_gw_open_dir: the opened directory must be the one lstat inspected (same dev/ino; a swap between the two
    refuses). Fault injection on the guard's own lstat."""
    repo = copy_host(scratch, tmpdir_)
    real = GW["_gw_lstat"]

    def stale(fd, name, rel, refuse):
        st = real(fd, name, rel, refuse)
        if st is not None and rel == ".git/refs":
            return os.stat_result((st.st_mode, st.st_ino + 1) + tuple(st)[2:])
        return st
    monkeypatch.setitem(GW, "_gw_lstat", stale)
    with pytest.raises(si.Refusal) as caught:
        GW["gw_scan"](repo, GW["gw_plan"](HOST_REF), gw_refuse)
    ok("changed while it was checked" in caught.value.reason, caught.value.reason)


@pytest.mark.parametrize("where", ["write-set-dir", "repository-ancestor"])
def test_guard_lstat_rule_isolated_from_the_nofollow_open(scratch, tmpdir_, monkeypatch, where):
    """W04 / W18: the lstat 'real directory' rule on its own. Fault injection: the guard's descriptor open is replaced
    by one that FOLLOWS symlinks and checks no identity (the masking layer gone); the symlinked directory must still
    refuse, by the lstat rule's own message."""
    repo = copy_host(scratch, tmpdir_)
    monkeypatch.setitem(GW, "_gw_open_dir", lambda fd, name, st, rel, refuse, flags=None: os.open(
        name, os.O_PATH | os.O_DIRECTORY | os.O_CLOEXEC, dir_fd=fd))
    path = repo
    if where == "write-set-dir":
        logs = os.path.join(repo, ".git/logs")
        os.makedirs(os.path.join(tmpdir_, "elsewhere"))
        if os.path.isdir(logs):
            shutil.rmtree(logs)
        os.symlink(os.path.join(tmpdir_, "elsewhere"), logs)
        want = ".git/logs is not a real directory (a symlink or another file type)"
    else:
        os.symlink(tmpdir_, os.path.join(tmpdir_, "alias"))
        path = os.path.join(tmpdir_, "alias", "repo")
        want = "repository path component %s/alias is not a real directory" % tmpdir_
    with pytest.raises(si.Refusal) as caught:
        GW["gw_scan"](path, GW["gw_plan"](HOST_REF), gw_refuse)
    ok(want in caught.value.reason, caught.value.reason)
