"""Ruling E5 (r3): nine runtime members that match an OUTCOME family by name only are exempt at exact path + git blob
OID, and are opaque (hashed, copied, exported, received; never returned for parsing). Synthetic stand-ins only, under
pytest's tmp_path: the real member blobs are never read. Tests pin synthetic OIDs; they never widen or move the list."""
import hashlib
import json
import os

import pytest

from conftest import make_file, ok, policy, refusal, role, si
from test_git_r2 import log_text, logged_git, make_repo, raw
from test_receive import refused_directly, run_receiver, shim  # noqa: F401  (shim is a fixture)

RULED = (                                       # COORDINATOR 2026-10-12 21:28Z ruling E5, verbatim
    ("reports/explore/k4s-confirm/check_games.py", "32b3e4d1154febcff73303a31c99bb1e711182ec"),
    ("reports/explore/k4s-confirm/qualify_games.py", "5f0b97b0586cd38f380e4bfb539741c783b5dc57"),
    ("reports/strategy_council_20260928/engine-speed/canonical/certify_games.py",
     "da72f140cc89df0eab0960b03009204c88c66991"),
    ("reports/strategy_council_20260928/imitation/exit-r3/round2/eval-ops/reduce_games.py",
     "d91d35a244d30dc6c3758360e8670749ae75ceda"),
    ("reports/strategy_council_20260928/imitation/exit-r3/round2/timing03/eval-ops/reduce_games.py",
     "2ebf150ddb79c90ea79b40a75d09ec5ed4c1bcca"),
    ("reports/strategy_council_20260928/search-tuning/timing_games.py", "6ff285d6874df1f7c5ea9451203d294518bfe70c"),
    ("scripts/collect_public_development_games.py", "63a4e37396bedab7943db87d85ace99dad614bfb"),
    ("scripts/compare_native_public_games.py", "9e128c268482a292297019e67df6eb068e2fe1d8"),
    ("tests/fixtures/native_friendly_completed_15_535_86.json", "c46248eb7cfb551b1a75c695265743a48d625801"),
)
PATHS = [p for p, _ in RULED]
FIXTURE = PATHS[-1]


def blob_oid(data):
    return hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest()


def sha(data):
    return hashlib.sha256(data).hexdigest()


E5_FILES = {p: b"# synthetic stand-in for " + p.encode() + b"\n" for p in PATHS}


def pin_e5(monkeypatch, files=None):
    """Test mode: replace the OIDs (only) with those of the synthetic stand-ins, in the module and in the namespace
    that holds the receive validator."""
    files = files or E5_FILES
    pairs = tuple((p, blob_oid(files[p])) for p in si.E5_PATHS)
    monkeypatch.setattr(si, "E5_RUNTIME_MEMBERS", pairs)
    monkeypatch.setitem(si._RECEIVE_NS, "E5_RUNTIME_MEMBERS", pairs)
    return dict(pairs)


def e5_role(name, root, access="read", exemptions=("E5",), **kw):
    return role(name, root, access=access, patterns=("**",), exemptions=exemptions, **kw)


# ---------------------------------------------------------------- the constant
def test_constant_is_exactly_the_ruling():
    ok(si.E5_RUNTIME_MEMBERS == RULED and si.E5_PATHS == tuple(PATHS) and isinstance(si.E5_RUNTIME_MEMBERS, tuple))
    ok("E5" in si.EXEMPTIONS)
    for path, oid in RULED:
        ok(si.e5_blob_oid(path) == oid)
        parts = path.split("/")
        ok(si.outcome_family(parts[-1]) is not None, path)            # matches by its leaf name ...
        ok(all(si.outcome_family(c) is None and si.end_claim_family(c) is None for c in parts[:-1]), path)
    ok(si.e5_blob_oid("scripts/other_games.py") is None and si.e5_blob_oid(PATHS[0].upper()) is None)
    ok(si.outcome_family("check_games.py") == "games")              # ... and the family is NOT narrowed
    ok(si.outcome_family("native_friendly_completed_15_535_86.json") == "complete-json")


