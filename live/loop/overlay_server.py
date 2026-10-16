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
import http.client
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from contextlib import contextmanager

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

LOOP = Path(os.path.expanduser(os.environ.get('LL_LOOP_DIR', '~/clasher-live/loop')))
PAUSE = Path(os.path.expanduser(os.environ.get('LL_PAUSE_FILE', str(LOOP/'PAUSE'))))
DECK = Path(os.path.expanduser(os.environ.get('LL_DECK_FILE', str(LOOP/'deck.json'))))
STATUS = LOOP/'status.txt'
DEFAULT_DECK = ['Knight', 'Archers', 'Minions', 'Arrows', 'Fireball', 'Giant', 'MiniPekka', 'Musketeer']


def page():
    # Keep the driver's controls and polling verbatim; adapt only the viewer.
    from overlay import PAGE
    html = PAGE.decode()
    html = html.replace('<head>', '<head><meta name="viewport" content="width=device-width, initial-scale=1">', 1)
    html = html.replace('</style>', """
#viewer{min-width:0;position:relative;flex-shrink:1}
#video{display:block;height:100vh;max-width:100%;object-fit:contain}
#quality{position:absolute;top:8px;left:8px;z-index:1;background:#111e;padding:8px;border-radius:6px}
#quality input,#low{min-width:20px;min-height:20px;vertical-align:middle}
#side{flex-shrink:0;overflow-wrap:anywhere}
#deck{box-sizing:border-box}
@media (max-width:800px),(pointer:coarse){
 body{display:block}
 #viewer{width:100%}
 #video{width:100%;height:auto;min-height:100px}
 #side{width:100%;max-width:640px;margin:auto}
 #quality{position:static;display:block;border-radius:0}
}
</style>""", 1)
    html = html.replace('<img id="video" src="/stream" style="height:100vh">',
        '<div id="viewer"><label id="quality"><input id="full" type="checkbox"> Full quality '
        '<span id="quality-status"></span></label><img id="video" alt="Live game overlay"></div>', 1)
    html = html.replace("""<input type="checkbox" onchange="document.getElementById('video').src=this.checked?'/stream?low=1':'/stream'">""",
                        '<input id="low" type="checkbox">', 1)
    return html.replace('<script>', r"""<script>
const full = document.getElementById('full'), low = document.getElementById('low');
let phoneQuality = matchMedia('(max-width:800px), (pointer:coarse)').matches;
let visibleFrameURL = null, frameNumber = 0;
function setQuality(phone) {
  phoneQuality = phone;
  full.checked = !phone;
  low.checked = phone;
  document.getElementById('quality-status').textContent = phone ? '(phone, up to 3 FPS)' : '(up to 10 FPS)';
}
full.onchange = () => setQuality(!full.checked);
low.onchange = () => setQuality(low.checked);
setQuality(phoneQuality);
async function nextFrame() {
  if (document.hidden) { setTimeout(nextFrame, 1000); return; }
  const started = performance.now(), phone = phoneQuality;
  let nextURL = null, delay = 0;
  try {
    const response = await fetch('/frame.jpg?low=' + (phone ? '1' : '0') +
      '&_=' + Date.now() + '-' + (++frameNumber), {cache:'no-store'});
    if (!response.ok) throw new Error('Frame HTTP ' + response.status);
    // Read the entire response first; never expose a network JPEG to the visible image.
    nextURL = URL.createObjectURL(await response.blob());
    const next = new Image();
    next.id = 'video';
    next.alt = 'Live game overlay';
    await new Promise((resolve, reject) => {
      next.onload = resolve;
      next.onerror = () => reject(new Error('Frame decode failed'));
      next.src = nextURL;
    });
    // A quality change in flight takes effect with the next request.
    document.getElementById('video').replaceWith(next);
    if (visibleFrameURL) URL.revokeObjectURL(visibleFrameURL);
    visibleFrameURL = nextURL;
    nextURL = null;
    delay = Math.max(0, (phone ? 1000/3 : 100) - (performance.now() - started));
  } catch (e) {
    // Retain the last complete frame across network/decode failures.
    delay = 1000;
  } finally {
    if (nextURL) URL.revokeObjectURL(nextURL);
    // Exactly one request/decode at a time, including on slow phone connections.
    setTimeout(nextFrame, delay);
  }
}
nextFrame();
""", 1).encode()


