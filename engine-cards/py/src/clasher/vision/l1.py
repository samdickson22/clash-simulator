"""Pixel boundary and calibrated geometry for the offline L1 renderer.

Coordinates refer to the 540 x 1140 downscaled AVD. Pixel boxes are weak
ground-anchor boxes, not exact sprite segmentations. No native state is read
by this module.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from clasher.rl.perspective_sanitizer import (
    DualHudPerspectiveSpec, NormalizedRegion, sanitize_dual_hud_frame,
)

WIDTH, HEIGHT = 540, 1140
ARENA = (0, 200, 540, 1000)
CLOCK = (446, 144, 532, 175)
OWN_HUD = (0, 1010, 540, 1140)
HAND = tuple((76 + 71*i, 1020, 134 + 71*i, 1080) for i in range(4))
NEXT = (18, 1028, 48, 1064)
ELIXIR = (50, 1109, 520, 1121)
ELIXIR_DIGIT = (22, 1099, 48, 1130)


def _region(box):
    x1, y1, x2, y2 = box
    return NormalizedRegion(x1/WIDTH, y1/HEIGHT, (x2-x1)/WIDTH, (y2-y1)/HEIGHT)


def public_pixels(raw: np.ndarray) -> np.ndarray:
    """Allowlist at source resolution before resizing or JPEG encoding.

    The black canvas contains only copies returned by the existing sanitizer.
    Top HUD pixels can never bleed through a resampling kernel.
    """
    if raw.shape != (2280, 1080, 3):
        raise ValueError(f"Uncalibrated source dimensions: {raw.shape}")
    spec = DualHudPerspectiveSpec(_region(ARENA), _region(CLOCK),
                                 _region(OWN_HUD), _region((0, 0, 540, 200)))
    safe = sanitize_dual_hud_frame(raw, spec)
    output = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
    for box, crop in ((ARENA, safe.arena), (CLOCK, safe.clock), (OWN_HUD, safe.own_hud)):
        x1, y1, x2, y2 = box
        output[y1:y2, x1:x2] = cv2.resize(crop, (x2-x1, y2-y1), interpolation=cv2.INTER_AREA)
    return output


def crop(image, box):
    x1, y1, x2, y2 = box
    return image[y1:y2, x1:x2]


class Geometry:
    def __init__(self, path: Path):
        payload = json.loads(path.read_text())
        self.matrix = np.asarray(payload['tile_to_pixel'], np.float64)
        self.inverse = np.linalg.inv(np.vstack((self.matrix, [0, 0, 1])))[:2]

    def pixel(self, x, y):
        return (self.matrix @ [x, y, 1]).tolist()

    def tile(self, x, y):
        return (self.inverse @ [x, y, 1]).tolist()

    def box(self, card, x, y):
        px, py = self.pixel(x, y)
        w, h, lift = box_shape(card)
        return [px-w/2, py-lift-h/2, px+w/2, py-lift+h/2]

    def anchor(self, card, box):
        x1, y1, x2, y2 = box
        # Offset is a fraction of predicted box height to tolerate resizing.
        _, h, lift = box_shape(card)
        return self.tile((x1+x2)/2, (y1+y2)/2 + (y2-y1)*lift/h)


def box_shape(card):
    if card == 'KingTower':
        return 95, 125, 38
    if card == 'Tower':
        return 77, 94, 29
    if card in ('Cannon', 'Tesla'):
        return 52, 70, 19
    if card in ('Giant', 'HogRider', 'Prince', 'DarkPrince'):
        return 48, 64, 18
    if card in ('Skeletons', 'Goblins', 'IceSpirit'):
        return 23, 35, 10
    return 34, 49, 14


def fit_calibration(output: Path):
    """Fit manually reviewed ground contacts; reserve kings and Tesla for QA."""
    train = [([3.5, 6.5], [112, 386]), ([14.5, 6.5], [426, 386]),
             ([3.5, 25.5], [112, 821]), ([14.5, 25.5], [426, 821])]
    test = [([9, 3], [269, 307]), ([9, 29], [269, 901]), ([5, 11], [155, 487])]
    a = np.array([[*t, 1] for t, p in train])
    matrix = np.linalg.lstsq(a, np.array([p for t, p in train]), rcond=None)[0].T
    inv = np.linalg.inv(np.vstack((matrix, [0, 0, 1])))[:2]
    px = [float(np.linalg.norm(matrix @ [*t, 1] - p)) for t, p in test]
    tiles = [float(np.linalg.norm(inv @ [*p, 1] - t)) for t, p in test]
    result = dict(schema='clasher.l1.calibration.v1', source_size=[1080, 2280],
                  jpeg_size=[540, 1140], tile_to_pixel=matrix.tolist(),
                  pixel_to_tile=inv.tolist(), training_landmarks=train, heldout_landmarks=test,
                  heldout_pixel_errors=px, heldout_tile_errors=tiles,
                  mean_tile_error=float(np.mean(tiles)), max_tile_error=max(tiles),
                  annotation_uncertainty_pixels=4,
                  sources=['preflight.jpg', 'calibration-probe.jpg', 'calibration-observe.json'],
                  scope='Affine ground contacts, manual landmarks; boxes are weak extents, not silhouette truth.')
    output.write_text(json.dumps(result, indent=2)+'\n')
    return result