def test_constant_is_in_the_fingerprint(monkeypatch):
    before = si.constants_fingerprint()
    pin_e5(monkeypatch)
    ok(si.constants_fingerprint() != before)


@pytest.mark.parametrize("label", ["tenth", "moved", "dropped", "reordered", "list", "bad-oid", "not-pairs"])
def test_test_mode_may_change_oids_only(monkeypatch, label):
    pin_e5(monkeypatch)                                              # changing OIDs is allowed
    ok(si.e5_blob_oid(PATHS[0]) == blob_oid(E5_FILES[PATHS[0]]))
    pairs = list(si.E5_RUNTIME_MEMBERS)
    if label == "tenth":
        pairs.append(("scripts/other_games.py", "1" * 40))
    elif label == "moved":
        pairs[0] = ("reports/explore/check_games.py", pairs[0][1])
    elif label == "dropped":
        pairs.pop()
    elif label == "reordered":
        pairs[0], pairs[1] = pairs[1], pairs[0]
    elif label == "bad-oid":
        pairs[3] = (pairs[3][0], "G" * 40)
    elif label == "not-pairs":
        pairs[2] = (pairs[2][0], pairs[2][1], "x")
    monkeypatch.setattr(si, "E5_RUNTIME_MEMBERS", pairs if label == "list" else tuple(pairs))
    refusal("policy", si.e5_blob_oid, PATHS[0])
    refusal("policy", si.e5_blob_oid, "scripts/other_games.py")


def test_name_gate_e5_argument_is_exact():
    root = "/mpac/sdicks02/k4s-runner/x"
    host = si.HOSTS[0]
    si.name_gate(root + "/" + PATHS[0], host, (), e5_rel=PATHS[0])
    refusal("name", si.name_gate, root + "/" + PATHS[0], host, ())
    refusal("exemption", si.name_gate, root + "/" + PATHS[0], host, (), e5_rel=PATHS[1])      # not its suffix
    refusal("exemption", si.name_gate, root + "/scripts/other_games.py", host, (), e5_rel="scripts/other_games.py")
    refusal("exemption", si.name_gate, root + "/x" + PATHS[0], host, (), e5_rel=PATHS[0])   # not a whole suffix
    refusal("name", si.name_gate, root + "/games/" + PATHS[0], host, (), e5_rel=PATHS[0])  # leaf only


# ---------------------------------------------------------------- git: phase 1 metadata pins, phase 2 opaque
def e5_repo(base, extra=None, links=()):
    files = dict(E5_FILES)
    files["src/a.py"] = b"a = 1\n"
    files.update(extra or {})
    return make_repo(os.path.join(base, "r"), files, links)


def no_reads_refusal(code, base, p, repo, head, **kw):
    wrapper, log = logged_git(base)
    reads = si.GIT_COUNTERS["object_reads"]
    refusal(code, si.git_plan, p, "rt", repo, head, git_binary=wrapper, **kw)
    ok(si.GIT_COUNTERS["object_reads"] == reads, "an object was read before the refusal")
    ok("--batch" not in log_text(log) and "ls-tree" in log_text(log))


