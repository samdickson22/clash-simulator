# Noise-robust decisions: progress (bot lead worker, exploration)

Design: DESIGN.md. Results: RESULTS.md. Code: bot/noise/ (filter.py, player.py, run.py, report.py, tune.py, env.sh).

## Resume
- **Trees** (bot/ plus reports/explore/x4s only; the runtime comes from clasher-bot-runtime):
  - 03/04/08: `/mpac/sdicks02/repos/clasher-bot-noise`.
  - 03/04: `clasher-bot-noise-abl`, which also holds the LIVE LEAD's uncommitted eval3 perc/empirical. It runs
    the ablation arms only.
  - Git worktree on 05: `/mpac/sdicks02/repos/clasher-bot-noise`, branch bot/noise-robust.
- **Run:** `source bot/noise/env.sh` (r1-total pins, THP off), then `$NR_PY -m bot.noise.run ...`. It is
  resumable: rerun the same command.
- **Jobs** go under `/mpac/sdicks02/jobs/clasher/bot-noise/<wave>`. Each has a `receipt.json` (PGID) and a
  `run.log`.
- **Analyse:** `$NR_PY -m bot.noise.report DIR[,DIR] --ref 'PERC-emp:LIVED-K4L-R-gs-rw-fc' --perfect LIVED-K4L-R-gs-rw-fc`.

## Log
- **13:55Z, start.**
  - Read the ablation (units are the lever for it5s2), perc.py/empirical.py and the K4L root path. The search root
    is `R.root(info.packet)`, and `_WallMulti.root_fn` is the hook.
  - Worktree created off origin/main c95ef57b.
- **14:00–14:20Z, built the pieces.**
  - EntityFilter, the NR/CAP/PERCs/LIVED wrappers, the runner and the offline capture/tuner.
  - **Identity filter:** bit-identical command hash to PERC-emp:LIVE-fast-it5s2.
  - **Bug found and fixed:** PercPlayer restarts the inner player on each resync (several per match). The filter
    now persists within a match.
  - **Capture** (60 game-seats, cases 1000–1029): raw recall .69, phantoms .10/poll. Coasting trades misses for
    ghosts.
- **14:25Z, wave 1 launched.** Arms vs R3a, HEADLINE 0–299, deterministic K4L twin:
  - baseline PERC-emp, reseeded PERCs1, perfect sight;
  - NR-c2i12m0v0 (hold phantoms), NR-c1i0m1v0d0 (coast 1), NR-c2i12m2v5d0 (both), NR-c2i12m2v5d0sr (root only).
  - **Hosts:**
    - 03: w1-r3a, 30 workers, PGID 567772.
    - 04: queued on a 40 lease, w1-abl = K4L ablation xunits/xev/xhud vs R3a, PGID 2954368.
    - 08: queued on a 40 lease, w1-v1 = the same main arms vs v1, PGID 2670099.

- **14:30Z.** 04/08 hold two long ExIt eval groups (~68 procs), so a 40-proc lease never fits under 105.
  Resubmitted with 30.
- **14:35Z, the bot lead freed all of 03** (the daily fresh-bank run ended), up to ~100 procs.
  - The ablation moved to 03.
  - **My mistake:** I stopped 08's w1-v1 after it had started (29 rows) and then restarted it. It is resumable,
    so nothing was lost.
- **Added code:**
  - the `e<ticks>` filter option: event-confirmed births, i.e. a new track near a same-owner play is output at once;
  - `bot/noise/shadow.py` FAN, a regret proxy: shadow filter chains plus a true-sight twin on the same states, with
    regret = truth best score − truth score of the chain's action.
- **Smoke on case 1000 vs R3a:** the base agrees with the true-sight action on 62% of decisions.

- **~15:00Z, fan1 regret proxy** (21 games, 2,287 decisions, 8 filter tags): the filters barely change K4L
  decisions.
  - Best regret −0.0011 vs base 0.0076/decision; agreement with the true-sight action 64% for every tag.
  - fan1 stopped (enough).
