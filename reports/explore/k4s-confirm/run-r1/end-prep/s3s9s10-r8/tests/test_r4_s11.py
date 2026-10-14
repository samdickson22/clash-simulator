"""r4 S11 (U1) on namespaced fake hosts: the host repository provisioned at P' on k4s-end-r1 and advanced to X, ONE login
per mode, shipped from the verified full clone as a git bundle through the D4 receive, verified on the host with the
S7-pinned host tool (staged by S10's tools component from the byte copies of s5s6s7-r4) and safe_input."""
import json
import os
import subprocess

import pytest

from conftest import C, S9, S10, S11, Args, make_file, ok, read, refused, s10_args, sha, si

HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(HERE, "vendor_s5s6s7_r5")
HOST = "127x03"
BASE = si.END_BASES[HOST]


def git(path, *args):
    env = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "GIT_CONFIG_NOSYSTEM": "1", "LC_ALL": "C"}
    done = subprocess.run(["/usr/bin/git", "-C", path] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=env)
    return done.returncode, done.stdout.decode().strip()


@pytest.fixture
def ready(world, hosts, tmpdir_):
    """A fake 03 whose <base> exists and whose <base>/tools was staged by S10 (the real U2 path)."""
    base = hosts.path(HOST, BASE)
    for d in S10.BASE_SUBDIRS:
        os.makedirs(os.path.join(base, d))
    S10.run(s10_args(tools_source=VENDOR, record=os.path.join(tmpdir_, "s10rec")), log=lambda *a: None)
    hosts.s10_logins = len(hosts.logins())
    return hosts


def s11_logins(hosts):
    return hosts.logins()[hosts.s10_logins:]


def args(mode, tmpdir_, commit, name="rec", **kw):
    base = dict(command=mode, host=HOST, commit=commit, record=os.path.join(tmpdir_, name),
                outside_end_window="TEST S11 GO", dry_run=False, prior=None, equivalence_record=None,
                equivalence_sha256=None, end_job_sha256=None)
    base.update(kw)
    return Args(**base)


def run(a):
    return S11.run(a, log=lambda *x: None)


def receipt(record):
    names = [n for n in os.listdir(record) if n.startswith("S11-REFUSAL-")]
    ok(len(names) == 1, os.listdir(record))
    return json.loads(read(os.path.join(record, names[0])))


def provision(world, ready, tmpdir_):
    doc = run(args("provision", tmpdir_, world.P, name="prov"))
    return doc, ready.path(HOST, BASE + "/repository")


# ---------------------------------------------------------------- provision

