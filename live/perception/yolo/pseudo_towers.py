"""Tower pseudo-labels for official training frames (KataCR data labels towers; our hand labels don't), and empty-arena hard
negatives: crops of battle-start frames whose only labels are the towers.

  --mode official: for every `image label` pair in LIST (KataCR crops), append king-tower/queen-tower boxes (score >= .5) predicted by
                   WEIGHTS unless the txt already has tower lines.
  --mode empty:    for every capture image in LIST, write a KataCR crop + tower-only txt into OUT and a pair list; a frame with any
                   confident non-tower detection (>= .6) is skipped (not empty).

  python pseudo_towers.py --weights W.pt --katacr-src SRC --mode official|empty --list LIST [--out DIR --out-list LIST2]
"""
import argparse
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_yolo import crop, NON_UNIT  # noqa: E402

TOWERS = {'king-tower', 'queen-tower', 'cannoneer-tower', 'dagger-duchess-tower'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--weights', required=True); p.add_argument('--katacr-src', required=True)
    p.add_argument('--mode', choices=('official', 'empty'), required=True); p.add_argument('--list', type=Path, required=True)
    p.add_argument('--out', type=Path); p.add_argument('--out-list', type=Path); p.add_argument('--device', default='0')
    a = p.parse_args()
    sys.path.insert(0, a.katacr_src)
    from katacr.constants.label_list import unit2idx
    from katacr.yolov8.train import YOLO_CR
    m = YOLO_CR(a.weights)

    def towers(img):
        r = m.predict(img, device=a.device, verbose=False, conf=.3, iou=.6, imgsz=(896, 576))[0]
        h, w = img.shape[:2]; rows, other = [], 0
        for b in r.orig_boxes.cpu().numpy():
            name, sc = m.names[int(b[5])], float(b[4])
            if name in TOWERS and sc >= .5:
                x1, y1, x2, y2 = b[:4]
                rows.append(f'{unit2idx[name]} {(x1+x2)/2/w:.6f} {(y1+y2)/2/h:.6f} {(x2-x1)/w:.6f} {(y2-y1)/h:.6f} {int(b[6])}')
            elif name not in NON_UNIT and sc >= .6:
                other += 1
        return rows, other

    if a.mode == 'official':
        n = 0
        for ln in a.list.read_text().splitlines():
            if not ln.strip():
                continue
            ip, lp = ln.split()[:2]
            have = Path(lp).read_text().splitlines()
            if any(int(float(x.split()[0])) in {unit2idx[t] for t in TOWERS} for x in have if x.strip()):
                continue
            rows, _ = towers(cv2.imread(ip))
            Path(lp).write_text('\n'.join([x for x in have if x.strip()]+rows)+'\n'); n += len(rows)
        print('tower boxes added', n)
    else:
        a.out.mkdir(parents=True, exist_ok=True); pairs = []; skipped = 0
        for k, src in enumerate(a.list.read_text().split()):
            img = crop(cv2.imread(src)); rows, other = towers(img)
            if other or len(rows) < 3:
                skipped += 1; continue
            name = f"empty-{k:03d}-{'-'.join(Path(src).parts[-3:-1])}"
            ip, lp = a.out/f'{name}.jpg', a.out/f'{name}.txt'
            cv2.imwrite(str(ip), img, [cv2.IMWRITE_JPEG_QUALITY, 95]); lp.write_text('\n'.join(rows)+'\n'); pairs.append(f'{ip} {lp}')
        a.out_list.write_text('\n'.join(pairs)+'\n')
        print('empty frames', len(pairs), 'skipped', skipped)


if __name__ == '__main__':
    main()
