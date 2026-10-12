"""Inode canaries under every role (hard-linked mode-000 outcome file; proof it is never opened or read, by inode
and by audit hook), and the exact E1/E4 exemptions."""
import hashlib
import os

import pytest

from conftest import (CANARY_BYTES, canary_unchanged, ident, make_canary, make_file, ok, policy, refusal, role, si)

E4_PATHS = sorted(si.E4_COMPLETE_JSON)
GAP = E4_PATHS[2]
END_JOB = "reports/explore/k4s-confirm/end/END-JOB.json"


def roles_for(base):
    """One role of every shape, each with a declared name `alias` will occupy."""
    r = os.path.join(base, "roots")
    roots = {name: os.path.join(r, name) for name in ("exact", "pattern", "deep", "e1", "e4", "end", "rj", "guard",
                                                      "big")}
    roots["end"] = os.path.join(r, "end-repo")              # END roles root ABOVE end/ and name exact .json files
    roots["rj"] = os.path.join(r, "jobs", "k4s-confirm-replacement-r4")
    roots["guard"] = os.path.join(r, "jobs", "k4s-end-guard-r1-pf01")
    for path in roots.values():
        os.makedirs(path, exist_ok=True)
    roles = [
        (role("exact", roots["exact"], exact=("alias.json",)), "alias.json"),
        (role("pattern", roots["pattern"], patterns=("*.json",)), "alias.json"),
        (role("deep", roots["deep"], patterns=("**",)), "x/y/alias.py"),
        (role("e1", roots["e1"], patterns=("**",), exemptions=("E1",)), "examples/visualize_battle.py"),
        (role("e4", roots["e4"], patterns=("**",), exemptions=("E4",)), GAP),
        (role("end", roots["end"], exact=(END_JOB,), grants=("end-json-exact", "end-claim-exact")), END_JOB),
        (role("rj", roots["rj"], exact=("system-bus-admission.json",), grants=("reporting-job-exact",)),
         "system-bus-admission.json"),
        (role("guard", roots["guard"], patterns=("**",), grants=("guard-job",)), "t1-freeze.json"),
        (role("big", roots["big"], patterns=("**",), max_size=1 << 30, exemptions=("E1", "E4")), "a.json"),
    ]
    return roles


@pytest.mark.parametrize("index", range(9))
def test_hard_linked_outcome_canary_never_opened_under_every_role(base, rec, index):
    canary = make_canary(base)
    r, alias = roles_for(base)[index]
    target = os.path.join(r.root, alias)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    os.link(canary, target)                                      # mode 000, st_nlink 2
    p = policy([r])
    calls = [lambda: si.read_bytes(p, r.name, alias), lambda: si.sha256_input(p, r.name, alias),
             lambda: si.read_json(p, r.name, alias, 1 << 20), lambda: si.open_input(p, r.name, alias),
             lambda: si.walk_tree(p, r.name)]
    if alias in si.E4_COMPLETE_JSON:
        calls = [lambda: si.hash_e4(p, r.name, alias)] + calls[4:]
    if r.name == "e1":
        os.symlink(si.E1_LINK_TEXT, os.path.join(r.root, si.E1_ALIAS))
        calls.append(lambda: si.check_e1(p, r.name))
    with rec:
        for i, call in enumerate(calls):
            walk = call is calls[-1] if r.name != "e1" else i == len(calls) - 2
            refusal("name" if (walk and r.name == "end") else "nlink", call)
    ok(not rec.touched(ident(canary)), "canary inode was opened or read")
    ok(os.path.basename(alias) not in rec.audit_names(), "audit hook saw an open of the alias")
    ok(canary_unchanged(canary))


def test_direct_outcome_name_never_touched(base, rec):
    canary = make_canary(base)
    p = policy([role("all", os.path.join(base, "canary-src"), patterns=("**",), exemptions=("E1", "E4"),
                     grants=("guard-job",))])
    with rec:
        refusal("name", si.read_bytes, p, "all", "games/g1/complete.json")
        refusal("name", si.walk_tree, p, "all")                 # the walk refuses 'games' before entering it
    ok(not rec.touched(ident(canary)))
    ok(all(not (c[0] in ("stat", "open") and c[1] == "games") for c in rec.calls), "games was lstat'ed/opened")


def test_canary_never_reaches_a_writer(base, rec):
    canary = make_canary(base)
    out = os.path.join(base, "out")
    os.makedirs(out)
    os.link(canary, os.path.join(out, "argv.nul"))
    p = policy([role("w", out, access="write", patterns=("**",))])
    w = si.Writer(p, "w")
    with rec:
        refusal("exists", w.create_excl, "argv.nul", b"\x00attacker argv\x00")
    ok(canary_unchanged(canary) and os.stat(canary).st_nlink == 2)


