# R3 resumable progress

Started real UTC 2026-10-10T03:57:38Z. Coordinator 0523ae6f. Exploration lane.
Both fits are active; no heldout evaluation, smoke, or reporting game launched.
Work is owned exclusively by exit-r3.

Authorized GPU: R3a 127x09, R3b 127x16; lease expires 2026-10-11T05:30Z.
Own job root: /mpac/sdicks02/jobs/clasher/exit-r3-20261010-r1.
Frozen R2 runtime dependency: /mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1.
Input corpus1c8e1f49, initd77005d5, assets3954af44, heldout0ecce0f0.

Coordinator seed correction: reporting4503601907370496+[0,600),
smoke4503601917370496+[0,8). Earlier720000000 proposal withdrawn, never used.
CPU admission: 03 physical0–59 nice10 SCHED_OTHER after explicit K2 release
and zero K2 PGIDs; 01 physical0–39 fallback only after X descriptive release.
No G on admitted host. Same-seed C-v1/R3a/R3b/K0 rotation; never pre-run controls.

Root-only trainer/head, tests, G schema/SHA inclusion and all-range audit are
complete. Scientific freeze bc542da8 was committed/secret-scanned/pushed before
fitting. Fits use own
setsid-f wrappers, loader6/prefetch4, parent118/119/126/workers120–125, ≤16procs,
nice≥10, PSSguard46GB/hard48GB, GPUfree≥8GiB, stop at Oct11 05:15Z.

2026-10-10T04:04:28Z own interval/formula audit passed all K/K-v2/K2/X/G and
coordinator descriptive20/201 banks, expanded helper offsets. Peer references
R3new ranges treated as declarations only. [Audit](receipts/seed-audit.json).
Gverification355files passed04:01:51Z; own copies finished04:03:34Z on09/16.
Actual eligibleR1roots6,009,681 plusG212,542=6,222,223. Five focused tests pass;
final metered re-run inreceipts/tests.json. PLAN/freeze includes all predeclared
thresholds and Ginclude decision. No fit started before prelaunch commit/push.

Resume fit command on each assigned host after checking own checkpoint/exit:
`bash $job/pilot/detach.sh $job/fit-ARM-resume1.log nice -n 10 $base/venv/bin/python -B $job/ops/supervise.py --job $job --arm ARM --resume $job/fits/ARM/step-XXXXXXXX.pt`
Use literaljob/base paths above; never overwrite existing log.pid. Check own
FIT.STOP reason and lease before clearing an OWN operational stop. Never clear
G/coordinator stops. Static trainer source pins must remain unchanged to resume.

2026-10-10T04:30:00Z: R3a09 and R3b16 healthy at last checks, step542/500 at
04:26:21Z, both checkpoint250 complete, finite losses. R3a start04:07:41Z:
supervisorPID/PGID2651869, trainerPID/PGID2651879. R3b start04:07:42Z:
supervisorPID/PGID1558809, trainerPID/PGID1558835. Both8Clasher processes,
nice10, PSS22.33/17.84GB and GPUfree48.41/48.30GB at04:28:40/37Z; no stop
reason. Own immutable job/source and job/ops remain pinned. Evaluation code
goes separately to job/eval-ops; never rsync over fit-source or fit-ops.

Evaluation code qualified:5 own tests +7 byte-frozen X clock tests, metered
receipts/evaluation-tests.json. [Operational supplement](EVALUATION.md).
Evaluation implementation freeze receipts/evaluation-freeze.json must be
committed/pushed and copied with evaluation-prelaunch.json before offline.
Fit hosts also need own heldout-corpus copy from frozen R2 runtime.

Bounded command-center advance (metadata/SSH only, safe on05):
`python3 reports/strategy_council_20260928/imitation/exit-r3/operations/stage.py --output /mpac/sdicks02/jobs/clasher/exit-r3-stage-state.json`
This waits for exact2500/clean final exit and starts own GPU offline once per
arm. It does not retry paused/failed fits or existing failed phase identities.
Inspect job/ARM-health.json, ARM-exit.json, fits/ARM/segment.json,
fit-ARM-attempt1.log and checkpoints for live fit progress. Collect whole-tree
exit meters; never add segment/nested child meters again.

CPU remains unclaimed. K2 accepted contract7404506e, no release yet. It will
atomically publish03:/mpac/sdicks02/jobs/clasher/k2-20261010-r1/K2-CPU-RELEASE.json
after1800 terminal cases, final source/vacate audit and all recorded PGIDs gone.
Require explicit K2 notification/PROGRESS03 RELEASE plus independent marker
SHA/fields/all-PGID absence/noK-v2/noK2/noG audit. Coordinator assigned03
physical0–59 nice10/SCHED_OTHER only after this release. Fallback01 physical
0–39 only after X descriptive explicit release/full drain. No ETA admission.
X descriptive e8c82b10 reporting20+[0,600),qualification201+[0,32) included
in seed audit; both X GPU jobs closed,01 reserved through descriptive finish.

