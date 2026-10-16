"""Mirror under the fc cut (fc_cut.mirror_need): cut vs uncut give identical decisions when Mirror is in hand.

    CLASHER_BOT_RUNTIME=<root> CLASHER_BOT_RUNTIME_PINS=r1-cards1 python mirror_probe.py OUT.json ROOTS.jsonl.gz...

For saved real roots (decision_timing/noncore --save-roots), seat s's hand slot 0 becomes Mirror (the card it
replaces goes to the end of the cycle), with last_card set to hand slot 1 ('last') or unset ('none'; Mirror becomes
playable once a rollout plays a card), and elixir 10. Three payloads of each state: full (whole R.config), side (the
installed fc cut, with mirror_need) and nomirror (the same cut without mirror_need: the reviewed bug). With R.native,
for seat s: public_mask of the Mirror slot, rollout_e1 for WAIT and up to 4 legal Mirror tiles x 3 styles,
select_action x 3 (+ digest), apply_discrete of the first Mirror tile + step 40, and step 1/49/150 digests.
side must equal full everywhere. nomirror is expected to differ where Mirror matters.
"""
import gzip
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
STYLES = ('balanced', 'pressure', 'defense')


def main():
    from bot.players.runtime import Runtime
    rt = Runtime()
    import clasher_core
    from bot.live.native_parity import rollout_args
    from bot.search import lopp_fast as lf
    from bot.cards import fc_cut
    R, args = rt.R, rollout_args(rt.R)
    assert getattr(lf, '_side_cut_installed', False), 'run under pins with fc_side_cut (r1-cards1)'
    text = json.dumps(R.config)
    side = lf.ConfigCache(text)
    nomirror = lf.ConfigCache(text)
    real = fc_cut.mirror_need
    dec = json.JSONDecoder()
    out = dict(states=0, side_eq_full=0, nomirror_eq_full=0, level12_in_side=0, level12_in_nomirror=0,
               mirror_legal_states=0, differing_side=[], examples_nomirror=[])
    n = 0
    for path in sys.argv[2:]:
        for line in gzip.open(path, 'rt'):
            n += 1
            if n % 2:
                continue
            r = json.loads(line)
            head, _, tail = lf.split_snapshot(r['snapshot'])
            i = head.index('"players":') + 10
            players, j = dec.raw_decode(head, i)
            for s in (0, 1):
                for mode in ('last', 'none'):
                    ps = json.loads(json.dumps(players))
                    p = ps[s]
                    if 'Mirror' in p['hand'] + p['cycle'] or None in p['hand'][:2]:
                        continue
                    replaced = p['hand'][0]
                    p['hand'][0] = 'Mirror'
                    p['cycle'] = p['cycle'] + [replaced]
                    p['elixir'] = 10.0
                    if mode == 'last':
                        p['last_card'] = p['hand'][1]
                        p['last_cost'] = float(R.costs[p['hand'][1]])
                    h = head[:i] + json.dumps(ps, separators=(',', ':')) + head[j:]
                    full = h + text + tail
                    pay_side = side.payload(h, tail)
                    fc_cut.mirror_need = lambda cards, players, available: cards
                    try:
                        pay_nom = nomirror.payload(h, tail)
                    finally:
                        fc_cut.mirror_need = real
                    vals = {}
                    for name, pay in (('full', full), ('side', pay_side), ('nomirror', pay_nom)):
                        root = clasher_core.BattleState(pay)
                        mask = list(R.native.public_mask(root, s))
                        legal = [a for a in range(576) if mask[a]]
                        tiles = sorted(random.Random(n * 7 + s).sample(legal, min(4, len(legal))))
                        v = dict(legal=len(legal),
                                 rollout=[float(R.native.rollout_e1(root, s, a, st, args['command_delay'],
                                                                    args['opponent_delay'], args['horizon'],
                                                                    args['interval'], args['elixir_weight'], 1e6)).hex()
                                          for a in [2304] + tiles for st in STYLES])
                        sel = []
                        for st in STYLES:
                            c = root.clone()
                            sel.append([int(R.native.select_action(c, s, st)), str(c.digest())])
                        v['select'] = sel
                        if tiles:
                            c = root.clone()
                            ok = R.native.apply_discrete(c, s, tiles[0])
                            c.step(40)
                            v['apply'] = [repr(ok), str(c.digest())]
                        c = root.clone()
                        v['step'] = []
                        for k in (1, 49, 150):
                            c.step(k)
                            v['step'].append(str(c.digest()))
                        vals[name] = (v, tiles)
                    # compare on the same tiles (the full root's legal set)
                    out['states'] += 1
                    out['mirror_legal_states'] += vals['full'][0]['legal'] > 0
                    out['level12_in_side'] += 'level12:' in pay_side[len(h):len(pay_side) - len(tail)]
                    out['level12_in_nomirror'] += 'level12:' in pay_nom[len(h):len(pay_nom) - len(tail)]
                    if vals['side'] == vals['full']:
                        out['side_eq_full'] += 1
                    elif len(out['differing_side']) < 5:
                        out['differing_side'].append(dict(n=n, seat=s, mode=mode))
                    if vals['nomirror'] == vals['full']:
                        out['nomirror_eq_full'] += 1
                    elif len(out['examples_nomirror']) < 3:
                        out['examples_nomirror'].append(dict(n=n, seat=s, mode=mode,
                                                             legal_full=vals['full'][0]['legal'],
                                                             legal_nomirror=vals['nomirror'][0]['legal']))
            if out['states'] >= 80:
                break
        if out['states'] >= 80:
            break
    Path(sys.argv[1]).write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
