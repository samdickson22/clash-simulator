"""r3 END-FULL-F4: the live full-clone verification is a MANDATORY precondition of every entrypoint that reads the
dedicated clone (S9 locate / build / verify / equivalence, S3 build / verify, S1b on REPO_FULL; S10 through S9.verify
and S3.verify). Each corruption of a private copy of the synthetic full clone must be refused by EVERY entrypoint,
before any object content or non-clone input is read. Includes Sol's END-FULL-F4 probe (remote.origin.promisor=true:
build / verify / equivalence refuse; the suite runs normal and -O)."""
import os
import shutil

import pytest

from conftest import (C, CANARY, S1B, S3, S9, S10, make_file, ok, refused, s1b_args, s3_args, s10_args, si)

PACK0 = "pack-" + "0" * 40


def corrupt(world, repo, kind):
    """One corruption of the clone at `repo` (test harness git only)."""
    git_dir = os.path.join(repo, ".git")
    config = os.path.join(git_dir, "config")

    def append(text):
        with open(config, "a") as stream:
            stream.write(text)

    if kind == "promisor":                                        # Sol END-FULL-F4 probe
        append('[remote "origin"]\n\tpromisor = true\n')
    elif kind == "promisor-same-line":                            # git reads a variable after the section header
        append('[remote "origin"] promisor = true\n')
        ok(world.git(repo, "config", "--local", "remote.origin.promisor") == b"true\n")
    elif kind == "promisor-bare-key":                             # `promisor` alone means true to git
        append('[remote "origin"]\n\tpromisor\n')
    elif kind == "promisor-pack":
        make_file(os.path.join(git_dir, "objects", "pack", PACK0 + ".promisor"), b"")
    elif kind == "extensions-partialclone":
        append("[extensions]\n\tpartialClone = origin\n")
    elif kind == "remote-partialclonefilter":
        append('[remote "origin"]\n\tpartialclonefilter = blob:none\n')
    elif kind == "core-partialclonefilter":
        append("[core]\n\tpartialCloneFilter = blob:none\n")
    elif kind == "include":
        append("[include]\n\tpath = /tmp/nowhere\n")
    elif kind == "quoted-value":                                  # git would unquote it; the grammar refuses
        with open(config) as stream:
            lines = stream.read().splitlines()
        url = [i for i, line in enumerate(lines) if line.startswith("\turl = ")]
        ok(len(url) == 1)
        lines[url[0]] = '\turl = "%s"' % lines[url[0]][len("\turl = "):]
        with open(config, "w") as stream:
            stream.write("\n".join(lines) + "\n")
    elif kind in ("bare-true", "format-1"):                       # plain-clone values: not bare, format 0
        with open(config) as stream:
            text = stream.read()
        old, new = (("\tbare = false\n", "\tbare = true\n") if kind == "bare-true"
                    else ("\trepositoryformatversion = 0\n", "\trepositoryformatversion = 1\n"))
        ok(text.count(old) == 1)
        with open(config, "w") as stream:
            stream.write(text.replace(old, new))
    elif kind == "hooks-executable":
        make_file(os.path.join(git_dir, "hooks", "post-checkout"), b"#!/bin/sh\nexit 0\n", 0o755)
    elif kind == "hooks-empty-dir":
        os.makedirs(os.path.join(git_dir, "hooks"))
    elif kind == "shallow":
        make_file(os.path.join(git_dir, "shallow"), (world.P + "\n").encode())
    elif kind == "replace-ref":
        core = world.git(repo, "rev-parse", world.P + ":src/clasher/core.py").decode().strip()
        canary = world.git(repo, "hash-object", "-w", "--stdin", data=CANARY).decode().strip()
        world.git(repo, "replace", core, canary)
    elif kind == "alternates":
        make_file(os.path.join(git_dir, "objects", "info", "alternates"), b"/tmp\n")
    elif kind == "http-alternates":
        make_file(os.path.join(git_dir, "objects", "info", "http-alternates"), b"http://example.invalid\n")
    elif kind == "grafts":
        make_file(os.path.join(git_dir, "info", "grafts"), (world.P + "\n").encode())
    elif kind == "config-worktree":
        make_file(os.path.join(git_dir, "config.worktree"), b"[core]\n\tsparseCheckout = false\n")
    elif kind == "tmp-pack":
        make_file(os.path.join(git_dir, "objects", "pack", "tmp_pack_abc123"), b"")
    elif kind == "gitfile":
        moved = repo + "-moved.git"
        os.rename(git_dir, moved)
        make_file(git_dir, ("gitdir: %s\n" % moved).encode())
    else:
        raise AssertionError(kind)


