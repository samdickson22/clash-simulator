"""Summarize one drive.py run dir: battle span/FPS, stage latencies, plays (accepted per the HUD), tap acks, errors.

  python report_run.py RUN_DIR [--json]
"""
import collections
import json
import sys
from pathlib import Path

import numpy as np


def load(p):
    return [json.loads(l) for l in open(p)] if Path(p).exists() else []


def pct(v):
    return [round(float(x), 1) for x in np.percentile(v, [50, 95, 99])] if v else None


def summarize(d):
    d = Path(d)
    F, D, T, E = (load(d/f'{k}.jsonl') for k in ('frames', 'decisions', 'taps', 'events'))
    S = json.loads((d/'session.json').read_text()) if (d/'session.json').exists() else {}
    B = [f for f in F if f.get('perc_ms') is not None]
    span = (B[-1]['ts_ms'] - B[0]['ts_ms'])/1e3 if len(B) > 1 else 0
    plays = [x for x in D if x.get('submitted')]
    acks = [t['write_to_ack_ms'] for t in T if t.get('write_to_ack_ms') is not None]
    tr = S.get('tr_stats', {})
    return dict(
        run=d.name, state=S.get('state'), battle_frames=len(B), battle_s=round(span, 1),
        fps=round(len(B)/span, 1) if span else None,
        latency_ms={k: pct([f[k] for f in B if f.get(k) is not None]) for k in ('cap_ms', 'canvas_ms', 'perc_ms', 'step_ms')},
        frame_to_tap_ms=pct([x['frame_to_tap_ms'] for x in plays if 'frame_to_tap_ms' in x]),
        tap_ack_ms=pct(acks), polls=len(D), plays=len(plays),
        plays_confirmed_by_hud=tr.get('own_play_confirmed_by_hud', 0),
        cards=dict(collections.Counter(x.get('card') for x in plays)),
        sources=dict(collections.Counter((x.get('stats') or {}).get('source') for x in D)),
        step_errors=dict(collections.Counter((f.get('err') or '')[:80] for f in B if f.get('err'))),
        elixir_floored=sum(1 for f in B if 'elixir_floored' in f),
        units_per_frame=pct([f['n_units'] for f in B]),
        events=[e.get('ev') for e in E], writer_dropped=S.get('writer_dropped'), capture_restarts=S.get('restarts'),
        play_list=[(round(x['tick']), x.get('card'), x.get('target_xy'), (x.get('stats') or {}).get('source')) for x in plays])


if __name__ == '__main__':
    s = summarize(sys.argv[1])
    print(json.dumps(s, indent=None if '--json' in sys.argv else 1, default=str))
