"""Own-hand classifier logits for every recorded perception frame of a run (offline, from the run's video), for replays.
  python hand_logits_offline.py MODEL OUT_DIR RUN_DIR [RUN_DIR ...]   -> OUT_DIR/<run>.npz (n [N], logits [N,5,56])
Frames as the driver gives them: normalize(canvas.to_android(video frame))."""
import sys
from pathlib import Path
import cv2, json, numpy as np, torch
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import canvas as C


def normalize(f):                       # = drive.normalize
    w = float(np.percentile(f[1600:1920:2, ::2].max(2), 99.5))
    return f if (w >= 245 or w < 80) else cv2.convertScaleAbs(f, alpha=255./w)


def main():
    model, out = sys.argv[1], Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(16)
    m = torch.jit.load(model, map_location='cpu').eval()
    for d in map(Path, sys.argv[3:]):
        rid = d.name if d.parent.name == 'runs' else f'{d.parent.name}-{d.name}'
        ns = [json.loads(l)['n'] for l in open(d/'perception.jsonl')]
        keep, lg = [], []
        with torch.inference_mode():
            for n in ns:
                im = cv2.imread(str(d/'video'/f'{n:06d}.jpg'))
                if im is None:
                    continue
                f = np.ascontiguousarray(normalize(C.to_android(im)))
                lg.append(m(torch.from_numpy(f)).float().numpy()); keep.append(n)
        np.savez_compressed(out/f'{rid}.npz', n=np.array(keep), logits=np.array(lg, np.float32))
        print(rid, len(keep), flush=True)


if __name__ == '__main__':
    main()
