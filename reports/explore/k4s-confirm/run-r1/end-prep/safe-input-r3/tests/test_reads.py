"""The component-wise O_NOFOLLOW walk, the descriptor gate, bounded reads and strict JSON."""
import json
import os
import socket

import pytest

from conftest import ident, make_file, ok, policy, refusal, role, si


@pytest.fixture
def data(base):
    root = os.path.join(base, "root")
    make_file(os.path.join(root, "a", "b", "c", "leaf.json"), b'{"k": 1}\n')
    make_file(os.path.join(root, "top.json"), b'[1, 2]')
    return root


def pol(root, **kw):
    args = dict(patterns=("**",), max_size=1 << 20)
    args.update(kw)
    return policy([role("r", root, **args)])


def test_happy_reads(data):
    p = pol(data)
    ok(si.read_bytes(p, "r", "a/b/c/leaf.json") == b'{"k": 1}\n')
    ok(si.read_json(p, "r", "a/b/c/leaf.json", 100) == {"k": 1})
    h = si.sha256_input(p, "r", "top.json")
    import hashlib
    ok(h == {"sha256": hashlib.sha256(b"[1, 2]").hexdigest(), "size": 6})
    ok(si.read_bytes(p, "r", "top.json", expected_size=6, expected_sha256=h["sha256"]) == b"[1, 2]")
    with si.open_input(p, "r", "top.json") as item:
        ok(item.size == 6)
        ok(item.read_bytes() == b"[1, 2]")
        refusal("state", item.read_bytes)                         # an Input is consumed once


# ---------------------------------------------------------------- root canonical / ancestors
def test_symlink_root_refuses(base, data):
    link = os.path.join(base, "rootlink")
    os.symlink(data, link)
    refusal("root", si.read_bytes, pol(link), "r", "top.json")


def test_symlink_ancestor_of_root_refuses(base, data):
    os.symlink(base, os.path.join(base, "anc"))
    e = refusal("root", si.read_bytes, pol(os.path.join(base, "anc", "root")), "r", "top.json")
    ok("ancestor or root" in e.reason and "is a symlink" in e.reason, e.reason)   # the explicit lstat layer


def test_missing_and_file_root_refuse(base, data):
    refusal("root", si.read_bytes, pol(os.path.join(base, "nope")), "r", "top.json")
    refusal("root", si.read_bytes, pol(os.path.join(data, "top.json")), "r", "x")


def test_realpath_is_checked_even_without_symlinks(monkeypatch, data):
    monkeypatch.setattr(os.path, "realpath", lambda p: p + "-elsewhere")
    refusal("root", si.read_bytes, pol(data), "r", "top.json")


# ---------------------------------------------------------------- symlink at every component and leaf
@pytest.mark.parametrize("depth", [0, 1, 2, 3])
def test_symlink_at_every_component_refuses(base, data, rec, depth):
    parts = ["a", "b", "c", "leaf.json"]
    target_dir = os.path.join(base, "elsewhere")
    os.makedirs(target_dir)
    victim = os.path.join(data, *parts[:depth + 1])
    real = victim + ".real"
    os.rename(victim, real)
    os.symlink(real, victim)                                     # an in-tree alias still refuses
    with rec:
        e = refusal("symlink", si.read_bytes, pol(data), "r", "a/b/c/leaf.json")
    ok("is a symlink" in e.reason, e.reason)                     # refused by the fstatat layer, before any open
    leaf_ident = ident(os.path.join(real, *parts[depth + 1:])) if depth < 3 else ident(real)
    ok(not rec.touched(leaf_ident), "the aliased leaf was opened or read")


def test_non_directory_component_refuses(data):
    make_file(os.path.join(data, "f"), b"x")
    refusal("not-dir", si.read_bytes, pol(data), "r", "f/x.json")


def test_missing_refuses(data):
    refusal("missing", si.read_bytes, pol(data), "r", "a/none.json")
    refusal("missing", si.read_bytes, pol(data), "r", "zz/none.json")


# ---------------------------------------------------------------- non-regular leaves: refused before any open
def test_fifo_leaf_refuses_without_open(data, rec):
    os.mkfifo(os.path.join(data, "fifo"))
    with rec:
        refusal("not-regular", si.read_bytes, pol(data), "r", "fifo")
    ok(rec.open_attempts.count(ident(os.path.join(data, "fifo"))) == 0)


def test_socket_leaf_refuses(data):
    sock = socket.socket(socket.AF_UNIX)
    path = os.path.join(data, "sock")
    try:
        sock.bind(path)
        refusal("not-regular", si.read_bytes, pol(data), "r", "sock")
    finally:
        sock.close()


def test_directory_leaf_refuses(data):
    refusal("not-regular", si.read_bytes, pol(data), "r", "a/b")


