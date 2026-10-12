"""Shared fail-closed helpers for the S1b / S3 / S9 / S10 candidates (stdlib only). CANDIDATE: Sol review.

* Reads of a named file use O_NOFOLLOW (a leaf symlink is refused, never followed), require a regular file by
  fstat of the opened descriptor, and are bounded by a size cap checked before the first byte is read.
* New local outputs must be absolute, normalized, under a permitted 05 root, with an existing parent whose
  realpath equals itself (no symlinked ancestor), and must not exist; files are created O_CREAT|O_EXCL|O_NOFOLLOW.
"""
import hashlib
import os
import stat
from pathlib import Path

# Where the candidates may create outputs on 05 (staging/records under the K4S runner; /tmp for scratch and tests).
PERMITTED_OUTPUT_ROOTS = ("/mpac/sdicks02/k4s-runner/", "/tmp/")
CHUNK = 1 << 20


class Refusal(RuntimeError):
    """Fail-closed refusal (explicit raise, never assert: holds under python -O)."""


def require(condition, message):
    if not condition:
        raise Refusal(message)


def open_regular(path, cap=None):
    """O_NOFOLLOW open; the opened object must be a regular file within the cap. Returns (fd, size)."""
    try:
        fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except OSError as error:
        raise Refusal(f"cannot open {path} without following links: {error.strerror}") from None
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or (cap is not None and info.st_size > cap):
        os.close(fd)
        raise Refusal(f"{path} is not a regular file within {cap} bytes")
    return fd, info.st_size


def read_bounded(path, cap):
    """Exactly the fstat size (<= cap) of a regular, non-symlink file; growth while reading refuses."""
    fd, size = open_regular(path, cap)
    try:
        chunks, left = [], size
        while left:
            data = os.read(fd, min(CHUNK, left))
            require(data, f"{path} shrank while reading")
            chunks.append(data)
            left -= len(data)
        require(os.read(fd, 1) == b"", f"{path} grew while reading")
    finally:
        os.close(fd)
    return b"".join(chunks)


def sha_file(path, cap=None):
    fd, size = open_regular(path, cap)
    h, left = hashlib.sha256(), size
    try:
        while left:
            data = os.read(fd, min(CHUNK, left))
            require(data, f"{path} shrank while hashing")
            h.update(data)
            left -= len(data)
        require(os.read(fd, 1) == b"", f"{path} grew while hashing")
    finally:
        os.close(fd)
    return h.hexdigest()


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def confined_new(path, label):
    """A new output path under a permitted root, with no symlinked ancestor; returns it as a Path."""
    text = str(path)
    require(os.path.isabs(text) and os.path.normpath(text) == text, f"{label} must be an absolute normal path")
    require(any(text.startswith(root) for root in PERMITTED_OUTPUT_ROOTS),
            f"{label} must be under one of {PERMITTED_OUTPUT_ROOTS}")
    parent = os.path.dirname(text)
    require(os.path.isdir(parent) and os.path.realpath(parent) == parent,
            f"{label}: parent must be an existing directory with no symlinked ancestor")
    require(not os.path.lexists(text), f"{label} must not exist: {text}")
    return Path(text)


def write_new(path, data, mode=0o444):
    """Create a NEW file (O_EXCL|O_NOFOLLOW; never overwrites, never follows), write, set mode."""
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fchmod(fd, mode)
    finally:
        os.close(fd)


def run_bounded(argv, timeout, out_limit, err_limit=1 << 20, feed=None):
    """Run argv; stdout/stderr are read up to their bounds (more kills the process and refuses); a watchdog kills
    the process at `timeout` even while `feed` (a function writing to its stdin) is blocked. Returns (rc, out, err)."""
    import signal
    import subprocess
    import threading
    # Own session/process group, so a kill reaches every descendant that could hold the pipes open.
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE if feed else subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    state = {"out": b"", "err": b"", "over": None, "timed_out": False}

    def kill():
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def drain(stream, key, limit):
        chunks, total = [], 0
        while True:
            data = stream.read1(CHUNK)
            if not data:
                break
            total += len(data)
            if total > limit:                           # keep only the bound; keep draining so no writer blocks
                if state["over"] is None:
                    state["over"] = key
                    kill()
                continue
            chunks.append(data)
        state[key] = b"".join(chunks)

    def expire():
        state["timed_out"] = True
        kill()

    readers = [threading.Thread(target=drain, args=(proc.stdout, "out", out_limit), daemon=True),
               threading.Thread(target=drain, args=(proc.stderr, "err", err_limit), daemon=True)]
    for t in readers:
        t.start()
    watchdog = threading.Timer(timeout, expire)
    watchdog.daemon = True
    watchdog.start()
    failure = None
    try:
        if feed:
            try:
                feed(proc.stdin)
            except BaseException as error:              # stop the stream; the caller refuses below
                failure = error
            finally:
                try:
                    proc.stdin.close()
                except BrokenPipeError:
                    pass
        proc.wait()
    finally:
        watchdog.cancel()
    for t in readers:
        t.join()
    err_tail = state["err"].decode(errors="replace")[-400:]
    require(not state["timed_out"], f"timed out after {timeout}s: {err_tail}")
    require(state["over"] is None, f"{state['over']} exceeds its {out_limit if state['over'] == 'out' else err_limit}-byte bound")
    if failure is not None:
        raise Refusal(f"stream aborted ({type(failure).__name__}: {failure}); rc={proc.returncode}: {err_tail}")
    return proc.returncode, state["out"], state["err"]
