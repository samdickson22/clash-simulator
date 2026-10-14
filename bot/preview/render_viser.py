"""Render a RoyaleGym trace (capture_rsim.py) with RoyaleViser to MP4, with a player-name header and a result card.

    SDL_VIDEODRIVER=dummy <clasher-bot-rsim venv>/python render_viser.py TRACE.msgpack SUMMARY.json --mp4 OUT.mp4
One battle tick per frame at 30 fps = 1.5x real time.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
import pygame  # noqa: E402

FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
FONT_R = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BLUE_L, RED_L, WHITE, MUTED, GOLD = (150, 190, 255), (255, 160, 150), (238, 240, 246), (150, 158, 180), (255, 204, 64)
HEAD = 58


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('trace', type=Path)
    ap.add_argument('summary', type=Path)
    ap.add_argument('--mp4', type=Path, required=True)
    ap.add_argument('--scale', type=int, default=24)
    ap.add_argument('--crop', default='left')
    ap.add_argument('--still', type=int, default=None, help='write one PNG at this frame index instead')
    a = ap.parse_args()
    from royaleviser.capture import draw_frames
    from royaleviser.render import ViewState
    from royaleviser.sources import open_source
    import imageio_ffmpeg
    pygame.font.init()
    f_big, f_med, f_small = pygame.font.Font(FONT, 20), pygame.font.Font(FONT, 34), pygame.font.Font(FONT_R, 13)
    summ = json.loads(a.summary.read_text())
    blue_seat = summ['seat']
    names = {blue_seat: f"{summ['candidate']} (bot)", 1 - blue_seat: f"{summ['opponent']} (IL replay BC)"}
    src = open_source(str(a.trace))
    view = ViewState(seat=blue_seat)
    indices = list(range(src.length)) if a.still is None else [a.still]
    frames = draw_frames(src, indices, scale=a.scale, view=view, crop=a.crop)
    writer = None
    size = None
    canvas = None
    team_col = {0: BLUE_L, 1: RED_L}   # RoyaleViser colours by team: team 0 blue, team 1 red

    def header(surf):
        canvas.fill((17, 21, 33))
        canvas.blit(surf, (0, HEAD))
        cw = canvas.get_width()
        l = f_big.render(names[0] + '  (blue)', True, team_col[0])
        r = f_big.render(names[1] + '  (red)', True, team_col[1])
        vs = f_big.render('vs', True, MUTED)
        x = (cw - l.get_width() - r.get_width() - vs.get_width() - 32) // 2
        canvas.blit(l, (x, 6)); x += l.get_width() + 16
        canvas.blit(vs, (x, 6)); x += vs.get_width() + 16
        canvas.blit(r, (x, 6))
        tag = f_small.render('RoyaleSim 15.535  ·  drawn by RoyaleViser  ·  1.5x playback', True, MUTED)
        canvas.blit(tag, ((cw - tag.get_width()) // 2, 36))
        return canvas

    last = None
    for surf, idx in frames:
        if canvas is None:
            w, h = surf.get_size()
            size = (w + w % 2, h + HEAD + (h + HEAD) % 2)
            canvas = pygame.Surface(size)
            if a.still is None:
                writer = imageio_ffmpeg.write_frames(str(a.mp4), size, fps=30, codec='libx264', pix_fmt_in='rgb24',
                                                     pix_fmt_out='yuv420p', quality=None, macro_block_size=2,
                                                     output_params=['-crf', '23', '-preset', 'medium', '-movflags', '+faststart', '-threads', '4'])
                writer.send(None)
        out = header(surf)
        if a.still is not None:
            pygame.image.save(out, str(a.mp4.with_suffix(f'.{idx}.png')))
            return
        writer.send(pygame.image.tobytes(out, 'RGB'))
        last = out.copy()
    # result card, 4 s
    w = summ['winner']
    crowns = summ['crowns']
    cb, cr = crowns[str(blue_seat)] if isinstance(crowns, dict) else crowns[blue_seat], \
        crowns[str(1 - blue_seat)] if isinstance(crowns, dict) else crowns[1 - blue_seat]
    head = 'DRAW' if w is None else f'{names[w]} WINS'
    col = WHITE if w is None else team_col[w]
    t = summ['ticks'] / 20
    for k in range(120):
        fade = min(1.0, k / 15)
        s = last.copy()
        dim = pygame.Surface(size, pygame.SRCALPHA); dim.fill((8, 10, 18, int(200 * fade))); s.blit(dim, (0, 0))
        for text, font, colr, dy in ((head, f_med, col, -60), (f'{cb} – {cr}  crowns', f_med, GOLD, 0),
                                     (f"game time {int(t) // 60}:{int(t) % 60:02d}{' (overtime)' if t > 180 else ''}"
                                      f"  ·  seed {summ['seed']}", f_small, MUTED, 55)):
            g = font.render(text, True, colr); g.set_alpha(int(255 * fade))
            s.blit(g, g.get_rect(center=(size[0] // 2, size[1] // 2 + dy)))
        writer.send(pygame.image.tobytes(s, 'RGB'))
    writer.close()
    print('mp4', a.mp4, a.mp4.stat().st_size, size)


if __name__ == '__main__':
    main()
