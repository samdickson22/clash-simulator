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
STATUS_FILE = Path(os.path.expanduser(os.environ.get('LL_STATUS_FILE', '~/clasher-live/loop/status.txt')))  # the page's between-sessions reason
# Boundary restart (ladder supervisor / staged deploys): if this file exists when a battle ends, the driver takes it (renamed
# <name>.taken-<pid>), logs restart_at_boundary and exits 0 on the result screen, before any nav tap, so the next session
# starts on a screen that waits for it. Never acted on mid-battle or between battles.
RESTART_FILE = Path(os.path.expanduser(os.environ.get('LL_RESTART_FILE', '~/clasher-live/loop/RESTART-AT-BOUNDARY')))
MANIFEST = Path(os.path.expanduser(os.environ.get('LL_MANIFEST', '~/clasher-live/loop/MANIFEST.json')))


def check_manifest():
    """Deployment check at session start: (problems, info). MANIFEST.json = {"commit": ..., "files": {relpath: sha256}}
    with relpaths under the code tree this drive.py runs from (live/loop/../..). Twice the Mac ran other code than we
    believed (PYTHONHASHSEED unset; a stale perception common.py). Missing manifest -> no check (logged), so shipping
    the guard never blocks play; a manifest that does not match -> the caller refuses to start."""
    import hashlib
    bad = [] if os.environ.get('PYTHONHASHSEED') == '0' else [f"PYTHONHASHSEED={os.environ.get('PYTHONHASHSEED')!r}, must be '0'"]
    if not MANIFEST.exists():
        return bad, dict(manifest=None)
    try:
        man = json.loads(MANIFEST.read_text())
        files = man['files']
    except Exception as ex:
        return bad + [f'manifest unreadable: {ex!r}'[:200]], dict(manifest=str(MANIFEST))
    root = HERE.parents[1]
    for rel, want in sorted(files.items()):
        p = root/rel
        if not p.is_file():
            bad.append(f'missing {rel}')
        elif hashlib.sha256(p.read_bytes()).hexdigest() != want:
            bad.append(f'changed {rel}')
    return bad, dict(manifest=str(MANIFEST), commit=man.get('commit'), files=len(files),
                     sha256=hashlib.sha256(MANIFEST.read_bytes()).hexdigest())


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
        self.stop, self.restarts, self.g, self.hold = False, 0, None, False
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        bsgrab, crop, size, fps, seconds = self.args
        t_end = time.monotonic() + seconds
        while not self.stop and time.monotonic() < t_end:      # restart on every SCK interruption (any other SCK client
                                                                # on the Mac can cause -3805; s3 lost capture after 5)
            while self.hold and not self.stop:                   # recrop(): our stream stays closed while the fit runs
                time.sleep(.05)
            bsgrab, crop, size, fps, seconds = self.args         # (recrop may have changed the crop)
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
            if not self.stop and not self.hold:
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

    def recrop(self, fit):
        """Stop the running stream, call fit() (which may run its own one-frame bsgrab), restart with its crop if any."""
        self.hold, new = True, None
        if self.g is not None:
            self.g.close()
        try:
            new = fit()
        finally:
            if new:
                bsgrab, _, size, fps, seconds = self.args
                self.args = (bsgrab, new, size, fps, seconds)
            self.hold = False
        return new


# Self-calibrating capture crop (--crop auto). BlueStacks Air draws a title bar above and a tool sidebar right of the
# Android view, in window points; the view is the remaining rect trimmed to 9:16. Measured on 400x686, 535x926 and
# 554x960 windows (2026-10-17; the adb screencap matched at NCC 0.94-1.00). Every fit is checked against an adb
# screencap of the same moment on the static HUD rows before use.
CHROME_TOP, CHROME_SIDE = 32., 32.


# Window bounds WITHOUT ScreenCaptureKit: `bsgrab info` queries SCShareableContent, which interrupts a running SCK stream
# (s66b 10-17: both -3805 capture resets, 634-655 ms gaps, within 1 s of a `bsgrab info` from another process). bsbounds
# reads CGWindowListCopyWindowInfo (CoreGraphics). The driver's only SCK calls are its own capture stream and the chrome
# grab of a fit, which runs only before the stream opens or inside recrop() while the stream is closed.
BOUNDS = os.path.expanduser(os.environ.get('LL_BOUNDS', '~/clasher-live/loop/bin/bsbounds'))


def window_bounds():
    """-> (w, h) in points of the BlueStacks window (CoreGraphics, no SCK), or None."""
    try:
        b = json.loads(subprocess.run([BOUNDS], capture_output=True, text=True, timeout=10).stdout)['bounds']
        return float(b[2]), float(b[3])
    except Exception:
        return None


def window_size(bsgrab):
    return window_bounds()


def crop_candidates(w, h):
    wv, hv = w - CHROME_SIDE, h - CHROME_TOP
    if abs(wv*16/9 - hv) <= 3:
        return [[0., CHROME_TOP, wv, hv]]
    if wv*16/9 < hv:                                    # width-limited: letterboxed top/bottom
        ch = wv*16/9
        return [[0., CHROME_TOP + (hv - ch)/2, wv, ch], [0., CHROME_TOP, wv, ch]]
    cw = hv*9/16                                         # height-limited: pillarboxed
    return [[(wv - cw)/2, CHROME_TOP, cw, hv], [0., CHROME_TOP, cw, hv]]


def crop_ncc(bsgrab, crop, size, adb_cmd):
    """One bsgrab frame with `crop` at `size` vs an adb screencap scaled to `size`: the minimum NCC over the static HUD
    rows (top bar, hand row, bottom strip), which moving units do not touch."""
    import struct
    W, H = size
    shot = subprocess.run(adb_cmd, capture_output=True, timeout=15).stdout
    raw = subprocess.run([bsgrab, 'stream', '--crop', ','.join(f'{v:g}' for v in crop), '--size', f'{W},{H}', '--fps', '2',
                          '--frames', '1'], capture_output=True, timeout=20).stdout
    if len(raw) < 32 or not shot:
        return 0.
    _, _, fw, fh, _, _ = struct.unpack('<4sIIIQQ', raw[:32])
    cap = np.frombuffer(raw[32:32 + fw*fh*4], np.uint8).reshape(fh, fw, 4)[..., :3].astype(np.float32)
    ref = cv2.imdecode(np.frombuffer(shot, np.uint8), cv2.IMREAD_COLOR)
    if ref is None:
        return 0.
    ref = cv2.resize(ref, (fw, fh), interpolation=cv2.INTER_AREA).astype(np.float32)
    def ncc(a, b):
        a = a.ravel() - a.mean(); b = b.ravel() - b.mean()
        return float((a*b).sum()/np.sqrt((a*a).sum()*(b*b).sum() + 1e-9))
    rows = [(0, int(.078*fh)), (int(.844*fh), int(.953*fh)), (int(.953*fh), fh)]
    return min(ncc(cap[a:b], ref[a:b]) for a, b in rows)


CROP_STATE = Path(os.path.expanduser(os.environ.get('LL_CROP_STATE', '~/clasher-live/loop/crop-last-good.json')))


