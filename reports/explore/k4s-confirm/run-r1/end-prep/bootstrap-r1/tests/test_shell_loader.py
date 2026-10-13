"""bootstrap-r1: the shell-wrapper form, as real processes. `python3 -I -S -c "$k4s_loader" PATH SHA SIZE -- ARGS`
and the canonical bash fragment, on every interpreter (fleet 3.8 and 3.12), normal and -O. Zero canary consumption is
judged by the kernel (atime held through an O_PATH descriptor) and by execution markers, since no recorder can be
installed inside a real `-c` process (the in-process recorder form is covered by test_kit_selftest.py, mode loader).
Also: argv/stdin/exit-code pass-through, verify-only executes nothing, sha256sum is never invoked, the wrapper's
exclusive metadata creation keeps its semantics, and the real S6 r2 host tool runs as __main__ under the loader."""
import hashlib
import os
import subprocess
import sys

import pytest

from conftest import END_PREP, LOADER_FILE, PYTHONS, SHELL_FILE, ok
from k4s_bootstrap_kit import Entrypoint, SCENARIOS, build, OUTCOME_DIR_NAMES


def read(path):
    with open(path, "rb") as handle:
        return handle.read()


LOADER = read(LOADER_FILE).decode()
MODES = [(py, opt) for py in PYTHONS for opt in (False, True)]
MODE_IDS = ["%s%s" % (os.path.basename(py) + ("38" if py == "/usr/bin/python3" else ""), "-O" if opt else "")
            for py, opt in MODES]

TOOL = (b"import os, sys\n"
        b"if __name__ != \"__main__\":\n    raise SystemExit(\"not main\")\n"
        b"if sys.argv[1:2] == [\"create\"]:\n"
        b"    data = sys.stdin.buffer.read()\n"
        b"    try:\n"
        b"        fd = os.open(sys.argv[2], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)\n"
        b"    except OSError as error:\n"
        b"        sys.stderr.write(\"REFUSE exists: %s\\n\" % error.strerror)\n"
        b"        raise SystemExit(3)\n"
        b"    os.write(fd, data)\n    os.close(fd)\n    print(\"CREATED\", len(data))\n    raise SystemExit(0)\n"
        b"print(\"ARGV\", sys.argv)\nprint(\"FILE\", __file__)\nprint(\"STDIN\", sys.stdin.read())\n"
        b"raise SystemExit(int(os.environ.get(\"TOOL_RC\", \"0\")))\n"
        + b"# padding so that a canary of the same size fits\n" * 20)
TOOL_SHA, TOOL_SIZE = hashlib.sha256(TOOL).hexdigest(), len(TOOL)
EP = Entrypoint("tool", {"tool.py": TOOL}, "tool.py", "tool.py", TOOL_SHA, TOOL_SIZE, mode="loader",
                loader_file=LOADER_FILE)


def loader_argv(py, opt, path, sha=TOOL_SHA, size=TOOL_SIZE, tail=("--",), flags=("-I", "-S")):
    return [py] + (["-O"] if opt else []) + list(flags) + ["-c", LOADER, path, sha, str(size)] + list(tail)


def run(argv, **kw):
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    kw.setdefault("timeout", 60)
    return subprocess.run(argv, **kw)


def fragment_script(body):
    return "set -u\npython=$1; host_tool=$2; host_tool_sha=$3; host_tool_size=$4\n" + read(SHELL_FILE).decode() + body


def bash(py, path, body, sha=TOOL_SHA, size=TOOL_SIZE, **kw):
    return run(["/bin/bash", "-c", fragment_script(body), "_", py, path, sha, str(size)], **kw)


def put(path, data):
    with open(path, "wb") as handle:
        handle.write(data)
    return path


def held(paths):
    out = {}
    for label, path in paths.items():
        st = os.stat(path, follow_symlinks=False)
        if not (st.st_mode & 0o170000) == 0o100000:
            continue
        os.utime(path, ns=(0, st.st_mtime_ns), follow_symlinks=False)
        out[label] = os.open(path, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC)
    return out


