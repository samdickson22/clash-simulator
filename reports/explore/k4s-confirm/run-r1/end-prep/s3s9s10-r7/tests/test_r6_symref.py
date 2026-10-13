"""r6 (Sol fix-check r5, U10): a symbolic or indirect DESTINATION ref moves git's ref and reflog writes to paths the
write-set plan never inspected. Sol's reproduction: refs/remotes/origin/k4s-end-r1 -> `ref: refs/remotes/victim/branch`
with the victim's reflog aliased (leaf symlink, hard link, symlinked ancestor) to a SYNTHETIC foreign marker; the fetch
appended to the marker and only the late ref comparison refused. Now every ref a command updates must be a direct ref
BEFORE it runs: the shared guard (gw_refs: the validated loose file holds exactly one object name; packed-refs is well
formed with no peeled line for it) and git's own view (for-each-ref %(symref)). Each case requires refusal before the
fetch (no writing git command ran; FETCH_HEAD unchanged), the foreign marker byte-identical, and no success record."""
import base64
import os

import pytest

from conftest import C, S9, make_file, ok, read, refused, si
import test_r4_s11 as T11
from test_r4_s11 import advanced_clone, ready  # noqa: F401  (fixtures)
from test_r4_s9 import origin_branch, refresh  # noqa: F401  (fixture)
from test_r5_git_write import (FOREIGN_NS, HOST_REF, MARKER, copy_host, fetch_spy, git_writes, gw_refuse,  # noqa: F401
                               local_main, scratch, tree_state)

GW = S9._GW
END_REF = S9.END_BRANCH_REF
VICTIM = "refs/remotes/victim/branch"
ALIASES = ["leaf-symlink", "hardlink", "ancestor-symlink"]                 # Sol's three, in his order


def plant_victim_log(repo, victim, alias, foreign, target_prefix=None):
    """Alias .git/logs/<victim> to the foreign marker: the leaf as a symlink or a hard link, or a symlinked ancestor
    directory holding the marker under the leaf's name. Returns the foreign file that git would append to."""
    log = os.path.join(repo, ".git/logs", victim)
    name = os.path.basename(log)
    os.makedirs(foreign, exist_ok=True)
    if alias == "ancestor-symlink":
        sub = os.path.join(foreign, "victim-dir")
        os.makedirs(sub)
        make_file(os.path.join(sub, name), MARKER)
        os.makedirs(os.path.dirname(os.path.dirname(log)), exist_ok=True)
        os.symlink((target_prefix or foreign) + "/victim-dir", os.path.dirname(log))
        return os.path.join(sub, name)
    target = os.path.join(foreign, "victim-log")
    make_file(target, MARKER)
    os.makedirs(os.path.dirname(log), exist_ok=True)
    if alias == "leaf-symlink":
        os.symlink((target_prefix or foreign) + "/victim-log", log)
    else:
        os.link(target, log)
    return target


def fetch_head(repo):
    path = os.path.join(repo, ".git/FETCH_HEAD")
    return read(path) if os.path.lexists(path) else None


def only_refusal(record_dir, prefix="S9-REFUSAL-"):
    names = os.listdir(record_dir)
    ok(len(names) == 1 and names[0].startswith(prefix), names)


# ---------------------------------------------------------------- S9 refresh-clone: Sol's three cases

@pytest.mark.parametrize("alias", ALIASES)
def test_s9_refresh_refuses_a_symbolic_destination_before_the_fetch(world, repo_copy, origin_branch, tmpdir_,
                                                                    fetch_spy, alias):
    make_file(os.path.join(repo_copy, ".git", VICTIM), (world.P + "\n").encode())
    world.git(repo_copy, "symbolic-ref", END_REF, VICTIM)
    foreign_dir = os.path.join(tmpdir_, "perception-synthetic")
    marker = plant_victim_log(repo_copy, VICTIM, alias, foreign_dir)
    state, fh = tree_state(foreign_dir), fetch_head(repo_copy)
    origin_branch(world.X2)
    S9.require_full_clone((world.P,))                                  # Sol: the earlier layers pass this state
    error = refused("git-write", refresh, tmpdir_, world.X2, base=world.P)
    ok(".git/" + END_REF in error.reason and "symbolic ref" in error.reason, error.reason)
    ok(git_writes(fetch_spy) == [], "a writing git command ran: %r" % git_writes(fetch_spy))
    ok(fetch_head(repo_copy) == fh, "FETCH_HEAD changed")
    ok(read(marker) == MARKER and tree_state(foreign_dir) == state, "the foreign marker changed")
    only_refusal(os.path.join(tmpdir_, "rec"))


