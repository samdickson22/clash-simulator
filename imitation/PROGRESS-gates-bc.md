# Gates (b)/(c) v1 execution

Updated 2026-10-08 22:44 UTC. PREPARATION; zero gate games, neither PREREG frozen.
No gate (a) heldout results opened or used.

Primary: main-2026100802, step 22552; released checkpoint SHA256
`d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed`.
Release `c8a44c8dcb04e07f582570bdf994e9c8c576c256f201a7f7b53de4b44412d3c5`;
selection `1cbb2bf54c98dc570eb1715950f9ec21e9f4459560727bb4ac26c0d63789fc69`.
Dev temperatures (gate/card/tile): 1.0635037422180176, 1.1410114765167236,
1.0741008520126343. Gate (c) requires sampling at T=1; release calibration is
recorded separately and does not authorize changing its preregistered policy.
Original qualified snapshot tree:
`e3c60ef30743427aa8b654d3327fe0a567791a78221c90468181c2ab70a6cc90`.

Checkpoint staging: 04 verified the released hash at
`/mpac/sdicks02/tmp/t5-checkpoint-backups-20261008/127x01/main-2026100802/best-dev-step-00022552.pt`.
Owned staged path on 03/04:
`/mpac/sdicks02/repos/clasher-eval-snapshots/inputs-bc-v1/main02.pt`.
Transfers directly worker-to-worker with rsync -c; no checkpoint payload on05.

Admission 20:41Z: 03/04/13/14/15 reachable; console users0 on all;
live Clasher leases13/14/15 valid through 2026-10-09 05:30Z, caps96.
Actual concurrency will reserve >=16 runnable CPU threads; lease process cap
alone is not a CPU budget. No gate (b) host admitted without timing pilot PASS.
03 will keep <=64 own processes once v4 CPU threshold grid begins.04 <=64.
Leased games stop starting04:30Z and all own children exit05:00Z.

## Coordinator decisions / prerequisites

20:52Z authorizes seed-only metadata inventory on01/08, single thread, nice19,
ionice idle; no gate4 heldout predictions/statistics/RESULTS reads. Only temporary
output under `/mpac/sdicks02/jobs/clasher/seed-inventory/` may be written there.
02/07 are back online and must be added to history inventory (not game hosts).
Record all payload exclusions. Initial drafts/merge require five inventories;
prospective update must require these seven plus available leased histories.
Independent Opus review will be arranged by coordinator upon “freeze candidate
ready” with paths/content hashes. Do not freeze or start gates until review PASS.

## Outstanding

Stage/verify immutable source and worker checkpoint; pilot real checkpoint at
fixed concurrency; complete seven-host seed/formula audit plus leased history;
prepare per-world atomic P16 recovery and complete timing receipt fields without
changing policies; pin final runtime and review both freeze candidates.
No active task-owned game PIDs yet. Exact launch/resume commands will be added
before each launch. Existing historical qualification evidence is retained.

## Pilots launched and first receipts

Actual launch clocks from wrappers are authoritative (coordinator decision text
arrived carrying20:52Z while worker clock was approximately20:43Z).
-03 label `gates-bc-pilot-03-16-r1`, wrapper3793338: exit0,16/16 terminal,
  11,906 decisions,p99 200.238ms,max202.289ms,zero>250ms/illegal/rejections.
-04 label `gates-bc-pilot-04-16-r1`, wrapper2737117: failed before games;
  read-only runtime lacked sidecar_observer. Retained. Isolated T1 dependency
  input copy staged; retry `gates-bc-pilot-04-16-r2`, wrapper2742226.
-13 label `gates-bc-pilot-13-16-r1`, wrapper3768393: exit0,16/16 terminal,
  12,042 decisions,p99 200.242ms,max201.131ms,zero>250ms/illegal/rejections.
-14 label `gates-bc-pilot-14-16-r1`, wrapper3709197: exit0,16/16 terminal,
  12,142 decisions,p99 200.443ms,max255.002ms,ONE>250ms. NOT admitted for b.
-15 label `gates-bc-pilot-15-16-r1`, wrapper3834346: exit0,16/16 terminal,
  12,075 decisions,p99 200.223ms,max202.596ms,zero>250ms/illegal/rejections.
These qualification games have no recorded winners/scores. Full20+ requalification
will use the final instrumented snapshot. No gate outcomes have been inspected.

Home run root `/mpac/sdicks02/repos/clasher-eval-snapshots/`;
lease run root `/mpac/sdicks02/repos/clasher-lease/eval-snapshots/`.
Pilot outputs `runs/gates-bc-pilot-HH-N-rR/` contain search/game receipts,
worker-I.pid/log, checkpoint.sha256, snapshot.json and exit.
Home wrapper logs/exits `/mpac/sdicks02/jobs/clasher/LABEL.{log,exit}`;
lease wrapper logs/exits `clasher-lease/jobs/LABEL.{log,exit.json}`.
Exact initial commands: home fleet_run.sh LABEL bash ROOT/operations-bc-v1/pilot.sh HH16;
lease run.sh LABEL bash ROOT/operations-bc-v1/pilot.sh HH16 lease.
In those command templates HH and16 are separate arguments.
Retry04 uses `pilot.sh 04 16 home r2`; do not restart completed labels.

Seed metadata scan labels `gates-bc-v1-r1` under each home host's
`/mpac/sdicks02/jobs/clasher/seed-inventory/`; nice19/ionice3, one process.
PIDs01=4038308,02=8982,03=3798899,04=2741246,07=8810,08=3837748.
Exact launch generator05: `python3 imitation/gates-bc/operations/launch_inventory.py`.
It refuses a preexisting pid file; for an interrupted scan use a fresh label,
retain prior artifacts and record technical reason. Source and explicit gate4
payload exclusions: `gates-bc/operations/seed_inventory.py`.

## Serving decision and additional qualification

Coordinator confirms both gates serve EMA at T=1; no calibrated arm. Both
PREREGs record the rationale and sealed calibration as provenance only. Added
executable T=1 buffer guards. No checkpoint weight changes. Post-T5 model source differences are described in the correction below.

04 instrumented32-game pilot `gates-bc-pilot-04-16-r3`, wrapper2748339, exit0:
24,051 decisions,p99 200.273ms,max202.195ms,zero>250ms/illegal/rejections.
14 reduced8-process pilot `gates-bc-pilot-14-8-r2`, wrapper3717648, exit0:
16/16 games,11,504 decisions,p99 200.306ms,max200.903ms,zero>250ms/illegal/rejections.
Both are below final T6/T8 qualified p99 200.362424ms. Prior14 failure retained.

P16 split-world parity on03 label `gates-bc-world-parity-r1`, wrapper3800897,
active; P16 first route PASS (4 full-cell games versus same4 split-world games).
H2H and native legacy route verification pending. Uses qualification seed69575001.

Isolated runtime staging source03 contains explicit489-file dependency inventory
(no whole-checkout transfer). Root `clasher-eval-snapshots/runtime-bc-v1`, manifest
SHA256 `2c5b84993715a2a1f7c1cc6f30a405784b9cfd08fbc25d1c7b2fb44d2f92f68a`.
Copies to04 same root,13/14/15 `clasher-lease/eval-snapshots/runtime-bc-v1` via
`rsync -rc --files-from=runtime-files.txt`. No shared runtime source overwritten.
Preparationr1 failed on an overbroad required glob with no matches; r2/r3 complete.

Leased metadata inventories (own wrapper, nice19/ionice3):13 wrapper3778613,
15 wrapper3843923,14 wrapper3723296, labels `gates-bc-seed-inventory-r1`.
No borrower/owner repo or cache outside Clasher footprint accessed.
05 metadata auditr1 retained eight missing-numpy archive errors; r2 uses ZIP keys
before loading metadata arrays and passes4385 files,zero exact overlaps/errors.
Formula review233 paths pending. Remote scans still progressing through historical
receipts; no completeness claim yet. Scans never expose outcome statistics.

## Closed runtime and seed audit continuation

Current source snapshot candidate `506eb289379861ce` (full SHA in its manifest).
Model source differs from original T6/T8 (see correction below). Evaluation changes add
T1 immutable dependency copies, atomic C56 publication, timing receipt fields,
T=1 guards, per-world P16 partitioning, seven-home/three-lease audit requirement,
and mandatory independent-review/content-pin checks for freeze.

Runtime token vocabulary JSON was absent from first closed-runtime copy;03r4
failed before games, retained. Added the exact token JSON to explicit input list
and to freeze verification. Runtime manifest now SHA256
`c3dbc5d31c91f0070c257609b11de5323baa1801d638a0540abdfea8d02c0213`.
03 closed-runtime pilotr5 wrapper3809484 PASS32/32,23,618 decisions,p99 200.224ms,
max202.238ms,zero>250ms/illegal/rejections;8 skew games6,326 exact rows.
P16 and H2H full-cell/split-world parity both PASS; native legacy route pending.

Lease inventoryr1 errors were own prospective scanner-state seed list matches
and an explicitly nonexistent `repo/imitation` directory. Original inventories
retained. R2 excludes its own prospective scanner state and inventories existing
lease repo/reports, jobs, eval-snapshots, and all T5-owned trees. Zero exact
matches/errors:13=2431 files,14=2557,15=2449. Formula review pending218/227/211
paths. Raw small seed-only receipts mirrored05 `gates-bc/receipts/inventories/`.
Home inventories continue single-threaded through historical gzip/NPZ receipts.
03/04 supplemental snapshot inventories include all earlier qualification outputs.
03 supplement999 files,zero errors/matches; PID3816780.04 PID2765909.


