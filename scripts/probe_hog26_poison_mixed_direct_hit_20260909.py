"""Expose the remaining direct-hit/Poison phase-order mismatch on a shield."""

import argparse
import hashlib
import json
from pathlib import Path

import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.dynamic_spells import create_spell_from_json
from clasher.entities import Building
from clasher.mechanics.shared.shield import Shield
from clasher.torch_sim.actions import NO_OP_ACTION
from scripts.probe_hog26_poison_scalar_lifecycle_20260909 import native_fixture


def spawn(battle, owner, x):
    before = set(battle.entities)
    battle._spawn_troop(Position(x, 25.0), owner, battle.card_loader.get_card("Knight"))
    troop = battle.entities[max(set(battle.entities) - before)]
    troop.deploy_delay_remaining = 0.0
    troop.placement_pending = False
    troop.hitpoints = 2000.0
    return troop


def probe(device):
    runtime = native_fixture(device)
    state = runtime.state
    knight = int(state.card_id[0, 6])
    direct_damage = float(runtime.action_kernel.catalog.effect_damage[knight])
    battle = BattleState()
    for entity in battle.entities.values():
        if isinstance(entity, Building):
            entity.damage = 0.0
    spell = create_spell_from_json(battle.card_loader.get_card("Poison")._raw_entry)
    target = spawn(battle, 1, 4.0)
    target.apply_stun(20.0)
    shield = Shield(1)
    shield.on_attach(target)
    shield.current_shield = 1
    target.mechanics.append(shield)
    target.apply_periodic_damage(source_id=999, source_kind=spell.name,
                                 duration=spell.periodic_damage_buff_duration,
                                 hit_interval=spell.damage_tick_interval, damage=spell.damage)
    # Snapshot an attached buff's last frame after leaving its source area.
    buff = target._periodic_damage_effects[999]
    buff.remaining = buff.time_to_next_hit = 0.05
    attacker = spawn(battle, 0, 4.5)
    attacker.damage = direct_damage
    attacker.target_id = target.id
    attacker._last_combat_target_id = target.id
    attacker.attack_cooldown = 0.0
    attacker._attack_windup_active = True

    runtime.modifiers.shield[0, 6] = runtime.modifiers.max_shield[0, 6] = 1
    runtime.effects.source_owner[0, 0] = 0
    runtime.effects.source_card_id[0, 0] = runtime.action_state.hand_ids[0, 0, 0]
    runtime.effects.target_local_damage[0, 0] = True
    runtime.effects.damage_interval_ticks[0, 0] = round(spell.damage_tick_interval / 0.05)
    runtime.effects.periodic_target_id[0, 0, 6] = 7
    runtime.effects.periodic_remaining_ticks[0, 0, 6] = 1
    runtime.effects.periodic_next_hit_ticks[0, 0, 6] = 1
    runtime.effects.periodic_damage[0, 0, 6] = spell.damage
    state.active[0, 7] = True
    state.stable_id[0, 7] = 8
    state.next_stable_id[0] = 9
    state.owner[0, 7] = 0
    state.card_id[0, 7] = knight
    state.x_units[0, 7], state.y_units[0, 7] = 4500, 25000
    state.hp[0, 7] = state.max_hp[0, 7] = 2000.0
    state.damage[0, 7] = direct_damage
    state.range_units[0, 7] = 5000
    state.sight_range_units[0, 7] = 6000
    state.hit_cooldown_ticks[0, 7] = round(attacker.get_base_attack_interval_seconds() / 0.05)
    state.target_id[0, 7] = 7
    battle.step()
    transition = runtime.step_tick(torch.full((1, 2), NO_OP_ACTION,
                                              dtype=torch.int64, device=device))
    return {
        "device": device, "full_scalar_battle_step_used": True,
        "full_native_runtime_step_used": True,
        "fixture": "Synthetic shield1, stationary Knight targetHP2000, ready opposing "
                   "Knight direct attack, and attached Poison buff due on its final frame. "
                   "Source area has expired; equivalent attached-buff snapshots are supplied.",
        "direct_damage": direct_damage, "poison_damage": spell.damage,
        "initial_target_hp": 2000.0, "initial_shield": 1.0,
        "scalar": {"target_hp": target.hitpoints, "hp_loss": 2000.0 - target.hitpoints,
                   "shield": shield.current_shield,
                   "attacker_cooldown_seconds": attacker.attack_cooldown},
        "native": {"target_hp": float(state.hp[0, 6]),
                   "hp_loss": 2000.0 - float(state.hp[0, 6]),
                   "shield": float(runtime.modifiers.shield[0, 6]),
                   "attacker_cooldown_ticks": int(state.cooldown_ticks[0, 7]),
                   "direct_attack_allocated": bool(transition.effect_allocation.accepted[0, 9])},
        "parity_passed": target.hitpoints == float(state.hp[0, 6]),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True, choices=["cpu", "mps:0"])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite diagnostic evidence")
    torch.set_num_threads(1)
    result = probe(args.device)
    result["status"] = "known_mixed_effect_mismatch" if not result["parity_passed"] else "scoped_agreement_only"
    result["interpretation"] = (
        "Scalar direct damage resolves in combat before CharacterBuff damage. Native direct "
        "hits remain queued until step_fast_effects, after its attached-buff advance. "
        "Whichever hit breaks the shield is absorbed in full. Standalone Poison lifecycle "
        "agreement does not establish whole-frame acceptance."
    )
    root = Path(__file__).resolve().parents[1]
    sources = [Path(__file__).relative_to(root).as_posix(),
               "scripts/probe_hog26_poison_scalar_lifecycle_20260909.py",
               "src/clasher/battle.py", "src/clasher/entities.py",
               "src/clasher/mechanics/shared/shield.py",
               "src/clasher/torch_sim/simple_runtime.py",
               "src/clasher/torch_sim/simple_effects.py",
               "src/clasher/torch_sim/simple_periodic_damage.py",
               "src/clasher/torch_sim/simple_attack_effects.py"]
    result["source_sha256"] = {path: hashlib.sha256((root / path).read_bytes()).hexdigest()
                               for path in sources}
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({key: value for key, value in result.items() if key != "source_sha256"}))


if __name__ == "__main__":
    main()
