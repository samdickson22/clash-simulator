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
