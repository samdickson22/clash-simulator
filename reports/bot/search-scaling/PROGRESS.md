# Search-compute scaling (exploration) — progress log

Question: does more search compute make K4S stronger, and along which axis?
Code: bot/search/players.py (MultiSearchPlayer, names K4S-m<M>/-w<N>/-st/-h<T>), bot/search/run.py (HEADLINE-v1 games + per-decision cost),
registration in bot/eval/headline.py make_player ('K4S-' prefix after the K4S-b/KU branches). Nothing frozen edited.
Host 127x03 only. Launcher /mpac/sdicks02/jobs/clasher/bot-search.sh (env of bot-headline-r1.sh, nice 10) -> python -m bot.search.run ARGS.
Baseline: K4S-b64 logs /mpac/sdicks02/jobs/clasher/bot-headline-r1/ on 03 (HEADLINE base 1455777415631152, cases 0..299).

## Log (UTC)
- 2026-10-14T04:07Z code written; synced bot/search/ + bot/eval/headline.py to 03 (only those paths; bot/exit/ belongs to another agent).
- 2026-10-14T04:07Z smoke launched: bot-search-smoke (K4S-m1,m4,w48,st,h320 x R3a,v1 x cases 0,1; 20 workers), receipt bot-search-smoke.receipt.json.
  Check: K4S-m1 command_sha256 must equal K4S-b64 baseline on the same (opponent,index).

## Resume
- Rows: /mpac/sdicks02/jobs/clasher/bot-search-*/games-*.jsonl on 03; bot.search.run skips finished (candidate,opponent,index) keys, so relaunching the same command resumes.
- 2026-10-14T04:13Z smoke done, 20/20 games, 0 errors. K4S-m1 command_sha256 == K4S-b64 baseline on 4/4 (opponent,index) -> wrapper exact.
  Cost/decision on 03 (loaded): m1 0.26-0.41 s, m4 1.13-1.42 s (~155-168 rollouts), w48 0.39-0.50 (~62 rollouts), st 0.35-0.40 (~45), h320 0.42-0.59.
  m4 diagnostics: single-root argmax differs from the mean-choice on 1-6% of decisions; SD of chosen score across roots ~0.001 -> determinizations barely matter to the scorer.
- 2026-10-14T04:13Z launched arm A: bot-search-a (K4S-m4 x R3a,v1 x 0..299, 30 workers; rsim headline holds 64 procs on 03).
- 2026-10-14T04:24Z rsim headline finished (slots free). Launched: bot-search-bc (K4S-w48,K4S-st,K4S-h320 x R3a,v1 x 0..299, 58 workers);
  bot-search-m1 (K4S-m1 x R3a,v1 x 0..29, 3 workers: baseline cost on the same host + hash equivalence); bot-search-diag/i0,i3 (diag_roots, 8 roots, 2400 ticks).
  bot-search-a at 98/600.
- 2026-10-14T04:28Z diag_roots done (8 roots, 2400 ticks; case 0 vs R3a, case 3 vs v1): mean distinct opponent (hand,cycle) states among 8 samples = 2.1 / 2.3
  (8 only at tick 90; mostly 1-2 after the first plays: the human-deck prior identifies the catalog deck fast). Median best-vs-2nd mean-score gap 0.0005 / 0.0004;
  median across-root SD 0; across-root SD > gap on 22% / 19% of decisions. -> M>1 has little to average over; expect A ~ null.
- 2026-10-14T05:19Z arms A/B/C done (m4 600/600 after tail; bc 1800/1800; m1 60/60 with command_sha256 == K4S-b64 on 60/60). report: st +0.058 [+0.018,+0.100] pooled;
  w48 +0.003; m4 -0.025; h320 -0.062. Lead asked: RESULTS.md, follow up st (st+w48, RoyaleSim), then full P1 rows if it holds in both engines.
- 2026-10-14T05:19Z added tokens stl (student plays appended last: lose ties) and sr (student plays forced into 3-style refine). Launched on 03:
  bot-search-rsim-st (headline --engine rsim15535, K4S-st x R3a,v1 x 0..299, 40 w); bot-search-rsim-m1 (K4S-m1 rsim 0..9: hash check vs bot-headline-rsim-r1, 2 w);
  bot-search-st2 (bot.search.run K4S-st-w48,K4S-stl,K4S-sr x R3a,v1 x 0..299, 50 w).
- 2026-10-14T06:12Z follow-ups done, 0 errors. ours: sr +0.065 [+0.025,+0.107], stl +0.062 [+0.023,+0.102], st-w48 +0.053 [+0.013,+0.095] (pooled paired vs K4S-b64).
  RoyaleSim 15.535: K4S-st +0.100 [+0.060,+0.142] (R3a +0.107, v1 +0.093); rsim K4S-m1 hash == rsim K4S-b64 20/20. -> st holds in both engines.
- 2026-10-14T06:12Z step 3: launched K4S-st vs scripted-balanced,scripted-pressure x 0..299: ours bot-search-st-p1 (46 w), rsim into bot-search-rsim-st (46 w).
- 2026-10-14T06:26Z P1 rows done (ours 600 + rsim 600, 0 errors). Pool P1: ours K4S-st 0.892 [0.877,0.908] vs b64 0.864 (paired +0.028 [+0.008,+0.049]);
  RoyaleSim K4S-st 0.901 [0.885,0.916] vs b64 0.851 (paired +0.050 [+0.029,+0.071]). RESULTS.md written. Recommendation: K4S-st = new best bot. DONE (no jobs running).
