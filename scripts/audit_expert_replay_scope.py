"""Read-only broad-deck replay audit, preserving form and level identities."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq

from clasher.data import CardDataLoader


def audit(path: Path, expected_sha256: str):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected_sha256:
        raise ValueError("replay shard hash does not match pinned source")
    loader = CardDataLoader()
    lookup = {}
    canonical_lookup = {}
    for name in loader.load_card_definitions():
        stats = loader.get_card(name)
        canonical_lookup[re.sub(r"[^a-z0-9]", "", stats.name.lower())] = stats.name
        for label in (name, stats._raw_entry.get("englishName", "")):
            if label:
                lookup.setdefault(re.sub(r"[^a-z0-9]", "", label.lower()), set()).add(
                    stats.name
                )
    counts, levels, forms, unknown_cards, kinds, event_forms = (
        Counter() for _ in range(6)
    )
    decks = Counter()
    payload_keys = Counter()
    for batch in pq.ParquetFile(path).iter_batches(
        batch_size=64, columns=["payload_json"]
    ):
        for row in batch.to_pylist():
            payload = row["payload_json"]
            for _ in range(3):
                if not isinstance(payload, str):
                    break
                payload = json.loads(payload)
            if not isinstance(payload, dict):
                raise TypeError("unsupported replay payload")
            counts["replays"] += 1
            payload_keys.update(payload.keys())
            match_candidate = True
            for side in ("team", "opponent"):
                players = payload["battle"][side]["players"]
                if len(players) != 1:
                    counts["non_single_player_sides"] += 1
                    match_candidate = False
                    continue
                deck = players[0]["deck"]
                keys = [card["card_key"] for card in deck]
                decks[tuple(sorted(keys))] += 1
                counts["sides"] += 1
                modified = [key for key in keys if re.search(r"-(?:ev\d+|hero)$", key)]
                forms.update(modified)
                supported_names = []
                for card in deck:
                    levels[str(card.get("level"))] += 1
                    label = re.sub(r"[^a-z0-9]", "", card["name"].lower())
                    matches = (
                        {canonical_lookup[label]}
                        if label in canonical_lookup
                        else lookup.get(label, set())
                    )
                    if len(matches) != 1:
                        unknown_cards[card["card_key"]] += 1
                    supported_names.append(len(matches) == 1)
                all_base = not modified
                level11 = all(card.get("level") == 11 for card in deck)
                valid = len(keys) == 8 and len(set(keys)) == 8
                counts["base_only_sides"] += int(all_base)
                counts["all_level11_sides"] += int(level11)
                counts["base_level11_sides"] += int(all_base and level11)
                candidate = valid and all_base and level11 and all(supported_names)
                counts["name_form_level_candidate_sides"] += int(candidate)
                match_candidate &= candidate
            counts["two_sided_name_form_level_candidate_replays"] += int(
                match_candidate
            )
            for event in payload["events"]:
                kinds[str(event.get("kind"))] += 1
                if event.get("kind") == "play_card":
                    event_forms[str(event.get("form_at_play"))] += 1
                if event.get("kind") == "activate_ability":
                    counts["ability_events"] += 1
                    counts["ability_events_with_authoritative_source"] += int(
                        bool(event.get("ability_source_authoritative"))
                    )
    return {
        "status": "read_only_compatibility_diagnostic_not_training_data",
        "source_sha256": digest,
        "counts": dict(counts),
        "levels": dict(levels),
        "modified_card_keys": dict(forms.most_common()),
        "unmapped_or_ambiguous_card_keys": dict(unknown_cards.most_common()),
        "event_kinds": dict(kinds),
        "play_event_forms": dict(event_forms),
        "payload_top_level_keys": dict(payload_keys),
        "distinct_exact_form_rosters": len(decks),
        "top_exact_form_rosters": [
            {"cards": list(cards), "sides": n} for cards, n in decks.most_common(30)
        ],
        "limitations": [
            "Fixed first shard is a convenience sample, not a corpus-wide estimate.",
            "Card names, forms and levels are necessary compatibility checks, not mechanic acceptance.",
            "No form labels were stripped to create training examples.",
            "Actions alone do not supply entity observations; replay reconstruction or aligned video is still required.",
            "No player/date split guarantee can be inferred from anonymized data.",
            "No fitting, calibration, promotion, or gameplay acceptance performed.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shard", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.shard, args.sha256)
    with args.output.open("x") as target:
        json.dump(result, target, indent=2)
        target.write("\n")
    print(json.dumps(result["counts"], indent=2))


if __name__ == "__main__":
    main()
