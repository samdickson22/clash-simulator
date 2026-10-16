"""What the bot sees, drawn over the captured frame and served as an MJPEG page (open http://<mac>:PORT/ in a browser).

Draws: perceived units (box + identity; blue = ours, red = opponent), tower HP as read, hand/next/elixir, tick, and the
bot's latest play (card + target tile). Serving is a daemon thread; update() only swaps the latest JPEG.
"""
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2

import canvas as C

PAGE = rb"""<html><head><title>clasher live</title><style>
body{margin:0;background:#111;color:#ddd;font:14px -apple-system,sans-serif;display:flex}
#side{width:300px;padding:14px;box-sizing:border-box} button{font-size:18px;padding:10px 18px;margin:4px 0;width:100%;
border:0;border-radius:6px;cursor:pointer} #pause{background:#c0392b;color:#fff} #play{background:#27ae60;color:#fff}
#deck{width:100%;height:150px;font:13px monospace;background:#222;color:#ddd;border:1px solid #444} .st{margin:10px 0;
padding:8px;background:#222;border-radius:6px;white-space:pre-wrap} .on{color:#f39c12;font-weight:bold}</style></head>
<body><img src="/stream" style="height:100vh"><div id="side"><h3>clasher live</h3>
<button id="pause" onclick="post('/pause')">Pause bot</button><button id="play" onclick="post('/resume')">Resume bot</button>
<div class="st" id="st">...</div>
<div><label><input type="checkbox" id="vc" onchange="post('/view/candidates')"> model candidates + heatmap</label><br>
<label><input type="checkbox" id="vm" onchange="post('/view/model_units')"> old model units (when YOLO is on)</label></div>
<b>Battle deck (8 cards, one per line)</b><br>
<textarea id="deck"></textarea>
<button style="background:#2980b9;color:#fff" onclick="post('/readdeck')">Read deck from screen</button>
<button onclick="post('/deck', document.getElementById('deck').value)">Apply deck</button>
<div class="st" id="msg"></div>
<div style="color:#888;font-size:12px">Paused: the bot makes no taps at all (no plays, no menu navigation); a battle in
progress is not played by the bot. To change the deck: Pause, edit the deck in the game, stay on the Battle Deck page,
press "Read deck from screen" (fills the box and warns about cards the bot cannot play), Apply deck, Resume. The deck is
used from the next battle on.</div></div>
<script>
let deckLoaded=false, lastRead=0;
async function post(u,b){const r=await fetch(u,{method:'POST',body:b||''});document.getElementById('msg').textContent=await r.text();poll();}
async function poll(){try{const s=await (await fetch('/state')).json();
const oos=s.deck_out_of_scope||[];const blocked=oos.length>0;
if(s.driver===false){document.getElementById('st').innerHTML='<span class=on>BETWEEN SESSIONS: '+(s.reason||'no driver running')+
'</span>'+(s.paused?'\n<span class=on>PAUSED ('+s.paused_reason+'): the next session starts paused</span>':'')+
'\nlast session: '+(s.last_session||'-')+(s.last_end?' (ended '+s.last_end+')':'')+'\ndeck: '+s.deck.join(', ')+
(oos.length?'\n<span class=on>deck has cards the bot cannot play: '+oos.join(', ')+'</span>':'');
if(!deckLoaded){document.getElementById('deck').value=s.deck.join('\n');deckLoaded=true;}return;}
document.getElementById('st').innerHTML=(blocked?'<span class=on>BLOCKED: deck has cards the bot cannot see or play: '+oos.join(', ')+
'. No battles until the deck is changed.</span>\n':'')+((s.paused||blocked)?'<span class=on>PAUSED'+(s.paused_reason?' ('+s.paused_reason+')':'')+'</span>':'running')+'\nstate: '+s.state+
'\nbattle: '+(s.match||'-')+'\ndeck: '+s.deck.join(', ')+(s.deck_pending?'\n(new deck from next battle)':'');
if(!deckLoaded){document.getElementById('deck').value=s.deck.join('\n');deckLoaded=true;}
if(s.view){document.getElementById('vc').checked=!!s.view.candidates;document.getElementById('vm').checked=!!s.view.model_units;}
if(s.read&&s.read.t!==lastRead){lastRead=s.read.t;
document.getElementById('deck').value=s.read.cards.map(c=>c||'???').join('\n');
document.getElementById('msg').textContent=s.read.msg;}}catch(e){}}
setInterval(poll,1000);poll();
</script></body></html>"""


# display-only: the body a source card puts on the field (perception labels every body with its source card)
BODY = {'SkeletonArmy': 'Skeleton', 'Skeletons': 'Skeleton', 'GoblinGang': 'Goblin', 'Goblins': 'Goblin',
        'MinionHorde': 'Minion', 'Minions': 'Minion', 'Barbarians': 'Barbarian', 'Archers': 'Archer',
        'GoblinHut': 'Spear Goblin', 'Tombstone': 'Skeleton', 'Witch': 'Witch', 'Graveyard': 'Skeleton',
        'Rascals': 'Rascal', 'RoyalRecruits': 'Royal Recruit', 'ThreeMusketeers': 'Musketeer', 'Bats': 'Bat',
        'FireSpirits': 'Fire Spirit', 'IceSpirit': 'Ice Spirit', 'Golem': 'Golem', 'ElixirGolem': 'Elixir Golem',
        'BarbarianHut': 'Barbarian', 'Furnace': 'Fire Spirit', 'FirespiritHut': 'Fire Spirit',
        'RoyalHogs': 'Royal Hog', 'Wallbreakers': 'Wall Breaker', 'SpearGoblins': 'Spear Goblin'}


