#!/Users/sam/clasher-live/venv/bin/python
"""Display-only feed + clean video pipeline for the clasher live viewer. Never sends input; never imports the driver.

  display_feed.py [--fps 30] [--desktop-rate 8000k,8000k,1000k] [--phone-rate 1500k,1500k,300k]

1. Video: `dispgrab stream` (own read-only ScreenCaptureKit capture of the BlueStacks game rect at native pixels, NV12,
   constant --fps) piped straight into ffmpeg h264_videotoolbox, publishing rtsp://127.0.0.1:8554/{desktop,phone} to
   MediaMTX. Python never touches pixels. The pipeline is (re)started ONLY while the driver is not in a battle: a second
   ScreenCaptureKit client starting/stopping has correlated with -3805 interruptions of the driver's capture (drive.py).
   A pipeline that dies mid-battle is restarted after the battle ends (the page falls back to JPEG snapshots meanwhile).
   Source: stream-source.json {"kind": "window", ...} = one window by owner app (+ optional title substring) with an
   explicit crop (or insets + aspect fit) and output size (see window_source); {"kind": "nulls", ...} = Null's grid;
   absent / anything else = the BlueStacks game rect (title bar + sidebar insets). The window is never started by us:
   a missing or non-matching window shows the status card.
2. Overlay feed: follows the driver's line-buffered logs (runs/<session>/[mNN/]perception, frames, decisions .jsonl)
   and writes ~/clasher-live/loop/display/state.json at 10 Hz (atomic): unit boxes / tower HP / plan / last play in
   Android px (1080x1920 guest), hand, next, elixir, crowns, session tally. The pages draw it on a <canvas>.
Writes only under ~/clasher-live/loop/display/. Never binds or reads the driver's 127.0.0.1:8766.
Env (tests): LL_LOOP_DIR, CLASHER_DISPLAY_GRAB, CLASHER_DISPLAY_FFMPEG, CLASHER_DISPLAY_RTSP, CLASHER_DISPLAY_OFFSETS.
"""
import argparse
import json
import math
import os
import re
import signal
import subprocess
import threading
import time
from collections import deque
from pathlib import Path

HOME = Path.home()
LOOP = Path(os.path.expanduser(os.environ.get('LL_LOOP_DIR', '~/clasher-live/loop')))
OUT = LOOP/'display'
GRAB = os.environ.get('CLASHER_DISPLAY_GRAB', str(OUT/'bin/dispgrab'))
FFMPEG = os.environ.get('CLASHER_DISPLAY_FFMPEG', str(HOME/'clasher-live/tools/ffmpeg'))
RTSP = os.environ.get('CLASHER_DISPLAY_RTSP', 'rtsp://127.0.0.1:8554')
VCODEC = os.environ.get('CLASHER_DISPLAY_VCODEC', 'h264_videotoolbox')     # tests on Linux: libx264
OFFSETS = os.environ.get('CLASHER_DISPLAY_OFFSETS', str(HOME/'clasher-live/yolo/ground-offsets-v2.json'))
STATUS = LOOP/'status.txt'
SOURCE_FILE = LOOP/'stream-source.json'   # the capture source: kind 'window' (one window + crop) / Null's grid / absent
CANVAS = (1044, 1856)                      # grid canvas = the ladder's native size (same renditions, no re-negotiation)
GATE_FILE = OUT/'capture-gate'             # 'hold' while the driver is in a battle: dispgrab restarts nothing in-process
MODE_FILE = OUT/'mode.txt'                 # 'display' / 'yield': read but since 2026-10-18 both behave alike: no own
                                           # capture while a vision driver exists (its frames instead), own otherwise.
TITLE_PT, SIDEBAR_PT = 32.0, 32.0          # BlueStacks title bar (top) and tool sidebar (right), points
IDLE_S = 3.0                               # driver logs idle longer than this = no session (display)
BATTLE_HOLD_S = 60.0                       # last state 'battle' + logs seen within this = treat as in battle (gate)
VISION_TTL_S = 1.0                         # driver_running() result reused this long (a vision driver needs ~20 s of
                                           # model loading before its first battle row, so 1 s cannot miss a battle)
STALE_UNITS_S = 0.5
STALE_S = float(os.environ.get('CLASHER_DISPLAY_STALE_S', '8'))   # dispgrab stats: no captured frame this long = stalled
STATS_LATE_S = 15.0                        # no dispgrab stats line (10 s period) this long = hung/stopped capture
WINDOW_POLL_S = 2.0                        # non-SCK window check (CGWindowList) period while a display capture runs
WINDOW_GONE_S = 3.0                        # source window absent from CGWindowList this long = stop -> status card
HEALTHY_S = 120.0                          # a capture healthy this long resets the stale-restart backoff
WAIT_ACTION = 2304                         # 4 slots x 576 tiles; >= this = hold
MATCH_RE = re.compile(r'^m\d{2,}$')        # battle dirs; renamed false matches (mNN-false-HHMMSS) excluded

# Geometry from live/loop/canvas.py (display only; Android px of the 1080x1920 guest).
ARENA_S, ARENA_T = 1.806, (51.5, -275.5)
TILE_A, TILE_B, TILE_C, TILE_D = 28.545, 12.09, 22.895, 237.18
CARD_X = ((242, 429), (444, 632), (647, 835), (850, 1037))
BODY = {'SkeletonArmy': 'Skeleton', 'Skeletons': 'Skeleton', 'GoblinGang': 'Goblin', 'Goblins': 'Goblin',
        'MinionHorde': 'Minion', 'Minions': 'Minion', 'Barbarians': 'Barbarian', 'Archers': 'Archer',
        'GoblinHut': 'Spear Goblin', 'Tombstone': 'Skeleton', 'Graveyard': 'Skeleton', 'Rascals': 'Rascal',
        'RoyalRecruits': 'Royal Recruit', 'ThreeMusketeers': 'Musketeer', 'Bats': 'Bat', 'FireSpirits': 'Fire Spirit',
        'IceSpirit': 'Ice Spirit', 'BarbarianHut': 'Barbarian', 'Furnace': 'Fire Spirit', 'RoyalHogs': 'Royal Hog',
        'Wallbreakers': 'Wall Breaker', 'SpearGoblins': 'Spear Goblin'}


def log(msg):
    print(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), msg, flush=True)


def tile_to_android(x, y):
    cx, cy = TILE_B + TILE_A*x, TILE_D + TILE_C*(32.0 - y)
    return ARENA_S*cx + ARENA_T[0], ARENA_S*cy + ARENA_T[1]


def box_shape(card):
    if card in ('Giant', 'HogRider', 'Prince', 'DarkPrince', 'Golem', 'PEKKA', 'MiniPekka', 'Balloon'):
        return 48, 64, 18
    if card in ('Skeletons', 'Goblins', 'IceSpirit', 'Minions', 'Bats'):
        return 23, 35, 10
    return 34, 49, 14


def short_label(cls):
    return BODY.get(cls) or str(cls)


def label(cls):
    """overlay.py's label: 'Skeleton (SkeletonArmy)' for multi-body / spawner cards, else the card name."""
    b = BODY.get(cls)
    return f'{b} ({cls})' if b and b.replace(' ', '') != cls else str(cls)


UBOT_MAX_S = 0.5                           # units_bot comes on poll frames (~every 4th, ~0.4 s): carry it this long


def _norm(n):
    return re.sub(r'[^a-z0-9]', '', str(n).lower())


def unit_rows_bot(perc, ubot):
    """Perception units (fresh positions, detector boxes) labelled with the bot's TRUE card from the latest frames.jsonl
    units_bot (matched by raw detector class + owner-agnostic nearest position, <= 2 tiles). Falls back per unit."""
    units = perc.get('units') or []
    yolo = perc.get('units_yolo') or []
    yolo = yolo if len(yolo) == len(units) else [None]*len(units)
    info = perc.get('units_yolo_info') or []
    info = info if len(info) == len(units) else [None]*len(units)
    pool = list(ubot or ())
    rows = []
    for u, y, inf in zip(units, yolo, info):
        best, bd = None, 4.0                     # squared tile distance limit (2 tiles)
        for j, b in enumerate(pool):
            if y and b['raw'] and _norm(b['raw']) != _norm(y):
                continue
            d = (b['x'] - u['x'])**2 + (b['y'] - u['y'])**2
            if d < bd:
                best, bd = j, d
        if best is not None:
            b = pool.pop(best)
            card, owner, lab = b['card'], b['owner'], label(b['card'])
        else:
            card, owner, lab = None, u.get('owner', 1), str(y) if y else short_label(u.get('cls'))
        box = inf.get('box') if isinstance(inf, dict) else None
        rows.append(dict(x=u['x'], y=u['y'], owner=owner, card=card, cls=card or u.get('cls'), yolo=y, label=lab,
                         score=u.get('score'), box=box if isinstance(box, list) and len(box) == 4 else None))
    return rows


def unit_rows(perc):
    """Units as the overlay labels them. Prefers the translator's units_bot (the card + owner the bot uses); else the
    perception units with the raw detector class (units_yolo), not the pre-translator proxy cls. Label 'class→card'
    when the detector class and the bot's card differ."""
    units = perc.get('units') or []
    yolo = perc.get('units_yolo') or []
    yolo = yolo if len(yolo) == len(units) else [None]*len(units)
    bot = perc.get('units_bot')
    rows = []
    if isinstance(bot, list):                    # an explicit (even empty) translator list is authoritative
        same = len(bot) == len(units)
        for i, b in enumerate(bot):
            if not isinstance(b, dict) or 'x' not in b or 'y' not in b:
                continue
            card = b.get('card') or b.get('cls')
            y = b.get('yolo') or b.get('units_yolo') or (yolo[i] if same else None)
            lab = short_label(card) if not y or _norm(y) in (_norm(card), _norm(short_label(card))) else f'{y}→{card}'
            sc = b.get('score', units[i].get('score') if same else None)
            rows.append(dict(x=b['x'], y=b['y'], owner=b.get('owner', 1), card=card, cls=card, yolo=y, label=lab, score=sc))
        return rows
    info = perc.get('units_yolo_info') or []
    info = info if len(info) == len(units) else [None]*len(units)
    for u, y, inf in zip(units, yolo, info):
        box = inf.get('box') if isinstance(inf, dict) else None
        rows.append(dict(x=u['x'], y=u['y'], owner=u.get('owner', 1), card=None, cls=u.get('cls'), yolo=y,
                         label=str(y) if y else short_label(u.get('cls')), score=u.get('score'),
                         box=box if isinstance(box, list) and len(box) == 4 else None))
    return rows


def tile_of(action):
    if action is None or action >= WAIT_ACTION:
        return None
    row, col = divmod(int(action) % 576, 18)
    return col, row


