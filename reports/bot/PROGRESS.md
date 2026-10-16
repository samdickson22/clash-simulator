# BOT LEAD progress (exploration)

Mandate: the strongest bot, judged by a trusted win rate. Coordinator ruling: COORDINATOR 91e2bb67 (exploration
tier). Report to coordinator thread 0523ae6f.

## Current handoff: Sol interim, 2026-10-16 09:10 UTC

Sam's 2026-10-16 direction: continue existing work on GPT-6.1-Sol high; no major strategy, runtime or model
promotion until Sam returns to Opus. Preserve ownership, data and existing gates. Bounded Astra high diagnostics
are allowed for deep technical uncertainties. All image/crop/zoom work uses Sol. Screen/input-only fairness and
Mac-only emulator scope remain binding; no heavy work on 05 and never hosts 09–18.

- **Best student remains RL r5 v10**, threshold 0.5375, SHA256
  `e188e2aeb9a6828ffbef237aa327e495eb39ca5f8322ae18aa70c63cb81bba19`. Iteration 10 is complete: r9 v4's F10
  delta was −0.003 [−0.026, +0.021], not confirmed (2,000 games, no errors). Details: `exit/PROGRESS.md`.
  C56 feeders deliberately remain OFF for G1. RL r9/r10 are checkpointed and paused; GPUs remain LIVE-owned.
- **Full-pool G1/K1:** existing Sol babysitter `fullpool-g1k1-babysit-r1` is active. Latest 08:55:24Z receipts:
  G1 4,881 rows / 1,936,547 labels / 52 known errors; K1 1,171 games / 719,578 recording rows / 7 known errors.
  All 13 recorded process groups alive. Existing r2 retry/preflight rules remain in force; no new root is promoted.
  See `fullpool/PROGRESS.md` and `/mpac/sdicks02/jobs/clasher/bot-fullpool/babysit-g1k1.log` on 05.
- **Revealed-set round 7:** existing Sol collector `revset-r7-collect-1` active. Floorchk 0/60, smoke 0/40 at
  09:05:46–47Z. Both wait on the canonical 03 cpu_room.sh: live count 107, cap 105, leased_idle 0; all five
  lease owners and all three claim owners alive. This is live-count saturation, not a stale lease. Bash wrappers
  containing "python" inflate that conservative count; no accounting script or priorities changed.
  LIVE comparison complete: patched 217 passed / 9 failed / 7 skipped, unpatched 178/9/7, identical failure sets.
  The +39 passing tests do not clear the pending floorchk/smoke gates or authorize deployment.
- **Level pilot HOLD before bank/game (09:10Z):** original owner resumed in place on Sol; helper completed the DEV harness. Four pytest tests pass;
  repeated four-game DEV A runs match all four hashes/logs/tower HP, 8/8 wins, no errors/rejections/failures.
  Original exporter on 01 PID 2918593 finished: L11 121 cards/no errors; L5 118 cards/3 errors (Clone, Earthquake,
  Tornado). Full-runtime check11 matches only 3/121 cards to R.config; 118 unsupported, including pilot cards.
  Arm B would silently retain L11 for most cards, so it must not run. The earlier 20-card preliminary mapping
  claim is not upheld by this full check. Owner diagnoses structural mismatch; disjoint exports4/6/7/9 continue.
  Deferred 03 probe
  expired its original admission timeout without running and was not requeued. Independent Sol review and a small
  Astra diagnostic on leaf normalization are active. No pilot bank drawn and no promotion. See `levels/PROGRESS.md`.
- **GPU reconciliation (LIVE/r3 owners):** 04 V7lo1024 completed rc0 at 08:39:34Z; 08 V6lo completed rc0 at
  08:53:40Z. Eval loops remain alive. 01 V8 PID 1967844 remains active around epoch 9/20. Idle 04/08 GPUs are
  completed jobs, not failures; no replacement trainer is authorized under the interim hold.
- **Descendant inventory:** 67 unique descendants at inspection: 4 running (all Sol), 57 completed, 3 interrupted,
  2 cancelled, 1 idle. Interrupted/cancelled tasks are superseded or already delivered results; the idle throughput
  researcher already delivered its result. No actually stopped unfinished descendant needed restarting. No duplicate
  jobs or review rounds were launched. The level helper completed after this inventory snapshot.
- **Next concrete action:** keep existing G1/K1 and round-7 collectors running; collect level reviews/export receipts.
  Keep fits behind their existing data/resource/review gates. Park promotions, new strategies and unresolved major
  normalization choices for Opus. Daily HEADLINE schedule remains enabled for 13:00Z, using the existing protocol.

### UTC audit

Audit, inventory and exact continuation commands: `audit/SOL-RESUME-20261016.md` and
`audit/sol-resume-descendants-20261016.json`. Parent coordinator was notified on resume; LIVE was notified of
the idle GPU receipt and confirmed clean completion. This continuation has made no account actions, signalled
no process, launched no compute job and changed no runtime/model pin. No rollback was needed.

## Layout

- **Worktree:** `/mpac/sdicks02/repos/clasher-bot` on 05, branch `bot/lead`.
  - Code lives in `bot/`, reports in `reports/bot/`.
  - The tree is synced to 03 and 04 with `rsync -a bot/ HOST:/mpac/sdicks02/repos/clasher-bot/bot/`.
