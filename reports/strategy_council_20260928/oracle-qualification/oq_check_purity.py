"""Purity check: planning must not perturb the real game. A "shadow" player plans at
every playable decision and then plays no-op; its game must equal the never-play
control (games/noop) on the same spec: same end tick and tower HP."""
import json, sys
import oq_lib

ctx = oq_lib.Context()
players = json.loads((oq_lib.OQ_DIR / "batches.json").read_text())["players"]
ok = True
for name in sys.argv[1:] or ["srp", "roll_pm", "default"]:
    spec = {"role": "holdout", "opponent": "balanced", "seed": oq_lib.PILOT_CELL_SEEDS[("holdout", "balanced")],
            "game": 1, "player": {"name": name + "_shadow", **players[name], "shadow": True}}
    out = oq_lib.play_game(ctx, spec)
    ref = json.loads((oq_lib.OQ_DIR / "games/noop/noop__holdout__balanced__s12009449__g001.json").read_text())
    same = all(out[k] == ref[k] for k in ("ticks", "outcome", "candidate_tower_hp", "opponent_tower_hp", "decisions"))
    ok &= same
    print(name, "planner calls", out["planner_calls"], "ticks", out["ticks"], ref["ticks"], "MATCH" if same else "MISMATCH", flush=True)
print("PURITY", "PASS" if ok else "FAIL")
