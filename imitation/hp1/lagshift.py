"""HP1 command-lag label overlay (reports/bot/hp1/DESIGN.md section 2.5). Read-only on the store.

Human labels are the human's own play ticks, replayed with no command delay. Our sim and the live loop execute a
command DELAY = 27 ticks after it is submitted, through a capacity-1 channel (bot/players/ours.py: ready commands
execute first, then the poll; a seat can act only when the channel is free, i.e. at ticks >= the pending command's due
tick). This module re-times each supervised human PLAY, in order within its perspective, to the decision row a lagged
player would have needed. With free = due tick of the previous re-timed command (-inf for the first):

  1. earliest row q with max(tick[p] - MAX_SHIFT, free) <= tick[q] < tick[p] that is a supervised WAIT row in the
     original labels, holds the played card in slots 0-3, and has the same tile legal for that slot (shifted earlier);
  2. else p itself if tick[p] >= free (fallback, unshifted);
  3. else (p falls while the channel is still busy) the earliest such row q with free <= tick[q] <= tick[p] + MAX_SHIFT
     and q before the perspective's next original play (delayed);
  4. else the play is dropped (p becomes unsupervised).
Its command is submitted at tick[q] and due at tick[q] + DELAY.

Labels: q gets slot_of_card(q) * 576 + tile and weight[p]. Rows with submit < tick < due (channel busy) become
unsupervised. A play's original row p that is not its target becomes WAIT (weight[p]; unsupervised if busy or if WAIT
is illegal there). p is never pre-thinned, so its weight carries no x2 wait-store factor, and with T11's sampling
(S122 waits kept with p 0.5, weight x0.5) and T4's x4 the expected weight of a converted row equals weight[p].
S122 perspectives are pre-thinned (50% of waits stored), so every window is defined in ticks, not rows.

    python -m imitation.hp1.lagshift --store .../v2-store-v1/train --out OVERLAY_DIR [--max-shift 30] [--delay 27]

Writes OVERLAY_DIR/{expert_actions,expert_action_supervision_valid,weights}.npy and overlay.json (parameters,
store/role/mask-table hashes, statistics, output SHA256). The trainer (imitation.hp1.train --overlay) verifies them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

WAIT = 2304
CADENCE = 5                 # decision rows are >= 5 ticks apart (checked), so a window of W ticks spans <= W/5 + 1 rows


def horizon(max_shift, delay):
    """Rows to scan so every row within max(max_shift, delay) ticks is seen (windows themselves are in ticks)."""
    if not (0 < max_shift <= 120 and 0 < delay <= 120):
        raise ValueError('max_shift and delay must be in (0, 120] ticks')
    return max(max_shift, delay) // CADENCE + 1


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def legal_bits(mask_table, mask_index_rows, actions):
    """mask_table rows are np.packbits(..., bitorder='big') of the 2306-bit action mask."""
    actions = np.asarray(actions, np.int64)
    byte = mask_table[mask_index_rows, actions >> 3]
    return ((byte >> (7 - (actions & 7))) & 1).astype(bool)


def check_layout(episode_ids, ticks):
    """Each perspective is one contiguous block of rows with strictly increasing ticks."""
    same = episode_ids[1:] == episode_ids[:-1]
    if (np.diff(ticks)[same] < CADENCE).any():
        raise ValueError(f'ticks not increasing by >= {CADENCE} within a perspective (decision cadence)')
    starts = np.concatenate(([0], np.flatnonzero(~same) + 1))
    if len(np.unique(episode_ids[starts])) != len(starts):
        raise ValueError('a perspective is split into several row blocks')


def _candidates(a, p, rows, lo, hi, card, tile, nxt):
    """Vectorised check of candidate rows (same perspective, lo <= tick <= hi, supervised original WAIT, before the
    perspective's next original play, card in slots 0-3, same tile legal). Returns (ok, action)."""
    ea, ok, ep, st, hid, mi, mt = a
    n = len(ea)
    inb = (rows >= 0) & (rows < n)
    qq = np.where(inb, rows, 0)
    cand = inb & (ep[qq] == ep[p]) & (st[qq] >= lo) & (st[qq] <= hi) & ok[qq] & (ea[qq] == WAIT) & (qq < nxt)
    match = hid[qq, :4] == card[:, None]
    cand &= match.any(1)
    qact = match.argmax(1).astype(np.int64) * 576 + tile
    cand &= legal_bits(mt, mi[qq], qact)
    return cand, qact


def compute_overlay(a, max_shift=30, delay=27):
    """a: dict of in-memory arrays expert_actions, expert_action_supervision_valid, weights, episode_ids,
    submitted_ticks, hand_ids (N,5), mask_index, mask_table, corpus_s122. Returns (actions, supervised, weights, stats)."""
    ea = np.asarray(a['expert_actions']); ok = np.asarray(a['expert_action_supervision_valid']).astype(bool)
    w = np.asarray(a['weights']); ep = np.asarray(a['episode_ids']); st = np.asarray(a['submitted_ticks']).astype(np.int64)
    hid = np.asarray(a['hand_ids']); mi = np.asarray(a['mask_index']); mt = np.asarray(a['mask_table'])
    cs = np.asarray(a['corpus_s122']).astype(bool)
    n = len(ea)
    check_layout(ep, st)
    lookback = horizon(max_shift, delay)
    arrays = (ea, ok, ep, st, hid, mi, mt)
    plays = np.flatnonzero(ok & (ea >= 0) & (ea < WAIT)).astype(np.int64)
    m = len(plays)
    first = np.ones(m, bool); first[1:] = ep[plays[1:]] != ep[plays[:-1]]
    group = np.cumsum(first) - 1                                   # perspective ordinal of each play
    starts = np.flatnonzero(first)
    ordinal = np.arange(m) - starts[group]                         # play ordinal within its perspective
    nxt = np.full(m, n, np.int64)                                  # next original play row of the same perspective
    has_next = np.zeros(m, bool); has_next[:-1] = ~first[1:]       # the next play belongs to the same perspective
    nxt[:-1][has_next[:-1]] = plays[1:][has_next[:-1]]
    free = np.full(len(starts), np.iinfo(np.int64).min // 2, np.int64)
    target = np.full(m, -1, np.int64); new_action = np.full(m, -1, np.int64); kind = np.zeros(m, np.int8)
    for k in range(int(ordinal.max()) + 1 if m else 0):
        j = np.flatnonzero(ordinal == k)
        p = plays[j]; g = group[j]; fr = free[g]
        act = ea[p].astype(np.int64); slot, tile = act // 576, act % 576
        card = hid[p, slot]
        tq = np.full(len(j), -1, np.int64); ta = np.full(len(j), -1, np.int64)
        lo = np.maximum(st[p] - max_shift, fr)
        for back in range(lookback, 0, -1):                        # earliest first; keep the first hit
            c, qa = _candidates(arrays, p, p - back, lo, st[p] - 1, card, tile, nxt[j])
            hit = c & (tq < 0)
            tq[hit] = (p - back)[hit]; ta[hit] = qa[hit]
        kd = np.where(tq >= 0, 1, 0).astype(np.int8)
        fallback = (tq < 0) & (st[p] >= fr)
        tq[fallback] = p[fallback]; ta[fallback] = act[fallback]; kd[fallback] = 2
        late = tq < 0
        for fwd in range(1, lookback + 1):                         # channel still busy at tick[p]: earliest free row
            if not late.any():
                break
            c, qa = _candidates(arrays, p, p + fwd, fr, st[p] + max_shift, card, tile, nxt[j])
            hit = c & late & (tq < 0)
            tq[hit] = (p + fwd)[hit]; ta[hit] = qa[hit]; kd[hit] = 3
        target[j] = tq; new_action[j] = ta; kind[j] = kd
        placed = tq >= 0
        free[g[placed]] = st[tq[placed]] + delay                   # dropped plays leave the channel as it was
    out_a, out_ok, out_w = ea.copy(), ok.copy(), w.copy()
    placed = target >= 0
    moved = placed & (target != plays)
    # original play rows that are not their own target: WAIT (or unsupervised if WAIT is illegal) / dropped plays
    out_a[plays[moved]] = WAIT
    out_ok[plays[moved]] = legal_bits(mt, mi[plays[moved]], np.full(int(moved.sum()), WAIT))
    out_ok[plays[~placed]] = False
    tq = target[placed]
    out_a[tq] = new_action[placed]; out_w[tq] = w[plays[placed]]; out_ok[tq] = True
    # busy rows: same perspective, submit < tick < due
    busy_total = 0
    for fwd in range(1, lookback + 1):
        q = tq + fwd
        inb = q < n
        qq = np.where(inb, q, 0)
        busy = inb & (ep[qq] == ep[tq]) & (st[qq] < st[tq] + delay)
        if (busy & np.isin(qq, tq)).any():
            raise AssertionError('a command target falls inside another command busy window')
        busy_total += int((busy & out_ok[qq]).sum())
        out_ok[qq[busy]] = False
    dt = np.where(placed, st[plays] - st[np.where(placed, target, 0)], 0)
    stats = dict(rows=int(n), supervised_plays=int(m), max_shift_ticks=max_shift, delay_ticks=delay,
                 shifted_earlier=int((kind == 1).sum()), unshifted=int((kind == 2).sum()),
                 delayed=int((kind == 3).sum()), dropped=int((~placed).sum()),
                 dt_ticks={str(int(v)): int(c) for v, c in zip(*np.unique(dt[placed], return_counts=True))},
                 shifted_earlier_by_corpus={'c56': int(((kind == 1) & ~cs[plays]).sum()), 's122': int(((kind == 1) & cs[plays]).sum())},
                 plays_by_corpus={'c56': int((~cs[plays]).sum()), 's122': int(cs[plays].sum())},
                 busy_rows_made_unsupervised=busy_total,
                 supervised_plays_after=int((out_ok & (out_a >= 0) & (out_a < WAIT)).sum()),
                 supervised_rows_before=int(ok.sum()), supervised_rows_after=int(out_ok.sum()))
    if stats['supervised_plays_after'] != m - stats['dropped']:
        raise AssertionError('play count mismatch')
    return out_a, out_ok, out_w, stats


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--store', required=True, type=Path, help='a v2-store-v1 role directory (train)')
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--max-shift', type=int, default=30)
    ap.add_argument('--delay', type=int, default=27)
    a = ap.parse_args(argv)
    if a.store.name != 'train':
        ap.error('the overlay is defined for the train role only')
    if a.out.exists():
        ap.error(f'{a.out} exists; overlays are written once')
    root = a.store.parent
    names = ('expert_actions', 'expert_action_supervision_valid', 'weights', 'episode_ids', 'submitted_ticks',
             'hand_ids', 'mask_index', 'corpus_s122')
    arrays = {k: np.load(a.store / f'{k}.npy', mmap_mode='r') for k in names}
    arrays = {k: np.asarray(v) for k, v in arrays.items()}
    arrays['mask_table'] = np.load(root / 'mask_table.npy')
    out_a, out_ok, out_w, stats = compute_overlay(arrays, a.max_shift, a.delay)
    a.out.mkdir(parents=True)
    files = {}
    for name, value in (('expert_actions', out_a), ('expert_action_supervision_valid', out_ok), ('weights', out_w)):
        if value.dtype != arrays[name].dtype or value.shape != arrays[name].shape:
            raise AssertionError(name)
        np.save(a.out / f'{name}.npy', value)
        files[name] = sha256(a.out / f'{name}.npy')
    meta = dict(schema='clasher.hp1.lag-overlay.v1', max_shift_ticks=a.max_shift, delay_ticks=a.delay, lookback_rows=horizon(a.max_shift, a.delay),
                store_manifest_sha256=sha256(root / 'manifest.json'), role_manifest_sha256=sha256(a.store / 'manifest.json'),
                mask_table_sha256=sha256(root / 'mask_table.npy'), files=files, stats=stats)
    (a.out / 'overlay.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(json.dumps(stats), flush=True)


if __name__ == '__main__':
    main()
