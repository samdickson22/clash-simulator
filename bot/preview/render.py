"""Render a captured game (capture.py) to a showcase MP4 + highlight GIF (headless pygame + imageio-ffmpeg).

    SDL_VIDEODRIVER=dummy python render.py CAPTURE.pkl.gz --mp4 OUT.mp4 --gif OUT.gif

One game tick (20 Hz) per video frame at 30 fps = 1.5x real time. The bot under test (meta.seat)
is drawn blue at the bottom; the opponent red at the top.
"""
from __future__ import annotations

import argparse
import gzip
import math
import os
import pickle
import re
import subprocess
import sys
from pathlib import Path

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
import pygame  # noqa: E402

W, H = 1280, 720
T = 20                      # pixels per tile
AW, AH = 18 * T, 32 * T     # 360 x 640
AX, AY = (W - AW) // 2, 40
FPS = 30
TICKS_PER_FRAME = 1         # 20 ticks/s game -> 30 fps = 1.5x
LABEL_FRAMES = 45           # 1.5 s of video
TPS = 20

BG = (17, 21, 33)
PANEL = (28, 34, 52)
PANEL_EDGE = (52, 62, 92)
WHITE = (238, 240, 246)
MUTED = (150, 158, 180)
BLUE = (64, 132, 255)
BLUE_D = (28, 66, 150)
BLUE_L = (150, 190, 255)
RED = (238, 72, 72)
RED_D = (140, 30, 36)
RED_L = (255, 160, 150)
ELIXIR = (214, 64, 214)
GOLD = (255, 204, 64)

NAMES = {'blue': 'K4C-r16 (bot)', 'red': 'v1 (human prior)'}
PRETTY = {'Log': 'The Log', 'Pekka': 'P.E.K.K.A', 'MiniPekka': 'Mini P.E.K.K.A', 'Xbow': 'X-Bow',
          'GoblinBarrel': 'Goblin Barrel', 'IceGolemite': 'Ice Golem'}
FONT_DIR = '/usr/share/fonts/truetype/dejavu'


def pretty(card):
    if card in PRETTY:
        return PRETTY[card]
    return re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', card)


