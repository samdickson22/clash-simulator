"""Card-scope coverage for the scope-expansion plan (read-only over the human-prior scan).

Reads ../m0/human-prior-scan/{corpus_index.jsonl.gz,supported_cards.json,corpus_tiers.json}
and writes scope_coverage.json. Usage: nice -n 15 python scope_coverage.py

Terms
- actor scope: cards the learner may hold/play.  engine scope: cards the simulator must
  reproduce for the opponent (S117 today; S122 once the five broken cards are fixed).
- both: matches whose two decks are inside the actor scope (the scan's "tier (a)").
- persp: (match, side) perspectives whose own deck is in the actor scope and whose
  opponent deck is in the engine scope; these are the usable labelled decision streams.
- matches_to_resim: distinct matches containing at least one such perspective.
"""
from __future__ import annotations

import collections
import gzip
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCAN = HERE.parent / "m0" / "human-prior-scan"
FIVE = {"vines", "void", "goblin-curse", "elixir-collector", "goblin-drill"}
DIVERSITY8 = ["arrows", "minions", "bats", "tornado", "balloon", "mini-pekka", "poison", "golem"]


def base(slug: str) -> str:
    for suffix in ("-ev1", "-ev2", "-hero"):
        if slug.endswith(suffix):
            return slug[: -len(suffix)]
    return slug


def main() -> None:
    cards = json.loads((SCAN / "supported_cards.json").read_text())["cards"]
    s117 = {c["slug"] for c in cards if c["scalar_s120"]}
    g66 = {c["slug"] for c in cards if c["simple_gym66"]}
    p16 = {c["slug"] for c in cards if c["pilot16"]}
    s122 = s117 | FIVE
    freq = json.loads((SCAN / "corpus_tiers.json").read_text())["card_deck_frequency_all"]
    matches = []
    with gzip.open(SCAN / "corpus_index.jsonl.gz", "rt") as handle:
        for line in handle:
            sides = json.loads(line)["sides"]
            if not sides["team"]["plays"] or not sides["opponent"]["plays"]:
                continue
            decks = [frozenset(base(c) for c in sides[k]["deck"]) for k in ("team", "opponent")]
            plays = [sides[k]["plays"] for k in ("team", "opponent")]
            princess = all(sides[k]["tower"] == "tower-princess" for k in ("team", "opponent"))
            matches.append((decks, plays, princess))

    def stats(scope: set[str], engine: set[str]) -> dict[str, int]:
        out = dict(both=0, both_plays=0, persp=0, persp_plays=0, persp_princess_towers=0,
                   matches_to_resim=0)
        for decks, plays, princess in matches:
            if not (decks[0] <= engine and decks[1] <= engine):
                continue
            inside = [decks[0] <= scope, decks[1] <= scope]
            if all(inside):
                out["both"] += 1
                out["both_plays"] += sum(plays)
            out["matches_to_resim"] += any(inside)
            for i in range(2):
                if inside[i]:
                    out["persp"] += 1
                    out["persp_plays"] += plays[i]
                    out["persp_princess_towers"] += princess
        return out

    # Greedy over own-deck completion (perspectives), seeded with the pilot roster.
    scope, order = set(p16), []
    while len(scope) < 72:
        gain: collections.Counter[str] = collections.Counter()
        for decks, _, _ in matches:
            if not (decks[0] <= s117 and decks[1] <= s117):
                continue
            for deck in decks:
                missing = deck - scope
                if len(missing) == 1:
                    gain[next(iter(missing))] += 1
                elif len(missing) == 2:
                    for card in missing:
                        gain[card] += 0.001
        best = max((c for c in sorted(s117) if c not in scope), key=lambda c: gain[c])
        scope.add(best)
        order.append(best)

    c48 = p16 | set(order[:32])
    c56 = c48 | set(DIVERSITY8)
    scopes = {"P16": p16, "C40": p16 | set(order[:24]), "C48": c48, "C56": c56,
              "G66": g66, "S117": s117, "S122": s122}
    result = {
        "greedy_order_from_p16": order,
        "c56_added_cards_by_deck_frequency": sorted(
            ((c, freq[c]) for c in c56 - p16), key=lambda item: -item[1]),
        "broken_or_approx_deck_frequency": {c: freq.get(c) for c in sorted(
            FIVE | {"heal-spirit", "spirit-empress"})},
        "scopes": {},
    }
    for name, cards_in in scopes.items():
        row = {"cards": len(cards_in), "engine_s122": stats(cards_in, s122)}
        if cards_in <= s117:
            row["engine_s117"] = stats(cards_in, s117)
        result["scopes"][name] = row
    result["c56_list"] = sorted(c56)
    (HERE / "scope_coverage.json").write_text(json.dumps(result, indent=1) + "\n")
    for name, row in result["scopes"].items():
        print(name, row)


if __name__ == "__main__":
    main()