def test_device_leaf_refuses_without_open(rec):
    p = policy([role("dev", "/dev", exact=("null", "zero"))])
    with rec:
        refusal("not-regular", si.read_bytes, p, "dev", "null")
        refusal("not-regular", si.read_bytes, p, "dev", "zero")
    ok(ident("/dev/null") not in rec.open_attempts and ident("/dev/zero") not in rec.open_attempts)


# ---------------------------------------------------------------- descriptor gate
def test_hard_link_refuses_before_open(base, data, rec):
    other = make_file(os.path.join(base, "outside.json"), b'{"x": 1}')
    os.link(other, os.path.join(data, "alias.json"))
    with rec:
        refusal("nlink", si.read_bytes, pol(data), "r", "alias.json")
    ok(not rec.touched(ident(other)))


def test_size_cap_refuses_before_open(data, rec):
    with rec:
        refusal("size", si.read_bytes, pol(data, max_size=5), "r", "top.json")
        refusal("size", si.read_bytes, pol(data), "r", "top.json", expected_size=7)
        refusal("size", si.read_bytes, pol(data), "r", "top.json", max_size=5)
    ok(not rec.touched(ident(os.path.join(data, "top.json"))))
    ok(si.read_bytes(pol(data, max_size=6), "r", "top.json") == b"[1, 2]")


def test_sha_mismatch_refuses(data):
    refusal("sha", si.read_bytes, pol(data), "r", "top.json", expected_sha256="0" * 64)


def _swap_between_check_and_open(monkeypatch, action):
    """Run `action` right before the leaf open (simulates a concurrent change after the fstatat check)."""
    real_open = os.open
    state = {"done": False}

    def wrapped(path, flags, mode=0o777, *, dir_fd=None):
        if not state["done"] and not flags & os.O_DIRECTORY and dir_fd is not None:
            state["done"] = True
            action()
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", wrapped)


def test_leaf_replaced_between_check_and_open_refuses(monkeypatch, data):
    leaf = os.path.join(data, "top.json")

    def replace():
        os.rename(leaf, leaf + ".old")
        make_file(leaf, b"[1, 2]")
    _swap_between_check_and_open(monkeypatch, replace)
    refusal("changed", si.read_bytes, pol(data), "r", "top.json")


def test_hard_link_appearing_at_open_refuses(monkeypatch, base, data):
    leaf = os.path.join(data, "top.json")
    _swap_between_check_and_open(monkeypatch, lambda: os.link(leaf, os.path.join(base, "late-link")))
    refusal("nlink", si.read_bytes, pol(data), "r", "top.json")


def test_growth_before_open_refuses(monkeypatch, data):
    leaf = os.path.join(data, "top.json")

    def grow():
        with open(leaf, "ab") as stream:
            stream.write(b"x" * 10)
    _swap_between_check_and_open(monkeypatch, grow)
    refusal("size", si.read_bytes, pol(data, max_size=8), "r", "top.json")


def test_directory_replaced_between_check_and_open_refuses(monkeypatch, data):
    real_open = os.open
    state = {"done": False}
    target = os.path.join(data, "a")

    def wrapped(path, flags, mode=0o777, *, dir_fd=None):
        if path == "a" and not state["done"]:
            state["done"] = True
            os.rename(target, target + ".old")
            os.mkdir(target)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", wrapped)
    refusal("changed", si.read_bytes, pol(data), "r", "a/b/c/leaf.json")


# ---------------------------------------------------------------- growth / shrink during the read
def test_growth_during_read_refuses(data):
    leaf = os.path.join(data, "top.json")
    item = si.open_input(pol(data), "r", "top.json")
    with open(leaf, "ab") as stream:
        stream.write(b"EXTRA")
    refusal("growth", item.read_bytes)


def test_shrink_during_read_refuses(data):
    leaf = os.path.join(data, "top.json")
    item = si.open_input(pol(data), "r", "top.json")
    os.truncate(leaf, 2)
    refusal("shrink", item.sha256)


def test_growth_after_last_byte_detected_by_fstat(monkeypatch, data):
    """An append racing exactly after the extra-byte probe is caught by the final fstat."""
    leaf = os.path.join(data, "top.json")
    item = si.open_input(pol(data), "r", "top.json")
    real_read = os.read
    calls = {"n": 0}

    def wrapped(fd, n):
        calls["n"] += 1
        out = real_read(fd, n)
        if calls["n"] == 2:                                      # the 1-byte probe returned b""
            with open(leaf, "ab") as stream:
                stream.write(b"Z")
        return out
    monkeypatch.setattr(os, "read", wrapped)
    refusal("growth", item.read_bytes)


# ---------------------------------------------------------------- strict JSON
@pytest.mark.parametrize("raw", [b'{"a": 1, "a": 2}', b'{"a": NaN}', b'[Infinity]', b'[-Infinity]', b'\xff\xfe{}',
                                 b'{"a": 1', b'', b'\xef\xbb\xbf{}'])
