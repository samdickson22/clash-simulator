"""Handsync off vs on: live reaction/defence metrics per battle (bot lead live-diag, exploration; read-only logs).

    python3 -m bot.livediag.handsync_cmp RUNS_DIR --off s41,s42,s43 --on s44,s45,s46 [--json OUT]

Per battle (session dir sNN-mMM):
  births     enemy plays, perception proxy: an enemy (owner 1) detection of class c with no enemy c detection within
             3 tiles in the previous 2 s of frames, present in >= 3 of the next 5 frames (flicker filter). The same
             rule on both arms, so the comparison is fair even though births are only a proxy for the translator's plays.
  reaction   birth -> our next submitted play (s); rich_waits = search WAIT decisions in between while perceived
             elixir >= the cheapest perceived hand card.
  guard      decisions with stats.tap_guard (handsync refusal) / (submitted plays + refusals); refusals within 2 s after
             a birth while an enemy troop is on our half (y < 16).
  plus live_metrics.analyse: plays per battle, Giant pushes undefended before contact, elixir at Giant cross,
  time to first play.
Battle-level means with a bootstrap 95% CI over battles (4000 draws, seed 0) for on - off.
"""
from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

from bot.livediag.live_metrics import analyse, jl

WAIT = 2304
COST = dict(Valkyrie=4, Archers=3, Minions=3, Cannon=3, Fireball=4, Giant=5, MiniPekka=4, Musketeer=4, Bats=2, Zap=2)


def births(perc):
    out, frames = [], [(p['tick'], [u for u in p['units'] if u.get('owner') == 1]) for p in perc]
    for i, (t, us) in enumerate(frames):
        for u in us:
            prev = [v for tt, vs in frames[max(0, i - 40):i] if t - tt <= 40 for v in vs
                    if v.get('cls') == u.get('cls') and abs(v['x'] - u['x']) <= 3 and abs(v['y'] - u['y']) <= 3]
            if prev:
                continue
            nxt = sum(1 for _, vs in frames[i + 1:i + 6]
                      if any(v.get('cls') == u.get('cls') and abs(v['x'] - u['x']) <= 3 and abs(v['y'] - u['y']) <= 3
                             for v in vs))
            if nxt >= 3 and not any(b[0] > t - 40 and b[1] == u.get('cls') and abs(b[2] - u['x']) <= 3 for b in out):
                out.append((t, u.get('cls'), u['x'], u['y']))
    return out


def battle(d: Path):
    perc, dec = jl(d / 'perception.jsonl'), jl(d / 'decisions.jsonl')
    m = analyse(perc, dec, dict(sid=d.name))
    pby = {p['n']: p for p in perc}
    plays = sorted(r['tick'] for r in dec if r.get('submitted'))
    b = births(perc)
    react, rich = [], []
    for t, cls, x, y in b:
        nxt = next((p for p in plays if p >= t), None)
        if nxt is None:
            continue
        react.append((nxt - t) / 20)
        k = 0
        for r in dec:
            s = r.get('stats') or {}
            if t <= r['tick'] < nxt and s.get('source') == 'search' and r['action'] >= WAIT and 'tap_guard' not in s:
                p = pby.get(r['n']) or {}
                hand = [c for c in (p.get('hand') or {}).get('cards') or [] if c in COST]
                if hand and (p.get('elixir') or 0) >= min(COST[c] for c in hand):
                    k += 1
        rich.append(k)
    guards = [r for r in dec if (r.get('stats') or {}).get('tap_guard')]
    near = 0
    for r in guards:
        p = pby.get(r['n']) or {}
        on_half = any(u.get('owner') == 1 and u['y'] < 16 for u in p.get('units', ()))
        if on_half and any(0 <= r['tick'] - t <= 40 for t, *_ in b):
            near += 1
    pu = m['giant_pushes']
    return dict(sid=d.name, births=len(b), react=react, rich=rich, plays=sum(m['plays'].values()),
                first_play_s=plays[0] / 20 if plays else None,
                guard=len(guards), attempts=len(guards) + len(plays), guard_near_threat=near,
                guard_reasons={k: sum(1 for r in guards if r['stats']['tap_guard'] == k)
                               for k in {r['stats']['tap_guard'] for r in guards}},
                pushes=len(pu), nodef=sum(p['no_def_before_contact'] for p in pu),
                elixir_cross=[p['elixir_cross'] for p in pu if p['elixir_cross'] is not None])


def mean(v):
    return sum(v) / len(v) if v else float('nan')


def boot_diff(a, b, f, draws=4000, seed=0):
    rng = random.Random(seed)
    pt = f(b) - f(a)
    d = sorted(f([rng.choice(b) for _ in b]) - f([rng.choice(a) for _ in a]) for _ in range(draws))
    return round(pt, 3), [round(d[int(.025 * draws)], 3), round(d[int(.975 * draws)], 3)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('runs', type=Path)
    ap.add_argument('--off', required=True)
    ap.add_argument('--on', required=True)
    ap.add_argument('--json')
    a = ap.parse_args()
    pick = lambda pre: sorted(p for p in a.runs.iterdir() if re.match(r's\d+', p.name)
                              and p.name.split('-')[0] in pre.split(',') and (p / 'decisions.jsonl').exists()
                              and (p / 'decisions.jsonl').stat().st_size > 0)
    arms = {k: [battle(d) for d in pick(v)] for k, v in (('off', a.off), ('on', a.on))}
    metrics = {
        'reaction_median_s': lambda bs: mean([sorted(x['react'])[len(x['react']) // 2] for x in bs if x['react']]),
        'reaction_mean_s': lambda bs: mean([mean(x['react']) for x in bs if x['react']]),
        'rich_waits_per_birth': lambda bs: mean([mean(x['rich']) for x in bs if x['rich']]),
        'plays_per_battle': lambda bs: mean([x['plays'] for x in bs]),
        'first_play_s': lambda bs: mean([x['first_play_s'] for x in bs if x['first_play_s'] is not None]),
        'nodef_share': lambda bs: sum(x['nodef'] for x in bs) / max(1, sum(x['pushes'] for x in bs)),
        'elixir_at_giant_cross': lambda bs: mean([e for x in bs for e in x['elixir_cross']]),
        'guard_share_of_attempts': lambda bs: sum(x['guard'] for x in bs) / max(1, sum(x['attempts'] for x in bs)),
    }
    out = dict(battles={k: len(v) for k, v in arms.items()},
               pushes={k: sum(x['pushes'] for x in v) for k, v in arms.items()},
               guards={k: dict(refusals=sum(x['guard'] for x in v), attempts=sum(x['attempts'] for x in v),
                               near_threat=sum(x['guard_near_threat'] for x in v)) for k, v in arms.items()},
               metrics={})
    for name, f in metrics.items():
        out['metrics'][name] = dict(off=round(f(arms['off']), 3), on=round(f(arms['on']), 3),
                                    on_minus_off=boot_diff(arms['off'], arms['on'], f))
    out['per_battle'] = {k: [{kk: vv for kk, vv in x.items() if kk not in ('react', 'rich', 'elixir_cross')}
                             for x in v] for k, v in arms.items()}
    text = json.dumps(out, indent=1)
    if a.json:
        Path(a.json).write_text(text + '\n')
    print(text)


if __name__ == '__main__':
    main()
