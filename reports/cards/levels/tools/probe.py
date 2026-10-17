"""Exploratory probe of the levels path on one runtime (prints a JSON summary).

    CLASHER_BOT_RUNTIME=<root> CLASHER_BOT_RUNTIME_PINS=<pins> python -m reports.cards.levels.tools.probe [--exports]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exports', default='', help='comma levels to build/check in the LevelConfigs cache, e.g. 16,17')
    a = ap.parse_args()
    from bot.players.runtime import Runtime
    rt = Runtime()
    R = rt.R
    from bot.levels.configs import base_cards
    from bot.levels.match import level_battle, max_levels, resolve
    from bot.levels.root import tower_stat
    cards = base_cards(R.config)
    out = dict(cards=len(cards), mirror='Mirror' in cards,
               level12=sum(k.startswith('level12:') for k in R.config['cards']))
    deck = ['Knight', 'Archers', 'Giant', 'Musketeer', 'Fireball', 'Arrows', 'Minions', 'Valkyrie']
    spec = resolve(max_levels(), [deck, deck])
    b = level_battle(5, [deck, deck], R.builder.loader, spec)
    towers = sorted((e.player_id, e.card_stats.name, float(e.max_hitpoints), float(e.damage))
                    for e in b.entities.values() if e.card_stats.name in ('Tower', 'KingTower'))
    out['towers16'] = towers
    out['towers16_curve'] = {n: (tower_stat(n, 'max_hp', 16), tower_stat(n, 'damage', 16)) for n in ('KingTower', 'Tower')}
    out['player_hp16'] = [[float(getattr(b.players[s], k)) for k in ('king_tower_hp', 'left_tower_hp', 'right_tower_hp')]
                          for s in (0, 1)]
    # Packet invariance at the first poll (towers full): level 11 vs level 16.
    from fair_player import observe
    from stage2_matches import battle
    b11 = battle(dict(seed=5, decks=[deck, deck]), R.builder.loader)
    import numpy as np
    for bb in (b, b11):
        while bb.tick < 90:
            bb.step()
    diffs = {}
    for seat in (0, 1):
        o16, o11 = observe(b, R.builder, seat, []).packet.observation, observe(b11, R.builder, seat, []).packet.observation
        for f in ('entity_ids', 'entity_features', 'global_features', 'hand_ids', 'entity_mask'):
            x, y = np.asarray(getattr(o16, f)), np.asarray(getattr(o11, f))
            if x.shape != y.shape or not np.array_equal(x, y):
                idx = np.argwhere(x != y)[:6].tolist() if x.shape == y.shape else 'shape'
                diffs[f'{seat}.{f}'] = idx
    out['packet_diff_tick90'] = diffs
    # Python deploys at level 16, every card, seat 0 (accepted? hp/damage vs level 11).
    from clasher.arena import Position
    from differential import initial
    from clasher.stat_scaling import level_multiplier
    deploy = {}
    for card in cards:
        res = {}
        for level in (11, 16):
            try:
                bb = initial(cards=(card, 'Knight', 'Archers', 'Giant'))
                bb.players[0].set_card_levels({card: level})
                bb.players[0].elixir = 10.
                before = set(bb.entities)
                ok = bb.deploy_card(0, card, Position(9.5 if card in ('Cannon',) else 4.5, 10.5))
                for _ in range(40):
                    bb.step()
                new = [bb.entities[i] for i in sorted(set(bb.entities) - before) if bb.entities[i].player_id == 0]
                res[level] = dict(ok=bool(ok), bodies=[(e.card_stats.name, float(e.max_hitpoints),
                                                        float(getattr(e, 'damage', 0) or 0),
                                                        getattr(e.card_stats, 'level', None)) for e in new[:6]])
            except Exception as ex:
                res[level] = dict(error=repr(ex)[:200])
        deploy[card] = res
    out['deploy'] = deploy
    out['deploy_failed16'] = sorted(c for c, r in deploy.items() if not r[16].get('ok'))
    out['ratio16'] = level_multiplier(16) / level_multiplier(11)
    if a.exports:
        from bot.levels.match import level_configs
        lc = level_configs(rt)
        out['cache'] = str(lc.dir)
        t = time.process_time()
        good, bad = lc.check11()
        out['supported11'] = len(good)
        out['unsupported11'] = bad
        for level in map(int, a.exports.split(',')):
            d = lc.load(level)
            out[f'export{level}_errors'] = d['errors']
        out['export_cpu'] = time.process_time() - t
    print(json.dumps(out, indent=1, default=str))


if __name__ == '__main__':
    main()
