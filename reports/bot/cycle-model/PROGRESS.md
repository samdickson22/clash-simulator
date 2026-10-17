# Opponent cycle model: PROGRESS (resume here)

Owner: cycle-model owner (Opus) under the BOT LEAD. Design: DESIGN.md. Results: RESULTS.md.
Worktree: 05:/mpac/sdicks02/repos/clasher-bot-cycle (branch bot-cycle-model, from origin/main 6ad1c9f2f). Job dir:
/mpac/sdicks02/jobs/clasher/bot-cycle (05, and the same path on 03/04/08 for staged trees + runs).

## Thread IDs (copy verbatim; never assemble)

| who | thread id |
|---|---|
| BOT LEAD | thread:delegated-task:command%3Amcp%3A53609d4a-a2de-484a-834d-8566c6339c9f%3Adelegate-task%3Aclasher-bot-lead-20261014-r1 |
| LIVE translator owner | thread:delegated-task:command%3Amcp%3A99d49b81-f9ec-41a6-bede-03f9b418a3db%3Adelegate-task%3Alive-translator-oov-owner-r1 |
| full-pool owner | thread:delegated-task:command%3Amcp%3Adfd92f6b-12ec-4f9d-b843-9d07e96ff7c2%3Adelegate-task%3Abot-lead-fullpool-prep-r1 |
| live-diag (sizing A/B, noise injector) | thread:delegated-task:command%3Amcp%3Ad5b57bd6-719b-4e85-a080-8b8bfc639a49%3Adelegate-task%3Abot-lead-live-diag-r1 |

## Inputs

- Problem write-up: 05:/mpac/sdicks02/jobs/clasher/live-multibody-20261015/guardfix/CYCLE-RULE.md (read-only).
- Labels for P(real): 05:.../guardfix/cycle-labels/ (MANIFEST.md; all-435-drops-features.json dd554ffa…,
  sample1-labels-with-features.json caf8f75f…). Sample 2 (160, stratified; SAMPLE2-DESIGN.json b36cde76…) is being
  labelled in place at .../realcheck/video/CYCLE-DROPS-SAMPLE2.json; the translator owner will message when it's final.
- The translator owner added `LiveTranslator.drop_features(tick, name, x, y)`. Patch:
  .../guardfix/ship-drop-features/drop_features.patch (256a69ae…), against main 11366f88e. Build the hand-off diff on
  top of it, and call `p_real(self.drop_features(...))` in the `_consistent` failure branch.
- Frozen belief files are identical in e4v3 (05) and live16402b-r3 (03/04/08): stage5 derived_public_state.py 18acd452…,
  s1 belief.py 5e6f07fc….

## Log (UTC)

- 01:55Z start. 02:01Z DESIGN.md. 02:05Z design + ETA sent to the BOT LEAD; acknowledged the translator owner; asked
  live-diag about their injector.
- 02:08Z bot/cyclemodel/belief.py (CycleBelief factory), test_cycle.py: 37 pass.
  - 25 random legal streams: rows, weights, ledger and samples equal the frozen Belief, with and without a deadline.
  - Hidden-spell streams: the frozen belief raises; the model explains every conflict and keeps P(true deck) = 1.
  - Also covered: soft phantom, 9th card, replay determinism, and a deadline conflict matching the unbounded path.
- Hook: bot/fullpool/belief.py planner_belief wraps `base` with bot.cyclemodel.belief.wrap. Unset env = the same class
  object as today.

- 02:09Z player parity launched on 08 (job dir parity-r1.jsonl: tree 7768d0497, off vs soft; parity-base.jsonl: pre-change
  tree 6ad1c9f2f via res_check). Smoke case 0: identical hash, and the soft belief logged 0 conflicts.