- **~15:05Z, bel1, belief error in the K4L root.** Opponent elixir from the noisy event stream is off by a mean
  +1.7–1.9 vs R3a (overestimate: missed spells, recall .30–.47 for Zap/Poison/Arrows/EQ) and −0.3 to −1.5 vs v1
  (spurious events). Mean |error| 1.8–2.5. The noisy belief's opponent hand essentially never equals the true one.
- **15:06–15:35Z, orc1 oracle decomposition** (28 games, 3,183 decisions). Agreement with the true-sight action,
  vs base 61.9%:
  - true units +5.5 pp;
  - true opponent elixir +1.1 pp (n.s.); the elixir correction was dropped;
  - true opponent belief sample +1.9 pp;
  - units + opponent sample together +16.4 pp.
  - Regret moves little for every chain (O:all −20%). The regret proxy under-reads: perfect units are worth +0.11
    in win rate. Agreement is the better proxy.
- **15:29Z, wave-1 interim** vs R3a (K4L twin, n≈113 per arm). The twin gap is −0.216 [−0.306, −0.126].
  - Ablation: xunits **+0.113 [+0.017, +0.217]**, xev +0.035, xhud 0.000.
  - All NR filter arms −0.018…+0.018 (n.s.). Reseeded reference +0.009.
- **15:20Z, bot lead's timing update:** the Mac is 2.8× a fleet core, so an arm fits if its fleet 4-core p99 is
  ≤ ~400 ms. Lever (b) is open.
  - Built `bot/noise/multiroot.py` LIVEMR-K<n>[-D][-U<m>q<pct>]: serial K4L, learned samples j>0 from their own
    root (an independent opponent belief sample and/or recently missed units re-inserted with probability q).
  - Smoke OK.
- **15:35Z, mr1 launched**, a multi-root win-rate screen; orc1 stopped (PGID 707369).

- **16:05Z, w1 vs R3a stopped at n≈176/arm** (PGID 567772); the references suffice.
  - Twin gap −0.189 [−0.269, −0.109].
  - Filters: c1i0m1v0d0 −0.006, c2i12m0v0 −0.006, c2i12m2v5d0 +0.029, …sr +0.023 (all n.s.).
  - Reseeded reference −0.034.
- **16:05Z, w1-abl done** (300 each vs R3a): xunits **+0.107 [+0.022, +0.191]**, xev +0.028, xhud +0.006
  (paired n=178).
  - w2-abl launched: xrecall/xfp/xconf, 18 workers, PGID 928737.
- **16:05Z, mr1 interim** (vs PERC-emp:LIVEMR-K1): K2 −0.038 (n=53), **K2-D +0.080 (n=50)**, K2-U3q50 0.000,
  **K3-D-U3q50 +0.119 (n=42)**. D looks like the active ingredient.
  - mr2 launched: K3-D and K4-D under PERC-emp, plus perfect-sight LIVEMR-K1 and LIVEMR-K3-D, 28 workers,
    PGID 930820.
- **16:07Z, bot/noise/mr_fast.py:** a live pooled multi-root, `LIVE-MRK<n>-D-w<ms>-t4-p4`. The worker accepts per-j
  roots, with no bot/search edits.
  - An equivalence smoke vs the serial twin is queued on 08 (lease 8).

- **16:35Z, live pooled multi-root is bit-identical to the serial twin.** `LIVE-MRK3-D-w5000-t4-p4` and
  `LIVEMR-K3-D` give the same command hash 4a18597e… on case 1500 vs R3a (08).
- **16:36Z, K4L sub-ablation** (n≈78 each, vs R3a): xrecall −0.013, xfp −0.013, xconf −0.013. No single unit
  component helps; only xunits as a whole (+0.107) does.
  - orc2 (41 games, 4,539 decisions), agreement: O:recall +0.8 pp, O:fp +0.1 pp, O:ownu +1.2 pp, O:oppu +2.4 pp,
    O:units +6.5 pp.
  - HP and position residuals are small (HP std .068; position median .09 tiles).
  - **Conclusion:** recall/phantom filtering targets the wrong component. The unit effect is an interaction through
    the translator.
