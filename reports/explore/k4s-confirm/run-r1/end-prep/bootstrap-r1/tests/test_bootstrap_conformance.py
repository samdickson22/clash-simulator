"""bootstrap-r1: the canonical bootstrap itself (in-process). Name-gate conformance with safe_input r3, every guard of
the contract (each with a direct refusal test, zero bytes read where the contract says so), execution semantics, and
the canonical-text invariants that let the same bytes be pasted into Python adopters and the shell wrappers."""
import ast
import errno
import hashlib
import itertools
import os
import random
import re
import subprocess
import sys
import traceback

import pytest

from conftest import (BUILDER_FILE, LOADER_FILE, SHELL_FILE, SI_SHA256, SI_SIZE, SNIPPET_FILE, load_snippet, ok)

BEGIN = b"# ==== BEGIN K4S CANONICAL BOOTSTRAP r1 "
END = b"# ==== END K4S CANONICAL BOOTSTRAP r1 ====\n"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    with open(path, "rb") as handle:
        return handle.read()


def put(path, data, mode=0o644):
    with open(path, "wb") as handle:
        handle.write(data)
    os.chmod(path, mode)
    return str(path)


class Recorder:
    """Counts os.open calls and os.read bytes per inode while installed (monkeypatch)."""

    def __init__(self, monkeypatch):
        self.opens, self.bytes, self.open_names = 0, {}, []
        real_open, real_read = os.open, os.read

        def h_open(path, flags, *a, **k):
            self.opens += 1
            self.open_names.append(path)
            return real_open(path, flags, *a, **k)

        def h_read(fd, n):
            data = real_read(fd, n)
            st = os.fstat(fd)
            key = (st.st_dev, st.st_ino)
            self.bytes[key] = self.bytes.get(key, 0) + len(data)
            return data

        monkeypatch.setattr(os, "open", h_open)
        monkeypatch.setattr(os, "read", h_read)

    def read_of(self, path):
        st = os.stat(path, follow_symlinks=False)
        return self.bytes.get((st.st_dev, st.st_ino), 0)


def open_fds():
    return sorted(os.listdir("/proc/self/fd"))


@pytest.fixture
def layer(tmp_path):
    """A small pinned layer in a clean tree: (path, bytes, sha, size)."""
    d = tmp_path / "clean" / "pkg"
    d.mkdir(parents=True)
    data = b"MARK = \"verified\"\nVALUE = 41 + 1\n" + b"# pad\n" * 20
    path = put(d / "layer.py", data)
    return path, data, sha(data), len(data)


def refuses(bs, path, pin, size, pattern, refusal=RuntimeError):
    with pytest.raises(refusal) as info:
        bs.k4s_bootstrap_read_verified(path, pin, size, refusal)
    ok(re.search(pattern, str(info.value)), str(info.value))
    ok(str(info.value).startswith("k4s bootstrap refused: "), str(info.value))
    return info.value


# ---------------------------------------------------------------- 2. the name gate == safe_input r3 outcome families

def test_family_literals_equal_safe_input_r3(bs, si):
    ok(bs.K4S_BOOTSTRAP_OUTCOME_FAMILIES == si.OUTCOME_FAMILIES, "family literals differ from safe_input r3")
    ok(si.constants_fingerprint() == "33f594ed75c3b3b6416ec8b4804490b82a85521533056b57c1d582529207f592")


