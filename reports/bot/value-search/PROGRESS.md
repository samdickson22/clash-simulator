# value-search PROGRESS (resumable)

Code: bot/value/ (05 bot/lead worktree; rsync to 03/04/08). Jobs: /mpac/sdicks02/jobs/clasher/bot-value-*/.
Hosts: CPU 03 (main); GPU 04/08 shared with ExIt (≤20 GB). NEVER run on 05.

## Log
- 2026-10-14: DESIGN.md written. Probing rollout_commands leaf equivalence on 03.
- 11:00Z probe (bot/value/probe.py, on 03): `rollout_commands(root, seat, a, [], style, 27, 27, 1, 1, 160, 10, 10, ew, True, False, False)`
  reproduces `rollout_e1` exactly (max |Δphi| 0.0) for plays and WAIT; timed waits 2400–2402 are rejected by it
  (they stay on e1; V variants correct them by the WAIT leaf's residual). `snapshot()` is 1.9 MB / 38 ms parse (too slow);
  `public_view(state, seat)` is 3 KB / 0.1 ms (bodies, own hand tokens, own elixir, tower fractions) -> feature source.
- 11:13Z data gen launched (bot/value/gen.py, K4S-st vs R3a/v1 alternating, BASE 3041844146963296, disjoint from HEADLINE):
  04 `bot-value-gen-127x04` games 0–1999, 8 workers, receipt pid 3159280; 08 `bot-value-gen-127x08` games 2000–3999,
  10 workers, receipt pid 2687115. ~130 roots/game, ~55 CPU s/game. Resumable (rerun same .sh; rm stale receipt; STOP file).
- 11:18Z gen on 03 too: bot-value-gen-127x03 games 4000–5999, 18 workers.
- 11:25Z code: bot/value/{features,fit,model,players,run}.py; `K4SV-<model>[-h<T>][-x<P>][-nost]` registered in
  bot/eval/headline.py make_player (synced to 03/04/08; headline.py was checksum-identical on all hosts before).
  Validity: K4SV-smokelin-x0 (lambda=0) reproduces K4S-st command_sha256 on HEADLINE R3a cases 0–3 (4/4, bot-value-eq on 03).
  Feature+V overhead ~0.3 ms per leaf vs ~4.5 ms rollout. bot.value.run = bot.search.run + diagnostics
  (changed = fraction of decisions where phi alone would pick differently from the same rollouts).
- 11:55Z fit1 on 925 games (03 gen + copies of 04/08 roots in bot-value-data/; out bot-value-fit1/, cache925.npz).
  Held-out AUC: phi 0.800, lin1 0.787, mlp1 0.792 (overfit), mlp3 (no hand, wd .1, drop .3) 0.796, mlp4 (+hand) 0.809.
  Offline = parity with phi. Models copied to /mpac/sdicks02/jobs/clasher/bot-value-models/ on 03/04/08.
- 12:05Z 03 gen STOPped (STOP file; ~470 games). screen1 (bot-value-screen1 on 03, pid 3958286): K4SV-lin1,mlp3,mlp4 vs
  R3a,v1 cases 0–149, 30 workers. screen2 (bot-value-screen2): K4SV-mlp3-h80, lin1-h80, 26 workers.
- 12:20Z SCREEN RESULT (ours, vs K4S-st paired, partial): pure V is much WORSE. lin1 both −0.280 [−0.340,−0.220] (n=300);
  mlp3-h80 −0.433; lin1-h80 R3a −0.568; mlp3 R3a −0.305 (n=82). changed 22–28% of decisions. Play rate unchanged
  (~12.6/min) -> card/placement choice is worse. Mechanism: in phi units V's board weight ~0 and elixir weight negative
  (−0.008/elixir vs phi +0.005): outcome regression on on-policy states can't identify the elixir<->board exchange
  rate that separates candidates. AUC parity offline was not evidence of ranking quality.
- 12:22Z screen3 (bot-value-screen3, pid 4020179): hash check K4SV-phi (6 R3a cases), then K4SV-phi-e50/e200/e400
  (phi elixir_weight tuned by harness outcome = option c done directly) + K4SV-mlp4-x25 vs R3a,v1 cases 0–149, 30 workers.
- 13:08Z screen3 complete. phi-e50 −0.010 [−0.067,+0.047], e200 −0.007 [−0.063,+0.050], e400 −0.187 [−0.247,−0.127];
  mlp4-x25 +0.003 [−0.057,+0.063] (changed 12.8%). K4SV-phi hash = K4S-st 6/6. All gen + screen jobs finished/stopped
  (no bot-value processes left on 03/04/08). RESULTS.md written. DONE (exploration): recommendation = keep K4S-st;
  no V arm qualified for RoyaleSim.
