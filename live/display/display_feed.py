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
MODE_FILE = OUT/'mode.txt'                 # 'display' = own capture always; 'yield' (default) = old :8766 publisher while
                                           # a driver session is active, own capture otherwise. Switch: echo the word.
TITLE_PT, SIDEBAR_PT = 32.0, 32.0          # BlueStacks title bar (top) and tool sidebar (right), points
IDLE_S = 3.0                               # driver logs idle longer than this = no session (display)
BATTLE_HOLD_S = 60.0                       # last state 'battle' + logs seen within this = treat as in battle (gate)
STALE_UNITS_S = 0.5
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
    """A bot driver process exists (bracket pattern: never matches this pgrep itself or any shell running it)."""
    try:
        return subprocess.run(['/usr/bin/pgrep', '-f', '[d]rive\\.py'], capture_output=True, timeout=3).returncode == 0
    except Exception:
        return True                              # unknown: assume a driver, i.e. hold no capture client


def list_windows():
    out = subprocess.run([GRAB, 'windows'], capture_output=True, text=True, timeout=3, stdin=subprocess.DEVNULL)
    if out.returncode != 0:
        raise RuntimeError(f'dispgrab windows rc={out.returncode}: {out.stderr.strip()[:200]}')
    return json.loads(out.stdout)


