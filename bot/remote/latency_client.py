#!/usr/bin/env python3
"""Mac-only bounded SSH latency probe. No driver, capture, or input integration."""
import argparse
import base64
import json
import math
import os
from pathlib import Path
import resource
import selectors
import signal
import subprocess
import sys
import time

from probe_process import SupervisedProcess

ROOT = Path("/tmp/bot-remote-probe")
REALISTIC_BYTES = 47281  # payload_size.json: s76/m01, measured on 127x05
REMOTE = "/mpac/sdicks02/jobs/clasher/bot-remote-probe/latency_responder.py"
STDERR_LIMIT = 64 * 1024


class Halt(Exception):
    pass


def confined(value):
    path = Path(value).absolute()
    if ROOT.is_symlink() or ROOT.resolve() not in path.resolve().parents:
        raise ValueError("paths must resolve beneath /tmp/bot-remote-probe/")
    return path


def ssh_command(host, seconds, requests):
    if host not in ("127x08", "127x04"):
        raise ValueError("responder must be 127x08 or 127x04")
    return ["ssh", "-T", "-o", "ControlMaster=no", "-o", "ControlPath=none",
            "-o", "ControlPersist=no", "-o", "ServerAliveInterval=5",
            "-o", "ServerAliveCountMax=1", "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=yes", "-o", "UpdateHostKeys=no",
            "-o", "PermitLocalCommand=no", "-o", "Compression=no",
            "-o", "ClearAllForwardings=yes", "-o", "ForwardAgent=no",
            "-o", "ForwardX11=no", "-o", "Tunnel=no",
            "-o", "ConnectTimeout=5", host,
            f"python3 {REMOTE} --max-seconds {seconds:g} --max-requests {requests}"]


def request_line(size, sequence, padding):
    # Random base64 ASCII avoids JSON escaping; total wire size INCLUDES NDJSON LF.
    prefix = ('{"id":"%08d","padding":"' % sequence).encode()
    needed = size - len(prefix) - 3
    if needed < 0:
        raise ValueError("payload too small")
    return prefix + padding[:needed] + b'"}\n'


def percentiles(values):
    ordered = sorted(values)
    result = {f"p{p}": ordered[math.ceil(p / 100 * len(ordered)) - 1] if ordered else None
              for p in (50, 90, 95, 99)}
    result["max"] = max(ordered) if ordered else None
    return result


def reap(process, grace=.05):
    """Only touch a Popen child owned by this invocation."""
    if isinstance(process, SupervisedProcess):
        return process.finish()
    if process.poll() is None:
        process.terminate()
    try:
        return process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        process.kill()
        return process.wait(timeout=.05)


class BoundedStderr:
    """Shared, nonblocking cap for SSH, sampler and guardian diagnostics."""
    def __init__(self):
        self.selector = selectors.DefaultSelector()
        self.streams = []
        self.buffer = bytearray()
        self.bytes_seen = 0
        self.exceeded = False

    def add(self, stream):
        os.set_blocking(stream.fileno(), False)
        self.streams.append(stream)
        self.selector.register(stream, selectors.EVENT_READ)

    def drain(self, abort=True):
        # At most cap+1 bytes are consumed after overflow; unread pipe data is
        # discarded when children exit. RAM and the eventual file stay <=64KiB.
        while not self.exceeded:
            events = self.selector.select(0)
            if not events:
                break
            for key, _ in events:
                try:
                    chunk = os.read(key.fd, min(4096, STDERR_LIMIT + 1 - self.bytes_seen))
                except BlockingIOError:
                    continue
                if not chunk:
                    self.selector.unregister(key.fileobj)
                    continue
                self.bytes_seen += len(chunk)
                self.buffer.extend(chunk[:STDERR_LIMIT - len(self.buffer)])
                if self.bytes_seen > STDERR_LIMIT:
                    self.exceeded = True
                    break
        if abort and self.exceeded:
            raise RuntimeError("stderr byte limit exceeded (65536 bytes)")

    def close(self):
        self.selector.close()
        for stream in self.streams:
            stream.close()


