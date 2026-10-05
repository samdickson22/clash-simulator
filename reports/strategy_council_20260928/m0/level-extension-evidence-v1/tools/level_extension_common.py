"""Shared helpers for the level-extension probe collector, scalar study and assembler.

Nothing here decides admission. The pinned verifier
(``clasher.rl.readiness_level_extension``) recomputes every accepted value
from the raw files these helpers write.

Level-aware public views
------------------------
The pinned native public adapter only projects level-11 frames (its scope and
Crown maxima are fixed). Ranking continuations still need public views at
levels 10/12, so native frames are projected through a *derived* copy in which
every body keeps its HP fraction but reports the level-11 maximum. The views
are then restored to the true visible levels. Before doing so, every body's
native level reading is checked against the declared plan, so the restoration
is exact. Raw native frames are retained unchanged; the derived copy is only a
controller input.
"""

from __future__ import annotations

import copy
import dataclasses
import gzip
import hashlib
import json
import os
import random
import sys
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent


def prefer_runtime_scripts() -> None:
    """Resolve native helper scripts from ``$CLASHER_ROOT/scripts`` first."""
    root = os.environ.get("CLASHER_ROOT")
    if not root:
        return
    runtime = str(Path(root).resolve() / "scripts")
    if sys.path and sys.path[0] == runtime:
        return
    sys.path[:] = [p for p in sys.path if p != runtime]
    sys.path.insert(0, runtime)
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.append(str(SCRIPT_DIR))


prefer_runtime_scripts()

from clasher.arena import Position  # noqa: E402
from clasher.battle import BattleState  # noqa: E402
from clasher.entities import Building  # noqa: E402
from clasher.player import PlayerState  # noqa: E402
from clasher.rl.action_space import DiscreteTileActionSpace  # noqa: E402
from clasher.rl.native_public_observation import (  # noqa: E402
    PUBLIC_REFERENCE_CARDS,
    TOWER_ANCHORS,
)
from clasher.rl.readiness_level_extension import (  # noqa: E402
    ANCHORS,
    BODY_CHECKS,
    HORIZON_TICKS,
    SPELL_CHECKS,
    NativeLevelPlan,
)
from clasher.rl.public_scripted_opponent import PublicScriptedOpponent  # noqa: E402

DECK = (*BODY_CHECKS, *SPELL_CHECKS, "HogRider")
RANKING_CONDITIONS = ("balanced/pressure", "defense/balanced")
# Two non-wait public alternatives, fixed before any outcome is observed: the
# pressure controller's top play, which must deploy a building-targeting troop
# (the deck's win condition), and the defense controller's best play with a
# different card. A root is the first five-tick boundary at/after the declared
# minimum tick where both exist (a public-state rule, never an outcome rule).
RANKING_ROLES = ("pressure_top_win_condition", "defense_other_card")
DEFAULT_RANKING_ROOT_TICK = 90
DEFAULT_MAX_PROBE_TICK = 3000
SLOTS = {"left": 0, "right": 1, "king": 2}
TROOP_ID_RANGE = (26000000, 27000000)
TOOL_SCHEMA = "readiness-level-extension-tooling-v1"
assert HORIZON_TICKS == 200


# --------------------------------------------------------------------- files


def file_sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def write_new(path: Path, value: Any) -> dict[str, str]:
    """Write JSON exactly once and return its FilePin dictionary."""
    path = Path(path)
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return pin(path)


def pin(path: Path) -> dict[str, str]:
    path = Path(path).resolve()
    return {"path": str(path), "sha256": file_sha(path)}


def read_jsonl(path: Path) -> list[Any]:
    data = Path(path).read_bytes()
    if str(path).endswith(".gz"):
        data = gzip.decompress(data)
    return [json.loads(line) for line in data.splitlines() if line.strip()]


