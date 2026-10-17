#!/usr/bin/env python3
"""05 dry-run stand-in for bsgrab: same CLI and stream format, synthetic frames. FAKE_MODE: ok | badmagic | truncate."""
import os
import struct
import sys
import time

import numpy as np

a = sys.argv[1:]
if os.environ.get('FAKE_BSGRAB_LOG'):       # every invocation (SCK-touching in the real bsgrab): tests count `info` calls
    with open(os.environ['FAKE_BSGRAB_LOG'], 'a') as _f:
        _f.write(f"{time.time():.3f} {' '.join(a[:1])}\n")
get = lambda k, d: a[a.index(k)+1] if k in a else d
if a[:1] == ['info']:                       # FAKE_BOUNDS_FILE: "w,h" (a resize test changes it mid-run)
    bw, bh = (open(os.environ['FAKE_BOUNDS_FILE']).read().strip().split(',') if os.environ.get('FAKE_BOUNDS_FILE')
              else ('540', '980'))
    print('{"window_id":1,"pid":2,"bounds":[100,50,%s,%s],"content_rect":[0,0,%s,%s],"scale":2.0}' % (bw, bh, bw, bh)); sys.exit(0)
w, h = map(int, get('--size', '540,1140').split(','))
fps, secs, nmax = int(get('--fps', '10')), float(get('--seconds', '60')), int(get('--frames', '0'))
mode = os.environ.get('FAKE_MODE', 'ok')
IMGS = []
if os.environ.get('FAKE_IMAGES'):           # cycle real screenshots (resized) instead of synthetic frames
    import cv2
    IMGS = [cv2.resize(cv2.imread(p), (w, h)) for p in os.environ['FAKE_IMAGES'].split(':')]
    IMGS = [np.dstack([i, np.full(i.shape[:2], 255, np.uint8)]) for i in IMGS]
    hold = int(os.environ.get('FAKE_HOLD', '50'))      # frames per image
crop = [float(v) for v in get('--crop', '0,0,1,1').split(',')]
if IMGS and os.environ.get('FAKE_CHROME') == '1' and crop[:2] == [0., 0.]:   # a full-window grab: BlueStacks chrome around
    k = w/crop[2]                                                                # the view (32 pt title bar + 32 pt sidebar)
    vw, vh, top = int(round((crop[2] - 32)*k)), int(round((crop[3] - 32)*k)), int(round(32*k))
    canvas = np.zeros((h, w, 4), np.uint8); canvas[..., :3] = 40; canvas[..., 3] = 255
    IMGS = [np.dstack([cv2.resize(i[..., :3], (vw, vh)), np.full((vh, vw), 255, np.uint8)]) for i in IMGS]
    IMGS = [(lambda c, i: (c.__setitem__((slice(top, top + vh), slice(0, vw)), i), c)[1])(canvas.copy(), i) for i in IMGS]
out = sys.stdout.buffer
t0, seq = time.time(), 0
while time.time()-t0 < secs and (not nmax or seq < nmax):
    if IMGS:
        img = IMGS[(seq // hold) % len(IMGS)]
    else:
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
