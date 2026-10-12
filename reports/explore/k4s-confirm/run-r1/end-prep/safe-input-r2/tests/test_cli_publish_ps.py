"""Writer.publish_excl (no-clobber tmp->final), the host-wrapper CLI, and ps field selection."""
import json
import os
import stat
import subprocess
import sys

from conftest import HOST, MODULE_PATH, make_file, ok, policy, refusal, role, si


def wpol(root, **kw):
    args = dict(access="write", patterns=("**",), max_size=1 << 20)
    args.update(kw)
    return policy([role("w", root, **args)])


def test_publish_excl(base):
    out = os.path.join(base, "job")
    os.makedirs(out)
    w = si.Writer(wpol(out), "w")
    w.create_excl("exit.json.tmp", b'{"a":1}')
    w.publish_excl("exit.json.tmp", "exit.json")
    ok(not os.path.lexists(os.path.join(out, "exit.json.tmp")))
    st = os.stat(os.path.join(out, "exit.json"))
    ok(st.st_nlink == 1 and stat.S_ISREG(st.st_mode))
    refusal("missing", w.publish_excl, "exit.json.tmp", "exit.json")


def test_publish_never_replaces(base):
    out = os.path.join(base, "job")
    os.makedirs(out)
    keep = make_file(os.path.join(base, "foreign", "keep"), b"KEEP")
    w = si.Writer(wpol(out), "w")
    for final, setup in (("a.json", lambda p: make_file(p, b"OLD")), ("b.json", lambda p: os.symlink(keep, p)),
                         ("c.json", lambda p: os.link(keep, p)), ("d.json", lambda p: os.symlink("/nonexistent", p))):
        setup(os.path.join(out, final))
        w.create_excl(final + ".tmp", b"NEW")
        refusal("exists", w.publish_excl, final + ".tmp", final)
        ok(os.path.exists(os.path.join(out, final + ".tmp")))       # the new file stays where it was
    with open(keep, "rb") as stream:
        ok(stream.read() == b"KEEP")
    with open(os.path.join(out, "a.json"), "rb") as stream:
        ok(stream.read() == b"OLD")
    ok(not os.path.exists("/nonexistent"))


def test_publish_refuses_aliased_tmp(base):
    out = os.path.join(base, "job")
    os.makedirs(out)
    w = si.Writer(wpol(out), "w")
    other = make_file(os.path.join(base, "other"), b"x")
    os.link(other, os.path.join(out, "t.tmp"))
    refusal("nlink", w.publish_excl, "t.tmp", "t.json")
    os.symlink(other, os.path.join(out, "s.tmp"))
    refusal("not-regular", w.publish_excl, "s.tmp", "s.json")
    os.mkdir(os.path.join(out, "d.tmp"))
    refusal("not-regular", w.publish_excl, "d.tmp", "d.json")
    refusal("name", w.publish_excl, "t.tmp", "complete.json")
    ok(not os.path.lexists(os.path.join(out, "t.json")) and not os.path.lexists(os.path.join(out, "s.json")))


