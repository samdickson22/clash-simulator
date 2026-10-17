"""05: label READY raw night chunks -> /mpac/sdicks02/scratch/nulls/night/i<N>/<run>/chunk-*/ (+READY), coverage.

  python -B label.py            loop forever (nice 19), also rewrites coverage-night.{json,md} every few minutes
  python -B label.py --once     one pass

Per frame JSON (night-label-3, agreed with live-perc-r3): native objects with exact team, kind, class, phase, HP,
deploy clock, effects, and a candidate pixel box from background differencing (ground-anchor assignment, shadow and
HUD overlays removed). Images / observations are hard links of the raw files; nothing is re-encoded.
Team: 0 = ours = bottom = native owner 1; 1 = opponent = top = native owner 0 (classes.json `belong`).
"""
import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict, deque
from pathlib import Path

import cv2
import numpy as np

cv2.setNumThreads(1)  # 05 is light-only: one core per labeller

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from overlay import Overlays  # noqa: E402

NIGHT = Path(os.environ.get('NULLS_NIGHT', '/mpac/sdicks02/scratch/nulls/night'))
RAW = NIGHT / 'raw'
DETS = NIGHT / 'dets'
REPO = HERE.parent.parent.parent
CLASSES = json.loads((REPO / 'live/yolo_synth/classes.json').read_text())
VOCAB = {n['name']: n for n in CLASSES['names']}
BODY_MAP = json.loads((HERE / 'body_name_map.json').read_text())['bodies']
BY_DGID = {int(v['catalog_id']): (k, v) for k, v in BODY_MAP.items() if str(v.get('catalog_id') or '').isdigit()}
CARDS = {c['id']: c for c in json.loads((HERE.parent / 'cards.json').read_text())}

# Native milli-tiles -> full 1080x2280 frame px. Replay layout measured at 1080x1920 (block 1: x = 540 + 48(tx-9),
# y = 1021 + 38.5(ty-16)) plus the candidate 180 px letterbox of the 1080x1920 wm size inside the 2280 panel.
# Verified / corrected by Sol on the first real frames (VIEWPORT_VERIFIED).
VIEWPORT = [0, 180, 1080, 2100]
AX, BX, AY, BY = 0.048, 108.0, 0.0385, 405.0 + VIEWPORT[1]
TOWER_IDS = range(5000000, 5000006)
# tower visual centre minus native ground anchor (px), measured by Sol on real night frames 10:05Z (+-4 px)
TOWER_VISUAL_DY = {('opp', 'king'): -50.5, ('own', 'king'): -34.5, ('opp', 'queen'): -37.0, ('own', 'queen'): -37.0}
VIEWPORT_VERIFIED = True  # Sol 10:05Z: upright, game area y 180-2100, black bands 0-179 / 2100-2279


def px(x, y):
    return AX * x + BX, AY * y + BY


DGID_COUNTS = Path('/mpac/sdicks02/scratch/nulls/client-tables/dgid_counts.json')
_EMP = {'mtime': None, 'map': {}}


def empirical():
    """dgid -> body learned from our own deployments (dgid_learn.py); reloaded when the file changes."""
    try:
        mt = DGID_COUNTS.stat().st_mtime
    except OSError:
        return _EMP['map']
    if mt != _EMP['mtime']:
        m = {}
        for dg, bodies in json.loads(DGID_COUNTS.read_text()).items():
            n = sum(bodies.values())
            b, k = max(bodies.items(), key=lambda kv: kv[1])
            if n >= 2 and k / n >= .8:
                m[int(dg)] = b
        _EMP.update(mtime=mt, map=m)
    return _EMP['map']


def resolve_body(o):
    """(body, body_map_entry, source). The probe's dataGlobalId order differs from the CSV/catalog order for later
    characters, so learned ids win; catalog ids are trusted only where the learned map agrees (else unverified)."""
    dg = o.get('dataGlobalId')
    emp = empirical()
    if dg in emp:
        b = emp[dg]
        if b not in BODY_MAP:  # a 15.535 body missing from the snapshot catalog: proposed name, out of vocab
            kind = 'building' if isinstance(dg, int) and dg // 1000000 == 35 else 'troop'
            BODY_MAP[b] = dict(status='new', kind=kind,
                               proposed_name=re.sub(r'(?<!^)(?=[A-Z])', '-', b).lower().replace('_', '-'))
        return b, BODY_MAP[b], 'empirical'
    body, entry = BY_DGID.get(dg, (None, None))
    if body is None:
        return None, None, 'unresolved'
    if o['nativeObjectId'] in TOWER_IDS or o.get('projectile') or (entry or {}).get('kind') not in ('troop', 'building'):
        return body, entry, 'catalog'  # towers / projectiles / spell objects: never boxed as bodies
    return body, entry, 'catalog_unverified'