KINDS = ("promisor", "promisor-same-line", "promisor-bare-key", "promisor-pack", "extensions-partialclone",
         "remote-partialclonefilter", "core-partialclonefilter", "include", "quoted-value", "bare-true", "format-1", "hooks-executable",
         "hooks-empty-dir", "shallow", "replace-ref", "alternates", "http-alternates", "grafts", "config-worktree",
         "tmp-pack", "gitfile")
CODES = {"gitfile": "not-dir"}                                    # .git must be a real directory (check_dir)


@pytest.fixture
def clone(world, tmpdir_, monkeypatch):
    """A private copy of the synthetic full clone as REPO_FULL of S9 and S3 (production: the same constant)."""
    path = os.path.join(tmpdir_, "repo-full")
    shutil.copytree(world.repo_full, path, symlinks=True)
    monkeypatch.setattr(S9, "REPO_FULL", path)
    monkeypatch.setattr(S3, "REPO_FULL", path)
    yield path
    if os.path.lexists(path + "-moved.git"):
        shutil.rmtree(path + "-moved.git")


@pytest.fixture
def opened(monkeypatch):
    """Every gated local open (role name, rel) and every object-content read (oid) during the call."""
    seen = dict(opens=[], objects=[])
    real_open, real_object = si._open_gated, si._git_object

    def spy_open(policy, role_name, rel, *a, **k):
        seen["opens"].append((role_name, rel))
        return real_open(policy, role_name, rel, *a, **k)

    def spy_object(repo, oid, *a, **k):
        seen["objects"].append(oid)
        return real_object(repo, oid, *a, **k)
    monkeypatch.setattr(si, "_open_gated", spy_open)
    monkeypatch.setattr(si, "_git_object", spy_object)
    return seen


def s9_policy(out):
    return si.Policy(C.local_host(), [S9.repo_role()] + S9.verify_roles("s9", out))


def entry_s9_build(world, ctx, tmpdir_):
    return S9.build(ctx["Args"](commit=world.P, out=os.path.join(tmpdir_, "rt"), python=world.python),
                    log=lambda *a: None)


def entry_s9_verify(world, ctx, tmpdir_):
    return S9.verify(s9_policy(ctx["runtime"]["out"]), "s9", ctx["runtime"]["sha"], log=lambda *a: None)


def entry_s9_equivalence(world, ctx, tmpdir_):
    return S9.equivalence(s9_policy(ctx["runtime"]["out"]), "s9", ctx["runtime"]["sha"], world.X, log=lambda *a: None)


def entry_s3_build(world, ctx, tmpdir_):
    return S3.build(s3_args(world, ctx["s1b_out"], os.path.join(tmpdir_, "guard")), log=lambda *a: None)


def entry_s3_verify(world, ctx, tmpdir_):
    g = ctx["guard03"]
    policy = si.Policy(C.local_host(), S3.verify_roles("s3", g["out"], g["job"]))
    return S3.verify(policy, "s3", g["out"], g["job"], g["sha"], log=lambda *a: None)


def entry_s1b(world, ctx, tmpdir_):
    return S1B.run(s1b_args(world, os.path.join(tmpdir_, "s1b"), repository=S9.REPO_FULL, dry_run=True),
                   log=lambda *a: None)


