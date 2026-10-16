"""Measurement-only mixed-deck lockstep runner for the pinned native engine.

Run in the prepared host root with PYTHONPATH=../out-total:engine-rs:src.
`plan` needs --pool-tool and --c56-source; workers need only the resulting plan.
Every completed game is atomically saved and skipped on restart. No engine edits.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, deque
import hashlib
import importlib.util
import itertools
import json
import os
from pathlib import Path
import random
import re
import time
import traceback

PIN = "681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b"
VERSION = 1


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=1, sort_keys=True) + "\n")
    temporary.replace(path)


def make_plan(args):
    spec = importlib.util.spec_from_file_location("card_pool", args.pool_tool)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Only names/kinds are retained; no official stat tables enter the report.
    pool = {c['name']: c['kind'] for c in module.ladder_pool()}
    tree = ast.parse(Path(args.c56_source).read_text())
    assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'C56' for t in n.targets))
    c56 = set(ast.literal_eval(assignment.value.args[0]))
    assert len(pool) == 122 and len(c56) == 56 and c56 <= pool.keys()
    names = sorted(pool)
    rng = random.Random(args.seed)
    counts, pairs = Counter(), set()
    games = []
    for i in range(args.games):
        # Random candidates are weighted toward underrepresented cards; select
        # for uncovered card-pair co-occurrence as well as balanced appearances.
        candidates = []
        for _ in range(64):
            choice = sorted(names, key=lambda n: rng.random() ** (1 + counts[n]))[-16:]
            ps = set(itertools.combinations(sorted(choice), 2))
            score = 10 * len(ps - pairs) - sum(counts[n] for n in choice)
            candidates.append((score, choice, ps))
        _, choice, ps = max(candidates, key=lambda x: x[0])
        rng.shuffle(choice)
        games.append(dict(game=i, seed=args.seed + 10000 + i,
                          decks=[choice[:8], choice[8:]], lane=i % 2,
                          style=(i // 2) % 3))
        counts.update(choice)
        pairs.update(ps)
    assert min(counts[n] for n in names if n not in c56) >= 30
    plan = dict(version=VERSION, seed=args.seed, ticks=args.ticks, pin=PIN,
                kinds=pool, c56=sorted(c56), games=games,
                appearances=dict(counts), card_pairs=len(pairs),
                missing_pairs=[list(p) for p in itertools.combinations(names, 2) if p not in pairs])
    atomic(args.plan, plan)
    print(json.dumps({k: plan[k] for k in ('version', 'seed', 'ticks', 'card_pairs', 'missing_pairs')}))
    print('appearance range', min(counts.values()), max(counts.values()), flush=True)


def setup(game, cfg):
    import differential as D
    b = D.initial(game['seed'])
    for player, deck in zip(b.players, game['decks']):
        player.deck = list(deck)
        player.hand = list(deck[:4])
        player.cycle_queue = deque(deck[4:])
        player.elixir = 10.0
    native = D.clasher_core.BattleState(D.snapshot(b, cfg))
    assert D.battle_digest(b) == native.digest(), 'initial import mismatch'
    return b, native


def positions(b, seat, card, kind, game, attempt):
    """Targets use the reference state; identical coordinates go to both APIs."""
    lane = 4.5 if game['lane'] == 0 else 13.5
    # Both seats share a lane to force encounters. A second lane is tried only
    # if a legal placement is blocked. Bridge/defense/backline vary by game.
    own_y = (14.0, 10.5, 7.5)[game['style']]
    y = own_y if seat == 0 else 32 - own_y
    units = [e for e in b.entities.values() if e.is_alive and e.entity_kind == 0]
    if card == 'Mirror':
        resolved = b.resolve_card_play(seat, card)
        if resolved:
            name, stats, spell = resolved
            kind = 'spell' if spell is not None else ('building' if str(stats.card_type).lower() == 'building' else 'troop')
            card = name
    if kind == 'spell':
        friendly = card in ('Heal', 'Rage', 'Clone')
        targets = [e for e in units if (e.player_id == seat) == friendly]
        if targets:
            # Densest cluster; Heal prefers injured friendlies when available.
            if card == 'Heal':
                hurt = [e for e in targets if e.hitpoints < e.max_hitpoints]
                targets = hurt or targets
            target = max(targets, key=lambda e: sum(
                (e.position.x - f.position.x)**2 + (e.position.y - f.position.y)**2 < 9
                for f in targets))
            x, y = target.position.x, target.position.y
            return [(x, y)]
        return [(lane, 25.5 if seat == 0 else 6.5)]
    if card == 'Heal':
        # This ladder name is a Heal Spirit in the current data, not the retired
        # heal spell: legal own-side deployment alongside friendly troops.
        friendly = [e for e in units if e.player_id == seat
                    and (e.position.y < 15 if seat == 0 else e.position.y > 17)]
        if friendly:
            target = min(friendly, key=lambda e: e.hitpoints / max(1, e.max_hitpoints))
            lane = min(16.5, max(1.5, target.position.x))
            y = min(14.0, target.position.y) if seat == 0 else max(18.0, target.position.y)
    if kind == 'building':
        y = 11.5 if seat == 0 else 20.5
        return [(7.5, y), (10.5, y), (lane, y - 3 if seat == 0 else y + 3)]
    return [(lane, y), (lane + (1 if lane < 9 else -1), y - 1 if seat == 0 else y + 1),
            (18 - lane, y)]


def scripted(b, native, game, kinds, counts, actions):
    import differential as D
    if b.tick % 40:
        return
    for seat in (0, 1):
        player = b.players[seat]
        eligible = []
        for card in player.hand:
            play = b.resolve_card_play(seat, card)
            if play is None:
                continue
            # Prefer Mirror while history is available; every other card is
            # round-robin by successful deployment count, then deck order.
            priority = counts[seat, card] - (0.25 if card == 'Mirror' else 0)
            eligible.append((priority, game['decks'][seat].index(card), card))
        for _, _, card in sorted(eligible):
            # Reserve enough elixir for the next least-played card. Picking only
            # affordable cards would permanently starve expensive cards.
            play = b.resolve_card_play(seat, card)
            if not player.can_play_card(card, play[1]):
                break
            success = False
            for x, y in positions(b, seat, card, kinds[card], game, counts[seat, card]):
                pa = bool(b.deploy_card(seat, card, D.Position(x, y)))
                ra = bool(native.apply_action(seat, card, x, y))
                actions.append([b.tick, seat, card, x, y, pa, ra])
                if pa != ra:
                    return
                if pa:
                    counts[seat, card] += 1
                    success = True
                    break
            if success:
                break


def focus_detail(b, native):
    from diagnostics import detail
    data = detail(b, native)
    ids = {int(m.group(1)) for d in data['field_diff']
           if (m := re.search(r'\.entities\.(\d+)\.', d['field']))}
    if any(d['field'] == '.entities.ids' for d in data['field_diff']):
        ids |= set(b.entities) ^ {e['id'] for e in data['rust']['entities']}
    # Include targets and sources to support interaction attribution.
    for eid in list(ids):
        e = b.entities.get(eid)
        if e:
            ids.add(e.target_id)
            src = getattr(e, 'source_entity', None)
            if src is not None:
                ids.add(src.id)
    return dict(field_diff=data['field_diff'],
                entities={str(eid): dict(name=getattr(getattr(b.entities.get(eid), 'card_stats', None), 'name', None),
                            python=data['python']['raw_entities'].get(str(eid)),
                            rust=next((e for e in data['rust']['entities'] if e['id'] == eid), None))
                          for eid in ids if eid is not None},
                entity_names={str(e.id): getattr(e.card_stats, 'name', type(e).__name__) for e in b.entities.values()})


def compact_phases(phases):
    result = {}
    for label, data in phases.items():
        ids = {int(m.group(1)) for d in data['field_diff']
               if (m := re.search(r'\.entities\.(\d+)\.', d['field']))}
        result[label] = dict(field_diff=data['field_diff'],
            entities={str(eid): dict(python=next((e for e in data['python']['entities'] if e['id'] == eid), None),
                                    rust=next((e for e in data['rust']['entities'] if e['id'] == eid), None))
                      for eid in ids})
    return result


def replay_triage(game, cfg, first, actions):
    import differential as D
    from diagnostics import phase_step
    b, native = setup(game, cfg)
    by_tick = {}
    for action in actions:
        by_tick.setdefault(action[0], []).append(action)
    step_tick = first['tick'] - (1 if first['kind'] == 'digest' else 0)
    for t in range(step_tick + 1):
        for tick, seat, card, x, y, expected_p, expected_r in by_tick.get(t, []):
            pa = bool(b.deploy_card(seat, card, D.Position(x, y)))
            ra = bool(native.apply_action(seat, card, x, y))
            assert (pa, ra) == (expected_p, expected_r), 'nondeterministic action replay'
            if t == step_tick and first['kind'] == 'action' and pa != ra:
                return dict(action=[tick, seat, card, x, y, pa, ra], detail=focus_detail(b, native))
        if t == step_tick:
            return dict(phases=compact_phases(phase_step(b, native)))
        b.step()
        native.step()
        assert D.battle_digest(b) == native.digest(), f'earlier replay mismatch {b.tick}'


def run_one(game, cfg, plan):
    import differential as D
    start = time.monotonic()
    out = dict(version=VERSION, game=game, pin=plan['pin'], status='running', actions=[], first=None)
    counts = Counter()
    nearby_cards, nearby_mechanics = set(), set()
    seen_mechanics = set()
    stage = 'setup'
    b = native = None
    try:
        b, native = setup(game, cfg)
        for _ in range(plan['ticks']):
            if b.game_over:
                break
            stage = 'actions'
            old_len = len(out['actions'])
            scripted(b, native, game, plan['kinds'], counts, out['actions'])
            rejected = [a for a in out['actions'][old_len:] if a[-2] != a[-1]]
            if rejected and out['first'] is None:
                out['first'] = dict(kind='action', tick=b.tick, action=rejected[0], detail=focus_detail(b, native))
            stage = 'python_step'
            b.step()
            if b.tick % 40 == 0:
                # A proximity observation is an encounter opportunity, not a
                # claim that a particular status effect/attack actually fired.
                live = [e for e in b.entities.values() if e.is_alive]
                tags = {e.id: sorted({type(m).__name__ for m in e.mechanics}) for e in live}
                for values in tags.values():
                    seen_mechanics.update(values)
                for e, f in itertools.combinations(live, 2):
                    if (e.position.x-f.position.x)**2 + (e.position.y-f.position.y)**2 <= 36:
                        en = getattr(e.card_stats, 'name', type(e).__name__)
                        fn = getattr(f.card_stats, 'name', type(f).__name__)
                        nearby_cards.add(tuple(sorted((en, fn))))
                        nearby_mechanics.update(tuple(sorted((a, z))) for a in tags[e.id] for z in tags[f.id])
            stage = 'native_step'
            native.step()
            stage = 'digest'
            pd, rd = D.battle_digest(b), native.digest()
            if pd != rd and out['first'] is None:
                out['first'] = dict(kind='digest', tick=b.tick, python_digest=pd, rust_digest=rd,
                                    detail=focus_detail(b, native))
        out.update(status='mismatch' if out['first'] else 'match', ticks=b.tick,
                   game_over=b.game_over, winner=b.winner,
                   deployments={f'{seat}:{name}': count for (seat, name), count in counts.items()})
    except BaseException as exc:
        out.update(status='panic' if type(exc).__name__ == 'PanicException' else 'exception',
                   error_type=type(exc).__name__, error_stage=stage,
                   error=traceback.format_exc(), ticks=b.tick if b is not None else 0)
        if b is not None and native is not None:
            try:
                out['exception_detail'] = focus_detail(b, native)
            except BaseException:
                pass
    out.update(nearby_cards=sorted(nearby_cards), nearby_mechanics=sorted(nearby_mechanics),
               seen_mechanics=sorted(seen_mechanics))
    if out['first']:
        try:
            out['triage'] = replay_triage(game, cfg, out['first'], out['actions'])
        except BaseException as exc:
            out['triage_error'] = dict(type=type(exc).__name__, error=traceback.format_exc())
    out['seconds'] = time.monotonic() - start
    return out


def worker(args):
    import differential as D
    binary = Path(D.clasher_core.__file__)
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    assert digest == PIN, (digest, PIN)
    plan = json.loads(Path(args.plan).read_text())
    cfg_start = time.monotonic()
    cfg = (json.loads(args.config_cache.read_text()) if args.config_cache and args.config_cache.exists()
           else D.config(tuple(sorted(plan['kinds']))))
    # Keep exported official config on the job host only, never in the repo.
    cache = args.config_cache
    if cache:
        atomic(cache, cfg)
    print(json.dumps(dict(worker=args.worker, pid=os.getpid(), config_seconds=time.monotonic()-cfg_start,
                          cards=len(cfg['cards']), pin=digest)), flush=True)
    for game in plan['games'][args.worker::args.workers]:
        path = args.output / f"game-{game['game']:04d}.json"
        if path.exists():
            continue
        result = run_one(game, cfg, plan)
        atomic(path, result)
        print(json.dumps(dict(game=game['game'], status=result['status'], ticks=result['ticks'],
                              first_tick=(result['first'] or {}).get('tick'), seconds=result['seconds'])), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['plan', 'worker'])
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--pool-tool', type=Path)
    p.add_argument('--c56-source', type=Path)
    p.add_argument('--games', type=int, default=600)
    p.add_argument('--ticks', type=int, default=3600)
    p.add_argument('--seed', type=int, default=6812026)
    p.add_argument('--worker', type=int, default=0)
    p.add_argument('--workers', type=int, default=1)
    p.add_argument('--output', type=Path, default=Path('games'))
    p.add_argument('--config-cache', type=Path)
    args = p.parse_args()
    (make_plan if args.mode == 'plan' else worker)(args)


if __name__ == '__main__':
    main()
