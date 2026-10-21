"""Native re-drive output -> live memory records -> pretrain-v1 features + lag-aligned imitation / value labels.

    python -m bot.pretrain_v1.dataset build [--src DIR] [--jobs DIR] [--out DIR] [--workers N] [--limit-batches N]

Incremental: one output shard per sealed, acked re-drive batch (`acked.txt`, `receipts/batch-*.json`); batches already
in OUT/MANIFEST.jsonl are skipped, so re-running picks up newly synced batches. Each shard is written to a temporary
directory and renamed into place; MANIFEST.jsonl is append-only.

Per match and seat (both perspectives of one physical match always share a split):
  1. Each raw native frame (5-tick grid) is rewritten as the reader's PRIVATE frame for that seat (own elixir / hand /
     next only, every entity row, projectile targets) and passed through parse_line + FrameBuilder.frame of the
     vendored, hash-pinned deployed live/mem/state.py, exactly as the live loop does; RF extras are the builder's
     unit_first_seen and spells, as memloop hands them to rfextras. Polling stops when FrameBuilder.decided() (live
     deauthorises there) or at the client's end tick.
  2. featurize.observe() on every poll, with History driven like the live command channel.
  3. Labels (DESIGN "Action timing"): a human play executed at E is a decision at d* = the latest poll <= E - 27.
     It is admitted only if, at d*: every ordinary-cycle opening assignment compatible with the seat's whole play
     sequence gives the same own hand set and next card (PREREG 4; otherwise the native deal's hand may not be the
     human's), the card is in the observed hand, affordable from observed elixir (Mirror: its source card's cost +
     1), the channel is free (one outstanding command), and a legal tile centre lies within 0.75 tile of the
     original native coordinate (placement label quantised; replay coordinates untouched). Admitted: History.submit
     at d*, channel busy until the card leaves the hand. Not admitted: no actor loss on polls d*..E (never relabelled
     as WAIT) and the play still enters own history. Own ability events and non-executed source plays also blank
     d*..E. Every other eligible poll (channel free, some legal slot, hand unambiguous) is a natural WAIT. Busy /
     all-masked / ambiguous-hand polls have no actor loss but keep value targets. Rows at or after the first
     source event (either seat) the client did not plainly execute carry `unc` = 1 (coordinator data rule: exact /
     outcome tiers are used whole; the flag allows a qualified-prefix ablation).
  4. WAIT and forced no-op rows are retained with probability .1 (deterministic hash) and weight 10; plays are kept.
  5. Value W/D/L only for tiers exact / outcome (no early end; winner and crowns agree with the source).
  6. Domain weight .25 for own decks with any evolution / hero form (modern-form transfer), 1 for vanilla.
"""
from __future__ import annotations

import argparse
import bisect
import gzip
import itertools
import hashlib
import json
import math
import os
import shutil
import sys
import time
import traceback
import zlib
from collections import Counter, deque
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from . import featurize as F

HERE = Path(__file__).resolve().parent
VENDOR = HERE/'vendor'/'livemem'
SRC = Path('/mpac/sdicks02/datasets/native-redrive-20261021')
JOBS = Path('/mpac/sdicks02/scratch/native-redrive-full-20261021/jobs')
OUT = Path('/mpac/sdicks02/datasets/pretrain-v1')
SCHEMA = 'clasher.pretrain_v1.dataset.v1'
KEEP_WAIT = .1
DOMAIN_MODERN = .25
HOG_CORE = {'HogRider', 'Musketeer', 'Cannon', 'IceGolem', 'Skeletons', 'IceSpirit', 'Fireball'}
VALUE_TIERS = {'exact', 'outcome'}


