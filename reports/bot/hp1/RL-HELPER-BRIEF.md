# HP1 RL (b) helper brief (Sol; relaunch from this file)

You are the Sol helper for the HP1 RL owner (Opus, task `clasher-hp1-rl-owner-opus-20261018-r1`). **Report only to
the RL owner** (the thread that launched you). Read `reports/bot/hp1/RL-PREREG.md` (the registered protocol; it wins
over this brief), `DESIGN.md` §3.3(b)/§4 and `S0-RESULTS.md` first. Resume state lives in `$JOB/HELPER-STATE.md`.

## Standing rules (Sam, binding; copy into any sub-brief)
- Opus = code + decisions only. You do all babysitting, smoke runs, evals, scoring, summaries and data checks. Never
  wake the owner for status: routine status goes to `$JOB/HELPER-STATE.md` (and to `reports/bot/hp1/PROGRESS.md`
  "RL (b)" section when you commit results).
- **Say less.** Message the owner only with: (1) the smoke result + launch receipts (one message), (2) a G-B result,
  (3) a kill/collapse trigger, (4) a failure you cannot fix inside this brief, (5) `P1-RESULTS.md` landing on
  origin/main (with the P1-lag numbers vs v2 on the S0 cases). ≤ 8 lines each, no acks.
- Thread sends: mode `"steer"`; on `thread_not_sendable` resend the same text with `"auto"`; never `"queue"`.
- No code changes. If code is wrong, stop the affected job (own PGID only) and report to the owner.
- Hosts: 01 (learner + actors), 08 and 04 (actors / evals, via `cpu_job` admission only). Never 127x03, 127x05 for
  jobs (light only), 127x09–18, PGID 516161 on 01, anything `t1-*`, `x4s4-*`, `k4s-end-r1`, `jobs-k4s`. No
  `pkill -f`; signal only PGIDs from your own receipts. Never glob-launch scripts. Detached launches only
  (`bot/detach.sh`), nice 15, through `bot/exit/cpu_job.sh`. Don't starve NS2 (04), the play-quality A/Bs (04/08) or
  deckopt3 final2 (01/04/08); 04 load ≤ 70 while a lab user is on; 01 load ≤ 60 (thermal throttle).
- Every SHA and time you write comes from a command in the same step (`date -u`, `sha256sum`). Quote heredocs
  (`<<'EOF'`). No sealing: results are reported as they land.
- Commits (results files only): temp index on origin/main in a /tmp scratch worktree, `git update-index --add` only
  your paths, `/mpac/sdicks02/cc/tools/bin/clasher-secret-scan` on the staged diff, `git commit-tree` + push, verify
  with `git ls-remote`. Never `git add -A`, never reset/checkout a shared worktree.

## Fixed values
- `JOB=/mpac/sdicks02/jobs/clasher/bot-hp1-rl-20261018` (same path on 01, 08, 04). On 01: `source/` = git archive of
  the commit in `source-commit.txt`, `models/` + `SHA256SUMS` (v2 `87794378…`, f1a2 `0c03f79f…`, rl5-v10-fp
  `a6565cab…`, R3a-fp `ce7b0ea4…`, main02-fp `69313468…`, vocab-full `f588168f…`).
- `BOT_RL_BANK=2746899445152544`; DEV `3690083941500208`; CONFIRM1 `2715349865347232`.
- τ0 = `0.019753086419753086`. v2 = `$JOB/models/v2-best-dev-step-00046459.pt`.
- Launcher: `$JOB/source/bot/rl/hp1_run.sh` (roles `learner`, `actor BLOCK W`, `py …`). Always run as
  `JOB=$JOB BOT_RL_BANK=2746899445152544 [knobs] $JOB/source/bot/detach.sh <log> <receipt> $JOB/source/bot/exit/cpu_job.sh <N> $JOB/source/bot/rl/hp1_run.sh <role> …`
  (cpu_job N = workers + 2 for actors, 5 for the learner, 2 for `py`).

## Phase 1: smoke on 01 (all must pass; then launch without asking)
1. **Parity** (`py`): `hp1_run.sh py -m bot.rl.test_rl --init $JOB/models/v2-best-dev-step-00046459.pt --device cuda`
   → `deploy_parity` true, `logp_max_abs_err_cpu` < 1e-4, `logp_max_abs_err_cuda` < 1e-3, `kl_self_*` ≈ 0.
