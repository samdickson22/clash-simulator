#!/usr/bin/env python3
"""TIERS Mac session wrapper (runs ON the Mac with the session Python; launched by run_session.sh after GO).

Implements README "Exact Mac session command" with TIERS Amendment 4's no-copy staging: the bundle was staged
earlier by stage_nocopy.py, so this wrapper does NOT run prepare_bundle. Under the SAME coordinator lock file
it holds from start to finish:
  1. daemonizes (double fork + setsid) so the ~6.5 h session survives the launching ssh disconnecting; stdout and
     stderr go to an exclusive-created console log; nice 10 is inherited from the launcher;
  2. starts `/usr/bin/caffeinate -i -w <own pid>` (coordinator-approved; operational only);
  3. takes fcntl.flock(LOCK_EX|LOCK_NB) on the lock file and keeps it until exit;
  4. writes session-pre.json (exclusive): utc, uname, python, nice, caffeinate pid, environment, software-update prefs;
  5. `stage_nocopy.py --verify-bundle <bundle>` (A4 condition 5), recording its new timestamped receipt;
  6. `build_tiers.sh <runtime> <bundle> <approved manifest SHA> <fresh build dir>` (frozen; asserts the manifest SHA);
  7. `measure_tiers.py --sam-authorized-replay ... --coordinator-lock <file> --coordinator-lock-fd <fd>` with
     pass_fds, exactly as README (exit 0 = session completed, not gates passed);
  8. always writes session-post.json (exclusive, in finally, lock still held): every step and exit code, any
     wrapper exception, this invocation's --verify-bundle receipt (path, SHA, methods, file SHAs), prefs after.
No retries, no outcome access, no network to any client. Paths are fixed below; nothing outside S is written.
Usage: python -B session_wrapper.py <S> <approved tiers-pins SHA>
"""
import fcntl
import hashlib
import json
import os
import platform
import subprocess
import sys
import sysconfig
import time
from pathlib import Path

E4V3_REL = "reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3"
PREF_KEYS = ("AutomaticDownload", "AutomaticallyInstallMacOSUpdates", "ConfigDataInstall", "CriticalUpdateInstall")


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_new(path, value):
    with open(path, "x") as stream:
        json.dump(value, stream, indent=1, sort_keys=True)
        stream.write("\n")


def prefs():
    out = {}
    for key in PREF_KEYS:
        try:  # never raises: a receipt must still be written if `defaults` is unavailable
            r = subprocess.run(["defaults", "read", "/Library/Preferences/com.apple.SoftwareUpdate", key],
                               capture_output=True, text=True, timeout=30)
            out[key] = r.stdout.strip() if r.returncode == 0 else "unreadable: " + r.stderr.strip()
        except Exception as error:
            out[key] = "unreadable: " + repr(error)
    return out


