"""Gate 3 diagnostic: full-pool K4L at level 16 searched on exact level roots (not a silent fallback).

    (source env-fp.sh) python reports/cards/levels/tools/gate3_diag.py OUT.json [CASES] [CANDIDATE] [OPPONENT]

Plays LIVE-AB1 cases (default 0,1) at max_levels() with play_match directly and records per game: level-root
counters (roots built, bodies, leveled bodies, towers), bot.search.lopp FAILURES (native failures), decisions with
rollouts, the result's level block, and any exception.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))


def main():
    out_path = Path(sys.argv[1])
    cases = [int(x) for x in (sys.argv[2] if len(sys.argv) > 2 else '0,1').split(',')]
    cand = sys.argv[3] if len(sys.argv) > 3 else 'K4L-R-gs-mk1a1'
    opp = sys.argv[4] if len(sys.argv) > 4 else 'R3a'
    from bot.players.runtime import Runtime
    from bot.fullpool.models import install_from_env
    from bot.fullpool.banks import BANKS, case as make_case, select
    rt = Runtime()
    install_from_env(rt)
    bank = BANKS['LIVE-AB1']
    select(rt, bank['decks'], None)
    from bot.eval.headline import make_player
    from bot.levels.match import max_levels
    from bot.players.ours import play_match
    from bot.search.lopp import FAILURES
    games = []
    for i in cases:
        c = make_case(rt, i, bank['base'], bank['decks'])
        player = make_player(rt, cand)
        decisions = []
        act = player.act

        def logged(view, act=act):
            d = act(view)
            if d.stats is not None:
                decisions.append(dict(tick=view.tick, rollouts=d.stats.get('rollouts'),
                                      native_failure=d.stats.get('native_failure')))
            return d
        player.act = logged
        players = {c['seat']: player, 1 - c['seat']: make_player(rt, opp)}
        before = Counter(FAILURES)
        t = time.time()
        row = dict(index=i, seat=c['seat'], decks=c['decks'])
        try:
            res = play_match(rt, players, seed=c['seed'], decks=c['decks'], levels=max_levels())
            row.update(winner=res['winner'], terminal=res['terminal'], ticks=res['ticks'], towers=res['towers'],
                       command_sha256=res['command_sha256'], levels=res['levels'])
        except Exception as ex:
            row.update(error=repr(ex)[:500], traceback=traceback.format_exc()[-2000:])
        root = getattr(player, 'level_root', None)
        row.update(wall=time.time() - t, level_root=getattr(root, 'stats', None),
                   root_config_report=None if root is None else {s: {k: v for k, v in rep.items() if k != 'direct'}
                                                                 for s, (_, _, rep) in root._cfg.items()},
                   failures=dict(Counter(FAILURES) - before), decisions=len(decisions),
                   decisions_with_rollouts=sum(1 for d in decisions if (d['rollouts'] or 0) > 0),
                   native_failures=sum(1 for d in decisions if d['native_failure']))
        games.append(row)
        print(json.dumps({k: v for k, v in row.items() if k not in ('decks', 'traceback')})[:1500], flush=True)
    out_path.write_text(json.dumps(dict(candidate=cand, opponent=opp, games=games), indent=1, default=str))


if __name__ == '__main__':
    main()
