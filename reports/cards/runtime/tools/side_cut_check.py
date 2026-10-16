"""Value parity of the side-table fc cut (bot/cards/fc_cut.py) on saved roots, under the selected pins.

    python side_cut_check.py OUT.json ROOTS.jsonl.gz [...]      (roots: decision_timing/noncore --save-roots, or
                                                                  record_roots dirs given as DIR/)
Per root, three payloads of the same state: full (head + json.dumps(R.config) + tail), cards (lopp_fast's
ConfigCache cut as shipped today) and side (fc_cut). With R.native: rollout_e1 for WAIT, timed WAIT and up to 4
legal plays x 3 styles (frozen no-deadline budget), select_action x 3 (+ digest), apply_discrete + step 40, and step
1/49/150 digests. Equal iff every value matches (float.hex). Also reports the config bytes of each payload.
"""
import gzip
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
STYLES = ('balanced', 'pressure', 'defense')


def load(paths):
    for p in paths:
        p = Path(p)
        files = sorted(p.glob('roots-*.jsonl.gz')) if p.is_dir() else [p]
        for f in files:
            for n, line in enumerate(gzip.open(f, 'rt')):
                if p.is_dir() and n % 4:           # recorded C56 games: every 4th root (~260 of 1,043)
                    continue
                r = json.loads(line)
                if 'snapshot' in r:
                    yield r['deck'], r['seat'], r['snapshot'], None
                else:
                    yield f'rec{r["index"]}', r['seat'], None, (r['head'], r['tail'])


def values(native, root, seat, k, args):
    mask = list(native.public_mask(root, seat))
    legal = [i for i in range(2304) if mask[i]]
    plays = sorted(random.Random(k).sample(legal, min(4, len(legal))))
    out = dict(rollout=[float(native.rollout_e1(root, seat, a, s, args['command_delay'], args['opponent_delay'],
                                                args['horizon'], args['interval'], args['elixir_weight'], 1e6)).hex()
                        for a in [2304, 2401] + plays for s in STYLES])
    sel = []
    for s in STYLES:
        c = root.clone()
        sel.append([int(native.select_action(c, seat, s)), str(c.digest())])
    out['select'] = sel
    if plays:
        c = root.clone()
        ok = native.apply_discrete(c, seat, plays[0])
        c.step(40)
        out['apply'] = [repr(ok), str(c.digest())]
    c = root.clone()
    out['step'] = []
    for n in (1, 49, 150):
        c.step(n)
        out['step'].append(str(c.digest()))
    out['digest'] = str(root.digest())
    return out


def main():
    from bot.players.runtime import Runtime
    rt = Runtime()
    import clasher_core
    from bot.live.native_parity import rollout_args
    from bot.search import lopp_fast as lf
    from bot.cards import fc_cut
    R, args = rt.R, rollout_args(rt.R)
    text = json.dumps(R.config)
    fc_cut.install()                                 # idempotent (the r1-cards1 pins install it already)
    side = lf.ConfigCache(text)
    plain = lf.ConfigCache(text)
    plain.__dict__.pop('side')                       # -> fc_cut falls back to lopp_fast's cards-only cut
    res = dict(scope=getattr(R, 'card_scope', 'c56'), roots=0, identical=0, differing=[], bytes={})
    sizes = {'full': [], 'cards': [], 'side': []}
    for k, (deck, seat, snap, ht) in enumerate(load(sys.argv[2:])):
        head, tail = (lf.split_snapshot(snap)[0], lf.split_snapshot(snap)[2]) if snap else ht
        pays = dict(full=head + text + tail, cards=plain.payload(head, tail), side=side.payload(head, tail))
        vals = {}
        for name, pay in pays.items():
            sizes[name].append(len(pay) - len(head) - len(tail))
            vals[name] = values(R.native, clasher_core.BattleState(pay), seat, k, args)
        res['roots'] += 1
        if vals['full'] == vals['cards'] == vals['side']:
            res['identical'] += 1
        elif len(res['differing']) < 10:
            res['differing'].append(dict(k=k, deck=deck, cards_eq_full=vals['cards'] == vals['full'],
                                         side_eq_full=vals['side'] == vals['full']))
        res.setdefault('by_deck', {}).setdefault(deck, 0)
        res['by_deck'][deck] += 1
    res['bytes'] = {n: dict(median=sorted(v)[len(v) // 2], max=max(v)) for n, v in sizes.items() if v}
    Path(sys.argv[1]).write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