- **16:36Z, multi-root interim** vs PERC-emp:LIVEMR-K1, R3a:
  - K2-D **+0.085 [−0.009, +0.179]** (n=106), K4-D +0.079 (n=63), K3-D-U3q50 +0.063 (n=95), K3-D +0.015 (n=66);
  - K2 −0.009, K2-U3q50 +0.027;
  - perfect sight: K3-D −0.043 [−0.157, +0.071] (n=70).
- **16:37Z, w1 vs v1 (08, n≈138):** c2i12m2v5d0 **+0.073 [0.000, +0.146]**, its sr variant +0.080, c2i12m0v0
  +0.029, c1i0m1v0d0 +0.015, reseeded reference +0.051. The twin gap vs v1 is −0.109.
- **16:37Z, reallocated** (orc2, the old mr2 list and w2-abl stopped, at 244 games):
  - mr2: perfect-sight K1 vs K2-D, plus noisy K4-D vs R3a;
  - mr3 (03, cases 0–149) and mr3-08 (08, cases 150–299): noisy K1 vs K2-D vs v1;
  - mr4: the combination PERC-emp:NR-c2i12m2v5d0:LIVEMR-K2-D vs R3a and v1.

- **16:45Z, committed b1438e52** (code + docs; only my 14 files).
- **16:49Z, PERC-emp interim** vs PERC-emp:LIVEMR-K1, R3a:
  - K2-D **+0.076 [−0.015, +0.168]** (n=131), K4-D +0.088 (n=91), K3-D-U3q50 +0.061, K2-U3q50 +0.030, K2 +0.015;
  - combination NR-c2i12m2v5d0 + K2-D: +0.107 (n=28);
  - perfect sight vs K1: K2-D **−0.011 [−0.098, +0.076]** (n=92), K3-D −0.041 (n=73).
  - vs v1 (n≈20): K2-D +0.053, combination +0.091.
- **16:50Z, switched to the deployed stats PERC-emp-sr1u50** (bot lead).
  - Tree `clasher-bot-noise-v2` on 03/08 = my code + main's bot/live perc/empirical/stats (unmodified).
  - Hash check: PERC-emp is bit-identical, and LIVEMR-K1 == LIVED on case 0.
  - Stopped on 03: mr1, mr3, mr4, f1.
  - Launched:
    - sr1 (PGID 1094409, 54 workers): sr1u50 × {K1, K2-D, NR-c2i12m2v5d0:K2-D} vs R3a and v1, cases 0–299;
    - sr1p (PGID 1094424, 6 workers): perfect-sight K1/K2-D vs v1.

- **17:12Z, early K4L gap under sr1u50** (reported to the bot lead): R3a −0.224 [−0.358, −0.090] (n=67). It does
  not shrink the way it5s2's did.
- **17:39Z, sr1 interim** (n≈150–175):
  - K4L gap R3a **−0.206 [−0.288, −0.124]** (0.820 → 0.606, n=170); v1 −0.134 [−0.239, −0.030] (n=67).
  - K2-D vs K1: R3a +0.013 [−0.080, +0.107], v1 +0.012 [−0.058, +0.087].
  - Filter + K2-D: R3a −0.003, v1 +0.011.
  - Perfect sight K2-D vs K1: R3a +0.017 [−0.033, +0.070] (n=299), v1 −0.079 (n=63).
  - **Reading:** D's PERC-emp signal (+0.076) does not carry over to sr1u50.
  - mr2 stopped.
- **17:40Z, the in-flight entity question** (capture: 29% of polls have a projectile/spell in the true table).
  orc3 (sr1u50, 14 games, 1,730 decisions):
  - O:unitrows (true troop/building rows only) agreement +4.3 pp, regret −28%;
  - O:nonunit (true projectiles/spells/effects only) +1.8 pp, regret ≈0;
  - O:units (both) +7.6 pp, regret −31%.
  - The spell-reconstruction idea was dropped.
- **17:58Z, K4L floor arm** (xunits+xhud+xev, round-1 stats) vs perfect sight: R3a **−0.012 [−0.085, +0.073]**
  (n=82), v1 −0.011 (n=90). It is level, so the translator's structural losses cost K4L nothing.
  - floor stopped.