class Session:
    def __init__(self, process, check):
        self.process, self.check = process, check
        self.selector = selectors.DefaultSelector()
        os.set_blocking(process.stdin.fileno(), False)
        os.set_blocking(process.stdout.fileno(), False)
        self.buffer = bytearray()

    def ready(self, stream, event, deadline):
        self.selector.register(stream, event)
        try:
            while True:
                self.check()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("request deadline exceeded")
                if self.selector.select(min(.05, remaining)):
                    return
        finally:
            self.selector.unregister(stream)

    def exchange(self, line, timeout):
        started = time.monotonic_ns()
        deadline = time.monotonic() + timeout
        pending = memoryview(line)
        while pending:
            self.ready(self.process.stdin, selectors.EVENT_WRITE, deadline)
            try:
                pending = pending[os.write(self.process.stdin.fileno(), pending):]
            except BlockingIOError:
                continue
        while b"\n" not in self.buffer:
            self.ready(self.process.stdout, selectors.EVENT_READ, deadline)
            try:
                chunk = os.read(self.process.stdout.fileno(), 4096)
            except BlockingIOError:
                continue
            if not chunk:
                raise RuntimeError("responder EOF")
            self.buffer.extend(chunk)
            if len(self.buffer) > 4096:
                raise ValueError("oversized response")
        ended = time.monotonic_ns()
        raw, _, rest = self.buffer.partition(b"\n")
        self.buffer = bytearray(rest)
        response = json.loads(raw)
        request_id = json.loads(line)["id"]
        if (not isinstance(response, dict) or response.get("id") != request_id or not isinstance(response.get("action"), dict)
                or not isinstance(response.get("server_receive_ns"), int)
                or not isinstance(response.get("server_send_ns"), int)
                or response["server_send_ns"] < response["server_receive_ns"]):
            raise ValueError("invalid response or request ID mismatch")
        return {"rtt_ms": (ended - started) / 1e6, "response_bytes": len(raw) + 1,
                "server_service_ms": (response["server_send_ns"] - response["server_receive_ns"]) / 1e6}

    def close(self):
        self.selector.close()
        self.process.stdin.close()
        self.process.stdout.close()


