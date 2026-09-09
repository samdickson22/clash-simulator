"""Record Poison lifecycle differences; this diagnostic does not certify parity."""

import argparse
import hashlib
import json
from dataclasses import fields, replace
from pathlib import Path

import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.dynamic_spells import create_spell_from_json
from clasher.entities import AreaEffect, Troop
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_catalog import FastCardCatalog
from clasher.torch_sim.simple_outcomes import FastMatchRules, FastTowerSpec
from clasher.torch_sim.simple_runtime import SimpleGymRuntime


def native_fixture(device):
    battle = BattleState()
    # Float64 setup authority stays on CPU; the runtime catalog uses float32.
    full = TensorCardCatalog.compile(battle.card_loader, ["Poison", "Knight"], device="cpu")
    catalog = FastCardCatalog.from_tensor_catalog(full, loader=battle.card_loader)
    catalog = replace(catalog, **{
        field.name: (getattr(catalog, field.name).to(device)
                     if isinstance(getattr(catalog, field.name), torch.Tensor)
                     else torch.device(device) if field.name == "device"
                     else getattr(catalog, field.name))
        for field in fields(catalog)
    })
    poison, knight = full.name_to_id["Poison"], full.name_to_id["Knight"]
    decks = torch.tensor([[[poison] * 8, [knight] * 8]], device=device)
    towers = FastTowerSpec(
        card_id=torch.full((2, 3), knight, dtype=torch.int64, device=device),
        x_units=torch.tensor([[3500, 14500, 9000]] * 2, device=device),
        y_units=torch.tensor([[6500, 6500, 2500], [25500, 25500, 29500]], device=device),
        hitpoints=torch.full((2, 3), 2000.0, device=device),
        damage=torch.zeros((2, 3), device=device),
        range_units=torch.full((2, 3), 7500, device=device),
        sight_range_units=torch.full((2, 3), 9500, device=device),
        hit_cooldown_ticks=torch.full((2, 3), 16, dtype=torch.int32, device=device),
    )
    runtime = SimpleGymRuntime(
        decks, catalog, towers, FastMatchRules(regulation_ticks=400, tiebreak_ticks=600),
        entity_token_lookup=torch.zeros((2, catalog.size), dtype=torch.int64, device=device),
        hand_token_lookup=torch.arange(catalog.size, dtype=torch.int64, device=device),
        max_entities=12, starting_elixir=10.0,
    )
    state = runtime.state
    state.active[0, 6] = True
    state.stable_id[0, 6] = 7
    state.next_stable_id[0] = 8
    state.kind[0, 6] = catalog.kind[knight]
    state.owner[0, 6] = 1
    state.card_id[0, 6] = knight
    state.x_units[0, 6], state.y_units[0, 6] = 4000, 25000
    state.hp[0, 6] = state.max_hp[0, 6] = 2000.0
    # The synthetic target intentionally has no attack or movement components.
    return runtime


def scalar_fixture():
    battle = BattleState()
    before = set(battle.entities)
    battle._spawn_troop(Position(4.0, 25.0), 1, battle.card_loader.get_card("Knight"))
    troop = battle.entities[max(set(battle.entities) - before)]
    assert isinstance(troop, Troop)
    troop.deploy_delay_remaining = 0.0
    troop.placement_pending = False
    troop.hitpoints = 2000.0
    tower = next(e for e in battle.entities.values()
                 if e.player_id == 1 and e.position.x == 3.5 and e.position.y == 25.5)
    tower.hitpoints = 2000.0
    raw = battle.card_loader.get_card("Poison")._raw_entry
    spell = create_spell_from_json(raw, battle.card_loader.load_card_definitions())
    assert spell.cast(battle, 0, Position(3.5, 25.5))
    area = next(e for e in battle.entities.values() if isinstance(e, AreaEffect))
    return battle, troop, tower, area, spell