def label(cls):
    """'Skeleton (SkeletonArmy)' for multi-body / spawner cards, else the card name."""
    b = BODY.get(cls)
    return f'{b} ({cls})' if b and b.replace(' ', '') != cls else str(cls)


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
    """MJPEG view + control: POST /pause, /resume, /deck (8 card names); GET /state. The driver polls `paused` and
    `take_deck()`; `deck_check(names) -> error or None` is set by the driver (card names it can play)."""
    def __init__(self, port=8765, host='0.0.0.0', every=2):
        self.jpg, self.cv, self.n, self.every, self.maps = None, threading.Condition(), 0, every, None
        self.paused, self.deck, self.deck_pending, self.status = False, [], None, {}
        self.read_req, self.read_result = False, None
        self.view = dict(candidates=False, model_units=False)      # page toggles; off = only what the bot uses
        self.deck_check = lambda names: None
        self.lock = threading.Lock()
        ov = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def reply(self, code, body, ctype='text/plain'):
                b = body.encode() if isinstance(body, str) else body
                self.send_response(code); self.send_header('Content-Type', ctype)
                self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)

            def do_POST(self):
                n = int(self.headers.get('Content-Length') or 0)
                body = self.rfile.read(n).decode(errors='replace') if n else ''
                if self.path == '/pause':
                    with ov.lock: ov.paused = True
                    return self.reply(200, 'paused: the bot makes no taps')
                if self.path == '/resume':
                    with ov.lock: ov.paused = False
                    return self.reply(200, 'resumed')
                if self.path.startswith('/view/'):
                    key = self.path[len('/view/'):]
                    if key not in ov.view:
                        return self.reply(404, 'unknown view toggle')
                    with ov.lock: ov.view[key] = not ov.view[key]
                    return self.reply(200, f"{key}: {'shown' if ov.view[key] else 'hidden'}")
                if self.path == '/readdeck':
                    with ov.lock: ov.read_req, ov.read_result = True, None
                    return self.reply(200, 'reading the deck from the screen ...')
                if self.path == '/deck':
                    names = [w.strip() for w in body.replace(',', '\n').split('\n') if w.strip()]
                    err = 'need exactly 8 distinct cards' if len(names) != 8 or len(set(names)) != 8 else ov.deck_check(names)
                    if err:
                        return self.reply(400, f'deck NOT applied: {err}')
                    with ov.lock: ov.deck_pending = names
                    return self.reply(200, 'deck accepted; used from the next battle')
                return self.reply(404, 'unknown')

            def do_GET(self):
                if self.path == '/state':
                    import json
                    with ov.lock:
                        reason = ov.status.get('paused_reason') or ('page' if ov.paused else None)
                        st = dict(ov.status, paused=bool(reason), paused_reason=reason, paused_by_page=ov.paused,
                                  deck=ov.deck, deck_pending=ov.deck_pending,
                                  read=ov.read_result, view=dict(ov.view))
                    return self.reply(200, json.dumps(st), 'application/json')
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

    def take_deck(self):
        with self.lock:
            d, self.deck_pending = self.deck_pending, None
        return d

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
        show_cand = self.view.get('candidates')
        if heat is not None and show_cand:
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
        for u in sorted(units_lo if show_cand else (), key=lambda u: -u.get('score', 0)):
            if u.get('score', 0) >= .08 and all((u['x']-b['x'])**2 + (u['y']-b['y'])**2 > 1 for b in best):
                best.append(u)
        for u in best:
            if u['score'] >= .5:
                continue                         # drawn bold below from the record
            ax, ay = C.tile_to_android(u['x'], u['y'])
            col = (180, 180, 255) if u['owner'] else (255, 210, 150)
            if u['score'] < .3:                  # faint: a weak guess the bot never sees
                col = tuple(int(c*.45) for c in col)
            cv2.circle(img, P(ax, ay), 9, col, 1)
            cv2.putText(img, f"{label(u.get('cls'))} {u['score']:.2f}", P(ax+13, ay+5), 0, .38, col, 1)
        if rec is not None:
            if self.view.get('model_units') and rec.get('units_model') is not None:   # old model's units (YOLO on)
                for u in rec['units_model']:
                    ax, ay = C.tile_to_android(u['x'], u['y'])
                    cv2.circle(img, P(ax, ay), 14, (160, 160, 160), 1)
                    cv2.putText(img, f"model:{label(u.get('cls'))} {u.get('score', 0):.2f}", P(ax+16, ay-8), 0, .38,
                                (160, 160, 160), 1)
            for u in rec.get('units', ()):         # what the bot actually gets (YOLO's units with --units yolo)
                ax, ay = C.tile_to_android(u['x'], u['y'])
                w, h, lift = (v*C.ARENA_S for v in _box_shape(u.get('cls')))
                col = (255, 140, 0) if u['owner'] == 0 else (0, 0, 255)
                cv2.rectangle(img, P(ax-w/2, ay-lift-h/2), P(ax+w/2, ay-lift+h/2), col, 2)
                cv2.putText(img, f"{label(u.get('cls'))} {u.get('score', 0):.2f}", P(ax-w/2, ay-lift-h/2-6), 0, .45, col, 1)
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