def test_provision_one_login_full_clone_on_the_end_branch(world, ready, tmpdir_):
    doc, repo = provision(world, ready, tmpdir_)
    ok(len(s11_logins(ready)) == 1 and doc["ssh_logins"] == 1, s11_logins(ready))
    ok(git(repo, "rev-parse", "HEAD") == (0, world.P), (git(repo, "rev-parse", "HEAD"), os.listdir(repo)))
    ok(git(repo, "rev-parse", "--symbolic-full-name", "HEAD") == (0, "refs/heads/k4s-end-r1"))
    ok(git(repo, "rev-parse", "--is-shallow-repository") == (0, "false"))
    ok(git(repo, "for-each-ref", "--format=%(refname)") == (0, "refs/heads/k4s-end-r1"))
    ok(git(repo, "merge-base", "--is-ancestor", world.base_commit, "HEAD")[0] == 0)
    ok(git(repo, "cat-file", "-e", world.base_commit + "^{commit}")[0] == 0)          # full history, not shallow
    ok(git(repo, "status", "--porcelain", "--untracked-files=all") == (0, ""))
    ok(not os.path.exists(os.path.join(repo, ".git", "hooks")) and not os.path.exists(repo + ".partial"))
    for rel in S9.SUPPORT_PINS:
        ok(read(os.path.join(repo, rel)) == world.files[rel])
    # the consumers' own clone check (S5 repository_clone / S7 frozen reader / S6 frozen-exec), byte copy of r3
    tool = S10.C.bootstrap_sibling("k4s_end_host_tool_vendored", os.path.join(VENDOR, "k4s_end_host_tool.py"),
                                   S10.TOOL_PINS["k4s_end_host_tool.py"][1], S10.TOOL_PINS["k4s_end_host_tool.py"][2])
    rec = tool.verify_clone(si, "127x05", repo, role="repository")
    ok(rec["role"] == "repository" and rec["hooks"] == [] and rec["promisor"] is False)
    # producer_claim can write its registry directory in the work tree (frozen end_evidence.py:499)
    claim_dir = os.path.join(repo, "reports/explore/k4s-confirm/end/registry/round-00/127x03")
    os.makedirs(claim_dir)
    os.rmdir(claim_dir)
    r = doc["result"]
    ok(r["final"]["head"] == world.P and r["partial"]["head"] == world.P and r["final"]["config_keys"] == sorted(
        S11.CORE_KEYS))
    ok(doc["host_paths_kept_needing_authorized_cleanup"] == [BASE + "/repository-transfer-" + world.P[:12]])
    transfer = ready.path(HOST, BASE + "/repository-transfer-" + world.P[:12] + "/" + S11.BUNDLE_NAME)
    ok(sha(read(transfer)) == doc["bundle"]["sha256"] and os.lstat(transfer).st_mode & 0o777 == 0o444)
    ok(doc["bundle"]["prerequisites"] == [] and [list(r) for r in doc["bundle"]["refs"]] == [[world.P, S9.END_BRANCH_REF]])
    ok(doc["check"]["git_version"].startswith("git version"))
    ok(json.loads(read(os.path.join(tmpdir_, "prov", "s11-provision.json")))["status"] == "provisioned")


def test_session_never_deletes_and_ships_sha_bound_programs(world, ready, tmpdir_):
    provision(world, ready, tmpdir_)
    line = s11_logins(ready)[0]
    words = set(line.replace("~", " ").split())
    ok(not {"rm", "rmdir", "unlink", "/usr/bin/rm", "/bin/rm", "tar", "mv"} & words, line[:300])
    ok(si.receive_program_sha256() in line)
    policy = si.Policy(C.local_host(), [C.code_role()])
    data, digest = S11.host_program(policy)
    ok(digest in line and line.count(digest) == 2)                     # check + provision, same program
    ok(data.decode().startswith(read(os.path.join(HERE, "k4s_bootstrap_r1.py")).decode()))   # canonical block verbatim
    ok("'" not in S11.HOST_BOOTSTRAP)


def test_provision_dry_run_no_login_no_leftover(world, ready, tmpdir_, monkeypatch):
    made = []                                     # this run's OWN private bundle dir (parallel suites make their own)
    real = S11.tempfile.mkdtemp
    def spy(*a, **k):
        path = real(*a, **k)
        if k.get("prefix") == "k4s-s11-bundle-":
            made.append(path)
        return path
    monkeypatch.setattr(S11.tempfile, "mkdtemp", spy)
    lines = []
    summary = S11.run(args("provision", tmpdir_, world.P, dry_run=True, record=None), log=lines.append)
    ok(s11_logins(ready) == [] and summary["logins_planned"] == 1 and not os.path.exists(os.path.join(tmpdir_, "rec")))
    ok(len(made) == 1 and made[0].startswith("/tmp/k4s-s11-bundle-") and not os.path.exists(made[0]), made)
    ok(json.loads(lines[0])["bundle"]["sha256"] == summary["bundle"]["sha256"])


@pytest.mark.parametrize("case,code,logins", [
    ("repository-exists", "remote-refused", 1), ("no-tools", "remote-refused", 1),
    ("tampered-host-tool", "remote-refused", 1), ("program-sha", "remote-refused", 1),
    ("bundle-sha", "sha", 1), ("tip-not-commit", "check", 0), ("not-descendant", "check", 0),
    ("corrupted-clone", "indirection", 0), ("no-window", "policy", 0), ("wrong-host-name", "remote-refused", 1)])