@pytest.mark.parametrize("path", PATHS)
def test_git_plan_accepts_each_member_opaquely(base, monkeypatch, path):
    repo, head = e5_repo(base)
    pins = pin_e5(monkeypatch)
    p = policy([e5_role("rt", repo, exemptions=("E1", "E4", "E5"))])
    reads = si.GIT_COUNTERS["object_reads"]
    plan = si.git_plan(p, "rt", repo, head, members=(path, "src/a.py"))
    ok(si.GIT_COUNTERS["object_reads"] == reads)
    ok([e["path"] for e in plan.e5] == [path] and [e["path"] for e in plan.files] == ["src/a.py"])
    ok(plan.e5[0]["oid"] == pins[path] and plan.e5[0]["mode"] == "100644")
    got = plan.hash_e5(plan.e5[0])
    ok(got == {"path": path, "git_oid": pins[path], "sha256": sha(E5_FILES[path]), "size": len(E5_FILES[path])})
    refusal("policy", plan.read, path)                               # never returned for parsing
    refusal("policy", plan.read, plan.e5[0])
    refusal("exemption", plan.hash_e5, plan.files[0])
    refusal("name", si.git_show_file, p, "rt", repo, head, path)
    out = os.path.join(base, "out")
    os.makedirs(out)
    inv = plan.export(si.Writer(policy([e5_role("w", out, access="write")]), "w"))
    ok(sorted(inv) == sorted([path, "src/a.py"]) and inv[path]["sha256"] == sha(E5_FILES[path]))
    with open(os.path.join(out, path), "rb") as stream:
        ok(stream.read() == E5_FILES[path])
    st = os.lstat(os.path.join(out, path))
    ok(st.st_nlink == 1 and st.st_mode & 0o777 == 0o444)
    out2 = os.path.join(base, "out2")
    os.makedirs(out2)
    refusal("exemption", plan.export, si.Writer(policy([role("w", out2, access="write", patterns=("**",))]), "w"))


def test_git_plan_whole_tree_with_all_nine(base, monkeypatch):
    repo, head = e5_repo(base)
    pin_e5(monkeypatch)
    p = policy([e5_role("rt", repo)])
    plan = si.git_plan(p, "rt", repo, head)
    ok(sorted(e["path"] for e in plan.e5) == sorted(PATHS) and [e["path"] for e in plan.files] == ["src/a.py"])
    for entry in plan.e5:
        ok(plan.hash_e5(entry)["sha256"] == sha(E5_FILES[entry["path"]]))


def test_real_oids_refuse_synthetic_stand_ins_before_any_read(base):
    repo, head = e5_repo(base)                                       # the ruled OIDs, not the stand-ins'
    p = policy([e5_role("rt", repo)])
    no_reads_refusal("exemption", base, p, repo, head)
    for path in PATHS:
        no_reads_refusal("exemption", base, p, repo, head, members=(path,))


@pytest.mark.parametrize("path", PATHS)
def test_changed_oid_refused_before_blob_read(base, monkeypatch, path):
    repo, head = e5_repo(base)
    pin_e5(monkeypatch)
    make_file(os.path.join(repo, path), E5_FILES[path] + b"# changed\n")
    raw(repo, "add", "-A")
    raw(repo, "commit", "-q", "-m", "change")
    head = raw(repo, "rev-parse", "HEAD").stdout.decode().strip()
    p = policy([e5_role("rt", repo)])
    no_reads_refusal("exemption", base, p, repo, head)
    no_reads_refusal("exemption", base, p, repo, head, members=(path,))


MOVED = ["scripts/old/compare_native_public_games.py", "compare_native_public_games.py",
         "reports/explore/check_games.py", "reports/explore/k4s-confirm/v2/check_games.py",
         "tests/native_friendly_completed_15_535_86.json"]


@pytest.mark.parametrize("moved", MOVED)
def test_moved_path_refused(base, monkeypatch, moved):
    leaf = moved.rsplit("/", 1)[-1]
    original = [p for p in PATHS if p.endswith("/" + leaf)][0]
    files = {k: v for k, v in E5_FILES.items() if k != original}
    files[moved] = E5_FILES[original]                                # same bytes, same blob OID, other path
    repo, head = make_repo(os.path.join(base, "r"), files)
    pin_e5(monkeypatch)
    p = policy([e5_role("rt", repo)])
    no_reads_refusal("name", base, p, repo, head, members=(moved,))
    no_reads_refusal("name", base, p, repo, head, members=lambda e: True)


@pytest.mark.parametrize("tenth", ["scripts/fetch_more_games.py", "tests/fixtures/native_friendly_completed_15_535_87.json",
                                   "reports/explore/k4s-confirm/check_games_v2.py", "games/x.py"])