def cli(*args, data=b""):
    proc = subprocess.run([sys.executable, "-I", "-S", MODULE_PATH] + list(args), input=data,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    return proc.returncode, proc.stdout, proc.stderr


def test_cli_create_mkdir_publish(base):
    out = os.path.join(base, "job")
    os.makedirs(out)
    rc, so, se = cli("mkdir-excl", "--host", HOST, "--root", out, "--rel", "sub")
    ok(rc == 0, se)
    rc, so, se = cli("create-excl", "--host", HOST, "--root", out, "--rel", "sub/argv.nul", "--max-size", "100",
                     data=b"a\x00b\x00")
    ok(rc == 0 and json.loads(so)["size"] == 4, se)
    ok(stat.S_IMODE(os.stat(os.path.join(out, "sub", "argv.nul")).st_mode) == 0o444)
    rc, so, se = cli("create-excl", "--host", HOST, "--root", out, "--rel", "x.tmp", "--max-size", "10",
                     "--mode", "0400", data=b"{}")
    ok(rc == 0, se)
    rc, so, se = cli("publish-excl", "--host", HOST, "--root", out, "--rel", "x.tmp", "--final", "x.json")
    ok(rc == 0 and os.path.exists(os.path.join(out, "x.json")), se)
    rc, so, se = cli("remote-program-sha256")
    ok(rc == 0 and so.decode().strip() == si.remote_program_sha256())


def test_cli_refusals(base):
    out = os.path.join(base, "job")
    os.makedirs(out)
    keep = make_file(os.path.join(base, "keep"), b"KEEP")
    os.link(keep, os.path.join(out, "argv.nul"))
    rc, so, se = cli("create-excl", "--host", HOST, "--root", out, "--rel", "argv.nul", "--max-size", "100",
                     data=b"cmd\x00")
    ok(rc == 3 and b"REFUSE exists" in se, se)
    with open(keep, "rb") as stream:
        ok(stream.read() == b"KEEP")
    os.symlink(os.path.join(base, "foreign"), os.path.join(base, "base-link"))
    os.makedirs(os.path.join(base, "foreign"))
    rc, so, se = cli("mkdir-excl", "--host", HOST, "--root", os.path.join(base, "base-link"), "--rel", "job")
    ok(rc == 3 and b"REFUSE root" in se and os.listdir(os.path.join(base, "foreign")) == [], se)
    rc, so, se = cli("create-excl", "--host", HOST, "--root", out, "--rel", "big", "--max-size", "3", data=b"1234")
    ok(rc == 3 and b"REFUSE size" in se, se)
    rc, so, se = cli("create-excl", "--host", HOST, "--root", out, "--rel", "games/x", "--max-size", "3")
    ok(rc == 3 and b"REFUSE name" in se, se)
    rc, so, se = cli("create-excl", "--host", HOST, "--root", out, "--rel", "m", "--max-size", "3", "--mode", "777")
    ok(rc == 3 and b"REFUSE policy" in se, se)
    other = "127x03" if HOST != "127x03" else "127x04"
    rc, so, se = cli("mkdir-excl", "--host", other, "--root", out, "--rel", "y")
    ok(rc == 3 and b"REFUSE policy" in se, se)
    rc, so, se = cli()
    ok(rc == 2)


def test_ps_fields(base):
    rows = si.ps_checked(fields=("pid", "ppid", "ni", "cls"))
    me = [r for r in rows if r["pid"] == os.getpid()][0]
    ok(isinstance(me["ni"], str) and isinstance(me["cls"], str) and me["ppid"] == os.getppid())
    for bad in (("ppid", "pid"), ("pid", "ppid", "pcpu"), ("pid", "ppid", "ni", "ni"), ("pid",)):
        refusal("subprocess", si.ps_checked, "/usr/bin/ps", 20, 1 << 20, bad)
    path = os.path.join(base, "ps")
    with open(path, "w") as stream:
        stream.write("#!/bin/sh\necho '%d %d 0 TS python'\necho '1 0 x TS init'\n" % (os.getpid(), os.getppid()))
    os.chmod(path, 0o755)
    refusal("subprocess", si.ps_checked, path, 20, 1 << 20, ("pid", "ppid", "ni", "cls"))
    with open(path, "w") as stream:
        stream.write("#!/bin/sh\necho '%d %d - FF python'\n" % (os.getpid(), os.getppid()))
    ok(si.ps_checked(path, 20, 1 << 20, ("pid", "ppid", "ni", "cls"))[0]["ni"] == "-")


def test_constants_fingerprint_is_pinned():
    ok(si.constants_fingerprint() == "6661ca0b7635a3a66d8ab6612b5617435f06128d6e18b6bf96e25594a624d367",
       si.constants_fingerprint())