PACKED_LINE = "%s " + END_REF + "\n"


@pytest.mark.parametrize("case", ["onelevel-symref", "loose-no-newline", "loose-two-lines", "packed-peeled",
                                  "packed-symref-line"])
def test_s9_refresh_refuses_other_indirect_destinations_before_the_fetch(world, repo_copy, origin_branch, tmpdir_,
                                                                         fetch_spy, case):
    """The other indirect / unexpected forms of the destination: a symbolic ref to a one-level name, a loose file that
    is not exactly '<oid>\\n', a peeled packed-refs entry, a packed-refs line that is not '<oid> <ref>'."""
    loose = os.path.join(repo_copy, ".git", END_REF)
    packed = os.path.join(repo_copy, ".git/packed-refs")
    text = read(packed).decode()
    ok((PACKED_LINE % world.P) in text, "the fixture's destination ref is packed")
    if case == "onelevel-symref":
        make_file(os.path.join(repo_copy, ".git/VICTIM_HEAD"), (world.P + "\n").encode())
        make_file(loose, b"ref: VICTIM_HEAD\n")
    elif case == "loose-no-newline":
        make_file(loose, world.P.encode())
    elif case == "loose-two-lines":
        make_file(loose, (world.P + "\n" + world.P + "\n").encode())
    else:
        extra = ("^" + world.P + "\n") if case == "packed-peeled" else ("ref: " + VICTIM + "\n")
        text = text.replace(PACKED_LINE % world.P, PACKED_LINE % world.P + extra)
        os.chmod(packed, 0o644)
        make_file(packed, text.encode())
    fh = fetch_head(repo_copy)
    origin_branch(world.X2)
    if case == "packed-symref-line":                # git itself cannot read it: an earlier S9 git call refuses first
        error = refused("subprocess", refresh, tmpdir_, world.X2)
        ok("unexpected line" in error.reason and "packed-refs" in error.reason, error.reason)
    else:
        error = refused("git-write", refresh, tmpdir_, world.X2)
        ok(("packed-refs" if case.startswith("packed") else ".git/" + END_REF) in error.reason, error.reason)
    ok(git_writes(fetch_spy) == [] and fetch_head(repo_copy) == fh)
    only_refusal(os.path.join(tmpdir_, "rec"))


def test_s9_git_view_check_isolated_from_the_guard(world, repo_copy, origin_branch, tmpdir_, fetch_spy, monkeypatch):
    """require_direct_ref on its own: gw_refs disabled (fault injection), Sol's case must still refuse before the
    fetch, by git's own for-each-ref %(symref) answer."""
    monkeypatch.setitem(GW, "gw_refs", lambda *a: None)
    make_file(os.path.join(repo_copy, ".git", VICTIM), (world.P + "\n").encode())
    world.git(repo_copy, "symbolic-ref", END_REF, VICTIM)
    foreign_dir = os.path.join(tmpdir_, "perception-synthetic")
    marker = plant_victim_log(repo_copy, VICTIM, "leaf-symlink", foreign_dir)
    origin_branch(world.X2)
    error = refused("git-write", refresh, tmpdir_, world.X2)
    ok("symbolic or indirect ref" in error.reason and VICTIM in error.reason, error.reason)
    ok(git_writes(fetch_spy) == [] and read(marker) == MARKER)


@pytest.mark.parametrize("layer", ["guard", "git-view"])
def test_s9_checkout_rechecks_the_destination(world, repo_copy, origin_branch, tmpdir_, monkeypatch, layer):
    """Both r6 checks also run before --checkout: the destination turned symbolic after the fetch refuses before the
    checkout (with gw_refs disabled for the git-view row), HEAD unchanged."""
    if layer == "git-view":
        monkeypatch.setitem(GW, "gw_refs", lambda *a: None)
    runs, real, real_paths = [], si.run_checked, S9.changed_paths
    monkeypatch.setattr(si, "run_checked", lambda argv, *a, **k: runs.append(list(argv)) or real(argv, *a, **k))

    def paths_then_symref(g_, old, new):                     # after every post-fetch check, before the checkout guard
        make_file(os.path.join(repo_copy, ".git", VICTIM), (world.X2 + "\n").encode())
        os.unlink(os.path.join(repo_copy, ".git", END_REF))
        make_file(os.path.join(repo_copy, ".git", END_REF), ("ref: %s\n" % VICTIM).encode())
        return real_paths(g_, old, new)
    monkeypatch.setattr(S9, "changed_paths", paths_then_symref)
    origin_branch(world.X2)
    error = refused("git-write", refresh, tmpdir_, world.X2, checkout=True)
    ok(("symbolic ref (" if layer == "guard" else "symbolic or indirect ref") in error.reason, error.reason)
    ok([r for r in runs if "fetch" in r] and not [r for r in runs if "checkout" in r], runs)
    ok(world.git(repo_copy, "rev-parse", "HEAD").decode().strip() == world.P)


