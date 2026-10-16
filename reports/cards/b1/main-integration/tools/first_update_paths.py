"""Native-vs-Python lockstep for every path that can create a first-update unit mid-phase (Batch A review r2).

A first-update unit is a death spawn of a spawner building (Tombstone, BarbarianHut, GoblinDrill) or a periodic
emission. Each case kills such a building through one effect (a spell, a projectile, melee, a tower shot, a death
bomb or death damage, a champion ability) and compares battle_digest every tick. Both seats: the red-seat variant
mirrors every tile (x, y) -> (18 - x, 32 - y) and swaps the sides.

Setup (Python only, before the shared snapshot is exported): deploys, steps, HP and position overrides, so that the
intended effect is the one that kills the building. The victim's death tick is recorded from Python.
Usage (PYTHONPATH = native : engine-rs : src : engine-speed): probe_first_update_paths.py OUT.json [CASE ...]
"""
import json, sys, traceback
from differential import config, initial, snapshot, battle_digest, clasher_core, Position

FILL = ('Knight', 'Archers', 'Giant', 'Musketeer')
T = (4.5, 10.5)  # the victim building's tile (blue)
TOMB = [('deploy', 0, 'Tombstone', T), ('step', 25)]


def spell(card, hp, tile=T, end=200, victim='Tombstone', pre=TOMB):
    return dict(setup=pre + [('hp', 0, victim, hp)], script=[(1, 1, card, tile)], end=end, victim=(0, victim))


def attacker(card, at, attacker_hp=None, hp=40, end=300):
    setup = [('deploy', 0, 'Tombstone', T), ('deploy', 1, card, (4.5, 17.5)), ('step', 25), ('move', 1, card, at),
             ('hp', 0, 'Tombstone', hp)]
    if attacker_hp is not None:
        setup.append(('hp', 1, card, attacker_hp))
    return dict(setup=setup, script=[], end=end, victim=(0, 'Tombstone'))


CASES = {
    # direct spells (attacker = side 1), HP sized so the spell, not lifetime decay, kills (control run checks it)
    'zap': spell('Zap', 100),
    'fireball': spell('Fireball', 300),
    'arrows': spell('Arrows', 60),
    'rocket': spell('Rocket', 500, end=300),
    'lightning': spell('Lightning', 500, end=300),
    'log': spell('Log', 60, tile=(4.5, 18.5)),
    'snowball': spell('Snowball', 100),
    'earthquake': spell('Earthquake', 60, end=300),
    'poison': spell('Poison', 40, end=300),
    'freeze': spell('Freeze', 20),
    'tornado': spell('Tornado', 30, end=300),
    'goblin_curse': spell('GoblinCurse', 30, end=300),
    'fireball_hut': spell('Fireball', 300, victim='BarbarianHut', pre=[('deploy', 0, 'BarbarianHut', T), ('step', 25)]),
    # projectile impacts and melee: the attacker is deployed at the bridge, then moved next to the Tombstone
    'musketeer_projectile': attacker('Musketeer', (4.5, 15.5), hp=200, end=400),
    'bomber_splash': attacker('Bomber', (4.5, 14.5)),
    'knight_melee': attacker('Knight', (4.5, 12.0), hp=200, end=400),
    # tower shot: a red GoblinDrill surfaces in range of the blue princess tower
    'tower_shot_drill': dict(setup=[('deploy', 1, 'GoblinDrill', (4.5, 9.5)), ('step', 60), ('hp', 1, 'GoblinDrill', 150)],
                             script=[], end=300, victim=(1, 'GoblinDrill')),
    # death-effect chains: a death bomb (Balloon shot down by the princess tower) and death damage (Ice Golem hit by
    # a Skeleton) kill the Tombstone
    'balloon_death_bomb': attacker('Balloon', (4.5, 10.8), attacker_hp=1, hp=40),
    'golem_death_damage': attacker('Golem', (4.5, 12.4), attacker_hp=1, hp=40),
    # champion ability: Mighty Miner's lane switch drops its bomb on the Tombstone
    'mighty_miner_ability': dict(attacker('MightyMiner', (4.5, 11.6), hp=150), script=[(5, 1, 'ABILITY', None)]),
    # review r1 case (a frozen Tombstone dies)
    'frozen_tombstone_death': dict(setup=[], script=[(0, 0, 'Tombstone', T), (40, 1, 'Freeze', T), (41, 1, 'Rocket', T)],
                                   end=400, victim=(0, 'Tombstone')),
}


def mirror(case):
    m = lambda t: None if t is None else (18 - t[0], 32 - t[1])
    out = dict(case)
    out['setup'] = [(op[0], 1 - op[1], op[2], m(op[3])) if op[0] in ('deploy', 'move') else
                    (op[0], 1 - op[1], op[2], op[3]) if op[0] == 'hp' else op for op in case['setup']]
    out['script'] = [(t, 1 - s, c, m(tile)) for t, s, c, tile in case['script']]
    out['victim'] = (1 - case['victim'][0], case['victim'][1])
    return out


