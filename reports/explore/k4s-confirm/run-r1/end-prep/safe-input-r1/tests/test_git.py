"""Git tree gate: names/modes/E1/E4 decided from tree metadata BEFORE any blob is read (reviewer probe S9-F1)."""
import hashlib
import os
import subprocess

import pytest

from conftest import make_file, ok, policy, refusal, role, si

GIT = "/usr/bin/git"
E4_PATHS = sorted(si.E4_COMPLETE_JSON)
GAP = E4_PATHS[2]


def git(repo, *args):
    env = dict(si.GIT_ENV, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t")
    return subprocess.run([GIT, "-C", repo] + list(args), check=True, stdout=subprocess.PIPE, env=env).stdout


def make_repo(base, files, symlinks=()):
    repo = os.path.join(base, "repo")
    os.makedirs(repo)
    git(repo, "init", "-q")
    for path, data in files.items():
        make_file(os.path.join(repo, path), data)
    for path, text in symlinks:
        os.symlink(text, os.path.join(repo, path))
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "synthetic")
    return repo, git(repo, "rev-parse", "HEAD").decode().strip()


def logging_git(base):
    """A git wrapper that logs every argv, so a test can prove no blob was read."""
    log = os.path.join(base, "git.log")
    path = os.path.join(base, "git-logged")
    with open(path, "w") as stream:
        stream.write('#!/bin/sh\necho "$*" >> %s\nexec %s "$@"\n' % (log, GIT))
    os.chmod(path, 0o755)
    return path, log


def read_log(log):
    if not os.path.exists(log):
        return []
    with open(log) as stream:
        return stream.read().splitlines()


def rpol(repo, **kw):
    args = dict(patterns=("**",), exemptions=("E1", "E4"))
    args.update(kw)
    return policy([role("rt", repo, **args)])


def test_reviewer_probe_games_and_unlisted_complete_json(base):
    repo, head = make_repo(base, {"games/reviewer.json": b"{}", "reports/other/complete.json": b"{}",
                                  "src/a.py": b"x = 1\n"})
    wrapper, log = logging_git(base)
    entries = si.git_ls_tree(repo, head, wrapper)
    refusal("name", si.gate_git_tree, rpol(repo), "rt", entries)
    ok(not any("cat-file" in line for line in read_log(log)), "a blob was read before the gate refused")
    only_complete = [e for e in entries if e["path"] != "games/reviewer.json"]
    refusal("name", si.gate_git_tree, rpol(repo), "rt", only_complete)
    only_games = [e for e in entries if e["path"] != "reports/other/complete.json"]
    refusal("name", si.gate_git_tree, rpol(repo), "rt", only_games)


@pytest.mark.parametrize("path", ["reports/explore/k4s-confirm/end/END-JOB.json", "x/hub-blocks/b",
                                  "k4s-confirm-reporting-r1/launch.json", "a/end-raw.json", "a/hub-ack.returned.json"])
def test_forbidden_tracked_paths_refuse(base, path):
    repo, head = make_repo(base, {path: b"{}", "ok.py": b""})
    refusal("name", si.gate_git_tree, rpol(repo), "rt", si.git_ls_tree(repo, head))


def test_symlinks_only_exact_e1(base):
    repo, head = make_repo(base, {"examples/visualize_battle.py": b"print(1)\n"},
                           [("other.py", "examples/visualize_battle.py")])
    refusal("symlink", si.gate_git_tree, rpol(repo), "rt", si.git_ls_tree(repo, head))
    repo2, head2 = make_repo(os.path.join(base, "b"), {"examples/visualize_battle.py": b"print(1)\n"},
                             [(si.E1_ALIAS, "examples/./visualize_battle.py")])
    entries = si.git_ls_tree(repo2, head2)
    refusal("symlink", si.gate_git_tree, rpol(repo2, exemptions=("E4",)), "rt", entries)
    plan = si.gate_git_tree(rpol(repo2), "rt", entries)
    refusal("exemption", si.git_blob, repo2, plan, plan["e1"])   # wrong link text


def test_gitlink_and_modes_refuse(base):
    repo, head = make_repo(base, {"a.py": b""})
    git(repo, "update-index", "--add", "--cacheinfo", "160000,%s,sub" % head)
    git(repo, "commit", "-q", "-m", "gitlink")
    head = git(repo, "rev-parse", "HEAD").decode().strip()
    refusal("not-regular", si.gate_git_tree, rpol(repo), "rt", si.git_ls_tree(repo, head))


