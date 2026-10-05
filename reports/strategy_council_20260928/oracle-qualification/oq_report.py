"""Aggregate games/ into tables (markdown on stdout, JSON in summary.json).

Usage: python3 oq_report.py [--max-game N] [player ...]
Plain python3 is enough (no clasher imports).
Intervals: Wilson 95% on the win rate; cluster bootstrap (matchup = both seats,
10,000 resamples, percentile) on the match score (win=1, draw=0.5).
"""

from __future__ import annotations

import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

OQ = Path(__file__).resolve().parent
COUNCIL = OQ.parent
DIAG = COUNCIL / "pilot/v7r2-launch/runs/s2903/seed-2903/scripted/diagnostic-evaluation"
STYLES = ("balanced", "pressure", "defense")
ROLES = ("holdout", "hog26")
SCORE = {"win": 1.0, "draw": 0.5, "loss": 0.0}


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def boot(clusters: list[list[float]], reps: int = 10000, seed: int = 20261001):
    """Percentile CI of the mean over games, resampling clusters (matchups)."""
    if not clusters:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(clusters)
    sums = [(sum(c), len(c)) for c in clusters]
    means = []
    for _ in range(reps):
        s = m = 0
        for _ in range(n):
            a, b = sums[rng.randrange(n)]
            s += a
            m += b
        means.append(s / m)
    means.sort()
    return (means[int(0.025 * reps)], means[int(0.975 * reps) - 1])


SCREEN_GAMES = {"balanced": 22, "pressure": 22, "defense": 20}  # 64-game screen
# Round two was cut by wall clock. analysis_caps.json keeps only complete seat pairs:
# keys "<player>|<role>|<opponent>" -> first game index NOT analysed.
_CAPS_PATH = OQ / "analysis_caps.json"
CAPS = json.loads(_CAPS_PATH.read_text()) if _CAPS_PATH.exists() else {}


def cap_for(spec: dict) -> int:
    return int(CAPS.get(f"{spec['player']['name']}|{spec['role']}|{spec['opponent']}", 10**9))


def load_games(max_game: int | None, screen: bool = False):
    games = defaultdict(dict)  # player -> (role, opp, game) -> record
    for path in sorted((OQ / "games").glob("*/*.json")):
        if path.name.endswith(".error.json"):
            continue
        rec = json.loads(path.read_text())
        spec = rec["spec"]
        if max_game is not None and spec["game"] >= max_game:
            continue
        if screen and spec["game"] >= SCREEN_GAMES.get(spec["opponent"], 10**9):
            continue
        if spec["game"] >= cap_for(spec):
            continue
        games[spec["player"]["name"]][(spec["role"], spec["opponent"], spec["seed"], spec["game"])] = rec
    return games


def load_pilot(prefix: str):
    out = {}
    for role in ROLES:
        for style in STYLES:
            path = DIAG / f"{prefix}-{role}-nominal-{style}.games.json"
            if path.exists():
                for rec in json.loads(path.read_text()):
                    out[(role, style, rec["matchup_seed"], rec["candidate_player"])] = rec
    return out


def summarise(records: list[dict]) -> dict:
    n = len(records)
    w = sum(r["outcome"] == "win" for r in records)
    d = sum(r["outcome"] == "draw" for r in records)
    l = n - w - d
    clusters = defaultdict(list)
    for r in records:
        clusters[(r["spec"]["role"], r["spec"]["opponent"], r["matchup_seed"])].append(SCORE[r["outcome"]])
    lo, hi = boot(list(clusters.values()))
    wl, wh = wilson(w, n)
    calls = sum(r.get("planner_calls", 0) for r in records)
    psec = sum(r.get("planner_seconds", 0.0) for r in records)
    return {
        "n": n, "wins": w, "draws": d, "losses": l,
        "score": (w + 0.5 * d) / n if n else float("nan"),
        "score_boot95": [lo, hi],
        "win_rate_wilson95": [wl, wh],
        "crown_diff": sum(r["candidate_crowns"] - r["opponent_crowns"] for r in records) / n if n else float("nan"),
        "placements_per_game": sum(r.get("placements", 0) for r in records) / n if n else float("nan"),
        "planner_calls_per_game": calls / n if n else 0.0,
        "planner_seconds_per_call": psec / calls if calls else 0.0,
        "planner_seconds_per_game": psec / n if n else 0.0,
        "planner_cpu_seconds_per_call": (sum(r.get("planner_cpu_seconds", 0.0) for r in records) / calls) if calls else 0.0,
        "planner_cpu_seconds_per_game": sum(r.get("planner_cpu_seconds", 0.0) for r in records) / n if n else 0.0,
        "cpu_seconds_per_game": sum(r.get("cpu_seconds", 0.0) for r in records) / n if n else 0.0,
        "mean_ticks": sum(r["ticks"] for r in records) / n if n else float("nan"),
        "failed_actions": sum(r.get("failed_actions", 0) for r in records),
        "actions_outside_public_mask": sum(r.get("actions_outside_public_mask", 0) for r in records),
    }


