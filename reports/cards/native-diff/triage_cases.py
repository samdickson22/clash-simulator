"""Deeper public-action replays around a game's first divergent tick.

Uses the same prepared host environment as mixed_games.py. Full config/raw tables
remain on the host; exported evidence is scrubbed before entering the worktree.
"""
import argparse
import json
from pathlib import Path
import re
import traceback

import mixed_games as M
from sanitize_results import scrub


def brief(b, native):
    from diagnostics import python_state, native_state
    p, n = python_state(b), native_state(native)
    # Preserve runtime state without bulky immutable source tables/prototypes.
    return scrub(dict(python=p, rust=n))


def replay(row, cfg):
    import differential as D
    from diagnostics import phase_step
    first = row['first']
    stop = first['tick'] - (first['kind'] == 'digest')
    b, native = M.setup(row['game'], cfg)
    actions = {}
    for action in row['actions']:
        actions.setdefault(action[0], []).append(action)
    history = []
    for t in range(stop + 1):
        if t >= stop - 12:
            history.append(dict(tick=t, when='before_actions', **brief(b, native)))
        for tick, seat, card, x, y, ep, er in actions.get(t, []):
            pa = bool(b.deploy_card(seat, card, D.Position(x, y)))
            ra = bool(native.apply_action(seat, card, x, y))
            assert (pa, ra) == (ep, er)
        if t == stop:
            phases = phase_step(b, native) if first['kind'] == 'digest' else {}
            return scrub(dict(game=row['game'], first=first,
                         before=history[-1], history=history, phases=phases))
        b.step()
        native.step()
        assert D.battle_digest(b) == native.digest(), f'earlier mismatch {b.tick}'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--directory', type=Path, required=True)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--worker', type=int, default=0)
    p.add_argument('--workers', type=int, default=1)
    p.add_argument('--all', action='store_true')
    args = p.parse_args()
    cfg = json.loads(args.config.read_text())
    rows = []
    for path in sorted(args.directory.glob('game-*.json')):
        row = json.loads(path.read_text())
        if not row.get('first'):
            continue
        # Missing FreezeIceGolemite is already unambiguous in first-detail.
        entities = row['first']['detail']['entities'].values()
        ice = any(e.get('python', {}).get('spell_name') == 'FreezeIceGolemite'
                  for e in entities if e.get('python'))
        if not ice or args.all:
            rows.append(row)
    for row in rows[args.worker::args.workers]:
        path = args.output / f"game-{row['game']['game']:04d}.json"
        if path.exists():
            continue
        try:
            M.atomic(path, replay(row, cfg))
            print('triaged', row['game']['game'], flush=True)
        except BaseException:
            M.atomic(path, dict(error=traceback.format_exc(), game=row['game']))
            print('triage-error', row['game']['game'], flush=True)


if __name__ == '__main__':
    main()
