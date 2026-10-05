"""Scalar-backed stand-in for the native probe (offline dry runs only).

It answers the probe commands the level collector uses (configure, observe,
observe-rich, step, replay-schedule-card, attest, status) with frames in the
native schema, and supplies a verified-read-session stand-in. Its levels,
Crown HP and spell damage come from the scalar engine, so it exercises the
collector and verifier end to end; it is never native evidence.
"""

from __future__ import annotations

import copy
import json
import random
import sys
import uuid
from collections import deque
from pathlib import Path

if "level_extension_common" not in sys.modules:
    sys.path.append(str(Path(__file__).resolve().parents[1] / "scripts"))

import level_extension_common as common  # noqa: E402

from clasher.arena import Position  # noqa: E402
from clasher.player import PlayerState  # noqa: E402
from clasher.rl.readiness_level_extension import (  # noqa: E402
    ANCHORS,
    SESSION_FREQUENCY,
    SESSION_SCHEMA,
    SPELL_CHECKS,
)

# Native attribution shapes recorded in level-extension-evidence-v2: Zap is an
# area effect (kind 3) and the rolling Log a projectile (kind 4), each its own
# ``source``; Fireball is a projectile thrown from the caster's King Tower,
# which native reports as ``source`` (cardId -1, kind 5).
SPELL_OBJECT_KIND = (("Zap", 3), ("Log", 4), ("Fireball", 4))
KING_TOWER_THROWN = frozenset({"Fireball"})
FAKE_ATTESTATION = {"ok": True, "attestation": {"synthetic_fake_native": True, "version": "fake"}}
READER_SHA = "f" * 64