def chrome_edges(bsgrab, w, h, scale=2.):
    """Content-independent check of the window chrome: one full-window frame; the sidebar is the first column (from the
    left) that is >= 95% the flat chrome colour, the title bar ends after the last such row. -> dict(side, top) in points,
    or None. The chrome colour is the median of the rightmost 2 px columns (BlueStacks Air dark: 40,40,40). s66 (10-17):
    side 522 / top 32 on the 554x960 window, while two content NCC checks taken ~1 s apart read .92 on the home screen."""
    import struct
    W, H = int(round(w*scale)), int(round(h*scale))
    raw = subprocess.run([bsgrab, 'stream', '--crop', f'0,0,{w:g},{h:g}', '--size', f'{W},{H}', '--fps', '2', '--frames', '1'],
                         capture_output=True, timeout=20).stdout
    if len(raw) < 32:
        return None
    _, _, fw, fh, _, _ = struct.unpack('<4sIIIQQ', raw[:32])
    im = np.frombuffer(raw[32:32 + fw*fh*4], np.uint8).reshape(fh, fw, 4)[..., :3].astype(np.int16)
    return chrome_edges_img(im, w)


def chrome_edges_img(im, w):
    fh, fw = im.shape[:2]
    c = np.median(im[:, -2:].reshape(-1, 3), 0)
    chrome = (np.abs(im - c) <= 4).all(-1)                     # [fh, fw]
    k = fw/float(w)
    body = chrome[int(.1*fh):int(.9*fh)]                       # rows below the title bar, above any bottom chrome
    cols = np.nonzero(body.mean(0) >= .95)[0]
    left = int(.5*fw)
    cols = cols[cols > left]
    if not len(cols):
        return None
    side = int(cols.min())
    rows = np.nonzero(chrome[:int(.2*fh), :side].mean(1) >= .95)[0]
    if not len(rows):
        return None
    top = int(rows.max()) + 1
    return dict(side=round(side/k, 1), top=round(top/k, 1), chrome=[int(v) for v in c])


def auto_crop(bsgrab, size, adb_cmd, thresh, tries=5):
    """Fit the crop for the current window. Exact 9:16 view (the chrome rule gives one candidate): verified by the
    chrome edges (content independent), else by the adb screencap NCC; any verified fit is saved as the last good crop.
    Nothing verified: the last good crop for the SAME window size (method last_good), else crop None."""
    wh = window_bounds()                                      # CoreGraphics: no SCK query
    if wh is None:
        return dict(crop=None, ncc=0., best=None, edges=None, window=None, why='no BlueStacks window (bsbounds)')
    w, h = wh
    scale = float(os.environ.get('LL_WINDOW_SCALE', '2'))
    cands = crop_candidates(w, h)
    best, edges = (0., None), None
    def ok(c, **kw):
        fit = dict(crop=[round(x, 2) for x in c], window=[w, h], **kw)
        try:
            tmp = CROP_STATE.with_name(CROP_STATE.name + '.tmp')
            tmp.write_text(json.dumps(dict(fit, ts=time.strftime('%FT%TZ', time.gmtime()))) + '\n'); os.replace(tmp, CROP_STATE)
        except OSError:
            pass
        return fit
    if len(cands) == 1:
        cx, cy, cw, ch = cands[0]
        for i in range(tries):
            try:
                edges = chrome_edges(bsgrab, w, h, scale)
            except Exception:
                edges = None
            if edges and abs(edges['side'] - (cx + cw)) <= 1.5 and abs(edges['top'] - cy) <= 1.5:
                return ok(cands[0], method='chrome', edges=edges, ncc=None)
            time.sleep(1.)
    for c in cands:
        for _ in range(3):
            v = crop_ncc(bsgrab, c, size, adb_cmd)
            if v > best[0]:
                best = (v, c)
            if v >= thresh:
                return ok(c, method='ncc', ncc=round(v, 4), edges=edges)
    try:
        last = json.loads(CROP_STATE.read_text())
        if [float(x) for x in last['window']] == [w, h] and last.get('crop'):
            return dict(crop=last['crop'], window=[w, h], method='last_good', ncc=round(best[0], 4), edges=edges,
                        last_good_ts=last.get('ts'))
    except Exception:
        pass
    return dict(crop=None, ncc=round(best[0], 4), best=best[1], edges=edges, window=[w, h])


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
        self.acked = {}                        # tap id -> ack time (unix ns): the guest finished both taps
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.p.stdout:
            w = line.split()
            if len(w) == 2 and w[0] == '__ack' and w[1].isdigit():
                n = int(w[1]); t = time.time_ns()
                s = self.sent.pop(n, None)
                self.acked[n] = t
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


class RawDump:
    """--dump-raw EVERY:MAX: lossless PNGs of every EVERY-th battle frame (at most MAX per battle) beside the q85 video,
    for the live-vs-offline input study: raw/NNNNNN.png = fr.bgr, the exact capture the video JPEG is encoded from;
    the first 3 also yolo_in/NNNNNN.png = the exact array passed to YoloUnits.step (normalize(to_android(fr.bgr))).
    A background thread writes (PNG level 1); a full queue drops the dump, never the frame."""
    def __init__(self, d, every, cap):
        self.d, self.every, self.cap, self.k, self.n_saved, self.dropped = d, every, cap, 0, 0, 0
        (d/'raw').mkdir(exist_ok=True); (d/'yolo_in').mkdir(exist_ok=True)
        self.q = queue.Queue(16)
        self.t = threading.Thread(target=self._run, daemon=True); self.t.start()

    def _run(self):
        while True:
            item = self.q.get()
            if item is None:
                return
            path, img = item
            cv2.imwrite(str(path), img, [cv2.IMWRITE_PNG_COMPRESSION, 1])

    def maybe(self, n, raw, yolo_in):
        self.k += 1
        if (self.k - 1) % self.every or self.n_saved >= self.cap:
            return
        try:
            self.q.put_nowait((self.d/'raw'/f'{n:06d}.png', raw.copy()))
            if self.n_saved < 3 and yolo_in is not None:
                self.q.put_nowait((self.d/'yolo_in'/f'{n:06d}.png', yolo_in.copy()))
            self.n_saved += 1
        except queue.Full:
            self.dropped += 1

    def close(self):
        self.q.put(None); self.t.join(60)


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


def B_load_templates():
    import battlelog
    return battlelog.load_templates(HERE/'cards')