P16 world partition qualification fully PASS03:4 original games reproduced as
2+2 for v1 scripts, v1 H2H and native s2902; exit0 at21:00:50Z, compact receipt
`gates-bc/receipts/p16-world-parity-PASS.json`. Synthetic analysis-contract tests
PASS03, wrapper3819871, label`gates-bc-analysis-contract-r1`, exit0,wall0.37s;
checks whole-world intervals, fixed-count draw-only bar rejection, duplicate and
partial rejection, exact McNemar and prescribed Newcombe implementation.

Final-runtime leased pilotr6:13 wrapper3787569 PASS32,24,604 decisions,
p99200.315ms,max202.602ms,2 unchanged-script rejections;15 wrapper3851998 PASS32,
24,000 decisions,p99200.269ms,max202.489ms,11 unchanged-script rejections;
14 wrapper3730795 PASS20,14,572 decisions,p99200.319ms,max202.827ms,0 script
rejections. All zero model illegal/rejected commands and zero>250ms. Script
rejections remain evidence, never removed. Prospective b concurrency16/16/16/8/16
on03/04/13/14/15 (72 total); c16 each,80 total, phases separated per host.

Final candidate source snapshot now`d9923a7325d679b9`, adding per-root actual A/B
candidate-count pairs outside the decision timer. Final03 smoke label
`gates-bc-pilot-03-16-r7`, wrapper3820604. No checkpoint-weight or search-selection rule changes; this uses the post-T5 model source.
Runtime dependency inventory also includes card_map.py for frozen role audits.
No confirmatory manifests exist. Keep all gate execution held for complete seed
history, formula review and coordinator-arranged independent Opus review.


## Correction: original versus post-T5 model source

Full per-file comparison found post-T5 source is NOT byte-identical to original
T6/T8 model source. Earlier progress statements claiming that were incorrect.
T5 model changes: tile_width default128→64 (released config explicit64); CUDA
training numeric GEMM and optional sparse tile training; entity cap64→128 and
192-row bucket; single-request inference avoids padding via single_features.
Raw checkpoint is unchanged/released. The original e3 snapshot was used only in
initial qualification; ed42/1fed/506e/d992 snapshots use post-T5 source. Later
pilots and all split-world parity tests therefore requalify that current source.
D1 equality checks in those later pilots use its new feature builder. Final
snapshot pin and T5 released source hash comparison are mandatory before freeze.

Post-T5 source comparison now PASS: all20 model/T1 Python files pinned in the
T5 resource-r2 executable manifest match current evaluation source byte-for-byte.
Receipt `gates-bc/receipts/t5-all-model-source-parity.json`; original-to-current
snapshot delta retained. This corrects and supersedes original-e3 parity claims.

Final d992 source smoke03r7 PASS32/32,23,834 decisions,p99 200.240ms,
max202.445ms,zero>250ms/model illegal/rejected commands;6,326 exact D1 rows.
`gates-bc/receipts/final-pilot-03.json` is compact mirror. Additional candidate-count
receipt instrumentation is outside the timer and passed this final-source smoke.
Analysis(c) synthetic fixed1792-contract test PASS03,wrapper3828615,exit0,
including pairing/physical swaps/draw treatment and separate decision bars.
Synthetic draw-only analysis fixtures use schedule identifiers but play no games;
this prospective validation exclusion is explicit in both draft PREREGs for review.

Pending allocation question: existing lease wrappers use exclusive host-workload
locks; they cannot concurrently host our CPU tree and v4's GPU tree. Do not bypass
those locks. Coordinator informed; either exclusive gate windows or home-only
execution while leases occupied must be selected before final execution plan.

## Binding coordinator allocation change — received during preparation

**Gate execution HOME CPU ONLY.** Main03/02/07; spare04/01. No gate games on
13/14/15 and no lease-wrapper windows. Their completed qualification/audit
receipts remain retained. Home01 game work is now authorized in addition to its
seed-only scan; never touch GPU jobs or gate(a) heldout payloads.02's GPU is
reserved for approximately30min GRU DDP qualification, CPU still allocated here.
Reserve >=24 runnable threads on GPU hosts01/07/04 and >=16 everywhere.
Prospective pools for requalification: b03/02/07=16 processes each,04/01=8 each;
c03/02/07=16 each,04/01=8 each,64 global worker slots per gate. Separate phases.
Requalify02/07 and the new01 pool before admission. Existing home03/04 receipts
are retained; reassess actual co-tenancy before choosing/fixing final concurrency.
Prior72-worker leased b plan is superseded, never launched. No gates frozen.

## Home-only staging and requalification — 2026-10-08 21:19Z

Latest snapshot `0f290ed17363df25` adds manifest runtime-root metadata to d992;
no game/adapter changes since final03 qualification. Isolated runtimes and released
checkpoint staged direct03→01/02/07/04 with rsync-c; exact checkpoint SHA verified
on every destination. Console counts0, low load at admission. New timing pilots:

| Host | Pool | Label | Wrapper PID |
|---|---:|---|---:|
|02|16|gates-bc-pilot-02-16-r8|32589|
|07|16|gates-bc-pilot-07-16-r8|37122|
|01|8|gates-bc-pilot-01-8-r8|4084627|
|04|8|gates-bc-pilot-04-8-r8|see jobs label.pid|

Output root per host `/mpac/sdicks02/repos/clasher-eval-snapshots/runs/LABEL/`;
wrapper receipts `/mpac/sdicks02/jobs/clasher/LABEL.{pid,log,exit}`. Resume an
active wrapper by repeating its command (label lock is idempotent):
`ssh 127xHH 'bash /mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/fleet/fleet_run.sh LABEL bash /mpac/sdicks02/repos/clasher-eval-snapshots/operations-bc-v1/pilot.sh HH N home r8 0f290ed17363df25'`.
A failed technical pilot requires a fresh attempt label, never overwrite evidence.

Closed-runtime standalone qualification03 label`gates-bc-closed-standalone-r1`
completed exit0: four complete games each P16 scripts, H2H, natural legacy and
standalone C56. Model/T1 code unchanged from released source parity receipt.

Inventory resource correction: initial metadata scanners created64 idle NumPy
threads despite ~one active CPU, contrary to intended single-thread startup.
At21:16Z verified each owned scanner by exact PID/cmdline and pinned ALL of its
threads to CPU127 (`taskset -apc 127 PID`), so no scanner can use >one CPU.
Nice19/ionice-idle preserved; no restart/lost audit progress. Per-host receipt
`jobs/clasher/seed-inventory/gates-bc-v1-r1/affinity-repair.txt` retained. Future
launches explicitly limit OMP/OPENBLAS/MKL/NUMEXPR threads to1. This correction
is disclosed to coordinator and does not retrospectively claim literal1 NLWP.
All six broad historical scans remain active; none is certified complete yet.

Home qualificationr8:01@8 PASS20/20,14,969 decisions,p99200.241,max202.186,
0>250/illegal/model rejections;04@8 PASS20/20,14,860 decisions,p99200.241,
max201.665,0>250/illegal/model rejections.04wrapper2783952. Compact receipts
`final-pilot-01.json` and `final-pilot-04.json`.
02@16 **FAIL timing**,32/32,25,560 decisions,p99200.739,max273.609,6>250;
illegal/rejections0. Retained`final-pilot-02.json`. Reduced8pilot r9 now launched
using same disjoint qualification namespace, no model or gate seed tuning.
07@16 unusually slow imports. Owned diagnostic label`gates-bc-import-07-r1`
wrapper41216 shows Numba compilation during import; diagnostic exited0.
Read-only CPU samples02~1483MHz,07~547MHz versus03~2200/04~3617; no system
settings changed. Python3.12.13/Torch2.10.0/NumPy2.3.5/Numba0.63.1/llvmlite0.46.0
match all five hosts.07 admission pending; no passing claim. Coordinator told.

21:23Z:127x07 SSH failed `No route to host` after last qualification count9/32.
Active owned scanPID8810, pilotwrapper37122. No gate games; no system/network
change attempted. Coordinator alerted. Do not claim07 inventory/pilot completion;
retain exact paths and wait for home-host recovery/allocation instruction.

02 reduced8pilot r9 wrapper43251 completed20/20 but **FAIL**:p99200.630ms,
max289.673ms,2>250;mask-illegal0,6 model rejections retained. Receipt
`pilot-02-r9-status.txt`.02 is NOT admitted to gate(b); it may run timing-insensitive
(c). No extra attempt selected based on strength. Prospective(b) allocation now
03@16,01@8,04@8 (32slots); (c)02@16 plus available pools after each host's(b)
work,07 pending recovery/qualification.07 remains unreachable21:25Z.

Audit scope repair before certification: original conservative exclusions also
skipped non-imitation historical RESULTS/statistics/predictions. No completeness
claim was made. Added targeted metadata supplements for those non-gate(a)
paths while retaining gate(a) exclusions.05 supplementr3 scans27 docs,zero
errors/overlap;3 formula lines are descriptive prose, no seed generators.
All original inventories are preserved. Home/lease supplements remain pending.

