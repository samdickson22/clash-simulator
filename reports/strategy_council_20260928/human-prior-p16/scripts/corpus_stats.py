"""Yields, cut reasons, token statistics and human behaviour statistics of data/recon.

Writes results/corpus_stats.json. Run with the frozen-runtime environment
(see reconstruct.py); single process, a few minutes.
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hp_bootstrap as hb  # noqa: E402

RECON = hb.OUT / "data" / "recon"
HOG26 = {"HogRider", "Musketeer", "IceGolem", "IceSpirit", "Skeletons", "Cannon", "Fireball", "Log"}
NO_OP = 2304


def quantiles(values, points=(5, 25, 50, 75, 95)):
    values = np.asarray(values, dtype=np.float64)
    return {f"p{point}": float(np.percentile(values, point)) for point in points} if values.size else {}


def main() -> None:
    hrd = hb.load_new_module("human_replay_demonstrations")
    builder = hb.pilot_builder()
    cost = {}
    for token, name in enumerate(builder.token_names):
        stats = builder.loader.get_card(name) if token > 1 else None
        if stats is not None and getattr(stats, "mana_cost", None) is not None:
            cost[token] = int(stats.mana_cost)
    done = sorted(RECON.glob("shard-*.done.json"))
    perspectives, errors = [], []
    for path in done:
        payload = json.loads(path.read_text())
        perspectives.extend(payload["perspectives"])
        errors.extend(payload["errors"])
    total = len(perspectives)
    counters = collections.Counter()
    token = collections.Counter()
    plays_by_card = collections.Counter()
    for summary in perspectives:
        counters.update(summary["counters"])
        token.update({k: v for k, v in summary["token_stats"].items() if k != "max_entities_in_row"})
        plays_by_card.update(summary["plays_by_card"])
    rows = sum(p["rows"] for p in perspectives)
    supervised = sum(p["supervised_rows"] for p in perspectives)
    plays = sum(p["supervised_plays"] for p in perspectives)
    recorded = sum(p["recorded_own_plays"] for p in perspectives)
    strict_rows = sum(p["rows"] if p["first_projected_row"] is None else p["first_projected_row"] for p in perspectives)
    fraction = [p["cut_tick"] / max(1, min(p["playable_end_tick"], 6001)) for p in perspectives]
    forms = collections.Counter()
    for p in perspectives:
        forms["own_evo_or_hero_slots"] += sum(form != "base" for form in p["own_forms"])
        forms["opponent_evo_or_hero_slots"] += sum(form != "base" for form in p["opponent_forms"])
        forms["perspectives_own_all_base"] += all(form == "base" for form in p["own_forms"])
        forms["perspectives_both_all_base"] += all(form == "base" for form in p["own_forms"] + p["opponent_forms"])
    by_reason = collections.defaultdict(list)
    for p, value in zip(perspectives, fraction):
        by_reason[p["cut_reason"]].append(value)
    result = {
        "source_shards_done": len(done), "perspectives": total, "errors": len(errors),
        "error_examples": errors[:5],
        "matches": len({p["match_id"] for p in perspectives}),
        "rows": rows, "supervised_rows": supervised, "supervised_play_rows": plays,
        "recorded_own_plays": recorded, "play_retention": plays / max(1, recorded),
        "strict_first_masked_tile_rows": strict_rows,
        "validation_perspectives": sum(p["fit_split"] for p in perspectives),
        "validation_rows": sum(p["rows"] for p in perspectives if p["fit_split"]),
        "hog26_perspectives": sum(set(p["own_deck"]) == HOG26 for p in perspectives),
        "side": dict(collections.Counter(p["side"] for p in perspectives)),
        "recorded_result": dict(collections.Counter(str(p["recorded_result"]) for p in perspectives)),
        "rows_by_recorded_result": {str(k): sum(p["rows"] for p in perspectives if p["recorded_result"] == k) for k in (1, 0, -1)},
        "cut_reason": dict(collections.Counter(p["cut_reason"] for p in perspectives).most_common()),
        "cut_fraction_of_match": quantiles(fraction),
        "cut_fraction_by_reason": {reason: quantiles(values, (25, 50, 75)) | {"n": len(values)} for reason, values in by_reason.items()},
        "rows_per_perspective": quantiles([p["rows"] for p in perspectives]),
        "plays_by_card": dict(plays_by_card.most_common()),
        "counters": dict(counters),
        "token_stats": dict(token),
        "max_entities_in_row": max(p["token_stats"]["max_entities_in_row"] for p in perspectives),
        "unknown_fraction_all_entity_tokens": token["entity_unknown"] / max(1, token["entity_tokens"]),
        "unknown_fraction_enemy_entity_tokens": token["enemy_unknown"] / max(1, token["enemy_tokens"]),
        "unknown_fraction_enemy_troop_tokens": token["enemy_troop_unknown"] / max(1, token["enemy_troop_tokens"]),
        "unknown_fraction_opponent_history": token["history_unknown"] / max(1, token["history_tokens"]),
        "unknown_fraction_opponent_seen_cards": token["seen_unknown"] / max(1, token["seen_tokens"]),
        "forms": dict(forms),
        "tower_cards": dict(collections.Counter("/".join(str(t) for t in p["info"]["tower_cards"]) for p in perspectives).most_common(6)),
        "sim_missing_real_princess_kills_at_cut": sum(
            max(0, (real or 0) - sim) for p in perspectives
            for real, sim in zip(p["real_princess_down"], p["sim_princess_down_at_cut"]) if p["cut_reason"] == "recorded_end"),
        "bytes": sum(part.stat().st_size for part in RECON.glob("shard-*-part-*.npz")),
    }
    # Behaviour statistics from the stored rows.
    held = collections.Counter()
    played = collections.Counter()
    elixir_at_play, per_minute = [], []
    totals = collections.Counter()
    gaps = []
    for part in sorted(RECON.glob("shard-*-part-*.npz")):
        shard = hrd.load_human_replay_shard(part)
        compact = shard.compact
        labels = compact["expert_actions"].astype(np.int64)
        valid = compact["expert_action_supervision_valid"]
        hands = compact["hand_ids"][:, :4].astype(np.int64)
        elixir = compact["global_features"][:, 5] * 10.0
        masks = np.unpackbits(compact["mask_table"], axis=1, count=2306).astype(bool)
        playable_table = masks[:, :NO_OP].any(axis=1)
        playable = playable_table[compact["mask_index"]]
        play = valid & (labels < NO_OP)
        totals["rows"] += int(valid.sum())
        totals["wait_rows"] += int((valid & (labels == NO_OP)).sum())
        totals["playable_rows"] += int((valid & playable).sum())
        totals["wait_when_playable"] += int((valid & playable & (labels == NO_OP)).sum())
        totals["full_elixir_rows"] += int((valid & (elixir >= 9.999)).sum())
        slots = labels[play] // 576
        chosen = hands[play, slots]
        elixir_at_play.extend(elixir[play].tolist())
        for row_hand, card in zip(hands[play], chosen):
            for token_id in row_hand:
                if token_id > 1:
                    held[int(token_id)] += 1
            played[int(card)] += 1
        for summary in shard.header["perspectives"]:
            begin, count = summary["row_offset"], summary["rows"]
            n = int(play[begin:begin + count].sum())
            if count >= 240:
                per_minute.append(n / (count * 5 / 20 / 60))
            rows_with_play = np.flatnonzero(play[begin:begin + count])
            gaps.extend(np.diff(rows_with_play).tolist())
    by_cost = collections.defaultdict(lambda: [0, 0])
    for token_id, count in held.items():
        by_cost[cost[token_id]][1] += count
        by_cost[cost[token_id]][0] += played[token_id]
    result["behaviour"] = {
        "wait_fraction": totals["wait_rows"] / max(1, totals["rows"]),
        "playable_fraction": totals["playable_rows"] / max(1, totals["rows"]),
        "wait_when_playable": totals["wait_when_playable"] / max(1, totals["playable_rows"]),
        "rows_at_full_elixir_fraction": totals["full_elixir_rows"] / max(1, totals["rows"]),
        "elixir_at_play": quantiles(elixir_at_play, (25, 50, 75)),
        "plays_per_minute": quantiles(per_minute, (25, 50, 75)) | {"mean": float(np.mean(per_minute)) if per_minute else None},
        "decision_steps_between_plays": quantiles(gaps, (25, 50, 75, 95)),
        "play_when_held_by_cost": {str(c): by_cost[c][0] / max(1, by_cost[c][1]) for c in sorted(by_cost)},
        "play_when_held_by_card": {builder.token_names[t]: played[t] / max(1, held[t]) for t in sorted(held)},
        "card_share": {builder.token_names[t]: played[t] / max(1, sum(played.values())) for t in sorted(played, key=lambda t: -played[t])},
        "mean_play_cost": sum(cost[t] * n for t, n in played.items()) / max(1, sum(played.values())),
        "share_cost_le_2": sum(n for t, n in played.items() if cost[t] <= 2) / max(1, sum(played.values())),
        "share_cost_ge_4": sum(n for t, n in played.items() if cost[t] >= 4) / max(1, sum(played.values())),
    }
    (hb.OUT / "results").mkdir(exist_ok=True)
    (hb.OUT / "results" / "corpus_stats.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in {"error_examples"}}, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