def kind_of(o, body, entry):
    if o['nativeObjectId'] in TOWER_IDS or (entry or {}).get('kind') == 'tower':
        return 'tower'
    if o.get('projectile'):
        return 'projectile'
    k = (entry or {}).get('kind')
    if k in ('troop', 'building'):
        return 'unit' if k == 'troop' else 'building'
    if k == 'spell' or (entry or {}).get('status') == 'skip':
        why = (entry or {}).get('why', '')
        return 'projectile' if 'projectile' in why.lower() and o.get('projectile') else 'spell'
    card = CARDS.get(o.get('cardId'))
    if card:
        return {'troop': 'unit', 'building': 'building', 'spell': 'spell'}[card['kind']]
    return 'effect'


def effects_of(o):
    """Buff names from the probe: 'ZapFreeze' is Zap's short stun, 'Freeze' the Freeze spell."""
    eff = o.get('activeEffects') or []
    flags = []
    for e in eff:
        n = str(e.get('name') or '').lower()
        if 'zap' in n or 'stun' in n or 'electro' in n:
            flags.append('stunned')
        elif 'freeze' in n:
            flags.append('frozen')
        elif 'slow' in n:
            flags.append('slowed')
        elif 'rage' in n:
            flags.append('raged')
        else:
            flags.append(n or 'effect')
    return eff, sorted(set(flags))


def phase_of(o, prev, flags, hitters=()):
    """deploy | frozen | stunned | attack_hit (fired/struck this step per combat events) | attack_windup (load
    timer running) | attack_recovery (in the attack cycle after the hit) | walk | idle."""
    ph = o.get('phaseRuntime') or {}
    if (ph.get('deployRemainingMs') or 0) > 0:
        return 'deploy'
    if 'frozen' in flags:
        return 'frozen'
    if 'stunned' in flags:
        return 'stunned'
    if o['nativeObjectId'] in hitters:
        return 'attack_hit'
    moving = prev is not None and abs(o['x'] - prev['x']) + abs(o['y'] - prev['y']) > 5
    if not moving and (ph.get('loadRemainingMs') or 0) > 0:
        return 'attack_windup'
    if not moving and (ph.get('attackTimelineMs') or 0) > 0:
        return 'attack_recovery'
    return 'walk' if moving else 'idle'


def hitters_of(rich, stride):
    """Objects that dealt damage or launched a projectile within the last `stride` ticks (combat event ring)."""
    tick = rich['tick']
    out = set()
    for e in (rich.get('combatEvents') or {}).get('events') or []:
        # an event stamped tick T first appears in the observation of tick T+1 (the frame that shows the hit)
        if e.get('kind') in ('damage', 'projectile_spawn') and tick - (stride or 1) - 1 < e.get('tick', -10**9) <= tick:
            for role in ('source', 'immediateSource'):
                src = e.get(role) or {}
                if src.get('present') and src.get('nativeObjectId') is not None:
                    out.add(src['nativeObjectId'])
    return out


def main_body(mask, rel=.25, gap=6):
    m = mask.astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    if n <= 1:
        return m > 0
    big = 1 + int(np.argmax(st[1:, 4]))
    bx, by, bw, bh, ba = st[big]

    def near(i, g):
        return (st[i, 0] <= bx + bw + g and bx <= st[i, 0] + st[i, 2] + g
                and st[i, 1] <= by + bh + g and by <= st[i, 1] + st[i, 3] + g)
    keep = [big] + [i for i in range(1, n) if i != big and (near(i, gap) or (st[i, 4] >= rel * ba and near(i, 3 * gap)))]
    return np.isin(lab, keep)


PRIORS = defaultdict(lambda: deque(maxlen=200))  # class -> recent clean (w, h, centre dx, bottom dy) from unsplit boxes


def prior_key(r):
    return (r['class_name'], r['phase'].startswith('attack'))


