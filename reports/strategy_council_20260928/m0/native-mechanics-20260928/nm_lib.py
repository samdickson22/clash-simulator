"""Shared native-vs-scalar scenario runner (opened development evidence only).

Reuses the historical tooling pattern of ``scripts/trace_native_public_prefix.py``
and ``collect-giant-log-river-controls.py``: configure a native battle, choose
the first seed in a fixed range whose initial hands expose the needed cards,
seed the scalar ``BattleState`` from the native initial deck/hand/cycle/elixir,
then schedule identical commands on both engines (native
``replay-schedule-card`` at submitted tick + 1, scalar ``deploy_card`` at the
submitted tick) and step both one tick at a time.

Commands may be static ``(tick, owner, card, (x, y))`` tuples or produced by a
per-engine ``policy(engine, tick, view)`` hook so that adaptive rules (for
example "Zap the King N ticks after it activates") can be applied identically
relative to each engine's own events.
"""

from __future__ import annotations

import copy
import hashlib
import json
import random
import socket
import sys
import time
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))

from clasher.arena import Position  # noqa: E402
from clasher.battle import BattleState  # noqa: E402
from clasher.data import CardDataLoader  # noqa: E402
from clasher.player import PlayerState  # noqa: E402

OUT = Path(__file__).resolve().parent
SNAPSHOT = ROOT / "reports/strategy_council_20260928/m0/runtime-snapshots/native-development-v1"
TEMPLATE = SNAPSHOT / "native-configs/template-config.json"
GAMEDATA = SNAPSHOT / "gamedata.json"  # daa58b28..., the captured 15.535.86 ruleset
ADB = "/Users/sam/.cache/clasher-native-reference/android-sdk/platform-tools/adb"
PORTS = {"emulator-5580": 26789, "emulator-5582": 26790}

LOADER = CardDataLoader(GAMEDATA)
NAME_OF_ID = {}


def card_id(name: str) -> int:
    cid = LOADER.get_card(name)._raw_entry["id"]
    NAME_OF_ID[cid] = name
    return cid


class Probe:
    """Persistent session-v1 connection (one command per line)."""

    def __init__(self, port: int):
        self.port = port
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=60)
        self.buf = bytearray()
        self.sock.sendall(b"session-v1\n")
        greeting = self._line()
        assert greeting.get("ok") and greeting.get("session") == "control-session.v1", greeting
        self.commands = 0

    def _line(self) -> dict:
        while True:
            i = self.buf.find(b"\n")
            if i >= 0:
                line = bytes(self.buf[:i])
                del self.buf[: i + 1]
                return json.loads(line)
            chunk = self.sock.recv(1 << 20)
            if not chunk:
                raise ConnectionError("probe closed the session")
            self.buf.extend(chunk)

    def __call__(self, command: str) -> dict:
        assert "\n" not in command and len(command.encode()) <= 4094
        self.sock.sendall(command.encode() + b"\n")
        self.commands += 1
        result = self._line()
        if not result.get("ok"):
            raise ValueError(f"native command rejected: {command[:80]} -> {result}")
        return result

    def close(self):
        try:
            self.sock.sendall(b"session-close\n")
            self._line()
        finally:
            self.sock.close()


def configure_single(port: int, config: dict) -> dict:
    """Single-shot configure (large payload exceeds the session line bound)."""
    payload = "configure " + json.dumps(config, separators=(",", ":"))
    with socket.create_connection(("127.0.0.1", port), timeout=60) as c:
        c.sendall(payload.encode() + b"\n")
        data = bytearray()
        while chunk := c.recv(65536):
            data.extend(chunk)
    result = json.loads(data)
    assert result.get("ok") and result["tick"] == 0, result
    return result


def single(port: int, command: str) -> dict:
    with socket.create_connection(("127.0.0.1", port), timeout=60) as c:
        c.sendall(command.encode() + b"\n")
        data = bytearray()
        while chunk := c.recv(65536):
            data.extend(chunk)
    return json.loads(data)


def make_config(deck0, deck1, seed, level=11, king_level=11):
    config = json.loads(TEMPLATE.read_text())
    for owner, deck in ((0, deck0), (1, deck1)):
        assert len(deck) == 8 and len(set(deck)) == 8
        config["battle"][f"deck{owner}"]["sp"] = [{"d": card_id(n)} for n in deck]
    config["battle"]["lvlcap"] = level
    config["battle"]["cardlvlmin"] = level
    for h in config["battle"]["hbd"]:
        h["kt"] = king_level
    config["rndSeed"] = seed
    return config