class FakeNative:
    def __init__(self, loader):
        self.loader = loader
        self.generation = 0
        self.battle = None
        self.events = []
        self.schedule = []
        self.sequence = 0
        self.event_sequence = 0
        self.plan = None
        self.names = {loader.get_card(n)._raw_entry["id"]: n for n in common.PUBLIC_REFERENCE_CARDS}
        self.ids = {v: k for k, v in self.names.items()}
        self.spells = {n: self.ids[n] for n in SPELL_CHECKS}
        self.commands = []
        self.deck_slots = {}

    # ------------------------------------------------------------ commands

    def __call__(self, command: str) -> dict:
        self.commands.append(command.split(" ", 1)[0])
        verb, _, rest = command.partition(" ")
        if verb == "attest":
            return copy.deepcopy(FAKE_ATTESTATION)
        if verb == "status":
            return {"ok": True, "ready": True, "paused": True, "configured": self.battle is not None}
        if verb == "configure":
            return self._configure(json.loads(rest))
        if verb == "observe":
            return self.observe()
        if verb == "observe-rich":
            return self.observe_rich()
        if verb == "step":
            return self._step(int(rest))
        if verb == "replay-schedule-card":
            return self._schedule(*map(int, rest.split()))
        raise ValueError(f"fake native: unsupported command {verb}")

    def _configure(self, config):
        battle_cfg = config["battle"]
        level = battle_cfg["lvlcap"]
        kings = [battle_cfg["hbd"][o]["kt"] for o in (0, 1)]
        seed = config["rndSeed"]
        players = []
        rng = random.Random(seed)
        self.deck_slots = {}
        for owner in (0, 1):
            deck = [self.names[c["d"]] for c in battle_cfg[f"deck{owner}"]["sp"]]
            self.deck_slots[owner] = {name: i for i, name in enumerate(deck)}
            order = list(deck)
            rng.shuffle(order)
            player = PlayerState(owner, deck=deck, hand=order[:4], cycle_queue=deque(order[4:]),
                                 card_levels={n: level for n in deck}, tower_level=level)
            player.king_tower_level = kings[owner]
            players.append(player)
        self.battle = common.PlannedLevelBattle(players=players, rng=random.Random(seed), card_loader=self.loader)
        self.plan = {"card_level": level, "kings": kings}
        self.generation += 1
        self.events, self.schedule = [], []
        return {"ok": True, "tick": 0}

    def _schedule(self, owner, card_id, x, y, execute_tick):
        if execute_tick != self.battle.tick + 1:
            raise ValueError("fake native: schedule must target the next tick")
        self.sequence += 1
        self.schedule.append((execute_tick, owner, self.names[card_id], x / 1000, y / 1000))
        return {"ok": True, "kind": "card", "registeredAtTick": self.battle.tick, "executeTick": execute_tick,
                "generation": self.generation, "stateEpoch": self.generation, "sequence": self.sequence}

    def _step(self, count):
        for _ in range(count):
            due = [s for s in self.schedule if s[0] == self.battle.tick + 1]
            self.schedule = [s for s in self.schedule if s[0] != self.battle.tick + 1]
            with common.DamageRecorder() as recorder:
                for _tick, owner, name, x, y in due:
                    self.battle.deploy_card(owner, name, Position(x, y))
                self.battle.step()
            self._record(recorder.calls)
        return {"ok": True, "tick": self.battle.tick, "advanced": count, "ended": self.battle.game_over}

    def _king_tower(self, owner):
        king = next(e for e in self.battle.entities.values()
                    if e.player_id == owner and getattr(e.card_stats, "name", None) == "KingTower")
        return {"validated": True, "present": True, "nativeObjectId": 5000000 + king.id, "owner": owner,
                "cardId": -1, "objectKind": 5,
                "position": [round(king.position.x * 1000), round(king.position.y * 1000)]}

    def _record(self, calls):
        for call in calls:
            name = call["source_kind"]
            spell = self.spells.get(name)
            target = call["target"]
            if spell is None or target in ("Tower", "KingTower") or target not in self.ids:
                continue
            amount = call["amount"]
            caster = 1 - call["target_owner"]
            self.event_sequence += 1
            delivered = {"validated": True, "present": True, "nativeObjectId": 4000000 + self.event_sequence,
                         "owner": caster, "cardId": spell, "objectKind": dict(SPELL_OBJECT_KIND)[name]}
            self.events.append({
                "sequence": self.event_sequence, "tick": self.battle.tick, "generation": self.generation,
                "stateEpoch": self.generation, "kind": "damage", "pool": "hitpoints",
                "requestedAmount": int(amount) if float(amount).is_integer() else amount,
                "source": self._king_tower(caster) if name in KING_TOWER_THROWN else dict(delivered),
                "immediateSource": delivered,
                "target": {"validated": True, "cardId": self.ids[target], "owner": call["target_owner"]},
            })

    # ------------------------------------------------------------- frames

    def _objects(self):
        objects = []
        for entity in self.battle.entities.values():
            stats = getattr(entity, "card_stats", None)
            if not entity.is_alive or stats is None or int(entity.entity_kind) not in (0, 1):
                continue
            if stats.name in ("Tower", "KingTower"):
                card_id = -1
            elif stats.name in self.ids:
                card_id = self.ids[stats.name]
            else:
                continue
            maximum = int(round(entity.max_hitpoints))
            objects.append({
                "nativeObjectId": 5000000 + entity.id, "owner": entity.player_id, "cardId": card_id,
                "x": round(entity.position.x * 1000), "y": round(entity.position.y * 1000),
                "hp": max(1, min(maximum, int(round(entity.hitpoints)))), "maxHp": maximum,
            })
        return objects

    def _player(self, owner):
        player = self.battle.players[owner]
        slots = self.deck_slots[owner]

        def card(name):
            identity = self.ids[name]
            return {"cardId": identity, "commandCardId": identity, "deckSlot": slots[name],
                    "cost": int(self.loader.get_card(name).mana_cost)}

        return {
            "owner": owner,
            "elixirRaw": int(round(player.elixir * 10000)),
            "elixir": round(player.elixir, 4),
            "hand": [{"handIndex": i, **card(n)} for i, n in enumerate(player.hand) if n],
            "nextCard": card(player.cycle_queue[0]),
            "deck": [{"deckSlot": i, "cardId": self.ids[n], "commandCardId": self.ids[n]}
                     for n, i in sorted(slots.items(), key=lambda kv: kv[1])],
            "cycle": [{"cycleIndex": i, "deckSlot": slots[n], "cardId": self.ids[n]}
                      for i, n in enumerate(player.cycle_queue)],
        }

    def observe(self):
        objects = self._objects()
        return {
            "ok": True, "generation": self.generation, "stateEpoch": self.generation, "tick": self.battle.tick,
            "ended": bool(self.battle.game_over), "finalized": False, "winner": None,
            "count": len(objects), "returned": len(objects), "truncated": False,
            "players": [self._player(0), self._player(1)], "objects": objects,
        }

    def observe_rich(self):
        objects = self._objects()
        return {
            "ok": True, "schema": "native-rich-telemetry.v3", "truncated": False, "tick": self.battle.tick,
            "generation": self.generation, "stateEpoch": self.generation, "count": len(objects),
            "returned": len(objects), "objects": objects,
            "combatEvents": {"ok": True, "complete": True, "hookSetAttested": True,
                             "generation": self.generation, "stateEpoch": self.generation,
                             "events": copy.deepcopy(self.events)},
        }

    def levels(self, ordinary):
        # Integer object-ID keys, exactly like ``read_native_public_levels``
        # (they only become strings once a frame is serialized to JSON).
        entities = {5000000 + e.id: e for e in self.battle.entities.values()}
        levels = {}
        for obj in ordinary["objects"]:
            if obj.get("hp") is None:
                continue
            if obj["cardId"] == -1:
                slot = ANCHORS[(obj["owner"], obj["x"], obj["y"])]
                levels[obj["nativeObjectId"]] = (
                    self.plan["kings"][obj["owner"]] if slot == 2 else self.plan["card_level"]
                )
            else:
                levels[obj["nativeObjectId"]] = int(entities[obj["nativeObjectId"]].card_stats.level)
        return levels

    def session_factory(self):
        return FakeSession(self)


