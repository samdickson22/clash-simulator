# T11 v2 store and training

2026-10-08 13:34 UTC: **STORE AND BOTH COPIES PASS; BOTH FRESH SEEDS TRAINING.**
No held-out scoring, commits or data deletions. Training is not complete.

Current training (supersedes the historical copy/build notes below):

| Host | Run label | Supervisor / trainer / loader PIDs | Start UTC | Step / rows at13:34:19Z | Loader-inclusive rows/s |
|---|---|---|---|---|---:|
|127x16|t11-v2-main-2026100821-v1|3555507 /3555509 /3555662|13:08:19Z|299 /2,449,408|1,610.4|
|127x18|t11-v2-main-2026100822-v1|1068869 /1068871 /1068993|13:07:40Z|356 /2,916,352|1,868.2|

Each PID independently verified by UID, command line, parent and start ticks
in `t11/receipts/status-127x16-20261008T1334Z.json` and matching127x18.
Both are fresh registered seeds, one per GPU, micro7168/effective8192,
one unchanged T5 bounded loader, six epochs maximum, dev patience3.
Initial train loss declines9.9553→7.5264 and9.7748→7.5218, respectively;
last20-step mean losses7.5828/7.4941. Both remain in epoch0 and progressed
138/150 steps since13:24:25Z. These are weighted minibatch losses, not dev NLL. No full epoch/dev
curve, selected checkpoint or checkpoint file yet (first regular save step1000).

At13:34:19Z: all resource/live-lease checks PASS. Three borrower processes
per host, all nice10; total PSS19,423,000,576/19,622,871,040 bytes below64GB.
GPU free17,340/17,252MiB, above8192MiB. No reclaim/refusal, console user,
stop reason or exit receipt. Leased deadline argument independently verified
`--stop-at 2026-10-09T04:20:00Z`; must checkpoint AND exit before05:00Z.

Observed loader-inclusive throughput is materially below the T4 qualification;
do not report optimizer-step throughput as achieved training throughput.
Both optimizer steps reach~12.3k rows/s while trainers wait for their active
loaders. At13:14:57Z the loader processes had physically read79.66/73.48GB,
consistent with large random mmap I/O contributing to the gap. No recipe,
sampler or qualified-loader change; monitor sustained progress/throughput.

Both copies verified259/259 artifact hashes,243,896,560,373 bytes each, and
exited0 (16 at13:07:50Z;18 at13:07:18Z). Receipts `t11/receipts/copy-127x16.json`
and `copy-127x18.json`, with original store/PREREG/source hashes. Preflight
PASS receipts are adjacent. Hub pipeline r2 exited0 at13:08:21Z after exactly
these two launches; never rerun it. `pipeline-state.json` contains exact
trainer argv and wrapper commands for both runs.

Copy receipt SHA256 (16 then18):
`d437cab45022e14c9433db1dc731016e9d967d33fc45d55a5c09af8f215ca8e9`,
`acad9c49bd58d65be64a208df6cb0a072afe305adcd1c905bb4175052a3c3d8e`.

Run directories: `/mpac/sdicks02/repos/clasher-lease/t11-20261008-v1/runs/`
`main-2026100821` (16) and `main-2026100822` (18). Wrapper logs/states/exits:
`/mpac/sdicks02/repos/clasher-lease/jobs/<run-label>.{log,state.json,exit.json}`.
Frozen source: sibling `source/`; copy/store paths unchanged. Resume is NOT
currently executable because no checkpoint exists yet. On first durable save,
record its SHA and a concrete `--resume` command using the exact argv above.
Never restart these active runs. Migration requires verified old exit plus
direct-LAN checksummed optimizer/scheduler/EMA/RNG/sampler state and logs to
available home01/04/08; remove only the leased stop-at argument on home.
No additional fitted trial and no bulk artifact on05. Eval remains embargoed.

`reports/strategy_council_20260928/imitation/data/receipts/T11-STORE-PASS.json`
SHA256 `0e14fefa47388dc0f8a436d2c6415224ac30af1cc3aed98a9092485deaf4b524`.
Final count366,365 eligible perspectives /177,371,708 packed rows, with exact
3,664-perspective round trip, eligible-role equality, unchanged v1 assignments
and zero train/held-out match leaks. Counts in the table below are now final.
Full-source frequency fitting used228,417,927 supervised train rows.
V2 dev frequency joint NLL0.350140699 (C560.439491836, S1220.323766206),
card NLL1.451014373, tile NLL4.191802055. These are baseline diagnostics,
not model results. Dev receipt SHA
`83c609eb335de768076a96a37a2d8937f36e0a5e508ab501c0d2040835fa7337`.

Frozen at2026-10-08T12:31:15.471872Z, before training or held-out scoring:

- `imitation/gate-a-v2/PREREG.md`: SHA
  `115ab2f62c999d96b908855ab6e45bade4d9573308a222659821f65a76e42749`.
- Executable manifest: SHA
  `a4801df32d4a546ed7df07faf070a138d4075cf4db6c193d38373f9194ff2e44`.
- Registration includes the output-identical padding amendment and its proof.
  Do not change frozen source files or registration in place.

Historical lease copy identities (completed; startup measurements):

- 127x16: `t11-v2-store-copy-127x16-v1`, supervisor3542706/child3542708,
  rsync3542834/ssh3542835, started12:31:18Z. Independently measured tree
  PSS2,877,196,288 bytes, four processes, all nice10. GPU48,666MiB free.
- 127x18: `t11-v2-store-copy-127x18-v1`, supervisor1056060/child1056062,
  rsync1056195/ssh1056196, started12:31:21Z. Independently measured tree
  PSS2,876,991,488 bytes, four processes, all nice10. GPU48,577MiB free.

At12:39:25Z both live shared leases remain valid through05:30Z Oct9, no
reclaim/refusal, zero console users, cap96, no wrapper stop or exit receipt.
No other borrower jobs were present in the full same-user process listing.
Monitoring evidence: `t11/receipts/monitor-127x16-20261008T1240Z.json` and
the matching127x18 receipt (filenames rounded to the monitoring interval).
Hub pipeline r2 verified launcher3613309/Python3613335, nice10; no duplicate.
Destination metadata totals2,423,052,910 bytes on each host. Rsync is doing
its source checksum pass before payload transfer: verified hub senders
3614282/3614340 each read137,501,661,024 bytes at12:38Z and accumulated over
five CPU minutes. Both sender identities were checked against the exact v2
source path and current UID, then their nice values corrected0→10. No restart,
signal, source change or frozen-code change. Do not mistake this checksum
phase for a stalled copy or duplicate it.

Historical continuation recheck13:04Z: hub authoritative state was `copies`, both
registered seeds not yet launched. Array rsync has ended on both hosts;
destination243,896,580,853 bytes each. The original copy drivers are hashing
all259 explicit artifacts: both have logged progress through file200, with no
mismatch/failure. Full checksum/copy PASS receipts remain pending; complete
payload size alone is not verification. Hub source directory243,898,128,284
bytes includes builder metadata excluded from the explicit transfer list.
Independent full borrower-tree PSS at13:04:22Z is2,872,087,552/2,873,167,872
bytes, now two processes each (verified original supervisor/driver), no copy
exit or trainer state. All live lease, process cap (including two monitoring
headroom processes), PSS, nice10 and GPU headroom checks PASS.
Receipts: `t11/receipts/status-127x16-20261008T1304Z.json` and matching127x18.
The T11 read-only `status_remote.py` now monitors copy/training wrappers and
all borrower descendants in one snapshot, without store/checkpoint reads.
Original copy drivers3542708/1056062 and supervisors3542706/1056060 retain
their labels/PIDs/nice10. Live leases and console/GPU headroom verified13:04Z,
no reclaim/refusal. GPU48,666/48,577MiB free, zero utilization, zero console
users. Hub launcher3613309/driver3613335 independently verified active/nice10.
No failure or duplicate launch. Pipeline owns the pending guarded launches.
Rows/s, curves, checkpoint hashes and concrete resume commands remain pending
actual training/checkpoint creation. The04:20Z stop timer/05:00Z exit deadline
and v1-publication/selection/calibration embargo remain unchanged.

Final report renderer now implemented: `t11/report.py`, standard library only,
consumes both completed runs plus sealed selection/release and all four
analysis/statistics completion artifacts. It preserves primary selection,
PASS/FAIL/N/A and original estimates/CIs; computes only descriptive OOD gaps.
Synthetic-only validation on01 PASS at12:45:18Z, including changed-v1-report
rejection and failed-primary/passing-secondary preservation. All fixtures
retained on01; no real model or held-out data touched. Receipt
`t11/receipts/report-renderer-validation.json` SHA
`5222384a76aa58d5e20e4130819fd91e31db8704e90416fce2969fabf61cdbfe`.
Reporting-only addendum `gate-a-v2/AMENDMENT-report-renderer.md` and separate
`report-renderer-freeze.json` frozen12:45:57Z before training/eval. Renderer SHA
`521a4a159206cfe9156e810ac553bb250db6d326879c4e6ede960caa1fe9176a`.
Original scientific manifest/PREREG/source files remain byte-identical.
Final invocation on a compute host, after actual completion, uses
`python -B imitation/t11/report.py --manifest MANIFEST --selection SELECTION
--release RELEASE --analyses SEED21_EVAL SEED21_OOD SEED22_EVAL SEED22_OOD
--statistics` followed by their four `complete.json` paths, then
`--runs main-2026100821=RUN21 main-2026100822=RUN22 --output RESULTS-v2-offline.md`.
These placeholders become concrete only after sealed result paths exist.