def test_e4_through_git(monkeypatch, base):
    files = {p: b"receipt-" + p.encode() for p in E4_PATHS}
    files["examples/visualize_battle.py"] = b"print(1)\n"
    files["src/m.py"] = b"y = 2\n"
    repo, head = make_repo(base, files, [(si.E1_ALIAS, si.E1_LINK_TEXT)])
    entries = si.git_ls_tree(repo, head)
    refusal("name", si.gate_git_tree, rpol(repo, exemptions=("E1",)), "rt", entries)
    plan = si.gate_git_tree(rpol(repo), "rt", entries)
    ok(sorted(e["path"] for e in plan["e4"]) == E4_PATHS)
    refusal("exemption", si.git_hash_e4, repo, plan, plan["e4"][0])     # real pins vs synthetic bytes
    refusal("policy", si.git_blob, repo, plan, plan["e4"][0])            # never as ordinary bytes
    for p in E4_PATHS:
        monkeypatch.setitem(si.E4_COMPLETE_JSON, p, hashlib.sha256(files[p]).hexdigest())
    got = si.git_hash_e4(repo, plan, plan["e4"][0])
    ok(set(got) == {"path", "sha256", "size"})
    out = os.path.join(base, "export")
    os.makedirs(out)
    p = policy([role("w", out, access="write", patterns=("**",), exemptions=("E1", "E4"))])
    refusal("policy", si.git_export, repo, plan, si.Writer(p, "w"), "follow")
    inventory = si.git_export(repo, plan, si.Writer(p, "w"), "symlink")
    ok(os.readlink(os.path.join(out, si.E1_ALIAS)) == si.E1_LINK_TEXT)
    for path, data in files.items():
        with open(os.path.join(out, path), "rb") as stream:
            ok(stream.read() == data)
        ok(inventory[path]["sha256"] == hashlib.sha256(data).hexdigest())
    refusal("exists", si.git_export, repo, plan, si.Writer(p, "w"), "symlink")   # never over an existing export
    out2 = os.path.join(base, "export2")
    os.makedirs(out2)
    p2 = policy([role("w", out2, access="write", patterns=("**",), exemptions=("E4",))])
    inventory = si.git_export(repo, plan, si.Writer(p2, "w"), "copy")
    alias = os.path.join(out2, si.E1_ALIAS)
    ok(not os.path.islink(alias) and os.stat(alias).st_nlink == 1)
    with open(alias, "rb") as stream:
        ok(stream.read() == files["examples/visualize_battle.py"])
    ok(inventory[si.E1_ALIAS]["copy_of"] == si.E1_LINK_TEXT)


def test_ls_tree_status_and_format(base):
    repo, head = make_repo(base, {"a.py": b"1"})
    refusal("subprocess", si.git_ls_tree, repo, "HEAD")
    refusal("subprocess", si.git_ls_tree, repo, "0" * 40)               # unknown commit: git rc != 0
    fake = os.path.join(base, "fakegit")
    with open(fake, "w") as stream:
        stream.write("#!/bin/sh\nprintf '100644 blob %s       1\\tgames/x.json\\000'; exit 37\n" % ("a" * 40))
    os.chmod(fake, 0o755)
    refusal("subprocess", si.git_ls_tree, repo, head, fake)              # valid listing + rc 37
    with open(fake, "w") as stream:
        stream.write("#!/bin/sh\nprintf 'garbage\\tx.py\\000'\n")
    refusal("subprocess", si.git_ls_tree, repo, head, fake)              # rc 0 but a malformed record


def test_blob_identity_checked(base, monkeypatch):
    repo, head = make_repo(base, {"a.py": b"abc"})
    plan = si.gate_git_tree(rpol(repo), "rt", si.git_ls_tree(repo, head))
    ok(si.git_blob(repo, plan, plan["files"][0]) == b"abc")
    forged = dict(plan["files"][0], oid="1" * 40)
    plan["files"].append(forged)
    refusal("subprocess", si.git_blob, repo, plan, forged)               # git refuses the unknown object
    refusal("policy", si.git_blob, repo, plan, dict(plan["files"][0]))   # an unplanned entry object


def test_blob_bytes_must_hash_to_the_object_id(base):
    repo, head = make_repo(base, {"a.py": b"abc"})
    plan = si.gate_git_tree(rpol(repo), "rt", si.git_ls_tree(repo, head))
    for name, body, code in (("swap", "printf xyz", "sha"), ("short", "printf ab", "size")):
        fake = os.path.join(base, name)
        with open(fake, "w") as stream:
            stream.write("#!/bin/sh\n%s\n" % body)
        os.chmod(fake, 0o755)
        refusal(code, si.git_blob, repo, plan, plan["files"][0], fake)


