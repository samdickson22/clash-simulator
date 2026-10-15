"""Frame-level VALIDATION metrics for a PerceptionV4 checkpoint (exploration tier).

Metrics: own hand (4 slots + next), own elixir, tower HP / alive, unit detection
(identity x owner and owner-only P/R at 1 tile and 1/4 tile). Validation split only;
heldout ids are asserted absent before any loader touches a match.

  nice -n 10 python live/perception/eval_val.py --checkpoint CKPT --out DIR [--device cuda] [--stride 1]
"""
import argparse
from collections import defaultdict
import json
import math
import time
from pathlib import Path

import numpy as np

import common as C

THRESHOLDS = (.2, .3, .4, .5, .6, .7)
RADII = (1.0, .25)


def match(preds, truth, radius, key):
    """Greedy score-ordered matching. preds: [(score,x,y,cls)], truth: [(x,y,cls)]. Returns tp, unmatched pred idx, matched truth set."""
    used = set(); tp = []; fp = []
    for i in sorted(range(len(preds)), key=lambda i: -preds[i][0]):
        s, x, y, c = preds[i]; best = None; bd = radius+1e-9
        for j, (tx, ty, tc) in enumerate(truth):
            if j in used or (key and tc != c):
                continue
            d = math.hypot(tx-x, ty-y)
            if d <= bd:
                best, bd = j, d
        if best is None:
            fp.append(i)
        else:
            used.add(best); tp.append((i, best, bd))
    return tp, fp, used


def near(x, y, pts, radius):
    return any(math.hypot(px-x, py-y) <= radius for px, py in pts)



class FormalTruth:
    """Formal training-cleaner truth (sparse: trusted identity + same-tick rich visibility)."""
    @staticmethod
    def truth(labels, i, bodies):
        row = labels.object_row(i)
        if row is None:
            return None
        objs = row['objects']; towers = {}
        for owner, kind, side, ax, ay in C.TOWER_SLOTS:
            t = [o for o in objs if o['card_id'] == -1 and o['owner'] == owner and o['x'] == ax and o['y'] == ay]
            if t and (t[0].get('hp') is None or not t[0].get('max_hp')):
                towers[(owner, ax, ay)] = 'unknown'; continue
            alive = bool(t) and t[0]['hp'] > 0
            towers[(owner, ax, ay)] = (alive, t[0]['hp']/t[0]['max_hp'] if alive else 0.)
        nontower = [o for o in objs if o['card_id'] != -1]
        known = [o for o in nontower if C.known_unit(o, bodies)]
        ignore_id = [(o['x']/1000, o['y']/1000) for o in nontower if not C.known_unit(o, bodies)]
        visible = [o for o in nontower if o.get('max_hp') and o['max_hp'] > 0 and o.get('visible_hint') == 'visible' and o.get('deploying') is False]
        ignore_own = [(o['x']/1000, o['y']/1000) for o in nontower if o not in visible]
        uncovered = [o.get('body_name') or ('hint:'+str(o.get('body_name_hint'))) for o in visible if not C.known_unit(o, bodies)]
        return (towers, [(o['x']/1000, o['y']/1000, (o['owner'], o['body_name'])) for o in known], ignore_id,
                [(o['x']/1000, o['y']/1000, o['owner']) for o in visible], ignore_own, uncovered)


def _formal_hud_row(self, i):
    return self.hud[self.frames[i]['seq']]


C.Labels.truth = lambda self, i, bodies: FormalTruth.truth(self, i, bodies)
C.Labels.hud_row = _formal_hud_row