def test_tenth_family_member_refused(base, monkeypatch, tenth):
    repo, head = e5_repo(base, {tenth: b"x = 10\n"})
    pin_e5(monkeypatch)
    p = policy([e5_role("rt", repo)])
    no_reads_refusal("name", base, p, repo, head)
    ok(len(si.git_plan(p, "rt", repo, head, members=lambda e: e["path"] != tenth).e5) == 9)


CASE = ["reports/explore/k4s-confirm/Check_games.py", "reports/explore/k4s-confirm/check_GAMES.py",
        "Scripts/compare_native_public_games.py", "tests/fixtures/native_friendly_completed_15_535_86.JSON",
        "tests/Fixtures/native_friendly_completed_15_535_86.json"]


@pytest.mark.parametrize("variant", CASE)
def test_case_variant_refused(base, monkeypatch, variant):
    original = [p for p in PATHS if p.casefold() == variant.casefold()][0]
    files = {k: v for k, v in E5_FILES.items() if k != original}
    files[variant] = E5_FILES[original]
    repo, head = make_repo(os.path.join(base, "r"), files)
    pin_e5(monkeypatch)
    p = policy([e5_role("rt", repo)])
    no_reads_refusal("name", base, p, repo, head, members=(variant,))


@pytest.mark.parametrize("variant", ["100755", "symlink", "gitlink"])
def test_non_100644_mode_refused(base, monkeypatch, variant):
    repo, head = e5_repo(base)
    target = PATHS[2]
    files = dict(E5_FILES)
    expected = "exemption"
    if variant == "100755":
        os.chmod(os.path.join(repo, target), 0o755)                  # same bytes and blob OID, mode differs
        raw(repo, "add", "-A")
    elif variant == "symlink":
        os.unlink(os.path.join(repo, target))
        os.symlink("../../../../src/a.py", os.path.join(repo, target))
        files[target] = b"../../../../src/a.py"                      # pin the link blob: only the mode differs
        raw(repo, "add", "-A")
    else:
        raw(repo, "rm", "-q", "--cached", target)
        raw(repo, "update-index", "--add", "--cacheinfo", "160000,%s,%s" % (head, target))
        expected = "not-regular"
    raw(repo, "commit", "-q", "-m", "mode")
    head = raw(repo, "rev-parse", "HEAD").stdout.decode().strip()
    pin_e5(monkeypatch, files)
    p = policy([e5_role("rt", repo, exemptions=("E1", "E5"))])
    entry = [e for e in si.git_ls_tree(repo, head) if e["path"] == target][0]
    ok(entry["mode"] == {"100755": "100755", "symlink": "120000", "gitlink": "160000"}[variant])
    no_reads_refusal(expected, base, p, repo, head)
    no_reads_refusal(expected, base, p, repo, head, members=(target,))


def test_e5_needs_the_role_exemption_and_the_cap(base, monkeypatch):
    repo, head = e5_repo(base)
    pin_e5(monkeypatch)
    no_reads_refusal("name", base, policy([e5_role("rt", repo, exemptions=("E1", "E4"))]), repo, head)
    no_reads_refusal("size", base, policy([e5_role("rt", repo, max_size=16)]), repo, head, members=(PATHS[0],))


# ---------------------------------------------------------------- on disk (e.g. S4's staged runtime)
@pytest.fixture
def tree(base):
    root = os.path.join(base, "runtime")
    for path, data in E5_FILES.items():
        make_file(os.path.join(root, path), data)
    make_file(os.path.join(root, "src/a.py"), b"a = 1\n")
    return root


@pytest.mark.parametrize("path", PATHS)
def test_on_disk_hash_each_member_and_never_parse(tree, monkeypatch, path):
    pins = pin_e5(monkeypatch)
    p = policy([e5_role("rt", tree), role("plain", tree, patterns=("**",))])
    got = si.hash_e5(p, "rt", path)
    ok(got == {"path": path, "git_oid": pins[path], "sha256": sha(E5_FILES[path]), "size": len(E5_FILES[path])})
    for fn, args in ((si.read_json, (p, "rt", path, 1 << 20)), (si.read_bytes, (p, "rt", path)),
                     (si.open_input, (p, "rt", path)), (si.sha256_input, (p, "rt", path)),
                     (si.hash_e4, (p, "rt", path))):
        refusal("exemption" if fn is si.hash_e4 else "name", fn, *args)   # parse/read attempts refuse by name
    refusal("exemption", si.hash_e5, p, "plain", path)               # a role without E5


