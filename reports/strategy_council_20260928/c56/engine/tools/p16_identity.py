"""16-card byte-identity recorder/checker for the C56 engine work.

Records a fixed set of scalar 16-card matches and branches (both seats played by
PublicScriptedOpponent with the pilot's declared level-11 ruleset and the active
CLASHER_ROOT gamedata) and stores a digest of the full mutable simulation
state every five ticks plus every selected action. ``check`` replays the same
set with the current workspace source and requires identical digests.

Usage (from the repository root):
  nice -n 10 .venv/bin/python reports/strategy_council_20260928/c56/engine/tools/p16_identity.py record OUT.json
  nice -n 10 .venv/bin/python reports/strategy_council_20260928/c56/engine/tools/p16_identity.py check BASELINE.json
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import random
import sys
import time
from collections import deque
from enum import Enum
from pathlib import Path

import numpy as np

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.paths import gamedata_path
from clasher.player import PlayerState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.native_public_observation import (
    NativeProjectileCatalog,
    public_reference_builder,
)
from clasher.rl.public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from clasher.rl.public_observation import reference_public_observation
from clasher.rl.public_scripted_opponent import PublicScriptedOpponent
from clasher.rl.readiness_execution import packet_sha

ROOT = Path(__file__).resolve().parents[5]
CATALOG = Path.home() / ".cache/clasher-native-reference/decoded-logic-1e505767/projectiles.csv"
CATALOG_SHA = "c59ef74273b721b861e6a499bc8869a6fc29ad07919884b79ebe859455d6eac5"
TRAINING_DECKS = ROOT / "reports/strategy_council_20260928/m0/data/roles_v2/training.json"

MATCH_TICKS = 3700  # regular time + early double elixir; keeps the check affordable
BRANCH_ROOTS = (600, 1500)
BRANCH_TICKS = 400
STYLES = ("balanced", "pressure", "defense")


def _primitive(value, depth=0):
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return float.hex(value)
    if isinstance(value, Enum):
        return str(value)
    if isinstance(value, Position):
        return (float.hex(float(value.x)), float.hex(float(value.y)))
    if isinstance(value, np.generic):
        return _primitive(value.item(), depth)
    if isinstance(value, np.ndarray):
        if value.size > 4096:
            return ("ndarray", value.shape, hashlib.sha256(value.tobytes()).hexdigest())
        return ("ndarray", value.shape, value.tobytes().hex())
    if depth >= 3:
        return type(value).__name__
    if isinstance(value, (list, tuple, deque)):
        return [_primitive(v, depth + 1) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(repr(_primitive(v, depth + 1)) for v in value)
    if isinstance(value, dict):
        return sorted((repr(k), repr(_primitive(v, depth + 1))) for k, v in value.items())
    if hasattr(value, "__dict__") and type(value).__module__.startswith("clasher"):
        # Card stats / loaders are immutable for this purpose; record identity only.
        name = type(value).__name__
        if name in {"CardStatsCompat", "CardDefinition", "CardDataLoader", "BattleState"}:
            return (name, getattr(value, "name", None))
        if name in {"Troop", "Building", "Projectile", "Entity", "AreaEffect"} or hasattr(value, "player_id") and hasattr(value, "position"):
            return (name, getattr(value, "id", None))
        return (name, _primitive(vars(value), depth + 1))
    return type(value).__name__


def state_digest(battle: BattleState) -> str:
    h = hashlib.sha256()
    head = {
        "tick": battle.tick,
        "time": float.hex(float(battle.time)),
        "flags": [battle.double_elixir, battle.triple_elixir, battle.overtime, battle.sudden_death, battle.game_over, battle.winner],
        "next_id": battle.next_entity_id,
        "players": [_primitive(vars(p)) for p in battle.players],
        "pending_spells": _primitive(battle._pending_spell_casts),
        "pending_impacts": _primitive(battle._pending_projectile_impacts),
        "history": _primitive(battle.public_card_play_history),
        "rng": hashlib.sha256(repr(battle.rng.getstate()).encode()).hexdigest(),
    }
    h.update(json.dumps(head, sort_keys=True, default=str).encode())
    for entity_id in sorted(battle.entities):
        entity = battle.entities[entity_id]
        record = (type(entity).__name__, entity_id, _primitive(vars(entity), 1))
        h.update(json.dumps(record, sort_keys=True, default=str).encode())
    return h.hexdigest()


def resources():
    loader = CardDataLoader(gamedata_path())
    catalog = NativeProjectileCatalog.from_csv(CATALOG, expected_sha256=CATALOG_SHA)
    builder = public_reference_builder(loader, catalog, public_contract_version=4)
    return loader, builder, PublicActionMaskBuilder(builder), DiscreteTileActionSpace()


def episodes():
    decks = [tuple(d["cards"]) for d in json.loads(TRAINING_DECKS.read_text())["decks"]]
    from clasher.rl.readiness_root_bank import DECKS

    pool = list(dict.fromkeys(list(DECKS) + decks))
    rng = random.Random(20261002)
    out = []
    for index in range(12):
        a, b = rng.choice(pool), rng.choice(pool)
        a, b = list(a), list(b)
        rng.shuffle(a)
        rng.shuffle(b)
        out.append(
            {
                "id": f"p16-{index:02d}",
                "seed": rng.getrandbits(32),
                "decks": [a, b],
                "styles": [rng.choice(STYLES), rng.choice(STYLES)],
            }
        )
    return out


def new_battle(ep, loader):
    players = [
        PlayerState(owner, deck=list(deck), hand=list(deck[:4]), cycle_queue=deque(deck[4:]))
        for owner, deck in enumerate(ep["decks"])
    ]
    return BattleState(players=players, rng=random.Random(ep["seed"]), card_loader=loader)


def play(battle, res, controllers, until, trace, forced=None, stop=None):
    loader, builder, mask_builder, space = res
    while battle.tick < 90 and not battle.game_over:
        battle.step()
    while battle.tick < until and not battle.game_over:
        views = [reference_public_observation(builder.build_actor(battle, o)) for o in (0, 1)]
        if stop is not None and stop(views):
            return
        actions = [int(c.select_action(v)) for c, v in zip(controllers, views)]
        if forced is not None:
            actions[0] = forced
            forced = None
        trace.append([battle.tick, actions, [packet_sha(v) for v in views], state_digest(battle)])
        for owner, action in enumerate(actions):
            mask = mask_builder.build(PublicActionMaskInput.from_confidence_observation(views[owner]))
            if not mask[action]:
                raise ValueError("illegal scripted action")
            choice = space.decode_action(action, owner)
            if choice.is_no_op:
                continue
            name = builder.card_name_for_token_id(int(views[owner].observation.hand_ids[choice.slot]))
            if not battle.deploy_card(owner, name, choice.position):
                raise ValueError("scalar rejected public-legal command")
        for _ in range(5):
            if not battle.game_over:
                battle.step()
    trace.append([battle.tick, None, None, state_digest(battle)])


def run_all(limit=None):
    res = resources()
    loader, builder, _, _ = res
    results = {}
    for ep in episodes()[:limit]:
        started = time.monotonic()
        with contextlib.redirect_stdout(io.StringIO()):
            battle = new_battle(ep, loader)
            controllers = [PublicScriptedOpponent(builder, style=s) for s in ep["styles"]]
            trace = []
            roots = {}
            for root_tick in BRANCH_ROOTS:
                play(battle, res, controllers, root_tick, trace)
                # Root = first five-tick boundary at which seat 0 has two distinct legal slots.
                play(battle, res, controllers, root_tick + 600, trace,
                     stop=lambda views: len({d.action_id // 576 for d in controllers[0].ranked_plays(views[0])}) >= 2)
                if battle.game_over:
                    break
                roots[battle.tick] = battle.clone()
            play(battle, res, controllers, MATCH_TICKS, trace)
            branches = {}
            for root_tick, root in roots.items():
                view = reference_public_observation(builder.build_actor(root, 0))
                best_per_slot = {}
                for d in controllers[0].ranked_plays(view):
                    best_per_slot.setdefault(d.action_id // 576, d.action_id)
                picks = [2304] + sorted(best_per_slot.values())
                for action in picks:
                    branch = root.clone()
                    bots = [PublicScriptedOpponent(builder, style=s) for s in ep["styles"]]
                    btrace = []
                    play(branch, res, bots, root_tick + BRANCH_TICKS, btrace, forced=action)
                    branches[f"{root_tick}:{action}"] = btrace
        results[ep["id"]] = {"episode": ep, "trace": trace, "branches": branches,
                             "final_tick": battle.tick, "winner": battle.winner}
        print(f"{ep['id']} ticks={battle.tick} branches={len(branches)} {time.monotonic()-started:.1f}s", file=sys.stderr, flush=True)
    return results


def main():
    mode, path = sys.argv[1], Path(sys.argv[2])
    if mode not in {"record", "check"}:
        raise ValueError(mode)
    if mode == "record" and path.exists():
        raise FileExistsError(path)
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else None
    results = run_all(limit)
    if mode == "record":
        path.write_text(json.dumps(results, separators=(",", ":")))
        boundaries = sum(len(r["trace"]) + sum(len(b) for b in r["branches"].values()) for r in results.values())
        print(json.dumps({"recorded_episodes": len(results), "digest_boundaries": boundaries}))
        return
    baseline = json.loads(path.read_text())
    mismatches = []
    boundaries = 0
    if limit is not None:
        baseline = {ep["id"]: baseline[ep["id"]] for ep in episodes()[:limit]}
    for key in sorted(results.keys() | baseline.keys()):
        if key not in results or key not in baseline:
            mismatches.append((key, "missing episode", None))
            continue
        row = results[key]
        base = baseline[key]
        for field in ("episode", "final_tick", "winner"):
            if row[field] != base[field]:
                mismatches.append((key, field, None))
        if json.loads(json.dumps(row["trace"])) != base["trace"]:
            first = next((i for i, (a, b) in enumerate(zip(json.loads(json.dumps(row["trace"])), base["trace"])) if a != b), None)
            mismatches.append((key, "match", first))
        for bkey in sorted(row["branches"].keys() | base["branches"].keys()):
            if json.loads(json.dumps(row["branches"].get(bkey))) != base["branches"].get(bkey):
                mismatches.append((key, bkey, None))
        boundaries += len(row["trace"]) + sum(len(b) for b in row["branches"].values())
    print(json.dumps({"checked_episodes": len(results), "digest_boundaries": boundaries, "mismatches": mismatches}))
    if mismatches:
        sys.exit(1)


if __name__ == "__main__":
    main()