Registration-source-only update: snapshot`81c245843244196c` adds pinning of
reviewed `operations/` and `evidence/` files alongside each manifest. Model,
engine, serving and all per-game code are unchanged from qualified0f290ed/d992.

## Coordinator R17/R19 and07 coverage —21:28Z

07 historical export plus launch delta is authorized as evidence-based coverage,
with disclosed outage01:14–20:32Z and post-recovery qualification/scan namespace.
Must identify latest export, check hub/05 launch metadata, and bound any other jobs.
No blanket waiver or implicit completeness claim.

(b)03@16;01@8/04@8 only after disjoint physical-core AND sibling isolation from
GPU loader trees, a frozen per-host pilot load ceiling, >=20 final-source games
including B-vs-A, zero>250ms and zero rejected model commands. GPU trees currently
allow CPUs0-127; coordinator asked owners to isolate them or confirm03-only.
I will not modify another owner's process affinity.02 excluded(b), allowed(c)16.

03 B-vs-A qualification label`gates-bc-pilot-03-16-r10-h2h`,wrapper3847961,
snapshot`ab881fcdeeb4fcee` adds only smoke CLI head-to-head mode to81c245.
32games, same qualificationseed base69175001,16workers. Script-route results
03/01/04 each had0 model rejections.02's6 alloccurred in game006,seat0,
actions1335 at3030/3040/3050 and813 at3840/3850/3860. Recorded-action replay
on03 label`gates-bc-rejection-replay-r1`,wrapper3848057, investigates exact engine
return guards; never retune serving or silently discard rejected commands.

Scope deviation21:27Z: while locating historical07 export, one overly broad
`rg --files` enumerated filenames under `/mpac/sdicks02`, including roader directories.
No file contents were opened or modified. Stopped that search and restricted all
further searches to explicit Clasher-owned paths. This violated the requested
path boundary and is retained here rather than omitted.

R19 explained via exact88-action replay: all6 rejections occur on live
`TimedExplosive` entities with `blocks_deployment=True`. BombTower anchor3.5,10.5
and RoyalHogs anchor3.5,13.5 hit payload occupancy; public masks were legal.
This reproduces on03 without inference/search/deadlines and applies to any host;
not clock staleness or wrong hand/elixir. Candidate seat0 applies first, excluding
inter-seat application race for this case. Full forensic receipts include source
line guards and blocker positions. No adapter/engine/serving change was made.

03r10 B-vs-A PASS32,30,036 decisions,p99200.296,max200.872,0>250,zero illegal
or rejected commands for B AND A,7,914 exact D1 checks. Receipt retained.
Final-source03r11 label`gates-bc-pilot-03-16-r11-h2h`,wrapper3863882,
snapshot`0ca7bf73fb010b10`: adds pre-world load-ceiling admission wait only,
no per-game serving change. Full load trajectory every2s is recorded to set the
frozen ceiling from actual pilot load; an in-progress game always completes,
and a slow/rejected gate decision is never retrospectively excluded.

Coordinator corrected07 export assumption: no further export search. Authorized
coverage is off-host job-history bounding, all job seed bounds disjoint from gate
worlds; unboundable/intersecting jobs require coordinator decision before any
seed change. Working table `gates-bc/receipts/07-COVERAGE.md`, explicit seed-source
hashes and hub launch metadata receipts. No07 certification claimed yet.

Final03r11 B-vs-A complete32/32,30,335 decisions,p99200.269ms,max201.416,
0>250 and0 rejected/illegal for B or A.84 two-second load samples peak19.59;
prospective frozen admission ceiling20. Receipt`final-pilot-03-r11.json`.
Main historical01/02/03/04/08 scans remain active through m0 archives ~55min;
no ETA/completeness claim. Supplementalr3 labels/pids in
`receipts/supplement-r3-launch.jsonl`, all outputs retained/mirrored. Some supplied
roots do not exist: shared`imitation/` on02/04/08, eval-snapshots on08. These are
scope-list mistakes, to be resolved with explicit absence metadata; raw errors
remain. Existing files scanned with0 proposed hits. No source directories created
to hide absence and no historical receipts deleted.

## Current preparation status — 21:55Z

No gate game and no freeze. 07 remains unreachable at21:55Z; no further search
for a historical export. Off-host reconstruction covers eight bounded job groups,
with zero intersections against all4,356 proposed gate/helper seeds. Evidence:
`gates-bc/receipts/07-COVERAGE.md` SHA256
`8ee40f6e7a160d93ec18882ee3fc20c2ac0efd5739134ef40449c4459201d72b`;
`gates-bc/receipts/inventories/127x07-offhost-candidate.json` SHA256
`576eaba2472e2822e70eaf831699d39768a94ca2ef9446cf2d6f83d7bff2c8b9`.
This is candidate evidence for independent review, not direct-scan certification.
Sources include post-recovery T11 synthetic RNG/mask qualification and T5/v4
copy staging as well as our qualification; the earlier "only our jobs" statement
was too broad. No unboundable job was identified in retained off-host records.

The active broad inventories have now run about68min. Verified scanner PIDs:
01=4038308,02=8982,03=3798899,04=2741246,08=3837748. Outputs and logs remain
`/mpac/sdicks02/jobs/clasher/seed-inventory/gates-bc-v1-r1/{inventory.json,log}`.
All are processing historical m0 compressed traces; do not relaunch while active.
A scanner-regex equivalence benchmark on03 passed but was slower, so the original
scans were left running unchanged. Benchmark label
`gates-bc-audit-regex-benchmark-r2`,wrapper3895890,exit0; r1 failed a leading-zero
boundary check and its failure remains retained. Neither benchmark ran a game.

Final runtime/snapshot qualification on03 is complete: snapshot tree
`0ca7bf73fb010b10ba277a6d34e44eac7ba5ede2e8092f77e355af111b1ea187`,
16 processes,32 B-vs-A games, zero rejected commands for either controller.
Frozen admission ceiling proposed20 from observed peak19.59. Current(b) usable
pool is03@16.01@8/04@8 remain conditional on coordinator/owners supplying actual
GPU-tree affinity isolation and passing final-source H2H pilots; no affinity of
another worker has been changed.02 is only eligible for(c)@16.

Pending coordinator answers: 01/04 isolation allocation, and SHA-only metadata
comparison for36 previously overexcluded historical non-imitation documents on
13/14/15. No lease-wrapper window was acquired or bypassed. Before review, finish
home audits, resolve absent-root scope receipts, review every seed formula, and
pin complete external PREREG/evidence/operations bundles. Do not call candidates
ready while those items remain incomplete.

21:59Z07 coverage refinement: a historical r1 peer-ready waiter could have
submitted07 after a successful smoke; no termination receipt was established.
Its archived r1 seed formulas are identical to r2, so the existing full192-world
bound also covers this possible delayed launch. No claim of an absent r1 launch
is needed. Updated candidate `inventories/127x07-offhost-candidate-r2.json` SHA256
`59f65b8ed6e194febe75a70a387ac9b923f6d2f24e9492e370ddcab9a1eea7f3`;
updated `07-COVERAGE.md` SHA256
`dce4fee7b28788349605e00daad2cb3c47c6cc6dc681d68b2710969d95cd8c3c`.
Prior doc retained as `07-COVERAGE-r1.md` and prior JSON remains unchanged.
All eight job groups still have zero overlap. Qualification plan/host-loss
metadata for T5 and archived S1 source/waiter hashes are included explicitly.

Scanner speed benchmarkr3 passed identical seed extraction plus ASCII/Unicode,
leading-zero, larger-integer, decimal and underscore boundary cases.74MB trace:
original1.399s versus optimized0.428s. This has NOT changed running audits or their
scope; no scanner restarted. Receipt`audit-regex-benchmark-r3.log`,wrapper3911685,
exit0. Candidate inventory composer `operations/combine_inventories.py` preserves
all raw hashes/versions, original errors and separately proven missing roots;
it cannot certify formula coverage. No canonical combined inventory produced yet.

22:00Z received delayed coordinator message labelled20:58Z: on13/14/15 the
combined Clasher cap is80 processes including v4 GPU jobs, perception has priority,
and sustained host load>112 requires backing off. Roader's32 processes are in
addition to that Clasher cap. This corrects the older96 figure above; those earlier
lines describe historical admission, not current authorization. The message also
records11's lease availability from21:10Z at96 processes and forbids its roader*
and excluded T5 main02 paths. No11 work or path access is planned. These historical
lease updates do not supersede the later21:30 home-only gate allocation or the
R17/R19 exclusion of02 from(b).03@16 remains the admitted(b) pool;02@16 is(c)-only;
07 is unreachable;01/04 admission is conditional as recorded above.

Read-only check22:00: all five broad scans retain their verified PIDs and are
active after74min, processing m0 compressed trace metadata; none has produced a
complete inventory. No gate or lease workload launched in response to this update.

## Parallel audit and independent review —22:06Z

