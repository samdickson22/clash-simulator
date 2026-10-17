# HP1 S0 helper brief (Sol, gpt-6.1-sol high). Relaunch from this file after any restart.

You run the rest of the pre-registered HP1 S0 screen for the HP1 owner (Opus). Report to nobody else.
**Wake the owner only by finishing your task:** on the final result, or on a failure you can't fix inside these rules.
Don't send progress messages.

## Standing rules (Sam, binding)

- **Always steer, never queue.** Every `t3_thread_send` uses `mode: "steer"`; on `thread_not_sendable` resend the same
  text with `mode: "auto"`; never `queue`. You shouldn't need to message anyone.
- **Say less:** no acks or "started/queued" messages. Results, failures and decisions only. Routine status goes in
  the Status section of `reports/bot/hp1/S0-RESULTS.md` (local working copy `/tmp/sdicks02-hp1-work/S0-RESULTS.md`).
- **Hosts:** 127x04 only for games (lab user present: `BOT_CPU_CAP=70`). Never 02, 03, 05 (except local analysis),
  06, 07 or 09–18. 08 is busy with higher-priority work; don't use it.
- **Signals:** never `pkill -f` or `pgrep -f` (they match their own shell). Signal only S0's own verified PGIDs (from
  each run's `runs/NAME.receipt.json`), only SIGSTOP/SIGCONT/SIGTERM. Never signal or renice foreign jobs.
- **Times and hashes:** times come from `date -u` in the same command; hashes come from commands, never typed.
- **No code changes** to the job's `source/`, `env.sh` or `run.sh`. If something needs a code change, stop and
  finish with a failure report.

## What is fixed (read first)

- Pre-registration: `reports/bot/hp1/S0-PREREG.md` (main 6a6708a14; local `/tmp/sdicks02-hp1-work/S0-PREREG.md`).
  Follow it exactly.
- Job: `04:/mpac/sdicks02/jobs/clasher/bot-hp1-s0-20261017/` (`env.sh`, `run.sh`, `STAGE.md`, `source/` = 1e933ddc3,
  `models/`).
- Validator (run on 05 only): `python3 /tmp/sdicks02-hp1-work/s0/s0_validate.py DIR --candidates C --opponents O
  --start S --games N --base B`. Exit 0 = valid. Any invalid run stops everything: report it, don't rerun.
- Rows: copy each finished run back with `rsync -a 127x04:$J/runs/NAME /tmp/sdicks02-hp1-work/s0rows/`, then validate.
- Done: the smoke (12/12 valid, 23:25Z). v2@0.10 played 6.0 (R3a) and 14.5 (K4C-r16) cards/game; f1a2 played
  61.5 / 41.5. Smoke rows are never used in estimates.

## Launch form (exact; env sourced first)

```
J=/mpac/sdicks02/jobs/clasher/bot-hp1-s0-20261017
ssh 127x04 "source $J/env.sh && bash $J/source/bot/detach.sh $J/runs/NAME.log $J/runs/NAME.receipt.json \
  bash $J/source/bot/exit/cpu_job.sh $((W+1)) nice -n 15 bash $J/run.sh NAME W 'CANDS' OPPS GAMES START BASE"
```

- Inside env.sh: `$V2` = v2 path (spec `student:$V2@TAU`), `$F1A2` = f1a2 spec, `$BASE` = 1192128049223264,
  `$CALBASE` = 874184153281168, `$CALSTART` = 46359089.
- Write TAU in Python `repr` form, e.g. `0.0666...`, and record the exact string.
- A run is finished when `runs/NAME.exit` exists. Its content is headline's exit code; validity comes from the
  validator. Wait with a sleep loop that polls only that file (≥ 60 s per poll), never pgrep.

## Sequence and worker budget (≤ 16 S0 game workers at any time)

1. **cal-t:** `cal-t 8 "$F1A2" R3a 64 $CALSTART $CALBASE`. Target = mean candidate plays/game (validator
   `plays_per_game`).