def released(handles):
    moved = {label: os.fstat(fd).st_atime_ns != 0 for label, fd in handles.items()}
    for fd in handles.values():
        os.close(fd)
    return moved


# ---------------------------------------------------------------- every kit scenario, real -c process

SCENARIO_NAMES = [s for s in SCENARIOS if s != "swap-ok"] + ["outcome-named-ancestor:" + n for n in OUTCOME_DIR_NAMES]


@pytest.mark.parametrize("mode", MODES, ids=MODE_IDS)
@pytest.mark.parametrize("scenario", SCENARIO_NAMES)
def test_real_loader_process_meets_every_scenario(tmp_path, mode, scenario):
    py, opt = mode
    root = str(tmp_path / "s")
    os.makedirs(root)
    sc = build(EP, scenario, root)
    handles = held(sc.watch)
    done = run(loader_argv(py, opt, sc.layer_path, tail=("--", "x", "y z")), stdin=subprocess.DEVNULL)
    moved = released(handles)
    ok(not os.listdir(root + "/markers"), "canary executed")
    if sc.expect == "ok":
        ok(done.returncode == 0 and "ARGV ['%s', 'x', 'y z']" % sc.layer_path in done.stdout, done.stdout + done.stderr)
        ok(moved.get("layer") is True, "atime instrument did not see the control read")
        return
    ok(done.returncode == 90 and done.stderr.startswith("k4s bootstrap refused: ") and "ARGV" not in done.stdout,
       (done.returncode, done.stdout, done.stderr))
    ok(done.stderr.count("\n") == 1, "one refusal line, no traceback: " + done.stderr)
    if sc.expect == "refuse-unread":
        ok(moved.get("canary", False) is False, "kernel atime shows the canary was read")
    else:                                                          # same-size mismatch: read, hashed, never run
        ok(sc.expect == "refuse-after-hash" and "SHA-256" in done.stderr, done.stderr)


@pytest.mark.parametrize("mode", MODES, ids=MODE_IDS)
@pytest.mark.parametrize("scenario", ["control", "ancestor-symlink", "hard-link-pinned-bytes", "same-size-mismatch",
                                      "fifo-leaf", "outcome-named-ancestor:games", "non-normalized-dotdot-alias"])
def test_bash_fragment_verify_step_meets_the_scenarios(tmp_path, mode, scenario):
    py, opt = mode
    if opt:
        py_cmd = str(tmp_path / "py-O")
        put(py_cmd, ("#!/bin/sh\nexec %s -O \"$@\"\n" % py).encode())
        os.chmod(py_cmd, 0o755)
    else:
        py_cmd = py
    root = str(tmp_path / "s")
    os.makedirs(root)
    sc = build(EP, scenario, root)
    handles = held(sc.watch)
    done = bash(py_cmd, sc.layer_path, "echo VERIFIED\ntool p q\necho TOOL_RC=$?\n", stdin=subprocess.DEVNULL)
    moved = released(handles)
    ok(not os.listdir(root + "/markers"))
    if sc.expect == "ok":
        ok(done.returncode == 0 and "VERIFIED" in done.stdout and "TOOL_RC=0" in done.stdout, done.stdout + done.stderr)
    else:
        ok(done.returncode == 90 and "VERIFIED" not in done.stdout and "k4s bootstrap refused" in done.stderr,
           (done.returncode, done.stdout, done.stderr))
        if sc.expect == "refuse-unread":
            ok(moved.get("canary", False) is False)


# ---------------------------------------------------------------- pass-through semantics

@pytest.fixture
def tool(tmp_path):
    d = tmp_path / "tools"
    d.mkdir()
    return put(str(d / "tool.py"), TOOL)


