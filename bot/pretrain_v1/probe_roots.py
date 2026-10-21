"""Offline evaluation hook (b): pretrain-v1 policy distributions at the defense / spell audit roots.

    python -m bot.pretrain_v1.probe_roots --ckpt CKPT --out probe.json [--window 60]

Inputs (frozen, read-only):
  /mpac/sdicks02/scratch/defense-failures-20261020/events.json      453 threat groups (root = first_root_tick)
  /mpac/sdicks02/scratch/spell-usage-20261020/opportunities.json    957 spell opportunities (root = best.tick)
  the c17 / c18 live recordings they reference (records.jsonl as frozen by the defense audit where available, else
  the mirror; decisions.jsonl for our accepted commands; projectiles.jsonl for in-flight carrier aims).

Each recording is replayed in order through featurize.observe with History driven by the live bot's ACCEPTED taps
(tap_id present), exactly the channel that game had. RF extras: carriers (aim, flown) are rebuilt from the
projectile log (first sight of each id); unit first-seen ages are not logged (no ids), so they are missing, the
state the BC model is trained on with probability .05. At every root the policy's distribution is read off:
P(play) at the root poll and P(any play within `window` ticks) along the RECORDED states (survival product over the
logged polls), P(card) per hand card, and for spell roots P(that spell) and the tile mass within 1.5 tiles of the
audit's best target. These are state-conditional diagnostics on the search's own trajectory, not counterfactual
outcomes (DESIGN: captured-root action choices are diagnostic; consequences need a continued battle).
"""
from __future__ import annotations

import argparse
import gzip
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

from . import featurize as F
from .model import collate, tiles_ok_np
from .policy import load

DEF = Path('/mpac/sdicks02/scratch/defense-failures-20261020')
SPELL = Path('/mpac/sdicks02/scratch/spell-usage-20261020')
MIRROR = Path('/mpac/sdicks02/scratch/live-mem/mirror')


def _lines(p):
    op = gzip.open if str(p).endswith('.gz') else open
    with op(p, 'rt') as f:
        for line in f:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def replay(game, model, ticks_needed):
    """-> {tick: dist} for the polls in ticks_needed (and every poll, for windows)."""
    frozen = DEF/'inputs'/game/'records.jsonl.gz'
    recs = list(_lines(frozen if frozen.exists() else MIRROR/game/'records.jsonl'))
    dec = {d['tick']: d for d in _lines(MIRROR/game/'decisions.jsonl')}
    # carrier flight ages per LIFETIME, as FrameBuilder.proj tracks them: a lifetime ends when the id is absent from a
    # logged row (the log has a row for every frame with any non-body entity; a frame without one ends them all) or
    # comes back with another card / owner (reader ids are reused)
    carriers, life = defaultdict(list), {}
    proj = MIRROR/game/'projectiles.jsonl'
    if proj.exists():
        last_t = None
        for row in _lines(proj):
            t = row['tick']
            present = {o[0] for o in row['o']}
            if last_t is not None and t - last_t > 3:
                life.clear()                              # unlogged frames in between: no non-body entity existed
            for uid in [u for u in life if u not in present]:
                del life[uid]
            for o in row['o']:
                ident = (o[1], o[2])
                if o[0] not in life or life[o[0]][1] != ident:
                    life[o[0]] = (t, ident)
                if len(o) >= 8 and isinstance(o[2], str) and o[2] in F.catalog().carriers:
                    carriers[t].append((int(o[1]), o[2], float(o[4]), float(o[5]), float(o[6]), float(o[7]),
                                        t - life[o[0]][0]))
            last_t = t
    h = F.History()
    out = {}
    last = None
    for r in recs:
        t = r['tick']
        if last is not None and t <= last:
            continue                                     # a logged continuation: keep the first record per tick
        gap = t - last if last is not None else F.POLL
        last = t
        extras = dict(first_seen=None, spells=carriers.get(t, []) if proj.exists() else None)
        try:
            feat = F.observe(r, extras, h)
        except F.FeatureError:
            h = F.History()
            continue
        out[t] = dist(model, feat, r, gap)
        d = dec.get(t)
        if d and d.get('submitted') and 'tap_id' in d and d.get('slot') is not None and h.pending is None:
            h.submit(t, int(d['slot']), d['card'], int(d['action']) % F.NTILE)
    return out