def test_provision_refusals(world, hosts, tmpdir_, monkeypatch, case, code, logins):
    base = hosts.path(HOST, BASE)
    for d in S10.BASE_SUBDIRS:
        os.makedirs(os.path.join(base, d))
    if case != "no-tools":
        S10.run(s10_args(tools_source=VENDOR, record=os.path.join(tmpdir_, "s10rec")), log=lambda *a: None)
    hosts.s10_logins = len(hosts.logins())
    a = args("provision", tmpdir_, world.P)
    if case == "repository-exists":
        os.makedirs(os.path.join(base, "repository"))
    elif case == "tampered-host-tool":
        path = os.path.join(base, "tools", "k4s_end_host_tool.py")
        os.chmod(os.path.join(base, "tools"), 0o755)
        os.chmod(path, 0o644)
        data = read(path)
        make_file(path, data[:-3] + b"#\n\n")                           # same size, other bytes
    elif case == "program-sha":
        real = S11.host_program
        monkeypatch.setattr(S11, "host_program", lambda policy: (real(policy)[0], "0" * 64))
    elif case == "bundle-sha":
        real = S11.make_bundle
        monkeypatch.setattr(S11, "make_bundle", lambda *x: dict(real(*x), sha256="0" * 64))
    elif case == "tip-not-commit":
        a = args("provision", tmpdir_, world.X)
    elif case == "not-descendant":
        monkeypatch.setattr(S11, "REQUIRED_ANCESTOR", world.X)
    elif case == "corrupted-clone":
        repo = os.path.join(tmpdir_, "rf")
        subprocess.run(["/bin/cp", "-a", world.repo_full, repo], check=True)
        monkeypatch.setattr(S9, "REPO_FULL", repo)
        with open(os.path.join(repo, ".git/config"), "a") as stream:
            stream.write('[remote "origin"]\n\tpromisor = true\n')
    elif case == "no-window":
        a.outside_end_window = ""
    elif case == "wrong-host-name":
        a.host = "127x04"                                                 # 04 has no base/tools in this fake fleet
    error = refused(code, run, a)
    ok(len(s11_logins(hosts)) == logins, (s11_logins(hosts), error.reason))
    ok(not os.path.exists(os.path.join(base, "repository.partial")) or case == "never")
    if case in ("repository-exists", "no-tools", "tampered-host-tool", "program-sha"):
        ok(not os.path.exists(os.path.join(base, "repository-transfer-" + world.P[:12])), error.reason)  # stopped at check
    if case == "bundle-sha":
        ok("changed while streaming" in error.reason, error.reason)
    receipt(a.record)


# ---------------------------------------------------------------- advance

@pytest.fixture
def advanced_clone(world, repo_copy, tmpdir_, runtime):
    """REPO_FULL (private copy) refreshed to X2 by S9 refresh-clone, and S9 equivalence P -> X2 recorded."""
    world.git(world.origin, "update-ref", "refs/heads/" + S9.END_BRANCH, world.X2)
    try:
        a = Args(command="refresh-clone", commit=world.X2, base_commit=world.P, checkout=False,
                 record=os.path.join(tmpdir_, "refresh"))
        record = C.Record(a.record, "S9", ("s9-refresh-clone.json",)).open()
        try:
            S9.refresh_clone(a, record, log=lambda *x: None)
        finally:
            record.close()
    finally:
        world.git(world.origin, "update-ref", "refs/heads/" + S9.END_BRANCH, world.P)
    ok(S9.main(["equivalence", "--out", runtime["out"], "--manifest-sha256", runtime["sha"], "--end-job-commit",
                world.X2, "--record", os.path.join(tmpdir_, "equiv")]) == 0)
    path = os.path.join(tmpdir_, "equiv", "s9-equivalence.json")
    return dict(record=path, sha=sha(read(path)))


