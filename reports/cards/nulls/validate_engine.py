#!/usr/bin/env python3
"""Offline deployability check against a reviewed Python engine checkout.

Not native evidence. The six-elixir initial value is a declared planning
assumption from historical native fixtures; captures always use measured values.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
from types import SimpleNamespace

sys.dont_write_bytecode = True
from capture import dump, job_path
from scenarios import scenarios


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    source = a.source_root.resolve()
    if "clasher-bot-runtime" in source.parts:
        raise ValueError("runtime worktree outside worker scope")
    sys.path[:0] = [str(source / "src"), str(source)]
    os.environ["CLASHER_ROOT"] = str(source)
    socket.create_connection = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("offline: native I/O forbidden"))
    from bot.fidelity.engines import OursEngine
    from bot.fidelity.fixture import Play
    from clasher.data import CardDataLoader
    loader = CardDataLoader()
    rows = []
    for row in scenarios():
        script = row["script"]
        ids = {n: loader.get_card(n)._raw_entry["id"] for deck in script["decks"] for n in deck}
        engine = OursEngine(ids)
        fix = SimpleNamespace(initial_order=[[ids[n] for n in deck] for deck in script["decks"]],
                              start_tick=0, initial_elixir=[6.0, 6.0])
        result = {"id": row["id"], "script_sha256": row["script_sha256"], "deployments": []}
        try:
            engine.reset(fix)
            commands = defaultdict(list)
            for c in script["commands"]:
                commands[c["command_tick"]].append(c)
            for tick in range(script["end_tick"]):
                for c in commands[tick]:
                    if engine.counters.get("hand_forced") or engine.counters.get("elixir_topped"):
                        raise ValueError("adapter previously forced hand or resources")
                    before = engine.b.players[c["side"]].elixir
                    play = Play(c["side"], c["card"], ids[c["card"]], "card", tuple(c["tile"]),
                                c["schedule_tick"], c["command_tick"], -1)
                    ok = engine.deploy(play)
                    result["deployments"].append({"card": c["card"], "tick": tick, "ok": bool(ok), "before_elixir": before})
                    if not ok or engine.counters.get("hand_forced") or engine.counters.get("elixir_topped"):
                        raise ValueError("refused or forced deployment")
                engine.step()
                if engine.tick != tick + 1:
                    raise ValueError("engine terminated or did not step exactly one tick")
            result["status"] = "pass"
        except Exception as exc:
            result.update(status="fail", error=f"{type(exc).__name__}: {exc}")
        rows.append(result)
    out = job_path(a.output)
    out.mkdir(parents=True, exist_ok=False)
    dump(out / "checks.json", {"scope": "offline only; initial six elixir, deterministic planning hand; not native evidence",
         "source_root": str(source), "gamedata_sha256": hashlib.sha256(Path(loader.data_file).read_bytes()).hexdigest(),
         "passed": sum(r["status"] == "pass" for r in rows), "total": len(rows), "scenarios": rows})
    print(json.dumps({"passed": sum(r["status"] == "pass" for r in rows), "total": len(rows),
                      "failures": [r for r in rows if r["status"] != "pass"]}, indent=2))
    raise SystemExit(any(r["status"] != "pass" for r in rows))


if __name__ == "__main__":
    main()