def phone_jpeg(jpg):
    """Fixed phone snapshots: full aspect ratio, at most 540 px wide, JPEG quality 50."""
    import cv2
    import numpy as np
    img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError('invalid viewer JPEG')
    h, w = img.shape[:2]
    if w > 540:
        img = cv2.resize(img, (540, max(1, round(h*540/w))), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 50,
                                       cv2.IMWRITE_JPEG_OPTIMIZE, 1])
    if not ok:
        raise ValueError('phone JPEG encode failed')
    return buf.tobytes()


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
        self.cv = threading.Condition()
        self.jpg = None
        self.serial = 0
        self.clients = 0
        self.last_client = 0.
        self.reader = None
        self.closed = False
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


    @contextmanager
    def frames(self):
        # One upstream reader and one complete frame, independent of downstream speed.
        with self.cv:
            self.clients += 1
            self.last_client = time.monotonic()
            if self.reader is None:
                self.reader = threading.Thread(target=self._read, name='viewer-upstream', daemon=True)
                self.reader.start()
        try:
            yield self
        finally:
            with self.cv:
                self.clients -= 1
                self.last_client = time.monotonic()
                self.cv.notify_all()

    def _read(self):
        from overlay import complete_jpeg
        try:
            while True:
                with self.cv:
                    # Keep reading through brief gaps between snapshot requests.
                    if self.closed or (not self.clients and time.monotonic() - self.last_client > 2):
                        return
                try:
                    with urllib.request.urlopen(self.base + '/stream', timeout=3) as up:
                        if up.headers.get_content_type() != 'multipart/x-mixed-replace' or up.headers.get_param('boundary') != 'f':
                            raise ValueError('unexpected upstream stream')
                        while True:
                            with self.cv:
                                if self.closed or (not self.clients and time.monotonic() - self.last_client > 2):
                                    return
                            jpg = read_part(up)
                            if not complete_jpeg(jpg):
                                raise ValueError('incomplete upstream JPEG')
                            with self.cv:
                                self.jpg = jpg
                                self.serial += 1
                                self.cv.notify_all()
                except (OSError, ValueError, EOFError, http.client.HTTPException):
                    # Keep the last complete frame when a driver/connection fails.
                    with self.cv:
                        if self.jpg is None:
                            st = idle_state()
                            self.jpg = idle_jpeg(['BETWEEN SESSIONS', st['reason'][:40],
                                                 'last: ' + (st['last_session'] or '-')[:40],
                                                 'ended: ' + (st['last_end'] or '-'),
                                                 'PAUSED (file)' if st['paused'] else ''])
                            self.serial += 1
                            self.cv.notify_all()
                        self.cv.wait(timeout=.5)
        finally:
            with self.cv:
                self.reader = None
                # A reconnect may arrive after the old reader decided to exit.
                if self.clients and not self.closed:
                    self.reader = threading.Thread(target=self._read, name='viewer-upstream', daemon=True)
                    self.reader.start()
                self.cv.notify_all()

    def close(self):
        with self.cv:
            self.closed = True
            reader = self.reader
            self.cv.notify_all()
        if reader:
            reader.join(timeout=4)


def read_part(up):
    """Read a bounded complete multipart part; never relay transport fragments."""
    if up.readline(128).strip() != b'--f':
        raise EOFError('missing upstream boundary')
    headers = {}
    for _ in range(16):
        line = up.readline(1024)
        if line == b'\r\n':
            break
        key, sep, value = line.partition(b':')
        if not sep:
            raise ValueError('invalid multipart header')
        headers[key.strip().lower()] = value.strip()
    else:
        raise ValueError('too many multipart headers')
    n = int(headers.get(b'content-length', b'0'))
    if headers.get(b'content-type') != b'image/jpeg' or not 0 < n <= 8*1024*1024:
        raise ValueError('invalid JPEG part length/type')
    jpg = up.read(n)
    if len(jpg) != n or up.read(2) != b'\r\n':
        raise EOFError('truncated upstream JPEG part')
    return jpg


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
            url = urlsplit(self.path)
            if url.path == '/frame.jpg':
                return self.frame(parse_qs(url.query).get('low') == ['1'])
            if self.path == '/state':
                st = proxy.alive()
                return self.reply(200, json.dumps(dict(st, driver=True) if st is not None else idle_state()),
                                  'application/json')
            if self.path in ('/stream', '/stream?low=1'):
                return self.stream()
            return self.reply(200, page(), 'text/html')

        def frame(self, low):
            """Serve one complete latest frame; preserve the MJPEG endpoints for older viewers."""
            try:
                with proxy.frames():
                    with proxy.cv:
                        proxy.cv.wait_for(lambda: proxy.closed or proxy.jpg is not None, timeout=5)
                        jpg = proxy.jpg
                    if jpg is None:
                        return self.reply(503, 'frame not ready; retry shortly')
                    self.connection.settimeout(30)
                    return self.reply(200, phone_jpeg(jpg) if low else jpg, 'image/jpeg')
            except (OSError, ValueError):
                # The client may leave while its complete snapshot is being transferred.
                return

        def stream(self):
            """Publish only complete latest frames; slow clients cannot stall the upstream reader."""
            from overlay import STREAM_TIMEOUT, LOW_FPS, viewer_jpeg, write_part
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=f')
            self.send_header('Cache-Control', 'no-store'); self.end_headers()
            self.connection.settimeout(STREAM_TIMEOUT)
            low = self.path.endswith('?low=1')
            serial, sent = -1, 0.
            try:
                with proxy.frames():
                    while not proxy.closed:
                        if low:
                            time.sleep(max(0, 1/LOW_FPS - (time.monotonic() - sent)))
                        with proxy.cv:
                            proxy.cv.wait_for(lambda: proxy.closed or proxy.serial != serial, timeout=1)
                            if proxy.closed:
                                return
                            jpg, current = proxy.jpg, proxy.serial
                        if jpg is None:
                            continue
                        # Repeat a last-good frame at most once a second to detect disconnected clients.
                        if current == serial and time.monotonic() - sent < 1:
                            continue
                        write_part(self, viewer_jpeg(jpg, low))
                        serial, sent = current, time.monotonic()
            except (OSError, ValueError):
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
    proxy = Proxy(a.driver_port)
    srv = None
    while srv is None:                          # an older driver may still hold the port: wait for it
        try:
            srv = ThreadingHTTPServer((a.host, a.port), make_handler(proxy))
        except OSError as e:
            print(f'port {a.port} busy ({e}); retrying in 5 s', flush=True); time.sleep(5)
    srv.daemon_threads = True
    print(f'overlay server on :{a.port} (driver page :{a.driver_port}), pid {os.getpid()}', flush=True)
    try:
        srv.serve_forever()
    finally:
        proxy.close()
        srv.server_close()


if __name__ == '__main__':
    sys.exit(main())