def provision_at_p(world, ready, tmpdir_, repo_copy, monkeypatch):
    """Provision from a REPO_FULL whose branch tip is still P (the advanced copy is installed afterwards)."""
    with monkeypatch.context() as m:
        m.setattr(S9, "REPO_FULL", world.repo_full)
        return provision(world, ready, tmpdir_)


def advance_args(world, tmpdir_, equivalence, **kw):
    base = dict(prior=world.P, equivalence_record=equivalence["record"], equivalence_sha256=equivalence["sha"],
                end_job_sha256=sha(world.end_job2))
    base.update(kw)
    return args("advance", tmpdir_, world.X2, name="adv", **base)


def test_advance_fast_forward_to_x_one_login(world, ready, tmpdir_, repo_copy, advanced_clone, monkeypatch):
    _, repo = provision_at_p(world, ready, tmpdir_, repo_copy, monkeypatch)
    n = len(s11_logins(ready))
    doc = run(advance_args(world, tmpdir_, advanced_clone))
    ok(len(s11_logins(ready)) == n + 1 and doc["ssh_logins"] == 1)
    ok(git(repo, "rev-parse", "HEAD") == (0, world.X2))
    ok(git(repo, "rev-parse", "--symbolic-full-name", "HEAD") == (0, "refs/heads/k4s-end-r1"))
    ok(read(os.path.join(repo, S9.END_JOB_REL)) == world.end_job2)
    ok(git(repo, "status", "--porcelain", "--untracked-files=all") == (0, ""))
    ok(doc["result"]["before"]["head"] == world.P and doc["result"]["final"]["head"] == world.X2)
    ok(doc["result"]["end_job"]["sha256"] == doc["result"]["end_job_committed"]["sha256"] == sha(world.end_job2))
    ok(doc["bundle"]["prerequisites"] == [world.P] and doc["equivalence"]["end_job_commit"] == world.X2)


@pytest.mark.parametrize("case,code,logins", [
    ("equivalence-sha", "sha", 0), ("equivalence-other", "check", 0), ("dirty-claim", "remote-refused", 1),
    ("end-job-sha", "remote-refused", 1), ("from-not-host-head", "remote-refused", 1), ("no-equivalence", "policy", 0),
    ("x-not-tip", "check", 0)])
def test_advance_refusals(world, ready, tmpdir_, repo_copy, advanced_clone, monkeypatch, case, code, logins):
    _, repo = provision_at_p(world, ready, tmpdir_, repo_copy, monkeypatch)
    n = len(s11_logins(ready))
    kw = {}
    if case == "equivalence-sha":
        kw["equivalence_sha256"] = "0" * 64
    elif case == "equivalence-other":
        doc = json.loads(read(advanced_clone["record"]))
        doc["end_job_commit"] = world.X
        path = make_file(os.path.join(tmpdir_, "eq2", "s9-equivalence.json"), json.dumps(doc).encode())
        kw.update(equivalence_record=path, equivalence_sha256=sha(read(path)))
    elif case == "dirty-claim":
        make_file(os.path.join(repo, "reports/explore/k4s-confirm/end/registry/round-00/127x03/attempt-00.json"), b"{}")
    elif case == "end-job-sha":
        kw["end_job_sha256"] = "1" * 64
    elif case == "from-not-host-head":
        git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "stray")
    elif case == "no-equivalence":
        kw.update(equivalence_record=None, equivalence_sha256=None)
    elif case == "x-not-tip":
        a = advance_args(world, tmpdir_, advanced_clone)
        a.commit = world.X
        error = refused(code, run, a)
        ok(len(s11_logins(ready)) == n)
        return
    a = advance_args(world, tmpdir_, advanced_clone, **kw)
    error = refused(code, run, a)
    ok(len(s11_logins(ready)) == n + logins, error.reason)
    if case in ("dirty-claim", "from-not-host-head"):
        ok(not os.path.exists(ready.path(HOST, BASE + "/repository-transfer-" + world.X2[:12])), error.reason)
    if case == "end-job-sha":                                            # refused BEFORE the work tree moved
        ok(git(repo, "rev-parse", "HEAD") == (0, world.P), error.reason)
    receipt(a.record)


