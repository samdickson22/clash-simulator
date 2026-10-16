"""Always-on clasher live page on :8765 (Sam's http://mac-mini:8765), independent of driver sessions.

  ~/clasher-live/venv/bin/python -B overlay_server.py [--port 8765] [--driver-port 8766]

- A driver alive (its own page on --driver-port, drive.py's default): /, /stream, /state and the POST controls are
  proxied to it, so the page is the live view with working Pause/Resume/deck controls.
- No driver: the same page with "BETWEEN SESSIONS: <reason>" (reason = ~/clasher-live/loop/status.txt, written by the
  operator, e.g. "starting next session", "held by LIVE LEAD"; default "no driver running"), the last session and its
  end time, the deck (deck.json) and a placeholder stream image. Pause/Resume then write/remove the PAUSE file (the next
  session starts paused), Apply deck writes deck.json (8 distinct names); Read deck needs a running driver.
- Survives drivers: it never exits on driver errors. One instance: an flock on overlay-server.lock (a second start
  exits 0 with "already running", so starting it is idempotent). If the port is busy (an older driver still serving
  :8765), it retries the bind every 5 s until it is free.
Env (tests): LL_LOOP_DIR (default ~/clasher-live/loop), LL_PAUSE_FILE, LL_DECK_FILE.
"""
import argparse
import fcntl
import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

LOOP = Path(os.path.expanduser(os.environ.get('LL_LOOP_DIR', '~/clasher-live/loop')))
PAUSE = Path(os.path.expanduser(os.environ.get('LL_PAUSE_FILE', str(LOOP/'PAUSE'))))
DECK = Path(os.path.expanduser(os.environ.get('LL_DECK_FILE', str(LOOP/'deck.json'))))
STATUS = LOOP/'status.txt'
DEFAULT_DECK = ['Knight', 'Archers', 'Minions', 'Arrows', 'Fireball', 'Giant', 'MiniPekka', 'Musketeer']


def page():
    from overlay import PAGE              # the driver page (same controls); it shows the between-sessions banner
    return PAGE


def c56():
    try:
        from battlelog import C56
        return C56
    except Exception:
        return None


def idle_jpeg(lines):
    import cv2
    import numpy as np
    img = np.full((1280, 720, 3), 24, np.uint8)
    y = 520
    for i, t in enumerate(lines):
        cv2.putText(img, t, (30, y), 0, 1.1 if i == 0 else .75, (0, 165, 255) if i == 0 else (220, 220, 220), 2)
        y += 60 if i == 0 else 42
    return cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()


def deck():
    try:
        d = json.loads(DECK.read_text())
        if isinstance(d, list) and len(d) == 8:
            return d
    except Exception:
        pass
    return list(DEFAULT_DECK)


def last_session():
    """Newest run dir under runs/ with its newest battle's end (match_end) time; '' if none."""
    runs = LOOP/'runs'
    try:
        dirs = sorted((d for d in runs.iterdir() if d.is_dir()), key=lambda d: d.stat().st_mtime)
    except Exception:
        return '', ''
    if not dirs:
        return '', ''
    d = dirs[-1]
    end = ''
    evs = sorted(d.glob('m*/events.jsonl'), key=lambda p: p.stat().st_mtime) or ([d/'events.jsonl'] if (d/'events.jsonl').exists() else [])
    if evs:
        end = time.strftime('%H:%M:%S %Z', time.localtime(evs[-1].stat().st_mtime))
        n = sum(1 for p in d.glob('m*/events.jsonl') if '"match_end"' in p.read_text())
        return f'{d.name} ({n} battle(s) played)', end
    return d.name, end


def idle_state():
    reason = STATUS.read_text().strip() if STATUS.exists() else ''
    ls, end = last_session()
    dk = deck(); C = c56()
    return dict(driver=False, reason=reason or 'no driver running', last_session=ls, last_end=end, deck=dk,
                deck_out_of_scope=[c for c in dk if C is not None and c not in C], paused=PAUSE.exists(),
                paused_reason='file' if PAUSE.exists() else None, state='between sessions', match=None,
                deck_pending=None, read=None)


class Proxy:
    def __init__(self, port):
        self.base = f'http://127.0.0.1:{port}'

    def alive(self):
        try:
            with urllib.request.urlopen(self.base + '/state', timeout=1.5) as r:
                return json.loads(r.read())
        except Exception:
            return None

    def post(self, path, body):
        req = urllib.request.Request(self.base + path, data=body, method='POST')
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read()


