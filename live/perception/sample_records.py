"""Sample downstream records for the bot-side test: LivePerception over whole validation matches
(raw 540x1140 frames from the original cache, every `stride`-th frame), each paired with the
truth in the same schema. Validation only.

  python sample_records.py EXPORT_DIR OUT_DIR [n_matches] [stride]
Writes OUT_DIR/<episode>.jsonl, one line per processed frame: {episode, seq, tick, pred, truth}.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

import common as C
import dense_labels as D
from infer import LivePerception

LABELS = Path('/mpac/sdicks02/jobs/clasher/live-perception-20261014/labels')


def truth_record(lab, ev_rows, i, cards, now_ms):
    got = D.frame_objects(lab, i); n = len(cards)
    units, towers = [], []
    alive = {}
    if got is not None:
        cls, own, x, y, frac, _ = got
        for c, o, xx, yy, f in zip(cls, own, x, y, frac):
            if c >= n:
                alive[(int(o), round(float(xx)*1000), round(float(yy)*1000))] = float(f); continue
            ow, bx, by = C.own_view(int(o), float(xx), float(yy))
            units.append(dict(cls=cards[c], card=cards[c], owner=ow, x=round(bx, 3), y=round(by, 3), hp_frac=round(float(f), 4)))
        for o, kind, side, ax, ay in C.TOWER_SLOTS:
            f = alive.get((o, ax, ay)); ow, _, _ = C.own_view(o, 9, 16)
            towers.append(dict(owner=ow, kind=kind, side=side, alive=f is not None, hp_frac=round(f, 4) if f is not None else 0.))
    hand = [cards[k] if k < n else None for k in lab['hand'][i]]
    evs = []
    for e in ev_rows:  # events executed in the last 1.5 s
        if 0 <= now_ms-e['exec_tick']*50. <= 1500:
            ow, bx, by = C.own_view(e['side'], e['tile'][0], e['tile'][1])
            evs.append(dict(owner=ow, card=e['card'], x=bx, y=by, tick=e['exec_tick']*50.))
    return dict(timestamp_ms=now_ms, units=units, towers=towers if got is not None else None,
                hand=dict(cards=hand[:4], next=hand[4]), elixir=float(lab['elixir'][i]), clock_s=float(lab['clock'][i]),
                phase=int(lab['phase'][i]), events=evs, objects_stale=got is None)


def main():
    export, out = Path(sys.argv[1]), Path(sys.argv[2]); nm = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    stride = int(sys.argv[4]) if len(sys.argv) > 4 else 2; out.mkdir(parents=True, exist_ok=True)
    from pixel_cache import decompress, RAW
    guard = C.HeldoutGuard(); eps = [e for e in guard.episodes('validation') if (C.CACHE/e/'raw.zst').exists()][:nm]; guard.check(eps)
    p = LivePerception(export, device='cpu')
    for ep in eps:
        p.reset(); lab = D.load(LABELS/f'{ep}.npz'); tick = lab['tick']
        idx = json.loads((C.CACHE/ep/'index.json').read_text())
        ev_rows = [e for e in C.read_jsonl(C.MATCHES/ep/'events.jsonl') if e['accepted'] and e['kind'] != 'champion ability']
        t0 = time.perf_counter(); n = 0
        with (out/f'{ep}.jsonl').open('w') as f, (C.CACHE/ep/'raw.zst').open('rb') as raw:
            for k, b in enumerate(idx['blocks']):
                off, size = b['raw.zst']; raw.seek(off); rows = decompress(raw.read(size), (b['count'], int(np.prod(RAW))))
                for j in range(b['count']):
                    i = k*idx['block_size']+j
                    if i % stride:
                        continue
                    now = float(tick[i])*50.
                    pred = p.step(rows[j].reshape(RAW), now)
                    f.write(json.dumps(dict(episode=ep, seq=i, tick=float(tick[i]), pred=pred,
                                            truth=truth_record(lab, ev_rows, i, guard.cards, now)))+'\n'); n += 1
        print(json.dumps(dict(episode=ep, frames=n, ms_per_frame=round(1000*(time.perf_counter()-t0)/n, 1))), flush=True)
    (out/'README.md').write_text(f"""# Sample perception records (validation matches, renderer domain)

One JSON line per processed frame (every {stride}th frame, ~{20/stride:.0f} FPS): `pred` = LivePerception output
(`clasher.live.perception-frame.v1`, export `{export}`), `truth` = the same schema built from the dense labels.
Truth `events` lists events executed in the last 1.5 s; `pred.events` contains each event once, when it is emitted.
Coordinates: owner 0 = us, x from the screen left, y = 32 - native y (our king at (9, 3)); hp is a fraction of max.
Matches: {', '.join(eps)} (validation split; heldout never opened). Defaults: units >= 0.4, events >= 0.6.
""")


if __name__ == '__main__':
    main()
