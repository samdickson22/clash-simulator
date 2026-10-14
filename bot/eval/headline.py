"""Headline evaluation in our engine: candidate vs a fixed opponent pool (exploration).

    CLASHER_BOT_RUNTIME=... python -m bot.eval.headline --out DIR --candidate K4S-b64 \
        --opponents v1,R3a,v1-greedy --games 300 --workers 64 [--base SEED_BASE]

Protocol HEADLINE-v1 (fixed; see reports/bot/HEADLINE.md):
- match = bot.players.ours.play_match (X4S loop: C56 Python engine, level 11, symmetric 27-tick command lag,
  one outstanding command, 5-tick polling from tick 90, abilities off, full 3+2 min);
- case i = x4s_setup(i, BASE): candidate seat i%2, candidate deck X-deck i%5, opponent deck X-deck (i//5)%5,
  both shuffled by Random(BASE+i); i = 0..games-1 for EVERY opponent (same cases across opponents);
- score: win 1, draw 0.5, loss 0 for the candidate.
Each worker builds the runtime once and plays its share; results append to DIR/games-<worker>.jsonl
(resumable: finished (candidate, opponent, index) keys are skipped).
"""
from __future__ import annotations

import argparse
import json
import os
import time
from multiprocessing import Process
from pathlib import Path

HEADLINE_BASE = 1455777415631152  # fresh bank: int.from_bytes(os.urandom(6),'big')<<4, drawn 2026-10-14 (see HEADLINE.md)


def make_player(rt, name):
    from bot.players.policy import PolicyPlayer
    from bot.players.search import SearchPlayer
    from bot.players.variants import ScriptedPlayer, VariantPolicyPlayer
    if name in ('v1', 'R3a'):
        return PolicyPlayer(rt, name)
    if name in ('v1-greedy', 'R3a-sampled'):
        return VariantPolicyPlayer(rt, name)
    if name.startswith('v1-tau'):
        return VariantPolicyPlayer(rt, 'v1-greedy', tau=float(name[6:]))
    if name == 'v1-logged':
        return VariantPolicyPlayer(rt, 'v1-logged', log_path=os.environ['BOT_PPLAY_LOG'])
    if name.startswith(('student:', 'student10:')):  # 'student:<ckpt>[@threshold]' (bot/exit/student.py)
        from bot.exit.student import StudentPlayer
        return StudentPlayer.from_spec(rt, name)
    if name.startswith('scripted-'):
        return ScriptedPlayer(rt, name.split('-', 1)[1])
    if name.startswith('rgym-'):  # RoyaleGym's shipped opponents (RoyaleSim engine only)
        from bot.players.royalesim_opponents import RoyaleGymPlayer
        return RoyaleGymPlayer(name[5:])
    if name.startswith('K4S-b'):
        return SearchPlayer(rt, mode='budget', budget=int(name[5:]), default='R3a')
    if name.startswith('K4-b'):
        return SearchPlayer(rt, mode='budget', budget=int(name[4:]), default='v1')
    if name == 'KU':
        return SearchPlayer(rt, mode='unbounded', default='R3a')
    if name.startswith('K4S-'):  # search-compute variants: K4S-m4, K4S-w48, K4S-st, K4S-h320, ... (bot/search)
        from bot.search.players import make_search_player
        return make_search_player(rt, name)
    raise ValueError(name)


def done_keys(out: Path):
    keys = set()
    for p in out.glob('games-*.jsonl'):
        for line in p.read_text().splitlines():
            try:
                r = json.loads(line)
                keys.add((r['candidate'], r['opponent'], r['index']))
            except Exception:
                pass
    return keys


def worker(wid, jobs, out: Path, base: int, engine: str = 'ours'):
    os.environ.setdefault('PYTHONHASHSEED', '0')
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    from bot.players.ours import play_match, x4s_setup
    rt = Runtime()
    vocab = None
    if engine != 'ours':
        from bot.players.royalesim_vocab import load
        from bot.players.royalesim_match import play_match as rsim_play_match
        vocab = load(rt)
        client = {'rsim15535': '15.535.29', 'rsim16402': '16.402'}[engine]
    fh = open(out / f'games-{wid:03d}.jsonl', 'a')
    for cand, opp, i in jobs:
        case = x4s_setup(rt, i, base)
        t0 = time.time()
        try:
            players = {case['seat']: make_player(rt, cand), 1 - case['seat']: make_player(rt, opp)}
            if engine == 'ours':
                res = play_match(rt, players, seed=case['seed'], decks=case['decks'])
            else:
                res = rsim_play_match(rt, players, seed=case['seed'], decks=case['decks'], vocab=vocab, client=client)
            from bot.players.variants import close_logged
            for pl in players.values():
                close_logged(pl)
            w = res['winner']
            score = 0.5 if w is None or w == -1 else (1.0 if w == case['seat'] else 0.0)
            row = dict(engine=engine, candidate=cand, opponent=opp, index=i, seat=case['seat'], seed=case['seed'], score=score,
                       winner=w, terminal=res['terminal'], ticks=res['ticks'], towers=res['towers'],
                       plays=res['plays'], accepted=res['accepted'], command_sha256=res['command_sha256'],
                       cpu_seconds=res['cpu_seconds'], wall_seconds=time.time() - t0)
        except Exception as ex:  # recorded, never silently dropped
            row = dict(candidate=cand, opponent=opp, index=i, seat=case['seat'], error=repr(ex)[:500])
        fh.write(json.dumps(row) + '\n'); fh.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--candidate', required=True, help='comma list allowed')
    ap.add_argument('--opponents', required=True)
    ap.add_argument('--games', type=int, default=300)
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--base', type=int, default=HEADLINE_BASE)
    ap.add_argument('--engine', default='ours', choices=['ours', 'rsim15535', 'rsim16402'])
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    done = done_keys(a.out)
    jobs = [(c, o, i) for c in a.candidate.split(',') for o in a.opponents.split(',')
            for i in range(a.start, a.start + a.games) if (c, o, i) not in done]
    # interleave so every worker gets a mix (search games are ~10x the cost of policy games)
    shares = [jobs[w::a.workers] for w in range(a.workers)]
    (a.out / 'launch.json').write_text(json.dumps(dict(args={k: str(v) for k, v in vars(a).items()},
                                                       jobs=len(jobs), started=time.time())))
    procs = [Process(target=worker, args=(w, s, a.out, a.base, a.engine)) for w, s in enumerate(shares) if s]
    for p in procs:
        p.start()
    for p in procs:
        p.join()


if __name__ == '__main__':
    main()