def test_s9_checkout_detach_with_a_symbolic_head_writes_no_referent_reflog(world, repo_copy, origin_branch, tmpdir_):
    """HEAD is not a planned direct ref: `checkout --detach` updates HEAD without dereferencing it. A HEAD that points
    at a victim branch whose reflog is aliased: refresh --checkout succeeds and the foreign marker is unchanged."""
    victim = "refs/heads/victim"
    make_file(os.path.join(repo_copy, ".git", victim), (world.P + "\n").encode())
    world.git(repo_copy, "symbolic-ref", "HEAD", victim)
    foreign_dir = os.path.join(tmpdir_, "perception-synthetic")
    marker = plant_victim_log(repo_copy, victim, "leaf-symlink", foreign_dir)
    state = tree_state(foreign_dir)
    origin_branch(world.X2)
    result = refresh(tmpdir_, world.X2, base=world.P, checkout=True)
    ok(result["head"] == world.X2 and result["git_write_guard"]["release"] == "k4s-git-write-guard-r6")
    ok(read(marker) == MARKER and tree_state(foreign_dir) == state)


# ---------------------------------------------------------------- gw_refs on the shared guard (both copies)

LOOSE_ROWS = [("symref", b"ref: refs/heads/victim\n", "symbolic ref"), ("symref-onelevel", b"ref: VICTIM\n",
              "symbolic ref"), ("empty", b"", "not exactly one object name"),
              ("no-newline", None, "not exactly one object name"), ("upper-hex", None, "not exactly one object name"),
              ("trailing", None, "not exactly one object name")]
PACKED_ROWS = [("peeled", "peeled (indirect) entry"), ("symref-line", "not '<object name> <ref>'"),
               ("peel-first", "unexpected peeled line"), ("double-peel", "unexpected peeled line"),
               ("bad-oid", "not '<object name> <ref>'"), ("not-refs", "not '<object name> <ref>'"),
               ("duplicate", "not '<object name> <ref>'"), ("no-final-newline", "does not end with a newline"),
               ("non-ascii", "is not ASCII"), ("space-in-name", "not '<object name> <ref>'")]


def both_guards(scratch):
    return [("s9", GW), ("host", scratch["ns"])]


@pytest.mark.parametrize("copy", ["s9", "host"])
@pytest.mark.parametrize("row", LOOSE_ROWS, ids=[r[0] for r in LOOSE_ROWS])
def test_guard_loose_destination_must_be_one_object_name(scratch, tmpdir_, copy, row):
    ns = dict(both_guards(scratch))[copy]
    repo = copy_host(scratch, tmpdir_)
    p = scratch["P"]
    data = {"no-newline": p.encode(), "upper-hex": (p.upper() + "\n").encode(),
            "trailing": (p + "\n ").encode()}.get(row[0], row[1])
    path = os.path.join(repo, ".git", HOST_REF)
    os.unlink(path)
    make_file(path, data)
    with pytest.raises(si.Refusal) as caught:
        ns["gw_scan"](repo, ns["gw_plan"](HOST_REF), gw_refuse)
    ok(caught.value.code == "git-write" and row[2] in caught.value.reason and HOST_REF in caught.value.reason,
       caught.value)


def packed_text(p, row):
    head = "# pack-refs with: peeled fully-peeled sorted \n"
    line = "%s %s\n" % (p, HOST_REF)
    body = {"peeled": line + "^" + p + "\n",
            "symref-line": "ref: refs/heads/victim\n",
            "peel-first": "^" + p + "\n" + line,
            "double-peel": "%s refs/tags/t\n^%s\n^%s\n" % (p, p, p),
            "bad-oid": "%s %s\n" % (p[:39], HOST_REF),
            "not-refs": "%s HEAD\n" % p,
            "duplicate": line + line,
            "no-final-newline": line[:-1],
            "non-ascii": "%s refs/heads/v\xe9\n" % p,
            "space-in-name": "%s refs/heads/a b\n" % p}[row]
    return (head + body).encode("latin-1")