Coordinator explicitly authorized parallel seed scans and review before audit
completion. Review-r1 candidates sent with "inventory pending, mechanical":
`gates-bc/review-r1/PREREG-gate-b.md` SHA256
`4590ec784e9b77b1a7a131a7c3d8386776dc7ff4915b0dedf6fa60e6f8f1fac4`;
`gates-bc/review-r1/PREREG-gate-c.md` SHA256
`a163dfc2655ac5f4d2acc70f409c4c837c832a448264e0b0efaa9948394d7713`.
`review-index.json` SHA256
`78d89f222c084daa1136361cccad1de64d54f3186e1a57403664c2082bd25b44`.
The allocation in this review is(b)03@16,load ceiling20, and(c)02@16,ceiling64.
No01/04 isolation dependency. Audit completion, delta approval, review PASS and
freeze still precede every gate game. Coordinator owns the independent reviewer.

Parallel inventory directory on each live home host:
`/mpac/sdicks02/jobs/clasher/seed-inventory/gates-bc-parallel-r4/`.
Managers:01=10740,02=99642,03=3933228,04=2875559,08=3932953.
01/08 each use7 single-thread scanners+1 sleeping manager (cap8);02/03/04 each
use31+1 (cap32). Nice19,ionice idle,OMP/BLAS/MKL/NUMEXPR1.07 remains offline;
its off-host bound remains candidate evidence. All original scanner identities
and start times were verified before individual SIGTERM; no broad process kill.
The original scans had no completed-file checkpoint, so parallel shards restart
metadata reads. Original logs and interruption CPU/path/identity receipts remain.
Per-host launch/stop receipts mirrored under`receipts/parallel-r4/127xHH/`.

Shard = SHA256(absolute path)[0:8] interpreted big-endian modulo shard count.
All original metadata fields and exclusions retained; merger asserts every shard
exactly once, disjoint file maps and identical roots/proposed integers/exclusions.
Missing-root errors are retained then deterministically deduplicated. All source
and formula evidence preserved. Scanner hash
`bb370cb3566d3878f6334992944558ea6888f67e30936ec98aa1a77954a8c3e9`.
After completion, compare unchanged file hashes/seed fields/formulas with the
completed single-thread historical-doc supplements, then review changed inputs.
Do not relaunch an active manager or duplicate its shards. Inspect via:
`ssh 127x03 'cat /mpac/sdicks02/jobs/clasher/seed-inventory/gates-bc-parallel-r4/exit.json'`
and the per-shard logs. No whole-checkout rsync or heldout payload read.

22:08Z: first sampled03 scanner3933244 has NLWP1,nice19 and nearly full single-core
CPU usage;31 workers are active. Load1 sampled01=10.54,02=32.18,03=30.23,
04=31.43,08=8.20. Gate launch remains prohibited while the inventory/review
prerequisites are pending. Review bundle hashes rechecked unchanged. Deterministic
merge-contract check passes against4,385-file single-process05 inventory, receipt
`parallel-merge-contract.json`; an older fixture lacked include_only and was
explicitly normalized to[] after the first fixture check raised KeyError. No
production merger change was needed. Actual same-host subset comparisons are
prepared in`operations/verify_inventory_subset.py` and await merged outputs.

22:10Z: coordinator confirms independent Opus5.5 review is already running
against canonical`imitation/gate-{b,c}/PREREG.md` and owns only
`imitation/reviews/GATES-BC-PREREG-REVIEW-20261008.md`. That report is untouched.
Canonical PREREGs now equal submitted review-r1 bytes (same hashes above).
Before/after SHA256s, preserved baseline drafts and full unified diffs are in
`gates-bc/review-deltas/execution-pins-delta.json` and adjacent files. Sent these
paths to coordinator so the running review can check this explicit delta. Do not
assume its eventual verdict covers later bytes without a delta check.
Parallel progress:03 8/31 complete shards;04 1/31;01/02/08 active with no merged
output yet. None of these partial inventories is freshness certification.

22:17Z:03 broad scan complete:173,531 files, full inventory SHA256
`6d86d926d1dbcb370538065b7b3843f296172c04033c8e1a7abe5a55834ab6fb`.
Raw inventory remains03 at the parallel-r4 path (large); compact.json and
single-process-comparison.json are mirrored under`receipts/parallel-r4/127x03/`.
Comparison with completed single-process supplements passes all1,561 unchanged
files (13 historical docs +1,548 snapshot files), zero missing/mismatch.
Raw scan has13 truncated-gzip errors and4,356 hits, all in our own prospective
`inputs-bc-v1/audit-proposed-seeds.json`. Preserve and explicitly resolve these,
never erase them or claim raw exact_scan_passed=true. The prospective input is
covered by the predeclared own-input exclusion; source/content proof is pending
in the final audit-delta bundle.

All13 truncated traces now have candidate disjoint seed bounds.11 branch traces
recompute their recorded execution identities exactly and match the capture
plan's byte hash;2 standalone episode11 traces have adjacent declared-plan seeds.
Possible seeds:860417871,1050893080,1927153533,3650154635,3952329234.
Receipt`parallel-r4/127x03/truncated-bounds-r2.json` SHA256
`e689a8eadac709cb842bc801a86ae9cc14501418b1af0358e333d08bb46afc65`.
The first diagnostic used systemPython3.8 and hit missingPath.is_relative_to;
pinnedPython3.12 rerun passes. Both receipts remain. This candidate evidence does
not itself clear the audit; coordinator/reviewer must check the delta.04 has30/31
shards complete;02/01/08 are still active. Formula review03 has345 unique contents;
160 differ from previously read inventories but only125 new expression strings,
all inspected. Actual invocation/range reconciliation still pending final merge.

22:23Z:04 complete245,683 files,zero literal matches,26 raw errors retained.
Raw inventory SHA256`f65c0ade560d08f3364d129e6d017db82bd1592e090e783220dc70b321b4a03a`.
Comparison passes1,058 unchanged files (29 docs+1,029 snapshot files),zero mismatch.
First comparison refused a wrong-host reference:04's jobs-path historical-docs.json
now says127x01 (SHA07c72995...), while our earlier preserved05 copy correctly
says127x04 (SHA169cc550...). The original04 receipt was used for the passing
comparison. Cause of replacement is not established; no mirror touched. Completed
03/04 raw inventories checksum-copied directly to03 protected task archive:
`/mpac/sdicks02/repos/clasher-eval-snapshots/audit-bc-v1/127xHH/inventory.json`.
03/04 original copies remain. Archive04 hash equals the compact receipt's original
hash, so no changed inventory was admitted. Exact comparisons are mirrored05.

04 error resolutions prepared (not yet audit certification):13 truncated traces
and ALL binding inputs match03 byte-for-byte (`truncated-bounds-identity.json`);
12 invalid gzip/npz files are literal synthetic v4 fixture bytes, checked against
pinned05 test generators (`synthetic-fixture-bounds.json`);1 absent sharedimitation
root has the earlier existence/symlink receipt. Fixture generator source files
are absent on04; first helper refused that absence, then used explicit05 source
pins and verified every artifact's exact expected bytes. No corrupted file was
repaired/deleted or silently excluded. Raw26 errors remain in inventory. These
resolutions still require coordinator/reviewer audit-delta approval.

22:30Z: R16 dev-only CPU forward comparison staged on04, where the dev store is
already local. Exactly52 T5 manifest-pinned files match05 before explicit-file
rsync; source under`clasher-eval-snapshots/dev-parity-source-v1`. Final0ca snapshot
also staged04. Fixed seed2026100826,4096rows,oversample >100entities, CPUfp32,
scorer padded batches128 versus serving unpaddedbatch1,1thread. Pre-execution
thresholds1e-4 legal logprob and1e-5top8 near-tie; identical legal masks required.
R1 diagnostic wrapper3008698 failed after first row because metric_rows returns
NumPy scalar and helper called torch.isfinite. No gate game/source/threshold
change; corrected to np.isfinite, retained failed attempt. Retry label
`gates-bc-dev-parity-04-r2` uses same sample and thresholds. Operations script
`gates-bc/operations/dev_forward_parity.py`; outputs04
`clasher-eval-snapshots/runs/gates-bc-dev-parity-04-r2/{plan,progress,result}.json`.
Exact invocation in home jobs`gates-bc-dev-parity-04-r2.log`; do not duplicate an
active wrapper. Descriptive GPUbf16 comparison requested by reviewer needs a
coordinator GPU window/receipt; pending question sent, CPU comparison independent.
Review R1–R21 corrections are still being applied; previous candidate is NOT
claimed compliant or freeze-ready.

22:34Z: R16 CPU dev check PASS4096 rows, zero mask/top8 mismatches (no tie
exceptions), max legal logprob delta gate2.3842e-6/card3.8147e-6/tile1.1444e-5.
Dev sample jointNLL0.34585835 (4089 supervised),80.63s compute. Dev population
contains zero rows with >100entities, explicitly recorded in plan. Plan/result
mirrored05`receipts/dev-forward-r2/`. GPU descriptive comparison still pending.
R15 source parity now records host/time/snapshot/manifest and T2 D1 dependency
hash equality in`final-source-parity-r2.json`.

Applied R4 decisive fraction/pair-mean count correction and R11 truncated P16/H2H
inclusion to analysis. Both complete synthetic analysis contracts pass on03;
fixtures `runs/analysis-contract-r2-{b,c}` are synthetic-only and excluded from
seed-history evidence. Report renderer now exposes truncations and per-arm host
timing. Draft R1–R21 wording changes remain review candidates, not frozen.