class DenseTruth:
    """Dense card-level truth from dense_labels.py npz: every HP object, identity = spawning card."""
    def __init__(self, guard, ep, labels_dir):
        import dense_labels as D
        guard.check([ep]); self.D = D
        self.lab = D.load(Path(labels_dir)/f'{ep}.npz')
        if str(self.lab['split']) != 'validation' or str(self.lab['episode']) != ep:
            raise AssertionError('dense label split/episode mismatch')
        self.cards = guard.cards; self.frames = range(len(self.lab['row']))

    def steady(self, i, k=3):
        L = self.lab; lo, hi = max(0, i-k), min(len(L['row']), i+k+1)
        h = L['hand'][lo:hi]; e = L['elixir_int'][lo:hi]
        return bool((h == h[0]).all()), bool((e == e[0]).all())

    def hud_row(self, i):
        L = self.lab; c = self.cards; n = len(c)
        names = [c[k] if k < n else None for k in L['hand'][i]]
        return dict(own_hand=names[:4], own_next_card=names[4], own_elixir=float(L['elixir'][i]),
                    displayed_integer_elixir=int(L['elixir_int'][i]), clock=float(L['clock'][i]), phase=int(L['phase'][i]))

    def truth(self, i, bodies):
        got = self.D.frame_objects(self.lab, i)
        if got is None:
            return None
        cls, own, x, y, frac, ign = got; n = len(self.cards)
        towers = {(o, ax, ay): (False, 0.) for o, k, s, ax, ay in C.TOWER_SLOTS}
        units = []
        for c, o, xx, yy, f in zip(cls, own, x, y, frac):
            if c >= n:
                for so, k, s, ax, ay in C.TOWER_SLOTS:
                    if so == o and abs(xx*1000-ax) < 1 and abs(yy*1000-ay) < 1:
                        towers[(so, ax, ay)] = (True, float(f))
            else:
                units.append((float(xx), float(yy), (int(o), self.cards[c])))
        ig = [(float(a), float(b)) for a, b in ign]
        return towers, units, ig, [(u[0], u[1], u[2][0]) for u in units], ig, []


class Acc:
    def __init__(self):
        self.d = defaultdict(float)

    def add(self, k, v=1.):
        self.d[k] += v