@pytest.mark.parametrize("copy", ["s9", "host"])
@pytest.mark.parametrize("row", PACKED_ROWS, ids=[r[0] for r in PACKED_ROWS])
def test_guard_packed_refs_must_be_well_formed_and_direct(scratch, tmpdir_, copy, row):
    ns = dict(both_guards(scratch))[copy]
    repo = copy_host(scratch, tmpdir_)
    make_file(os.path.join(repo, ".git/packed-refs"), packed_text(scratch["P"], row[0]))
    with pytest.raises(si.Refusal) as caught:
        ns["gw_scan"](repo, ns["gw_plan"](HOST_REF), gw_refuse)
    ok(caught.value.code == "git-write" and row[1] in caught.value.reason and "packed-refs" in caught.value.reason,
       caught.value)


@pytest.mark.parametrize("copy", ["s9", "host"])
def test_guard_accepts_direct_refs_and_peeled_tags(scratch, tmpdir_, copy):
    """The healthy forms pass: a loose '<oid>\\n', and a packed-refs with a header, the ref and a peeled TAG entry."""
    ns = dict(both_guards(scratch))[copy]
    repo = copy_host(scratch, tmpdir_)
    p = scratch["P"]
    make_file(os.path.join(repo, ".git/packed-refs"), ("# pack-refs with: peeled fully-peeled sorted \n%s %s\n"
                                                       "%s refs/tags/t\n^%s\n" % (p, HOST_REF, p, p)).encode())
    facts = ns["gw_scan"](repo, ns["gw_plan"](HOST_REF), gw_refuse)
    ok(facts[".git/packed-refs"][0] == "file" and facts[".git/" + HOST_REF][0] == "file")
    ok(ns["gw_plan"](HOST_REF)["direct"] == [HOST_REF])


@pytest.mark.parametrize("copy", ["s9", "host"])
@pytest.mark.parametrize("case", ["not-validated", "identity", "limit", "dir-identity", "symlink-to-same"])
def test_guard_reads_only_the_validated_leaf(scratch, tmpdir_, copy, case):
    """_gw_read: only a leaf this scan validated, through a no-follow descriptor whose fstat is that same file (and
    the same directories above it), bounded."""
    ns = dict(both_guards(scratch))[copy]
    repo = copy_host(scratch, tmpdir_)
    rel = ".git/" + HOST_REF
    facts = ns["gw_scan"](repo, ns["gw_plan"](HOST_REF), gw_refuse)
    if case == "not-validated":
        facts.pop(rel)
        want = "was not validated"
    elif case == "identity":
        make_file(os.path.join(repo, rel + ".new"), (scratch["P"] + "\n").encode())
        os.rename(os.path.join(repo, rel + ".new"), os.path.join(repo, rel))
        want = "changed while it was checked"
    elif case == "dir-identity":
        heads = os.path.join(repo, ".git/refs/heads")
        os.rename(heads, heads + ".old")
        os.makedirs(heads)
        make_file(os.path.join(heads, S9.END_BRANCH), (scratch["P"] + "\n").encode())
        want = "changed while they were checked"
    elif case == "symlink-to-same":                # the same validated inode behind a symlink: only O_NOFOLLOW sees it
        moved = os.path.join(tmpdir_, "moved-ref")
        os.rename(os.path.join(repo, rel), moved)
        os.symlink(moved, os.path.join(repo, rel))
        want = "cannot be opened without following"
    fd = ns["gw_open_root"](repo, gw_refuse)
    try:
        if case == "limit":
            with pytest.raises(si.Refusal) as caught:
                ns["_gw_read"](fd, rel, facts, 40, gw_refuse)
            want = "larger than 40 bytes"
        else:
            with pytest.raises(si.Refusal) as caught:
                ns["_gw_read"](fd, rel, facts, 4096, gw_refuse)
        if case == "limit":
            ok(ns["_gw_read"](fd, rel, facts, 41, gw_refuse) == (scratch["P"] + "\n").encode())
    finally:
        os.close(fd)
    ok(want in caught.value.reason, caught.value)


# ---------------------------------------------------------------- S11 advance (fake host, one login)

