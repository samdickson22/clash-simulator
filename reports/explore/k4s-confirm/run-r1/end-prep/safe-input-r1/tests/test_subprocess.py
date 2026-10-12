"""run_checked and the rc-checked ps/hostname/git helpers (valid-looking stdout with rc != 0 refuses)."""
import os
import time

import pytest

from conftest import HOST, ok, refusal, si


def script(base, name, body):
    path = os.path.join(base, name)
    with open(path, "w") as stream:
        stream.write("#!/bin/sh\n" + body + "\n")
    os.chmod(path, 0o755)
    return path


def test_run_checked_ok_and_no_shell(base):
    r = si.run_checked(["/bin/echo", "$(id)", ";", "|"], 10, 1024)
    ok(r.rc == 0 and r.stdout == b"$(id) ; |\n")
    r = si.run_checked(["/bin/cat"], 10, 1024, stdin_bytes=b"fed")
    ok(r.stdout == b"fed")


def test_unread_stdin_refuses(base):
    e = refusal("subprocess", si.run_checked, ["/bin/true"], 10, 10, stdin_bytes=b"x" * (16 << 20))
    ok("stdin" in e.reason, e.reason)


def test_rc_nonzero_with_valid_stdout_refuses(base):
    fake = script(base, "fake", 'echo "OK|valid|output"; exit 37')
    e = refusal("subprocess", si.run_checked, [fake], 10, 1024)
    ok("37" in str(e))
    ok(si.run_checked([fake], 10, 1024, ok_rcs=(37,)).stdout == b"OK|valid|output\n")


def test_bounds_and_timeout(base):
    refusal("subprocess", si.run_checked, [script(base, "flood", "yes | head -c 100000")], 10, 1000)
    refusal("subprocess", si.run_checked, [script(base, "eflood", "yes >&2")], 10, 1000, stderr_limit=1000)
    start = time.time()
    refusal("subprocess", si.run_checked, [script(base, "slow", "sleep 30")], 1, 1000)
    ok(time.time() - start < 10)
    start = time.time()
    e = refusal("subprocess", si.run_checked, [script(base, "bg", "sleep 30 & echo started")], 25, 1000)
    ok("descendant" in e.reason and time.time() - start < 15, e.reason)


def test_argv_and_env_rules(base):
    refusal("subprocess", si.run_checked, ["echo", "x"], 10, 10)            # relative argv[0]
    refusal("subprocess", si.run_checked, ["/bin/../bin/echo"], 10, 10)     # not normalized
    refusal("subprocess", si.run_checked, [], 10, 10)
    refusal("subprocess", si.run_checked, "/bin/echo", 10, 10)
    refusal("subprocess", si.run_checked, ["/bin/echo"], 0, 10)
    refusal("subprocess", si.run_checked, ["/bin/echo"], 10, 0)
    refusal("subprocess", si.run_checked, [os.path.join(base, "missing")], 10, 10)
    os.environ["SAFE_INPUT_TEST_SECRET"] = "leak"
    try:
        r = si.run_checked(["/usr/bin/env"], 10, 4096, env={"A": "1"})
        ok(r.stdout == b"A=1\n")
        r = si.run_checked(["/usr/bin/env"], 10, 4096, env_allow=("SAFE_INPUT_TEST_SECRET",))
        ok(r.stdout == b"SAFE_INPUT_TEST_SECRET=leak\n")
    finally:
        del os.environ["SAFE_INPUT_TEST_SECRET"]


def ps_row(pid, ppid, args="x"):
    return "%7d %7d %7d %7d %5d %s" % (pid, ppid, pid, pid, os.getuid(), args)


def test_ps_checked(base):
    rows = si.ps_checked()                                       # real /usr/bin/ps
    ok(any(r["pid"] == os.getpid() for r in rows))
    table = "\n".join([ps_row(1, 0, "/sbin/init"), ps_row(os.getpid(), os.getppid(), "python")])
    good = script(base, "ps-good", "cat <<'EOF'\n%s\nEOF" % table)
    ok(len(si.ps_checked(good)) == 2)
    failed = script(base, "ps-37", "cat <<'EOF'\n%s\nEOF\nexit 37" % table)
    refusal("subprocess", si.ps_checked, failed)                 # the reviewer's failed-ps probe
    missing_me = script(base, "ps-short", "echo '%s'" % ps_row(1, 0))
    refusal("subprocess", si.ps_checked, missing_me)
    garbage = script(base, "ps-bad", "cat <<'EOF'\n%s\nnot a row\nEOF" % table)
    refusal("subprocess", si.ps_checked, garbage)


def test_hostname_checked(base):
    ok(si.hostname_checked(expected=HOST).split(".")[0] == HOST)
    refusal("subprocess", si.hostname_checked, script(base, "h37", "echo %s; exit 37" % HOST), HOST)
    refusal("subprocess", si.hostname_checked, script(base, "h2", "echo a; echo b"))
    refusal("subprocess", si.hostname_checked, script(base, "h0", "printf ''"))
    refusal("subprocess", si.hostname_checked, script(base, "hx", "echo other-host"), HOST)


def test_git_checked_rc(base):
    fake = script(base, "git", 'echo "100644 blob %s       3\tok.py"; exit 37' % ("a" * 40))
    refusal("subprocess", si.git_checked, base, ["ls-tree", "HEAD"], fake)
    refusal("path", si.git_checked, base + "/x/..", ["status"], fake)
    os.symlink(base, os.path.join(base, "lnk"))
    refusal("root", si.git_checked, os.path.join(base, "lnk"), ["status"], fake)