def name_corpus():
    tokens = ["games", "game", "gamess", "xgames", "games1", "1games", "my-games", "my_games.d", "gamesx", "agames",
              "hub-blocks", "hub_blocks", "hub.blocks", "hubblocks", "hub-block", "hubblock", "hubxblocks", "hub--blocks",
              "complete", "complete.json", "x.complete.json", "completejson", "incomplete.json.tmp", ".complete.json",
              "interference.json", "interference", "interferencejson", "hub-ack.json", "hub_ack.json", "huback.json",
              "hub-ack", "hub--ack.json", "end-raw.json", "end_raw.json", "endraw.json", "end--raw.json", "end-raw",
              "json", "safe_input.py", "k4s-confirm", "end", "attempt-01.json", "END-JOB", "end-final", "gameſ",
              "GAMEẞ", "Ｇames", "gamеs", "hub\u212aack.json", "ﬁnal", "games\n", "games\x00x", "complete\u0130.json",
              "\ngames", "a\nb_games", "complete\n.json", "x\ncomplete.json", "complete.json\nz", "hub\nack.json",
              "end-raw\n.json", "interference\n.json"]
    affixes = ["", "x", "1", "-", "_", ".", "a-", "-z", ".bak", ".json", "~", "é"]
    rng = random.Random(20261012)
    out = set()
    for token in tokens:
        cases = {token, token.upper(), token.lower(), token.title(), token.swapcase()}
        for _ in range(3):
            cases.add("".join(c.upper() if rng.random() < 0.5 else c.lower() for c in token))
        for case, pre, post in itertools.product(sorted(cases), affixes, affixes):
            out.add(pre + case + post)
    alphabet = "gamesGAMEScompletJSONhubkrwdif-_.1ſßK" + "\u212a"
    for _ in range(30000):
        out.add("".join(rng.choice(alphabet) for _ in range(rng.randint(1, 16))))
    return sorted(out)


def test_name_gate_agrees_with_safe_input_on_a_broad_corpus(bs, si):
    corpus = name_corpus()
    labels = {}
    for name in corpus:
        mine, theirs = bs.k4s_bootstrap_name_family(name), si.outcome_family(name)
        ok(mine == theirs, "disagreement on %r: bootstrap %r, safe_input %r" % (name, mine, theirs))
        labels[mine] = labels.get(mine, 0) + 1
    ok(len(corpus) > 40000, len(corpus))
    ok(set(labels) == {None} | {f[0] for f in si.OUTCOME_FAMILIES}, labels)       # every family exercised
    ok(labels[None] > 5000 and sum(v for k, v in labels.items() if k) > 5000, labels)


@pytest.mark.parametrize("component", ["games", "GAMES", "Games.d", "x-games", "gameſ", "hub-blocks", "Hub_Block",
                                       "old.hubblocks", "a.complete.json", "COMPLETE.JSON.tmp", "interference.json~",
                                       "hub.ack.json", "End-Raw.json.bak", "endraw.JSON"])
@pytest.mark.parametrize("position", ["ancestor", "leaf"])
def test_outcome_named_component_refuses_before_any_open(bs, si, tmp_path, monkeypatch, component, position):
    ok(si.outcome_family(component) is not None)
    d = tmp_path / "t"
    d.mkdir()
    if position == "ancestor":
        (d / component).mkdir()
        path = put(d / component / "layer.py", b"x = 1\n")
    else:
        path = put(d / component, b"x = 1\n")
    rec = Recorder(monkeypatch)
    refuses(bs, path, sha(b"x = 1\n"), 6, r"outcome name family")
    ok(rec.opens == 0 and not rec.bytes, (rec.opens, rec.bytes))


# ---------------------------------------------------------------- 1. pins and path form (no syscall at all)

@pytest.mark.parametrize("pin,size,pattern", [
    ("A" * 64, 10, "SHA-256 pin"), ("a" * 63, 10, "SHA-256 pin"), ("g" * 64, 10, "SHA-256 pin"), (None, 10, "SHA-256 pin"),
    ("a" * 64, 0, "size pin"), ("a" * 64, -1, "size pin"), ("a" * 64, True, "size pin"), ("a" * 64, "10", "size pin"),
    ("a" * 64, (1 << 24) + 1, "size pin"), ("a" * 64, 10.0, "size pin")])
def test_bad_pins_refuse_without_any_syscall(bs, layer, monkeypatch, pin, size, pattern):
    rec = Recorder(monkeypatch)
    refuses(bs, layer[0], pin, size, pattern)
    ok(rec.opens == 0)


@pytest.mark.parametrize("form", ["relative", "double-slash-start", "trailing-slash", "dot", "dotdot", "empty-component",
                                  "control", "backslash", "nul", "root", "bytes", "none"])
def test_non_normalized_path_refuses_without_any_syscall(bs, layer, monkeypatch, form):
    path = layer[0]
    head, leaf = os.path.split(path)
    bad = {"relative": os.path.relpath(path, "/"), "double-slash-start": "/" + path, "trailing-slash": path + "/",
           "dot": head + "/./" + leaf, "dotdot": head + "/../pkg/" + leaf, "empty-component": head + "//" + leaf,
           "control": head + "/la\tyer.py", "backslash": head + "/la\\yer.py", "nul": head + "/la\x00yer.py",
           "root": "/", "bytes": path.encode(), "none": None}[form]
    rec = Recorder(monkeypatch)
    refuses(bs, bad, layer[2], layer[3], r"absolute normalized|control or backslash|empty, \. or \.\.")
    ok(rec.opens == 0)