- Rebased onto origin/main 566ddfd5b (live-diag's HistoryNoise guard=False).
- bot/cyclemodel/preal.py: v0 strata, plus a logistic `fit` for v1.
- bot/cyclemodel/ab.py: `cyc-hard` / `cyc-soft` view wrapper over `histnoise:raw`, run via
  `python -m bot.cyclemodel.ab` (ours_diag).
- 02:17Z A/B smoke on 08 (absmoke-*): no errors.
  - Case 0 had no conflict, and hard and soft gave identical hashes.
  - Case 1 had 6–10 conflicts from 2 hidden spells plus 1 phantom. Once the D1 mirror is one short, drops cascade.
- CYC-AB1 pre-registered in RESULTS.md (base 1185182611752721). 02:18Z launched (tree 725699ca87e7, cases 0–99,
  vs LIVE-K4CW-r16 and R3a, W 8 each):
  - clean on 03, PGID 3669139;
  - hard on 04, PGID 990286 (env off);
  - soft on 04, PGID 990453 (BOT_CYCLE_MODEL=soft).
  - Outputs: job dir `cycab1/<arm>/games-*.jsonl` on that host. Summarise with `python -m bot.livediag.sim_report`
    plus the noise counts.
- 02:19Z translator hand-off diff ready (05 job dir translator-diff/, README.md; diffs 3b9cc441… on top of
  drop_features, 1fd4a18e… vs main). Not sent yet: waiting on parity.
- 02:19Z offline 80-battle belief replay launched on 08 (r80-v0.json; tree 1500228a7395; bot/cyclemodel/replay80.py).

- 02:24Z **parity PASS**: 20/20 + 20/20 soft == off == pre-change main (RESULTS (c)).
- 02:32Z offline 80-battle replay (r80-v0c.json): 0 errors.
  - 302/434 drops have a feasible real explanation; 132 are phantom-only.
  - Labelled: 26/27 real feasible; 11/13 phantoms rejected by the elixir/cycle bound.
  - Resolver p95 29 ms, max 111 ms (the first conflict at ~100k rows).
- Faster merge: uint64 keys, no double merge.
- Sol review r1 launched (task id: see the delegated tasks of this thread; clientRequestId cycle-model-sol-review-r1).
- Translator diff copied to reports/bot/cycle-model/translator/.

- 02:35Z Sol r1: 7 findings. Fixed #1, #2 (hidden-cost weighting for k ≥ 2: a real bug), #5, #6, #7. #3 is in the
  bot/live diff. #4 is intentional. Tests: 41 pass.
  - The soft A/B arm restarted on fixed tree 579ddf11c52f (04, PGID 1264836); the old one is in cycab1/soft-bug-r0,
    unread.
  - Parity r2: 20/20.
  - Replay r80-v0d: 327 feasible / 107 phantom-only; labelled real 27/27, phantoms 9/13 rejected.
- 02:37Z Sol r2 review launched (clientRequestId cycle-model-sol-review-r2).
- reports/bot/cycle-model/MAC-PACKAGE.md: draft.

- 02:45Z C56-path smoke of the translator diff in the wall-clock LIVE-K4L player (LiveBelief over CycleBelief): 0 errors,
  48 soft events, 3% cutoff defaults (RESULTS).
- 02:50Z Sol r2: 6 edge-case findings, all fixed (zero-weight rows, tolerance in elixir units, k\*=0 merge, stats
  reset in the deadline path, finite config, stable sigmoid). Tests: 42. None changes the default config in practice,
  so CYC-AB1 soft continues on 579ddf11c52f.
- The BOT LEAD relayed Sam's standing rule: play evaluations at max levels (16) on a level-capable engine (RoyaleSim).
  CYC-AB1 (our engine, level 11) finishes as is. The live deck is changing (Sam chooses it).

- 03:12Z P(real) v1 on the final 200 labels: LOO log loss 0.229 (v0 0.514); preal-v1.json on main d4c8eaf24. Replay
  with v1: credited 282 real vs the labelled estimate of 303.
- Translator gate (their thread):
  - On 593beb054: 0 errors; full-pool cutoffs 56 → 52; decisions differ 13–16% vs a 3–5% off-vs-off noise floor.
  - C56 path wired OK. One oddity: s47-m03 cutoffs went 9 → 19, probably the LiveBelief rebuild replaying soft events
    at full prior size. C56 is not live; to look at if C56 ever matters.
  - The v1 gate is queued on d4c8eaf24.
- 03:39Z **CYC-AB1 readout:** soft − hard +0.020 [−0.048, +0.088]; hard − clean −0.010 [−0.081, +0.061]; 0 errors.
  Inconclusive: the pre-registered ship rule is not met, and there is no harm (RESULTS (a)).

## Next

1. When parity is done, fill RESULTS (c) and send the translator owner the diff.
2. Commit to main (temp index on the latest origin/main; secret scan).
3. CYC-AB1 readout, then RESULTS (a).
4. preal v1 after sample 2; rerun replay80 with v1.
5. Mac package spec, checked with the LIVE LEAD.

## Open questions / risks

- Every `info.events` consumer must handle `card?`: s1 Belief, LiveBelief, FullPoolBelief, packet_check (via
  planner_belief, so covered), and lopp's own belief, if any. To audit before the diff ships.
- `amount` holds p_real for `card?`. Check that nothing sums `amount` across event kinds.
