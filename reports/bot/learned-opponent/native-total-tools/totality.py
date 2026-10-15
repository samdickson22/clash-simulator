"""Totality probe: on-board entities / pending casts whose card is absent from the state's config (or the
scripts' metadata). One native per process (CLASHER_DELAY_NATIVE_DIR via bot Runtime).

    CLASHER_DELAY_NATIVE_DIR=<dir> python totality.py --roots DIR --out OUT.json

Base state: the first recorded real root of game 0 (roots-000), seat 0 hand[0] := card, elixir 10. The card is
played with apply_action, the state is advanced t ticks (t in CUTS; t=0 = cast still pending), then the
listed config entries are deleted from the snapshot's config and the state is rebuilt. Probes on the cut state
(each caught separately, BaseException so PanicException counts): step(400); rollout_e1 WAIT x 3 styles for both
seats; public_view / public_mask / evaluate / select_action(3 styles) for both seats. Scenario `meta-*` instead
keeps the config and drops the card from the NativeScripts metadata (cards + bodies).
"""
import argparse
import copy
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, '/mpac/sdicks02/repos/clasher-bot')
STYLES = ('balanced', 'pressure', 'defense')
CUTS = [0, 1, 2, 3, 5, 8, 12, 16, 20, 25, 30, 40, 50, 60, 75, 90, 110, 130, 160, 200, 250, 300]
# name, card, (x, y) for seat 0, config entries removed: [(map, key)], ability activation tick or None
SCEN = [
    ('electro-spirit', 'ElectroSpirit', (3.5, 14.5), [('cards', 'ElectroSpirit')], None),
    ('poison-area', 'Poison', (3.5, 25.5), [('cards', 'Poison')], None),
    ('lightning-strike', 'Lightning', (3.5, 25.5), [('cards', 'Lightning')], None),
    ('goblin-barrel-delivery', 'GoblinBarrel', (3.5, 25.5), [('cards', 'GoblinBarrel')], None),
    ('royal-delivery', 'RoyalDelivery', (3.5, 12.5), [('cards', 'RoyalDelivery')], None),
    ('log-rolling', 'Log', (3.5, 14.5), [('cards', 'Log')], None),
    ('barblog-rolling', 'BarbLog', (3.5, 14.5), [('cards', 'BarbLog')], None),
    ('fireball-projectile', 'Fireball', (3.5, 25.5), [('cards', 'Fireball')], None),
    ('rocket-projectile', 'Rocket', (3.5, 25.5), [('cards', 'Rocket')], None),
    ('arrows', 'Arrows', (3.5, 25.5), [('cards', 'Arrows')], None),
    ('zap', 'Zap', (3.5, 25.5), [('cards', 'Zap')], None),
    ('tornado', 'Tornado', (3.5, 20.5), [('cards', 'Tornado')], None),
    ('earthquake', 'Earthquake', (3.5, 25.5), [('cards', 'Earthquake')], None),
    ('firespirit-hut-production', 'FirespiritHut', (4.5, 10.5),
     [('cards', 'FirespiritHut'), ('production_children', 'FirespiritHut')], None),
    ('goblin-hut-production', 'GoblinHut', (4.5, 10.5),
     [('cards', 'GoblinHut'), ('production_children', 'GoblinHut')], None),
    ('mighty-miner-bomb', 'MightyMiner', (3.5, 12.5),
     [('cards', 'MightyMiner'), ('ability_bombs', 'MightyMiner')], 20),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--roots', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--scrub', action='store_true', help='also replace the cut card in hands/cycles by Skeletons')
    a = ap.parse_args()
    from bot.players.runtime import Runtime
    rt = Runtime(verify=False)
    import clasher_core
    from bot.live.native_parity import rollout_args
    R, args = rt.R, rollout_args(rt.R)
    d = Path(a.roots)
    with gzip.open(d / 'roots-000.jsonl.gz', 'rt') as fh:
        r0 = json.loads(fh.readline())
    cfg_text = (d / f"config-{r0['config'][:16]}.json").read_text()
    base = json.loads(r0['head'] + cfg_text + r0['tail'])

    def probes(state, native):
        res = {}

        def run(name, f):
            try:
                f()
                res[name] = 'ok'
            except BaseException as ex:  # PanicException is a BaseException
                res[name] = f'{type(ex).__name__}: {str(ex)[:120]}'

        def stepper():
            c = state.clone(); c.step(400)
        run('step400', stepper)
        for s in (0, 1):
            for st in STYLES:
                run(f'rollout_e1[{s},{st}]', lambda s=s, st=st: native.rollout_e1(
                    state, s, 2304, st, args['command_delay'], args['opponent_delay'], args['horizon'],
                    args['interval'], args['elixir_weight'], 1e6))
            run(f'public_view[{s}]', lambda s=s: native.public_view(state.clone(), s))
            run(f'public_mask[{s}]', lambda s=s: native.public_mask(state.clone(), s))
            run(f'evaluate[{s}]', lambda s=s: native.evaluate(state, s, args['elixir_weight']))
            for st in STYLES:
                run(f'select_action[{s},{st}]', lambda s=s, st=st: native.select_action(state.clone(), s, st))
        return res

    report = dict(native=clasher_core.__file__, scenarios={})
    for name, card, (x, y), removed, ability in SCEN:
        snap = copy.deepcopy(base)
        snap['players'][0]['hand'][0] = card
        snap['players'][0]['elixir'] = 10.0
        st = clasher_core.BattleState(json.dumps(snap))
        played = st.apply_action(0, card, x, y)
        rows = {}
        t, activated = 0, False
        for cut in CUTS:
            while t < cut:
                if ability is not None and t >= ability and not activated and st.can_activate_champion_ability(0):
                    activated = bool(st.activate_champion_ability(0)) or True
                st.step(1); t += 1
            s = json.loads(st.snapshot())
            for m, k in removed:
                s['config'][m].pop(k, None)
            if a.scrub:  # the real crash: card on board only (cut config keeps hand+cycle cards)
                for p in s['players']:
                    p['hand'] = [c if c != card else 'Skeletons' for c in p['hand']]
                    p['cycle'] = [c if c != card else 'Skeletons' for c in p['cycle']]
                    if p.get('last_card') == card:
                        p['last_card'] = 'Skeletons'
            try:
                cut_state = clasher_core.BattleState(json.dumps(s))
            except BaseException as ex:
                rows[cut] = {'build': f'{type(ex).__name__}: {str(ex)[:120]}'}
                continue
            rows[cut] = probes(cut_state, R.native)
        fails = {c: {k: v for k, v in p.items() if v != 'ok'} for c, p in rows.items()}
        fails = {c: v for c, v in fails.items() if v}
        report['scenarios'][name] = dict(played=bool(played), ability_activated=activated if ability is not None else None, cuts=len(rows),
                                         probes=sum(len(p) for p in rows.values()),
                                         failing_cuts=len(fails), failures=fails)
        print(name, played, 'failing cuts', len(fails), flush=True)
    # metadata-cut NativeScripts: ElectroSpirit on board and in hand, absent from metadata cards+bodies
    meta = copy.deepcopy(R.meta)
    for key in ('cards', 'bodies'):
        meta[key].pop('ElectroSpirit', None)
    cut_native = type(R.native)(json.dumps(meta))
    snap = copy.deepcopy(base)
    snap['players'][0]['hand'][0] = 'ElectroSpirit'
    snap['players'][0]['elixir'] = 10.0
    st = clasher_core.BattleState(json.dumps(snap))
    played = st.apply_action(0, 'ElectroSpirit', 3.5, 14.5)
    snap = json.loads(st.snapshot())
    snap['players'][0]['hand'][1] = 'ElectroSpirit'
    st = clasher_core.BattleState(json.dumps(snap))
    st.step(2)
    rows = {0: probes(st, cut_native)}
    fails = {c: {k: v for k, v in p.items() if v != 'ok'} for c, p in rows.items()}
    fails = {c: v for c, v in fails.items() if v}
    report['scenarios']['meta-electro-spirit'] = dict(played=bool(played), cuts=1,
                                                      probes=sum(len(p) for p in rows.values()),
                                                      failing_cuts=len(fails), failures=fails)
    print('meta-electro-spirit', played, 'failing cuts', len(fails), flush=True)
    Path(a.out).write_text(json.dumps(report, indent=1, sort_keys=True))


if __name__ == '__main__':
    main()
