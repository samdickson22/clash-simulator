# Learned rollout opponent in K4C-r16 — progress log (exploration)

Resumable log. Code (05, rsynced to 03 file by file): bot/search/lopp.py (K4L-* arms + Python-driven batched
rollout), lopp_feat.py (features + numpy forward), lopp_train.py (torch trainer), lopp_record.py (recording
runner), lopp_check.py (exactness/timing), make_player line in bot/eval/headline.py. Jobs on 127x03 under
/mpac/sdicks02/jobs/clasher/bot-lopp-*/; runner bot-lopp-run.sh MODULE ARGS (env as bot-opp-run.sh, plus
CLASHER_LOPP_MODELS=/mpac/sdicks02/jobs/clasher/bot-lopp-models). Use ABSOLUTE --out paths (runner cd's to repo).

## Banks
- Training data: FIT bank BASE 2249738988533344 (previous agent's, never HEADLINE), cases 0-599 x R3a,v1,
  K4C-r16 as our side. Validation = case index % 10 == 9.
- Evaluation: HEADLINE 1455777415631152 cases 0-299, paired vs bot-headline-r16-ours.

## Log
- 2026-10-14T21:41:58Z code written. Recording smoke (bot-lopp-smoke): case 0 R3a/v1 command_sha256 ==
  bot-opp-fitA K4O-mean (recording does not perturb the match); 60/60 R3a labels legal under Rust public_mask.
  Launched bot-lopp-rec (1200 games, 100 workers, receipt bot-lopp-rec.receipt.json) and bot-lopp-check
  (rollout_e1 vs Python loop on 3x30 HEADLINE roots).
- 2026-10-14T21:45Z bot-lopp-check: Python loop == rollout_e1 bit for bit on 6,561 rollouts (90 HEADLINE roots,
  3 styles, all candidates incl. WAIT/timed waits): max |diff| 0.0; cost equal (6.42 vs 6.43 ms/rollout).
  Learned-opponent rollout ~11-12 ms (gate-first: public_mask only built when the gate says play).
- 2026-10-14T22:05Z bot-lopp-rec done: 1200 games, 0 errors, 695,089 free-poll rows (40,792 plays); recorded games
  == bot-opp-fitA K4O-mean command_sha256 600/600 (cases 0-299). Real elixir at play R3a 4.0 (play rate 7.2%/poll),
  v1 ~ (see RESULTS).
- 2026-10-14T22:08Z models v0 (8 epochs, no early stop; kept in bot-lopp-models/v0) overfit (train card/tile NLL
  far below val). R3a model val: gate AUC .88, card top1 .84, tile top1 .43 / within-2 .63. v1 (T=1 sampler):
  gate AUC .63, card .43, tile .10. Retraining with dropout .3 + early stop on val loss (v1 = metrics on the same
  val split -> slightly optimistic).
- 2026-10-14T22:12Z models (bot-lopp-models; dropout .3, early stop): pool ep4, R3a ep5, v1 ep1. Launched bot-lopp-eq
  (K4L-X, K4L-M0, HEADLINE 0-49 x R3a,v1; must == K4C-r16 sha) and bot-lopp-hl1 (K4L-R,L,M50 pool thr).
- 2026-10-14T22:17Z bot-lopp-diag (60 HEADLINE roots vs R3a): in-rollout behaviour (plays/160-tick rollout, elixir at
  play): pool thr 0.60/5.7, pool gs 1.53/5.0, R3a thr 1.50/5.0, R3a gs 2.00/4.3, v1 thr 0.36/7.0, v1 gs 1.26/5.3.
  Real: R3a 7.2%/poll ~2.3 plays per 160 ticks at 4.06; v1 4.5%/poll ~1.45 at 7.85. Threshold gate is too passive
  in rollouts -> killed hl1 (176 games kept in bot-lopp-hl1-thr-partial) and launched bot-lopp-hl2:
  K4L-R-gs, K4L-L-gs, K4L-R-mR3a-gs (HEADLINE 0-299 x R3a,v1, 92 workers). ~10 ms per learned rollout.
- 2026-10-14T22:36Z bot-lopp-eq: K4L-X == K4C-r16 command_sha256 100/100 (HEADLINE 0-49 x R3a,v1), K4L-M0 59/59;
  stopped (purpose served). HEADLINE ours, K4L-R-gs complete (600): vs K4C-r16 paired both +0.045 [+0.012,+0.077]
  (R3a +0.067, v1 +0.023); CPU 0.415 s/dec vs K4L-M0 0.414 (same run/load), 33.2 rollouts/dec. >= +0.02 ->
  RoyaleSim (R3a, v1, rext-bc) vs bot-headline-r16-rsim15535: bot-lopp-rsim-a (cases 0-39, 14 workers, now);
  cases 40-299 -> bot-lopp-rsim-b once hl2 frees the host.
- 2026-10-14T22:36:31Z FRESH BANK drawn before any RoyaleSim result: BASE **2195817639077040** (int.from_bytes(os.urandom(6),'big')<<4).
  Rule (fixed now): if K4L-R-gs RoyaleSim HEADLINE pooled (R3a, v1, rext-bc) >= +0.02 vs K4C-r16, run the fresh bank
  in RoyaleSim 15.535: cases 0-1199 x R3a, v1, rext-bc, both K4L-R-gs and K4C-r16; else stop at RoyaleSim.
- 2026-10-14T22:52Z bot-lopp-hl2 done (1800, 0 errors), HEADLINE ours vs K4C-r16 (paired, both): K4L-R-gs +0.045
  [+0.012,+0.077] (R3a +0.067, v1 +0.023; 0.415 s/dec, 33.2 rollouts); K4L-R-mR3a-gs +0.022 [-0.012,+0.056]
  (R3a +0.055, v1 -0.010; 0.391 s/dec); K4L-L-gs -0.012 [-0.047,+0.025] (R3a -0.023, v1 0.000; 0.426 s/dec,
  23.8 rollouts). Load-matched K4L-M0 (== K4C-r16) 0.412 s/dec, 41.3 rollouts. RoyaleSim slice a (cases 0-39,
  bot-lopp-rsim-a, 0 errors): K4L-R-gs +0.025 pooled (noisy, n=40/opp). Launched bot-lopp-rsim-b (cases 40-299,
  100 workers).
- 2026-10-14T23:04Z RoyaleSim HEADLINE (bot-lopp-rsim-a + -b, 900 games, 0 errors) K4L-R-gs vs K4C-r16
  (bot-headline-r16-rsim15535): pooled +0.028 [+0.000,+0.054] (R3a +0.010, v1 +0.033, rext-bc +0.040) >= +0.02 ->
  rule triggers. Launched bot-lopp-fresh: RoyaleSim 15.535, BASE 2195817639077040, cases 0-1199 x R3a,v1,rext-bc,
  K4L-R-gs and K4C-r16 (7200 games, 100 workers, ~85 min).
- 2026-10-14T23:14Z bot-lopp-diag2 (K4L-R-gs games, HEADLINE cases 0-3, first 60 roots each): pre-S-default choice
  differs from the frozen 3-style mean on the same roots in 67/240 (R3a) and 63/240 (v1) = 27% (K4O arms: 2-9%);
  plays chosen: arm 67 vs base 67 (R3a), 64 vs 73 (v1). Fresh bank 511/7200 at 23:14Z (~54 games/min, ETA ~01:20Z).
- 2026-10-14T23:30Z BOT LEAD 23:22Z: let fresh bank finish, then NOTHING more on 03 (LIVE LEAD exclusive ~3 h);
  further compute -> ask lead (04/08). Wall/decision (hl2/eq, 03 at ~100 procs): K4L-R-gs CPU 0.415 / wall 0.416 s,
  K4L-M0 0.412 / 0.414, K4L-X 0.411 / 0.412. Threading test (bot.search.lopp_threads, 8 roots, 10 keys, 4 threads,
  under the fresh-bank load; values identical across modes): native rollout_e1 68 ms seq -> 24 ms wall threaded
  (pinned native releases the GIL, 2.9x); learned lockstep batch 141 ms seq -> 136 ms wall threaded (CPU 302 ms):
  the Python-driven learned rollout is GIL-bound and does not scale with threads.
- 2026-10-15T00:48Z bot-lopp-fresh done (7200 RoyaleSim games, 0 errors). K4L-R-gs vs K4C-r16 paired, BASE
  2195817639077040, 1200 cases/opp: pooled +0.055 [+0.041,+0.068]; R3a +0.049 [+0.021,+0.076], v1 +0.055
  [+0.034,+0.076], rext-bc +0.060 [+0.037,+0.082]. CONFIRMED. Per BOT LEAD, nothing further launched on 03 (0 procs).
  RESULTS.md final. Nothing committed. Open: uncontended single-thread timing + i10 strength screen need 04/08 room.

## K4L live-tier speed (worker of the BOT LEAD, 2026-10-15; hosts 04/08 only)
Goal: a K4L variant that keeps most of +0.055 and fits 200 ms wall per decision on 4-5 cores. Jobs on 127x04 under
/mpac/sdicks02/jobs/clasher/bot-lfast/ (runner bot-lopp-run.sh copied to 04/08; models copied 03 -> 04/08 under
bot-lopp-models, sha256 equal). New code: bot/search/lopp_time.py (pinned per-decision timing), lopp_fast.py
(t/c/p/w tokens), lopp_fast_check.py (exactness); lopp.batch_rollouts gained an optional deadline (values unchanged).
- 2026-10-15T01:18:37Z Step 1 (time1; 04 cores 0-9, one pinned game per core, 40-slot cpu_job lease, SMT siblings
  <=1% busy over the run, i.e. quiet): 20 HEADLINE games each (cases 0-9 x R3a,v1), single thread, per searched
  decision: K4C-r16 wall p50/p95/p99/mean 273/462/656/253 ms (CPU 253; search 219/399, prep 49/73; 42.4 rollouts);
  K4L-R-gs 242/383/463/222 ms (CPU 222; search 190/325, prep 48/67; 33.4 rollouts). The 03 numbers (0.415 s) were
  ~1.9x inflated by load. lopp_threads (30 roots, 8 keys/root, cores 20-24): native rollout_e1 36.8 ms seq ->
  24.0 ms wall on 4 threads; learned lockstep batch 69.6 ms seq -> 79.3 ms wall on 4 threads (CPU 128 ms): worse.
- Profile (cProfile, lopp_check, 12 roots): learned rollout ~5.3 ms vs native 3.7 ms; ~half is BattleState.step
  (GIL held: the native's 'gil-release' cargo feature is compiled out in 44874fd6), half Python decide (public_view
  JSON + featurize + small numpy calls). The forward is already batched across rollouts (lever c is in place).
- numpy float32 forward rows depend on batch composition (1858/~2000 rows differ in low bits when re-batched), so
  re-chunking cannot be bit-identical to K4L-R-gs by construction. Design: t<N> (threaded native, learned batch
  unchanged: == K4L-R-gs exactly), c<P> (fixed chunks, serial twin), p<P> (same chunks in P forked workers: == c<P>).
- Smoke (case 0 vs R3a): K4L-R-gs-t4, -c4, -t4-p4 all reproduce K4L-R-gs's command_sha256 (c97c01ef...).
  lopp_fast_check (12 roots, 972 scripted + 324 learned rollouts): snapshot round trip, threads, pool == rollout_e1
  bit for bit; pool == c4 bit for bit; chunked == unchunked on all 324 values. Root snapshot is 2.1 MB (config 2.07
  MB = 56-card catalogue): shipping it cost ~39 ms on the GIL + 15 ms parse per worker under load -> workers now get
  the config once and rebuild each root from the ~60 KB dynamic part with only the deck cards (parse 1.1 vs 7.1 ms).
- 2026-10-15T01:38:04Z Contended smokes (04 load ~60, siblings 20-32% busy; NOT representative of quiet cores):
  t4-p4 search p50 118 ms vs t4 160 (native phase 62-75 ms on 4 threads, learned 42 vs 95); K4CW-r16-w200-t4 in the
  same run hit its cutoff on 90% of decisions and fell back to R3a on 35%. Root shipping after the config cut:
  ship 9 ms, worker parse 3 ms (was 39 / 15). Benchmark on 40 dumped roots: learned rollout 10-12 ms at ANY batch
  size (native 5.3 ms) because the opponent trunk streams W1 (888x256 f32, 0.9 MB) per call: a 1-row forward is
  0.038 ms, a 2-row forward 0.26 ms (OpenBLAS small-M gemm). New token rw: one row per forward. Values then do not
  depend on batching, and learned rollouts cost 6.5-8.4 ms (native 4.2) instead of 9.9-12.3 (native 5.3).
  lopp_fast_check --rowwise (50 roots, cases 0,3): scripted 2940/2940 and learned pool == UNCHUNKED serial
  980/980 bit for bit; roots rebuilt with the deck-card-only config: 0 mismatches. So K4L-R-gs-rw is the exact
  serial twin of K4L-R-gs-rw-t4-p4 (any chunking).
- Prep profile (60 decisions): per searched decision R3a's forward runs twice (poll + r16 re-rank, ~8-10 ms each)
  and Resources.root json.dumps the 2 MB config (~12-17 ms) + parses it (7 ms). New token fp (install_fast_prep):
  cached config JSON spliced into the byte-identical payload, and an exact-input memo of R3a's outputs().
  Verify mode (CLASHER_FASTPREP_VERIFY=1, recompute + assert): case 2 vs v1, K4L-R-gs-rw-fp == K4L-R-gs-rw
  command_sha256 (ac5b989b...), 101 json + 101 memo hits, no mismatch.
- 2026-10-15T01:38:04Z Screens launched (bot.search.run, HEADLINE 0-299 x R3a,v1, 600 games each): K4L-R-gs-rw on 04
  (bot-lfast/scr-rw, 40 workers) and K4L-R-gs-rw-i10 on 08 (bot-lfast/scr-rwi10, 36 workers), both via cpu_job
  leases. Baselines copied read-only from 03 to bot-lfast/base/ (bot-lopp-hl2, bot-headline-r16-ours, RoyaleSim dirs).