- **17:59Z, orc4 launched:** O:recall2 (every unmatched true unit added, swarms included) vs O:attrs (matched units
  get true position/hp/body/facing) vs O:unitrows/O:fp, under sr1u50.

## Running (since 17:59Z; 03 at 100 procs)
- **03, sr1** (PGID 1094409, 54 workers): sr1u50 × {K1, K2-D, NR+K2-D} vs R3a and v1.
- **03, sr1p** (PGID 1094424, 6 workers): perfect-sight K1/K2-D vs v1.
- **03, orc3** (PGID 1251970, 12 workers): sr1u50 oracle split, cases 1600+.
- **03, orc4** (PGID 1313904, 24 workers): sr1u50 presence vs attributes oracle, cases 1700+.
- **08, mr3-08** (PGID 3351467): PERC-emp K1/K2-D vs v1, cases 150–299 (secondary).

## Round 2 (worker bot-lead-noise-robust-r2; resumes after the T3 restart)
- **20:37Z, resume.** 03 idle (all r1 jobs dead). orc3 (41 games, 4,817 decisions) + orc4 (25 games, 2,583
  decisions, cut at the fb1 launch) analysed, agreement vs the true-sight action / regret per decision:
  - orc3: O:units **+6.8 pp** (regret −26%), O:unitrows +4.5 pp (−18%), O:nonunit +0.9 pp (−8%).
  - orc4 (base 64.8%): O:unitrows +4.5 pp (−11%), **O:recall2 (presence) +1.7 pp (−9%)**, **O:attrs (attributes)
    +2.1 pp (−5%)**, O:fp −0.1 pp. Neither dominates; recall2 + attrs ≈ 3.8 of unitrows' 4.5 pp. Each ≈2σ at this n.
  - LIVE LEAD pointers checked: the v2 harness tree's bot/live translate/resync/perc/empirical/player are byte-identical
    to origin/main (resync tracker 9090b0d7 and board sanitizer 45658350 included).
- **New tree** 03:`clasher-bot-noise-v3` (= v2 + round-2 bot/noise); git worktree 05:`clasher-bot-noise2`, branch
  bot/noise-robust-r2.
- **New code:** `bot/noise/audit.py` `AUD:<player>` (translator audit: perceived vs true opponent revealed set, wrong
  cards, first time the perceived set is full with a wrong card, board_dropped split true/false card, stream/resync
  counters); shadow.py oracle splits O:pos/O:hp/O:face/O:body (one attribute of matched units from truth),
  O:missown/O:missopp (recall2 per owner), O:phant (unmatched noisy units removed).
- **20:36Z launched on 03:** aud1 (PGID 1823292, 20 workers): AUD:PERC-emp-sr1u50:LIVED-K4L vs R3a/v1, cases 0–99;
  orc5 (PGID 1823306, 60 workers): FAN[O:unitrows|O:missopp|O:missown|O:phant|O:pos|O:hp|O:face|O:body], cases 1800+.

## Round 3 (worker bot-lead-noise-robust-r3; r2 was cut off by a T3 restart before committing)
- **21:01Z, resume.** r2's uncommitted code (audit.py, trfix.py, shadow.py O:pos/hp/face/body/missown/missopp/phant,
  report.py pooled rows) committed as found. smoke-r2 (PERCXb3e2, 2 games): the r2 rule never fired (hashes equal):
  the wrong cards there (Ghost, BarbLog) had board evidence from false-positive units, so they were protected, and
  the locked-out cards were spells.
- **aud1 audit** (AUD:PERC-emp-sr1u50:LIVED-K4L, HEADLINE 0–99, 194 games): the perceived opponent card set holds a
  card the opponent never played in **164/194 games** (R3a 82/94, v1 82/100; 1.2 wrong cards/game), and is full (8)
  with a wrong card in **154/194**, median from tick 1930 (~1:37 into the match). A true card is locked out in
  **124/194** games, mostly spells: Fireball 45, Arrows 14, Royal Delivery 14, Log 13, Goblin Barrel 13, Rocket 9;
  troops Giant 8, Valkyrie 8. Real board units are dropped in 43/194 games (6,274 unit-records). Wrong cards are the
  spurious-event cards (Earthquake 26, Ghost 25, BarbLog 20, Mighty Miner 17, Ice Spirit 17, Arrows 16).
  'ninth_enemy_card_dropped' is 0 everywhere: the 9th card's plays are dropped earlier by the mirror's 8-card check
  in _consistent (counted as cycle_conflict_dropped:1), so the belief never holds the locked-out card.
