"""LIVE loop driver: BlueStacks window frames -> canvas -> LivePerception -> LiveSession(LivePlayer) -> ADB taps.

  python -I drive.py --out DIR [--source live|replay:<recording dir>] [--tap adb|none] [--seconds 420]

* Frames: live = bsgrab (latest frame only; a reader thread drops stale ones; restarted on stream errors), or a recording
  replayed at its own pace (05 dry run). Every processed frame is also written as JPEG (writer thread) for the video.
* Match start = the battle HUD (elixir drop) present on 3 consecutive frames -> ClockTracker.anchor(0, ts). Match end =
  HUD absent for 3 s after the start. No tap is ever sent outside the battle window.
* HUD overrides (official 16:9 layout; see canvas.py): elixir from the bar fill, clock/phase from the anchored tick.
  Hand, next, units, towers and events come from LivePerception on the canvas.
* Taps (adb input, guest only, never the Mac desktop): card slot centre, then the arena target (canvas.action_target);
  both validated against the card row and the arena box. --tap none logs them only.
Logs in --out: frames.jsonl (per processed frame: timings, HUD, perception summary), decisions.jsonl, taps.jsonl,
session.json (stats at the end), video/NNNNNN.jpg.
"""
import argparse
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import canvas as C  # noqa: E402
import towers as TW  # noqa: E402
import ownplay  # noqa: E402
import handread  # noqa: E402
from battlelog import C56  # noqa: E402  (the 56 cards our engines and perception know)
from frames import Grabber  # noqa: E402

MIN_FREE = 6 << 30
GB = 1 << 30
DISK_PAUSE = float(os.environ.get('LL_DISK_PAUSE_GB', 6))*GB    # below: no new battles (low_disk pause)
DISK_RESUME = float(os.environ.get('LL_DISK_RESUME_GB', 7))*GB  # above again: resume
DISK_STOP = float(os.environ.get('LL_DISK_STOP_GB', 3))*GB      # below: stop, even mid-battle
FALSE_MATCH_MS = 30_000
STALL_MS = float(os.environ.get('LL_STALL_S', 6))*1000   # full elixir this long without a play -> fast tier          # a battle ending sooner than this after match_start was a false HUD transition
DECK = ['Knight', 'Archers', 'Minions', 'Arrows', 'Fireball', 'Giant', 'MiniPekka', 'Musketeer']
DECK_FILE = Path(os.path.expanduser(os.environ.get('LL_DECK_FILE', '~/clasher-live/loop/deck.json')))      # set from the live page; survives restarts
PAUSE_FILE = Path(os.path.expanduser(os.environ.get('LL_PAUSE_FILE', '~/clasher-live/loop/PAUSE')))         # exists = paused (same as the page button)


def load_deck():
    try:
        d = json.loads(DECK_FILE.read_text())
        if isinstance(d, list) and len(d) == 8:
            return d
    except Exception:
        pass
    return list(DECK)
ADB = os.path.expanduser(os.environ.get('LL_ADB', '~/clasher-live/tools/platform-tools/adb'))   # LL_ADB: tests only


def normalize(f):
    """Undo a uniform dim: scale so the HUD's white text (p99.5 of the bottom HUD, 255 on normal frames) maps to 255.
    After ~01:00Z on 10-16 the whole BlueStacks output dimmed to a white level of ~185 (cause unknown, in the guest
    framebuffer too); the colour readers and tower OCR then failed (elixir 0, every princess 'dead')."""
    w = float(np.percentile(f[1600:1920:2, ::2].max(2), 99.5))
    if w >= 245 or w < 80:
        return f, w
    return cv2.convertScaleAbs(f, alpha=255./w), w


def screen_kind(f):
    """Between battles (normalized Android frame): 'result' (blue OK right of yellow Play Again), 'home' (yellow
    Battle button above the tab bar, no dark overlay), 'road' (trophy road: blue OK at the bottom, the blue trophy
    column on the left), else None. Only these get auto-navigation taps, each on its OK / Battle button."""
    m = lambda x1, y1, x2, y2: f[y1:y2, x1:x2].reshape(-1, 3).mean(0)
    ok, again, battle = m(600, 1700, 810, 1780), m(250, 1700, 490, 1780), m(400, 1430, 700, 1540)
    yellow = lambda c: c[2] > 190 and c[1] > 150 and c[0] < 140
    blue = lambda c: c[0] > 200 and c[2] < 140
    if blue(ok) and yellow(again):
        return 'result'
    coin = m(440, 35, 475, 75)                          # the gold coin in the home top bar (absent in battle)
    bar = f[1000:1700, 0:90].astype(np.int16)              # the blue trophy column at the left edge, any x
    col = ((bar[..., 0] > 180) & (bar[..., 2] < 120)).mean(0).max()
    if blue(m(440, 1810, 640, 1880)) and col > .6 and not yellow(coin):
        return 'road'                                   # trophy road after a trophy gain: only its OK button
    if yellow(battle) and yellow(coin) and m(0, 1760, 1080, 1900)[0] > 90 and f[300:1300:8, ::8].mean() > 70:
        return 'home'
    return None


