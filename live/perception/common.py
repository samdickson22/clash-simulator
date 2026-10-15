"""Shared helpers for the LIVE perception exploration track (step B).

Split guard, lossless pixel-cache reader, label loading and the downstream
per-frame record. Heldout matches are never read: membership comes from the
frozen split.json alone, before any match file is opened.
"""
import gzip
import json
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
V4L1 = REPO/'reports/strategy_council_20260928/live-loop/v4/l1'
for p in (REPO/'src', V4L1):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

SPLIT_SHA = '3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258'
DATA = Path('/mpac/sdicks02/repos/clasher-v4-data')
SPLIT = DATA/'registration/v4-registration-460aabbd70b894da/split.json'
MATCHES = DATA/'matches'
CACHE = Path('/mpac/sdicks02/repos/clasher-v4-cache')
LOCAL_CACHE = Path('/mpac/sdicks02/jobs/clasher/live-perception-20261014/cache')  # matches missing from CACHE on 01
# Label/geometry inputs pinned to the T7 training snapshot (repo gamedata.json drifted since).
SNAPSHOT = Path(__file__).resolve().parent/'snapshot'

TOWER_SLOTS = [  # native owner, kind, side (native x<9 = 'left'), native milli-tile anchor
    (0, 'king', 'center', 9000, 3000), (0, 'princess', 'left', 3500, 6500), (0, 'princess', 'right', 14500, 6500),
    (1, 'king', 'center', 9000, 29000), (1, 'princess', 'left', 3500, 25500), (1, 'princess', 'right', 14500, 25500)]
TOWER_BODIES = ('KingTower', 'PrincessTower')
OWN_NATIVE = 1  # recorded viewpoint: HUD own_hand is deck[1]; own king at native y=29 (screen bottom)


def sha(path):
    import hashlib
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


class HeldoutGuard:
    def __init__(self, split_file=SPLIT):
        if sha(split_file) != SPLIT_SHA:
            raise ValueError('split.json differs from the registered split')
        frozen = json.loads(Path(split_file).read_text())
        self.split = {m['episode']: m['split'] for m in frozen['matches']}
        self.heldout = {e for e, s in self.split.items() if s == 'heldout'}
        self.cards = frozen['cards']

    def episodes(self, split, root=MATCHES):
        if split not in ('train', 'validation'):
            raise ValueError('only train/validation may be listed')
        # Directory listing only; nothing under a match dir is opened here.
        present = {p.name for p in Path(root).iterdir()}
        eps = sorted(e for e, s in self.split.items() if s == split and e in present)
        self.check(eps)
        return eps

    def check(self, eps):
        bad = set(eps) & self.heldout
        if bad:
            raise AssertionError(f'heldout episode reached a loader: {sorted(bad)[:3]}')
        for e in eps:
            if self.split.get(e) not in ('train', 'validation'):
                raise AssertionError(f'episode outside train/validation: {e}')


def read_jsonl(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]


def load_receipt(guard, ep, split):
    guard.check([ep])
    r = json.loads((MATCHES/ep/'receipt.json').read_text())
    if r['split'] != split or r['episode'] != ep:
        raise AssertionError('receipt split mismatch')
    return r


class Pixels:
    """Read-only lossless cache reader (prepared 832x448 arena + 64x448 HUD, BGR uint8)."""
    def __init__(self, guard, ep, receipt):
        from pixel_cache import ARENA, HUD, PIXEL_BYTES, SCHEMA
        guard.check([ep])
        self.dir = CACHE/ep if (CACHE/ep/'index.json').exists() else LOCAL_CACHE/ep
        self.idx = json.loads((self.dir/'index.json').read_text())
        if self.idx['schema'] != SCHEMA or self.idx['episode'] != ep or self.idx['split'] != receipt['split']:
            raise ValueError('cache identity mismatch')
        if self.idx['frames'] != receipt['frames'] or self.idx['video_sha256'] != receipt['files']['video.mp4']:
            raise ValueError('cache/receipt mismatch')
        self.n = self.idx['frames']; self.bs = self.idx['block_size']
        self.arena, self.hud, self.width = ARENA, HUD, PIXEL_BYTES

    def block(self, k):
        from pixel_cache import decompress
        b = self.idx['blocks'][k]; off, size = b['pixels.zst']
        with (self.dir/'pixels.zst').open('rb') as f:
            f.seek(off); blob = f.read(size)
        rows = decompress(blob, (b['count'], self.width))
        na = int(np.prod(self.arena))
        return rows[:, :na].reshape(-1, *self.arena), rows[:, na:].reshape(-1, *self.hud)


