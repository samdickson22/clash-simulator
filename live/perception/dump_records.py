"""Per-frame perception dump over VALIDATION matches for offline tracker/bot replays (LIVE integration step).

Runs LivePerception (TorchScript export, CPU fp32, the live code path) on the prepared pixel cache of every
validation match (every `stride`-th frame, ~10 FPS at 2) and writes OUT/<episode>.jsonl.gz:
  line 0: {episode, split, frames, truth_events: [accepted card plays from events.jsonl]}
  then per processed frame: {seq, tick, ts, pred (frame_record with the default tracker's events),
                             truth (sample_records.truth_record), units_lo (units >= 0.25, record frame),
                             peaks [[side, x, y, existence, age_ms, probs[58]]] (EventTracker.peaks)}
Heldout is never listed or opened: episodes come from HeldoutGuard.episodes('validation') and every one is checked.

  python dump_records.py EXPORT_DIR OUT_DIR --shard K --nshards N [--stride 2] [--threads 4]
"""
import argparse
import gzip
import json
import os
import time
from pathlib import Path

import torch

import common as C
import dense_labels as D
from infer import LivePerception
from sample_records import LABELS, truth_record


def main():
    p = argparse.ArgumentParser(); p.add_argument('export'); p.add_argument('out', type=Path)
    p.add_argument('--shard', type=int, default=0); p.add_argument('--nshards', type=int, default=1)
    p.add_argument('--stride', type=int, default=2); p.add_argument('--threads', type=int, default=4)
    p.add_argument('--max-matches', type=int, default=0)
    a = p.parse_args(); torch.set_num_threads(a.threads); a.out.mkdir(parents=True, exist_ok=True)
    guard = C.HeldoutGuard(); eps = guard.episodes('validation')
    eps = eps[:a.max_matches] if a.max_matches else eps
    eps = eps[a.shard::a.nshards]; guard.check(eps)
    lp = LivePerception(a.export, device='cpu')
    for ep in eps:
        dst = a.out/f'{ep}.jsonl.gz'
        if dst.exists():
            continue
        guard.check([ep])
        rec = C.load_receipt(guard, ep, 'validation'); px = C.Pixels(guard, ep, rec)
        lab = D.load(LABELS/f'{ep}.npz'); tick = lab['tick']
        ev_rows = [e for e in C.read_jsonl(C.MATCHES/ep/'events.jsonl') if e['accepted'] and e['kind'] != 'champion ability']
        lp.reset(); t0 = time.perf_counter(); n = 0
        tmp = dst.with_suffix('.tmp')
        with gzip.open(tmp, 'wt') as f:
            f.write(json.dumps(dict(episode=ep, split='validation', frames=px.n, stride=a.stride,
                                    truth_events=[dict(card=e['card'], side=e['side'], tile=e['tile'], exec_tick=e['exec_tick'])
                                                  for e in ev_rows]))+'\n')
            for k in range((px.n+px.bs-1)//px.bs):
                arena, hud = px.block(k)
                for j in range(len(arena)):
                    i = k*px.bs+j
                    if i % a.stride:
                        continue
                    now = float(tick[i])*50.
                    pred = lp.step_prepared(arena[j], hud[j], now, unit_floor=.25)
                    pk = [[s, x, y, round(e, 4), round(age, 1), [round(float(v), 4) for v in probs]]
                          for s, x, y, e, probs, age in lp.last['peaks']]
                    f.write(json.dumps(dict(seq=i, tick=float(tick[i]), ts=now, pred=pred, units_lo=lp.last['units_lo'], peaks=pk,
                                            truth=truth_record(lab, ev_rows, i, guard.cards, now)))+'\n'); n += 1
        os.replace(tmp, dst)
        print(json.dumps(dict(episode=ep, frames=n, ms_per_frame=round(1000*(time.perf_counter()-t0)/max(1, n), 1))), flush=True)


if __name__ == '__main__':
    main()
