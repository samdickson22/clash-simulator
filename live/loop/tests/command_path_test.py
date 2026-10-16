"""Bounded command-path integration: exact pinned queue + actual session + exact driver predicate/tap writer.

No Runtime/models/native engine, capture, subprocess, network, or real input. Token packet and player are fixtures.
"""
import ast
import copy
from dataclasses import dataclass, replace
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import types

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import canvas as C
import handsync
from bot.players.base import WAIT

# Reuse the existing small session fixture without executing its test cases or replay entry point.
fixture_path = HERE/'test_handsync.py'
tree = ast.parse(fixture_path.read_text())
keep_names = {'HERE', 'DECK', 'ORDER', 'C', 'G', 'E', 'H'}
nodes = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef)) or
         isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in keep_names or
         isinstance(t, ast.Tuple) and any(isinstance(e, ast.Name) and e.id in keep_names for e in t.elts)
         for t in n.targets)]
fixture = {'__file__': str(fixture_path), '__name__': 'small_session_fixture'}
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(fixture_path), 'exec'), fixture)
DECK, H = fixture['DECK'], fixture['H']

queue_path = Path('/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1/src/clasher/analysis/loss_review/delay_fixes.py')
queue_tree = ast.parse(queue_path.read_text())
nodes = [n for n in queue_tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
         and n.name in ('ticks', 'Reservation', 'CommandQueue')]
qm = types.ModuleType('pinned_command_queue_test')
sys.modules[qm.__name__] = qm
qm.__dict__.update(copy=copy, dataclass=dataclass, replace=replace, WAIT=WAIT, np=np)
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(queue_path), 'exec'), qm.__dict__)

driver_path = HERE.parent/'drive.py'
driver_tree = ast.parse(driver_path.read_text())
predicate = next(n.value for n in ast.walk(driver_tree) if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'submitted' for t in n.targets))
predicate = compile(ast.Expression(predicate), str(driver_path), 'eval')
tap_class = next(n for n in driver_tree.body if isinstance(n, ast.ClassDef) and n.name == 'AdbTaps')
tap_ns = {'time': time}
exec(compile(ast.Module(body=[tap_class], type_ignores=[]), str(driver_path), 'exec'), tap_ns)


@dataclass
class Info:
    tick: int
    own: dict
    packet: object


def packet():
    obs = types.SimpleNamespace(hand_ids=np.ones(5, np.int64), hand_levels=np.ones(5),
                                hand_level_confidence=np.ones(5), global_features=np.zeros(10))
    return types.SimpleNamespace(observation=obs, hand_id_confidence=np.ones(5))


def session():
    st = fixture['session'](676)
    st.started, st.last_poll = True, 95
    st.ch = qm.CommandQueue(27, 1)
    builder = types.SimpleNamespace(token_id=lambda name, namespace: DECK.index(name)+1)
    st.rt.R.builder = builder
    def information(record):
        for e in record.get('events', ()):
            st.tr.plays[0].append((e['tick'], e['card']))
            st.tr.own_tracker.play(e['tick'], e['card'])
        own = handsync.SyncTranslator.hud(st.tr, record)
        return Info(record['tick'], own, packet())
    st.tr.information = information
    own = dict(hand=list(H), cycle=['Giant','Valkyrie','Archers','Cannon'], elixir=10., refill=0)
    st.ch.submit(Info(95, own, packet()), 100, st.rt.R.costs, builder)
    tap = tap_ns['AdbTaps'].__new__(tap_ns['AdbTaps'])
    tap.n, tap.sent = 0, {}
    tap.p = types.SimpleNamespace(stdin=io.StringIO())
    return st, tap


rows = []
for mode in ('greyed_highconfidence_jitter','coloured_missing','coloured_low','coloured_jitter',
             'valid_empty_completion','valid_coloured_completion','expiry'):
    st, tap = session()
    polls = (190,) if mode == 'expiry' else (100,105)
    for k, tick in enumerate(polls):
        ui, cards, probs = [fixture['C']]*4, list(H), [.99]*4
        if mode.startswith('greyed'):
            ui[0], cards[0] = fixture['G'], ['Valkyrie','Giant'][k]
        elif mode == 'coloured_missing':
            cards[0], probs[0] = 'Giant', None
        elif mode == 'coloured_low':
            cards[0], probs[0] = 'Giant', .01
        elif mode == 'coloured_jitter':
            cards[0] = ['Valkyrie','Giant'][k]
        elif mode == 'valid_empty_completion':
            ui[0], cards[0], probs[0] = fixture['E'], None, None
        elif mode == 'valid_coloured_completion':
            cards[0] = 'Giant'
        rec = fixture['rec'](tick, ui=ui, cards=cards, probs=probs)
        before = st.ch.submitted
        pending_before = len(st.ch.pending)
        d = st.step(rec)
        submitted = d is not None and eval(predicate, {'sess':st,'d':d,'submitted0':before,'WAIT':WAIT})
        if submitted:
            _, card_xy, target = C.action_target(d.action)
            tap.play(card_xy, target)
        rows.append(dict(mode=mode,tick=tick,pending_before=pending_before,pending_after=len(st.ch.pending),
                         new_submissions=st.ch.submitted-before,driver_submitted=bool(submitted)))
    confirmed = st.tr.stats['own_play_confirmed_by_hud']
    if mode in ('valid_empty_completion','valid_coloured_completion','expiry'):
        assert st.ch.submitted == 2 and len(st.ch.pending) == 1 and st.ch.pending[0].card == 'Fireball'
        assert st.ch.executed == 1 and st.ch.rejected == int(mode == 'expiry')
        assert tap.n == 1 and st.ch.submitted-before == 1, mode
        _, xy, target = C.action_target(676)
        expected = f'input tap {xy[0]} {xy[1]}; input tap {target[0]} {target[1]}; echo __ack 1\n'
        assert tap.p.stdin.getvalue() == expected, (mode,tap.p.stdin.getvalue())
        assert confirmed == int(mode != 'expiry'), (mode,confirmed)
    else:
        assert st.ch.submitted == 1 and st.ch.executed == 0 and tap.n == 0 and confirmed == 0
        assert st.tr.plays[0] == [], (mode, st.tr.plays[0])
    print('PASS exact pinned queue/driver/tap path',mode)