def find_seed(port, deck0, deck1, need0=(), need1=(), start=1609280001, count=200):
    """First seed in a fixed range exposing required initial hands (no outcome selection)."""
    need = {0: {card_id(n) for n in need0}, 1: {card_id(n) for n in need1}}
    for seed in range(start, start + count):
        config = make_config(deck0, deck1, seed)
        configure_single(port, config)
        initial = single(port, "observe")
        hands = {p["owner"]: {c["cardId"] for c in p["hand"]} for p in initial["players"]}
        if need[0] <= hands[0] and need[1] <= hands[1]:
            return seed, config, initial
    raise RuntimeError("no seed in fixed range exposes required hands")


def scalar_from_initial(initial: dict, config: dict, deck_names) -> BattleState:
    names = {card_id(n): n for deck in deck_names for n in deck}
    players = []
    for owner in (0, 1):
        native = next(p for p in initial["players"] if p["owner"] == owner)
        players.append(PlayerState(
            owner,
            deck=[names[c["cardId"]] for c in native["deck"]],
            hand=[names[c["cardId"]] for c in sorted(native["hand"], key=lambda c: c["handIndex"])],
            cycle_queue=deque(names[c["cardId"]] for c in sorted(native["cycle"], key=lambda c: c["cycleIndex"])),
            elixir=native["elixir"],
        ))
    return BattleState(players=players, rng=random.Random(config["rndSeed"]), card_loader=LOADER)


# ---------------------------------------------------------------- frames ----

def native_frame(probe, rich: bool):
    ordinary = probe("observe")
    assert not ordinary["truncated"]
    frame = {"tick": ordinary["tick"], "ended": ordinary["ended"], "winner": ordinary["winner"],
             "players": [{"owner": p["owner"], "elixir": p["elixir"],
                          "hand": [c["cardId"] for c in sorted(p["hand"], key=lambda c: c["handIndex"])]}
                         for p in ordinary["players"]],
             "objects": []}
    richmap = {}
    if rich:
        r = probe("observe-rich")
        assert r["tick"] == ordinary["tick"] and not r["truncated"]
        richmap = {o["nativeObjectId"]: o for o in r["objects"]}
    for o in ordinary["objects"]:
        row = {"id": o["nativeObjectId"], "owner": o["owner"], "card": o["cardId"],
               "name": NAME_OF_ID.get(o["cardId"], ("tower" if o["maxHp"] is not None else "projectile")
                                       if o["cardId"] == -1 else str(o["cardId"])),
               "x": o["x"], "y": o["y"], "hp": o["hp"], "maxHp": o["maxHp"]}
        ro = richmap.get(o["nativeObjectId"])
        if ro is not None:
            tk = ro.get("targetEntityKey")
            row["target"] = tk[2] if tk else None
            sh = ro.get("shield") or {}
            row["shield"] = sh.get("current")
            row["stage"] = ro.get("attackSequenceStage")
            ph = ro.get("phaseRuntime") or {}
            row["timeline"] = ph.get("attackTimelineMs")
            row["load"] = ph.get("loadRemainingMs")
            row["effects"] = [e.get("name") or e.get("dataGlobalId") for e in (ro.get("activeEffects") or [])]
            pr = ro.get("projectile")
            if pr is not None:
                row["projectile"] = pr.get("projectileDataGlobalId")
                src = pr.get("sourceEntityKey")
                row["source"] = src[2] if src else None
                pt = pr.get("targetEntityKey")
                row["target"] = pt[2] if pt else None
        frame["objects"].append(row)
    return frame