2. **ef**, at the same time as calibration: `ef 8 "$F1A2,v1" R3a,K4C-r16 100 0 $BASE`. 400 games.
3. **cal-0, cal-1, …** (sequential, 8 workers each): `cal-K 8 "student:$V2@TAU_K" R3a 64 $CALSTART $CALBASE`.
   - τ0 = 0.10.
   - No bracket: τ ← τ×1.5 if plays > target, else τ/1.5.
   - With a bracket (some τ above the target and some below): secant inside it, as in `bot.exit.calibrate`:
     `tau = lo + (hi-lo)*(p_lo - target)/max(1e-9, p_lo - p_hi)`, where lo = the largest τ with plays > target and
     hi = the smallest τ with plays < target.
   - Stop when |plays − target| ≤ 1.5, or after 6 rounds.
   - τ* = the round τ closest to the target. Record every round in S0-RESULTS.md **before** launching h.
4. **h:** `h W "student:$V2@TAU*" R3a,K4C-r16 100 0 $BASE`. 200 games. W = 8 while ef runs, 16 if ef has finished.

## Priority and load

- **S0 ranks** below deckopt3 (`deckopt3_driver`), LVG2 (`bot-cycle/lvg2`) and LV2; equal to NS2; above PT1, HZ1
  and K1. `cpu_job.sh` admission does the waiting; don't bypass it.
- **If 04's 1-min load stays > 80 for 10 min while one of the higher-priority jobs is running:**
  - SIGSTOP your newest running S0 PGID;
  - SIGCONT it when load < 70;
  - log each STOP/CONT with `date -u` in the Status section.

## Readout (when ef and h are both valid)

Write `/tmp/sdicks02-hp1-work/S0-RESULTS.md` (results first, short):
1. **Calibration table:** each round's τ, plays/game (± se), score; the target; τ*.
2. **Per arm × opponent:** n, score with 95% CI (4000-draw case bootstrap, Python `random.Random(0)`, percentile
   sorted[100]/sorted[3899]), plays/game, mean CPU s/game, W/D/L. K4C-r16 is always separate.
3. **Paired contrasts per opponent:** H−E and H−F, resampling matched case indices; same bootstrap. No pooling of
   K4C-r16.
4. **Context, not paired:** NS1 rl5-only vs R3a 0.77 and vs K4C-r16 0.52, on a different bank.
5. **Descriptive** where present in rows: accepted plays, reaction fields, undefended Giant pushes.
6. **Status log and resources:** CPU-h, wall time, any STOP/CONT.

Analysis scripts may live only in `/tmp/sdicks02-hp1-work/s0helper/` on 05. Keep them, and put their SHA256 in the
report.

## Publishing

- Commit only `reports/bot/hp1/S0-RESULTS.md`, using a temp index on origin/main:
  1. `export GIT_INDEX_FILE=$(mktemp)`; `git read-tree origin/main`; `git hash-object -w`; `git update-index
     --add --cacheinfo 100644,BLOB,reports/bot/hp1/S0-RESULTS.md`;
  2. run `/mpac/sdicks02/cc/tools/bin/clasher-secret-scan` (non-zero = stop);
  3. `git write-tree`; `git commit-tree -p origin/main`; `git push origin SHA:refs/heads/main`. Retry on a push race
     after re-fetching.
- End the commit message with `Co-Authored-By: GPT-6.1-Sol <noreply@openai.com>`.
- Publish once when calibration is frozen (Status + calibration table), and once at the end. No data or rows in git.
- Work in `/mpac/sdicks02/repos/clasher` with the temp index only. Never touch that checkout's own index or working
  tree.

## Finish

Your final message, ≤ 12 lines:
- τ*;
- the per-cell scores;
- H−E and H−F with CIs per opponent;
- validity (all runs valid, 0 errors);
- the S0-RESULTS.md commit SHA.

On failure: what failed, the exact run, the log tail, and what you left running (PGIDs).
