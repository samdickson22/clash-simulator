"""Paired comparison of two evaluated checkpoints on identical matchup seeds.

Prints wins, the Newcombe (Wilson-score) 95% interval of the win-rate difference
and an exact two-sided McNemar test on game-by-game paired outcomes.
  python compare.py A B
"""
import json
import math
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from behaviour_stats import ROLES, STYLES, wilson  # noqa: E402


def outcomes(name, role):
    games = []
    for style in STYLES:
        path = OUT / "evaluation" / name / f"{role}-nominal-{style}.games.json"
        games += [(style, game["game"], game["matchup_seed"], game["outcome"] == "win") for game in json.loads(path.read_text())]
    return games


def newcombe(a, n, b, m):
    la, ua = wilson(a, n)
    lb, ub = wilson(b, m)
    pa, pb = a / n, b / m
    d = pa - pb
    return d, d - math.sqrt((pa - la) ** 2 + (ub - pb) ** 2), d + math.sqrt((ua - pa) ** 2 + (pb - lb) ** 2)


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def compare(a, b):
    result = {}
    for role in ROLES + ("both",):
        roles = ROLES if role == "both" else (role,)
        x = [g for r in roles for g in outcomes(a, r)]
        y = [g for r in roles for g in outcomes(b, r)]
        assert [g[:3] for g in x] == [g[:3] for g in y], "games are not paired"
        wa, wb = sum(g[3] for g in x), sum(g[3] for g in y)
        only_a = sum(p[3] and not q[3] for p, q in zip(x, y))
        only_b = sum(q[3] and not p[3] for p, q in zip(x, y))
        d, lo, hi = newcombe(wa, len(x), wb, len(y))
        result[role] = {"a_wins": wa, "b_wins": wb, "games": len(x), "difference": d, "difference_ci95": [lo, hi],
                        "a_only_wins": only_a, "b_only_wins": only_b, "mcnemar_p": mcnemar(only_a, only_b)}
    return result


if __name__ == "__main__":
    print(json.dumps(compare(sys.argv[1], sys.argv[2]), indent=1))
