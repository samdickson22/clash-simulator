"""Batch C1 focused native==Python lockstep cases (digest every tick), each on both seats (the red one is the
blue script mirrored: tile (x, y) -> (18 - x, 32 - y), sides swapped). Reuses batchA/tools/probe_native_scen.py.
Usage (PYTHONPATH = native : engine-rs : src : engine-speed : batchA tools): probe_c1_cases.py OUT.json [NAME ...]"""
import json, sys
import probe_native_scen as P

A, K = (3.5, 10.5), (3.5, 22.5)
BLUE = {
    # Bandit-family dash (stand ~58..72, travel ~73..79 against a Knight from K).
    'bandit_freeze_stand': [(0, 'Assassin', A, 0), (1, 'Knight', K, 0), (1, 'Freeze', (3.5, 14.0), 62)],
    'bandit_zap_stand': [(0, 'Assassin', A, 0), (1, 'Knight', K, 0), (1, 'Zap', (3.5, 14.0), 62)],
    'bandit_zap_travel': [(0, 'Assassin', A, 0), (1, 'Knight', K, 0), (1, 'Zap', (3.5, 15.5), 76)],
    'bandit_icespirit_50': [(0, 'BossBandit', A, 0), (1, 'Knight', K, 0), (1, 'IceSpirit', (3.5, 18.5), 50)],
    'bandit_icespirit_56': [(0, 'BossBandit', A, 0), (1, 'Knight', K, 0), (1, 'IceSpirit', (3.5, 18.5), 56)],
    'bandit_fisherman': [(0, 'Assassin', A, 0), (1, 'Fisherman', K, 0)],
    'bandit_log_stand': [(0, 'BossBandit', A, 0), (1, 'Knight', K, 0), (1, 'Log', (3.5, 17.5), 58)],
    'bandit_target_dies': [(0, 'Assassin', A, 0), (1, 'Skeletons', K, 0)],
    'bandit_water_end': [(0, 'Assassin', (8.5, 11.5), 0), (1, 'Cannon', (8.5, 17.5), 0)],
    'bandit_vs_inferno': [(0, 'BossBandit', A, 0), (1, 'InfernoTower', (3.5, 21.5), 0)],
    'bandit_vs_miner': [(0, 'Assassin', A, 0), (1, 'MightyMiner', K, 0)],
    # Mega Knight timed dash.
    'mk_zap_stand': [(0, 'MegaKnight', A, 0), (1, 'Knight', K, 0), (1, 'Zap', (3.5, 14.0), 66)],
    'mk_fisherman': [(0, 'MegaKnight', A, 0), (1, 'Fisherman', K, 0)],
    'mk_target_dies': [(0, 'MegaKnight', A, 0), (1, 'Skeletons', K, 0), (1, 'Arrows', (3.5, 18.0), 80)],
    'mk_vs_giant': [(0, 'MegaKnight', A, 0), (1, 'Giant', K, 0)],
    # Bowler straight boulder.
    'bowler_barbarians': [(0, 'Bowler', (3.5, 12.5), 0), (1, 'Barbarians', (3.5, 18.5), 0)],
    'bowler_offaxis': [(0, 'Bowler', (2.5, 12.5), 0), (1, 'Knight', (5.5, 18.5), 0), (1, 'Archers', (1.5, 20.5), 0)],
    # Sparky LoadFirstHit + recoil.
    'zap_machine_zapped': [(0, 'ZapMachine', A, 0), (1, 'Knight', K, 0), (1, 'Zap', (3.5, 13.0), 70)],
    'zap_machine_target_dies': [(0, 'ZapMachine', A, 0), (1, 'Skeletons', K, 0), (0, 'Arrows', (3.5, 17.5), 60)],
    'zap_machine_giant': [(0, 'ZapMachine', A, 0), (1, 'Giant', K, 0)],
    # Inferno Dragon overloaded clock.
    'inferno_dragon_skeletons': [(0, 'InfernoDragon', A, 0), (1, 'SkeletonArmy', K, 0)],
    'inferno_dragon_zap': [(0, 'InfernoDragon', A, 0), (1, 'Giant', K, 0), (1, 'Zap', (3.5, 14.0), 90)],
    # Electro Dragon hop wait / dead hop.
    'electro_dragon_army': [(0, 'ElectroDragon', A, 0), (1, 'SkeletonArmy', K, 0)],
    'electro_dragon_goblins': [(0, 'ElectroDragon', A, 0), (1, 'Goblins', K, 0), (1, 'Archers', (5.5, 20.5), 0)],
    # Electro/Ice Wizard play area at creation.
    'ewiz_close_at_birth': [(1, 'Knight', (3.5, 17.5), 0), (0, 'ElectroWizard', (3.5, 14.5), 30)],
    'iwiz_close_at_birth': [(1, 'Knight', (3.5, 17.5), 0), (0, 'IceWizard', (3.5, 14.5), 30)],
    'ewiz_clone': [(0, 'ElectroWizard', A, 0), (1, 'Knight', K, 0), (0, 'Clone', A, 30)],
    'ewiz_mirror': [(0, 'ElectroWizard', A, 0), (0, 'Mirror', (5.5, 10.5), 25), (1, 'Knight', K, 0)],
    # Fisherman current-target hook.
    'fisherman_giant': [(0, 'Fisherman', A, 0), (1, 'Giant', K, 0)],
    'fisherman_two': [(0, 'Fisherman', A, 0), (1, 'Knight', (3.5, 18.5), 0), (1, 'Musketeer', (5.5, 21.5), 0)],
    # Executioner axe.
    'axe_skeletons': [(0, 'AxeMan', A, 0), (1, 'SkeletonArmy', K, 0)],
    'axe_owner_dies': [(0, 'AxeMan', (3.5, 13.5), 0), (1, 'Knight', (3.5, 18.5), 0), (1, 'Rocket', (3.5, 13.5), 45)],
    # Ronin counter.
    'ronin_barbarians': [(0, 'Ronin', (3.5, 12.5), 0), (1, 'Barbarians', (3.5, 18.5), 0)],
    'ronin_minions': [(0, 'Ronin', (3.5, 12.5), 0), (1, 'Minions', (3.5, 18.5), 0)],
    'ronin_prince': [(0, 'Ronin', (3.5, 12.5), 0), (1, 'Prince', (3.5, 22.5), 0)],
    'ronin_ewiz': [(0, 'Ronin', (3.5, 12.5), 0), (1, 'ElectroWizard', (3.5, 18.5), 0)],
}


def red(seq):
    return [(1 - s, c, (18.0 - x, 32.0 - y), t) for s, c, (x, y), t in seq]


CASES = {}
for name, seq in BLUE.items():
    CASES[name] = (seq, 400)
    CASES[name + '_red'] = (red(seq), 400)
P.CASES.update(CASES)

if __name__ == '__main__':
    names = sys.argv[2:] or list(CASES)
    res = []
    for name in names:
        r = P.one(name, 'case', name); res.append(r)
        bad = [d for d in r.get('deploys', []) if not (d[3] and d[4])]
        print(name, r.get('native'), r.get('first_mismatch'), 'rejected' if bad else '', bad,
              (r.get('error') or '').strip().splitlines()[-1:], flush=True)
    json.dump(res, open(sys.argv[1], 'w'), indent=1)