class FakeSession:
    def __init__(self, native: FakeNative):
        self.native = native
        self.session_id = uuid.uuid4().hex
        self.reads = 0
        self.state = "new"
        self.identity = {"mode": "fake", "generation": native.generation}
        self.attestation_sha = common.canonical_sha(FAKE_ATTESTATION)

    def __enter__(self):
        self.state = "open"
        self.identity = {"mode": "fake", "generation": self.native.generation}
        return self

    def __exit__(self, exc_type, exc, tb):
        self.state = "failed" if exc is not None else "verified"
        return False

    def read_levels(self, ordinary=None):
        before = self.native.observe() if ordinary is None else ordinary
        self.reads += 1
        return {
            "ordinary": before,
            "levels": self.native.levels(before),
            "attestation": copy.deepcopy(FAKE_ATTESTATION["attestation"]),
            "reader_sha256": READER_SHA,
            "verified_session": {
                "schema": SESSION_SCHEMA, "session_id": self.session_id, "read_index": self.reads,
                "runtime_identity": copy.deepcopy(self.identity), "verification_frequency": SESSION_FREQUENCY,
                "pending_final_verification": True,
            },
        }

    @property
    def provenance(self):
        return {
            "schema": SESSION_SCHEMA, "session_id": self.session_id, "status": self.state,
            "verification_frequency": SESSION_FREQUENCY,
            "expected_attestation_sha256": self.attestation_sha,
            "start_attestation_sha256": self.attestation_sha,
            "end_attestation_sha256": self.attestation_sha,
            "runtime_identity": copy.deepcopy(self.identity), "reads_completed": self.reads,
            "reader_sha256": READER_SHA, "failures": [] if self.state == "verified" else ["failed"],
        }