class Labels:
    """Per-match truth: HUD rows, cleaned object rows (training cleaner), frame ticks."""
    _cleaner = None

    def __init__(self, guard, ep, receipt, slim=True):
        guard.check([ep])
        from labels_v4 import BodyLabels, read_objects
        if Labels._cleaner is None:
            Labels._cleaner = BodyLabels(SNAPSHOT/'gamedata.json', SNAPSHOT/'body-catalog.json')
        root = MATCHES/ep
        self.frames = read_jsonl(root/'frames.jsonl')
        self.hud = {h['seq']: h for h in read_jsonl(root/'hud.jsonl')}
        self.events = [e for e in read_jsonl(root/'events.jsonl') if e['accepted'] and e['kind'] != 'champion ability']
        with gzip.open(root/'objects.jsonl.gz', 'rt') as f:
            rows = [json.loads(x) for x in f]
        rows = Labels._cleaner.clean(rows, read_objects(root/'rich-objects.jsonl.gz'))
        keep = ('card_id', 'body_name', 'body_name_hint', 'body_identity_source', 'owner', 'x', 'y', 'hp', 'max_hp',
                'visible_hint', 'deploying')
        if slim:
            rows = [dict(tick=r['tick'], objects=[{k: o.get(k) for k in keep} for o in r['objects']]) for r in rows]
        self.objects = rows
        self.ticks = [r['tick'] for r in rows]

    def tick(self, i):
        f = self.frames[i]
        return (f['tick_lo']+f['tick_hi'])/2

    def object_row(self, i):
        import bisect
        t = self.tick(i); j = max(0, bisect.bisect_right(self.ticks, t)-1)
        if abs(self.ticks[j]-t) > 5:
            return None
        return self.objects[j]


def trusted(o):
    return bool(o.get('body_name') and o.get('body_identity_source') in ('unique_card_payload_hp', 'tower_anchor_hp'))


def known_unit(o, bodies):
    return (trusted(o) and o['body_name'] in bodies and o.get('visible_hint') == 'visible'
            and o.get('deploying') is False)


# ---------------------------------------------------------------- downstream record
def own_view(native_owner, x, y):
    """Native (owner 1 = us, native y grows down the screen) -> bot frame: owner 0 = us, 1 = opp;
    x unchanged (screen-left origin), y = 32 - native y (screen-bottom origin), so our king sits at (9, 3).
    A pure y-flip keeps screen left == bot left, so actuation needs only the inverse y-flip."""
    return (0 if native_owner == OWN_NATIVE else 1), float(x), 32.0-y


def body_card(identity):
    from clasher.vision.l1_v4 import body_action
    return {'GoblinHut_Rework': 'GoblinHut', 'Furnace_rework': 'FirespiritHut', 'AngryBarbarian': 'AngryBarbarians',
            'RascalBoy': 'Rascals', 'RascalGirl': 'Rascals', 'Golemite': 'Golem', 'DeliveryRecruit': 'RoyalDelivery',
            'Goblinstein_doctor': 'Goblinstein', 'IceGolemite': 'IceGolem', 'IceSpirits': 'IceSpirit',
            'Goblin': 'Goblins', 'SpearGoblin': 'Goblins'}.get(identity, body_action(identity))


def refine(scores, c, gy, gx):
    """3x3 score-weighted centroid around a peak, in half-tile cells."""
    h, w = scores.shape[-2:]
    y0, y1, x0, x1 = max(0, gy-1), min(h, gy+2), max(0, gx-1), min(w, gx+2)
    patch = scores[c, y0:y1, x0:x1]
    yy, xx = np.mgrid[y0:y1, x0:x1]
    s = patch.sum()
    return float((patch*xx).sum()/s), float((patch*yy).sum()/s)


# Cards that put several same-card bodies on the board (swarms, spawners, splits): the only identities the count
# decode may add bodies for (a second Knight next to a Knight is a double count, not a merge).
MULTI_BODY = frozenset({'AngryBarbarians', 'Archers', 'Bats', 'FireSpirits', 'FirespiritHut', 'GoblinBarrel', 'GoblinGang',
                        'GoblinHut', 'Goblins', 'Golem', 'Goblinstein', 'Minions', 'MinionHorde', 'Rascals', 'RoyalHogs',
                        'SkeletonArmy', 'Skeletons', 'Wallbreakers'})