NAV_TAP = {'result': (705, 1740), 'home': (550, 1489), 'road': (540, 1845)}


def frame_health(f):
    """Mean brightness of the arena (Android rows 300..1500). Normal battle frames are ~90-110; a BlueStacks overlay
    window dimmed the game to ~40 and capture went black (0) in s2 battle 2: the colour readers then fail."""
    return float(f[300:1500:8, ::8].mean())


def hud_read(f):
    """Android-size frame -> (battle HUD present, elixir 0..10 or None). The bar (x 290..1038, 10 segments of 74.8 px)
    is filled pink for whole elixir (light pink while it flashes) and light blue for the growing partial segment;
    empty is dark blue. Present = the pink elixir drop at x 250..285."""
    o = f[1868:1888, 250:1040].astype(np.int16)
    b, g, r = o[..., 0], o[..., 1], o[..., 2]
    pink = (r > 170) & (b > 150)
    partial = (r > 25) & (r < 110) & (g > 65) & (b > 140)
    # the drop is saturated magenta (green well below red and blue); a bright neutral / pinkish-white full-screen flash
    # in the menus also passes `pink` and started two false battles in s10 (m01, m02) while Sam was paused in the menus
    magenta = pink & (g < .6*np.minimum(r, b))
    present = (magenta.mean(0) > .5)[:35].mean() > .6
    col = ((pink | partial).mean(0) > .5)[40:]                 # the bar from x 290
    xs = np.nonzero(col)[0]
    elixir = float(np.clip((xs.max() + 1 + 40 + 250 - 290)/74.8, 0, 10)) if len(xs) else 0.
    return bool(present), (elixir if present else None)


class LiveFrames:
    """bsgrab in a thread; get() returns the newest frame (or None after `timeout`)."""
    def __init__(self, bsgrab, crop, size, fps, seconds, log):
        self.args, self.log, self.slot, self.cv = (bsgrab, crop, size, fps, seconds), log, None, threading.Condition()
        self.stop, self.restarts, self.g = False, 0, None
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        bsgrab, crop, size, fps, seconds = self.args
        t_end = time.monotonic() + seconds
        while not self.stop and time.monotonic() < t_end:      # restart on every SCK interruption (any other SCK client
                                                                # on the Mac can cause -3805; s3 lost capture after 5)
            self.g = Grabber(bsgrab, crop, size, fps, int(t_end - time.monotonic()) + 2, stderr=self.log)
            try:
                for fr in self.g:
                    with self.cv:
                        self.slot = fr; self.cv.notify()
                    if self.stop:
                        break
            except ValueError:
                pass
            self.g.close()
            if not self.stop:
                self.restarts += 1; time.sleep(.5)

    def get(self, timeout=2.):
        with self.cv:
            if self.slot is None:
                self.cv.wait(timeout)
            fr, self.slot = self.slot, None
            return fr

    def close(self):
        self.stop = True
        if self.g is not None:
            self.g.close()


class ReplayFrames:
    """A record.py recording at its own pace (dry run): yields Frame-like tuples with the recorded display_ns."""
    def __init__(self, rec, realtime=True):
        from frames import Frame
        self.rows = [json.loads(l) for l in open(Path(rec)/'frames.jsonl')]
        self.rec, self.Frame, self.i, self.real = Path(rec), Frame, 0, realtime
        self.t0w, self.t0r = time.monotonic(), self.rows[0]['display_ns']

    def get(self, timeout=2.):
        if self.i >= len(self.rows):
            return None
        if self.real:      # skip to the newest row due now (drops frames the way the live reader does)
            due = self.t0r + (time.monotonic() - self.t0w)*1e9
            while self.i + 1 < len(self.rows) and self.rows[self.i + 1]['display_ns'] <= due:
                self.i += 1
            wait = (self.rows[self.i]['display_ns'] - due)/1e9
            if wait > 0:
                time.sleep(wait)
        r = self.rows[self.i]; self.i += 1
        return self.Frame(r['seq'], cv2.imread(str(self.rec/r['file'])), r['display_ns'], r['emit_ns'], time.time_ns())

    def close(self):
        pass


