"""Observe one excluded mirror replay; preserve all original decisions and physics."""

import fcntl
import json
from pathlib import Path
from unittest.mock import patch

import run_controls as rc
from value_contract import ROOT, publish, sha

from clasher.battle import BattleState


def snapshot(battle):
    return [{"id": e.id, "type": type(e).__name__, "seat": e.player_id,
             "hp": float(e.hp), "x": float(e.position.x), "y": float(e.position.y)}
            for e in battle.entities.values() if hasattr(e, "hp")]


def main():
    output = ROOT / 'reports/hog26_scalar_mirror_trace_20260913.json'
    pin_path = ROOT / 'reports/hog26_scalar_mirror_trace_pin_20260913.json'
    if output.exists() or pin_path.exists():
        raise ValueError('preserve prior observational audit')
    rc.torch.set_num_threads(1)
    pin = rc.validate()
    authority = rc.source_authority()
    baseline_path = rc.OUTPUT / 'mirror_a.json'
    baseline = json.loads(baseline_path.read_text())
    publish(pin_path, {'source_sha256': sha(Path(__file__)), 'baseline_sha256': sha(baseline_path),
                      'control_pin_sha256': sha(rc.PIN), 'seed': 1281001,
                      'scope': 'Excluded observational replay. Read-only scalar tick snapshots, original method called once. No fitting or acceptance.'})
    model, builder = rc.load_model(pin['policy_checkpoint'], rc.torch.device('cpu'))
    vocabulary = rc.load_current_client_typed_vocabulary()
    setup = rc.compile_standard_simple_setup(builder.loader, authority['contract']['canonical_names'], device='cpu', canonical_lane_globals=True)
    lookup, _ = rc._typed_lookups(setup, builder.loader, vocabulary)
    provider = rc.SimplePublicMaskV2Provider(rc._compile_public_mask_v2_tables(builder, setup, lookup))
    original = BattleState._step_logic_tick
    unequal = []
    ending = []

    def observed(battle):
        before = snapshot(battle) if battle.tick >= 2935 else None
        result = original(battle)
        hp = [[float(getattr(player, name)) for name in ('left_tower_hp', 'right_tower_hp', 'king_tower_hp')]
              for player in battle.players]
        if hp[0] != [hp[1][1], hp[1][0], hp[1][2]]:
            unequal.append({'tick': battle.tick, 'tower_hp': hp})
        if before is not None:
            ending.append({'tick': battle.tick, 'before': before, 'after': snapshot(battle), 'tower_hp': hp})
        return result

    with patch.object(BattleState, '_step_logic_tick', observed):
        result = rc.run(model, builder, vocabulary, provider, None, seat=0, seed=1281001,
                        opponent_deck=rc.DECK, expanded_receipts=True, policy_selfplay=True)
    ignored = {'elapsed_seconds', 'source_scope', 'encoder_rows'}
    if {k: v for k, v in result.items() if k not in ignored} != {k: v for k, v in baseline.items() if k not in ignored}:
        raise ValueError('observational replay changed baseline')
    rc.validate()
    publish(output, {'status': 'complete-exact-observational-replay', 'pin_sha256': sha(pin_path),
                     'baseline_trace_and_result_exact': True, 'unequal_tower_ticks': unequal,
                     'terminal_frames': ending, 'fitting': False, 'acceptance': False})
    print(json.dumps({'status': 'complete', 'first_unequal': unequal[:1], 'unequal_tick_count': len(unequal)}))


if __name__ == '__main__':
    lock = Path('/Users/sam/Library/Application Support/ClasherMonitor/comparison.lock')
    with lock.open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        main()