# Gap regression: exercise real external-event acceptance and cycle guards, not just public rows.
import ownplay
sys.path.insert(0, '/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1')
sys.path.insert(0, '/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1/imitation/evaluation/runtime_dependencies')
sys.path.insert(0, '/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1/reports/strategy_council_20260928/srp-public/cold-start-v3')
from imitation.evaluation.d1 import DerivedD1
from own_cycle import OwnCycle
for mode in ('gap_current_event', 'gap_buffered_event', 'gap_hud_only'):
    st, tap = session()
    tr = st.tr
    tr._seen, tr._floor, tr.events = set(), 0, []
    tr._mirrors = {0: DerivedD1(tr.costs), 1: DerivedD1(tr.costs)}
    tr._own_cycle = OwnCycle(fixture['ORDER'])
    tr.unknown_card = 'drop'
    def information(record):
        tr.accept_events(record)
        own = handsync.SyncTranslator.hud(tr, record)
        return Info(record['tick'], own, packet())
    tr.information = information
    tracker_calls = []
    real_play = tr.own_tracker.play
    def tracked_play(tick, card):
        tracker_calls.append((tick, card))
        return real_play(tick, card)
    tr.own_tracker.play = tracked_play
    ticks = (100, 102, 110) if mode == 'gap_buffered_event' else (100, 115)
    for tick in ticks:
        rec = fixture['rec'](tick, ui=['empty']+['coloured']*3, cards=[None]+H[1:])
        if (mode == 'gap_current_event' and tick == 115 or
                mode == 'gap_buffered_event' and tick == 102):
            rec['events'] = [dict(owner=0, card='Musketeer', tick=tick, x=10., y=10.)]
        ownplay.dedupe_own_events(rec, st)       # production driver pre-step dedupe
        before = st.ch.submitted
        d = st.step(rec)
        submitted = d is not None and eval(predicate, {'sess':st,'d':d,'submitted0':before,'WAIT':WAIT})
        if submitted:
            _, xy, target = C.action_target(d.action)
            tap.play(xy, target)
    assert tracker_calls == [(115 if mode != 'gap_buffered_event' else 102, 'Musketeer')], (mode, tracker_calls)
    assert not tr.stats['own_reanchor_play'] and not tr.stats['cycle_conflict_dropped:0'], (mode, dict(tr.stats))
    expected_hand = ['Giant' if mode == 'gap_buffered_event' else None]+H[1:]
    expected_queue = (['Valkyrie','Archers','Cannon','Musketeer'] if mode == 'gap_buffered_event' else
                      ['Giant','Valkyrie','Archers','Cannon','Musketeer'])
    assert len(tr.plays[0]) == 1 and tr.own_tracker.hand == expected_hand
    assert tr.own_tracker.hyps[tr.own_tracker.best].queue == expected_queue, (mode, dict(tr.stats))
    assert st.ch.submitted == 2 and st.ch.executed == 1 and st.ch.pending[0].card == 'Fireball'
    assert tap.n == 1 and tr.stats['own_play_confirmed_by_hud'] == int(mode == 'gap_hud_only')
    _, xy, target = C.action_target(676)
    assert tap.p.stdin.getvalue() == f'input tap {xy[0]} {xy[1]}; input tap {target[0]} {target[1]}; echo __ack 1\n'
    rows.append(dict(mode=mode,tracker_calls=tracker_calls,queue=list(tr.own_tracker.hyps[tr.own_tracker.best].queue),
                     stats=dict(tr.stats),taps=tap.n,new_submissions=st.ch.submitted-1))
    print('PASS gap real event/cycle/queue/tap path', mode)
out = Path(sys.argv[1]) if len(sys.argv)>1 else Path('/tmp/handsync-r3-command-probes.json')
out.write_text(json.dumps(dict(queue_path=str(queue_path),queue_sha256=hashlib.sha256(queue_path.read_bytes()).hexdigest(),
                               driver_sha256=hashlib.sha256(driver_path.read_bytes()).hexdigest(),rows=rows),indent=2)+'\n')
print('receipt:',out)
