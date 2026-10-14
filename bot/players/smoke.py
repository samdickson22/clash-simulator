"""Smoke: ONE short match in our engine, search player (budget mode) vs v1 policy.

    bot/players/run.sh -m bot.players.smoke --ticks 1200 --budget 48 --out reports/bot/inventory/smoke.json

Light by design (127x05 command-center host): one thread, nice 19 via run.sh.
"""
import argparse
import json
from pathlib import Path
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ticks', type=int, default=1200, help='max ticks (6001 = full game)')
    ap.add_argument('--index', type=int, default=0, help='X4S-style case index (decks/seat)')
    ap.add_argument('--base', type=int, default=4503604817370496, help='seed bank (default: X4S smoke bank)')
    ap.add_argument('--mode', default='budget', choices=['budget', 'unbounded', 'wall'])
    ap.add_argument('--budget', type=int, default=48)
    ap.add_argument('--default', default='R3a', choices=['R3a', 'v1'])
    ap.add_argument('--check-equivalence', type=int, default=3)
    ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    cpu0 = time.process_time()
    from bot.players.runtime import Runtime
    rt = Runtime()
    setup_cpu = time.process_time()-cpu0
    from bot.players.ours import play_match, x4s_setup
    from bot.players.policy import PolicyPlayer
    from bot.players.search import SearchPlayer
    case = x4s_setup(rt, a.index, a.base)
    bot = SearchPlayer(rt, mode=a.mode, budget=a.budget, default=a.default,
                       check_equivalence=a.check_equivalence)
    players = {case['seat']: bot, 1-case['seat']: PolicyPlayer(rt, 'v1')}
    result = play_match(rt, players, seed=case['seed'], decks=case['decks'], max_ticks=a.ticks)
    d = bot.decisions
    searched = [s for s in d if 'completed' in s]
    result.update(
        bot_seat=case['seat'], setup_cpu_seconds=setup_cpu, total_cpu_seconds=time.process_time()-cpu0,
        runtime_root=str(rt.root),
        bot_summary=dict(decisions=len(d), searched=len(searched),
                         hit=sum(bool(s.get('hit')) for s in d),
                         student_default=sum(bool(s.get('student_default')) for s in d),
                         plays=sum(s['action'] < 2304 for s in d),
                         mean_rollouts=(sum(s.get('rollouts', 0) for s in searched)/len(searched)) if searched else None,
                         mean_scored_set=(sum(s['candidates'] for s in searched)/len(searched)) if searched else None,
                         mean_wall_ms=1000*sum(s['wall_seconds'] for s in d)/max(1, len(d))),
        equivalence=bot.equivalence)
    text = json.dumps(result, indent=1, default=str)
    print(text)
    if a.out:
        a.out.write_text(text+'\n')


if __name__ == '__main__':
    main()