@torch.inference_mode()
def dist(model, feat, rec, gap=F.POLL):
    """The distribution policy.Session would sample at this poll: survival-scaled gate p_wait5**(gap/5) with
    gap clipped to [1, 10], play mass redistributed over slots proportionally; stale (gap > 10) or all-masked polls
    are declined (p_wait 1)."""
    from .policy import STALE_GAP
    b = collate([feat])
    cls, hand = model.trunk(b)
    p = torch.softmax(model.gate_logits(cls, hand, b['slot_ok'])[0], -1).double().numpy()
    if not feat['slot_ok'].any() or gap > STALE_GAP:
        p = np.r_[1.0, np.zeros(4)]
    else:
        pw = p[0]**(min(max(gap, 1), STALE_GAP)/F.POLL)
        play = p[1:]/max(p[1:].sum(), 1e-12)*(1 - pw)
        p = np.r_[pw, play]
    tok = torch.from_numpy(tiles_ok_np(feat['hand'][None], feat['slot_ok'][None], feat['alive'][None]))
    tiles = {}
    for s in range(4):
        if feat['slot_ok'][s]:
            z = model.tile_logits(cls, hand, torch.tensor([s]), tok[:, s])[0]
            tiles[rec['hand']['cards'][s]] = torch.softmax(z, -1).double().numpy()
    v = torch.softmax(model.value(cls)[0], -1).numpy()
    return dict(p_wait=float(p[0]), p_card={rec['hand']['cards'][s]: float(p[1 + s]) for s in range(4)},
                legal=[rec['hand']['cards'][s] for s in range(4) if feat['slot_ok'][s]], tiles=tiles,
                value=float(v[2] - v[0]))