Both training wrappers enforce64,000,000,000-byte PSS caps. Completed copy
receipts, guarded launches and independently observed steps are recorded in
the current status above. No completed dev curve or selected checkpoint yet.
Continuation schedule remains enabled every ten minutes in this same thread.

Latest: production builder exited0 at12:23:41Z, 1,986.35s build wall. All
8,751 units /3,664 sampled perspectives pass exact round trips; column hashes
complete. Root store manifest SHA
`7180964c1d470807a97ad7a990ac8eb145fb25d15f1c95edf165b3f87743d20f`.

The first baseline attempt exited1 at12:25:30Z on two S122 dev play rows with
duplicate **illegal token0 padding slots**. Dev audit: two duplicate rows,
zero duplicate nonzero/legally selectable/labeled tokens. No model fitting
or held-out scoring. Original counts/logs retained; store unchanged. The
T11-only private baseline view imports T5 unchanged and assigns unique dummy
IDs only to zero-mass masked padding slots. Proof on both affected rows plus
128 ordinary dev rows: all four NLL statistics exactly equal T3 formulas;
ordinary rows equal unchanged T5; source bytes unchanged; nonpadding duplicates
still rejected. Amendment: `gate-a-v2/AMENDMENT-padding-baseline.md`; evidence:
`t11/receipts/frequency-padding-validation.json`.

Counts SHA remains
`fef76fcb1dd5eac5cd1ac51c72244afe06eaa22daddd53eba1c6a9520640d752`.
Both failed r1 supervisors exited1; no verified process was killed. Their
state is preserved as `pipeline-state-before-padding-fix.json`.
Fresh continuations (supersede the waiting r1 labels described below):
`t11-store-finish-20261008-r2` launcher3613302, and
`t11-launch-pipeline-20261008-r2` launcher3613309, explicitly using
`--finish-label t11-store-finish-20261008-r2`. Counts are reused, only the
interrupted dev baseline is recomputed. No store rebuild or fitting retry.
Current authoritative state remains `t11/receipts/pipeline-state.json` on01.

T11-owned dev selection/calibration, embargoed once-only scoring, separate
C56/S122 cohort analysis, and exact-eligible-P16 baseline entry points are
implemented. Scoring/selection negative guard tests PASS before checkpoint
IO. All scientific T11 adapters and unchanged imported T4/T5 helpers will
be pinned in the pretraining executable manifest. P16 CPU scorer imports
the unchanged T3 upgrade/scoring functions; it is embargoed with model eval.

Host 127x01 is idle and has 1.3 TB available for the CPU store build. Hosts
127x16/18 have valid shared leases ending 2026-10-09 05:30Z, max_workers=96,
zero console users, idle A6000s and 48,666/48,577 MiB free. Both use T5's
PSS-aware supervisor SHA 00cdaa8ad3be41a0a85481d318ad03920b87e2564ab541e8f9a9d5bf801d246f.
Live preflight must be repeated before each launch. Build uses at most 12
workers; training uses one loader and one run per GPU, nice 10 or higher.

Required input reading completed: DESIGN sections 2.8/3/4.3/4.4/5.1/7,
T3/S122 progress and actual T10-PASS, T4 README/throughput PASS, T5 progress,
v1 registration and resource-r2 amendment, and fleet sharing/lease rules.
No repository/ancestor AGENTS.md found. Other workers' modified files untouched.

V2 roles SHA: 1f45f1d147040e4502a18820ed9eec172b2d5f304589eaf96cbd87aa84f547e8.
All 82,231 C56 role assignments remain frozen. T9 marks 2,361 old C56
perspectives with Three Musketeers opponents ineligible for the v2 actor;
counts will explicitly reconcile raw roles, excluded_leak and actor exclusions.
Battle Healer/Mirror flags are retained. S122 input: 333,934 perspectives,
233,788,896 rows, zero errors/illegal labels/truth violations.

Owned code is imitation/t11/. It imports upstream code without edits. Store
destination on hub: reports/strategy_council_20260928/imitation/data/v2-store-v1/.
S122 train waits are deterministically pre-thinned to 50%, stored weights ×2;
epoch sampling is 50% of retained S122 waits and 25% of C56 waits, total IPW ×4.
Dev/eval/eval_ood retain every eligible row. Planned seeds: 2026100821/2026100822.

