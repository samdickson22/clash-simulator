"""Read our 8-card Battle Deck from the Cards → Decks → "Battle Deck" page (Android 1080x1920 frame, normalized).

Grid (BlueStacks 16:9, 2026-10 client): 4 columns at x 38 + 260*c (212 wide), rows at y 496 and 916 (262 tall: card art
+ the "Level N" band). Each cell is scaled to the Battle Log cell size (104x128) and matched against the card templates
(live/loop/cards/<Card>/*.png, see battlelog.identify). A slot scoring below MIN_SCORE is reported as unknown (a card
we have no template for, or the page is not open); its crop is saved for labelling.
"""
import time
from pathlib import Path

import cv2

import battlelog as B

COLS, ROWS, CW, CH = [38 + 260*c for c in range(4)], [496, 916], 212, 262
MIN_SCORE = .75


def read_deck(frame, templates, save_dir=None):
    """-> dict(cards=[8 names or None], scores=[8], unknown=[slot indices]). Slots: row-major, as on the page."""
    cards, scores, unknown = [], [], []
    for r, y in enumerate(ROWS):
        for c, x in enumerate(COLS):
            cell = cv2.resize(frame[y:y+CH, x:x+CW], (104, 128), interpolation=cv2.INTER_AREA)
            name, s = B.identify(cell, templates, thr=0)
            i = 4*r + c
            if s < MIN_SCORE:
                name = None
                unknown.append(i)
                if save_dir is not None:
                    d = Path(save_dir); d.mkdir(parents=True, exist_ok=True)
                    cv2.imwrite(str(d/f'deck-slot{i}-{time.strftime("%Y%m%dT%H%M%S")}.png'), cell)
            cards.append(name); scores.append(round(float(s), 3))
    return dict(cards=cards, scores=scores, unknown=unknown)