After explicit CPU release: copy own eval-ops, frozen-x, source/exit_r3 and
freeze/audit/eval pins to own home job, write CPU-RELEASE-EVIDENCE.json and
CPU-RELEASE-ADMITTED.json (explicit_release:true, correcthost,
release_evidence_sha256, vacated_pgids:[allrecorded], realUTC). Run stage_cpu.py
under admitted nice10/SCHED_OTHER on manager59(03)/39(01), then require its
CPU-STAGING.json passed. Source/native/heldout/checkpoint SHAs are mandatory.
Do not stage bulk CPU assets before explicit admission.

Then use the bounded stage command with --cpu-host 127x03 (or admitted01).
It advances only regret64 → stage1reduce → survivor-only excluded smoke0/1
→ qualification →600 reporting complete interleaved blocks → paired reduce.
Regretpool8workers, reporting≤46worker blocks, manager59/39. No mixed-block
reuse; archive/replay every arm together and charge failed attempts. If both
arms fail stage1, skip stage2 and report both killed. Own stop flags and the
Oct11 05:15Z deadline remain active through all phases.

Final deliverable: update RESULTS.md with calibrated binarymetrics, W-score
regret, per-stage kills, paired C-v1/K0 intervals if any survivors, full parent
tree CPU/GPU costs including failed attempts, and adoption status. Commit
only explicit own paths; secret-scan before each push. Notify coordinator
0523ae6f with milestones under150words. Remove any continuation timer at final
completion or expiry, and record its ID/last state here.

2026-10-10T04:32:40Z — Evaluation freeze33cff003 pushed and deployed on09/16;
all mapped file SHAs and pushed prelaunch freeze SHA verified independently
on each host. Own heldout-corpus staged. Fit latest step708/671 at04:32:11Z.
No offline/evaluation game launched. K2 still behind K-v2 release, no CPU claim.

Temporary same-thread continuation every10minutes; nextRunAt
2026-10-10T04:41:59.626Z. scheduledTaskId:
`scheduled-task:command:mcp:41973a00-3443-411b-88ab-c1f2788161a1:schedule-task:r3-continuation-20261010-r1`
Read current state before any action and never duplicate active attempts.
Delete timer after full RESULTS completion or expiry/vacancy.

2026-10-10T04:39:31Z — Coordinator grants regret-only04 physical12–19/nice19/≤8processes.
Manager19 + three workers12–14. Immediate owned stop if PSI memory fullavg10>10;
vacate before any A19 launch and by Oct10 08:00Z. New guard/pool/staging/advance
entrypoints freeze before replay; scientific plan/seeds/gates unchanged.
No paired games on04. Watch current RUNBOOK.md and PROGRESS-T6T7.md SHA; any
authority change or unavailable check halts/reaps children, requires review.
Guard test passes pressure/cores/nice/heartbeat/deadline/A19/stop mutations.

Continuation after GPU offline: refresh own04 admission only if latest A19
progress still clearly held/no launch and no recognized A19 process. Copy exact
coordinator grant to REGRET04-AUTHORITY.json, write REGRET04-ADMITTED.json with
regret_only:true,host:127x04,authority_sha256,a19_progress_sha256 mapping actual
command-center RUNBOOK and PROGRESS-T6T7 absolute paths, realUTC. Then guarded
stage_regret04.py --offline on04 nice19/core19. Earlier base-only staging may
prepare scorer/heldout while fits run; REGRET04-STAGING.passed staysfalse until
final GPU proposals copied. Use advance_regret04.py --output own metadata JSON
from05 to launch owned setsid-f regret pool once and reduce64 completegames.
Regret worker uses R3_REGRET04=1; no other mode can claim04. Own REGRET04.STOP
and REGRET04-VACATED.json durable; record every pool/worker PID/PGID.

After04 stage1 reduction, transfer stage1-results.json and merged offline
R3a/R3b metrics plus all regret64 seals/meters to finally admitted03/01 after
home stage_cpu.py. This overwrites RAW GPU offline metrics only with the
validated04 merged Stage1 metrics; do not repeat regret on03/01. Then normal
stage.py --cpu-host advances survivor smoke/reporting or both-killed skip.

2026-10-10T04:42:36Z base-only04 staging COMPLETE: PID/PGID865011 exited;
all scorer/source/native/heldout SHAs verified. Own CPU16.468019s, wall87.184854s;
remote sender CPU unmetered. Base ready, overall staging passed:false until
final GPU offline proposals arrive. No replay or timing game launched.
Durable every-worker REGRET04-PGIDS.json added before replay, copied into final
REGRET04-VACATED.json; independent all-PGID absence check still required.

