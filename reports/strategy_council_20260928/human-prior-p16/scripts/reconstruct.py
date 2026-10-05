"""Reconstruct every P16 perspective into compact human-replay shards.

Input : data/payloads/shard-XXX.jsonl.gz (fetch_payloads.py)
Output: data/recon/shard-XXX-part-YY.npz and data/recon/shard-XXX.done.json
Resumable per source shard (a shard without its .done.json is redone).

Run (from the frozen runtime root):
  R=<repo>/reports/strategy_council_20260928/m0/runtime-snapshots/pilot-runtime-v4
  cd $R && CLASHER_ROOT=$R PYTHONPATH=$R/src OMP_NUM_THREADS=1 nice -n 10 \
    <repo>/.venv/bin/python <out>/scripts/reconstruct.py --workers 4
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import sys
import time
import traceback
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hp_bootstrap as hb  # noqa: E402

RECON = hb.OUT / "data" / "recon"
PART_PERSPECTIVES = 48
_STATE: dict = {}


def fit_split(match_id: str) -> int:
    """1 = validation (10% of matches, both perspectives together)."""
    return int(int(hashlib.sha256(match_id.encode()).hexdigest()[:8], 16) % 10 == 0)


def token_stats(arrays) -> dict:
    mask = arrays["entity_mask"]
    ids = arrays["entity_ids"][mask]
    features = arrays["entity_features"][mask]
    enemy = features[:, 3] > 0.5
    kinds = features[:, 4:9].argmax(axis=1)
    unknown = ids == 1
    history = arrays["opponent_history_ids"]
    seen = arrays["opponent_seen_card_ids"]
    result = {
        "entity_tokens": int(ids.size), "entity_unknown": int(unknown.sum()),
        "enemy_tokens": int(enemy.sum()), "enemy_unknown": int((unknown & enemy).sum()),
        "own_unknown": int((unknown & ~enemy).sum()),
        "history_tokens": int((history > 0).sum()), "history_unknown": int((history == 1).sum()),
        "seen_tokens": int((seen > 0).sum()), "seen_unknown": int((seen == 1).sum()),
        "max_entities_in_row": int(mask.sum(axis=1).max()),
    }
    for index, name in enumerate(("troop", "building", "projectile", "area", "other")):
        result[f"enemy_{name}_tokens"] = int((enemy & (kinds == index)).sum())
        result[f"enemy_{name}_unknown"] = int((enemy & unknown & (kinds == index)).sum())
    return result


def plays_by_card(arrays, builder) -> dict:
    labels = arrays["expert_actions"]
    rows = np.flatnonzero((labels < 2304) & arrays["expert_action_supervision_valid"])
    counts: dict[str, int] = {}
    for row in rows:
        name = builder.token_names[int(arrays["hand_ids"][row, labels[row] // 576])]
        counts[name] = counts.get(name, 0) + 1
    return counts


def run_shard(shard: int) -> dict:
    if "builder" not in _STATE:
        _STATE["hrd"] = hb.load_new_module("human_replay_demonstrations")
        _STATE["builder"] = hb.pilot_builder()
        _STATE["mask"] = _STATE["hrd"].CachedPublicActionMask(_STATE["builder"])
        _STATE["slugs"] = hb.slug_map()
    hrd, builder, mask_builder, slugs = (_STATE[name] for name in ("hrd", "builder", "mask", "slugs"))
    started = time.time()
    for stale in RECON.glob(f"shard-{shard:03d}-part-*.npz*"):
        stale.unlink()
    writer = hrd.HumanReplayShardWriter()
    parts, summaries, errors = [], [], []

    def flush() -> None:
        nonlocal writer
        if len(writer):
            path = RECON / f"shard-{shard:03d}-part-{len(parts):02d}.npz"
            writer.write(path, extra={"source_shard": shard})
            parts.append({"path": path.name, "rows": writer.rows, "perspectives": len(writer),
                          "bytes": path.stat().st_size})
        writer = hrd.HumanReplayShardWriter()

    for match_index, record in enumerate(hb.read_payloads(shard)):
        try:
            match = hrd.parse_il_replay_record(record, slugs)
        except Exception as error:  # malformed recording
            errors.append({"match_id": record.get("tag"), "stage": "parse", "error": repr(error)})
            continue
        for side in record["p16_sides"]:
            seat = ("team", "opponent").index(side)
            episode = shard * 100_000 + match_index * 2 + seat
            try:
                game = hrd.reconstruct_perspective(match, seat, builder, mask_builder=mask_builder, episode_id=episode)
            except Exception as error:
                errors.append({"match_id": match.match_id, "side": side, "stage": "reconstruct",
                               "error": repr(error), "trace": traceback.format_exc()[-1500:]})
                continue
            arrays = game.imitation_arrays()
            game.summary["fit_split"] = fit_split(match.match_id)
            game.summary["token_stats"] = token_stats(arrays)
            game.summary["plays_by_card"] = plays_by_card(arrays, builder)
            writer.add(game)
            summaries.append(game.summary | {"part": len(parts)})
            if len(writer) >= PART_PERSPECTIVES:
                flush()
    flush()
    done = {"shard": shard, "parts": parts, "perspectives": summaries, "errors": errors,
            "wall_seconds": round(time.time() - started, 1),
            "mask_cache": {"hits": mask_builder.hits, "misses": mask_builder.misses}}
    temporary = RECON / f"shard-{shard:03d}.done.json.tmp"
    temporary.write_text(json.dumps(done, sort_keys=True))
    temporary.replace(RECON / f"shard-{shard:03d}.done.json")
    return {"shard": shard, "perspectives": len(summaries), "rows": sum(part["rows"] for part in parts),
            "errors": len(errors), "wall_seconds": done["wall_seconds"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--shards", type=int, nargs="*")
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        raise SystemExit("use at most four workers")
    hb.bind_runtime()
    RECON.mkdir(parents=True, exist_ok=True)
    shards = args.shards if args.shards else list(range(52))
    pending = [shard for shard in shards if not (RECON / f"shard-{shard:03d}.done.json").exists()]
    pending.sort(key=lambda shard: -(hb.OUT / "data/payloads" / f"shard-{shard:03d}.jsonl.gz").stat().st_size)
    print(json.dumps({"pending": pending}), flush=True)
    with multiprocessing.get_context("spawn").Pool(args.workers, maxtasksperchild=4) as pool:
        for result in pool.imap_unordered(run_shard, pending):
            print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