@pytest.mark.parametrize("mode", MODES, ids=MODE_IDS)
def test_argv_stdin_and_exit_code_pass_through(tool, mode):
    py, opt = mode
    done = run(loader_argv(py, opt, tool, tail=("--", "--out", "", "a b", "-c")), input="piped-bytes",
               env=dict(os.environ, TOOL_RC="7"))
    ok(done.returncode == 7, done.stderr)
    ok("ARGV ['%s', '--out', '', 'a b', '-c']" % tool in done.stdout and "FILE %s" % tool in done.stdout)
    ok("STDIN piped-bytes" in done.stdout, done.stdout)


@pytest.mark.parametrize("mode", MODES, ids=MODE_IDS)
def test_verify_only_executes_nothing_and_leaves_stdin_unread(tool, tmp_path, mode):
    py, opt = mode
    stdin_file = put(str(tmp_path / "stdin.bin"), b"must-stay-unread")
    before = sorted(os.listdir(str(tmp_path)))
    with open(stdin_file, "rb") as handle:
        done = run(loader_argv(py, opt, tool, tail=("--verify-only",)), stdin=handle)
        offset = os.lseek(handle.fileno(), 0, os.SEEK_CUR)
    ok(done.returncode == 0 and done.stdout == "" and done.stderr == "", (done.returncode, done.stdout, done.stderr))
    ok(offset == 0, "the loader consumed stdin")
    ok(sorted(os.listdir(str(tmp_path))) == before, "the loader created a file")


@pytest.mark.parametrize("mode", MODES, ids=MODE_IDS)
@pytest.mark.parametrize("bad", ["no-dashdash", "verify-extra", "size-zero", "size-word", "size-lead-zero", "too-few",
                                 "sha-upper", "relative"])
def test_loader_usage_refusals(tool, mode, bad):
    py, opt = mode
    argv = {"no-dashdash": loader_argv(py, opt, tool, tail=("x",)),
            "verify-extra": loader_argv(py, opt, tool, tail=("--verify-only", "x")),
            "size-zero": loader_argv(py, opt, tool, size=0), "size-word": loader_argv(py, opt, tool, size="ten"),
            "size-lead-zero": loader_argv(py, opt, tool, size="0%d" % TOOL_SIZE),
            "too-few": loader_argv(py, opt, tool, tail=())[:-1],
            "sha-upper": loader_argv(py, opt, tool, sha=TOOL_SHA.upper()),
            "relative": loader_argv(py, opt, os.path.relpath(tool, "/"))}[bad]
    done = run(argv, stdin=subprocess.DEVNULL, cwd="/")
    ok(done.returncode == 90 and done.stderr.startswith("k4s bootstrap refused") and "ARGV" not in done.stdout,
       (done.returncode, done.stdout, done.stderr))


@pytest.mark.parametrize("mode", MODES, ids=MODE_IDS)
@pytest.mark.parametrize("flags", [("-I",), ("-S",), ()])
def test_loader_refuses_without_isolated_no_site(tool, mode, flags):
    py, opt = mode
    done = run(loader_argv(py, opt, tool, flags=flags), stdin=subprocess.DEVNULL)
    ok(done.returncode == 90 and "must run under python3 -I -S" in done.stderr and "ARGV" not in done.stdout,
       done.stderr)


def test_sha256sum_is_never_invoked(tool, tmp_path):
    shims = tmp_path / "shims"
    shims.mkdir()
    log = tmp_path / "sha256sum.log"
    put(str(shims / "sha256sum"), ("#!/bin/sh\necho called >> %s\nexit 0\n" % log).encode())
    os.chmod(str(shims / "sha256sum"), 0o755)
    env = dict(os.environ, PATH=str(shims) + ":" + os.environ.get("PATH", "/usr/bin:/bin"))
    for py in PYTHONS:
        good = bash(py, tool, "tool\n", env=env, stdin=subprocess.DEVNULL)
        bad = bash(py, tool, "tool\n", sha="0" * 64, env=env, stdin=subprocess.DEVNULL)
        ok(good.returncode == 0 and bad.returncode == 90, (good.stderr, bad.stderr))
    ok(not log.exists(), "sha256sum was invoked")


