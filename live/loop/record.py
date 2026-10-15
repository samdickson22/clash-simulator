"""Record the BlueStacks viewport via bsgrab: JPEG frames + frames.jsonl (timestamps) + summary.json.

  python -I record.py --bsgrab BIN --crop x,y,w,h --size 540,1140 --fps 10 --seconds 240 --name tc2-r1

Writes only under $LL_REC_ROOT (default ~/clasher-live/loop/recordings)/<name>/ (must not exist yet). Stops at
--seconds (<= 900), when the free space of that disk drops below 6 GiB, when the recording exceeds --max-gb (<= 3),
or when bsgrab ends. The summary has FPS, capture latency (receive - display time), and sequence gaps.
"""
import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from frames import Grabber  # noqa: E402

MIN_FREE = max(6 << 30, int(float(os.environ.get('LL_MIN_FREE_GB', 0))*(1 << 30)))   # env can only raise it


def pct(xs, q):
    return float(np.percentile(xs, q)) if xs else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--bsgrab', required=True)
    ap.add_argument('--crop', required=True)
    ap.add_argument('--size', default='540,1140')
    ap.add_argument('--fps', type=int, default=10)
    ap.add_argument('--seconds', type=float, default=240)
    ap.add_argument('--name', required=True)
    ap.add_argument('--quality', type=int, default=90)
    ap.add_argument('--max-gb', type=float, default=3)
    a = ap.parse_args(argv)
    root = Path(os.environ.get('LL_REC_ROOT', '~/clasher-live/loop/recordings')).expanduser().resolve()
    out = (root/a.name).resolve()
    if out.parent != root or not a.name.replace('-', '').replace('_', '').isalnum():
        sys.exit(f'bad --name {a.name!r}')
    seconds, max_bytes = min(a.seconds, 900), min(a.max_gb, 3)*(1 << 30)
    if shutil.disk_usage(root).free < MIN_FREE:
        sys.exit('free space below 6 GiB: not starting')
    out.mkdir()   # fails if it exists
    crop = [float(v) for v in a.crop.split(',')]; size = [int(v) for v in a.size.split(',')]
    log = open(out/'bsgrab.stderr', 'wb')
    g = Grabber(a.bsgrab, crop, size, a.fps, seconds+5, stderr=log)
    t0, n, nbytes, lat, gaps, last, stop = time.time(), 0, 0, [], 0, None, 'bsgrab ended'
    with open(out/'frames.jsonl', 'w') as idx:
        try:
            for f in g:
                name = f'{n:06d}.jpg'
                ok, buf = cv2.imencode('.jpg', f.bgr, [cv2.IMWRITE_JPEG_QUALITY, a.quality])
                if not ok:
                    stop = 'jpeg encode failed'; break
                (out/name).write_bytes(buf.tobytes()); nbytes += len(buf)
                idx.write(json.dumps(dict(i=n, seq=f.seq, file=name, display_ns=f.display_ns, emit_ns=f.emit_ns,
                                          recv_ns=f.recv_ns, w=f.bgr.shape[1], h=f.bgr.shape[0]))+'\n')
                lat.append((f.recv_ns-f.display_ns)/1e6)
                if last is not None and f.seq != last+1:
                    gaps += 1
                last = f.seq; n += 1
                if time.time()-t0 >= seconds:
                    stop = 'seconds'; break
                if nbytes > max_bytes:
                    stop = 'max-gb'; break
                if n % 50 == 0 and shutil.disk_usage(root).free < MIN_FREE:
                    stop = 'free space below 6 GiB'; break
        except ValueError as e:
            stop = f'bad stream: {e}'
        finally:
            rc = g.close()
    idx_rows = [json.loads(l) for l in open(out/'frames.jsonl')]
    span = (idx_rows[-1]['display_ns']-idx_rows[0]['display_ns'])/1e9 if len(idx_rows) > 1 else 0
    summary = dict(name=a.name, stop=stop, bsgrab_rc=rc, frames=n, bytes=nbytes, crop=crop, size=size, fps_req=a.fps,
                   fps=(n-1)/span if span else None, seq_gaps=gaps, latency_ms_p50=pct(lat, 50),
                   latency_ms_p95=pct(lat, 95), latency_ms_max=max(lat) if lat else None, wall_s=time.time()-t0)
    (out/'summary.json').write_text(json.dumps(summary, indent=1)+'\n')
    print(json.dumps(summary))
    return 0 if n and stop in ('seconds', 'bsgrab ended') else 1


if __name__ == '__main__':
    sys.exit(main())
