"""What the bot sees, drawn over the captured frame and served as an MJPEG page (open http://<mac>:PORT/ in a browser).

Draws: perceived units (box + identity; blue = ours, red = opponent), tower HP as read, hand/next/elixir, tick, and the
bot's latest play (card + target tile). Serving is a daemon thread; update() only swaps the latest JPEG.
"""
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2

import canvas as C

PAGE = (b'<html><head><title>clasher live</title></head><body style="margin:0;background:#111">'
        b'<img src="/stream" style="height:100vh"></body></html>')


def _box_shape(card):
    if card in ('Giant', 'HogRider', 'Prince', 'DarkPrince', 'Golem', 'PEKKA', 'MiniPekka', 'Balloon'):
        return 48, 64, 18
    if card in ('Skeletons', 'Goblins', 'IceSpirit', 'Minions', 'Bats'):
        return 23, 35, 10
    return 34, 49, 14


def heat_maps(w, h):
    """Frame px (w x h, a scaled 1080x1920 viewport) -> body-heatmap cell coords (gx, gy) through the tile calibration
    (cell g covers native tile g/2..(g+1)/2; native y grows down the screen)."""
    import numpy as np
    u, v = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    s = C.W/w
    cx, cy = (u*s - C.ARENA_T[0])/C.ARENA_S, (v*s - C.ARENA_T[1])/C.ARENA_S
    tx, ty = (cx - C.TILE_B)/C.TILE_A, (cy - C.TILE_D)/C.TILE_C
    return (2*tx - .5).astype(np.float32), (2*ty - .5).astype(np.float32)


class Overlay:
    def __init__(self, port=8765, host='0.0.0.0', every=2):
        self.jpg, self.cv, self.n, self.every, self.maps = None, threading.Condition(), 0, every, None
        ov = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path != '/stream':
                    self.send_response(200); self.send_header('Content-Type', 'text/html'); self.end_headers()
                    self.wfile.write(PAGE); return
                self.send_response(200)
                self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=f'); self.end_headers()
                last = None
                try:
                    while True:
                        with ov.cv:
                            ov.cv.wait_for(lambda: ov.jpg is not last, timeout=5)
                            last = ov.jpg
                        if last is None:
                            continue
                        self.wfile.write(b'--f\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n' % len(last))
                        self.wfile.write(last + b'\r\n')
                except (BrokenPipeError, ConnectionResetError):
                    return

        self.srv = ThreadingHTTPServer((host, port), H)
        self.srv.daemon_threads = True
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def update(self, bgr, rec=None, state='', tick=None, elixir=None, last_play=None, heat=None, units_lo=()):
        """heat: (per-owner max unit heatmap [2, 64, 36], native owner 1 = us) after sigmoid; units_lo: every decoded
        candidate down to the low floor (record coords, with score)."""
        import numpy as np
        self.n += 1
        if self.n % self.every:
            return
        img = bgr.copy()
        s = img.shape[1]/C.W                     # android px -> this frame
        P = lambda x, y: (int(x*s), int(y*s))
        if heat is not None:
            if self.maps is None or self.maps[0].shape != img.shape[:2]:
                self.maps = heat_maps(img.shape[1], img.shape[0])
            mx, my = self.maps
            layer = np.zeros(img.shape, np.float32); alpha = np.zeros(img.shape[:2], np.float32)
            for native_owner, col in ((0, (0, 0, 255)), (1, (255, 120, 0))):       # opponent red, ours blue
                hm = cv2.remap(heat[native_owner].astype(np.float32), mx, my, cv2.INTER_LINEAR, borderValue=0)
                a = np.clip((hm - .03)/.27, 0, 1)*.7            # weak responses (0.03..0.3) made visible
                layer += a[..., None]*np.array(col, np.float32); alpha = np.maximum(alpha, a)
            img = (img*(1 - alpha[..., None]) + layer).clip(0, 255).astype(np.uint8)
        best = []                                # the model's best guess per spot (candidates within 1 tile merged)
        for u in sorted(units_lo, key=lambda u: -u.get('score', 0)):
            if u.get('score', 0) >= .08 and all((u['x']-b['x'])**2 + (u['y']-b['y'])**2 > 1 for b in best):
                best.append(u)
        for u in best:
            if u['score'] >= .5:
                continue                         # drawn bold below from the record
            ax, ay = C.tile_to_android(u['x'], u['y'])
            col = (180, 180, 255) if u['owner'] else (255, 210, 150)
            cv2.circle(img, P(ax, ay), 9, col, 1)
            cv2.putText(img, f"{u.get('cls')} {u['score']:.2f}", P(ax+13, ay+5), 0, .38, col, 1)
        if rec is not None:
            for u in rec.get('units', ()):
                ax, ay = C.tile_to_android(u['x'], u['y'])
                w, h, lift = (v*C.ARENA_S for v in _box_shape(u.get('cls')))
                col = (255, 140, 0) if u['owner'] == 0 else (0, 0, 255)
                cv2.rectangle(img, P(ax-w/2, ay-lift-h/2), P(ax+w/2, ay-lift+h/2), col, 2)
                cv2.putText(img, f"{u.get('cls')} {u.get('score', 0):.2f}", P(ax-w/2, ay-lift-h/2-6), 0, .45, col, 1)
            for t in rec.get('towers', ()):
                x = {'left': 3.5, 'right': 14.5, 'center': 9}[t['side']]
                y = (6.5 if t['kind'] != 'king' else 3) if t['owner'] == 0 else (25.5 if t['kind'] != 'king' else 29)
                ax, ay = C.tile_to_android(x, y)
                txt = f"{t.get('hp_read', '?')}" if t['alive'] else 'DEAD'
                cv2.putText(img, txt, P(ax-40, ay+50), 0, .6, (0, 255, 255), 2)
            h = rec.get('hand') or {}
            for i, c in enumerate(h.get('cards', ())):
                cx, cy = C.CARD_SLOTS[i]
                cv2.putText(img, str(c), P(cx-90, 1590), 0, .45, (0, 255, 0), 1)
            cv2.putText(img, f"next {h.get('next')}", P(20, 1585), 0, .45, (0, 255, 0), 1)
        if last_play is not None and time.time() - last_play['t'] < 3:
            ax, ay = last_play['target_xy']
            cv2.drawMarker(img, P(ax, ay), (255, 0, 255), cv2.MARKER_CROSS, 40, 3)
            cv2.putText(img, f"PLAY {last_play['card']}", P(ax+25, ay), 0, .7, (255, 0, 255), 2)
        el = '-' if elixir is None else f'{elixir:.1f}'
        cv2.rectangle(img, (0, 0), (img.shape[1], 26), (0, 0, 0), -1)
        cv2.putText(img, f"{state} tick {tick if tick is None else int(tick)}  elixir {el}", (6, 19), 0, .55,
                    (255, 255, 255), 1)
        ok, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if ok:
            with self.cv:
                self.jpg = buf.tobytes(); self.cv.notify_all()

    def close(self):
        self.srv.shutdown()
