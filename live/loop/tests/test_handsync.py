"""handui slot UI + handsync (ReconcilingOwnTracker, SyncSession guard / opening wait) + the s21/s22 replays.
   PYTHONPATH=<repo>:<repo>/src python tests/test_handsync.py [--replay]   (--replay: sync_replay.py on s21-m03, s22-m03)"""
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import handui  # noqa: E402
import handsync  # noqa: E402
from bot.players.base import Decision, WAIT
from bot.live.translate import OwnTracker, LiveSession, own_invariant_breaks  # noqa: E402

checks = []


def check(name, cond):
    checks.append(bool(cond)); print(('PASS ' if cond else 'FAIL ') + name)


# --- handui: synthetic frames at two sizes, then real recorded frames (s21-m03) ---
def frame(w, h, kinds):
    hsv = np.zeros((h, w, 3), np.uint8)
    for (x1, y1, x2, y2), k in zip(handui.SLOT_BOXES, kinds):
        sx, sy = w/1080, h/1920
        box = (slice(int(y1*sy), int(y2*sy)), slice(int(x1*sx), int(x2*sx)))
        if k == 'empty':
            hsv[box] = (106, 243, 100)
        elif k == 'coloured':
            hsv[box] = np.random.default_rng(0).integers((0, 120, 60), (180, 255, 255), hsv[box].shape)
        else:
            hsv[box] = (0, 3, 150)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


kinds = ['coloured', 'greyed', 'empty', 'coloured']
check('slot_ui on a 720x1280 frame', handui.slot_ui(frame(720, 1280, kinds)) == kinds)
check('slot_ui on a 1080x1920 frame', handui.slot_ui(frame(1080, 1920, kinds)) == kinds)
V = Path('/mpac/sdicks02/scratch/live-loop/runs/s21/m03/video')
if V.exists():   # n364: 4 greyed (slot 3 = the greyed Valkyrie); n368: slot 3 empty after it left; n372: 3 coloured
    check('real s21-m03 n364: all greyed', handui.slot_ui(cv2.imread(str(V/'000364.jpg'))) == ['greyed']*4)
    check('real s21-m03 n368: slot 3 empty', handui.slot_ui(cv2.imread(str(V/'000368.jpg')))[3] == 'empty')
    check('real s21-m03 n372: slots 0-2 coloured, 3 empty',
          handui.slot_ui(cv2.imread(str(V/'000372.jpg'))) == ['coloured']*3 + ['empty'])

# --- ReconcilingOwnTracker ---
DECK = ['Valkyrie', 'Archers', 'Minions', 'Cannon', 'Fireball', 'Giant', 'MiniPekka', 'Musketeer']
ORDER = ['Musketeer', 'Fireball', 'MiniPekka', 'Minions', 'Giant', 'Valkyrie', 'Archers', 'Cannon']
C, G, E = 'coloured', 'greyed', 'empty'


def tracker(cls=handsync.ReconcilingOwnTracker):
    return cls(DECK, stats=Counter(), order=ORDER, known=5)


def feed(t, polls, hand, nxt='Giant', ui=None, probs=(.3,)*4, next_prob=.98, tick0=100):
    out = None
    for k in range(polls):
        if hasattr(t, 'ui'):
            t.ui = ui
        out = t.own(tick0 + 5*k, 5., list(hand), nxt, list(probs), next_prob)
    return out


t = tracker()
own = feed(t, 1, ['Musketeer', 'Fireball', 'MiniPekka', 'Valkyrie'], ui=[C]*4)
check('one poll of a coloured disagreement does not sync', own['hand'][3] == 'Minions')
own = feed(t, 1, ['Musketeer', 'Fireball', 'MiniPekka', 'Valkyrie'], ui=[C]*4, tick0=105)
check('2 polls: the coloured read (a queue card) moves into the slot', own['hand'][3] == 'Valkyrie'
      and 'Minions' in own['cycle'] and own_invariant_breaks(own, DECK) == [] and t.stats['own_sync:slot'] == 1)
