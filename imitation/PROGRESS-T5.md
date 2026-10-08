# T5 v1 training and gate (a)

## Current status — 2026-10-08 13:34 UTC

**All five fresh entrants are active; main02 loader starvation is fixed.**

Latest health check **13:34 UTC**: all five current trainer identities verified,
logs advancing, no exits or lease stop reasons. Steps04/11/13/14/08:7477/2101/8230/7060/266.
Latest25-step loader-inclusive rows/s:7276/8163/7839/7540/242.
GPU free19688/17332/17340/16928/8701MiB. Main02 has resumed epoch1 training after its first dev pass;
no new dev scores this poll. Shared13/14 PSS7.75/10.44GB; full11 diagnostic
PSS71.48GB remains uncapped by the shared-host64GB rule. Process occupancy
5/7/4/4/5 including monitoring; no console users; live leases valid.
No job/source/recipe changes or model held-out inference this poll.
Receipt `t5/receipts/status-20261008T1334Z.json` includes current checkpoint hashes.
Existing10-minute schedule continues; healthy jobs remain active.

Authoritative current identities and exact continuation commands:
`t5/receipts/active-runs-20261008T1308Z.json`. Never use the superseded PIDs or
restart any active run. Check identities/exits before a future resume and refresh
its checkpoint SHA and unused label. All scientific sources/recipe remain frozen r2.

| Run | Host | Current trainer | Step | Recent loader-inclusive rows/s | GPU free MiB |
|---|---|---:|---:|---:|---:|
|main01|04|2498867|7477|7276|19688|
|main02|11|972158|2101|8163|17332|
|main03|13|3494088|8230|7839|17340|
|noD1|14|3481715|7060|7540|16928|
|GRU|08|3548451|266|242|8701|

Latest uncalibrated EMA dev joint NLL: main01 .3629642253437192 atstep5638;
main02 .4401884629339961 atstep1880; main03 .3561387059512377 atstep7518;
noD1 .36447309169620945 atstep5638. GRU has not reached its first dev pass.
No selection, calibration or held-out inference. Current resource and checkpoint
hashes are in the latest health receipt above.

**Main02 operational loader recovery.** Old trainer948307 stopped12:50:58Z at
step967, checkpoint SHA bb6e4ab771dfb1fb97fc69c0162c6f8df7e2aa11c78205ebc105577cf45febad.
Same checkpoint/output resumed12:58:37Z, first new step968, now606 updates later.
No discarded or repeated update, seed or recipe reset. Actual loader workers4
and original qualified BatchedStore without per-batch mmap eviction are explicit
in the launcher/operational log; immutable parent args retain workers1 for the
r2 guard. Old1250inclusive rows/s improved to7838 cumulative after resume and
8064 latest25 steps. The loader was runnable but dominated by kernel page faults;
bounded1/original1/original4 diagnostics took60.76/26.06/19.61s for identical65536
train rows, including startup and tensor hashing. Synthetic full checkpoint replay
was bit-exact, including optimizer/EMA/scheduler/sampler and all RNG state.
Restart gap459s; prior loader delay estimated90.6minutes against measured resumed
throughput (descriptive counterfactual, not a precise idle-time measurement).
Initial import-path and adapter CLI errors failed before real updates and are
retained. `t5/receipts/main02-loader4-recovery.json` documents the recovery.

Main02 label `t5-v1-main-2026100802-r2-fresh-loader4-v2`, supervisor972156.
Operational freeze SHA6a62d14dc5739f91277085d1d4f491864f5e283eba52ed8bd0b19fa0cdaf0465.
Exact command: `t5/receipts/main02-loader4-launch-v2.json`.
Amendments: `gate-a/amendments/main02-loader4-20261008.md`, `main02-loader4-cli-v2.md`.

**Separate GPU cache headroom recovery.** noD1 supervisor stopped it12:52:05Z
after a5972-row epoch-tail batch raised reserved cache to42070MiB, although
allocated peak was30132MiB. Its full step5638 state was retained. Main01 had
5480MiBfree and was identity-verified/checkpointed/stopped13:02:25Z atstep6018.
Both resumed13:07Z without losing updates. An explicit resource-only adapter
sets CUDA caching-allocator fraction0.75; all model/data/training math and
micro7168/effective8192 remain unchanged. Synthetic GPU checkpoint replay was
bit-exact; unfitted real tail probes left>16GiBfree with parameters unchanged and
no optimizer state created. noD1 completed dev and resumed atstep5639; its low
initial cumulative rate includes that dev pass, not a renewed loader stall.