def test_on_disk_changed_bytes_and_unpinned_refuse(tree, monkeypatch):
    p = policy([e5_role("rt", tree)])
    refusal("exemption", si.hash_e5, p, "rt", PATHS[0])              # ruled OID vs stand-in bytes
    pin_e5(monkeypatch)
    os.chmod(os.path.join(tree, PATHS[1]), 0o644)
    make_file(os.path.join(tree, PATHS[1]), E5_FILES[PATHS[1]].upper())
    refusal("exemption", si.hash_e5, p, "rt", PATHS[1])
    refusal("exemption", si.hash_e5, p, "rt", "src/a.py")
    make_file(os.path.join(tree, "scripts/other_games.py"), b"x\n")
    refusal("exemption", si.hash_e5, p, "rt", "scripts/other_games.py")
    make_file(os.path.join(tree, "Scripts/compare_native_public_games.py"), E5_FILES[PATHS[7]])
    refusal("exemption", si.hash_e5, p, "rt", "Scripts/compare_native_public_games.py")


@pytest.mark.parametrize("kind", ["hardlink", "symlink", "directory", "fifo"])
def test_on_disk_normal_gates_apply(tree, monkeypatch, base, kind):
    pin_e5(monkeypatch)
    target = os.path.join(tree, PATHS[0])
    if kind == "hardlink":
        os.link(target, os.path.join(base, "elsewhere"))
        code = "nlink"
    elif kind == "symlink":
        os.rename(target, os.path.join(tree, "moved.py"))
        os.symlink("../../../moved.py", target)
        code = "symlink"
    elif kind == "directory":
        os.unlink(target)
        os.mkdir(target)
        code = "not-regular"
    else:
        os.unlink(target)
        os.mkfifo(target)
        code = "not-regular"
    p = policy([e5_role("rt", tree)])
    refusal(code, si.hash_e5, p, "rt", PATHS[0])
    walk_code = {"hardlink": "nlink", "symlink": "symlink", "directory": "not-regular", "fifo": "not-regular"}[kind]
    refusal(walk_code, si.walk_tree, p, "rt")


def test_on_disk_copy_byte_exact(tree, base, monkeypatch):
    pin_e5(monkeypatch)
    p = policy([e5_role("rt", tree)])
    out = os.path.join(base, "copy")
    os.makedirs(os.path.join(out, "scripts"))
    w = si.Writer(policy([e5_role("w", out, access="write")]), "w")
    got = si.copy_e5(p, "rt", PATHS[7], w)
    ok(got["sha256"] == sha(E5_FILES[PATHS[7]]) and got["git_oid"] == blob_oid(E5_FILES[PATHS[7]]))
    with open(os.path.join(out, PATHS[7]), "rb") as stream:
        ok(stream.read() == E5_FILES[PATHS[7]])
    ok(os.lstat(os.path.join(out, PATHS[7])).st_mode & 0o777 == 0o444)
    refusal("exists", si.copy_e5, p, "rt", PATHS[7], w)              # never overwritten
    plain = si.Writer(policy([role("w2", out, access="write", patterns=("**",))]), "w2")
    refusal("exemption", si.copy_e5, p, "rt", PATHS[6], plain)
    refusal("name", si.copy_input, p, "rt", PATHS[6], w, PATHS[6])  # not through the ordinary copy either
    refusal("name", w.create_excl, PATHS[6], b"x")


def test_on_disk_copy_of_unpinned_bytes_creates_nothing(tree, base, monkeypatch):
    pin_e5(monkeypatch)
    make_file(os.path.join(tree, PATHS[6]), E5_FILES[PATHS[6]].upper())
    p = policy([e5_role("rt", tree)])
    out = os.path.join(base, "copy")
    os.makedirs(os.path.join(out, "scripts"))
    w = si.Writer(policy([e5_role("w", out, access="write")]), "w")
    refusal("exemption", si.copy_e5, p, "rt", PATHS[6], w)
    ok(os.listdir(os.path.join(out, "scripts")) == [], "a copy was started before the hash pass")