def prior_ellipse(r):
    ax, ay = r['anchor_px']
    p = PRIORS.get(prior_key(r))
    if not p or len(p) < 5:
        p = PRIORS.get((r['class_name'], False))
    if p and len(p) >= 5:
        w, h, dx, dy2 = np.median(np.array(p), 0)
    else:
        air = bool((VOCAB.get(r['class_name']) or {}).get('air'))
        w, h, dx, dy2 = 70.0, 90.0, 0.0, (-45.0 if air else 6.0)
    return ax + dx, ay + dy2 - h / 2, max(w / 2, 12.0), max(h / 2, 12.0)


class RunState:
    def __init__(self, bg_imgs):
        stack = np.stack([b.astype(np.int16) for b in bg_imgs])
        self.bg = np.median(stack, 0).astype(np.int16)
        noise = np.abs(stack - self.bg).max(0).max(-1).astype(np.uint8)
        self.noise = cv2.dilate(noise, np.ones((5, 5), np.uint8)).astype(np.int32)
        h, w = self.bg.shape[:2]
        self.roi = np.zeros((h, w), bool)
        self.roi[max(0, int(px(0, -1500)[1])):min(h, int(px(0, 33500)[1]))] = True
        self.prev = {}
        self.last_seen = {}  # id -> (obj, tick, entry)


OVERLAYS = None