def make_handler(proxy):
    class H(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.0'

        def log_message(self, *a):
            pass

        def reply(self, code, body, ctype='text/plain'):
            b = body.encode() if isinstance(body, str) else body
            self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)

        def do_GET(self):
            if self.path == '/state':
                st = proxy.alive()
                return self.reply(200, json.dumps(dict(st, driver=True) if st is not None else idle_state()),
                                  'application/json')
            if self.path == '/stream':
                return self.stream()
            return self.reply(200, page(), 'text/html')

        def stream(self):
            """Relay the driver's MJPEG while it is up; otherwise a placeholder frame every second, retrying."""
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=f'); self.end_headers()
            try:
                while True:
                    try:
                        with urllib.request.urlopen(proxy.base + '/stream', timeout=3) as up:
                            ctype = up.headers.get('Content-Type', '')
                            if 'boundary=f' not in ctype:
                                raise OSError('unexpected upstream stream')
                            while True:
                                chunk = up.read(65536)
                                if not chunk:
                                    break
                                self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        return
                    except Exception:
                        pass
                    st = idle_state()
                    jpg = idle_jpeg(['BETWEEN SESSIONS', st['reason'][:40], 'last: ' + (st['last_session'] or '-')[:40],
                                     'ended: ' + (st['last_end'] or '-'), 'PAUSED (file)' if st['paused'] else ''])
                    for _ in range(2):
                        self.wfile.write(b'--f\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n' % len(jpg))
                        self.wfile.write(jpg + b'\r\n'); self.wfile.flush()
                        time.sleep(1)
            except (BrokenPipeError, ConnectionResetError):
                return

        def do_POST(self):
            n = int(self.headers.get('Content-Length') or 0)
            body = self.rfile.read(n) if n else b''
            if proxy.alive() is not None:
                try:
                    code, out = proxy.post(self.path, body)
                    return self.reply(code, out)
                except urllib.error.HTTPError as e:
                    return self.reply(e.code, e.read())
                except Exception as e:
                    return self.reply(502, f'driver did not answer: {e!r}'[:200])
            # no driver: act on the files the next session reads
            if self.path == '/pause':
                PAUSE.parent.mkdir(parents=True, exist_ok=True); PAUSE.write_text('paused from the page (no driver)\n')
                return self.reply(200, 'paused: the next session starts paused (PAUSE file written)')
            if self.path == '/resume':
                if PAUSE.exists():
                    PAUSE.unlink()
                return self.reply(200, 'resumed: PAUSE file removed')
            if self.path == '/deck':
                names = [w.strip() for w in body.decode(errors='replace').replace(',', '\n').split('\n') if w.strip()]
                if len(names) != 8 or len(set(names)) != 8:
                    return self.reply(400, 'deck NOT applied: need exactly 8 distinct cards')
                DECK.parent.mkdir(parents=True, exist_ok=True); DECK.write_text(json.dumps(names))
                C = c56(); oos = [c for c in names if C is not None and c not in C]
                return self.reply(200, 'deck saved; the next session uses it' +
                                  (f' (OUT OF SCOPE, battles will be blocked: {", ".join(oos)})' if oos else ''))
            if self.path == '/readdeck':
                return self.reply(409, 'no driver running: "Read deck from screen" needs a live session')
            return self.reply(404, 'unknown')
    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--driver-port', type=int, default=8766)
    ap.add_argument('--host', default='0.0.0.0')
    a = ap.parse_args()
    LOOP.mkdir(parents=True, exist_ok=True)
    lock = open(LOOP/'overlay-server.lock', 'a+')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock.seek(0)
        print(f'overlay server already running ({lock.read().strip()})'); return 0
    lock.seek(0); lock.truncate(); lock.write(f'pid {os.getpid()} port {a.port} started {time.strftime("%FT%T%z")}\n'); lock.flush()
    (LOOP/'overlay-server.pid').write_text(f'{os.getpid()}\n')
    srv = None
    while srv is None:                          # an older driver may still hold the port: wait for it
        try:
            srv = ThreadingHTTPServer((a.host, a.port), make_handler(Proxy(a.driver_port)))
        except OSError as e:
            print(f'port {a.port} busy ({e}); retrying in 5 s', flush=True); time.sleep(5)
    srv.daemon_threads = True
    print(f'overlay server on :{a.port} (driver page :{a.driver_port}), pid {os.getpid()}', flush=True)
    srv.serve_forever()


if __name__ == '__main__':
    sys.exit(main())
