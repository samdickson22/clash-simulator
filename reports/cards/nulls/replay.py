#!/usr/bin/env python3
"""Strict short-fixture replay through existing adapters; never retries a play.

Run on Linux, after raw recordings are copied to 127x05. Does not import or
change the existing scenario runner's hard-coded runtime source selection.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from adjudicate import derive
from capture import dump, job_path
from scenarios import VERSION, signature


def replay_binding(fix):
    return signature({"initial_order": fix.initial_order, "initial_elixir": fix.initial_elixir,
                      "start_tick": fix.start_tick, "end_tick": fix.end_tick,
                      "plays": [vars(p) for p in fix.plays]})


def frame(engine, kind, tick):
    types = json.loads(engine.b.unit_types_json()) if kind == "rsim" else None
    rsim_rows = {r[engine.F["uid"]]: r for r in engine._st()["entities"]} if kind == "rsim" else None
    objects = []
    for unit in engine.units():
        if unit.tower_slot is not None:
            name = "KingTower" if unit.tower_slot == 0 else "PrincessTower"
        elif kind == "ours":
            entity = engine.b.entities[unit.key]
            raw = getattr(entity.card_stats, "summon_character_data", None) or {}
            name = raw.get("name") or entity.card_stats.name
        else:
            name = types[rsim_rows[unit.key][engine.F["unit_type"]]]
        if kind == "ours":
            entity = engine.b.entities[unit.key]
            maximum = round(entity.max_hitpoints)
        else:
            maximum = rsim_rows[unit.key][engine.F["max_hp"]]
        objects.append({"native_id": unit.key, "owner": unit.side, "card_id": unit.root,
                        "body_name": name, "x": unit.x, "y": unit.y, "hp": unit.hp, "max_hp": maximum})
    return {"tick": tick, "objects": objects}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fixture", type=Path, required=True)
    p.add_argument("--source-root", type=Path, required=True, help="reviewed engine checkout containing src/ and bot/")
    p.add_argument("--arm", choices=("native", "ours", "rsim"), required=True)
    p.add_argument("--ruleset-label", required=True, help="record real base/overlay identity, e.g. batchA-no-stat-overlay")
    p.add_argument("--rsim-client", choices=("15.535.29", "16.402"), default="16.402")
    p.add_argument("--rsim-table", choices=("adapter", "160402"), default="adapter")
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    source = a.source_root.resolve()
    if "clasher-bot-runtime" in source.parts:
        raise ValueError("runtime worktree is outside this worker's scope")
    sys.path[:0] = [str(source / "src"), str(source)]
    os.environ["CLASHER_ROOT"] = str(source)
    from bot.fidelity.fixture import load_fixture, load_split
    metadata = json.loads((a.fixture / "metadata.json").read_text())
    if metadata["status"] != "complete" or metadata["native_version"] != VERSION:
        raise ValueError("only complete versioned fixtures may be replayed")
    fix = load_fixture(a.fixture, load_split(a.fixture / "split.json"))
    metadata["replay_sha256"] = replay_binding(fix)
    out = job_path(a.output)
    out.mkdir(parents=True, exist_ok=False)
    provenance = {"ruleset_label": a.ruleset_label, "source_root": str(source),
                  "fixture_metadata_sha256": hashlib.sha256((a.fixture / "metadata.json").read_bytes()).hexdigest()}
    if a.arm == "native":
        trace = a.fixture / "objects.jsonl.gz"
        provenance["attestation"] = json.loads((a.fixture / "attestation.json").read_text())
    else:
        from bot.fidelity.engines import OursEngine, RsimEngine
        ids = json.loads((a.fixture / "ids.json").read_text())
        engine = OursEngine(ids) if a.arm == "ours" else RsimEngine(ids, client=a.rsim_client)
        if a.arm == "rsim" and a.rsim_table == "160402":
            engine.b = engine.rs.Battle(card_names=None, slot_of_k=[[0, 1, 2], [0, 1, 2]],
                calibration_overrides={"cards.CARD_TABLE": '"client160402017_20261006"'})
            engine.cat_idx = {r[0]: i for i, r in enumerate(json.loads(engine.b.catalogue_json()))}
        engine.reset(fix)
        if a.arm == "ours":
            import clasher.battle
            path = Path(clasher.battle.__file__).resolve()
            if source not in path.parents:
                raise ValueError(f"wrong engine imported: {path}")
            provenance.update(battle_source=str(path), battle_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            data = Path(engine.b.card_loader.data_file)
            provenance.update(gamedata=str(data), gamedata_sha256=hashlib.sha256(data.read_bytes()).hexdigest())
        else:
            provenance.update(client=a.rsim_client, table=engine.b.card_table(), binding=engine.b.provenance())
        by_tick = {}
        for play in fix.plays:
            by_tick.setdefault(play.exec_tick - 1, []).append(play)
        trace = out / "objects.jsonl.gz"
        issued = []
        with gzip.open(trace, "wt") as stream:
            for tick in range(fix.start_tick, fix.end_tick + 1):
                if engine.tick != tick:
                    raise ValueError("engine did not advance exactly one tick")
                stream.write(json.dumps(frame(engine, a.arm, tick)) + "\n")
                if tick == fix.end_tick:
                    break
                for play in by_tick.get(tick, []):
                    ok = engine.deploy(play)
                    issued.append({"card": play.card, "side": play.side, "tick": tick, "accepted": bool(ok)})
                    if not ok:
                        raise ValueError(f"deployment refused at tick {tick}: {play.card}; no retry")
                    if engine.counters.get("hand_forced") or engine.counters.get("elixir_topped"):
                        raise ValueError("adapter forced hand/elixir; strict native replay invalid")
                engine.step()
                if any(k.startswith("step_refused_") and v for k, v in engine.counters.items()):
                    raise ValueError("RoyaleSim rejected queued deployment")
        if len(issued) != len(fix.plays):
            raise ValueError("some accepted native actions were not replayed")
        dump(out / "deployments.json", issued)
    result = derive(trace, metadata, a.arm, provenance)
    dump(out / "measurements.json", result)
    dump(out / "replay-metadata.json", metadata)
    print(out / "measurements.json")


if __name__ == "__main__":
    main()