def tile_mass_near(probs, xy, r=1.5):
    if probs is None or xy is None:
        return 0.0
    c = np.arange(F.NTILE)
    d = np.hypot(c % F.W + .5 - xy[0], c//F.W + .5 - xy[1])
    return float(probs[d <= r].sum())


def window_play(dists, t0, window):
    """P(at least one play in [t0, t0 + window]) along the recorded polls (survival product of p_wait)
    -> (probability or None, polls, covered ticks, truncated?). Truncated = the recording ends before t0 + window."""
    ts = [t for t in sorted(dists) if t0 <= t <= t0 + window]
    if not ts:
        return None, 0, 0, True
    surv = 1.0
    for t in ts:
        surv *= dists[t]['p_wait']
    last = max(dists)
    return 1 - surv, len(ts), ts[-1] - ts[0], last < t0 + window


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--ckpt', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--window', type=int, default=60)
    ap.add_argument('--limit-games', type=int, default=0)
    a = ap.parse_args(argv)
    torch.set_num_threads(4)
    model, ck = load(a.ckpt)
    events = json.loads((DEF/'events.json').read_text())
    opps = json.loads((SPELL/'opportunities.json').read_text())
    games = sorted({e['game'] for e in events} | {o['game'] for o in opps})
    if a.limit_games:
        games = games[:a.limit_games]
    dists = {}
    for g in games:
        if not (MIRROR/g/'records.jsonl').exists() and not (DEF/'inputs'/g/'records.jsonl.gz').exists():
            continue
        dists[g] = replay(g, model, None)
    res = dict(ckpt=a.ckpt, feature_hash=F.feature_hash(), games=len(dists), window=a.window, defense={}, spell={},
               coverage={})
    by = defaultdict(list)
    cov = dict(assigned=len(events), no_recording=0, no_root_tick=0, root_offset_gt5=0, window_unknown=0,
               window_truncated=0, observed=0)
    for e in events:
        d = dists.get(e['game'], {})
        t0 = e.get('first_root_tick')
        if not d:
            cov['no_recording'] += 1
            continue
        if t0 is None:
            cov['no_root_tick'] += 1
            continue
        rt = t0 if t0 in d else min(d, key=lambda t: abs(t - t0))
        off = abs(rt - t0)
        cov['root_offset_gt5'] += int(off > 5)
        pw, n, span, trunc = window_play(d, t0, a.window)
        cov['window_truncated'] += int(trunc)
        if pw is None:
            cov['window_unknown'] += 1                 # kept out of every mean, never counted as zero
            continue
        if trunc or off > 5:                           # partial coverage: a diagnostic, not a full-window estimate
            cov.setdefault('partial', []).append(dict(id=e['id'], root_offset=off, covered_ticks=span,
                                                      p_play_partial=pw))
            continue
        cov['observed'] += 1
        root = d[rt]
        spell_mass = sum(root['p_card'].get(c, 0) for c in ('Zap', 'Fireball'))
        bld = root['p_card'].get('Cannon', 0)
        by[e['class']].append((1 - root['p_wait'], pw, spell_mass, bld, bool(e.get('direct_affordable'))))
        by['ALL'].append(by[e['class']][-1])
        if e['card'] == 'GoblinBarrel':
            by['card:GoblinBarrel'].append(by[e['class']][-1])
    for k, v in sorted(by.items()):
        arr = np.array(v, dtype=float)
        res['defense'][k] = dict(n=len(v), p_play_root=float(arr[:, 0].mean()), p_play_window=float(arr[:, 1].mean()),
                                 p_spell_root=float(arr[:, 2].mean()), p_cannon_root=float(arr[:, 3].mean()))
    res['coverage']['defense'] = cov
    sb = defaultdict(list)
    cov = dict(assigned=len(opps), no_recording=0, no_root_tick=0, root_offset_gt5=0, window_unknown=0,
               window_truncated=0, observed=0)
    for o in opps:
        d = dists.get(o['game'], {})
        best = o.get('best') or {}
        t0 = best.get('tick', o.get('start'))
        if not d:
            cov['no_recording'] += 1
            continue
        if t0 is None:
            cov['no_root_tick'] += 1
            continue
        rt = t0 if t0 in d else min(d, key=lambda t: abs(t - t0))
        off = abs(rt - t0)
        cov['root_offset_gt5'] += int(off > 5)
        if off > 5:                                    # the root poll itself is not observed: excluded, listed
            cov.setdefault('partial', []).append(dict(id=o['id'], root_offset=off))
            continue
        root = d[rt]
        pw, _, span, trunc = window_play(d, t0, a.window)
        cov['window_truncated'] += int(trunc)
        cov['window_unknown'] += int(pw is None)
        if trunc and pw is not None:                   # root-poll metrics stay; the window estimate is partial
            cov.setdefault('partial', []).append(dict(id=o['id'], covered_ticks=span, p_play_partial=pw))
            pw = None
        cov['observed'] += 1
        ps = root['p_card'].get(o['spell'], 0.0)
        near = tile_mass_near(root['tiles'].get(o['spell']), best.get('xy'))
        key = f"{o['kind']}|{o['spell']}"
        legal = o['spell'] in root['legal']
        sb[key].append((ps, near, float('nan') if pw is None else pw, legal))
        sb['ALL'].append(sb[key][-1])
    for k, v in sorted(sb.items()):
        arr = np.array(v, dtype=float)
        leg = arr[arr[:, 3] > 0]
        res['spell'][k] = dict(n=len(v), legal=int(arr[:, 3].sum()),
                               p_spell_root_legal=float(leg[:, 0].mean()) if len(leg) else None,
                               tile_mass_near_best_legal=float(leg[:, 1].mean()) if len(leg) else None,
                               p_play_window=float(np.nanmean(arr[:, 2])) if np.isfinite(arr[:, 2]).any() else None,
                               window_unknown=int(np.isnan(arr[:, 2]).sum()))
    res['coverage']['spell'] = cov
    Path(a.out).write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