def run_probe(command, sizes, count, hz, seconds, timeout, stop_file, stderr, stop_signal=lambda: False,
              diagnostics=None):
    """Internal command injection is for local subprocess tests; CLI always uses SSH."""
    started = time.monotonic()
    cpu = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = {"reconnect_count": 0, "ssh_sessions_started": 0, "timeouts": 0,
              "reason": "complete", "payloads": [], "warmup": None}
    interval, deadline = 1 / hz, started + seconds
    padding = base64.b64encode(os.urandom(max(sizes)))
    process = session = None
    own_diagnostics = diagnostics is None
    diagnostics = diagnostics or BoundedStderr()

    def check():
        diagnostics.drain()
        if stop_signal() or stop_file.exists():
            raise Halt("stop")
        if time.monotonic() >= deadline:
            raise Halt("max_seconds")

    def sleep_until(due):
        while time.monotonic() < due:
            check()
            time.sleep(min(.05, max(0, due - time.monotonic())))
        check()

    try:
        check()  # Existing STOP means no SSH process is launched.
        process = SupervisedProcess(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, bufsize=0)
        diagnostics.add(process.stderr)
        result["ssh_sessions_started"] = 1
        session = Session(process, check)
        # First exchange includes SSH setup and is reported separately, never hidden.
        result["warmup"] = session.exchange(request_line(sizes[0], 0, padding), max(timeout, 10))
        sequence, due = 1, time.monotonic() + interval
        for size in sizes:
            group = {"request_bytes": size, "requested_count": count, "count": 0,
                     "attempted_count": 0, "timeouts": 0, "samples": [], "skipped_slots": 0}
            result["payloads"].append(group)
            for _ in range(count):
                sleep_until(due)
                line = request_line(size, sequence, padding)
                group["attempted_count"] += 1
                try:
                    sample = session.exchange(line, timeout)
                except TimeoutError:
                    group["timeouts"] += 1
                    raise
                sample["id"] = f"{sequence:08d}"
                group["samples"].append(sample)
                group["count"] += 1
                sequence += 1
                due += interval
                # Never burst to catch up after a slow response.
                if due < time.monotonic():
                    skipped = math.ceil((time.monotonic() - due) / interval)
                    group["skipped_slots"] += skipped
                    due += skipped * interval
    except Halt as exc:
        result["reason"] = str(exc)
    except TimeoutError as exc:
        result.update(reason="timeout", error=str(exc), timeouts=1)
    except (OSError, ValueError, RuntimeError) as exc:
        result.update(reason="error", error=str(exc))
    finally:
        if process is not None:
            # EOF lets the responder exit; no remote kill command or orphan daemon.
            process.stdin.close()
            try:
                result["ssh_returncode"] = process.wait(timeout=.05)
            except subprocess.TimeoutExpired:
                result["ssh_returncode"] = reap(process)
            finally:
                process.stop()
        if session is not None:
            session.close()
        diagnostics.drain(abort=False)
        if diagnostics.exceeded:
            result.update(reason="error", error="stderr byte limit exceeded (65536 bytes)")
        result.update(stderr_bytes_captured=len(diagnostics.buffer), stderr_limit_exceeded=diagnostics.exceeded)
        if own_diagnostics:
            if hasattr(stderr, "write"):
                stderr.write(bytes(diagnostics.buffer))
            diagnostics.close()
    elapsed = time.monotonic() - started
    end_cpu = resource.getrusage(resource.RUSAGE_SELF)
    end_children = resource.getrusage(resource.RUSAGE_CHILDREN)
    used = end_cpu.ru_utime + end_cpu.ru_stime - cpu.ru_utime - cpu.ru_stime
    child_used = end_children.ru_utime + end_children.ru_stime - children.ru_utime - children.ru_stime
    result.update(elapsed_s=elapsed, client_cpu_seconds=used,
                  client_cpu_percent_one_core=100 * used / elapsed,
                  child_cpu_percent_one_core=100 * child_used / elapsed)
    for group in result["payloads"]:
        group["rtt_ms"] = percentiles([sample["rtt_ms"] for sample in group["samples"]])
    if result["reason"] == "complete" and result.get("ssh_returncode") != 0:
        result.update(reason="error", error="SSH/responder did not exit cleanly")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("127x08", "127x04"), default="127x08")
    parser.add_argument("--payload", choices=("all", "realistic", "5kb", "50kb"), default="all")
    parser.add_argument("--realistic-bytes", type=int, default=REALISTIC_BYTES)
    parser.add_argument("--count", type=int, default=150, help="measured requests per payload (default 150)")
    parser.add_argument("--hz", type=float, default=2)
    parser.add_argument("--max-seconds", type=float, default=600)
    parser.add_argument("--timeout-seconds", type=float, default=2)
    parser.add_argument("--stop-file", default=str(ROOT / "STOP"))
    parser.add_argument("--output", default=str(ROOT / "summary.json"))
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("production client is Mac-only; use unittest for local loopback")
    if (not 1 <= args.count <= 300 or not 0 < args.hz <= 2
            or not 0 < args.max_seconds <= 600 or not 0 < args.timeout_seconds <= 10
            or not 64 <= args.realistic_bytes <= 1024 * 1024):
        parser.error("limits: count 1..300, hz (0,2], seconds (0,600], timeout (0,10], bytes 64..1MiB")
    try:
        output, stop = confined(args.output), confined(args.stop_file)
    except ValueError as exc:
        parser.error(str(exc))
    sizes = {"realistic": args.realistic_bytes, "5kb": 5 * 1024, "50kb": 50 * 1024}
    selected = list(sizes.values()) if args.payload == "all" else [sizes[args.payload]]
    output.parent.mkdir(parents=True, exist_ok=True)
    stderr_path = output.with_suffix(".ssh-stderr.txt")
    sampler_output = output.with_suffix(".tailscaled.json")
    for path in (output, stderr_path, sampler_output):
        confined(path)
        if path.exists():
            parser.error(f"refusing to overwrite {path}")
    sampler_path = Path(__file__).with_name("tailscaled_sampler.py")
    if not sampler_path.is_file():
        parser.error("copy tailscaled_sampler.py alongside client before running")
    os.nice(max(0, 10 - os.nice(0)))
    cpu_started = resource.getrusage(resource.RUSAGE_SELF)
    child_cpu_started = resource.getrusage(resource.RUSAGE_CHILDREN)
    run_started = time.monotonic()
    interrupted = False

    def halt(_signum, _frame):
        nonlocal interrupted
        interrupted = True

    signal.signal(signal.SIGTERM, halt)
    signal.signal(signal.SIGINT, halt)
    signal.signal(signal.SIGHUP, halt)
    sampler = None
    diagnostics = BoundedStderr()
    with stderr_path.open("xb") as stderr:
        try:
            if not stop.exists():
                sampler = SupervisedProcess([sys.executable, "-B", str(sampler_path), "--label", "during",
                                            "--output", str(sampler_output), "--stop-file", str(stop),
                                            "--max-seconds", str(args.max_seconds)], grace=.3,
                                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                diagnostics.add(sampler.stderr)
            result = run_probe(ssh_command(args.host, args.max_seconds, args.count * len(selected) + 1),
                               selected, args.count, args.hz, args.max_seconds, args.timeout_seconds,
                               stop, stderr, lambda: interrupted, diagnostics=diagnostics)
        finally:
            if sampler is not None:
                result_sampler_rc = reap(sampler, grace=.3)
            diagnostics.drain(abort=False)
            stderr.write(bytes(diagnostics.buffer))
            diagnostics.close()
    result.update(stderr_bytes_captured=len(diagnostics.buffer), stderr_limit_exceeded=diagnostics.exceeded)
    if diagnostics.exceeded:
        result.update(reason="error", error="stderr byte limit exceeded (65536 bytes)")
    result.update(host=args.host, hz=args.hz, payload_label="proxy: per-frame perception row + 30 s play history",
                  sampler_output=str(sampler_output), stop_file=str(stop),
                  utc_finished=subprocess.check_output(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], text=True).strip())
    if sampler_output.exists():
        result["tailscaled"] = json.loads(sampler_output.read_text())
    result["sampler_ok"] = (sampler is not None and result_sampler_rc == 0
                            and bool(result.get("tailscaled", {}).get("samples"))
                            and not result.get("tailscaled", {}).get("errors"))
    cpu_ended = resource.getrusage(resource.RUSAGE_SELF)
    child_cpu_ended = resource.getrusage(resource.RUSAGE_CHILDREN)
    elapsed = time.monotonic() - run_started
    own_seconds = cpu_ended.ru_utime + cpu_ended.ru_stime - cpu_started.ru_utime - cpu_started.ru_stime
    child_seconds = (child_cpu_ended.ru_utime + child_cpu_ended.ru_stime
                     - child_cpu_started.ru_utime - child_cpu_started.ru_stime)
    result.update(client_cpu_seconds=own_seconds, cpu_measurement_elapsed_s=elapsed,
                  client_cpu_percent_one_core=100 * own_seconds / elapsed,
                  child_cpu_percent_one_core=100 * child_seconds / elapsed,
                  total_local_cpu_percent_one_core=100 * (own_seconds + child_seconds) / elapsed,
                  cpu_scope="client self; waited children include SSH, sampler and its ps/pgrep children")
    result["stable_session"] = result["reason"] == "complete" and result["reconnect_count"] == 0
    with output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"summary": str(output), "reason": result["reason"]}), flush=True)
    rc = 0 if result["reason"] == "complete" and result["sampler_ok"] else 1
    print(f"__RC={rc}", flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
