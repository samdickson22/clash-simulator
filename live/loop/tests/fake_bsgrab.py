#!/usr/bin/env python3
"""05 dry-run stand-in for bsgrab: same CLI and stream format, synthetic frames. FAKE_MODE: ok | badmagic | truncate."""
import os
import struct
import sys
import time

import numpy as np

a = sys.argv[1:]
get = lambda k, d: a[a.index(k)+1] if k in a else d
if a[:1] == ['info']:
    print('{"window_id":1,"pid":2,"bounds":[100,50,540,980],"content_rect":[0,0,540,980],"scale":2.0}'); sys.exit(0)
w, h = map(int, get('--size', '540,1140').split(','))
fps, secs, nmax = int(get('--fps', '10')), float(get('--seconds', '60')), int(get('--frames', '0'))
mode = os.environ.get('FAKE_MODE', 'ok')
out = sys.stdout.buffer
t0, seq = time.time(), 0
while time.time()-t0 < secs and (not nmax or seq < nmax):
    img = np.zeros((h, w, 4), np.uint8); img[..., 0] = seq % 256; img[: (seq*7) % h, :, 1] = 200
    disp = time.time_ns()-15_000_000
    magic = b'XXXX' if mode == 'badmagic' and seq == 3 else b'BSF1'
    try:
        out.write(struct.pack('<4sIIIQQ', magic, seq, w, h, disp, time.time_ns()))
        out.write(img.tobytes()[: (w*h*2 if mode == 'truncate' and seq == 5 else None)])
        out.flush()
    except BrokenPipeError:
        sys.exit(0)
    if mode == 'truncate' and seq == 5:
        sys.exit(0)
    seq += 1 if not (mode == 'gap' and seq == 4) else 2
    time.sleep(1/fps)
