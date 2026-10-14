# Opponent model in K4C-r16 rollouts — progress log (exploration)

Resumable log. Code: bot/search/oppmodel.py (K4O-* arms), bot/search/opp_run.py (runner + diagnostics),
make_player line in bot/eval/headline.py. Jobs on 127x03 under /mpac/sdicks02/jobs/clasher/bot-opp-*/.
Repo copy on 03 is rsynced from 05 (only the files above).

## Banks (recorded before any result)
- FIT bank (weights / style-model fitting; never the HEADLINE bank): BASE **2249738988533344**,
  int.from_bytes(os.urandom(6),'big')<<4, drawn 2026-10-14T18:04:45Z.
- HEADLINE bank: 1455777415631152 (evaluation only).
- Fresh confirmation bank: drawn later, before any confirmation result.

## K4C-r16 baseline games (03)
- ours, HEADLINE, R3a/v1: bot-headline-r16-ours (= bot-cand-ours r16, 600/600 command_sha256 identical)
- RoyaleSim, HEADLINE, R3a/v1/rext-bc: bot-headline-r16-rsim15535

## Log
- 2026-10-14T18:05:52Z code written; next: rsync to 03, equivalence K4O-mean vs K4C-r16 (cases 0-9 x R3a,v1).
- 2026-10-14T18:11:54Z equivalence OK: K4O-mean == K4C-r16 command_sha256 20/20 (bot-opp-eq, HEADLINE 0-9 x R3a,v1). Calibration (bot-opp-cal, fit bank 0-19): scripted styles indistinguishable in play features vs our bot (elixir at issue ~2.9 all 3; v1 7.6, R3a 4.2). Launched arm-A grid on FIT bank: bot-opp-fitA (8 arms x 600 games).
- 2026-10-14T18:27:08Z refactor: reducer takes {spec: weight}; added arm C specs (rollout_commands opp delay/interval) and arm B blend (lo/hi weights by opponent elixir-at-issue). Dropped 3-style Gaussian inference (styles indistinguishable). Grid arithmetic unchanged (same sum order).
- 2026-10-14T19:25:35Z fitA done (0 errors): all flat; mean-changed 1.7-3% (min 7.6%). both vs mean: min -0.030 [-0.063,+0.003] (R3a -0.080), w0.0.100 -0.022, w0.100.0 -0.008, w100.0.0 -0.008 (24.2 vs 41.2 rollouts), w25.25.50 -0.003, w25.50.25 -0.002, w50.25.25 +0.002. Launched bot-opp-fitBC (B blend lo50.25.25-hi100.0.0; C x25bd47,x25di40,x25bi30; fit bank) and bot-opp-hl (HEADLINE: mean[eq recheck vs r16 games],min,w50.25.25,w100.0.0).
- 2026-10-14T20:42:21Z fitBC (fit bank, vs mean): B lo50.25.25-hi100.0.0 +0.045 [+0.012,+0.077] (R3a +0.027, v1 +0.063; weights R3a .59/.21/.21, v1 .93/.03/.03); C x25bd47 +0.017, x25di40 +0.018, x25bi30 -0.007. HEADLINE ours vs K4C-r16 (bot-opp-hl): mean == r16 600/600 sha; min -0.007 [-0.042,+0.028]; w50.25.25 -0.003; w100.0.0 -0.012 (24.1 rollouts/dec). Launched bot-opp-hl2: B + x25bd47 + x25di40 on HEADLINE ours.
- 2026-10-14T21:14:14Z hl2 HEADLINE ours vs K4C-r16: B blend -0.010 [-0.043,+0.027] (fit-bank +0.045 did not replicate); x25bd47 +0.017 [-0.017,+0.052] (R3a +0.043); x25di40 +0.008. No arm >= +0.02 in ours. DECISION (before any RoyaleSim result): x25bd47 replicated +0.017 on 2 independent banks -> run RoyaleSim HEADLINE (R3a,v1,rext-bc) as an informational below-gate check; fresh-bank confirmation only if RoyaleSim pooled >= +0.02.
- 2026-10-14T21:30:09Z RoyaleSim HEADLINE (bot-opp-rsim) x25bd47 vs K4C-r16: pooled -0.008 [-0.034,+0.019] (R3a -0.013, v1 +0.010, rext-bc -0.020). Below rule -> no fresh-bank confirmation. DONE: RESULTS.md written; 12,507 games, 0 errors. No jobs running. Nothing committed.
