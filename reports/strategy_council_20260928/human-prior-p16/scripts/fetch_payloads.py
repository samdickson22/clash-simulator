"""Re-stream IL_Replay shards and keep only matches with a P16 perspective.

P16 perspective: one side's 8 cards (base forms) are all pilot cards and both
decks are simulable in the S117 scalar scope.  Each source shard is verified
against the pinned manifest SHA-256, filtered, written as
data/payloads/shard-XXX.jsonl.gz and discarded.  Finished shards are skipped.

Run: nice -n 10 .venv/bin/python fetch_payloads.py
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "data" / "payloads"
ROOT = HERE.parents[3]
SCAN = ROOT / "reports/strategy_council_20260928/m0/human-prior-scan"
sys.path.insert(0, str(SCAN))
from card_map import PILOT16, SLUG_TO_GAMEDATA, UNSUPPORTED_BASE, base_slug  # noqa: E402

SRC = ROOT / "artifacts/worktree-data/clasher-event-policy/reports/external_reel_DdMGvYLsyL_20260913"
LOCAL0 = SRC / "sample-part-000000.parquet"
MANIFEST = json.loads((SRC / "hf_manifest.json").read_text())
REV = "059d43a02138a34b1b3009cc2acc7630fb99a638"
URL = "https://huggingface.co/datasets/VanguardX101/IL_Replay/resolve/{rev}/{path}"
P16 = set(PILOT16)


def fetch(entry) -> bytes:
    if entry["path"].endswith("part-000000.parquet"):
        data = LOCAL0.read_bytes()
    else:
        url = URL.format(rev=REV, path=entry["path"])
        for attempt in range(6):
            try:
                with urllib.request.urlopen(url, timeout=180) as response:
                    data = response.read()
                break
            except Exception as exc:  # transient network errors
                print("retry", entry["path"], exc, flush=True)
                time.sleep(5 * (attempt + 1))
        else:
            raise RuntimeError(f"failed {entry['path']}")
    if hashlib.sha256(data).hexdigest() != entry["sha256"] or len(data) != entry["bytes"]:
        raise RuntimeError(f"hash/size mismatch {entry['path']}")
    return data


def deck_ok(deck, scope):
    bases = [base_slug(card["card_key"])[0] for card in deck]
    if scope == "p16":
        return len(bases) == 8 and all(SLUG_TO_GAMEDATA.get(b) in P16 for b in bases)
    return len(bases) == 8 and all(b in SLUG_TO_GAMEDATA and b not in UNSUPPORTED_BASE for b in bases)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    entries = [f for f in MANIFEST["files"] if f["path"].startswith("replays/")]
    for index, entry in enumerate(entries):
        target = OUT / f"shard-{index:03d}.jsonl.gz"
        if target.exists():
            continue
        data = fetch(entry)
        parquet = pq.ParquetFile(io.BytesIO(data))
        kept = rows = 0
        temporary = target.with_suffix(".tmp")
        with gzip.open(temporary, "wt") as stream:
            for group in range(parquet.num_row_groups):
                table = parquet.read_row_group(group, columns=["replay_tag", "battle_type", "game_mode", "payload_json"])
                columns = {name: table.column(name).to_pylist() for name in table.column_names}
                for row in range(table.num_rows):
                    rows += 1
                    payload = json.loads(columns["payload_json"][row])
                    battle = payload["battle"]
                    sides = {}
                    for side in ("team", "opponent"):
                        players = battle[side]["players"]
                        sides[side] = players[0]["deck"] if len(players) == 1 else None
                    if any(deck is None for deck in sides.values()):
                        continue
                    if not all(deck_ok(deck, "s117") for deck in sides.values()):
                        continue
                    p16_sides = [side for side in ("team", "opponent") if deck_ok(sides[side], "p16")]
                    if not p16_sides:
                        continue
                    events = payload.get("events") or []
                    if any(not any(e.get("side") == side and e.get("kind") == "play_card" for e in events) for side in ("team", "opponent")):
                        continue
                    stream.write(json.dumps({"tag": columns["replay_tag"][row], "shard": index,
                        "battle_type": columns["battle_type"][row], "game_mode": columns["game_mode"][row],
                        "p16_sides": p16_sides, "payload": payload}, separators=(",", ":")) + "\n")
                    kept += 1
        os.replace(temporary, target)
        print(json.dumps({"shard": index, "rows": rows, "kept": kept, "sha256_verified": True,
                          "source": "local" if index == 0 else "hf-stream"}), flush=True)
        del data, parquet


if __name__ == "__main__":
    main()