t = tracker()
own = feed(t, 2, ['Musketeer', 'MiniPekka', 'Fireball', 'Minions'], ui=[C]*4)
check('coloured reads of two held cards swap them (hand stays a permutation)',
      own['hand'] == ['Musketeer', 'MiniPekka', 'Fireball', 'Minions'] and own_invariant_breaks(own, DECK) == [])
for cls, name in ((OwnTracker, 'base'), (handsync.ReconcilingOwnTracker, 'sync')):
    t = tracker(cls)
    own = feed(t, 10, ['Musketeer', 'Fireball', 'MiniPekka', 'Valkyrie'], ui=[G]*4)
    if name == 'base':
        check('base tracker: 10 polls of one greyed misread re-anchor it (the s22-m03 n314 regression)',
              own['hand'][3] == 'Valkyrie' and t.stats['own_reanchor_hud'] >= 1)
    else:
        check('sync tracker: greyed reads never move a card (no re-anchor, no sync)',
              own['hand'][3] == 'Minions' and not t.stats['own_reanchor_hud'] and not t.stats['own_sync:slot'])
t = tracker(); t.busy = {3}
own = feed(t, 5, ['Musketeer', 'Fireball', 'MiniPekka', 'Valkyrie'], ui=[C]*4)
check('the slot of a pending command is not synced', own['hand'][3] == 'Minions')
t = tracker()
own = feed(t, 5, ['Musketeer', 'Fireball', 'MiniPekka', 'Valkyrie'], ui=[C, C, C, E])
check('no sync while a slot is empty (a card slides in)', own['hand'][3] == 'Minions' and not t.stats['own_sync:slot'])
t = tracker()
own = feed(t, 5, ['Musketeer', 'Fireball', 'MiniPekka', 'Valkyrie'], ui=[C]*4, probs=(.3, .3, .3, .05))
check('a coloured read under p .1 is not used', own['hand'][3] == 'Minions')
t = tracker()
own = feed(t, 2, ['Musketeer', 'Fireball', 'MiniPekka', 'Minions'], nxt='Cannon', ui=[C]*4)
check('a confident Next read reorders the queue', own['cycle'][0] == 'Cannon' and own_invariant_breaks(own, DECK) == [])
t = tracker()
own = feed(t, 5, ['Musketeer', 'Fireball', 'MiniPekka', 'Minions'], nxt='Musketeer', ui=[G]*4)
check('a Next read of a held card does not pull it out of the hand', own['hand'][0] == 'Musketeer'
      and own_invariant_breaks(own, DECK) == [])
a, b = tracker(), tracker(OwnTracker)
seq = [(['Musketeer', 'Fireball', 'MiniPekka', 'Valkyrie'], 'Giant')]*6 + [(['Archers', 'Fireball', 'MiniPekka', 'Minions'], 'Cannon')]*6
oa = [feed(a, 1, h, n, ui=None, tick0=100 + 5*i) for i, (h, n) in enumerate(seq)]
ob = [feed(b, 1, h, n, ui=None, tick0=100 + 5*i) for i, (h, n) in enumerate(seq)]
check('without ui the sync tracker is the base tracker', oa == ob)

# --- SyncSession: tap guard + opening wait (stub sessions; the full session is covered by --replay) ---
def guard(hand_tracked, cards, probs, ui):
    st = SimpleNamespace(_rec=dict(hand=dict(cards=cards, probs=probs, ui=ui)), guard_p=handsync.SyncSession.guard_p,
                         tr=SimpleNamespace(own_tracker=SimpleNamespace(hand=hand_tracked)))
    return lambda slot: handsync.SyncSession.tap_guard(st, slot*576 + 100)