2026-10-10T04:46:13Z — Operational PID-journal/guard pin revision732a9382 pushed;
current evaluation-prelaunch.json points to732a9382 and matches updated freeze.
Every mapped file SHA/AST/pushed prelaunch verified09/16/04. Independent04
all-PGID865011 vacancy audit passed04:45:05Z, PSI fullavg10=0.00. Base job
is idle; no replay started. Latest healthy fits04:45:04Z step1068/1047,
8processes each, PSS19.88/23.35GB, GPUfree48.41/48.30GB; no stop reason.

X descriptive update: selection addendum693bc3b1 to e8c82b10 pushed;600fresh
reporting200 active01 since04:42:48Z pool2035131, same-seed interleaved
Cv1/X1/X2/X4/K0 on physical0–39/nice10/SCHED_OTHER. Qualification201+4/5 passed
6 terminal games, reserved seed banks/offsets unchanged. X5/X7 finish original
fit/offline independently.01 fallback remains QUEUED until explicit X release
and all owned game groups vacated. No original150/151/R2 reporting.

2026-10-10T04:55:05Z — Bounded continuation: fits healthy1145/1126 at04:47:42Z,
checkpoint1000 present onboth;8Clasher processes each, no stop reason.
Stage advance did not launch offline because neither2500 clean exit exists.
K2 still behind K-v2 finalrelease; X descriptive01 remains active.04 base
staging remains vacated. A19 RUNBOOK/PROGRESS bytes changed after the stored
clear snapshot, so that stale admission cannot launch replay. Fresh manual
A19-held/no-launch/no-recognized-process review required after finalproposals.

Metadata-only result collector added (no scientific source/recipe changes):
`python3 reports/strategy_council_20260928/imitation/exit-r3/operations/collect_results.py`
Default09/16; optional --hosts127x04/03/01 only when allowed/read-only. Saves
SHA-labelled immutable process meters and decisions under receipts/process-snapshots.
Run BEFORE any exact-checkpoint resume or replay so overwritten exit/decision
paths cannot lose earlier attempt costs. Copies metadata only, no arrays,
checkpoint bytes, games, native/Torch imports or host claims.

`python3 reports/strategy_council_20260928/imitation/exit-r3/operations/render_results.py --stage1-host HOST --stage2-host HOST`
Use appropriate collectedCPU hosts, omitpendingflags. Renders verifiedJSON
decisions and whole-tree cost receipts only; no bootstrap/recomputed outcome.
Current RESULTS clearly pending; prep55.608171CPU s (including16.468019s04base),
fit/offline/game costs pending their exitmeters. Nested diagnostic meters
never added; copied same-SHA meters counted once acrosshosts. Finalreport
requires both final2500 EMAs and all prescribed stage1/2 gatesresolved.

2026-10-10T05:02:05Z — Continued live fits: R3a1561/R3b1531 at05:01:33/34Z; both
step1500 checkpoints present. Health8 processes each, PSS16.62/23.65GB,
GPUfree48.41/48.30GB, no stop reason. No2500 complete/exit/offline exists;
bounded stage.py made no launches. Metadata process snapshots refreshed and
RESULTS remains explicitly pending; fit costs accrue until whole-tree exit.

A19 latest05:00:49Z combinedcandidate remains HELD, no production authority
or launch; original CPU52 seal unchanged. Progress bytes changed again, so
04 stays idle and its stale admitted snapshot cannot start final staging.
K2 at04:58:29Z remains behind K-v2 release (2312/2400 terminal, originalPGIDs
live); no K2 release or03 admission.01 still awaits explicit X study release.
Temporary continuation enabled at10-minute cadence; retain until finalRESULTS
or lease expiry/vacancy, and do not duplicate fit/offline/replay attempts.

2026-10-10T05:14:03Z — Healthy fits R3a1876/R3b1843 at05:12:20/21Z, both1750
checkpoints saved. Eight processes each, PSS19.17/27.68GB, GPUfree48.41/48.30GB;
no stop reason. Final2500 complete/segment/exit receipts are absent. Bounded
stage.py waits without launching; no heldout outcome or replay has run.
K2 remains unlaunched awaiting K-v2 explicit release despite2400 terminal files;
R3 still awaits K2 final release.01 remains queued behind X descriptive release.

A19 latest05:10:06Z remains HELD pending actual operator gates/approval;
original CPU52 seal continues.04 remains idle with stale admission; refresh
only after both final GPU offline files and fresh no-launch/process audit.
Metadata-only renderer now prints every input/native SHA and final effective
rows/s using all retained fit-attempt wall time, plus em dash for absent anchor
contrasts. Pending render and diff checks passed on05; no scientific entrypoint,
freeze, thresholds or seed changes. Whole-tree costs remain pending final exits.
