# R3 resumable progress

Started real UTC 2026-10-10T03:57:38Z. Coordinator 0523ae6f. Exploration lane.
No fit or reporting game launched. Work is owned exclusively by exit-r3.

Authorized GPU: R3a 127x09, R3b 127x16; lease expires 2026-10-11T05:30Z.
Own job root: /mpac/sdicks02/jobs/clasher/exit-r3-20261010-r1.
Frozen R2 runtime dependency: /mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1.
Input corpus1c8e1f49, initd77005d5, assets3954af44, heldout0ecce0f0.

Coordinator seed correction: reporting4503601907370496+[0,600),
smoke4503601917370496+[0,8). Earlier720000000 proposal withdrawn, never used.
CPU admission: 03 physical0–59 nice10 SCHED_OTHER after explicit K2 release
and zero K2 PGIDs; 01 physical0–39 fallback only after X descriptive release.
No G on admitted host. Same-seed C-v1/R3a/R3b/K0 rotation; never pre-run controls.

Next: implement own root-only trainer/head and tests; schema/SHA G decision;
all-range seed audit; freeze/commit/secret-scan/push before fitting. Fits use own
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
