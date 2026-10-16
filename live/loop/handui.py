"""Hand-slot UI state of the official client, from pixels: 'empty' (the blue crown placeholder while a card slides
in), 'coloured' (affordable) or 'greyed' (unaffordable), per hand slot. A UI property, not a perception model; no bot
imports (drive.py loads it before the pinned runtime). Thresholds measured on s17-s22 (slot_audit.py).
"""
import cv2

EMPTY_BLUE = .9           # fraction of placeholder-blue pixels for an empty slot
COLOURED_SAT = 60         # mean HSV saturation: coloured cards ~150-250, greyed ~0-5, measured on s17-s22
# official hand-card boxes in 1080x1920 Android px (canvas.HUD_MAP[:4] targets)
_CARD_X = ((242, 429), (444, 632), (647, 835), (850, 1037))
SLOT_BOXES = [(x1 + 11, 1619, x2 - 11, 1828) for x1, x2 in _CARD_X]


def slot_stats(frame):
    """[(empty, mean saturation)] for the 4 hand slots of a portrait frame of any size (16:9 guest)."""
    h, w = frame.shape[:2]
    sx, sy = w/1080, h/1920
    out = []
    for x1, y1, x2, y2 in SLOT_BOXES:
        crop = frame[int(y1*sy):int(y2*sy), int(x1*sx):int(x2*sx)]
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV).reshape(-1, 3)
        blue = ((hsv[:, 0] > 95) & (hsv[:, 0] < 125) & (hsv[:, 1] > 120)).mean()
        out.append((bool(blue > EMPTY_BLUE), float(hsv[:, 1].mean())))
    return out


def ui_of(stats):
    return ['empty' if e else 'coloured' if s > COLOURED_SAT else 'greyed' for e, s in stats]


def slot_ui(frame):
    return ui_of(slot_stats(frame))