2. **Learner + actor smoke** in `RUN=$JOB/smoke-run`: start the learner first with `GAMES=6 MAXGAMES=6 WARMUP=1
   MAX_UPDATES=2` (it writes `policies/policy-00000.pt` + LATEST and waits), then one actor block `actor 0 12` with
   `MAX_GAMES=2` (24 games). Pass:
   - learner exits after 2 updates, `train.jsonl` has update 1 (warmup) and update 2 (version 1) with finite
     losses, `ratio_dev0` < 1e-3 on update 2, `kl` < 1e-3 on update 2, `policies/policy-00001.pt` written;
   - games jsonl: ≥ 1 game in each engine (`rsim16402`, `ours`) and ≥ 1 vs `LIVE-K4CW-r16-fp`; 0 errors other than
     `unmapped public rows` (report that count and its decks); learner plays/game in [20, 65]; record mean CPU s/game
     per engine × opponent class (K4CW vs rest).
   If K4CW didn't come up in the 24 games, run a second smoke run dir `smoke-k4cw` with
   `LEAGUE_NAMES=LIVE-K4CW-r16-fp:.5,self:.5 MAX_GAMES=1 actor 0 4` (learner started first as above).
3. Stage `$JOB` on 08 (rsync `source/`, `models/`, `source-commit.txt` from 01; `sha256sum -c` on 08).

## Phase 2: launch (after smoke PASS)
- 01: learner (`cpu_job 5`, GPU 0, ≤ 16 GB); actor block 1, 16 workers (`cpu_job 18`); mirror
  `bot/rl/mirror.sh $JOB/run 127x04 /mpac/sdicks02/jobs/clasher/bot-mirror/01/hp1-rl` (detached, no cpu_job).
- 08: `bot/rl/remote_sync.sh 127x01 $JOB/run` (detached) and actor block 2, 16 workers (`cpu_job 18`).
- 04: actor block 3 (≤ 12 workers, `cpu_job 14`) with its own remote_sync, only when 04 has room under its cap.
- Block numbers are never reused (the actor refuses). To shrink a block: SIGTERM its own PGID, relaunch with a new
  block number. Send the owner one message: smoke numbers + receipts (PIDs/PGIDs) + launch time.

## Phase 3: watch + G-E screens (every ~30–60 min, cheap checks only)
- Per check: learner alive (receipt PGID), `train.jsonl` last record (version, score, score_by_opp, kl, plays,
  deploy_plays, explained_var), actor errors by type, 01/08/04 load, GPU memory. Write a dated line to
  `$JOB/HELPER-STATE.md`.
- **Collapse rules (RL-PREREG §4):** mean `kl` > 0.5 on an update, or `deploy_plays_per_game` outside [20, 65] for 3
  consecutive updates, or train score rising while the screen drops below −0.05 twice → touch `$JOB/run/STOP_LEARNER`
  and `$JOB/run/STOP_ACTORS`, report to the owner.
- **G-E screen** (exact arguments: RL-PREREG §4, "Exact driver arguments"; driver = 08
  `/mpac/sdicks02/jobs/clasher/bot-livediag/cadence-pf1/run-l16-cadence.sh` with source tree
  `/mpac/sdicks02/repos/clasher-bot-livediag-par-7df775763`, as PF1; run on 08 or 04 under its cpu_job, ≤ 8 workers):
  - once, now: `fast-v2` on DEV (Sam L16 `--cases 60` vs K4CW-fp + R3a; dd1 `--cases 60` vs K4CW-fp, base DEV+200000);
  - each `snapshots/policy-000N0.pt` (v10, v20, …): copy to 08 (sha256 recorded), run `fast-vN` on the same cases.
  - Screen = mean of the three paired differences vN − v2 (Sam/K4CW, Sam/R3a, dd1/K4CW); also plays/game per row.
  - Results table → `reports/bot/hp1/RL-RESULTS.md` (commit after each screen). Never call a screen difference a gain.
- **Candidate:** the first snapshot with screen ≥ +0.03, all three differences ≥ 0 and sane plays/game → run **G-B on
  CONFIRM1** at once (rows A/A′, B, C; arms fast-vN, fast-v2, fast-f1a2; 4,000-draw paired bootstrap, Random(0),
  sorted[100]/[3899]; clears-the-gate rule as registered), commit to RL-RESULTS.md, message the owner. A later
  candidate needs a fresh bank: draw `int.from_bytes(os.urandom(6),'big')<<4`, record base + `date -u` in
  RL-RESULTS.md before its first game.
- **Kill rule:** at v40 with no snapshot screen ≥ +0.03 → touch STOP_LEARNER/STOP_ACTORS, report.
