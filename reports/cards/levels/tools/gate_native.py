"""Gate 2 (planner side): native rollouts on the per-seat level config == the Python engine at the same levels,
for cards whose bodies come later (spawners, death spawns, spell spawns, Mirror's level+1 copy).

    (source env-fp.sh) python reports/cards/levels/tools/gate_native.py OUT.json

Per card: a level-11-tower start state with seat 0's cards at level A and seat 1's at level B; both seats play the
card (Mirror: Knight, then Mirror). Python (PlayerState card levels, the true game) and native
(clasher_core.BattleState on LevelConfigs.mixed + match.mirror_config, the planner's rollout config) step 700
ticks; digests compared every tick (first divergence reported); bodies (owner, name, max HP > 1, damage) every 10.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

CASES = [('Tombstone', 16, 11), ('Witch', 16, 11), ('Graveyard', 16, 11), ('Golem', 16, 11),
         ('SkeletonArmy', 11, 16), ('BattleRam', 16, 11), ('LavaHound', 16, 11), ('ElixirGolem', 16, 11),
         ('GoblinHut', 16, 11), ('Fireball', 16, 11), ('Earthquake', 16, 11), ('Mirror', 16, 16),
         ('Knight', 16, 16)]
POS = {0: (4.5, 10.5), 1: (13.5, 21.5)}
SPELL_POS = {0: (13.5, 21.5), 1: (4.5, 10.5)}


def bodies_py(b):
    return {(e.player_id, e.card_stats.name, round(float(e.max_hitpoints), 1), round(float(getattr(e, 'damage', 0) or 0), 1))
            for e in b.entities.values() if getattr(e, 'card_stats', None) is not None
            and e.card_stats.name not in ('Tower', 'KingTower') and float(getattr(e, 'max_hitpoints', 0) or 0) > 1}


def bodies_native(n):
    return {(e['owner'], e['stats']['name'], round(float(e['stats']['max_hp']), 1), round(float(e['stats']['damage']), 1))
            for e in json.loads(n.snapshot())['entities'] if e['stats']['name'] not in ('Tower', 'KingTower', '')
            and float(e['stats']['max_hp']) > 1}


def main():
    out_path = Path(sys.argv[1])
    from bot.players.runtime import Runtime
    rt = Runtime()
    R = rt.R
    import clasher_core
    from clasher.arena import Position
    from differential import initial, snapshot, battle_digest
    from bot.levels.match import install_engine_levels, level_configs, mirror_config
    install_engine_levels()
    lc = level_configs(rt)
    out = {}
    for card, la, lb in CASES:
        if card not in R.config['cards']:
            out[card] = 'not in runtime'
            continue
        cards = ('Knight', 'Mirror', 'Archers', 'Giant') if card == 'Mirror' else \
            (card, 'Knight', 'Archers', 'Giant') if card != 'Knight' else ('Knight', 'Archers', 'Giant', 'Musketeer')
        levels = (la, lb)
        cfg, report = lc.mixed(lambda s, c: levels[s])
        if card == 'Mirror':
            cfg, bad = mirror_config(lc, cfg, la + 1)
            report['mirror_unsupported'] = bad
        b = initial(cards=cards)
        for s in (0, 1):
            b.players[s].set_card_levels({c: levels[s] for c in cards})
            b.players[s].elixir = 10.
        n = clasher_core.BattleState(snapshot(b, cfg))
        spellcard = str(getattr(R.builder.loader.get_card(card), 'card_type', '') or '').lower() == 'spell'
        plays = [('Knight', POS), ('Mirror', POS)] if card == 'Mirror' else [(card, SPELL_POS if spellcard else POS)]
        row = dict(levels=levels, report={k: v for k, v in report.items() if k != 'direct'}, accepted=[])
        seen_py, seen_nat, first_div = set(), set(), None
        for name, where in plays:
            for s in (0, 1):
                x, y = where[s]
                pa = b.deploy_card(s, name, Position(x, y))
                ra = n.apply_action(s, name, x, y)
                row['accepted'].append([name, s, bool(pa), bool(ra)])
            for _ in range(5):
                b.step(); n.step()
        for t in range(700):
            b.step(); n.step()
            if t % 10 == 0:
                seen_py |= bodies_py(b)
                seen_nat |= bodies_native(n)
            if first_div is None and battle_digest(b) != n.digest():
                first_div = b.tick
        lv = {}
        for e in b.entities.values():
            cs = getattr(e, 'card_stats', None)
            if cs is not None:
                lv.setdefault(f'{e.player_id}:{cs.name}', getattr(cs, 'level', None))
        row.update(first_digest_divergence=first_div, bodies_equal=seen_py == seen_nat,
                   only_python=sorted(map(list, seen_py - seen_nat))[:12],
                   only_native=sorted(map(list, seen_nat - seen_py))[:12],
                   python_levels_at_end=lv, n_bodies=len(seen_py))
        out[card] = row
        print(card, levels, 'digest div', first_div, 'bodies equal', seen_py == seen_nat, row['accepted'], flush=True)
    out_path.write_text(json.dumps(out, indent=1, default=str))


if __name__ == '__main__':
    main()
