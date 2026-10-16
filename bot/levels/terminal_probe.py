"""Pinned RoyaleSim command closure and real terminal drain; no Runtime or models.

Run only after source review, under the existing CPU1 lease/nice envelope.
The exclusive receipt retains partial evidence and traceback; no cache/export writes.
Expected GAME_OVER refusals here are API fixtures, never accepted pilot plays.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import traceback
from datetime import datetime, timezone

from bot.players.royalesim_match import CommandPhase
from bot.players.royalesim_vocab import rsim_battle

VERSION = 'rsim-terminal-boundary-v1'
DECK = ('Knight', 'Archers', 'Cannon', 'Giant', 'Fireball', 'Arrows', 'Minions', 'Musketeer')


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def public_result(state):
    """All terminal score inputs, with both seats' HP in native tower-slot order."""
    return dict(tick=state['tick'], game_over=state['game_over'], winner=state['winner'],
                crowns=[p['crowns'] for p in state['players']], towers=[p['tower_hp'] for p in state['players']])


def scenario(client='16.402', *, start=5970, weaker=1, tie=False, crown_end=False, king_end=False):
    """Public reset fixtures; normally empty/equal crowns, or a deliberate early end."""
    from bot.players.royalesim_adapter import royalesim_card
    b = rsim_battle(client)
    b.set_command_delay_ticks(0, 0)
    names = [r[0] for r in json.loads(b.catalogue_json())]
    deck = [names.index(royalesim_card(c)) for c in DECK]
    kwargs = dict(seed=1, decks=[deck, deck], shuffle=0, start_tick=start,
                  elixir_milli=[10000, 10000], spawns=[], levels=[[11]*8, [11]*8], tower_levels=[11, 11])
    b.reset(tower_hp=None, **kwargs)
    hp = [list(p['tower_max_hp']) for p in json.loads(b.state_json())['players']]
    hp[0][1] = hp[1][1] = 1000
    if not tie:
        hp[weaker][1] = 900
    if crown_end:
        hp[weaker][1] = 0
    if king_end:
        hp[weaker][0] = 1  # Reset must not invent an already destroyed king.
        kwargs['spawns'] = [(1-weaker, names.index('Knight'), 9*18000,
                             (5 if weaker == 0 else 27)*18000, -1)]
    b.reset(tower_hp=hp, **kwargs)
    state = json.loads(b.state_json())
    require(state['tick'] == start and [p['tower_hp'] for p in state['players']] == hp,
            'native reset did not preserve fixture clock/tower HP')
    CommandPhase(b, state)  # Validate before any commands; no builder or spell registry.
    return b, names


def drain(b, *, limit=7200):
    """Independent one-tick native continuation; no adapter/policy/phase termination."""
    trace = [public_result(json.loads(b.state_json()))]
    while not trace[-1]['game_over'] and trace[-1]['tick'] < limit:
        before = trace[-1]['tick']
        b.step([], 1)
        trace.append(public_result(json.loads(b.state_json())))
        require(trace[-1]['tick'] == before+1, 'native empty-command drain made no one-tick progress')
    require(trace[-1]['game_over'], 'native drain exhausted safeguard without final game_over')
    return trace


