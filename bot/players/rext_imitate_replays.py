"""IL_Replay human games -> RoyaleImitate demonstration shards in OUR training env (rext-bc).

Runs in the learnvenv (royaleimitate 0.2.13, MIT). No conversion of the data format is needed:
royaleimitate reads IL_Replay's own `replays/*.parquet` (`payload_json` column), which is what
the local copy holds (127x03 /mpac/sdicks02/repos/clasher-local-data/il_replay, HF revision
059d43a0...; license unchecked, the same corpus our v1 human prior was trained from).

What this adds to `royaleimitate.write_matches` (whose `match_plan` and `_replay` it reuses
unchanged, so every match is replayed exactly as RoyaleImitate replays it):
- the environment is `rext_envs.build_env` (level 11, 15.535.29 arms, engine delay 27/27,
  RoyaleGym default observation and actions), so the shards' engine key is the PPO run's;
- sharding over processes: worker i reads parquet parts i, i+N, ...; `merge` joins the worker
  directories into one shard directory (the parts are untouched; the manifest is summed);
- a card-scope filter (`--scope`): `c56both` keeps a match only when both decks lie in our C56
  catalogue, `c56any` when one does (the other seat's rows are then dropped), `all` keeps every
  match RoyaleSim's catalogue holds;
- no-op subsampling: each no-op row is kept with probability `--noop-keep` p and weight 1/p
  (every play row is kept, weight 1). The weighted cross-entropy `clone` minimises is then an
  unbiased estimate of the full one, with about 3x fewer rows to read per epoch.

    learnvenv/bin/python -m bot.players.rext_imitate_replays stats --data-dir D --parts 2
    learnvenv/bin/python -m bot.players.rext_imitate_replays replay --data-dir D --out O \
        --worker 0 --workers 24 --matches 400 --scope c56both --noop-keep 0.25
    learnvenv/bin/python -m bot.players.rext_imitate_replays merge --out O
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

import numpy as np

# bot/fidelity/c56_native_ids.json mapped by royalesim_adapter.royalesim_card (RoyaleSim names).
C56 = frozenset((
    'AngryBarbarians', 'Archer', 'ArcherQueen', 'Arrows', 'BabyDragon', 'Balloon', 'BarbLog', 'Bats',
    'Berserker', 'BlowdartGoblin', 'BombTower', 'Cannon', 'DarkPrince', 'Earthquake', 'ElectroSpirit',
    'FireSpirits', 'Fireball', 'Firecracker', 'FirespiritHut', 'Ghost', 'Giant', 'GoblinBarrel',
    'GoblinGang', 'GoblinHut', 'Goblins', 'Goblinstein', 'Golem', 'HogRider', 'IceGolemite', 'IceSpirits',
    'InfernoTower', 'Knight', 'Lightning', 'Log', 'MightyMiner', 'Miner', 'MiniPekka', 'MinionHorde',
    'Minions', 'Musketeer', 'Poison', 'Prince', 'Princess', 'Rascals', 'Rocket', 'RoyalDelivery',
    'RoyalHogs', 'SkeletonArmy', 'Skeletons', 'Tesla', 'Tornado', 'Valkyrie', 'Wallbreakers', 'Wizard',
    'Xbow', 'Zap'))
AGENTS = ('blue', 'red')


def parts_of(data_dir, worker=0, workers=1, first_part=0):
    parts = sorted(Path(data_dir).glob('replays/*.parquet'))[first_part:]
    if not parts:
        raise SystemExit(f'{data_dir} has no replays/*.parquet')
    return parts[worker::workers]


def payloads(parts):
    import pyarrow.parquet as pq
    for part in parts:
        table = pq.ParquetFile(part)
        for batch in table.iter_batches(columns=['payload_json'], batch_size=256):
            for text in batch.column(0).to_pylist():
                yield json.loads(text)


def scope_seats(plan, scope):
    """Seats whose rows are kept under `scope`, or () to skip the match."""
    inside = [set(deck) <= C56 for deck in plan.decks]
    if scope == 'all':
        return (0, 1)
    if scope == 'c56both':
        return (0, 1) if all(inside) else ()
    if scope == 'c56any':
        return tuple(s for s in (0, 1) if inside[s])
    raise ValueError(scope)


def learner_for_env(scratch):
    """A Learner over rext_envs.build_env (same net config as rext_imitate_ppo), never trained."""
    from bot.players.rext_imitate_ppo import make_learner
    return make_learner(save_dir=scratch)


def stats(a):
    from royaleimitate.replays import match_plan
    from bot.players.rext_envs import X4S_DECKS
    catalogue = frozenset(_catalogue_names())
    counts, x4s = Counter(), Counter()
    xsets = [frozenset(d) for d in X4S_DECKS]
    for n, payload in enumerate(payloads(parts_of(a.data_dir)[: a.parts])):
        counts['matches'] += 1
        plan = match_plan(payload, catalogue)
        if isinstance(plan, str):
            counts['skip: ' + plan] += 1
            continue
        counts['planned'] += 1
        inside = [set(d) <= C56 for d in plan.decks]
        counts[f'c56 decks={sum(inside)}'] += 1
        for d in plan.decks:
            if frozenset(d) in xsets:
                x4s[xsets.index(frozenset(d))] += 1
        counts['plays'] += sum(len(p) for p in plan.plays)
    print(json.dumps(dict(counts), indent=1))
    print('x4s deck seats:', dict(x4s))


def _catalogue_names():
    from bot.players.rext_envs import make_engine
    return [card.name for card in make_engine().cards()]


def replay_match(env, battle, plan, seed, *, shift=0, retry=0):
    """royaleimitate.replays._replay (MIT, RoyaleGym org), with two changes for a command delay.

    - `shift`: a play recorded at tick t is made at the first decision at or after t - shift.
    - `retry`: a play the engine refuses at its decision (its card not yet back in hand, or its
      hand slot / elixir still held by a waiting command of the same seat, which a 27-tick
      engine delay makes common) waits at the head of the seat's queue for up to `retry` more
      decisions, the seat labelled the no-op meanwhile, instead of the match being skipped.
    Returns rows (agent, obs, action, step) or the reason the match is skipped, and the number
    of plays that had to wait.
    """
    from collections import deque
    from royalegym.protocol import EMPTY_CARD, MatchSetup, ShuffleMode
    from royaleimitate.replays import _UNITS_PER_TILE
    names = {card.name: card.card_id for card in battle.engine.cards()}
    parser = battle.action_parser
    tiles_x, tiles_y = parser.nx // parser.pitch_div, parser.ny // parser.pitch_div
    setup = MatchSetup(decks=[[names[name] for name in deck] for deck in plan.decks],
                       shuffle=int(ShuffleMode.NONE))
    obs, _info = env.reset(seed=seed, options={'setup': setup})
    waiting = [deque(plan.plays[0]), deque(plan.plays[1])]
    tries = [0, 0]
    delayed = 0
    rows = []
    step = 0
    while env.agents:
        state = battle.battle_state
        actions = {}
        for seat, agent in enumerate(AGENTS):
            action = 0
            queue = waiting[seat]
            if queue and queue[0].tick - shift <= state.tick:
                play = queue[0]
                hand = list(state.players[seat].hand)
                card = names[play.card]
                ok = card in hand and card != EMPTY_CARD
                if ok:
                    x = min(play.x * parser.nx // (tiles_x * _UNITS_PER_TILE), parser.nx - 1)
                    y = min(play.y * parser.ny // (tiles_y * _UNITS_PER_TILE), parser.ny - 1)
                    if seat == 1:  # Red acts in its own frame, turned half a turn
                        x, y = parser.nx - 1 - x, parser.ny - 1 - y
                    action = parser.encode(hand.index(card), x, y)
                    ok = bool(obs[agent]['action_mask'][action])
                if ok:
                    queue.popleft()
                    delayed += tries[seat] > 0
                    tries[seat] = 0
                else:
                    action = 0
                    tries[seat] += 1
                    if tries[seat] > retry:
                        return ('card not in hand' if card not in hand else 'play refused by the engine'), delayed
            actions[agent] = action
            rows.append((agent, {k: np.array(v) for k, v in obs[agent].items()}, action, step))
        obs, _rewards, _terminated, _truncated, _info = env.step(actions)
        step += 1
    return rows, delayed


def replay(a):
    from royaleimitate.replays import _battle_env, match_plan
    from royaleimitate.shards import ShardContext, ShardWriter
    import tempfile
    t0 = time.time()
    with tempfile.TemporaryDirectory() as scratch:
        learner = learner_for_env(scratch)
        env = learner.build_env()
        battle = _battle_env(env)
        catalogue = frozenset(card.name for card in battle.engine.cards())
        context = ShardContext.of_config(learner.config)
    rng = np.random.default_rng(1_000_003 * a.seed + a.worker)
    skipped, kept_rows = Counter(), Counter()
    written = rows = 0
    producer = {'tool': 'bot.players.rext_imitate_replays (royaleimitate.replays match_plan/_replay)',
                'dataset': f'VanguardX101/IL_Replay local copy {a.data_dir}', 'scope': a.scope,
                'noop_keep': a.noop_keep, 'shift': a.shift, 'retry': a.retry, 'worker': a.worker, 'workers': a.workers, 'first_part': a.first_part, 'seed': a.seed}
    out = Path(a.out) / f'w{a.worker:03d}'
    with ShardWriter(out, context, producer=producer) as writer:
        for index, payload in enumerate(payloads(parts_of(a.data_dir, a.worker, a.workers, a.first_part))):
            if written >= a.matches:
                break
            plan = match_plan(payload, catalogue)
            if isinstance(plan, str):
                skipped[plan] += 1
                continue
            seats = scope_seats(plan, a.scope)
            if not seats:
                skipped['out of scope'] += 1
                continue
            replayed, delayed = replay_match(env, battle, plan, a.worker * 10_000_000 + index,
                                             shift=a.shift, retry=a.retry)
            kept_rows['plays delayed'] += delayed
            if isinstance(replayed, str):
                skipped[replayed] += 1
                continue
            group = int(plan.tag[:15], 16)
            for agent, obs, action, step in replayed:
                seat = AGENTS.index(agent)
                if seat not in seats:
                    continue
                if action == 0:
                    if rng.random() >= a.noop_keep:
                        kept_rows['noop dropped'] += 1
                        continue
                    weight = 1.0 / a.noop_keep
                    kept_rows['noop kept'] += 1
                else:
                    weight = 1.0
                    kept_rows['play'] += 1
                writer.add(obs, action=action, weight=weight, group=group, seat=seat, tick=step)
                rows += 1
            written += 1
            if written % 50 == 0:
                print(f'{written} matches, {rows} rows, {sum(skipped.values())} skipped, '
                      f'{time.time() - t0:.0f} s', flush=True)
        writer.manifest.producer.update({'matches': written, 'rows': rows, 'row_kinds': dict(kept_rows),
                                         'skipped': dict(sorted(skipped.items()))})
    env.close()
    print(f'DONE worker {a.worker}: {written} matches, {rows} rows {dict(kept_rows)}; skipped {dict(skipped)}; '
          f'{time.time() - t0:.0f} s', flush=True)


def merge(a):
    """Join <input>/w*/<engine key>/ of every input root (default: --out) into out/merged/<engine key>/
    (the parts are symlinked, untouched)."""
    import msgspec
    from royaleimitate.shards import MANIFEST_NAME, ShardManifest
    root = Path(a.out)
    dirs = sorted(p.parent.resolve() for r in (a.inputs or [a.out]) for p in Path(r).glob('w*/*/' + MANIFEST_NAME))
    if not dirs:
        raise SystemExit('no finished worker shard directories')
    manifests = [msgspec.json.decode((d / MANIFEST_NAME).read_bytes(), type=ShardManifest) for d in dirs]
    keys = {m.engine_key for m in manifests}
    if len(keys) != 1:
        raise SystemExit(f'workers disagree on the engine key: {keys}')
    key = keys.pop()
    target = root / 'merged' / key
    target.mkdir(parents=True, exist_ok=False)
    first = manifests[0]
    merged = msgspec.structs.replace(first, parts=[], rows=0, validation_rows=0, flag_counts={},
                                     producer={'tool': 'rext_imitate_replays merge', 'workers': []})
    for d, m in zip(dirs, manifests):
        for part in m.parts:
            link = target / f'{d.parent.parent.name}-{d.parent.name}-{part.name}'
            link.symlink_to(d / part.name)
            merged.parts.append(msgspec.structs.replace(part, name=link.name))
        merged.rows += m.rows
        merged.validation_rows += m.validation_rows
        for flag, count in m.flag_counts.items():
            merged.flag_counts[flag] = merged.flag_counts.get(flag, 0) + count
        merged.producer['workers'].append(m.producer)
    (target / MANIFEST_NAME).write_bytes(msgspec.json.format(msgspec.json.encode(merged), indent=1))
    print(f'merged {len(dirs)} workers: {merged.rows} rows ({merged.validation_rows} validation) -> {target}')


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('stats')
    s.add_argument('--data-dir', required=True)
    s.add_argument('--parts', type=int, default=1)
    r = sub.add_parser('replay')
    r.add_argument('--data-dir', required=True)
    r.add_argument('--out', required=True)
    r.add_argument('--worker', type=int, default=0)
    r.add_argument('--first-part', type=int, default=0, help='skip the first parquet parts (a disjoint batch)')
    r.add_argument('--workers', type=int, default=1)
    r.add_argument('--matches', type=int, default=100, help='matches written by this worker')
    r.add_argument('--scope', default='c56both', choices=('all', 'c56both', 'c56any'))
    r.add_argument('--noop-keep', type=float, default=0.25)
    r.add_argument('--seed', type=int, default=20261014)
    r.add_argument('--shift', type=int, default=0, help='make each play this many ticks before its recorded tick')
    r.add_argument('--retry', type=int, default=0, help='decisions a refused play may wait')
    m = sub.add_parser('merge')
    m.add_argument('--out', required=True)
    m.add_argument('--inputs', nargs='*', help='roots holding w*/ worker directories (default: --out)')
    a = ap.parse_args()
    {'stats': stats, 'replay': replay, 'merge': merge}[a.cmd](a)


if __name__ == '__main__':
    main()