R1 required executable shared HALT on worker exception/nonzero exit, checked
before every new world/game; console admission also halts starts. Model/search
unchanged, but launcher executed code changed: new tree
`798e333b2d78718396834239b94e393e2fb75ca62465ab7765133f829b12db39`;
per-file delta `source-r12-delta.json`. Requalification03@16 B-vs-A started22:33Z,
label`gates-bc-pilot-03-16-r12`, wrapper4052278. Exact command:
`ssh 127x03 'bash /mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/fleet/fleet_run.sh gates-bc-pilot-03-16-r12 bash /mpac/sdicks02/repos/clasher-eval-snapshots/operations-bc-v1/pilot.sh 03 16 home r12 798e333b2d787183 h2h'`.
Do not relaunch active/completed label. This is unscored qualification only.

08parallel scan complete148,702 files,zero literal overlap,14 raw errors retained.
InventorySHA`b00ab2785b03723645d9327705787d924d7bb90dd3522f3f7bdc8d35d55e9dd5`,
archived03`audit-bc-v1/127x08/inventory.json`; compact receipt mirrored05.
15 unchanged single-thread historical docs match exactly; zero mismatch/missing.
Errors:13 known truncated m0 traces plus missingimitation root. Formula review
and bound-identity reconciliation pending.01/02 scans still active, oneCPUthread
perworker,nice19, full affinity0..127 verified (not accidentally pinned to oneCPU).

22:38–22:44Z: coordinator waived descriptive GPUbf16 comparison (CPUfp32 is
serving and required comparison passed), authorized exact36historical doc hashes
on13/14/15 outside workload lock. All36 SHA256s equal05; no remote writes/content
parsing/lock interaction. Receipt`lease-historical-doc-shas-r1.json`.

R12 initially disclosed4model rejections as zero-rejection blocker. Coordinator
repeated binding R19 restatement: only timing/staleness/load-attributable rejects
block admission; deterministic mask-v1 occupancy rejects remain part of play.
All4 reproduced exactly in186-action replay: RoyalHogs813 ticks5970/80/90/6000,
TimedExplosive blocks_deployment. Receipt`rejection-03-r12-replay.json`. A/B use
same engine-drop/no-op semantics before resource/cycle mutation.03@16 r12 thus
passes restated admission; no clean-sample rerun. r12p99200.270319,max201.498525,
0>250,0illegal,7693 exact D1 rows. Both-arm counters retain4B/0A.

Required per-card command-attempt/rejection counters added outside decision
clock, plus legacy comparator audit-only wrapper; no model/mask/engine changes.
New candidate tree`211087027eeb448bffdde4b0f9e5a99411abfe0afed84fdf828b59304af5dc37`.
`source-r13-delta.json` and`final-source-parity-r3.json` bind model/T2-D1 equality.
Audit-code qualification03@16r13 wrapper4098192 (same pilot samples), exactresume:
`ssh 127x03 'bash /mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/fleet/fleet_run.sh gates-bc-pilot-03-16-r13 bash /mpac/sdicks02/repos/clasher-eval-snapshots/operations-bc-v1/pilot.sh 03 16 home r13 211087027eeb448b h2h'`.
Do not duplicate active/completed labels. Synthetic full analyses with command
counts pass (`analysis-contract-r3-b/c`); no simulator used by those tests.

R13 high-seed (>2^31) six-route plumbing on03 old798e passed12games, exit0, no
outcomes read. New audit-wrapper repeat04 label`gates-bc-high-seed-04-r2`,
wrapper3065468, runs`operations-bc-v1/high_seed_smokes_r2.sh` viafleet_run.
World base3900000001, all helpers below2^32 and disjoint from gate world sets.
Routes search/C56/P16/H2H/natural/s2902,2games each, unscored. Old03wrapper4080002
complete. Actual source/numerics same on02/03 (uv pip freeze used because Python
venvs contain no pip module); first capture helper failures retained.

Review2 running under coordinator. New canonical hashes sent:
b4ee3c55b39fc19580f5d397c53c1de649b8f22bf52715537665cef6c5a06ca14,
c b38e4681cbf574baf7b3fb1744f1e9e04aa19a760141c637a12e0fded7481e35.
Delta chain`review-deltas/r2-required-changes/` then`r2-r19-restatement/` preserves
before/after drafts and patches. Neither frozen. Current draft still contains
historical earlier statements explicitly superseded by later R19/source deltas;
final consolidation will require its own logged review delta.
01all7shards completed, merge finishing;02first3/31complete.08all13truncated
artifacts/binding inputs match03/04 byte-for-byte; raw errors remain, receipt
`parallel-r4/127x08/truncated-bounds-08.json`. No new08formula contents beyond04.
04new140formula contents inspected (350lines unique-expression review); full
invocation/range reconciliation remains open, not a freshness certification.

22:57–23:10Z continuation (review RC-1…RC-12; no gate game/freeze):
- R17 cache PID3838563 verified ALL threads on48–63,112–127 by read-only
  sched_getaffinity. Receipt `gates-bc/receipts/r17-cache-affinity-r1.json`.
  Coordinator keeps v4 CPU grid off03 throughout gate(b); load ceiling20 unchanged.
- 02parallel-r4 complete139219files,0literal collisions,14rawerrors (13known
  truncated traces + absentimitationroot). SHA467b46b3e632cc69c35fcba3aa4b046a30aa37ee279eefabccbc6a2cde26d9d0.
  Unchanged subset713files (12docs+701snapshots),0mismatch/changed/missing.
  Raw archive remains02`clasher-eval-snapshots/audit-bc-v1/127x02/inventory.json`.
- RC5 source/config/test/checkpoint/dataset supplement `gates-bc-roots-r5` launched
  nice19/ioniceidle with7shards+manager perhost:01PID312301,02PID250161,
  03PID4175067,04PID3152824,08PID4110551. Paths and launch argv in
  `receipts/roots-r5-launch.json`; exact resume is inspect existing pid/exit and
  collect completed shards, NEVER rerun an active label.01/03/04/08complete,
  no rawerrors/literalhits. Formula/range review remains open.07offline covered
  by disclosed off-host bounds; f35additionalhistory question sent coordinator.
- RC4 P16 audit receipts now retain non-wait command sequences and exact reset
  metadata for outcome-blind replay. No model/policy/mask/engine changes.
  register.py rejects incomplete candidate text outside historical sections.
  New candidate treef88e2cb1685b7d3b, staged02/03; b executed decision/receipt
  code is unchanged fromr13. c requalification runs below on realcheckpoint.
- RC2b four games per route(p16,natural,s2902,h2h,c56):
  02`gates-bc-cqual-02-r4`PID257201;03`gates-bc-cqual-03-r4`PID4183973;
  03historical798e`gates-bc-cqual-798e-r4`PID4184063;
  03historical2110`gates-bc-cqual-2110-r4`PID4184189.
  All exact argv/resume commands in `receipts/cqual-r4-launch.json`; outputs
  `/mpac/sdicks02/repos/clasher-eval-snapshots/runs/<label>/`. Don’t duplicate.
  Historical sources unchanged; external qualification harness records actions.
- RC8 low-seed differential at3900000001-2^31=1752516353:02five c routes
  `gates-bc-low-seed-c-r4`PID262610;03search
  `gates-bc-low-seed-search-r4`PID4190942. Exact argv/labels in
  `receipts/low-seed-r4-launch.json`. These are qualification, never gate worlds.
  No qualification strength analysis performed. Outcomes remain unused.
- Full before/after RC delta and final inventories/replay/analysis pins remain
  incomplete; do NOT treat this as “freeze candidate ready”. Both canonical
  PREREGs remain drafts awaiting coordinator final delta review.

23:10–23:25Z review continuation (NO gate games, NO freeze):
RC2b PASS: 20games each finalf88/02,f88/03,798e/03,2110/03;
exact non-wait action streams, initial decks, seeds, seats, terminalticks across
all five routes;0illegal/rejections. Receipts `cqual-r4-{source,host}-parity.json`.
Audit-only P16 full command/reset fields qualify exact replay:20games/1328commands
PASS, `replay-qualification-r1.json`. New generic RC4 replayer also reproduces
r12's4RoyalHogs/TimedExplosive rejects, `rejection-rc4-r1.json`.
RC4 analysis requires full-count outcome-blind replay receipt with every game
hash before any strength analysis. RC12 episode counts and exact paired-world
sign-permutation descriptive test implemented; no score adjustment. Synthetic
analysis contracts r5/r6 passed, no simulator. r6 exercises>=2^40 fixture seeds.

Coordinator23:20Z changed seed policy before any gate outcome: f35 gap is genuine.
Git catalog7commits/2615unique blobs/1383seed-bearing records,0oldliteralhits,
`f35-git-r2/catalog.json`. Unknown readiness root-bank master seeds draw32-bit
worlds; missing f35 archives/argv cannot be assumed complete. NEW seeds will be
hash-committed>=2^40,<2^48, offsetting old formulas. Old4356seed audit preserved.
Seed construction helper `operations/seed_namespace.py`; canonical UTF8 JSON
object b,c with one delimited seed section replaced by a fixed placeholder in
each document; prefix `clasher-gates-bc-v1|`. H not yet selected while non-seed
candidate bytes are being finalized. No original prospective files overwritten.

