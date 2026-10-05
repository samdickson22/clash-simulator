#!/usr/bin/env python3
"""Merge-plan item 4a: half-tile lattice audit (read-only; no fitting).

Measures how often native-accepted and human placements sit on tile centres
(x.5, y.5) versus tile-edge/corner lattice points (integer coordinates), per
card, with the 2x2 (even-footprint) Tesla highlighted, and checks whether our
576-tile-centre action space round-trips each placement through the simulator's
building-anchor rule. Writes lattice-audit.json next to this script.

Run from the repo root:
  OMP_NUM_THREADS=4 .venv/bin/python -B reports/strategy_council_20260928/m0/merge-audits/lattice_audit.py
"""

from __future__ import annotations

import collections
import gzip
import hashlib
import json
import lzma
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
READINESS = ROOT / "reports/strategy_council_20260928/m0/readiness"
IL_REPLAY = (
    ROOT
    / "artifacts/worktree-data/clasher-event-policy/reports/"
    "external_reel_DdMGvYLsyL_20260913/sample-part-000000.parquet"
)
KATACR = ROOT / "datasets/external/Clash-Royale-Replay-Dataset"
INTERRUPTED = "native-prefix-development-v2-remaining/episode-11"

IN_SCOPE = {
    "archers": "Archers", "cannon": "Cannon", "dark-prince": "DarkPrince",
    "fireball": "Fireball", "giant": "Giant", "goblins": "Goblins",
    "hog-rider": "HogRider", "ice-golem": "IceGolem", "ice-spirit": "IceSpirit",
    "knight": "Knight", "the-log": "Log", "musketeer": "Musketeer",
    "prince": "Prince", "skeletons": "Skeletons", "tesla": "Tesla", "zap": "Zap",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def axis_class(units: int) -> str:
    r = units % 1000
    if r in (499, 500, 501):
        return "centre"
    if r in (999, 0, 1):
        return "edge"
    return "other"


def lattice_class(x: int, y: int) -> str:
    cx, cy = axis_class(x), axis_class(y)
    if cx == cy == "centre":
        return "tile_centre"
    if cx == cy == "edge":
        return "tile_corner"
    if "other" in (cx, cy):
        return "off_lattice"
    return "tile_edge_midpoint"


def footprint_sizes() -> dict[str, int]:
    from clasher.battle import BattleState

    battle = BattleState()
    sizes = {}
    for name in IN_SCOPE.values():
        stats = battle.card_loader.get_card(name)
        if getattr(stats, "card_type", None) == "Building" or name in ("Cannon", "Tesla"):
            sizes[name] = battle._building_footprint_size_tiles(stats)
    return sizes


def reproduced_anchor(x: int, y: int, footprint: int | None, *, lattice_round: bool):
    """Project a world placement to our tile action, decode, and re-anchor."""
    from clasher.arena import Position
    from clasher.placement import building_anchor

    if lattice_round:
        x, y = round(x / 500) * 500, round(y / 500) * 500
    tile_x = min(17, max(0, math.floor(x / 1000)))
    tile_y = min(31, max(0, math.floor(y / 1000)))
    centre = Position(tile_x + 0.5, tile_y + 0.5)
    if footprint is None:
        return round(centre.x * 1000), round(centre.y * 1000)
    anchor = building_anchor(centre, footprint)
    return round(anchor.x * 1000), round(anchor.y * 1000)


def native_audit(sizes):
    commands = collections.Counter()
    per_card = collections.defaultdict(collections.Counter)
    interrupted = 0
    buildings = []
    truncated_streams = []
    episodes = sorted(READINESS.glob("native-prefix-development-v2*/episode-*"))
    for episode in episodes:
        path = episode / "accepted-commands.jsonl"
        if not path.exists():
            continue
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        is_interrupted = str(episode).endswith(INTERRUPTED)
        for row in rows:
            x, y = row["native_xy"]
            per_card[row["name"]][lattice_class(x, y)] += 1
            commands[lattice_class(x, y)] += 1
            interrupted += is_interrupted
        wanted = [row for row in rows if row["name"] in sizes]
        if not wanted or not (episode / "native-frames.jsonl.gz").exists():
            continue
        # First new native object of that card/owner at or after execution.
        seen, spawned = set(), []
        try:
            with gzip.open(episode / "native-frames.jsonl.gz", "rt") as stream:
                for line in stream:
                    try:
                        ordinary = json.loads(line)["ordinary"]
                    except json.JSONDecodeError:
                        break
                    for obj in ordinary["objects"]:
                        if obj["nativeObjectId"] in seen:
                            continue
                        seen.add(obj["nativeObjectId"])
                        spawned.append((ordinary["tick"], obj))
        except EOFError:
            truncated_streams.append(str(episode.relative_to(READINESS)))
        used = set()
        for row in wanted:
            match = next(
                (
                    (tick, obj) for tick, obj in spawned
                    if tick >= row["execution_tick"]
                    and obj["cardId"] == row["native_card_id"]
                    and obj["owner"] == row["owner"]
                    and obj["nativeObjectId"] not in used
                ),
                None,
            )
            if match is None:
                continue
            tick, obj = match
            used.add(obj["nativeObjectId"])
            predicted = reproduced_anchor(*row["native_xy"], sizes[row["name"]], lattice_round=False)
            buildings.append({
                "episode": str(episode.relative_to(READINESS)),
                "card": row["name"],
                "footprint_tiles": sizes[row["name"]],
                "command_xy": row["native_xy"],
                "native_object_xy": [obj["x"], obj["y"]],
                "native_object_lattice": lattice_class(obj["x"], obj["y"]),
                "simulator_anchor_prediction": list(predicted),
                "prediction_matches_native": list(predicted) == [obj["x"], obj["y"]],
                "first_seen_tick": tick,
            })
    return {
        "source": "our submitted, native-accepted development commands (tile-centre action space by construction)",
        "episode_directories": len(episodes),
        "commands": sum(commands.values()),
        "commands_from_interrupted_claim_partial_artifacts": interrupted,
        "command_lattice": dict(commands),
        "truncated_frame_streams_read_up_to_break": truncated_streams,
        "command_lattice_by_card": {k: dict(v) for k, v in sorted(per_card.items())},
        "building_anchor_checks": buildings,
        "building_anchor_summary": {
            card: {
                "checked": sum(item["card"] == card for item in buildings),
                "native_object_lattice": dict(collections.Counter(
                    item["native_object_lattice"] for item in buildings if item["card"] == card)),
                "simulator_prediction_matches": sum(
                    item["prediction_matches_native"] for item in buildings if item["card"] == card),
            }
            for card in sorted({item["card"] for item in buildings})
        },
    }


def human_il_replay(sizes):
    import pyarrow.parquet as pq

    table = pq.read_table(IL_REPLAY, columns=["payload_json"])
    per_card = collections.defaultdict(collections.Counter)
    roundtrip = collections.defaultdict(lambda: collections.Counter())
    total = collections.Counter()
    replays = 0
    for payload in table.column("payload_json").to_pylist():
        replays += 1
        for event in json.loads(payload)["events"]:
            if event.get("kind") != "play_card":
                continue
            coords = (event.get("coordinates") or {}).get("native_world_units")
            if not coords:
                continue
            key = event.get("card_key")
            x, y = int(coords["x"]), int(coords["y"])
            label = lattice_class(x, y)
            total[label] += 1
            per_card[key][label] += 1
            if key in IN_SCOPE:
                name = IN_SCOPE[key]
                for mode, rounding in (("floor", False), ("lattice_round_then_floor", True)):
                    rx, ry = reproduced_anchor(x, y, sizes.get(name), lattice_round=rounding)
                    ok = abs(rx - x) <= 1 and abs(ry - y) <= 1
                    roundtrip[name][f"{mode}_exact_within_1_unit"] += ok
                roundtrip[name]["plays"] += 1
    in_scope = {IN_SCOPE[k]: dict(v) for k, v in per_card.items() if k in IN_SCOPE}
    non_centre = {
        k: dict(v) for k, v in per_card.items()
        if sum(n for label, n in v.items() if label != "tile_centre")
    }
    return {
        "source": str(IL_REPLAY.relative_to(ROOT)),
        "source_sha256": sha(IL_REPLAY),
        "replays": replays,
        "plays_with_coordinates": sum(total.values()),
        "lattice": dict(total),
        "in_scope_lattice_by_card": dict(sorted(in_scope.items())),
        "cards_with_any_non_centre_placement": dict(sorted(non_centre.items())),
        "in_scope_roundtrip_through_576_tile_actions": {k: dict(v) for k, v in sorted(roundtrip.items())},
        "caveats": [
            "RoyaleAPI replay markers after inversion (native = 18000 - raw x); +-1 unit is rounding.",
            "All placement forms are unknown; current-ladder levels and forms, not the pinned base ruleset.",
            "Opened development source (previously audited); not acceptance evidence and not used for fitting.",
        ],
    }


def human_katacr(max_files: int = 60):
    """Camera-estimated fractional tile coordinates (noisy); Cannon vs others."""
    files = sorted(KATACR.glob("*/*.npy.xz"))[:max_files]
    fractions = collections.defaultdict(list)
    for path in files:
        with lzma.open(path) as stream:
            payload = np.load(stream, allow_pickle=True).item()
        for state, action in zip(payload["state"], payload["action"]):
            slot = int((action or {}).get("card_id", 0) or 0)
            if slot <= 0:
                continue
            cards = state.get("cards") or []
            name = cards[slot] if slot < len(cards) else None
            xy = np.asarray(action["xy"], dtype=np.float64)
            fractions[str(name)].append(xy % 1.0)
    summary = {}
    for name, values in sorted(fractions.items(), key=lambda kv: -len(kv[1])):
        values = np.asarray(values)
        near_centre = np.all(np.abs(values - 0.5) < 0.25, axis=1)
        near_edge = np.all(np.minimum(values, 1 - values) < 0.25, axis=1)
        summary[name] = {
            "plays": int(len(values)),
            "both_axes_nearer_centre": float(near_centre.mean()),
            "both_axes_nearer_corner": float(near_edge.mean()),
        }
    return {
        "source": str(KATACR.relative_to(ROOT)),
        "files_read": len(files),
        "by_card_name_as_recorded": summary,
        "caveat": "Card identities are recorded as numeric detector class ids, and xy are camera-derived estimates whose y axis is not lattice-aligned; this source cannot resolve the half-tile lattice and is excluded from the conclusion. Hog 2.6 roster has no Tesla.",
    }


def main():
    sizes = footprint_sizes()
    result = {
        "schema": "clasher.merge-audit.half-tile-lattice.v1",
        "fitting": "none",
        "simulator_footprint_tiles": sizes,
        "native": native_audit(sizes),
        "human_il_replay": human_il_replay(sizes),
        "human_katacr": human_katacr(),
    }
    (HERE / "lattice-audit.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: result[k] for k in ("simulator_footprint_tiles",)}, indent=1))
    print(json.dumps(result["native"]["building_anchor_summary"], indent=1))
    print(json.dumps(result["human_il_replay"]["lattice"], indent=1))
    print(json.dumps(result["human_il_replay"]["cards_with_any_non_centre_placement"], indent=1))
    print(json.dumps(result["human_il_replay"]["in_scope_roundtrip_through_576_tile_actions"], indent=1))


if __name__ == "__main__":
    main()