ENTRIES = dict(s9_build=entry_s9_build, s9_verify=entry_s9_verify, s9_equivalence=entry_s9_equivalence,
               s3_build=entry_s3_build, s3_verify=entry_s3_verify, s1b=entry_s1b)


@pytest.fixture
def ctx(request, world):
    from conftest import Args
    out = dict(Args=Args)
    for name in ("runtime", "s1b_out", "guard03"):               # session artifacts built from the healthy clone
        out[name] = request.getfixturevalue(name)
    return out


def test_healthy_copy_passes_every_entrypoint_precondition(world, clone, opened):
    facts = S9.require_full_clone((world.P, world.X))
    ok(opened["opens"] == [("clone", ".git/config")], opened)       # the spy is live: only the clone config is read
    ok(facts["repository"] == clone and facts["shallow"] is False and facts["replace_refs"] == 0)
    ok(sorted(facts["config_keys"]) == sorted(S9.CLONE_CONFIG_KEYS) and facts["absent"] == list(S9.CLONE_ABSENT))
    ok(facts["packs"] and all(S9.CLONE_PACK_NAME.fullmatch(n) for n in facts["packs"]), facts["packs"])


@pytest.mark.parametrize("entry", sorted(ENTRIES))
@pytest.mark.parametrize("kind", KINDS)
def test_every_entrypoint_refuses_a_corrupted_clone(world, clone, ctx, tmpdir_, opened, entry, kind):
    corrupt(world, clone, kind)
    error = refused(CODES.get(kind, "indirection"), ENTRIES[entry], world, ctx, tmpdir_)
    ok(opened["objects"] == [], "object content read before the precondition: %r" % opened["objects"][:3])
    ok(all(role == "clone" for role, _ in opened["opens"]),
       "non-clone input opened before the precondition: %r" % opened["opens"][:4])
    ok(not os.path.exists(os.path.join(tmpdir_, "rt")) and not os.path.exists(os.path.join(tmpdir_, "guard")))
    if entry in ("s9_build", "s3_build"):                         # refused inside .partial: a receipt, no output
        partial = os.path.join(tmpdir_, "rt.partial" if entry == "s9_build" else "guard.partial")
        ok([n for n in os.listdir(partial) if "-REFUSAL-" in n], os.listdir(partial))
    ok(error.reason)


@pytest.mark.parametrize("kind", ("promisor", "shallow", "replace-ref", "alternates"))
def test_locate_cli_refuses_a_corrupted_clone(world, clone, opened, capsys, kind):
    corrupt(world, clone, kind)
    ok(S9.main(["locate", "--commit", world.P]) == 2)
    ok("S9 REFUSED: indirection" in capsys.readouterr().err)
    ok(opened["objects"] == [] and all(role == "clone" for role, _ in opened["opens"]), opened)


@pytest.mark.parametrize("kind", ("promisor", "hooks-executable", "shallow"))
def test_s10_staging_refuses_before_any_login(world, clone, ctx, hosts, tmpdir_, kind):
    """S10 consumes S9.verify / S3.verify: a corrupted clone refuses on 05, before the first login."""
    corrupt(world, clone, kind)
    g, rt = ctx["guard03"], ctx["runtime"]
    for a in (s10_args(runtime=rt["out"], runtime_manifest_sha256=rt["sha"], record=os.path.join(tmpdir_, "r1")),
              s10_args(guard_job=g["out"], guard_job_name=g["job"], guard_manifest_sha256=g["sha"],
                       record=os.path.join(tmpdir_, "r2"))):
        refused("indirection", S10.run, a, log=lambda *x: None)
    ok(hosts.logins() == [])