H = ['Musketeer', 'Fireball', 'MiniPekka', 'Minions']
g = guard(H, ['Musketeer', 'Fireball', 'MiniPekka', 'Valkyrie'], [.9, .9, .9, .15], [C, C, C, G])
check('guard: greyed slot refused (s21-m03 n364: Minions submitted on a greyed Valkyrie)', g(3) == 'greyed')
check('guard: coloured slot with the same card passes', g(0) is None)
g = guard(H, ['Musketeer', 'Fireball', 'MiniPekka', 'Archers'], [.9, .9, .9, .3], [C, C, C, C])
check('guard: coloured slot read as another card refused', g(3) == 'coloured_mismatch')
g = guard(H, ['Musketeer', 'Fireball', 'MiniPekka', 'Archers'], [.9, .9, .9, .05], [C, C, C, C])
check('guard: a coloured read under p .1 stays unverified', g(3) == 'coloured_unverified')
g = guard(H, ['Musketeer', 'Fireball', 'MiniPekka', None], [.9, .9, .9, 0], [C, C, C, E])
check('guard: empty slot refused', g(3) == 'empty')
st = SimpleNamespace(_rec=dict(hand=dict(cards=H, probs=[.9]*4)), guard_p=.1,
                     tr=SimpleNamespace(own_tracker=SimpleNamespace(hand=H)))