- **orc5 final** (168 games, 18,683 K4L decisions, sr1u50; agreement with the true-sight action vs base 61.6%):
  O:unitrows **+4.9 pp** [+4.4, +5.5] (regret −14%); its parts: O:pos +1.2, O:missown +1.0, O:missopp +1.0,
  O:hp +0.2, O:body +0.1, O:phant +0.1, O:face +0.1 pp (sum 3.7 of 4.9; the rest is interaction). No single
  attribute dominates.
- **Fix built (harness-side copy, bot/live untouched):** bot/noise/livefix/{translate,resync,revealed}.py are the
  proposed bot/live files (only imports differ; `python -m bot.noise.revfix --diff` prints the exact patch);
  `PERCR<tag>-<arm>:<player>` swaps the patched translator into the deployed PercPlayer (same noise stream).
  - RevealedSet (one object for play acceptance AND the board sanitizer, LIVE LEAD req. 2): members = accepted
    opponent plays + board-admitted cards. A full set evicts a WEAK card W (a unit card the board never confirmed
    within 4 s of any of its plays, ≤2 plays; or a spell with ≤1 play) when a non-member X shows ≥2 plays (≥1 vs a
    contradicted W) or ≥10 records meeting 3-of-4 persistence. Evidence = perceived plays/units only (req. 1; unit
    scores unused). Eviction re-runs the resync translator's acceptance over the perceived plays without W's, plus
    X's rejected ones, and sets `resynced` (req. 3: D1/belief rebuilt).
  - `PERCRoff` (patched code, eviction off) is bit-identical to PERC-emp-sr1u50 (8/8 command hashes, fast tier).
  - `PERCRoracle` (diagnostic): revealed set = the opponent's TRUE revealed cards, all else noisy.
  - bot/noise/test_revealed.py: 9 tests (first-come rule when off, lock-out, eviction + resync consistency, one play
    not enough, well-evidenced never evicted, board/sanitizer share the set, flicker is not evidence, contradicted
    troop first, fair-information invariance with opponent-private truth injected into the records). 9/9 pass on 03.
