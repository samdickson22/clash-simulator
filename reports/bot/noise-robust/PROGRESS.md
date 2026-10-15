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

## Running (since 16:38Z; 03 at 100 procs)
- **03, mr1** (PGID 817335, 25 workers): noisy K1/K2/K2-D/K2-U3q50/K3-D-U3q50 vs R3a, to 300.
- **03, mr2** (PGID 1046183, 36 workers): LIVEMR-K1, LIVEMR-K2-D (perfect sight), PERC-emp:LIVEMR-K4-D vs R3a.
- **03, mr3** (PGID 1047691, 10 workers): noisy K1, K2-D vs v1, cases 0–149.
- **03, mr4** (PGID 1049731, 18 workers): PERC-emp:NR-c2i12m2v5d0:LIVEMR-K2-D vs R3a and v1.
- **03, f1** (PGID 672354, 6 workers): fast-tier filters.
- **08, mr3-08** (PGID 3351467, 30-proc lease): noisy K1, K2-D vs v1, cases 150–299.
