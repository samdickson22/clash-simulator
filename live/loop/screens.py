"""Between-battle screens for autonav (normalized 1080x1920 Android frames, drive.normalize). UI handling only.

classify(f) -> (kind, (x, y)) or (None, None). These existing UI heuristics offer navigation targets:
  result  battle result: yellow Play Again left of a blue OK in the button row (any row y 1640..1900, so result
          variants with a taller reward area or overlays drawn over the buttons still match); tap OK
  road    blue OK centred in the grey footer, blue trophy column at the left edge, no detected resource coin;
          tap footer OK. This pre-existing heuristic also matches some manual road / Pass pages and the recorded
          l12g-bs.png Collection variant; it does not establish which page is open.
  home    yellow Battle button above the tab bar; tap Battle
Known reward presenters (chests, gold, cards, snippets, mystery boxes) remain unknown with no tap and require deferred
manual handling. Generic smooth-background recognition was removed: it cannot establish reward identity, and a
synthetic Buy button at (540, 1500) reproduced an unsafe tap. This rejection does not establish purchase-screen safety
for the retained result/home/road heuristics. Other unmatched frames return (None, None).
Recorded fixtures and the synthetic Buy regression are checked in tests/test_screens.py.
"""
import numpy as np

STABLE = dict(result=5, home=5, road=5)      # required stable-frame counts; enforced by the driver


def _mean(f, x1, y1, x2, y2):
    return f[y1:y2, x1:x2].reshape(-1, 3).mean(0)


def _yellow(c):
    return c[2] > 190 and c[1] > 150 and c[0] < 140


def _blue(c):
    return c[0] > 200 and c[2] < 140


def _frac(f, x1, y1, x2, y2, kind):
    b, g, r = [f[y1:y2, x1:x2, i].astype(np.int16) for i in range(3)]
    if kind == 'yellow':
        m = (r > 190) & (g > 150) & (b < 140)
    else:
        m = (b > 200) & (r < 140)
    return float(m.mean())


def result_row(f):
    """y of the result button row (Play Again yellow at x 250..490 and OK blue at x 600..810 on the same 80 px
    band; pixel fractions, so a translucent overlay over part of a button still matches), else None."""
    for y in range(1640, 1830, 10):
        if _frac(f, 260, y, 480, y + 80, 'yellow') > .45 and _frac(f, 610, y, 800, y + 80, 'blue') > .45:
            return y + 40
    return None


def classify(f):
    y = result_row(f)
    if y is not None:
        return 'result', (705, y)
    coin = _mean(f, 440, 35, 475, 75)                          # the gold coin in the top resource bar (home)
    bar = f[1000:1700, 0:90].astype(np.int16)                  # the blue trophy column at the left edge
    col = ((bar[..., 0] > 180) & (bar[..., 2] < 120)).mean(0).max()
    footer = _mean(f, 0, 1890, 400, 1920)                      # the grey footer under the OK (home: the tab bar)
    grey_footer = footer.max() - footer.min() < 45 and 50 < footer.mean() < 140   # road ~(102, 82, 69) BGR
    if _blue(_mean(f, 440, 1810, 640, 1880)) and col > .6 and grey_footer and not _yellow(coin):
        return 'road', (540, 1845)
    if (_yellow(_mean(f, 400, 1430, 700, 1540)) and _yellow(coin) and _mean(f, 0, 1760, 1080, 1900)[0] > 90
            and f[300:1300:8, ::8].mean() > 70):
        return 'home', (550, 1489)
    return None, None
