#!/usr/bin/env python3
"""stdin -> stdout at most <bytes/s> (local bandwidth cap for the single-session capture stream)."""
import sys
import time

rate, chunk, sent, start = int(sys.argv[1]), 1 << 20, 0, time.monotonic()
reader, writer = sys.stdin.buffer, sys.stdout.buffer
while True:
    data = reader.read(chunk)
    if not data:
        break
    writer.write(data)
    sent += len(data)
    ahead = sent / rate - (time.monotonic() - start)
    if ahead > 0:
        time.sleep(ahead)
writer.flush()
