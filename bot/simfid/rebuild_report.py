"""Aggregate bot.simfid.rebuild result files into JSON and the markdown tables of reports/bot/simfid-20261020/
REBUILD.md.

    python -m bot.simfid.rebuild_report RUN_DIR [--json OUT.json] [--md OUT.md]
RUN_DIR/results/<sample>/<engine>/<config>.jsonl (one line per match). Pure Python; no engine import.
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

# Oct 4 native-client pass on the same 50 matches (reports/strategy_council_20260928/native-corpus/PROGRESS.md).
OCT4 = {
    'native baseline (arbitrary order, L-mode)': dict(n=50, winner=28, crowns=16, six_hp=1, hp_mae=1459.66, complete=1,
                                                     injected=2299, card_unavailable=301, ability_unavailable=22,
                                                     pending=1150),
    'native first-use order': dict(n=50, winner=40, crowns=37, six_hp=2, hp_mae=663.06, complete=26, card_unavailable=13,
                                   ability_unavailable=4, pending=411),
    'native first-use order + real levels': dict(n=50, winner=41, crowns=39, six_hp=2, hp_mae=622.78, complete=28,
                                                 injected=3356, card_unavailable=13, ability_unavailable=3, pending=400),
}
CARD_UNAVAILABLE = ('not_in_hand', 'refill_pending')
PLAY_REJECT = CARD_UNAVAILABLE + ('elixir', 'placement', 'mirror_unresolvable', 'unresolvable', 'engine_error')
ABILITY = ('ability_unavailable', 'ability_ambiguous', 'ability_unsupported_form', 'ability_unsupported_engine',
           'ability_unattributed')


def load(path):
    return [json.loads(line) for line in Path(path).open() if line.strip()]


def _q(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else None


def summarize(rows):
    st = Counter(r['status'] for r in rows)
    ran = [r for r in rows if r.get('score')]
    cmd = Counter()
    for r in ran:
        cmd.update(r['commands'])
    tiers = Counter(r['classify']['tier'] for r in rows if 'classify' in r)
    cls = [r['classify'] for r in rows if 'classify' in r]

    def has(r, keys):
        return any(r['commands'].get(k, 0) for k in keys)

    errs = [e for r in ran for e in r['score']['hp_abs_err']]
    out = dict(
        n=len(rows), status=dict(st), ran=len(ran),
        tiers=dict(tiers),
        forms=dict(evo=sum(bool(c['evo_cards']) for c in cls), hero=sum(bool(c['hero_cards']) for c in cls),
                   tower_troop=sum(bool(c['tower_troops']) for c in cls),
                   approx=sum(bool(c['approx_cards']) for c in cls),
                   evo_played=sum(bool(c['flagged_plays'].get('evo')) for c in cls),
                   hero_played=sum(bool(c['flagged_plays'].get('hero')) for c in cls),
                   prefix_end_median=_q([c['faithful_prefix_end_tick'] for c in cls
                                         if c['faithful_prefix_end_tick'] is not None], .5),
                   prefix_zero=sum(c['faithful_prefix_end_tick'] == 0 for c in cls)),
        commands=dict(cmd),
        source_events=sum(r.get('events', 0) for r in ran),
        matches=dict(card_unavailable=sum(has(r, CARD_UNAVAILABLE) for r in ran),
                     elixir=sum(has(r, ('elixir',)) for r in ran), placement=sum(has(r, ('placement',)) for r in ran),
                     ability_any=sum(has(r, ABILITY) for r in ran),
                     ability_unsupported=sum(has(r, ('ability_unsupported_form', 'ability_unsupported_engine'))
                                             for r in ran),
                     pending=sum(r['commands'].get('pending_at_terminal', 0) > 0 for r in ran),
                     plays_complete=sum(not has(r, PLAY_REJECT) and not r['commands'].get('pending_at_terminal')
                                        for r in ran),
                     clean=sum(r['clean'] for r in ran),
                     engine_crash=st.get('engine-crash', 0)),
        winner=sum(r['score']['winner'] for r in ran), crowns=sum(r['score']['crowns'] for r in ran),
        six_hp=sum(r['score']['six_hp'] for r in ran),
        hp_mae=round(sum(errs) / len(errs), 2) if errs else None,
        wall_s=dict(mean=round(statistics.mean(r['wall_s'] for r in ran), 3) if ran else None,
                    median=_q([r['wall_s'] for r in ran], .5)),
        cpu_s=dict(mean=round(statistics.mean(r['cpu_s'] for r in ran), 3) if ran else None,
                   p95=_q([r['cpu_s'] for r in ran], .95)),
    )
    sides = [c for r in rows for c in (r.get('cycle') or [])]
    if sides:
        ns = [c['n'] for c in sides]
        out['cycle'] = dict(
            sides=len(sides), consistent=sum(n > 0 for n in ns),
            matches_both=sum(all(c['n'] > 0 for c in r['cycle']) for r in rows if r.get('cycle')),
            matches_with_cycle=sum(1 for r in rows if r.get('cycle')),
            unique=sum(n == 1 for n in ns),
            bins={b: sum(lo <= n <= hi for n in ns) for b, (lo, hi) in
                  {'0': (0, 0), '1': (1, 1), '2-8': (2, 8), '9-64': (9, 64), '65-256': (65, 256),
                   '257-1680': (257, 1680)}.items()},
            median=_q(ns, .5), hand_set_unique=sum(c.get('hand_sets') == 1 for c in sides),
            queue_fixed_mean=round(statistics.mean(c.get('queue_positions_fixed', 0) for c in sides if c['n']), 3))
    by_tier = {}
    for t in tiers:
        rr = [r for r in ran if r['classify']['tier'] == t]
        if rr:
            e = [x for r in rr for x in r['score']['hp_abs_err']]
            by_tier[t] = dict(ran=len(rr), winner=sum(r['score']['winner'] for r in rr),
                              crowns=sum(r['score']['crowns'] for r in rr),
                              six_hp=sum(r['score']['six_hp'] for r in rr), hp_mae=round(sum(e) / len(e), 2),
                              clean=sum(r['clean'] for r in rr))
    out['by_tier'] = by_tier
    clean = [r for r in ran if r['clean']]
    out['clean_outcomes'] = dict(n=len(clean), winner=sum(r['score']['winner'] for r in clean),
                                 crowns=sum(r['score']['crowns'] for r in clean))
    return out


def agreement(a_rows, b_rows):
    """Per-match engine winner/crowns agreement between two configs (diagnostic, e.g. candidate sensitivity)."""
    a = {r['key']: r for r in a_rows if r.get('engine')}
    b = {r['key']: r for r in b_rows if r.get('engine')}
    keys = sorted(set(a) & set(b))
    return dict(n=len(keys), same_winner=sum(a[k]['engine']['winner'] == b[k]['engine']['winner'] for k in keys),
                same_crowns=sum(a[k]['engine']['crowns'] == b[k]['engine']['crowns'] for k in keys),
                identical=sum(a[k]['engine'] == b[k]['engine'] and a[k]['commands'] == b[k]['commands'] for k in keys))


def collect(run_dir):
    res = {}
    for path in sorted(Path(run_dir, 'results').glob('*/*/*.jsonl')):
        sample, eng, cfg = path.parts[-3], path.parts[-2], path.stem
        res.setdefault(sample, {}).setdefault(eng, {})[cfg] = load(path)
    return res


def pct(a, n):
    return f'{a}/{n} ({100 * a / n:.1f}%)' if n else '-'


def markdown(summ, agree):
    lines = []
    for sample, engines in summ.items():
        lines.append(f'### {sample}\n')
        lines.append('| engine / config | ran | winner | crowns | six-HP | HP MAE | clean | plays complete | '
                     'card-unavail. | elixir | placement | ability (any) | pending events (matches) | CPU s/match |')
        lines.append('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
        for eng, cfgs in engines.items():
            for cfg, s in cfgs.items():
                c, m, n = s['commands'], s['matches'], s['ran']
                lines.append(
                    f"| {eng} / {cfg} | {n}/{s['n']} | {pct(s['winner'], n)} | {pct(s['crowns'], n)} | "
                    f"{s['six_hp']} | {s['hp_mae']} | {m['clean']} | {m['plays_complete']} | "
                    f"{sum(c.get(k, 0) for k in CARD_UNAVAILABLE)} ({m['card_unavailable']}) | "
                    f"{c.get('elixir', 0)} ({m['elixir']}) | {c.get('placement', 0)} ({m['placement']}) | "
                    f"{sum(c.get(k, 0) for k in ABILITY)} ({m['ability_any']}) | "
                    f"{c.get('pending_at_terminal', 0)} ({m['pending']}) | {s['cpu_s']['mean']} |")
        lines.append('')
    if agree:
        lines.append('| comparison | n | same engine winner | same crowns | identical terminal + receipts |')
        lines.append('|---|---|---|---|---|')
        for k, a in agree.items():
            lines.append(f"| {k} | {a['n']} | {a['same_winner']} | {a['same_crowns']} | {a['identical']} |")
    return '\n'.join(lines) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('run_dir')
    ap.add_argument('--json')
    ap.add_argument('--md')
    a = ap.parse_args(argv)
    res = collect(a.run_dir)
    summ = {s: {e: {c: summarize(rows) for c, rows in cfgs.items()} for e, cfgs in engs.items()}
            for s, engs in res.items()}
    agree = {}
    for s, engs in res.items():
        for e, cfgs in engs.items():
            if 'main' in cfgs:
                for other in ('lastcand', 'main-repeat'):
                    if other in cfgs:
                        agree[f'{s} {e}: main vs {other}'] = agreement(cfgs['main'], cfgs[other])
    out = dict(summary=summ, agreement=agree, oct4_native=OCT4)
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1, sort_keys=True) + '\n')
    md = markdown(summ, agree)
    if a.md:
        Path(a.md).write_text(md)
    print(md)


if __name__ == '__main__':
    main()
