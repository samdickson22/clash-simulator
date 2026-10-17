"""05: draw night labels on frames for visual QA (Sol). Writes JPEGs + an index.json to the output dir.

  python -B qa_overlay.py OUT_DIR LABEL_JSON [LABEL_JSON ...]

Blue boxes = team 0 (ours/bottom), red = team 1 (opp/top); a dot = native ground anchor; yellow crosses = tower
visual centres (arena_calib); cyan rectangle = candidate 1080x1920 viewport. Text: class, team, phase, hp_frac, flags.
"""
import json
import sys
from pathlib import Path

import cv2


def draw(label_path, out_dir):
    rec = json.loads(Path(label_path).read_text())
    img = cv2.imread(str(Path(label_path).parent / rec['frame']))
    x1, y1, x2, y2 = rec['viewport']
    cv2.rectangle(img, (x1, y1), (x2 - 1, y2 - 1), (255, 255, 0), 2)
    for k, (cx, cy) in (rec.get('arena_calib') or {}).items():
        cv2.drawMarker(img, (int(cx), int(cy)), (0, 255, 255), cv2.MARKER_CROSS, 30, 2)
        cv2.putText(img, k, (int(cx) + 8, int(cy) - 8), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 255, 255), 2)
    for o in rec['objects']:
        if o['kind'] == 'tower':
            continue
        col = (255, 80, 0) if o['team'] == 0 else (0, 0, 255)
        ax, ay = o['anchor_px']
        cv2.circle(img, (int(ax), int(ay)), 5, col, -1)
        if o['box']:
            bx1, by1, bx2, by2 = o['box']
            cv2.rectangle(img, (bx1, by1), (bx2, by2), col, 2)
            txt = f"{o['class_name'] or o['body_name']} t{o['team']} {o['phase']} hp{o['hp_frac']}"
            if o['box_flags']:
                txt += ' ' + ','.join(o['box_flags'])
            cv2.putText(img, txt, (bx1, max(12, by1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, .5, col, 2)
        else:
            cv2.putText(img, f"NOBOX {o['kind']} {o['class_name'] or o['body_name']} t{o['team']} {o['phase']}",
                        (int(ax), int(ay) + 18), cv2.FONT_HERSHEY_SIMPLEX, .5, col, 2)
    name = Path(label_path).stem + '-qa.jpg'
    cv2.imwrite(str(out_dir / name), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return dict(qa_image=name, label=str(label_path), source_frame=str(Path(label_path).parent / rec['frame']),
                tick=rec['tick'], complete=rec['complete'],
                objects=[{k: o[k] for k in ('object_id', 'kind', 'class_name', 'team', 'native_owner', 'phase',
                                             'hp_frac', 'box', 'box_flags', 'anchor_px')}
                         for o in rec['objects'] if o['kind'] != 'tower'])


if __name__ == '__main__':
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    index = [draw(p, out) for p in sys.argv[2:]]
    (out / 'index.json').write_text(json.dumps(index, indent=1))
    print(len(index), 'overlays in', out)
