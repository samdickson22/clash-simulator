"""Rebuild perception.jsonl + session-config.json for battles played before live logging (s6), from the saved video.

  python reconstruct.py RUN_DIR --export EXPORT_DIR [--threads 8]

For every frame the driver processed (frames.jsonl rows with perc_ms), in order and with the same ts_ms: the same
brightness normalization and canvas mapping, LivePerception on the export that played the battle (fresh state at match
start, as the driver), then the driver's overrides from what it logged for that frame: elixir = the bar reading,
floored at the pending reservations ('elixir_floored'); phase / clock_s from the anchored tick; towers from the logged
(owner, kind, side, alive, hp_read) with hp_frac = hp / max HP at the tower level read in that battle (live1-2 logged
perception's own tower head: kept as decoded). The perception itself is recomputed (05 CPU vs Mac CPU: tiny numeric
differences possible). Rows carry logged='reconstructed'.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent/'perception'), str(HERE.parent.parent/'src')]
import canvas as C  # noqa: E402
import towers as TW  # noqa: E402


def normalize(f):
    w = float(np.percentile(f[1600:1920:2, ::2].max(2), 99.5))
    return (f if w >= 245 or w < 80 else cv2.convertScaleAbs(f, alpha=255./w))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run')
    ap.add_argument('--export', required=True)
    ap.add_argument('--threads', type=int, default=8)
    a = ap.parse_args()
    import torch
    torch.set_num_threads(a.threads)
    from infer import LivePerception
    d = Path(a.run)
    F = [json.loads(l) for l in open(d/'frames.jsonl')]
    B = [f for f in F if f.get('perc_ms') is not None]
    if not B:
        sys.exit(f'{d}: no processed battle frames')
    # tower level per side from the largest princess reading (as TowerReader.level)
    lv = {}
    for side, owner in (('own', 0), ('opp', 1)):
        reads = [t[4] for f in B for t in f.get('towers') or [] if t[0] == owner and t[1] == 'p' and isinstance(t[4], int)]
        lv[side] = TW.level_of_princess(max(reads)) if reads and max(reads) > 2 else 1
    p = LivePerception(a.export)
    out = open(d/'perception.jsonl', 'w')
    for f in B:
        im = cv2.imread(str(d/'video'/f"{f['n']:06d}.jpg"))
        if im is None:
            continue
        rec = p.step(C.canvas(normalize(C.to_android(im))), f['ts_ms'])
        tick = f['tick']
        rec['elixir'] = max(f.get('elixir') or 0., f.get('elixir_floored') or 0.)
        rec['phase'] = 1 if tick < 2400 else (2 if tick < 4800 else 3)
        rec['clock_s'] = max(0., 180 - tick/20) if tick < 3600 else max(0., 300 - tick/20)
        logged = {(t[0], t[1], t[2]): t for t in f.get('towers') or []}
        for t in rec['towers']:
            r = logged.get((t['owner'], t['kind'][0], t['side'][0]))
            if r is not None and isinstance(r[4], (int, float)) and r[4] > 1:        # OCR era: hp_read logged
                mx = TW.tower_hp(t['kind'], lv['own' if t['owner'] == 0 else 'opp'])
                t['alive'], t['hp_read'] = bool(r[3]), int(r[4])
                full = r[4] in {TW.tower_hp(t['kind'], l) for l in range(1, 16)}   # driver's undamaged placeholder
                t['hp_frac'] = (1.0 if full else round(min(1., r[4]/mx), 4)) if r[3] else 0.
            elif r is not None:
                t['alive'] = bool(r[3])
                if not r[3]:
                    t['hp_frac'] = 0.
        rec.update(n=f['n'], tick=tick, ts_ms=f['ts_ms'], logged='reconstructed')
        out.write(json.dumps(rec, default=float) + '\n')
    out.close()
    sha = hashlib.sha256((Path(a.export)/'frame.pt').read_bytes()).hexdigest()
    ev = [json.loads(l) for l in open(d/'events.jsonl')] if (d/'events.jsonl').exists() else []
    loaded = next((e for e in ev if e.get('ev') == 'loaded'), {})
    cfg = dict(schema='clasher.live.loop.session-config.v1', logged='reconstructed',
               deck=['Knight', 'Archers', 'Minions', 'Arrows', 'Fireball', 'Giant', 'MiniPekka', 'Musketeer'],
               player=loaded.get('player', 'LIVE-K4L-R-gs-rw-fc-w200-t4-p4'), fast=loaded.get('fast'),
               export=str(a.export), export_frame_sha256=sha, unit_threshold=p.ut, tower_threshold=p.tt,
               event_threshold=p.et, unit_filter=None, tower_levels=lv,
               translator=dict(cls='bot.live.translate.LiveTranslator', unknown_card='drop', plays_from='births'),
               session=dict(cls='bot.live.translate.LiveSession', seed=0, command_delay=27, expire=90))
    (d/'session-config.json').write_text(json.dumps(cfg, indent=1) + '\n')
    print(d.name, len(B), 'frames reconstructed with', sha[:12])


if __name__ == '__main__':
    main()
