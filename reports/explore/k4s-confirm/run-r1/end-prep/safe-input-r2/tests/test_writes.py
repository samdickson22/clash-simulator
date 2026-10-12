"""Exclusive, no-follow, never-truncating writes; canonical destination roots; refusal receipts."""
import hashlib
import json
import os
import stat

import pytest

from conftest import ident, make_file, ok, policy, refusal, role, si


@pytest.fixture
def out(base):
    path = os.path.join(base, "out")
    os.makedirs(path)
    return path


def wpol(root, **kw):
    args = dict(access="write", patterns=("**",), max_size=1 << 20)
    args.update(kw)
    return policy([role("w", root, **args)])


def test_happy_writes(out):
    w = si.Writer(wpol(out), "w")
    w.mkdir_excl("a")
    w.mkdir_excl("a/b")
    got = w.create_excl("a/b/x.bin", b"hello")
    ok(got == {"sha256": hashlib.sha256(b"hello").hexdigest(), "size": 5})
    st = os.stat(os.path.join(out, "a", "b", "x.bin"))
    ok(stat.S_IMODE(st.st_mode) == 0o444 and st.st_nlink == 1)
    w.write_json_once("r.json", {"b": 1, "a": [1]})
    with open(os.path.join(out, "r.json")) as stream:
        ok(json.load(stream) == {"a": [1], "b": 1})
    f = w.open_excl("stream.bin")
    f.write(b"ab")
    f.write(b"cd")
    ok(f.finish(0o440)["size"] == 4)
    refusal("state", f.write, b"x")
    w.close()
    refusal("state", w.create_excl, "late", b"x")


def test_existing_file_never_truncated(out):
    victim = make_file(os.path.join(out, "argv.nul"), b"ORIGINAL")
    before = ident(victim)
    w = si.Writer(wpol(out), "w")
    refusal("exists", w.create_excl, "argv.nul", b"NEW")
    refusal("exists", w.open_excl, "argv.nul")
    refusal("exists", w.write_json_once, "argv.nul", {})
    refusal("exists", w.mkdir_excl, "argv.nul")
    with open(victim, "rb") as stream:
        ok(stream.read() == b"ORIGINAL" and ident(victim) == before)


def test_existing_symlink_never_followed(base, out):
    foreign = make_file(os.path.join(base, "foreign", "keep.txt"), b"KEEP")
    os.symlink(foreign, os.path.join(out, "link"))
    os.symlink(os.path.join(base, "foreign", "new.txt"), os.path.join(out, "dangling"))
    w = si.Writer(wpol(out), "w")
    refusal("exists", w.create_excl, "link", b"X")
    refusal("exists", w.create_excl, "dangling", b"X")
    refusal("exists", w.mkdir_excl, "dangling")
    with open(foreign, "rb") as stream:
        ok(stream.read() == b"KEEP")
    ok(not os.path.exists(os.path.join(base, "foreign", "new.txt")))


def test_hard_linked_argv_nul_probe(base, out):
    """Reviewer probe S6-F2, generically: a foreign 'keep me' inode hard-linked as the metadata name."""
    keep = make_file(os.path.join(base, "foreign", "keep-me"), b"KEEP ME")
    job = os.path.join(out, "job")
    os.makedirs(job)
    os.link(keep, os.path.join(job, "argv.nul"))
    w = si.Writer(wpol(out), "w")
    refusal("exists", w.create_excl, "job/argv.nul", b"cmd\x00arg\x00")
    with open(keep, "rb") as stream:
        ok(stream.read() == b"KEEP ME" and os.stat(keep).st_nlink == 2)


def test_base_symlink_foreign_launch_dir_probe(base):
    """Reviewer probe S7-F1, generically: the declared base is a static symlink to a foreign directory."""
    foreign = os.path.join(base, "foreign-dir")
    os.makedirs(foreign)
    parent = os.path.join(base, "jobs")
    os.makedirs(parent)
    os.symlink(foreign, os.path.join(parent, "k4s-end-r1"))
    refusal("root", si.Writer, wpol(os.path.join(parent, "k4s-end-r1")), "w")
    w = si.Writer(wpol(parent), "w")                             # base as a component below a canonical root
    refusal("symlink", w.mkdir_excl, "k4s-end-r1/attempt-01")
    refusal("symlink", w.create_excl, "k4s-end-r1/wrapper.sh", b"#!/bin/sh\n")
    ok(os.listdir(foreign) == [])


def test_ancestor_symlink_root_refuses(base, out):
    os.symlink(base, os.path.join(base, "anc"))
    refusal("root", si.Writer, wpol(os.path.join(base, "anc", "out")), "w")


def test_write_name_and_allowlist_gates(out, rec):
    w = si.Writer(policy([role("w", out, access="write", patterns=("*.json",), max_size=10)]), "w")
    with rec:
        refusal("name", w.create_excl, "complete.json", b"{}")
        refusal("name", w.create_excl, "end-raw.json", b"{}")
        refusal("name", w.mkdir_excl, "games")
        refusal("name", w.mkdir_excl, "k4s-confirm-x")
        refusal("allowlist", w.create_excl, "x.txt", b"x")
        refusal("path", w.create_excl, "../x.json", b"x")
    ok(rec.calls == [], "a syscall happened before a write-name refusal")
    refusal("size", w.create_excl, "big.json", b"x" * 11)
    ok(os.path.getsize(os.path.join(out, "big.json")) == 0)     # partial (empty) kept, never unlinked


def test_missing_parent_refuses(out):
    w = si.Writer(wpol(out), "w")
    refusal("missing", w.create_excl, "nodir/x", b"x")


def test_refusal_receipts(out):
    p = policy([role("ref", out, access="write", patterns=("S7-REFUSAL-*.json",), max_size=1 << 16)])
    w = si.Writer(p, "ref")
    names = set()
    for _ in range(3):
        names.add(si.write_refusal_receipt(w, "S7", si.Refusal("nlink", "probe"), {"argv": ["x"]}))
    ok(len(names) == 3)
    for name in names:
        with open(os.path.join(out, name)) as stream:
            body = json.load(stream)
        ok(body["schema"] == si.REFUSAL_SCHEMA and body["code"] == "nlink" and body["context"] == {"argv": ["x"]})
        ok(stat.S_IMODE(os.stat(os.path.join(out, name)).st_mode) == 0o444)
    refusal("allowlist", si.write_refusal_receipt, w, "S9", si.Refusal("x", "y"))
    refusal("policy", si.write_refusal_receipt, w, "S7/../x", si.Refusal("x", "y"))
