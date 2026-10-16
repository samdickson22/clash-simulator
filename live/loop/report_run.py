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
        step_errors=dict(collections.Counter((f.get('err') or '')[:80] for f in F if f.get('err'))),
        elixir_floored=sum(1 for f in B if 'elixir_floored' in f),
        units_per_frame=pct([f['n_units'] for f in B]),
        events=[e.get('ev') for e in E], writer_dropped=S.get('writer_dropped'), capture_restarts=S.get('restarts'),
        play_list=[(round(x['tick']), x.get('card'), x.get('target_xy'), (x.get('stats') or {}).get('source')) for x in plays],
        **guards(B, plays, tr, E))


def full_elixir_max_s(B, level=9.5):
    """Longest stretch (s) of battle frames with elixir >= level (a stalled bot sits at full elixir)."""
    best, start = 0., None
    for f in B:
        if (f.get('elixir') or 0) >= level:
            start = f['ts_ms'] if start is None else start
            best = max(best, (f['ts_ms'] - start)/1e3)
        else:
            start = None
    return round(best, 1)


# LIVE LEAD rollback triggers for handsync + autonav (10-16): any of these -> roll back (see HANDOFF / babysitter steps)
TRIGGERS = dict(tap_guard_rate=.10, full_elixir_s=8., fps=7.0, step_p95_ms=45.)


def guards(B, plays, tr, E):
    """handsync / autonav health + the rollback flags."""
    tg = {k.split(':', 1)[1]: v for k, v in tr.items() if k.startswith('tap_guard:')}
    refused = sum(tg.values())
    rate = refused/(len(plays) + refused) if plays or refused else 0.
    span = (B[-1]['ts_ms'] - B[0]['ts_ms'])/1e3 if len(B) > 1 else 0
    fps = len(B)/span if span else None
    steps = [f['step_ms'] for f in B if f.get('step_ms') is not None]
    p95 = float(np.percentile(steps, 95)) if steps else None
    full = full_elixir_max_s(B)
    nav = collections.Counter(e.get('screen') for e in E if e.get('ev') == 'nav_tap')
    flags = []
    if rate > TRIGGERS['tap_guard_rate']:
        flags.append(f'tap_guard refusals {refused}/{len(plays) + refused} = {rate:.0%} > 10%')
    if full > TRIGGERS['full_elixir_s']:
        flags.append(f'elixir >= 9.5 for {full} s > 8 s')
    if any(e.get('ev') == 'nav_stuck' and e.get('n', 0) > 0 for e in E):
        flags.append('nav_stuck')
    if fps is not None and fps < TRIGGERS['fps']:
        flags.append(f'FPS {fps:.1f} < 7.0')
    if p95 is not None and p95 > TRIGGERS['step_p95_ms']:
        flags.append(f'step p95 {p95:.1f} ms > 45')
    if any(e.get('ev') == 'step_error' for e in E):
        flags.append('step_error (driver/reader)')
    if any(e.get('ev') == 'handsync_hold' for e in E):
        flags.append('handsync_hold')
    return dict(tap_guard=dict(tg, refused=refused, rate=round(rate, 3)),
                handsync={k: v for k, v in tr.items() if k.startswith(('own_sync:', 'opening_hand_waits', 'submit_refused', 'handsync_hold:'))},
                full_elixir_max_s=full, nav_taps=dict(nav), nav_stuck=sum(e.get('ev') == 'nav_stuck' for e in E),
                rollback_flags=flags)


if __name__ == '__main__':
    s = summarize(sys.argv[1])
    print(json.dumps(s, indent=None if '--json' in sys.argv else 1, default=str))
