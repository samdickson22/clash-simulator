"""Viewer-only local HTTP probes; no capture, models, bot, browser or Mac.
Run nice -n 19 with OMP/OPENBLAS/MKL_NUM_THREADS=1; optional VIEWER_REPORT writes measurements.
Reconnect probes imitate HTTP image reconnects, not a real Safari decoder test.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np
cv2.setNumThreads(1)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import overlay as O
import overlay_server as S

SOURCE = Path('/mpac/sdicks02/scratch/live-loop/runs/s32/m01/video/001219.jpg')
METRICS = {}


def part(jpg):
    return b'--f\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n' % len(jpg) + jpg + b'\r\n'


def wait(cond, seconds=5):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(.02)
    return bool(cond())


class Server(ThreadingHTTPServer):
    daemon_threads = True
    def handle_error(self, *a):
        pass  # deliberate client resets / truncated fake upstreams


def start(handler):
    srv = Server(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    return srv, thread


class ViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = cv2.imread(str(SOURCE)) if SOURCE.exists() else np.random.default_rng(17).integers(0, 256, (1280, 720, 3), np.uint8)
        cls.jpg = cv2.imencode('.jpg', cls.frame, [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()

    def setUp(self):
        self.mode = 'normal'
        self.active = 0
        self.posts = []
        owner = self
        class Backend(BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_POST(self):
                owner.posts.append((self.path, self.rfile.read(int(self.headers.get('Content-Length', 0)))))
                self.send_response(200); self.end_headers(); self.wfile.write(b'ok')
            def do_GET(self):
                if self.path == '/state':
                    self.send_response(200); self.end_headers(); self.wfile.write(b'{"deck": [], "state": "battle"}'); return
                self.send_response(200)
                self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=f'); self.end_headers()
                owner.active += 1
                try:
                    while True:
                        mode = owner.mode
                        body = part(owner.jpg)
                        if mode == 'truncated':
                            self.wfile.write(body[:len(body)//2]); self.wfile.flush(); return
                        if mode == 'stall':
                            time.sleep(3.3); return
                        if mode == 'slow':
                            for n in range(0, len(body), 4096):
                                self.wfile.write(body[n:n+4096]); self.wfile.flush(); time.sleep(.003)
                        else:
                            self.wfile.write(body); self.wfile.flush()
                        time.sleep(.1)
                except OSError:
                    pass
                finally:
                    owner.active -= 1
        self.up, self.ut = start(Backend)
        self.proxy = S.Proxy(self.up.server_port)
        self.srv, self.st = start(S.make_handler(self.proxy))
        self.base = f'http://127.0.0.1:{self.srv.server_port}'
        self.responses = []

    def tearDown(self):
        for r in self.responses:
            r.close()
        self.proxy.close()
        self.srv.shutdown(); self.srv.server_close(); self.st.join(2)
        self.up.shutdown(); self.up.server_close(); self.ut.join(2)
        self.assertTrue(wait(lambda: self.proxy.clients == 0 and self.proxy.reader is None and self.active == 0, 5))

    def stream(self, low=False):
        r = urllib.request.urlopen(self.base + ('/stream?low=1' if low else '/stream'), timeout=5)
        self.responses.append(r)
        self.assertEqual(r.headers.get_param('boundary'), 'f')
        return r

    def test_complete_validation_and_multipart(self):
        self.assertTrue(O.complete_jpeg(self.jpg))
        self.assertFalse(O.complete_jpeg(self.jpg[:-20]))
        self.assertFalse(O.complete_jpeg(b'\xff\xd8not JPEG\xff\xd9'))
        self.assertEqual(S.read_part(io.BytesIO(part(self.jpg))), self.jpg)
        for body in (part(self.jpg)[:-20], part(self.jpg)[:-2], b'--wrong\r\n', b'--f\r\nContent-Length: 99999999\r\n\r\n'):
            with self.assertRaises((ValueError, EOFError)):
                S.read_part(io.BytesIO(body))

    def test_served_bytes_and_bandwidth(self):
        r = self.stream()
        ts = []; sizes = []
        for _ in range(12):
            b = S.read_part(r); ts.append(time.monotonic()); sizes.append(len(b))
            self.assertEqual(b, self.jpg)
        full_rate = sum(sizes[1:])/(ts[-1]-ts[0])
        low = self.stream(True)
        ts = []; sizes = []
        for _ in range(8):
            b = S.read_part(low); ts.append(time.monotonic()); sizes.append(len(b))
            im = cv2.imdecode(np.frombuffer(b, np.uint8), 1)
            self.assertEqual(im.shape[:2], (640, 360))
        rate = sum(sizes[1:])/(ts[-1]-ts[0])
        self.assertLess(rate, full_rate*.35)
        self.assertGreaterEqual(ts[-1]-ts[0], 7/3-.1)
        METRICS.update(default_bytes_per_frame=len(self.jpg), mobile_bytes_per_frame=sum(sizes)/len(sizes), default_bytes_per_second=full_rate, mobile_bytes_per_second=rate, source=str(SOURCE), source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest() if SOURCE.exists() else 'synthetic fallback')

    def test_truncated_upstream_retains_last_good(self):
        r = self.stream(); self.assertEqual(S.read_part(r), self.jpg)
        self.mode = 'truncated'
        for _ in range(3):
            self.assertEqual(S.read_part(r), self.jpg)
        self.assertEqual(self.proxy.jpg, self.jpg)

    def test_slow_upstream_complete_only(self):
        self.mode = 'slow'
        r = self.stream()
        for _ in range(3):
            self.assertEqual(S.read_part(r), self.jpg)

    def test_initial_truncation_placeholder_and_recovery(self):
        self.mode = 'truncated'
        r = self.stream()
        placeholder = S.read_part(r)
        self.assertTrue(O.complete_jpeg(placeholder))
        self.assertNotEqual(placeholder, self.jpg)
        self.mode = 'normal'
        self.assertTrue(wait(lambda: self.proxy.jpg == self.jpg))
        for _ in range(3):
            frame = S.read_part(r)
            self.assertTrue(O.complete_jpeg(frame))
            if frame == self.jpg:
                break
        self.assertEqual(frame, self.jpg)

    def test_stalled_upstream_controls_and_last_good(self):
        r = self.stream(); self.assertEqual(S.read_part(r), self.jpg)
        self.mode = 'stall'
        t = time.monotonic()
        for path in ('/pause', '/resume', '/readdeck', '/deck'):
            req = urllib.request.Request(self.base+path, data=b'Knight,Archers,Minions,Arrows,Fireball,Giant,MiniPekka,Musketeer', method='POST')
            with urllib.request.urlopen(req, timeout=1) as resp:
                self.assertEqual(resp.status, 200)
        self.assertLess(time.monotonic()-t, 1)
        self.assertEqual([p for p,b in self.posts], ['/pause','/resume','/readdeck','/deck'])
        self.assertEqual(S.read_part(r), self.jpg)

    def test_slow_client_and_reconnect_cleanup(self):
        before = len(os.listdir('/proc/self/fd'))
        slow = socket.socket(); slow.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,1024)
        slow.connect(('127.0.0.1', self.srv.server_port)); slow.sendall(b'GET /stream HTTP/1.0\r\n\r\n')
        try:
            for _ in range(5):
                r = self.stream(True); self.assertTrue(O.complete_jpeg(S.read_part(r))); r.close()
            with urllib.request.urlopen(self.base+'/state',timeout=1) as resp:
                self.assertTrue(json.load(resp)['driver'])
            self.assertLessEqual(self.active, 1)
        finally:
            slow.close()
        self.assertTrue(wait(lambda: self.proxy.clients == 0 and self.proxy.reader is None, 6))
        self.assertLessEqual(len(os.listdir('/proc/self/fd')), before+2)

    def test_direct_overlay_input_controls_and_low_mode(self):
        ov = O.Overlay(0, host='127.0.0.1', every=1)
        base = f'http://127.0.0.1:{ov.srv.server_port}'
        try:
            before = self.frame.copy(); ov.update(self.frame, state='viewer test')
            self.assertTrue(np.array_equal(self.frame, before))
            for suffix, shape in (('/stream', self.frame.shape[:2]),('/stream?low=1',(640,360))):
                with urllib.request.urlopen(base+suffix,timeout=2) as r:
                    b = S.read_part(r)
                    self.assertEqual(cv2.imdecode(np.frombuffer(b,np.uint8),1).shape[:2],shape)
            for path in ('/pause','/resume','/readdeck','/deck'):
                req = urllib.request.Request(base+path, data=b'Knight,Archers,Minions,Arrows,Fireball,Giant,MiniPekka,Musketeer',method='POST')
                with urllib.request.urlopen(req,timeout=1) as r:
                    self.assertEqual(r.status,200)
            self.assertTrue(ov.read_req); self.assertEqual(len(ov.take_deck()),8)
            self.assertIn(b'Mobile low bandwidth', O.PAGE)
        finally:
            ov.close()
        self.assertFalse(ov.thread.is_alive())
        self.assertEqual(ov.srv.socket.fileno(), -1)


if __name__ == '__main__':
    result = unittest.main(exit=False, verbosity=2).result
    if os.environ.get('VIEWER_REPORT'):
        Path(os.environ['VIEWER_REPORT']).write_text(json.dumps(METRICS, indent=2)+'\n')
    sys.exit(not result.wasSuccessful())