def crowns(towers):
    """(ours, theirs) from frames.jsonl tower rows [owner, k/p, side, alive, hp]; owner 0 = ours; king down = 3."""
    out = []
    for victim in (1, 0):
        ts = [t for t in towers or () if t[0] == victim]
        out.append(3 if any(t[1] == 'k' and not t[3] for t in ts) else sum(1 for t in ts if t[1] == 'p' and not t[3]))
    return tuple(out)


def status_reason():
    try:
        return STATUS.read_text().strip()[:120] or 'no driver running'
    except OSError:
        return 'no driver running'


def game_crop(info):
    """Window-relative 9:16 game rect (points) below the title bar and left of the sidebar."""
    _, _, w, h = info['bounds']
    aw, ah = w - SIDEBAR_PT, h - TITLE_PT
    if aw <= 0 or ah <= 0:
        raise ValueError(f'window too small: {info["bounds"]}')
    gw, gh = (ah*9/16, ah) if aw/ah > 9/16 else (aw, aw*16/9)
    return (0.0, TITLE_PT, round(gw, 1), round(gh, 1))


CARD_BG = (58, 40, 30)                     # BGR dark slate: visibly a status card, never a black frame


def render_card(lines, w, h):
    """The status card picture (BGR uint8 h x w x 3): lines centred on a dark slate background, the first bold/white,
    the last (the time) small/grey; each line shrunk to fit 88% of the width. Legible at the 540-wide phone rendition
    (the visible-status-card rule of 2026-10-18 supersedes the 10-17 'plain black, one small line' card)."""
    import cv2
    import numpy as np
    img = np.full((h, w, 3), CARD_BG, np.uint8)
    font, base = cv2.FONT_HERSHEY_SIMPLEX, w/1034*1.7
    rows = []
    for i, t in enumerate(lines):
        last = i == len(lines) - 1 and len(lines) > 1
        sc = base*(.7 if last else 1.15 if i == 0 else 1.)
        th = max(1, round(sc*(2.2 if i == 0 else 1.6)))
        (tw, tht), _ = cv2.getTextSize(t, font, sc, th)
        if tw > .88*w:
            sc *= .88*w/tw
            th = max(1, round(th*.88*w/tw))
            (tw, tht), _ = cv2.getTextSize(t, font, sc, th)
        rows.append((t, sc, th, tw, tht, (245, 245, 245) if i == 0 else (165, 165, 165) if last else (215, 215, 215)))
    gap = int(.9*max(r[4] for r in rows)) if rows else 0
    y = (h - sum(r[4] for r in rows) - gap*(len(rows) - 1))//2
    for t, sc, th, tw, tht, col in rows:
        y += tht
        cv2.putText(img, t, ((w - tw)//2, y), font, sc, col, th, cv2.LINE_AA)
        y += gap
    return img


class NoWindow(RuntimeError):
    pass


def grab_info(src=None):
    """dispgrab info for the window dispgrab stream would pick: the BlueStacks default, or src's owner (+ title)."""
    out = subprocess.run([GRAB, 'info'] + window_args(src), capture_output=True, text=True, timeout=3,
                         stdin=subprocess.DEVNULL)
    if out.returncode == 3:                      # dispgrab: no on-screen source window (quit / restarting / not open)
        raise NoWindow(out.stderr.strip()[:200])
    if out.returncode != 0:
        raise RuntimeError(f'dispgrab info rc={out.returncode}: {out.stderr.strip()[:200]}')
    return json.loads(out.stdout)


class WrongWindow(NoWindow):
    """A window matched the source's owner/title but is not the game (e.g. a landscape setup dialog): show the card."""


def _num_list(v, n, name, positive=False):
    if not isinstance(v, (list, tuple)) or len(v) != n or not all(isinstance(x, (int, float)) and not isinstance(x, bool)
                                                                    and math.isfinite(x) for x in v):
        raise ValueError(f'{name} must be a list of {n} finite numbers')
    if any(x < 0 for x in v) or (positive and any(x <= 0 for x in v)):
        raise ValueError(f'{name} must be {"positive" if positive else "non-negative"}')
    return tuple(float(x) for x in v)


def window_source():
    """stream-source.json {"kind": "window"} -> normalised dict (file read only: no ScreenCaptureKit call), else None.
      owner   (required) app name exactly as ScreenCaptureKit reports it, e.g. "MuMu Android Device"
      title   (optional) window-title substring (dispgrab: largest on-screen window of owner containing it, >= 200 pt)
      crop    [x, y, w, h] window-relative points: the portrait game area; or, without crop,
      insets  [top, right, bottom, left] points + aspect [9, 16]: the largest such rect inside, left aligned and
              anchored "top" (default) or "bottom" (anchor; bottom skips a title/tool bar of unknown height above)
      size    [W, H] output pixels (even; default crop x the window's backing scale); fps (default the feed's --fps)
      label   overlay source label (default "LADDER")
      portrait (default true): a matched window that is not taller than wide is not the game -> status card
    Fail closed: an unreadable / malformed file (bad JSON, NaN/Infinity, not an object) or a malformed window config ->
    dict(error=...) = the status card, never a silent fallback to the BlueStacks default. Absent file -> None (default);
    a valid object of another kind (Null's grid) -> None."""
    def bad(msg):
        err = f'stream-source.json: {msg}'[:160]
        return dict(kind='window', error=err, key='error:' + err)

    def no_constant(c):
        raise ValueError(f'{c} is not allowed')
    try:
        text = SOURCE_FILE.read_text()
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as ex:
        return bad(f'unreadable ({type(ex).__name__})')
    try:
        d = json.loads(text, parse_constant=no_constant)
    except (ValueError, RecursionError) as ex:
        return bad(f'invalid JSON ({str(ex)[:80]})')
    if not isinstance(d, dict):
        return bad('not a JSON object')
    if str(d.get('kind', '')).lower() != 'window':
        return None
    try:
        owner = d.get('owner')
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError('owner is required')
        title = d.get('title')
        if title is not None and not isinstance(title, str):
            raise ValueError('title must be a string')
        crop = _num_list(d['crop'], 4, 'crop') if d.get('crop') is not None else None
        if crop is not None and (crop[2] <= 0 or crop[3] <= 0):
            raise ValueError('crop w, h must be positive')
        insets = _num_list(d.get('insets', [0, 0, 0, 0]), 4, 'insets')
        aspect = _num_list(d.get('aspect', [9, 16]), 2, 'aspect', positive=True)
        size = None
        if d.get('size') is not None:
            fs = _num_list(d['size'], 2, 'size', positive=True)
            if max(fs) > 4096 or any(v != int(v) or int(v) % 2 for v in fs):
                raise ValueError('size must be even integers <= 4096')
            size = tuple(int(v) for v in fs)
        fps = d.get('fps')
        if fps is not None and (not isinstance(fps, int) or isinstance(fps, bool) or not 1 <= fps <= 60):
            raise ValueError('fps must be an integer 1..60')
        anchor = d.get('anchor', 'top')
        if anchor not in ('top', 'bottom'):
            raise ValueError('anchor must be "top" or "bottom"')
        portrait = d.get('portrait', True)
        if not isinstance(portrait, bool):
            raise ValueError('portrait must be true/false')
    except (KeyError, ValueError, TypeError, OverflowError) as ex:
        return bad(str(ex))
    src = dict(kind='window', owner=owner, title=title or None, crop=crop, insets=insets, aspect=aspect, anchor=anchor,
               size=size, fps=fps, portrait=portrait, label=str(d.get('label') or 'LADDER')[:60])
    src['key'] = json.dumps({k: src[k] for k in sorted(src)}, sort_keys=True)
    return src


def window_args(src):
    """dispgrab --owner/--title for a window source ([] = dispgrab's BlueStacks default)."""
    if not src or src.get('error'):
        return []
    return ['--owner', src['owner']] + (['--title', src['title']] if src.get('title') else [])


def window_crop(src, info):
    """(crop, size) for a window source and dispgrab info of the matched window; WrongWindow if it is not the game."""
    _, _, w, h = info['bounds']
    if src['portrait'] and not h > w:
        raise WrongWindow(f'{src["owner"]} window {info.get("window_id")} is {w:g}x{h:g} pt (not portrait)')
    if src['crop'] is not None:
        crop = src['crop']
    else:
        t, r, b, l = src['insets']
        aw, ah = w - l - r, h - t - b
        if aw <= 0 or ah <= 0:
            raise WrongWindow(f'window {w:g}x{h:g} pt is smaller than the insets {src["insets"]}')
        ax, ay = src['aspect']
        gw, gh = (ah*ax/ay, ah) if aw/ah > ax/ay else (aw, aw*ay/ax)
        gw, gh = round(gw, 1), round(gh, 1)
        crop = (l, t if src['anchor'] == 'top' else round(h - b - gh, 1), gw, gh)
    x, y, cw, ch = crop
    if x + cw > w + .5 or y + ch > h + .5:
        raise WrongWindow(f'crop {list(crop)} outside the {w:g}x{h:g} pt {src["owner"]} window {info.get("window_id")}')
    s = float(info.get('scale', 2.0))
    size = src['size'] or (int(round(cw*s)) & ~1, int(round(ch*s)) & ~1)
    if size[0] < 2 or size[1] < 2:
        raise WrongWindow(f'crop {list(crop)} too small')
    return tuple(crop), tuple(size)


def driver_running():
    """A bot driver process exists (bracket pattern: never matches this pgrep itself or any shell running it).
    pgrep rc 0 = match, 1 = no match; any other rc or an error = unknown -> True (hold no capture client)."""
    try:
        return subprocess.run(['/usr/bin/pgrep', '-f', '[d]rive\\.py'], capture_output=True, timeout=3).returncode != 1
    except Exception:
        return True                              # unknown: assume a driver, i.e. hold no capture client


def capture_clients():
    """PIDs of every dispgrab stream/grid process (ScreenCaptureKit stream clients of ours), from the process table.
    pgrep rc 1 = none -> []; any other rc or an error = unknown -> None (callers then start nothing: fail closed)."""
    try:
        out = subprocess.run(['/usr/bin/pgrep', '-f', '[d]ispgrab (stream|grid) '], capture_output=True, text=True,
                             timeout=3)
    except Exception:
        return None
    if out.returncode == 1:
        return []
    if out.returncode != 0:
        return None
    toks = out.stdout.split()
    if not toks or not all(t.isdigit() and int(t) > 1 for t in toks):
        return None                              # rc 0 must list positive pids only: anything else = unknown
    return [int(t) for t in toks]


_CG = {}


def cg_windows():
    """On-screen windows from CoreGraphics CGWindowListCopyWindowInfo (WindowServer metadata only: NOT a
    ScreenCaptureKit client, so it cannot interrupt a running SCK stream the way a `dispgrab info/windows` process does:
    replayd drops the active stream when another SCK client process exits, 2026-10-18 05:42:18Z).
    -> [dict(id, owner, title, layer, pid, bounds=[x, y, w, h] points)]. title is '' without screen-recording permission.
    Tests: CLASHER_DISPLAY_CGWIN = a JSON file holding that list. Raises on any failure (callers never fall back to SCK
    while a capture runs)."""
    fake = os.environ.get('CLASHER_DISPLAY_CGWIN')
    if fake:
        return json.loads(Path(fake).read_text())
    import ctypes
    if not _CG:
        V, L = ctypes.c_void_p, ctypes.c_long
        cf = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        cg = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')

        class Rect(ctypes.Structure):
            _fields_ = [('x', ctypes.c_double), ('y', ctypes.c_double), ('w', ctypes.c_double), ('h', ctypes.c_double)]
        for fn, res, args in ((cg.CGWindowListCopyWindowInfo, V, [ctypes.c_uint32, ctypes.c_uint32]),
                              (cg.CGRectMakeWithDictionaryRepresentation, ctypes.c_bool, [V, ctypes.POINTER(Rect)]),
                              (cf.CFArrayGetCount, L, [V]), (cf.CFArrayGetValueAtIndex, V, [V, L]),
                              (cf.CFDictionaryGetValue, V, [V, V]),
                              (cf.CFStringCreateWithCString, V, [V, ctypes.c_char_p, ctypes.c_uint32]),
                              (cf.CFStringGetCString, ctypes.c_bool, [V, ctypes.c_char_p, L, ctypes.c_uint32]),
                              (cf.CFNumberGetValue, ctypes.c_bool, [V, ctypes.c_int, V]),
                              (cf.CFGetTypeID, ctypes.c_ulong, [V]), (cf.CFStringGetTypeID, ctypes.c_ulong, []),
                              (cf.CFNumberGetTypeID, ctypes.c_ulong, []), (cf.CFRelease, None, [V])):
            fn.restype, fn.argtypes = res, args
        keys = {k: cf.CFStringCreateWithCString(None, k.encode(), 0x08000100) for k in
                ('kCGWindowNumber', 'kCGWindowOwnerName', 'kCGWindowName', 'kCGWindowLayer', 'kCGWindowOwnerPID',
                 'kCGWindowBounds')}
        _CG.update(cf=cf, cg=cg, Rect=Rect, keys=keys, str_t=cf.CFStringGetTypeID(), num_t=cf.CFNumberGetTypeID())
    cf, cg, keys = _CG['cf'], _CG['cg'], _CG['keys']

    def get(d, k):
        return cf.CFDictionaryGetValue(d, keys[k])

    def text(v):
        if not v or cf.CFGetTypeID(v) != _CG['str_t']:
            return ''
        buf = ctypes.create_string_buffer(1024)
        return buf.value.decode('utf-8', 'replace') if cf.CFStringGetCString(v, buf, 1024, 0x08000100) else ''

    def num(v):
        out = ctypes.c_int64(0)
        if not v or cf.CFGetTypeID(v) != _CG['num_t'] or not cf.CFNumberGetValue(v, 4, ctypes.byref(out)):
            return None                          # 4 = kCFNumberSInt64Type
        return out.value
    arr = cg.CGWindowListCopyWindowInfo(1 | 16, 0)   # on-screen only | exclude desktop elements; kCGNullWindowID
    if not arr:
        raise RuntimeError('CGWindowListCopyWindowInfo returned NULL')
    try:
        rows = []
        for i in range(cf.CFArrayGetCount(arr)):
            d = cf.CFArrayGetValueAtIndex(arr, i)
            r = _CG['Rect']()
            b = get(d, 'kCGWindowBounds')
            wid = num(get(d, 'kCGWindowNumber'))
            if wid is None or not b or not cg.CGRectMakeWithDictionaryRepresentation(b, ctypes.byref(r)):
                continue
            rows.append(dict(id=wid, owner=text(get(d, 'kCGWindowOwnerName')), title=text(get(d, 'kCGWindowName')),
                             layer=num(get(d, 'kCGWindowLayer')), pid=num(get(d, 'kCGWindowOwnerPID')) or 0,
                             bounds=[r.x, r.y, r.w, r.h]))
        return rows
    finally:
        cf.CFRelease(arr)


def cg_find(src):
    """The window dispgrab's findWindow would pick (largest layer-0 on-screen window of the owner, >= 200 pt, title
    containing the source title), from CGWindowList (no SCK). -> dict(window_id, pid, bounds) or None (absent).
    A title-filtered source whose titles are unreadable (no permission) raises: unknown, never 'absent'."""
    owner = src['owner'] if src and not src.get('error') else 'BlueStacks'
    title = src.get('title') if src else None
    ws = [w for w in cg_windows() if w.get('layer') == 0 and w.get('owner') == owner
          and w['bounds'][2] >= 200 and w['bounds'][3] >= 200]
    if title:
        if ws and not any(w.get('title') for w in ws):
            raise RuntimeError('window titles unreadable via CGWindowList')
        ws = [w for w in ws if title in (w.get('title') or '')]
    if not ws:
        return None
    w = max(ws, key=lambda w: w['bounds'][2]*w['bounds'][3])
    return dict(window_id=w['id'], pid=w.get('pid', 0), bounds=[float(v) for v in w['bounds']])


def list_windows(sck_guard=None):
    """Windows for the Null's grid plan: CGWindowList (no SCK) when it shows titles; else `dispgrab windows` (a
    short-lived SCK client) only if sck_guard() -- Pipeline.sck_block, read fresh right before the query -- returns
    None (no capture child of ours, live or unreaped, no dispgrab capture anywhere, no vision driver, gate open)."""
    why = None
    try:
        ws = [w for w in cg_windows() if w.get('layer') == 0]
        if any(w.get('title') for w in ws):
            return ws
        why = 'CGWindowList shows no titles'
    except Exception as ex:
        why = f'CGWindowList failed ({ex!r})'[:120]
    block = 'no SCK guard' if sck_guard is None else sck_guard()
    if block:
        raise RuntimeError(f'{why}; no dispgrab windows query: {block}')
    out = subprocess.run([GRAB, 'windows'], capture_output=True, text=True, timeout=3, stdin=subprocess.DEVNULL)
    if out.returncode != 0:
        raise RuntimeError(f'dispgrab windows rc={out.returncode}: {out.stderr.strip()[:200]}')
    return json.loads(out.stdout)


def source_plan(sck_guard=None):
    """stream-source.json -> (label, [(window, tile label)]) when it asks for a Null's grid whose windows exist, else None.
    Lenient about the schema: source/mode/kind mentioning 'null'; instances/windows list with window_title/title.
    sck_guard: see list_windows."""
    try:
        d = json.loads(SOURCE_FILE.read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or str(d.get('kind', '')).lower() == 'window':
        return None
    kind = ' '.join(str(d.get(k, '')) for k in ('source', 'mode', 'kind', 'label')).lower()
    if 'null' not in kind:
        return None
    inst = d.get('instances') or d.get('windows') or []
    if not inst:
        return None                              # nothing to show: no ScreenCaptureKit query at all
    wins = list_windows(sck_guard)
    picked = []
    for i, it in enumerate(inst if isinstance(inst, list) else []):
        if not isinstance(it, dict):
            continue
        title = it.get('window') or it.get('window_title') or it.get('title') or ''
        wid = it.get('window_id')
        w = next((w for w in wins if (wid and w['id'] == wid) or (title and title in (w.get('title') or ''))), None)
        if w is None:
            continue
        parts = [f"instance {it.get('n', it.get('instance', i + 1))}", it.get('card'), it.get('team')]
        picked.append((w, str(it.get('label') or ' · '.join(str(p) for p in parts if p))[:60]))
    if not picked:
        return None
    return str(d.get('label') or "DATA CAPTURE · Null's Royale")[:60], picked[:9]


def grid_layout(n, aspect, W, H):
    """Best cols x rows for n windows of aspect w/h in a W x H canvas -> list of even (x, y, w, h)."""
    best = None
    for cols in range(1, n + 1):
        rows = -(-n//cols)
        cw, ch = W//cols, H//rows
        tw, th = (cw, cw/aspect) if cw/aspect <= ch else (ch*aspect, ch)
        if best is None or tw*th > best[0]:
            best = (tw*th, cols, rows, cw, ch, int(tw) & ~1, int(th) & ~1)
    _, cols, rows, cw, ch, tw, th = best
    out = []
    for i in range(n):
        r, c = divmod(i, cols)
        out.append(((c*cw + (cw - tw)//2) & ~1, (r*ch + (ch - th)//2) & ~1, tw, th))
    return out


class Tail:
    """Incremental reader of a growing JSONL file; starts near the end; resets on replacement or truncation."""
    MAX_BUF = 1 << 20

    def __init__(self, path, back=64 << 10):
        self.path, self.back = path, back
        self.pos, self.buf, self.ino = None, b'', None
        self.mtime = 0.

    def lines(self):
        try:
            st = self.path.stat()
        except OSError:
            return []
        self.mtime = st.st_mtime
        if self.ino != (st.st_dev, st.st_ino) or (self.pos is not None and st.st_size < self.pos):
            first = self.ino is None
            self.ino, self.buf = (st.st_dev, st.st_ino), b''
            self.pos = max(0, st.st_size - self.back) if first else 0
        if st.st_size == self.pos:
            return []
        try:
            with open(self.path, 'rb') as f:
                f.seek(self.pos)
                data = f.read(min(st.st_size - self.pos, 4 << 20))
        except OSError:
            return []
        self.pos += len(data)
        parts = (self.buf + data).split(b'\n')
        self.buf = parts.pop()
        if len(self.buf) > self.MAX_BUF:
            self.buf = b''
        rows = []
        for p in parts:
            try:
                rows.append(json.loads(p))
            except ValueError:
                pass
        return rows


class Driver:
    """The active session's logs -> latest display state. Read-only."""
    def __init__(self):
        self.match_dir = None
        self.run = self.match = ''
        self.tails = {}
        self.ground_dy = {}
        try:
            self.ground_dy = {k: float(v['dy']) for k, v in json.loads(Path(OFFSETS).read_text()).items()}
        except Exception as ex:
            log(f'ground offsets unavailable ({ex!r}); fixed box lift')
        self.results = {}
        self.tally = dict(w=0, l=0, d=0)
        self.reset()

    def reset(self):
        self.view = (self.match_dir, None)     # (battle dir, latest frames row): one reference, read by other threads
        self.frame = self.perc = self.decision = self.last_play = None
        self.ubot, self.ubot_t = None, 0.
        self.frame_t = self.perc_t = self.decision_t = self.last_play_t = 0.
        self.plays = deque(maxlen=8)

    @staticmethod
    def _activity(d):
        """Newest frames.jsonl mtime of a battle/run dir (0 if none)."""
        try:
            return (d/'frames.jsonl').stat().st_mtime
        except OSError:
            return 0.

    def find(self):
        """The battle (or single-battle run) dir with the newest frames.jsonl write, over all session dirs."""
        try:
            runs = [d for d in (LOOP/'runs').iterdir() if d.is_dir()]
        except OSError:
            return None
        cands = []
        for r in runs:
            try:
                ms = [m for m in r.iterdir() if m.is_dir() and MATCH_RE.match(m.name)]
            except OSError:
                continue
            cands += ms or [r]
        cands = [(self._activity(c), c) for c in cands]
        cands = [c for c in cands if c[0] > 0]
        return max(cands)[1] if cands else None

    def follow(self, m):
        if m is None or m == self.match_dir:
            return
        self.match_dir = m
        multi = MATCH_RE.match(m.name) is not None
        self.run, self.match = (m.parent.name, m.name) if multi else (m.name, '')
        self.tails = {n: Tail(m/f'{n}.jsonl') for n in ('frames', 'perception', 'decisions')}
        self.reset()
        log(f'following {m}')

    def poll(self):
        now = time.monotonic()
        for name, t in self.tails.items():
            rows = t.lines()
            if not rows:
                continue
            if name == 'frames':
                self.frame, self.frame_t = rows[-1], now
                self.view = (self.match_dir, self.frame)
                for r in reversed(rows):         # the newest translated (poll) frame's units_bot, with its positions
                    ub, us = r.get('units_bot'), r.get('units')
                    if isinstance(ub, list) and isinstance(us, list) and len(ub) == len(us):
                        self.ubot = [dict(card=b.get('card'), owner=b.get('owner', 1), raw=b.get('raw'), x=u[2], y=u[3])
                                     for b, u in zip(ub, us) if isinstance(b, dict) and isinstance(u, list) and len(u) >= 4]
                        self.ubot_t = now
                        break
            elif name == 'perception':
                self.perc, self.perc_t = rows[-1], now
            else:
                for d in rows:
                    self.decision, self.decision_t = d, now
                    # A reserved move may be refused before input (gate, age, PAUSE, dry run).
                    if (d.get('submitted') and type(d.get('tap_id')) is int
                            and d['tap_id'] > 0 and not d.get('tap')):
                        self.last_play, self.last_play_t = d, now
                        self.plays.append(dict(t=time.time(), card=d.get('card'), tile=tile_of(d.get('action'))))

    def logs_t(self):
        """Newest write to the followed battle's frames.jsonl (written at ~10 Hz for every frame, between battles too);
        an empty file just created at session start does not count (the driver then loads models for ~20 s)."""
        t = self.tails.get('frames')
        if t is None:
            return 0.
        try:
            st = t.path.stat()
        except OSError:
            return 0.
        return st.st_mtime if st.st_size > 0 else 0.

    def active(self):
        return time.time() - self.logs_t() < IDLE_S

    def in_battle(self):
        """Restart gate: the last seen state was 'battle' and the logs moved within BATTLE_HOLD_S (a driver that stalls
        or dies mid-battle keeps the gate closed for a minute; a battle that ended normally logs a non-battle state)."""
        return (self.frame or {}).get('state') == 'battle' and time.time() - self.logs_t() < BATTLE_HOLD_S

    def update_tally(self):
        m = self.match_dir
        if m is None or not MATCH_RE.match(m.name):
            return
        for d in sorted(x for x in m.parent.iterdir() if x.is_dir() and MATCH_RE.match(x.name)):
            if d in self.results:
                continue
            try:
                if b'"match_end"' not in (d/'events.jsonl').read_bytes():
                    continue
            except OSError:
                continue
            last = None
            for row in Tail(d/'frames.jsonl', back=256 << 10).lines():
                if row.get('state') == 'battle' and row.get('towers'):
                    last = row
            if last is None:
                self.results[d] = '?'
                continue
            us, them = crowns(last['towers'])
            self.results[d] = 'W' if us > them else 'L' if them > us else 'D'
        rs = [r for d, r in self.results.items() if d.parent == m.parent]
        self.tally = dict(w=rs.count('W'), l=rs.count('L'), d=rs.count('D'))

    def overlay(self, now):
        """Display primitives in Android px (x, y top-left origin of the 1080x1920 guest)."""
        perc, frame = self.perc, self.frame or {}
        battle = self.active() and frame.get('state') == 'battle'
        o = dict(units=[], towers=[], plan=None, play=None)
        if battle and perc is not None and now - self.perc_t < STALE_UNITS_S:
            fresh_bot = self.ubot is not None and now - self.ubot_t <= UBOT_MAX_S
            for u in (unit_rows_bot(perc, self.ubot) if fresh_bot else unit_rows(perc)):
                if u.get('box'):                 # the detector's own box (Android px)
                    x1, y1, x2, y2 = u['box']
                    o['units'].append(dict(x=round(x1), y=round(y1), w=round(x2 - x1), h=round(y2 - y1),
                                           own=u['owner'] == 0, label=u['label'],
                                           score=round(u['score'], 2) if isinstance(u['score'], (int, float)) else None))
                    continue
                ax, ay = tile_to_android(u['x'], u['y'])
                bw, bh, lift = (v*ARENA_S for v in box_shape(u['card'] or u['cls']))
                dy = self.ground_dy.get(u['yolo']) if isinstance(u['yolo'], str) else None
                if dy is not None:
                    lift = bh/2 + dy*TILE_C*ARENA_S
                o['units'].append(dict(x=round(ax - bw/2), y=round(ay - lift - bh/2), w=round(bw), h=round(bh),
                                       own=u['owner'] == 0, label=u['label'],
                                       score=round(u['score'], 2) if isinstance(u['score'], (int, float)) else None))
            for t in perc.get('towers') or ():
                x = {'left': 3.5, 'right': 14.5, 'center': 9}.get(t.get('side'), 9)
                y = (6.5 if t.get('kind') != 'king' else 3) if t.get('owner') == 0 else (25.5 if t.get('kind') != 'king' else 29)
                ax, ay = tile_to_android(x, y)
                o['towers'].append(dict(x=round(ax), y=round(ay + 50), own=t.get('owner') == 0,
                                        text=str(t.get('hp_read', '?')) if t.get('alive') else 'DEAD'))
        d = self.decision
        if battle and d is not None and now - self.decision_t < 2:
            a = d.get('action')
            if a is None or a >= WAIT_ACTION:
                o['plan'] = dict(text='hold')
            else:
                slot = int(a)//576
                cards = (self.hand() or {}).get('cards') or []
                card = d.get('card') or (cards[slot] if slot < len(cards) else f'slot {slot + 1}')
                col, row = tile_of(a)
                x, y = tile_to_android(col + .5, row + .5)
                o['plan'] = dict(text=f'{card} @ ({col},{row})', card=card, x=round(x), y=round(y))
        lp = self.last_play
        if battle and lp is not None and now - self.last_play_t < 3 and lp.get('target_xy'):
            o['play'] = dict(card=lp.get('card'), x=lp['target_xy'][0], y=lp['target_xy'][1],
                             age=round(now - self.last_play_t, 2))
        return o

    def hand(self):
        for src in (self.perc, self.frame):
            if src and src.get('hand'):
                return src['hand']
        return {}


class Pipeline:
    """dispgrab | ffmpeg; started only when allowed() (driver not in a battle); bounded stop; progress watchdog."""
    PIDS = OUT/'pipeline.json'

    def __init__(self, fps, rates, phone, cap_fps=None, cap_size=None):
        self.fps, self.rates, self.phone = fps, rates, phone
        self.cap_fps, self.cap_size = cap_fps or fps, cap_size   # lighter capture (test): fewer/smaller SCK frames
        self.reaped = False                      # stale children of a hard-killed instance: reaped once, gated
        self.grab = self.ff = None
        self.size = self.crop = self.window = None
        self.started_t = 0.
        self.backoff, self.next_try = 2., 0.
        self.starts = 0
        self.last_error = ''
        self.deferred = False
        self.progress = OUT/'ffmpeg-progress.txt'
        self.last_frame_n, self.last_frame_t = -1, 0.
        self.kind = None                         # display | grid (dispgrab | ffmpeg), legacy (ffmpeg from :8766), card
        self.tiles = None
        self.legacy_fails, self.legacy_block_until, self.legacy_fallback = 0, 0., False
        self.source = None                       # window_source() (kind 'window') or None = BlueStacks default; set by main
        self.src_key = None                      # the source key of the running display capture
        self.src_label = None                    # ... and its label (the pending self.source may differ / be invalid)
        self.allowed_fn = None                   # fresh "no battle" check (main's allowed); None = ungated (tests)
        self.log_off = 0                         # dispgrab.log size when the current capture started: its stats only
        self.started_wall = 0.
        self.stale_restarts = 0                  # consecutive stale-capture recoveries (backoff + card between them)
        self.last_stale = ''
        self.win_check_t = self.win_missing_t = 0.
        self.window_probe = None                 # last non-SCK window check result (state.json)
        self.card_why = ''

    @staticmethod
    def fresh_allowed(allowed_fn):
        """A fresh 'driver not in a battle' read, taken right before a signal; an error counts as 'in a battle'.
        allowed_fn.fresh (main's allowed) re-reads the process table too instead of the cached vision check."""
        if allowed_fn is None:
            return True
        try:
            return bool(getattr(allowed_fn, 'fresh', allowed_fn)())
        except Exception:
            return False

    def stale_entries(self):
        try:
            old = json.loads(self.PIDS.read_text())
        except (OSError, ValueError):
            return []
        if not isinstance(old, dict):
            return []
        return [(pid, exe) for pid, exe in ((old.get('dispgrab'), GRAB), (old.get('ffmpeg'), FFMPEG))
                if isinstance(pid, int) and not isinstance(pid, bool) and pid > 1]

    UNKNOWN = '?unknown'                         # stale_cmd: the process check itself failed (never read as 'gone')

    @staticmethod
    def stale_cmd(pid, exe):
        """The command of pid if it is still our pipeline child (exe + pipeline arguments); None only if positively
        absent (ps rc 1 with no output) or the pid now runs something else; Pipeline.UNKNOWN if ps failed / timed out /
        gave an unexpected rc (callers treat unknown as alive: no query, start, cleanup success or record removal)."""
        try:
            out = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True, timeout=3)
        except Exception:                        # timeout, OSError, anything: unknown, not gone
            return Pipeline.UNKNOWN
        cmd = out.stdout.strip()
        if out.returncode == 1 and not cmd:
            return None                          # no such process
        if out.returncode != 0 or not cmd:
            return Pipeline.UNKNOWN
        return cmd if cmd.startswith(exe) and (RTSP in cmd or ' stream ' in cmd or ' grid ' in cmd) else None

    def stale_pids(self):
        """[(pid, cmd)] of recorded children still alive OR of unknown state (cmd == UNKNOWN): both block."""
        return [(pid, cmd) for pid, exe in self.stale_entries() for cmd in [self.stale_cmd(pid, exe)] if cmd]

    def stale_alive(self):
        return bool(self.stale_pids())

    def reap_stale(self, allowed_fn=None):
        """Children of an earlier display_feed that was killed hard: terminate them only if pid AND command match.
        Before EVERY signal (TERM, and the KILL 2 s later) the identity is re-validated and then a fresh allowed_fn()
        read is taken; in a battle nothing is signalled and False is returned (cleanup stays pending, retried later).
        True = nothing stale left (pipeline.json removed)."""
        for pid, exe in self.stale_entries():
            for sig in (signal.SIGTERM, signal.SIGKILL):
                cmd = self.stale_cmd(pid, exe)   # blocking ps: validated first, the battle check comes after it
                if cmd is None:
                    break                        # gone (or the pid now belongs to something else)
                if cmd == Pipeline.UNKNOWN:
                    log(f'stale pipeline child {pid}: process check failed; record kept, retried later')
                    return False                 # never signal or forget an identity we could not verify
                if not self.fresh_allowed(allowed_fn):
                    self.deferred = True
                    log(f'stale pipeline child {pid}: cleanup deferred (driver in a battle)')
                    return False
                log(f'{"terminating" if sig == signal.SIGTERM else "killing"} stale pipeline child {pid}: {cmd[:120]}')
                try:
                    os.kill(pid, sig)
                except OSError:
                    break
                t_end = time.monotonic() + 2.
                while time.monotonic() < t_end:
                    try:
                        os.kill(pid, 0)
                    except OSError:
                        break
                    time.sleep(.05)
                else:
                    continue                     # still alive after 2 s: escalate (re-validated + re-gated above)
                break
        if self.stale_pids():
            return False                         # something survived: keep pending
        try:
            self.PIDS.unlink()
        except OSError:
            pass
        return True

    def running(self):
        if self.kind in ('legacy', 'card', 'frames'):
            return self.ff is not None and self.ff.poll() is None
        return self.grab is not None and self.grab.poll() is None and self.ff is not None and self.ff.poll() is None

    def legacy_args(self):
        """The pre-display-r1 publisher: the driver's composited :8766 MJPEG (10 FPS) -> the same RTSP paths."""
        a = [FFMPEG, '-hide_banner', '-nostdin', '-loglevel', 'warning', '-threads', '2', '-filter_threads', '2',
             '-filter_complex_threads', '2', '-progress', str(self.progress), '-stats_period', '2',
             '-rw_timeout', '5000000', '-fflags', '+nobuffer', '-flags', '+low_delay',
             '-use_wallclock_as_timestamps', '1', '-f', 'mpjpeg', '-probesize', '32768', '-analyzeduration', '0',
             '-i', 'http://127.0.0.1:8766/stream',
             '-filter_complex', '[0:v]fps=10,split=2[a][b];[a]scale=540:960:flags=fast_bilinear,format=yuv420p[p];[b]format=yuv420p[d]']
        for lab, name, rate, peak, buf in (('p', 'phone', '380k', '450k', '100k'), ('d', 'desktop', '1000k', '1200k', '250k')):
            if VCODEC == 'h264_videotoolbox':
                enc = ['-c:v', 'h264_videotoolbox', '-allow_sw', '0', '-realtime', '1', '-prio_speed', '1', '-constant_bit_rate', '1']
            else:
                enc = ['-c:v', VCODEC, '-preset', 'ultrafast', '-tune', 'zerolatency']
            a += ['-map', f'[{lab}]', '-an'] + enc + ['-profile:v', 'baseline', '-bf', '0', '-g', '10', '-b:v', rate,
                  '-maxrate', peak, '-bufsize', buf, '-threads', '2', '-fps_mode', 'cfr', '-flush_packets', '1',
                  '-muxdelay', '0', '-max_delay', '0', '-rtsp_transport', 'tcp', '-f', 'rtsp', f'{RTSP}/{name}']
        return a

    def start_legacy(self):
        with open(OUT/'ffmpeg.log', 'ab') as flog:
            flog.write(f'{time.strftime("%FT%TZ", time.gmtime())} start legacy ffmpeg from :8766\n'.encode()); flog.flush()
            self.ff = subprocess.Popen(self.legacy_args(), stdin=subprocess.DEVNULL, stdout=flog, stderr=flog)
        self.grab, self.kind = None, 'legacy'
        self.PIDS.write_text(json.dumps(dict(ffmpeg=self.ff.pid)))
        self.starts += 1
        self.started_t = time.monotonic()
        self.last_frame_n, self.last_frame_t = -1, time.monotonic()
        log(f'pipeline start #{self.starts}: LEGACY ffmpeg pid {self.ff.pid} from :8766')

    def sck_block(self, allowed_fn=None):
        """Why no ScreenCaptureKit client of ours (dispgrab info / windows / stream / grid) may start right now, or
        None. Read fresh on every call (never a cached loop value), fail closed:
          - a capture child object of ours exists (alive, or exited but not positively reaped by stop());
          - a pipeline.json child of an earlier feed is still alive;
          - any dispgrab stream/grid process exists, or pgrep failed;
          - a vision driver process exists (its bsgrab is an SCK client), or pgrep failed;
          - the gate check (allowed_fn, else self.allowed_fn) says battle or errors."""
        if self.grab is not None:
            return f'capture child {self.grab.pid} not reaped'
        stale = self.stale_pids()
        if stale:
            return f'earlier capture child alive: {[pid for pid, _ in stale]}'
        pids = capture_clients()
        if pids is None:
            return 'capture client check failed (pgrep)'
        if pids:
            return f'another dispgrab capture is alive: {pids[:4]}'
        if driver_running():
            return 'vision driver present (or pgrep failed)'
        if not self.fresh_allowed(allowed_fn or self.allowed_fn):
            return 'battle in progress (gate)'
        # the gate read may block (log scan) and short-circuits its own vision check outside battles: re-read the
        # process table last, so a vision driver or capture that appeared meanwhile still blocks
        if driver_running():
            return 'vision driver present (appeared during the checks, or pgrep failed)'
        pids = capture_clients()
        if pids is None or pids:
            return f'capture client appeared during the checks: {pids}'
        return None

    def sole_client_ok(self, allowed_fn=None):
        """sck_block() as an exception: raised before every dispgrab call; nothing is queried or started."""
        why = self.sck_block(allowed_fn)
        if why:
            raise RuntimeError(f'no SCK client start: {why}')

    def _spawn_capture(self, cmd, ff_args, glog, flog):
        """Capture child first, its identity recorded in pipeline.json at once, then the encoder. If the encoder cannot
        start, the capture is stopped via stop() (gated, bounded, reaped); if it is not reaped, self.grab and the record
        are kept (sck_block then refuses every SCK client until a later stop() reaps it)."""
        self.grab = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=glog, stdin=subprocess.DEVNULL)
        self.PIDS.write_text(json.dumps(dict(dispgrab=self.grab.pid)))
        try:
            self.ff = subprocess.Popen(ff_args, stdin=self.grab.stdout, stdout=flog, stderr=flog)
        except Exception:
            self.grab.stdout.close()
            self.stop('encoder start failed')
            raise
        self.grab.stdout.close()                 # only ffmpeg holds the pipe's read end
        self.PIDS.write_text(json.dumps(dict(dispgrab=self.grab.pid, ffmpeg=self.ff.pid)))

    def mark_log(self):
        try:
            self.log_off = (OUT/'dispgrab.log').stat().st_size
        except OSError:
            self.log_off = 0
        self.started_wall = time.time()

    def start_grid(self, plan):
        """Null's data capture: one dispgrab grid process (one SCK stream per window) -> the same encoder/paths."""
        label, picked = plan
        W, H = CANVAS
        if not self.fresh_allowed(self.allowed_fn):   # the gate, re-checked right before a capture client starts
            self.deferred = True
            return
        self.sole_client_ok(self.allowed_fn)
        b = picked[0][0]['bounds']
        rects = grid_layout(len(picked), b[2]/b[3] if b[3] else 9/16, W, H)
        cmd = [GRAB, 'grid', '--size', f'{W},{H}', '--fps', str(self.fps), '--seconds', '0', '--gate', str(GATE_FILE)]
        for (w, _), (x, y, tw, th) in zip(picked, rects):
            cmd += ['--tile', f"{w['id']}:{x},{y},{tw},{th}"]
        self.size, self.crop, self.window = (W, H), None, None
        self.mark_log()
        with open(OUT/'dispgrab.log', 'ab') as glog, open(OUT/'ffmpeg.log', 'ab') as flog:
            stamp = time.strftime('%FT%TZ', time.gmtime())
            glog.write(f'{stamp} start {" ".join(cmd[1:])}\n'.encode()); glog.flush()
            flog.write(f'{stamp} start ffmpeg grid {W}x{H}@{self.fps}\n'.encode()); flog.flush()
            self.kind = 'grid'                   # before the spawn: a partial start is stopped as a capture
            self._spawn_capture(cmd, self.ffargs(), glog, flog)
        sx = 1080/W                              # overlay space: Android px of a 1080-wide frame
        self.tiles = dict(label=label, ids=[w['id'] for w, _ in picked],
                          tiles=[dict(x=round(x*sx), y=round(y*sx), w=round(tw*sx), h=round(th*sx), label=lab)
                                 for (_, lab), (x, y, tw, th) in zip(picked, rects)])
        self.starts += 1
        self.started_t = time.monotonic()
        self.last_frame_n, self.last_frame_t = -1, time.monotonic()
        self.grid_t = time.monotonic()
        log(f'pipeline start #{self.starts}: GRID {len(picked)} window(s) {self.tiles["ids"]} dispgrab pid {self.grab.pid} '
            f'ffmpeg pid {self.ff.pid}')

    def start_frames(self, drv):
        """Driver session in yield mode: the driver's OWN recorded frames (runs/<s>/mNN/video/NNNNNN.jpg, written for
        every frame anyway) -> constant 30 FPS NV12 (last frame repeated) -> the same encoder. No capture client, no
        load on the driver's page; the browser overlay matches these frames exactly."""
        self.size = (720, 1280)
        self.crop = None
        with open(OUT/'ffmpeg.log', 'ab') as flog:
            flog.write(f'{time.strftime("%FT%TZ", time.gmtime())} start frames ffmpeg (driver video frames)\n'.encode()); flog.flush()
            self.ff = subprocess.Popen(self.ffargs(in_fps=self.fps, desktop_rate=('3000k', '3000k', '600k')), stdin=subprocess.PIPE,
                                       stdout=flog, stderr=flog, bufsize=0)
        self.grab, self.kind = None, 'frames'
        self.PIDS.write_text(json.dumps(dict(ffmpeg=self.ff.pid)))
        self.starts += 1
        self.started_t = time.monotonic()
        self.last_frame_n, self.last_frame_t = -1, time.monotonic()
        self.frames_stats = dict(new=0, repeat=0, misses=0, t=time.monotonic())
        threading.Thread(target=self._frames_writer, args=(self.ff, drv), name='frames', daemon=True).start()
        log(f'pipeline start #{self.starts}: FRAMES ffmpeg pid {self.ff.pid} (driver video frames, 720x1280 -> {self.fps} fps)')

    def _frames_writer(self, ff, drv):
        import cv2
        import numpy as np
        w, h = self.size
        black = np.zeros(w*h*3//2, np.uint8); black[w*h:] = 128
        frame, shown, nxt = black.tobytes(), None, time.monotonic()
        q = (w//2)*(h//2)
        st = self.frames_stats
        self.frames_new_t = time.monotonic()

        def load(path):
            """A complete JPEG (non-empty, ends with EOI) decoded, else None: the driver's cv2.imwrite is not atomic."""
            try:
                data = np.fromfile(str(path), np.uint8)
                if data.size < 4 or data[-2] != 0xFF or data[-1] != 0xD9:
                    return None
                return cv2.imdecode(data, cv2.IMREAD_COLOR)
            except (OSError, ValueError, cv2.error):
                return None
        try:
            while ff.poll() is None:
                m, row = drv.view
                n = row.get('n') if isinstance(row, dict) else None
                if m is not None and isinstance(n, int) and (str(m), n) != shown:
                    img = None
                    for k in (n, n - 1, n - 2, n - 3):   # the driver's writer queue may lag a little
                        if shown is not None and (str(m), k) == shown:
                            break                        # nothing newer is complete yet: keep the current frame
                        img = load(m/'video'/f'{k:06d}.jpg')
                        if img is not None:
                            break
                    if img is not None:
                        if img.shape[:2] != (h, w):
                            img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
                        flat = cv2.cvtColor(img, cv2.COLOR_BGR2YUV_I420).ravel()
                        uv = np.empty((h//2, w), np.uint8)
                        uv[:, 0::2] = flat[w*h:w*h + q].reshape(h//2, w//2)
                        uv[:, 1::2] = flat[w*h + q:w*h + 2*q].reshape(h//2, w//2)
                        frame = flat[:w*h].tobytes() + uv.tobytes()
                        shown = (str(m), k)              # the frame actually shown; frame n is retried if k < n
                        st['new'] += 1
                        self.frames_new_t = time.monotonic()
                    else:
                        st['misses'] += 1
                else:
                    st['repeat'] += 1
                ff.stdin.write(frame)
                nxt += 1/self.fps
                time.sleep(max(0., nxt - time.monotonic()))
                if time.monotonic() - nxt > .5:
                    nxt = time.monotonic()
        except (OSError, ValueError):
            pass

    def start_card(self, why):
        """No source window: a rendered status card at 10 FPS through the same encoder, so the stream never blanks."""
        self.size = self.size or (1044, 1856)
        self.crop = None
        with open(OUT/'ffmpeg.log', 'ab') as flog:
            flog.write(f'{time.strftime("%FT%TZ", time.gmtime())} start card ffmpeg ({why})\n'.encode()); flog.flush()
            self.ff = subprocess.Popen(self.ffargs(in_fps=10), stdin=subprocess.PIPE, stdout=flog, stderr=flog, bufsize=0)
        self.grab, self.kind, self.card_why = None, 'card', why
        self.PIDS.write_text(json.dumps(dict(ffmpeg=self.ff.pid)))
        self.starts += 1
        self.started_t = time.monotonic()
        self.last_frame_n, self.last_frame_t = -1, time.monotonic()
        self.card_t = time.monotonic()
        threading.Thread(target=self._card_writer, args=(self.ff,), name='card', daemon=True).start()
        log(f'pipeline start #{self.starts}: CARD ffmpeg pid {self.ff.pid} ({why})')

    def card_text(self, src):
        """The status card's short lines (the time is appended by the writer)."""
        wait = max(0, round(self.next_try - time.monotonic()))
        if (self.card_why or '').startswith('capture stalled'):
            return ['Video capture stalled', f'reconnecting, attempt {self.stale_restarts}', f'retry in {wait} s']
        if (self.card_why or '').startswith('capture start failed'):
            return ['Video capture unavailable', 'retrying', f'retry in {wait} s']
        return ['Waiting for the', f'{src["owner"]} window' if src and src.get('owner') and not src.get('error')
                else 'game window']

    def _card_writer(self, ff):
        import cv2
        import numpy as np
        w, h = self.size
        frame, t_render, nxt = None, 0., time.monotonic()
        try:
            while ff.poll() is None:
                now = time.monotonic()
                if now - t_render > 1:
                    t_render = now
                    pt = time.strftime('%H:%M', time.localtime())
                    try:
                        pt = subprocess.run(['/bin/date', '+%H:%M %Z'], capture_output=True, text=True, timeout=1,
                                            env=dict(os.environ, TZ='America/Los_Angeles')).stdout.strip() or pt
                    except Exception:
                        pass
                    img = render_card(self.card_text(self.source) + [pt], w, h)
                    flat = cv2.cvtColor(img, cv2.COLOR_BGR2YUV_I420).ravel()
                    q = (w//2)*(h//2)
                    yy = flat[:w*h]
                    u, v = flat[w*h:w*h + q].reshape(h//2, w//2), flat[w*h + q:w*h + 2*q].reshape(h//2, w//2)
                    uv = np.empty((h//2, w), np.uint8); uv[:, 0::2] = u; uv[:, 1::2] = v
                    frame = yy.tobytes() + uv.tobytes()
                ff.stdin.write(frame)
                nxt += .1
                time.sleep(max(0., nxt - time.monotonic()))
        except (OSError, ValueError):
            pass

    def ffargs(self, in_fps=None, desktop_rate=None):
        w, h = self.size
        pw, ph = self.phone
        a = [FFMPEG, '-hide_banner', '-nostdin', '-loglevel', 'warning', '-threads', '2', '-filter_threads', '2',
             '-filter_complex_threads', '2', '-progress', str(self.progress), '-stats_period', '2',
             '-fflags', '+nobuffer', '-flags', '+low_delay',
             '-f', 'rawvideo', '-pix_fmt', 'nv12', '-video_size', f'{w}x{h}', '-framerate', str(in_fps or self.fps),
             '-use_wallclock_as_timestamps', '1', '-thread_queue_size', '8', '-i', 'pipe:0',
             '-filter_complex', f'[0:v]split=2[d][a];[a]scale={pw}:{ph}:flags=bilinear[p]']
        for lab, name in (('d', 'desktop'), ('p', 'phone')):
            rate, peak, buf = desktop_rate if (desktop_rate and name == 'desktop') else self.rates[name]
            if VCODEC == 'h264_videotoolbox':
                enc = ['-c:v', 'h264_videotoolbox', '-allow_sw', '0', '-realtime', '1', '-prio_speed', '1',
                       '-constant_bit_rate', '1']
            else:
                enc = ['-c:v', VCODEC, '-preset', 'ultrafast', '-tune', 'zerolatency']
            a += ['-map', f'[{lab}]', '-an'] + enc + ['-profile:v', 'baseline', '-bf', '0', '-g', str(self.fps),
                  '-b:v', rate, '-maxrate', peak, '-bufsize', buf,
                  '-color_range', 'tv', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
                  '-fps_mode', 'cfr', '-r', str(self.fps), '-flush_packets', '1', '-muxdelay', '0', '-max_delay', '0',
                  '-rtsp_transport', 'tcp', '-f', 'rtsp', f'{RTSP}/{name}']
        return a

    def probe(self, allowed_fn=None):
        """(info, crop, size) of the current source's window: one dispgrab info query (an SCK client), made only after a
        fresh sole_client_ok (RuntimeError otherwise: nothing queried). NoWindow/WrongWindow if absent."""
        src = self.source
        if src and src.get('error'):
            raise WrongWindow(src['error'])
        self.sole_client_ok(allowed_fn)
        info = grab_info(src)
        if src:
            crop, size = window_crop(src, info)
        else:
            crop = game_crop(info)
            s = float(info.get('scale', 2.0))
            size = (int(round(crop[2]*s)) & ~1, int(round(crop[3]*s)) & ~1)
            if self.cap_size:
                size = self.cap_size
        return info, crop, size

    def start(self, allowed):
        src = self.source
        if not self.fresh_allowed(allowed):      # fresh gate first: in a battle nothing is queried or started
            self.deferred = True
            return
        info, crop, size = self.probe(allowed)   # probe() runs sole_client_ok (incl. vision) before dispgrab info
        if not self.fresh_allowed(allowed):      # the gate is re-checked after the (up to 4 s) window query
            self.deferred = True
            return
        self.sole_client_ok(allowed)             # re-checked right before the stream client starts
        s = float(info.get('scale', 2.0))
        cap_fps = min(self.fps, src['fps']) if src and src.get('fps') else self.cap_fps
        grab_cmd = [GRAB, 'stream', '--crop', ','.join(map(str, crop)), '--size', f'{size[0]},{size[1]}',
                    '--fps', str(cap_fps), '--seconds', '0', '--gate', str(GATE_FILE)] + window_args(src)
        self.size, self.crop, self.window = size, crop, (info.get('window_id'), s, tuple(info['bounds']))
        self.kind = 'display'
        self.src_key = src['key'] if src else None
        self.src_label = src['label'] if src else None
        self.mark_log()
        self.win_check_t, self.win_missing_t = time.monotonic(), 0.
        with open(OUT/'dispgrab.log', 'ab') as glog, open(OUT/'ffmpeg.log', 'ab') as flog:
            stamp = time.strftime('%FT%TZ', time.gmtime())
            glog.write(f'{stamp} start {" ".join(grab_cmd[1:])}\n'.encode()); glog.flush()
            flog.write(f'{stamp} start ffmpeg {size[0]}x{size[1]}@{self.fps}\n'.encode()); flog.flush()
            self._spawn_capture(grab_cmd, self.ffargs(in_fps=cap_fps), glog, flog)
        self.starts += 1
        self.started_t = time.monotonic()
        self.last_frame_n, self.last_frame_t = -1, time.monotonic()
        log(f'pipeline start #{self.starts}: dispgrab pid {self.grab.pid} ffmpeg pid {self.ff.pid} '
            f'{size[0]}x{size[1]}@{self.fps} crop {crop} window {self.window[0]}'
            + (f' owner {src["owner"]!r}' + (f' title {src["title"]!r}' if src.get('title') else '') if src else ''))

    def stop(self, why, allowed_fn=None):
        """Stop both children. While a capture child (dispgrab) is alive, every signal (TERM to each child, the KILL
        escalation after 2 s) is preceded by a fresh allowed check (allowed_fn, else self.allowed_fn); in a battle
        nothing more is signalled, the state is kept and False is returned (the caller retries later). True = stopped."""
        gate = allowed_fn or self.allowed_fn
        procs = [p for p in (self.grab, self.ff) if p is not None]

        def may_signal():
            capture = self.grab is not None and self.grab.poll() is None
            return not capture or self.fresh_allowed(gate)
        for p in procs:
            if p.poll() is None:
                if not may_signal():
                    self.deferred = True
                    return False
                p.terminate()
        deadline = time.monotonic() + 2
        for p in procs:
            try:
                p.wait(max(.05, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                if not may_signal():             # TERM sent; the KILL waits for the gate
                    self.deferred = True
                    return False
                p.kill()
                try:
                    p.wait(2.)
                except subprocess.TimeoutExpired:
                    pass                         # not reaped: checked below, state kept
        unreaped = [p for p in procs if p.poll() is None]
        if unreaped:
            self.last_error = ('not reaped after KILL: ' + ', '.join(f'{"dispgrab" if p is self.grab else "ffmpeg"} '
                                                                     f'{p.pid}' for p in unreaped))
            log(f'pipeline stop ({why}): {self.last_error}; kept, retried later (no replacement until reaped)')
            return False
        if self.kind in ('card', 'frames') and self.ff is not None and self.ff.stdin:
            try:
                self.ff.stdin.close()            # after ffmpeg is gone: the (unbuffered) writer gets EPIPE and ends
            except OSError:
                pass
        if procs:
            log(f'pipeline stopped ({why}): ' + ', '.join(f'{"dispgrab" if p is self.grab else "ffmpeg"} rc {p.returncode}'
                                                         for p in procs))
        self.grab = self.ff = None
        self.kind = None
        self.tiles = None
        self.src_key = self.src_label = None
        try:
            self.PIDS.unlink()
        except OSError:
            pass
        return True

    @staticmethod
    def tail_text(path, n=2048):
        try:
            with open(path, 'rb') as f:
                f.seek(0, 2)
                f.seek(max(0, f.tell() - n))
                return f.read().decode(errors='replace')
        except OSError:
            return ''

    STATS_RE = re.compile(r'^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ) dispgrab: stats .*last_capture_age (-?[\d.]+) s', re.M)

    def capture_stats(self):
        """(wall time, last_capture_age) of the newest dispgrab stats line written by THE CURRENT capture (log text
        after the offset taken at its start: an earlier process's ages never count), or None if it wrote none yet."""
        path = OUT/'dispgrab.log'
        try:
            size = path.stat().st_size
            if size < self.log_off:
                self.log_off = 0                 # log truncated/replaced since the start: read it all
            with open(path, 'rb') as f:
                f.seek(max(self.log_off, size - 8192))
                txt = f.read().decode(errors='replace')
        except OSError:
            return None
        m = self.STATS_RE.findall(txt)
        if not m:
            return None
        try:
            import calendar
            return calendar.timegm(time.strptime(m[-1][0], '%Y-%m-%dT%H:%M:%SZ')), float(m[-1][1])
        except ValueError:
            return None

    def capture_age(self):
        """Seconds since dispgrab's newest captured frame per its newest stats line of THIS capture (None if unknown)."""
        st = self.capture_stats()
        return st[1] if st and st[1] >= 0 else None

    def capture_stale(self, now_wall=None):
        """Why the running capture counts as stalled, else None. From the current capture's stats lines only:
        (a) a stats line says no frame for >= STALE_S (dispgrab emits the last frame forever: emitted fps stays 30
        while captured is 0 after replayd drops the stream without any delegate error, 2026-10-18 05:42:18Z);
        (b) no stats line for STATS_LATE_S (process stopped/hung; first line due 10 s after its stream started);
        (c) stats say no frame was ever captured once the capture ran STATS_LATE_S."""
        if self.kind not in ('display', 'grid'):
            return None
        now_wall = now_wall or time.time()
        st = self.capture_stats()
        ref = st[0] if st else self.started_wall
        if now_wall - ref > STATS_LATE_S:
            return f'no dispgrab stats line for {now_wall - ref:.0f} s'
        if st is None:
            return None
        if st[1] >= STALE_S:
            return f'no captured frame for {st[1]:.1f} s'
        if st[1] < 0 and now_wall - self.started_wall > STATS_LATE_S:
            return 'no frame captured since start'
        if now_wall - self.started_wall > HEALTHY_S and st[1] < 2:
            self.stale_restarts = 0              # healthy for a while: the next stall restarts at once again
        return None

    def frames_done(self):
        txt = self.tail_text(self.progress)
        if not txt:
            return None
        ns = re.findall(r'^frame=(\d+)', txt, re.M)
        return int(ns[-1]) if ns else None

    def count_legacy_failure(self, now):
        if self.kind != 'legacy':
            return
        self.legacy_fails = self.legacy_fails + 1 if now - self.started_t < 25 else 1
        if self.legacy_fails >= 3:
            self.legacy_fails, self.legacy_fallback = 0, True

    def tick(self, allowed_fn, want='display', plan=None):
        """Called ~10x/s from the main loop: watchdog + gated (re)start. Mid-battle nothing is stopped or started:
        a child that exits takes its partner down by itself (EPIPE/EOF); we only reap."""
        now = time.monotonic()
        self.allowed_fn = allowed_fn             # stop() re-reads it right before every signal
        allowed = allowed_fn()
        cap = ('display', 'grid')                # kinds that own a ScreenCaptureKit client
        # in a battle no capture client may start: the stream is then served by the driver's own page (legacy)
        want = want if (allowed or want not in cap) else 'frames'
        if want == 'legacy' and (self.legacy_fallback or now < self.legacy_block_until):
            want = 'card'                        # the driver page is not answering: show the status card meanwhile
        if not self.reaped:
            if not self.stale_alive():
                self.reaped = True               # nothing stale: no reason to wait for the gate
            elif not allowed or not self.reap_stale(allowed_fn):
                self.deferred = True             # the stale publisher keeps serving the stream until the battle ends
                return
            else:
                self.reaped = True
        if (self.kind == 'card' and self.running() and want == 'display' and now >= self.next_try
                and now - self.card_t > 5):
            self.card_t = now                    # is a source window back (or a stall retry due)? then leave the card
            if self.window_present():
                if self.stop('capture retry due' if self.card_why.startswith(('capture stalled', 'capture start failed'))
                             else 'source window is back'):
                    self.next_try = 0.
        if self.grab is not None or self.ff is not None:
            regrid = (self.kind == 'grid' and want == 'grid' and plan is not None and self.tiles is not None
                      and [w['id'] for w, _ in plan[1]] != self.tiles['ids'])
            if (self.kind == 'grid' and plan is not None and self.tiles is not None
                    and [w['id'] for w, _ in plan[1]] == self.tiles['ids']):
                self.tiles['label'] = plan[0]    # label-only changes: no capture restart
                for t, (_, lab) in zip(self.tiles['tiles'], plan[1]):
                    t['label'] = lab
            resource = (self.kind == 'display' and want == 'display'
                        and self.src_key != (self.source['key'] if self.source else None))
            if (self.running() and (self.kind != want or regrid or resource)
                    and not (self.kind == 'card' and want == 'display')
                    and (allowed or self.kind not in cap)):      # a running capture is never stopped mid-battle
                if not self.stop('stream-source.json changed' if resource else f'switching {self.kind} -> {want}'):
                    return                       # a battle began during the checks: nothing signalled
                self.next_try = 0.
                self.backoff = 2.
            elif self.running():
                why = self.capture_stale() if self.kind in cap else None
                if why:
                    if not allowed:
                        self.deferred = True     # a capture client is never stopped mid-battle: after it
                        self.last_stale = f'{why} (recovery deferred: battle)'
                        return
                    self.recover_stale(why, now)
                    return
                n = self.frames_done()
                if n is not None and n != self.last_frame_n:
                    self.last_frame_n, self.last_frame_t = n, now
                    if now - self.started_t > 30:
                        self.backoff = 2.
                elif now - self.last_frame_t > 20:
                    if allowed or self.kind not in cap:
                        self.last_error = 'encoder made no progress for 20 s'
                        self.count_legacy_failure(now)
                        if not self.stop(self.last_error):
                            return
                        if self.legacy_fallback:
                            self.next_try = now
                    else:
                        self.deferred = True
                return
            self.count_legacy_failure(now)
            self.last_error = (f'exited: dispgrab rc {self.grab.poll() if self.grab else None}, '
                               f'ffmpeg rc {self.ff.poll() if self.ff else None}')
            alive = [p for p in (self.grab, self.ff) if p is not None and p.poll() is None]
            if self.grab is not None and self.grab in alive and not allowed:   # never signal a capture child mid-battle
                self.deferred = True
                return
            prev = self.kind
            if not self.stop(self.last_error):   # capture first (stop's order), each child reaped, else state kept
                return
            self.next_try = now if self.legacy_fallback else now + self.backoff
            self.backoff = min(60., self.backoff*2)
            if prev == 'display':                # a display child exited early (e.g. SCK start failed, encoder died)
                self.failure_card(want)
        if now < self.next_try:
            return
        self.deferred = not allowed
        self.allowed_fn = allowed_fn
        try:
            if want == 'legacy':
                self.start_legacy()
            elif want == 'grid' and plan is not None:
                self.start_grid(plan)
            elif want == 'frames':
                self.start_frames(self.drv)
            elif want == 'card':
                self.start_card('driver page not answering')
                if self.legacy_fallback:         # the cooldown runs from the card's actual start
                    self.legacy_fallback, self.legacy_block_until = False, now + 30
            else:
                self.start(allowed_fn)
        except NoWindow as ex:
            self.last_error = f'no source window: {ex}'[:200]
            if not self.stop('no window'):
                return
            log(f'pipeline: {self.last_error}')
            self.start_card('no source window')
        except Exception as ex:
            self.last_error = repr(ex)[:200]
            log(f'pipeline start failed: {self.last_error}')
            if not self.stop('start failed'):
                return                           # a child not reaped: identity kept, no card, no new SCK client
            self.next_try = now + self.backoff
            self.backoff = min(60., self.backoff*2)
            self.failure_card(want)

    def failure_card(self, want):
        """After a failed display capture (a start exception or an early child exit) that stop() fully reaped: the
        ffmpeg-only status card publishes through the backoff (no SCK client). Never while any child object remains
        (an unreaped capture keeps its identity; no card, no new SCK client)."""
        if want != 'display' or self.grab is not None or self.ff is not None:
            return
        try:
            self.start_card('capture start failed')
        except Exception as ex:
            log(f'card start failed: {ex!r}'[:200])

    def recover_stale(self, why, now):
        """Stop the stalled capture (both children terminated AND reaped by stop(), so the replacement is the only SCK
        client), then restart: the first stall at once, repeated ones after 4, 8, ... 60 s with the status card shown
        in between (ffmpeg only, no capture client)."""
        self.last_stale = why
        log(f'capture stale: {why}; stopping dispgrab {self.grab.pid if self.grab else None}')
        if not self.stop(f'capture stale: {why}'):
            return                               # a battle began during the checks: nothing (more) signalled
        self.stale_restarts += 1
        delay = 0. if self.stale_restarts == 1 else min(60., 2.**min(self.stale_restarts, 6))   # 4, 8, ... 60
        self.next_try = now + delay
        self.backoff = 2.
        log(f'capture recovery {self.stale_restarts}: restart in {delay:.0f} s')
        if delay > 0:
            self.start_card(f'capture stalled; retry {self.stale_restarts}')

    def window_present(self):
        """Card -> capture: is the source window back? CGWindowList only (no SCK). If CoreGraphics is unavailable,
        fall back to one `dispgrab info` only when no vision driver and no capture client of ours exists."""
        src = self.source
        if src and src.get('error'):
            return False
        try:
            info = cg_find(src)
            if info is None:
                return False
            if src:
                info['scale'] = (self.window or (None, 2.0))[1]
                window_crop(src, info)           # WrongWindow (e.g. a landscape dialog) -> still the card
            return True
        except NoWindow:
            return False
        except Exception as ex:
            self.window_probe = f'CGWindowList failed: {ex!r}'[:160]
        try:
            self.probe()                         # guarded: sole_client_ok (no capture, no vision, gate) first
            return True
        except Exception:
            return False

    def check_window(self, allowed_fn):
        """Every ~2 s while a display capture runs, between battles only: restart if the source window got another id
        or size, show the card if it is gone. CGWindowList only: NEVER `dispgrab info` beside a running stream (a second
        SCK client process makes replayd drop the running stream). The backing scale cannot change for the same window
        id + size without a display change; a scale-only change is left to the in-process restart."""
        if self.kind != 'display' or not self.running() or self.window is None:
            return
        now = time.monotonic()
        if now - self.win_check_t < WINDOW_POLL_S:
            return
        self.win_check_t = now
        try:
            info = cg_find(self.source)
        except Exception as ex:
            self.window_probe = f'unavailable: {ex!r}'[:160]
            return                               # unknown: never fall back to an SCK query here
        if info is None:
            self.win_missing_t = self.win_missing_t or now
            self.window_probe = f'source window absent {now - self.win_missing_t:.0f} s'
            if now - self.win_missing_t < WINDOW_GONE_S:
                return
            why = 'source window is gone'
        else:
            self.win_missing_t = 0.
            self.window_probe = f'window {info["window_id"]} {info["bounds"][2]:g}x{info["bounds"][3]:g}'
            if info['window_id'] == self.window[0] and tuple(info['bounds'][2:]) == tuple(self.window[2][2:]):
                return
            why = f'window changed {self.window[0]} -> {info["window_id"]} {info["bounds"][2]:g}x{info["bounds"][3]:g}'
        if not self.fresh_allowed(allowed_fn):
            self.deferred = True
            return
        log(f'pipeline: {why}')
        if self.stop(why, allowed_fn):           # fresh check right before each signal; the start re-probes
            self.next_try = 0.


def write_state(path, drv, pipe, now):
    live = drv.active()
    frame = (drv.frame or {}) if live else {}
    hand = drv.hand() if live else {}
    towers = frame.get('towers') or []
    battle = live and frame.get('state') == 'battle'
    st = dict(t=time.time(), driver=live, reason=None if live else status_reason(), run=drv.run, match=drv.match,
              state=frame.get('state') if live else 'no session', tick=frame.get('tick'),
              elixir=frame.get('elixir') if battle else None,
              hand=(hand.get('cards') or [])[:4] if battle else [], next=hand.get('next') if battle else None,
              crowns=crowns(towers) if battle and towers else None, tally=drv.tally,
              plays=list(drv.plays)[-6:] if live else [], overlay=dict(drv.overlay(now), **(dict(tiles=pipe.tiles['tiles'])
                                                                                       if pipe.tiles else {})),
              source=(pipe.tiles['label'] if pipe.tiles else
                      pipe.src_label if pipe.kind == 'display' and pipe.src_label else
                      'LADDER' if pipe.kind in ('display', 'legacy') else
                      'LADDER PAUSED' if pipe.kind == 'card' else ''),
              video=dict(running=pipe.running(), size=list(pipe.size) if pipe.size else None, crop=pipe.crop,
                         starts=pipe.starts, deferred=pipe.deferred, error=pipe.last_error, fps=pipe.fps, kind=pipe.kind,
                         capture_age_s=pipe.capture_age() if pipe.running() and pipe.kind in ('display', 'grid') else None,
                         stale_restarts=pipe.stale_restarts, last_stale=pipe.last_stale or None,
                         window_probe=pipe.window_probe, capture_pid=pipe.grab.pid if pipe.grab else None,
                         frames_age_s=round(time.monotonic() - pipe.frames_new_t, 2)
                         if pipe.kind == 'frames' and getattr(pipe, 'frames_new_t', None) else None))
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(st, default=float, separators=(',', ':')))
    os.replace(tmp, path)


def exit_ready(pipe, allowed):
    """May the feed exit (and so stop its children) now? Not while a capture client runs and the driver is in a battle
    (fresh log read): no ScreenCaptureKit client stops mid-battle, also on SIGTERM / Ctrl-C / --seconds."""
    holds = pipe.kind in ('display', 'grid') and pipe.grab is not None and pipe.grab.poll() is None
    if not holds:
        return True
    try:
        return allowed()
    except Exception:
        return False                             # unknown: keep the capture; in_battle clears 60 s after logs stop


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--desktop-rate', default='8000k,8000k,1000k', help='target,max,bufsize (CBR)')
    ap.add_argument('--phone-rate', default='1500k,1500k,300k')
    ap.add_argument('--phone', default='540,960')
    ap.add_argument('--cap-fps', type=int, default=0, help='capture fps of the native display capture (0 = --fps)')
    ap.add_argument('--cap-size', default='', help='W,H of the display capture (empty = native window pixels)')
    ap.add_argument('--no-video', action='store_true', help='feed only (tests)')
    ap.add_argument('--seconds', type=float, default=0, help='tests: stop after this long')
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    drv = Driver()
    pipe = Pipeline(a.fps, dict(desktop=a.desktop_rate.split(','), phone=a.phone_rate.split(',')),
                    tuple(int(v) for v in a.phone.split(',')), cap_fps=a.cap_fps or None,
                    cap_size=tuple(int(v) for v in a.cap_size.split(',')) if a.cap_size else None)
    pipe.drv = drv
    t0 = time.monotonic()
    k = 0
    mode, plan, drv_proc = 'yield', None, True
    log(f'display_feed pid {os.getpid()} fps {a.fps} video {"off" if a.no_video else "on"}')

    vis = dict(t=-1e9, v=True)

    def vision(fresh=False):
        """A vision driver process exists (the only other ScreenCaptureKit client). Fail closed: a pgrep error = True.
        The memory route (live/mem) captures nothing, so its battles must not hold the gate or force 'frames'.
        Cached VISION_TTL_S for the 10 Hz loop; fresh=True (every signal / capture start / exit check) always re-reads."""
        t = time.monotonic()
        if fresh or t - vis['t'] >= VISION_TTL_S:
            vis.update(t=t, v=driver_running())
        return vis['v']

    def allowed(fresh=False):
        # fresh read of the driver logs right before any start/stop decision; a battle gates only while a vision
        # driver exists (any battle log then counts, whatever run it came from)
        drv.follow(drv.find())
        drv.poll()
        return not (drv.in_battle() and vision(fresh))
    allowed.fresh = lambda: allowed(True)        # Pipeline.fresh_allowed / exit_ready use this
    pipe.allowed_fn = allowed                    # every capture-child signal re-checks it (also the exit stop)

    def write_gate():
        hold = 'hold' if drv.in_battle() and vision() else 'open'
        if hold != getattr(main, 'gate', None):
            tmp = GATE_FILE.with_name(GATE_FILE.name + '.tmp')
            tmp.write_text(hold + '\n')
            os.replace(tmp, GATE_FILE)
            main.gate = hold
    exiting = False
    try:
        while True:
            now = time.monotonic()
            if stop.is_set() or (a.seconds and now - t0 > a.seconds):
                if exit_ready(pipe, allowed.fresh):
                    break
                if not exiting:                  # keep feeding state + gate; start/stop nothing until the battle ends
                    exiting = True
                    log('exit requested during a battle: capture kept until the battle ends')
            try:
                if k % 20 == 0:
                    drv.follow(drv.find())
                if k % 100 == 0:
                    drv.update_tally()
                drv.poll()
                write_gate()
                if not a.no_video and not exiting and not stop.is_set():
                    starts = pipe.starts
                    if k % 10 == 0:
                        try:
                            m = MODE_FILE.read_text().strip()
                        except OSError:
                            m = 'yield'
                        mode = m if m in ('display', 'yield') else 'yield'
                    if k % 50 == 0:
                        pipe.source = window_source()    # file read only, no ScreenCaptureKit call
                    if k % 50 == 0 and (drv_proc or pipe.source is not None):
                        plan = None              # a driver exists: no ScreenCaptureKit call of ANY kind (even a query)
                    elif k % 50 == 0:
                        try:
                            plan = source_plan(sck_guard=pipe.sck_block)   # fresh guard, not drv_proc
                        except Exception as ex:          # transient discovery failure: keep the last plan
                            log(f'stream-source: {ex!r}'[:200])
                    drv_proc = vision()
                    if drv_proc:
                        # a vision driver process exists (even still loading models / fitting its crop): hold NO
                        # capture client, in either mode (its bsgrab is the one SCK client); its own frames (or the
                        # last picture) are shown instead. Logs without a vision process (the memory route: no video/
                        # frames) keep the window capture. Pipeline.sck_block re-checks this fresh before any dispgrab.
                        want = 'frames'
                    else:
                        want = 'grid' if plan is not None else 'display'
                    pipe.tick(allowed, want, plan)
                    if pipe.starts == starts and not exiting and not stop.is_set():
                        pipe.check_window(allowed)   # rate-limited inside (WINDOW_POLL_S); CGWindowList, no SCK
                write_state(OUT/'state.json', drv, pipe, now)
            except Exception as ex:
                log(f'loop: {ex!r}'[:300])
            k += 1
            pause = max(0., .1 - (time.monotonic() - now))
            if stop.is_set():
                time.sleep(pause)                # stop.wait returns at once once set: no busy loop while deferring
            else:
                stop.wait(pause)
    finally:
        # gated like every stop: a battle that began after exit_ready() keeps the capture until it ends
        while not pipe.stop('display_feed exiting'):
            time.sleep(.5)
            try:
                write_gate()
            except Exception:
                pass
        log('display_feed stopped')


if __name__ == '__main__':
    main()
