#!/Users/sam/clasher-live/venv/bin/python
"""Display-only feed + clean video pipeline for the clasher live viewer. Never sends input; never imports the driver.

  display_feed.py [--fps 30] [--desktop-rate 8000k,8000k,1000k] [--phone-rate 1500k,1500k,300k]

1. Video: `dispgrab stream` (own read-only ScreenCaptureKit capture of the BlueStacks game rect at native pixels, NV12,
   constant --fps) piped straight into ffmpeg h264_videotoolbox, publishing rtsp://127.0.0.1:8554/{desktop,phone} to
   MediaMTX. Python never touches pixels. The pipeline is (re)started ONLY while the driver is not in a battle: a second
   ScreenCaptureKit client starting/stopping has correlated with -3805 interruptions of the driver's capture (drive.py).
   A pipeline that dies mid-battle is restarted after the battle ends (the page falls back to JPEG snapshots meanwhile).
2. Overlay feed: follows the driver's line-buffered logs (runs/<session>/[mNN/]perception, frames, decisions .jsonl)
   and writes ~/clasher-live/loop/display/state.json at 10 Hz (atomic): unit boxes / tower HP / plan / last play in
   Android px (1080x1920 guest), hand, next, elixir, crowns, session tally. The pages draw it on a <canvas>.
Writes only under ~/clasher-live/loop/display/. Never binds or reads the driver's 127.0.0.1:8766.
Env (tests): LL_LOOP_DIR, CLASHER_DISPLAY_GRAB, CLASHER_DISPLAY_FFMPEG, CLASHER_DISPLAY_RTSP, CLASHER_DISPLAY_OFFSETS.
"""
import argparse
import json
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
SOURCE_FILE = LOOP/'stream-source.json'   # written by the capture owner: Null's data-capture blocks (grid of windows)
CANVAS = (1044, 1856)                      # grid canvas = the ladder's native size (same renditions, no re-negotiation)
GATE_FILE = OUT/'capture-gate'             # 'hold' while the driver is in a battle: dispgrab restarts nothing in-process
MODE_FILE = OUT/'mode.txt'                 # 'display' = own capture always; 'yield' (default) = old :8766 publisher while
                                           # a driver session is active, own capture otherwise. Switch: echo the word.
TITLE_PT, SIDEBAR_PT = 32.0, 32.0          # BlueStacks title bar (top) and tool sidebar (right), points
IDLE_S = 3.0                               # driver logs idle longer than this = no session (display)
BATTLE_HOLD_S = 60.0                       # last state 'battle' + logs seen within this = treat as in battle (gate)
STALE_UNITS_S = 1.0
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


def _norm(n):
    return re.sub(r'[^a-z0-9]', '', str(n).lower())


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
            rows.append(dict(x=b['x'], y=b['y'], owner=b.get('owner', 1), card=card, cls=card, yolo=y, label=lab))
        return rows
    for u, y in zip(units, yolo):
        rows.append(dict(x=u['x'], y=u['y'], owner=u.get('owner', 1), card=None, cls=u.get('cls'), yolo=y,
                         label=str(y) if y else short_label(u.get('cls'))))
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


