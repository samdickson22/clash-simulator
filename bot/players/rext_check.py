"""Check that RextPolicyPlayer's view of OUR match battle equals RoyaleGym's own engine state.

Two battles from one setup (X4S decks, level 11, 15.535.29 arms, shuffle 0, 6 elixir, delay 0):
  A: our match battle (royalesim_vocab.rsim_battle, slot_of_k [[0,1,2],[0,1,2]]) read through
     rext_policy.SlotRemapBattle inside a RoyaleGym RustEngine, as the player reads it;
  B: a plain RoyaleGym RustEngine reset with the same MatchSetup.
Both are driven by the same random legal plays; every 10 ticks the decoded BattleStates and the
SpatialObsBuilder observations + masks for both seats must be identical.

    bot/players/run.sh -m bot.players.rext_check --ticks 3000 --seeds 3
"""
from __future__ import annotations

import argparse
import json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ticks', type=int, default=3000)
    ap.add_argument('--seeds', type=int, default=3)
    a = ap.parse_args()
    import numpy as np
    from .rext_policy import SlotRemapBattle, _vendor
    from .rext_envs import X4S_DECKS
    from .royalesim_vocab import rsim_battle
    _vendor()
    from royalegym import MatchSetup, RustEngine, SpatialObsBuilder, TileActionParser
    from royalegym.rust_engine import client_overrides
    report = []
    for seed in range(a.seeds):
        rng = np.random.default_rng(seed)
        decks_names = [X4S_DECKS[seed % 5], X4S_DECKS[(seed + 2) % 5]]
        ours = rsim_battle('15.535.29')
        cat = json.loads(ours.catalogue_json())
        ids = {row[0]: i for i, row in enumerate(cat)}
        decks = [[ids[c] for c in d] for d in decks_names]
        ours.set_command_delay_ticks(0, 0)
        ours.reset(seed=seed, decks=decks, shuffle=0, start_tick=0, elixir_milli=[6000, 6000], tower_hp=None, spawns=[])
        ea = RustEngine(calibration_overrides=client_overrides('15.535.29'))
        ea._battle = SlotRemapBattle(ours, ea.slot_of_k)
        ea._reset_called = True
        ea._setup_cards = [(list(d), [0]*8) for d in decks]
        eb = RustEngine(calibration_overrides=client_overrides('15.535.29'))
        eb.reset(seed, MatchSetup(decks=decks, shuffle=0, elixir_milli=[6000, 6000],
                                  levels=[[11]*8, [11]*8], tower_levels=[11, 11]))
        sides = []
        for e in (ea, eb):
            parser = TileActionParser(); parser.bind(e)
            builder = SpatialObsBuilder(); builder.bind(e, parser); builder.command_delay = (0, 0)
            builder.reset(e.state())
            sides.append((e, parser, builder))
        checks = mismatch = plays = 0
        first_bad = None
        for tick in range(0, a.ticks, 10):
            obs = []
            for e, parser, builder in sides:
                st = e.state()
                per = []
                for team in (0, 1):
                    mask = parser.action_mask(st, team)
                    per.append((mask, builder.build(st, team, mask)))
                obs.append((st, per))
            (sa, pa), (sb, pb) = obs
            checks += 1
            same = sa == sb and all(
                np.array_equal(pa[t][0], pb[t][0]) and all(np.array_equal(pa[t][1][k], pb[t][1][k]) for k in pa[t][1])
                for t in (0, 1))
            if not same:
                mismatch += 1
                first_bad = first_bad or tick
            cmds = []
            for team in (0, 1):
                legal = np.flatnonzero(pa[team][0][1:]) + 1
                if len(legal) and rng.random() < 0.3:
                    cmds.append(sides[0][1].parse(int(rng.choice(legal)), sa, team))
            plays += len(cmds)
            for e, parser, _ in sides:
                e.step(cmds, 10)
            if sides[0][0].state().game_over:
                break
        report.append(dict(seed=seed, decks=decks_names, checks=checks, mismatches=mismatch, first_bad_tick=first_bad,
                           plays=plays, end_tick=sides[0][0].state().tick,
                           state_hash_equal=int(ours.state_hash()) == eb.state_hash()))
        print(json.dumps(report[-1]), flush=True)
    assert all(r['mismatches'] == 0 for r in report), 'views differ'
    print('OK: identical BattleState, masks and observations for both seats at every check')


if __name__ == '__main__':
    main()