# ---- small handsync (LL_HANDSYNC=1; default off = the base LiveSession, byte-for-byte the old behaviour) ------------
# Measured (05, s17-s41 video truth): the bot's TRACKED own hand is wrong on ~8-9% of plays (s41: 11/118), so the tap
# lands on a different card than the bot chose. Small parts, no bot/search/runtime/tracker change:
#  1. slot UI from pixels per hand slot: 'empty' (blue placeholder while a card slides in) / 'coloured' / 'greyed'
#     (rec['hand']['ui']). The HUD read of a COLOURED slot is right 95-99.8% at p >= .1; a GREYED one 59-96%.
#  2. opening wait: the opening order is taken from a dealt hand (no empty slot) read the same on 2 frames, not from
#     the first frame after match start (mid-deal reads made 12 opening plays wrong, e.g. s27-m04 n212).
#  The tracker itself is untouched (base OwnTracker + its whole-hand HUD re-anchor): masking greyed reads from it was
#  measured WORSE on s41 (slot agreement .938 -> .868, re-anchors 150 -> 3), and per-slot swaps broke reservations (r4).
#  + tap guard: a play is not submitted on a slot that is empty, greyed (the bot only plays affordable cards) or
#     coloured with another card read (at any p): WAIT, re-decided next poll; counted in tr_stats tap_guard:*.
#     A coloured_mismatch refusal on a read with hud_precision >= SWAP_PREC puts that
#     card into the tracked slot (feedback), so the next decision sees the card actually shown instead of re-choosing the
#     stale belief (s45-m03: 9 coloured_mismatch refusals in 19 plays). The HUD reads Archers (and Giant) as Valkyrie at
#     p .2-.6 (s44-s46: 30% of coloured Archers frames), so precision is per read card, from video truth (CAL).
HANDSYNC = os.environ.get('LL_HANDSYNC', '0') == '1'
GUARD_ENFORCE = os.environ.get('LL_HANDSYNC_GUARD', 'enforce') != 'measure'   # measure: offline replay only
# Elixir bar flash: for ~2-3 frames after our own play the client flashes the bar (filled colour with green raised: G 70-154
# vs <= 66.5 on 6,746 normal battle frames), and hud_read returns the spent card's cost (4.08 / 3.06) instead of the true
# level; the bot then believed it still had ~2.5 elixir and chose unaffordable cards (s44-m01: 3 of 7 greyed refusals;
# s29-s41: 11 of 565 plays tapped during a flash, 10 unaffordable). During a flash after our play the reading is replaced
# by the last pre-flash reading minus that card's cost (median 0.22 from the next true reading, 120 flashes), until the
# bar shows the post-spend level (reading <= estimate + .8) or 8 frames pass. Default: on with LL_HANDSYNC=1.
ELIXIR_FLASH = os.environ.get('LL_ELIXIR_FLASH', '1' if HANDSYNC else '0') == '1'
# Reservation floor AFTER the pending command is reconciled (default on with LL_HANDSYNC=1). The bot's spendable elixir
# is the reading minus pending commands' costs, so the driver floors the reading at those costs (CommandQueue raises on
# a negative). Floored BEFORE LiveSession.step, a command that completes in that very poll (_reconcile) leaves the floor
# behind as elixir the bot does not have: s47-m01, 8 of 11 greyed refusals (bar 0.3-2.2, believed 3-4 = the card just
# played; 21 of 71 greyed refusals on s44-s47), undoing the flash correction exactly where it applied. Late: the floor is
# applied in SyncSession._reconcile to the commands still pending, on the unfloored reading.
FLOOR_LATE = os.environ.get('LL_FLOOR_LATE', '1' if HANDSYNC else '0') == '1'
# Own-hand classifier: LL_HAND_MODEL=<TorchScript hand.pt> (live/perception/hand/, h1 = live-perc-r3, 2026-10-16) maps the
# normalized Android frame f [1920,1080,3] uint8 BGR -> [5, 56] logits (slots 0-3, next; perc.cards order, checked against
# vocab.json beside it), decoded by the same handread.deck_constrained. Held-out (25 battles): coloured .997 vs ft-r6 .967,
# greyed .995 vs .878, Archers .999 vs .756 (ft-r6's HUD head shares the arena backbone). Unset = ft-r6's HUD head (the
# rollback); with it set, ft-r6's decode is logged beside it in rec['hand']['ft']. Mac CPU at --perc-threads 4: 6.1 ms p50
# per frame. LL_HAND_EVERY=N runs it on every Nth battle frame (reusing the last logits) if FPS suffers.
HAND_MODEL = os.environ.get('LL_HAND_MODEL')
HAND_EVERY = max(1, int(os.environ.get('LL_HAND_EVERY', '1')))


def bar_flash(f):
    """Mean green of the bar's filled columns (Android frame) > 70: the post-spend flash."""
    o = f[1868:1888, 250:1040].astype(np.int16)
    cols = ((o[..., 2] > 170) & (o[..., 0] > 150)).mean(0) > .5
    return bool(cols.sum() >= 20 and o[..., 1][:, cols].mean() > 70)


class ElixirFlash:
    def __init__(self):
        self.last_good, self.left, self.est, self.last_play = None, 0, None, None

    def own_play(self, n, cost):
        self.last_play = (n, cost)

    def update(self, f, elixir, n):
        """-> (elixir to use, raw reading if it was replaced else None)."""
        if self.left == 0 and self.last_good is not None and self.last_play and n - self.last_play[0] <= 15 and bar_flash(f):
            self.est, self.left = max(0., self.last_good - self.last_play[1]), 8
        if self.left > 0:
            if elixir <= self.est + .8:
                self.left = 0
            else:
                self.left -= 1
                return self.est, elixir
        self.last_good = elixir
        return elixir, None
_SLOT_X = ((242, 429), (444, 632), (647, 835), (850, 1037))
SLOT_BOXES = [(x1 + 11, 1619, x2 - 11, 1828) for x1, x2 in _SLOT_X]      # Android px (canvas.HUD_MAP card targets)
# Precision of the HUD's read of a COLOURED slot, P(video truth == read), per read card and p bin (CAL_BINS lower edges),
# from slot_audit video truth on s29-s35 + s41-s43 (live/loop/hud_calibration.py); None = under 30 frames (untrusted).
# Cards not in CAL (a deck change) are never swapped in: the guard then works as r2.
# A table belongs to ONE hand head, keyed by the sha256 of the model whose hand reads it was measured on (the export
# frame.pt ft-r6, or LL_HAND_MODEL's hand.pt when set). At session start CAL = CALS[hand head]; a head without a table
# turns swaps off (event hud_cal_off) until one is measured (hud_calibration.py, on labels that predate that head).
CAL_BINS = (0., .3, .5, .7, .9)
CALS = {
    '650bd5cf5d6677de7da2837cee401ea66efa17f9791c4bdfa942636aa97e63da': {"Archers": [0.985, 0.999, 1.0, None, None], "Cannon": [0.957, 0.998, 1.0, 1.0, 1.0], "Fireball": [None, None, None, None, 1.0], "Giant": [None, None, None, 1.0, 1.0], "MiniPekka": [0.582, 0.993, 1.0, 1.0, 1.0], "Minions": [0.254, 0.875, 0.917, 1.0, 1.0], "Musketeer": [0.566, None, 1.0, 1.0, 1.0], "Valkyrie": [0.843, 0.731, 0.956, None, None]},   # ft-r6 HUD head
    # h1 (LL_HAND_MODEL hand.pt): live-perc-r3, held-out sessions s20 s25 s27 s33 s39 s42 s46 (labels predate h1)
    '027a8c8f8444aa21972ade53282ab4e734f00f217d8228f7ce6993ae8ffe2fc8': {"Archers": [None, None, None, None, 0.9993], "Cannon": [None, None, None, None, 1.0], "Fireball": [None, None, None, None, 1.0], "Giant": [None, None, None, None, 1.0], "MiniPekka": [None, None, None, None, 1.0], "Minions": [None, None, None, None, 1.0], "Musketeer": [None, None, None, None, 1.0], "Valkyrie": [None, None, None, None, 1.0]},
    # h1.1 (live-perc-r3, h1 + Sam's Bats/Zap deck): coloured slot frames of s63-m02..m07 (ft-r6 sessions h1.1 never
    # trained on, 13.8k frames), truth = slot_audit video truth (cal_h11.py, analysis-20261016/h11-cal)
    '8ae221cab44a87a4dfe598ae2d2c00a84f6ad35f0af14b825743c8296b5b36c0': {"Archers": [None, None, None, None, 0.998], "Bats": [None, None, None, None, 1.0], "Cannon": [None, None, None, None, 1.0], "Fireball": [None, None, None, None, 1.0], "Giant": [None, None, None, None, 1.0], "MiniPekka": [None, None, None, None, 1.0], "Valkyrie": [None, None, None, None, 1.0], "Zap": [None, None, None, None, 1.0]},
    # x2a (live-perc-r3, 121-card vocab): coloured slot frames of r3's held-out s63-m01/m02 + s65-m01..m04 (10.2k frames),
    # slot_audit video truth (analysis-20261016/x2a-cal); rows only for the deck it was measured on (others: no swaps)
    'fbb52a6c58010dafc014b6afab792d89c89191627a1782965d167f9d4ac2579e': {"Archers": [None, None, None, None, 1.0], "Bats": [None, None, None, None, 1.0], "Cannon": [None, None, None, None, 1.0], "Fireball": [None, None, None, None, 1.0], "Giant": [None, None, None, None, 1.0], "MiniPekka": [None, None, None, None, 1.0], "Valkyrie": [None, None, None, None, 1.0], "Zap": [None, None, None, None, 1.0]},
}
CAL = dict(CALS['650bd5cf5d6677de7da2837cee401ea66efa17f9791c4bdfa942636aa97e63da'])        # the table in use: replaced at session start by the hand head's (empty: swaps off)
CAL_HEAD = '650bd5cf5d6677de7da2837cee401ea66efa17f9791c4bdfa942636aa97e63da'
TRUST_P = 0.      # coloured-slot reads disagreeing with the tracked card refuse at any p (s44-m01 n586: p .04; refusing
#                   only precise reads let 9 wrong cards through for 9 saved delays on s44-s46)
SWAP_PREC = .98   # ... and a refusal on a read at least this precise corrects the tracked slot (feedback)