def grab_info():
    out = subprocess.run([GRAB, 'info'], capture_output=True, text=True, timeout=3, stdin=subprocess.DEVNULL)
    if out.returncode == 3:                      # dispgrab: no on-screen BlueStacks window (quit / restarting)
        raise NoWindow(out.stderr.strip()[:200])
    if out.returncode != 0:
        raise RuntimeError(f'dispgrab info rc={out.returncode}: {out.stderr.strip()[:200]}')
    return json.loads(out.stdout)


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
    if not isinstance(d, dict):
        return None
    kind = ' '.join(str(d.get(k, '')) for k in ('source', 'mode', 'kind', 'label')).lower()
    if 'null' not in kind:
        return None
    inst = d.get('instances') or d.get('windows') or []
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
        self.frame = self.perc = self.decision = self.last_play = None
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
            elif name == 'perception':
                self.perc, self.perc_t = rows[-1], now
            else:
                for d in rows:
                    self.decision, self.decision_t = d, now
                    if d.get('submitted'):
                        self.last_play, self.last_play_t = d, now
                        self.plays.append(dict(t=time.time(), card=d.get('card'), tile=tile_of(d.get('action'))))

    def logs_t(self):
        return max((t.mtime for t in self.tails.values()), default=0.)

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
            for u in unit_rows(perc):
                ax, ay = tile_to_android(u['x'], u['y'])
                bw, bh, lift = (v*ARENA_S for v in box_shape(u['card'] or u['cls']))
                dy = self.ground_dy.get(u['yolo']) if isinstance(u['yolo'], str) else None
                if dy is not None:
                    lift = bh/2 + dy*TILE_C*ARENA_S
                o['units'].append(dict(x=round(ax - bw/2), y=round(ay - lift - bh/2), w=round(bw), h=round(bh),
                                       own=u['owner'] == 0, label=u['label']))
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

    def __init__(self, fps, rates, phone):
        self.fps, self.rates, self.phone = fps, rates, phone
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

    def stale_pids(self):
        try:
            old = json.loads(self.PIDS.read_text())
        except (OSError, ValueError):
            return []
        out = []
        for pid, exe in ((old.get('dispgrab'), GRAB), (old.get('ffmpeg'), FFMPEG)):
            if not isinstance(pid, int) or pid <= 1:
                continue
            try:
                cmd = subprocess.check_output(['ps', '-p', str(pid), '-o', 'command='], text=True).strip()
            except subprocess.CalledProcessError:
                continue
            if cmd.startswith(exe) and (RTSP in cmd or ' stream ' in cmd or ' grid ' in cmd):
                out.append((pid, cmd))
        return out

    def stale_alive(self):
        return bool(self.stale_pids())

    def reap_stale(self):
        """Children of an earlier display_feed that was killed hard: terminate them only if pid AND command match."""
        try:
            old = json.loads(self.PIDS.read_text())
        except (OSError, ValueError):
            return
        for pid, exe in ((old.get('dispgrab'), GRAB), (old.get('ffmpeg'), FFMPEG)):
            if not isinstance(pid, int) or pid <= 1:
                continue
            try:
                cmd = subprocess.check_output(['ps', '-p', str(pid), '-o', 'command='], text=True).strip()
            except subprocess.CalledProcessError:
                continue
            if cmd.startswith(exe) and (RTSP in cmd or ' stream ' in cmd or ' grid ' in cmd):
                log(f'terminating stale pipeline child {pid}: {cmd[:120]}')
                for sig, wait_s in ((signal.SIGTERM, 2.), (signal.SIGKILL, 2.)):
                    try:
                        os.kill(pid, sig)
                    except OSError:
                        break
                    t_end = time.monotonic() + wait_s
                    while time.monotonic() < t_end:
                        try:
                            os.kill(pid, 0)
                        except OSError:
                            break
                        time.sleep(.05)
                    else:
                        continue
                    break
        try:
            self.PIDS.unlink()
        except OSError:
            pass

    def running(self):
        if self.kind in ('legacy', 'card'):
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
                    try:
                        nulls = 'null' in json.dumps(json.loads(SOURCE_FILE.read_text())).lower()
                    except (OSError, ValueError):
                        nulls = False
                    head, sub = (("DATA CAPTURE - Null's Royale", 'emulator window not on screen yet') if nulls else
                                 ('LADDER PAUSED', 'BlueStacks restarting / not open'))
                    lines = [(head, 2.0 if nulls else 2.4, (80, 180, 255)), (sub, 1.25, (235, 235, 235)),
                             (status_reason()[:46], 1.0, (200, 210, 220)), (status_reason()[46:92], 1.0, (200, 210, 220)),
                             (f'clasher live  {pt}', 1.0, (150, 160, 175))]
                    y = int(h*.38)
                    for t, sc, col in lines:
                        if t:
                            (tw, th), _ = cv2.getTextSize(t, cv2.FONT_HERSHEY_DUPLEX, sc, 2)
                            cv2.putText(img, t, ((w - tw)//2, y), cv2.FONT_HERSHEY_DUPLEX, sc, col, 2, cv2.LINE_AA)
                            y += int(th*2.2)
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

    def ffargs(self, in_fps=None):
        w, h = self.size
        pw, ph = self.phone
        a = [FFMPEG, '-hide_banner', '-nostdin', '-loglevel', 'warning', '-threads', '2', '-filter_threads', '2',
             '-filter_complex_threads', '2', '-progress', str(self.progress), '-stats_period', '2',
             '-fflags', '+nobuffer', '-flags', '+low_delay',
             '-f', 'rawvideo', '-pix_fmt', 'nv12', '-video_size', f'{w}x{h}', '-framerate', str(in_fps or self.fps),
             '-use_wallclock_as_timestamps', '1', '-thread_queue_size', '8', '-i', 'pipe:0',
             '-filter_complex', f'[0:v]split=2[d][a];[a]scale={pw}:{ph}:flags=bilinear[p]']
        for lab, name in (('d', 'desktop'), ('p', 'phone')):
            rate, peak, buf = self.rates[name]
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

    def start(self, allowed):
        info = grab_info()
        if not allowed():                        # the gate is re-checked after the (up to 4 s) window query
            self.deferred = True
            return
        crop = game_crop(info)
        s = float(info.get('scale', 2.0))
        size = (int(round(crop[2]*s)) & ~1, int(round(crop[3]*s)) & ~1)
        grab_cmd = [GRAB, 'stream', '--crop', ','.join(map(str, crop)), '--size', f'{size[0]},{size[1]}',
                    '--fps', str(self.fps), '--seconds', '0', '--gate', str(GATE_FILE)]
        self.size, self.crop, self.window = size, crop, (info.get('window_id'), s, tuple(info['bounds']))
        self.kind = 'display'
        with open(OUT/'dispgrab.log', 'ab') as glog, open(OUT/'ffmpeg.log', 'ab') as flog:
            stamp = time.strftime('%FT%TZ', time.gmtime())
            glog.write(f'{stamp} start {" ".join(grab_cmd[1:])}\n'.encode()); glog.flush()
            flog.write(f'{stamp} start ffmpeg {size[0]}x{size[1]}@{self.fps}\n'.encode()); flog.flush()
            self.grab = subprocess.Popen(grab_cmd, stdout=subprocess.PIPE, stderr=glog, stdin=subprocess.DEVNULL)
            try:
                self.ff = subprocess.Popen(self.ffargs(), stdin=self.grab.stdout, stdout=flog, stderr=flog)
            finally:
                self.grab.stdout.close()            # only ffmpeg holds the pipe's read end
        self.PIDS.write_text(json.dumps(dict(dispgrab=self.grab.pid, ffmpeg=self.ff.pid)))
        self.starts += 1
        self.started_t = time.monotonic()
        self.last_frame_n, self.last_frame_t = -1, time.monotonic()
        log(f'pipeline start #{self.starts}: dispgrab pid {self.grab.pid} ffmpeg pid {self.ff.pid} '
            f'{size[0]}x{size[1]}@{self.fps} crop {crop} window {self.window[0]}')

    def stop(self, why):
        procs = [p for p in (self.grab, self.ff) if p is not None]
        for p in procs:
            if p.poll() is None:
                p.terminate()
        deadline = time.monotonic() + 2
        for p in procs:
            try:
                p.wait(max(.05, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
        if self.kind == 'card' and self.ff is not None and self.ff.stdin:
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
        try:
            self.PIDS.unlink()
        except OSError:
            pass

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
        allowed = allowed_fn()
        cap = ('display', 'grid')                # kinds that own a ScreenCaptureKit client
        # in a battle no capture client may start: the stream is then served by the driver's own page (legacy)
        want = want if (allowed or want not in cap) else 'legacy'
        if want == 'legacy' and (self.legacy_fallback or now < self.legacy_block_until):
            want = 'card'                        # the driver page is not answering: show the status card meanwhile
        if not self.reaped:
            if not self.stale_alive():
                self.reaped = True               # nothing stale: no reason to wait for the gate
            elif not allowed:
                self.deferred = True             # the stale publisher keeps serving the stream until the battle ends
                return
            else:
                self.reaped = True
                self.reap_stale()
        if self.kind == 'card' and self.running() and want == 'display' and now - self.card_t > 5:
            self.card_t = now                    # is a source window back? then leave the card
            try:
                grab_info()
                self.stop('source window is back')
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
            if (self.running() and (self.kind != want or regrid) and not (self.kind == 'card' and want == 'display')
                    and (allowed or self.kind not in cap)):      # a running capture is never stopped mid-battle
                self.stop(f'switching {self.kind} -> {want}')
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
                        self.stop(self.last_error)
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
            self.stop(self.last_error)
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
            elif want == 'card':
                self.start_card('driver page not answering')
                if self.legacy_fallback:         # the cooldown runs from the card's actual start
                    self.legacy_fallback, self.legacy_block_until = False, now + 30
            else:
                self.start(allowed_fn)
        except NoWindow as ex:
            self.last_error = f'no source window: {ex}'[:200]
            self.stop('no window')
            self.start_card('no BlueStacks window')
        except Exception as ex:
            self.last_error = repr(ex)[:200]
            log(f'pipeline start failed: {self.last_error}')
            self.stop('start failed')
            self.next_try = now + self.backoff
            self.backoff = min(60., self.backoff*2)

    def check_window(self, allowed_fn):
        """Every ~20 s, only between battles: restart if the window moved to another id/scale/size."""
        if self.kind != 'display' or not allowed_fn() or not self.running():
            return
        try:
            info = grab_info()
            crop = game_crop(info)
        except Exception as ex:
            self.last_error = repr(ex)[:200]
            return
        if (info.get('window_id'), float(info.get('scale', 2.0)), crop) != (self.window[0], self.window[1], self.crop):
            if not allowed_fn():
                return
            self.stop('window changed')
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
              source=(pipe.tiles['label'] if pipe.tiles else 'LADDER' if pipe.kind in ('display', 'legacy') else
                      'LADDER PAUSED' if pipe.kind == 'card' else ''),
              video=dict(running=pipe.running(), size=list(pipe.size) if pipe.size else None, crop=pipe.crop,
                         starts=pipe.starts, deferred=pipe.deferred, error=pipe.last_error, fps=pipe.fps, kind=pipe.kind,
                         capture_age_s=pipe.capture_age() if pipe.running() else None))
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(st, default=float, separators=(',', ':')))
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--desktop-rate', default='8000k,8000k,1000k', help='target,max,bufsize (CBR)')
    ap.add_argument('--phone-rate', default='1500k,1500k,300k')
    ap.add_argument('--phone', default='540,960')
    ap.add_argument('--no-video', action='store_true', help='feed only (tests)')
    ap.add_argument('--seconds', type=float, default=0, help='tests: stop after this long')
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    drv = Driver()
    pipe = Pipeline(a.fps, dict(desktop=a.desktop_rate.split(','), phone=a.phone_rate.split(',')),
                    tuple(int(v) for v in a.phone.split(',')))
    t0 = time.monotonic()
    k = 0
    mode, plan = 'yield', None
    log(f'display_feed pid {os.getpid()} fps {a.fps} video {"off" if a.no_video else "on"}')
    try:
        while not stop.is_set():
            now = time.monotonic()
            if a.seconds and now - t0 > a.seconds:
                break
            try:
                if k % 20 == 0:
                    drv.follow(drv.find())
                if k % 100 == 0:
                    drv.update_tally()
                drv.poll()
                def allowed():
                    # fresh read of the driver logs right before any start/stop decision
                    drv.follow(drv.find())
                    drv.poll()
                    return not drv.in_battle()
                hold = 'hold' if drv.in_battle() else 'open'
                if hold != getattr(main, 'gate', None):
                    tmp = GATE_FILE.with_name(GATE_FILE.name + '.tmp')
                    tmp.write_text(hold + '\n')
                    os.replace(tmp, GATE_FILE)
                    main.gate = hold
                if not a.no_video and not stop.is_set():
                    starts = pipe.starts
                    if k % 10 == 0:
                        try:
                            m = MODE_FILE.read_text().strip()
                        except OSError:
                            m = 'yield'
                        mode = m if m in ('display', 'yield') else 'yield'
                    if k % 50 == 0:
                        try:
                            plan = source_plan()
                        except Exception as ex:          # transient discovery failure: keep the last plan
                            log(f'stream-source: {ex!r}'[:200])
                    if mode == 'yield' and drv.active():
                        want = 'legacy'
                    else:
                        want = 'grid' if plan is not None else 'display'
                    pipe.tick(allowed, want, plan)
                    if k % 200 == 100 and pipe.starts == starts and not stop.is_set():
                        pipe.check_window(allowed)
                write_state(OUT/'state.json', drv, pipe, now)
            except Exception as ex:
                log(f'loop: {ex!r}'[:300])
            k += 1
            stop.wait(max(0., .1 - (time.monotonic() - now)))
    finally:
        pipe.stop('display_feed exiting')
        log('display_feed stopped')


if __name__ == '__main__':
    main()
