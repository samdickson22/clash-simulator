# HP1 (human-init full-pool policy): PROGRESS (resume here)

Owner: HP1 owner (Opus), for the BOT LEAD. Design: `DESIGN.md` (main 1a6983396). S0 pre-registration: `S0-PREREG.md`
(main 6a6708a14, registered 2026-10-17 22:57:26Z, 0 games at registration).

**STANDING RULE (Sam, via BOT LEAD, 2026-10-17): always steer, never queue.**
- Every `t3_thread_send` uses `mode: "steer"`.
- If it returns `thread_not_sendable`, resend the same text with `mode: "auto"`.
- Never `queue`. Copy this rule into every helper brief.

**STANDING RULE (Sam, via BOT LEAD, 2026-10-17): say less.** No acks or "started/queued" messages. Report only results,
failures and decisions; routine status goes here in PROGRESS.md.

## BOT LEAD decisions (2026-10-17 ~22:52Z)

1. **S0 GO (CPU):**
   - Priority: below deckopt3, LVG2 and LV2; alongside NS2; above PT1, HZ1 and K1.
   - Hosts: 04/08 within caps (04 ≤ 70 while the lab user is on). ≤ 16 workers, via `cpu_job`.
2. **P1:** write the trainer with the lag shift and get a Sol review. Then tell the BOT LEAD it is OK-to-run; they
   arrange the GPU window with the LIVE LEAD. **Never take a GPU yourself.**
3. **PT2:** the BOT LEAD tells the cycle-model owner to use v2 as π.

## S0 state

- **Job:** `04:/mpac/sdicks02/jobs/clasher/bot-hp1-s0-20261017/`.
  - `source/` = git archive of 1e933ddc3. `models/` holds v2 (`87794378…`) and f1a2 (`0c03f79f…`), read-only,
    sha-checked.
  - `provenance-models.txt` has the main02-fp `69313468…`, R3a-fp `ce7b0ea4…` and rl5 `e188e2ae…` hashes.
  - `env.sh`, `run.sh` and `STAGE.md` define the launch form and run sequence.
  - The validator `s0_validate.py` stays on 05 (`/tmp/sdicks02-hp1-work/s0/`, copied into `reports/bot/hp1/s0/`).
