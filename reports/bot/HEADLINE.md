# HEADLINE: our best bot vs a fixed opponent pool (exploration, tracked daily)

The single tracked number is **pool score in RoyaleSim (15.535.29 rules)**, with our engine as a second column (DECISION-ENGINE.md). Pool score is: the candidate's mean score (win 1, draw 0.5, loss 0) against each pool
opponent, averaged with equal weight over opponents. It is reported in each engine. Every row is exploration-tier.

## Protocol HEADLINE-v1 (fixed 2026-10-14)

- **Match loop:** `bot/players/ours.py:play_match`, the X4S harness loop.
  - Symmetric 27-tick command lag with one outstanding command.
  - Every seat is polled every 5 ticks from tick 90; search acts on 10-tick multiples.
  - Abilities are off. Level 11. Full 3 + 2 min.
- **Engines:**
  - **ours:** Clasher Python engine, C56. The X4S-pinned runtime is `clasher-bot-runtime/r1`, with native
    44874fd6, v1 d77005d5 and R3a 37509a43.
  - **RoyaleSim:** royalesim 0.1.34 with `client_arms("15.535.29")`, the arm that best matched the native recordings
    (FIDELITY.md). Driven through `bot/players/royalesim_match.py` once that lands.
- **Cases:** `x4s_setup(i, BASE)` for i = 0…299, with `BASE = 1455777415631152`.
  - BASE is a fresh bank, `int.from_bytes(os.urandom(6),'big') << 4`, drawn 2026-10-14.
  - Case i puts the candidate in seat i%2, with X-deck i%5 against X-deck (i//5)%5. Both decks are shuffled by
    `Random(BASE+i)`.
  - The same cases are used against every opponent and in every engine.
- **Pool P1 (fixed):**
  - `v1`: the human-prior imitation policy, T=1 sampling;
  - `R3a`: the root-distilled student with its calibrated gate;
  - `scripted-balanced` and `scripted-pressure`: `PublicScriptedOpponent`, C56.
- **Candidate (the "best bot"):** `K4S-b64`.
  - This is the K4 W-screen8 public search with the R3a student as cutoff default, run with a **deterministic
    64-rollout budget** instead of a wall-clock deadline (`SearchPlayer(mode='budget', budget=64, default='R3a')`).
  - It is hardware-independent and reproducible.
  - A full decision is about 45 rollouts, so b64 is close to the unbounded KU.
- **Statistics:** 95% bootstrap CI over games per opponent. The pool CI resamples games within each opponent.
- **Run:**

  ```
  CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/r1 python -m bot.eval.headline \
      --out DIR --candidate K4S-b64 --opponents v1,R3a,scripted-balanced,scripted-pressure --games 300 --workers 96
  python -m bot.eval.summarize DIR
  ```

## Protocol HEADLINE-v2 (2026-10-14, coordinator request: external opponents)

Everything is as in v1 (same cases, BASE, candidate and match loop), with two changes:
- **Engine:** RoyaleSim only. The external opponents are RoyaleSim-native and act on RoyaleSim state.
- **Pool P2 = P1 ∪ external.** The external members are:
  - RoyaleGym's shipped scripted opponents, from upstream RoyaleGym `royalegym/opponents.py` (MIT), wrapped by
    `bot/players/royalesim_opponents.py`: `rgym-patient` (ready=3), `rgym-push`, `rgym-defend` and
    `rgym-first-affordable`;
  - `rext-*`: any RoyaleLearn/RoyaleImitate reference policies plus a policy trained with RoyaleLearn's own trainer
    on our decks, when available (`reports/bot/external-opponents/`).
- **No ClashAI code or checkpoints** (license unclear).
- **Scores reported:** pool-v2 (all members, equal weight), external-only, and P1, so the v1 number stays continuous.

## Protocol HEADLINE-v3 (2026-10-14): a strong external opponent

Everything is as in v2 (RoyaleSim 15.535, same cases and BASE), but the pool is **P3 = P1 ∪ {rext-bc, rext-bcppo}**:
- **`rext-bc`:** RoyaleImitate behaviour clone (RoyaleLearn's default 32ch×2 net and observation) trained on
  IL_Replay human games.
  - 19,200 matches, 2.89M rows, C56 decks only.
  - **IL_Replay has no stated license. The coordinator ruled it internal evaluation only:** the data and weights live
    only under `/mpac/sdicks02/jobs/clasher/bot-ext2-*` and are never committed or published.
- **`rext-bcppo`:** `rext-bc` plus RoyaleLearn PPO with a KL anchor (24.1M decisions). It is more exploitable than
  the clone.
- The saturated RoyaleGym scripted bots and rext-rlppo are dropped from the headline pool. Their rows above stay for
  the record.
- **Scores reported:** pool-v3, external-only (rext-bc, rext-bcppo) and P1.

## Daily fresh banks (pre-registered before any game)

| drawn (UTC) | BASE | protocol |
|---|---|---|
| 2026-10-15T13:00:21Z | 3459036173349312 | RoyaleSim 15.535; best bot K4L-R-gs vs R3a, v1, rext-bc, cases 0–399 each; paired reference K4C-r16 on the same cases; quoted number = pool score with bootstrap 95% CI |
| 2026-10-16T13:17:50Z | 3877999783388832 | Recovery of failed20261016daily; RoyaleSim15.535, K4L-R-gs + pairedK4C-r16 vs R3a,v1,rext-bc; cases0–399each;04cases0–79/8workers,08cases80–399/32workers, leases9/33, cap105; quoted number=equal-opponent pool bootstrap95%CI; no outcomes yet |
| 2026-10-17T03:23:51Z | 2464432084633360 | EARLY MAX daily HEADLINE, exploration: RoyaleSim 0.1.34 / 16.402 (`rsim16402`), `--levels max` (all cards and towers level 16, both sides); C56 x4s cases 0–299 each vs R3a,v1,rext-bc for K4L-R-gs,K4L-R-gs-res,K4C-r16; separately cases 0–149 vs LIVE-K4CW-r16, never pooled. Host127x03 only; four detached blocks, 11 workers + parent per lease12 (44 workers total), nice15, PYTHONHASHSEED=0, NUMPY_MADVISE_HUGEPAGE=0. Pool bootstrap95%CI, paired res−base and base−reference by opponent and pool; mechanism metrics only if recorded. No games yet.  **SUPERSEDED:** 53 nonconforming strong rows used generic it5s2; excluded, retained in nonconforming-it5s2. Replacement bank below pins documented rl5 v10. |
| 2026-10-17T03:30:02Z | 3313223055714752 | EARLY MAX daily HEADLINE, exploration: RoyaleSim 0.1.34 / 16.402 (`rsim16402`), `--levels max` (all cards and towers level 16, both sides); C56 x4s cases 0–299 each vs R3a,v1,rext-bc for K4L-R-gs,K4L-R-gs-res,K4C-r16; separately cases 0–149 vs LIVE-K4CW-r16, never pooled. Host127x03 only; four detached blocks, 11 workers + parent per lease12 (44 workers total), nice15, PYTHONHASHSEED=0, NUMPY_MADVISE_HUGEPAGE=0. Pool bootstrap95%CI, paired res−base and base−reference by opponent and pool; mechanism metrics only if recorded. Strong fast policy pinned to live-diag rl5 v10: student:/mpac/sdicks02/jobs/clasher/bot-rl03/ckpt/policy-00010.pt@0.5375, SHA256 e188e2aeb9a6828ffbef237aa327e495eb39ca5f8322ae18aa70c63cb81bba19. Corrective fresh bank; no games yet. |

## Tracked numbers

> **Selection-bias caveat (2026-10-15 12:47Z).** Two reseeded copies of K4L-R-gs scored −0.027 and −0.038 against K4L-R-gs's own
> games on HEADLINE cases 0–299 (`reports/bot/learned-opponent/RESULTS.md`, round 2). Bots chosen on this bank are
> therefore lucky there by about 0.03, so absolute HEADLINE rows for selected bots are optimistic by roughly that much.
> Claims of a new best bot rest only on fresh-bank paired deltas.

| date (UTC) | engine | candidate | pool score [95% CI] | vs v1 | vs R3a | vs scripted-balanced | vs scripted-pressure | games | notes |
|---|---|---|---|---|---|---|---|---:|---|
| 2026-10-14 03:50 | ours (Python C56) | K4S-b64 | **0.864 [0.847, 0.882]** | 0.830 [0.787, 0.870] | 0.633 [0.580, 0.687] | 0.997 [0.990, 1.000] | 0.996 [0.990, 1.000] | 1200 | first run, bot-headline-r1 on 03. Scripted opponents are saturated, so the R3a and v1 columns carry the signal. |
| 2026-10-14 04:35 | **RoyaleSim 0.1.34, 15.535.29 rules (primary from now on)** | K4S-b64 | **0.851 [0.833, 0.869]** | 0.797 [0.750, 0.840] | 0.617 [0.563, 0.673] | 0.993 [0.983, 1.000] | 0.997 [0.990, 1.000] | 1200 | bot-headline-rsim-r1 on 03, same 1200 cases. Paired RoyaleSim − ours: vs v1 −0.033 [−0.093, +0.023], vs R3a −0.017 [−0.077, +0.047]. |
| 2026-10-14 05:00 | RoyaleSim 15.535, **HEADLINE-v2** | K4S-b64 | pool-v2 0.923 [0.913, 0.932]; external-only 0.994 [0.989, 0.998]; P1 0.851 | 0.797 | 0.617 | 0.993 | 0.997 | 2400 | External opponents: rgym-patient 0.983, rgym-push 1.000, rgym-defend 0.997, rgym-first-affordable 0.997, all **saturated**. The trained external policy (rext-rlppo) is pending. Until then **read P1 and the per-opponent v1/R3a numbers**, not pool-v2. |
| 2026-10-14 06:26 | ours (Python C56) | **K4S-st** (new best bot) | **0.892 [0.877, 0.908]** | 0.860 [0.820, 0.900] | 0.720 [0.670, 0.770] | 0.997 | 0.993 | 1200 | R3a's top-8 plays added to the search's candidates (bot/search). Paired pool vs K4S-b64: +0.028 [+0.008, +0.049]. |
| 2026-10-14 06:26 | **RoyaleSim 15.535 (primary)** | **K4S-st** (new best bot) | **0.901 [0.885, 0.916]** | 0.890 [0.853, 0.923] | 0.723 [0.670, 0.773] | 0.997 | 0.993 | 1200 | Paired pool vs K4S-b64: **+0.050 [+0.029, +0.071]**. Same cases. See search-scaling/RESULTS.md. |
| 2026-10-14 08:05 | RoyaleSim 15.535, HEADLINE-v2 | K4S-st | pool-v2 0.947; external-only 0.994 [0.989, 0.998]; P1 0.901 | 0.890 | 0.723 | 0.997 | 0.993 | 2400 | External opponents: rgym-defend 1.000, rgym-first-affordable 1.000, rgym-patient 0.980, rgym-push 0.997 (saturated). |
| 2026-10-14 08:05 | RoyaleSim 15.535, **fresh-bank confirmation** (BASE 594368345275696, not the HEADLINE bank) | K4S-st vs K4S-b64 | R3a+v1 pool: st 0.798 [0.765, 0.828] vs b64 0.718 [0.682, 0.752] | st 0.857 / b64 0.803 | st 0.740 / b64 0.633 | — | — | 1200 | Paired st − b64: vs R3a **+0.107 [+0.047, +0.167]**, vs v1 +0.053 [+0.000, +0.107]. The gain is not a selection artefact of the HEADLINE bank. |
| 2026-10-14 09:50 | RoyaleSim 15.535, HEADLINE-v2 (rext) | K4S-st / K4S-b64 | vs RoyaleLearn-trained policies: st 1.000, b64 0.997 | — | — | — | — | 1200 | rext-rlppo (48.6M PPO steps from scratch, RoyaleLearn's own trainer, our 5 decks) and rext-rlppo-r5: K4S-st 600-0-0, K4S-b64 598-0-2. Saturated, so these opponents are weak. A BC-initialised external opponent (RoyaleImitate on IL_Replay, internal evaluation only) is in progress. |
| 2026-10-14 10:20 | RoyaleSim 15.535 (primary) | K4S-st@student:D (ExIt student D, it2, thr 0.5375, as proposer and default) | 0.897 [0.881, 0.913] | 0.870 | 0.727 | 0.997 | 0.997 | 1200 | Paired vs K4S-st on the same cases: R3a +0.003 [−0.053, +0.060], v1 −0.020 [−0.067, +0.027]. **Null.** K4S-st stays the best bot. |
| 2026-10-14 10:20 | ours | K4S-st@student:D | 0.906 [0.890, 0.921] | 0.907 | 0.730 | 0.993 | 0.993 | 1200 | Paired vs K4S-st: R3a +0.010 [−0.050, +0.067], v1 +0.047 [−0.003, +0.097]. Not significant. |
| 2026-10-14 11:05 | RoyaleSim 15.535 (primary) | student D alone (ExIt it2; one network forward per decision; deployable tier) | P1 0.820 (mean of 4) | 0.807 [0.760, 0.850] | 0.587 [0.530, 0.640] | 0.937 | 0.950 | 1500 | Head-to-head vs K4S-st **0.313 [0.260, 0.367]**: the best bot beats D 69%. |
| 2026-10-14 11:05 | ours | student D alone | P1 0.839 (mean of 4) | 0.827 [0.780, 0.870] | 0.627 [0.570, 0.680] | 0.937 | 0.963 | 1500 | vs K4S-st 0.307 [0.257, 0.360]. |
| 2026-10-14 13:00 | **RoyaleSim 15.535 (primary)**, DAILY | K4S-st (best bot, unchanged; runtime r1) | **0.901 [0.885, 0.917]** | 0.890 | 0.723 | 0.997 | 0.993 | 1200 | Daily re-confirmation. The candidate and code are unchanged since 06:26, so the existing games were re-summarised rather than re-run. |
| 2026-10-14 13:00 | ours, DAILY | K4S-st (unchanged) | 0.892 [0.876, 0.909] | 0.860 | 0.720 | 0.997 | 0.993 | 1200 | Daily re-confirmation; same games as 06:26. The engine merge doesn't affect bots, which stay on frozen runtime r1. |
| 2026-10-14 13:40 | RoyaleSim 15.535, **HEADLINE-v3** | K4S-st (best bot) | **pool-v3 0.895** (mean of 6); external-only 0.883; P1 0.901 | 0.890 | 0.723 | 0.997 | 0.993 | 2400 | vs **rext-bc 0.833 [0.790, 0.877]**, vs rext-bcppo 0.933 [0.903, 0.960]. For reference, v1 scores 0.583 vs rext-bc and 0.480 vs rext-bcppo. Source: external-opponents/NOTES-2.md. |
| 2026-10-14 17:59 | RoyaleSim 15.535, **fresh-bank confirmation** (BASE 4108986455895680) | **K4C-r16** vs K4S-st | R3a+v1+rext-bc pool: r16 0.842 [0.830, 0.853] vs st 0.820 [0.808, 0.833] | r16 0.897 / st 0.863 | r16 0.749 / st 0.728 | — | — | 7200 | 1200 cases per opponent. Paired r16 − st, pooled: **+0.021 [+0.007, +0.036]**; vs v1 +0.033 [+0.011, +0.057], vs R3a +0.022 [−0.007, +0.051], vs rext-bc +0.009 [−0.014, +0.033]. **K4C-r16 is the new best bot** (R3a top-16 proposals; ~12% more rollouts). |
| 2026-10-14 17:59 | **RoyaleSim 15.535 (primary), v1 + v3** | **K4C-r16 (best bot)** | **P1 0.921 [0.907, 0.935]**; pool-v3 0.924 [0.912, 0.936]; external-only 0.930 | 0.900 | 0.797 | 0.993 | 0.993 | 1800 | vs rext-bc 0.897, vs rext-bcppo 0.963. This is the HEADLINE bank, where r16 was selected among four arms, so its delta vs K4S-st here is inflated (R3a +0.073). The trustworthy delta is the fresh-bank +0.021. |
| 2026-10-14 17:59 | ours | K4C-r16 | P1 0.917 [0.902, 0.931] | 0.917 | 0.753 | 0.997 | 1.000 | 1200 | Same caveat. |
| 2026-10-15 00:50 | RoyaleSim 15.535, **fresh-bank confirmation** (BASE 2195817639077040) | **K4L-R-gs** vs K4C-r16 | R3a+v1+rext-bc pool: K4L 0.885 [0.875, 0.895] vs r16 0.831 [0.818, 0.843] | K4L 0.935 / r16 0.880 | K4L 0.796 / r16 0.748 | — | — | 7200 | 1200 cases per opponent, 0 errors. Paired K4L − r16, pooled: **+0.055 [+0.040, +0.069]**; vs v1 +0.055 [+0.034, +0.077], vs R3a +0.049 [+0.021, +0.077], vs rext-bc +0.060 [+0.039, +0.084]. Equal CPU per decision (0.415 vs 0.412 s). **K4L-R-gs is the new best bot** (K4C-r16 whose rollouts score (balanced + learned opponent)/2; `reports/bot/learned-opponent/`). Turn-based tiers only: its Python rollouts are serial and don't fit the 200 ms live deadline yet. HEADLINE-bank deltas: ours +0.045, RoyaleSim +0.028. |
| 2026-10-15 04:19 | **RoyaleSim 15.535 (primary), v1 + v3** | **K4L-R-gs (best bot)** | **P1 0.931 [0.917, 0.945]**; pool-v3 0.937 [0.925, 0.948]; external-only 0.950 [0.932, 0.967] | 0.933 | 0.807 | 0.993 | 0.990 | 1800 | vs rext-bc 0.937, vs rext-bcppo 0.963; 0 errors. Against the K4C-r16 rows above: P1 +0.010, v3 +0.013, rext-bc +0.040. These are unpaired HEADLINE-bank numbers; the trustworthy delta is the fresh-bank +0.055. |
| 2026-10-15 04:19 | ours | K4L-R-gs | P1 0.935 [0.921, 0.948] | 0.940 | 0.820 | 0.987 | 0.993 | 1200 | 0 errors. K4C-r16 had P1 0.917 here. |
| 2026-10-15 06:42 | RoyaleSim 15.535, **fresh bank 2** (BASE 203119344380352) + 4-core wall | **LIVE-K4L-R-gs-rw-fc-w200-t4-p4** (live variant of the best bot) | fresh bank 2, paired vs K4C-r16: fp +0.053 [+0.039, +0.067], i10 +0.057 [+0.043, +0.071] (3600 games each, 0 errors, recomputed by the lead) | — | — | — | — | 10800 | Real 200 ms wall deadline on 4 pinned cores, paired vs K4CW-r16-w200-t4: **+0.058 [+0.020, +0.095]**; at 150 ms +0.160. 4-core ms per decision p50/p95: K4L 79/126 vs K4CW 138/192. Same moves as K4L-R-gs when the search completes. `reports/bot/learned-opponent/RESULTS.md`. |
| 2026-10-15 14:35 | **RoyaleSim 15.535, daily fresh bank** (BASE 3459036173349312, pre-registered 7c8d8b16) | **K4L-R-gs (best bot) — quoted number** | **pool R3a+v1+rext-bc 0.880 [0.863, 0.898]**; K4C-r16 0.854 [0.834, 0.873] | 0.917 / 0.897 | 0.797 / 0.755 | — | — | 2400 | Cases 0–399 per opponent, 0 errors. vs rext-bc 0.925 / 0.910. Paired K4L − K4C-r16: pooled **+0.026 [+0.003, +0.049]**; R3a +0.043 [−0.007, +0.092], v1 +0.020 [−0.015, +0.055], rext-bc +0.015 [−0.020, +0.052]. Unbiased: no bot was selected on this bank. |
| 2026-10-15 14:35 | HEADLINE bank (selection-biased), RoyaleSim v1 + v3 and ours v1 | K4L-R-gs | re-confirmed, not re-run: RoyaleSim P1 0.931, v3 0.937; ours P1 0.935 (rows of 2026-10-15 04:19) | — | — | — | — | 0 | The candidate's decisions are unchanged since those rows: the panic fix 654b18bb kept command hashes equal on 24/24 games. Read these as ~0.03 optimistic (caveat above). |
| 2026-10-16 14:15 | **RoyaleSim 15.535, daily fresh bank** (BASE 3877999783388832, pre-registered bb74fc17) | **K4L-R-gs (best bot) — quoted number** | **pool R3a+v1+rext-bc 0.878 [0.859, 0.895]**; K4C-r16 0.826 [0.804, 0.848] | 0.9275 / 0.8625 | 0.810 / 0.740 | — | — | 2400 | Cases0–399 per opponent per bot; 2400unique terminal rows,0errors/missing/duplicates. rext-bc0.895/0.875. Paired K4L−K4C pool **+0.052 [+0.028, +0.076]** (exactCI[+0.0275,+0.0758333]); R3a+0.070[+0.025,+0.115],v1+0.065[+0.0275,+0.1025],rext-bc+0.020[−0.0225,+0.0625]. Bootstrap4000draws/seed0/withinopponent/equalweight. 04/08existing reviewed launchers,leases9/33/workers8/32; no runtime/model change. Currentchampion retained; source-onlyR8notinstalled. |
| 2026-10-16 14:15 | **HEADLINE bank (selection-biased)**, RoyaleSim v1+v3; ours v1 | K4L-R-gs | **re-confirmed, not re-run:** RoyaleSim P1 0.931 [0.917,0.945], v3 0.937 [0.925,0.948]; ours P1 0.935 [0.921,0.948] | — | — | — | — | 0 | Same fixed-bank rows of2026-10-15 04:19, prior24/24commandhash bridge retained. 143tracked turn-basedbotfiles match accepted daily0cd7fd28; changed/absentfiles live-only/accounting, runtimepinsunchanged04/08before/after. Re-confirmation is for frozen executed candidate; publishedsource-onlyR8e883wasnotinstalled/synced. Selected-bank scores remain about0.03optimistic. |
| 2026-10-17T03:33:52Z | RoyaleSim16.402 / 0.1.34, allL16, STRONG ONLY | K4L-R-gs | separate strong 0.6000 [0.4000, 0.8000]; headline pool pending | — | — | — | — | 25 | BASE3313223055714752, prereg980e9d671; PARTIAL, running; rext-bc pending. Separate strong 0.6000 [0.4000, 0.8000] n=25. Full paired deltas and fast-tier configuration: [results](HEADLINE-MAX-20261017.md). Reaction/Giant traces unavailable. |
