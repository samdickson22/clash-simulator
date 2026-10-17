"""Headline evaluation in our engine: candidate vs a fixed opponent pool (exploration).

    CLASHER_BOT_RUNTIME=... python -m bot.eval.headline --out DIR --candidate K4S-b64 \
        --opponents v1,R3a,v1-greedy --games 300 --workers 64 [--base SEED_BASE]

Protocol HEADLINE-v1 (fixed; see reports/bot/HEADLINE.md):
- match = bot.players.ours.play_match (X4S loop: C56 Python engine, level 11, symmetric 27-tick command lag,
  one outstanding command, 5-tick polling from tick 90, abilities off, full 3+2 min); --levels max plays every
  card and both King towers at level 16 (our engine: bot/levels/match.py; RoyaleSim: reset levels);
- case i = x4s_setup(i, BASE): candidate seat i%2, candidate deck X-deck i%5, opponent deck X-deck (i//5)%5,
  both shuffled by Random(BASE+i); i = 0..games-1 for EVERY opponent (same cases across opponents);
  --decks fullpool:<seed>[:own=c56] swaps only the deck lists for full-pool sampler decks (bot/fullpool/banks.py;
  --bank NAME picks a named bank); the default 'x4s' is HEADLINE-v1 unchanged;
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
    if name.startswith('aliased:'):   # live-perception alias of the opponent's off-vocab cards (bot/fullpool/alias.py)
        from bot.fullpool.alias import AliasedPlayer
        return AliasedPlayer(rt, make_player(rt, name[8:]), name)
    if name.startswith(('LIVE-K4CW-', 'K4CW-', 'PERC-')):   # bot/live/player.py names (e.g. LIVE-K4CW-r16, live belief)
        from bot.live.player import make_live_player
        return make_live_player(rt, name)
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
    if name.startswith('rext-'):  # external trained policies, RoyaleLearn (RoyaleSim 15.535 only; bot/players/rext_policy.py)
        from bot.players.rext_policy import RextPolicyPlayer
        model = name[5:]
        greedy = model.endswith('-greedy')
        model = model.removesuffix('-greedy')
        if model.startswith('bc'):  # rext-bc*/rext-bcppo*: IL_Replay-derived, internal eval only; weights stay in the /mpac job dir
            model = os.path.join(os.environ.get('REXT_EXT2_MODELS', '/mpac/sdicks02/jobs/clasher/bot-ext2-models'), model)
        return RextPolicyPlayer(model, greedy=greedy)
    if name.startswith('K4SV-'):  # K4S-st with a learned leaf value V(state, seat) (bot/value/players.py)
        from bot.value.players import make_value_player
        return make_value_player(rt, name)
    if name.startswith('K4L-'):  # K4C-r16 with a learned rollout opponent (bot/search/lopp.py)
        from bot.search.lopp import make_lopp_player
        return make_lopp_player(rt, name)
    if name.startswith('K4O-'):  # K4C-r16 with other style aggregations / online style inference (bot/search/oppmodel.py)
        from bot.search.oppmodel import make_oppmodel_player
        return make_oppmodel_player(rt, name)
    if name.startswith('K4C-'):  # K4S-st with other proposal lists: R3a top-N, student K top-M (bot/search/candidates.py)
        from bot.search.candidates import make_candidate_player
        return make_candidate_player(rt, name)
    if name.startswith('K4S') and '@student' in name:  # search with a student proposer/default (bot/exit/teacher.py)
        from bot.exit.teacher import student_search
        return student_search(rt, name)
    if name.startswith('K4SP'):  # K4S + proposer top-k as extra candidates (bot/exit/teacher.py)
        from bot.exit.teacher import from_spec
        return from_spec(rt, name)
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


MAX_LEVEL = 16   # live16402c gamedata: every rarity's levelCount + relativeLevel = 16; expLevels towerLevel max 16


def worker(wid, jobs, out: Path, base: int, engine: str = 'ours', decks: str = 'x4s', belief=None, levels='none'):
    os.environ.setdefault('PYTHONHASHSEED', '0')
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    from bot.players.ours import play_match
    from bot.fullpool.banks import case as make_case, check_scope, select
    from bot.fullpool.models import install_from_env
    from bot.levels.match import max_levels
    rt = Runtime()
    install_from_env(rt)         # BOT_FULLPOOL_POLICIES (extended v1/R3a); unset = no-op
    select(rt, decks, belief)    # full-pool belief prior for search players; x4s = no-op
    check_scope(rt, decks, len(jobs), min((i for _, _, i in jobs), default=0), base)
    vocab = None
    if engine != 'ours':
        from bot.players.royalesim_vocab import load
        from bot.players.royalesim_match import play_match as rsim_play_match
        vocab = load(rt)
        client = {'rsim15535': '15.535.29', 'rsim16402': '16.402'}[engine]
    fh = open(out / f'games-{wid:03d}.jsonl', 'a')
    for cand, opp, i in jobs:
        case = make_case(rt, i, base, decks)   # decks='x4s' -> x4s_setup (HEADLINE-v1)
        t0 = time.time()
        try:
            players = {case['seat']: make_player(rt, cand), 1 - case['seat']: make_player(rt, opp)}
            if engine == 'ours':
                lv = {} if levels == 'none' else dict(levels=dict(max_levels(MAX_LEVEL),   # bot/levels/match.py
                                                                  planner=os.environ.get('BOT_LEVEL_PLANNER', 'exact')))
                res = play_match(rt, players, seed=case['seed'], decks=case['decks'],
                                 verbose=bool(os.environ.get('BOT_PLAYLOG')), **lv)   # per-play log for reaction metrics
            else:
                lv = {} if levels == 'none' else dict(     # --levels max: every card and both King towers at max
                    levels=[{c: MAX_LEVEL for c in d} for d in case['decks']], tower_levels=[MAX_LEVEL, MAX_LEVEL])
                res = rsim_play_match(rt, players, seed=case['seed'], decks=case['decks'], vocab=vocab, client=client,
                                      **lv)
            from bot.players.variants import close_logged
            for pl in players.values():
                close_logged(pl)
            w = res['winner']
            score = 0.5 if w is None or w == -1 else (1.0 if w == case['seat'] else 0.0)
            row = dict(engine=engine, candidate=cand, opponent=opp, index=i, seat=case['seat'], seed=case['seed'], score=score,
                       winner=w, terminal=res['terminal'], ticks=res['ticks'], towers=res['towers'],
                       plays=res['plays'], accepted=res['accepted'], command_sha256=res['command_sha256'],
                       cpu_seconds=res['cpu_seconds'], wall_seconds=time.time() - t0)
            if decks != 'x4s':
                row.update(decks=decks, deck_lists=case['decks'])
            if levels != 'none':
                row.update(levels=f'card{MAX_LEVEL}-tower{MAX_LEVEL}')
                if 'levels' in res:   # our engine: which seats planned with exact levels, packet normalisation
                    row.update(level_planners=res['levels']['planners'], level_packets=res['levels']['packets'])
            if 'play_log' in res:   # {seat: [(tick, card, action, accepted), ...]} (BOT_PLAYLOG=1)
                row['play_log'] = {str(k): [list(x) for x in v] for k, v in res['play_log'].items()}
            alias = {s: dict(p.observe_alias.counts) for s, p in players.items() if getattr(p, 'observe_alias', None)}
            if alias:
                row['alias_counts'] = alias
        except Exception as ex:  # recorded, never silently dropped
            row = dict(candidate=cand, opponent=opp, index=i, seat=case['seat'], error=repr(ex)[:500])
            if decks != 'x4s':
                row.update(decks=decks, deck_lists=case['decks'])
        fh.write(json.dumps(row) + '\n'); fh.flush()



def reap(procs):
    """Join workers as they exit (not in list order), so finished workers never linger as zombies."""
    from multiprocessing.connection import wait
    live = {p.sentinel: p for p in procs}
    while live:
        for sentinel in wait(list(live)):
            live.pop(sentinel).join()

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
    ap.add_argument('--decks', default='x4s', help="'x4s' (HEADLINE-v1) or a full-pool deck spec, e.g. "
                    "'fullpool:<seed>' or 'fullpool:<seed>:own=c56' (bot/fullpool/banks.py; needs pins r1-cards1)")
    ap.add_argument('--belief-prior', default=None, help="search belief prior: 'c56' or a deck spec "
                    "(default: the --decks sampler when full-pool, else the C56 catalog)")
    ap.add_argument('--bank', default=None, help='a named bank of bot/fullpool/banks.py BANKS: sets --base and --decks')
    ap.add_argument('--level-planner', default='exact', choices=['exact', 'l11'],
                    help="our engine with --levels max: search planners plan at the exact game levels (default) or at "
                         "level 11 (the deployed live assumption; ~9x cheaper per game)")
    ap.add_argument('--levels', default='none', choices=['none', 'max'],
                    help="'max': every card on both sides and both King towers at level 16. RoyaleSim engines: planners "
                         "keep their own level assumptions. Our engine (bot/levels/match.py): search players with a "
                         "root_fn plan with the exact level-16 game; policies read level-11 packets.")
    a = ap.parse_args()
    os.environ['BOT_LEVEL_PLANNER'] = a.level_planner      # read by the workers (bot/levels/match.py planner)
    if a.bank:
        from bot.fullpool.banks import BANKS
        a.base, a.decks = BANKS[a.bank]['base'], BANKS[a.bank]['decks']
    if a.engine != 'ours' and a.decks != 'x4s':
        raise ValueError('full-pool decks need our engine (the RoyaleSim vocab is C56)')
    a.out.mkdir(parents=True, exist_ok=True)
    done = done_keys(a.out)
    jobs = [(c, o, i) for c in a.candidate.split(',') for o in a.opponents.split(',')
            for i in range(a.start, a.start + a.games) if (c, o, i) not in done]
    # interleave so every worker gets a mix (search games are ~10x the cost of policy games)
    shares = [jobs[w::a.workers] for w in range(a.workers)]
    (a.out / 'launch.json').write_text(json.dumps(dict(args={k: str(v) for k, v in vars(a).items()},
                                                       jobs=len(jobs), started=time.time())))
    procs = [Process(target=worker, args=(w, s, a.out, a.base, a.engine, a.decks, a.belief_prior, a.levels))
             for w, s in enumerate(shares) if s]
    for p in procs:
        p.start()
    reap(procs)


if __name__ == '__main__':
    main()