def hud_precision(card, p):
    row = CAL.get(card)
    if row is None or p is None:
        return 0.
    return row[max(i for i, b in enumerate(CAL_BINS) if p >= b)] or 0.


def slot_ui(frame):
    """['empty' | 'coloured' | 'greyed'] for the 4 hand slots of a portrait frame of any size."""
    h, w = frame.shape[:2]
    sx, sy = w/1080, h/1920
    out = []
    for x1, y1, x2, y2 in SLOT_BOXES:
        hsv = cv2.cvtColor(frame[int(y1*sy):int(y2*sy), int(x1*sx):int(x2*sx)], cv2.COLOR_BGR2HSV).reshape(-1, 3)
        blue = ((hsv[:, 0] > 95) & (hsv[:, 0] < 125) & (hsv[:, 1] > 120)).mean()
        out.append('empty' if blue > .9 else 'coloured' if hsv[:, 1].mean() > 60 else 'greyed')
    return out


def _spec_record(var):
    """{path, sha256} of a translator switch spec named by an env var (None when unset): replays can then rebuild it."""
    import hashlib
    p = os.environ.get(var)
    return None if not p else dict(path=p, sha256=hashlib.sha256(Path(p).read_bytes()).hexdigest())


def playable_cards(rt):
    """Cards our deck may hold: the C56, or with a full card-scope runtime (the card-pool switch, e.g.
    CLASHER_BOT_RUNTIME_PINS=live16402b-r3) every playable card it has: its config cards minus level variants
    ('level12:Knight'), each with a cost."""
    if (getattr(rt, 'pins', None) or {}).get('card_scope', 'c56') == 'full':
        return {c for c in rt.R.config['cards'] if ':' not in c and c in rt.R.costs}
    return set(C56)


# LL_UNITS_BOT=1: log what the bot's board got per translated frame (frames.jsonl units_bot, parallel to rec['units']: the
# card after true ids (alias = the C56 look-alike it replaced), the owner after the learned owner model (owner_det = the
# detector's), the body the unit tracker assigned, the raw detector class), and let the overlay draw it instead of
# units[].cls (Sam saw proxy labels: Barbarians shown as Knight, Tombstone as Cannon). Read-only wrapper around
# LiveTranslator.assign; translate.py unchanged. Off = identical.
UNITS_BOT = os.environ.get('LL_UNITS_BOT', '0') == '1'


def board_hook(tr):
    inner = getattr(tr, 'assign', None)
    if inner is None:
        return
    names = {tuple(v): k for k, v in (getattr(tr, 'units', None) or {}).items()}
    tr.board_last = None

    def assign(record):
        res = inner(record)
        if not record.get('_synthetic'):
            try:
                units = record.get('units') or ()
                raw = record.get('units_yolo')
                raw = raw if raw is not None and len(raw) == len(units) else [None]*len(units)
                rows = []
                for u, r, a in zip(units, raw, res[0]):
                    row = dict(card=u.get('card') or u.get('cls'), owner=int(u['owner']), raw=r)
                    for k in ('alias', 'owner_det'):
                        if k in u:
                            row[k] = u[k]
                    body = a[0] if a else None
                    row['body'] = None if body is None else (names.get(tuple(body)) or str(body))
                    rows.append(row)
                tr.board_last = (record.get('timestamp_ms'), rows)
            except Exception as ex:
                tr.board_last = (record.get('timestamp_ms'), [dict(error=repr(ex)[:200])])
        return res
    tr.assign = assign


def make_session(rt, player, deck):
    sess = _make_session(rt, player, deck)
    if UNITS_BOT:
        board_hook(sess.tr)
    # Executed own commands (translator own-play history): one dict per tap the guest acknowledged, in order:
    # {card, slot, action, tile (col, row) of the target, submit_tick (the deciding frame's tick), exec_tick (the session
    # clock at the adb ack = both taps done; None in dry runs), tap_id, n}. Also logged as events.jsonl ev 'executed'.
    # executed_from_logs() rebuilds the same list for past battles. Read-only for the bot; nothing reads it yet.
    sess.executed, sess.exec_pending = [], {}
    return sess


def executed_from_logs(run_dir):
    """sess.executed for a recorded battle dir (decisions.jsonl + taps.jsonl + frames.jsonl). exec_tick is
    reconstructed as the deciding frame's tick + (capture latency + frame-to-tap write + write-to-ack) / 50 ms, which
    matches the live value to about a tick; plays without an ack get exec_tick None."""
    d = Path(run_dir)
    cap = {}
    for l in open(d/'frames.jsonl'):
        r = json.loads(l)
        if 'cap_ms' in r:
            cap[r['n']] = r['cap_ms']
    acks = {}
    if (d/'taps.jsonl').exists():
        for l in open(d/'taps.jsonl'):
            r = json.loads(l)
            if 'ack' in r:
                acks[r['ack']] = r.get('write_to_ack_ms')
    out = []
    for l in open(d/'decisions.jsonl'):
        r = json.loads(l)
        if not r.get('submitted') or r.get('card') is None:
            continue
        row, col = divmod(int(r['action']) % 576, 18)
        tid, ack = r.get('tap_id'), acks.get(r.get('tap_id'))
        ex = None
        if tid is not None and tid in acks and ack is not None and r.get('frame_to_tap_ms') is not None:
            ex = r['tick'] + (cap.get(r['n'], 0.) + r['frame_to_tap_ms'] + ack)/50.
        out.append(dict(card=r['card'], slot=r.get('slot'), action=int(r['action']), tile=(col, row), submit_tick=r['tick'],
                        exec_tick=ex, tap_id=tid, n=r['n']))
    return out