def label_frame(img, obs, rs, meta):
    global OVERLAYS
    OVERLAYS = OVERLAYS or Overlays()
    rich = obs['before']
    tick = rich['tick']
    h, w = img.shape[:2]
    objs = [o for o in rich['objects'] if not o.get('null')]
    hitters = hitters_of(rich, meta.get('tick_stride'))
    rows = []
    for o in objs:
        body, entry, body_source = resolve_body(o)
        kind = kind_of(o, body, entry)
        name = (entry or {}).get('name') or (entry or {}).get('proposed_name')
        eff, flags = effects_of(o)
        ax, ay = px(o['x'], o['y'])
        hp, mhp = o.get('hp'), o.get('maxHp')
        ph = o.get('phaseRuntime') or {}
        rows.append(dict(
            object_id=o['nativeObjectId'], kind=kind, body_name=body, body_source=body_source, class_name=name,
            class_idx=VOCAB[name]['idx'] if name in VOCAB else None, in_vocab=name in VOCAB,
            native_owner=o.get('owner'), team=(1 - o['owner']) if o.get('owner') in (0, 1) else None,
            card_id=o.get('cardId'), data_global_id=o.get('dataGlobalId'), x=o['x'], y=o['y'],
            anchor_px=[round(ax, 1), round(ay, 1)], hp=hp, max_hp=mhp,
            hp_frac=round(hp / mhp, 4) if hp is not None and mhp else None,
            hp_bar_visible=bool(kind != 'tower' and hp is not None and mhp and hp < mhp),
            phase=phase_of(o, rs.prev.get(o['nativeObjectId']), flags, hitters), effect_flags=flags, effects=eff,
            attack_stage=o.get('attackSequenceStage'), attack_timeline_ms=ph.get('attackTimelineMs'),
            load_remaining_ms=ph.get('loadRemainingMs'), deploy_remaining_ms=ph.get('deployRemainingMs'),
            visibility=o.get('visibilityState'), target=o.get('targetEntityKey'),
            facing='R' if (o.get('targetX') if o.get('targetX') is not None else o['x']) >= o['x'] else 'L',
            box=None, box_source=None, box_flags=[]))
    ids_now = {r['object_id'] for r in rows}
    # recently vanished bodies: death animation candidates
    for k, (r0, t0) in list(rs.last_seen.items()):
        if k in ids_now or tick - t0 > 14:
            if tick - t0 > 14:
                del rs.last_seen[k]
            continue
        d = dict(r0, phase='death', hp=0, hp_frac=0.0, hp_bar_visible=False, box=None, box_source=None,
                 box_flags=['vanished'], vanished_ticks=tick - t0)
        rows.append(d)
    # --- pixel boxes
    d = np.abs(img.astype(np.int16) - rs.bg).max(-1)
    changed = (d > np.maximum(28, rs.noise * 2 + 8)) & rs.roi
    # hysteresis (v2): body sprites are high-contrast against the arena; walking dust, deploy debris and faint
    # residue are weak changes. Weak pixels count only within 4 px of a strong one.
    strong = (d > np.maximum(60, rs.noise * 2 + 30)) & rs.roi
    near_strong = cv2.dilate(strong.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
    spawning = any(r['phase'] == 'deploy' for r in rows)
    damaged = [tuple(r['anchor_px']) for r in rows if r['hp_bar_visible']]
    ov_mask, ov_items = OVERLAYS.detect(img, changed, spawning, damaged)
    m = changed & near_strong & ~ov_mask
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lab, stats, cent = cv2.connectedComponentsWithStats(m, 8)
    towers = [r for r in rows if r['kind'] == 'tower' and r['phase'] != 'death']
    tower_boxes = []
    for t in towers:
        tx, ty = t['anchor_px']
        tower_boxes.append((tx - 95, ty - 190, tx + 95, ty + 55) if abs(t['x'] - 9000) < 500 else
                           (tx - 75, ty - 160, tx + 75, ty + 45))
    sinks = [r for r in rows if r['kind'] != 'tower']
    for t in towers:  # pixel sinks only (never boxed): ellipse around the tower's visual centre
        king = abs(t['x'] - 9000) < 500
        side = 'opp' if t['team'] == 1 else 'own'
        cy = t['anchor_px'][1] + TOWER_VISUAL_DY[(side, 'king' if king else 'queen')]
        sinks.append(dict(t, _ell=(t['anchor_px'][0], cy, 100.0 if king else 80.0, 115.0 if king else 95.0)))
    anchors = np.array([r['anchor_px'] for r in sinks]) if sinks else np.zeros((0, 2))
    parts = defaultdict(list)
    split = set()
    for i in range(1, n):
        bx, by, bw, bh, area = stats[i]
        if area < 40:
            continue
        if any(bx >= X1 and by >= Y1 and bx + bw <= X2 and by + bh <= Y2 for X1, Y1, X2, Y2 in tower_boxes):
            continue
        if not len(anchors):
            continue
        inside = [j for j, (ax, ay) in enumerate(anchors) if bx - 40 <= ax <= bx + bw + 40 and by - 40 <= ay <= by + bh + 90]
        if not inside:
            dist = np.hypot(anchors[:, 0] - cent[i][0], anchors[:, 1] - cent[i][1])
            j = int(dist.argmin())
            if dist[j] < 170:
                inside = [j]
        if not inside:
            continue
        blob = lab[by:by + bh, bx:bx + bw] == i
        if len(inside) == 1:
            parts[inside[0]].append((bx, by, blob))
            continue
        ys, xs = np.nonzero(blob)
        # shared blob: each pixel goes to the body whose class-size ellipse (learned from clean boxes) fits it best
        ell = np.array([sinks[j].get('_ell') or prior_ellipse(sinks[j]) for j in inside])  # cx, cy, w/2, h/2
        dist = (((xs[:, None] + bx - ell[None, :, 0]) / ell[None, :, 2]) ** 2
                + ((ys[:, None] + by - ell[None, :, 1]) / ell[None, :, 3]) ** 2)
        near = dist.argmin(1)
        for jj, j in enumerate(inside):
            sel = near == jj
            if sel.any():
                sub = np.zeros_like(blob)
                sub[ys[sel], xs[sel]] = True
                parts[j].append((bx, by, sub))
                split.add(j)
    for j, plist in parts.items():
        r = sinks[j]
        if r['kind'] not in ('unit', 'building'):
            continue
        if r['phase'] == 'death':
            r['box_flags'].append('death_anim_pixels')
            continue
        x1 = min(p[0] for p in plist); y1 = min(p[1] for p in plist)
        x2 = max(p[0] + p[2].shape[1] for p in plist); y2 = max(p[1] + p[2].shape[0] for p in plist)
        mask = np.zeros((y2 - y1, x2 - x1), bool)
        for bx, by, blob in plist:
            mask[by - y1:by - y1 + blob.shape[0], bx - x1:bx - x1 + blob.shape[1]] |= blob
        ci = img[y1:y2, x1:x2].astype(np.float32) + 1
        ratio = ci / (rs.bg[y1:y2, x1:x2].astype(np.float32) + 1)
        shadow = (ratio.max(-1) < .93) & (ratio.min(-1) > .3) & (ratio.max(-1) - ratio.min(-1) < .08)
        body = main_body(mask & ~shadow)
        if body.sum() < 30:
            r['box_flags'].append('tiny_mask')
            continue
        ys, xs = np.nonzero(body)
        box = [int(x1 + xs.min()), int(y1 + ys.min()), int(x1 + xs.max() + 1), int(y1 + ys.max() + 1)]
        ax, ay = r['anchor_px']
        air = bool((VOCAB.get(r['class_name']) or {}).get('air'))
        if not air and r['kind'] == 'unit':  # ground troops stand on their anchor: below it is shadow / effect
            box[3] = min(box[3], int(ay + 14))
        if j in split:
            r['box_flags'].append('split')
        effect_near = bool(set(r['effect_flags']) & {'stunned', 'frozen', 'slowed'}) or any(
            s_['kind'] == 'spell' and abs(s_['anchor_px'][0] - ax) < 260 and abs(s_['anchor_px'][1] - ay) < 260
            for s_ in sinks)
        if effect_near:
            r['box_flags'].append('effect_overlap')
            if not r['phase'].startswith('attack'):
                cx, cy, hw, hh = prior_ellipse(r)
                box = [max(box[0], int(cx - 1.5 * hw)), max(box[1], int(cy - 1.5 * hh)),
                       min(box[2], int(cx + 1.5 * hw)), min(box[3], int(cy + 1.5 * hh))]
        if box[2] - box[0] < 6 or box[3] - box[1] < 6:
            r['box_flags'].append('degenerate')
            continue
        r['box'] = box
        r['box_source'] = 'diff'
        if any(abs(r['anchor_px'][0] - t['anchor_px'][0]) < 110 and abs(r['anchor_px'][1] - t['anchor_px'][1]) < 130
               for t in towers):
            r['box_flags'].append('near_tower')
        if not r['box_flags'] and r['phase'] not in ('death', 'deploy') and r['class_name']:
            PRIORS[prior_key(r)].append((box[2] - box[0], box[3] - box[1], (box[0] + box[2]) / 2 - ax, box[3] - ay))
    # HUD overlays found in the frame (badge / HP bar / deploy dial): owner from badge colour, nearest body
    hud = []
    for it in ov_items:
        x1, y1, x2, y2 = it['box']
        cx = (x1 + x2) / 2
        cand = [r for r in rows if r['kind'] in ('unit', 'building') and abs(r['anchor_px'][0] - cx) < 110
                and -40 < r['anchor_px'][1] - y2 < 240]
        best = min(cand, key=lambda r: (r['anchor_px'][0] - cx) ** 2 + (r['anchor_px'][1] - y2) ** 2) if cand else None
        hud.append(dict(type=it['type'], box=it['box'], badge_team=(1 - it['owner']) if it.get('owner') in (0, 1) else None,
                        object_id=best['object_id'] if best else None))
    for r in rows:
        r['hud'] = [hh for hh in hud if hh['object_id'] == r['object_id']]
    resolve_boxes(rows, meta.get('_dets'), rs)
    # state for the next frame
    for o, r in zip(objs, rows):
        if r['kind'] in ('unit', 'building'):
            rs.last_seen[o['nativeObjectId']] = (r, tick)
    rs.prev = {o['nativeObjectId']: o for o in objs}
    visible = [r for r in rows if r['kind'] in ('unit', 'building') and r.get('visibility', 'visible') == 'visible'
               and r['phase'] != 'death']
    # complete: synced fresh frame, every visible body boxed AND its identity learned from our own deploys
    complete = bool(meta.get('sync')) and meta.get('render_fresh') is not False \
        and all(r['box'] is not None and r.get('body_source') == 'empirical' for r in visible)
    calib = {}
    for t in towers:
        side = 'opp' if t['team'] == 1 else 'own'
        if abs(t['x'] - 9000) < 500:
            key, dy = f'{side}_king', TOWER_VISUAL_DY[(side, 'king')]
        else:
            key, dy = f"{side}_{'left' if t['x'] < 9000 else 'right'}", TOWER_VISUAL_DY[(side, 'queen')]
        calib[key] = [round(t['anchor_px'][0], 1), round(t['anchor_px'][1] + dy, 1)]
    return rows, complete, calib


FIT = defaultdict(lambda: deque(maxlen=300))  # (class, attack?, facing) -> trusted (w, h, centre dx, bottom dy)
AGREE_PX = 5


def side_gap(a, b):
    return max(abs(x - y) for x, y in zip(a, b)) if a and b else None


def box_iou(a, b):
    if not a or not b:
        return 0.0
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix * iy
    return ix * iy / u if u > 0 else 0.0


def fit_key(r):
    return (r['class_name'], r['phase'].startswith('attack'), r.get('facing', 'R'))


def match_dets(bodies, dets):
    """Hungarian match of detector boxes (unit classes) to native bodies on body-centre distance; team/class aware."""
    from scipy.optimize import linear_sum_assignment
    cand = [d for d in dets if (VOCAB.get(d[4]) or {}).get('kind') not in ('tower', 'spell', 'object', 'ui', 'unknown')]
    out = {}
    if not bodies or not cand:
        return out
    cost = np.full((len(bodies), len(cand)), 1e6)
    for i, r in enumerate(bodies):
        cx, cy, hw, hh = prior_ellipse(r)
        air = bool((VOCAB.get(r['class_name']) or {}).get('air'))
        for j, d in enumerate(cand):
            dx = ((d[0] + d[2]) / 2 - cx) / max(2 * hw, 30)
            dy = ((d[1] + d[3]) / 2 - cy) / max(2 * hh, 30) / (1.6 if air else 1.0)
            dist = (dx * dx + dy * dy) ** .5
            if dist <= 1.0:
                cost[i, j] = dist + (0 if d[5] == r['team'] else .6) + (0 if d[4] == r['class_name'] else .3)
    for i, j in zip(*linear_sum_assignment(cost)):
        if cost[i, j] < 1e5:
            out[bodies[i]['object_id']] = cand[j]
    return out


def resolve_boxes(rows, dets, rs):
    """v3 box policy (LEAD 10-17): `box` only when the x1h detector box and the diff box agree within AGREE_PX on every
    side (Sol: 89 % ok). Every proposal is kept: box_diff, box_det (+conf/cls/belong), box_fit (per class x phase x
    facing geometry at the native anchor, isolated bodies only), box_split (solo swarm diff split). r3 admits by method."""
    bodies = [r for r in rows if r['kind'] in ('unit', 'building') and r['phase'] != 'death']
    for r in rows:
        r['box_diff'], r['box_diff_flags'] = r['box'], list(r['box_flags'])
        r['box'] = None
        r['box_method'] = 'none'
    dm = match_dets(bodies, dets) if dets is not None else {}
    for r in bodies:
        d = dm.get(r['object_id'])
        if d is not None:
            r['box_det'] = [int(round(v)) for v in d[:4]]
            r['det_conf'], r['det_cls'], r['det_belong'] = round(float(d[6]), 3), d[4], d[5]
        bd, bf = r.get('box_det'), r['box_diff']
        gap = side_gap(bd, bf)
        r['box_agree'] = dict(side_px=gap, iou=round(box_iou(bd, bf), 3)) if bd and bf else None
        if bd and bf and gap <= AGREE_PX:
            r['box'], r['box_method'], r['box_source'] = bd, 'x1h_agreed', 'x1h_agreed'
            if r['class_name']:
                ax, ay = r['anchor_px']
                cx = (bd[0] + bd[2]) / 2 - ax
                FIT[fit_key(r)].append((bd[2] - bd[0], bd[3] - bd[1], cx if r.get('facing') == 'R' else -cx, bd[3] - ay))
        else:
            r['box_method'] = 'x1h_only' if bd else 'diff_only' if bf else 'none'
            if dets is None:
                r['box_method'] = 'no_dets_yet'
        if 'split' in r['box_diff_flags'] and bf:
            r['box_split'] = bf  # solo-run swarm split (pixels to the nearest class ellipse); held until Sol-graded
    # anchor_fit for untrusted ISOLATED bodies (no other body within 1.5 tiles)
    for r in bodies:
        if r['box'] is not None:
            continue
        if any(o is not r and ((o['x'] - r['x']) ** 2 + (o['y'] - r['y']) ** 2) ** .5 < 1500 for o in bodies):
            continue
        f = FIT.get(fit_key(r))
        if not f or len(f) < 5:
            continue
        w, h, dx, dy2 = np.median(np.array(f), 0)
        ax, ay = r['anchor_px']
        cx = ax + (dx if r.get('facing') == 'R' else -dx)
        r['box_fit'] = [int(cx - w / 2), int(ay + dy2 - h), int(cx + w / 2), int(ay + dy2)]


def hand_from_obs(plain):
    """Exact hands from the native plain observe: ours = native owner 1 (bottom). slots in hand order."""
    out = {}
    for pl in plain.get('players', []):
        hand = sorted(pl.get('hand', []), key=lambda c: c.get('handIndex', 0))
        nm = lambda cid: (CARDS.get(cid) or {}).get('name')
        out['ours' if pl.get('owner') == 1 else 'opp'] = dict(
            slots=[c['cardId'] for c in hand], slot_names=[nm(c['cardId']) for c in hand],
            slot_costs=[c.get('cost') for c in hand], next=(pl.get('nextCard') or {}).get('cardId'),
            next_name=nm((pl.get('nextCard') or {}).get('cardId')), elixir=pl.get('elixir'),
            cycle=[c['cardId'] for c in sorted(pl.get('cycle', []), key=lambda c: c.get('cycleIndex', 0))])
    return out


def hand_of(meta):
    h = meta.get('hand') or {}
    # native owner 1 = ours (bottom)
    return dict(ours=h.get('1'), opp=h.get('0'))


def process_chunk(raw_chunk, out_chunk, states):
    run = raw_chunk.parent.name
    metas = sorted((json.loads(p.read_text()) for p in raw_chunk.glob('*.json')
                    if p.name not in ('manifest.json', 'events.json')), key=lambda m: (m['purpose'] != 'background', m['tick'], m['frame']))
    out_chunk.mkdir(parents=True, exist_ok=True)
    for name in ('manifest.json', 'events.json'):
        if (raw_chunk / name).exists() and not (out_chunk / ('raw-' + name)).exists():
            os.link(raw_chunk / name, out_chunk / ('raw-' + name))
    bgs = [cv2.imread(str(raw_chunk / m['frame'])) for m in metas if m['purpose'] == 'background']
    if bgs:
        states[run] = RunState(bgs)
    rs = states.get(run)
    counts = Counter()
    (out_chunk / 'READY').unlink(missing_ok=True)  # readers never see a half-rewritten chunk as complete
    det_file = DETS / raw_chunk.relative_to(RAW) / 'dets.json'
    det_ready = (det_file.parent / 'READY').exists()
    dets = json.loads(det_file.read_text())['frames'] if det_ready else {}
    for m in metas:
        for key in ('frame', 'png', 'observations'):
            if m.get(key) and not (out_chunk / m[key]).exists():
                os.link(raw_chunk / m[key], out_chunk / m[key])
        rec = dict(version='night-label-3', **{k: m.get(k) for k in (
            'frame', 'png', 'observations', 'run', 'card', 'card_id', 'card_kind', 'purpose', 'tick', 'tick_stride',
            'time_scale', 'stepping', 'frame_shape', 'wm_size', 'location', 'seed', 'instance', 'wall_epoch', 'client',
            'sync', 'render_wait_s', 'render_fresh')})
        rec.update(viewport=VIEWPORT, viewport_verified=VIEWPORT_VERIFIED,
                   native_milli_to_frame=[[AX, 0, BX], [0, AY, BY]], transform_verified=VIEWPORT_VERIFIED,
                   bottom_native_owner=1, team_rule='team = 1 - native_owner (0 ours/bottom, 1 opp/top)',
                   hand=hand_of(m), qa=dict(checked=False, verdict=None), deployments=m.get('deployments'))
        if m['purpose'] == 'background' or rs is None:
            rec.update(objects=[], complete=False, arena_calib=None,
                       note='empty-arena background frame' if m['purpose'] == 'background' else 'no background for run')
        else:
            img = cv2.imread(str(raw_chunk / m['frame']))
            with gzip.open(raw_chunk / m['observations'], 'rt') as f:
                obs = json.load(f)
            m['_dets'] = dets.get(Path(m['frame']).stem) if det_ready else None
            rows, complete, calib = label_frame(img, obs, rs, m)
            rec.update(objects=rows, complete=complete, arena_calib=calib, hand=hand_from_obs(obs.get('plain') or {}))
            counts['frames'] += 1
            counts['complete'] += complete
        tmp = out_chunk / ('.' + m['frame'].replace('.jpg', '.json') + '.part')
        tmp.write_text(json.dumps(rec, separators=(',', ':')))
        os.replace(tmp, out_chunk / m['frame'].replace('.jpg', '.json'))
    if rs is not None and not (out_chunk.parent / 'clean_plate.png').exists():
        cv2.imwrite(str(out_chunk.parent / 'clean_plate.png'), rs.bg.astype(np.uint8))  # empty-arena median (paint-out)
    if det_ready:
        (out_chunk / 'DETS').write_text('x1h\n')
    else:
        (out_chunk / 'DETS').unlink(missing_ok=True)
    (out_chunk / 'READY').write_text(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()) + '\n')
    return counts


