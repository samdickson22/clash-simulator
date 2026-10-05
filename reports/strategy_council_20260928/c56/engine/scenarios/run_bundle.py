"""Validate written nm_lib scenarios; native execution requires EMULATOR_OK.

This program never starts emulators. --run uses an already provisioned probe.
All attempts, including rejection and seed-search failures, remain on disk.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(
    0, str(ROOT / "reports/strategy_council_20260928/m0/native-mechanics-20260928")
)
import nm_lib as L

from clasher.arena import Position


def validate(manifest):
    seen = set()
    for s in manifest["scenarios"]:
        assert s["id"] not in seen
        seen.add(s["id"])
        for owner, deck in enumerate(s["decks"]):
            assert len(deck) == len(set(deck)) == 8
            assert set(s["need"][owner]) <= set(deck) and len(s["need"][owner]) <= 4
            assert all(L.LOADER.get_card(n) is not None for n in deck)
        for commands in s["variants"].values():
            for c in commands:
                assert 0 <= c["tick"] < s["end_tick"] and c["owner"] in (0, 1)
                assert ("card" in c) != ("ability" in c)
                assert c.get("card", c.get("ability")) in s["decks"][c["owner"]]
                if "card" in c:
                    assert 0 <= c["xy"][0] < 18 and 0 <= c["xy"][1] < 32
    return len(seen)


def capture(probe, battle, result):
    native = L.native_frame(probe, True)
    native["rich"] = probe("observe-rich")
    assert native["rich"]["tick"] == native["tick"] and not native["rich"]["truncated"]
    scalar = L.scalar_frame(battle)
    for row in scalar["objects"]:
        entity = battle.entities[row["id"]]
        row["deploy_remaining"] = entity.deploy_delay_remaining
        row["underground"] = bool(getattr(entity, "_underground_deployment", False))
        row["stealth_until_ms"] = getattr(entity, "_stealth_until", 0)
        for mechanic in entity.mechanics:
            ability = getattr(mechanic, "ability", None)
            if ability is not None:
                row["ability"] = {
                    "name": ability.name,
                    "active": ability.is_active,
                    "activation_ms": ability.activation_time,
                    "cooldown_ms": ability.get_cooldown_remaining(battle),
                    "duration_ms": ability.get_duration_remaining(battle),
                }
    result["native_frames"].append(native)
    result["scalar_frames"].append(scalar)


def run_pair(port, initial, config, scenario, commands, output_path):
    """nm_lib one-tick stepping with the probe's scheduled ability extension."""
    L.configure_single(port, config)
    battle = L.scalar_from_initial(initial, config, scenario["decks"])
    probe = L.Probe(port)
    result = {
        "commands": commands,
        "native_frames": [],
        "scalar_frames": [],
        "receipts": [],
        "scalar_rejected": [],
    }
    try:
        for tick in range(scenario["end_tick"]):
            capture(probe, battle, result)
            for c in (c for c in commands if c["tick"] == tick):
                if "ability" in c:
                    # Native parser: OWNER NAME_HINTS EXECUTE_TICK. '-' chooses
                    # the current champion; scalar uses the same one-button API.
                    command = f"replay-schedule-ability {c['owner']} - {tick + 1}"
                    accepted = battle.activate_champion_ability(c["owner"])
                else:
                    x, y = (round(v * 1000) for v in c["xy"])
                    command = f"replay-schedule-card {c['owner']} {L.card_id(c['card'])} {x} {y} {tick + 1}"
                    accepted = battle.deploy_card(
                        c["owner"], c["card"], Position(*c["xy"])
                    )
                result["receipts"].append(
                    {
                        "command": c,
                        "native": probe(command),
                        "scalar_accepted": accepted,
                    }
                )
                if not accepted:
                    result["scalar_rejected"].append(c)
            stepped = probe("step 1")
            assert stepped["tick"] == tick + 1
            battle.step()
            if battle.game_over or stepped.get("ended"):
                break
        capture(probe, battle, result)
        return result
    finally:
        output_path.write_text(json.dumps(result, default=str) + "\n")
        probe.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", choices=["B1", "B2", "B3", "B4"])
    parser.add_argument("--scenario")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    manifest = json.loads((HERE / "manifest.json").read_text())
    count = validate(manifest)
    if not args.run:
        print(json.dumps({"validated": count, "native_executions": 0}))
        return
    if not (HERE.parent / "EMULATOR_OK").is_file():
        parser.error("native execution blocked: c56/engine/EMULATOR_OK absent")
    if args.port is None:
        parser.error("--port is required for --run")
    for s in manifest["scenarios"]:
        if args.bundle and s["bundle"] != args.bundle:
            continue
        if args.scenario and s["id"] != args.scenario:
            continue
        output = HERE / "results" / s["id"]
        output.mkdir(parents=True, exist_ok=False)  # no silent replacement of attempts
        record = {
            "scenario": s,
            "provenance": L.provenance(),
            "variants": {},
            "manifest_sha256": L.sha(HERE / "manifest.json"),
            "runner_sha256": L.sha(Path(__file__)),
        }
        try:
            seed, config, initial = L.find_seed(
                args.port,
                *s["decks"],
                need0=s["need"][0],
                need1=s["need"][1],
                start=s["seed_start"],
                count=s["seed_count"],
            )
            record.update(seed=seed, config=config, initial=initial)
            for name, commands in s["variants"].items():
                trace_path = output / f"{name}.json"
                result = run_pair(args.port, initial, config, s, commands, trace_path)
                record["variants"][name] = {
                    "trace_file": trace_path.name,
                    "scalar_rejected": result["scalar_rejected"],
                }
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            (output / "trace.json").write_text(json.dumps(record, default=str) + "\n")


if __name__ == "__main__":
    main()
