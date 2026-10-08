# T5 v1 training and gate (a)

2026-10-08 05:20 UTC — **WAITING FOR START CONDITIONS.** No T5 GPU jobs,
training, calibration or eval/eval_ood scoring have been launched. No commits.

## Qualification

- Checked 127x01 directly at 05:19:06 UTC, who empty. Required receipt absent:
  `reports/strategy_council_20260928/imitation/data/receipts/T3-PASS.json`.
- Data handoff: T2 PASS; T3 store/frequency baseline finished, P16 baseline
  scoring and verified LAN copies to 04/08 still pending. Root manifest's
  passed=true is **not** the final T3-PASS receipt.
- T4 shakedown is pending T3. Its existing 10-minute scheduled task remains
  enabled; do not launch or duplicate its shakedown. Read model receipts and
  PROGRESS-model.md after T3-PASS; if shakedown fails, report and stop T5.
- Required fleet documentation is actually at
  `reports/strategy_council_20260928/fleet/GPU-CHECK.md`; launcher is alongside it.
  User's explicit permitted hosts and worker limits override old fleet examples.

## Prepared and remaining implementation

Registration draft:
`reports/strategy_council_20260928/imitation/gate-a/PREREG.draft.md`.
It records the exact A1–A4 bars, statistical choices, train seeds, bootstrap
seed 2026100805, available store/role pins, and prior exposure to T3's published
baseline summaries. It is deliberately **not frozen** while T4 can still change
code and qualification is pending. No PREREG.md/freeze receipt yet.

Code inspection found that the current T4 trainer only implements main, with
no noD1/GRU switches. Store/evaluator enforce train/dev roles only. T5 must
implement ablation support and a receipt-guarded one-time held-out scoring
entry point in owned files, without racing or overwriting T4's live files.
Complete dev/synthetic verification, freeze final code hashes and feature/
sequence definitions before any held-out inference. For GRU, preserve causal
32-row contexts within a perspective and correct sequential evaluation.

Read: DESIGN §§4.3–4.4, 5.1, 7; model README/progress and trainer/evaluator;
data progress/manifest and frozen eval spec; fleet GPU rules and launcher.
No AGENTS.md found in the repository/parent search.

## Runs and resume

Planned five runs: main seeds 2026100801/2026100802/2026100803;
noD1 and GRU seed 2026100801. No run labels/PIDs/checkpoints exist yet.
Packing and rows/s are **unmeasured**, not the design estimate.
Training curves, selected hashes, A1–A4 numbers and compute are pending.
T5 training/GPU compute used so far: zero.

Next: verify T3-PASS, wait for T4 PASS at 10-minute intervals, finalize owned
code and freeze PREREG, then use the updated five-GPU allocation below.

Once launched, record host, label, launcher and trainer PIDs, source/config
hashes, log/exit paths, run directory, checkpoint and exact resume command
here before handing off. Generic resume shape (not runnable before filling
owned frozen paths):

```text
bash reports/strategy_council_20260928/fleet/fleet_run.sh NEW-T5-LABEL \
  env PYTHONPATH=FROZEN-T5-SOURCE \
  /mpac/sdicks02/envs/clasher-gpu/bin/python -B -m FROZEN-T5-TRAINER \
  SAME-RECIPE-FLAGS --resume VERIFIED-CHECKPOINT
```

Never duplicate a live run. Use verified PIDs only; technical retries require
recorded reasons and preserve old outputs. Never delete stores/checkpoints.
Mirror only owned docs, receipts and results to 05 with rsync -c.

Temporary same-thread continuation schedule created and enabled, every 10 min:
`scheduled-task:command:mcp:3edbde69-151b-4209-8cf7-c6c1eac260db:schedule-task:clasher-imitation-t5-continuation-20261008-v1`.
First nextRunAt: `2026-10-08T05:32:37.789Z` (2026-10-07 22:32:37 PDT).
Readiness receipt: `imitation/t5/receipts/prerequisite-wait.json`.
Disable after the final report or if T4 fails/an upstream terminal blocker is
reported. This does not replace or modify the separate data/T4 schedules.

Latest scheduled check: 2026-10-08 05:42:49 UTC — T3-PASS absent on 01; who empty. T4 checked at 05:41:17 UTC and remains pending T3. Data worker reports active P16 scoring at 05:36:59 UTC, no terminal blocker. No T5 jobs launched; 10-minute continuation remains active.

## Coordinator lease update — 2026-10-08 05:45 UTC

Read binding `/mpac/sdicks02/cc/FLEET-SHARING.md` and
`reports/strategy_council_20260928/fleet/LEASED-HOSTS.md`. User explicitly
authorizes the seven leased hosts, superseding the earlier 09–18 exclusion
only for 09/11/13/14/15/16/18. Never contact 02/07/10/12/17.

Plan one run per GPU, after T3 and T4 PASS and verified stores:
- 04: main 2026100801.
- 11: main 2026100802 (lease cap 96 total Clasher processes).
- 13: main 2026100803 (lease cap 64).
- 14: noD1 2026100801 (lease cap 64).
- 08: GRU 2026100801 (keep potentially longer recurrence on a home host).

If copies are not ready, use at most two concurrent runs/GPU on 04/08 and
queue any remaining run; measure aggregate throughput without adding trials.
Data worker owns store copies; do not duplicate its transfer. Coordinator says
T3's P16 baseline process deadlocked and the data worker is fixing it. That
ongoing repair is not a terminal blocker; do not interfere with its processes.

Hub lease-readiness receipts inspected at 05:44:59 UTC: 11/13/14 all
qualified=true, data_copied=false, ready_for_gpu_training_on_c56_store=false.
T3-PASS still absent on this turn; no GPU jobs launched. Receipt SHA256:
- 11: a9e4814d0df5136ae10f73132f928e2770383b60c4b9ccf628ed9eee7ed1925a
- 13: 7e231a1af2dc6422e01fb8d3744e06199b2606c89dbacf3c0d2640b3948b3c6f
- 14: e9abe197e6a4cd5c65adb14e9c3444ee718defa8d6faf1d7a381ac4dcc48b2f2

Lease expiry is **2026-10-09 05:30Z**. Validate live leases before every launch;
stop before expiry, initiate planned checkpoint/exit by 05:00Z if still running.
Earlier reclaim requires checkpoint/exit within 30 min. Use only the existing
lease wrapper, which polls every minute and verifies descendant PIDs. Validate
the trainer's SIGTERM path exits after a checkpoint **without full dev scoring**
before deploying on leased hosts (current T4 loop would otherwise evaluate dev).
Preserve run/RNG/optimizer/sampler state for resumption on a home GPU.

On borrowed hosts all workload/env/cache/output paths stay inside
`/mpac/sdicks02/repos/clasher-lease/`. Source its env.sh and launch via its
run.sh; NEVER original fleet_run.sh or shared /mpac/sdicks02/env.sh there.
GPU interpreter: `clasher-lease/envs/clasher-gpu/bin/python`; store:
`clasher-lease/data/c56-store-v1`. Keep ≥8192 MiB GPU free and shared-host
Clasher RSS ≤64,000,000,000 bytes. Nice ≥10, count supervisors/loaders/shells,
reserve ≥2 supervision processes, and cap at min(lease cap,16) with console user.
Reserve hosts 16/18 have cap48; GPU-only09/15 cap8 and one loader worker unless
measured otherwise. No extra runs are authorized by extra capacity.
No roader repo/jobs/caches or shared env/tool/home changes. No builds/tests/
games/training/bulk transfer on05. Only owned small docs/results/receipts mirror.
