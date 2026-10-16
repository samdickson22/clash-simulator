"""Live A/B readout, -res vs base (pre-registered in reports/bot/live-diag/RESULTS.md §7; bot lead live-diag).

    python3 -m bot.livediag.ab_live RUNS_DIR --from 52 [--json OUT]

Arm = session-config.json `player` (never inferred): base LIVE-K4L-R-gs-rw-fc-w200-t4-p4, treatment ...-res. Battles:
session number >= --from, e16 deck, >= 100 logged decisions; everything else is listed as excluded with a reason.
Primary per arm (handsync_cmp.battle per battle): elixir at Giant cross, undefended Giant-push share, reaction (births
proxy; per-battle median, mean over battles), plays per battle, Giant and Fireball plays per battle; treatment - base
with a bootstrap 95% CI over battles. Secondary: win rate where session.json/events carry a result.
Stratified (RESULTS §7a): stratum = perception version from session-config units_source ('v9a' / 'e16' / other);
per-stratum rows plus a pooled delta = battle-weighted mean of stratum deltas, bootstrap resampling battles within
each stratum (4000 draws, seed 0).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from bot.livediag.handsync_cmp import battle, boot_diff, mean
from bot.livediag.live_metrics import CARDS, analyse, jl

ARMS = {'LIVE-K4L-R-gs-rw-fc-w200-t4-p4': 'base', 'LIVE-K4L-R-gs-rw-fc-w200-t4-p4-res': 'res'}


def arm_of(player, phase):
    """(phase, arm) from the session-config player name (RESULTS §7b): phase 'fullpool' if the name carries mk1a1,
    else 'c56'; arm 'res' if a -res token is present, else 'base'. None for other players."""
    if not player or not player.startswith('LIVE-K4L-R-gs-rw-fc-w200-t4-p4'):
        return None
    toks = player.split('-')
    ph = 'fullpool' if any(t.startswith('mk1a1') for t in toks) else 'c56'
    if ph != phase:
        return None
    if any(t not in ('LIVE', 'K4L', 'R', 'gs', 'rw', 'fc', 'w200', 't4', 'p4', 'res') and not t.startswith('mk1a1')
           for t in toks):
        return None
    return 'res' if 'res' in toks else 'base'


RESULTS_MD = Path('/mpac/sdicks02/repos/clasher-live/reports/live/loop/RESULTS.md')   # babysitter-verified W/L
_RES = None


def result(d):
    """'W' / 'L' / 'D' for battle dir sNN-mNN from the LIVE LEAD's results table (read in place), else None."""
    global _RES
    if _RES is None:
        _RES = {}
        if RESULTS_MD.exists():
            for line in RESULTS_MD.read_text().splitlines():
                cells = [c.strip() for c in line.strip().strip('|').split('|')]
                if len(cells) > 1 and re.fullmatch(r's\d+[a-z]?-m\d+', cells[0]):
                    r = cells[1].replace('*', '').strip()
                    if r[:1] in 'WLD':
                        _RES[cells[0]] = r[:1]
    return _RES.get(d.name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('runs', type=Path)
    ap.add_argument('--from', dest='first', type=int, default=52)
    ap.add_argument('--json')
    ap.add_argument('--phase', default='c56', choices=['c56', 'fullpool'], help='RESULTS §7b: never pooled')
    a = ap.parse_args()
    arms, excluded = {'base': [], 'res': []}, []
    for d in sorted(a.runs.iterdir()):
        m = re.match(r's(\d+)', d.name)
        if not m or int(m[1]) < a.first:
            continue
        try:
            cfg = json.loads((d / 'session-config.json').read_text())
        except Exception as ex:
            excluded.append((d.name, f'no session-config ({ex!r})'[:80])); continue
        arm = arm_of(cfg.get('player'), a.phase)
        us = cfg.get('units_source')
        spec = (us.get('spec') if isinstance(us, dict) else us) or cfg.get('export') or ''
        stratum = next((v for v in ('v11b', 'v9a', 'e16') if v in spec), 'other')
        if arm is None:
            excluded.append((d.name, f"player {cfg.get('player')}")); continue
        if sorted(cfg.get('deck') or []) != sorted(CARDS):
            excluded.append((d.name, 'deck')); continue
        if not (d / 'decisions.jsonl').exists() or sum(1 for _ in open(d / 'decisions.jsonl')) < 100:
            excluded.append((d.name, '< 100 decisions')); continue
        b = battle(d)
        m2 = analyse(jl(d / 'perception.jsonl'), jl(d / 'decisions.jsonl'), dict(sid=d.name))
        b.update(giant=m2['plays'].get('Giant', 0), fireball=m2['plays'].get('Fireball', 0), result=result(d),
                 stratum=stratum)
        arms[arm].append(b)
    metrics = {
        'elixir_at_giant_cross': lambda bs: mean([e for x in bs for e in x['elixir_cross']]),
        'undefended_share': lambda bs: sum(x['nodef'] for x in bs) / max(1, sum(x['pushes'] for x in bs)),
        'reaction_s': lambda bs: mean([sorted(x['react'])[len(x['react']) // 2] for x in bs if x['react']]),
        'reaction_p90_s': lambda bs: mean([sorted(x['react'])[int(.9 * len(x['react']))] for x in bs if x['react']]),
        'plays_per_battle': lambda bs: mean([x['plays'] for x in bs]),
        'giant_per_battle': lambda bs: mean([x['giant'] for x in bs]),
        'fireball_per_battle': lambda bs: mean([x['fireball'] for x in bs]),
    }
    out = dict(phase=a.phase, giant_pushes={k: sum(x['pushes'] for x in v) for k, v in arms.items()}, battles={k: len(v) for k, v in arms.items()}, sessions={k: sorted({x['sid'].split('-')[0] for x in v})
                                                                        for k, v in arms.items()},
               excluded=excluded, metrics={})
    for name, f in metrics.items():
        row = {k: round(f(v), 3) if v else None for k, v in arms.items()}
        if arms['base'] and arms['res'] and len(arms['base']) > 1 and len(arms['res']) > 1:
            row['res_minus_base'] = boot_diff(arms['base'], arms['res'], f)
        out['metrics'][name] = row
    import random
    strata = sorted({x['stratum'] for v in arms.values() for x in v})
    out['strata'] = {}
    for st in strata:
        sub = {k: [x for x in v if x['stratum'] == st] for k, v in arms.items()}
        out['strata'][st] = dict(battles={k: len(v) for k, v in sub.items()}, metrics={})
        for name, f in metrics.items():
            row = {k: round(f(v), 3) if v else None for k, v in sub.items()}
            if len(sub['base']) > 1 and len(sub['res']) > 1:
                row['res_minus_base'] = boot_diff(sub['base'], sub['res'], f)
            out['strata'][st]['metrics'][name] = row
    usable = [st for st in strata if all(len([x for x in arms[k] if x['stratum'] == st]) > 1 for k in arms)]
    if usable:
        rng = random.Random(0)
        w = {st: sum(1 for v in arms.values() for x in v if x['stratum'] == st) for st in usable}
        out['pooled_blocked'] = {}
        for name, f in metrics.items():
            def est(pick):
                tot = 0.
                for st in usable:
                    b0 = pick([x for x in arms['base'] if x['stratum'] == st])
                    b1 = pick([x for x in arms['res'] if x['stratum'] == st])
                    tot += w[st] * (f(b1) - f(b0))
                return tot / sum(w.values())
            pt = est(lambda v: v)
            draws = sorted(est(lambda v: [rng.choice(v) for _ in v]) for _ in range(4000))
            out['pooled_blocked'][name] = dict(delta=round(pt, 3), ci=[round(draws[100], 3), round(draws[3900], 3)],
                                               strata=usable)
    out['results'] = {k: [x['result'] for x in v] for k, v in arms.items()}
    win = lambda bs: mean([1. if x['result'] == 'W' else (0.5 if x['result'] == 'D' else 0.)
                          for x in bs if x['result'] is not None])
    out['win_rate'] = {k: dict(n=sum(1 for x in v if x['result']), rate=round(win(v), 3) if any(x['result'] for x in v)
                               else None) for k, v in arms.items()}
    for st in out['strata']:
        sub = {k: [x for x in v if x['stratum'] == st and x['result']] for k, v in arms.items()}
        out['strata'][st]['win_rate'] = {k: dict(n=len(v), rate=round(win(v), 3) if v else None) for k, v in sub.items()}
        if len(sub['base']) > 1 and len(sub['res']) > 1:
            out['strata'][st]['win_rate']['res_minus_base'] = boot_diff(sub['base'], sub['res'], win)
    text = json.dumps(out, indent=1, default=str)
    if a.json:
        Path(a.json).write_text(text + '\n')
    print(text)


if __name__ == '__main__':
    main()