def test_cli(world, ready, tmpdir_):
    ok(S11.main(["provision", "--host", HOST, "--commit", world.P, "--dry-run"]) == 0)
    with pytest.raises(SystemExit):
        S11.main(["provision", "--host", HOST, "--commit", world.P])         # --record required (live)
    ok(S11.main(["provision", "--host", HOST, "--commit", "abc", "--dry-run"]) == 2)
    with pytest.raises(SystemExit):
        S11.main(["advance", "--host", HOST, "--commit", world.X2, "--dry-run"])   # --from etc. required
    ok(s11_logins(ready) == [])


# ---------------------------------------------------------------- the host program's own guards, run locally

def host_namespace():
    """The S11 host program (canonical block + HOST_MAIN) WITHOUT its trailing entry block, executed here."""
    policy = si.Policy(C.local_host(), [C.code_role()])
    text = S11.host_program(policy)[0].decode()
    body = text[:text.index("\ntry:\n    _rc = _main(_sys.argv)")]
    ns = {"__name__": "k4s_s11_host_under_test"}
    exec(compile(body, "<k4s-s11-host-test>", "exec"), ns)
    return ns


def verify_params(world):
    return dict(host="127x05", branch=S9.END_BRANCH, required_ancestor=world.base_commit, study=S11.STUDY_REL,
                core_keys=list(S11.CORE_KEYS))


@pytest.mark.parametrize("case", ["ok", "head", "detached", "extra-ref", "untracked", "shallow", "config-key", "hooks",
                                  "not-writable", "ancestor"])
def test_host_verify_branches(world, ready, tmpdir_, case):
    _, repo = provision(world, ready, tmpdir_)
    ns = host_namespace()
    tool = S10.C.bootstrap_sibling("k4s_end_host_tool_vendored", os.path.join(VENDOR, "k4s_end_host_tool.py"),
                                   S10.TOOL_PINS["k4s_end_host_tool.py"][1], S10.TOOL_PINS["k4s_end_host_tool.py"][2])
    p = verify_params(world)
    commit = world.P
    if case == "head":
        commit = world.X
    elif case == "detached":
        git(repo, "checkout", "-q", "--detach", world.P)
    elif case == "extra-ref":
        git(repo, "update-ref", "refs/heads/main", world.P)
    elif case == "untracked":
        make_file(os.path.join(repo, "reports/explore/k4s-confirm/end/registry/round-00/127x03/attempt-00.json"), b"{}")
    elif case == "shallow":
        make_file(os.path.join(repo, ".git", "shallow"), (world.P + "\n").encode())
    elif case == "config-key":
        git(repo, "config", "remote.origin.url", "file:///elsewhere")
    elif case == "hooks":
        make_file(os.path.join(repo, ".git", "hooks", "README.sample"), b"#\n")
    elif case == "not-writable":
        os.chmod(os.path.join(repo, S11.STUDY_REL), 0o555)
    elif case == "ancestor":
        p["required_ancestor"] = world.X
    try:
        if case == "ok":
            rec = ns["_verify"](si, tool, p, repo, commit)
            ok(rec["head"] == world.P and rec["writable"] and rec["refs"] == ["%s refs/heads/k4s-end-r1" % world.P])
        else:
            with pytest.raises((ns["_Refused"], si.Refusal)):
                ns["_verify"](si, tool, p, repo, commit)
    finally:
        os.chmod(os.path.join(repo, S11.STUDY_REL), 0o755)