class AdbTaps:
    """One persistent `adb shell`; play() writes `input tap card; input tap target; echo` and returns at once; a reader
    thread logs the ack (guest finished both taps)."""
    def __init__(self, serial, port, log):
        self.p = subprocess.Popen([ADB, '-P', str(port), '-s', serial, 'shell'], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        self.log, self.sent, self.n = log, {}, 0
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.p.stdout:
            w = line.split()
            if len(w) == 2 and w[0] == '__ack' and w[1].isdigit():
                n = int(w[1]); t = time.time_ns()
                s = self.sent.pop(n, None)
                self.log(dict(ack=n, ack_ns=t, write_to_ack_ms=(t - s)/1e6 if s else None))
            else:
                self.log(dict(adb_out=line.rstrip()[:200]))

    def play(self, card_xy, target_xy):
        self.n += 1
        self.sent[self.n] = time.time_ns()
        self.p.stdin.write(f'input tap {card_xy[0]} {card_xy[1]}; input tap {target_xy[0]} {target_xy[1]}; '
                           f'echo __ack {self.n}\n')
        self.p.stdin.flush()
        return self.n

    def close(self):
        try:
            self.p.stdin.close(); self.p.wait(3)
        except Exception:
            self.p.kill()


def valid_tap(card_xy, target_xy):
    return (card_xy in [tuple(map(int, c)) for c in C.CARD_SLOTS]
            and 40 <= target_xy[0] <= 1040 and 80 <= target_xy[1] <= 1540)


class Writer:
    def __init__(self, d):
        self.d, self.q, self.dropped = d, queue.Queue(64), 0
        self.t = threading.Thread(target=self._run, daemon=True); self.t.start()

    def _run(self):
        while True:
            item = self.q.get()
            if item is None:
                return
            n, img = item
            cv2.imwrite(str(self.d/f'{n:06d}.jpg'), img, [cv2.IMWRITE_JPEG_QUALITY, 85])

    def put(self, n, img):
        try:
            self.q.put_nowait((n, img))
        except queue.Full:
            self.dropped += 1

    def close(self):
        self.q.put(None); self.t.join(30)


class _CodeFallback:
    """Finder appended to sys.meta_path: a clasher.* module that no earlier finder (the pinned runtime src first) can
    find is loaded from this code tree's src/ (only perception's clasher.vision / clasher.rl.perspective_sanitizer)."""
    root = HERE.parent.parent/'src'

    def find_spec(self, name, path=None, target=None):
        import importlib.util
        if not name.startswith('clasher.'):
            return None
        base = self.root.joinpath(*name.split('.'))
        if (base/'__init__.py').exists():
            return importlib.util.spec_from_file_location(name, base/'__init__.py', submodule_search_locations=[str(base)])
        if base.with_suffix('.py').exists():
            return importlib.util.spec_from_file_location(name, base.with_suffix('.py'))
        return None


def grab_arena_bg(bsgrab, crop, out_dir, tag, log):
    """Perception round 3 request: 3 full-resolution frames of the (still empty) arena right after the battle starts,
    from a second, short bsgrab stream at the viewport's native pixel size."""
    from frames import read_frames
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        w, h = int(round(crop[2]*2)), int(round(crop[3]*2))
        p = subprocess.Popen([bsgrab, 'stream', '--crop', ','.join(map(str, crop)), '--size', f'{w},{h}', '--fps', '4',
                              '--frames', '3', '--seconds', '5'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        k = 0
        for fr in read_frames(p.stdout):
            cv2.imwrite(str(out_dir/f'{tag}-{k}-{w}x{h}.png'), fr.bgr); k += 1
        p.wait(5)
        log('events', dict(ev='arena_bg', dir=str(out_dir), frames=k))
    except Exception as ex:
        log('events', dict(ev='arena_bg_error', error=repr(ex)[:200]))


def B_load_templates():
    import battlelog
    return battlelog.load_templates(HERE/'cards')


def build_bot(player_name, deck):
    if os.environ.get('LL_PINS'):       # Mac: register the mac-r1-total pin set before Runtime() (as mac_bench)
        import bot.live.mac_pins as mp
        mp.register(Path(os.environ['LL_PINS']))
    from bot.players.runtime import Runtime
    from bot.live.player import make_live_player
    from bot.live.translate import LiveSession
    rt = Runtime()
    sys.meta_path.append(_CodeFallback())   # last resort: modules the pinned runtime src lacks (perception's vision)
    import clasher_core
    if Path(clasher_core.__file__).resolve().parent != rt.native_dir.resolve():
        sys.exit(f'clasher_core loaded from {clasher_core.__file__}, not the pinned {rt.native_dir}')
    player = make_live_player(rt, player_name)
    return rt, LiveSession(rt, player, deck)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--source', default='live')
    ap.add_argument('--tap', default='adb', choices=('adb', 'none'))
    ap.add_argument('--seconds', type=float, default=420)
    ap.add_argument('--fps', type=int, default=10)
    ap.add_argument('--bsgrab', default=os.path.expanduser('~/clasher-live/loop/bin/bsgrab'))
    ap.add_argument('--crop', default='0,32,510,908')
    ap.add_argument('--size', default='720,1280')
    ap.add_argument('--export', required=True)
    ap.add_argument('--player', default='LIVE-K4L-R-gs-rw-fc-w200-t4-p4')
    ap.add_argument('--adb-port', type=int, default=5047)
    ap.add_argument('--serial', default='127.0.0.1:5555')
    ap.add_argument('--overlay-port', type=int, default=8766,
                    help='the driver\'s own page/MJPEG (0 = off); the always-on overlay_server.py on :8765 proxies it')
    ap.add_argument('--arena', default='goblin-stadium', help='arena-bgs/<arena>/ name for the battle-start frames')
    ap.add_argument('--matches', type=int, default=1, help='battles in one session (each in <out>/mNN/ when > 1)')
    ap.add_argument('--autonav', action='store_true', help='tap OK on the result screen and Battle on home between battles')
    ap.add_argument('--no-realtime', action='store_true', help='replay: every frame, as fast as possible')
    ap.add_argument('--units', default='model', help="'model' (default: LivePerception units) or "
                    "'yolo:<model>[+<model>]:<mapping.json>[:conf=.5,cu=ne|gpu|cpu|all,device=cpu|mps,every=1]': a YOLO "
                    "detector replaces only the record's units / unknown_units (live/perception/yolo_units.py)")
    a = ap.parse_args(argv)
    import signal

    def _term(signum, frame):                 # TERM (the documented stop) must run the finally: logs, session.json
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, _term)
    seconds = min(a.seconds, 900*max(1, min(a.matches, 4)))
    # one driver at a time (one operator): an exclusive flock held for the process lifetime; a second driver exits
    lock_path = Path(os.path.expanduser(os.environ.get('LL_LOCK_FILE', '~/clasher-live/loop/driver.lock')))
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    import fcntl
    lock_fd = open(lock_path, 'a+')
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_fd.seek(0)
        sys.exit(f'another driver holds {lock_path} ({lock_fd.read().strip() or "unknown"}): refusing to start')
    lock_fd.seek(0); lock_fd.truncate(); lock_fd.write(f'pid {os.getpid()} out {a.out} started {time.strftime("%FT%T%z")}\n')
    lock_fd.flush()
    out = Path(a.out)
    if out.exists():                          # a reused session name must not stall the ladder (s10 restart, 10-16)
        out = out.with_name(f"{out.name}-{time.strftime('%H%M%S')}")
        print(f'run dir {a.out} exists; using {out}', file=sys.stderr)
    out.mkdir(parents=True)
    if shutil.disk_usage(out).free < DISK_STOP:
        sys.exit('free space below the stop floor')
    lock = threading.Lock()
    cur = {}

    def open_match(k):
        """Per-battle dir (the run dir itself for a single battle): logs, video writer."""
        d = out if a.matches == 1 else out/f'm{k:02d}'
        d.mkdir(exist_ok=True); (d/'video').mkdir()
        cur.update(dir=d, k=k, wr=Writer(d/'video'),
                   logs={x: open(d/f'{x}.jsonl', 'a', buffering=1) for x in ('frames', 'decisions', 'taps', 'events', 'perception')})

    def log(kind, row):
        with lock:
            cur['logs'][kind].write(json.dumps(row, default=float) + '\n')

    def close_match(state, n, sess, restarts, summary='session.json'):
        cur['wr'].close()
        st = dict(state=state, frames=n, writer_dropped=cur['wr'].dropped, tr_stats=dict(sess.tr.stats), restarts=restarts)
        try:
            sess.close()
        except Exception as ex:
            st['close_error'] = repr(ex)
        (cur['dir']/summary).write_text(json.dumps(st, indent=1, default=str) + '\n')
        (cur['dir']/'session-config.json').write_text(json.dumps(session_cfg, indent=1, default=str) + '\n')
        for f in cur['logs'].values():
            f.close()

    open_match(1)
    from infer import LivePerception
    from bot.players.base import WAIT
    from bot.live.player import make_live_player
    from bot.live.translate import LiveSession
    t = time.monotonic()
    perc = LivePerception(a.export)
    yolo = None
    if a.units != 'model':                      # YOLO units (perception keeps hand, elixir, towers, clock, events)
        from yolo_units import from_spec
        yolo = from_spec(a.units)
    deck = load_deck()
    rt, sess = build_bot(a.player, deck)
    raw = {}                                   # the frame model's last outputs (overlay: what the model sees)
    _frame = perc.frame
    def _tap_frame(*args):
        o = _frame(*args); raw['out'] = o; return o
    perc.frame = _tap_frame
    from clasher.vision.l1_v4 import prepare_pixels
    import hashlib
    export_sha = hashlib.sha256((Path(a.export)/'frame.pt').read_bytes()).hexdigest()
    loaded = dict(ev='loaded', load_s=time.monotonic() - t, player=a.player, fast=os.environ.get('CLASHER_LIVE_FAST'),
                  export=str(a.export), export_frame_sha256=export_sha, units=a.units)
    log('events', loaded)
    # everything needed to replay LiveSession offline from perception.jsonl (bot lead): deck, players, export, options
    client = {}
    try:                                       # read-only: the live client's package version (CARD LEAD / bot lead)
        pkg = subprocess.run([ADB, '-P', str(a.adb_port), '-s', a.serial, 'shell',
                              'dumpsys package com.supercell.clashroyale | grep -E "versionName|versionCode|lastUpdateTime"; '
                              'getprop persist.sys.timezone'], capture_output=True, text=True, timeout=20).stdout
        for tok in pkg.split():
            if '=' in tok and tok.split('=')[0] in ('versionName', 'versionCode', 'lastUpdateTime'):
                client[tok.split('=')[0]] = tok.split('=', 1)[1]
        lines = pkg.strip().splitlines()
        upd = [l for l in lines if 'lastUpdateTime' in l]
        if upd:
            client['lastUpdateTime'] = upd[0].split('=', 1)[1].strip()
        client['guest_timezone'] = lines[-1].strip() if lines else None
    except Exception as ex:
        client['error'] = repr(ex)[:200]
    session_cfg = dict(schema='clasher.live.loop.session-config.v1', client=client, deck=deck, deck_out_of_scope=[c for c in deck if c not in C56], player=a.player,
                       fast=os.environ.get('CLASHER_LIVE_FAST'), export=str(a.export), export_frame_sha256=export_sha,
                       unit_threshold=perc.ut, tower_threshold=perc.tt, event_threshold=perc.et, unit_filter=None,
                       translator=dict(cls='bot.live.translate.LiveTranslator', unknown_card='drop', plays_from='births'),
                       session=dict(cls='bot.live.translate.LiveSession', seed=0, command_delay=27, expire=90),
                       pins=os.environ.get('CLASHER_BOT_RUNTIME_PINS'),
                       overrides='elixir from the HUD bar (floored at pending reservations), phase/clock_s from the tick '
                                 'anchored at battle start, towers alive/hp from the drawn numbers (towers.py)',
                       logged='live', units_source='model' if yolo is None else dict(spec=a.units, **yolo.info()))
    (cur['dir']/'session-config.json').write_text(json.dumps(session_cfg, indent=1, default=str) + '\n')
    crop = [float(v) for v in a.crop.split(',')]; size = [int(v) for v in a.size.split(',')]
    if a.source == 'live':
        src = LiveFrames(a.bsgrab, crop, size, a.fps, seconds, open(out/'bsgrab.stderr', 'ab'))
    else:
        src = ReplayFrames(a.source.split(':', 1)[1], realtime=not a.no_realtime)
    taps = AdbTaps(a.serial, a.adb_port, lambda r: log('taps', r)) if a.tap == 'adb' else None
    ov, last_play = None, None
    if a.overlay_port:
        from overlay import Overlay
        ov = Overlay(a.overlay_port, every=1)
        ov.deck = list(deck)
        playable = C56
        ov.deck_check = lambda names: None     # any 8 distinct names are recorded; out-of-scope cards block battles
        import deckread
        card_templates = B_load_templates()
    state, streak, miss, start_ms, n, t_end = 'wait', 0, 0, None, 0, time.monotonic() + seconds
    t0_ns, first_hud_ms = None, None
    base_bright = []
    nav_seen, nav_last, nav_t = 0, None, 0.
    nav_stuck_t = time.monotonic()
    was_paused = False
    low_disk = False
    try:
        while time.monotonic() < t_end:
            fr = src.get()
            if fr is None:
                if a.source != 'live':
                    break
                log('events', dict(ev='no_frame', t=time.time())); continue
            t_in = time.perf_counter()
            t0_ns = t0_ns or fr.display_ns
            ts_ms = (fr.display_ns - t0_ns)/1e6
            f, white = normalize(C.to_android(fr.bgr))
            bright = frame_health(f)
            if state == 'battle' and len(base_bright) < 20:
                base_bright.append(bright)
            ref = float(np.median(base_bright)) if len(base_bright) >= 5 else None
            # black frame, or (in battle) dimmed below 80% of this battle's own arena brightness (Bone Pit ~140, a
            # BlueStacks overlay dimmed it to ~100 in s2): no state change, no decision, no tap
            if bright < 40 or (state == 'battle' and ref is not None and bright < .8*ref):
                cur['wr'].put(n, fr.bgr); n += 1
                log('frames', dict(n=n-1, seq=fr.seq, ts_ms=(fr.display_ns - (t0_ns or fr.display_ns))/1e6, state=state,
                                   unhealthy=round(bright, 1)))
                if ov is not None:
                    ov.update(fr.bgr, state=f'PAUSED: frame too dark ({bright:.0f})')
                continue
            present, elixir = hud_read(f)
            deck_oos = [c for c in deck if c not in C56]
            why = ('file' if PAUSE_FILE.exists() else 'page' if (ov is not None and ov.paused) else
                   'deck_out_of_scope' if deck_oos else 'low_disk' if (low_disk and state != 'battle') else None)
            paused = why is not None
            if paused != was_paused:
                log('events', dict(ev='paused_by_user' if paused else 'resumed_by_user', reason=why, state=state,
                                   ts_ms=ts_ms, n=n, deck_out_of_scope=deck_oos))
                was_paused = paused
            if ov is not None:
                ov.status.update(deck_out_of_scope=deck_oos, paused_reason=why)
                ov.status.update(state=state, match=f"{out.name}/m{cur['k']:02d}")
                if ov.read_req:                # "Read deck from screen": the Battle Deck page must be open
                    ov.read_req = False
                    r = deckread.read_deck(f, card_templates, save_dir=out/'deck-unknown')
                    known = [c for c in r['cards'] if c]
                    oos = [c for c in known if c not in playable]
                    msg = []
                    if r['unknown']:
                        msg.append(f"unrecognized slots {[i + 1 for i in r['unknown']]} (open Battle Deck? new card -> crop saved)")
                    if oos:
                        msg.append(f"OUT OF SCOPE (the bot cannot see or play): {', '.join(oos)}")
                    ov.read_result = dict(r, out_of_scope=oos, t=time.time(),
                                          msg='; '.join(msg) or 'all 8 cards recognized and in scope; press Apply deck')
                    log('events', dict(ev='deck_read', cards=r['cards'], scores=r['scores'], out_of_scope=oos))
                if state == 'wait':
                    newdeck = ov.take_deck()
                    if newdeck:
                        deck = newdeck; ov.deck = list(deck)
                        DECK_FILE.write_text(json.dumps(deck))
                        sess = LiveSession(rt, make_live_player(rt, a.player), deck)
                        session_cfg['deck'] = list(deck)
                        session_cfg['deck_out_of_scope'] = [c for c in deck if c not in C56]
                        log('events', dict(ev='deck_change', deck=deck))
            row = dict(n=n, seq=fr.seq, ts_ms=ts_ms, cap_ms=(fr.recv_ns - fr.display_ns)/1e6, hud=present, white=round(white),
                       elixir=elixir, state=state)
            cur['wr'].put(n, fr.bgr); n += 1
            if n % 50 == 1:
                # a transient swap spike must not kill the session: below DISK_PAUSE no NEW battle starts (a battle in
                # progress is finished), resume above DISK_RESUME; only below DISK_STOP does the driver stop
                free = shutil.disk_usage(out).free
                if free < DISK_STOP:
                    log('events', dict(ev='stop', why='free space below the stop floor', free_gb=round(free/GB, 2))); break
                if not low_disk and free < DISK_PAUSE:
                    low_disk = True; log('events', dict(ev='low_disk', free_gb=round(free/GB, 2), state=state))
                elif low_disk and free > DISK_RESUME:
                    low_disk = False; log('events', dict(ev='disk_ok', free_gb=round(free/GB, 2), state=state))
            if state == 'wait' and a.autonav and taps is not None and not present and not paused:
                kind = screen_kind(f)
                nav_seen = nav_seen + 1 if kind and kind == nav_last else (1 if kind else 0); nav_last = kind
                if kind and nav_seen >= 5 and time.monotonic() - nav_t > 4:     # stable for 5 frames, 4 s apart
                    x, y = NAV_TAP[kind]
                    taps.p.stdin.write(f'input tap {x} {y}\n'); taps.p.stdin.flush()
                    nav_t, nav_seen = time.monotonic(), 0
                    log('events', dict(ev='nav_tap', screen=kind, xy=[x, y], ts_ms=ts_ms))
                # unknown screen (reward, popup, menu, Sam in the menus): never tap; log once per 60 s of no progress
                if kind is None and time.monotonic() - max(nav_t, nav_stuck_t) > 60:
                    nav_stuck_t = time.monotonic()
                    log('events', dict(ev='nav_stuck', ts_ms=ts_ms, n=n-1, note='unknown screen for 60 s, no tap'))
            if state == 'wait':
                streak = streak + 1 if present else 0
                first_hud_ms = (first_hud_ms if streak > 1 else ts_ms) if present else None
                # paused (Sam in the menus): menu screens can flash HUD-like pixels -> need 1.5 s of HUD, not 0.3 s
                if streak >= (15 if paused else 3):
                    state, start_ms = 'battle', first_hud_ms
                    perc.reset(); sess.tr.clock.anchor(0, start_ms); towers = TW.TowerReader()
                    yolo_last, yolo_k = None, 0
                    tower_last, tower_missing = {}, 0
                    last_play_ms, stall = start_ms, False
                    if os.environ.get('LL_TEST_STALL') == '1' and getattr(sess.player, 'search', None) is not None:
                        from bot.players.base import Decision as _D     # test hook: the search tier always WAITs
                        sess.player.search.act = lambda view, **kw: _D(WAIT, stats={'source': 'test-stall', 'wall_seconds': 0.0})
                    log('events', dict(ev='match_start', ts_ms=start_ms, n=n))
                    if a.source == 'live':
                        threading.Thread(target=grab_arena_bg, daemon=True, args=(
                            a.bsgrab, crop, Path(os.path.expanduser('~/clasher-live/loop/arena-bgs'))/a.arena,
                            out.name + ('' if a.matches == 1 else f"-m{cur['k']:02d}"),
                            log)).start()
                if ov is not None:
                    ov.update(fr.bgr, state='PAUSED (no taps)' if paused else 'waiting for battle', elixir=elixir)
                log('frames', row); continue
            if state == 'battle':
                miss = 0 if present else miss + 1
                if miss >= 3*a.fps and ts_ms - start_ms < FALSE_MATCH_MS:
                    # a 'battle' shorter than 30 s is a false HUD transition (s10-m01: 4.8 s while Sam was in the menus):
                    # logged, its dir renamed mNN-false-<time> with false_match.json (no session.json), and it does not
                    # count toward --matches; the same mNN is reopened with a fresh LiveSession
                    log('events', dict(ev='false_match', start_ms=start_ms, end_ms=ts_ms, seconds=round((ts_ms - start_ms)/1e3, 1),
                                       n=n, paused=paused))
                    log('frames', row)
                    k = cur['k']
                    if a.matches > 1:
                        close_match('false_match', n, sess, getattr(src, 'restarts', 0), summary='false_match.json')
                        cur['dir'].rename(cur['dir'].with_name(f"{cur['dir'].name}-false-{time.strftime('%H%M%S')}"))
                        open_match(k)
                        log('events', dict(loaded, ev='loaded', load_s=0, session=k, after='false_match'))
                        (cur['dir']/'session-config.json').write_text(json.dumps(session_cfg, indent=1, default=str) + '\n')
                    sess = LiveSession(rt, make_live_player(rt, a.player), deck)
                    state, streak, miss, first_hud_ms, last_play = 'wait', 0, 0, None, None
                    if a.matches > 1:
                        n, t0_ns = 0, None
                    base_bright = []
                    continue
                if miss >= 3*a.fps:
                    state = 'ended'; log('events', dict(ev='match_end', ts_ms=ts_ms, n=n)); log('frames', row)
                    if cur['k'] >= a.matches:
                        break
                    close_match(state, n, sess, getattr(src, 'restarts', 0))      # next battle: fresh logs + bot
                    open_match(cur['k'] + 1)
                    sess = LiveSession(rt, make_live_player(rt, a.player), deck)
                    log('events', dict(loaded, ev='loaded', load_s=0, session=cur['k']))
                    (cur['dir']/'session-config.json').write_text(json.dumps(session_cfg, indent=1, default=str) + '\n')
                    state, streak, miss, n, t0_ns, first_hud_ms, last_play = 'wait', 0, 0, 0, None, None, None
                    base_bright = []
                    continue
                if not present:
                    log('frames', row); continue
                t1 = time.perf_counter(); cv = C.canvas(f); t2 = time.perf_counter()
                # YOLO units on a worker thread, overlapping our frame model; every=N: detect on every Nth battle frame and
                # reuse the last detections in between (units_age_ms in the record)
                fut = yolo.submit(f) if yolo is not None and yolo_k % yolo.every == 0 else None
                yolo_k += 1
                arena_px, hud_px = prepare_pixels(cv)
                rec = perc.step_prepared(arena_px, hud_px, ts_ms, unit_floor=.05 if ov is not None else None)
                if yolo is not None:
                    tw0 = time.perf_counter()
                    if fut is not None:
                        try:
                            yolo_last = dict(fut.result(), ts_ms=ts_ms)
                        except Exception as ex:          # no units this frame rather than a dead loop
                            yolo_last = dict(units=[], unknown_units=[], units_yolo=[], ts_ms=ts_ms, error=repr(ex)[:200])
                            log('events', dict(ev='yolo_error', n=n-1, error=yolo_last['error']))
                    row.update(yolo_ms=yolo.last_ms if fut is not None else None, yolo_wait_ms=1e3*(time.perf_counter() - tw0))
                    rec['units_model'] = rec['units']
                    rec['units'], rec['unknown_units'] = list(yolo_last['units']), list(yolo_last['unknown_units'])
                    rec['units_yolo'], rec['units_age_ms'] = yolo_last['units_yolo'], ts_ms - yolo_last['ts_ms']
                towers.apply(rec, f)       # tower alive/HP from the drawn numbers (perception's HP head misreads)
                gone = TW.guard_towers(rec, tower_last)       # always 6 towers; missing -> last state; dead stays dead
                if gone:
                    tower_missing += gone
                    if tower_missing == gone or tower_missing % 50 < gone:      # first time, then every ~50 slots
                        log('events', dict(ev='tower_missing', n=n-1, tick=(ts_ms - start_ms)/50, this_frame=gone,
                                           count=tower_missing))
                t3 = time.perf_counter()
                tick = (ts_ms - start_ms)/50
                # Our taps land ~15 ms after submit, so the HUD bar drops BEFORE the bot's command model (27-tick delay)
                # expects; floor the reading at the still-pending reservations (CommandQueue.reserved_own raises otherwise,
                # which breaks the 250 ms fast-tier gate for the rest of the match: live1, tick 895).
                reserved = sum(c.cost for c in sess.ch.pending)
                rec['elixir'] = max(elixir, reserved)
                if reserved > elixir:
                    row['elixir_floored'] = reserved
                rec['phase'] = 1 if tick < 2400 else (2 if tick < 4800 else 3)
                rec['clock_s'] = max(0., 180 - tick/20) if tick < 3600 else max(0., 300 - tick/20)
                if 'out' in raw:                                  # own hand = most probable distinct DECK cards (handread.py)
                    hr = handread.deck_constrained(raw['out'][4][0].float().cpu().numpy(), perc.cards, deck)
                    if hr is not None:
                        rec['hand'] = dict(rec.get('hand') or {}, cards=hr['cards'], probs=hr['probs'], next=hr['next'],
                                           next_prob=hr['next_prob'], raw=hr['raw'])
                ownplay.dedupe_own_events(rec, sess)            # one own play per deploy (see ownplay.py)
                log('perception', dict(rec, n=n-1, tick=tick, ts_ms=ts_ms))   # exactly what LiveSession.step gets
                pend0 = len(sess.ch.pending)
                d, err = None, None
                try:
                    d = None if paused else sess.step(rec)
                except Exception as ex:          # logged; the loop keeps feeding frames
                    import traceback
                    err = repr(ex)[:300]
                    if not getattr(sess, '_tb_logged', 0):
                        sess._tb_logged = 1; log('events', dict(ev='step_error', tb=traceback.format_exc()[-3000:]))
                t4 = time.perf_counter()
                row.update(tick=tick, canvas_ms=1e3*(t2-t1), perc_ms=1e3*(t3-t2), step_ms=1e3*(t4-t3),
                           pre_ms=1e3*(t1-t_in), hand=rec['hand'], n_units=len(rec['units']),
                           units=[(u['owner'], u.get('cls'), round(u['x'], 1), round(u['y'], 1)) for u in rec['units']],
                           towers=[(t['owner'], t['kind'][0], t['side'][0], int(t['alive']), t.get('hp_read'))
                                   for t in rec['towers']],
                           events=[(e['owner'], e['card'], round(e['x'], 1), round(e['y'], 1)) for e in rec['events']],
                           err=err)
                # stall guard: full elixir and no play for STALL_MS in a battle the bot is playing -> fast tier (rl5
                # student on the deck-constrained hand) until the next play; logged and shown on the overlay
                if not paused and elixir is not None and elixir >= 9.5 and ts_ms - last_play_ms > STALL_MS and not stall:
                    stall = True
                    log('events', dict(ev='stall_alert', n=n-1, tick=tick, ts_ms=ts_ms, elixir=elixir,
                                       session_started=bool(sess.started), seconds=round((ts_ms - last_play_ms)/1e3, 1)))
                    if hasattr(sess.player, 'search_disabled'):
                        sess.player.search_disabled = True
                if d is not None:
                    submitted = len(sess.ch.pending) > pend0 and d.action < WAIT
                    if submitted:
                        last_play_ms = ts_ms
                        if stall:
                            stall = False
                            if hasattr(sess.player, 'search_disabled'):
                                sess.player.search_disabled = False
                            log('events', dict(ev='stall_cleared', n=n-1, tick=tick, card_source=(d.stats or {}).get('source')))
                    drow = dict(n=n-1, tick=tick, poll=sess.last_poll, action=int(d.action), submitted=submitted,
                                step_ms=1e3*(t4-t3), stats=d.stats, own=sess.log[-1] if sess.log else None)
                    if submitted:
                        slot, card_xy, target_xy = C.action_target(d.action)
                        card = sess.ch.pending[-1].card if sess.ch.pending else None
                        drow.update(slot=slot, card=card, card_xy=card_xy, target_xy=target_xy)
                        if not valid_tap(card_xy, target_xy):
                            drow['tap'] = 'refused: outside the card row / arena'
                        elif taps is not None:
                            tw = time.perf_counter()
                            drow.update(tap_id=taps.play(card_xy, target_xy), frame_to_tap_ms=1e3*(tw - t_in),
                                        tap_write_ns=time.time_ns())
                            last_play = dict(t=time.time(), target_xy=target_xy, card=card)
                        else:
                            drow['tap'] = 'dry'
                    log('decisions', drow)
                if ov is not None:
                    heat = None
                    if 'out' in raw:            # per-owner max over unit identities (towers / spell effects excluded)
                        hm = raw['out'][0][0].float().sigmoid().cpu().numpy()
                        nb = len(perc.identities)
                        keep = [i for i, n in enumerate(perc.identities)
                                if n not in ('KingTower', 'PrincessTower') and not str(n).startswith('fx:')]
                        heat = np.stack([hm[o*nb:(o+1)*nb][keep].max(0) for o in (0, 1)])
                    ov.update(fr.bgr, rec, 'PAUSED (bot not playing)' if paused else ('STALL: fast tier' if stall else 'battle'),
                              tick, elixir, last_play, heat=heat,
                              units_lo=perc.last.get('units_lo', ()))
                log('frames', row)
    finally:
        src.close()
        if ov is not None:
            ov.close()
        if taps is not None:
            time.sleep(1); taps.close()
        close_match(state, n, sess, getattr(src, 'restarts', 0))
    print(json.dumps(dict(state=state, frames=n)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