def source_plan():
    """stream-source.json -> (label, [(window, tile label)]) when it asks for a Null's grid whose windows exist, else None.
    Lenient about the schema: source/mode/kind mentioning 'null'; instances/windows list with window_title/title."""
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
    wins = list_windows()
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
                    if d.get('submitted'):
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

    @staticmethod
    def fresh_allowed(allowed_fn):
        """A fresh 'driver not in a battle' read, taken right before a signal; an error counts as 'in a battle'."""
        if allowed_fn is None:
            return True
        try:
            return bool(allowed_fn())
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

    @staticmethod
    def stale_cmd(pid, exe):
        """The command of pid if it is still our pipeline child (exe + pipeline arguments), else None."""
        try:
            cmd = subprocess.check_output(['ps', '-p', str(pid), '-o', 'command='], text=True,
                                          stderr=subprocess.DEVNULL, timeout=3).strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            return None
        return cmd if cmd.startswith(exe) and (RTSP in cmd or ' stream ' in cmd or ' grid ' in cmd) else None

    def stale_pids(self):
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

    def start_grid(self, plan):
        """Null's data capture: one dispgrab grid process (one SCK stream per window) -> the same encoder/paths."""
        label, picked = plan
        W, H = CANVAS
        if not self.allowed_fn():                # the gate, re-checked right before a capture client starts
            self.deferred = True
            return
        b = picked[0][0]['bounds']
        rects = grid_layout(len(picked), b[2]/b[3] if b[3] else 9/16, W, H)
        cmd = [GRAB, 'grid', '--size', f'{W},{H}', '--fps', str(self.fps), '--seconds', '0', '--gate', str(GATE_FILE)]
        for (w, _), (x, y, tw, th) in zip(picked, rects):
            cmd += ['--tile', f"{w['id']}:{x},{y},{tw},{th}"]
        self.size, self.crop, self.window = (W, H), None, None
        with open(OUT/'dispgrab.log', 'ab') as glog, open(OUT/'ffmpeg.log', 'ab') as flog:
            stamp = time.strftime('%FT%TZ', time.gmtime())
            glog.write(f'{stamp} start {" ".join(cmd[1:])}\n'.encode()); glog.flush()
            flog.write(f'{stamp} start ffmpeg grid {W}x{H}@{self.fps}\n'.encode()); flog.flush()
            self.grab = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=glog, stdin=subprocess.DEVNULL)
            try:
                self.ff = subprocess.Popen(self.ffargs(), stdin=self.grab.stdout, stdout=flog, stderr=flog)
            finally:
                self.grab.stdout.close()
        self.kind = 'grid'
        sx = 1080/W                              # overlay space: Android px of a 1080-wide frame
        self.tiles = dict(label=label, ids=[w['id'] for w, _ in picked],
                          tiles=[dict(x=round(x*sx), y=round(y*sx), w=round(tw*sx), h=round(th*sx), label=lab)
                                 for (_, lab), (x, y, tw, th) in zip(picked, rects)])
        self.PIDS.write_text(json.dumps(dict(dispgrab=self.grab.pid, ffmpeg=self.ff.pid)))
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
                    img = np.full((h, w, 3), (30, 22, 16), np.uint8)
                    pt = time.strftime('%H:%M', time.localtime())
                    try:
                        pt = subprocess.run(['/bin/date', '+%H:%M %Z'], capture_output=True, text=True, timeout=1,
                                            env=dict(os.environ, TZ='America/Los_Angeles')).stdout.strip() or pt
                    except Exception:
                        pass
                    src = self.source
                    img[:] = 0                   # plain black; one small unobtrusive line (Sam 2026-10-17)
                    t = (f'waiting for the {src["owner"]} window' if src and src.get('owner') and not src.get('error')
                         else 'waiting for the game window') + f'  {pt}'
                    cv2.putText(img, t, (24, h - 40), cv2.FONT_HERSHEY_SIMPLEX, .7, (150, 150, 150), 1, cv2.LINE_AA)
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

    def probe(self):
        """(info, crop, size) of the current source's window: one dispgrab info query. NoWindow/WrongWindow if absent."""
        src = self.source
        if src and src.get('error'):
            raise WrongWindow(src['error'])
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
        info, crop, size = self.probe()
        if not allowed():                        # the gate is re-checked after the (up to 4 s) window query
            self.deferred = True
            return
        s = float(info.get('scale', 2.0))
        cap_fps = min(self.fps, src['fps']) if src and src.get('fps') else self.cap_fps
        grab_cmd = [GRAB, 'stream', '--crop', ','.join(map(str, crop)), '--size', f'{size[0]},{size[1]}',
                    '--fps', str(cap_fps), '--seconds', '0', '--gate', str(GATE_FILE)] + window_args(src)
        self.size, self.crop, self.window = size, crop, (info.get('window_id'), s, tuple(info['bounds']))
        self.kind = 'display'
        self.src_key = src['key'] if src else None
        self.src_label = src['label'] if src else None
        with open(OUT/'dispgrab.log', 'ab') as glog, open(OUT/'ffmpeg.log', 'ab') as flog:
            stamp = time.strftime('%FT%TZ', time.gmtime())
            glog.write(f'{stamp} start {" ".join(grab_cmd[1:])}\n'.encode()); glog.flush()
            flog.write(f'{stamp} start ffmpeg {size[0]}x{size[1]}@{self.fps}\n'.encode()); flog.flush()
            self.grab = subprocess.Popen(grab_cmd, stdout=subprocess.PIPE, stderr=glog, stdin=subprocess.DEVNULL)
            try:
                self.ff = subprocess.Popen(self.ffargs(in_fps=cap_fps), stdin=self.grab.stdout, stdout=flog, stderr=flog)
            finally:
                self.grab.stdout.close()            # only ffmpeg holds the pipe's read end
        self.PIDS.write_text(json.dumps(dict(dispgrab=self.grab.pid, ffmpeg=self.ff.pid)))
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
                p.wait()
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

    def capture_age(self):
        """Seconds since dispgrab's newest captured frame, from its 10 s stats line (None if unknown)."""
        m = re.findall(r'last_capture_age (-?[\d.]+) s', self.tail_text(OUT/'dispgrab.log', 4096))
        return float(m[-1]) if m and float(m[-1]) >= 0 else None

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
        if self.kind == 'card' and self.running() and want == 'display' and now - self.card_t > 5:
            self.card_t = now                    # is a source window back? then leave the card
            try:
                self.probe()
                if self.stop('source window is back'):
                    self.next_try = 0.
            except Exception:
                pass
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
            if not self.stop(self.last_error):
                return
            self.next_try = now if self.legacy_fallback else now + self.backoff
            self.backoff = min(60., self.backoff*2)
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
                return
            self.next_try = now + self.backoff
            self.backoff = min(60., self.backoff*2)

    def check_window(self, allowed_fn):
        """Every ~20 s, only between battles: restart if the window moved to another id/scale/size."""
        if self.kind != 'display' or not allowed_fn() or not self.running():
            return
        try:
            info, crop, _ = self.probe()
        except Exception as ex:
            self.last_error = repr(ex)[:200]
            return
        key = (info.get('window_id'), float(info.get('scale', 2.0)), tuple(crop))
        ref = (self.window[0], self.window[1], tuple(self.crop))
        if self.src_key is not None:             # window source: a resize may move the game area under a fixed crop
            key, ref = key + tuple(info['bounds'][2:]), ref + tuple(self.window[2][2:])
        if key != ref:
            if self.stop('window changed', allowed_fn):    # fresh check right before each signal
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

    def allowed():
        # fresh read of the driver logs right before any start/stop decision
        drv.follow(drv.find())
        drv.poll()
        return not drv.in_battle()
    pipe.allowed_fn = allowed                    # every capture-child signal re-checks it (also the exit stop)

    def write_gate():
        hold = 'hold' if drv.in_battle() else 'open'
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
                if exit_ready(pipe, allowed):
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
                            plan = source_plan()
                        except Exception as ex:          # transient discovery failure: keep the last plan
                            log(f'stream-source: {ex!r}'[:200])
                    if k % 20 == 0:
                        drv_proc = driver_running()
                    if mode == 'yield' and (drv_proc or drv.active()):
                        # a driver process exists (even still loading models / fitting its crop): hold NO capture
                        # client; the driver's own frames (or the last picture) are shown instead
                        want = 'frames'
                    else:
                        want = 'grid' if plan is not None else 'display'
                    pipe.tick(allowed, want, plan)
                    if k % 200 == 100 and pipe.starts == starts and not exiting and not stop.is_set():
                        pipe.check_window(allowed)
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
