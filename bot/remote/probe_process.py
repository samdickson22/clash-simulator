#!/usr/bin/env python3
"""Pipe-owned subprocess guardian. No sockets, threads or persistent service."""
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys


class SupervisedProcess:
    def __init__(self, command, grace=.05, **kwargs):
        read_fd, self.lifetime_fd = os.pipe()
        try:
            self.process = subprocess.Popen(
                [sys.executable, "-B", str(Path(__file__).resolve()),
                 str(read_fd), str(grace), *command], pass_fds=(read_fd,), **kwargs)
        except BaseException:
            os.close(self.lifetime_fd)
            raise
        finally:
            os.close(read_fd)
        self.grace = grace
        self.stdin, self.stdout, self.stderr = self.process.stdin, self.process.stdout, self.process.stderr

    def poll(self):
        return self.process.poll()

    @property
    def returncode(self):
        return self.process.returncode

    def wait(self, timeout=None):
        return self.process.wait(timeout=timeout)

    def stop(self):
        if self.lifetime_fd is not None:
            os.close(self.lifetime_fd)
            self.lifetime_fd = None

    def finish(self):
        self.stop()
        # Guardian handles TERM/KILL and reaps its own child before exiting.
        return self.wait(timeout=self.grace + .2)


def guardian(read_fd, grace, command):
    stopped = False

    def halt(_signum, _frame):
        nonlocal stopped
        stopped = True

    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(signum, halt)
    process = None
    with selectors.DefaultSelector() as selector:
        selector.register(read_fd, selectors.EVENT_READ)
        try:
            # The writer exists only in the invoking parent (never inherited by
            # siblings or the command). EOF detects SIGKILL as well as close().
            if stopped or selector.select(0):
                return 1
            process = subprocess.Popen(command)
            while not stopped and process.poll() is None:
                if selector.select(.025) and not os.read(read_fd, 1):
                    stopped = True
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=grace)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=.05)
            rc = process.wait()
            return rc if rc >= 0 else 128 - rc
        finally:
            os.close(read_fd)
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=.05)


if __name__ == "__main__":
    sys.exit(guardian(int(sys.argv[1]), float(sys.argv[2]), sys.argv[3:]))