def test_component_check_is_independent_of_normpath(bs, layer, monkeypatch):
    """With normpath neutralised (identity), the explicit component check still refuses '.', '..' and ''."""
    monkeypatch.setattr(os.path, "normpath", lambda p: p)
    head, leaf = os.path.split(layer[0])
    for bad in (head + "/./" + leaf, head + "/../pkg/" + leaf, head + "//" + leaf):
        refuses(bs, bad, layer[2], layer[3], r"empty, \. or \.\. component")


def test_default_path_never_resolves_or_normalizes(bs, tmp_path, monkeypatch):
    ok(bs.k4s_bootstrap_default_path("/a/link/../b/s2.py", "safe_input.py") == "/a/link/../b/safe_input.py")
    ok(bs.k4s_bootstrap_default_path("/a/alias/s2.py", "safe_input.py") == "/a/alias/safe_input.py")
    monkeypatch.chdir(tmp_path)
    cwd = os.getcwd()
    ok(bs.k4s_bootstrap_default_path("s2.py", "safe_input.py") == cwd + "/safe_input.py")
    ok(bs.k4s_bootstrap_default_path("./s2.py", "safe_input.py") == cwd + "/./safe_input.py")    # walk refuses it
    ok(bs.k4s_bootstrap_default_path("sub/s2.py", "safe_input.py") == cwd + "/sub/safe_input.py")


# ---------------------------------------------------------------- 3. the component walk

def test_ancestor_symlink_refuses_with_zero_canary_bytes(bs, layer, tmp_path, monkeypatch):
    path, data, pin, size = layer
    games = tmp_path / "synth" / "games" / "pkg"
    games.mkdir(parents=True)
    canary = put(games / "layer.py", b"Z" * size)
    os.symlink(str(games), str(tmp_path / "alias"))
    before = open_fds()
    rec = Recorder(monkeypatch)
    refuses(bs, str(tmp_path / "alias" / "layer.py"), pin, size, r"ancestor 'alias' is a symlink")
    ok(rec.read_of(canary) == 0 and not rec.bytes)
    ok(open_fds() == before, "descriptor leak")


def test_ancestor_symlink_to_pinned_bytes_still_refuses(bs, layer, tmp_path, monkeypatch):
    path, data, pin, size = layer
    os.symlink(os.path.dirname(path), str(tmp_path / "alias"))
    rec = Recorder(monkeypatch)
    refuses(bs, str(tmp_path / "alias" / "layer.py"), pin, size, r"ancestor 'alias' is a symlink")
    ok(not rec.bytes)


def test_ancestor_symlink_high_in_the_path_refuses(bs, layer, tmp_path, monkeypatch):
    path, data, pin, size = layer
    os.symlink(str(tmp_path / "clean"), str(tmp_path / "up"))
    rec = Recorder(monkeypatch)
    refuses(bs, str(tmp_path / "up" / "pkg" / "layer.py"), pin, size, r"ancestor 'up' is a symlink")
    ok(not rec.bytes)


def test_ancestor_that_is_a_file_or_missing_refuses(bs, layer, tmp_path):
    path, data, pin, size = layer
    put(tmp_path / "plainfile", b"")
    refuses(bs, str(tmp_path / "plainfile" / "layer.py"), pin, size, r"ancestor 'plainfile'.*Not a directory")
    refuses(bs, str(tmp_path / "absent" / "layer.py"), pin, size, r"ancestor 'absent'.*No such file")