# ---------------------------------------------------------------- E1
@pytest.fixture
def e1tree(base):
    root = os.path.join(base, "repo")
    make_file(os.path.join(root, "examples", "visualize_battle.py"), b"print('vb')\n")
    os.symlink(si.E1_LINK_TEXT, os.path.join(root, si.E1_ALIAS))
    return root


def test_e1_exact_alias(e1tree, rec):
    p = policy([role("rt", e1tree, patterns=("**",), exemptions=("E1",))])
    with rec:
        info = si.check_e1(p, "rt")
    ok(info == {"alias": si.E1_ALIAS, "link": si.E1_LINK_TEXT, "target": si.E1_LINK_TEXT, "target_size": 12})
    ok(ident(os.path.join(e1tree, si.E1_ALIAS)) not in rec.open_attempts, "the alias itself was opened (followed)")
    ok(ident(os.path.join(e1tree, si.E1_LINK_TEXT)) not in rec.read_inodes, "check_e1 read target bytes")
    ok(si.read_bytes(p, "rt", si.E1_LINK_TEXT) == b"print('vb')\n")
    refusal("symlink", si.read_bytes, p, "rt", si.E1_ALIAS)     # never read through the link
    tree = si.walk_tree(p, "rt")
    ok(tree["e1"] == {"rel": si.E1_ALIAS, "link": si.E1_LINK_TEXT})
    ok([f["rel"] for f in tree["files"]] == [si.E1_LINK_TEXT])


def test_e1_refusals(base, e1tree):
    alias = os.path.join(e1tree, si.E1_ALIAS)
    no_e1 = policy([role("rt", e1tree, patterns=("**",))])
    refusal("exemption", si.check_e1, no_e1, "rt")
    refusal("symlink", si.walk_tree, no_e1, "rt")
    p = policy([role("rt", e1tree, patterns=("**",), exemptions=("E1",))])
    os.unlink(alias)
    os.symlink("examples/../examples/visualize_battle.py", alias)
    refusal("exemption", si.check_e1, p, "rt")
    refusal("exemption", si.walk_tree, p, "rt")
    os.unlink(alias)
    os.symlink(os.path.join(e1tree, si.E1_LINK_TEXT), alias)   # absolute text: not the exact entry
    refusal("exemption", si.check_e1, p, "rt")
    os.unlink(alias)
    make_file(alias, b"x")
    refusal("exemption", si.check_e1, p, "rt")                 # a regular file is not the alias
    os.unlink(alias)
    refusal("missing", si.check_e1, p, "rt")
    os.symlink(si.E1_LINK_TEXT, alias)
    target = os.path.join(e1tree, si.E1_LINK_TEXT)
    os.link(target, os.path.join(base, "hl"))
    refusal("nlink", si.check_e1, p, "rt")                     # the target passes the hard-link gate too
    os.unlink(os.path.join(base, "hl"))
    os.rename(target, target + ".real")
    os.symlink(target + ".real", target)
    refusal("symlink", si.check_e1, p, "rt")
    os.unlink(target)
    refusal("exemption", si.walk_tree, p, "rt")                # dangling alias: target absent from the tree
    os.makedirs(os.path.join(e1tree, "sub"))
    os.symlink(si.E1_LINK_TEXT, os.path.join(e1tree, "sub", si.E1_ALIAS))
    os.rename(target + ".real", target)
    refusal("symlink", si.walk_tree, p, "rt")                  # only the root-level entry is exempt


def test_e1_symlink_creation_is_exact(base):
    out = os.path.join(base, "out")
    os.makedirs(out)
    p = policy([role("w", out, access="write", patterns=("**",), exemptions=("E1",)),
                role("w2", out, access="write", patterns=("**",))])
    refusal("exemption", si.Writer(p, "w2").create_e1_symlink)
    w = si.Writer(p, "w")
    w.create_e1_symlink()
    ok(os.readlink(os.path.join(out, si.E1_ALIAS)) == si.E1_LINK_TEXT)
    refusal("exists", w.create_e1_symlink)


# ---------------------------------------------------------------- E4 (hash-only, exact path + SHA)
@pytest.fixture
def e4tree(base):
    root = os.path.join(base, "repo4")
    for path in E4_PATHS:
        make_file(os.path.join(root, path), b"synthetic-transfer-receipt:" + path.encode())
    return root