def test_s1b_live_run_on_the_clone_refuses_before_any_login(world, clone, hosts, tmpdir_):
    corrupt(world, clone, "promisor")
    dest = os.path.join(tmpdir_, "s1b")
    refused("indirection", S1B.run, s1b_args(world, dest, repository=clone), log=lambda *a: None)
    ok(hosts.logins() == [])
    ok([n for n in os.listdir(dest) if n.startswith("S1B-REFUSAL-")], os.listdir(dest))


def test_prepare_clone_receipt_is_not_a_substitute(world, clone, tmpdir_):
    """A directory named repo-full (even with a prepare receipt beside it) proves nothing: the recheck runs live."""
    make_file(clone + "-PREPARE.json", b'{"schema": "%s"}\n' % S9.CLONE_SCHEMA.encode())
    corrupt(world, clone, "promisor")
    refused("indirection", S9.require_full_clone, (world.P,))


@pytest.mark.parametrize("text", ['[remote.origin]\n\tpromisor = true\n', '[core]\n\tbare = false # x\n',
                                  '\tstray = 1\n', '[core]\n\tname = "a\\"b"\n'])
def test_config_grammar_refusals(world, clone, text):
    path = os.path.join(clone, ".git", "config")
    with open(path) as stream:
        good = stream.read()
    with open(path, "w") as stream:
        stream.write(text + good if text.startswith("\t") else good + text)
    refused("indirection", S9.require_full_clone, ())


def test_config_non_utf8_refused(world, clone):
    with open(os.path.join(clone, ".git", "config"), "ab") as stream:
        stream.write(b"# \xff\xfe\n")
    refused("indirection", S9.require_full_clone, ())


def test_s3_and_s9_bind_the_same_clone_in_production():
    from conftest import ORIG
    ok(ORIG[("s9_end_runtime", "REPO_FULL")] == ORIG[("s3_guard_job", "REPO_FULL")]
       == "/mpac/sdicks02/k4s-runner/run-r1/end-prep/repo-full")


def test_commits_must_be_in_the_verified_clone(world, runtime, tmpdir_, monkeypatch):
    """A healthy full clone that lacks the commit refuses: require_full_clone() checks every given commit, and
    S9.verify binds the runtime manifest's commit to the verified clone."""
    from conftest import Args
    other = os.path.join(tmpdir_, "other-origin")
    os.makedirs(other)
    world.git(other, "init", "-q", "--template=")
    world.git(other, "symbolic-ref", "HEAD", "refs/heads/main")
    only = world.git.commit(other, {"README": b"another history\n"}, "unrelated")
    monkeypatch.setattr(S9, "ORIGIN_URL", "file://" + other)
    monkeypatch.setattr(S9, "REPO_FULL", os.path.join(tmpdir_, "repo-full"))
    S9.prepare_clone(Args(commit=only), log=lambda *a: None)
    ok(S9.require_full_clone((only,))["commits"] == [only])
    with pytest.raises(si.Refusal):
        S9.require_full_clone((world.P,))
    with pytest.raises(si.Refusal):
        S9.verify(s9_policy(runtime["out"]), "s9", runtime["sha"], log=lambda *a: None)


@pytest.mark.parametrize("line,value", [(1, b"true"), (2, b"true"), (0, b"/elsewhere/.git"), (3, b"/elsewhere")])
def test_git_view_must_agree(world, clone, monkeypatch, line, value):
    """Fault injection (test-only): if git itself reported a bare / shallow / relocated repository while every
    static check passed, verify_clone() still refuses (the rev-parse cross-check is independent of the file checks)."""
    real = si.git_run

    def lying(repo, args, *a, **k):
        result = real(repo, args, *a, **k)
        if args[:2] == ["rev-parse", "--absolute-git-dir"]:
            lines = result.stdout.split(b"\n")
            lines[line] = value
            result = si.RunResult(result.argv, result.rc, b"\n".join(lines), result.stderr)
        return result
    monkeypatch.setattr(si, "git_run", lying)
    error = refused("indirection", S9.require_full_clone, ())
    ok("non-bare, non-shallow" in error.reason, error.reason)