Labels `t5-v1-main-2026100801-r2-fresh-gpu-headroom` (supervisor2498854) and
`t5-v1-noD1-2026100801-r2-fresh-gpu-headroom` (supervisor3481713).
Operational freeze SHAc710ea1b34d73931c2bdc52f18834898ecd2473e9766839a0c482414ee9638a7.
Exact commands: `t5/receipts/gpu-headroom-launches.json`; validation
`t5/receipts/gpu-headroom-validation.json`; amendment
`gate-a/amendments/gpu-headroom-20261008.md`. Main03/GRU are unchanged. Recovery receipt `t5/receipts/gpu-headroom-recovery.json`
records restart gaps294.6s/917.3s (main01/noD1), zero lost updates and validation
compute24.5wall/23.99CPU seconds. noD1 recent25-step inclusive throughput7693
confirms normal loader progress after the resumed dev pass.

Parent r2 PREREG SHA b5bace9160f97f12b880f3e01471642ea0780c8ae2280deed7fd49f5a10fee02;
manifest2854ce1f96fdd2fcc04dd0e6ef15dce3435758ec40369a80bba29b1a1e29db13.
No receipt-covered or frozen scientific source was changed. Additional executable
adapters and validation files were separately frozen and staged hashes checked
before each continuation. Preserve all operational provenance in final results.
Leased04:20Z Oct9 timers remain; checkpoint AND exit by05:00Z, directLAN migration
before lease expiry. Scheduler remains10min; next13:14:39Z. All older PID/worker/headroom claims
below are historical and superseded by this section.

Historical prior health sample follows:
Latest health check **12:45 UTC**: all five fresh trainer identities verified;
no exits or lease stop reasons. Steps04/11/13/14/08:5181/921/5541/5264/177.
Losses5.01870/6.34117/4.93473/5.08176/8.13309; cumulative loader-inclusive rows/s
7035/1251/7529/7154/241. Shared13/14 PSS14.24/7.07GB; full11 diagnostic PSS10.37GB.
Minimum GPU free8705MiB. No source, recipe, worker or job changes.

Latest fresh uncalibrated EMA dev joint NLL atstep3759 (two epochs) remains:
- main2026100801:0.3811127407615681.
- main2026100803:0.3825878528271366.
- noD1:0.3853155954656844.
Main02/GRU have no dev result yet. No selection, calibration or held-out scoring.
Host11 advances atabout82steps per10minutes; preserve exact run and plan home
migration before lease end if needed. Latest checkpointsstep5000 on04/13/14,
step170 on08. Hashes: `t5/receipts/status-fresh-r2-20261008T1245Z.json`.
Guarded command patterns remain in `t5/receipts/resume-fresh-r2-20261008T1145Z.json`;
refresh to latest checkpoint/hash and verify own exit before any resume.
Next scheduled poll12:54Z. Existing jobs continue without intervention.

Latest verification11:06Z: all five fresh logs begin atstep1/8192rows and
advance without exit receipts. Shared13/14 PSS13.36/14.58GB versus RSS-sum15.08/
18.35GB, safely below64GB. Full11 PSS7.72GB is diagnostic, with no64GBcap.

| Fresh run | Host | Step | Loss | Loader-inclusive rows/s |
|---|---|---:|---:|---:|
|main-2026100801|127x04|102|8.38284|7078.98|
|main-2026100802|127x11|73|8.84680|5242.82|
|main-2026100803|127x13|105|8.46122|7616.80|
|noD1-2026100801|127x14|102|8.37505|7519.13|
|gru-2026100801|127x08|3|9.79958|245.30|

Fresh curves are in `t5/receipts/status-fresh-r2-20261008T1106Z.json` and each
fresh run's `train.jsonl`. No fresh dev result or selected checkpoint exists yet.
A resume command cannot point to a fresh checkpoint until one is saved; use
`launches-r2-fresh.json` arguments with a fresh unused label and add
`--resume` only after verifying the latest complete checkpoint's r2 hashes and
old process exit. Never use superseded attempts' checkpoints for these entrants.
Next scheduled poll11:14:34Z (10-minute cadence).

**Coordinator-directed fresh r2 starts are now the five gate entrants.**
Fresh launches occurred11:04:21–24Z on04/11/13/14/08. All prior r1 and resumed
r2 segments are excluded from checkpoint selection and retained for the audit
and compute accounting. No calibration or held-out inference has occurred.