def test_strict_json_refuses(data, raw):
    make_file(os.path.join(data, "bad.json"), raw)
    refusal("json", si.read_json, pol(data), "r", "bad.json", 100)


def test_json_cap(data):
    make_file(os.path.join(data, "big.json"), json.dumps(list(range(100))).encode())
    refusal("size", si.read_json, pol(data), "r", "big.json", 10)


# ---------------------------------------------------------------- confined recursive walk
def test_walk_tree(base, data):
    tree = si.walk_tree(pol(data), "r")
    ok([f["rel"] for f in tree["files"]] == ["a/b/c/leaf.json", "top.json"] and tree["e1"] is None)
    ok(si.walk_tree(pol(data), "r", "a")["files"][0]["rel"] == "a/b/c/leaf.json")
    refusal("allowlist", si.walk_tree, pol(data, patterns=("*.json",)), "r")      # a/b/c/leaf.json is undeclared
    make_file(os.path.join(data, "a", "x.txt"), b"x")
    refusal("allowlist", si.walk_tree, pol(data, patterns=("**/*.json", "*.json")), "r")
    os.unlink(os.path.join(data, "a", "x.txt"))
    os.mkfifo(os.path.join(data, "a", "fifo"))
    refusal("not-regular", si.walk_tree, pol(data), "r")
    os.unlink(os.path.join(data, "a", "fifo"))
    os.link(os.path.join(data, "top.json"), os.path.join(base, "hl"))
    refusal("nlink", si.walk_tree, pol(data), "r")
    os.unlink(os.path.join(base, "hl"))
    refusal("size", si.walk_tree, pol(data, max_size=5), "r")
    refusal("size", si.walk_tree, pol(data), "r", None, 3)
    os.symlink(os.path.join(data, "top.json"), os.path.join(data, "a", "ln"))
    refusal("symlink", si.walk_tree, pol(data), "r")


# ---------------------------------------------------------------- directory helpers
def test_check_dir_and_absent(base, data):
    p = pol(data)
    ok(si.check_dir(p, "r")["ino"] == os.stat(data).st_ino)
    ok(si.check_dir(p, "r", "a/b")["ino"] == os.stat(os.path.join(data, "a", "b")).st_ino)
    refusal("not-dir", si.check_dir, p, "r", "top.json")
    refusal("name", si.check_dir, p, "r", "games")
    ok(si.check_absent(p, "r", "a/new.json") is True)
    refusal("exists", si.check_absent, p, "r", "top.json")
    os.symlink("/nonexistent", os.path.join(data, "dangling"))
    refusal("exists", si.check_absent, p, "r", "dangling")
    os.symlink(base, os.path.join(data, "sl"))
    refusal("symlink", si.check_absent, p, "r", "sl/x")
    refusal("symlink", si.check_dir, p, "r", "sl")


# ---------------------------------------------------------------- the open flags themselves (races after the fstatat)
def test_directory_swapped_to_symlink_at_open_refuses_by_o_nofollow(monkeypatch, base, data):
    real_open = os.open
    state = {"done": False}
    target = os.path.join(data, "a")
    os.makedirs(os.path.join(base, "other", "b", "c"))

    def wrapped(path, flags, mode=0o777, *, dir_fd=None):
        if path == "a" and not state["done"]:
            state["done"] = True
            os.rename(target, target + ".old")
            os.symlink(os.path.join(base, "other"), target)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", wrapped)
    refusal("symlink", si.read_bytes, pol(data), "r", "a/b/c/leaf.json")


def test_leaf_swapped_to_symlink_at_open_refuses_by_o_nofollow(monkeypatch, base, data):
    leaf = os.path.join(data, "top.json")
    other = make_file(os.path.join(base, "other.json"), b"[1, 2]")

    def swap():
        os.rename(leaf, leaf + ".old")
        os.symlink(other, leaf)
    _swap_between_check_and_open(monkeypatch, swap)
    refusal("symlink", si.read_bytes, pol(data), "r", "top.json")


def test_leaf_swapped_to_fifo_at_open_never_blocks(monkeypatch, data):
    import threading
    leaf = os.path.join(data, "top.json")

    def swap():
        os.rename(leaf, leaf + ".old")
        os.mkfifo(leaf)
    _swap_between_check_and_open(monkeypatch, swap)
    result = {}

    def run():
        try:
            si.read_bytes(pol(data), "r", "top.json")
        except si.Refusal as error:
            result["code"] = error.code
    t = threading.Thread(target=run)
    t.daemon = True
    t.start()
    t.join(10)
    if t.is_alive():                                             # release the blocked open, then fail
        fd = os.open(leaf, os.O_WRONLY | os.O_NONBLOCK)
        os.close(fd)
        t.join(5)
        raise AssertionError("the leaf open blocked on a FIFO (O_NONBLOCK missing)")
    ok(result.get("code") == "not-regular", result)