def paired_vs_pilot(records: list[dict], pilot: dict) -> dict | None:
    clusters = defaultdict(list)
    base = []
    for r in records:
        key = (r["spec"]["role"], r["spec"]["opponent"], r["matchup_seed"], r["candidate_player"])
        if key not in pilot:
            continue
        diff = SCORE[r["outcome"]] - SCORE[pilot[key]["outcome"]]
        clusters[key[:3]].append(diff)
        base.append(SCORE[pilot[key]["outcome"]])
    if not base:
        return None
    n = len(base)
    lo, hi = boot(list(clusters.values()))
    return {"n": n, "pilot_score": sum(base) / n, "diff": sum(sum(c) for c in clusters.values()) / n, "diff_boot95": [lo, hi]}


def fmt(s: dict) -> str:
    return (
        f"{s['wins']}-{s['draws']}-{s['losses']} | {s['score']:.3f} | "
        f"[{s['score_boot95'][0]:.3f}, {s['score_boot95'][1]:.3f}] | "
        f"[{s['win_rate_wilson95'][0]:.3f}, {s['win_rate_wilson95'][1]:.3f}] | {s['crown_diff']:+.2f}"
    )


def main() -> None:
    args = sys.argv[1:]
    max_game = None
    if args[:1] == ["--max-game"]:
        max_game = int(args[1])
        args = args[2:]
    screen = False
    if args[:1] == ["--screen"]:
        screen = True
        args = args[1:]
    games = load_games(max_game, screen)
    pilots = {"ckpt-2903-1M": load_pilot("policy_decisions_001000000"), "warm-start-2903": load_pilot("scripted")}
    players = args or sorted(games)
    summary = {}
    for player in players:
        recs = games.get(player, {})
        if not recs:
            continue
        summary[player] = {}
        print(f"\n### {player}\n")
        print("| cell | n | W-D-L | score | score 95% (matchup bootstrap) | win rate 95% (Wilson) | crown diff |")
        print("|---|---|---|---|---|---|---|")
        groups: dict[str, list[dict]] = defaultdict(list)
        for (role, opp, _seed, _game), rec in sorted(recs.items()):
            groups[f"{role}:{opp}"].append(rec)
            if opp in STYLES:
                groups[f"{role}:ALL-SCRIPTS"].append(rec)
        for cell in sorted(groups, key=lambda c: (c.split(":")[0] != "holdout", c.split(":")[1] == "ALL-SCRIPTS", c)):
            s = summarise(groups[cell])
            summary[player][cell] = s
            print(f"| {cell} | {s['n']} | {fmt(s)} |")
        any_s = summarise([r for r in recs.values()])
        summary[player]["_cost"] = {k: any_s[k] for k in ("planner_calls_per_game", "planner_seconds_per_call", "planner_seconds_per_game", "planner_cpu_seconds_per_call", "planner_cpu_seconds_per_game", "cpu_seconds_per_game", "placements_per_game", "mean_ticks", "failed_actions", "actions_outside_public_mask")}
        c = summary[player]["_cost"]
        print(f"\ncost: {c['planner_calls_per_game']:.0f} planner calls/game, {c['planner_seconds_per_call']:.2f} s/call, "
              f"{c['planner_seconds_per_game']:.0f} planner-s/game (cpu {c['planner_cpu_seconds_per_call']:.2f} s/call), {c['cpu_seconds_per_game']:.0f} cpu-s/game; "
              f"{c['placements_per_game']:.0f} placements/game; mean ticks {c['mean_ticks']:.0f}; "
              f"failed actions {c['failed_actions']}, outside public mask {c['actions_outside_public_mask']}")
        for pname, pilot in pilots.items():
            for role in ROLES:
                sel = [r for (ro, opp, _s, _g), r in recs.items() if ro == role and opp in STYLES]
                p = paired_vs_pilot(sel, pilot)
                if p:
                    summary[player][f"paired_vs_{pname}:{role}"] = p
                    print(f"paired vs {pname} on {role} common games (n={p['n']}): pilot score {p['pilot_score']:.3f}, "
                          f"difference {p['diff']:+.3f} [{p['diff_boot95'][0]:+.3f}, {p['diff_boot95'][1]:+.3f}]")
    name = "summary-screen64.json" if screen else ("summary.json" if max_game is None else f"summary-max{max_game}.json")
    (OQ / name).write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