Correction to the coordinator's assumed state: main01/main02 had stopped near
10:42Z to migrate checkpoint state, then resumed at10:45Z; they did not initialize
fresh atthat time. All five were still running at11:00Z. Following the explicit
new instruction, verified trainers were SIGTERMed11:00:55–11:01:14Z and exited0,
preserving all artifacts. Their last steps were2190/1837/892/878/27. Only the new
fresh output directories below participate in eventual dev-only selection.

| Entrant | Host | Label | Launcher / trainer PID |
|---|---|---|---|
| main2026100801 |04|t5-v1-main-2026100801-r2-fresh|2471647 /2471660|
| main2026100802 |11|t5-v1-main-2026100802-r2-fresh|948305 /948307|
| main2026100803 |13|t5-v1-main-2026100803-r2-fresh|3494086 /3494088|
| noD1 seed2026100801 |14|t5-v1-noD1-2026100801-r2-fresh|3456814 /3456816|
| GRU seed2026100801 |08|t5-v1-gru-2026100801-r2-fresh|3548438 /3548451|

Exact commands: `t5/receipts/launches-r2-fresh.json`; **none includes --resume**.
Home outputs: `/mpac/sdicks02/tmp/t5-20261008-r2/fresh-runs/RUN`.
Lease outputs: `/mpac/sdicks02/repos/clasher-lease/t5-20261008-r2/fresh-runs/RUN`.
All use the existing, hash-verified r2 source snapshots and manifest
`2854ce1f96fdd2fcc04dd0e6ef15dce3435758ec40369a80bba29b1a1e29db13`.
Resource-r2 PREREG remains
`b5bace9160f97f12b880f3e01471642ea0780c8ae2280deed7fd49f5a10fee02`.
Microbatch7168/effective8192/workers1 and exact qualified T4 sources unchanged.
Fresh-start addendum SHA:
`46f7543a70222480a7b89dbd998832e5b8c04cfe0a17eb6e076d3c3ef4ebdc40`.
`t5/receipts/fresh-r2-freeze.json` records this and the exact launch plan before
any fresh launch. No new scientific trial or changed statistical rule.

PSS lease supervisor SHA:
`00cdaa8ad3be41a0a85481d318ad03920b87e2564ab541e8f9a9d5bf801d246f`.
Owned implementation: `t5/operations/lease_watch_pss.py`. Regression checks on04
passed for PSS-vs-RSS accounting, exact field parsing, stale/disappeared PIDs,
fail-closed missing PSS, shared-host scope and real smaps_rollup. It sums PSS over
the verified owned process tree; RSS-sum is retained in state/log/peak receipts.
64GB applies only to shared13/14/16/18, not full11 or home04/08. R2 mmap lifecycle
remains unchanged. Installed in lease-local wrappers11/13/14/16/18 with originals
retained. New T5 supervisors already use PSS; any pre-existing non-T5 supervisor
on16/18 retains its loaded old code until its owner restarts it. T5 does not
signal another worker's processes.

All five host preflights passed with source/role/asset hashes, idle GPUs, empty
who, valid leases and process budget reserved. Live11 monitor shows no PSS cap;
13/14 show64000000000. No lease stop reason or new exit receipt. Source training
files were not changed for this operational wrapper correction.

The earlier progress/throughput/dev numbers below belong to superseded attempts.
Fresh curves/dev scores will be recorded independently. No selected checkpoint
yet. CPU/GPU/wall accounting must include superseded attempts and operational
validation separately. Borrowed timers still trigger2026-10-09T04:20Z and must
finish checkpoint/exit by05:00Z. Ten-minute continuation remains enabled.

## Superseded status — 2026-10-08 10:55 UTC

Latest health check **2026-10-08 10:58 UTC**: all five trainer PID identities
verified and advancing; no exit receipts or lease stop reasons. Steps04/11/13/14/08
are2046/1812/722/716/21. New main01 step2000 and GRU step20 checkpoints exist.
Leased wrappers report3 processes each and RSS13.6–18.4GB. No new dev result
beyond main01's0.43433783253200153; no held-out inference. Compact receipt:
`t5/receipts/status-20261008T1058Z.json` (includes current process CPU observations).
Existing jobs continue; no launches, source changes or scientific changes this poll.


**All five declared runs are active under frozen resource revision r2.**
T3 training release, qualifying T4 rerun, T4 throughput receipt and all five
store copies passed before launch. Historical pending/failure notes below
are an audit trail, not current launch instructions. No calibration or model
held-out inference has occurred. Gate A1–A4, final selected checkpoint hashes
and `RESULTS-v1-offline.md` remain pending training completion.