def scalar_frame(battle: BattleState):
    rows = []
    for e in battle.entities.values():
        name = e.card_stats.name if e.card_stats else type(e).__name__
        row = {"id": e.id, "owner": e.player_id, "name": name, "kind": e.entity_kind,
               "x": round(e.position.x * 1000), "y": round(e.position.y * 1000),
               "hp": round(e.hitpoints, 3), "target": e.target_id,
               "shield": next((m.current_shield for m in getattr(e, "mechanics", [])
                               if hasattr(m, "current_shield")), None)}
        for attr in ("_is_king_tower", "_tower_active", "_has_attacked_once", "stun_timer",
                     "activation_delay_remaining", "activation_first_hit_delay_remaining",
                     "_freeze_target_pause_remaining", "attack_cooldown", "source_id"):
            v = getattr(e, attr, None)
            if v is not None and v is not False and v != 0:
                row[attr] = v if not isinstance(v, float) else round(v, 4)
        src = getattr(getattr(e, "source_entity", None), "id", None)
        if src is not None:
            row["source"] = src
        prim = getattr(getattr(e, "primary_target", None), "id", None)
        if prim is not None and row["target"] is None:
            row["target"] = prim
        rows.append(row)
    return {"tick": battle.tick, "ended": battle.game_over, "winner": battle.winner,
            "players": [{"owner": p.player_id, "elixir": round(p.elixir, 4), "hand": list(p.hand)}
                        for p in battle.players],
            "objects": rows}


# ---------------------------------------------------------------- runner ----

def run_native(port, config, commands, end_tick, rich=True, policy=None, render_off=True, record_from=0):
    """commands: list of dicts {tick, owner, card, xy(tiles)}; policy(tick, frame)->list of extra commands."""
    configure_single(port, config)
    probe = Probe(port)
    try:
        if render_off:
            gate = probe("render off")
            assert gate.get("renderSuppressed") is True, gate
        by_tick = {}
        for c in commands:
            by_tick.setdefault(c["tick"], []).append(c)
        frames, receipts, issued = [], [], []
        frame = native_frame(probe, rich)
        frames.append(frame)
        tick = 0
        while tick < end_tick and not frame["ended"]:
            todo = list(by_tick.get(tick, []))
            if policy is not None:
                todo += policy("native", tick, frame)
            for c in todo:
                x, y = (round(v * 1000) for v in c["xy"])
                receipt = probe(f"replay-schedule-card {c['owner']} {card_id(c['card'])} {x} {y} {tick + 1}")
                receipts.append({"tick": tick, "command": c, "receipt": receipt})
                issued.append(dict(c, tick=tick))
            stepped = probe("step 1")
            assert stepped["tick"] == tick + 1, stepped
            tick += 1
            frame = native_frame(probe, rich)
            assert frame["tick"] == tick
            if tick >= record_from or frame["ended"]:
                frames.append(frame)
        return {"frames": frames, "receipts": receipts, "issued": issued}
    finally:
        try:
            if render_off:
                probe("render on")
        finally:
            probe.close()


def run_scalar(initial, config, decks, commands, end_tick, policy=None, record_from=0, battle_hook=None):
    battle = scalar_from_initial(initial, config, decks)
    if battle_hook is not None:
        battle_hook(battle)
    by_tick = {}
    for c in commands:
        by_tick.setdefault(c["tick"], []).append(c)
    frames, rejected, issued = [scalar_frame(battle)], [], []
    while battle.tick < end_tick and not battle.game_over:
        todo = list(by_tick.get(battle.tick, []))
        if policy is not None:
            todo += policy("scalar", battle.tick, frames[-1] if frames else None)
        for c in todo:
            ok = battle.deploy_card(c["owner"], c["card"], Position(*c["xy"]))
            if not ok:
                rejected.append(dict(c, tick=battle.tick))
            issued.append(dict(c, tick=battle.tick, accepted=bool(ok)))
        battle.step()
        f = scalar_frame(battle)
        if battle.tick >= record_from or battle.game_over:
            frames.append(f)
        else:
            frames[-1:] = [f]
    return {"frames": frames, "rejected": rejected, "issued": issued, "battle": battle}


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def provenance(extra=None):
    files = [Path(__file__), GAMEDATA]
    rec = {"role": "opened development evidence only; no fitting, no ledger claims, no acceptance",
           "gamedata_sha256": sha(GAMEDATA),
           "producer_sha256": {str(p.relative_to(ROOT)): sha(p) for p in files},
           "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if extra:
        rec.update(extra)
    return rec


def dump(name: str, payload: dict):
    path = OUT / name
    path.write_text(json.dumps(payload, indent=1, default=str) + "\n")
    return path


def free_gib() -> float:
    import shutil
    return shutil.disk_usage("/").free / 2**30