def run_case(device, exit_after_tick):
    runtime = native_fixture(device)
    battle, troop, tower, area, spell = scalar_fixture()
    records = []
    for tick in range(1, 181):
        action = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=device)
        if tick == 1:
            action[0, 0] = 25 * 18 + 3
        result = runtime.step_tick(action)
        if tick == 1:
            assert result.action_success.tolist() == [[True, True]]
        # Isolate scalar effect lifecycle while preserving target-before-area order.
        # Neither scalar movement/attacks nor unrelated battle systems are stepped.
        for target in (troop, tower):
            target._update_periodic_damage_effects(0.05)
        area.update(0.05, battle)
        record = {
            "tick": tick, "seconds": tick * 0.05,
            "scalar_troop_loss": 2000.0 - troop.hitpoints,
            "native_troop_loss": 2000.0 - float(runtime.state.hp[0, 6]),
            "scalar_tower_loss": 2000.0 - tower.hitpoints,
            "native_tower_loss": 2000.0 - float(runtime.state.hp[0, 3]),
            "scalar_troop_buff_count": len(troop._periodic_damage_effects),
            "scalar_area_alive": area.is_alive,
            "native_area_alive": bool(runtime.effects.active.any()),
        }
        records.append(record)
        if tick == exit_after_tick:
            troop.position = Position(17.0, 25.0)
            runtime.state.x_units[0, 6] = 17000
    damage_ticks = {}
    for engine in ("scalar", "native"):
        for target in ("troop", "tower"):
            key = f"{engine}_{target}_loss"
            previous = 0.0
            hits = []
            for row in records:
                if row[key] != previous:
                    hits.append({"tick": row["tick"], "damage": row[key] - previous})
                previous = row[key]
            damage_ticks[key] = hits
    mismatches = [row["tick"] for row in records
                  if row["scalar_troop_loss"] != row["native_troop_loss"]
                  or row["scalar_tower_loss"] != row["native_tower_loss"]]
    return {
        "case": "stationary" if exit_after_tick is None else "exit_after_first_scan",
        "exit_after_tick": exit_after_tick,
        "scalar_payload": {"damage": spell.damage, "crown_damage": spell.crown_tower_damage,
                           "target_local_damage": spell.target_local_damage,
                           "buff_duration": spell.periodic_damage_buff_duration,
                           "scan_interval": spell.effect_tick_interval},
        "parity_passed": not mismatches, "mismatch_ticks": mismatches,
        "damage_events": damage_ticks, "trace": records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True, choices=["cpu", "mps:0"])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite diagnostic report")
    torch.set_num_threads(1)
    if args.device == "mps:0" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS unavailable")
    cases = [run_case(args.device, None), run_case(args.device, 5)]
    root = Path(__file__).resolve().parents[1]
    sources = [Path(__file__).relative_to(root).as_posix(),
               "src/clasher/dynamic_spells.py", "src/clasher/entities.py",
               "src/clasher/torch_sim/simple_catalog.py",
               "src/clasher/torch_sim/simple_effects.py",
               "src/clasher/torch_sim/simple_runtime.py"]
    report = {
        "status": "diagnostic_mismatch" if any(not c["parity_passed"] for c in cases)
        else "scoped_fixture_agreement_only",
        "device": args.device, "torch_version": torch.__version__,
        "scope": "Native full runtime ticks versus isolated scalar target-buff and area updates; "
                 "synthetic stationary targets, no scalar battle movement or attacks. "
                 "Not a full-game parity test, acceptance gate, corpus, or authority refresh.",
        "source_sha256": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in sources},
        "cases": cases,
    }
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "device": args.device,
                      "cases": [{"case": c["case"], "parity_passed": c["parity_passed"],
                                 "first_mismatch_tick": next(iter(c["mismatch_ticks"]), None),
                                 "damage_events": c["damage_events"]} for c in cases]}))


if __name__ == "__main__":
    main()
