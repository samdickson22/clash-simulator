"""Official-client frame (portrait, any size; geometry in 1080x1920 Android px, BlueStacks 16:9) -> the 540x1140
sanitized canvas LivePerception was trained on (offline renderer 1080x2280 downscaled 2x; clasher.vision.l1 boxes).

Arena: a uniform scale + offset fitted on 5 tower template matches between renderer validation frames and official
ladder frames (residuals < 0.5 px at 540 width; reports/live/loop/PROGRESS.md): android = ARENA_S*canvas + ARENA_T.
HUD: each renderer box is filled from the corresponding official box (layouts differ: official cards are taller, the
elixir digit sits beside the drop, the next card sits under the emote button). Taps: tile -> android px.
"""
import cv2
import numpy as np

W, H = 1080, 1920                       # Android px of the 16:9 guest
ARENA_S, ARENA_T = 1.806, (51.5, -275.5)
# canvas boxes (clasher.vision.l1) -> official boxes (x1, y1, x2, y2) in Android px
_CARD_X = ((242, 429), (444, 632), (647, 835), (850, 1037))
HUD_MAP = [((76 + 71*i, 1020, 134 + 71*i, 1080), (x1 + 11, 1619, x2 - 11, 1828)) for i, (x1, x2) in enumerate(_CARD_X)]
HUD_MAP += [((18, 1028, 48, 1064), (63, 1797, 138, 1878)),        # next card (art, above its cost drop)
            ((50, 1109, 520, 1121), (290, 1866, 1036, 1890)),     # elixir bar
            ((22, 1099, 48, 1130), (285, 1832, 355, 1878)),       # elixir digit
            ((446, 144, 532, 175), (880, 40, 1060, 90))]          # clock ("Time left" value, top right; to verify)
CARD_SLOTS = [((x1 + x2)/2, 1712) for x1, x2 in _CARD_X]          # tap centres of the 4 hand cards
# renderer tile calibration (clasher.vision.l1.fit_calibration): native tile (x, y down) -> canvas px
TILE_A, TILE_B, TILE_C, TILE_D = 28.545, 12.09, 22.895, 237.18


def to_android(frame):
    return frame if frame.shape[:2] == (H, W) else cv2.resize(frame, (W, H), interpolation=cv2.INTER_LINEAR)


def canvas(frame):
    """BGR official frame -> 540x1140 BGR canvas (black outside the arena and the HUD boxes)."""
    f = to_android(frame)
    m = np.array([[ARENA_S, 0, ARENA_T[0]], [0, ARENA_S, ARENA_T[1]]], np.float64)
    out = cv2.warpAffine(f, m, (540, 1140), flags=cv2.INTER_AREA | cv2.WARP_INVERSE_MAP)
    out[:200] = 0; out[1000:] = 0
    for (cx1, cy1, cx2, cy2), (ox1, oy1, ox2, oy2) in HUD_MAP:
        out[cy1:cy2, cx1:cx2] = cv2.resize(f[oy1:oy2, ox1:ox2], (cx2-cx1, cy2-cy1), interpolation=cv2.INTER_AREA)
    return out


def tile_to_android(x, y):
    """Bot/record tile coords (x from screen left 0..18, y from screen bottom 0..32) -> Android px (int)."""
    cx, cy = TILE_B + TILE_A*x, TILE_D + TILE_C*(32.0 - y)
    return int(round(ARENA_S*cx + ARENA_T[0])), int(round(ARENA_S*cy + ARENA_T[1]))


def action_target(action):
    """Bot action (slot*576 + row*18 + col) -> (slot, card tap px, arena tap px)."""
    slot, rem = divmod(int(action), 576)
    row, col = divmod(rem, 18)
    return slot, tuple(map(int, CARD_SLOTS[slot])), tile_to_android(col + .5, row + .5)