- **Fast-tier smoke** (cases 0–29 × R3a/v1, 60 paired games; tuned on these, so not evidence): true opponent units
  dropped 2,273 → 117 (oracle 48); evictions 50, of which 40 removed a wrong card; Δscore +0.068 (oracle +0.083).
  Rule history: v1 (r2's b3 / removal only) failed on cycle-inconsistent removals and swarm misreads
  (Skeletons→SkeletonArmy reached 3 records), hence the rebuild, b10 and the 4 s sighting window.
- **21:24Z launched on 03** (tree clasher-bot-noise-v4s, code sha in each job's code.sha256; HEADLINE 0–299 × R3a/v1):
  scr1 (PGID 1966302, 80 workers): K4L twin × {sr1u50 base, PERCRe2b10 fix, PERCRoracle, perfect sight, PERCs1
  reseeded}; scr1f (PGID 1966317, 16 workers): fast tier × {base, fix, oracle, perfect}.

## Round 4 (worker bot-lead-noise-robust-r4; r3 was interrupted externally at 21:55:39Z, no error)
- **22:02Z, resume.** 03 jobs alive (scr1 PGID 1966302 ~1000/3000, scr1f PGID 1966317 ~340/2400, floorchk PGID 2015046
  23/60; base 1455777415631152 = HEADLINE). scr1f runs at ~10 games/min (≈3.4 h), so its upper half (cases 150–299)
  is queued on a 04 lease: tree 04:`clasher-bot-noise-v4s` (rsync of 03's; whole-tree sha256 0da7ef99… equal on both
  hosts; runtime r1/native-total-r1 and it5s2 student hashes equal), job 04:/mpac/sdicks02/jobs/clasher/bot-noise/scr1f-hi04
  (`bot/exit/cpu_job.sh 30`, PGID 1054542, waiting for room). 03's scr1f is stopped once it passes case 150.
- **Interim scr1** (K4L, paired vs AUD:PERC-emp-sr1u50 baseline, n≈83–99 per opponent):
  fix PERCRe2b10 R3a +0.036 [−0.024, +0.096], v1 +0.061 [+0.010, +0.122], pooled +0.050 [+0.006, +0.094] (n=181);
  oracle revealed set pooled +0.083 [+0.017, +0.150]; reseeded baseline PERCs1 pooled +0.000 [−0.082, +0.082];
  perfect sight pooled +0.168 [+0.098, +0.239].
- **22:59Z, floorchk final** (clean channel `-xunits-xev-xhud`, cases 0–14 × R3a/v1): fix vs baseline **30/30 identical
  command hashes**, Δscore 0.000, 0 restarts. The fix is a no-op when perception is clean.
- **Defect found in the r3 patch (fixed):** the LIVE test `test_hand_fix.py::test_perc_emp_game_own_state_is_exact…`
  passes on unpatched main but failed on r3's patched tree (`bot.errors == 1`). Cause: an eviction rebuilt the
  opponent mirror up to the RECORD tick (`max(tick, self.tick)`, and `assign`, i.e. the board path, runs before
  `accept_events`), so any opponent event in that record that was earlier than the record tick (a lagged detection)
  raised `ValueError('public time moved backwards')` in the stream guard. PercPlayer swallows this as a WAIT and loses
  the rest of the record's events, including the evicting play. In a live session the exception would reach the loop.
  Fix (bot/noise/livefix/resync.py `_admit`): rebuild up to the stream guard's time, i.e. the event's floored tick on
  the play path, or `_floor` (the previous record's tick, the floor of every event still to come) on the board path.
  Two regression tests were added (lagged play eviction; a board eviction followed by a lagged event in the same
  record). Both fail on r3's resync.py ('public time moved backwards') and pass on the fix. test_revealed 11/11.
  On the tree patched with the fixed code, the LIVE tests give 52 passed, 2 skipped, 3 deselected. The deselected
  tests are `test_wall_deadline_is_kept`, which also fails on unpatched main at load 100, and two that import
  `labels_v4`, which a bot-only tree does not have and which also fail on main.
  The proposal patch was regenerated with `python -m bot.noise.revfix --diff`.
- **Consequence for the screens:** scr1/scr1f ran r3's code, where about half of the play-triggered evictions also
  lost one poll and the evicting play. The screen gates the fresh bank; the fresh bank runs the FIXED code.
- **Patch equivalence (r3 claim re-checked):** the patch applies cleanly to main's bot/live, and the result is
  byte-identical to r3's patchcheck tree. 03 patchcheck (patched bot/live, plays[1] membership) vs the scr1f harness arm
  (rows membership): 20/20 identical command hashes.
- **23:13Z, screens final** (RESULTS 5a/5c). K4L fix pooled **+0.022 [+0.000, +0.043]** (n=600), oracle +0.032, perfect
  sight +0.143. Fast tier fix +0.015 [−0.007, +0.037], oracle +0.018, perfect sight +0.077. The point estimate is
  > 0, so the fresh bank was pre-registered (RESULTS 6, BASE 4405930208510496, committed 6f85e8df at 23:11Z before any
  game). It was launched at 23:11–23:12Z, all chunks with code = main 6f85e8df (per-job code.sha256 identical):
  - 03 fb2 (PGID 2293689, 80 workers, cases 0–439);
  - 03 fb2-hi03 (PGID 2296905, 18 workers, 520–599);
  - 04 fb2-hi04 (`cpu_job.sh 20`, PGID 1429951, 440–519). The first 04 lease asked for 30, waited with no room, and
    was stopped before any game.
  03 scr1f was stopped (SIGTERM PGID 1966317) after its cases 0–149 completed. 03 is at 100 live python.
- **23:42Z, fresh bank interim (progress only; outcome not inspected):** fb2 897/1760, hi03 191/320, hi04 243/320, 0
  errors. perc_errors = 0 in the fix arm, with evictions occurring (correctness check of the r4 rebuild fix).
