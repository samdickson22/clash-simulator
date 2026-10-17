"""Convert a battle's --dump-raw .bin captures to lossless PNG (run on 05 after the copy, never on the live Mac).
  python raw_bin_to_png.py MATCH_DIR [MATCH_DIR ...] [--delete-bin]
Reads <dir>/raw/index.jsonl and <dir>/yolo_in/index.jsonl (shape/dtype per file), writes NNNNNN.png beside each .bin
(cv2 PNG level 3), checks the PNG decodes back to the identical array, and with --delete-bin removes the verified .bin."""
import json, sys
from pathlib import Path
import cv2, numpy as np


def convert(d, delete):
    n = 0
    for sub in ('raw', 'yolo_in'):
        idx = Path(d)/sub/'index.jsonl'
        if not idx.exists():
            continue
        for l in open(idx):
            r = json.loads(l)
            b = Path(d)/sub/r['file']
            if not b.exists():
                continue
            img = np.fromfile(b, dtype=r['dtype']).reshape(r['shape'])
            png = b.with_suffix('.png')
            cv2.imwrite(str(png), img, [cv2.IMWRITE_PNG_COMPRESSION, 3])
            back = cv2.imread(str(png), cv2.IMREAD_UNCHANGED)
            if back is None or back.shape != img.shape or not np.array_equal(back, img):
                sys.exit(f'verify failed: {png}')
            if delete:
                b.unlink()
            n += 1
    return n


if __name__ == '__main__':
    dirs = [a for a in sys.argv[1:] if not a.startswith('--')]
    for d in dirs:
        print(d, convert(d, '--delete-bin' in sys.argv), 'converted')