def test_walk_opens_only_directory_nofollow_components_relative_to_parents(bs, layer, monkeypatch):
    path, data, pin, size = layer
    calls = []
    real_open = os.open

    def h_open(p, flags, *a, **k):
        calls.append((p, flags, k.get("dir_fd")))
        return real_open(p, flags, *a, **k)
    monkeypatch.setattr(os, "open", h_open)
    ok(bs.k4s_bootstrap_read_verified(path, pin, size, RuntimeError) == data)
    parts = path[1:].split("/")
    ok([c[0] for c in calls] == ["/"] + parts, calls)
    for name, flags, dir_fd in calls[1:-1]:
        ok(flags & os.O_DIRECTORY and flags & os.O_NOFOLLOW and dir_fd is not None, (name, flags))
    leaf_flags = calls[-1][1]
    ok(leaf_flags & os.O_NOFOLLOW and leaf_flags & os.O_NONBLOCK and not leaf_flags & (os.O_WRONLY | os.O_RDWR))
    ok(calls[-1][2] is not None)


def test_ancestor_must_be_a_directory_even_if_open_succeeds(bs, layer, monkeypatch):
    """If an ancestor open ever returned a non-directory (O_DIRECTORY ignored), the fstat check refuses."""
    path, data, pin, size = layer
    real_open = os.open
    parts = path[1:].split("/")

    def h_open(p, flags, *a, **k):
        if p == parts[-2]:
            return real_open(path, os.O_RDONLY)                    # a regular file posing as the parent directory
        return real_open(p, flags, *a, **k)
    monkeypatch.setattr(os, "open", h_open)
    refuses(bs, path, pin, size, r"ancestor '%s' is not a directory" % parts[-2])


def test_root_must_be_a_directory(bs, layer, monkeypatch):
    path, data, pin, size = layer
    real_open = os.open

    def h_open(p, flags, *a, **k):
        if p == "/":
            return real_open(path, os.O_RDONLY)
        return real_open(p, flags, *a, **k)
    monkeypatch.setattr(os, "open", h_open)
    refuses(bs, path, pin, size, r"/ is not a directory")


# ---------------------------------------------------------------- 4. the leaf, before any read

def test_leaf_symlink_refuses_unopened(bs, layer, tmp_path, monkeypatch):
    path, data, pin, size = layer
    target = put(tmp_path / "games-target.py", data)                  # even the pinned bytes, via a link
    os.unlink(path)
    os.symlink(target, path)
    rec = Recorder(monkeypatch)
    refuses(bs, path, pin, size, r"leaf is not a single-link regular file")
    ok(not rec.bytes and rec.opens == len(path[1:].split("/")))       # "/" + ancestors only; the leaf never opened


def test_hard_linked_leaf_refuses_unread(bs, layer, tmp_path, monkeypatch):
    path, data, pin, size = layer
    os.link(path, str(tmp_path / "games-hardlink.py"))
    rec = Recorder(monkeypatch)
    refuses(bs, path, pin, size, r"leaf is not a single-link regular file")
    ok(not rec.bytes)


@pytest.mark.parametrize("delta", [1, -1])
def test_wrong_size_refuses_unread(bs, layer, monkeypatch, delta):
    path, data, pin, size = layer
    rec = Recorder(monkeypatch)
    refuses(bs, path, pin, size + delta, r"pinned size")
    ok(not rec.bytes)


def test_fifo_leaf_refuses_unopened(bs, tmp_path, monkeypatch):
    os.mkfifo(str(tmp_path / "layer.py"))
    rec = Recorder(monkeypatch)
    refuses(bs, str(tmp_path / "layer.py"), "a" * 64, 10, r"leaf is not a single-link regular file")
    ok(not rec.bytes and "layer.py" not in rec.open_names)


def test_directory_leaf_refuses_unopened(bs, tmp_path, monkeypatch):
    (tmp_path / "layer.py").mkdir()
    rec = Recorder(monkeypatch)
    refuses(bs, str(tmp_path / "layer.py"), "a" * 64, 10, r"leaf is not a single-link regular file")
    ok("layer.py" not in rec.open_names)


def test_missing_leaf_refuses(bs, tmp_path):
    refuses(bs, str(tmp_path / "nothing.py"), "a" * 64, 10, r"leaf cannot be inspected.*No such file")


def test_leaf_replaced_between_inspection_and_open_refuses_unread(bs, layer, tmp_path, monkeypatch):
    """Same size, single link, regular - but another inode: the dev/ino comparison refuses before reading."""
    path, data, pin, size = layer
    other = put(tmp_path / "other.py", b"Q" * size)
    rec = Recorder(monkeypatch)
    inner_open = os.open

    def h_open(p, flags, *a, **k):
        if p == "layer.py":
            os.rename(other, path)
        return inner_open(p, flags, *a, **k)
    monkeypatch.setattr(os, "open", h_open)
    refuses(bs, path, pin, size, r"opened leaf is not the inspected")
    ok(rec.read_of(path) == 0)