P16 legacy np.random.seed scalar rejects>32bits: added qualified input-only shim
`evaluation/seed_compat.py`, SeedSequence(full integer)->624uint32 seed words.
For<2^32 the original API is called unchanged; masks/model/T=1 unchanged.
Seed contract passes old-state equality, high-minus2^31/mod32 distinction,
Torchinitial_seed exact. Wide plumbing namespace is2^44+3900000001, disjoint
from the entire proposed new base band. Sourcea8e5cb06adaa479c qualified:
02`gates-bc-cqual-02-r5`PID292496,03`gates-bc-cqual-03-r5`PID35306;
02`gates-bc-wide-low-c-r5`PID294604,03`gates-bc-wide-search-r5`PID38020.
All completedexit0; all six routes pass, c20games02↔03 exact,0illegal/rejected.
Receipts `wide-seed-c-parity-r5.json`,`wide-seed-search-r5.json`,
`seed-compat-r1.json`; exact commands in `cqual-r5-launch.json` and
`wide-seed-r5-launch.json`. Do not relaunch completed labels.
Coordinator explicitly carries timing/host qualification across seed changes.
Current code snapshot1cc0c7420398775695e014108e43ce370a68c24a03ed9fa2553a792be874d03f
only adds freeze-time namespace-basis verification/docs over wide-qualifieda8;
`source-r17-delta.json`, `final-source-parity-r6.json` pin the evidence.

All five worker RC5root supplements completed:0rawerrors/oldliteralhits.
05light metadata sweep2094files had2tool-environment errors (Python3.8
removesuffix, then missingNumPy); both scalar NPZmetadata reconciled withstdlib
zip/npy decoding, seeds1261001/1262001, source hashes retained in
`roots-r5/127x05/npz-stdlib-metadata.json`. No media/data arrays read.
All02truncated artifacts and binding inputs match03/04 exactly, receipt
`parallel-r4/127x02/truncated-bounds-02.json`. Allworker shard hashes verified.
Own4356input content equals exact union, `own-input-proof-r3.json`.
Post-scan job ledger captures121command receipts across01/02/03/04/08;
exploration lanes>=2^48, own widequal>=2^44, other worlds bounded below2^40.
07stillNoRoute; no prohibited host contacted.11T6/T8 qualification seeds explicitly
included in `offhost-rc5-bounds-r3.json`. No history gap silently certified.

23:36–23:48Z r3 final candidate (NO gate games; NO freeze):
04 overwrite root cause is coordinator hub-mirror-127x04-20261008-r2, every30min
sinceOct7 writing01files into04live paths. Stopped~23:33Z; v2 targets isolated
mirrors/hub01. Coordinator authorizes original03archive f65c0ade… with245683files,
31originalshard hashes,24matchingrawparts and7replacedparts00–06. Full disclosure
receipts/parallel-r4/127x04/overwrite-incident-r2.json; before/after preserved.

Final H e730c9f1f71f4402b47a8dff2593e5b659c947fd7b0184c3cdeafa2799f49f50,
base1359319908352. Both original32-bit and superseded firstwideH bdc74e65…
retained ashistory. New4356union SHA c92f33839665d705e1579ae9f758c8ca621b895cefeab992f438d8d2752e58a8.
Merged audit PASS:26434 observed historical integers,94resolvedrawerrors,
0unresolved/overlap; all derived/formula/job ranges checked.02inventory complete.
Supplement launch-ledger-r7 closes scan delta,48job entries,0unknown/intersection;
07 recheck remainsNoRoute. No gate(a)heldout opened.

Canonical drafts b7524a4e14c70bab4304acd996ac910330bfc3f56d9bee295e4e7b237514fc347,
c8d565be1aad244a21790124f946b981e8cd6849da2ecb8d8269cd56ce1f021db.
Fullsnapshot016b42fac2c40614fa55a8bb859a80893f6bea91c189a350d2f34fb3bab1b907,
staged02/03; metadata-only successor of1cc, serving code unchanged.
Schedules prepared03: gates-bc-prepare-wide-r3-final PID160919 completedexit0.
Synthetic analysis gates-bc-analysis-contract-r7 PID160999 completedexit0.
Worker preparation paths /mpac/sdicks02/repos/clasher-eval-snapshots/prepare-bc-wide-r3-final/gate-{b,c}/.
Exact preparation argv and completed logs:receipts/prospective-wide-r3-final/launch.json.
Do not relaunch completed labels. Checkpoint rehashed02/03 exactd77005d5….

Coordinator RC3 interpretation: competing COMPUTE workloads block; enumerated
idle baseline services remain subject to average<=0.5core and5speak<=2cores.
No baseline affinity changes; never touch tailscale. Existing canonicalbytes/H
unchanged. External baseline monitor approved, writes sharedHALT between games
on breach; activegamesfinish, noadjustment, registeredincidentresumeonly.
03marker /mpac/sdicks02/jobs/clasher/GATES-03-RESERVED touched23:46:01Z,
authorized todrain exploration. Cache3838563 verifiedheadroomcores.
Five-minute baseline label gates-bc-baseline-prelaunch-r3 PID175475;
path /mpac/sdicks02/repos/clasher-eval-snapshots/runs/baseline-prelaunch-r3/;
exact argv receipts/prospective-wide-r3-final/baseline-launch.json.
Resume: inspect existing PID/exit and collect result; never duplicate active label.
Before freeze still require baseline completion, sealed index and coordinator
final delta-only approval. No frozen manifests exist.

23:52Z: freeze candidate ready (delta r3) posted to coordinator; NOT approved/frozen.
Index imitation/gates-bc/review-deltas/r3-sealed/index.json SHA256
5575fb3997750ce6aad4a3a5bc1ae30093e07aa140a68943921858c6be035fcd.
Canonical b7524a4e1…/c8d565be1… and fullsnapshot016b42fa… unchanged.
Baseline completed302.3358s average0.00853356core peak5s0.01785504core PASS.
Original endcapture includes v4rsyncPID196329, retained asblocker; itdrained.
Separate quiet-host-r3.json PASS0competingworkloads,cachepin correct,markerexists.
External monitor lifecycle synthetic tests on02label
gates-bc-baseline-supervisor-test-r3 PID416634 exited0:success,breach,monitorfailure;
all active fake hosts finish and failures publishHALT. No simulator used.
All files in sealedindex verifiedstable after handoff. Exact freeze/launch argv
and sshcommands:receipts/prospective-wide-r3-final/execution-commands.json.
Gateb03 /mpac/sdicks02/repos/clasher-eval-snapshots/confirmation-bc-v1/gate-b/;
gatec02 sameparent/gate-c/. Workerops/evidence/schedules stagedchecksum-verified,
receipt execution-bundle-stage-r3.json. approval.json deliberately absent until
coordinator finaldelta approval; freeze/launch commands have NOT executed.
Next: obtain reviewapproval naming bothcanonicalhashes+fullsnapshot,stage its
receipts; freeze BOTH throughfleet_run; verify frozenbytes/manifests;recheck
quietaffinity/load/cache/baseline; launch b03@16 andc02@16 throughfixedcommands.
Resume only by existingmanifest/worldindexmodulo16 withnewexecution/monitorlabel
and registered technicalincident receipt. Never reruncompleted games.

23:53Z inventory ETA clarification to coordinator's queued sharding instruction:
Inventory remaining ETA: 0 minutes; no archive family remains unfinished or
projects past1hour. Authorized parallelization already completed:31 disjoint
shards plus manager on02/03/04,7plusmanager on01/08, nice19/ioniceidle and
single-threaded math libraries. Deterministic merges and completed single-process
subset comparisons passed. End times:03 22:13:06Z;04 22:18:48Z;08 22:32:52Z;
01 22:42:26Z;02 22:57:29Z. Expanded source/config/test/checkpoint/dataset roots
also complete.07 remains unreachable and uses the coordinator-approved off-host
job bounds; f35's genuine32bitdraw gap is covered by the approved wide namespace.
04uses the coordinator-accepted preserved03mergedarchive, not overwrittenlive
shards. No remaining archive stream needs an index shortcut or a new5%sample.
Completed full scans and existing binding/equivalence checks remain the evidence;
no retroactive index-only substitution and no redundant rescans launched.

Reverified merged audit44af35a20b912933ecab37ff44794632af9f92565af0ceaefc76ebcf5b1ad4e1:
4356proposedseeds;26434historicalvalues;94rawerrorswithresolutions;0unresolved,
0intersections. All393files in sealed r3 index remain byte-stable.
Current critical path is required final independent delta review, not inventories.
Both PREREGs remain unfrozen and no gate games have started. The reviewed
execution bundle is staged; freeze BOTH and launch only after approval arrives.

Coordinator message labelled~00:28Z confirms R20 decision:
Keep sealed secondary order B0,B1,A0,A1. The older21:35Z interleave instruction
is explicitly superseded. R20review allowed stated-order/per-host-timingfallback;
R2review§4 accepted it ondedicated03. No new pre-freeze delta, no PREREG/source/H
change. Per-host timing stays in registered reporting. Coordinator has informed
finaldelta reviewer; this is a decision record, not an approval tofreeze.

