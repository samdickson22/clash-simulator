"""Compact README tables from games/ (plain python3). Uses oq_report helpers.

Usage: python3 oq_tables.py            # all tables
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict

import oq_report as R

ORDER = ["noop", "random96", "greedy1", "default", "legacy", "legacy_pm", "roll_raw", "roll_ctr",
         "roll_pm", "srp_small", "srp", "srp_xm", "ckpt2903"]


def cell(recs):
    if not recs:
        return "-"
    s = R.summarise(recs)
    return f"{s['wins']}-{s['draws']}-{s['losses']} {s['score']:.3f} [{s['score_boot95'][0]:.2f}, {s['score_boot95'][1]:.2f}]"


def strength(games, title, screen_only):
    print(f"\n#### {title}\n")
    print("| player | holdout balanced | holdout pressure | holdout defense | holdout pooled | hog26 balanced | hog26 pressure | hog26 defense | hog26 pooled |")
    print("|---|---|---|---|---|---|---|---|---|")
    for player in ORDER:
        recs = games.get(player)
        if not recs:
            continue
        row = [player]
        for role in R.ROLES:
            pooled = []
            for style in R.STYLES:
                sel = [r for (ro, op, _s, g), r in recs.items() if ro == role and op == style]
                pooled += sel
                row.append(cell(sel))
            row.append(cell(pooled))
        print("| " + " | ".join(row) + " |")


def pilot_rows(games_subset_keys=None):
    out = {}
    for name, prefix in (("warm start 2903 (pilot)", "scripted"), ("seed-2903 1M ckpt (pilot)", "policy_decisions_001000000")):
        pilot = R.load_pilot(prefix)
        out[name] = pilot
    return out


def pilot_table(screen: bool):
    print("\n| pilot policy (public, not privileged) | holdout balanced | holdout pressure | holdout defense | holdout pooled | hog26 balanced | hog26 pressure | hog26 defense | hog26 pooled |")
    print("|---|---|---|---|---|---|---|---|---|")
    import json as _j
    for name, prefix in (("warm start seed 2903", "scripted"), ("seed-2903 1M checkpoint", "policy_decisions_001000000")):
        row = [name]
        for role in R.ROLES:
            pooled = []
            for style in R.STYLES:
                path = R.DIAG / f"{prefix}-{role}-nominal-{style}.games.json"
                recs = _j.loads(path.read_text())
                if screen:
                    recs = [r for r in recs if r["game"] < R.SCREEN_GAMES[style]]
                fake = [{"outcome": r["outcome"], "matchup_seed": r["matchup_seed"], "spec": {"role": role, "opponent": style},
                         "candidate_crowns": r["candidate_crowns"], "opponent_crowns": r["opponent_crowns"], "ticks": r["ticks"]} for r in recs]
                pooled += fake
                row.append(cell(fake))
            row.append(cell(pooled))
        print("| " + " | ".join(row) + " |")


def cost(games):
    print("\n#### Cost per game and per planner call (from the evaluation games; CPU = process_time)\n")
    print("| player | games | decisions/game | planner calls/game | CPU s/call | planner CPU s/game | total CPU s/game | placements/game |")
    print("|---|---|---|---|---|---|---|---|")
    for player in ORDER:
        recs = list(games.get(player, {}).values())
        if not recs:
            continue
        n = len(recs)
        calls = sum(r.get("planner_calls", 0) for r in recs)
        with_cpu = [r for r in recs if "planner_cpu_seconds" in r]
        ccalls = sum(r["planner_calls"] for r in with_cpu)
        cpu_call = (sum(r["planner_cpu_seconds"] for r in with_cpu) / ccalls) if ccalls else None
        wall_call = (sum(r["planner_seconds"] for r in recs) / calls) if calls else None
        per_call = f"{cpu_call:.2f}" if cpu_call is not None else (f"{wall_call:.2f} (wall)" if wall_call else "-")
        pcpu = (cpu_call if cpu_call is not None else (wall_call or 0.0)) * calls / n
        print(f"| {player} | {n} | {sum(r['decisions'] for r in recs)/n:.0f} | {calls/n:.0f} | {per_call} | {pcpu:.0f} | "
              f"{sum(r['cpu_seconds'] for r in recs)/n:.0f} | {sum(r['placements'] for r in recs)/n:.0f} |")


def cards(games):
    print("\n#### Share of placements by card cost class (all games of the player)\n")
    cheap = {"Skeletons", "IceSpirit", "Zap", "Log", "IceGolem", "Goblins"}  # 1-2 elixir
    mid = {"Archers", "Knight", "Cannon"}  # 3
    print("| player | placements | 1-2 elixir | 3 elixir | 4+ elixir | top cards |")
    print("|---|---|---|---|---|---|")
    for player in ORDER:
        recs = games.get(player, {})
        c = Counter()
        for r in recs.values():
            for t in r.get("trace", []):
                if len(t) >= 3:
                    c[t[2]] += 1
        tot = sum(c.values())
        if not tot:
            continue
        a = sum(v for k, v in c.items() if k in cheap) / tot
        b = sum(v for k, v in c.items() if k in mid) / tot
        print(f"| {player} | {tot} | {a:.0%} | {b:.0%} | {1-a-b:.0%} | {', '.join(f'{k} {v}' for k, v in c.most_common(5))} |")


def vs_other(games):
    print("\n#### Other opponents (holdout decks for the player; opponent decks from roles_v2/training.json)\n")
    print("| player | vs seed-2903 1M checkpoint (stochastic) | vs StrategyBot balanced | vs StrategyBot bridge-pressure |")
    print("|---|---|---|---|")
    for player in ORDER:
        recs = games.get(player, {})
        row = [player]
        for opp in ("policy", "sb-balanced", "sb-bridge-pressure"):
            row.append(cell([r for (ro, op, _s, g), r in recs.items() if op == opp]))
        if any(x != "-" for x in row[1:]):
            print("| " + " | ".join(row) + " |")


def vs_policy(games):
    print("\n#### Versus the seed-2903 1M checkpoint (opponent = policy, stochastic; planner on holdout decks, checkpoint on training decks)\n")
    print("| player | n | W-D-L | score | score 95% (matchup bootstrap) | win rate 95% (Wilson) | crown diff |")
    print("|---|---|---|---|---|---|---|")
    for player in ORDER:
        sel = [r for (ro, op, _s, g), r in games.get(player, {}).items() if op == "policy"]
        if sel:
            s = R.summarise(sel)
            print(f"| {player} | {s['n']} | {R.fmt(s)} |")


def main():
    screen = R.load_games(None, True)
    allg = R.load_games(None, False)
    strength(screen, "64-game screen cells (games 0-21 balanced, 0-21 pressure, 0-19 defense per deck role); W-D-L score [95% matchup bootstrap]", True)
    pilot_table(True)
    strength(allg, "All games played (controls: 32 per cell; pilots: 4 per cell)", False)
    pilot_table(False)
    vs_other(allg)
    cost(allg)
    cards(allg)


if __name__ == "__main__":
    main()