def test_leaf_hard_linked_between_inspection_and_open_refuses_unread(bs, layer, tmp_path, monkeypatch):
    path, data, pin, size = layer
    real_open = os.open
    rec_bytes = {}
    real_read = os.read

    def h_open(p, flags, *a, **k):
        if p == "layer.py":
            os.link(path, str(tmp_path / "late-link.py"))
        return real_open(p, flags, *a, **k)

    def h_read(fd, n):
        rec_bytes[fd] = rec_bytes.get(fd, 0) + n
        return real_read(fd, n)
    monkeypatch.setattr(os, "open", h_open)
    monkeypatch.setattr(os, "read", h_read)
    refuses(bs, path, pin, size, r"opened leaf is not the inspected")
    ok(not rec_bytes)


def test_leaf_grown_between_inspection_and_open_refuses_unread(bs, layer, monkeypatch):
    path, data, pin, size = layer
    real_open = os.open
    reads = []
    real_read = os.read

    def h_open(p, flags, *a, **k):
        if p == "layer.py":
            with open(path, "ab") as handle:
                handle.write(b"#")
        return real_open(p, flags, *a, **k)
    monkeypatch.setattr(os, "open", h_open)
    monkeypatch.setattr(os, "read", lambda fd, n: reads.append(n) or real_read(fd, n))
    refuses(bs, path, pin, size, r"opened leaf is not the inspected")
    ok(not reads)


def test_leaf_turned_non_regular_after_open_refuses(bs, layer, monkeypatch):
    """Defence in depth: if fstat of the opened descriptor ever showed a non-regular file, nothing is read."""
    path, data, pin, size = layer
    real_fstat = os.fstat

    class Fake:
        def __init__(self, st):
            self.st_mode, self.st_nlink, self.st_size = 0o010644, st.st_nlink, st.st_size
            self.st_dev, self.st_ino = st.st_dev, st.st_ino

    def h_fstat(fd):
        st = real_fstat(fd)
        if st.st_size == size and st.st_ino == os.stat(path).st_ino:
            return Fake(st)
        return st
    monkeypatch.setattr(os, "fstat", h_fstat)
    refuses(bs, path, pin, size, r"opened leaf is not the inspected")


def test_short_read_refuses(bs, layer, monkeypatch):
    path, data, pin, size = layer
    monkeypatch.setattr(os, "read", lambda fd, n: b"")
    refuses(bs, path, pin, size, r"shrank while read")


def test_growth_after_size_bytes_refuses(bs, layer, monkeypatch):
    path, data, pin, size = layer
    real_read = os.read
    monkeypatch.setattr(os, "read", lambda fd, n: real_read(fd, n) or b"+")
    refuses(bs, path, pin, size, r"grew while read")


def test_chunked_reads_are_accumulated(bs, layer, monkeypatch):
    path, data, pin, size = layer
    real_read = os.read
    monkeypatch.setattr(os, "read", lambda fd, n: real_read(fd, min(n, 7)))
    ok(bs.k4s_bootstrap_read_verified(path, pin, size, RuntimeError) == data)


# ---------------------------------------------------------------- 5. hash, then exactly those bytes

def test_same_size_mismatch_is_read_once_and_refused_by_the_pin(bs, layer, monkeypatch):
    path, data, pin, size = layer
    put(path, b"raise SystemExit(\"executed\")\n".ljust(size, b"#"))
    rec = Recorder(monkeypatch)
    refuses(bs, path, pin, size, r"not the pinned SHA-256")
    ok(rec.read_of(path) == size and rec.opens == len(path[1:].split("/")) + 1)


def test_returns_exactly_the_pinned_bytes(bs, layer):
    path, data, pin, size = layer
    ok(bs.k4s_bootstrap_read_verified(path, pin, size, RuntimeError) == data)


