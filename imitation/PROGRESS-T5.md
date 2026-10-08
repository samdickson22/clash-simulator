# T5 v1 training and gate (a)

2026-10-08 09:15 UTC — **T4 SHAKEDOWN PASS; WAITING FOR THROUGHPUT PASS.** No T5 GPU jobs,
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

Next: verify T3-PASS, wait for T4 rerun PASS AND throughput-pass.json at
10-minute intervals, finalize qualifying code and freeze PREREG with its
exact hash/microbatch, then use the updated five-GPU allocation below.

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

Temporary same-thread continuation schedule (resumed by coordinator at07:44 UTC):
`scheduled-task:command:mcp:3edbde69-151b-4209-8cf7-c6c1eac260db:schedule-task:clasher-imitation-t5-continuation-20261008-v1`.
First nextRunAt: `2026-10-08T05:32:37.789Z` (2026-10-07 22:32:37 PDT).
Readiness receipt: `imitation/t5/receipts/prerequisite-wait.json`.
Disable after the final report or if T4 fails/an upstream terminal blocker is
reported. This does not replace or modify the separate data/T4 schedules.

Latest scheduled check: 2026-10-08 09:34:38 UTC — T4 shakedown PASS retained. throughput-pass.json absent; latest T4 progress still reports snapshot0924Z qualification underway. No terminal blocker or T5 jobs; continuation remains active.

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
coordinator now requires checkpoint AND exit completed by05:00Z. Trigger early
enough to meet that deadline, not merely initiate at05:00Z.
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

06:03 UTC upstream clarification: PROGRESS-data.md reports the 05:44–05:54
investigation found no deadlock: both spawned P16 workers advanced CPU and I/O
over 93.9 s. The idle parent waits for whole-partition results. No job was
restarted. This evidence supersedes the earlier coordinator suspicion of a
deadlock; await actual T3-PASS and do not intervene in data-worker processes.

## T3 training release received — 2026-10-08 06:43 UTC

Actual T3-PASS.json published06:42:32 UTC; passed=true. Mirrored with rsync -c
to `imitation/t5/receipts/T3-PASS-training-release.json`, SHA256
`6b335ec4470215922c1ff346da18535fe3f8e3eb9e88dfe109d16d1f86b9472c`.
Store/role hashes match the draft;805 exact round-trip perspectives and role
counts equality are true. Receipt records coordinator decision to release
training from qualified store/frequency baselines; P16 baseline remains an
A2 requirement. It explicitly has copies_status=pending and p16_baseline=pending.
Require separate `T3-COPIES.json`/target checksum receipts before using a host;
require `T3-P16-BASELINE.json` before claiming A2. Qualification alone does not
prove a target store is ready. T4 owns the next shakedown; do not duplicate it.
Earlier pending-T3 entries above are historical. No T5 code freeze or fitting.

## Hard stop: T4 shakedown failure — 2026-10-08 07:23 UTC

Verified04 label `t4-shakedown-20261008T0714Z`, launcher2393301, exited1
at07:19:29 UTC. Eight subset-training steps completed65,519 sampled rows,
then dev_joint_nll failed in features.build_row:
`ValueError: more than 64 visible entities: outside v6 contract`.
Overfit and final dev evaluator did not complete. This is not T4 PASS.

Per user hard rule, T5 stopped and its temporary schedule is confirmed
enabled=false, nextRunAt=null. T4 schedule/source/jobs were not changed,
restarted or duplicated. T4 owns repair and requalification.
Small log, numeric exit and status.json mirrored with rsync -c into
`imitation/t5/receipts/t4-shakedown-failure-20261008T0714Z/`; evidence hashes
recorded in prerequisite-wait.json. No checkpoints or stores copied to05.

Observed T4 diagnostics (not T5 results or a passing shakedown): last measured
loader-inclusive2,131.94 rows/s, step-only2,902.05 rows/s, GPU peak allocated
530.78 MiB, reserved734 MiB; subset total loss9.73854→9.58864. Entire failed
T4 wrapper wall299.82s, CPU318.72s. No full-run throughput conclusion.
T5 GPU compute remains0; no selected checkpoints, frozen PREREG, heldout
scores or gate verdict exist. Resume T5 only after the coordinator resumes it
and T4 publishes a passing shakedown; preserve this failure evidence.

## Coordinator resume — 2026-10-08 07:45 UTC

User explicitly resumed T5 and requested re-enabling continuation. The new
gate is T4 rerun `t4-shakedown-20261008T0727Z`, launcher2398593 on04. PASS
permits T5 preparation/freeze and the five planned runs; **a second failure
must disable T5 continuation and stop again**. The first failure remains
preserved history, not a reason to stop this resumed attempt.

Read actual rerun status at07:44:50 UTC: verified PID2398593 live at nice10,
stage subset (full dev validation), no exit receipt. No duplicate job launched.
T4 fixed the cap to128 entities, added a192-token bucket and retains all rows.
It also applied the predeclared tile-width64 latency fallback; rerun command
confirms --tile-width64. Current model has2,254,938 parameters. PREREG draft
records both technical changes and independently matched04/05 source hashes.
Final frozen PREREG must bind the exact staged T5 code before T5 training;
pending T4 hashes are not the final T5 freeze.

Data-worker07:37 report:04/08/11/13 copies verified;14 copy running. T5 will
check authoritative per-host receipts/live leases before launch. Data worker
retains copy ownership. One run per04/08/11/13/14 remains the plan.

## Additional start gate — coordinator update 2026-10-08 08:45 UTC

Require `imitation/model/receipts/throughput-pass.json` **in addition to** T4
rerun PASS. Receipt is currently absent. T4 owns the larger-microbatch and
vectorized loader/evaluator work, targeting≥8k loader-inclusive rows/s.
Do not launch any of the five runs on the old snapshot or microbatch64 simply
because the shakedown passes. Read receipt contents/provenance, bind exact
qualified code hash and microbatch in frozen PREREG, and verify remote source
hashes. Receipt-covered source changes require matching requalification.
T5 ablation/scoring extensions must also be in the executable manifest.

The 05:00Z Oct9 leased-host deadline means checkpoint and EXIT by that time,
before lease expiry05:30Z. Plan using measured train/dev/checkpoint timings;
set the graceful-stop trigger with enough lead time and verify completed
checkpoint/exit. Resume unfinished runs with unchanged recipe/state on
home01/04/08 as capacity permits (01 only if perception not using its GPU).
Direct LAN checkpoint transfer with hashes, never via05. Reclaim still
requires checkpoint/exit within30min through existing lease-local wrapper.
No T5 fitting, performance probes or held-out scoring has started.

09:15 UTC qualification: T4 rerun `t4-shakedown-20261008T0727Z` PASS,
completed09:05:52.560799Z, exit0. Verified local summary bound to immutable
T3 certificate, SHA256 `5cda727dacb9743c922dc8f36aba13124d0fb30133b95f0cf75ab56f9d1f303f`.
Status receipt SHA `d7fbbd99f3ea9d9cf3a644269587d1d1d9d7b2c3f85e2e2925734ccf9ed4414e`.
T4 completed subset, overfit, full dev metrics/calibration/bootstrap/export.
This satisfies shakedown only; throughput-pass.json still absent. Do not
launch T5 or freeze old source/microbatch while T4 optimization is underway.
