"""Round-3 diagnosis of 'zero units on official frames': input statistics and raw unit-heatmap scores, renderer vs official.

  python diag_zero.py EXPORT_DIR OUT.json REF_CANVAS.png... -- OFFICIAL.jpg...
Renderer frames are sanitized 540x1140 canvases; official frames go through live/loop/canvas.py (read-only import).
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

R = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(R/'src'), str(R/'live/perception'), str(R/'live/loop')]
from clasher.vision.l1_v4 import prepare_pixels  # noqa: E402
import canvas as LC  # noqa: E402
from infer import FRAME_KEYS  # noqa: E402


def run(frame, vocab, img):
    arena, hud = prepare_pixels(img)
    t = lambda x: torch.from_numpy(np.ascontiguousarray(x)).permute(2, 0, 1)[None].float().div(255)
    with torch.inference_mode():
        out = dict(zip(FRAME_KEYS, frame(t(arena), t(hud))))
    ids = vocab['identities']; nb = len(ids)
    heat = out['body_heatmap'][0].sigmoid().numpy()
    unit = np.array([i % nb < nb-2 and not str(ids[i % nb]).startswith('fx:') for i in range(2*nb)])
    uh = heat[unit]; th = heat[~unit]
    flat = np.argsort(-uh.ravel())[:5]
    uidx = np.nonzero(unit)[0]
    top = []
    for f in flat:
        c, y, x = np.unravel_index(f, uh.shape); ch = uidx[c]
        top.append(dict(owner=int(ch//nb), ident=ids[ch % nb], gx=int(x), gy=int(y), score=round(float(uh[c, y, x]), 4)))
    a = arena.reshape(-1, 3).astype(np.float32)
    return dict(arena_mean_bgr=a.mean(0).round(1).tolist(), arena_std_bgr=a.std(0).round(1).tolist(),
                unit_max=round(float(uh.max()), 4), unit_p999=round(float(np.quantile(uh, .999)), 4),
                n_ge_05=int((uh >= .5).sum()), n_ge_02=int((uh >= .2).sum()), n_ge_01=int((uh >= .1).sum()),
                tower_max=round(float(th.max()), 4), top=top)


def main():
    exp, out = Path(sys.argv[1]), Path(sys.argv[2])
    k = sys.argv.index('--'); refs, offs = sys.argv[3:k], sys.argv[k+1:]
    torch.set_num_threads(8)
    frame = torch.jit.load(str(exp/'frame.pt'), map_location='cpu').eval()
    vocab = json.loads((exp/'vocab.json').read_text())
    res = {}
    for p in refs:
        res['renderer:'+Path(p).name] = run(frame, vocab, cv2.imread(p))
    for p in offs:
        res['official:'+'/'.join(Path(p).parts[-2:])] = run(frame, vocab, LC.canvas(cv2.imread(p)))
    for k_, v in res.items():
        print(k_, 'max', v['unit_max'], 'p999', v['unit_p999'], '>=.5', v['n_ge_05'], '>=.2', v['n_ge_02'], 'mean', v['arena_mean_bgr'],
              'std', v['arena_std_bgr'], 'top', [(t['ident'], t['owner'], t['gx'], t['gy'], t['score']) for t in v['top'][:3]])
    out.write_text(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
