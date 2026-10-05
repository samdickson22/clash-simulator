"""Stream every IL_Replay replay shard and write a compact per-match index.

Shard 0 is read from the existing local copy.  The other 51 shards are not on
disk; they are streamed from the pinned public HF revision into memory,
SHA-256 checked against the dataset manifest, parsed, and discarded (no raw
shard is persisted).  Only deck/level/form/result/action-count metadata is
indexed; full payloads are kept only for small re-simulation candidate pools.

Run: OMP_NUM_THREADS=1 nice -n 15 .venv/bin/python scan_corpus.py
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import sys
import time
import urllib.request
from pathlib import Path

import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
from card_map import PILOT16, SLUG_TO_GAMEDATA, UNSUPPORTED_BASE, base_slug  # noqa: E402

SRC = ROOT / "artifacts/worktree-data/clasher-event-policy/reports/external_reel_DdMGvYLsyL_20260913"
LOCAL0 = SRC / "sample-part-000000.parquet"
MANIFEST = json.loads((SRC / "hf_manifest.json").read_text())
REV = "059d43a02138a34b1b3009cc2acc7630fb99a638"
URL = "https://huggingface.co/datasets/VanguardX101/IL_Replay/resolve/{rev}/{path}"
G66 = set(json.loads((ROOT / "training_decks/simple_gym_supported_v1.json").read_text())["support_profile"]["supported_public_cards"])
P16 = set(PILOT16)
PAYLOAD_CAP = {"p16": 2_000, "g66": 1_500, "s120": 400}


def fetch(entry) -> bytes:
    if entry["path"].endswith("part-000000.parquet"):
        data = LOCAL0.read_bytes()
    else:
        url = URL.format(rev=REV, path=entry["path"])
        for attempt in range(5):
            try:
                with urllib.request.urlopen(url, timeout=120) as r:
                    data = r.read()
                break
            except Exception as exc:  # retry transient network errors
                print("retry", entry["path"], exc, flush=True)
                time.sleep(5 * (attempt + 1))
        else:
            raise RuntimeError(f"failed {entry['path']}")
    digest = hashlib.sha256(data).hexdigest()
    if digest != entry["sha256"] or len(data) != entry["bytes"]:
        raise RuntimeError(f"hash/size mismatch {entry['path']}")
    return data


def side_scope(deck_bases):
    gd = [SLUG_TO_GAMEDATA.get(b) for b in deck_bases]
    return {
        "p16": sum(1 for g in gd if g not in P16),
        "g66": sum(1 for g in gd if g not in G66),
        "s120": sum(1 for b, g in zip(deck_bases, gd) if g is None or b in UNSUPPORTED_BASE),
    }


def main():
    entries = [f for f in MANIFEST["files"] if f["path"].startswith("replays/")]
    out_index = gzip.open(HERE / "corpus_index.jsonl.gz", "wt")
    pools = {k: gzip.open(HERE / f"payloads_{k}_tier_a.jsonl.gz", "wt") for k in PAYLOAD_CAP}
    pool_n = dict.fromkeys(PAYLOAD_CAP, 0)
    shard_log = []
    t0 = time.time()
    for si, entry in enumerate(entries):
        data = fetch(entry)
        pf = pq.ParquetFile(io.BytesIO(data))
        rows = 0
        for rg in range(pf.num_row_groups):
            tbl = pf.read_row_group(rg, columns=["replay_tag", "battle_type", "game_mode", "result", "team_crowns", "opponent_crowns", "payload_json"])
            cols = {c: tbl.column(c).to_pylist() for c in tbl.column_names}
            for i in range(tbl.num_rows):
                rows += 1
                raw = cols["payload_json"][i]
                pl = json.loads(raw)
                rec = {
                    "tag": cols["replay_tag"][i], "shard": si, "bt": cols["battle_type"][i],
                    "gm": cols["game_mode"][i], "res": cols["result"][i],
                    "tc": cols["team_crowns"][i], "oc": cols["opponent_crowns"][i],
                    "dur": (pl.get("replay") or {}).get("duration", {}).get("timeline_seconds"),
                }
                sides = {}
                for side in ("team", "opponent"):
                    players = pl["battle"][side]["players"]
                    p = players[0] if players else {"deck": [], "tower_card": {}}
                    deck = [(c["card_key"], c["level"]) for c in p["deck"]]
                    bases = [base_slug(k)[0] for k, _ in deck]
                    forms = [base_slug(k)[1] for k, _ in deck]
                    sides[side] = {
                        "n_players": len(players),
                        "deck": [k for k, _ in deck], "lv": [lv for _, lv in deck],
                        "forms": {"evo": forms.count("evo"), "hero": forms.count("hero")},
                        "tower": (p.get("tower_card") or {}).get("card_key"),
                        "ftw": p.get("final_tower_hitpoints"),
                        "unsup": side_scope(bases),
                        "unk": sorted({b for b in bases if b not in SLUG_TO_GAMEDATA}),
                        "s120_missing": sorted({b for b in bases if b not in SLUG_TO_GAMEDATA or b in UNSUPPORTED_BASE}),
                        "g66_missing": sorted({b for b in bases if SLUG_TO_GAMEDATA.get(b) not in G66}),
                    }
                ev = pl.get("events") or []
                for side in ("team", "opponent"):
                    sides[side]["plays"] = sum(1 for e in ev if e.get("side") == side and e.get("kind") == "play_card")
                    sides[side]["abil"] = sum(1 for e in ev if e.get("side") == side and e.get("kind") == "activate_ability")
                    sides[side]["last_tick"] = max((e.get("replay_tick_20hz") or 0 for e in ev if e.get("side") == side), default=0)
                rec["sides"] = sides
                val = pl.get("validation") or {}
                rec["unmatched"] = val.get("unmatched_timeline_event_count")
                rec["nocoord_plays"] = sum(1 for e in ev if e.get("kind") == "play_card" and not (e.get("coordinates") or {}).get("native_world_units"))
                out_index.write(json.dumps(rec, separators=(",", ":")) + "\n")
                both_logs = sides["team"]["plays"] > 0 and sides["opponent"]["plays"] > 0
                one_v_one = sides["team"]["n_players"] == 1 and sides["opponent"]["n_players"] == 1
                if both_logs and one_v_one:
                    for k in PAYLOAD_CAP:
                        if sides["team"]["unsup"][k] == 0 and sides["opponent"]["unsup"][k] == 0 and pool_n[k] < PAYLOAD_CAP[k]:
                            pools[k].write(json.dumps({"tag": rec["tag"], "shard": si, "payload": pl}, separators=(",", ":")) + "\n")
                            pool_n[k] += 1
            del tbl, cols
        shard_log.append({"path": entry["path"], "rows": rows, "sha256_verified": True, "source": "local" if si == 0 else "hf-stream"})
        print(f"shard {si} rows {rows} pools {pool_n} {time.time() - t0:.0f}s", flush=True)
        del data, pf
    out_index.close()
    for f in pools.values():
        f.close()
    (HERE / "scan_shards.json").write_text(json.dumps({"revision": REV, "shards": shard_log, "payload_pools": pool_n}, indent=1) + "\n")


if __name__ == "__main__":
    main()
