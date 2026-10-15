"""Dense card-level labels (exploration tier) -> compact per-match npz.

Unit identity = the spawning card (object card_id -> C56 card name), towers by native
anchor. Every hit-point-bearing object is a positive except Ghost (invisible phases)
and unknown card ids, which become ignore regions. Objects without HP (projectiles,
spell areas) are background. Train/validation only, guarded by the frozen split.

Round 2 (--r2, live-dense-v2 vocabulary): objects without HP that belong to a spell card become positives of
an EFFECT identity 'fx:<spell>' (appended after the towers; frame-level spell supervision, never a unit), and Royal
Ghost becomes a positive while it is stationary on its target (raw x,y == targetX,targetY) more than 20 ticks after
it first appeared: on the train rich snapshots that state is visible 87% of the time (moving: 27%), deploying is always
invisible. Other Ghost frames stay ignore regions.

  nice python live/perception/dense_labels.py --out /mpac/sdicks02/jobs/clasher/live-perception-20261014/labels --workers 12
  nice python live/perception/dense_labels.py --r2 --out /mpac/sdicks02/jobs/clasher/live-perc-r2-20261015/labels-r2 --workers 12
"""
import argparse
import gzip
import json
from multiprocessing import Pool
from pathlib import Path

import numpy as np

import common as C

TOWER_IDX = {'KingTower': 0, 'PrincessTower': 1}
IGNORE_CARDS = ('Ghost',)
EFFECTS = ('Arrows', 'BarbLog', 'Earthquake', 'Fireball', 'GoblinBarrel', 'Lightning', 'Log', 'Poison', 'Rocket',
           'RoyalDelivery', 'Tornado', 'Zap')
GHOST_SETTLE_TICKS = 20


def vocab(cards, effects=False):
    return list(cards)+['KingTower', 'PrincessTower']+(['fx:'+c for c in EFFECTS] if effects else [])


def build(args):
    ep, split, out = args[:3]
    r2 = len(args) > 3 and args[3]
    guard = C.HeldoutGuard()
    guard.check([ep])
    target = Path(out)/f'{ep}.npz'
    if target.exists():
        return ep, 'cached'
    receipt = C.load_receipt(guard, ep, split)
    cards = guard.cards; ids = json.loads(C.SPLIT.read_text())['ids']
    id2idx = {v: cards.index(k) for k, v in ids.items()}
    root = C.MATCHES/ep
    frames = C.read_jsonl(root/'frames.jsonl'); hud = {h['seq']: h for h in C.read_jsonl(root/'hud.jsonl')}
    n = len(frames)
    if n != receipt['frames']:
        raise ValueError('frame count')
    hand = np.full((n, 5), len(cards), np.int16); el_int = np.zeros(n, np.int8); el = np.zeros(n, np.float32)
    clock = np.zeros(n, np.float32); phase = np.zeros(n, np.int8); tick = np.zeros(n, np.float32)
    for i, f in enumerate(frames):
        h = hud[f['seq']]; tick[i] = (f['tick_lo']+f['tick_hi'])/2
        hand[i] = [cards.index(c) if c in cards else len(cards) for c in (*h['own_hand'], h['own_next_card'])]
        el_int[i] = h['displayed_integer_elixir']; el[i] = h['own_elixir']; clock[i] = h['clock']; phase[i] = h['phase']
    with gzip.open(root/'objects.jsonl.gz', 'rt') as f:
        rows = [json.loads(x) for x in f]
    rticks = np.asarray([r['tick'] for r in rows], np.float32)
    offsets = [0]; cols = []; first_seen = {}
    anchors = {(o, ax, ay): k for o, k, s, ax, ay in C.TOWER_SLOTS}
    for r in rows:
        for o in r['objects']:
            hp = o['hp'] if o['hp'] is not None else -1; mx = o['max_hp'] if o['max_hp'] is not None else -1
            if o['card_id'] == -1:
                kind = anchors.get((o['owner'], o['x'], o['y']))
                if kind is None:
                    if mx > 0:
                        cls, flag = -1, 0  # unresolved HP object: ignore
                    else:
                        continue
                else:
                    if hp <= 0:
                        continue  # destroyed tower: background
                    cls, flag = len(cards)+TOWER_IDX['KingTower' if kind == 'king' else 'PrincessTower'], 1
            else:
                cls = id2idx.get(o['card_id'], -1)
                if mx <= 0:
                    if r2 and cls >= 0 and cards[cls] in EFFECTS:   # spell area / projectile: effect identity
                        cols.append((len(cards)+2+EFFECTS.index(cards[cls]), o['owner'], o['x'], o['y'], -1, -1, 1))
                    continue  # projectile / spell area: background
                flag = 1 if (cls >= 0 and cards[cls] not in IGNORE_CARDS and hp > 0) else 0
                if r2 and cls >= 0 and cards[cls] == 'Ghost' and hp > 0:
                    t0 = first_seen.setdefault(o.get('native_id'), r['tick'])
                    raw = o.get('raw') or {}
                    still = (raw.get('targetX'), raw.get('targetY')) == (o['x'], o['y'])
                    flag = int(still and r['tick']-t0 > GHOST_SETTLE_TICKS)
            cols.append((cls, o['owner'], o['x'], o['y'], hp, mx, flag))
        offsets.append(len(cols))
    objs = np.asarray(cols, np.int32).reshape(-1, 7)
    # nearest previous object row per frame within 5 ticks
    j = np.clip(np.searchsorted(rticks, tick, side='right')-1, 0, len(rticks)-1)
    row = np.where(np.abs(rticks[j]-tick) <= 5, j, -1).astype(np.int32)
    tmp = target.with_suffix('.tmp.npz')
    np.savez(tmp, hand=hand, elixir_int=el_int, elixir=el, clock=clock, phase=phase, tick=tick, row=row,
             offsets=np.asarray(offsets, np.int32), objects=objs, split=np.asarray(split), episode=np.asarray(ep))
    tmp.replace(target)
    return ep, 'built'


def load(path):
    z = np.load(path)
    return {k: z[k] for k in z.files}


def frame_objects(lab, i):
    """(positives [K,6]: cls, owner, x_tiles, y_tiles, hp_frac, is_tower) , ignore [M,2] xy tiles) or None if stale."""
    r = int(lab['row'][i])
    if r < 0:
        return None
    o = lab['objects'][lab['offsets'][r]:lab['offsets'][r+1]]
    pos = o[o[:, 6] == 1]; ign = o[o[:, 6] == 0]
    frac = np.clip(pos[:, 4]/np.maximum(pos[:, 5], 1), 0, 1)
    return pos[:, 0], pos[:, 1], pos[:, 2]/1000., pos[:, 3]/1000., frac, ign[:, 2:4]/1000.


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--workers', type=int, default=12); p.add_argument('--splits', default='train,validation')
    p.add_argument('--r2', action='store_true', help='effect identities + stationary-Ghost positives (live-dense-v2)')
    a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    guard = C.HeldoutGuard()
    jobs = [(ep, s, str(a.out), a.r2) for s in a.splits.split(',') for ep in guard.episodes(s)]
    guard.check([j[0] for j in jobs])
    with Pool(a.workers) as pool:
        for k, (ep, status) in enumerate(pool.imap_unordered(build, jobs)):
            if k % 50 == 0:
                print(k, len(jobs), ep, status, flush=True)
    (a.out/'vocab.json').write_text(json.dumps(dict(identities=vocab(guard.cards, a.r2), cards=guard.cards,
                                                    note='identity index = card index (C56 order from split.json) + KingTower, PrincessTower'))+'\n')
    print('done', len(jobs), flush=True)