def font(size, bold=True):
    path = os.path.join(FONT_DIR, 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')
    return pygame.font.Font(path if os.path.exists(path) else None, size)


def mmss(seconds):
    s = max(0, int(math.ceil(seconds - 1e-6)))
    return f'{s // 60}:{s % 60:02d}'


class Renderer:
    def __init__(self, cap):
        pygame.init()
        self.cap = cap
        self.meta = cap['meta']
        self.blue = self.meta['seat']           # seat of the bot under test
        self.flip = self.blue == 0              # blue's side drawn at the bottom
        self.f = {k: font(s, b) for k, (s, b) in dict(
            tiny=(10, True), small=(12, True), body=(15, True), body_r=(15, False), med=(19, True),
            big=(26, True), clock=(44, True), huge=(54, True), name=(20, True)).items()}
        self._text = {}
        self.screen = pygame.Surface((W, H))
        self.arena_bg = self._arena_bg()
        frames = cap['frames']
        self.frames = frames
        # tower slots from the first frame (position + kind), so destroyed towers become rubble
        self.tower_slots = [(e['id'], e['p'], e['x'], e['y'], e['king']) for e in frames[0]['ents'] if e.get('tower')]
        self.plays = [p for p in cap['plays'] if p['ok']]
        self.end_tick = frames[-1]['tick']

    # ---------- helpers ----------
    def side(self, seat):
        return 'blue' if seat == self.blue else 'red'

    def col(self, seat, shade=''):
        s = self.side(seat)
        return {('blue', ''): BLUE, ('blue', 'd'): BLUE_D, ('blue', 'l'): BLUE_L,
                ('red', ''): RED, ('red', 'd'): RED_D, ('red', 'l'): RED_L}[(s, shade)]

    def w2s(self, x, y):
        if self.flip:
            x, y = 18 - x, 32 - y
        return int(AX + x * T), int(AY + y * T)

    def text(self, s, f='body', color=WHITE, shadow=True):
        key = (s, f, color, shadow)
        surf = self._text.get(key)
        if surf is None:
            fg = self.f[f].render(s, True, color)
            if shadow:
                surf = pygame.Surface((fg.get_width() + 2, fg.get_height() + 2), pygame.SRCALPHA)
                surf.blit(self.f[f].render(s, True, (0, 0, 0)), (2, 2))
                surf.blit(fg, (0, 0))
            else:
                surf = fg
            if len(self._text) > 4000:
                self._text.clear()
            self._text[key] = surf
        return surf

    def blit_text(self, s, pos, f='body', color=WHITE, anchor='topleft', shadow=True, target=None, alpha=None):
        surf = self.text(s, f, color, shadow)
        if alpha is not None and alpha < 255:
            surf = surf.copy(); surf.set_alpha(alpha)
        r = surf.get_rect(**{anchor: pos})
        (target or self.screen).blit(surf, r)
        return r

    # ---------- static arena ----------
    def _arena_bg(self):
        s = pygame.Surface((AW, AH))
        for ty in range(32):
            for tx in range(18):
                c = (98, 172, 74) if (tx + ty) % 2 == 0 else (90, 162, 68)
                if ty in (0, 31) and (tx < 6 or tx > 11):
                    c = (58, 92, 52)
                pygame.draw.rect(s, c, (tx * T, ty * T, T, T))
        # river (world y 15..17) and bridges (x 2..5, 13..16)
        pygame.draw.rect(s, (54, 140, 214), (0, 15 * T, AW, 2 * T))
        for i in range(0, AW, 14):
            pygame.draw.line(s, (90, 172, 236), (i, 15 * T + 12), (i + 7, 15 * T + 12), 2)
            pygame.draw.line(s, (90, 172, 236), (i + 5, 16 * T + 10), (i + 12, 16 * T + 10), 2)
        for bx in (2, 13):
            pygame.draw.rect(s, (150, 108, 66), (bx * T, 15 * T - 4, 3 * T, 2 * T + 8))
            for k in range(1, 6):
                yy = 15 * T - 4 + k * (2 * T + 8) // 6
                pygame.draw.line(s, (112, 78, 46), (bx * T, yy), (bx * T + 3 * T - 1, yy), 1)
            pygame.draw.rect(s, (90, 62, 36), (bx * T, 15 * T - 4, 3 * T, 2 * T + 8), 2)
        # side tints: blue half / red half (subtle)
        tint = pygame.Surface((AW, 15 * T), pygame.SRCALPHA)
        tint.fill((255, 80, 80, 14)); s.blit(tint, (0, 0))
        tint.fill((80, 120, 255, 16)); s.blit(tint, (0, 17 * T))
        pygame.draw.rect(s, (40, 60, 36), (0, 0, AW, AH), 3)
        return s

    # ---------- dynamic drawing ----------
    def draw_towers(self, fr):
        alive = {e['id']: e for e in fr['ents'] if e.get('tower')}
        for tid, p, x, y, king in self.tower_slots:
            sx, sy = self.w2s(x, y)
            half = int((2.0 if king else 1.5) * T)
            rect = pygame.Rect(sx - half, sy - half, 2 * half, 2 * half)
            e = alive.get(tid)
            if e is None:  # destroyed
                pygame.draw.rect(self.screen, (92, 86, 78), rect, border_radius=6)
                for k in range(5):
                    rx = sx - half + 6 + (k * 13) % (2 * half - 12)
                    ry = sy - half + 6 + (k * 17) % (2 * half - 12)
                    pygame.draw.circle(self.screen, (124, 116, 104), (rx, ry), 5)
                pygame.draw.rect(self.screen, (54, 50, 46), rect, 2, border_radius=6)
                continue
            pygame.draw.rect(self.screen, self.col(p, 'd'), rect, border_radius=6)
            pygame.draw.rect(self.screen, self.col(p), rect.inflate(-8, -8), border_radius=5)
            pygame.draw.rect(self.screen, (20, 20, 28), rect, 2, border_radius=6)
            if king:  # crown
                cx, cy = sx, sy
                pts = [(cx - 12, cy + 6), (cx - 12, cy - 6), (cx - 6, cy), (cx, cy - 9), (cx + 6, cy), (cx + 12, cy - 6), (cx + 12, cy + 6)]
                pygame.draw.polygon(self.screen, GOLD, pts); pygame.draw.polygon(self.screen, (120, 90, 10), pts, 2)
            ratio = max(0.0, min(1.0, e['hp'] / max(1.0, e['mhp'])))
            bw = 2 * half + 6
            bx, by = sx - bw // 2, sy - half - 11
            pygame.draw.rect(self.screen, (10, 10, 14), (bx - 1, by - 1, bw + 2, 8))
            pygame.draw.rect(self.screen, self.col(p, 'l') if ratio > 0.3 else GOLD, (bx, by, int(bw * ratio), 6))
            self.blit_text(f'{int(e["hp"])}', (sx, sy + half + 1), 'small', WHITE, 'midtop')

    def draw_entities(self, fr):
        overlay = pygame.Surface((AW, AH), pygame.SRCALPHA)
        units, air = [], []
        for e in fr['ents']:
            if e.get('tower') or e.get('kind') == 'ERR':
                continue
            k = e['kind']
            sx, sy = self.w2s(e['x'], e['y'])
            ox, oy = sx - AX, sy - AY
            if k in ('AreaEffect', 'BuffAreaEffect', 'DeathAreaEffectContainer'):
                rad = int(max(e['radius'], 1.0) * T)
                pygame.draw.circle(overlay, (255, 230, 120, 70), (ox, oy), rad)
                pygame.draw.circle(overlay, (255, 230, 120, 170), (ox, oy), rad, 2)
                continue
            if k in ('Projectile', 'SpawnProjectile'):
                if e['splash'] > 0.9 and e['tx'] is not None:  # spell-sized splash: show the landing zone
                    tx, ty = self.w2s(e['tx'], e['ty'])
                    pygame.draw.circle(overlay, (255, 150, 60, 50), (tx - AX, ty - AY), int(e['splash'] * T))
                    pygame.draw.circle(overlay, (255, 150, 60, 150), (tx - AX, ty - AY), int(e['splash'] * T), 2)
                    pygame.draw.circle(self.screen, (255, 170, 60), (sx, sy), 7)
                    pygame.draw.circle(self.screen, (255, 240, 180), (sx, sy), 4)
                else:
                    pygame.draw.circle(self.screen, (255, 250, 210), (sx, sy), 3)
                    pygame.draw.circle(self.screen, self.col(e['p'], 'd'), (sx, sy), 3, 1)
                continue
            if k == 'RollingProjectile':
                w_, h_ = int(max(e['roll'][0], 1.0) * 2 * T), int(max(e['roll'][1], 0.4) * 2 * T)
                r = pygame.Rect(0, 0, w_, h_); r.center = (sx, sy)
                pygame.draw.rect(self.screen, (132, 92, 52), r, border_radius=h_ // 2)
                pygame.draw.rect(self.screen, (70, 44, 20), r, 2, border_radius=h_ // 2)
                continue
            if k in ('Troop', 'Building'):
                (air if e['air'] else units).append(e)
                continue
            pygame.draw.circle(overlay, (255, 255, 255, 90), (ox, oy), 8)  # misc effect markers
        self.screen.blit(overlay, (AX, AY))
        self._labels = []
        for e in units + air:
            self.draw_unit(e)

    def draw_unit(self, e):
        sx, sy = self.w2s(e['x'], e['y'])
        rad = max(5, int(e['r'] * T * 0.9))
        p = e['p']
        if e['air']:
            pygame.draw.ellipse(self.screen, (30, 60, 30), (sx - rad, sy + 2, 2 * rad, rad))
            sy -= 10
        fill, edge = self.col(p), self.col(p, 'd')
        if e['pending']:
            ghost = pygame.Surface((2 * rad + 4, 2 * rad + 4), pygame.SRCALPHA)
            pygame.draw.circle(ghost, (*fill, 110), (rad + 2, rad + 2), rad)
            pygame.draw.circle(ghost, (255, 255, 255, 160), (rad + 2, rad + 2), rad, 1)
            self.screen.blit(ghost, (sx - rad - 2, sy - rad - 2))
        elif e['kind'] == 'Building':
            r = pygame.Rect(sx - rad, sy - rad, 2 * rad, 2 * rad)
            pygame.draw.rect(self.screen, fill, r, border_radius=4)
            pygame.draw.rect(self.screen, (15, 15, 20), r, 2, border_radius=4)
        else:
            pygame.draw.circle(self.screen, fill, (sx, sy), rad)
            pygame.draw.circle(self.screen, self.col(p, 'l'), (sx - rad // 3, sy - rad // 3), max(2, rad // 3))
            pygame.draw.circle(self.screen, (15, 15, 20) if not e['air'] else WHITE, (sx, sy), rad, 2)
            if 0 <= e['attack'] < 0.12:
                pygame.draw.circle(self.screen, (255, 255, 220), (sx, sy), rad + 3, 2)
        if e['mhp'] > 0 and e['hp'] < e['mhp'] and not e['pending']:
            ratio = max(0.0, e['hp'] / e['mhp'])
            bw = max(16, 2 * rad)
            pygame.draw.rect(self.screen, (10, 10, 14), (sx - bw // 2 - 1, sy - rad - 7, bw + 2, 5))
            pygame.draw.rect(self.screen, self.col(p, 'l'), (sx - bw // 2, sy - rad - 6, int(bw * ratio), 3))
        if (rad >= 8 or e['kind'] == 'Building') and not any(
                n == e['eng'] and abs(lx - sx) < 40 and abs(ly - sy) < 24 for n, lx, ly in self._labels):
            self._labels.append((e['eng'], sx, sy))
            label = e['eng'] if len(e['eng']) <= 11 else e['eng'][:10] + '.'
            self.blit_text(label, (sx, sy + rad + 1), 'tiny', WHITE, 'midtop')

    def draw_play_labels(self, tick):
        active = [p for p in self.plays if 0 <= tick - p['tick'] < LABEL_FRAMES * TICKS_PER_FRAME]
        placed = []
        for p in active:
            age = (tick - p['tick']) / TICKS_PER_FRAME
            alpha = 255 if age < LABEL_FRAMES - 12 else int(255 * (LABEL_FRAMES - age) / 12)
            sx, sy = self.w2s(p['x'], p['y'])
            ring = int(6 + age * 0.9)
            if age < 18:
                pygame.draw.circle(self.screen, WHITE, (sx, sy), ring, 2)
            s = f"{'Blue' if self.side(p['seat']) == 'blue' else 'Red'}: {pretty(p['card'])}"
            surf = self.text(s, 'body', WHITE, False)
            pill = pygame.Surface((surf.get_width() + 16, surf.get_height() + 8), pygame.SRCALPHA)
            pygame.draw.rect(pill, (*self.col(p['seat'], 'd'), 235), pill.get_rect(), border_radius=10)
            pygame.draw.rect(pill, (*self.col(p['seat'], 'l'), 255), pill.get_rect(), 2, border_radius=10)
            pill.blit(surf, (8, 4))
            r = pill.get_rect(midbottom=(sx, sy - 14))
            r.clamp_ip(pygame.Rect(AX - 26, AY, AW + 52, AH))
            while any(r.colliderect(q) for q in placed):
                r.move_ip(0, -(r.height + 2) if self.side(p['seat']) == 'blue' else r.height + 2)
            placed.append(r)
            pill.set_alpha(alpha)
            self.screen.blit(pill, r)

    def crowns(self, fr, seat):
        """Crowns earned by `seat` = enemy towers destroyed (king = 3)."""
        tw = fr['players'][1 - seat]['towers']
        if tw[0] <= 0:
            return 3
        return int(tw[1] <= 0) + int(tw[2] <= 0)

    def player_card(self, fr, seat, top):
        x0, w = 28, 400
        h = 200
        y0 = 40 if top else H - 40 - h
        side = self.side(seat)
        pygame.draw.rect(self.screen, PANEL, (x0, y0, w, h), border_radius=14)
        pygame.draw.rect(self.screen, self.col(seat), (x0, y0, 8, h), border_top_left_radius=14, border_bottom_left_radius=14)
        pygame.draw.rect(self.screen, PANEL_EDGE, (x0, y0, w, h), 2, border_radius=14)
        self.blit_text(NAMES[side], (x0 + 24, y0 + 14), 'big', self.col(seat, 'l'))
        sub = 'search bot  ·  BLUE' if side == 'blue' else 'imitation policy  ·  RED'
        self.blit_text(sub, (x0 + 24, y0 + 48), 'small', MUTED)
        # crowns
        c = self.crowns(fr, seat)
        for k in range(3):
            cx, cy = x0 + w - 100 + k * 30, y0 + 30
            pts = [(cx - 11, cy + 8), (cx - 11, cy - 5), (cx - 5, cy + 1), (cx, cy - 9), (cx + 5, cy + 1), (cx + 11, cy - 5), (cx + 11, cy + 8)]
            pygame.draw.polygon(self.screen, GOLD if k < c else (70, 76, 96), pts)
            pygame.draw.polygon(self.screen, (20, 20, 28), pts, 2)
        # elixir
        el = fr['players'][seat]['elixir']
        ey = y0 + 82
        self.blit_text('Elixir', (x0 + 24, ey), 'body', WHITE)
        bx, bw, bh = x0 + 100, 250, 20
        pygame.draw.rect(self.screen, (40, 18, 46), (bx, ey, bw, bh), border_radius=6)
        pygame.draw.rect(self.screen, ELIXIR, (bx, ey, int(bw * min(el, 10) / 10), bh), border_radius=6)
        for k in range(1, 10):
            pygame.draw.line(self.screen, (40, 18, 46), (bx + k * bw // 10, ey), (bx + k * bw // 10, ey + bh - 1), 2)
        pygame.draw.rect(self.screen, (120, 60, 130), (bx, ey, bw, bh), 2, border_radius=6)
        self.blit_text(f'{int(el)}', (bx + bw + 12, ey + bh // 2), 'med', (255, 150, 255), 'midleft')
        # hand
        hy = y0 + 120
        self.blit_text('Hand', (x0 + 24, hy + 6), 'small', MUTED)
        hand = fr['players'][seat]['hand']
        for k, card in enumerate(hand):
            cw = 70
            r = pygame.Rect(x0 + 72 + k * (cw + 6), hy, cw, 30)
            pygame.draw.rect(self.screen, (44, 52, 78), r, border_radius=6)
            pygame.draw.rect(self.screen, self.col(seat, 'd'), r, 2, border_radius=6)
            name = pretty(card)
            name = name if len(name) <= 9 else name[:8] + '.'
            self.blit_text(name, r.center, 'tiny', WHITE, 'center', shadow=False)
        nxt = fr['players'][seat]['nxt']
        if nxt:
            self.blit_text(f'Next: {pretty(nxt)}', (x0 + 72, hy + 40), 'small', MUTED)

    def right_panel(self, fr, tick):
        x0, w = W - 28 - 400, 400
        pygame.draw.rect(self.screen, PANEL, (x0, 40, w, 150), border_radius=14)
        pygame.draw.rect(self.screen, PANEL_EDGE, (x0, 40, w, 150), 2, border_radius=14)
        t = fr['time']
        if fr['overtime'] or t >= 180:
            label, rem, colr = 'OVERTIME', 300 - t, GOLD
        else:
            label, rem, colr = 'TIME LEFT', 180 - t, WHITE
        self.blit_text(label, (x0 + 24, 54), 'small', MUTED)
        self.blit_text(mmss(rem), (x0 + 24, 70), 'clock', colr)
        phase = '3x ELIXIR' if fr['triple'] else ('2x ELIXIR' if fr['double'] else '1x ELIXIR')
        pc = (255, 120, 255) if fr['double'] or fr['triple'] else MUTED
        self.blit_text(phase, (x0 + w - 24, 58), 'med', pc, 'topright')
        self.blit_text(f'game time {int(t) // 60}:{int(t) % 60:02d}', (x0 + w - 24, 92), 'small', MUTED, 'topright')
        self.blit_text('playback 1.5x', (x0 + w - 24, 112), 'small', MUTED, 'topright')
        cb, cr = self.crowns(fr, self.blue), self.crowns(fr, 1 - self.blue)
        self.blit_text(f'{cb}', (x0 + 24, 138), 'big', BLUE_L)
        self.blit_text('crowns', (x0 + 60, 146), 'small', MUTED)
        self.blit_text(f'{cr}', (x0 + 150, 138), 'big', RED_L)
        # play feed
        fy = 206
        fh = H - 40 - fy
        pygame.draw.rect(self.screen, PANEL, (x0, fy, w, fh), border_radius=14)
        pygame.draw.rect(self.screen, PANEL_EDGE, (x0, fy, w, fh), 2, border_radius=14)
        self.blit_text('CARD PLAYS', (x0 + 24, fy + 14), 'small', MUTED)
        recent = [p for p in self.plays if p['tick'] <= tick][-15:][::-1]
        for k, p in enumerate(recent):
            yy = fy + 40 + k * 29
            pt = p['tick'] / TPS
            alpha = 255 if k < 10 else int(255 * (15 - k) / 6)
            tag = 'Blue' if self.side(p['seat']) == 'blue' else 'Red'
            self.blit_text(f'{int(pt) // 60}:{int(pt) % 60:02d}', (x0 + 24, yy), 'body_r', MUTED, alpha=alpha)
            pygame.draw.circle(self.screen, self.col(p['seat']), (x0 + 92, yy + 10), 6)
            self.blit_text(f'{tag}: {pretty(p["card"])}', (x0 + 106, yy), 'body', self.col(p['seat'], 'l'), alpha=alpha)

    def banners(self):
        self.blit_text(NAMES['red'], (AX + AW // 2, AY - 6), 'name', RED_L, 'midbottom')
        self.blit_text(NAMES['blue'], (AX + AW // 2, AY + AH + 6), 'name', BLUE_L, 'midtop')

    def frame(self, k):
        fr = self.frames[k]
        tick = fr['tick']
        self.screen.fill(BG)
        self.screen.blit(self.arena_bg, (AX, AY))
        self.draw_towers(fr)
        self.draw_entities(fr)
        self.draw_play_labels(tick)
        self.banners()
        self.player_card(fr, 1 - self.blue, top=True)
        self.player_card(fr, self.blue, top=False)
        self.right_panel(fr, tick)
        return self.screen

    def result(self):
        fr = self.frames[-1]
        cb, cr = self.crowns(fr, self.blue), self.crowns(fr, 1 - self.blue)
        w = self.cap['result']['winner']
        if w is None or w == -1:
            head, colr = 'DRAW', WHITE
        else:
            head, colr = (f'{NAMES["blue"]} WINS', BLUE_L) if w == self.blue else (f'{NAMES["red"]} WINS', RED_L)
        return dict(head=head, colr=colr, cb=cb, cr=cr, t=fr['time'])

    def final_card(self, base, fade=1.0):
        s = base.copy()
        dim = pygame.Surface((W, H), pygame.SRCALPHA); dim.fill((8, 10, 18, int(200 * fade)))
        s.blit(dim, (0, 0))
        r = self.result()
        a = int(255 * fade)
        box = pygame.Rect(0, 0, 640, 300); box.center = (W // 2, H // 2)
        panel = pygame.Surface(box.size, pygame.SRCALPHA)
        pygame.draw.rect(panel, (*PANEL, int(240 * fade)), panel.get_rect(), border_radius=20)
        pygame.draw.rect(panel, (*GOLD, a), panel.get_rect(), 3, border_radius=20)
        s.blit(panel, box)
        self.blit_text(r['head'], (W // 2, box.top + 30), 'huge', r['colr'], 'midtop', target=s, alpha=a)
        y = box.top + 120
        self.blit_text(f'{r["cb"]}', (W // 2 - 70, y), 'huge', BLUE_L, 'midtop', target=s, alpha=a)
        self.blit_text('–', (W // 2, y), 'huge', WHITE, 'midtop', target=s, alpha=a)
        self.blit_text(f'{r["cr"]}', (W // 2 + 70, y), 'huge', RED_L, 'midtop', target=s, alpha=a)
        self.blit_text('crowns', (W // 2, y + 66), 'small', MUTED, 'midtop', target=s, alpha=a)
        ot = ' (overtime)' if r['t'] > 180 else ''
        t = int(r['t'])
        self.blit_text(f'Game time {t // 60}:{t % 60:02d}{ot}   ·   seed {self.meta["seed"]}',
                       (W // 2, box.bottom - 36), 'body_r', MUTED, 'midtop', target=s, alpha=a)
        return s

    def title_card(self, base, fade=1.0):
        s = base.copy()
        dim = pygame.Surface((W, H), pygame.SRCALPHA); dim.fill((8, 10, 18, int(215 * fade)))
        s.blit(dim, (0, 0))
        a = int(255 * fade)
        self.blit_text('Clasher  ·  bot showcase', (W // 2, 200), 'huge', WHITE, 'midtop', target=s, alpha=a)
        self.blit_text(NAMES['blue'], (W // 2 - 30, 300), 'big', BLUE_L, 'topright', target=s, alpha=a)
        self.blit_text('vs', (W // 2, 304), 'med', MUTED, 'midtop', target=s, alpha=a)
        self.blit_text(NAMES['red'], (W // 2 + 30, 300), 'big', RED_L, 'topleft', target=s, alpha=a)
        self.blit_text(f'our engine (Python physics)  ·  level 11  ·  HEADLINE case {self.meta["index"]}  ·  1.5x playback',
                       (W // 2, 370), 'body_r', MUTED, 'midtop', target=s, alpha=a)
        return s


def surf_bytes(s):
    return pygame.image.tobytes(s, 'RGB')


def ffmpeg_writer(path, fps, size=(W, H), crf=23):
    import imageio_ffmpeg
    w = imageio_ffmpeg.write_frames(str(path), size, fps=fps, codec='libx264', pix_fmt_in='rgb24', pix_fmt_out='yuv420p',
                                    quality=None, macro_block_size=8,
                                    output_params=['-crf', str(crf), '-preset', 'medium', '-movflags', '+faststart', '-threads', '4'])
    w.send(None)
    return w


def blue_kill_window(cap, span):
    """Window ending ~2 s after the last enemy tower the bot under test destroyed (the decisive push), or None."""
    frames, blue = cap['frames'], cap['meta']['seat']
    kills = []
    for i in range(1, len(frames)):
        a, b = frames[i - 1]['players'][1 - blue]['towers'], frames[i]['players'][1 - blue]['towers']
        if any(x > 0 >= y for x, y in zip(a, b)):
            kills.append(i)
    if not kills:
        return None
    end = min(len(frames), kills[-1] + 40)
    return max(0, end - span), kills[-1]


def highlight_window(cap, frames_len_ticks):
    """Start tick of the most action-packed window: tower damage + card plays, big bonus for a tower kill."""
    frames = cap['frames']
    n = len(frames)
    score = [0.0] * n
    prev = None
    for i, fr in enumerate(frames):
        cur = [v for p in fr['players'] for v in p['towers']]
        if prev is not None:
            for a, b in zip(prev, cur):
                if b < a:
                    score[i] += (a - b) / 100.0
                if a > 0 >= b:
                    score[i] += 400.0
        prev = cur
    by_tick = {fr['tick']: i for i, fr in enumerate(frames)}
    for p in cap['plays']:
        if p['ok'] and p['tick'] in by_tick:
            score[by_tick[p['tick']]] += 4.0
    best, best_i, run = -1, 0, sum(score[:frames_len_ticks])
    for i in range(0, n - frames_len_ticks):
        if i:
            run += score[i + frames_len_ticks - 1] - score[i - 1]
        # prefer windows whose biggest moment is not at the very edge
        if run > best:
            best, best_i = run, i
    return best_i, best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('capture', type=Path)
    ap.add_argument('--mp4', type=Path)
    ap.add_argument('--gif', type=Path)
    ap.add_argument('--gif-seconds', type=float, default=15.0)
    ap.add_argument('--gif-scale', type=float, default=0.8)
    ap.add_argument('--gif-fps', type=int, default=15)
    ap.add_argument('--still', type=Path, help='write a PNG of frame --still-frame and exit')
    ap.add_argument('--still-frame', type=int, default=1200)
    a = ap.parse_args()
    with gzip.open(a.capture, 'rb') as fh:
        cap = pickle.load(fh)
    R = Renderer(cap)
    if a.still:
        pygame.image.save(R.frame(min(a.still_frame, len(R.frames) - 1)), str(a.still))
        pygame.image.save(R.final_card(R.frame(len(R.frames) - 1)), str(a.still.with_suffix('.final.png')))
        pygame.image.save(R.title_card(R.frame(0)), str(a.still.with_suffix('.title.png')))
        return
    if a.mp4:
        wr = ffmpeg_writer(a.mp4, FPS)
        first = R.frame(0).copy()
        for k in range(int(2.5 * FPS)):   # title, then fade into the game
            fade = 1.0 if k < 2.0 * FPS else 1.0 - (k - 2.0 * FPS) / (0.5 * FPS)
            wr.send(surf_bytes(R.title_card(first, fade)))
        for k in range(0, len(R.frames), TICKS_PER_FRAME):
            wr.send(surf_bytes(R.frame(k)))
        last = R.frame(len(R.frames) - 1).copy()
        for k in range(int(0.5 * FPS)):
            wr.send(surf_bytes(last))
        for k in range(int(4.5 * FPS)):
            wr.send(surf_bytes(R.final_card(last, min(1.0, k / (0.5 * FPS)))))
        wr.close()
        print('mp4', a.mp4, a.mp4.stat().st_size)
    if a.gif:
        span = int(a.gif_seconds * FPS * TICKS_PER_FRAME)
        bk = blue_kill_window(cap, span)
        start, sc = bk if bk else highlight_window(cap, span)
        step = max(1, round(FPS / a.gif_fps)) * TICKS_PER_FRAME
        gw, gh = int(W * a.gif_scale) // 2 * 2, int(H * a.gif_scale) // 2 * 2
        tmp = a.gif.with_suffix('.seg.mp4')
        wr = ffmpeg_writer(tmp, FPS / (step / TICKS_PER_FRAME), size=(gw, gh), crf=12)
        for k in range(start, min(start + span, len(R.frames)), step):
            wr.send(surf_bytes(pygame.transform.smoothscale(R.frame(k), (gw, gh))))
        if start + span >= len(R.frames):  # the window reaches the end: close on the result card
            last = R.frame(len(R.frames) - 1).copy()
            n = int(2.0 * a.gif_fps)
            for k in range(n):
                card = R.final_card(last, min(1.0, k / (0.3 * a.gif_fps)))
                wr.send(surf_bytes(pygame.transform.smoothscale(card, (gw, gh))))
        wr.close()
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        subprocess.run([ff, '-y', '-loglevel', 'error', '-i', str(tmp), '-vf',
                        'split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle',
                        '-loop', '0', str(a.gif)], check=True)
        tmp.unlink()
        f0, f1 = R.frames[start]['time'], R.frames[min(start + span, len(R.frames) - 1)]['time']
        print('gif', a.gif, a.gif.stat().st_size, f'window game time {f0:.1f}-{f1:.1f}s score {sc:.1f}')


if __name__ == '__main__':
    sys.exit(main())