- **Sol review:** r1/r2/r3 findings all fixed (r3: plays must be nonnegative integers); package cleared 23:15Z.
- **Runs:** smoke PASS 23:25Z (12/12 valid; v2@0.10 plays 6.0 / 14.5 per game vs f1a2 61.5 / 41.5).
- **Handed to a Sol helper (Sam's rule "Sol first, Opus minimal", 2026-10-17 ~23:30Z):** task `hp1-s0-helper-r1`;
  relaunch from `reports/bot/hp1/S0-HELPER-BRIEF.md`. It runs cal-t, ef, cal-k, h, then publishes `S0-RESULTS.md`,
  and wakes the owner only on the result or a failure. Sequence: smoke → cal-t (f1a2 target) → cal-0.. (v2 τ) ∥ ef (f1a2, v1 arms) → h (v2@τ*).
  Validate each with `s0_validate.py` before proceeding.

## P1 state

- **Code:** `/tmp/sdicks02-hp1-work/p1/imitation/hp1/{lagshift.py,train.py,test_lagshift.py,README.md}`. 10/10
  unit tests pass locally; committed at main 5e1003463 after review.
- **Sol review:** r1/r2 fixed; r3 OK-TO-RUN; code on main 5e1003463.
- **Host checks (job `04:/mpac/sdicks02/jobs/clasher/bot-hp1-p1-20261017/`, source 5e1003463, env
  `/mpac/sdicks02/envs/clasher-gpu`):**
  - CPU smoke cap-1 PASS: fresh launch, 10 steps, stopped at the epoch boundary (`state.epoch` 1, cursor 0).
  - The overlay build FAILED its layout check: 39,518 final terminal-context rows sit 1–4 ticks after the last
    decision row (all unsupervised, all last-of-perspective). The fix allows only that row (22 tests); Sol r4
    OK-TO-RUN; main ff5fa65fc, staged as `$J/src-ff5fa65fc7ba`.
  - The CPU smoke chain (overlay-b, cap1-b, cap2-b resume, lag-b, lag2-b resume, pin check) is handed to a Sol
    helper, task `hp1-p1-smoke-helper-r1`; relaunch from `reports/bot/hp1/P1-SMOKE-HELPER-BRIEF.md`. On PASS, tell
    the BOT LEAD OK-to-run for the GPU window.
- **Before the GPU window:**
  - build the overlay on 04 (CPU, minutes);
  - run the CPU smoke of both arms (`--device cpu --max-steps 2 --smoke`);
  - then the BOT LEAD arranges the GPU, starting with a GPU smoke of 20 steps.
- **Inputs:** 04 `~/repos/clasher-t11-home-v1/inputs/{assets.npz,T11-STORE-PASS.json}`. The store is on 04 and 08.

## Facts to keep

- v2 config is identical to v1: 2,254,949 parameters. rl5/f1a2 = 6L/FFN 1536, 4,918,757.
- v2 epoch-1 dev EMA joint NLL is 0.28237 (seed 22, step 7744); final 0.26592.
- Lag legality at shift 25/30 ticks: 93.9% / 90.5% of C56 train plays.
- 04 GPU: shared. 08 GPU: lent to YOLO.

## RL (b) 2026-10-18

Owner: HP1 RL owner (Opus, task `clasher-hp1-rl-owner-opus-20261018-r1`), for the coordinator (b4f05b1c). Pre-registration
`RL-PREREG.md` (init v2 @τ0 0.019753086419753086, KL anchor v2, 2-environment L16 mixture (RoyaleSim Sam deck vs Battle Log + our engine full-pool), 6-way league, G-E DEV
screen + G-B fresh-bank confirm on the PF1 driver).

**Rule in every brief:** Opus = code + decisions only; all babysitting, evals, scoring, summaries, data checks and
reviews go to Sol helpers (gpt-6.1-sol, high), which report to the RL owner. No Opus polling turns. Say less. Thread
sends: "steer"; on thread_not_sendable resend "auto"; never "queue".

- 2026-10-18T04:55:38Z: init = v2 (P1 not reported; switch rule in RL-PREREG §1). Banks drawn 04:53:51Z on 05: RL 2746899445152544,
  DEV 3690083941500208, CONFIRM1 2715349865347232. Code: bot/rl actor/learner/test_rl diff + hp1_run.sh + mirror.sh
  in scratch worktree /tmp/sdicks02-hp1rl-wt (05), diff /tmp/sdicks02-hp1rl-r1.diff. Sol review r1 task
  `clasher-hp1-rl-review-sol-20261018-r1` running.
- 2026-10-18T05:00:05Z: Sol r1 NOT-OK (3 MAJOR, 1 MINOR): vocab-full misses some full-pool cards → RoyaleSim full-pool env
  dropped + unmapped-row guard; exact PF1-driver args registered; legacy tau0 default 0.5375; share validation. r2
  task `clasher-hp1-rl-review-sol-20261018-r2` running (diff /tmp/sdicks02-hp1rl-r2.diff).
- 2026-10-18T05:02:48Z: Sol r2 NOT-OK (1 MAJOR, 2 MINOR): learner resume identity check (tau0/init/league), no_template
  translator guard, mirror includes policies/. r3 task `clasher-hp1-rl-review-sol-20261018-r3` running.
- 2026-10-18T05:04:57Z: Sol r3: one MINOR (mirror LATEST race) → LATEST read before listing, pushed last. Code +
  RL-PREREG committed (this commit).
- 2026-10-18T05:07:14Z: code + RL-PREREG on main 03658e3f0. Job dir staged on 01 (6 model/vocab hashes match). Launcher
  smoke knobs (py role, RUN, GAMES/MAXGAMES/WARMUP) + `RL-HELPER-BRIEF.md` (smoke → launch → G-E screens → G-B) added.
- Next (Sol helper, from RL-HELPER-BRIEF.md): job dir 01 `/mpac/sdicks02/jobs/clasher/bot-hp1-rl-20261018/`
  → Sol smoke helper (test_rl parity v2, per-env actor smoke, 4-update learner smoke) → launch learner (01 GPU) +
  actor block 01 (16) + cpu_job blocks 08/04 + mirror to 04 → Sol eval helper (G-E screens every 10 versions).

- 2026-10-18T05:20:14Z: Sol smoke PASS after owner correction of the smoke KL bound to <0.05 (post-step epoch-average KL=0.00126906; ratio_dev0=2.861e-05). 24 attempted / 21 retained games; 3 permitted SpearGoblin_Dummy unmapped errors; both engines and K4CW covered. Production learner01 + actor01 block1/16 launched; actor08 block2/16 and G-E v2 baseline await cpu_job admission; sync08 and hourly mirror04 active. 04 actors deferred under load cap. Receipts, decks and CPU timings in RL-RESULTS.md; resume at 01 /mpac/sdicks02/jobs/clasher/bot-hp1-rl-20261018/HELPER-STATE.md.

- 2026-10-18T05:55:16Z: Sol Phase3 check: learner warmup update 2, v0, no collapse; 01/08 actor blocks admitted. 04 staged with six hashes checked; actor block3 W12 PGID 1203513, sync PGID 1203459, own load guard PGID 1203435, cap70. Bootstrap mirror to04 PASS. DEV baseline08 Sam 18/120 clean-so-far, no completed screen. Details in RL-RESULTS.md; no owner status message.

- 2026-10-18T06:23:16Z: Sol found remote_sync policy-publication race: 3 block2 workers on08 died loading uncopied policy-00002.pt. Stopped owned08 block2/sync and owned04 block3/sync/guard; groups verified absent; completed rollouts flushed. Owner notified; no helper code changes; blocks2/3 spent. Learner01/actor1 and baseline08 continue, no collapse (update5/v2 KL.00493). Baseline Sam77/120 clean-so-far. Remote restart awaits owner repair; full receipts/evidence in RL-RESULTS.md and primary HELPER-STATE.md.

- 2026-10-18T06:54:17Z: Sol: owner fix6ca53032b deployed only to08/04 after source-use checks and six model/vocab checksum checks; blocks4(08,W16) and5(04,W12) admitted, old2/3 spent, 01 source/learner/actor1 untouched. DEV fast-v2 baseline validated180/180 with0 problems: Sam K4CW-fp .516667/47.0667plays, SamR3a .583333/48.7167plays, dd1K4CW-fp .533333/47.0667plays. These are the paired reference, no gain claim. Watch update8/v5 KL.00805, no collapse; next screen v10. RL-RESULTS.md and HELPER-STATE.md hold receipts/readout; no owner status ping.

- 2026-10-18T08:51:33Z: Sol G-E v10 validated180/180, zero problems, exact paired cases. Differences vs v2 (Sam/K4CW, Sam/R3a, dd1/K4CW): +0.116667, +0.150000, +0.133333; equal screen=+0.133333; candidate predicate=True. DEV selection only, no gain claim. Full plays/checkpoint provenance in RL-RESULTS.md; resume from primary HELPER-STATE.md.

- 2026-10-18T09:04:51Z: Sol launched first G-B v10 on single-use CONFIRM1 (08 PGID4142369,3300 total rows pending) immediately after validated selection; DEV v20 screen PGID4147276 also active. Owner-authorized expansion:04 blocks6/7 target40 workers incl5;01 block8 admitted targeting24 incl1 afterMHz check;08 block9 queued targeting32 incl4. New aggregate04 guard replaces oldblock5 guard, cap70;01 newguard owns8/cap56, originalguard1/learner untouched. Baseline5.903252updates/h; postscale rate pending enough updates, backlog145 at09:01:30Z (<960). No gain or throughput-increase claim yet; all receipts/state in RL-RESULTS.md and primary HELPER-STATE.md. No owner status message.

- 2026-10-18T09:53:09Z: Sol applied owner overload placement: stopped08 actor4/queued9, verified all32 game logs synced and finishedrollout count0, then stopped08sync. Existing G-Bv10/G-Ev20 continue; no new08 work during PTR1.04 block10W16 replaces queued6, total40 with5/7; newaggregate guard owns5/7/10. At09:51 blocks7/10 admitted with load pauses. Measured partial-scale3.057325updates/h vs pre-scale5.903252: no increase demonstrated, backlog43 (<960), learner flags unchanged. Trainupdate28/v25 KL.03241, no collapse/new worker error; v20Sam120clean/dd1pending and G-BSam115/1800. Full receipts/evidence in RL-RESULTS and HELPER-STATE. No owner status ping.

- 2026-10-18T10:23:51Z: Sol G-E v20 validated180/180, zero problems, exact paired cases. Differences vs v2 (Sam/K4CW, Sam/R3a, dd1/K4CW): +0.100000, +0.083333, +0.100000; equal screen=+0.094444; candidate predicate=True. DEV selection only, no gain claim. Full plays/checkpoint provenance in RL-RESULTS.md; resume from primary HELPER-STATE.md.
- 2026-10-18T10:38:57Z: Sam/coordinator direction: policy-only bot must beat live search (G-S, RL-PREREG amendments 1-3: all-deck
  opponents, deck mix 50/30/20, SEARCH in league, no separate IL deck fine-tune). Corpus deck table on 01 models/
  (sha 16ca9bfb…, 40,188 decks). Sol reviews gs-r1..r4 → OK-TO-SMOKE. Rule: QUIET (coordinator only G-S/confirm
  results, policy beats search, failures; ≤3 lines). RoyaleSim GoblinHut gap had voided 35% of run1 rsim games.

- 2026-10-18T10:42:48Z: Sol Amendment deployment corpus registration. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T11:04:35Z: Sol Amendment smoke failure and exclusion probe. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.
- 2026-10-18T11:24:22Z: RoyaleSim probe: 19 translator-gap cards (51% of corpus weight) → amendment 4 exclusion set; sam kind split rsim/ours; coordinator told.

- 2026-10-18T11:26:31Z: Sol G-E v30 validated180/180, zero problems, exact paired cases. Differences vs v2 (Sam/K4CW, Sam/R3a, dd1/K4CW): +0.116667, +0.216667, +0.166667; equal screen=+0.166667; candidate predicate=True. DEV selection only, no gain claim. Full plays/checkpoint provenance in RL-RESULTS.md; resume from primary HELPER-STATE.md.

- 2026-10-18T11:29:44Z: Sol RoyaleSim coverage probe and amendment 4 smoke. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T11:53:12Z: Sol Amendment 4 smoke3 PASS. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.
- 2026-10-18T11:56:03Z: ExIt aux loss (learner --aux-data, default off) + EXIT-AUX-SPEC.md; Sol aux-r1 NOT-OK fixed (illegal-label rows masked; features recorded live). Re-review before the first --aux-data run. Data requested from the play-quality owner via the coordinator.
- 2026-10-18T12:11:43Z: OwnCycle errors (6/214) → 6 more RoyaleSim exclusions (note to amendment 4); new-mix deployment released.

- 2026-10-18T12:14:49Z: Sol Amendment 4 residual errors and expanded coverage limit. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T12:20:08Z: Sol G-S DEV reference index0 retry registration. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T12:28:27Z: Sol Expanded exclusion cohort launch receipts. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T12:30:11Z: Sol G-E v40 validated180/180, zero problems, exact paired cases. Differences vs v2 (Sam/K4CW, Sam/R3a, dd1/K4CW): +0.116667, +0.166667, +0.133333; equal screen=+0.138889; candidate predicate=True. DEV selection only, no gain claim. Full plays/checkpoint provenance in RL-RESULTS.md; resume from primary HELPER-STATE.md.
- 2026-10-18T12:39:31Z: OwnCycle early-refill fix (royalesim_translate); exclusions back to the 19 probe cards.

- 2026-10-18T12:42:27Z: Sol OwnCycle source fix and explicit DEV recovery registration. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T12:47:35Z: Sol OwnCycle-fixed actor rotation and fresh DEV launch receipts. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.
- 2026-10-18T12:53:32Z: OwnCycle resync-to-RoyaleSim fix; SEARCH-opponent rejections recorded, not voiding.
- 2026-10-18T13:01:57Z: G-S --keep-going + case-level exclusion (≤5%) for RoyaleSim cycle-fidelity errors.

- 2026-10-18T13:09:45Z: Sol Cycle-fidelity failures and amended training gate registration. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T13:21:32Z: Sol Amended training gate pass and production resumption. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.
- 2026-10-18T13:46:12Z: G-S drop limit 10% for SEARCH-opponent rows (DEV 6.7%), registered before any confirm game.

- 2026-10-18T13:53:37Z: Sol Registered G-S drop limits and archetype reporting. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T14:24:27Z: Sol G-E v50 validated180/180, zero problems, exact paired cases. Differences vs v2 (Sam/K4CW, Sam/R3a, dd1/K4CW): +0.150000, +0.166667, +0.133333; equal screen=+0.150000; candidate predicate=True. DEV selection only, no gain claim. Full plays/checkpoint provenance in RL-RESULTS.md; resume from primary HELPER-STATE.md.

- 2026-10-18T14:31:31Z: Sol Source8f rotation completion and measured throughput. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T15:02:51Z: Sol G-S DEV all-deck reference validation (source8f). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T15:04:13Z: Sol G-S DEV screen v60 (source8f; selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T15:05:13Z: Sol G-S DEV screen v70 (source8f; selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T15:09:30Z: Sol G-E v60 validated180/180, zero problems, exact paired cases. Differences vs v2 (Sam/K4CW, Sam/R3a, dd1/K4CW): +0.150000, +0.250000, +0.216667; equal screen=+0.205556; candidate predicate=True. DEV selection only, no gain claim. Full plays/checkpoint provenance in RL-RESULTS.md; resume from primary HELPER-STATE.md.

- 2026-10-18T15:09:39Z: Sol G-E v70 validated180/180, zero problems, exact paired cases. Differences vs v2 (Sam/K4CW, Sam/R3a, dd1/K4CW): +0.283333, +0.266667, +0.116667; equal screen=+0.222222; candidate predicate=True. DEV selection only, no gain claim. Full plays/checkpoint provenance in RL-RESULTS.md; resume from primary HELPER-STATE.md.

- 2026-10-18T15:26:00Z: Sol G-S DEV screen v80 (source8f; selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T15:33:43Z: Sol G-E v80 validated180/180, zero problems, exact paired cases. Differences vs v2 (Sam/K4CW, Sam/R3a, dd1/K4CW): +0.166667, +0.200000, +0.200000; equal screen=+0.188889; candidate predicate=True. DEV selection only, no gain claim. Full plays/checkpoint provenance in RL-RESULTS.md; resume from primary HELPER-STATE.md.

- 2026-10-18T15:35:10Z: Sol Original DEV SEARCH secondary reference: invalid translator coverage. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.
- 2026-10-18T15:36:01Z: G-E screens moved to ALL-16 DEV rows (Battle Log pool rows invalid: GoblinHut).

- 2026-10-18T15:41:33Z: Sol G-E moves to ALL-16 plus dd1; v110 launch receipts. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T15:57:31Z: Sol G-S DEV screen v90 (source8f; selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T15:58:20Z: Sol Revised ALL-16 plus dd1 DEV screen v90 (selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T16:00:39Z: Sol DD1 SEARCH reference launch correction and updated throughput. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T16:30:24Z: Sol 08 SSH outage recovery rule and04 v120 screen receipts. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T16:44:28Z: Sol 08 memory recovery:64actors, persistent20GiB floor and verified rollout drain. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T16:52:50Z: Sol G-S DEV screen v100 (source8f; selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T16:53:45Z: Sol G-S DEV screen v110 (source8f; selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T16:54:56Z: Sol DD1 SEARCH reference: invalid translator coverage, retained paired readout. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T16:55:50Z: Sol Revised ALL-16 plus dd1 DEV screen v110 (selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.
- 2026-10-18T16:56:33Z: dd1 rows dropped from G-E/G-B (GoblinHut decks void in RoyaleSim).

- 2026-10-18T17:05:32Z: Sol ALL-16 two-row DEV screen v90 (selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T17:06:48Z: Sol ALL-16 two-row DEV screen v100 (selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T17:07:05Z: Sol ALL-16 two-row DEV screen v110 (selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T17:08:23Z: Sol G-E/G-B dd1 retired; two-row screens and candidate OFF1 orchestration. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T17:24:17Z: Sol G-S DEV screen v130 (source8f; selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T17:25:10Z: Sol ALL-16 two-row DEV screen v130 (selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T17:26:17Z: Sol G-S DEV screen v120 (source8f; selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T17:26:48Z: Sol ALL-16 two-row DEV screen v120 (selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T17:30:54Z: Sol Completed ALL-16 v120/v130; untouched v140 placement and G-B boundary. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T17:31:39Z: Sol G-B v10 CONFIRM bank 2715349865347232: registered result. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T17:57:47Z: Sol G-S DEV screen v140 (source8f; selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T17:58:46Z: Sol ALL-16 two-row DEV screen v140 (selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T18:00:21Z: Sol ALL-16 v140 selection readout;04 memory retirement and v160 queue. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T18:26:12Z: Sol G-S DEV screen v150 (source8f; selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T18:26:34Z: Sol ALL-16 two-row DEV screen v150 (selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T18:27:30Z: Sol Memory guard retirement, stable sync drain and snapshot170 launch. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T18:52:54Z: Sol G-S DEV screen v160 (source8f; selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T18:53:16Z: Sol ALL-16 two-row DEV screen v160 (selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T18:55:17Z: Sol G-S DEV screen v170 (source8f; selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T18:55:29Z: Sol ALL-16 two-row DEV screen v170 (selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T19:23:15Z: Sol Snapshot180 launch and never-admitted memory-queue placement. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T19:53:23Z: Sol G-S DEV screen v180 (source8f; selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T19:53:50Z: Sol ALL-16 two-row DEV screen v180 (selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T19:54:21Z: Sol 04 memory containment and snapshot190 launch. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T20:23:06Z: Sol G-S DEV screen v190 (source8f; selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T20:23:26Z: Sol ALL-16 two-row DEV screen v190 (selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T20:23:51Z: Sol Snapshot200 shared DEV launch and resource watch. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T20:52:57Z: Sol G-S DEV screen v200 (source8f; selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T20:53:16Z: Sol ALL-16 two-row DEV screen v200 (selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T20:53:43Z: Sol Snapshot210 shared DEV launch and resource watch. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T21:23:06Z: Sol G-S DEV screen v210 (source8f; selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T21:23:24Z: Sol ALL-16 two-row DEV screen v210 (selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T21:23:51Z: Sol Snapshot220 shared DEV launch and resource watch. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T21:52:54Z: Sol G-S DEV screen v220 (source8f; selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T21:53:20Z: Sol ALL-16 two-row DEV screen v220 (selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T22:22:44Z: Sol Snapshot230 shared DEV launch and resource watch. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T22:54:52Z: Sol G-S candidate v230: OFF1 sanity registered before games. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T22:55:15Z: Sol G-S v230 confirm bank 3262629447693008: registered before games. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T22:55:38Z: Sol G-S DEV screen v230 (source8f; selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T22:56:18Z: Sol ALL-16 two-row DEV screen v230 (selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T22:58:46Z: Sol v230 first G-S selector: OFF1 and S-CONFIRM1 launched; v240 screen. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T23:23:08Z: Sol G-S DEV screen v240 (source8f; selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T23:23:36Z: Sol ALL-16 two-row DEV screen v240 (selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-18T23:23:52Z: Sol 04 actor54 memory retirement; completed data preserved. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-19T00:25:44Z: Sol v230 OFF1 invalid: our-engine errors preserved; v250 DEV launched. See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.

- 2026-10-19T00:53:04Z: Sol G-S DEV screen v250 (source8f; selection only). See RL-RESULTS.md for the registered provenance and measured status; primary HELPER-STATE.md retains launch/resume receipts. QUIET rule: only gate results/policy beating search/failures to owner, at most3 lines.