check('guard: no ui -> no verdict (base behaviour)', handsync.SyncSession.tap_guard(st, 3*576) is None)
# Exercise inherited catch-up/pending/decision behavior without loading a Runtime or a model.
def session(action=WAIT, mode='enforce'):
    st = handsync.SyncSession.__new__(handsync.SyncSession)
    st.started, st.last_poll, st.wait_until, st.expire = False, None, 0, 90
    st.seed, st.command_delay, st.own_deck = 0, 27, DECK
    st._buffer, st._evidence, st.log = [], 0, []
    st.guard, st.guarded, st._rec, st._open = mode, [], None, None
    st.hold_reason = st._opening_since = st._refusal_since = st._opening_frame = st._confirm_frame = None
    st._confirm_command = st._confirm_observation = None
    st._opening_frames = st._refusals = 0
    st._frame_ms = 0.
    st.tr = handsync.SyncTranslator.__new__(handsync.SyncTranslator)
    st.tr.own_tracker, st.tr.stats = tracker(), Counter()
    st.tr.plays, st.tr.public_events, st.tr.costs = [[], []], [], dict.fromkeys(DECK, 4)
    st.tr.set_own_order = lambda order, known: st.tr.own_tracker.reset(order, known)
    def information(record):
        for e in record.get('events', ()):
            st.tr.plays[0].append((e['tick'], e['card']))
            st.tr.own_tracker.play(e['tick'], e['card'])
        return SimpleNamespace(tick=record['tick'], own=handsync.SyncTranslator.hud(st.tr, record))
    st.tr.information = information
    st.ch = SimpleNamespace(pending=[], available=True, submitted=0, finished=[])
    def finish(ok):
        st.ch.finished.append(ok)
        st.ch.pending.clear()
        st.ch.available = True
    st.ch.finish = finish
    st.ch.own_packet = lambda info, builder: info
    def submit(info, action, costs, builder):
        st.ch.submitted += 1
        st.ch.pending.append(SimpleNamespace(action=action, card=info.own['hand'][action // 576],
                                            submitted=info.tick))
        st.ch.available = False
    st.ch.submit = submit
    st.rt = SimpleNamespace(R=SimpleNamespace(builder=None, costs=dict.fromkeys(DECK, 4)))
    inner = SimpleNamespace(calls=0, starts=0, search_disabled=False)
    def act(view):
        inner.calls += 1
        return Decision(action)
    def start(ctx):
        inner.starts += 1
    inner.act, inner.start, inner.close = act, start, lambda: None
    st.player = handsync._GuardedPlayer(inner, st)
    return st


def rec(tick, ui=None, cards=H, nxt='Giant', next_prob=.98, probs=None, ts_ms=None):
    return dict(tick=tick, ts_ms=tick*50 if ts_ms is None else ts_ms, elixir=10.,
                hand=dict(cards=list(cards), probs=[.99]*4 if probs is None else probs,
                          next=nxt, next_prob=next_prob, ui=[C]*4 if ui is None else ui))


st = session()
st.step(rec(0, [C, E, C, C]))
st.step(rec(5))
check('opening: empty frame and first reliable full frame wait', not st.started)
st.step(rec(10, nxt='Cannon', next_prob=.01))
check('opening: stable four coloured cards start despite noisy low-confidence Next',
      st.started and st.player.inner.starts == 1 and len(st.tr.own_tracker.hyps) == 24)
st = session()
st.step(rec(0))
st.step(rec(5, ts_ms=0))
check('opening: repeated capture cannot satisfy stability', not st.started)
st.step(rec(10))
check('opening: a distinct stable capture starts', st.started)
for mode in ('empty', 'alternating', 'confidence_none'):
    st = session()
    for k in range(100):
        cards = H if mode != 'alternating' or k % 2 else [H[1], H[0], H[2], H[3]]
        st.step(rec(k*5, [E]*4 if mode == 'empty' else [C]*4, cards=cards,
                    probs=[None]*4 if mode == 'confidence_none' else [.99]*4))
    check('opening: bounded fail-closed hold for ' + mode,
          not st.started and st.hold_reason == 'opening_unreliable' and st.player.inner.calls == 0)

# Reserved sources and destinations remain unchanged in every hypothesis, even after re-anchor thresholds.
t = tracker(); t.busy = {0}
raw = ['Fireball', 'Musketeer', 'MiniPekka', 'Minions']
feed(t, 10, raw, ui=[C]*4, probs=[.99]*4)
check('busy source: no reconciliation/re-anchor moves pending Musketeer in any hypothesis',
      all(h.hand == H for h in t.hyps) and not t.stats['own_sync:slot'])
t = tracker(); t.busy = {0}
t.hyps[-1].hand[0], t.hyps[-1].hand[3] = t.hyps[-1].hand[3], t.hyps[-1].hand[0]
before = [(list(h.hand), list(h.queue)) for h in t.hyps]
feed(t, 2, ['Musketeer', 'Fireball', 'MiniPekka', 'Musketeer'], ui=[G, G, G, C])
check('busy source in a non-best hypothesis vetoes entire swap',
      [(h.hand, h.queue) for h in t.hyps] == before)

st = session(576+100); st.started, st.last_poll = True, 95
st.ch.pending = [SimpleNamespace(action=100, card='Musketeer', submitted=95)]
st.ch.available = False
st.step(rec(100, cards=raw)); st.step(rec(105, cards=raw))
check('pending race: no phantom acknowledgement or untapped replacement command',
      st.ch.finished == [] and st.ch.submitted == 0 and st.tr.own_tracker.hand[0] == 'Musketeer')
# Even an externally changed tracked slot cannot alone acknowledge execution with UI enabled.
st.tr.own_tracker.hyps[st.tr.own_tracker.best].hand[0] = 'Fireball'
st._reconcile(SimpleNamespace(tick=110, own=dict(hand=['Fireball']+H[1:])))
check('HUD-only tracked change cannot acknowledge pending command', st.ch.finished == [])

st = session(); st.started, st.last_poll = True, 100
st.step(rec(115, cards=H[:3]+['Valkyrie']))
check('capture gap: two inherited catchups count as one reconciliation frame',
      st.tr.stats['catchup_polls'] == 2 and st.tr.own_tracker.hand[3] == 'Minions')
st.step(rec(120, cards=H[:3]+['Valkyrie']))
check('second distinct capture permits reconciliation', st.tr.own_tracker.hand[3] == 'Valkyrie')
st = session(); st.started, st.last_poll = True, 100
st.ch.pending = [SimpleNamespace(action=100, card='Musketeer', submitted=95)]
st.ch.available = False
st.step(rec(115, ui=[E, C, C, C], cards=[None]+H[1:]))
check('capture gap: one screenshot cannot confirm pending execution twice',
      not st.ch.finished and not st.tr.stats['own_play_confirmed_by_hud'])
st.step(rec(120, ui=[E, C, C, C], cards=[None]+H[1:]))
check('pending command still confirms on two distinct captures', st.ch.finished == [True])

for ui, probabilities in ((G, [.99, .99]), (C, [None, None]), (C, [.01, .01])):
    st = session(); st.started, st.last_poll = True, 95
    st.ch.pending = [SimpleNamespace(action=100, card='Musketeer', submitted=95)]
    st.ch.available = False
    for tick, replacement, p in zip((100, 105), ('Valkyrie', 'Giant'), probabilities):
        st.step(rec(tick, ui=[ui,C,C,C], cards=[replacement]+H[1:], probs=[p,.99,.99,.99]))
    check(f'pending: untrusted {ui}/{probabilities} cannot synthesize a play',
          st.ch.finished == [] and st.tr.plays[0] == [] and not st.tr.stats['own_play_confirmed_by_hud'])

st = session(); st.started, st.last_poll = True, 95
st.ch.pending = [SimpleNamespace(action=100, card='Musketeer', submitted=95)]
st.ch.available = False
st.step(rec(100, cards=['Valkyrie']+H[1:]))
st.step(rec(105, cards=['Giant']+H[1:]))
check('pending: two conflicting coloured replacement identities do not agree',
      not st.ch.finished and not st.tr.plays[0])
st.ch.pending = [SimpleNamespace(action=100, card='Musketeer', submitted=105)]
st.step(rec(110, cards=['Giant']+H[1:]))
check('pending: a replacement command does not inherit evidence from the old command',
      not st.ch.finished and not st.tr.plays[0])
st.step(rec(115, cards=['Giant']+H[1:]))
check('pending: reliable matching coloured replacements confirm the same command', st.ch.finished == [True])

st = session(); st.started, st.last_poll = True, 95
st.ch.pending = [SimpleNamespace(action=100, card='Musketeer', submitted=95)]
st.ch.available = False
st.step(rec(100, ui=[E,C,C,C], cards=[None]+H[1:]))
r = rec(105, ui=[E,C,C,C], cards=[None]+H[1:]); r['events'] = [dict(owner=0,card='Musketeer',tick=105)]
st.step(r)
check('pending: current external own-play event is not duplicated by HUD confirmation',
      st.tr.plays[0] == [(105,'Musketeer')] and not st.tr.stats['own_play_confirmed_by_hud'])

t = tracker()
t.hyps[-1].play('Musketeer'); t.hyps[-1].refill = 1000
feed(t, 2, H[:3]+['Valkyrie'], ui=[C]*4, tick0=1)
check('refilling non-best hypothesis prevents visual swaps', not t.stats['own_sync:slot'])

t = tracker()
t.play(100, 'Musketeer')
feed(t, 2, ['Musketeer', 'Fireball', 'MiniPekka', 'Minions'], ui=[C]*4, tick0=130)
check('recent play cannot be moved from queue tail back into hand by coloured noise',
      'Musketeer' not in t.hand and t.hyps[t.best].queue[-1] == 'Musketeer')
feed(t, 2, t.hand, nxt='Musketeer', ui=[C]*4, tick0=145)
check('Next noise cannot move a recent play ahead of still-unknown draws',
      t.hyps[t.best].queue[-1] == 'Musketeer')

st = session(); st.started, st.last_poll = True, 100
r = rec(115, cards=H[:3]+['Valkyrie']); r.pop('ts_ms', None); r['timestamp_ms'] = 1234.5
st.step(r)
r = rec(120, cards=H[:3]+['Valkyrie']); r.pop('ts_ms', None); r['timestamp_ms'] = 1234.5
st.step(r)
check('native timestamp_ms identifies one capture despite rewritten policy ticks',
      st.tr.own_tracker.hand[3] == 'Minions' and st._frame_ms == 1234.5)

for p in (None, float('nan'), float('inf'), -.1, 1.1):
    t = tracker()
    own = feed(t, 6, H[:3]+['Valkyrie'], nxt='Cannon', ui=[C]*4, probs=[p]*4, next_prob=p)
    check('invalid confidence cannot sync or re-anchor: ' + str(p),
          own['hand'] == H and own['cycle'][0] == 'Giant' and not t.stats['own_reanchor_hud'])
    g = guard(H, H, [p]*4, [C]*4)
    check('invalid confidence cannot authorize coloured tap: ' + str(p), g(0) == 'coloured_unverified')

st = session(100); st.started = True
for k in range(480):
    st.player.search_disabled = k >= 24
    st.step(rec(100+5*k, ui=[G, C, C, C]))
check('persistent false-grey: enforced refusal reaches bounded explicit hold without submissions',
      st.hold_reason == 'tap_guard:greyed' and st.ch.submitted == 0
      and len(st.guarded) == st.refusal_limit and st.player.inner.calls == st.refusal_limit)
check('hold count exposed to reporting', handsync.counts(st.tr.stats).get('handsync_hold:tap_guard:greyed') == 1)
st = session(100); st.started = True
st.step(rec(100, ui=[G, C, C, C])); st.step(rec(225, ui=[G, C, C, C]))
check('sparse refusals reach six-second hold before count limit',
      st.hold_reason == 'tap_guard:greyed' and len(st.guarded) == 2 and st.ch.submitted == 0)
st = session(100); st.started = True
st.step(rec(100, ui=[G, C, C, C])); st.step(rec(105))
check('transient grey revalidates before hold and permits original verified action',
      st.ch.submitted == 1 and st.hold_reason is None and st._refusals == 0)
st = session(100, mode='measure'); st.started = True
st.step(rec(100, ui=[G, C, C, C]))
check('measure mode reports guard but keeps original action and submission',
      st.ch.submitted == 1 and len(st.guarded) == 1 and st.hold_reason is None)
st = session(100); st.started = True
r = rec(100); del r['hand']['ui']
st.step(r)
check('no UI keeps base submission behavior', st.ch.submitted == 1 and st.hold_reason is None)

if '--replay' in sys.argv:
    R = Path('/mpac/sdicks02/scratch/live-loop/runs')
    out = '/tmp/test_handsync_replay.json'
    p = subprocess.run([sys.executable, '-B', str(HERE/'sync_replay.py'), str(R/'s21/m03'), str(R/'s22/m03'),
                        '--jobs', '4', '--json', out], env=os.environ, capture_output=True, text=True, timeout=3600)
    J = json.load(open(out))
    S = J['summary']
    base = {(r['run'], x['n']): x for r in J['results'] if r['arm'] == 'base' for x in r['rows']}
    check('replay: no errors', p.returncode == 0 and 'ERROR' not in p.stdout)
    check('replay: base submits Minions for the greyed Valkyrie at s21-m03 n364',
          base.get(('s21-m03', 364), {}).get('card') == 'Minions' and base[('s21-m03', 364)]['truth'] == 'Valkyrie')
    check(f"replay: base wrong deploys {S['base']['wrong']} >= 5 on s21-m03 + s22-m03", S['base']['wrong'] >= 5)
    check(f"replay: measured residual after guard flags (MEASURE mode) = {S['sync']['residual']}", S['sync']['residual'] == 0)
print(f'{sum(checks)} passed, {len(checks) - sum(checks)} failed')
sys.exit(0 if all(checks) else 1)
