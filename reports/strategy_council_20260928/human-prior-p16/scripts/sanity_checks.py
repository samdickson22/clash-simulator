"""Sanity checks on reconstructed perspectives before any fitting.

(a) every recorded action is legal under the stored mask, and the stored mask
    equals an uncached PublicActionMaskBuilder rebuild from the stored row;
(b) row/label alignment in the style of tests/test_scripted_demo_wait_rows.py,
    against the source events and against a fresh re-simulation;
(c) how the observation builder treats cards outside the pilot vocabulary.

  ... python sanity_checks.py --perspectives 200
Writes results/sanity_checks.json.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hp_bootstrap as hb  # noqa: E402

RECON = hb.OUT / "data" / "recon"
NO_OP = 2304


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--perspectives", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20261001)
    parser.add_argument("--fold", type=int, default=0, help="which quarter of the sampled perspectives to check")
    parser.add_argument("--folds", type=int, default=1)
    args = parser.parse_args()
    hrd = hb.load_new_module("human_replay_demonstrations")
    from clasher.rl.public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput

    builder = hb.pilot_builder()
    direct_mask = PublicActionMaskBuilder(builder)
    slugs = hb.slug_map()
    index = []
    for path in sorted(RECON.glob("shard-*.done.json")):
        payload = json.loads(path.read_text())
        index.extend((payload["shard"], summary) for summary in payload["perspectives"])
    rng = np.random.default_rng(args.seed)
    chosen = [index[int(i)] for i in sorted(rng.choice(len(index), size=min(args.perspectives, len(index)), replace=False))]
    chosen = chosen[args.fold::args.folds]
    by_shard = collections.defaultdict(list)
    for shard, summary in chosen:
        by_shard[shard].append(summary)

    # (c) instrument the builder's identity path during the re-simulation.
    vocabulary = set(builder._name_to_id)
    identity = collections.Counter()
    examples = collections.defaultdict(collections.Counter)
    original = builder._runtime_entity_token_id

    def traced(entity, namespace):
        token = original(entity, namespace)
        names = [str(value) for value in (
            getattr(getattr(entity, "card_stats", None), "name", None), getattr(entity, "spell_name", None),
            getattr(entity, "source_name", None)) if value]
        name = names[0] if names else ""
        if name in {"Tower", "KingTower"}:
            kind = "tower"
        elif any(candidate in vocabulary for candidate in names):
            kind = "in_vocabulary"
        elif not names:
            kind = "unnamed_effect"
        elif token > 1:
            kind = "outside_vocabulary_aliased_to_known_token"
            examples[name][builder.token_names[token]] += 1
        else:
            kind = "outside_vocabulary_unknown_token"
        identity[(namespace, kind)] += 1
        return token

    builder._runtime_entity_token_id = traced
    report = collections.Counter()
    failures = []
    for shard, summaries in sorted(by_shard.items()):
        records = list(hb.read_payloads(shard))
        parts = {}
        for summary in summaries:
            episode = summary["episode_id"]
            record = records[(episode % 100_000) // 2]
            seat = episode % 2
            if record["tag"] != summary["match_id"]:
                failures.append((episode, "episode id does not address its source match"))
                continue
            part = parts.setdefault(summary["part"], hrd.load_human_replay_shard(RECON / f"shard-{shard:03d}-part-{summary['part']:02d}.npz"))
            stored_summary = next(item for item in part.header["perspectives"] if item["episode_id"] == episode)
            rows = np.arange(stored_summary["row_offset"], stored_summary["row_offset"] + stored_summary["rows"])
            stored = part.arrays(rows)
            labels, valid = stored["expert_actions"], stored["expert_action_supervision_valid"]
            report["perspectives"] += 1
            report["rows"] += len(labels)
            # (a) legality under the stored mask, and stored mask == uncached rebuild.
            legal = stored["action_masks"][np.arange(len(labels)), labels]
            report["supervised_rows"] += int(valid.sum())
            report["illegal_supervised_labels"] += int((valid & ~legal).sum())
            play_rows = np.flatnonzero(valid & (labels < NO_OP))
            report["play_rows"] += len(play_rows)
            check_rows = sorted(set(play_rows.tolist()) | set(range(0, len(labels), 10)))
            for row in check_rows:
                request = PublicActionMaskInput(
                    entity_ids=stored["entity_ids"][row], entity_features=stored["entity_features"][row],
                    entity_mask=stored["entity_mask"][row], hand_ids=stored["hand_ids"][row],
                    global_features=stored["global_features"][row],
                    entity_id_confidence=stored["entity_id_confidence"][row],
                    hand_id_confidence=stored["hand_id_confidence"][row],
                    global_feature_confidence=stored["global_feature_confidence"][row],
                    terminal=bool(stored["terminal_status"][row]), board_rotated=bool(stored["board_rotated"][row]))
                report["mask_rebuild_rows"] += 1
                report["mask_rebuild_mismatches"] += int(not np.array_equal(direct_mask.build(request), stored["action_masks"][row]))
            # (b) alignment against the source events.
            match = hrd.parse_il_replay_record(record, slugs)
            own = [play for play in match.plays if play.player == seat]
            hands = stored["hand_ids"][:, :4]
            ticks = stored["submitted_ticks"]
            for order, row in enumerate(play_rows):
                play = own[order]
                token = builder.token_id(play.card)
                slot, tile = divmod(int(labels[row]), 576)
                tile_x, tile_y = hrd.world_tile(play.x_millitiles, play.y_millitiles)
                if seat == 1:
                    tile_x, tile_y = 17 - tile_x, 31 - tile_y
                distance = float(np.hypot(tile % 18 - tile_x, tile // 18 - tile_y))
                problems = []
                if hands[row][slot] != token:
                    problems.append("labelled slot is not the recorded card")
                if stored["recorded_play_ticks"][row] != play.tick:
                    problems.append("row is not paired with its recorded play")
                if not ticks[row] <= play.tick < ticks[row] + 5:
                    report["plays_labelled_one_step_late"] += 1
                    if not ticks[row] - 5 <= play.tick < ticks[row]:
                        problems.append("label is more than one step from the recorded tick")
                if row + 1 < len(labels) and token in hands[row + 1]:
                    problems.append("played card is still in hand on the next row")
                if abs(distance - float(stored["label_projection_distance"][row])) > 1e-5:
                    problems.append("label tile is not the recorded tile or its declared projection")
                report["plays_projected_one_tile"] += int(distance > 0)
                if distance > 2 ** 0.5 + 1e-6:  # one tile in each axis
                    problems.append("label projected farther than an adjacent tile")
                failures.extend((episode, int(row), problem) for problem in problems)
            for row in np.flatnonzero(valid[:-1] & (labels[:-1] == NO_OP)):
                if any(token and token not in hands[row + 1] for token in hands[row]):
                    failures.append((episode, int(row), "wait row but a card left the hand this step"))
            if not np.array_equal(stored["previous_actions"][1:], labels[:-1]) or stored["previous_actions"][0] != NO_OP:
                failures.append((episode, "previous actions are not the shifted labels"))
            decision_ticks = ticks[:-1] if stored_summary["terminal_context_row"] else ticks
            if np.any(np.diff(decision_ticks) != 5) or ticks[0] != 0:
                failures.append((episode, "rows are not consecutive five-tick steps"))
            if set(np.unique(stored["board_rotated"])) != {seat}:
                failures.append((episode, "learner is not in the canonical seat frame"))
            # Fresh re-simulation: pre-decision engine hands and byte-identical rows.
            observed = []
            game = hrd.reconstruct_perspective(
                match, seat, builder, episode_id=episode,
                row_observer=lambda battle, learner, label: observed.append(
                    [0 if name is None else builder.token_id(name) for name in battle.players[learner].hand[:4]]))
            fresh = game.imitation_arrays() | game.execution
            if game.summary["terminal_context_row"]:
                observed.append(fresh["hand_ids"][-1, :4].tolist())
            if not np.array_equal(np.asarray(observed), hands):
                failures.append((episode, "stored hand is not the pre-decision engine hand"))
            for name, values in fresh.items():
                if not np.array_equal(values, stored[name], equal_nan=values.dtype.kind == "f"):
                    failures.append((episode, f"re-simulation differs in {name}"))
                    report["nondeterministic_fields"] += 1
            print(json.dumps({"episode": episode, "rows": len(labels), "plays": len(play_rows), "failures": len(failures)}), flush=True)
    totals = collections.Counter()
    for (namespace, kind), count in identity.items():
        totals[kind] += count
    outside = totals["outside_vocabulary_aliased_to_known_token"] + totals["outside_vocabulary_unknown_token"]
    for name in list(examples):
        if not name:
            del examples[name]
    result = {
        "checks": dict(report), "failures": failures[:50], "failure_count": len(failures),
        "builder_identity_calls": {f"{namespace}:{kind}": count for (namespace, kind), count in sorted(identity.items())},
        "builder_identity_totals": dict(totals),
        "outside_vocabulary_fraction_aliased_to_known_token": totals["outside_vocabulary_aliased_to_known_token"] / max(1, outside),
        "alias_examples": {name: dict(tokens.most_common(3)) for name, tokens in sorted(examples.items(), key=lambda item: -sum(item[1].values()))[:40]},
    }
    (hb.OUT / "results").mkdir(exist_ok=True)
    (hb.OUT / "results" / (f"sanity_checks-fold{args.fold}.json" if args.folds > 1 else "sanity_checks.json")).write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "builder_identity_calls"}, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
