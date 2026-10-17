"""Attachment-graph class probe: Goblin Giants under every displacement source, through real roots and native.

Natural play_match games (ordinary economy, legal-mask actions; no direct spawns or private state). Both seats run
the same scripted policy: deploy Goblin Giant at a bridge, Clone it, and aim displacement cards (Fisherman, Tornado,
Log, Fireball, Snowball, BarbLog, RoyalDelivery, Bowler) at the nearest enemy Goblin Giant. Every tick with a Goblin
Giant or rider on the board, each seat's public root is built by the runtime consumer (R.root). The runtime's
public_root.repair_public_graph is wrapped so the SAME entity rows also run through reference helpers (--ref: the
pre-fix a156cf5b1 and B1 complete-population 244e385ca versions); their outcomes are counted, never used. Roots whose repair
needed the structural fallback are cloned, reloaded and stepped natively. Optional HELPER replaces the runtime's
helper in place (same module object), for testing a candidate against an existing runtime.

    python graph_stress.py REPO OUT.json [--helper public_root.py] [--ref NAME=old_public_root.py ...] [--seeds N]
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import random
import sys
import types

import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument('repo', type=Path)
ap.add_argument('out', type=Path)
ap.add_argument('--helper', type=Path)
ap.add_argument('--ref', action='append', default=[], help='NAME=PATH of a reference helper (counted, never used)')
ap.add_argument('--seeds', type=int, default=6)
ap.add_argument('--seed0', type=int, default=20261017100)
ap.add_argument('--max-ticks', type=int, default=4001)
a = ap.parse_args()
if a.out.exists():
    raise SystemExit('fresh output required')
repo = a.repo.resolve(strict=True)
sys.path.insert(0, str(repo))

import bot.players.runtime as runtime  # noqa: E402

rt = runtime.Runtime()
R = rt.R
import public_root as module  # noqa: E402  (the runtime's helper, as every consumer imports it)
if a.helper:
    code = a.helper.read_bytes()
    exec(compile(code, str(a.helper), 'exec'), module.__dict__)
helper_sha = hashlib.sha256(code if a.helper else Path(module.__file__).read_bytes()).hexdigest()


def reference(path):
    ns = types.ModuleType('public_root_reference')
    ns.__dict__['__file__'] = module.__file__
    exec(compile(Path(path).read_bytes(), str(path), 'exec'), ns.__dict__)
    return ns


refs = {name: reference(path) for name, path in (r.split('=', 1) for r in a.ref)}
ref_sha = {name: hashlib.sha256(Path(path).read_bytes()).hexdigest() for name, path in (r.split('=', 1) for r in a.ref)}
current = module.repair_public_graph
metrics = Counter()
witness = {}


def wrapped(entities):
    riders = sum(e['class'] == 'Troop' and e['stats']['name'] == module.GG_RIDER for e in entities)
    parents = sum(e['class'] == 'Troop' and e['stats']['name'] == module.GG_PARENT for e in entities)
    if riders or parents:
        metrics['graph_boards'] += 1
        for name, ref in refs.items():
            try:
                ref.repair_public_graph(copy.deepcopy(entities))
            except ref.PublicGraphError as ex:
                metrics[f'{name}_graph_errors'] += 1
                witness.setdefault(name, dict(report=ex.report, ctx=dict(context)))
    try:
        report = current(entities)
    except module.PublicGraphError as ex:
        metrics['candidate_graph_errors'] += 1
        witness.setdefault('candidate', dict(report=ex.report, ctx=dict(context)))
        raise
    if report.get('structural_fallback'):
        metrics['structural_boards'] += 1
        metrics['structural_riders'] += report['structural_riders']
        if report['riders'] < 2 * report['parents']:
            metrics['structural_partial_boards'] += 1
        witness.setdefault('structural', dict(report=report, ctx=dict(context)))
    return report


module.repair_public_graph = wrapped
context = {}

from bot.players.base import Decision, WAIT  # noqa: E402
from bot.players.ours import play_match  # noqa: E402
from clasher.rl.public_action_mask import PublicActionMaskInput  # noqa: E402
from derived_public_state import DerivedPublicState  # noqa: E402

DISPLACE = ['Fisherman', 'Tornado', 'Log', 'Fireball', 'Snowball', 'BarbLog', 'RoyalDelivery', 'Bowler']
missing = [c for c in ['GoblinGiant', 'Clone'] + DISPLACE if c not in R.config['cards']]
if missing:
    raise SystemExit(f'cards missing from runtime scope: {missing}')
GIANT = R.builder.token_id('GoblinGiant', namespace='troop_body')


def graph_ok(state):
    rows = state['entities']
    ids = {e['id']: e for e in rows}
    slots = set()
    for e in rows:
        if e.get('mount') is not None:
            p = ids.get(e['mount'])
            assert e['class'] == 'Troop' and e['stats']['name'] == module.GG_RIDER, 'non-rider attached'
            assert p is not None and p['stats']['name'] == module.GG_PARENT and p['owner'] == e['owner'], 'bad parent'
            slot = (p['id'], e.get('rider_rank', 0))
            assert slot[1] in (0, 1) and slot not in slots, 'duplicate slot'
            slots.add(slot)
        elif e['class'] == 'Troop' and e['stats']['name'] == module.GG_RIDER:
            raise AssertionError('observed rider lost its mount')
    return len(slots)


def inspect(info, opponent, seed):
    import clasher_core
    from bot.search.lopp_fast import split_snapshot
    context.update(tick=int(info.tick), seat=int(info.seat), seed=seed)
    before = metrics['structural_boards']
    rng = np.random.default_rng(900000 + info.tick + info.seat)
    try:
        root = R.root(info, opponent, rng)
    except module.PublicGraphError:
        metrics['root_errors'] += 1
        return
    finally:
        context.clear()
    metrics['roots'] += 1
    head, _, tail = split_snapshot(root.snapshot())
    metrics['attached_rows'] += graph_ok(json.loads(head + '{}' + tail))
    if metrics['structural_boards'] > before or info.tick % 100 == 0:
        x, y = root.clone(), clasher_core.BattleState(root.snapshot())
        for _ in range(4):
            x.step(); y.step()
            assert x.snapshot() == y.snapshot(), 'native continuation/reload mismatch'
        metrics['native_continuations'] += 1
        if metrics['structural_boards'] > before:
            metrics['native_structural_continuations'] += 1


class Player:
    deadline_seconds = None
    name = 'graph-stress'

    def __init__(self, seed, opponent_deck):
        self.seed = seed
        self.opponent_deck = opponent_deck

    def start(self, ctx):
        self.seat = ctx.seat
        self.belief = DerivedPublicState({'decks': [dict(cards=self.opponent_deck, frequency=1)]}, R.costs)
        self.np_rng = np.random.default_rng(ctx.seed + ctx.seat)
        self.rng = random.Random(ctx.seed * 3 + ctx.seat)
        self.plays = Counter()

    def act(self, view):
        info = view.info
        obs = info.packet.observation
        rows = list(zip(obs.entity_ids[obs.entity_mask], obs.entity_features[obs.entity_mask]))
        own_gg = [r for t, r in rows if int(t) == GIANT and r[2] and r[4]]
        enemy_gg = [r for t, r in rows if int(t) == GIANT and not r[2] and r[4]]
        if (own_gg or enemy_gg) and not obs.terminal:
            self.belief.update(info.tick, info.events)
            inspect(info, self.belief.sample(self.np_rng), self.seed)
        if not view.can_act or view.tick % 5:
            return Decision(WAIT)
        mask = R.bots['balanced'].mask_builder.build(
            PublicActionMaskInput.from_confidence_observation(view.reserved.packet))
        hand = info.own['hand'][:4]
        choice = None
        if enemy_gg:
            options = [(self.plays[c], s, c) for s, c in enumerate(hand) if c in DISPLACE]
            if options:
                _, slot, card = min(options)
                target = enemy_gg[self.rng.randrange(len(enemy_gg))]
                choice = slot, card, float(target[0]) * 18, float(target[1]) * 32
        if choice is None and own_gg and 'Clone' in hand:
            target = own_gg[0]
            choice = hand.index('Clone'), 'Clone', float(target[0]) * 18, float(target[1]) * 32
        if choice is None and 'GoblinGiant' in hand and not own_gg:
            choice = hand.index('GoblinGiant'), 'GoblinGiant', self.rng.choice((3.5, 14.5)), 14.5
        if choice is None:
            return Decision(WAIT)
        slot, card, x, y = choice
        legal = np.flatnonzero(mask[slot * 576:(slot + 1) * 576])
        if not len(legal):
            return Decision(WAIT)
        tile = min(map(int, legal), key=lambda t: ((t % 18 + .5 - x) ** 2 + (t // 18 + .5 - y) ** 2, t))
        self.plays[card] += 1
        metrics['plays_' + card] += 1
        return Decision(slot * 576 + tile)

    def close(self):
        pass


DECK = ['GoblinGiant', 'Clone', 'Fisherman', 'Tornado', 'Log', 'Fireball', 'Snowball', 'RoyalDelivery']
DECK2 = ['GoblinGiant', 'Clone', 'Fisherman', 'Tornado', 'BarbLog', 'Fireball', 'Bowler', 'Log']
games = []
for i in range(a.seeds):
    seed = a.seed0 + i
    decks = [DECK[:], DECK2[:]] if i % 2 == 0 else [DECK2[:], DECK[:]]
    result = play_match(rt, {0: Player(seed, decks[1]), 1: Player(seed, decks[0])}, seed=seed, decks=decks, max_ticks=a.max_ticks,
                        verbose=True)
    result.pop('play_log', None)
    games.append(dict(seed=seed, ticks=result.get('ticks'), winner=result.get('winner'),
                      errors=result.get('errors'), crash=result.get('crash')))
    print(json.dumps(dict(game=i, seed=seed, ticks=result.get('ticks'), metrics=dict(metrics))), flush=True)

out = dict(helper=str(a.helper or module.__file__), helper_sha256=helper_sha, references=ref_sha,
           native=str(Path(sys.modules['clasher_core'].__file__).resolve()),
           runtime=str(rt.root), games=games, metrics=dict(metrics), witness=witness)
a.out.write_text(json.dumps(out, indent=1, sort_keys=True, default=str) + '\n')
assert metrics['candidate_graph_errors'] == 0 and metrics['root_errors'] == 0, metrics
assert metrics['roots'] > 0 and metrics['attached_rows'] > 0, metrics
print('PASS', json.dumps(dict(metrics)))