def find(b, side, name):
    return [e for e in b.entities.values() if getattr(e, 'player_id', None) == side and e.is_alive
            and getattr(e.card_stats, 'name', '') == name]


def one(name, case, control=False):
    out = dict(case=name)
    try:
        need = {0: [], 1: []}
        for op in case['setup']:
            if op[0] == 'deploy':
                need[op[1]].append(op[2])
        for _, s, c, _ in case['script']:
            if c != 'ABILITY':
                need[s].append(c)
        names = list(dict.fromkeys(need[0] + need[1] + list(FILL)))
        cards = tuple(names[:8])
        cfg = config(cards)
        b = initial(7, cards=cards)
        for side in (0, 1):
            mine = list(dict.fromkeys(need[side]))
            p = b.players[side]
            p.elixir = 10.0
            p.hand = (mine + [c for c in cards if c not in mine])[:4]
            p.cycle_queue.clear(); p.cycle_queue.extend(c for c in cards if c not in p.hand)
        for op in case['setup']:
            if op[0] == 'deploy':
                assert b.deploy_card(op[1], op[2], Position(*op[3])), op
                b.players[op[1]].elixir = 10.0
            elif op[0] == 'step':
                for _ in range(op[1]):
                    b.step()
            elif op[0] == 'hp':
                for e in find(b, op[1], op[2]):
                    e.hitpoints = float(op[3])
            elif op[0] == 'move':
                for e in find(b, op[1], op[2]):
                    e.position = Position(*op[3])
        if case.get('disable_towers'):
            for e in b.entities.values():
                if getattr(e.card_stats, 'name', '') in ('Tower', 'PrincessTower', 'KingTower'):
                    e.damage = 0
        for p in b.players:
            p.elixir = 10.0
        victims = find(b, *case['victim'])
        last_hp = [None]
        native = None if control else clasher_core.BattleState(snapshot(b, cfg))
        out['actions'], out['first_mismatch'], out['victim_death'] = [], None, None
        bytick = {}
        for t, s, c, tile in case['script']:
            bytick.setdefault(t, []).append((s, c, tile))
        for t in range(case['end']):
            if control:
                last_hp[0] = sum(v.hitpoints for v in victims if v.is_alive)
                b.step()
                if out['victim_death'] is None and victims and not any(v.is_alive for v in victims):
                    out['victim_death'] = t
                    out['hp_before_death'] = round(last_hp[0], 2)
                continue
            last_hp[0] = sum(v.hitpoints for v in victims if v.is_alive)
            for s, c, tile in bytick.get(t, []):
                if c == 'ABILITY':
                    pa, ra = bool(b.activate_champion_ability(s)), bool(native.activate_champion_ability(s))
                else:
                    pa = bool(b.deploy_card(s, c, Position(*tile)))
                    ra = bool(native.apply_action(s, c, *tile))
                out['actions'].append([t, s, c, pa, ra])
                if pa != ra and out['first_mismatch'] is None:
                    out['first_mismatch'] = f'action@{t}'
            if not victims:
                victims = find(b, *case['victim'])
            b.step(); native.step(1)
            if out['victim_death'] is None and victims and not any(v.is_alive for v in victims):
                out['victim_death'] = t
                out['hp_before_death'] = round(last_hp[0], 2)
            if out['first_mismatch'] is None and native.digest() != battle_digest(b):
                out['first_mismatch'] = t
                break
        out['native'] = 'ok'
        out['final_digest'] = None if control else str(battle_digest(b))
    except BaseException as e:
        out['native'] = 'error'
        out['error'] = (type(e).__name__ + ': ' + traceback.format_exc(limit=5))[-900:]
    return out


if __name__ == '__main__':
    names = sys.argv[2:] or list(CASES)
    res = []
    for n in names:
        for seat, case in (('blue', CASES[n]), ('red', mirror(CASES[n]))):
            r = one(f'{n}/{seat}', case)
            # Control (Python only): no scripted action and no attacker, so the victim only decays.
            vs = case['victim'][0]
            ctl = dict(case, script=[], setup=[op for op in case['setup']
                                               if not (op[0] in ('deploy', 'move', 'hp') and op[1] != vs)])
            r['control_death'] = one(f'{n}/{seat}', ctl, control=True).get('victim_death')
            res.append(r)
            print(r['case'], r['native'], 'mismatch', r.get('first_mismatch'), 'victim_death', r.get('victim_death'),
                  'blow', r.get('hp_before_death'), 'control', r['control_death'],
                  [a for a in r.get('actions', []) if not (a[3] and a[4])], (r.get('error') or '').strip().splitlines()[-1:],
                  flush=True)
    json.dump(res, open(sys.argv[1], 'w'), indent=1)