Initial PREREG froze at10:21:37Z, before initial training:
`71335325d383282bfe8effd6bf550ef322713520bb6119b8ed363e3869835cce`.
The resource amendment froze at10:41:48Z, before any retry:
`b5bace9160f97f12b880f3e01471642ea0780c8ae2280deed7fd49f5a10fee02`.
Active r2 executable manifest:
`2854ce1f96fdd2fcc04dd0e6ef15dce3435758ec40369a80bba29b1a1e29db13`.
Both immutable registrations live under `reports/strategy_council_20260928/imitation/gate-a/`,
with r2 in `resource-r2/`. The unchanged T4 qualified source hash is
`301caa1003ab47eadc3f56973ec5398bed4d166dc1a0163d213e60a61854959d`;
throughput receipt SHA is `5c7e83bacc92096a30520ccdaf002321b753542a7afc489e57183df865fc7229`.
Microbatch7168, effective batch8192, full128 entities and tile_width64 remain fixed.

### Runs, packing and curves

One run per GPU. T4 measured single12154.126 loader-inclusive rows/s versus
11394.330 aggregate for two concurrent runs. Resource-bounded production uses
one loader worker and drops copied read-only mmap pages; it is slower than the
qualification benchmark. Current reported inclusive throughput includes the
resumed segment and, for main01, its first dev evaluation.

| Run | Host | Launcher / trainer PID | Step | Loss first → latest | Inclusive rows/s |
|---|---|---|---:|---:|---:|
| main2026100801 |04|2466890 /2466903|1883|9.62873 →5.64667|6014.63|
| main2026100802 |11|944260 /944262|1767|9.76893 →5.65169|4773.38|
| main2026100803 |13|3488684 /3488686|548|9.59941 →6.92137|7349.60|
| noD1 seed2026100801 |14|3452625 /3452627|552|9.55094 →6.65031|7388.14|
| GRU seed2026100801 |08|3544737 /3544750|16|9.78977 →9.75399|241.28|

Main01 first uncalibrated EMA dev joint NLL: **0.43433783253200153** atstep1880.
Other dev values are not yet measured. These are interim curves, not checkpoint
selection or gate results. Train epochs contain15,400,370 sampled rows. Atcurrent
GRU speed, one epoch projects to17.7h and12epochs to8.9days before evaluation;
early stopping may shorten this. Exact differentiable32-row iid contexts account
for repeated trunk work. Keep this same run on home08; do not alter its recipe.

### Technical failures and recovery

Initial 13/14 runs exceeded the lease wrapper's aggregate64GB RSS limit and
checkpointed/exited atsteps61/63. Initial GRU OOMed atstep3 without a checkpoint;
its two completed steps and failure logs remain intact. This is one recorded
technical restart of the same declared seed, not an extra trial. Main01/02 were
gracefully stopped at1481/1452 to use one consistent frozen r2 manifest.

R2 uses one loader, bounded read-only mmap residency, and1024-row historical
GRU encoding chunks. All20 T4 qualified source files remain byte-identical.
Eight behavioral tests passed; 4→1worker synthetic resumes were bit-exact for
model/EMA/sampler across all variants. A full8192-row real-train GRU forward/
backward passed with **no parameter update**, peak reserved37484MiB. Four
checkpoint migrations preserve every payload field except explicit hash metadata
bit-for-bit. See `t5/receipts/resource-validation-r2.json`, `r2-migrations.json`
and `gate-a/amendments/resource-r2.md`.

At10:50Z aggregate trainer/loader RSS was12.1–19.1GB; leased wrapper states
reported3 processes each and no stop reason. GPU free at10:55Z was17.3–18.3GiB
on main/noD1 and8707MiB on08. GRU checkpointstep10 SHA:
`6302b86e2e212b96598eae87c1b78ecce401c6d56c3eaaa962bb311ea0225117`.
This is a recovery checkpoint, **not** a final selected checkpoint.

### Paths, resumption and continuation

Exact launch commands/arguments: `t5/receipts/launches-r2.json`.
Exact candidate resume commands and current checkpoint paths:
`t5/receipts/resume-r2-20261008T1055Z.json`. Never execute them while a run is
live. Check its own verified PID, current label log/exit and latest complete
r2 checkpoint first; retain optimizer/RNG/sampler state and use a fresh label.
The old r1 `resume_template` fields were superseded because they had stale flags.