def _state_module():
    import importlib.util
    path = VENDOR/'state.py'
    if hashlib.sha256(path.read_bytes()).hexdigest() != '9085e33798b009aed7e5f40e192fb80713cf7d21aa6958b2faf9145b61c6223c':
        raise SystemExit('vendored state.py does not match the deployed sha256 9085e337...')
    spec = importlib.util.spec_from_file_location('pv1_livemem_state', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ST = _state_module()
# Declared projection adaptation (the file stays byte-identical; these are its module constants). Live feeds the
# FrameBuilder about one reader frame per tick, so "absent from 20 / 40 complete frames" means ~20 / 40 ticks there;
# the re-drive has one frame per 5 ticks, where the same wall-clock rule is 4 / 8 frames. Native frames drop a
# destroyed tower's row (no 0-HP row), so without this a fallen tower stays alive in the record for 100 ticks.
ST.GONE_FRAMES, ST.STALE_FRAMES = 4, 8
BIND =json.loads((VENDOR/'binding-subset.json').read_text())
BINDING = SimpleNamespace(tile=1000, world_w=18000, world_h=32000, elixir_unit=10000,
                          screen_x_flip=BIND['screen_x_flip'],
                          tower_names={k: frozenset(v) | ({'ChefTowerKing'} if k == 'king' else set())
                                       for k, v in BIND['tower_names'].items()})
CARDS = VENDOR/'data'/'cards-122.json'
EXTRA = json.loads((VENDOR/'extra_bodies.json').read_text())
BY_ID, _ = ST.load_cards(CARDS)


def reader_frame(f, seat, token):
    """Raw native frame -> the reader's PRIVATE frame for `seat` (re-drive project.py, sha bedce0f2..., unchanged)."""
    p = next(x for x in f['p'] if x[0] == seat)
    _, elixir, hand, _, nxt, _ = p
    units = [[o[0], o[1], o[2], o[3], o[4], -1 if o[5] is None else o[5], -1 if o[6] is None else o[6], o[8] or '']
             for o in f['o']]
    proj = [[o[0], o[9], o[10]] for o in f['o'] if o[7] and o[7]//1000000 == 10]
    return dict(t=f['t'], b=token, s=seat, e=elixir, h=hand, n=nxt, u=units, p=proj, m=1 if f.get('tr') else 0)


def keep(key, seat, tick, p=KEEP_WAIT):
    h = hashlib.blake2b(f'{key}|{seat}|{tick}'.encode(), digest_size=8).digest()
    return int.from_bytes(h, 'little')/2**64 < p


def fingerprint(job):
    """Seat-swap-normalised physical-game fingerprint: decks (card, form, level), towers and the ordered commands."""
    def canon(swap):
        seats = (1, 0) if swap else (0, 1)
        decks = [sorted((c['slug'], c['form'], c['level']) for c in job['decks'][s]) for s in seats]
        tw = [(job['towers'][s]['slug'], job['towers'][s]['level']) for s in seats]

        def xy(e):                                  # the opposite seat's view is the board rotated 180 degrees
            x, y = e.get('x'), e.get('y')
            if swap and x is not None and y is not None:
                return 18000 - x, 32000 - y
            return x, y
        ev = [(e['tick'], seats.index(e['seat']), e['kind'], e.get('slug'), *xy(e)) for e in job['events']]
        return json.dumps([decks, tw, ev], separators=(',', ':'))
    return min(hashlib.sha256(canon(s).encode()).hexdigest() for s in (False, True))


def split_of(fp):
    b = int(fp[:8], 16) % 10
    return 'train' if b < 8 else 'dev' if b == 8 else 'final'


def deck_flags(names, forms):
    s = set(names)
    hog = HOG_CORE <= s and bool({'Log', 'Zap'} & s)
    return dict(hog26=int(hog), hog26_zap=int(hog and 'Zap' in s), vanilla=int(all(f == 'base' for f in forms)))


class Rows:
    def __init__(self):
        self.cols = {k: [] for k in ('tow', 'hand', 'glob', 'lag', 'slot_ok', 'alive', 'gate', 'slot', 'tile', 'actor',
                                     'w_ipw', 'w_dom', 'value', 'resid', 'match', 'seat', 'tick', 'why', 'unc')}
        self.ent, self.ev, self.rev = [], [], []
        self.resid_log = []                        # (card, placement residual in tiles) of admitted play labels

    def add(self, feat, **lab):
        self.ent.append(feat['ent'])
        self.ev.append(feat['ev'][feat['ev'][:, F.V_PRESENT] == 1])
        self.rev.append(feat['rev'][feat['rev'][:, F.R_PRESENT] == 1])
        for k in ('tow', 'hand', 'glob', 'lag', 'slot_ok', 'alive'):
            self.cols[k].append(feat[k])
        for k, v in lab.items():
            self.cols[k].append(v)

    def __len__(self):
        return len(self.cols['tick'])


WHY = {'wait': 0, 'play': 1, 'forced': 2, 'window': 3, 'busy': 4, 'ambiguous': 5}


START_TICK = 90                     # LiveSession / the sim harness poll from tick 90 (bot/players/base.py START_TICK)
NEVER_OPENING = {27000007}          # Elixir Collector is never dealt into the opening hand (re-drive prep.py)


def infer_cycle(seq, deck):
    """Every (opening hand set, queue front-first) under which each card of `seq` is in hand when played
    (origin/main:bot/simfid/rebuild.py infer_cycle, as the re-drive's prep.py uses it)."""
    found = []
    for hand in itertools.combinations(deck, 4):
        rest = [c for c in deck if c not in hand]
        for queue in itertools.permutations(rest):
            held, qd = set(hand), deque(queue)
            for card in seq:
                if card not in held:
                    break
                held.remove(card)
                held.add(qd.popleft())
                qd.append(card)
            else:
                found.append((hand, queue))
    return found


def cycle_agreement(job, seat):
    """Number of own plays after which EVERY compatible opening assignment gives the same own hand set and next card
    (PREREG 4: actor labels need agreement across surviving initial-hand candidates); None if never / no candidate."""
    deck = [c['d'] for c in job['decks'][seat]]
    seq = [e['d'] for e in job['events'] if e['seat'] == seat and e['kind'] == 'play']
    cands = [(h, qq) for h, qq in infer_cycle(seq, deck) if not set(h) & NEVER_OPENING]
    if not cands:
        return None
    for k in range(len(seq) + 1):
        states = set()
        for hand, queue in cands:
            held, qd = set(hand), deque(queue)
            for card in seq[:k]:
                held.remove(card)
                held.add(qd.popleft())
                qd.append(card)
            states.add((frozenset(held), qd[0]))
            if len(states) > 1:
                break
        if len(states) == 1:
            return k
    return None


def project(d, seat, stats, frames=None):
    """One perspective's POLICY polls with live semantics -> ([(record, extras)], FrameBuilder) or (None, None).

    As memloop + LiveSession: the FrameBuilder sees every frame from tick 0 (tracking, first sight), but the policy
    is polled only from START_TICK; a frame failing the reader schema (champion-cycle hand hole) is skipped; a
    FrameBuilder error ends the battle's decisions (live refuses the battle); the deciding record is never a poll
    (memloop deauthorises before stepping); a stale tower ends decisions (live disarms the gate)."""
    deck = sorted(d['result']['native_decks'][seat], key=lambda x: x['slot'])
    order = [BY_ID.get(x['card']) for x in deck]
    if None in order:
        stats['persp_deck_unmapped'] += 1
        return None, None
    b = ST.FrameBuilder(BINDING, order, CARDS, extra_bodies=EXTRA, spell_events=False, stats=Counter())
    token = zlib.crc32(d['key'].encode()) + 1
    end = d['labels'].get('native_end_tick') or 10**9
    recs = []
    for f in (d['frames'] if frames is None else frames):
        if f['t'] > end:
            break
        rf = reader_frame(f, seat, token)
        try:
            _, pf = ST.parse_line(json.dumps(rf))
        except (ValueError, ST.FrameError):
            stats['frame_schema_skip'] += 1
            continue
        try:
            rec = b.frame(pf)
        except ST.FrameError as ex:
            stats[f'frame_error_refuse:{str(ex)[:50]}'] += 1
            break
        if rec is None:
            stats['frame_unoriented'] += 1
            continue
        if b.stale is not None:
            stats['stale_tower_stop'] += 1
            break
        if b.decided(rec['tick']):
            break
        if rec['tick'] < START_TICK:
            continue
        recs.append((rec, dict(first_seen=list(b.unit_first_seen), spells=list(b.spells))))
    if not recs:
        stats['persp_no_records'] += 1
        return None, None
    return recs, b


def first_uncertainty(d):
    """Earliest execution tick of any source event (either seat) the client did not plainly execute: injected
    (unverified) abilities, plays not executed, pending at the end. Rows at or after it are flagged `unc`."""
    ticks = [int(e.get('E', e.get('tick', 0))) for e in d['result']['events'] if e.get('outcome') != 'executed']
    return min(ticks) if ticks else 10**9


def build_perspective(d, job, seat, rows, stats, mi, value, dom, trace=None):
    """Append one perspective's retained rows; `trace` (a list) receives, per poll, (tick, feature sha, admitted
    (slot, tile) or None, own-tile hints) -- every History call the builder made after observing that poll."""
    key = d['key']
    recs, b = project(d, seat, stats)
    if recs is None:
        return None
    end = d['labels'].get('native_end_tick') or 10**9
    res_by_i = {e['i']: e for e in d['result']['events']}
    attempts, blanks = [], []                       # attempts: every own source card play (executed or not)
    for e in job['events']:
        if e['seat'] != seat:
            continue
        r = res_by_i.get(e['i'], {})
        E = int(r.get('E', e['tick']))
        if e['kind'] == 'play' and e['tick'] <= end:
            attempts.append((E, e, r.get('outcome') == 'executed'))
        elif e['tick'] <= end:
            blanks.append(E)                        # ability events: no expressible action
    plays = [(E, e) for E, e, ok in attempts if ok]
    unc_t = first_uncertainty(d)
    k_agree = cycle_agreement(job, seat)
    exec_E = sorted(E for E, _ in plays)
    if k_agree is None:
        stats['persp_cycle_never_agrees'] += 1
    ticks = [r[0]['tick'] for r in recs]

    def agreed(t):
        # the k-th own play has certainly left the hand by E + 5 ("confirmed" in the re-drive receipts)
        return k_agree is not None and bisect.bisect_right(exec_E, t - 5) >= k_agree

    def dstar(E):
        i = bisect.bisect_right(ticks, E - F.COMMAND_LAG) - 1
        return ticks[i] if i >= 0 else None
    label_at, windows = {}, []
    for E, e, ok in sorted(attempts, key=lambda p: (p[0], p[1]['i'])):
        t = dstar(E)
        if t is None:
            windows.append((ticks[0], E))
            stats['label_no_poll'] += 1
            continue
        label_at.setdefault(t, []).append((E, e, ok))
    for E in blanks:
        t = dstar(E)
        windows.append((t if t is not None else ticks[0], E))
    cat = F.catalog()
    # unshifted audit (DESIGN: both label conventions are audited; only the lag-aligned one trains): card in hand and
    # affordable at the latest poll <= E itself
    by_tick = {r[0]['tick']: r[0] for r in recs}
    for E, e in plays:
        i = bisect.bisect_right(ticks, E) - 1
        if i < 0:
            continue
        r0 = by_tick[ticks[i]]
        card = BY_ID.get(e['d'])
        ok = card in r0['hand']['cards'] and r0['elixir'] + 1e-9 >= cat.cost[cat.card(card)]
        stats['unshifted_plays'] += 1
        stats['unshifted_ok'] += int(ok)
    hist = F.History()
    n0 = len(rows)
    for rec, extras in recs:
        t = rec['tick']
        try:
            feat = F.observe(rec, extras, hist)
        except F.FeatureError as ex:
            stats[f'feature_error:{str(ex)[:40]}'] += 1
            return None                                    # history broken: drop the rest of this perspective
        unc = int(t >= unc_t)
        # The channel is driven ONLY by what is observable at this poll (own hand, elixir, channel, geometry) and the
        # human's decision itself: never by its future execution, the opening-cycle agreement or the tile residual,
        # which decide only whether the row carries actor loss.
        lab, sub, hints = None, None, []
        for E, e, executed in label_at.get(t, ()):
            card = BY_ID.get(e['d'])
            sx, sy = b.screen(e['x'], e['y'])
            fallback = min(max(int(math.floor(sy)), 0), F.H - 1)*F.W + min(max(int(math.floor(sx)), 0), F.W - 1)
            why = None
            if sub is not None:
                why = 'second_play_same_poll'
            elif card not in rec['hand']['cards']:
                why = 'not_in_hand'
            else:
                slot = rec['hand']['cards'].index(card)
                if feat['glob'][F.G_BUSY]:
                    why = 'channel_busy'
                elif not feat['hand'][slot, F.H_AFFORD]:
                    why = 'unaffordable'
                elif not feat['slot_ok'][slot]:
                    why = 'no_legal_tile'
                else:
                    # the slot's effective placement (Mirror: its source card's) from the featurizer
                    mask = F.tile_mask(int(feat['hand'][slot, F.H_PLACE]), tuple(bool(a) for a in feat['alive']))
                    tile, resid = F.nearest_legal_tile(sx, sy, mask)
                    if tile is None:
                        why = 'tile_far'                   # not expressible at d*: no submission, a history hint
                    else:
                        assert mask[tile] and feat['slot_ok'][slot]
                        sub = (slot, tile, card)           # the channel rejects it by the shared record rule
                    if why is not None:
                        pass
                    elif not executed:
                        why = 'not_executed'
                    elif not agreed(t):
                        why = 'hand_ambiguous'
                    else:
                        lab = (slot, tile, resid, card)
                        rows.resid_log.append((card, resid))
            if executed:
                stats['plays'] += 1
                if why is None:
                    stats['label_ok'] += 1
                    stats['label_ok_unc'] += unc
            if why is not None:
                stats[f'label_reject:{why}'] += 1
                windows.append((t, E))
                if sub is None or sub[2] != card:          # no submission for this play: history learns it on hand
                    hist.hint_own_tile(card, fallback)     # departure (offline only)
                    hints.append((card, fallback))
        if trace is not None:
            trace.append((t, F.feature_bytes(feat), sub[:2] if sub is not None else None, tuple(hints)))
        if sub is not None:
            hist.submit(t, sub[0], sub[2], sub[1])
        if lab is not None:
            slot, tile, resid, card = lab
            rows.add(feat, gate=1, slot=slot, tile=tile, actor=1, w_ipw=1., w_dom=dom, value=value, resid=resid,
                     match=mi, seat=seat, tick=t, why=WHY['play'], unc=unc)
            continue
        if any(a <= t <= z for a, z in windows):
            kind = 'window'
        elif feat['glob'][F.G_BUSY]:
            kind = 'busy'
        elif not feat['slot_ok'].any():
            kind = 'forced'
        elif not agreed(t):
            kind = 'ambiguous'
        else:
            kind = 'wait'
        stats[f'poll:{kind}'] += 1
        if not keep(key, seat, t):
            continue
        rows.add(feat, gate=0, slot=-1, tile=-1, actor=int(kind == 'wait'), w_ipw=1/KEEP_WAIT, w_dom=dom,
                 value=value, resid=0., match=mi, seat=seat, tick=t, why=WHY[kind], unc=unc)
    stats['persp_ok'] += 1
    return len(rows) - n0, ticks


def value_of(d, seat):
    if d['labels']['tier'] not in VALUE_TIERS:
        return -1
    w = d['result']['source'].get('winner')
    if w is None:
        return 1
    return 2 if w == seat else 0


def build_batch(batch, src, jobs_dir, out_dir):
    rec = json.loads((src/'receipts'/f'batch-{batch}.json').read_text())
    shard = rec['shard']
    jobs = {}
    with gzip.open(jobs_dir/f'{shard}.jsonl.gz', 'rt') as f:
        want = set(rec['keys'])
        for line in f:
            j = json.loads(line)
            if j['key'] in want:
                jobs[j['key']] = j
    rows = Rows()
    stats = Counter()
    matches = []
    for k in rec['keys']:
        stats['matches'] += 1
        path = src/'out'/shard/f"{k.split(':')[1]}.json.gz"
        want_sha = rec['files'].get(f"{shard}/{k.split(':')[1]}.json.gz")
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            stats['match_missing_file'] += 1
            continue
        if want_sha is not None and hashlib.sha256(raw).hexdigest() != want_sha:
            stats['match_sha_mismatch'] += 1
            continue
        d = json.loads(gzip.decompress(raw))
        L = d['labels']
        if L.get('status') != 'ok' or not L.get('content_compatible') or L.get('tier') == 'failed' or not d.get('frames'):
            stats[f"match_skip:{L.get('tier')}:{L.get('status')}"] += 1
            continue
        job = jobs.get(k)
        if job is None:
            stats['match_no_job'] += 1
            continue
        fp = fingerprint(job)
        mi = len(matches)
        meta = dict(key=k, fp=fp, split=split_of(fp), tier=L['tier'], mode=L.get('mode'), early_end=L.get('early_end'),
                    native_end_tick=L.get('native_end_tick'), play_confirmed_frac=L.get('play_confirmed_frac'),
                    unc_tick=first_uncertainty(d),
                    verification=L.get('verification'), seats=[])
        for seat in (0, 1):
            names = [BY_ID.get(x['card']) for x in sorted(d['result']['native_decks'][seat], key=lambda x: x['slot'])]
            forms = [c['form'] for c in job['decks'][seat]]
            flags = deck_flags(names, forms)
            dom = 1. if flags['vanilla'] else DOMAIN_MODERN
            value = value_of(d, seat)
            try:
                r = build_perspective(d, job, seat, rows, stats, mi, value, dom)
            except Exception:
                stats['persp_exception'] += 1
                print(f'{k} seat {seat}:\n{traceback.format_exc()}', file=sys.stderr)
                r = None
            meta['seats'].append(dict(deck=names, forms=forms, tower=job['towers'][seat]['slug'], value=value,
                                      rows=r[0] if r else 0, polls=len(r[1]) if r else 0, **flags))
        matches.append(meta)
    return rows, matches, stats


def ragged(parts, cols, dtype):
    off = np.zeros(len(parts) + 1, np.int64)
    off[1:] = np.cumsum([len(p) for p in parts])
    data = np.concatenate(parts).astype(dtype) if off[-1] else np.zeros((0, cols), dtype)
    return data, off


def write_shard(batch, rows, matches, stats, out_dir):
    tmp = out_dir/'shards'/f'.{batch}.tmp'
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    c = rows.cols
    arrays = dict(
        tow=np.array(c['tow'], np.int16).reshape(-1, 6, F.T_COLS), hand=np.array(c['hand'], np.int16).reshape(-1, 5, F.H_COLS),
        glob=np.array(c['glob'], np.int32).reshape(-1, F.G_COLS), lag=np.array(c['lag'], np.int16).reshape(-1, len(F.LAGS), F.L_COLS),
        slot_ok=np.array(c['slot_ok'], bool).reshape(-1, 4), alive=np.array(c['alive'], bool).reshape(-1, 6),
        gate=np.array(c['gate'], np.int8), slot=np.array(c['slot'], np.int8), tile=np.array(c['tile'], np.int16),
        actor=np.array(c['actor'], np.int8), w_ipw=np.array(c['w_ipw'], np.float32), w_dom=np.array(c['w_dom'], np.float32),
        value=np.array(c['value'], np.int8), resid=np.array(c['resid'], np.float32), match=np.array(c['match'], np.int32),
        seat=np.array(c['seat'], np.int8), tick=np.array(c['tick'], np.int32), why=np.array(c['why'], np.int8),
        unc=np.array(c['unc'], np.int8))
    arrays['ent'], arrays['ent_off'] = ragged(rows.ent, F.E_COLS, np.int16)
    arrays['ev'], arrays['ev_off'] = ragged(rows.ev, F.V_COLS, np.int16)
    arrays['rev'], arrays['rev_off'] = ragged(rows.rev, F.R_COLS, np.int16)
    sums = {}
    for k, a in arrays.items():
        np.save(tmp/f'{k}.npy', a)
        sums[k] = hashlib.sha256((tmp/f'{k}.npy').read_bytes()).hexdigest()
    resid = Counter()
    by_card = {}
    for card, r in rows.resid_log:
        by_card.setdefault(card, []).append(r)
    resid = {card: dict(n=len(v), p50=float(np.percentile(v, 50)), p95=float(np.percentile(v, 95)), max=float(max(v)))
             for card, v in by_card.items()}
    meta = dict(schema=SCHEMA, batch=batch, rows=len(rows), matches=matches, stats=dict(stats), resid=resid,
                feature_hash=F.feature_hash(), catalog_sha256=F.catalog().sha256, files=sums,
                builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (tmp/'meta.json').write_text(json.dumps(meta) + '\n')
    final = out_dir/'shards'/batch
    if final.exists():
        shutil.rmtree(final)
    os.rename(tmp, final)
    return meta


def run_one(args):
    batch, src, jobs_dir, out_dir = args
    t0 = time.time()
    rows, matches, stats = build_batch(batch, Path(src), Path(jobs_dir), Path(out_dir))
    meta = write_shard(batch, rows, matches, stats, Path(out_dir))
    return dict(batch=batch, rows=meta['rows'], matches=len(matches), wall_s=round(time.time() - t0, 1),
                feature_hash=meta['feature_hash'], files_sha256=hashlib.sha256(
                    json.dumps(meta['files'], sort_keys=True).encode()).hexdigest(),
                stats={k: v for k, v in stats.items() if not k.startswith('resid:')})


def done_batches(out_dir):
    m = out_dir/'MANIFEST.jsonl'
    if not m.exists():
        return {}
    out = {}
    for line in m.read_text().splitlines():
        r = json.loads(line)
        out[r['batch']] = r
    return out


def cmd_build(a):
    fh = F.feature_hash()
    bh = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    src, out = Path(a.src), Path(a.out)/f'f-{fh[:12]}-b-{bh[:8]}'   # one store per featurizer + builder identity
    (out/'shards').mkdir(parents=True, exist_ok=True)
    acked = [b for b in (src/'acked.txt').read_text().split() if (src/'receipts'/f'batch-{b}.json').exists()]
    done = done_batches(out)
    stale = [b for b, r in done.items() if r['feature_hash'] != fh]
    if stale and not a.allow_mixed:
        raise SystemExit(f'{len(stale)} built shards have another feature hash; build into a new OUT')
    todo = [b for b in acked if b not in done][:a.limit_batches]
    print(f'acked {len(acked)}, built {len(done)}, to build {len(todo)}', flush=True)
    if not todo:
        return
    from multiprocessing import get_context
    with get_context('spawn').Pool(a.workers, maxtasksperchild=4) as pool:
        for r in pool.imap_unordered(run_one, [(b, str(src), a.jobs, str(out)) for b in todo]):
            r['built_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            with open(out/'MANIFEST.jsonl', 'a') as f:
                f.write(json.dumps(r) + '\n')
            print(json.dumps({k: r[k] for k in ('batch', 'rows', 'matches', 'wall_s')}), flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('--src', default=str(SRC))
    b.add_argument('--jobs', default=str(JOBS))
    b.add_argument('--out', default=str(OUT))
    b.add_argument('--workers', type=int, default=16)
    b.add_argument('--limit-batches', type=int, default=10**9)
    b.add_argument('--allow-mixed', action='store_true')
    a = ap.parse_args(argv)
    if a.cmd == 'build':
        cmd_build(a)


if __name__ == '__main__':
    main()