def coverage():
    cov = defaultdict(Counter)
    frames = Counter()
    for p in NIGHT.glob('i*/*/chunk-*/*.json'):
        if p.name.startswith('raw-'):
            continue
        try:
            rec = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        if rec.get('purpose') != 'scene':
            continue
        frames['frames'] += 1
        frames['complete'] += bool(rec.get('complete'))
        for o in rec.get('objects', []):
            if o['kind'] in ('unit', 'building') and o.get('body_source') == 'empirical':
                ph = o['phase']
                key = f"{o['class_name'] or o['body_name']}|{o['team']}"
                cov[key][ph] += 1
                if o['hp_bar_visible']:
                    cov[key]['hp_bar'] += 1
                if o['box']:
                    cov[key]['boxed'] += 1
                if o.get('box_det'):
                    cov[key]['det'] += 1
                if o.get('box_fit'):
                    cov[key]['fit'] += 1
    out = dict(updated=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), totals=frames,
               coverage={k: dict(v) for k, v in sorted(cov.items())})
    (NIGHT.parent / 'coverage-night.json').write_text(json.dumps(out, indent=1))
    phases = ['deploy', 'walk', 'idle', 'attack_windup', 'attack_hit', 'attack_recovery', 'stunned', 'frozen',
              'death', 'hp_bar', 'boxed', 'det', 'fit']
    lines = [f"# Null's night coverage ({out['updated']})", '',
             f"scene frames {frames['frames']}, complete {frames['complete']}. Counts are object-instances per phase "
             '(team 0 = ours/bottom, 1 = opp/top); identities learned from our deploys only. hp_bar = HP bar shown; boxed = x1h_agreed box; det = x1h box matched; fit = anchor-fit proposal.', '',
             '|class|team|' + '|'.join(phases) + '|', '|---|---|' + '---:|' * len(phases)]
    for k, v in sorted(cov.items()):
        c, t = k.rsplit('|', 1)
        lines.append(f'|{c}|{t}|' + '|'.join(str(v.get(p, 0)) for p in phases) + '|')
    (NIGHT.parent / 'coverage-night.md').write_text('\n'.join(lines) + '\n')
    return out