def daemonize(console):
    if os.fork() > 0:
        os._exit(0)
    os.setsid()
    if os.fork() > 0:
        os._exit(0)
    fd = os.open(console, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    null = os.open("/dev/null", os.O_RDONLY)
    os.dup2(null, 0)
    os.dup2(fd, 1)
    os.dup2(fd, 2)
    os.close(null)
    os.close(fd)


def main():
    S, manifest_sha = Path(sys.argv[1]).resolve(), sys.argv[2]
    assert platform.system() == "Darwin" and platform.machine() == "arm64" and sys.version_info >= (3, 12)
    assert len(manifest_sha) == 64 and all(c in "0123456789abcdef" for c in manifest_sha)
    runtime, bundle = S / "runtime-a5", S / "staged-a5" / "bundle-a5"
    build, output = S / "build-a5", S / "session-a5-r1"
    helper = S / "helpers" / "mac-registration-e2" / "stage_nocopy.py"
    lock_path, console = S / "session.lock", S / "session-a5-r1.console.log"
    pre, post = S / "session-a5-r1.pre.json", S / "session-a5-r1.post.json"
    for path in (build, output, console, pre, post):
        if os.path.lexists(path):
            raise SystemExit("refusing: exists " + str(path))
    if hashlib.sha256((bundle / "tiers-pins.json").read_bytes()).hexdigest() != manifest_sha:
        raise SystemExit("staged bundle tiers-pins.json differs from the approved manifest SHA")
    if os.getpriority(os.PRIO_PROCESS, 0) != 10:
        raise SystemExit("launch under nice -n 10")
    daemonize(console)
    me = os.getpid()
    steps, failure, rc, verification = [], None, None, None
    caffeinate = lock = None
    try:
        caffeinate = subprocess.Popen(["/usr/bin/caffeinate", "-i", "-w", str(me)])
        lock = open(lock_path, "r+")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        e4v3 = runtime / E4V3_REL
        native = build / ("clasher_core" + sysconfig.get_config_var("EXT_SUFFIX"))
        env = dict(os.environ)
        env.update(SAM_AUTHORIZED_REPLAY="yes", PYO3_PYTHON=sys.executable, OMP_NUM_THREADS="1",
                   OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", PYTHONDONTWRITEBYTECODE="1",
                   # Coordinator ruling (a): T1's import-path-only addition, inside the qualified runtime bytes.
                   PYTHONPATH=str(runtime / "imitation/evaluation/runtime_dependencies") + ":" +
                              str(runtime / "reports/strategy_council_20260928/imitation"))
        write_new(pre, dict(schema="clasher.mac-e4-session.session-pre.v1", utc=utc(), pid=me,
            caffeinate_pid=caffeinate.pid, caffeinate_argv=["/usr/bin/caffeinate", "-i", "-w", str(me)],
            nice=os.getpriority(os.PRIO_PROCESS, 0), python=sys.executable, python_version=platform.python_version(),
            uname=list(platform.uname()), manifest_sha256=manifest_sha, bundle=str(bundle), runtime=str(runtime),
            build=str(build), output=str(output), lock=str(lock_path), lock_fd=lock.fileno(),
            environment={k: env[k] for k in ("SAM_AUTHORIZED_REPLAY", "PYO3_PYTHON", "OMP_NUM_THREADS",
                         "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "PYTHONDONTWRITEBYTECODE", "PYTHONPATH")},
            software_update_prefs_before=prefs(),
            software_update_change="none (no sudo/GUI route; coordinator dbe683e0)"))

        def run(name, argv, **kw):
            entry = dict(step=name, argv=argv, started=utc())
            steps.append(entry)
            result = subprocess.run(argv, env=env, **kw)
            entry.update(ended=utc(), returncode=result.returncode)
            return result

        # A4 condition 5: this invocation's own verification receipt (exact new file, its SHA and content).
        existing = set(bundle.parent.glob(bundle.name + ".nocopy-verify-*.json"))
        result = run("verify-bundle", [sys.executable, "-B", str(helper), "--verify-bundle", str(bundle)],
                     capture_output=True, text=True)
        rc = result.returncode
        new_receipts = sorted(set(bundle.parent.glob(bundle.name + ".nocopy-verify-*.json")) - existing)
        if rc == 0:
            if len(new_receipts) != 1:
                raise RuntimeError("expected exactly one new --verify-bundle receipt: " + repr(new_receipts))
            content = json.loads(new_receipts[0].read_text())
            if json.loads(result.stdout) != content or content.get("passes") is not True or content.get("helper_used") is not True:
                raise RuntimeError("verify-bundle stdout/receipt mismatch or not passing")
            verification = dict(path=str(new_receipts[0]), sha256=hashlib.sha256(new_receipts[0].read_bytes()).hexdigest(),
                                helper_used=content["helper_used"], helper_sha256=content["helper_sha256"],
                                tiers_pins_sha256=content["tiers_pins_sha256"], files=content["files"], utc=content["utc"])
            if content["tiers_pins_sha256"] != manifest_sha:
                raise RuntimeError("verification tiers-pins differs from the approved manifest")
        else:
            verification = dict(stdout=result.stdout[-4000:], stderr=result.stderr[-4000:])
        if rc == 0:
            rc = run("build", ["bash", str(e4v3 / "build_tiers.sh"), str(runtime), str(bundle), manifest_sha, str(build)]).returncode
        if rc == 0:
            rc = run("measure", [sys.executable, "-B", str(e4v3 / "measure_tiers.py"), "--sam-authorized-replay",
                                 "--bundle", str(bundle), "--runtime-root", str(runtime), "--native", str(native),
                                 "--manifest-sha256", manifest_sha, "--coordinator-lock", str(lock_path),
                                 "--coordinator-lock-fd", str(lock.fileno()), "--output", str(output)],
                     pass_fds=(lock.fileno(),)).returncode
    except BaseException:
        import traceback
        failure = traceback.format_exc()
        rc = 1 if rc in (None, 0) else rc
    finally:
        # Written while the lock (if taken) is still held; missing post receipt = incomplete attempt.
        try:
            write_new(post, dict(schema="clasher.mac-e4-session.session-post.v1", utc=utc(), steps=steps,
                                 final_returncode=rc, wrapper_failure=failure, nocopy_session_verification=verification,
                                 software_update_prefs_after=prefs(),
                                 caffeinate_returncode=caffeinate.poll() if caffeinate is not None else None))
        finally:
            if lock is not None:
                lock.close()
    return rc
    rc = run("verify-bundle", [sys.executable, "-B", str(helper), "--verify-bundle", str(bundle)])
    if rc == 0:
        rc = run("build", ["bash", str(e4v3 / "build_tiers.sh"), str(runtime), str(bundle), manifest_sha, str(build)])
    if rc == 0:
        rc = run("measure", [sys.executable, "-B", str(e4v3 / "measure_tiers.py"), "--sam-authorized-replay",
                             "--bundle", str(bundle), "--runtime-root", str(runtime), "--native", str(native),
                             "--manifest-sha256", manifest_sha, "--coordinator-lock", str(lock_path),
                             "--coordinator-lock-fd", str(lock.fileno()), "--output", str(output)],
                 pass_fds=(lock.fileno(),))
    verify_receipts = sorted(p.name for p in bundle.parent.glob(bundle.name + ".nocopy-verify-*.json"))
    write_new(post, dict(schema="clasher.mac-e4-session.session-post.v1", utc=utc(), steps=steps, final_returncode=rc,
                         nocopy_verify_receipts=verify_receipts, software_update_prefs_after=prefs(),
                         caffeinate_returncode=caffeinate.poll()))
    lock.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
