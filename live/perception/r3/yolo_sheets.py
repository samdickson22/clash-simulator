"""Box-refinement sheets for helpers: the capture frame's arena with numbered draft boxes (from yolo_labels.py priors) and a pixel
ruler (capture pixels), plus a clean copy. Images stay in scratch.

  python yolo_sheets.py LABEL_DIR INDEX_JSON OUT_DIR
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from yolo_labels import BODY, CARD, SIZE, DEFAULT, tile_px  # noqa: E402
import canvas as LC  # noqa: E402

lab_dir, ix_path, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]); out.mkdir(parents=True, exist_ok=True)
ix = {x['id']: x for x in json.loads(ix_path.read_text())}
for f in sorted(lab_dir.glob('*.json')):
    lab = json.loads(f.read_text()); src = ix[lab['id']]['source']; im = cv2.imread(src); h, w = im.shape[:2]
    t = LC.ARENA_S*LC.TILE_A*w/LC.W
    y0, y1 = int(tile_px(0, -1.5, w, h)[1]), int(tile_px(0, 33, w, h)[1])
    ann = im.copy()
    for k in range(0, w, 50):
        cv2.line(ann, (k, y0), (k, y0+8), (255, 255, 255), 1); cv2.putText(ann, str(k), (k+1, y0+18), 0, .33, (255, 255, 255), 1)
    for k in range(y0-y0 % 50, y1, 50):
        cv2.line(ann, (0, k), (8, k), (255, 255, 255), 1); cv2.putText(ann, str(k), (10, k+4), 0, .33, (255, 255, 255), 1)
    for i, u in enumerate(lab['units']):
        name = BODY.get(u.get('body')) or CARD.get(u['card'], 'unknown')
        c = (255, 160, 0) if u['owner'] == 'us' else (0, 0, 255)
        if u.get('box_px'):
            bx1, by1, bx2, by2 = map(int, u['box_px'])
        else:
            gx, gy = tile_px(float(u['x']), float(u['y']), w, h); bw, up, dn = SIZE.get(name, DEFAULT)
            bx1, by1, bx2, by2 = int(gx-bw*t/2), int(gy-up*t), int(gx+bw*t/2), int(gy+dn*t)
        cv2.rectangle(ann, (bx1, by1), (bx2, by2), c, 1)
        cv2.putText(ann, f'{i}', (bx1, by1-2), 0, .45, (0, 0, 0), 3)
        cv2.putText(ann, f'{i}', (bx1, by1-2), 0, .45, (0, 255, 255), 1)
    sheet = np.hstack([im[y0:y1], np.full((y1-y0, 6, 3), 255, np.uint8), ann[y0:y1]])
    cv2.imwrite(str(out/f"{lab['id']}.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 93])
print('sheets', len(list(out.glob('*.jpg'))))