def one_pass(states, inst='*', shard=0, nshards=1):
    done = 0
    for ready in sorted(RAW.glob(f'i{inst}/*/chunk-*/READY'), key=lambda p: (p.parent.parent.name, p.parent.name)):
        raw_chunk = ready.parent
        if nshards > 1 and int(hashlib.md5(raw_chunk.parent.name.encode()).hexdigest(), 16) % nshards != shard:
            continue
        out_chunk = NIGHT / raw_chunk.relative_to(RAW)
        has_dets = (DETS / raw_chunk.relative_to(RAW) / 'READY').exists()
        if (out_chunk / 'READY').exists():
            # relabel once the chunk's detector boxes have landed
            if (out_chunk / 'DETS').exists() or not has_dets:
                continue
        elif not has_dets and time.time() - ready.stat().st_mtime < 1200:
            continue  # wait (up to 20 min) for the x1h boxes rather than labelling twice
        run = raw_chunk.parent.name
        if run not in states and raw_chunk.name != 'chunk-000001':
            first = raw_chunk.parent / 'chunk-000001'
            bgs = [cv2.imread(str(first / json.loads(p.read_text())['frame'])) for p in first.glob('*-bg*.json')] \
                if (first / 'READY').exists() else []
            if bgs:
                states[run] = RunState([b for b in bgs if b is not None])
        c = process_chunk(raw_chunk, out_chunk, states)
        while len(states) > 6:  # backgrounds are ~25 MB per run
            states.pop(next(iter(states)))
        done += 1
        print(f"{time.strftime('%H:%M:%SZ', time.gmtime())} {raw_chunk.relative_to(RAW)}: {dict(c)}", flush=True)
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--once', action='store_true')
    ap.add_argument('--inst', default='*', help='only raw/i<inst> (one labeller per capture instance)')
    ap.add_argument('--coverage', action='store_true', help='this labeller also rewrites the coverage files')
    ap.add_argument('--shard', default='0/1', help='k/n: only runs whose name hashes to k mod n')
    a = ap.parse_args()
    os.nice(19)
    states = {}
    last_cov = 0
    while True:
        k, nsh = (int(v) for v in a.shard.split('/'))
        n = one_pass(states, a.inst, k, nsh)
        if (a.coverage or a.inst == '*') and (time.time() - last_cov > 300 or a.once):
            coverage()
            last_cov = time.time()
        if a.once:
            break
        if not n:
            time.sleep(10)


if __name__ == '__main__':
    main()
