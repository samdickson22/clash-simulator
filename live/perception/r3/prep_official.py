"""Round 3: official empty-arena floors -> arena-cache space (canvas.py mapping + prepare_pixels), one npz.

  python r3/prep_official.py OUT.npz IMG...      (never Training Camp: held-out arena)
"""
import sys
from pathlib import Path

import cv2
import numpy as np

R = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(R/'src'), str(R/'live/loop')]
import canvas as LC  # noqa: E402
from clasher.vision.l1_v4 import prepare_pixels  # noqa: E402

out, paths = sys.argv[1], sys.argv[2:]
arenas = [prepare_pixels(LC.canvas(cv2.imread(p)))[0] for p in paths]
np.savez(out, arena=np.stack(arenas), names=np.array(['/'.join(Path(p).parts[-2:]) for p in paths]))
print(len(arenas), arenas[0].shape)
