"""Reproduce/profile exact-level planning on LIVE-AB1 without changing its commands.

Source bot/fullpool/run/env.sh; run under cpu_job on 04/08. --ticks 6001 = terminal games.
Profiles only the first and fourth eligible decisions (cold/warm); timings are inclusive.
"""
from __future__ import annotations

import argparse
import cProfile
import functools
import json
import os
from pathlib import Path
import pstats
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--levels', choices=['none', 'max'], default='none')
    ap.add_argument('--cases', default='0,1,2')
    ap.add_argument('--ticks', type=int, default=601)
    ap.add_argument('--profile', action='store_true')
    ap.add_argument('--config-cache', type=Path)
    ap.add_argument('--candidate', default='K4L-R-gs-mk1a1')
    ap.add_argument('--reload-configs', action='store_true', help='fresh disk loader before every case')
    a = ap.parse_args()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    if a.config_cache is not None:
        os.environ['CLASHER_LEVELS_CACHE'] = str(a.config_cache)
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    from bot.fullpool.models import install_from_env
    from bot.fullpool.banks import BANKS, case, select
    from bot.eval.headline import make_player
    from bot.levels.match import max_levels
    from bot.players.ours import play_match
    from bot.search.lopp import FAILURES
    from bot.levels import configs as level_module
    exports, builds = [], []
    original_export, original_build = level_module._export, level_module.LevelConfigs.build

    def exported(card, level):
        t = time.perf_counter()
        try:
            return original_export(card, level)
        finally:
            exports.append(dict(card=card, level=level, seconds=time.perf_counter()-t))
            if len(exports) % 25 == 0:
                print(f'exported {len(exports)} card/levels; last {card} L{level}', flush=True)

    def built(self, level, *args, **kwargs):
        t = time.perf_counter()
        result = original_build(self, level, *args, **kwargs)
        row = dict(level=level, seconds=time.perf_counter()-t, cards=len(result['cards']),
                   errors=result['errors'])
        builds.append(row)
        print('built ' + json.dumps(row), flush=True)
        return result

    level_module._export, level_module.LevelConfigs.build = exported, built
    startup = time.perf_counter()
    rt = Runtime()
    install_from_env(rt)
    bank = BANKS['LIVE-AB1']
    select(rt, bank['decks'], None)
    print(f'runtime ready after {time.perf_counter()-startup:.3f}s', flush=True)
    for sequence, i in enumerate(map(int, a.cases.split(','))):
        if a.reload_configs:
            rt.__dict__.pop('_match_level_configs', None)
        export_start, build_start = len(exports), len(builds)
        c = case(rt, i, bank['base'], bank['decks'])
        player = make_player(rt, a.candidate)
        phases, decisions, profiles = {}, [], []

        def wrap(obj, name, key):
            orig = getattr(obj, name)
            @functools.wraps(orig)
            def timed(*args, **kwargs):
                t = time.perf_counter()
                try:
                    return orig(*args, **kwargs)
                finally:
                    row = phases.setdefault(key, dict(calls=0, seconds=0.))
                    row['calls'] += 1
                    row['seconds'] += time.perf_counter() - t
            setattr(obj, name, timed)

        start = player.start
        def started(ctx):
            start(ctx)
            if a.profile:
                if player.root_fn is None:
                    player.root_fn = rt.R.root
                wrap(player, 'root_fn', 'root_inclusive')
                wrap(player.p.core, 'score_candidates', 'search_inclusive')
        player.start = started
        act = player.act
        eligible = 0
        def logged(view):
            nonlocal eligible
            profile = None
            if view.can_act and view.tick % 10 == 0:
                eligible += 1
                if a.profile and eligible in (1, 4):
                    profile = cProfile.Profile()
                    profile.enable()
            t = time.perf_counter()
            d = act(view)
            wall = time.perf_counter() - t
            if profile is not None:
                profile.disable()
                path = a.out.with_name(f'{a.out.stem}-case{i}-decision{eligible}.prof')
                profile.dump_stats(str(path))
                stats = pstats.Stats(profile)
                rows = [dict(file=k[0], line=k[1], function=k[2], calls=v[1], self_seconds=v[2],
                             cumulative_seconds=v[3]) for k, v in stats.stats.items()]
                profiles.append(dict(tick=view.tick, decision=eligible, wall=wall,
                                     rows=sorted(rows, key=lambda x: -x['cumulative_seconds'])[:100]))
            if d.stats is not None:
                decisions.append(dict(tick=view.tick, wall=wall, stats=d.stats))
            return d
        player.act = logged
        players = {c['seat']: player, 1-c['seat']: make_player(rt, 'R3a')}
        t = time.perf_counter()
        failures = sum(FAILURES.values())
        res = play_match(rt, players, seed=c['seed'], decks=c['decks'], max_ticks=a.ticks,
                         levels=None if a.levels == 'none' else max_levels())
        row = dict(case=i, sequence=sequence, host=os.uname().nodename, levels=a.levels, ticks_limit=a.ticks,
                   exports=exports[export_start:], builds=builds[build_start:],
                   wall_seconds=time.perf_counter()-t, result=res, phases=phases, decisions=decisions,
                   profiles=profiles, failures=sum(FAILURES.values())-failures)
        root = getattr(player, 'level_root', None)
        if root is not None:
            row['runtime_export_sha256'] = root.lc.runtime_export_sha256
            row['runtime_export_identity'] = root.lc.runtime_export_identity
            row['preparation_seconds'] = getattr(root, 'preparation_seconds', None)
            row['root_stats'] = root.stats
            row['config_seats'] = len(root._cfg)
            row['cut_entries'] = {s: len(cut._cut) for s, (_, cut, _) in root._cfg.items()}
        with a.out.open('a') as f:
            f.write(json.dumps(row, default=str) + '\n')
        print(json.dumps({k: row[k] for k in ('case', 'levels', 'ticks_limit', 'wall_seconds', 'failures')}) +
              ' hash=' + res['command_sha256'], flush=True)


if __name__ == '__main__':
    main()