def synthetic_pins(monkeypatch, root):
    """Test-only: the real pins cannot be matched by synthetic bytes, so the shared dict is patched for this test."""
    for path in E4_PATHS:
        with open(os.path.join(root, path), "rb") as stream:
            monkeypatch.setitem(si.E4_COMPLETE_JSON, path, hashlib.sha256(stream.read()).hexdigest())


def test_e4_hash_only_with_exact_path_and_sha(monkeypatch, base, e4tree):
    synthetic_pins(monkeypatch, e4tree)
    p = policy([role("rt", e4tree, patterns=("**",), exemptions=("E4",)),
                role("out", os.path.join(base, "o"), access="write", patterns=("**",), exemptions=("E4",))])
    for path in E4_PATHS:
        got = si.hash_e4(p, "rt", path)
        ok(set(got) == {"path", "sha256", "size"} and got["sha256"] == si.E4_COMPLETE_JSON[path])
        refusal("name", si.read_bytes, p, "rt", path)            # bytes never through the ordinary API
        refusal("name", si.open_input, p, "rt", path)
    tree = si.walk_tree(p, "rt")
    ok(tree["e4"] == E4_PATHS and tree["files"] == [])
    os.makedirs(os.path.join(base, "o"))
    w = si.Writer(p, "out")
    parent = os.path.dirname(GAP).split("/")
    for i in range(len(parent)):
        w.mkdir_excl("/".join(parent[:i + 1]))
    got = si.copy_e4(p, "rt", GAP, w)
    refusal("exists", si.copy_e4, p, "rt", GAP, w)              # never over an existing copy
    ok(got["sha256"] == si.E4_COMPLETE_JSON[GAP])
    with open(os.path.join(base, "o", GAP), "rb") as stream:
        ok(hashlib.sha256(stream.read()).hexdigest() == got["sha256"])


def test_e4_refusals(monkeypatch, base, e4tree):
    p = policy([role("rt", e4tree, patterns=("**",), exemptions=("E4",)),
                role("plain", e4tree, patterns=("**",))])
    refusal("exemption", si.hash_e4, p, "rt", GAP)              # real pin vs synthetic bytes: refused
    refusal("exemption", si.hash_e4, p, "plain", GAP)           # role without E4
    refusal("name", si.walk_tree, p, "plain")
    make_file(os.path.join(e4tree, "reports", "other", "complete.json"), b"x")
    refusal("exemption", si.hash_e4, p, "rt", "reports/other/complete.json")
    refusal("name", si.walk_tree, p, "rt")                      # unlisted complete.json anywhere refuses the walk
    synthetic_pins(monkeypatch, e4tree)
    os.link(os.path.join(e4tree, GAP), os.path.join(base, "hl"))
    refusal("nlink", si.hash_e4, p, "rt", GAP)
    os.unlink(os.path.join(base, "hl"))
    refusal("exemption", si.hash_e4, p, "rt", GAP.replace("complete.json", "complete.json.tmp"))
    ok(si.hash_e4(p, "rt", GAP)["path"] == GAP)
    with open(os.path.join(e4tree, GAP), "ab") as stream:
        stream.write(b"changed")
    refusal("exemption", si.hash_e4, p, "rt", GAP)


def test_e4_copy_refuses_when_pin_differs(base, e4tree):
    p = policy([role("rt", e4tree, patterns=("**",), exemptions=("E4",)),
                role("out", os.path.join(base, "o"), access="write", patterns=("**",), exemptions=("E4",))])
    os.makedirs(os.path.join(base, "o", os.path.dirname(GAP)))
    refusal("exemption", si.copy_e4, p, "rt", GAP, si.Writer(p, "out"))
    ok(not os.path.exists(os.path.join(base, "o", GAP)))       # the hash pass refused before any copy


def test_e4_copy_rechecks_the_pin_on_the_copy_pass(monkeypatch, base, e4tree):
    synthetic_pins(monkeypatch, e4tree)
    p = policy([role("rt", e4tree, patterns=("**",), exemptions=("E4",)),
                role("out", os.path.join(base, "o"), access="write", patterns=("**",), exemptions=("E4",))])
    os.makedirs(os.path.join(base, "o", os.path.dirname(GAP)))
    real = si.hash_e4

    def then_change(*args):
        got = real(*args)
        with open(os.path.join(e4tree, GAP), "ab") as stream:
            stream.write(b"changed-between-passes")
        return got
    monkeypatch.setattr(si, "hash_e4", then_change)
    refusal("exemption", si.copy_e4, p, "rt", GAP, si.Writer(p, "out"))
    ok(os.path.exists(os.path.join(base, "o", GAP)))           # the refused partial copy is kept, never unlinked