- **Envs on 03:**
  - `/mpac/sdicks02/repos/clasher-bot/.venv` (py3.12, `uv sync`, plus royalesim 0.1.34);
  - `/mpac/sdicks02/repos/clasher-bot-rsim/.venv` (`royalegym[all]` 0.1.24);
  - upstream clones (read-only reference) in `/mpac/sdicks02/repos/clasher-bot-rsim/upstream/{RoyaleSim,RoyaleGym}`.
  - Source `bot/env.sh` for the cargo and uv cache paths.
- **Data on 03:** `/mpac/sdicks02/repos/clasher-bot-data/t1-trainval/` holds the 577 train+val match dirs (no
  video), copied read-only from 01. `t1-split.json` is the registered split.
- **Job dirs:** `/mpac/sdicks02/jobs/clasher/bot-*` on 03 and 04.

## Done

- **2026-10-14 ~03:15Z, step 1 fidelity:** `reports/bot/FIDELITY.md`. Results are in `bot-fid-r2` on 03.
  - No towers, within ¼ tile: RoyaleSim 15.535 **78.8%**, ours **51.4%**, RoyaleSim 16.402 72.1%.
  - Paired: +26.1 pp for RoyaleSim, better in 530/577 fixtures.

- **2026-10-14 ~03:25Z, step 2 speed:** `reports/bot/SPEED.md`.
  - Rust core 34.3k ticks/s with a 5 µs clone; RoyaleSim 30.8k (16.402 rules) or 14.2k (15.535 rules) with a ~5 ms
    save+load branch; Python 521.

- **2026-10-14 ~03:45Z, RoyaleSim clone spike:** `reports/bot/RSIM-CLONE-SPIKE.md`.
  - `restore_from` takes 9.8 µs. The fork is byte-identical to the PyPI wheel on fidelity.
- **2026-10-14 ~04:00Z, step 3 (our engine):** `reports/bot/STRENGTH.md` and `HEADLINE.md`.
  - K4S-b64 pool score 0.864 [0.847, 0.882].
  - Sampling the gate costs −24 pp; v1's calibrated threshold is τ = 0.1387.

- **2026-10-14 ~04:35Z:**
  - RoyaleSim headline: K4S-b64 pool 0.851.
  - Step 4 decision ACCEPTED by the coordinator: plan and train on our Rust core, trusted headline in RoyaleSim,
    calibrate ours behind the 577-fixture gate (`DECISION-ENGINE.md`).
- The v1-τ arm collapsed (−45 pp): thresholds must be calibrated on-policy.

- **2026-10-14 afternoon:**
  - The engine calibration batch 1+2 is merged into main (0ecdd97d, tag `engine-r1`). Fidelity is 72.3/74.5%; parity 574/577.
  - The planner A/B on r2 vs r1 is null. Learned leaf value: negative. Candidate round 2: R3a top-16 confirmed.
  - **Best bot: K4C-r16** (fresh-bank +0.021 over K4S-st). RoyaleSim P1 0.921, v3 0.924.
  - **Best student: it5s2** (ExIt; 0.883 vs v1). HEADLINE-v3 adds the human-clone external `rext-bc`.

- **2026-10-15 ~00:50Z:**
  - **Best bot: K4L-R-gs** (K4C-r16 with a learned rollout opponent). Fresh bank, RoyaleSim: +0.055 [+0.040, +0.069]
    over K4C-r16 at equal CPU (`reports/bot/learned-opponent/`). Turn-based tiers only until its rollouts fit 200 ms.
  - RL fine-tune of it5s2 (PPO, KL-anchored): null (`reports/bot/rl/`).
  - ExIt iteration 7: 9 refits of it5s2, none better; it5s2 stays the best student.

- **2026-10-15 06:42Z:** live K4L variant `LIVE-K4L-R-gs-rw-fc-w200-t4-p4`: 4-core p50/p95 79/126 ms, +0.058 [+0.020, +0.095]
  vs K4CW-r16 at a real 200 ms; fresh bank 2 +0.053 vs K4C-r16. Handed to the LIVE LEAD (hook + Mac timing pending).

## Historical running status (2026-10-15 06:42Z; superseded by current handoff above)

- **ExIt it9** (`bot-lead-exit-it9-r1`, Opus) on 01/04/08 (GPUs + CPU feeders): gentle refits of it5s2 and Kall on all labels.
- **K4L round 2** (`bot-lead-lopp-r2-r1`, Opus), primary host 03: learned-term weight, multi-sample, opponent model v2.
- **Daily headline:** T3 scheduled task at 13:00Z (v1 + v3), best bot from this file.
- **Hosts:** 01, 03, 04, 08 (05 light only). Exclusions: 01 PGID 516161, x4s4-onpolicy, t1-*; 08 v4-b-20261012-r1.

## Next

1. ExIt: next best student, both engines plus rext-bc. Feeders switch to on-policy behaviour.
2. Search scorer: the scripted opponent models inside rollouts. These are the remaining lever after the candidate and
   leaf nulls.
3. Re-headline the best bot when the code changes. Live play is a separate, later authorization.