Gate(b) wall-time projection from r13's32games at16workers,179.10s elapsed:
1152/32*179.10=6447.6s=1.791h; operational budget2–2.5h plus prolongedexternal
pauses. This scales qualification throughput, not outcomes, and does not change
fixedcounts or admission. Actual elapsed/CPU/resource use will be reported.
Gate(c) preliminary capacity projection from02widequalification20games across
5routeworkers:365.93s wall and1424.81CPU seconds. CPU-scaled1792games/16workers
is2.22h; slowest-route conservativewall scaling2.85h; allow3–4h for route/deck
mix, per-world startup and pauses. These are planning estimates, not guarantees.
Both gates can run concurrently ontheir separate frozenhosts afterBOTHfreeze.

R15/R16/R18/R19 checks againstqueued21:35Zmessage are already inr3evidence:
sourceparity receipts includehost/UTC/tree;4096CPUdevrowsPASSmaxΔ1.144409e-5,
identicalmasks/top8;02/03stackmatchesincludingnumba0.63.1 andenvironmenthash
4f99be7e0d350f39fa15f986e990e1682a3d47cfbf22092a2f3ceae824dd1a5c;
current-qualifiedBvsApilot/r13 andcrosshostcactionchecksPASS. Detectionbounduses
laterpooled120467Bdecisions(~2.5e-5),withthezero-tolerancebarunchanged.
Finaldelta approval remains outstanding. No frozenmanifest/no gate game.

2026-10-08T23:56:24.856648+00:00 R17ownerreceipt read-only verification PASS.
Owner receipt reports/strategy_council_20260928/live-loop/v4/l1/receipts/inference-sharing-20261008/cache03-affinity-r17-20261008-2253.json
SHA256 0852e20bad52ed3a966bea0e4fb1dbb0e39f1f2e815e85256467ddcd8814b5e3; actualownerUTC 2026-10-08T22:53:39.423581+00:00.
LivePID3838563/start128394416 matches; everythread exactly48–63,112–127.
Evidence imitation/gates-bc/receipts/r17-owner-receipt-verification-r3.json. No service affinity changed.
Threshold grids remainexcluded from03 duringgateb. TrustreceiptUTC,notapproximate
coordinator-message timestamps. CanonicalPREREGs/H/sealedr3indexunchanged.

2026-10-08T23:56:59.896146+00:00 Final independent delta review launched bycoordinator
on exactcanonicalb7524a4e1…/c8d565be1…/index5575fb39…/snapshot016b42fa…;
review output imitation/reviews/GATES-BC-PREREG-REVIEW-R3-DELTA-20261009.md.
Allcanonicalhashes and everyimmutablesnapshotfile reverifiedunchanged.
No canonicaledits duringreview. Executionbundles already30filesperhost staged
andverified03/02; approval.json absent, freeze/launch notexecuted.
Coordinator confirms v4rsync196329/196314 drained and no perception bulk source
on03 duringgateb. Markerremainsreserved. Next gatebstart stillrequiresfresh
quiet/load/cache-affinity check and approvedbaselineguard; bothgatesmustfreeze
beforeeither starts. Await exact-hash approval; reviewlaunch isnotapproval.

2026-10-09T00:10:09.938359+00:00 Coordinator APPROVED FOR FREEZE received.
FinalreviewSHA f199e096c3574dc6b4bf256cccd4a8b82f37ead4cc4d42338ddf1cad9707cf06
verified; exactcandidate b7524…/c8d565…/fullsnapshot016b… remains unchanged.
F2 finalreview and correct per-gate approval.json staged inboth evidencebundles.
F1initialdelta23:47Z→00:08Z:41knownjobs,0unknown/intersection; closingdelta will
runimmediatelybeforefreeze. F3all114snapshotfiles/491runtimeinputs/checkpoint/
32stagedfiles perhost PASS;currentPython/Torch/NumPy/Numba/envhashidentical.
07NoRoute. O4stale04merge labelled bysidecar, originalindexedbytes preserved.

L1freshbaseline03 label gates-bc-baseline-prelaunch-final-v1 PID249782 running;
path /mpac/sdicks02/repos/clasher-eval-snapshots/runs/baseline-prelaunch-final-v1/.
Exact argv receipts/freeze-launch-v1/baseline-launch.json; neverduplicateactivejob.
Console0,markerpresent. Collect>=300sresult andrequireempty nonbaselineoverlap;
archivebesideexecution-1/admission.json afterlaunchercreatesdirectory.
Optionalnew-overlap monitor extension DECLINED; no pinnedoperation change.
ExistingapprovedbaselineCPUmonitor remainsunchanged. No gategamesyet.
Freeze/launchargv remainindexed execution-commands.json. Bothfreeze beforeeither
launch. Gateb03@16 ceiling20;gatec02@16 ceiling64sharingqualifiedv4GPUhost.

2026-10-09T00:14:55.836817+00:00 BOTH FROZEN; GATES LAUNCHED.
F1closingledgerPASS13knownjobs inlastdelta;F2review+approvalpinned;F3allbytesexact,
07offline. L1fresh302.37894s baselineavg0.00476224core,peak0.01190558core;
nonbaseline_overlapping=[],console0,markerpresent,cacheexact. Freshquiet recheck
immediatelybeforelaunchPASS. L1capture archivedbesidebexecution-1/admission.json.

Gateb03 label imitation-gate-b-v1-r1 wrapperPID268887;
gatec02 label imitation-gate-c-v1-r1 wrapperPID530957.
ExactUTC/manager/16workerPIDs inreceipts/freeze-launch-v1/launch-summary.json;
exactexecutedargv in game-launches.json. Both16workers started, noHALT/exit.
Paths: /mpac/sdicks02/repos/clasher-eval-snapshots/confirmation-bc-v1/gate-{b,c}/
with games/,execution-1/{launch,admission,resources,exit}.json[ l ] andb/baseline-1/.
Wrapper logs/exits/PIDs under /mpac/sdicks02/jobs/clasher/<label>.{log,exit,pid}.
Initialhostloads03=1.65,02=7.56. Nooutcome/timingcontents inspected.

b frozenPREREG50823cd38a4406bd45839e6de083cd3d00cc74458c9fdd0e647fbbaf3ec36023,
manifest18f08db24a1474491c2a86e303f23dbe0f18ae834ca0d7692f2ebeca822ce858.
c frozenPREREGaed4478bd764a14037e54cf58f8dfab023fcde7ae38407958629a5f4e1896666,
manifest99ab97a8f557e86bfd373496dd059bf8bca4e027d052702f352f1ae429bc01eb.
Frozen copies mirrored to imitation/gate-{b,c}/PREREG.frozen.md;canonicalapproved
DRAFTbytes remain unchanged. Freezeexit0both;Hroundtrip verifiedexact.
Expectedb1.8hgames/budget2–2.5h,c3–4hplanning,pluspauses/replay/reporting.

Resume commands must use same frozenmanifest,host,16workers/modulo16. Firstread
verifiedPIDs/exit/HALT only;neverduplicateactiveworkers. For genuineexternal
technicalincident only: registeredprepare_resume withincident+newattemptlabel,
preservecompletegames;newexecution-N/baseline-N. Anygameexceptionstops gate;
doNOTreplaytoeraseit. No partialanalysis. Afterfullcompletion: outcome-blind
replay everyreject,registeredspot/role/legal checks,thenanalysisandRESULTS.

2026-10-09T01:17:44.189564+00:00 Gate (b) execution COMPLETE, exit 0 at 01:10:47.857417Z.
All 1,152 terminal game receipts and exact scheduled keys present. No strength
analysis yet. Gate (c) remains active on 02 under its frozen 16-worker map.
B verification on 03: gates-bc-b-verification-v1, wrapper PID 762778,
24 rejection-bearing games selected for outcome-blind recorded-action replay;
output confirmation-bc-v1/gate-b/analysis/rejection-replay.json.
Four fixed R12 prefixes: gates-bc-b-spot-verification-v2, wrapper PID 776591;
output analysis/spot-replay.json. Exact launch/resume argv are in
receipts/gate-b-completion-v1/{verification-launch,spot-launch-v2}.json.
Never duplicate an active label. V1 helper failed before producing results:
native search rejects an infinite deadline; archived before/after helper hashes
and retained failure in spot-helper-repair.json. V2 uses a finite one-hour
budget for originally complete prefix roots. This is verification only, with
no new gate games and no changes to frozen serving or analysis.

R12 verification limit (coordinator explicitly accepted actual ~01:18Z): original
receipts retain seeds/decks, actions, candidate counts and deadline flags but
not original full candidate-list hashes or an initial-state hash. Direct equality
to the unrecorded original lists cannot be asserted. Check first four fixed
world/arm/seat prefixes through the last non-truncated root, exact recorded
non-truncated actions/counts; require two independent deterministic replay
candidate-list/public-state hashes to agree; retain all recorded B-root count
assertions. Report limitation in RESULTS. No score adjustment, new games or
change to decision rule. Future registrations should log the candidate-list
hash per root and initial-state hash per game. After replay and registered
analysis, remove only the authorized 03 reservation marker and notify coordinator.

2026-10-09T01:23:48.265349+00:00 R12 spot checks PASS (spot-summary.json):
four fixed prefixes, two independent deterministic replays each; 1,434 decisions,
111 candidate lists and six B count-assertion roots per replay. All non-truncated
recorded commands and retained counts match; duplicate candidate-list and initial
public-state hashes match. No claim about unrecorded original full lists/state.
R19 full replay remains active; 70 rejects in 24 games, 3,508 recorded non-wait
commands across 123,568 simulated ticks. Analysis waits for its receipt.