# ---------------------------------------------------------------- the wrapper's exclusive metadata creation

@pytest.mark.parametrize("py", PYTHONS)
def test_exclusive_metadata_creation_is_preserved(tool, tmp_path, py):
    """`printf ... | tool <create-excl> ...` keeps its meaning: the piped bytes reach the tool, an existing name or a
    planted symlink refuses with the tool's own status, nothing is truncated or followed, and the loader itself
    creates nothing."""
    job = tmp_path / "job"
    job.mkdir()
    victim = put(str(tmp_path / "victim"), b"keep")
    os.symlink(victim, str(job / "planted"))
    body = ("receipt=$(printf 'a\\0b\\0' | tool create \"$5/argv.nul\") || exit 91\necho \"$receipt\"\n"
            "printf 'again' | tool create \"$5/argv.nul\"; echo SECOND=$?\n"
            "printf 'evil' | tool create \"$5/planted\"; echo PLANTED=$?\n")
    done = run(["/bin/bash", "-c", fragment_script(body), "_", py, tool, TOOL_SHA, str(TOOL_SIZE), str(job)])
    ok(done.returncode == 0 and "CREATED 4" in done.stdout and "SECOND=3" in done.stdout and "PLANTED=3" in done.stdout,
       done.stdout + done.stderr)
    ok(read(str(job / "argv.nul")) == b"a\0b\0" and read(victim) == b"keep")
    ok(sorted(os.listdir(str(job))) == ["argv.nul", "planted"])


def test_a_mid_run_tool_change_refuses_with_status_90(tool):
    """Every tool() call re-verifies; if the tool changed after the initial verify, the call refuses (status 90) and
    the changed bytes never run. Wrappers that record a tool's exit status must treat 90 as a bootstrap refusal."""
    body = "printf 'raise SystemExit(5)\\n' > \"$2.new\"\nmv \"$2.new\" \"$2\"\ntool x; echo RC=$?\n"
    done = bash("/usr/bin/python3", tool, body, stdin=subprocess.DEVNULL)
    ok(done.returncode == 0 and "RC=90" in done.stdout and "pinned size" in done.stderr, done.stdout + done.stderr)


S6_R2 = END_PREP + "/s5s6s7-r2"


@pytest.mark.parametrize("py", PYTHONS)
def test_real_s6_r2_host_tool_runs_as_main_under_the_loader(tmp_path, py):
    """The unchanged r2 host tool (copied to scratch with its vendored layer) runs under the loader: it loads its own
    safe_input from the sibling path the loader gave it as __file__, parses argv, and reaches its live host gate
    (os.uname; 127x05 is not an END host), refusing with its own convention (exit 3, REFUSE host)."""
    if not os.path.exists(S6_R2 + "/k4s_end_host_tool.py"):
        pytest.skip("s5s6s7-r2 not present")
    tools = tmp_path / "tools"
    tools.mkdir()
    for name in ("k4s_end_host_tool.py", "safe_input.py"):
        put(str(tools / name), read(S6_R2 + "/" + name))
    host_tool = str(tools / "k4s_end_host_tool.py")
    data = read(host_tool)
    ok(hashlib.sha256(data).hexdigest() == "cf19269071d57f0d1fe9b7ce5f865b4641ecda62c88e418cd73b711a57a5d6f3")
    done = run(loader_argv(py, False, host_tool, sha=hashlib.sha256(data).hexdigest(), size=len(data),
                           tail=("--", "si", "--", "create-excl", "--host", "127x03", "--root", str(tmp_path),
                                 "--rel", "argv.nul", "--max-size", "65536")), input="x")
    ok(done.returncode == 3 and "REFUSE host" in done.stderr, (done.returncode, done.stderr))
    usage = run(loader_argv(py, False, host_tool, sha=hashlib.sha256(data).hexdigest(), size=len(data)))
    ok(usage.returncode == 2 and "K4S END host-side helpers" in usage.stderr, usage.stderr)
    ok(not (tmp_path / "argv.nul").exists())
