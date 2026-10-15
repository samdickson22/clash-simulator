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