def _make_session(rt, player, deck):
    from bot.live.translate import LiveSession
    if not HANDSYNC:
        return LiveSession(rt, player, deck)

    class GuardedPlayer:
        def __init__(self, inner, sess):
            object.__setattr__(self, 'inner', inner); object.__setattr__(self, 'sess', sess)

        def __getattr__(self, k):
            return getattr(self.inner, k)

        def __setattr__(self, k, v):
            setattr(self.inner, k, v)

        def act(self, view):
            from bot.players.base import WAIT
            d = self.inner.act(view)
            if view.can_act and d.action < WAIT:
                why = self.sess.tap_guard(int(d.action))
                if why:
                    self.sess.tr.stats[f'tap_guard:{why}'] += 1
                    self.sess.guarded.append((int(view.tick), int(d.action), why))
                    if why == 'coloured_mismatch' and GUARD_ENFORCE:
                        self.sess.feedback(int(d.action) // 576)
                    if GUARD_ENFORCE:
                        d.stats = dict(d.stats or {}, tap_guard=why, guarded_action=int(d.action))
                        d.action = WAIT
            return d

    class SyncSession(LiveSession):
        def __init__(self, rt, player, deck):
            super().__init__(rt, player, deck)
            self.player = GuardedPlayer(player, self)
            self._rec, self._open, self.guarded, self.swaps, self._info = None, None, [], [], None

        def step(self, record):
            h = record.get('hand') or {}
            ui = h.get('ui') if isinstance(h, dict) else None
            if not self.started and ui is not None:
                read = (tuple(h.get('cards') or ()), h.get('next'))
                if 'empty' in ui or read != self._open:
                    self._open = None if 'empty' in ui else read
                    self.tr.stats['opening_hand_waits'] += 1
                    return None
            self._rec = record
            return super().step(record)

        def _reconcile(self, info):
            super()._reconcile(info)
            if FLOOR_LATE:                         # floor at the commands STILL pending (see FLOOR_LATE)
                reserved = sum(c.cost for c in self.ch.pending)
                if info.own['elixir'] < reserved:
                    info.own['elixir'] = float(reserved)
                    self.tr.stats['elixir_floor_late'] += 1
            self._info = info

        def feedback(self, slot):
            """A refused coloured_mismatch: put the confidently read card into the tracked slot (every hypothesis; a swap
            with its current place in hand or queue, so hand + queue stay the deck). Never while a card slides in (an empty
            UI slot or an empty tracked slot), never on a pending command's slot or taking the card from one (r4: moving a
            reserved slot broke the command queue). The next poll then decides on the card actually shown."""
            h = (self._rec or {}).get('hand') or {}
            ui = h.get('ui') if isinstance(h, dict) else None
            if ui is None or 'empty' in ui:
                return False
            read, p = (h.get('cards') or [None]*4)[slot], (h.get('probs') or [0]*4)[slot]
            t = self.tr.own_tracker
            busy = {c.action // 576 for c in self.ch.pending}
            if read is None or hud_precision(read, p) < SWAP_PREC or slot in busy or read not in t.deck:
                return False
            for hyp in t.hyps:                       # check first: apply to all hypotheses or to none
                if None in hyp.hand or (read in hyp.hand and hyp.hand.index(read) in busy):
                    return False
            for hyp in t.hyps:
                cur = hyp.hand[slot]
                if cur == read:
                    continue
                if read in hyp.hand:
                    j = hyp.hand.index(read); hyp.hand[slot], hyp.hand[j] = read, cur
                elif read in hyp.queue:
                    q = hyp.queue.index(read); hyp.hand[slot], hyp.queue[q] = read, cur
            self.tr.stats['own_sync:refusal'] += 1
            self.swaps.append((self.last_poll, slot, read))
            return True

        def tap_guard(self, action):
            h = (self._rec or {}).get('hand') or {}
            ui = h.get('ui') if isinstance(h, dict) else None
            if ui is None:
                return None
            slot = action // 576
            if ui[slot] in ('empty', 'greyed'):
                return ui[slot]
            read, p = (h.get('cards') or [None]*4)[slot], (h.get('probs') or [0]*4)[slot]
            if read is not None and read != self.tr.own_tracker.hand[slot] and (p is None or p >= TRUST_P):
                return 'coloured_mismatch'
            return None

    return SyncSession(rt, player, deck)


def build_bot(player_name, deck):
    if os.environ.get('LL_PINS'):       # Mac: register the mac-r1-total pin set before Runtime() (as mac_bench)
        import bot.live.mac_pins as mp
        mp.register(Path(os.environ['LL_PINS']))
    from bot.players.runtime import Runtime
    from bot.live.player import make_live_player
    rt = Runtime()
    sys.meta_path.append(_CodeFallback())   # last resort: modules the pinned runtime src lacks (perception's vision)
    import clasher_core
    if Path(clasher_core.__file__).resolve().parent != rt.native_dir.resolve():
        sys.exit(f'clasher_core loaded from {clasher_core.__file__}, not the pinned {rt.native_dir}')
    player = make_live_player(rt, player_name)
    return rt, make_session(rt, player, deck)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--source', default='live')
    ap.add_argument('--tap', default='adb', choices=('adb', 'none'))
    ap.add_argument('--seconds', type=float, default=420)
    ap.add_argument('--fps', type=int, default=10)
    ap.add_argument('--bsgrab', default=os.path.expanduser('~/clasher-live/loop/bin/bsgrab'))
    ap.add_argument('--crop', default='0,32,510,908',
                    help="x,y,w,h in window points, or 'auto': fit the Android view from bsgrab's window size at session start, "
                         "each battle and on any resize, verified against an adb screencap (--crop-ncc)")
    ap.add_argument('--crop-ncc', type=float, default=.98, help='--crop auto: minimum NCC vs the adb screencap')
    ap.add_argument('--size', default='720,1280')
    ap.add_argument('--export', required=True)
    ap.add_argument('--player', default='LIVE-K4L-R-gs-rw-fc-w200-t4-p4')
    ap.add_argument('--alternate-player', default=None, metavar='NAME',
                    help='play NAME in the even battles of the session (battle 2, 4, ...) and --player in the odd ones (A/B '
                         'within one session); the arm of each battle is in its session-config/session.json')
    ap.add_argument('--adb-port', type=int, default=5047)
    ap.add_argument('--serial', default='127.0.0.1:5555')
    ap.add_argument('--overlay-port', type=int, default=8766,
                    help='the driver\'s own page/MJPEG (0 = off); the always-on overlay_server.py on :8765 proxies it')
    ap.add_argument('--arena', default='goblin-stadium', help='arena-bgs/<arena>/ name for the battle-start frames')
    ap.add_argument('--matches', type=int, default=1, help='battles in one session (each in <out>/mNN/ when > 1)')
    ap.add_argument('--autonav', action='store_true', help='tap OK on the result screen and Battle on home between battles')
    ap.add_argument('--no-realtime', action='store_true', help='replay: every frame, as fast as possible')
    ap.add_argument('--dump-raw', default=None, metavar='EVERY:MAX',
                    help='lossless PNG of every EVERY-th battle frame (at most MAX per battle) in <match>/raw/ (study only; off by default)')
    ap.add_argument('--dump-raw-battles', type=int, default=0, metavar='N',
                    help='with --dump-raw: dump only the first N battles of the session (0 = every battle, the default)')
    ap.add_argument('--dump-raw-every-n-battles', type=int, default=0, metavar='N',
                    help='with --dump-raw: ALSO dump every Nth battle of the session (battles 1, N+1, 2N+1, ...); 0 = off '
                         '(unchanged); combined with --dump-raw-battles B: a battle dumps if k <= B or (k-1) %% N == 0')
    ap.add_argument('--perc-threads', type=int, default=0,
                    help='torch intra-op threads while our frame model runs (0 = unchanged: the bot pins torch to 1 thread '
                         'process-wide; 4 roughly halves perc_ms on the Mac); restored right after each frame')
    ap.add_argument('--units', default='model', help="'model' (default: LivePerception units) or "
                    "'yolo:<model>[+<model>]:<mapping.json>[:conf=.5,cu=ne|gpu|cpu|all,device=cpu|mps,every=1]': a YOLO "
                    "detector replaces only the record's units / unknown_units (live/perception/yolo_units.py)")
    a = ap.parse_args(argv)
    import signal

    def _term(signum, frame):                 # TERM (the documented stop) must run the finally: logs, session.json
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, _term)
    seconds = a.seconds              # whole session (bsgrab's own 900 s stream cap is handled by LiveFrames' restarts)
    player_for = lambda k: a.alternate_player if (a.alternate_player and k % 2 == 0) else a.player
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
        st = dict(state=state, frames=n, writer_dropped=cur['wr'].dropped, tr_stats=dict(sess.tr.stats), restarts=restarts,
                  capture=session_cfg.get('capture'), player=session_cfg.get('player'), arm=session_cfg.get('arm'))
        if cur.get('dump') is not None:          # --dump-raw: flush this battle's PNGs
            cur['dump'].close()
            st['dump_raw'] = dict(saved=cur['dump'].n_saved, dropped=cur['dump'].dropped)
            cur['dump'] = None
        try:
            sess.close()
        except Exception as ex:
            st['close_error'] = repr(ex)
        (cur['dir']/summary).write_text(json.dumps(st, indent=1, default=str) + '\n')
        (cur['dir']/'session-config.json').write_text(json.dumps(session_cfg, indent=1, default=str) + '\n')
        for f in cur['logs'].values():
            f.close()

    open_match(1)
    bad, man_info = check_manifest()                # before anything loads and before any tap
    if bad:
        log('events', dict(ev='manifest_refused', problems=bad[:20], **man_info))
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATUS_FILE.write_text('REFUSED (deployment check): ' + '; '.join(bad)[:400] + '\n')
        print('deployment check failed:', *bad[:20], sep='\n  ', file=sys.stderr)
        return 3
    log('events', dict(ev='manifest_ok' if man_info.get('manifest') else 'manifest_absent', **man_info))
    from infer import LivePerception
    from bot.players.base import WAIT
    from bot.live.player import make_live_player
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
    hand_model, hand_info, hand_cards = None, None, None
    if HAND_MODEL:
        import torch
        hp = Path(os.path.expanduser(HAND_MODEL))
        vj = json.loads((hp.parent/'vocab.json').read_text())
        voc, not_legal = vj['cards'], list(vj.get('not_deck_legal') or ())
        hand_model = torch.jit.load(str(hp), map_location='cpu').eval()
        with torch.inference_mode():                   # the logit width must be the vocab (+ an optional 'empty' class)
            width = int(hand_model(torch.zeros((1920, 1080, 3), dtype=torch.uint8)).shape[-1])
        why = ('vocab.json is not a list of distinct card names' if not (voc and all(isinstance(c, str) for c in voc)
                                                                         and len(set(voc)) == len(voc)) else
               f'logit width {width} != {len(voc)} vocab cards (+1 empty)' if width not in (len(voc), len(voc) + 1) else None)
        if why:
            log('events', dict(ev='hand_model_refused', path=str(hp), why=why))
            STATUS_FILE.write_text(f'REFUSED (hand model): {why} ({hp.parent})\n')
            return 3
        hand_cards = list(voc)
        hand_info = dict(path=str(hp), sha256=hashlib.sha256(hp.read_bytes()).hexdigest(), every=HAND_EVERY,
                         vocab=len(voc), vocab_is_export=hand_cards == list(perc.cards), not_deck_legal=not_legal)
        log('events', dict(ev='hand_model', **hand_info))
    # Our own hand is read over the hand head's vocabulary (LL_HAND_MODEL's vocab.json, in its logit order; else the
    # export's perc.cards): a deck card outside it could never be read in hand, so it stays out of scope (paused) even
    # when the runtime could play it. PLAYABLE = runtime-playable cards that the hand head can read.
    # vocab.json "not_deck_legal" (e.g. Ronin: no art, untrained head row): such a card is never decoded into the hand;
    # a deck holding it is out of scope (paused, no taps) like any card the head cannot read.
    hand_cards = hand_cards if hand_model is not None else list(perc.cards)
    PLAYABLE = playable_cards(rt) & (set(hand_cards) - set(hand_info['not_deck_legal'] if hand_info else ()))
    global CAL_HEAD
    hand_head = hand_info['sha256'] if hand_info else export_sha
    CAL.clear(); CAL.update(CALS.get(hand_head, {}))   # the precision table measured on this hand head, if any
    CAL_HEAD = hand_head if hand_head in CALS else None
    if HANDSYNC and not CAL:
        log('events', dict(ev='hud_cal_off', hand_head=hand_head, source='hand_model' if hand_info else 'export'))
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
    session_cfg = dict(schema='clasher.live.loop.session-config.v1', client=client, deck=deck, deck_out_of_scope=[c for c in deck if c not in PLAYABLE], player=a.player,
                       fast=os.environ.get('CLASHER_LIVE_FAST'), export=str(a.export), export_frame_sha256=export_sha,
                       unit_threshold=perc.ut, tower_threshold=perc.tt, event_threshold=perc.et, unit_filter=None,
                       translator=dict(cls='bot.live.translate.LiveTranslator', unknown_card='drop', plays_from='births'),
                       session=dict(cls=type(sess).__name__, handsync=HANDSYNC, elixir_flash=ELIXIR_FLASH, seed=0, command_delay=27, expire=90,
                                    swap_prec=SWAP_PREC, hud_cal=bool(CAL), cal_head=(CAL_HEAD or '')[:12], floor_late=FLOOR_LATE),
                       hand_model=hand_info,
                       pins=os.environ.get('CLASHER_BOT_RUNTIME_PINS'), manifest=man_info,
                       card_scope=(getattr(rt, 'pins', None) or {}).get('card_scope', 'c56'), playable_cards=len(PLAYABLE),
                       true_ids=_spec_record('CLASHER_LIVE_TRUE_IDS'), play_decider=_spec_record('CLASHER_LIVE_PLAY_DECIDER'),
                       owner_model=_spec_record('CLASHER_LIVE_OWNER_MODEL'),
                       overrides='elixir from the HUD bar (floored at pending reservations), phase/clock_s from the tick '
                                 'anchored at battle start, towers alive/hp from the drawn numbers (towers.py)',
                       logged='live', perc_threads=a.perc_threads, dump_raw=a.dump_raw, dump_raw_battles=a.dump_raw_battles, dump_raw_every_n_battles=a.dump_raw_every_n_battles, units_source='model' if yolo is None else dict(spec=a.units, **yolo.info()))
    (cur['dir']/'session-config.json').write_text(json.dumps(session_cfg, indent=1, default=str) + '\n')
    size = [int(v) for v in a.size.split(',')]
    adb_shot = [ADB, '-P', str(a.adb_port), '-s', a.serial, 'exec-out', 'screencap', '-p']
    cap = dict(mode='fixed', refits=0)
    if a.crop == 'auto' and a.source == 'live':
        fit = auto_crop(a.bsgrab, size, adb_shot, a.crop_ncc)
        log('events', dict(ev='crop_fit', **fit))
        if not fit['crop']:
            STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATUS_FILE.write_text(f"REFUSED: auto-crop failed (window {fit['window']}, best NCC {fit['ncc']})\n")
            print('auto-crop failed:', fit, file=sys.stderr)
            return 3
        crop = fit['crop']; cap.update(mode='auto', crop=crop, ncc=fit['ncc'], window=fit['window'], method=fit.get('method'))
    else:
        crop = [float(v) for v in a.crop.split(',')]; cap['crop'] = crop
    session_cfg['capture'] = dict(cap, size=size)
    session_cfg['player'], session_cfg['arm'] = player_for(1), ('alt' if player_for(1) != a.player else 'main')
    (cur['dir']/'session-config.json').write_text(json.dumps(session_cfg, indent=1, default=str) + '\n')
    if a.source == 'live':
        src = LiveFrames(a.bsgrab, crop, size, a.fps, seconds, open(out/'bsgrab.stderr', 'ab'))
        if cap['mode'] == 'auto':                      # window size watcher: a resize re-fits the crop at the next frame
            def _watch_window():
                while not src.stop:
                    try:
                        ws = window_size(a.bsgrab)                   # CoreGraphics; None (read failed) is never a resize
                        if ws is not None and ws != tuple(cap['window']):
                            src.resized = True
                    except Exception:
                        pass
                    time.sleep(5)
            src.resized = False
            threading.Thread(target=_watch_window, daemon=True).start()
    else:
        src = ReplayFrames(a.source.split(':', 1)[1], realtime=not a.no_realtime)
    taps = AdbTaps(a.serial, a.adb_port, lambda r: log('taps', r)) if a.tap == 'adb' else None
    ov, last_play = None, None
    if a.overlay_port:
        from overlay import Overlay
        ov = Overlay(a.overlay_port, every=1)
        ov.deck = list(deck)
        if yolo is not None:                   # display only: unit boxes from the same per-class ground offsets as the board
            ov.ground_dy = {n: float(o['dy']) for n, o in yolo.offsets.items()}
        playable = PLAYABLE
        ov.deck_check = lambda names: None     # any 8 distinct names are recorded; out-of-scope cards block battles
        import deckread
        card_templates = B_load_templates()
    state, streak, miss, start_ms, n, t_end = 'wait', 0, 0, None, 0, time.monotonic() + seconds
    eflash = ElixirFlash()
    t0_ns, first_hud_ms = None, None
    base_bright = []
    nav_seen, nav_last, nav_t = 0, None, 0.
    nav_stuck_t = time.monotonic()
    was_paused = False
    low_disk = False
    crop_bad = crop_bad_logged = False                 # --crop auto: a resize without a verified fit -> no taps
    try:
        while time.monotonic() < t_end:
            if getattr(src, 'resized', False):           # --crop auto: the window was resized -> re-fit before the next frame
                src.resized = False
                fit = {}
                def _fit():
                    fit.update(auto_crop(a.bsgrab, size, adb_shot, a.crop_ncc))
                    return fit['crop']
                new = src.recrop(_fit)
                log('events', dict(ev='crop_refit', state=state, n=n, **fit))
                if new:
                    crop_bad = crop_bad_logged = False
                    cap.update(crop=new, ncc=fit['ncc'], window=fit['window'], method=fit.get('method')); cap['refits'] += 1
                    session_cfg['capture'] = dict(cap, size=size)
                else:                                    # keep the old crop, no taps; the watcher retries every 5 s
                    crop_bad = True
                    if not crop_bad_logged:
                        crop_bad_logged = True
                        log('events', dict(ev='crop_unverified', why='window resized, no verified fit; taps paused',
                                           window=fit.get('window')))
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
            flash_raw = None
            if ELIXIR_FLASH and present and elixir is not None and state == 'battle':
                elixir, flash_raw = eflash.update(f, elixir, n)
            deck_oos = [c for c in deck if c not in PLAYABLE]
            why = ('file' if PAUSE_FILE.exists() else 'page' if (ov is not None and ov.paused) else
                   'crop_unverified' if crop_bad else
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
                        sess = make_session(rt, make_live_player(rt, player_for(cur['k'])), deck)
                        session_cfg['deck'] = list(deck)
                        session_cfg['deck_out_of_scope'] = [c for c in deck if c not in PLAYABLE]
                        log('events', dict(ev='deck_change', deck=deck))
            row = dict(n=n, seq=fr.seq, ts_ms=ts_ms, cap_ms=(fr.recv_ns - fr.display_ns)/1e6, hud=present, white=round(white),
                       elixir=elixir, state=state)
            if flash_raw is not None:
                row['elixir_flash_raw'] = flash_raw
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
                    perc.reset(); sess.tr.clock.anchor(0, start_ms); towers = TW.TowerReader(); eflash = ElixirFlash()
                    yolo_last, yolo_k = None, 0
                    hand_last, hand_k = None, 0
                    tower_last, tower_missing = {}, 0
                    last_play_ms, stall = start_ms, False
                    if os.environ.get('LL_TEST_STALL') == '1' and getattr(sess.player, 'search', None) is not None:
                        from bot.players.base import Decision as _D     # test hook: the search tier always WAITs
                        sess.player.search.act = lambda view, **kw: _D(WAIT, stats={'source': 'test-stall', 'wall_seconds': 0.0})
                    log('events', dict(ev='match_start', ts_ms=start_ms, n=n))
                    if a.source == 'live':
                        # Reuse the three HUD frames already queued in the main recording. Starting another SCK
                        # client here correlates with -3805 interruptions in s29; never open a second capture stream.
                        log('events', dict(ev='arena_bg', source='main_stream_recording', arena=a.arena,
                                           dir='video', path_base='event_directory',
                                           candidate_files=[f'{i:06d}.jpg' for i in range(max(0, n - 3), n)],
                                           requested_frames=min(3, n), frames=None, width=int(fr.bgr.shape[1]), height=int(fr.bgr.shape[0]),
                                           native_resolution=False, writer_pending=True,
                                           availability='unverified; check recording after writer close',
                                           frame_metadata='frames.jsonl', n=n-1, ts_ms=ts_ms))
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
                    sess = make_session(rt, make_live_player(rt, player_for(cur['k'])), deck)
                    state, streak, miss, first_hud_ms, last_play = 'wait', 0, 0, None, None
                    if a.matches > 1:
                        n, t0_ns = 0, None
                    base_bright = []
                    continue
                if miss >= 3*a.fps:
                    state = 'ended'; log('events', dict(ev='match_end', ts_ms=ts_ms, n=n)); log('frames', row)
                    if cur['k'] >= a.matches:
                        break
                    if RESTART_FILE.exists():
                        try:
                            taken = RESTART_FILE.with_name(f'{RESTART_FILE.name}.taken-{os.getpid()}')
                            RESTART_FILE.rename(taken)
                            log('events', dict(ev='restart_at_boundary', file=str(taken), battle=cur['k']))
                            break
                        except OSError as ex:
                            log('events', dict(ev='restart_file_error', error=repr(ex)[:200]))
                    close_match(state, n, sess, getattr(src, 'restarts', 0))      # next battle: fresh logs + bot
                    open_match(cur['k'] + 1)
                    sess = make_session(rt, make_live_player(rt, player_for(cur['k'])), deck)
                    session_cfg['player'] = player_for(cur['k'])
                    session_cfg['arm'] = 'alt' if session_cfg['player'] != a.player else 'main'
                    if cap['mode'] == 'auto' and a.source == 'live':   # each battle: re-check the window size (fit if changed)
                        try:
                            ws = window_size(a.bsgrab)                   # CoreGraphics; None (read failed) is never a resize
                            if ws is not None and ws != tuple(cap['window']):
                                src.resized = True
                        except Exception:
                            pass
                    log('events', dict(loaded, ev='loaded', load_s=0, session=cur['k'], player=session_cfg['player']))
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
                if a.dump_raw and (not (a.dump_raw_battles or a.dump_raw_every_n_battles) or cur['k'] <= a.dump_raw_battles
                                   or (a.dump_raw_every_n_battles and (cur['k'] - 1) % a.dump_raw_every_n_battles == 0)):
                    # study only: the exact capture (and, first 3, the YOLO input) of this frame n-1; --dump-raw-battles N
                    # limits it to the session's first N battles (a lossless held-out slice per session)
                    if cur.get('dump') is None or cur['dump'].d != cur['dir']:
                        if cur.get('dump') is not None:
                            cur['dump'].close()
                        ev, mx = (int(v) for v in a.dump_raw.split(':'))
                        cur['dump'] = RawDump(cur['dir'], ev, mx)
                    cur['dump'].maybe(n - 1, fr.bgr, f if fut is not None else None)
                yolo_k += 1
                arena_px, hud_px = prepare_pixels(cv)
                if a.perc_threads:
                    import torch
                    nt = torch.get_num_threads(); torch.set_num_threads(a.perc_threads)
                rec = perc.step_prepared(arena_px, hud_px, ts_ms, unit_floor=.05 if ov is not None else None)
                if a.perc_threads:
                    torch.set_num_threads(nt)
                if yolo is not None:
                    tw0 = time.perf_counter()
                    if fut is not None:
                        try:
                            yolo_last = dict(fut.result(), ts_ms=ts_ms)
                        except Exception as ex:          # no units this frame rather than a dead loop
                            yolo_last = dict(units=[], unknown_units=[], units_yolo=[], units_yolo_info=[], unknown_yolo_info=[],
                                             ts_ms=ts_ms, error=repr(ex)[:200])
                            log('events', dict(ev='yolo_error', n=n-1, error=yolo_last['error']))
                    row.update(yolo_ms=yolo.last_ms if fut is not None else None, yolo_wait_ms=1e3*(time.perf_counter() - tw0))
                    rec['units_model'] = rec['units']
                    rec['units'], rec['unknown_units'] = list(yolo_last['units']), list(yolo_last['unknown_units'])
                    rec['units_yolo'], rec['units_age_ms'] = yolo_last['units_yolo'], ts_ms - yolo_last['ts_ms']
                    # logging only (translator's temporal owner model): team probability + class score per unit, parallel
                    rec['units_yolo_info'] = yolo_last.get('units_yolo_info', [])
                    rec['unknown_yolo_info'] = yolo_last.get('unknown_yolo_info', [])
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
                rec['elixir'] = elixir if FLOOR_LATE else max(elixir, reserved)   # FLOOR_LATE: SyncSession._reconcile
                if reserved > elixir:
                    row['elixir_floored'] = reserved
                rec['phase'] = 1 if tick < 2400 else (2 if tick < 4800 else 3)
                rec['clock_s'] = max(0., 180 - tick/20) if tick < 3600 else max(0., 300 - tick/20)
                if 'out' in raw:                                  # own hand = most probable distinct DECK cards (handread.py)
                    ft = raw['out'][4][0].float().cpu().numpy()
                    logits = ft
                    if hand_model is not None:                    # LL_HAND_MODEL: the own-hand classifier's logits
                        if hand_last is None or hand_k % HAND_EVERY == 0:
                            th = time.perf_counter()
                            if a.perc_threads:
                                nt = torch.get_num_threads(); torch.set_num_threads(a.perc_threads)
                            with torch.inference_mode():
                                hand_last = hand_model(torch.from_numpy(f)).float().numpy()
                            if a.perc_threads:
                                torch.set_num_threads(nt)
                            row['hand_ms'] = round(1e3*(time.perf_counter() - th), 2)
                        hand_k += 1
                        logits = hand_last
                    hr = handread.deck_constrained(logits, hand_cards if hand_model is not None else perc.cards, deck)
                    if hr is not None:
                        rec['hand'] = dict(rec.get('hand') or {}, cards=hr['cards'], probs=hr['probs'], next=hr['next'],
                                           next_prob=hr['next_prob'], raw=hr['raw'])
                        if hand_model is not None:                # ft-r6's read beside it (comparison only)
                            h0 = handread.deck_constrained(ft, perc.cards, deck)
                            if h0 is not None:
                                rec['hand']['ft'] = dict(cards=h0['cards'], probs=h0['probs'], next=h0['next'],
                                                         next_prob=h0['next_prob'])
                if HANDSYNC and isinstance(rec.get('hand'), dict):
                    rec['hand']['ui'] = slot_ui(f)
                if taps is not None and sess.exec_pending:      # acked taps -> sess.executed (before the bot steps)
                    for tid in sorted(t for t in sess.exec_pending if t in taps.acked):
                        e = sess.exec_pending.pop(tid)
                        ack_ns = taps.acked.pop(tid)
                        w_ns, f2t = e.pop('_w')
                        try:   # live: frame display times and the ack are both unix ns -> the session clock at the ack
                            e['exec_tick'] = round((ack_ns - t0_ns)/1e6/50 + sess.tr.clock.offset(), 2) \
                                if a.source == 'live' else round(e['submit_tick'] + (f2t + (ack_ns - w_ns)/1e6)/50, 2)
                        except Exception:
                            e['exec_tick'] = None
                        sess.executed.append(e)
                        log('events', dict(ev='executed', **e))
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
                if UNITS_BOT:
                    bl = getattr(sess.tr, 'board_last', None)
                    if bl is not None and bl[0] == rec.get('timestamp_ms'):     # translated this frame (a poll)
                        row['units_bot'] = rec['units_bot'] = bl[1]
                    elif getattr(sess.tr, 'true_ids', None) is not None and rec.get('units'):
                        # between polls (overlay only, not logged): the same true-id mapping, detector owners
                        try:
                            tu = sess.tr.true_units(dict(rec, _synthetic=True))
                            yn = rec.get('units_yolo') or [None]*len(tu)
                            rec['units_bot'] = [dict(card=u.get('card') or u.get('cls'), owner=int(u['owner']), raw=r)
                                                for u, r in zip(tu, yn)]
                        except Exception:
                            pass
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
                        eflash.own_play(n - 1, sess.ch.pending[-1].cost)
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
                            row_, col_ = divmod(int(d.action) % 576, 18)
                            sess.exec_pending[drow['tap_id']] = dict(card=card, slot=slot, action=int(d.action),
                                                                     tile=(col_, row_), submit_tick=tick,
                                                                     exec_tick=None, tap_id=drow['tap_id'], n=n-1,
                                                                     _w=(drow['tap_write_ns'], drow['frame_to_tap_ms']))
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
