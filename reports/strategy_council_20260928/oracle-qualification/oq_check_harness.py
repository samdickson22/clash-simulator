"""Harness parity check: replay pilot diagnostic games of the seed-2903 1M checkpoint
through oq_lib.play_game(kind=policy) and compare with the pilot's .games.json."""

from __future__ import annotations

import json
import sys

import oq_lib

N = int(sys.argv[1]) if len(sys.argv) > 1 else 4
ctx = oq_lib.Context()
diag = oq_lib.CKPT_2903_1M.parent / "diagnostic-evaluation"
ok = True
for role, style in (("holdout", "balanced"), ("hog26", "pressure")):
    ref = json.loads(
        (diag / f"policy_decisions_001000000-{role}-nominal-{style}.games.json").read_text()
    )
    for game in range(N):
        spec = {
            "role": role,
            "opponent": style,
            "seed": oq_lib.PILOT_CELL_SEEDS[(role, style)],
            "game": game,
            "player": {"name": "ckpt2903", "kind": "policy"},
        }
        out = oq_lib.play_game(ctx, spec)
        r = ref[game]
        same = all(
            out[k] == r[k]
            for k in (
                "outcome",
                "ticks",
                "candidate_crowns",
                "opponent_crowns",
                "candidate_deck",
                "opponent_deck",
                "candidate_tower_hp",
                "opponent_tower_hp",
                "matchup_seed",
                "candidate_player",
            )
        )
        ok &= same
        print(role, style, game, out["outcome"], out["ticks"], "MATCH" if same else f"MISMATCH ref={r['outcome']},{r['ticks']}", f"{out['wall_seconds']:.1f}s", flush=True)
print("HARNESS_PARITY", "PASS" if ok else "FAIL")