def entry(path, mode="100644", kind="blob", size=1):
    return {"mode": mode, "type": kind, "oid": "a" * 40, "size": size, "path": path}


@pytest.mark.parametrize("bad,code", [
    (entry("x.py", mode="100664"), "not-regular"), (entry("x.py", kind="tree"), "not-regular"),
    (entry("x.py", mode="160000", kind="commit"), "not-regular"), (entry("x.py", size=(1 << 20) + 1), "size"),
    (entry("x.py", size=None), "size"), (entry("../x.py"), "path"), (entry("games/x.py"), "name"),
    (entry("visualize_battle.py", mode="120000"), "exemption"),          # E1 entry without its target
])
def test_pure_tree_gate(base, bad, code):
    p = policy([role("rt", base, patterns=("**",), exemptions=("E1", "E4"), max_size=1 << 20)])
    refusal(code, si.gate_git_tree, p, "rt", [entry("ok.py"), bad])
    refusal("path", si.gate_git_tree, p, "rt", [entry("ok.py"), entry("ok.py")])


def test_git_show_file(base):
    repo, head = make_repo(base, {"a/x.json": b'{"k": 1}', "examples/visualize_battle.py": b"v", "big.bin": b"z" * 64,
                                  "games/g.json": b"{}", "a/complete.json": b"{}"},
                           [("a/link.json", "x.json")])
    wrapper, log = logging_git(base)
    p = policy([role("repo", repo, exact=("examples",), patterns=("a/*", "big.bin", "examples/*", "nope.json"),
                     max_size=32),
                role("other", base, patterns=("**",))])
    ok(si.git_show_file(p, "repo", repo, head, "a/x.json", git_binary=wrapper) == b'{"k": 1}')
    ok(si.git_show_file(p, "repo", repo, head, "a/x.json",
                        expected_sha256=hashlib.sha256(b'{"k": 1}').hexdigest()) == b'{"k": 1}')
    refusal("sha", si.git_show_file, p, "repo", repo, head, "a/x.json", expected_sha256="0" * 64)
    before = len(read_log(log))
    refusal("name", si.git_show_file, p, "repo", repo, head, "games/g.json", git_binary=wrapper)
    refusal("name", si.git_show_file, p, "repo", repo, head, "a/complete.json", git_binary=wrapper)
    refusal("allowlist", si.git_show_file, p, "repo", repo, head, "src.py", git_binary=wrapper)
    refusal("root", si.git_show_file, p, "other", repo, head, "a/x.json", git_binary=wrapper)
    ok(len(read_log(log)) == before, "git ran before a name/allowlist/root refusal")
    refusal("symlink", si.git_show_file, p, "repo", repo, head, "a/link.json")
    refusal("size", si.git_show_file, p, "repo", repo, head, "big.bin")
    refusal("size", si.git_show_file, p, "repo", repo, head, "a/x.json", max_size=3)
    refusal("missing", si.git_show_file, p, "repo", repo, head, "nope.json")
    refusal("subprocess", si.git_show_file, p, "repo", repo, "HEAD", "a/x.json")
    refusal("not-regular", si.git_show_file, p, "repo", repo, head, "examples")   # a tree, not a blob
    os.symlink(os.path.join(base, "nonexistent"), os.path.join(repo, "a", "y.json"))
    fake = os.path.join(base, "fake-ls")
    with open(fake, "w") as stream:
        stream.write("#!/bin/sh\nprintf '100644 blob %s       8\\ta/x.json\\000100644 blob %s       8\\ta/y.json\\000'\n"
                     % ("a" * 40, "b" * 40))
    os.chmod(fake, 0o755)
    e = refusal("subprocess", si.git_show_file, p, "repo", repo, head, "a/x.json", git_binary=fake)
    ok("exactly" in e.reason, e.reason)                                  # refused at the listing, not later
    with open(fake, "w") as stream:
        stream.write("#!/bin/sh\nprintf '100644 blob %s       8\\ta/y.json\\000'\n" % ("b" * 40))
    e = refusal("subprocess", si.git_show_file, p, "repo", repo, head, "a/x.json", git_binary=fake)
    ok("exactly" in e.reason, e.reason)                                  # another path than the one asked for