@pytest.mark.parametrize("case", ["ok", "exists", "symlink", "missing"])
def test_host_publish_is_no_replace(tmpdir_, case):
    ns = host_namespace()
    base = os.path.join(tmpdir_, "base")
    os.makedirs(os.path.join(base, "repository.partial"))
    make_file(os.path.join(base, "repository.partial", "f"), b"new")
    if case == "exists":
        os.makedirs(os.path.join(base, "repository"))                    # an EMPTY dir: rename(2) would replace it
    elif case == "symlink":
        os.rename(os.path.join(base, "repository.partial"), os.path.join(base, "elsewhere"))
        os.symlink(os.path.join(base, "elsewhere"), os.path.join(base, "repository.partial"))
    elif case == "missing":
        os.rename(os.path.join(base, "repository.partial"), os.path.join(base, "elsewhere"))
    if case == "ok":
        ns["_publish"](si, base, "repository.partial", "repository")
        ok(read(os.path.join(base, "repository", "f")) == b"new" and not os.path.exists(base + "/repository.partial"))
    else:
        with pytest.raises((ns["_Refused"], OSError)):
            ns["_publish"](si, base, "repository.partial", "repository")
        if case == "exists":
            ok(os.listdir(os.path.join(base, "repository")) == [])


def test_host_layers_refuse_a_foreign_fingerprint(world, ready, tmpdir_):
    ns = host_namespace()
    tools = ready.path(HOST, BASE + "/tools")
    p = dict(tools=tools, safe_input_sha256=S10.TOOL_PINS["safe_input.py"][1],
             safe_input_size=S10.TOOL_PINS["safe_input.py"][2], safe_input_fingerprint="0" * 64,
             host_tool_sha256=S10.TOOL_PINS["k4s_end_host_tool.py"][1],
             host_tool_size=S10.TOOL_PINS["k4s_end_host_tool.py"][2])
    saved = {m: os.sys.modules.get(m) for m in ("safe_input", "k4s_end_host_tool")}
    try:
        with pytest.raises(ns["_Refused"]):
            ns["_layers"](p)
    finally:
        for m, v in saved.items():                                       # the session's safe_input stays in place
            if v is None:
                os.sys.modules.pop(m, None)
            else:
                os.sys.modules[m] = v


@pytest.mark.parametrize("case", ["ok", "other-ref", "prerequisite-missing", "prerequisite-ok"])
def test_bundle_identity_is_checked(world, tmpdir_, monkeypatch, case):
    """The 05 bundle names exactly the END ref at the commit, with exactly the expected prerequisites (fault
    injection: a bundle of another ref, or a complete bundle where P'..X is expected)."""
    work = os.path.join(tmpdir_, "b")
    os.makedirs(work)
    real = S11.git_bundle_argv
    if case == "other-ref":
        monkeypatch.setattr(S11, "git_bundle_argv", lambda *a: real(*(
            [a[0], a[1], "refs/remotes/origin/main"] if a[0] == "create" else a)))
    elif case == "prerequisite-missing":
        monkeypatch.setattr(S11, "git_bundle_argv", lambda *a: real(*(
            [a[0], a[1], S9.END_BRANCH_REF] if a[0] == "create" else a)))
    if case == "ok":
        b = S11.make_bundle(work, world.P)
        ok(b["prerequisites"] == [] and b["refs"] == [(world.P, S9.END_BRANCH_REF)] and b["spec"] == S9.END_BRANCH_REF)
    elif case == "prerequisite-ok":
        b = S11.make_bundle(work, world.P, prior=world.base_commit)
        ok(b["prerequisites"] == [world.base_commit] and b["spec"] == "%s..%s" % (world.base_commit, S9.END_BRANCH_REF))
    elif case == "other-ref":
        refused("check", S11.make_bundle, work, world.P)
    else:
        error = refused("check", S11.make_bundle, work, world.P, world.base_commit)
        ok("prerequisites" in error.reason, error.reason)