def evaluate(a):
    import torch
    from clasher.vision.l1_v4 import PerceptionV4
    torch.set_num_threads(a.threads)
    guard = C.HeldoutGuard()
    eps = guard.episodes('validation')
    if a.max_matches:
        eps = eps[:a.max_matches]
    guard.check(eps)
    assert not set(eps) & guard.heldout
    state = torch.load(a.checkpoint, map_location='cpu', weights_only=False)
    cards, bodies = state['cards'], state['bodies']
    dense_model = state.get('format') in ('live-dense-v1', 'live-dense-v2')
    if cards != guard.cards:
        raise ValueError('card vocabulary differs from split cards')
    model = PerceptionV4(len(cards), len(bodies)); model.load_state_dict(state['model']); model.eval().to(a.device)
    acc = Acc(); per_class = defaultdict(lambda: defaultdict(float)); conf = defaultdict(lambda: defaultdict(int))
    tower_err = defaultdict(list); elixir_err = []; frames_done = 0; started = time.time(); infer_s = 0.
    records = (open(a.out/'records-sample.jsonl', 'w') if a.records else None)
    for mi, ep in enumerate(eps):
        receipt = C.load_receipt(guard, ep, 'validation')
        if a.truth == 'formal':
            labels = C.Labels(guard, ep, receipt)
        else:
            labels = DenseTruth(guard, ep, a.labels)
        pix = C.Pixels(guard, ep, receipt)
        if len(labels.frames) != pix.n:
            raise ValueError('frame count mismatch')
        wanted = list(range(a.offset, pix.n, a.stride)); wanted_set = set(wanted)
        for k in sorted({i//pix.bs for i in wanted}):
            ar, hu = pix.block(k)
            idx = [i for i in range(k*pix.bs, min(pix.n, (k+1)*pix.bs)) if i in wanted_set]
            if not idx:
                continue
            sel = [i-k*pix.bs for i in idx]
            t0 = time.perf_counter()
            with torch.inference_mode():
                arena = torch.from_numpy(np.ascontiguousarray(ar[sel])).to(a.device).permute(0, 3, 1, 2).float()/255
                hud = torch.from_numpy(np.ascontiguousarray(hu[sel])).to(a.device).permute(0, 3, 1, 2).float()/255
                out = model.encode(arena, hud)
                out = {n: out[n].float().cpu().numpy() for n in ('body_heatmap', 'body_hp', 'body_hp_visible', 'body_box', 'hud_cards',
                                                                 'elixir_digit', 'elixir_fraction', 'clock_seconds', 'phase')}
            infer_s += time.perf_counter()-t0
            for b, i in enumerate(idx):
                dec = C.decode_frame(out, b, cards, bodies, threshold=min(THRESHOLDS), refine_pos=not a.no_refine, offsets=dense_model,
                                      counts=False if a.no_counts else None)
                if not dense_model:  # map body identities onto card names for card-level dense truth
                    for u in dec['units']:
                        u['body'] = u['identity']
                        if a.truth == 'dense' and u['identity'] not in C.TOWER_BODIES:
                            u['identity'] = C.body_card(u['identity'])
                score_frame(dec, labels, i, cards, bodies, acc, per_class, conf, tower_err, elixir_err)
                if records is not None and mi < 2 and i % 20 == 0:
                    records.write(json.dumps(dict(episode=ep, seq=i, record=C.frame_record(
                        dict(dec, units=[u for u in dec['units'] if u['score'] >= .5]), timestamp_ms=None)))+'\n')
                frames_done += 1
        print(json.dumps(dict(match=mi+1, of=len(eps), episode=ep, frames=frames_done, elapsed=round(time.time()-started, 1),
                              infer_ms_per_frame=round(1000*infer_s/max(1, frames_done), 2))), flush=True)
    if records:
        records.close()
    return summarize(a, acc, per_class, conf, tower_err, elixir_err, frames_done, eps, state, bodies)


def score_frame(dec, labels, i, cards, bodies, acc, per_class, conf, tower_err, elixir_err):
    h = labels.hud_row(i)
    truth_cards = [*h['own_hand'], h['own_next_card']]
    for s, (p, t) in enumerate(zip([*dec['hand'], dec['next']], truth_cards)):
        if t not in cards:
            acc.add(f'hand_slot{s}_unknown_truth'); continue
        acc.add(f'hand_slot{s}_n'); acc.add(f'hand_slot{s}_ok', p == t)
        if p != t:
            conf['hand'][f'{t}->{p}'] += 1
    steady = getattr(labels, 'steady', None)
    if steady is not None:
        hs, es = steady(i)
        if hs:
            ok4 = [p == t for p, t in zip([*dec['hand'], dec['next']], truth_cards) if t in cards]
            acc.add('hand_steady_slots_n', len(ok4)); acc.add('hand_steady_slots_ok', sum(ok4))
            acc.add('hand_steady_all4_n'); acc.add('hand_steady_all4_ok', dec['hand'] == truth_cards[:4])
        if es:
            acc.add('elixir_steady_n'); acc.add('elixir_steady_int_ok', dec['elixir_digit'] == h['displayed_integer_elixir'])
    if all(t in cards for t in truth_cards[:4]):
        acc.add('hand4_n'); acc.add('hand4_ok', dec['hand'] == truth_cards[:4])
        acc.add('hand5_n'); acc.add('hand5_ok', dec['hand'] == truth_cards[:4] and dec['next'] == truth_cards[4])
    acc.add('elixir_n'); elixir_err.append(abs(dec['elixir']-h['own_elixir']))
    acc.add('elixir_int_ok', dec['elixir_digit'] == h['displayed_integer_elixir'])
    acc.add('elixir_floor_ok', int(dec['elixir']) == int(h['own_elixir']))
    acc.add('clock_abs', abs(dec['clock']-h['clock'])); acc.add('phase_ok', dec['phase'] == h['phase'])
    got = labels.truth(i, bodies)
    if got is None:
        acc.add('stale_object_frames'); return
    acc.add('object_frames')
    tower_truth, truth_id, ignore_id, truth_ow, ignore_own, uncovered = got
    # Towers
    for (owner, kind, side, ax, ay), pt in zip(C.TOWER_SLOTS, dec['towers']):
        tt = tower_truth[(owner, ax, ay)]
        if tt == 'unknown':
            acc.add('tower_unknown'); continue
        alive, frac = tt
        name = f"{'own' if owner == C.OWN_NATIVE else 'opp'}_{kind}_{side}"
        for th in THRESHOLDS:
            pa = pt['score'] >= th
            acc.add(f'tower_alive_ok@{th}', pa == alive)
            pf = pt['hp_frac'] if pa else 0.
            acc.add(f'tower_abs_all@{th}', abs(pf-frac))
        acc.add('tower_n'); acc.add(f'tower_alive_truth', alive)
        if alive:
            tower_err[name].append(abs(pt['hp_frac']-frac)); acc.add(f'tower_alive_n_{name}')
            if frac < .999:
                tower_err[name+'_damaged'].append(abs(pt['hp_frac']-frac))
        acc.add(f'tower_alive_ok_{name}', (pt['score'] >= .5) == alive); acc.add(f'tower_n_{name}')
    # Units
    units = [u for u in dec['units'] if u['identity'] not in C.TOWER_BODIES]
    acc.add('units_visible_hp', len(truth_ow)); acc.add('units_known', len(truth_id))
    for name in uncovered:
        conf['uncovered'][name] += 1
    for th in THRESHOLDS:
        P = [u for u in units if u['score'] >= th]
        for r in RADII:
            preds = [(u['score'], u['x'], u['y'], (u['owner'], u['identity'])) for u in P]
            tp, fp, used = match(preds, truth_id, r, True)
            fp = [k for k in fp if not near(preds[k][1], preds[k][2], ignore_id, max(r, 1.))]
            acc.add(f'id_tp@{th}@{r}', len(tp)); acc.add(f'id_fp@{th}@{r}', len(fp)); acc.add(f'id_fn@{th}@{r}', len(truth_id)-len(used))
            if th == .5 and r == 1.:
                for k, j, d in tp:
                    per_class[truth_id[j][2]]['tp'] += 1; acc.add('id_dist_sum', d)
                for k in fp:
                    per_class[preds[k][3]]['fp'] += 1
                for j in set(range(len(truth_id)))-used:
                    per_class[truth_id[j][2]]['fn'] += 1
                # identity confusions: unmatched truth with a same-owner pred within 1 tile
                for j in set(range(len(truth_id)))-used:
                    tx, ty, (to, tn) = truth_id[j]
                    cand = [p for p in preds if p[3][0] == to and math.hypot(p[1]-tx, p[2]-ty) <= 1.]
                    if cand:
                        conf['identity'][f'{tn}->{max(cand)[3][1]}'] += 1
            preds_o = [(u['score'], u['x'], u['y'], u['owner']) for u in P]
            tp, fp, used = match(preds_o, truth_ow, r, True)
            fp = [k for k in fp if not near(preds_o[k][1], preds_o[k][2], ignore_own, max(r, 1.))]
            acc.add(f'ow_tp@{th}@{r}', len(tp)); acc.add(f'ow_fp@{th}@{r}', len(fp)); acc.add(f'ow_fn@{th}@{r}', len(truth_ow)-len(used))
            # owner-only restricted to vocabulary-covered truth (comparable to the identity metric)
            truth_ok = [(x, y, k[0]) for x, y, k in truth_id]
            tp, fp, used = match(preds_o, truth_ok, r, True)
            fp = [k for k in fp if not near(preds_o[k][1], preds_o[k][2], ignore_id, max(r, 1.))]
            acc.add(f'owk_tp@{th}@{r}', len(tp)); acc.add(f'owk_fp@{th}@{r}', len(fp)); acc.add(f'owk_fn@{th}@{r}', len(truth_ok)-len(used))


def prf(d, p, th, r):
    tp, fp, fn = d[f'{p}_tp@{th}@{r}'], d[f'{p}_fp@{th}@{r}'], d[f'{p}_fn@{th}@{r}']
    P = tp/max(1, tp+fp); R = tp/max(1, tp+fn)
    return dict(precision=round(P, 4), recall=round(R, 4), f1=round(2*P*R/max(1e-9, P+R), 4), tp=int(tp), fp=int(fp), fn=int(fn))


def summarize(a, acc, per_class, conf, tower_err, elixir_err, frames, eps, state, bodies):
    d = acc.d
    hand = {f'slot{s}' if s < 4 else 'next': round(d[f'hand_slot{s}_ok']/max(1, d[f'hand_slot{s}_n']), 5) for s in range(5)}
    hand['all4'] = round(d['hand4_ok']/max(1, d['hand4_n']), 5); hand['all4+next'] = round(d['hand5_ok']/max(1, d['hand5_n']), 5)
    hand['mean_4slots'] = round(sum(d[f'hand_slot{s}_ok'] for s in range(4))/max(1, sum(d[f'hand_slot{s}_n'] for s in range(4))), 5)
    hand['unknown_truth_slots'] = int(sum(d[f'hand_slot{s}_unknown_truth'] for s in range(5)))
    if d['hand_steady_slots_n']:
        hand['steady_state_slot_acc'] = round(d['hand_steady_slots_ok']/d['hand_steady_slots_n'], 5)
        hand['steady_state_all4'] = round(d['hand_steady_all4_ok']/d['hand_steady_all4_n'], 5)
        hand['steady_state_frame_fraction'] = round(d['hand_steady_all4_n']/max(1, d['elixir_n']), 4)
        hand['steady_definition'] = 'no hand/next change within +-3 frames (150 ms)'
    e = np.asarray(elixir_err)
    elixir = dict(mae=round(float(e.mean()), 4), p95_abs=round(float(np.quantile(e, .95)), 4),
                  exact_integer_acc=round(d['elixir_int_ok']/d['elixir_n'], 5), floor_of_float_acc=round(d['elixir_floor_ok']/d['elixir_n'], 5),
                  steady_state_integer_acc=round(d['elixir_steady_int_ok']/max(1, d['elixir_steady_n']), 5),
                  steady_state_frame_fraction=round(d['elixir_steady_n']/max(1, d['elixir_n']), 4))
    towers = dict(alive_acc={str(th): round(d[f'tower_alive_ok@{th}']/max(1, d['tower_n']), 5) for th in THRESHOLDS},
                  hp_mae_all_with_destroyed_as_0={str(th): round(d[f'tower_abs_all@{th}']/max(1, d['tower_n']), 5) for th in THRESHOLDS},
                  per_tower={k: dict(hp_mae_when_alive=round(float(np.mean(v)), 5), p95=round(float(np.quantile(v, .95)), 5), n=len(v))
                             for k, v in sorted(tower_err.items())},
                  alive_acc_per_tower={k[len('tower_n_'):]: round(d['tower_alive_ok_'+k[len('tower_n_'):]]/d[k], 5)
                                       for k in sorted(d) if k.startswith('tower_n_')},
                  truth_alive_fraction=round(d['tower_alive_truth']/max(1, d['tower_n']), 4), unknown=int(d['tower_unknown']))
    units = {}
    for p, name in (('id', 'identity_x_owner'), ('ow', 'owner_only_all_visible'), ('owk', 'owner_only_vocab_covered')):
        units[name] = {f'r={r}': {str(th): prf(d, p, th, r) for th in THRESHOLDS} for r in RADII}
    units['mean_match_distance_tiles@0.5'] = round(d['id_dist_sum']/max(1, d['id_tp@0.5@1.0']), 4)
    units['vocab_coverage_of_visible_units'] = round(d['units_known']/max(1, d['units_visible_hp']), 4)
    units['visible_units_total'] = int(d['units_visible_hp'])
    pc = []
    for (owner, name), v in per_class.items():
        tp, fp, fn = v['tp'], v['fp'], v['fn']
        pc.append(dict(cls=name, owner='own' if owner == C.OWN_NATIVE else 'opp', tp=int(tp), fp=int(fp), fn=int(fn),
                       precision=round(tp/max(1, tp+fp), 3), recall=round(tp/max(1, tp+fn), 3)))
    pc.sort(key=lambda r: -(r['tp']+r['fn']))
    top = lambda c, n=25: sorted(c.items(), key=lambda kv: -kv[1])[:n]
    return dict(schema='clasher.live.perception-eval.v1', split='validation', heldout_opened=False,
                checkpoint=str(a.checkpoint), checkpoint_sha256=C.sha(a.checkpoint), matches=len(eps), frames=frames,
                stride=a.stride, offset=a.offset, device=a.device, refine=not a.no_refine, truth=a.truth,
                hand=hand, elixir=elixir, clock_mae_s=round(d['clock_abs']/max(1, d['elixir_n']), 3),
                phase_acc=round(d['phase_ok']/max(1, d['elixir_n']), 5), towers=towers, units=units,
                per_class_r1_t05=pc, confusions=dict(hand=top(conf['hand']), identity=top(conf['identity']),
                                                      uncovered_visible=top(conf['uncovered'], 40)),
                object_frames=int(d['object_frames']), stale_object_frames=int(d['stale_object_frames']),
                bodies=bodies, notes='Unit truth = training-cleaner trusted, visible, non-deploying objects; '
                'identity metric ignores predictions near untrusted/out-of-vocab objects; owner-only covers all visible HP objects.')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--checkpoint', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--device', default='cpu'); p.add_argument('--threads', type=int, default=12)
    p.add_argument('--stride', type=int, default=1); p.add_argument('--offset', type=int, default=0)
    p.add_argument('--max-matches', type=int, default=0); p.add_argument('--no-refine', action='store_true'); p.add_argument('--no-counts', action='store_true')
    p.add_argument('--records', action='store_true'); p.add_argument('--truth', choices=('dense', 'formal'), default='dense')
    p.add_argument('--labels', type=Path, default=Path('/mpac/sdicks02/jobs/clasher/live-perception-20261014/labels'))
    a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    result = evaluate(a)
    (a.out/'metrics.json').write_text(json.dumps(result, indent=1)+'\n')
    print(json.dumps({k: result[k] for k in ('hand', 'elixir', 'frames')}), flush=True)
