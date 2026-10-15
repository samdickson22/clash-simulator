"""Empirical perception noise measured on VALIDATION, for synthetic-perception win-rate runs (LIVE integration).

fit   python -m bot.live.empirical fit --dump DUMP_DIR --out bot/live/empirical-val.json [--fusion JSON]
      Reads the per-frame validation dump (live/perception/dump_records.py: pred + truth per processed frame, plus the
      event-head peaks) and measures, in the record frame (owner 0 = us):
        units   per-owner greedy match (<= 1 tile, card ignored): true card -> predicted card confusion, misses,
                detection persistence (Markov: P(hit | hit / miss on the same true unit one frame earlier)), position
                and hp residuals, false positives per frame and owner (card distribution, distance to the nearest true
                unit);
        towers  alive flips and hp residuals; hand slot / next error rates; elixir residuals;
        events  opponent plays through the body-fused tracker (live/perception/events.py, config --fusion):
                detection probability per true card, card confusion, detection latency, execution-time and placement
                error, spurious events per minute (card distribution). Own plays are not modelled (live: our commands).
EmpiricalNoise(stats, rng, deck)   stateful per-match channel: perfect SynthPerception record -> record with that
      noise (detections Markov-correlated per true unit; events decided once per play and emitted after the sampled
      latency; spurious events as a Poisson stream). Used by bot/live/perc.py arms 'emp' (plays from events),
      'emp-births' (plays from births) and 'emp-both' (events + births).
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

STATS = Path(__file__).resolve().parent / 'empirical-val.json'
SAMPLE = 4000


def _greedy(P, T, r):
    pairs, used = [], set()
    cand = sorted((math.hypot(p['x']-t['x'], p['y']-t['y']), i, j) for i, p in enumerate(P) for j, t in enumerate(T))
    ui = set()
    for d, i, j in cand:
        if d > r:
            break
        if i in ui or j in used:
            continue
        ui.add(i); used.add(j); pairs.append((i, j, d))
    return pairs


def _sample(lst, rng, k=SAMPLE):
    if len(lst) <= k:
        return [round(float(x), 4) if not isinstance(x, (list, tuple)) else [round(float(v), 4) for v in x] for x in lst]
    idx = rng.choice(len(lst), size=k, replace=False)
    return _sample([lst[i] for i in sorted(idx)], rng, k)


def fit(dump, out, fusion, vocab, unit_threshold=None, counted=True, unit_filter=None):
    from bot.live.real_replay import load_dump, fused_events, OWN_NATIVE
    rng = np.random.default_rng(0)
    cards = json.loads(Path(vocab).read_text())['cards']
    conf, miss, tot = defaultdict(Counter), Counter(), Counter()
    markov = Counter()
    pos, hp, fp_card, fp_dist = [], [], {0: Counter(), 1: Counter()}, []
    fp_n, frames_n = Counter(), 0
    tw_flip, tw_n, tw_hp = 0, 0, []
    hand_err, hand_n, next_err, next_n, elix = 0, 0, 0, 0, []
    ev_conf, ev_tot, ev_det, lat, exec_err, place = defaultdict(Counter), Counter(), Counter(), [], [], []
    spur_card, spur_n, minutes = Counter(), 0, 0.
    files = sorted(Path(dump).glob('*.jsonl.gz'))
    for f in files:
        head, rows = load_dump(f)
        prev = None
        flt = None
        if unit_filter is not None:      # perception round 2: live/perception/unit_filter.UnitFilter, run over every frame
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'live/perception'))
            from unit_filter import UnitFilter
            flt = UnitFilter(**unit_filter)
        for r in rows:
            tr, pr = r['truth'], r['pred']
            if flt is not None:
                pr = dict(pr, units=flt([u for u in r['units_lo'] if not u.get('effect') and (counted or not u.get('counted'))]))
            elif unit_threshold is not None or not counted:   # re-decide the unit set from the dump's >= 0.25 detections
                pr = dict(pr, units=[u for u in r['units_lo'] if not u.get('effect') and (counted or not u.get('counted'))
                                     and u['score'] >= (unit_threshold if unit_threshold is not None else .4)])
            if tr.get('objects_stale'):
                prev = None
                continue
            frames_n += 1
            cur = []
            for owner in (0, 1):
                T = [u for u in tr['units'] if u['owner'] == owner]
                P = [u for u in pr['units'] if u['owner'] == owner]
                pairs = _greedy(P, T, 1.0)
                hit_t = {j for _, j, _ in pairs}
                for i, j, d in pairs:
                    conf[T[j]['card']][P[i]['card']] += 1
                    pos.append((P[i]['x']-T[j]['x'], P[i]['y']-T[j]['y']))
                    if P[i].get('hp_frac') is not None and T[j].get('hp_frac') is not None:
                        hp.append(P[i]['hp_frac']-T[j]['hp_frac'])
                for j, t in enumerate(T):
                    tot[t['card']] += 1
                    if j not in hit_t:
                        miss[t['card']] += 1
                    cur.append((owner, t['card'], t['x'], t['y'], j in hit_t))
                used = {i for i, _, _ in pairs}
                for i, p in enumerate(P):
                    if i in used:
                        continue
                    fp_n[owner] += 1
                    fp_card[owner][p['card']] += 1
                    if T:
                        fp_dist.append(min(math.hypot(p['x']-t['x'], p['y']-t['y']) for t in T))
            if prev is not None:
                for owner, card, x, y, h in cur:
                    best = None
                    for po, pc, px, py, ph in prev:
                        if po == owner and pc == card:
                            d = math.hypot(px-x, py-y)
                            if d <= .75 and (best is None or d < best[0]):
                                best = (d, ph)
                    if best is not None:
                        markov[(int(best[1]), int(h))] += 1
            prev = cur
            if tr.get('towers') and pr.get('towers'):
                got = {(t['owner'], t['kind'], t['side']): t for t in pr['towers']}
                for t in tr['towers']:
                    side = 'center' if t['kind'] == 'king' else t['side']
                    p = got.get((t['owner'], t['kind'], side))
                    if p is None:
                        continue
                    tw_n += 1
                    tw_flip += int(bool(p['alive']) != bool(t['alive']))
                    if p['alive'] and t['alive']:
                        tw_hp.append(p['hp_frac']-t['hp_frac'])
            for a, b in zip(tr['hand']['cards'], pr['hand']['cards']):
                if a is not None:
                    hand_n += 1; hand_err += int(a != b)
            if tr['hand'].get('next') is not None:
                next_n += 1; next_err += int(tr['hand']['next'] != pr['hand'].get('next'))
            elix.append(pr['elixir']-tr['elixir'])
        # events (opponent): fused tracker vs the true plays
        per_row, _ = fused_events(rows, cards, fusion)
        P = []
        for r, evs in zip(rows, per_row):
            for e in evs:
                if e['owner'] == 1:
                    P.append(dict(card=e['card'], x=e['x'], y=e['y'], exec_ms=e['tick'], det_ms=r['ts']))
        T = [dict(card=e['card'], x=e['tile'][0], y=32.-e['tile'][1], exec_ms=e['exec_tick']*50.)
             for e in head['truth_events'] if e['side'] != OWN_NATIVE and e['card'] in cards and
             rows[0]['ts'] <= e['exec_tick']*50. <= rows[-1]['ts']]
        minutes += (rows[-1]['ts']-rows[0]['ts'])/60000.
        used_p = set()
        for t in sorted(T, key=lambda t: t['exec_ms']):
            ev_tot[t['card']] += 1
            best = None
            for i, p in enumerate(P):
                if i in used_p:
                    continue
                dl = p['det_ms']-t['exec_ms']
                d = math.hypot(p['x']-t['x'], p['y']-t['y'])
                if 0 <= dl <= 1500 and d <= 2.5:
                    key = (p['card'] != t['card'], dl)
                    if best is None or key < best[0]:
                        best = (key, i)
            if best is None:
                continue
            p = P[best[1]]; used_p.add(best[1])
            ev_det[t['card']] += 1
            ev_conf[t['card']][p['card']] += 1
            lat.append(p['det_ms']-t['exec_ms']); exec_err.append(p['exec_ms']-t['exec_ms'])
            place.append((p['x']-t['x'], p['y']-t['y']))
        for i, p in enumerate(P):
            if i not in used_p:
                spur_n += 1; spur_card[p['card']] += 1
    mk = {f'{a}{b}': markov[(a, b)] for a in (0, 1) for b in (0, 1)}
    stats = dict(
        schema='clasher.live.empirical-noise.v1', split='validation', heldout_opened=False, matches=len(files),
        frames=frames_n, fusion=fusion, units_decode=dict(threshold=unit_threshold if unit_threshold is not None else 'record',
                                                           count_extras=counted, unit_filter=unit_filter),
        units=dict(confusion={k: dict(v) for k, v in conf.items()}, total=dict(tot), missed=dict(miss),
                   recall=sum(tot.values()) and 1-sum(miss.values())/sum(tot.values()),
                   markov=mk, p_hit_after_hit=mk['11']/max(1, mk['11']+mk['10']), p_hit_after_miss=mk['01']/max(1, mk['01']+mk['00']),
                   pos_residual=_sample(pos, rng), hp_residual=_sample(hp, rng),
                   fp_per_frame={str(o): fp_n[o]/max(1, frames_n) for o in (0, 1)},
                   fp_card={str(o): dict(fp_card[o]) for o in (0, 1)}, fp_dist=_sample(fp_dist, rng)),
        towers=dict(flip=tw_flip/max(1, tw_n), hp_residual=_sample(tw_hp, rng)),
        hud=dict(hand_slot_error=hand_err/max(1, hand_n), next_error=next_err/max(1, next_n), elixir_residual=_sample(elix, rng)),
        events=dict(total=dict(ev_tot), detected=dict(ev_det), confusion={k: dict(v) for k, v in ev_conf.items()},
                    recall=sum(ev_det.values())/max(1, sum(ev_tot.values())),
                    latency_ms=_sample(lat, rng), exec_err_ms=_sample(exec_err, rng), placement=_sample(place, rng),
                    spurious_per_min=spur_n/max(1e-9, minutes), spurious_card=dict(spur_card), minutes=minutes))
    Path(out).write_text(json.dumps(stats, separators=(',', ':'))+'\n')
    return stats


# Ablation parts (perc.py '-x<part>' arm tokens): the named noise component is removed, everything else as fitted.
PARTS = {
    'units': 'all unit noise (recall 1, true card, exact position/hp, no false positives)',
    'recall': 'unit misses only (every true unit detected; confusion/position/FP noise kept)',
    'conf': 'unit card confusion only', 'fp': 'false-positive units only',
    'hud': 'hand/next/elixir/tower noise', 'ev': 'all opponent play-event noise (perfect, immediate events)',
    'spell': 'opponent spell events perfect', 'troop': 'opponent troop/building events perfect',
    'spur': 'spurious events only', 'lat': 'event latency and execution-time error only'}

SPELLS = {'Arrows', 'BarbLog', 'Earthquake', 'Fireball', 'GoblinBarrel', 'Lightning', 'Log', 'Poison', 'Rocket',
          'RoyalDelivery', 'Tornado', 'Zap'}


class EmpiricalNoise:
    """Per-match stateful channel (see module docstring). record: SynthPerception record (ticks, our frame)."""

    def __init__(self, stats, rng, deck, cards=None, ablate=frozenset()):
        self.s, self.rng, self.deck = stats, rng, list(deck)
        bad = set(ablate)-set(PARTS)
        if bad:
            raise ValueError(f'unknown ablation parts {sorted(bad)}')
        self.x = frozenset(ablate)
        u = stats['units']
        self.recall = {c: 1-u['missed'].get(c, 0)/n for c, n in u['total'].items() if n >= 30}
        self.r0 = u['recall']
        self.p11, self.p01 = u['p_hit_after_hit'], u['p_hit_after_miss']
        self.conf = {c: (list(v), np.asarray(list(v.values()), float)/sum(v.values())) for c, v in u['confusion'].items()}
        self.pos, self.hp = np.asarray(u['pos_residual']), np.asarray(u['hp_residual'])
        self.fp_rate = {int(k): v for k, v in u['fp_per_frame'].items()}
        self.fp_card = {int(k): (list(v), np.asarray(list(v.values()), float)/max(1, sum(v.values()))) for k, v in u['fp_card'].items()}
        self.fp_dist = np.asarray(u['fp_dist'])
        e = stats['events']
        self.ev_tot, self.ev_det, self.ev_conf = e['total'], e['detected'], e['confusion']
        cls = {k: [0, 0] for k in ('spell', 'troop')}
        for c, n in e['total'].items():
            k = 'spell' if c in SPELLS else 'troop'
            cls[k][0] += n; cls[k][1] += e['detected'].get(c, 0)
        self.ev_cls = {k: v[1]/max(1, v[0]) for k, v in cls.items()}
        self.lat, self.xerr, self.place = np.asarray(e['latency_ms']), np.asarray(e['exec_err_ms']), np.asarray(e['placement'])
        self.spur_rate = e['spurious_per_min']/1200.     # per tick
        self.spur = (list(e['spurious_card']), np.asarray(list(e['spurious_card'].values()), float)/max(1, sum(e['spurious_card'].values())))
        self.cards = cards or sorted({c for c in u['total']} | set(e['total']))
        self.prev, self.fate, self.out, self.last_tick, self.n_spur = [], {}, [], None, 0

    def _pick(self, names, p):
        return names[int(self.rng.choice(len(names), p=p))]

    def _det_p(self, card, was_hit):
        base = self.p11 if was_hit else (self.p01 if was_hit is not None else self.r0)
        return float(np.clip(base*self.recall.get(card, self.r0)/max(1e-6, self.r0), 0., 1.))

    def __call__(self, record):
        rng, tick, ab = self.rng, int(record['tick']), self.x
        units, cur = [], []
        for t in record['units']:
            was = None
            for po, pc, px, py, ph in self.prev:
                if po == t['owner'] and pc == t['card'] and math.hypot(px-t['x'], py-t['y']) <= 1.5:
                    was = ph
                    break
            hit = rng.random() < self._det_p(t['card'], was)
            if ab & {'units', 'recall'}:
                hit = True
            cur.append((t['owner'], t['card'], t['x'], t['y'], hit))
            if not hit:
                continue
            u = dict(t)
            if 'units' in ab:
                u['score'] = .8
                units.append(u)
                continue
            names, p = self.conf.get(t['card'], ([t['card']], np.ones(1)))
            u['card'] = u['cls'] = self._pick(names, p) if 'conf' not in ab else t['card']
            dx, dy = self.pos[rng.integers(len(self.pos))] if len(self.pos) else (0., 0.)
            u['x'] = float(np.clip(t['x']+dx, 0, 18)); u['y'] = float(np.clip(t['y']+dy, 0, 32))
            if len(self.hp):
                u['hp_frac'] = float(np.clip(t['hp_frac']+self.hp[rng.integers(len(self.hp))], 0, 1))
            u['score'] = .8
            units.append(u)
        self.prev = cur
        for owner in (0, 1):
            own_true = [t for t in record['units'] if t['owner'] == owner]
            names, p = self.fp_card[owner]
            if not own_true or not names or ab & {'units', 'fp'}:
                continue
            for _ in range(rng.poisson(self.fp_rate[owner])):
                a = own_true[rng.integers(len(own_true))]
                d = float(self.fp_dist[rng.integers(len(self.fp_dist))]) if len(self.fp_dist) else 1.
                ang = rng.random()*2*math.pi
                c = self._pick(names, p)
                units.append(dict(cls=c, card=c, owner=owner, x=float(np.clip(a['x']+d*math.cos(ang), 0, 18)),
                                  y=float(np.clip(a['y']+d*math.sin(ang), 0, 32)), hp_frac=1., score=.6))
        towers = []
        for t in record['towers']:
            t = dict(t)
            if t['alive'] and 'hud' not in ab:
                tw = self.s['towers']['hp_residual']
                t['hp_frac'] = float(np.clip(t['hp_frac']+tw[rng.integers(len(tw))], .01, 1)) if tw else t['hp_frac']
            towers.append(t)
        hud = self.s['hud']
        hand = dict(record['hand'])
        hud = dict(hud, hand_slot_error=0., next_error=0., elixir_residual=[]) if 'hud' in ab else hud
        hand['cards'] = [(self._other(c) if c is not None and rng.random() < hud['hand_slot_error'] else c) for c in hand['cards']]
        if hand.get('next') is not None and rng.random() < hud['next_error']:
            hand['next'] = self._other(hand['next'])
        er = hud['elixir_residual']
        elixir = float(np.clip(record['elixir']+(er[rng.integers(len(er))] if er else 0.), 0, 10))
        # events: own plays pass (our commands); opponent plays decided once each, emitted after the latency
        for e in record.get('events', ()):
            if e['owner'] == 0:
                continue
            key = (e['card'], int(e['tick']), round(float(e['x']), 1), round(float(e['y']), 1))
            if key in self.fate:
                continue
            if 'ev' in ab or ('spell' if e['card'] in SPELLS else 'troop') in ab:
                self.fate[key] = dict(owner=1, card=e['card'], x=float(e['x']), y=float(e['y']), tick=int(e['tick']),
                                      due=e['tick'])
                continue
            n = self.ev_tot.get(e['card'], 0)
            p = self.ev_det.get(e['card'], 0)/n if n >= 10 else self.ev_cls['spell' if e['card'] in SPELLS else 'troop']
            if rng.random() >= p:
                self.fate[key] = None
                continue
            row = self.ev_conf.get(e['card'])
            card = self._pick(list(row), np.asarray(list(row.values()), float)/sum(row.values())) if row else e['card']
            lat = float(self.lat[rng.integers(len(self.lat))]) if len(self.lat) else 150.
            xe = float(self.xerr[rng.integers(len(self.xerr))]) if len(self.xerr) else 0.
            if 'lat' in ab:
                lat = xe = 0.
            dx, dy = self.place[rng.integers(len(self.place))] if len(self.place) else (0., 0.)
            self.fate[key] = dict(owner=1, card=card, x=float(np.clip(e['x']+dx, 0, 18)), y=float(np.clip(e['y']+dy, 0, 32)),
                                  tick=int(round(e['tick']+xe/50.)), due=e['tick']+lat/50.)
        for key, ev in list(self.fate.items()):
            if ev is not None and not ev.get('sent') and tick >= ev['due']:
                ev['sent'] = True
                self.out.append(dict(owner=1, card=ev['card'], x=ev['x'], y=ev['y'], tick=min(tick, ev['tick'])))
        if self.last_tick is not None and self.spur[0] and not ab & {'ev', 'spur'}:
            for _ in range(rng.poisson(self.spur_rate*max(0, tick-self.last_tick))):
                opp = [t for t in record['units'] if t['owner'] == 1]
                x, y = ((opp[rng.integers(len(opp))]['x'], opp[rng.integers(len(opp))]['y']) if opp and rng.random() < .5
                        else (float(rng.uniform(1, 17)), float(rng.uniform(17, 31))))
                self.n_spur += 1
                self.out.append(dict(owner=1, card=self._pick(*self.spur), x=float(x), y=float(y), tick=tick-int(rng.integers(0, 10))))
        self.last_tick = tick
        events = [e for e in record.get('events', ()) if e['owner'] == 0] + list(self.out)
        return dict(record, units=units, towers=towers, hand=hand, elixir=elixir, events=events)

    def _other(self, c):
        opts = [d for d in self.deck if d != c]
        return opts[int(self.rng.integers(len(opts)))] if opts else c


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    f = sub.add_parser('fit')
    f.add_argument('--dump', type=Path, required=True)
    f.add_argument('--out', type=Path, default=STATS)
    f.add_argument('--fusion', type=json.loads, required=True)
    f.add_argument('--vocab', default='/mpac/sdicks02/jobs/clasher/live-perception-20261014/export-final/vocab.json')
    f.add_argument('--unit-threshold', type=float, default=None, help='re-threshold units from the dump units_lo (>= 0.25)')
    f.add_argument('--no-count-extras', action='store_true', help='drop count-decode extra bodies (round 2)')
    f.add_argument('--unit-filter', type=json.loads, default=None, help='UnitFilter JSON (live/perception/unit_filter.py)')
    a = ap.parse_args()
    s = fit(a.dump, a.out, a.fusion, a.vocab, a.unit_threshold, not a.no_count_extras, a.unit_filter)
    print(json.dumps(dict(matches=s['matches'], frames=s['frames'], unit_recall=round(s['units']['recall'], 4),
                          p11=round(s['units']['p_hit_after_hit'], 3), p01=round(s['units']['p_hit_after_miss'], 3),
                          fp_per_frame=s['units']['fp_per_frame'], hand=s['hud']['hand_slot_error'],
                          event_recall=round(s['events']['recall'], 3), spurious_per_min=round(s['events']['spurious_per_min'], 2))))


if __name__ == '__main__':
    main()