Home source: `/mpac/sdicks02/tmp/t5-20261008-r2/source`.
Lease source: `/mpac/sdicks02/repos/clasher-lease/t5-20261008-r2/source`.
Main/noD1 outputs still append under each host's `t5-20261008-v1/runs/RUN`;
GRU output is `/mpac/sdicks02/tmp/t5-20261008-r2/runs/gru-2026100801`.
Labels are `t5-v1-RUN-r2`. Home wrapper logs/receipts are under
`/mpac/sdicks02/jobs/clasher`; lease wrapper logs/state/receipts under
`/mpac/sdicks02/repos/clasher-lease/jobs`. Each run retains `train.jsonl`,
`segments.jsonl`, checkpoints and later completion receipts. Process CPU/wall
and GPU-allocated wall accounting remains provisional while jobs are live;
final accounting must include original segments, failures and validation separately.

Leased timers trigger **2026-10-09T04:20:00Z**, allowing40min before mandatory
checkpoint AND exit by05:00Z. Reclaim wrapper remains authoritative. Before
lease expiry, move required completed or interrupted checkpoints directly over
LAN to an available home GPU host; never05. GRU on08 can outlast the lease.
Use `who` and the fleet console-user helper plus all-worker occupancy before
any new launch; preserve all host caps, RSS limits and GPU headroom.

Current monitoring receipts: `t5/receipts/status-20261008T105055Z.json` and
`status-20261008T105510Z.json`. The same-thread10-minute continuation remains
enabled; next scheduled check11:04:33Z. Healthy jobs should continue quietly.
Disable the schedule when the final report is complete or an applicable upstream
terminal blocker is explicitly reported. The historical T4 failure is not a blocker.

## Historical audit trail (superseded status snapshots)

2026-10-08 10:02 UTC — **FIVE RUNS LAUNCHED; TECHNICAL RESOURCE RECOVERY.** No T5 GPU jobs,
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

## T5 implementation after throughput release

T4 throughput PASS at09:40:36 UTC; receipt SHA256 `5c7e83bacc92096a30520ccdaf002321b753542a7afc489e57183df865fc7229`. Canonical qualified source hash `301caa1003ab47eadc3f56973ec5398bed4d166dc1a0163d213e60a61854959d`; all20 files verified on05 and copied read-only from T4's immutable snapshot into the fresh04 T5 source. No T4 source changes. Qualified microbatch7168, effective8192, workers4; one/GPU12154.126 rows/s vs two/GPU11394.330 aggregate. No duplicate throughput benchmark.

Owned extensions under imitation/t5: explicit injection around unchanged qualified trainer, noD1 removal, exact sliding32-row GRU contexts with differentiable activation checkpointing, frozen-role/content guards, dev calibration and once-only heldout claims/statistics, analysis from committed statistics only. Five synthetic behavior tests PASS on04 (0.645s); resume/signal integration and final registration are still pending. No real T5 fitting or heldout scoring yet. GRU recomputes history under current weights and retains iid endpoint sampling; its throughput is not the main's qualified throughput and will be measured from the declared run.

Validation staging: 04:/mpac/sdicks02/tmp/t5-20261008-v1/source. No training PID, selected checkpoint, frozen PREREG, or results yet.

## Runs launched / resource failures — 2026-10-08 10:36 UTC

Frozen PREREG SHA71335325d383282bfe8effd6bf550ef322713520bb6119b8ed363e3869835cce; manifest934516a0ae3a2d950a676d6c35f0d310ead7ad951ec2c776967ccbd21a7e7f9f. All five launched10:25Z, one/GPU. Exact command/argv/source/output/launcher PID/resume template for each is in imitation/t5/receipts/launches.json.

04 main01 and11 main02 remain active. 13 main03 and14 noD1 were automatically checkpointed/stopped by lease wrapper for64GB aggregate RSS excess (153.297/154.110GB peak counted across processes); exit0, own PIDs no longer exist. Main03 checkpointstep61; noD1 latest checkpoint pending audit. GRU08 completed2steps, then CUDA OOM in step3backward at10:26:46Z; exit1, no checkpoint yet. Original outputs retained. No model heldout inference.

Technical amendment recorded before retry: gate-a/amendments/resource-r2.md. Developing RSS-bounded read-only mmap lifecycle with one loader and smaller GRU history-only1024chunks (primary7168/effective8192 unchanged); no T4 files edited. Validate old4worker -> new1worker exact state replay and unfitted full-batch GRU memory on08, then freeze revised source before any continuation. Healthy04/11 will be gracefully checkpointed for provenance-only migration to one coherent r2manifest; every training tensor/RNG/optimizer/sampler state verified unchanged. The GRU same-seed restart is solely due to its recorded technical OOM. Do NOT launch duplicate jobs or use historical no-T5-job notes above as current status.
