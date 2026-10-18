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