def _count_extras(heat, box, b, nb, peaks_cs, peaks_ys, peaks_xs, n_unit, floor, bodies=None, cmin=.9, radius=1):
    """Round-2 count decode (window sum): body_box[2 + native owner] = bodies per half-tile cell. Peaks in descending score;
    each peak of a MULTI_BODY identity claims its unclaimed (2r+1)^2 window, whose expected body count is the sum of the
    owner's (clipped) count map there; extras = floor(sum - peaks in the window + 1 - cmin), placed on the window's
    highest residual-count cells whose heat for that identity >= floor. Chosen on 6 val matches (r2/decode_grid.py,
    ft-r3b epoch 6: F1 .823 vs .815 peaks only; recall .767 -> .816, swarm .684 -> .782).
    -> [(c, gy, gx, fx, fy, score)] in half-tile cells."""
    h, w = heat.shape[-2:]
    cnt = np.clip(box[b, 2:4], 0, None)
    order = np.argsort(-heat[peaks_cs, peaks_ys, peaks_xs])
    pk = [(int(peaks_cs[k]), int(peaks_ys[k]), int(peaks_xs[k])) for k in order if int(peaks_cs[k]) % nb < n_unit]
    peakcount = np.zeros((2, h, w), int)
    for c, gy, gx in pk:
        peakcount[c//nb, gy, gx] += 1
    claimed = np.zeros((2, h, w), bool)
    extras = []
    for c, gy, gx in pk:
        o = c//nb
        y0, y1, x0, x1 = max(0, gy-radius), min(h, gy+radius+1), max(0, gx-radius), min(w, gx+radius+1)
        free = ~claimed[o, y0:y1, x0:x1]
        tot = float((cnt[o, y0:y1, x0:x1]*free).sum()); n_pk = int((peakcount[o, y0:y1, x0:x1]*free).sum())
        claimed[o, y0:y1, x0:x1] = True
        if bodies is not None and bodies[c % nb] not in MULTI_BODY:
            continue
        extra = int(math.floor(tot-n_pk+1-cmin)) if tot-n_pk >= cmin else 0
        if extra <= 0:
            continue
        cells = sorted(((float(cnt[o, y, x])-peakcount[o, y, x], y, x) for y in range(y0, y1) for x in range(x0, x1)), reverse=True)
        k = 0
        while extra > 0 and k < 3*len(cells):
            _, y, x = cells[k % len(cells)]
            if heat[c, y, x] >= floor:
                j = k//len(cells); ang = 2.4*k
                extras.append((c, y, x, x+float(box[b, 0, y, x])-.5+.3*j*math.cos(ang), y+float(box[b, 1, y, x])-.5+.3*j*math.sin(ang),
                               float(heat[c, gy, gx])*.999))
                extra -= 1
            k += 1
    return extras


def decode_frame(out, b, cards, bodies, threshold=.5, refine_pos=True, max_units=128, offsets=False, counts=None,
                 count_floor=.2):
    """One frame of numpy head outputs -> native-coordinate detections, towers, HUD.

    out: dict of numpy arrays for batch item b (sigmoid NOT yet applied to heatmap).
    live-dense-v2 (identities 'fx:<spell>' present): effect peaks go to dec['effects'], never units, and with
    `counts` (default: on for v2) the count head adds one detection per counted body (_count_extras).
    """
    v2 = any(str(n).startswith('fx:') for n in bodies)
    counts = v2 if counts is None else counts
    n_unit = len(bodies)-sum(str(n).startswith('fx:') for n in bodies)-2  # card identities (towers follow)
    heat = 1/(1+np.exp(-out['body_heatmap'][b]))  # [2*nb,64,36]
    nb = len(bodies)
    # 3x3 NMS per channel
    from scipy.ndimage import maximum_filter
    peaks = (heat == maximum_filter(heat, size=(1, 3, 3), mode='constant')) & (heat >= threshold)
    cs, ys, xs = np.nonzero(peaks)
    order = np.argsort(-heat[cs, ys, xs])[:max_units]
    hp = out['body_hp'][b, 0]; hpv = 1/(1+np.exp(-out['body_hp_visible'][b, 0]))
    units, effects = [], []
    if counts:
        extra = _count_extras(heat, out['body_box'], b, nb, cs, ys, xs, n_unit, max(count_floor, min(threshold, count_floor)),
                              bodies=bodies if counts != 'all' else None)
        extra = [e for e in extra if e[5] >= threshold]
    else:
        extra = []
    for k in order:
        c, gy, gx = int(cs[k]), int(ys[k]), int(xs[k]); owner, ident = divmod(c, nb)
        if bodies[ident].startswith('fx:'):
            effects.append(dict(identity=bodies[ident], owner=owner, x=(gx+float(out['body_box'][b, 0, gy, gx])+0.)/2,
                                y=(gy+float(out['body_box'][b, 1, gy, gx])+0.)/2, score=float(heat[c, gy, gx])))
            continue
        if offsets:  # live-dense-v1: body_box[0:2] = sub-cell offset; returns x = (gx+off)/2 below
            fx, fy = gx+float(out['body_box'][b, 0, gy, gx])-.5, gy+float(out['body_box'][b, 1, gy, gx])-.5
        elif refine_pos:
            fx, fy = refine(heat, c, gy, gx)
        else:
            fx, fy = gx, gy
        units.append(dict(identity=bodies[ident], owner=owner, x=(fx+.5)/2, y=(fy+.5)/2, score=float(heat[c, gy, gx]),
                          hp_frac=float(hp[gy, gx]) if (offsets or hpv[gy, gx] >= .5) else None))
    for c, gy, gx, fx, fy, sc in extra:
        owner, ident = divmod(int(c), nb)
        units.append(dict(identity=bodies[ident], owner=owner, x=(fx+.5)/2, y=(fy+.5)/2, score=sc, hp_frac=float(hp[gy, gx]),
                          counted=True))
    towers = []
    for owner, kind, side, ax, ay in TOWER_SLOTS:
        ident = bodies.index('KingTower' if kind == 'king' else 'PrincessTower'); c = owner*nb+ident
        gx, gy = int(ax/500), int(ay/500)
        y0, x0 = max(0, gy-2), max(0, gx-2)
        win = heat[c, y0:gy+3, x0:gx+3]
        wy, wx = np.unravel_index(int(win.argmax()), win.shape)
        towers.append(dict(owner=owner, kind=kind, side=side, score=float(win.max()),
                           hp_frac=float(hp[y0+wy, x0+wx])))
    probs = np.exp(out['hud_cards'][b]-out['hud_cards'][b].max(-1, keepdims=True)); probs /= probs.sum(-1, keepdims=True)
    ids = probs.argmax(-1)
    names = [cards[i] if i < len(cards) else None for i in ids]
    digit = int(out['elixir_digit'][b].argmax())
    return dict(units=units, effects=effects, towers=towers, hand=names[:4], next=names[4], hand_prob=[float(probs[j, ids[j]]) for j in range(5)],
                hand_probs=probs, elixir_digit=digit, elixir=min(10., digit+float(out['elixir_fraction'][b])),
                clock=float(out['clock_seconds'][b]), phase=int(out['phase'][b].argmax())+1)


def frame_record(dec, timestamp_ms=None, tower_threshold=.5, events=()):
    """Downstream bot-adapter schema (LIVE LEAD request, 2026-10-14). Own-perspective coordinates."""
    units = []
    for u in dec['units']:
        if u['identity'] in TOWER_BODIES:
            continue
        owner, x, y = own_view(u['owner'], u['x'], u['y'])
        units.append(dict(cls=u['identity'], card=body_card(u['identity']), owner=owner, x=round(x, 3), y=round(y, 3),
                          hp_frac=None if u['hp_frac'] is None else round(u['hp_frac'], 4), score=round(u['score'], 4),
                          **({'counted': True} if u.get('counted') else {})))
    towers = []
    for t in dec['towers']:
        owner, _, _ = own_view(t['owner'], 9, 16)
        side = t['side']  # screen left/right (x unchanged by own_view)
        alive = t['score'] >= tower_threshold
        towers.append(dict(owner=owner, kind=t['kind'], side=side, alive=bool(alive),
                           hp_frac=round(t['hp_frac'], 4) if alive else 0.0, score=round(t['score'], 4)))
    evs = []
    for e in events:
        owner, x, y = own_view(e['side'], e['x_tiles'], e['y_tiles'])
        evs.append(dict(owner=owner, card=e['card'], x=round(x, 3), y=round(y, 3),
                        tick=round(float(e['execution_timestamp_ms']), 1), score=round(float(e['existence_q']), 4)))
    fx = [dict(card=e['identity'][3:], owner=own_view(e['owner'], e['x'], e['y'])[0], x=round(e['x'], 3),
               y=round(32.-e['y'], 3), score=round(e['score'], 4)) for e in dec.get('effects', ())]
    return dict(timestamp_ms=timestamp_ms, units=units, towers=towers, **(dict(effects=fx) if fx else {}),
                hand=dict(cards=dec['hand'], probs=[round(p, 4) for p in dec['hand_prob'][:4]],
                          next=dec['next'], next_prob=round(dec['hand_prob'][4], 4)),
                elixir=round(dec['elixir'], 3), clock_s=round(dec['clock'], 2), phase=dec['phase'], events=evs,
                schema='clasher.live.perception-frame.v1', hp_kind='fraction_of_max',
                event_tick_unit='ms on the caller timestamp clock (estimated execution time)')
