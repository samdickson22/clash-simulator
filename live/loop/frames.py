"""Reader for bsgrab's frame stream (live/loop/mac/bsgrab.swift).

Per frame: a 32-byte little-endian header 'BSF1' | u32 seq | u32 width | u32 height | u64 display_unix_ns |
u64 emit_unix_ns, then width*height*4 bytes BGRA. `Grabber` spawns bsgrab and yields Frame tuples with the receive time.
"""
import struct
import subprocess
import time
from collections import namedtuple

import numpy as np

HDR = struct.Struct('<4sIIIQQ')
Frame = namedtuple('Frame', 'seq bgr display_ns emit_ns recv_ns')
MAX_SIDE = 4096


def read_exact(f, n):
    buf = bytearray(n); view = memoryview(buf); got = 0
    while got < n:
        k = f.readinto(view[got:])
        if not k:
            return None
        got += k
    return buf


def read_frames(f):
    """Yield Frames from a binary stream until EOF. A malformed header raises ValueError."""
    while True:
        h = read_exact(f, HDR.size)
        if h is None:
            return
        magic, seq, w, hgt, disp, emit = HDR.unpack(h)
        if magic != b'BSF1' or not (0 < w <= MAX_SIDE and 0 < hgt <= MAX_SIDE):
            raise ValueError(f'bad frame header {bytes(h)!r}')
        body = read_exact(f, w*hgt*4)
        if body is None:
            return
        recv = time.time_ns()
        bgra = np.frombuffer(body, np.uint8).reshape(hgt, w, 4)
        yield Frame(seq, np.ascontiguousarray(bgra[:, :, :3]), disp, emit, recv)


class Grabber:
    """bsgrab stream as a child process; iterate for Frames; close() ends it (TERM, then KILL) and returns its rc."""
    def __init__(self, bsgrab, crop, size, fps=10, seconds=60, frames=0, stderr=None):
        cmd = [bsgrab, 'stream', '--crop', ','.join(map(str, crop)), '--size', ','.join(map(str, size)),
               '--fps', str(fps), '--seconds', str(seconds), '--frames', str(frames)]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=stderr, bufsize=0)

    def __iter__(self):
        return read_frames(self.proc.stdout)

    def close(self):
        p = self.proc
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(3)
            except subprocess.TimeoutExpired:
                p.kill(); p.wait()
        p.stdout.close()
        return p.returncode
