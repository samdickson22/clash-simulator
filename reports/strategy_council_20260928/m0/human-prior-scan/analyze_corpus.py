"""Tier counts and coverage leverage from corpus_index.jsonl.gz.

Run: OMP_NUM_THREADS=1 nice -n 15 .venv/bin/python analyze_corpus.py
"""

from __future__ import annotations

import collections
import gzip
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
from card_map import (APPROX, BODY_ONLY, NO_EFFECT, PILOT16, SLUG_TO_GAMEDATA,  # noqa: E402
                      TOWER_SUBSTITUTE, base_slug)

G66 = set(json.loads((ROOT / "training_decks/simple_gym_supported_v1.json").read_text())["support_profile"]["supported_public_cards"])
P16 = set(PILOT16)
SCOPES = {
    "p16": lambda b: SLUG_TO_GAMEDATA.get(b) in P16,
    "g66": lambda b: SLUG_TO_GAMEDATA.get(b) in G66,
    "s120": lambda b: b in SLUG_TO_GAMEDATA and b not in NO_EFFECT and b not in BODY_ONLY,
}


def greedy(missing_sets, top=20):
    """missing_sets: list of frozensets of unsupported base cards per match (union of both decks)."""
    remaining = [m for m in missing_sets if m]
    added, cum, steps = set(), sum(1 for m in missing_sets if not m), []
    for _ in range(top):
        gain = collections.Counter()
        for m in remaining:
            left = m - added
            if len(left) == 1:
                gain[next(iter(left))] += 1
        if not gain:
            # fall back to the card that most reduces remaining distance
            dist = collections.Counter(c for m in remaining for c in (m - added))
            if not dist:
                break
            card, g = dist.most_common(1)[0][0], 0
        else:
            card, g = gain.most_common(1)[0]
        added.add(card)
        cum += g
        remaining = [m for m in remaining if m - added]
        steps.append({"add": card, "new_tier_a": g, "cumulative_tier_a": cum})
    return steps


def main():
    recs = []
    with gzip.open(HERE / "corpus_index.jsonl.gz", "rt") as f:
        for line in f:
            recs.append(json.loads(line))
    total = len(recs)
    funnel = collections.OrderedDict()
    funnel["matches_in_corpus"] = total
    one_v_one = [r for r in recs if r["sides"]["team"]["n_players"] == 1 and r["sides"]["opponent"]["n_players"] == 1
                 and len(r["sides"]["team"]["deck"]) == 8 and len(r["sides"]["opponent"]["deck"]) == 8]
    funnel["1v1_with_two_8card_decks"] = len(one_v_one)
    both = [r for r in one_v_one if r["sides"]["team"]["plays"] > 0 and r["sides"]["opponent"]["plays"] > 0]
    funnel["both_sides_action_logs"] = len(both)
    clean = [r for r in both if r["unmatched"] == 0 and r["nocoord_plays"] == 0]
    funnel["both_logs_and_all_plays_have_coords_and_no_unmatched_events"] = len(clean)
    funnel["result_decisive"] = sum(r["res"] in ("victory", "defeat") for r in both)

    def bases(side):
        return [base_slug(k)[0] for k in side["deck"]]

    unknown_slugs = collections.Counter(b for r in both for s in ("team", "opponent") for b in bases(r["sides"][s]) if b not in SLUG_TO_GAMEDATA)
    tiers, leverage, marginal = {}, {}, {}
    for scope, ok in SCOPES.items():
        counts = collections.Counter()
        missing_sets = []
        for r in both:
            per_side = []
            union = set()
            for s in ("team", "opponent"):
                miss = [b for b in bases(r["sides"][s]) if not ok(b)]
                per_side.append(len(miss))
                union |= set(miss)
            mx = max(per_side)
            if mx == 0:
                counts["a_all16_supported"] += 1
            if mx <= 1:
                counts["b_le1_unsupported_per_deck"] += 1
            if mx <= 2:
                counts["c_le2_unsupported_per_deck"] += 1
            missing_sets.append(frozenset(union))
        # Also: strictly base forms (no evo/hero) and both level-11 subsets of tier a.
        exact_base = sum(1 for r, m in zip(both, missing_sets) if not m and all(
            r["sides"][s]["forms"]["evo"] == 0 and r["sides"][s]["forms"]["hero"] == 0 for s in ("team", "opponent")))
        lvl11 = sum(1 for r, m in zip(both, missing_sets) if not m and all(set(r["sides"][s]["lv"]) == {11} for s in ("team", "opponent")))
        counts["a_and_no_evo_or_hero_forms"] = exact_base
        counts["a_and_all_level_11"] = lvl11
        counts["a_and_princess_tower_both"] = sum(1 for r, m in zip(both, missing_sets) if not m and all(r["sides"][s]["tower"] == "tower-princess" for s in ("team", "opponent")))
        tiers[scope] = dict(counts)
        single = collections.Counter(next(iter(m)) for m in missing_sets if len(m) == 1)
        marginal[scope] = single.most_common(25)
        leverage[scope] = greedy(missing_sets, top=20)
    # Card frequency (decks containing the base card) among both-log matches.
    freq = collections.Counter(b for r in both for s in ("team", "opponent") for b in set(bases(r["sides"][s])))
    forms = collections.Counter()
    levels = collections.Counter()
    towers = collections.Counter()
    for r in both:
        for s in ("team", "opponent"):
            sd = r["sides"][s]
            for k in sd["deck"]:
                forms[base_slug(k)[1]] += 1
            levels.update(sd["lv"])
            towers[sd["tower"]] += 1
    modes = collections.Counter(f"{r['bt']}/{r['gm']}" for r in both)
    plays = sorted(r["sides"]["team"]["plays"] + r["sides"]["opponent"]["plays"] for r in both)
    out = {
        "funnel": funnel,
        "tiers_by_scope": tiers,
        "marginal_single_card_unlocks": marginal,
        "greedy_cumulative_top20": leverage,
        "unknown_slugs": dict(unknown_slugs),
        "card_deck_frequency_top40": freq.most_common(40),
        "card_deck_frequency_all": dict(freq),
        "deck_slot_forms": dict(forms),
        "deck_slot_levels": dict(sorted(levels.items())),
        "tower_troops": dict(towers),
        "modes_top": modes.most_common(12),
        "plays_per_match_median": plays[len(plays) // 2] if plays else None,
        "scope_definitions": {
            "p16": "the 16 pilot cards (native-calibrated public roster)",
            "g66": "66 cards in training_decks/simple_gym_supported_v1.json (tensor simple-Gym support profile)",
            "s120": "all base cards that pass the scalar smoke test (deploy accepted at L11, defining effect observed); excludes NO_EFFECT and BODY_ONLY",
        },
        "approximations": {"APPROX": APPROX, "NO_EFFECT": NO_EFFECT, "BODY_ONLY": BODY_ONLY, "TOWER_SUBSTITUTE": TOWER_SUBSTITUTE},
    }
    (HERE / "corpus_tiers.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("funnel", "tiers_by_scope", "unknown_slugs", "tower_troops", "deck_slot_forms")}, indent=1))
    for scope in SCOPES:
        print(scope, "marginal", marginal[scope][:12])
        print(scope, "greedy", [(s["add"], s["new_tier_a"], s["cumulative_tier_a"]) for s in leverage[scope]])


if __name__ == "__main__":
    main()