Smoke PASS: two units, 71 retained perspectives, every source/sidecar array and
decoded mask exact. Adapter validation PASS (no fitting or held-out scoring):
C56 sampler equals T4 for both seeds/all six epochs; exact mixed hash/shuffle;
total wait IPW4 for both corpora with workers0/1; exact resume-cursor replay;
real train/dev batched tensors unchanged by T5 mmap release; all supervised
plays/abilities retained. Receipt: `t11/receipts/adapter-validation.json`.
Validation r1 failed before reading data because the hub had no T4 source;
qualified files were staged into a T11-owned snapshot, with unchanged hashes.
r2 passed; r3 repeated the same checks to bind source/loader/asset hashes.
No change to the model, optimizer or upstream files.

Production plan is complete: 8,751 units; 3,664 randomly selected perspective
round trips. At12:05:54Z, 5,051 units /2,118 checks are done; no failure.
Final counts (qualified by the STORE-PASS above):

| Role | Perspectives | C56 | New S122 | Stored rows | Original eligible rows |
|---|---:|---:|---:|---:|---:|
|train|318,766|67,378|251,388|143,740,698|228,863,669|
|dev|16,662|3,436|13,226|11,776,480|11,776,480|
|eval|16,013|3,644|12,369|11,416,079|11,416,079|
|eval_ood|14,924|3,643|11,281|10,438,451|10,438,451|

Total177,371,708 stored rows. Three Musketeers exclusions by frozen role:
train2,002/dev110/eval121/OOD128, in addition to47,439 excluded-leak entries.
The 85,122,971 discarded train waits are S122 only. Train frequency counts
will read the full unthinned eligible source, avoiding sampling noise/bias in
the baseline. Only v2 dev baseline is scored before the held-out embargo.

Original hub labels (historical; r2 continuations are listed above; jobs under
`/mpac/sdicks02/jobs/clasher/`):

- `t11-store-build-20261008-r1` (completed0): launcher3600605, driver3600618, eight workers
  3600958–3600965. Logs `.log`; exit `.exit`. Resume only after verified exit,
  with a fresh label and the SAME `imitation/t11/build_store.py --out
  reports/strategy_council_20260928/imitation/data/v2-store-v1 --workers 8`.
  Completed disjoint units are durable and resumable; no current restart.
- `t11-store-finish-20261008-r1`: launcher3602004. Waits for the builder's
  exact exit0, fits full-source train-only frequency counts, scores dev,
  writes `data/receipts/T11-STORE-PASS.json`, mirrors small receipts05.
- `t11-launch-pipeline-20261008-r1`: launcher3605187. Waits for finish exit0;
  freezes `imitation/gate-a-v2/PREREG.md` and executable manifest; starts
  checksum copies through each lease wrapper; rechecks copy receipts, live
  leases, PSS supervisor hash, idle GPU and process headroom; launches each
  registered seed on its respective host when ready. No held-out scoring.
  Durable state: `t11/receipts/pipeline-state.json`, authoritative on01.
  Never launch a duplicate copy/trainer or restart the pipeline blindly.

Source snapshot on01: `/mpac/sdicks02/jobs/clasher/t11-20261008-v1/source`;
assets: sibling `inputs/assets.npz`, verified T5 asset SHA
3954af44678a5f397c22d1eaa4c6be9b3c7517b3c5fe0d0e3151f4ab9937c737.
All20 T4 files independently verified against the throughput receipt. T5
resources/guards/baseline match its immutable r2 executable manifest exactly.
Only T11 adapters are new. Snapshot trainer sampling imports the T5 loader.

Verified leased copies: `clasher-lease/data/v2-store-v1/`; code, assets and
outputs: `clasher-lease/t11-20261008-v1/`. Copy labels
`t11-v2-store-copy-127x16-v1` /`t11-v2-store-copy-127x18-v1`.
Training labels `t11-v2-main-2026100821-v1` /`t11-v2-main-2026100822-v1`.
Current verified training PIDs/throughput and registration hashes are above.
The completed pipeline records exact argv and launch responses in its receipt.

Remaining: complete both training runs, curves/checkpoints,
lease migration if needed, completed selection/calibration, v1 gate embargo
release, then v2 gate(a) reports. The immutable registration is now
`imitation/gate-a-v2/PREREG.md`; the draft is retained as historical preparation.
Leased runs must trigger graceful stop at 04:20Z and checkpoint/exit before
05:00Z, then resume exact optimizer/scheduler/RNG/sampler state on available
home GPUs. Eval remains blocked until training completes, selection is sealed
and the v1 offline gate has been reported.

Temporary ten-minute continuation is enabled, bound to this T3 thread:
`scheduled-task:command:mcp:a7c7a951-1d27-4ece-936a-d804c703d70c:schedule-task:clasher-t11-v2-continuation-20261008-v1`.
First nextRunAt2026-10-08T12:13:53.490Z. It owns monitoring, failure recovery,
lease migration, selection, embargo release and final gate reporting. Disable
after final completion or an explicitly reported unresolved external blocker.
It does not replace the fleet coordinator's separate heartbeat.