def test_load_executes_exactly_the_hashed_bytes_and_never_reopens(bs, layer, tmp_path, monkeypatch):
    path, data, pin, size = layer
    decoy = put(tmp_path / "decoy.py", b"MARK = \"decoy\"\n".ljust(size, b"#"))
    real_read = bs.k4s_bootstrap_read_verified
    opens_after_hash = []

    def read_then_swap(*a):
        result = real_read(*a)
        os.rename(decoy, path)                                    # pathname now names other bytes
        real_open = os.open
        monkeypatch.setattr(os, "open", lambda p, *x, **k: opens_after_hash.append(p) or real_open(p, *x, **k))
        return result
    monkeypatch.setattr(bs, "k4s_bootstrap_read_verified", read_then_swap)
    module = bs.k4s_bootstrap_load(path, pin, size, "_bs_test_swap", RuntimeError)
    ok(module.MARK == "verified" and module.VALUE == 42)
    ok(sys.modules["_bs_test_swap"] is module and module.__file__ == path)
    ok(module.__k4s_bootstrap__ == ("k4s-bootstrap-r1", path, pin, size))
    ok(not [p for p in opens_after_hash if "layer" in str(p)], opens_after_hash)
    del sys.modules["_bs_test_swap"]


def test_traceback_shows_verified_lines_without_reopening(bs, tmp_path, monkeypatch):
    data = b"def boom():\n    raise ValueError(\"m\")  # verified-source-line\n"
    path = put(tmp_path / "tb.py", data)
    module = bs.k4s_bootstrap_load(path, sha(data), len(data), "_bs_test_tb", RuntimeError)
    put(path, b"def boom():\n    raise ValueError(\"m\")  # SWAPPED-SOURCE-LINE\n")
    seen = []
    real_open = os.open
    monkeypatch.setattr(os, "open", lambda p, *a, **k: seen.append(p) or real_open(p, *a, **k))
    import io
    real_io_open = io.open
    monkeypatch.setattr(io, "open", lambda p, *a, **k: seen.append(p) or real_io_open(p, *a, **k))
    try:
        module.boom()
    except ValueError:
        text = traceback.format_exc()
    ok("# verified-source-line" in text and "SWAPPED" not in text, text)    # the line comes from linecache
    ok("<k4s-bootstrap sha256=" + sha(data) in text, text)
    ok(path not in [str(p) for p in seen], seen)
    del sys.modules["_bs_test_tb"]


def test_failed_exec_restores_sys_modules(bs, tmp_path):
    data = b"raise KeyError(\"boom\")\n"
    path = put(tmp_path / "bad.py", data)
    with pytest.raises(KeyError):
        bs.k4s_bootstrap_load(path, sha(data), len(data), "_bs_test_fail", RuntimeError)
    ok("_bs_test_fail" not in sys.modules)
    sentinel = object()
    sys.modules["_bs_test_fail"] = sentinel
    with pytest.raises(KeyError):
        bs.k4s_bootstrap_load(path, sha(data), len(data), "_bs_test_fail", RuntimeError)
    ok(sys.modules["_bs_test_fail"] is sentinel)
    del sys.modules["_bs_test_fail"]


def test_module_is_registered_before_exec(bs, tmp_path):
    data = b"import sys\nSELF = sys.modules[__name__]\n"
    path = put(tmp_path / "selfref.py", data)
    module = bs.k4s_bootstrap_load(path, sha(data), len(data), "_bs_test_self", RuntimeError)
    ok(module.SELF is module)
    del sys.modules["_bs_test_self"]


def test_safe_input_loads_and_executes_through_the_bootstrap(si):
    ok(si.__k4s_bootstrap__[2:] == (SI_SHA256, SI_SIZE))
    ok(si.constants_fingerprint() == "33f594ed75c3b3b6416ec8b4804490b82a85521533056b57c1d582529207f592")
    ok(si.receive_program_sha256() == "39a92e9d55f9ffefba57bae453677bad7c834f7761283268b84e40bb2d1210b4")
    ok(si.remote_program_sha256() == "2d2f212d73b49176c53b1a03a621b64fbc6a8d4c15bd18051ac31f91016a6152")


# ---------------------------------------------------------------- 6. refusal conventions; descriptors