B load handling is recorded in load-pauses.json: 1,190 worker-level admission
wait records (overlapping 5-second waits, not additive wall time), max sampled
load1=21.3. Pinned may_start checks and pauses each new game above 20; running
games finish unchanged. No HALT.json, all 16 completion markers present. The
baseline bound passed at average .004158 core and peak5s .013956 core.

C progress at 01:22:26Z: 147 completed P16 two-seat world receipts (96 v1,
51 s2902 in block0), no exit. At this early aggregate rate, the 704 P16/H2H
worlds alone project about 5.5h from launch, plus C56; the original 3–4h planning
estimate was optimistic. Later protocol costs differ, so no precise finish ETA
yet. Frozen 02@16 stays unchanged. No gate(c) outcomes inspected.

2026-10-09T01:29:50.912932+00:00 GATE (b) COMPLETE — PASS. Report: imitation/RESULTS-gate-b.md
Report SHA256 bb1adf3f83f0afcc30967c767080193ef0f85ec87cf0896d1de3db3c41332d40.
All 1,152 games retained. Primary B420/D0/L220, score .656250, paired-world
95% CI [.628125,.684375], 320 worlds. Secondary B−A +.05078125,
95% descriptive CI [.01953125,.0859375]. B p99 200.286562ms, A200.236560ms;
B max202.825966ms, zero >250ms. All strength/timing/integrity bars PASS.
77,381 B-root count assertions match. Role/prior/deck/frozen-input audits PASS.
R19 PASS: 24 histories, 3,508 commands, all70 rejects reproduced and classified
(67 payload,3 building); B10/A24/script36. No rejection or score adjustment.
R12 prefix PASS with the previously disclosed absence of original list/state
hashes; recommendation to log these in future registrations stands.

All five application-time mask flags (B3/scripts2, every flag seat1) reproduced
under an additional descriptive command replay. Every flagged command was legal
before either seat applied a command; seat0 application changed the mask before
seat1's audit. Engine responses match: three rejected, two accepted. No change
to the registered bars or serving. Receipt legality-apply-order.json. Helper
label gates-bc-b-legality-explanation-v1 PID803636 exited0; analysis label
gates-bc-b-analysis-v1 PID800439 exited0. Their complete argv are in local
receipts/gate-b-completion-v1/{legality-launch,analysis-launch}.json.

Gate wall 3399.260s; game child CPU17.2919475h; enclosing gate/monitor wrapper
plus all verification attempts and analysis CPU17.6302472h. Peak summed gate
PSS13.280GiB. No GPU used. Load pauses and helper failure retained in report.
Qualification/shared seed audit preflight costs are separate, not included in
these gate execution figures. Full compute/provenance/receipt hashes in
receipts/gate-b-completion-v1/completion-index.json and compute.json.

03 RELEASED at 2026-10-09T01:28:07.985887Z. All six relevant wrapper PIDs
verified absent and exits retained; authorized empty GATES-03-RESERVED marker
removed. release-03.json records metadata and authorization. Coordinator
notified. No remaining gate(b) job or reservation; do not resume completed(b).
B becoming the default is the registered gate decision; this worker has not
changed any live consumer deployment/configuration.

Gate(c) remains imitation-gate-c-v1-r1 on02, wrapper530957/manager530970,
16 workers, original execution-1 and immutable manifest. It has no verdict yet.
To inspect safe liveness (not outcomes):

```bash
ssh 127x02 'test ! -e /mpac/sdicks02/jobs/clasher/imitation-gate-c-v1-r1.exit || cat /mpac/sdicks02/jobs/clasher/imitation-gate-c-v1-r1.exit; tail -n 1 /mpac/sdicks02/repos/clasher-eval-snapshots/confirmation-bc-v1/gate-c/execution-1/resources.jsonl'
```

Exact existing launch argv: receipts/freeze-launch-v1/game-launches.json gate c.
No resume is needed or allowed while active. An actual external interruption
must first get its registered incident/prepare_resume receipt and a fresh label
and execution-N path; never blindly relaunch or overwrite completed receipts.

2026-10-09T07:12:45.724512+00:00 Gate(c) completed on02 at06:54:07.177993Z,
execution exit0, all16 workers0, wall23999.174s. Coordinator released02 to v4;
NO new worker launched on02. Read-only rsync -rc copied only our complete
confirmation-bc-v1/gate-c/ bundle (~40MB) directly02→03, same absolute path.
No raw game dumps copied to05. Post-processing is on03, nice10, CPU-only.

Completeness:384 C56 game receipts,704 two-seat P16/H2H legality+adapter receipts,
1,792 games total,16 completion markers; originalmanifest99ab97a8… unchanged.
R19 outcome-blind recorded-action replay: gates-bc-c-verification-v1 PID1739393,
taskset48–51, nine rejection-bearing games/25 rejected commands. Output:
confirmation-bc-v1/gate-c/analysis/rejection-replay.json on03.
R12 action-stream spots: gates-bc-c-spot-verification-v1 PID1742541,
taskset16–23, first world/both seats of each five routes (10 replayed games).
The PREREG requires spots but gives no count/selection; this fixed choice was
made before outcome analysis, and will be disclosed. Replay outputs stay in
analysis/spot-routes/ and cannot enter the canonical game analysis root.
Serving/analysis bytes unchanged. Exact argv and resume labels are in
receipts/gate-c-completion-v1/{verification-launch,spot-launch}.json.
No duplicate active labels, no new gate worlds, no outcome analysis yet.

2026-10-09T07:14:25.563759+00:00 R12 action-stream spots PASS, all10games,
allfive routes; original vs replayed command hashes/actions, decks/reset metadata,
ticks, terminal status and legality/rejection audits exactly equal. Manifest
inputs verified578/578. New helper only orchestrates the frozen serving paths;
no score comparison. R19 remains active; analysis still waits for its receipt.
Execution resource audit:3708 samples, maxload24.64,0above64,0admission waits,
noHALT. CPU child372179.951362s; peakPSS11982291968bytes. Fullcompute pending
verification/analysis completion. Only compact receipts/logs mirrored to05.

2026-10-09T07:18:38.535275+00:00 GATE(c) COMPLETE. Both registered decisions PASS;
there is no combined PASS in the frozen PREREG. Report imitation/RESULTS-gate-c.md,
SHA256 a9610429b7241cd564dab9e8d6a31d295563110c399feb449e7d6c5642c9537d.
P16 v1:191W/0D/193L of384,49.739583%; natural66W/0D/318L,17.1875%;
exact paired McNemar p5.83635188709137e-25,discordances144/19. P16 PASS.
s2902:162W/0D/222L,42.1875%; v1−s2902 +.0755208333,
Newcombe95% CI [.0050471302,.1449436515], descriptive/no bar.
H2H:170W/0D/86L of256,score.6640625,paired-world95%CI
[.61328125,.71484375]; replacement criterion PASS,replace s2902 asP16reference.
C56:319W/0D/65L of384,score.8307291667,paired95%CI
[.7890625,.8697916667],descriptive only. Allper-cell/style outputs inreport.
No live consumer deployment/configuration was changed by this worker.

All1792 games included. Frozen completeness/seed/deck/level/role/manifest audits
PASS; no truncated P16/H2H games. Instrumented v1 illegal0;C56illegal0/0.
Legacy P16 candidate-illegal fields are null (not certified zero); limitation
explicit inreport. R19 PASS:25occupancy rejects across9C56histories (4v1,
21scripts),all knownTimedExplosive.blocks_deployment;863commands replayexact.
No P16/H2H rejects,no replay mismatch protocols. R12all10spotsPASS. Only
post-exit procedural clarification: PREREG did not specify spot count/selection;
firstworld/bothseats per5routes fixed before outcome analysis and disclosed.
No extra outcomeanalysis,adjustedscore,discardedgame or serving/statistic change.

03postprocessing labels all exited0; wrapperPIDs absent:
gates-bc-c-verification-v1/1739393 (254.40s wall),
gates-bc-c-spot-verification-v1/1742541 (87.88s wall),
gates-bc-c-analysis-v1/1756090 (2.91s wall).
Exactargv and smallstdout/exit/compute/provenance/hash receipts are in
receipts/gate-c-completion-v1/, sealedbycompletion-index.json.
Raw originals02 confirmation-bc-v1/gate-c/games/; checksumcopy03samepath;
verification/analysis outputs03 confirmation-bc-v1/gate-c/analysis/.
Onlydocs/compactreceipts on05. Nothingfurther launchedon02; it remainsreleased.
No03reservation recreated; allpostprocessingfinished. No resume needed: both
registered gates are complete; do not rerun worlds. An independentlyregistered
future experiment would require its own seeds and approval.

Compute:gate02 wall23999.173743s,childCPU103.3833198h,peakPSS11.159GiB;
including enclosinggate/manager and03verification/analysis wrappers105.0531722h.
These overlappingCPUfigures mustnotbesummed. NoGPUused. Maximumsampledload24.64,
ceiling64,zero loadpauses/HALT/restarts. Sharedqualification/inventorypreflight
costs are outside these executionfigures, asdisclosed inreport.
BothcanonicalapprovedPREREGhashes remainunchanged. Gate(a)outcomes neverused.