def test_on_disk_copy_rechecks_the_pin_on_the_copy_pass(tree, base, monkeypatch):
    pin_e5(monkeypatch)
    p = policy([e5_role("rt", tree)])
    out = os.path.join(base, "copy")
    os.makedirs(os.path.join(out, "scripts"))
    w = si.Writer(policy([e5_role("w", out, access="write")]), "w")
    real = si.hash_e5
    source = os.path.join(tree, PATHS[6])

    def then_change(*args):
        got = real(*args)
        os.chmod(source, 0o644)
        make_file(source, E5_FILES[PATHS[6]].upper())
        return got

    monkeypatch.setattr(si, "hash_e5", then_change)
    refusal("exemption", si.copy_e5, p, "rt", PATHS[6], w)


def test_walk_tree_lists_e5_separately(tree, monkeypatch):
    pin_e5(monkeypatch)
    p = policy([e5_role("rt", tree), role("plain", tree, patterns=("**",))])
    got = si.walk_tree(p, "rt")
    ok(got["e5"] == sorted(PATHS) and [f["rel"] for f in got["files"]] == ["src/a.py"])
    refusal("name", si.walk_tree, p, "plain")
    make_file(os.path.join(tree, "scripts/fetch_more_games.py"), b"x\n")
    refusal("name", si.walk_tree, p, "rt")


# ---------------------------------------------------------------- D4 receive (S10 ships the runtime)
def dirs_of(paths):
    out = []
    for path in sorted(paths):
        parts = path.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            d = "/".join(parts[:i])
            if d not in out:
                out.append(d)
    return out


def shipped_with(pins):
    source = si.receive_program_source()
    for path, oid in RULED:
        ok(source.count(oid) == 1)
        source = source.replace(oid, pins[path])
    return source


def receive_policies(base, tree, dest_name, local_exemptions=("E5",), dest_exemptions=("E5",)):
    host_root = os.path.join(base, "host")
    os.makedirs(host_root, exist_ok=True)
    remote = policy([e5_role("dest", os.path.join(host_root, dest_name), access="write",
                             exemptions=dest_exemptions)], remote=True)
    local = policy([e5_role("src", tree, exemptions=local_exemptions)])
    return remote, local, os.path.join(host_root, dest_name)


def item(path, data, **kw):
    out = {"src_role": "src", "src_rel": path, "dst": path, "size": len(data), "sha256": sha(data), "e5": True}
    out.update(kw)
    return out


def test_receive_carries_all_nine(base, tree, shim, monkeypatch):  # noqa: F811
    pins = pin_e5(monkeypatch)
    shipped = shipped_with(pins)
    monkeypatch.setattr(si, "receive_program_source", lambda: shipped)
    remote, local, dest = receive_policies(base, tree, "runtime-e5.partial")
    files = [item(p, E5_FILES[p]) for p in PATHS] + [dict(item("src/a.py", b"a = 1\n"), e5=False)]
    receipt = si.remote_receive(remote, "dest", local, files, dirs_of(PATHS + ["src/a.py"]), ssh_binary=shim[0])
    ok(sorted(f["rel"] for f in receipt["files"]) == sorted(PATHS + ["src/a.py"]))
    for path in PATHS:
        with open(os.path.join(dest, path), "rb") as stream:
            ok(stream.read() == E5_FILES[path])
        ok(os.lstat(os.path.join(dest, path)).st_mode & 0o777 == 0o444)


