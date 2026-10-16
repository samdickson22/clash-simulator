# live16402 pin set: progress (resumable)

Worker `cards-live16402-opus-r1` for CARD LEAD. Edits: bot/cards/{balance_overlay,test_balance_overlay,build_live16402}.py
(new), bot/players/runtime.py (PIN_SETS['live16402'] + 3-line gamedata pin check), reports/cards/live16402/. No commits.
Job dirs: 05 /mpac/sdicks02/jobs/clasher/cards/live16402/ (gen/ = local overlay run); 08 same path (repo/ = code copy,
rs/ = RoyaleSim derived copies, runtime/live16402-dev is NOT here: it is jobs/clasher/cards/runtime/live16402-dev).

## Restart recipe
1. Code to 08: `bash /mpac/sdicks02/jobs/clasher/cards/live16402/sync08.sh` (05).
2. Assemble (08): see sync08.sh header (build_live16402.py --base runtime/r1-cards1-dev --target runtime/live16402-dev).
3. Gates: jobs/clasher/cards/live16402/gate.sh {nocrash|eval} on 08/04 under cpu_job.sh, setsid.

## Log
- 2026-10-16T00:58:56Z generator + tests done (15 pass; 7 mutations caught). Local overlay output sha a7de3e93 (deterministic).
  Pass 1 (comparer slots) 57 apply + 5 calibration; pass 2 (named projectiles/areas/buffs/characters) 16 + 1.
- 2026-10-16T01:08:20Z live16402-dev assembled on 08 (jobs/clasher/cards/runtime/live16402-dev; gamedata a7de3e93, native
  681b5f2c; copy on 03 jobs/clasher/cards/live16402/runtime/). Effect check (effect.sh): 43/46 changed cards reach the
  engine config; Fireball L11 crown was masked by balance.TOURNAMENT_SPELL_OVERRIDES (172) and Mirror's level12:Fireball
  payload vanished (unreconciled) -> pin key tournament_crown_from_gamedata=('Fireball','Poison') + hook: now 159/174,
  Poison 21/23. GoblinGiant riders not in engine config (no effect), MergeMaiden out of scope.
- Gates launched: 08 totality (cpu_job 4) + eval l16 (cpu_job 12, 12 workers); 04 eval cur = r1-total (cpu_job 16);
  03 matches (cpu_job 8). Outputs: <host>:/mpac/sdicks02/jobs/clasher/cards/live16402/gate/. Resume: headline is
  resumable (rerun the same gate.sh eval command); matches/totality rerun from scratch (move the old gate/ files).
- 2026-10-16T01:26:17Z totality done (08): 4 x 6707 probes, 0 panics, scrub 0 failures. Current-pin arm: 04/03 queues
  saturated, so cancelled (by PGID, before any python) and replaced: 12 HEADLINE cases x R3a,v1 of K4L-R-gs-rw-fc under
  r1-total (08 gate/hl-cur) replay the bot lead's 04:jobs/clasher/bot-lopp2/base/bot-lopp-hl2 K4L-R-gs games with
  identical command_sha256 24/24 -> hl2 cases 0-199 are the current-pin arm (copy: 05 jobs/.../live16402/ref/).
  Matches moved 03 -> 08 (cpu_job 8). Eval l16 running on 08 (12 workers, ~150 s/game).
- 2026-10-16T01:49:15Z eval l16 done (400/400, 0 non-terminal). vs hl2 cases 0-199: R3a 0.810 vs 0.830 (paired -0.020
  [-0.080,+0.045]); v1 0.920 vs 0.950 (paired -0.030 [-0.075,+0.015]); pooled paired -0.025 [-0.0625,+0.0125], 60
  discordant cases (25 l16 better / 35 current better). nonlive done (10 games). matches running (R3a specs left).
  Local copies: 05 jobs/clasher/cards/live16402/ref/ (eval.json, hl-l16/, *.jsonl).
- 2026-10-16T02:09:39Z matches done (08): LIVE 33 + fast 36 games, 0 crashes/panics/errors; RESULTS.md complete. DONE
  pending lead review/commit. Leftovers: 03 jobs/clasher/cards/live16402/runtime/ (unused copy of the dev root; safe to delete).