class JsonlWriter:
    """Exclusive-create gzip JSONL stream (one compact JSON value per line)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._stream = None

    def __enter__(self):
        self._stream = gzip.open(self.path, "xt")
        return self

    def write(self, value: Any) -> None:
        self._stream.write(json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n")
        self._stream.flush()

    def __exit__(self, *exc):
        self._stream.close()
        return False


def source_pins(paths) -> dict[str, str]:
    return {str(Path(p).resolve()): file_sha(Path(p)) for p in sorted(set(map(str, paths)))}


def runtime_identity() -> dict[str, Any]:
    """Where the imported simulator and native helpers actually came from."""
    import clasher

    identity = {
        "clasher_package": str(Path(clasher.__file__).resolve().parent),
        "clasher_root_env": os.environ.get("CLASHER_ROOT"),
        "python": sys.executable,
    }
    for name in ("read_native_public_levels", "run_readiness_v2", "smoke_reference_battle"):
        module = sys.modules.get(name)
        identity[name] = None if module is None else str(Path(module.__file__).resolve())
    return identity


def require_runtime_root(allow_workspace: bool) -> Path | None:
    """CLI guard: with CLASHER_ROOT set, every import must come from that root."""
    root = os.environ.get("CLASHER_ROOT")
    identity = runtime_identity()
    if root is None:
        if not allow_workspace:
            raise SystemExit(
                "CLASHER_ROOT is unset; run from the admitted runtime snapshot "
                "(or pass --allow-workspace-runtime for development only)"
            )
        return None
    root_path = Path(root).resolve()
    package = Path(identity["clasher_package"])
    if not package.is_relative_to(root_path / "src"):
        raise SystemExit(f"clasher imported from {package}, not {root_path}/src")
    for name in ("read_native_public_levels", "run_readiness_v2", "smoke_reference_battle"):
        location = identity.get(name)
        if location is not None and not Path(location).is_relative_to(root_path / "scripts"):
            raise SystemExit(f"{name} imported from {location}, not {root_path}/scripts")
    return root_path


def runtime_source_files(extra=()) -> list[Path]:
    import clasher

    package = Path(clasher.__file__).resolve().parent
    files = sorted(package.rglob("*.py"))
    for name in ("read_native_public_levels", "run_readiness_v2", "smoke_reference_battle",
                 "compare_reacting_public_branches"):
        module = sys.modules.get(name)
        if module is not None:
            files.append(Path(module.__file__).resolve())
    files.extend(Path(p).resolve() for p in extra)
    return files


# ------------------------------------------------------------- level plans


def plan_from_declared(row: dict[str, Any]) -> NativeLevelPlan:
    return NativeLevelPlan.model_validate(row)


def tower_levels_by_owner(plan: NativeLevelPlan) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    return plan.tower_levels(0), plan.tower_levels(1)


def attacker_for_probe(index: int) -> int:
    """Alternate which seat carries the body checks so both seats are exercised."""
    return index % 2


def ranking_root_owner(index: int) -> int:
    # Fixed by the verifier: probe p ranks for seat p % 2.
    return index % 2


# ------------------------------------------------------- scalar construction


class PlannedLevelBattle(BattleState):
    """Scalar battle whose Crowns follow a per-seat Princess/King level plan.

    Identical to ``BattleState._create_towers`` except that each seat's King
    Tower may use ``player.king_tower_level`` (native ``hbd.kt``) while its
    Princess Towers use ``player.tower_level``.
    """

    def _create_towers(self) -> None:
        cache: dict[int, tuple[Any, Any]] = {}

        def stats(level: int):
            if level not in cache:
                cache[level] = self._tower_stats(level)
            return cache[level]

        towers = []
        for player_id, anchors in enumerate((
            (self.arena.BLUE_LEFT_TOWER, self.arena.BLUE_RIGHT_TOWER, self.arena.BLUE_KING_TOWER),
            (self.arena.RED_LEFT_TOWER, self.arena.RED_RIGHT_TOWER, self.arena.RED_KING_TOWER),
        )):
            player = self.players[player_id]
            princess = stats(player.tower_level)[0]
            king = stats(getattr(player, "king_tower_level", player.tower_level))[1]
            for slot, anchor, tower_stats in zip(("left", "right", "king"), anchors, (princess, princess, king)):
                tower = self._spawn_entity(Building, Position(anchor.x, anchor.y), player_id, tower_stats)
                tower._crown_tower_slot = slot
                towers.append(tower)
        for tower in towers:
            tower.deploy_delay_remaining = 0.0
            tower.on_spawn()


def card_names_by_id(loader) -> dict[int, str]:
    return {loader.get_card(name)._raw_entry["id"]: name for name in PUBLIC_REFERENCE_CARDS}


def scalar_battle_from_native_initial(
    initial: dict[str, Any],
    config: dict[str, Any],
    loader,
    *,
    card_levels: tuple[dict[str, int], dict[str, int]],
    princess_levels: tuple[int, int],
    king_levels: tuple[int, int],
) -> PlannedLevelBattle:
    """Mirror ``compare_reacting_public_branches.scalar_initial`` with levels."""
    names = card_names_by_id(loader)
    players = []
    for owner in (0, 1):
        state = next(p for p in initial["players"] if p["owner"] == owner)
        player = PlayerState(
            owner,
            deck=[names[c["cardId"]] for c in state["deck"]],
            hand=[names[c["cardId"]] for c in sorted(state["hand"], key=lambda c: c["handIndex"])],
            cycle_queue=deque(
                names[c["cardId"]] for c in sorted(state["cycle"], key=lambda c: c["cycleIndex"])
            ),
            elixir=state["elixir"],
            card_levels=dict(card_levels[owner]),
            tower_level=princess_levels[owner],
        )
        player.king_tower_level = king_levels[owner]
        players.append(player)
    return PlannedLevelBattle(players=players, rng=random.Random(config["rndSeed"]), card_loader=loader)


def scalar_battle_for_case(
    decks: tuple[list[str], list[str]],
    card_levels: tuple[dict[str, int], dict[str, int]],
    tower_levels: tuple[int, int],
    loader,
    seed: int,
) -> PlannedLevelBattle:
    """Independent-card scalar case; hands come from a declared seeded shuffle."""
    players = []
    rng = random.Random(seed)
    for owner in (0, 1):
        order = list(decks[owner])
        rng.shuffle(order)
        players.append(
            PlayerState(
                owner,
                deck=list(decks[owner]),
                hand=order[:4],
                cycle_queue=deque(order[4:]),
                card_levels=dict(card_levels[owner]),
                tower_level=tower_levels[owner],
            )
        )
    return PlannedLevelBattle(players=players, rng=random.Random(seed + 1), card_loader=loader)


def scalar_crowns(battle) -> list[dict[str, Any]]:
    """Engine-reported Crown rows (owner, slot, level, HP) at their anchors."""
    rows = []
    for entity in battle.entities.values():
        stats = getattr(entity, "card_stats", None)
        if stats is None or stats.name not in ("Tower", "KingTower") or int(entity.entity_kind) != 1:
            continue
        x, y = round(entity.position.x * 1000), round(entity.position.y * 1000)
        slot = SLOTS[entity._crown_tower_slot]
        if ANCHORS.get((entity.player_id, x, y)) != slot:
            raise ValueError("scalar Crown is not at its declared native anchor")
        rows.append({
            "owner": entity.player_id,
            "slot": slot,
            "x": x,
            "y": y,
            "level": int(stats._raw_entry.get("publicLevel", 0)),
            "hp": float(max(0.0, entity.hitpoints)) if entity.is_alive else 0.0,
            "maxHp": int(round(entity.max_hitpoints)),
        })
    return sorted(rows, key=lambda r: (r["owner"], r["slot"]))


def scalar_crown_frame(battle) -> dict[str, Any]:
    return {
        "engine": "scalar",
        "tick": battle.tick,
        "objects": [
            {"cardId": -1, "owner": r["owner"], "x": r["x"], "y": r["y"], "hp": r["hp"],
             "maxHp": r["maxHp"], "level": r["level"]}
            for r in scalar_crowns(battle)
        ],
    }


def native_crown_frame(ordinary: dict[str, Any]) -> dict[str, Any]:
    """Crown-body projection of a raw native ending frame.

    Tower projectiles also carry ``cardId == -1`` (with ``hp == null``) and the
    pinned verifier's Crown sum does not skip them, so the ending file keeps
    only Crown *bodies*. The raw frame is retained and hash-linked.
    """
    objects = []
    for obj in ordinary["objects"]:
        if obj.get("cardId") != -1 or obj.get("hp") is None:
            continue
        if (obj["owner"], obj["x"], obj["y"]) not in ANCHORS:
            raise ValueError("native Crown body is not at a declared anchor")
        objects.append({k: obj[k] for k in ("nativeObjectId", "owner", "cardId", "x", "y", "hp", "maxHp")})
    return {
        "engine": "reference",
        "tick": ordinary["tick"],
        "generation": ordinary["generation"],
        "stateEpoch": ordinary["stateEpoch"],
        "objects": objects,
    }


def crown_projection_record(ordinary: dict[str, Any], raw_path: Path) -> dict[str, Any]:
    return {
        "schema": "readiness-level-ending-crowns-v1",
        "ordinary": native_crown_frame(ordinary),
        "raw_ordinary_sha256": canonical_sha(ordinary),
        "raw_frame": pin(raw_path),
        "projection": "Crown bodies only (cardId -1 with HP); hp-null tower projectiles omitted",
    }


# ------------------------------------------------------ level-aware views


def check_native_levels(frame: dict[str, Any], plan: NativeLevelPlan, loader) -> None:
    """Every HP-bearing object must carry exactly its declared native level."""
    ordinary = frame["ordinary"]
    levels = frame["level_source"]["levels"]
    deck_ids = {loader.get_card(name)._raw_entry["id"] for name in DECK}
    for obj in ordinary["objects"]:
        if obj.get("hp") is None:
            continue
        level = levels.get(str(obj["nativeObjectId"]))
        if obj["cardId"] == -1:
            slot = ANCHORS.get((obj["owner"], obj["x"], obj["y"]))
            if slot is None or level != plan.tower_levels(obj["owner"])[slot]:
                raise ValueError("native Crown level differs from the declared plan")
        elif obj["cardId"] not in deck_ids or level != plan.card_level:
            raise ValueError("native body level differs from the uniform card plan")


def level11_projection_frame(frame: dict[str, Any], adapter) -> dict[str, Any]:
    """Derived frame for the pinned level-11 adapter: HP fractions kept."""
    ordinary = copy.deepcopy(frame["ordinary"])
    rich = copy.deepcopy(frame["rich"])
    rich_by_id = {o["nativeObjectId"]: o for o in rich.get("objects", [])}
    for obj in ordinary["objects"]:
        if obj.get("hp") is None:
            continue
        if obj["cardId"] == -1:
            target = TOWER_ANCHORS[(obj["owner"], obj["x"], obj["y"])][1]
        else:
            entry = adapter.cards.get(obj["cardId"])
            if entry is None:
                raise ValueError(f"undeclared native body {obj['cardId']}")
            target = int(entry[1].scaled_hitpoints)
        hp, maximum = int(obj["hp"]), int(obj["maxHp"])
        scaled = 0 if hp <= 0 else max(1, min(target, round(hp * target / maximum)))
        obj["hp"], obj["maxHp"] = scaled, target
        if obj["nativeObjectId"] in rich_by_id:
            rich_by_id[obj["nativeObjectId"]]["hp"] = scaled
            rich_by_id[obj["nativeObjectId"]]["maxHp"] = target
    source = copy.deepcopy(frame["level_source"])
    source["ordinary"] = ordinary
    source["levels"] = {key: 11 for key in source["levels"]}
    return {"ordinary": ordinary, "rich": rich, "level_source": source}


def restore_true_levels(view, builder, perspective: int, plan: NativeLevelPlan):
    """Put the (already checked) declared visible levels back into the view."""
    obs = view.observation
    levels = np.array(obs.entity_levels, copy=True)
    towers = {
        builder.token_id("Tower", namespace="tower"): 0,
        builder.token_id("KingTower", namespace="tower"): 2,
    }
    for index in np.flatnonzero(obs.entity_mask):
        if levels[index] == 0:
            continue
        if levels[index] != 11:
            raise ValueError("derived projection must report level 11")
        token = int(obs.entity_ids[index])
        if token in towers:
            owner = perspective if obs.entity_features[index][2] > 0.5 else 1 - perspective
            levels[index] = plan.tower_levels(owner)[towers[token]]
        else:
            levels[index] = plan.card_level
    restored = dataclasses.replace(obs, entity_levels=levels)
    return dataclasses.replace(view, observation=restored)


def native_level_views(frame, plan, adapter, maps, history, loader, builder, public_views):
    """Level-true public views of a native probe frame for both seats."""
    check_native_levels(frame, plan, loader)
    derived = level11_projection_frame(frame, adapter)
    views = public_views(derived, adapter, maps, history)
    return [restore_true_levels(view, builder, owner, plan) for owner, view in enumerate(views)]


def ranking_candidates(builder, view) -> list[dict[str, Any]]:
    """Attack-versus-defense alternatives; raise ValueError when ineligible."""
    ids = view.observation.hand_ids
    pressure = PublicScriptedOpponent(builder, style="pressure").ranked_plays(view)
    defense = PublicScriptedOpponent(builder, style="defense").ranked_plays(view)
    if not pressure:
        raise ValueError("ineligible ranking root: no legal play")
    first = pressure[0]
    first_token = int(ids[first.action_id // 576])
    name = builder.card_name_for_token_id(first_token)
    stats = None if name is None else builder.loader.get_card(name)
    if stats is None or str(stats.card_type).lower() != "troop" or not stats.targets_only_buildings:
        raise ValueError("ineligible ranking root: pressure top play is not a win-condition troop")
    other = next((p for p in defense if int(ids[p.action_id // 576]) != first_token), None)
    if other is None:
        raise ValueError("ineligible ranking root: no defensive play with another card")
    rows = []
    for index, (role, play) in enumerate(zip(RANKING_ROLES, (first, other))):
        token = int(ids[play.action_id // 576])
        rows.append({
            "candidate": index,
            "role": role,
            "action_id": int(play.action_id),
            "card_token": token,
            "card": builder.card_name_for_token_id(token),
            "public_score": float(play.score),
        })
    return rows


class DamageRecorder:
    """Record every ``Entity.take_damage`` request made by the scalar engine.

    The requested amount is the engine's own value before shields/modifiers,
    matching the native ``requestedAmount`` field. Restored on exit.
    """

    def __init__(self):
        self.calls: list[dict[str, Any]] = []
        self._original = None

    def __enter__(self):
        from clasher.entities import Entity

        original = Entity.take_damage
        recorder = self

        def take_damage(entity, amount, *, source_kind=None, affects_hidden=False):
            stats = getattr(entity, "card_stats", None)
            recorder.calls.append({
                "entity_id": entity.id,
                "target": None if stats is None else stats.name,
                "target_owner": entity.player_id,
                "amount": float(amount),
                "source_kind": source_kind,
                "tick": getattr(getattr(entity, "battle_state", None), "tick", None),
            })
            return original(entity, amount, source_kind=source_kind, affects_hidden=affects_hidden)

        self._original = original
        Entity.take_damage = take_damage
        return self

    def __exit__(self, *exc):
        from clasher.entities import Entity

        Entity.take_damage = self._original
        return False


# --------------------------------------------------------- coverage driver


def spell_damage_events(rich: dict[str, Any], spell_ids: dict[int, str]) -> list[dict[str, Any]]:
    """Validated spell HP damage on a troop/building body (verifier's filter)."""
    combat = rich.get("combatEvents") or {}
    found = []
    for event in combat.get("events") or ():
        source, target = event.get("source") or {}, event.get("target") or {}
        if (
            event.get("kind") == "damage"
            and event.get("pool") == "hitpoints"
            and source.get("validated") is True
            and target.get("validated") is True
            and source.get("cardId") in spell_ids
            and isinstance(target.get("cardId"), int)
            and 26000000 <= target["cardId"] < 28000000
        ):
            found.append(event)
    return found


class CoverageDriver:
    """Deterministic public-legal plays that make every level check observable.

    The attacker seat plays each body check (Knight, Musketeer, Dark Prince,
    Cannon) in one lane; the defender casts Fireball, Log and Zap on attacking
    troops once they cross into its half. Other cards cycle the hand. Every
    action is chosen from the public action mask; nothing is forced natively.
    """

    RETRY_TICKS = 100

    def __init__(self, loader, *, attacker: int, card_level: int):
        self.loader = loader
        self.attacker, self.defender = attacker, 1 - attacker
        self.card_level = card_level
        self.space = DiscreteTileActionSpace()
        self.ids = {name: loader.get_card(name)._raw_entry["id"] for name in DECK}
        self.names = {v: k for k, v in self.ids.items()}
        self.spell_ids = {self.ids[name]: name for name in SPELL_CHECKS}
        self.body_ids = {self.ids[name]: name for name in BODY_CHECKS}
        self.bodies_seen: dict[str, int] = {}
        self.spells_seen: dict[str, int] = {}
        self.pending: dict[tuple[int, str], int] = {}
        self._keep_cycling = False

    # Intents in world tile coordinates for seat 0; seat 1 is point-mirrored.
    LANE = (3.5, 13.5)
    BUILDING = (9.5, 9.5)
    BACK_OPPOSITE = (16.5, 1.5)
    BACK_SAME = (1.5, 1.5)

    @staticmethod
    def _mirror(point, owner):
        return point if owner == 0 else (18.0 - point[0], 32.0 - point[1])

    def observe(self, frame: dict[str, Any]) -> None:
        ordinary = frame["ordinary"]
        tick = ordinary["tick"]
        levels = frame["level_source"]["levels"]
        for obj in ordinary["objects"]:
            name = self.body_ids.get(obj.get("cardId"))
            if (
                name is not None
                and obj.get("hp") is not None
                and obj["owner"] == self.attacker
                and levels.get(str(obj["nativeObjectId"])) == self.card_level
            ):
                self.bodies_seen.setdefault(name, tick)
        for event in spell_damage_events(frame.get("rich", {}), self.spell_ids):
            if event["source"].get("owner") == self.defender:
                self.spells_seen.setdefault(self.spell_ids[event["source"]["cardId"]], tick)

    def needs(self, owner: int) -> list[str]:
        if owner == self.attacker:
            return [n for n in BODY_CHECKS if n not in self.bodies_seen]
        return [n for n in SPELL_CHECKS if n not in self.spells_seen]

    def complete(self) -> bool:
        return not self.needs(self.attacker) and not self.needs(self.defender)

    def coverage(self) -> dict[str, Any]:
        return {
            "attacker": self.attacker,
            "card_level": self.card_level,
            "bodies_first_seen_tick": dict(self.bodies_seen),
            "spells_first_damage_tick": dict(self.spells_seen),
            "complete": self.complete(),
        }

    def _legal_nearest(self, mask, owner: int, slot: int, point) -> int | None:
        best, best_distance = None, None
        base = slot * 576
        for tile in np.flatnonzero(mask[base:base + 576]):
            action = base + int(tile)
            position = self.space.decode_action(action, owner).position
            distance = (position.x - point[0]) ** 2 + (position.y - point[1]) ** 2
            if best_distance is None or distance < best_distance - 1e-9:
                best, best_distance = action, distance
        return best

    def _available(self, player, mask, owner):
        cards = []
        for card in player["hand"]:
            name = self.names.get(card["cardId"])
            slot = card["handIndex"]
            if name is not None and mask[slot * 576: slot * 576 + 576].any():
                cards.append((name, slot, card["cost"]))
        return cards

    def _pending(self, owner, name, tick):
        started = self.pending.get((owner, name))
        return started is not None and tick - started < self.RETRY_TICKS

    def _attack_troops(self, ordinary):
        """Attacker troops already in the defender's half, most advanced first."""
        rows = []
        for obj in ordinary["objects"]:
            card = obj.get("cardId")
            if (
                obj.get("hp") in (None, 0)
                or obj["owner"] != self.attacker
                or not isinstance(card, int)
                or not TROOP_ID_RANGE[0] <= card < TROOP_ID_RANGE[1]
            ):
                continue
            y = obj["y"]
            crossed = y >= 17000 if self.defender == 1 else y <= 15000
            if crossed:
                progress = y if self.defender == 1 else -y
                rows.append((progress, obj["nativeObjectId"], obj))
        return [row[2] for row in sorted(rows, key=lambda r: (-r[0], r[1]))]

    def choose(self, owner: int, ordinary: dict[str, Any], mask, *, keep_cycling: bool = False
               ) -> tuple[int, dict[str, Any]]:
        """``keep_cycling`` keeps a seat cycling after coverage (ranking root search)."""
        self._keep_cycling = keep_cycling
        tick = ordinary["tick"]
        player = next(p for p in ordinary["players"] if p["owner"] == owner)
        elixir = player["elixirRaw"] / 10000
        cards = self._available(player, mask, owner)
        needs = self.needs(owner)
        wait = (self.space.no_op_action, {"intent": "wait"})
        if owner == self.attacker:
            for name, slot, _cost in cards:
                if name in needs and not self._pending(owner, name, tick):
                    point = self.BUILDING if name == "Cannon" else self.LANE
                    action = self._legal_nearest(mask, owner, slot, self._mirror(point, owner))
                    if action is not None:
                        self.pending[(owner, name)] = tick
                        return action, {"intent": "body_check", "card": name}
            troops_alive = any(
                obj["owner"] == owner and obj.get("hp") and TROOP_ID_RANGE[0] <= obj["cardId"] < TROOP_ID_RANGE[1]
                for obj in ordinary["objects"]
            )
            if not needs and self.needs(self.defender) and not troops_alive:
                troops = [c for c in cards if TROOP_ID_RANGE[0] <= self.ids[c[0]] < TROOP_ID_RANGE[1]]
                if troops:
                    name, slot, _ = min(troops, key=lambda c: (c[2], c[1]))
                    action = self._legal_nearest(mask, owner, slot, self._mirror(self.LANE, owner))
                    if action is not None:
                        return action, {"intent": "spell_target", "card": name}
            return self._cycle(owner, cards, needs, elixir, mask, wait)
        targets = self._attack_troops(ordinary)
        if targets:
            target = targets[0]
            for name, slot, _cost in cards:
                if name in needs and not self._pending(owner, name, tick):
                    x, y = target["x"] / 1000, target["y"] / 1000
                    if name == "Log":
                        # The Log rolls away from its caster; start behind the target.
                        y += 1.0 if owner == 1 else -1.0
                    action = self._legal_nearest(mask, owner, slot, (x, y))
                    if action is not None:
                        self.pending[(owner, name)] = tick
                        return action, {
                            "intent": "spell_check",
                            "card": name,
                            "target_native_object_id": target["nativeObjectId"],
                        }
        return self._cycle(owner, cards, needs, elixir, mask, wait)

    def _cycle(self, owner, cards, needs, elixir, mask, wait):
        """Cycle an unneeded card far from the action once elixir is high."""
        if not self.needs(self.attacker) and not self.needs(self.defender) and not self._keep_cycling:
            return wait
        if elixir < 8.5 or any(name in needs for name, _s, _c in cards):
            return wait
        spare = [c for c in cards if c[0] not in needs]
        if not spare:
            return wait
        name, slot, _ = min(spare, key=lambda c: (c[2], c[1]))
        point = self.BACK_OPPOSITE if owner == self.defender else self.BACK_SAME
        if owner == self.attacker and TROOP_ID_RANGE[0] <= self.ids[name] < TROOP_ID_RANGE[1]:
            point = self.LANE  # extra attacking troops become spell targets
        action = self._legal_nearest(mask, owner, slot, self._mirror(point, owner))
        if action is None:
            return wait
        return action, {"intent": "cycle", "card": name}