@pytest.mark.parametrize("alias", ALIASES + ["onelevel"])
def test_s11_advance_refuses_a_symbolic_destination_before_the_fetch(world, ready, tmpdir_, repo_copy,
                                                                     advanced_clone, monkeypatch, alias):
    """refs/heads/k4s-end-r1 made a symbolic ref (to a victim branch whose reflog is aliased: Sol's three forms; or to
    a one-level name) on the provisioned host repository: refused at the [check] stage by the existing exact-ref
    VERIFY (HEAD must resolve to refs/heads/k4s-end-r1, the only ref), before the bundle is received or fetched."""
    _, repo = T11.provision_at_p(world, ready, tmpdir_, repo_copy, monkeypatch)
    foreign_dir = ready.path(T11.HOST, FOREIGN_NS)
    if alias == "onelevel":
        make_file(os.path.join(repo, ".git/VICTIM_HEAD"), (world.P + "\n").encode())
        target, marker = "VICTIM_HEAD", None
        os.makedirs(foreign_dir, exist_ok=True)
        make_file(os.path.join(foreign_dir, "marker"), MARKER)
    else:
        target = "refs/heads/victim"
        make_file(os.path.join(repo, ".git", target), (world.P + "\n").encode())
        marker = plant_victim_log(repo, target, alias, foreign_dir, target_prefix=FOREIGN_NS)
    os.unlink(os.path.join(repo, ".git", HOST_REF))
    make_file(os.path.join(repo, ".git", HOST_REF), ("ref: %s\n" % target).encode())
    state, fh = tree_state(foreign_dir), fetch_head(repo)
    a = T11.advance_args(world, tmpdir_, advanced_clone)
    error = refused("remote-refused", T11.run, a)
    ok('"check"' in error.reason and "stages ['@@RC|check|3']" in error.reason, error.reason)
    ok(T11.git(repo, "cat-file", "-e", world.X2 + "^{commit}")[0] != 0, "the fetch ran")
    ok(fetch_head(repo) == fh, "FETCH_HEAD changed")
    ok(marker is None or read(marker) == MARKER)
    ok(tree_state(foreign_dir) == state, "the foreign marker changed")
    T11.receipt(a.record)
    ok(not os.path.exists(os.path.join(a.record, "s11-advance.json")))


def run_local_main(ns, mode, p):
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
    return caught.value


@pytest.mark.parametrize("layer", ["guard", "git-view"])
def test_s11_host_advance_symbolic_destination_isolated_from_verify(world, ready, tmpdir_, repo_copy, advanced_clone,
                                                                     monkeypatch, layer):
    """The host program's own r6 checks, with _verify stubbed (so the exact-ref VERIFY cannot refuse first): the
    advance fetch refuses `git-write` before it runs (X absent, no FETCH_HEAD), the aliased victim reflog unchanged.
    git-view row: gw_refs disabled too, so only the _guarded for-each-ref %(symref) check remains."""
    p, local = local_main(world, ready, tmpdir_, repo_copy, advanced_clone, monkeypatch, "advance")
    repo = os.path.join(local, "repository")
    target = "refs/heads/victim"
    make_file(os.path.join(repo, ".git", target), (world.P + "\n").encode())
    foreign_dir = os.path.join(tmpdir_, "perception-synthetic")
    marker = plant_victim_log(repo, target, "leaf-symlink", foreign_dir)
    os.unlink(os.path.join(repo, ".git", HOST_REF))
    make_file(os.path.join(repo, ".git", HOST_REF), ("ref: %s\n" % target).encode())
    fh = fetch_head(repo)
    ns = T11.host_namespace()
    ns["_verify"] = lambda si_, tool, p_, path, commit: dict(head=commit)
    if layer == "git-view":
        ns["gw_refs"] = lambda *a: None
    error = run_local_main(ns, "advance", p)
    want = "symbolic ref (" if layer == "guard" else "symbolic or indirect ref"
    ok(error.code == "git-write" and want in error.reason and HOST_REF in error.reason, error)
    ok(T11.git(repo, "cat-file", "-e", world.X2 + "^{commit}")[0] != 0, "the fetch ran")
    ok(fetch_head(repo) == fh and read(marker) == MARKER)


def test_s11_host_provision_symbolic_destination_refused_before_the_fetch(world, ready, tmpdir_, repo_copy,
                                                                          advanced_clone, monkeypatch):
    """provision: a symbolic refs/heads/k4s-end-r1 appearing in the fresh repository (injected right after `git init`;
    the partial directory is created exclusively, so this only proves the check) refuses before the fetch."""
    p, local = local_main(world, ready, tmpdir_, repo_copy, advanced_clone, monkeypatch, "provision")
    ns = T11.host_namespace()
    real = ns["_git"]

    def init_then_symref(si_, path, args, **kw):
        out = real(si_, path, args, **kw)
        if args[0] == "init":
            make_file(os.path.join(path, ".git", HOST_REF), b"ref: refs/heads/victim\n")
        return out
    ns["_git"] = init_then_symref
    error = run_local_main(ns, "provision", p)
    ok(error.code == "git-write" and "symbolic ref (" in error.reason, error)
    partial = os.path.join(local, "repository.partial")
    ok(not os.path.lexists(os.path.join(partial, ".git/FETCH_HEAD")))
    ok(not os.path.lexists(os.path.join(partial, ".git/refs/heads/victim")))
