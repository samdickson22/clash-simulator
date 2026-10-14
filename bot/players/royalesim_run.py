"""Play N X4S-style games of bot A vs bot B in RoyaleSim (or our engine, for pairing).

Bot A sits in x4s_setup(index)'s seat with deck X[i%5], B in the other seat with X[(i//5)%5];
seeds = base + index. One JSON line per game (append) with the result, A's seat, crowns,
command hash, CPU seconds and A's decision summary.

Player specs:
  v1 | R3a                         PolicyPlayer (v1 policy / R3a student alone)
  search:budget:48[:R3a|v1]        SearchPlayer, deterministic rollout budget (default R3a = K4S)
  search:unbounded[:R3a|v1]        SearchPlayer KU (no cutoff)
  scripted:balanced|pressure|defense   our PublicScriptedOpponent
  rgym:patient|push|defend|first-affordable|random|noop   RoyaleGym built-ins (RoyaleSim only)

  bot/players/run.sh -m bot.players.royalesim_run --a search:budget:48 --b v1 \\
      --indices 0 1 --base 4503604817370496 --out games.jsonl [--engine ours] [--repeat 2]
  --shard k/n plays indices i with i % n == k (one process per core).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time


def make_player(rt, spec):
    from .policy import PolicyPlayer
    from .search import SearchPlayer
    from .royalesim_opponents import RoyaleGymPlayer, ScriptedPlayer
    parts = spec.split(':')
    if parts[0] in ('v1', 'R3a', 'v1-cached'):
        return PolicyPlayer(rt, parts[0])
    if parts[0] == 'search':
        mode = parts[1]
        if mode == 'budget':
            budget = int(parts[2])
            default = parts[3] if len(parts) > 3 else 'R3a'
            return SearchPlayer(rt, mode='budget', budget=budget, default=default)
        default = parts[2] if len(parts) > 2 else 'R3a'
        return SearchPlayer(rt, mode=mode, default=default)
    if parts[0] == 'scripted':
        return ScriptedPlayer(rt, parts[1])
    if parts[0] == 'rgym':
        return RoyaleGymPlayer(parts[1])
    raise ValueError(f'unknown player spec {spec!r}')


def summarize(player):
    d = getattr(player, 'decisions', None)
    if not isinstance(d, list):
        return None
    searched = [s for s in d if 'completed' in s]
    return dict(decisions=len(d), searched=len(searched), hit=sum(bool(s.get('hit')) for s in d),
                student_default=sum(bool(s.get('student_default')) for s in d),
                plays=sum(s['action'] < 2304 for s in d),
                mean_rollouts=(sum(s.get('rollouts', 0) for s in searched)/len(searched)) if searched else None,
                mean_wall_ms=1000*sum(s['wall_seconds'] for s in d)/max(1, len(d)))


def play(rt, vocab, a_spec, b_spec, index, base, *, engine='rsim', client='15.535.29', max_ticks=None):
    from .ours import x4s_setup
    case = x4s_setup(rt, index, base)
    a, b = make_player(rt, a_spec), make_player(rt, b_spec)
    players = {case['seat']: a, 1-case['seat']: b}
    cpu0 = time.process_time()
    if engine == 'rsim':
        from .royalesim_match import play_match, MAX_TICKS
        result = play_match(rt, players, seed=case['seed'], decks=case['decks'], vocab=vocab, client=client,
                            max_ticks=max_ticks or MAX_TICKS)
    else:
        from .ours import play_match
        result = play_match(rt, players, seed=case['seed'], decks=case['decks'], max_ticks=max_ticks or 6001)
        # crowns = enemy crown towers down (king down = 3), as both engines count them
        result['crowns'] = {s: 3 if result['towers'][1-s][0] <= 0 else sum(h <= 0 for h in result['towers'][1-s][1:])
                            for s in (0, 1)}
    seat = case['seat']
    winner = result['winner']
    result.update(index=index, base=base, engine_arm=engine if engine == 'ours' else f'rsim-{client}',
                  a=a_spec, b=b_spec, a_seat=seat,
                  a_outcome='draw' if winner is None else ('win' if winner == seat else 'loss'),
                  a_summary=summarize(a), game_cpu_seconds=time.process_time()-cpu0)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--a', required=True)
    ap.add_argument('--b', default='v1')
    ap.add_argument('--indices', type=int, nargs='*')
    ap.add_argument('--range', type=int, nargs=2, metavar=('START', 'STOP'))
    ap.add_argument('--shard', default='0/1')
    ap.add_argument('--base', type=int, default=4503604817370496)
    ap.add_argument('--engine', default='rsim', choices=['rsim', 'ours'])
    ap.add_argument('--client', default='15.535.29', choices=['15.535.29', '16.402'])
    ap.add_argument('--max-ticks', type=int)
    ap.add_argument('--repeat', type=int, default=1, help='play each game this many times (determinism check)')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    indices = list(a.indices or []) + (list(range(*a.range)) if a.range else [])
    k, n = map(int, a.shard.split('/'))
    indices = [i for i in indices if i % n == k]
    cpu0 = time.process_time()
    from .runtime import Runtime
    rt = Runtime()
    vocab = None
    if a.engine == 'rsim':
        from .royalesim_vocab import load
        vocab = load(rt)
    setup = time.process_time()-cpu0
    a.out.parent.mkdir(parents=True, exist_ok=True)
    for index in indices:
        for rep in range(a.repeat):
            r = play(rt, vocab, a.a, a.b, index, a.base, engine=a.engine, client=a.client, max_ticks=a.max_ticks)
            r.update(repeat=rep, setup_cpu_seconds=setup, runtime_root=str(rt.root))
            with a.out.open('a') as f:
                f.write(json.dumps(r, default=str) + '\n')
            print(json.dumps({k: r[k] for k in ('index', 'repeat', 'a_seat', 'a_outcome', 'winner', 'crowns', 'ticks',
                                                'command_sha256', 'game_cpu_seconds')}, default=str), flush=True)


if __name__ == '__main__':
    main()
