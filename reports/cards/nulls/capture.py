#!/usr/bin/env python3
"""Slot-only probe collector. No adb, SSH, app lifecycle or emulator operations.

Run ON THE MAC, from a jobs directory, after an exclusive slot is granted.
Raw official recordings, input tables, and configs stay in jobs directories.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
import platform
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time

sys.dont_write_bytecode = True
from scenarios import VERSION, scenarios, signature

PORT = 26795
SERIAL = "emulator-5596"
JOB_ROOTS = (Path("/mpac/sdicks02/jobs/clasher/cards/nulls"),
             Path("/Users/sam/.cache/clasher-native-reference/cards/nulls"))


def job_path(path):
    p = Path(path).resolve()
    if not any(p == root or root in p.parents for root in JOB_ROOTS):
        raise ValueError(f"output must be inside a cards/nulls jobs directory: {p}")
    return p


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def append(path, value):
    with Path(path).open("a") as f:
        f.write(json.dumps(value, separators=(",", ":")) + "\n")


def swap_used():
    raw = subprocess.check_output(["sysctl", "-n", "vm.swapusage"], text=True)
    match = re.search(r"used\s*=\s*([0-9.]+)([MG])", raw)
    if not match:
        raise ValueError(f"cannot parse swap usage: {raw}")
    return round(float(match[1]) * (1024 ** (2 if match[2] == "M" else 3)))


def slot_guard(slot, directory):
    now = datetime.now(timezone.utc)
    start, end = [datetime.fromisoformat(slot[k].replace("Z", "+00:00")) for k in ("start", "end")]
    if start.tzinfo is None or end.tzinfo is None or not start <= now < end:
        raise ValueError("outside the granted slot")
    if not 0 < (end - start).total_seconds() <= 7200:
        raise ValueError("slot duration must be <= 2 hours")
    if (slot["serial"], slot["probe_port"], slot["adb_server_port"]) != (SERIAL, PORT, 5049):
        raise ValueError("slot instance does not match the authorized reference instance")
    if slot.get("native_version") != VERSION or not slot.get("grant_reference"):
        raise ValueError("slot needs lead grant reference and exact native version")
    free = shutil.disk_usage(directory).free
    growth = swap_used() - slot["baseline_swap_bytes"]
    if free < 8 * 1024**3 or growth > 1.5 * 1024**3:
        raise RuntimeError(f"resource stop: free={free}, swap_growth={growth}")
    stop = slot.get("stop_file")
    if stop and Path(stop).exists():
        raise RuntimeError("owner/watchdog requested stop")
    return {"at": now.isoformat(), "free_bytes": free, "swap_growth_bytes": growth}


def single(command):
    with socket.create_connection(("127.0.0.1", PORT), timeout=30) as sock:
        sock.sendall(command.encode() + b"\n")
        data = bytearray()
        while block := sock.recv(65536):
            data.extend(block)
            if len(data) > 16 * 1024**2:
                raise ValueError("oversized probe response")
    result = json.loads(data)
    if result.get("ok") is not True:
        raise ValueError(result)
    return result


class Session:
    """Existing session-v1 wire contract; failed mutations are never retried."""
    def __init__(self):
        self.deadline = None
        self.sock = socket.create_connection(("127.0.0.1", PORT), timeout=30)
        self.buffer = bytearray()
        self.sock.sendall(b"session-v1\n")
        greeting = self.line()
        if greeting != {"ok": True, "session": "control-session.v1"}:
            self.sock.close()
            raise ValueError(greeting)

    def line(self):
        while b"\n" not in self.buffer:
            block = self.sock.recv(65536)
            if not block:
                raise ConnectionError("probe session closed; no mutation retry")
            self.buffer.extend(block)
            if len(self.buffer) > 16 * 1024**2:
                raise ValueError("oversized probe response")
        raw, _, rest = self.buffer.partition(b"\n")
        self.buffer = bytearray(rest)
        value = json.loads(raw)
        if value.get("ok") is not True:
            raise ValueError(value)
        return value

    def __call__(self, command):
        if self.deadline is not None and datetime.now(timezone.utc) >= self.deadline:
            raise RuntimeError("slot ending; no further probe commands")
        if any(c in command for c in "\r\n\0") or len(command.encode()) > 4094:
            raise ValueError("invalid session command")
        self.sock.sendall(command.encode() + b"\n")
        return self.line()

    def close(self):
        # Closing the socket releases the probe session even after a failed call.
        self.sock.close()


def make_config(template, row, ids, seed):
    config = copy.deepcopy(template.get("config", template))
    config["cmd"], config["evt"], config["rndSeed"] = [], [], seed
    config["endTick"] = 7200  # scene watchdog; collector always stops at <=600
    battle = config["battle"]
    battle["lvlcap"] = battle["cardlvlmin"] = 11
    for owner, deck in enumerate(row["script"]["decks"]):
        battle[f"deck{owner}"]["sp"] = [{"d": ids[n]} for n in deck]
        support = battle[f"deck{owner}"]["sc"]
        if len(support) != 1:
            raise ValueError("template must have one Princess support per side")
        support[0] = {"d": 159000000}
        battle["hbd"][owner]["kt"] = 11
        battle[f"avatar{owner}"]["expLevel"] = 11
    return config


def initial_hands(frame):
    return {p["owner"]: {h["cardId"] for h in p["hand"]} for p in frame["players"]}


def normalized_objects(ordinary, rich, initial_towers, body_names):
    richmap = {o["nativeObjectId"]: o for o in rich["objects"]}
    result = []
    for o in ordinary["objects"]:
        ro = richmap.get(o["nativeObjectId"], {})
        body = initial_towers.get(o["nativeObjectId"])
        if body is None:
            body = body_names.get(str(ro.get("dataGlobalId")), f"data:{ro.get('dataGlobalId', 'unknown')}")
        result.append({"native_id": o["nativeObjectId"], "owner": o["owner"],
                       "card_id": o["cardId"], "body_name": body,
                       "x": o["x"], "y": o["y"], "hp": o.get("hp"), "max_hp": o.get("maxHp"),
                       "data_global_id": ro.get("dataGlobalId"), "rich": ro})
    return result


def checked_frame(call, expected):
    ordinary, rich = call("observe"), call("observe-rich")
    if ordinary["tick"] != expected or rich["tick"] != expected:
        raise ValueError("observation tick changed while paused")
    if ordinary.get("truncated") is not False or rich.get("truncated") is not False:
        raise ValueError("truncated/uncertified observation")
    return ordinary, rich


def accepted_event(command, ids, before, after, receipt):
    owner, cid = command["side"], ids[command["card"]]
    pre = next(p for p in before["players"] if p["owner"] == owner)
    post = next(p for p in after["players"] if p["owner"] == owner)
    card = next(h for h in pre["hand"] if h["cardId"] == cid)
    remaining = {h["handIndex"]: h["cardId"] for h in post["hand"]}
    # One tick; the generous 0.1 allowance exceeds max normal regeneration.
    valid = (receipt.get("state") == "succeeded" and receipt.get("error") == "none"
             and receipt.get("executeTick") == command["schedule_tick"]
             and remaining.get(card["handIndex"]) != cid
             and abs((pre["elixir"] - post["elixir"]) - card["cost"]) <= 0.1)
    return {"accepted": valid, "side": owner, "card": command["card"], "card_id": cid,
            "tile": command["tile"], "kind": "card", "slot": card["handIndex"],
            "command_tick": command["command_tick"], "exec_tick": command["schedule_tick"] if valid else None,
            "tick_basis": "schedule executeTick + one-tick hand-change/spend witness; not visual birth",
            "before_elixir": pre["elixir"], "after_elixir": post["elixir"], "cost": card["cost"],
            "receipt": receipt}


def capture(args):
    if platform.system() != "Darwin":
        raise RuntimeError("capture runs on the Mac only; phase 1 is offline")
    slot = json.loads(args.slot.read_text())
    out = job_path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    slot_guard(slot, out.parent)
    deadline = datetime.fromisoformat(slot["end"].replace("Z", "+00:00")) - timedelta(seconds=5)
    def one(command):
        if datetime.now(timezone.utc) >= deadline:
            raise RuntimeError("slot ending; no further probe commands")
        return single(command)
    out.mkdir(exist_ok=False)
    row = next(r for r in scenarios() if r["id"] == args.scenario)
    template = json.loads(args.template.read_text())
    spells = json.loads(args.gamedata.read_text())["items"]["spells"]
    ids = {s["name"]: s["id"] for s in spells}
    expected_attestation = json.loads(args.attestation.read_text())
    body_names = json.loads(args.body_names.read_text()) if args.body_names else {}
    metadata = {"schema": "cards.nulls.fixture.v1", "native_version": VERSION, "scenario": row,
                "slot": slot, "serial": SERIAL, "probe_port": PORT, "adb_server_port": 5049,
                "input_hashes": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                                 (args.template, args.gamedata, args.attestation) + ((args.body_names,) if args.body_names else ())},
                "code_hashes": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                                (Path(__file__), Path(__file__).with_name("scenarios.py"))},
                "status": "incomplete", "issue_offset": -1}
    dump(out / "metadata.json", metadata)
    call = None
    started = time.monotonic()
    try:
        status, attest = one("status"), one("attest")
        dump(out / "status-before.json", status)
        dump(out / "attestation.json", attest)
        if status.get("ready") is not True or status.get("paused") is not True:
            raise ValueError("owner must provide ready, paused instance")
        if signature(attest) != signature(expected_attestation):
            raise ValueError("live attestation differs from slot-provided reference")
        needed = {s: {ids[c["card"]] for c in row["script"]["commands"] if c["side"] == s} for s in (0, 1)}
        for seed in range(1610150001, 1610150201):
            slot_guard(slot, out)
            config = make_config(template, row, ids, seed)
            configured = one("configure " + json.dumps(config, separators=(",", ":")))
            initial = one("observe")
            append(out / "seed-attempts.jsonl", {"seed": seed, "configured": configured, "initial": initial})
            if configured.get("tick") != 0 or initial["tick"] != 0 or initial.get("truncated") is not False:
                raise ValueError("invalid native initial frame")
            hands = initial_hands(initial)
            if all(needed[s] <= hands[s] for s in (0, 1)):
                break
        else:
            raise ValueError("no eligible opening hand in fixed 200-seed range")
        dump(out / "config.json", config)
        dump(out / "ids.json", {n: ids[n] for deck in row["script"]["decks"] for n in deck})
        call = Session()
        # Every session command checks expiry, including between resource polls.
        # Leave five seconds for transport return and owner handoff.
        call.deadline = deadline
        configured_status = call("status")
        if configured_status.get("ready") is not True or configured_status.get("paused") is not True:
            raise ValueError("configured instance must remain ready and paused")
        original_render = status.get("renderSuppressed")
        # Preserve the owner's rendering setting; no render/forward changes.
        begin = row["script"]["start_tick"]
        if call(f"step {begin}")["tick"] != begin:
            raise ValueError("warmup tick mismatch")
        ordinary, rich = checked_frame(call, begin)
        towers = {o["nativeObjectId"]: "KingTower" if o["x"] == 9000 else "PrincessTower"
                  for o in ordinary["objects"] if o["cardId"] == -1 and o.get("hp") is not None}
        if len(towers) != 6 or any(o["cardId"] != -1 and o.get("hp") is not None for o in ordinary["objects"]):
            raise ValueError("initial state must contain exactly six towers and no other bodies")
        entry = {"episode": out.name, "split": "train", "purpose": "exploration-development-only",
                 "decks": row["script"]["decks"], "start_tick": begin, "native_version": VERSION}
        dump(out / "setup.json", {"entry": entry, "native_version": VERSION, "seed": seed,
                                   "script_sha256": row["script_sha256"], "config_sha256": signature(config)})
        dump(out / "split.json", {"matches": [{"episode": out.name, "split": "train"}],
                                  "purpose": "local loader compatibility; no acceptance/training authorization"})
        commands = row["script"]["commands"]
        with gzip.open(out / "evaluation-only.jsonl.gz", "wt") as evaluations, \
                gzip.open(out / "objects.jsonl.gz", "wt") as objects, \
                gzip.open(out / "rich.jsonl.gz", "wt") as raw:
            for tick in range(begin, row["script"]["end_tick"] + 1):
                if tick % 10 == 0:
                    append(out / "resources.jsonl", slot_guard(slot, out))
                evaluations.write(json.dumps({"observation": ordinary}) + "\n")
                objects.write(json.dumps({"tick": tick, "objects": normalized_objects(ordinary, rich, towers, body_names)}) + "\n")
                raw.write(json.dumps(rich, separators=(",", ":")) + "\n")
                if tick == row["script"]["end_tick"]:
                    break
                if ordinary.get("ended"):
                    raise ValueError("battle ended before planned short horizon")
                todo = [c for c in commands if c["command_tick"] == tick]
                pending = []
                if len({c["side"] for c in todo}) != len(todo):
                    raise ValueError("one command per side per tick required for spend witnesses")
                for c in todo:
                    x, y = [round(v * 1000) for v in c["tile"]]
                    ack = call(f"replay-schedule-card {c['side']} {ids[c['card']]} {x} {y} {c['schedule_tick']}")
                    append(out / "schedules.jsonl", {"command": c, "ack": ack})
                    pending.append((c, ack))
                if call("step 1")["tick"] != tick + 1:
                    raise ValueError("step tick mismatch")
                before, ordinary = ordinary, call("observe")
                if ordinary["tick"] != tick + 1 or ordinary.get("truncated") is not False:
                    raise ValueError("post-action observation invalid")
                for c, ack in pending:
                    receipt = call(f"replay-schedule-status {ack['sequence']}")
                    event = accepted_event(c, ids, before, ordinary, receipt)
                    append(out / "events.jsonl", event)
                    if not event["accepted"]:
                        raise ValueError("card not proven accepted; retain failed attempt, do not retry")
                rich = call("observe-rich")
                if rich["tick"] != tick + 1 or rich.get("truncated") is not False:
                    raise ValueError("rich observation invalid")
        final_status = call("status")
        if signature(call("attest")) != signature(expected_attestation):
            raise ValueError("attestation changed during capture")
        if final_status.get("paused") is not True:
            raise ValueError("instance did not remain paused")
        metadata.update(status="complete", seed=seed, wall_seconds=time.monotonic() - started,
                        final_tick=ordinary["tick"], render_before=original_render,
                        render_after=final_status.get("renderSuppressed"))
        dump(out / "complete.json", {"native_version": VERSION, "scenario_id": row["id"],
                                      "script_sha256": row["script_sha256"], "final_tick": ordinary["tick"]})
    except Exception as exc:
        metadata.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        dump(out / "failure.json", {"error": metadata["error"], "native_version": VERSION})
        raise
    finally:
        if call:
            call.close()
        dump(out / "metadata.json", metadata)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scenario", required=True, choices=[r["id"] for r in scenarios()])
    p.add_argument("--slot", type=Path, required=True)
    p.add_argument("--template", type=Path, required=True)
    p.add_argument("--gamedata", type=Path, required=True)
    p.add_argument("--attestation", type=Path, required=True)
    p.add_argument("--body-names", type=Path, help="optional native dataGlobalId -> body name, kept only in jobs")
    p.add_argument("--output", type=Path, required=True)
    capture(p.parse_args())


if __name__ == "__main__":
    main()
