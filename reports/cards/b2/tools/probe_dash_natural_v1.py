"""PROPOSAL: natural dash fixture; same frozen semantic-v1 comparison, no new exemptions.

No direct launch, teleport, cleared history or altered stun. A real enemy Knight
establishes a normal dash opportunity; effects can legitimately delay/prevent it.
Run only after required independent review, in an affected bounded CPU job.
"""
import copy
from functools import lru_cache
import json
import sys

if not __debug__ or sys.flags.optimize:
    raise SystemExit('optimized execution invalidates fixture assertions')

from differential import config, initial, clasher_core, Position, battle_digest
from probe_dash_semantic_v1 import (CASES, FILL, END, OWN, P, B, mirror,
                                    probe_snapshot, observe_effect_queries)
from snapshot_contract_v1 import VERSION, fresh_troop_templates, compare_states

FIXTURE = 'b2-natural-dash-fixture-v1'


def prepare(card, kind, cards, seat):
    b = initial(7, cards=cards)
    caster = seat if kind == OWN else 1-seat
    for owner in (0, 1):
        want = ['Bandit'] if owner == seat else ['Knight']
        if owner == caster:
            want.append(card)
        p = b.players[owner]
        p.elixir = 10.0
        p.hand = (want + [c for c in cards if c not in want])[:4]
        p.cycle_queue.clear(); p.cycle_queue.extend(c for c in cards if c not in p.hand)
    assert b.deploy_card(seat, 'Bandit', Position(*mirror(P, seat))), 'Bandit setup rejected'
    assert b.deploy_card(1-seat, 'Knight', Position(*mirror(B, seat))), 'Knight setup rejected'
    bandit = b.entities[7]
    assert any(type(m).__name__ == 'BanditDash' for m in bandit.mechanics)
    return b, bandit, caster


@lru_cache(maxsize=64)
def reference_launch(card, kind, cards, seat):
    """Observe, never force, the no-effect reference launch time for this exact setup."""
    b, bandit, _ = prepare(card, kind, cards, seat)
    history = []
    for _ in range(120):
        before = dict(tick=b.tick, charging=bool(getattr(bandit, '_bandit_charging', False)),
                      dashing=bool(getattr(bandit, '_bandit_dashing', False)),
                      stunned=bandit.is_stunned(), target=bandit.target_id,
                      timer=getattr(bandit, '_bandit_dash_timer', 0.0))
        mechanic = next(m for m in bandit.mechanics if type(m).__name__ == 'BanditDash')
        target = b.entities.get(bandit.target_id)
        before['target_edge_distance'] = mechanic._target_edge_distance(bandit, target) if target else None
        b.step()
        if getattr(bandit, '_bandit_dashing', False):
            assert before['charging'] and not before['stunned'], ('non-normal reference launch', before)
            assert before['target_edge_distance'] is not None
            assert b.tick >= 36, 'reference too early for the existing positive offset range'
            return b.tick, dict(before=before, after_tick=b.tick,
                                target=getattr(bandit, '_bandit_dash_target_id', None))
        history.append(before)
    raise AssertionError(('no natural reference dash within120ticks', history[-5:]))


def root_context(b, cfg, bandit_id=7):
    state = json.loads(probe_snapshot(b, cfg))
    row = next((r for r in state['entities'] if r['id'] == bandit_id), None)
    # This is independently observed Python state; no actual native value enters expected state.
    return dict(tick=b.tick, bandit=copy.deepcopy(row),
                entities=[{key: r.get(key) for key in ('id', 'class', 'x', 'y', 'alive', 'target', 'facing', 'dash')}
                          for r in state['entities']])


def one(card, kind, tile, lead, seat, cfg, cards):
    launch_tick, reference = reference_launch(card, kind, cards, seat)
    b, bandit, caster = prepare(card, kind, cards, seat)
    out = dict(contract=VERSION, fixture=FIXTURE, lead=lead, first=None, field=None, cast=None,
               gate_queries=[], differences=[], applicability=[], raw_first=None, raw_differences=[],
               reference_launch_tick=launch_tick, reference_launch=reference, compared_ticks=0, digest_diverged=False)
    ledger, deltas = {}, {}
    observe_effect_queries(bandit, card, out['gate_queries'])
    if card == 'Heal':
        bandit.hitpoints = min(bandit.hitpoints, bandit.max_hitpoints/2)

    def cast(native=None):
        if native is None:
            # Fixture resource setup happens only before export, never in one continuation arm.
            for player in b.players:
                player.elixir = 10.0
        py = bool(b.deploy_card(caster, card, Position(*mirror(tile, seat))))
        rs = None if native is None else bool(native.apply_action(caster, card, *mirror(tile, seat)))
        out['cast'] = dict(python=py, native=rs, before_export=native is None, tick=b.tick)
        assert py and (native is None or rs), ('required source cast rejected', card, seat, lead)

    for _ in range(launch_tick-max(lead, 0)):
        b.step()
    if lead > 0:
        cast()
        for _ in range(lead):
            b.step()
    else:
        for player in b.players:
            player.elixir = 10.0
    assert b.tick == launch_tick
    out['root_context'] = root_context(b, cfg)
    initial_input = probe_snapshot(b, cfg)
    native = clasher_core.BattleState(initial_input)
    initial_python = json.loads(initial_input)
    initial_native = json.loads(native.snapshot())
    out['initial_root'] = dict(python=initial_python, native=initial_native)
    out['fresh_troop_templates'] = fresh_troop_templates(initial_native)
    for tick in range(END):
        if lead <= 0 and tick == -lead:
            cast(native)
        # Capture after this frame's actions, immediately before either engine steps.
        before = dict(python=json.loads(probe_snapshot(b, cfg)), native=json.loads(native.snapshot()))
        b.step(); native.step(1)
        python_state = json.loads(probe_snapshot(b, cfg))
        # Serde canonicalization only: the expected constructor is never stepped.
        expected_state = json.loads(clasher_core.BattleState(json.dumps(python_state)).snapshot())
        actual_state = json.loads(native.snapshot())
        delta, applicability, raw = compare_states(expected_state, actual_state, b.entities)
        out['compared_ticks'] += 1
        for item in applicability:
            key = json.dumps(item, sort_keys=True)
            if key not in ledger:
                ledger[key] = dict(item, ticks=[])
            ledger[key]['ticks'].append(tick)
        if raw and out['raw_first'] is None:
            out['raw_first'], out['raw_differences'] = tick, raw
        equal = native.digest() == battle_digest(b)
        for item in delta:
            key = json.dumps(item, sort_keys=True)
            if key not in deltas:
                deltas[key] = dict(item, tick=tick, digest_equal=equal)
        if (delta or not equal) and out['first'] is None:
            out.update(first=tick, field=delta[0]['field'] if delta else 'digest', digest_equal=equal,
                       first_context=dict(before=before,
                                          after=dict(python=python_state, native=actual_state)))
        if not equal:
            out['digest_diverged'] = True
            break
    assert out['cast'] is not None
    out['applicability'], out['differences'] = list(ledger.values()), list(deltas.values())
    return out

