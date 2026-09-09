"""Record isolated scalar/native Arrows defects without opening outcome data."""

import argparse
import json
from pathlib import Path

import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.dynamic_spells import create_spell_from_json
from clasher.rl.simple_pytorch_backend import (
    DEFAULT_SIMPLE_TOKEN_VOCABULARY,
    _typed_lookups,
    load_current_client_typed_vocabulary,
)
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.simple_standard import compile_standard_simple_setup


def probe(device):
    torch.set_num_threads(1)
    loader = CardDataLoader()
    setup = compile_standard_simple_setup(loader, ["Arrows", "Knight"], device=device,
                                         canonical_lane_globals=True)
    vocab = load_current_client_typed_vocabulary(DEFAULT_SIMPLE_TOKEN_VOCABULARY)
    entity, hand = _typed_lookups(setup, loader, vocab)
    runtime = setup.create_runtime([[["Arrows"] * 8, ["Arrows"] * 8]] * 2,
                                  entity_token_lookup=entity, hand_token_lookup=hand,
                                  canonical_lane_globals=True, starting_elixir=10)
    cases = []
    for owner, target in [(0, Position(3.5, 25.5)), (1, Position(14.5, 6.5))]:
        battle = BattleState()
        battle.rng.seed(1279011)
        before = set(battle.entities)
        spell = create_spell_from_json(loader.get_card("Arrows")._raw_entry,
                                       loader.load_card_definitions())
        assert spell.cast(battle, owner, target)
        projectiles = [value for key, value in battle.entities.items() if key not in before]
        tower = next(e for e in battle.entities.values()
                     if e.position == target and e.player_id != owner)
        slot = int(torch.nonzero((runtime.state.x_units[owner] == round(target.x * 1000))
                                & (runtime.state.y_units[owner] == round(target.y * 1000))).flatten()[0])
        record = {"owner": owner, "seed": 1279011,
                  "scalar_projectile_count": len(projectiles),
                  "scalar_group_sizes": [sum(p.damage_group_hit_entity_ids is group
                                              for p in projectiles)
                                         for group in [projectiles[i].damage_group_hit_entity_ids
                                                       for i in (0, 10, 20)]],
                  "scalar_damage_per_wave": spell.damage,
                  "scalar_crown_damage_per_wave": spell.crown_tower_damage,
                  "launch_delays": [p.launch_delay for p in projectiles],
                  "destinations": [[p.target_position.x, p.target_position.y] for p in projectiles],
                  "trace": []}
        cases.append((battle, projectiles, tower, slot, record))
    for tick in range(1, 61):
        actions = torch.full((2, 2), NO_OP_ACTION, dtype=torch.int64, device=device)
        if tick == 1:
            actions[0, 0] = actions[1, 1] = 25 * 18 + 3
        runtime.step_tick(actions)
        for row, (battle, projectiles, tower, slot, record) in enumerate(cases):
            battle._defer_projectile_impacts = True
            for projectile in projectiles:
                projectile.update(.05, battle)
            battle._resolve_pending_projectile_impacts()
            record["trace"].append({"tick": tick, "scalar_tower_hp": tower.hitpoints,
                                    "native_tower_hp": float(runtime.state.hp[row, slot]),
                                    "scalar_alive": sum(p.is_alive for p in projectiles),
                                    "native_primary_active": int(runtime.effects.active[row].sum())})
    return {"device": device, "status": "diagnostic; known grouped-projectile mismatch",
            "scope": "Stationary crown targets, both seats, isolated scalar spell updates. No full-game parity claim.",
            "cases": [case[-1] for case in cases]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = probe(args.device)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    for case in report["cases"]:
        print(json.dumps({"owner": case["owner"], "first_tick": case["trace"][0],
                          "last_tick": case["trace"][-1]}))


if __name__ == "__main__":
    main()
