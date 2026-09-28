"""Summarize finite paired branch outcomes without promoting or selecting a policy."""

import argparse
import hashlib
import itertools
import json
from pathlib import Path


def utility(result, owner):
    if result["failure"] is not None or result["terminal"] is None:
        raise ValueError("Incomplete branch cannot receive a utility")
    terminal = result["terminal"]
    outcome = (
        0 if terminal["winner"] is None else (1 if terminal["winner"] == owner else -1)
    )
    hp_margin = sum(
        e["hp"] * (1 if e["owner"] == owner else -1) for e in terminal["towers"]
    )
    return outcome, hp_margin


def compare(a, b):
    return int(a > b) - int(a < b)


def audit(path):
    protocol = json.loads((path / "protocol.json").read_text())
    complete = json.loads((path / "complete.json").read_text())
    results = json.loads((path / "results.json").read_text())
    assert complete["sources_unchanged"]
    expected = {
        (seed, c["name"], engine)
        for seed in protocol["response_seeds"]
        for c in protocol["candidates"]
        for engine in ("native", "scalar")
    }
    indexed = {(r["response_seed"], r["candidate"], r["engine"]): r for r in results}
    if len(indexed) != len(results) or set(indexed) != expected:
        raise ValueError("Missing or duplicate branch")
    rows, pairs = [], []
    for seed in protocol["response_seeds"]:
        for c in protocol["candidates"]:
            name = c["name"]
            n, s = (indexed[seed, name, engine] for engine in ("native", "scalar"))
            nu, su = utility(n, protocol["owner"]), utility(s, protocol["owner"])
            nc = {
                (e["submitted_tick"], e["owner"]): (e["name"], e["xy"])
                for e in n["commands"]
            }
            sc = {
                (e["submitted_tick"], e["owner"]): (e["name"], e["xy"])
                for e in s["commands"]
            }
            diffs = [
                {"tick": k[0], "owner": k[1], "native": nc.get(k), "scalar": sc.get(k)}
                for k in sorted(nc.keys() | sc.keys())
                if nc.get(k) != sc.get(k)
            ]
            rows.append(
                {
                    "seed": seed,
                    "candidate": name,
                    "native_utility": nu,
                    "scalar_utility": su,
                    "winner_matches": n["terminal"]["winner"]
                    == s["terminal"]["winner"],
                    "terminal_tick_delta": s["terminal"]["tick"]
                    - n["terminal"]["tick"],
                    "command_differences": diffs,
                    "decision_counts": {
                        e: indexed[seed, name, e]["decision_counts"]
                        for e in ("native", "scalar")
                    },
                }
            )
        for a, b in itertools.combinations(
            [c["name"] for c in protocol["candidates"]], 2
        ):
            ranks = {
                engine: compare(
                    utility(indexed[seed, a, engine], protocol["owner"]),
                    utility(indexed[seed, b, engine], protocol["owner"]),
                )
                for engine in ("native", "scalar")
            }
            outcome_ranks = {
                engine: compare(
                    utility(indexed[seed, a, engine], protocol["owner"])[0],
                    utility(indexed[seed, b, engine], protocol["owner"])[0],
                )
                for engine in ("native", "scalar")
            }
            pairs.append(
                {
                    "seed": seed,
                    "a": a,
                    "b": b,
                    **ranks,
                    "outcome_ranks": outcome_ranks,
                    "outcome_order_disagreement": outcome_ranks["native"]
                    != outcome_ranks["scalar"],
                    "hp_only_order_disagreement": outcome_ranks["native"]
                    == outcome_ranks["scalar"]
                    and ranks["native"] != ranks["scalar"],
                    "strict_reversal": ranks["native"] * ranks["scalar"] == -1,
                    "tie_disagreement": (ranks["native"] == 0)
                    != (ranks["scalar"] == 0),
                }
            )
    aggregate_utilities = {}
    for candidate in protocol["candidates"]:
        name = candidate["name"]
        aggregate_utilities[name] = {}
        for engine in ("native", "scalar"):
            values = [
                utility(indexed[seed, name, engine], protocol["owner"])
                for seed in protocol["response_seeds"]
            ]
            aggregate_utilities[name][engine] = tuple(
                sum(value[i] for value in values) / len(values) for i in (0, 1)
            )
    aggregate_pairs = []
    for a, b in itertools.combinations(aggregate_utilities, 2):
        ranks = {
            engine: compare(
                aggregate_utilities[a][engine], aggregate_utilities[b][engine]
            )
            for engine in ("native", "scalar")
        }
        aggregate_pairs.append(
            {
                "a": a,
                "b": b,
                **ranks,
                "strict_reversal": ranks["native"] * ranks["scalar"] == -1,
                "tie_disagreement": (ranks["native"] == 0) != (ranks["scalar"] == 0),
            }
        )
    return {
        "role": "opened development",
        "auditor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "acceptance_passed": False,
        "physical_roots": 1,
        "independent_acceptance_roots": 0,
        "response_seed_count": len(protocol["response_seeds"]),
        "limitations": [
            "Opened root used for repairs",
            "Weak fixed controller",
            "No independent acceptance thresholds or variance estimate",
        ],
        "results_sha256": hashlib.sha256(
            (path / "results.json").read_bytes()
        ).hexdigest(),
        "branches": rows,
        "pairwise_rankings": pairs,
        "response_mean_scope": "Exploratory uniform mean of frozen response seeds; aggregation was not separately preregistered. No population inference.",
        "response_mean_utilities": aggregate_utilities,
        "response_mean_rankings": aggregate_pairs,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capture", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = audit(args.capture)
    with args.output.open("x") as f:
        f.write(json.dumps(result, indent=2) + "\n")
    print(
        "paired branches",
        len(result["branches"]),
        "per-seed strict reversals",
        sum(p["strict_reversal"] for p in result["pairwise_rankings"]),
        "tie disagreements",
        sum(p["tie_disagreement"] for p in result["pairwise_rankings"]),
        "exploratory response-mean strict reversals",
        sum(p["strict_reversal"] for p in result["response_mean_rankings"]),
    )


if __name__ == "__main__":
    main()