# ---------------------------------------------------------------- guards masked by redundant layers (first campaign)

def test_tip_mismatch_refused_before_any_bundle(world, tmpdir_, monkeypatch):
    """U01: the END tip must be --commit, checked BEFORE a bundle is made (the bundle-identity layers would also catch
    it, later)."""
    made = []
    monkeypatch.setattr(S11, "make_bundle", lambda *a: made.append(a) or {})
    error = refused("check", run, args("provision", tmpdir_, world.X))
    ok("run S9 refresh-clone" in error.reason and made == [], error.reason)


def test_bundle_heads_are_checked_independently_of_the_header(world, tmpdir_, monkeypatch):
    """U05: `git bundle list-heads` must name exactly the END ref at the commit, independently of the header parse
    (fault injection: list-heads filtered to another ref name prints nothing while the header is correct)."""
    work = os.path.join(tmpdir_, "b")
    os.makedirs(work)
    real = S11.git_bundle_argv
    monkeypatch.setattr(S11, "git_bundle_argv", lambda *a: real(*a) + (["refs/heads/k4s-none"]
                                                                       if a[0] == "list-heads" else []))
    error = refused("check", S11.make_bundle, work, world.P)
    ok("bundle heads" in error.reason, error.reason)


@pytest.mark.parametrize("case", ["ok", "oid", "worktree-bytes", "committed-bytes"])
def test_host_end_job_checks(world, tmpdir_, case):
    """U16/U17: the host END-JOB checks, run locally on a clone at X (END-JOB committed): the blob OID at the revision
    and, with end_job_sha256, the bytes (committed: through git_show_file; HEAD: the work-tree file)."""
    repo = os.path.join(tmpdir_, "x")
    subprocess.run(["/usr/bin/git", "clone", "-q", "--no-checkout", world.origin, repo], check=True,
                   env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "GIT_CONFIG_NOSYSTEM": "1"})
    git(repo, "checkout", "-q", "--detach", world.X)
    ns = host_namespace()
    data = read(os.path.join(repo, S9.END_JOB_REL))
    p = dict(host="127x05", end_job_rel=S9.END_JOB_REL, end_job_oid=git(repo, "rev-parse", "HEAD:" + S9.END_JOB_REL)[1],
             end_job_sha256=sha(data))
    if case == "ok":
        ok(ns["_end_job"](si, p, repo, world.X)["sha256"] == sha(data))
        ok(ns["_end_job"](si, p, repo, "HEAD")["oid"] == p["end_job_oid"])
        return
    rev = "HEAD"
    if case == "oid":
        p["end_job_oid"] = "0" * 40
    elif case == "worktree-bytes":
        path = os.path.join(repo, S9.END_JOB_REL)
        make_file(path, data[:-2] + b"9\n")                               # same size, the committed OID unchanged
    else:
        rev = world.X
        p["end_job_sha256"] = "1" * 64
    with pytest.raises((ns["_Refused"], si.Refusal)):
        ns["_end_job"](si, p, repo, rev)


def test_advance_requires_a_strict_descendant_before_any_bundle(world, tmpdir_, repo_copy, advanced_clone, monkeypatch):
    """U03: --from must be a strict ancestor of X on 05, checked BEFORE a bundle is made (fault injection: an
    equivalence record crafted for the non-ancestor main X, so the record check cannot mask it)."""
    doc = json.loads(read(advanced_clone["record"]))
    doc["runtime_commit"] = world.X                                     # main's X is not an ancestor of X2
    path = make_file(os.path.join(tmpdir_, "eqx", "s9-equivalence.json"), json.dumps(doc).encode())
    made = []
    monkeypatch.setattr(S11, "make_bundle", lambda *a: made.append(a) or {})
    a = advance_args(world, tmpdir_, dict(record=path, sha=sha(read(path))), prior=world.X)
    error = refused("check", run, a)
    ok("fast-forward only" in error.reason and made == [], error.reason)