def test_receive_local_refusals_before_ssh(base, tree, shim, monkeypatch):  # noqa: F811
    pin_e5(monkeypatch)
    remote, local, dest = receive_policies(base, tree, "runtime-e5.partial")
    path, data = PATHS[0], E5_FILES[PATHS[0]]
    dirs = dirs_of([path])
    refusal("name", si.remote_receive, remote, "dest", local, [item(path, data, e5=False)], dirs, ssh_binary=shim[0])
    refusal("exemption", si.remote_receive, remote, "dest", local, [item(path, data, dst=PATHS[1])],
            dirs_of(PATHS[:2]), ssh_binary=shim[0])
    refusal("exemption", si.remote_receive, remote, "dest", local, [item(path, data, mode=0o555)], dirs,
            ssh_binary=shim[0])
    refusal("sha", si.remote_receive, remote, "dest", local, [item(path, data, sha256="0" * 64)], dirs,
            ssh_binary=shim[0])
    _, local_plain, _ = receive_policies(base, tree, "runtime-e5b.partial", local_exemptions=())
    refusal("exemption", si.remote_receive, remote, "dest", local_plain, [item(path, data)], dirs, ssh_binary=shim[0])
    remote_plain, _, _ = receive_policies(base, tree, "runtime-e5c.partial", dest_exemptions=())
    refusal("exemption", si.remote_receive, remote_plain, "dest", local, [item(path, data)], dirs, ssh_binary=shim[0])
    os.chmod(os.path.join(tree, path), 0o644)
    make_file(os.path.join(tree, path), data.upper())                # local bytes no longer hash to the pin
    refusal("exemption", si.remote_receive, remote, "dest", local, [item(path, data.upper())], dirs,
            ssh_binary=shim[0])
    ok(not os.path.exists(shim[1]) and not os.path.exists(dest), "ssh ran or the destination was created")


def e5_manifest(dest, path, data, **fields):
    record = {"rel": path, "size": len(data), "sha256": sha(data), "mode": 0o444, "e4": False, "e5": True}
    record.update(fields)
    req = {"schema": si.RECEIVE_REQUEST_SCHEMA, "host": os.uname().nodename.split(".")[0], "root": dest,
           "grants": [], "dirs": dirs_of([path]), "files": [record], "max_total": len(data)}
    return json.dumps(req, sort_keys=True, separators=(",", ":")).encode()


def test_receiver_checks_the_blob_oid_itself(base):
    path, data = PATHS[0], E5_FILES[PATHS[0]]                        # real pins in the shipped program
    dest = os.path.join(base, "d1")
    reply = refused_directly(e5_manifest(dest, path, data), data, "exemption")
    ok(reply["created"][-1] == path)                                 # partial kept and listed
    with open(os.path.join(dest, path), "rb") as stream:
        ok(stream.read() == data)


@pytest.mark.parametrize("label", ["mode-0555", "not-e5-path", "case-variant", "e4-too", "flag-false", "flag-type"])
def test_receiver_manifest_refusals_create_nothing(base, label):
    path, data, fields, code = PATHS[0], E5_FILES[PATHS[0]], {}, "exemption"
    if label == "mode-0555":
        fields = {"mode": 0o555}
    elif label == "not-e5-path":
        path = "scripts/other_games.py"
    elif label == "case-variant":
        path = "Scripts/compare_native_public_games.py"
    elif label == "e4-too":
        fields = {"e4": True}
    elif label == "flag-false":
        fields, code = {"e5": False}, "name"
    else:
        fields, code = {"e5": 1}, "request"
    dest = os.path.join(base, "d")
    reply = refused_directly(e5_manifest(dest, path, data, **fields), data, code)
    ok(reply["created"] == [] and not os.path.exists(dest))


def test_receiver_accepts_pinned_bytes(base):
    path, data = PATHS[-1], E5_FILES[PATHS[-1]]
    pins = {p: o for p, o in RULED}
    pins[path] = blob_oid(data)
    dest = os.path.join(base, "d")
    man = e5_manifest(dest, path, data)
    rc, out, err = run_receiver(man, data, program=shipped_with(pins).encode())
    ok(rc == 0, (rc, out, err))
    si.parse_receive_receipt(man, rc, out)
    with open(os.path.join(dest, path), "rb") as stream:
        ok(stream.read() == data)