def test_refusal_conventions(bs, tmp_path):
    bad = str(tmp_path / "missing.py")
    with pytest.raises(SystemExit) as info:
        bs.k4s_bootstrap_read_verified(bad, "a" * 64, 1, SystemExit)
    ok(str(info.value.code).startswith("k4s bootstrap refused: leaf cannot be inspected"))

    class HostRefusal(Exception):
        def __init__(self, code, reason):
            Exception.__init__(self, code + ": " + reason)
            self.code = code
    with pytest.raises(HostRefusal) as info2:
        bs.k4s_bootstrap_read_verified(bad, "a" * 64, 1, lambda m: HostRefusal("bootstrap", m))
    ok(info2.value.code == "bootstrap")


def test_no_descriptor_leaks_on_any_path(bs, layer, tmp_path):
    path, data, pin, size = layer
    before = open_fds()
    for args in ((path, pin, size), (path, pin, size + 1), (path, "b" * 64, size), (str(tmp_path / "x" / "y"), pin, 1),
                 (str(tmp_path / "clean" / "pkg" / "nope.py"), pin, 1)):
        try:
            bs.k4s_bootstrap_read_verified(args[0], args[1], args[2], RuntimeError)
        except RuntimeError:
            pass
    ok(open_fds() == before, (before, open_fds()))


def test_no_assert_dependence_under_optimize(bs, layer):
    """The same refusal under -O in a fresh interpreter (no assert statements anywhere in the snippet)."""
    path, data, pin, size = layer
    code = ("import importlib.util,sys\ns=importlib.util.spec_from_file_location(\"b\",sys.argv[1])\n"
            "m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\n"
            "try:\n m.k4s_bootstrap_read_verified(sys.argv[2],sys.argv[3],int(sys.argv[4])+1,RuntimeError)\n"
            "except RuntimeError as e:\n print(\"REFUSED\",e)\n")
    for py in dict.fromkeys([sys.executable, "/usr/bin/python3"]):
        done = subprocess.run([py, "-O", "-B", "-I", "-c", code, SNIPPET_FILE, path, pin, str(size)],
                              capture_output=True, text=True)
        ok(done.returncode == 0 and "REFUSED k4s bootstrap refused" in done.stdout, done.stdout + done.stderr)


# ---------------------------------------------------------------- canonical text invariants

def test_snippet_text_invariants():
    text = read(SNIPPET_FILE)
    ok(text.startswith(BEGIN) and text.endswith(END) and text.count(BEGIN) == 1 and text.count(END) == 1)
    ok(b"'" not in text, "a single quote would break the shell embedding")
    tree = ast.parse(text)
    ok(not [n for n in ast.walk(tree) if isinstance(n, ast.Assert)], "assert in the snippet")
    imported = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imported |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            imported.add(n.module)
    ok(imported == {"hashlib", "os", "re", "stat", "sys", "types", "linecache"}, imported)
    top = {t.id for n in tree.body if isinstance(n, ast.Assign) for t in n.targets} | \
          {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    ok(all(name.startswith(("K4S_BOOTSTRAP_", "k4s_bootstrap_")) for name in top), top)
    code = text.decode()
    ok("realpath" not in code.replace("realpath is never called", "") and "abspath" not in code)


def test_loader_is_the_snippet_plus_main():
    snippet, loader = read(SNIPPET_FILE), read(LOADER_FILE)
    ok(loader.startswith(snippet) and b"'" not in loader)
    tail = loader[len(snippet):]
    ok(not [n for n in ast.walk(ast.parse(tail)) if isinstance(n, ast.Assert)])


def test_shell_fragment_is_regenerated_exactly_and_bash_passes_the_loader_unchanged():
    done = subprocess.run([sys.executable, "-I", "-B", BUILDER_FILE, LOADER_FILE], capture_output=True)
    ok(done.returncode == 0 and done.stdout == read(SHELL_FILE), "fragment differs from build_shell_fragment output")
    stub = ("python=/bin/false; host_tool=/x; host_tool_sha=x; host_tool_size=1\n"
            "k4s_verify_host_tool() { :; }\n")
    text = read(SHELL_FILE).decode()
    body = text.replace("k4s_verify_host_tool || exit 90\n", "")           # define only; do not run the verify
    script = stub + body + "printf %s \"$k4s_loader\"\n"
    out = subprocess.run(["/bin/bash", "-c", script], capture_output=True)
    ok(out.returncode == 0 and out.stdout == read(LOADER_FILE), out.stderr)
    code_lines = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
    ok(not [line for line in code_lines if "sha256sum" in line], "the fragment must not call sha256sum")
