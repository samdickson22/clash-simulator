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
from frames import Grabber  # noqa: E402

MIN_FREE = 6 << 30
DECK = ['Knight', 'Archers', 'Minions', 'Arrows', 'Fireball', 'Giant', 'MiniPekka', 'Musketeer']
ADB = os.path.expanduser('~/clasher-live/tools/platform-tools/adb')


def hud_read(f):
    """Android-size frame -> (battle HUD present, elixir 0..10 or None). Pink = elixir drop / bar fill."""
    o = f[1868:1888, 250:1040].astype(np.int16)
    col = ((o[..., 2] > 170) & (o[..., 0] > 150) & (o[..., 1] < 130)).mean(0) > .5
    present = col[:35].mean() > .6                       # the drop at x 250..285
    xs = np.nonzero(col[40:])[0]                          # the bar from x 290
    elixir = float(np.clip((xs.max() + 40 + 250 - 290)/74.8, 0, 10)) if len(xs) else 0.
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
        while not self.stop and time.monotonic() < t_end and self.restarts <= 5:
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


def build_bot(player_name):
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
    return rt, LiveSession(rt, player, DECK)


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
    ap.add_argument('--overlay-port', type=int, default=8765, help='MJPEG view of what the bot sees (0 = off)')
    ap.add_argument('--arena', default='goblin-stadium', help='arena-bgs/<arena>/ name for the battle-start frames')
    ap.add_argument('--no-realtime', action='store_true', help='replay: every frame, as fast as possible')
    a = ap.parse_args(argv)
    seconds = min(a.seconds, 900)
    out = Path(a.out); out.mkdir(parents=True); (out/'video').mkdir()
    if shutil.disk_usage(out).free < MIN_FREE:
        sys.exit('free space below 6 GiB')
    logs = {k: open(out/f'{k}.jsonl', 'a', buffering=1) for k in ('frames', 'decisions', 'taps', 'events')}
    lock = threading.Lock()

    def log(kind, row):
        with lock:
            logs[kind].write(json.dumps(row, default=float) + '\n')

    from infer import LivePerception
    from bot.players.base import WAIT
    t = time.monotonic()
    perc = LivePerception(a.export)
    rt, sess = build_bot(a.player)
    raw = {}                                   # the frame model's last outputs (overlay: what the model sees)
    _frame = perc.frame
    def _tap_frame(*args):
        o = _frame(*args); raw['out'] = o; return o
    perc.frame = _tap_frame
    from clasher.vision.l1_v4 import prepare_pixels
    log('events', dict(ev='loaded', perception_s=None, load_s=time.monotonic() - t, player=a.player,
                       fast=os.environ.get('CLASHER_LIVE_FAST')))
    crop = [float(v) for v in a.crop.split(',')]; size = [int(v) for v in a.size.split(',')]
    if a.source == 'live':
        src = LiveFrames(a.bsgrab, crop, size, a.fps, seconds, open(out/'bsgrab.stderr', 'ab'))
    else:
        src = ReplayFrames(a.source.split(':', 1)[1], realtime=not a.no_realtime)
    taps = AdbTaps(a.serial, a.adb_port, lambda r: log('taps', r)) if a.tap == 'adb' else None
    wr = Writer(out/'video')
    ov, last_play = None, None
    if a.overlay_port:
        from overlay import Overlay
        ov = Overlay(a.overlay_port)
    state, streak, miss, start_ms, n, t_end = 'wait', 0, 0, None, 0, time.monotonic() + seconds
    t0_ns, first_hud_ms = None, None
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
            f = C.to_android(fr.bgr)
            present, elixir = hud_read(f)
            row = dict(n=n, seq=fr.seq, ts_ms=ts_ms, cap_ms=(fr.recv_ns - fr.display_ns)/1e6, hud=present,
                       elixir=elixir, state=state)
            wr.put(n, fr.bgr); n += 1
            if n % 100 == 0 and shutil.disk_usage(out).free < MIN_FREE:
                log('events', dict(ev='stop', why='free space below 6 GiB')); break
            if state == 'wait':
                streak = streak + 1 if present else 0
                first_hud_ms = (first_hud_ms if streak > 1 else ts_ms) if present else None
                if streak >= 3:
                    state, start_ms = 'battle', first_hud_ms
                    perc.reset(); sess.tr.clock.anchor(0, start_ms); towers = TW.TowerReader()
                    log('events', dict(ev='match_start', ts_ms=start_ms, n=n))
                    if a.source == 'live':
                        threading.Thread(target=grab_arena_bg, daemon=True, args=(
                            a.bsgrab, crop, Path(os.path.expanduser('~/clasher-live/loop/arena-bgs'))/a.arena, out.name,
                            log)).start()
                if ov is not None:
                    ov.update(fr.bgr, state='waiting for battle', elixir=elixir)
                log('frames', row); continue
            if state == 'battle':
                miss = 0 if present else miss + 1
                if miss >= 3*a.fps:
                    state = 'ended'; log('events', dict(ev='match_end', ts_ms=ts_ms, n=n)); log('frames', row); break
                if not present:
                    log('frames', row); continue
                t1 = time.perf_counter(); cv = C.canvas(f); t2 = time.perf_counter()
                arena_px, hud_px = prepare_pixels(cv)
                rec = perc.step_prepared(arena_px, hud_px, ts_ms, unit_floor=.05 if ov is not None else None)
                towers.apply(rec, f)       # tower alive/HP from the drawn numbers (perception's HP head misreads)
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
                pend0 = len(sess.ch.pending)
                d, err = None, None
                try:
                    d = sess.step(rec)
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
                if d is not None:
                    submitted = len(sess.ch.pending) > pend0 and d.action < WAIT
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
                    ov.update(fr.bgr, rec, 'battle', tick, elixir, last_play, heat=heat,
                              units_lo=perc.last.get('units_lo', ()))
                log('frames', row)
    finally:
        src.close(); wr.close()
        if ov is not None:
            ov.close()
        if taps is not None:
            time.sleep(1); taps.close()
        st = dict(state=state, frames=n, writer_dropped=wr.dropped, tr_stats=dict(sess.tr.stats),
                  restarts=getattr(src, 'restarts', 0))
        try:
            sess.close()
        except Exception as ex:
            st['close_error'] = repr(ex)
        (out/'session.json').write_text(json.dumps(st, indent=1, default=str) + '\n')
        for f in logs.values():
            f.close()
    print(json.dumps(dict(state=state, frames=n)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
