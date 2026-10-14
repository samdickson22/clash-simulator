"""Play one HEADLINE case in our engine and snapshot the battle every tick (for the showcase video).

    CLASHER_BOT_RUNTIME=... python capture.py --index 0 --out DIR [--candidate K4C-r16 --opponent v1]

Writes DIR/case-<index>.pkl.gz = dict(meta, result, plays, frames). The snapshot is taken after
each b.step() (outside every decision window), so the bots' timing is unaffected except for the
snapshot's own CPU cost between ticks. Rendering happens later (render.py).
"""
from __future__ import annotations

import argparse
import gzip
import json
import pickle
import sys
import time
from pathlib import Path

sys.path.insert(0, '/mpac/sdicks02/repos/clasher-bot')


def snap_entity(e):
    cs = getattr(e, 'card_stats', None)
    kind = type(e).__name__
    name = getattr(cs, 'name', None) or getattr(e, 'spell_name', None) or getattr(e, 'source_name', None) or kind
    eng = getattr(cs, 'english_name', None) or name
    tp = getattr(e, 'target_position', None)
    return dict(
        id=e.id, kind=kind, name=name, eng=eng, p=e.player_id,
        x=float(e.position.x), y=float(e.position.y),
        hp=float(getattr(e, 'hitpoints', 0) or 0), mhp=float(getattr(e, 'max_hitpoints', 0) or 0),
        r=float(getattr(cs, 'collision_radius', 0.5) or 0.5) if cs is not None else 0.5,
        air=bool(getattr(e, 'is_air_unit', False)),
        pending=bool(getattr(e, 'placement_pending', False)),
        king=bool(getattr(e, '_is_king_tower', False)), slot=getattr(e, '_crown_tower_slot', None),
        tower=getattr(cs, 'name', None) in ('Tower', 'KingTower'),
        tx=float(tp.x) if tp is not None else None, ty=float(tp.y) if tp is not None else None,
        splash=float(getattr(e, 'splash_radius', 0) or 0),
        radius=float(getattr(e, 'radius', 0) or 0),
        roll=(float(getattr(e, 'rolling_radius', 0) or 0), float(getattr(e, 'radius_y', 0) or 0)),
        attack=float(b_time[0] - (getattr(e, 'last_attack_time', -9) or -9)),
    )


b_time = [0.0]


def snapshot(b):
    b_time[0] = b.time
    ents = []
    for e in b.entities.values():
        if e.is_alive:
            try:
                ents.append(snap_entity(e))
            except Exception as ex:  # never let a snapshot break the game
                ents.append(dict(id=getattr(e, 'id', -1), kind='ERR', err=repr(ex)[:80]))
    ps = [dict(elixir=float(p.elixir), hand=list(p.hand), nxt=(list(p.cycle_queue)[:1] or [None])[0],
               towers=[float(p.king_tower_hp), float(p.left_tower_hp), float(p.right_tower_hp)]) for p in b.players]
    return dict(tick=b.tick, time=float(b.time), double=bool(b.double_elixir), triple=bool(b.triple_elixir),
                overtime=bool(b.overtime), sudden=bool(getattr(b, 'sudden_death', False)), players=ps, ents=ents)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--index', type=int, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--candidate', default='K4C-r16')
    ap.add_argument('--opponent', default='v1')
    ap.add_argument('--base', type=int, default=None)
    a = ap.parse_args()
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    from bot.players.ours import play_match, x4s_setup
    from bot.eval.headline import make_player, HEADLINE_BASE
    base = HEADLINE_BASE if a.base is None else a.base
    rt = Runtime()  # bootstraps the runtime import paths; import clasher only after this
    from clasher.rl.action_space import DiscreteTileActionSpace
    import stage2_matches
    orig = stage2_matches.battle
    frames = []

    def patched(*args, **kw):
        b = orig(*args, **kw)
        step = b.step

        def step_and_snap(*sa, **sk):
            out = step(*sa, **sk)
            frames.append(snapshot(b))
            return out
        b.step = step_and_snap
        frames.append(snapshot(b))
        return b
    stage2_matches.battle = patched
    case = x4s_setup(rt, a.index, base)
    seat = case['seat']
    players = {seat: make_player(rt, a.candidate), 1 - seat: make_player(rt, a.opponent)}
    t0 = time.time()
    res = play_match(rt, players, seed=case['seed'], decks=case['decks'], verbose=True)
    space = DiscreteTileActionSpace()
    plays = []
    for actor, log in res.pop('play_log').items():
        for tick, card, action, ok in log:
            pos = space.decode_action(action, actor).position
            plays.append(dict(tick=tick, seat=actor, card=card, ok=ok, x=float(pos.x), y=float(pos.y)))
    plays.sort(key=lambda r: r['tick'])
    meta = dict(index=a.index, base=base, seed=case['seed'], seat=seat, decks=case['decks'],
                candidate=a.candidate, opponent=a.opponent, wall_seconds=time.time() - t0)
    res = json.loads(json.dumps(res, default=str))
    a.out.mkdir(parents=True, exist_ok=True)
    with gzip.open(a.out / f'case-{a.index}.pkl.gz', 'wb') as fh:
        pickle.dump(dict(meta=meta, result=res, plays=plays, frames=frames), fh)
    summary = dict(meta, winner=res['winner'], ticks=res['ticks'], towers=res['towers'],
                   command_sha256=res['command_sha256'], frames=len(frames))
    (a.out / f'case-{a.index}.json').write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