def boundary_case(client, weaker, *, tie=False, evidence=None):
    """Accepted5997 vs refused6000, then actual later win or delayed exact draw."""
    import royalesim as rs
    row = {} if evidence is None else evidence
    row.update(client=client, weaker=weaker, exact_tie=tie, passed=False)
    b, _ = scenario(client, start=5997, weaker=weaker, tie=tie)
    state = json.loads(b.state_json())
    phase = CommandPhase(b, state)
    row.update(phase=phase.receipt(), before=public_result(state), overrides=b.calibration_overrides())
    require(state['overtime'] and not state['game_over'] and not phase.closed(state),
            'fixture is not an active preclosure overtime')
    command = (0, 0, 171000, 189000)  # Knight, own tile(9,10), certified home control.
    accepted = b.step([command], 0)
    row['last_accepted'] = [list(r) for r in accepted]
    require(len(accepted) == 1 and accepted[0][1] == 0 and accepted[0][2] == 5997,
            f'legal last preclosure command refused or mistimed: {accepted}')
    b.step([], 3)
    state = json.loads(b.state_json())
    row['at_closure'] = public_result(state)
    require(state['tick'] == state['regular_ticks']+state['overtime_ticks'] == 6000
            and not state['game_over'] and phase.closed(state), 'wrong public no-play boundary')
    before = json.loads(b.state_json())
    refused = b.step([(1, 0, 153000, 387000)], 0)
    row['at_closure_command'] = [list(r) for r in refused]
    require(len(refused) == 1 and rs.DEPLOY_REASONS[refused[0][1]] == 'GAME_OVER'
            and refused[0][2] == 6000, f'closed phase accepted a command or returned another reason: {refused}')
    require(json.loads(b.state_json()) == before, 'refused zero-tick command changed native physical state')
    trace = row['drain'] = drain(b)
    final = trace[-1]
    require(final['tick'] > 6067 and final['tick'] < 7200, 'drain was truncated or safeguard supplied score')
    if tie:
        changes = [r for a, r in zip(trace, trace[1:]) if a['towers'] != r['towers']]
        # The upkeep at input tick6067 is visible in state6068; judgment6147 in state6148.
        require(len(changes) == 1 and changes[0]['tick'] == 6068 and final['tick'] == 6148,
                'pinned exact weakest-HP tie must drain once, then reach the delayed draw')
        require(final['winner'] == 2 and final['crowns'] == [0, 0], 'exact tie did not finish as native draw')
        require(final['towers'] == [[hp-50 for hp in side] for side in row['at_closure']['towers']],
                'exact tie changed HP beyond its single50HP drain step')
    else:
        winner = 1-weaker
        require(final['winner'] == winner and final['crowns'][winner] == 1 and final['crowns'][weaker] == 0
                and final['towers'][weaker][1] == 0, 'native drain scored the wrong winner/crown/tower')
        require(final['towers'] == [[max(0, hp-900) for hp in side] for side in row['at_closure']['towers']],
                'unequal fixture final tower HP differs from its weakest900HP draining out')
    row.update(final=final, passed=True)
    return row


def run(receipt):
    from .placement_probe import installed_identity, validate_identity
    identity = installed_identity()
    receipt.update(protocol=VERSION, passed=False, identity=identity, cases=[], host=socket.gethostname(),
                   pid=os.getpid(), time=datetime.now(timezone.utc).isoformat(), runtime_models_loaded=False)
    validate_identity(identity)
    root = Path(__file__).resolve().parents[1]
    sources = [Path(__file__), root/'players/royalesim_match.py', root/'players/royalesim_vocab.py',
               root/'players/royalesim_adapter.py']
    env_path = Path('/mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh')
    receipt.update(source_sha256={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
                   env_sha256=hashlib.sha256(env_path.read_bytes()).hexdigest(),
                   environment={k: os.environ.get(k) for k in ('PYTHONHASHSEED', 'PYTHONDONTWRITEBYTECODE',
                       'CUDA_VISIBLE_DEVICES', 'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                       'RAYON_NUM_THREADS', 'CLASHER_BOT_RUNTIME', 'CLASHER_BOT_RUNTIME_PINS')})
    require(os.environ.get('PYTHONHASHSEED') == '0', 'probe requires PYTHONHASHSEED=0')
    for client in ('16.402', '15.535.29'):
        for weaker, tie in ((0, False), (1, False), (1, True)):
            row = {}
            receipt['cases'].append(row)
            boundary_case(client, weaker, tie=tie, evidence=row)
    validate_identity(installed_identity())
    receipt['passed'] = True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    receipt = dict(protocol=VERSION, passed=False)
    with args.out.open('x') as stream:
        try:
            run(receipt)
        except Exception as exc:
            receipt.update(passed=False, error=repr(exc), traceback=traceback.format_exc())
        stream.write(json.dumps(receipt, indent=2, sort_keys=True)+'\n')
    print(json.dumps(dict(passed=receipt['passed'], receipt=str(args.out))), flush=True)
    return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
